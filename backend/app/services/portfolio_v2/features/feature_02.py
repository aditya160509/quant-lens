"""F02 Honest Backtesting Engine."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from ..core.analytics import (
    calmar_ratio,
    deflated_sharpe_ratio,
    feature_meta,
    harvey_liu_correction,
    load_context,
    min_track_record_length,
    omega_ratio,
    pbo_cscv,
    performance_metrics,
    politis_romano_block,
    response,
    ulcer_index,
    up_down_capture,
    value_at_risk_methods,
)

FEATURE_ID = "02"
FEATURE_NAME = "Honest Backtesting Engine"
INPUTS = ["tickers", "weights", "lookback_days", "frequency", "rebalance_frequency", "transaction_cost_bps"]
OUTPUTS = ["equity_curve", "drawdown", "performance_table", "monthly_heatmap", "psr_dsr", "walk_forward", "bias_audit"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    rets = ctx["returns"]
    cost = float(payload.get("transaction_cost_bps") or 5) / 10000
    w = ctx["weights"].reindex(rets.columns).fillna(0.0)

    # Single numpy pass — gross + bench + net without three separate Series calls
    w_arr = w.to_numpy(dtype=np.float64)
    bench_arr = np.full(rets.shape[1], 1.0 / max(rets.shape[1], 1))
    ret_arr = rets.to_numpy(dtype=np.float64)
    np.nan_to_num(ret_arr, copy=False)
    gross_arr = ret_arr @ w_arr
    bench_arr_ret = ret_arr @ bench_arr

    turnover_proxy = float(np.abs(w_arr).sum()) / max(int(payload.get("rebalance_days") or 21), 1)
    net_arr = gross_arr - cost * turnover_proxy
    net = pd.Series(net_arr, index=rets.index)
    bench = pd.Series(bench_arr_ret, index=rets.index)

    # Single cumprod pass for both equity curves
    gross_equity_arr = np.cumprod(1.0 + gross_arr)
    equity_arr = np.cumprod(1.0 + net_arr)
    drawdown_arr = equity_arr / np.maximum.accumulate(equity_arr) - 1.0

    metrics = performance_metrics(net, ctx["annualization_factor"])

    sr = metrics.get("sharpe", 0.0)
    sk = metrics.get("skew", 0.0)
    ku = metrics.get("kurtosis", 3.0)
    n = len(net)
    denom = math.sqrt(max(1e-12, (1 - sk * sr + (ku - 1) * sr * sr / 4) / max(n - 1, 1)))
    psr = float(stats.norm.cdf((sr - 0.0) / denom))
    dsr = deflated_sharpe_ratio(sr, n, max(variants_count if "variants_count" in locals() else rets.shape[1], 1), sk, ku)

    # Resample once, assign year/month in-place
    monthly = net.resample("ME").sum()
    monthly_df = monthly.to_frame("return")
    monthly_df["year"] = monthly.index.year
    monthly_df["month"] = monthly.index.month

    # Walk forward with precomputed splits
    rebalance = str(payload.get("rebalance_frequency") or "monthly").lower()
    split_default = {"weekly": 63, "monthly": 126, "quarterly": 252}.get(rebalance, 126)
    split = int(payload.get("walk_forward_window") or max(split_default, len(net) // 6))
    wf = []
    for i in range(split, len(net), split):
        sample = net.iloc[max(0, i - split):i]
        out_s = net.iloc[i:i + split]
        wf.append({
            "fold": len(wf) + 1,
            "train_sharpe": performance_metrics(sample, ctx["annualization_factor"]).get("sharpe", 0.0),
            "test_sharpe": performance_metrics(out_s, ctx["annualization_factor"]).get("sharpe", 0.0),
        })

    # Variants in one numpy block — einsum for momentum tilt
    n_cols = rets.shape[1]
    variants = pd.DataFrame(index=rets.index)
    variants["equal_weight"] = ret_arr.mean(axis=1)
    variants["current_weight"] = gross_arr
    half = max(2, n_cols // 2)
    top_vol_idx = np.argsort(rets.std().to_numpy())[:half]
    variants["top_vol_trim"] = ret_arr[:, top_vol_idx].mean(axis=1)
    mom_w = rets.rolling(63).mean().rank(axis=1, pct=True).shift(1).fillna(0.5).to_numpy(dtype=np.float64)
    variants["momentum_tilt"] = np.einsum("ij,ij->i", ret_arr, mom_w) / max(n_cols, 1)

    pbo = pbo_cscv(variants)
    variants_count = variants.shape[1]
    extra = {
        "omega_ratio": omega_ratio(net),
        "ulcer_index": ulcer_index(net),
        "calmar_ratio": calmar_ratio(net, ctx["annualization_factor"]),
        **up_down_capture(net, bench),
        "politis_romano_block_length": politis_romano_block(net),
    }
    charts = {
        "equity_curve": [{"date": str(k.date()), "gross": float(g), "net": float(nv)} for k, g, nv in zip(rets.index, gross_equity_arr, equity_arr)],
        "drawdown": [{"date": str(k.date()), "drawdown": float(v)} for k, v in zip(rets.index, drawdown_arr)],
        "monthly_heatmap": monthly_df.reset_index().to_dict("records"),
        "pbo_distribution": pbo["distribution"],
        "risk_methods": value_at_risk_methods(net, float(payload.get("var_confidence") or 0.95), int(payload.get("var_simulations") or 10_000)),
    }
    tables = {
        "performance_table": [{**metrics, **extra}],
        "psr_dsr": [{"psr": psr, "dsr": dsr, "min_track_record_length_days": min_track_record_length(sr, skew=sk, kurtosis=ku), **harvey_liu_correction(sr, trials=max(n_cols, 1))}],
        "pbo_distribution": pbo["distribution"],
        "walk_forward": wf,
        "bias_audit": [{"test": "survivorship_bias", "status": "data_limited", "detail": "Point-in-time historical constituents not present."}],
    }
    return response(
        FEATURE_ID,
        [{"label": "Net Sharpe", "value": sr}, {"label": "DSR", "value": dsr}, {"label": "Net MDD", "value": metrics.get("max_drawdown", 0.0), "format": "percent"}],
        charts, tables, meta=feature_meta(ctx, ["point-in-time constituents unavailable"]),
    )
