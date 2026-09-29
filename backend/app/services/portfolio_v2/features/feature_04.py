"""F04 Portfolio Stress Testing and Scenario Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.analytics import (
    correlation_breakdown_stress,
    feature_meta,
    historical_crisis_replay,
    load_context,
    response,
    reverse_stress_test,
    minimum_mahalanobis_reverse_stress,
    stationary_block_bootstrap_paths,
    stress_scenarios,
)
from ..core.performance import cached_correlation_frame

FEATURE_ID = "04"
FEATURE_NAME = "Portfolio Stress Testing and Scenario Engine"
INPUTS = ["tickers", "weights", "lookback_days", "scenario", "shock_size", "monte_carlo_paths"]
OUTPUTS = ["scenario_waterfall", "scenario_table", "correlation_stress", "monte_carlo", "reverse_stress"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    rets, w = ctx["returns"], ctx["weights"]

    # Single numpy port computation reused everywhere
    w_arr = w.reindex(rets.columns).fillna(0.0).to_numpy(dtype=np.float64)
    ret_arr = rets.to_numpy(dtype=np.float64)
    np.nan_to_num(ret_arr, copy=False)
    port_arr = ret_arr @ w_arr
    mu = float(port_arr.mean())
    sigma = float(port_arr.std())

    stress = stress_scenarios(rets, w)

    # Stationary block bootstrap retains observed volatility clustering instead
    # of assuming independent Gaussian daily returns.
    paths = int(min(float(payload.get("monte_carlo_paths") or 1000), 5000))
    horizon = int(payload.get("horizon_days") or 21)
    blocks = stationary_block_bootstrap_paths(pd.Series(port_arr), paths, horizon, payload.get("bootstrap_block_length"))
    sims = blocks.sum(axis=1)

    # Cache corr, compute avg_corr vectorized
    corr = cached_correlation_frame(rets)
    corr_arr = corr.to_numpy(dtype=np.float64)
    iu = np.triu_indices_from(corr_arr, k=1)
    avg_corr = float(corr_arr[iu].mean()) if len(iu[0]) else 0.0

    threshold = abs(float(payload.get("loss_threshold") or 0.15))
    reverse = minimum_mahalanobis_reverse_stress(rets, w, threshold)
    corr_stress = correlation_breakdown_stress(rets, w)
    historical = historical_crisis_replay(rets, w)
    historical_normalized = [{"scenario": r["scenario"], "portfolio_return": r["return"], "pl_bps": r["return"] * 10000, "worst_day": r.get("worst_day")} for r in historical]

    # Precompute quantiles in one call
    q05, q50, q95 = np.quantile(sims, [0.05, 0.50, 0.95])
    verdict = "red" if q05 < -0.20 else "amber" if q05 < -0.10 else "green"

    # Vectorized MC quantile chart
    quantile_points = np.linspace(0.01, 0.99, 50)
    mc_quantiles = np.quantile(sims, quantile_points)

    hypothetical = payload.get("hypothetical_shocks") or {}
    if isinstance(hypothetical, dict) and hypothetical:
        shock = np.asarray([float(hypothetical.get(c, 0.0)) for c in rets.columns])
        stress["scenario_table"].append({"scenario": "user_defined", "portfolio_return": float(w_arr @ shock), "pl_bps": float(w_arr @ shock * 10000)})
    tables = {
        "scenario_table": stress["scenario_table"] + historical_normalized,
        "correlation_stress": [{"stress_level": "current", "avg_corr": avg_corr}, {"stress_level": "crisis_plus_25pct", "avg_corr": min(1.0, avg_corr * 1.25 + 0.10)}],
        "reverse_stress": [reverse, {"legacy_proportional": reverse_stress_test(rets, w, threshold)}],
        "stress_verdict": [{"verdict": verdict, **corr_stress}],
        "monte_carlo_summary": [{"p05": float(q05), "p50": float(q50), "p95": float(q95), "method": "stationary_block_bootstrap", "block_length": int(payload.get("bootstrap_block_length") or 0) or None}],
    }
    charts = {
        "scenario_waterfall": stress["waterfall"],
        "monte_carlo": [{"quantile": float(q), "return": float(v)} for q, v in zip(quantile_points, mc_quantiles)],
    }
    return response(
        FEATURE_ID,
        [{"label": "5% MC Loss", "value": float(q05), "format": "percent"}, {"label": "Avg Corr", "value": avg_corr}],
        charts, tables, meta=feature_meta(ctx),
    )
