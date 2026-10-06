"""Train-only Gaussian regime models with causal forward filtering."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import multivariate_normal
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from .common import build_provenance, date_str, matrix_records, put_artifact, response, series_hash, summary
from .data_loader import universe_label
from .panel import load_context
from .performance import max_drawdown, sharpe


def forward_filter(model, observations):
    """P(state_t | observations through t), with no backward smoothing."""
    log_transition = np.log(np.maximum(model.transmat_, 1e-300))
    prior = np.log(np.maximum(model.startprob_, 1e-300))
    probabilities = []
    for index, observation in enumerate(observations):
        if index:
            prior = logsumexp(posterior[:, None] + log_transition, axis=0)
        emissions = np.array([multivariate_normal.logpdf(observation, mean=model.means_[state],
            cov=model.covars_[state], allow_singular=False) for state in range(model.n_components)])
        posterior = prior + emissions
        posterior -= logsumexp(posterior)
        probabilities.append(np.exp(posterior))
    return np.asarray(probabilities)


def filtered_stress_probability(returns: pd.Series, train_n: int, seed: int = 7) -> pd.Series | None:
    """P(stress_t | returns up to t): a two-state Gaussian HMM fit on the first ``train_n`` returns, then forward-filtered.

    Stress is the state with the larger fitted variance. No smoothing, so a value never changes when later returns arrive.
    Returns None when the fit fails or the two states are not separated.
    """
    from hmmlearn.hmm import GaussianHMM
    clean = returns.dropna()
    if train_n < 60 or len(clean) <= train_n:
        return None
    scaled = (clean.to_numpy() * 100.0).reshape(-1, 1)
    try:
        model = GaussianHMM(n_components=2, covariance_type="full", n_iter=100, tol=1e-4, random_state=seed, min_covar=1e-4).fit(scaled[:train_n])
        variances = np.array([float(model.covars_[k].reshape(-1)[0]) for k in range(2)])
        if not np.all(np.isfinite(model.transmat_)) or variances.max() < 1.2 * variances.min():
            return None
        return pd.Series(forward_filter(model, scaled)[:, int(variances.argmax())], index=clean.index, name="stress_probability")
    except (ValueError, np.linalg.LinAlgError):
        return None


def run_regime_engine(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from hmmlearn.hmm import GaussianHMM
    ctx = load_context(payload, min_symbols=12)
    market = ctx.returns.mean(axis=1, skipna=False)
    rolling = market.rolling(21)
    available = pd.DataFrame({"returns":market,"realized_vol":rolling.std()*np.sqrt(ctx.annualization),
        "rolling_sharpe":rolling.mean()/rolling.std()*np.sqrt(ctx.annualization),
        "skew":rolling.skew(),"kurtosis":rolling.kurt()})
    selected = ctx.payload.get("input_features",["returns","realized_vol"])
    if not isinstance(selected,list) or not selected or set(selected)-set(available.columns):
        raise ValueError("Select supported price-derived input_features; vintage macro inputs are not supported")
    features = available[selected].replace([np.inf,-np.inf],np.nan).dropna()
    cut = int(len(features)*.6)
    states_count = int(ctx.payload.get("hmm_state_count",3))
    components = int(ctx.payload.get("gmm_component_count",3))
    if cut < 60 or len(features)-cut < 20:
        raise ValueError("Insufficient complete dates for train-only regime fitting")
    scaler = StandardScaler().fit(features.iloc[:cut])
    scaled = scaler.transform(features)
    model = GaussianHMM(n_components=states_count,covariance_type="diag",n_iter=200,tol=1e-4,
                        random_state=7,min_covar=1e-3).fit(scaled[:cut])
    if not np.all(np.isfinite(model.transmat_)):
        raise ValueError("HMM fit produced invalid transition probabilities")
    probabilities = forward_filter(model,scaled)
    training_labels = probabilities[:cut].argmax(axis=1)
    means = [market.reindex(features.index[:cut])[training_labels==state].mean() for state in range(states_count)]
    # Empty training states sort last; do not create a fictitious return mean.
    order = np.argsort([-float(v) if pd.notna(v) else np.inf for v in means])
    # Stress is the state with the highest training-window market volatility, whatever its return ordering.
    market_vol = market.rolling(21).std().reindex(features.index[:cut])
    state_vol = [market_vol[training_labels==state].mean() for state in range(states_count)]
    stress_state = int(np.argmax([v if pd.notna(v) else -np.inf for v in state_vol]))
    # Plain names by training-window volatility rank: lowest is Calm, highest is Stress, anything between is Normal.
    vol_rank = np.argsort(np.argsort([v if pd.notna(v) else np.inf for v in state_vol]))
    def _name(state: int) -> str:
        return "Stress" if state == stress_state else "Calm" if vol_rank[state] == 0 else "Normal" if states_count == 3 else f"Normal {vol_rank[state]}"
    probabilities = probabilities[:,order]
    stress_series = pd.Series(probabilities[:,int(np.flatnonzero(order==stress_state)[0])],index=features.index)
    labels = probabilities.argmax(axis=1)
    oos_dates = features.index[cut:]
    probabilities = probabilities[cut:]; labels = labels[cut:]
    transition = model.transmat_[np.ix_(order,order)]
    classifier = RandomForestClassifier(n_estimators=80,max_depth=4,random_state=7,n_jobs=1)
    classifier.fit(scaled[:cut],forward_filter(model,scaled[:cut])[:,order].argmax(axis=1))
    classified = classifier.predict(scaled[cut:])
    gmm = GaussianMixture(n_components=components,random_state=29).fit(scaled[:cut])
    gp = gmm.predict_proba(scaled[cut:])
    rows = [{"date":date_str(date),"dominant_state":int(prob.argmax()+1),
             **{f"state_{j+1}":float(v) for j,v in enumerate(prob)}} for date,prob in zip(oos_dates,probabilities)]
    gmm_rows = [{"date":date_str(date),**{f"component_{j+1}":float(v) for j,v in enumerate(prob)}} for date,prob in zip(oos_dates,gp)]
    pc1 = []
    window = int(ctx.payload.get("pc1_window",63))
    for position in range(window,len(ctx.returns)):
        history = ctx.returns.iloc[position-window:position].dropna()
        if len(history) >= 20 and history.var().sum()>0:
            ratio = PCA(n_components=1).fit(history).explained_variance_ratio_[0]
            pc1.append({"date":date_str(ctx.returns.index[position]),"pc1_explained_variance":float(ratio)})
    threshold = float(ctx.payload.get("random_graph_threshold",.45))
    alert_threshold = float(ctx.payload.get("regime_alert_threshold",.65))
    if not 0<=threshold<=1 or not 0<=alert_threshold<=1:
        raise ValueError("Correlation and alert thresholds must be between zero and one")
    correlation = ctx.returns.tail(126).dropna().corr()
    edge_values = correlation.to_numpy()[np.triu_indices(len(correlation),k=1)]
    density = float((np.abs(edge_values)>threshold).mean()) if len(edge_values) else None
    aligned = ctx.returns.reindex(oos_dates)
    conditional = [{"asset":ticker,"regime":int(state+1),"mean_log_return":float(values.mean()),"observations":int(values.count())}
        for state in range(states_count) for ticker in aligned
        if len(values := aligned.loc[labels==state,ticker].dropna())]
    exposure = (1-stress_series.reindex(oos_dates)).shift(1).fillna(1-stress_series.iloc[cut-1])
    market_oos = market.reindex(oos_dates)
    controls = {"regime_filtered":exposure,"constant_exposure":pd.Series(float(exposure.mean()),index=oos_dates),"unmanaged":pd.Series(1.,index=oos_dates)}
    exposure_rows = []
    for name,weight in controls.items():
        strategy = weight*market_oos
        exposure_rows.append({"strategy":name,"average_exposure":float(weight.mean()),"annual_return":float(strategy.mean()*ctx.annualization),
            "annual_volatility":float(strategy.std()*np.sqrt(ctx.annualization)),"sharpe":sharpe(strategy.to_numpy(),ctx.annualization),
            "max_drawdown":max_drawdown(np.exp(strategy.fillna(0).cumsum()).to_numpy())})
    artifact_id = put_artifact("regime",{"stress_probability":{date_str(d):float(v) for d,v in stress_series.items()},"universe":sorted(ctx.symbols),
        "series_hash":series_hash(stress_series),"as_of":date_str(stress_series.index[-1])})
    provenance = build_provenance(ctx.closes,calendar=ctx.calendar,train_window=(features.index[0],features.index[cut-1]),
        test_window=(oos_dates[0],oos_dates[-1]),purge=0,embargo=0,universe=universe_label(ctx.payload,ctx.symbols))
    alerts = [{"level":"info","message":f"Current state {labels[-1]+1} probability exceeds configured threshold"}] if probabilities[-1].max()>=alert_threshold else []
    transition_rows = matrix_records(pd.DataFrame(transition,index=[f"state_{i+1}" for i in range(states_count)],columns=[f"state_{i+1}" for i in range(states_count)]))
    stay=float(1/max(1-transition[labels[-1],labels[-1]],1e-9))
    now_stress=float(stress_series.iloc[-1])>=.5
    sharpes={r["strategy"]:r["sharpe"] for r in exposure_rows}
    cards=[summary("Regime","stress" if now_stress else "calm","state"),summary("Stress probability",float(stress_series.iloc[-1]),"%"),
        summary("Expected stay",stay,"days"),summary("Filter vs constant exposure",sharpes["regime_filtered"]-sharpes["constant_exposure"],"Δ Sharpe")]
    return response("06",cards,
        charts={"regime_probability_time_series":rows,"regime_transition_heatmap":transition_rows,
            "ensemble_vs_hmm_comparison":[{"oos_agreement":float(np.mean(classified==labels)),"observations":len(labels)}],
            "pc1_variance_monitor":pc1,"regime_conditional_asset_returns":conditional,
            "correlation_network_density":[{"density":density,"absolute_correlation_threshold":threshold}],
            "parallel_gmm_regime_probabilities":gmm_rows},
        tables={"transition_matrix":transition_rows,"current_regime_probabilities":[{**rows[-1],"stress_probability":float(stress_series.iloc[-1])}],
            "regime_vs_constant_exposure":exposure_rows,
            "training_audit":[{"train_dates":cut,"test_dates":len(oos_dates),"training_end":date_str(features.index[cut-1]),"hmm_converged":bool(model.monitor_.converged)}]},
        alerts=alerts,provenance=provenance,meta={"artifact_id":artifact_id,"stress_state":int(np.flatnonzero(order==stress_state)[0]+1),
                                     "state_labels":{f"state_{i+1}":_name(int(order[i])) for i in range(states_count)},
                                     "state_volatility":{f"state_{i+1}":(float(state_vol[int(order[i])]*np.sqrt(252)) if pd.notna(state_vol[int(order[i])]) else None) for i in range(states_count)},"stress_definition":"state with the highest training-window market volatility",
            "exposure_rule":"exposure = 1 - stress probability, applied to the next session; constant control uses the same average exposure",
            "probability_protocol":"forward_filter_no_backward_smoothing","fit_protocol":"fixed_train_only_60_percent",
            "state_ordering":"training_mean_returns_only","macro":"excluded_without_release_vintages",
            "conditional_returns":"descriptive_same_period; not strategy attribution","gmm":"parallel_model_not_fallback"})
