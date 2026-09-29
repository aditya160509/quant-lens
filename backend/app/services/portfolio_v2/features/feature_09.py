"""F09 Alpha Decay and Factor Half-Life Engine."""

from __future__ import annotations

import numpy as np

from ..core.analytics import (
    alpha_capacity,
    alpha_decay,
    decay_adjusted_weights,
    decay_model_selection,
    feature_meta,
    hyperbolic_decay_fit,
    load_context,
    optimal_rebalance_frequency,
    response,
)

FEATURE_ID = "09"
FEATURE_NAME = "Alpha Decay and Factor Half-Life Engine"
INPUTS = ["tickers", "lookback_days", "factor_taxonomy", "max_horizon"]
OUTPUTS = ["ic_decay_curve", "half_life_table", "crowding_proxy", "decay_adjusted_weights", "publication_decay"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)

    # Compute decay once, reuse ic_curve everywhere
    decay = alpha_decay(ctx["returns"], max_horizon=int(payload.get("max_horizon") or 63))
    ic_curve = decay["ic_curve"]
    half = decay["half_life"] or 63

    fit = hyperbolic_decay_fit(ic_curve)
    decay_models = decay_model_selection(ic_curve)
    opt_freq = optimal_rebalance_frequency(ic_curve, float(payload.get("transaction_cost_bps") or 10))

    # Vectorized age grid — np.exp on array instead of Python loop
    age_arr = np.arange(0, 126, 5, dtype=np.float64)
    scale_arr = np.exp(-age_arr / max(half, 1))
    age_grid = [{"age_days": int(a), "weight_scale": float(s)} for a, s in zip(age_arr, scale_arr)]

    # Batch dispersion — single rolling std pass over all columns at once
    rets_arr = ctx["returns"]
    rolling_std = rets_arr.rolling(63).std()
    last_std = rolling_std.iloc[-1].to_numpy(dtype=np.float64)
    global_std = rets_arr.std().to_numpy(dtype=np.float64)
    global_std[global_std < 1e-12] = 1.0
    dispersion_arr = last_std / global_std
    cols_arr = list(rets_arr.columns[:80])
    crowd = [
        {"ticker": str(c), "dispersion_proxy": float(d), "crowding_percentile": float(min(100, max(0, 50 + 20 * (d - 1))))}
        for c, d in zip(cols_arr, dispersion_arr[:80])
    ]

    ic0 = ic_curve[0]["ic"] if ic_curve else 0.0
    cap = alpha_capacity(ic0, float(ctx["returns"].std().mean()), 0.10)
    adjusted = decay_adjusted_weights(ctx["weights"], ic_curve, half)

    tables = {
        "half_life_table": [{"signal": "cross_sectional_momentum_proxy", "half_life_days": half, "taxonomy": payload.get("factor_taxonomy", "mechanical"), **fit, "selected_model": decay_models[0]["model"] if decay_models else "hyperbolic"}],
        "decay_model_selection": decay_models,
        "crowding_proxy": crowd,
        "optimal_rebalance_frequency": [opt_freq],
        "alpha_capacity": [{"capacity_proxy": cap}],
        "factor_zoo_comparison": [{"factor": "momentum_proxy", "taxonomy": "mechanical", "half_life": half}],
        "publication_decay": [{"status": "not_available", "reason": "Factor publication dates not available in local data."}],
    }
    charts = {
        "ic_decay_curve": ic_curve,
        "decay_adjusted_weights": adjusted if adjusted else age_grid,
    }
    return response(
        FEATURE_ID,
        [{"label": "Half-Life", "value": half}, {"label": "IC(1D)", "value": ic0}],
        charts, tables, meta=feature_meta(ctx, ["ETF AUM growth data unavailable; crowding uses cross-sectional dispersion proxy"]),
    )
