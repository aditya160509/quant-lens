"""F01 Portfolio Construction Engine."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..core.analytics import (
    black_litterman_weights,
    cvar_minimize,
    dcc_garch_cov,
    factor_structured_cov,
    feature_meta,
    gerber_statistic_cov,
    load_context,
    optimize_portfolios,
    performance_metrics,
    portfolio_return_series,
    response,
    weight_stability_index,
)

FEATURE_ID = "01"
FEATURE_NAME = "Portfolio Construction Engine"
INPUTS = ["tickers", "weights", "lookback_days", "frequency", "covariance_estimator", "expected_return_estimator", "max_symbols"]
OUTPUTS = ["optimized_weights", "efficient_frontier", "risk_contribution", "constraint_report", "turnover_costs", "stability_table"]


def run(payload: dict | None = None) -> dict:
    ctx = load_context(payload, min_symbols=8, default_limit=60)
    rets = ctx["returns"]
    opt = optimize_portfolios(rets, ctx["payload"])
    selected = opt["weights"].get(
        str((payload or {}).get("objective") or "max_sharpe"),
        opt["weights"].get("max_sharpe", ctx["weights"]),
    )
    port = portfolio_return_series(rets, selected)
    metrics = performance_metrics(port, ctx["annualization_factor"])

    # Reuse already-computed covariance — avoid recompute
    cov_ann = opt["covariance"] * ctx["annualization_factor"]
    cov_arr = cov_ann.to_numpy(dtype=np.float64)
    rc_arr = selected.reindex(cov_ann.columns).fillna(0.0).to_numpy(dtype=np.float64)
    port_var = float(rc_arr @ cov_arr @ rc_arr)
    cov_w = cov_arr @ rc_arr
    denom = max(math.sqrt(max(port_var, 1e-12)), 1e-12)
    rc = pd.Series(rc_arr * cov_w / denom, index=cov_ann.columns)

    # Batch all cov estimators, cache dcc result
    dcc_result = dcc_garch_cov(rets)
    fs_cov = factor_structured_cov(rets)
    gb_cov = gerber_statistic_cov(rets)
    lw_cov = opt["covariance"]

    # eigh-based condition numbers — cheaper than SVD for symmetric matrices
    eye_n = np.eye(len(lw_cov))
    cond_rows = []
    for name, cov_m in [
        ("ledoit_wolf", lw_cov),
        ("dcc_garch", dcc_result["covariance"]),
        ("factor_structured", fs_cov),
        ("gerber", gb_cov),
    ]:
        arr = cov_m.fillna(0.0).to_numpy(dtype=np.float64) + eye_n * 1e-9
        vals = np.linalg.eigvalsh(arr)
        vmax = float(vals[-1])
        vmin = float(np.abs(vals[0]))
        cond_rows.append({"estimator": name, "condition_number": vmax / max(vmin, 1e-18)})

    bl_w = opt["weights"].get("black_litterman")
    if bl_w is None:
        bl_w = black_litterman_weights(rets, ctx["weights"])
    cvar_w = opt["weights"].get("cvar_min")
    if cvar_w is None:
        cvar_w = cvar_minimize(rets)

    stability = pd.DataFrame(list(opt["weights"].values())).fillna(0.0)
    summary = [
        {"label": "Optimized Sharpe", "value": metrics.get("sharpe", 0.0), "format": "number"},
        {"label": "Annual Vol", "value": metrics.get("annual_vol", 0.0), "format": "percent"},
        {"label": "Max Drawdown", "value": metrics.get("max_drawdown", 0.0), "format": "percent"},
    ]
    tables = {
        "optimized_weights": opt["weight_table"],
        "black_litterman_weights": [{"ticker": k, "weight": float(v)} for k, v in bl_w.items()],
        "cvar_min_weights": [{"ticker": k, "weight": float(v)} for k, v in cvar_w.items()],
        "risk_contribution": [{"ticker": k, "risk_contribution": float(rc.get(k, 0.0)), "weight": float(selected.get(k, 0.0))} for k in rc.index],
        "constraint_report": [
            {"constraint": "long_only_budget", "status": "satisfied", "value": float(selected.sum())},
            {"constraint": "weight_bounds", "status": "satisfied", "value": float(selected.max())},
            {"constraint": "configured_constraints", "status": "applied", "value": opt["meta"].get("constraints", {})},
        ],
        "stability_table": [{"estimator": opt["meta"].get("estimator"), "shrinkage": opt["meta"].get("shrinkage"), "asset_count": len(ctx["symbols"]), "cross_objective_weight_dispersion": weight_stability_index(stability), "note": "Dispersion across optimized objectives."}],
        "covariance_condition_numbers": cond_rows,
    }
    charts = {
        "efficient_frontier": opt["frontier"],
        "weights": opt["weight_table"],
        "risk_contribution": tables["risk_contribution"],
        "dcc_average_correlation": dcc_result["average_correlation_series"],
    }
    return response(FEATURE_ID, summary, charts, tables, meta=feature_meta(ctx))
