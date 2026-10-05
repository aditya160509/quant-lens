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
from .common import date_str, matrix_records, response, summary
from .panel import load_context


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
    probabilities = probabilities[:,order]
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
    alerts = [{"level":"info","message":f"Current state {labels[-1]+1} probability exceeds configured threshold"}] if probabilities[-1].max()>=alert_threshold else []
    transition_rows = matrix_records(pd.DataFrame(transition,index=[f"state_{i+1}" for i in range(states_count)],columns=[f"state_{i+1}" for i in range(states_count)]))
    return response("06",[summary("Current State",int(labels[-1]+1),"state"),summary("Correlation network density",density,"ratio")],
        charts={"regime_probability_time_series":rows,"regime_transition_heatmap":transition_rows,
            "ensemble_vs_hmm_comparison":[{"oos_agreement":float(np.mean(classified==labels)),"observations":len(labels)}],
            "pc1_variance_monitor":pc1,"regime_conditional_asset_returns":conditional,
            "correlation_network_density":[{"density":density,"absolute_correlation_threshold":threshold}],
            "parallel_gmm_regime_probabilities":gmm_rows},
        tables={"transition_matrix":transition_rows,"current_regime_probabilities":[rows[-1]],
            "training_audit":[{"train_dates":cut,"test_dates":len(oos_dates),"training_end":date_str(features.index[cut-1]),"hmm_converged":bool(model.monitor_.converged)}]},
        alerts=alerts,meta={"probability_protocol":"forward_filter_no_backward_smoothing","fit_protocol":"fixed_train_only_60_percent",
            "state_ordering":"training_mean_returns_only","macro":"excluded_without_release_vintages",
            "conditional_returns":"descriptive_same_period; not strategy attribution","gmm":"parallel_model_not_fallback"})
