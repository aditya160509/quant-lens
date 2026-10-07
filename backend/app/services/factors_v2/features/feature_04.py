"""Training-only regime fits and causal filtered holdout probabilities."""

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import norm
from hmmlearn.hmm import GaussianHMM
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from app.services.factors_v2.core.analytics import (
    factor_returns,
    response,
    matrix_records,
)
from app.services.factors_v2.core.data_loader import load_category7_macro


def forward_filter(log_emissions, start, transition):
    posterior = []
    previous = np.log(np.maximum(start, 1e-300))
    trans = np.log(np.maximum(transition, 1e-300))
    for i, emission in enumerate(log_emissions):
        prior = previous if i == 0 else logsumexp(previous[:, None] + trans, axis=0)
        previous = prior + emission
        previous -= logsumexp(previous)
        posterior.append(np.exp(previous))
    return np.asarray(posterior)


def run(payload):
    returns = (
        factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    )
    obs = returns.rolling(21).mean().dropna()
    states = int(payload.get("states", 4))
    split = int(len(obs) * 0.6)
    if split < max(80, states * 20):
        raise ValueError("Insufficient training history for requested regime count")
    scaler = StandardScaler().fit(obs.iloc[:split])
    values = scaler.transform(obs)
    hmm = GaussianHMM(
        n_components=states, covariance_type="diag", n_iter=200, random_state=7
    ).fit(values[:split])
    if not hmm.monitor_.converged:
        raise ValueError("HMM did not converge")
    order = np.argsort(hmm.means_.mean(axis=1))
    names = [f"regime_{i + 1}" for i in range(states)]
    var = np.maximum(hmm.covars_.diagonal(axis1=1, axis2=2), 1e-12)
    emissions = norm.logpdf(
        values[:, None, :], loc=hmm.means_[None, :, :], scale=np.sqrt(var)[None, :, :]
    ).sum(axis=2)
    filtered = forward_filter(emissions, hmm.startprob_, hmm.transmat_)
    holdout = pd.DataFrame(
        filtered[split:, order], index=obs.index[split:], columns=names
    )
    macro = load_category7_macro().set_index("date").sort_index()
    # Market-observation rules use prior exact-day data; revised macro releases are not used.
    prior = macro.reindex(returns.index).shift(1)
    rules = []
    for column, threshold, op in [
        ("vix_close", payload.get("vix_threshold", 25), "above"),
        ("yc_slope_10y_2y", 0, "below"),
    ]:
        if column in prior:
            series = prior[column]
            flag = series > threshold if op == "above" else series < threshold
            rules.append(
                {
                    "rule": column,
                    "latest_value": float(series.iloc[-1])
                    if pd.notna(series.iloc[-1])
                    else None,
                    "breached": bool(flag.iloc[-1])
                    if pd.notna(series.iloc[-1])
                    else None,
                }
            )
    gmm_rows = []
    if payload.get("include_gmm", False):
        gmm = GaussianMixture(n_components=states, random_state=7).fit(values[:split])
        if not gmm.converged_:
            raise ValueError("GMM did not converge")
        gmm_rows = (
            pd.DataFrame(
                gmm.predict_proba(values[split:])[
                    :, np.argsort(gmm.means_.mean(axis=1))
                ],
                index=obs.index[split:],
                columns=names,
            )
            .reset_index()
            .to_dict("records")
        )
    dominant = holdout.idxmax(axis=1)
    conditional = []
    for regime in names:
        sub = returns.reindex(holdout.index).loc[dominant == regime]
        for f in sub:
            conditional.append(
                {
                    "factor": f,
                    "regime": regime,
                    "avg_daily_return": sub[f].mean(),
                    "sample": len(sub),
                    "sharpe": sub[f].mean() / sub[f].std() * np.sqrt(252)
                    if sub[f].std() > 0
                    else None,
                }
            )
    return response(
        "feature_04",
        summary_cards=[
            {"label": "Filtered Regime", "value": holdout.iloc[-1].idxmax()},
            {"label": "Confidence", "value": float(holdout.iloc[-1].max())},
        ],
        charts={
            "hmm_probability": holdout.tail(260).reset_index().to_dict("records"),
            "gmm_probability": gmm_rows,
            "current_regime": [
                {"regime": f, "probability": holdout.iloc[-1][f]} for f in names
            ],
        },
        tables={
            "transition_matrix": matrix_records(
                pd.DataFrame(
                    hmm.transmat_[np.ix_(order, order)], index=names, columns=names
                )
            ),
            "conditional_returns": conditional,
            "observed_market_rules": rules,
        },
        meta={
            "states": states,
            "training_end": str(obs.index[split - 1].date()),
            "method": "Training-only standardized Gaussian HMM with causal forward filtering; probabilities reported only on holdout",
            "missing_output_reasons": {
                "composite_probability": "No full-sample future-volatility IC weighting or arbitrary fusion weights",
                "macro_growth_regimes": "Economic release vintages are not verified; model states are statistical regimes",
            },
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("04")
OUTPUTS = _outputs("04")
