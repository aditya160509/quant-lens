"""Filtered regime probabilities and genuine conditional portfolio optimization."""

import numpy as np
from ..core.context import load_context, feature_meta
from ..core.common import response, matrix_records
from ..core.stats import portfolio_return_series, performance_metrics
from ..core.regimes import (
    causal_regimes,
    regime_allocations,
    kaplan_meier_survival,
    regime_factor_performance,
)
from ..core.data_loader import load_macro

from .inputs import inputs_for, output

FEATURE_ID = "06"
FEATURE_NAME = "Market Regime Detection and Regime-Aware Allocation Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    returns = ctx["returns"]
    port = portfolio_return_series(returns, ctx["weights"])
    records, transition = causal_regimes(
        port,
        load_macro(),
        int(payload.get("regime_count", 3)),
        int(payload.get("regime_min_train", 126)),
        int(payload.get("regime_refit_interval", 21)),
        payload.get("regime_model", "hmm"),
        payload.get("transition_structure", "homogeneous"),
    )
    if records.empty:
        raise ValueError("No matching observed regime dates")
    conditional, mixture, issues = regime_allocations(
        returns, records, payload.get("objective", "global_min_variance")
    )
    states = records.set_index("date").regime
    performance = []
    covs = []
    for k in states.unique():
        sample = returns.reindex(states.index[states.eq(k)]).dropna()
        if len(sample) > 1:
            performance.append(
                {
                    "regime": int(k),
                    **performance_metrics(
                        sample @ ctx["weights"], ctx["annualization_factor"]
                    ),
                }
            )
            covs.extend(
                {"regime": int(k), **row} for row in matrix_records(sample.corr())
            )
    trans = (
        []
        if transition is None
        else [
            {"row": str(i), "col": str(j), "value": float(transition[i, j])}
            for i in range(len(transition))
            for j in range(len(transition))
        ]
    )
    latest = records.iloc[-1]
    state = int(latest.regime)
    pchange = float(1 - latest[f"probability_{state}"])
    if transition is not None:
        probabilities = np.array(
            [latest[f"probability_{k}"] for k in range(len(transition))]
        )
        pchange = float(1 - probabilities @ transition[:, state])
    severity = "red" if pchange > 0.5 else "amber" if pchange > 0.3 else "clear"
    alerts = (
        []
        if severity == "clear"
        else [
            {
                "severity": severity,
                "message": "Probability of leaving current state exceeds declared 30%/50% threshold",
                "probability": pchange,
            }
        ]
    )
    return response(
        FEATURE_ID,
        [{"label": "Current Regime", "value": state}],
        {
            "regime_timeline": records.to_dict("records"),
            "transition_matrix": trans,
            "regime_conditional_correlation": covs,
        },
        {
            "regime_performance": performance,
            "regime_conditional_weights": conditional,
            "regime_mixture_weights": mixture,
            "survival_curves": kaplan_meier_survival(states),
            "asset_performance_by_regime": regime_factor_performance(returns, states),
            "regime_alerts": alerts,
        },
        meta={
            **feature_meta(ctx, issues),
            "model": payload.get("regime_model", "hmm"),
            "probabilities": "Prefix-fitted filtered probabilities; no full-sample scaling, backward smoothing or fallback classifiers",
            "transition_structure": payload.get("transition_structure", "homogeneous"),
        },
        alerts=alerts,
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("regime_timeline", "charts", "line", True),
    output("transition_matrix", "charts", "heatmap", False),
    output("regime_conditional_correlation", "charts", "heatmap", False),
    output("regime_performance"),
    output("regime_conditional_weights"),
    output("regime_mixture_weights"),
    output("survival_curves"),
    output("asset_performance_by_regime"),
    output("regime_alerts"),
]
