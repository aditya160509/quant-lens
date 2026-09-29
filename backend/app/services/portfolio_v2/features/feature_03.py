"""F03 Performance Attribution Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.analytics import (
    brinson_attribution,
    brinson_fachler,
    carino_link,
    drawdown_attribution,
    feature_meta,
    grap_link,
    load_context,
    menchero_link,
    performance_metrics,
    response,
    risk_attribution_xsr,
    skill_luck_bootstrap,
)

FEATURE_ID = "03"
FEATURE_NAME = "Performance Attribution Engine"
INPUTS = ["tickers", "weights", "lookback_days", "benchmark"]
OUTPUTS = ["brinson_table", "factor_attribution", "drawdown_attribution", "risk_attribution", "skill_luck"]


def run(payload: dict | None = None) -> dict:
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    rets, w = ctx["returns"], ctx["weights"]

    # Single numpy pass for port + bench + active
    w_arr = w.reindex(rets.columns).fillna(0.0).to_numpy(dtype=np.float64)
    bench_arr = np.full(rets.shape[1], 1.0 / max(rets.shape[1], 1))
    ret_arr = rets.to_numpy(dtype=np.float64)
    np.nan_to_num(ret_arr, copy=False)
    port_arr = ret_arr @ w_arr
    bench_arr_ret = ret_arr @ bench_arr
    active_arr = port_arr - bench_arr_ret
    port = pd.Series(port_arr, index=rets.index)
    bench = pd.Series(bench_arr_ret, index=rets.index)
    active = pd.Series(active_arr, index=rets.index)

    brinson = brinson_attribution(rets, w, ctx["sectors"])
    bench_w = pd.Series(1 / len(rets.columns), index=rets.columns)
    bf = brinson_fachler(rets, w, bench_w, ctx["sectors"])

    # Vectorized contribution — single einsum
    mean_ret = rets.mean().to_numpy(dtype=np.float64)
    contrib_arr = mean_ret * w_arr
    order = np.argsort(contrib_arr)
    waterfall = [{"component": str(rets.columns[i]), "value": float(contrib_arr[i])} for i in order]

    # Single cumprod for equity + drawdown, no intermediate Series
    equity_arr = np.cumprod(1.0 + port_arr)
    peak_arr = np.maximum.accumulate(equity_arr)
    dd_arr = equity_arr / np.maximum(peak_arr, 1e-18) - 1.0
    trough_idx = int(np.argmin(dd_arr))
    peak_idx = int(np.argmax(equity_arr[: trough_idx + 1]))

    window = rets.iloc[peak_idx: trough_idx + 1].to_numpy(dtype=np.float64)
    contrib_dd = (window * w_arr).sum(axis=0)
    drawdown_attr = [{"ticker": c, "contribution": float(v)} for c, v in zip(rets.columns, contrib_dd)]

    metrics = performance_metrics(active, ctx["annualization_factor"])
    effects = active.resample("ME").sum()
    port_monthly = port.resample("ME").sum()
    da = drawdown_attribution(rets, w)
    sl = skill_luck_bootstrap(active)
    carino = carino_link(effects, port_monthly)
    menchero = menchero_link(effects, port_monthly)
    grap = grap_link(effects, port_monthly)

    tables = {
        "brinson_table": brinson,
        "brinson_fachler": bf,
        "factor_attribution": waterfall,
        "drawdown_attribution": da if da else drawdown_attr,
        "risk_attribution": risk_attribution_xsr(rets, w),
        "linking_methods": [{"date": str(k.date()), "carino": float(v), "menchero": float(menchero.loc[k]), "grap": float(grap.loc[k])} for k, v in carino.items()],
        "skill_luck": [{"observed_t": sl.get("observed_t"), "p_value": sl.get("p_value"), "active_sharpe": metrics.get("sharpe", 0.0), "interpretation": "statistically_interesting" if abs(metrics.get("sharpe", 0.0)) > 1 else "needs_more_evidence"}],
        "skill_luck_null_distribution": sl.get("null_distribution", []),
    }
    charts = {
        "attribution_waterfall": waterfall,
        "active_return_series": [{"date": str(k.date()), "active_return": float(v)} for k, v in zip(active.index, active_arr)],
    }
    return response(
        FEATURE_ID,
        [{"label": "Active Sharpe", "value": metrics.get("sharpe", 0.0)}, {"label": "Active Return", "value": metrics.get("annual_return", 0.0), "format": "percent"}],
        charts, tables, meta=feature_meta(ctx),
    )
