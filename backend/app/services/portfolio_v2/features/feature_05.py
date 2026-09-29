"""F05 Market-Implied Macro Factor Model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.analytics import (
    compact_records,
    factor_crowding_rank,
    factor_risk_budget,
    feature_meta,
    implied_alpha_required,
    load_context,
    load_macro,
    mcte_per_position,
    newey_west_regression,
    response,
)

FEATURE_ID = "05"
FEATURE_NAME = "Market-Implied Macro Factor Model"
INPUTS = ["tickers", "weights", "lookback_days", "macro_factors"]
OUTPUTS = ["macro_exposures", "macro_factor_returns", "rolling_exposure", "unintended_macro_bets"]


def run(payload: dict | None = None) -> dict:
    ctx = load_context(payload, min_symbols=8, default_limit=80)

    # Single port computation reused for all regressions
    w_arr = ctx["weights"].reindex(ctx["returns"].columns).fillna(0.0).to_numpy(dtype=np.float64)
    ret_arr = ctx["returns"].to_numpy(dtype=np.float64)
    np.nan_to_num(ret_arr, copy=False)
    port_arr = ret_arr @ w_arr
    port = pd.Series(port_arr, index=ctx["returns"].index, name="portfolio_return")

    macro = load_macro()
    if macro.empty:
        return response(FEATURE_ID, [], {}, {}, meta=feature_meta(ctx, ["category7 macro parquet unavailable"]))

    x = macro.set_index("date").reindex(port.index, method="ffill")
    cols = [c for c in ["vix_close", "vixcls", "yc_slope_10y_2y", "bamlh0a0hym2", "bamlc0a0cm", "dgs10", "dgs2"] if c in x.columns]
    X = x[cols].ffill().pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = port.reindex(X.index).fillna(0.0)

    X_arr = X.to_numpy(dtype=np.float64)
    y_arr = y.to_numpy(dtype=np.float64)
    nw = newey_west_regression(y, X[cols], 4)
    nw_rows = {r["factor"]: r for r in nw["coefficients"]}
    exposures = [{"factor": c, "beta": float(nw_rows.get(c, {}).get("beta", 0.0)), "newey_west_t": nw_rows.get(c, {}).get("t"), "newey_west_se": nw_rows.get(c, {}).get("se")} for c in cols]

    # Batch all asset regressions — single Ridge closed-form solve (X'X + aI)^-1 X' Y
    y_matrix = ctx["returns"].reindex(X.index).fillna(0.0).to_numpy(dtype=np.float64)
    Xt = X_arr.T
    XtX = Xt @ X_arr
    n_f = XtX.shape[0]
    XtX_reg = XtX + np.eye(n_f) * 1.0
    XtX_inv = np.linalg.inv(XtX_reg)
    B = XtX_inv @ (Xt @ y_matrix)  # shape: (n_factors, n_assets)
    asset_exposures = {
        str(sym): {c: float(B[i, j]) for i, c in enumerate(cols)}
        for j, sym in enumerate(ctx["returns"].columns)
    }
    exposure_matrix = pd.DataFrame.from_dict(asset_exposures, orient="index").fillna(0.0)

    # Rolling with stride, single linalg.solve instead of Ridge per step
    rolling = []
    for i in range(126, len(X), 10):
        subx = X_arr[i - 126:i]
        suby = y_arr[i - 126:i]
        subXtX = subx.T @ subx + np.eye(n_f) * 1.0
        try:
            coef = np.linalg.solve(subXtX, subx.T @ suby)
        except Exception:
            coef = np.linalg.lstsq(subx, suby, rcond=None)[0]
        row = {"date": str(X.index[i].date())}
        row.update({c: float(b) for c, b in zip(cols, coef)})
        rolling.append(row)

    loadings = pd.Series({r["factor"]: abs(r["beta"]) for r in exposures})
    mcte = mcte_per_position(ctx["returns"], ctx["weights"])
    tables = {
        "macro_exposures": exposures,
        "unintended_macro_bets": [r for r in exposures if abs(r["beta"]) > float(np.percentile([abs(e["beta"]) for e in exposures], 75))] if exposures else [],
        "mcte_per_position": mcte,
        "implied_alpha_required": implied_alpha_required(mcte),
        "factor_crowding_rank": factor_crowding_rank(loadings),
        "factor_risk_budget": factor_risk_budget(exposure_matrix, ctx["returns"]),
    }
    charts = {
        "macro_factor_returns": compact_records(X.reset_index().rename(columns={"index": "date"}), 500),
        "rolling_exposure": rolling,
    }
    return response(
        FEATURE_ID,
        [{"label": "Macro R2", "value": float(nw.get("r2", 0.0))}, {"label": "Top Beta", "value": max([abs(e["beta"]) for e in exposures] or [0.0])}],
        charts, tables, meta=feature_meta(ctx),
    )
