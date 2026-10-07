"""Observed factor diagnostics without invented classifier training labels."""

import statsmodels.api as sm
from app.services.factors_v2.core.analytics import (
    factor_returns,
    backtest_series,
    response,
    run_feature_module,
)


def run(payload):
    rets = factor_returns(payload)
    target = backtest_series(payload)["column"]
    subset = rets.dropna().tail(int(payload.get("window_days", 756)))
    others = [c for c in subset if c != target]
    fit = (
        sm.OLS(subset[target], sm.add_constant(subset[others])).fit(
            cov_type="HAC", cov_kwds={"maxlags": 21}
        )
        if others and len(subset) > len(others) + 30
        else None
    )
    purity = {
        "alpha_annualized": float(fit.params.iloc[0] * 252) if fit else None,
        "r_squared": float(fit.rsquared) if fit else None,
        "method": "HAC spanning regression on other selected published factors",
    }
    decay = run_feature_module(5, payload)
    crowd = run_feature_module(6, payload)
    metrics = [
        {
            "axis": "IC",
            "value": (decay.get("tables", {}).get("ic_by_horizon") or [{}])[0].get(
                "mean_ic"
            ),
            "unit": "Spearman rho",
        },
        {
            "axis": "Half-life",
            "value": (decay.get("summary_cards") or [{}, {}])[1].get("value"),
            "unit": "sessions",
        },
        {
            "axis": "Annualized spanning alpha",
            "value": purity["alpha_annualized"],
            "unit": "return",
        },
        {"axis": "Spanning R2", "value": purity["r_squared"], "unit": "fraction"},
    ]
    comparisons = []
    for f in payload.get("comparison_factors", []):
        if f == payload.get("factor"):
            continue
        sub = run_feature_module(5, {**payload, "factor": f})
        comparisons.append(
            {
                "factor": f,
                "ic_by_horizon": sub.get("tables", {}).get("ic_by_horizon", []),
            }
        )
    return response(
        "feature_12",
        charts={
            "dna_radar": metrics,
            "correlation_dna": [
                {"factor": c, "correlation": subset[c].corr(subset[target])}
                for c in others
            ],
        },
        tables={
            "dna_vector": metrics,
            "purity_regression": [purity],
            "concentration": crowd.get("tables", {}).get("crowding_metrics", []),
            "comparison_factors": comparisons,
        },
        meta={
            "factor": payload.get("factor", "momentum_12_1"),
            "radar_scaling": "Raw observed units; no arbitrary 0-100 score",
            "missing_output_reasons": {
                "classifier_probability": "No measured labelled academic training set; handwritten archetypes and jitter are removed",
                "return_anatomy": "Correlation shares do not identify economic return sources",
                "macro_growth_rates_dna": "Release-vintage-safe macro regime integration is unavailable",
            },
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("12")
OUTPUTS = _outputs("12")
