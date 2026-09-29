"""F10 Growth-Optimal Position Sizing and Capital Allocation."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..core.analytics import (
    alpha_decay,
    covariance_matrix,
    decay_adjusted_weights,
    drawdown_constrained_leverage,
    effective_kelly_fraction,
    expected_returns,
    feature_meta,
    kelly_sizing,
    load_context,
    optimize_portfolios,
    response,
    ruin_probability_surface,
    turnover_optimal_kelly,
)

FEATURE_ID = "10"
FEATURE_NAME = "Growth-Optimal Position Sizing and Capital Allocation Engine"
INPUTS = ["tickers", "weights", "lookback_days", "kelly_fraction", "leverage_cap", "transaction_cost_bps"]
OUTPUTS = ["position_sizing", "growth_frontier", "ruin_probability", "drawdown_leverage", "turnover_optimal_kelly"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)

    # Compute cov + mu once, reuse for all kelly paths
    cov, _ = covariance_matrix(ctx["returns"], payload.get("covariance_estimator", "ledoit_wolf"))
    ann = ctx["annualization_factor"]
    cov_ann = cov * ann
    cov_ann_arr = cov_ann.to_numpy(dtype=np.float64)
    mu = expected_returns(ctx["returns"], payload.get("expected_return_estimator", "shrinkage"), ann)
    mu_arr = mu.reindex(ctx["returns"].columns).fillna(0.0).to_numpy(dtype=np.float64)

    kelly = kelly_sizing(
        mu, cov_ann, ctx["weights"],
        float(payload.get("kelly_fraction") or 0.5),
        float(payload.get("leverage_cap") or 1.0),
        float(payload.get("transaction_cost_bps") or 10.0),
    )
    markowitz = optimize_portfolios(ctx["returns"], {**ctx["payload"], "objective": "max_sharpe"})
    markowitz_weights = markowitz["weights"].get("max_sharpe", pd.Series(dtype=float)).reindex(ctx["returns"].columns).fillna(0.0)

    # Vectorized growth rates — single matmul instead of per-weight loop
    kelly_w = np.array([r["kelly_weight"] for r in kelly["table"]], dtype=np.float64)
    constrained_w = np.array([r["constrained_weight"] for r in kelly["table"]], dtype=np.float64)
    unconstrained_g = float(kelly_w @ mu_arr - 0.5 * kelly_w @ cov_ann_arr @ kelly_w)
    constrained_g = float(constrained_w @ mu_arr - 0.5 * constrained_w @ cov_ann_arr @ constrained_w)

    # Vectorized ruin probabilities — single np.exp on array
    w_vec = ctx["weights"].reindex(ctx["returns"].columns).fillna(0.0).to_numpy(dtype=np.float64)
    port_var = float(w_vec @ cov_ann_arr @ w_vec)
    port_sigma = math.sqrt(max(port_var, 1e-12))
    port_mu = float(mu_arr.mean())
    lev_arr = np.array([1.0, 1.25, 1.5, 2.0], dtype=np.float64)
    exp_arg = -2.0 * max(port_mu, 1e-6) / np.maximum(port_var * lev_arr ** 2, 1e-8)
    ruin_probs = np.clip(np.exp(exp_arg), 0.0, 1.0)
    ruin = [{"leverage": float(lv), "ruin_probability": float(rp)} for lv, rp in zip(lev_arr, ruin_probs)]

    turnover = turnover_optimal_kelly(mu, cov_ann, ctx["weights"], float(payload.get("transaction_cost_bps") or 10.0))
    decay = alpha_decay(ctx["returns"])

    tables = {
        "position_sizing": kelly["table"],
        "ruin_probability": ruin,
        "drawdown_leverage": [{"max_drawdown_limit": payload.get("drawdown_limit", 0.20), "safe_leverage": drawdown_constrained_leverage(port_mu, port_sigma, float(payload.get("drawdown_limit") or 0.20))}],
        "effective_kelly_fraction": [{"value": effective_kelly_fraction(constrained_g, unconstrained_g)}],
        "turnover_optimal_kelly": [{"kelly_fraction": turnover["best_fraction"]}],
        "kelly_vs_markowitz": [{"ticker": ticker, "kelly_weight": float(krow["constrained_weight"]), "markowitz_weight": float(markowitz_weights.get(ticker, 0.0)), "difference": float(krow["constrained_weight"] - markowitz_weights.get(ticker, 0.0))} for ticker, krow in ((row["ticker"], row) for row in kelly["table"])],
    }

    # Ruin surface vectorized — batch np.exp over full grid
    mu_grid = np.array([port_mu * 0.5, port_mu, port_mu * 1.5], dtype=np.float64)
    sig_grid = np.array([max(port_sigma, 1e-6), max(port_sigma * 1.5, 1e-6)], dtype=np.float64)
    lev_grid = np.array([1.0, 1.5, 2.0], dtype=np.float64)
    ruin_surface = []
    for mu_v in mu_grid:
        for sig_v in sig_grid:
            args = -2.0 * max(mu_v, 1e-9) / np.maximum(sig_v ** 2 * lev_grid ** 2, 1e-12)
            probs = np.clip(np.exp(args), 0.0, 1.0)
            for lv, p in zip(lev_grid, probs):
                ruin_surface.append({"mu": float(mu_v), "sigma": float(sig_v), "leverage": float(lv), "ruin_probability": float(p)})

    charts = {
        "growth_frontier": kelly["growth_curve"],
        "kelly_weights": kelly["table"],
        "ruin_probability_surface": ruin_surface,
        "turnover_optimal_curve": turnover["curve"],
        "signal_decay_sizing": decay_adjusted_weights(ctx["weights"], decay["ic_curve"], decay.get("half_life") or 63),
        "markowitz_weights": [{"ticker": k, "weight": float(v)} for k, v in markowitz_weights.items()],
    }
    return response(
        FEATURE_ID,
        [{"label": "Turnover-Optimal f", "value": kelly["turnover_optimal_fraction"]}, {"label": "Mean Kelly Gap", "value": sum(abs(r["sizing_gap"]) for r in kelly["table"]) / max(len(kelly["table"]), 1)}],
        charts, tables, meta=feature_meta(ctx),
    )
