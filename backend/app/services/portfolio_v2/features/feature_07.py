"""F07 Liquidity Analytics Engine."""

from __future__ import annotations

import pandas as pd

from ..core.analytics import crisis_liquidation_cost, feature_meta, liquidity_frontier, liquidity_halflife, liquidity_table, load_context, ohlcv_for_symbols, recency_weighted_amihud, regulatory_classification, response

FEATURE_ID = "07"
FEATURE_NAME = "Liquidity Analytics Engine"
INPUTS = ["tickers", "weights", "lookback_days", "portfolio_nav", "participation_rate"]
OUTPUTS = ["liquidity_table", "days_to_liquidate", "liquidity_var", "liquidation_schedule", "half_life"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    nav = float(payload.get("portfolio_nav") or 1_000_000)
    table = pd.DataFrame(liquidity_table(ctx["symbols"], ctx["lookback_days"], nav, ctx["weights"]))
    if table.empty:
        return response(FEATURE_ID, [], {}, {}, meta=feature_meta(ctx, ["volume data unavailable for selected symbols"]))
    schedule = []
    dtl_col = "days_to_liquidate_20pct_adv"
    for ticker, dtl in zip(table["ticker"].astype(str).to_numpy(), table[dtl_col].to_numpy(dtype=float, copy=False)):
        days = max(1, int(round(dtl)))
        for day in range(1, min(days, 20) + 1):
            schedule.append({"ticker": ticker, "day": day, "remaining_pct": float(max(0.0, 1 - day / days))})
    raw = ohlcv_for_symbols(ctx["symbols"], ctx["lookback_days"])
    rw = recency_weighted_amihud(raw)
    halflife_rows = []
    for ticker, group in raw.groupby("Ticker"):
        group = group.sort_values("Date")
        oc_ret = (group["Close"] / group["Open"].replace(0, pd.NA) - 1).abs()
        dv = (group["Close"] * group["Volume"].fillna(0)).replace(0, pd.NA)
        amihud_series = (oc_ret / dv).replace([float("inf"), float("-inf")], pd.NA).dropna()
        halflife_rows.append({"ticker": ticker, "liquidity_halflife_days": liquidity_halflife(amihud_series)})
    liq_rows = table.to_dict("records")
    tables = {
        "liquidity_table": [{**r, "recency_weighted_amihud": float(rw.get(r["ticker"], r.get("amihud", 0.0))), "regulatory_bucket": regulatory_classification(float(r[dtl_col]))} for r in liq_rows],
        "days_to_liquidate": table[["ticker", dtl_col]].to_dict("records"),
        "liquidity_var": table[["ticker", "liquidity_var_bps"]].to_dict("records"),
        "half_life": halflife_rows,
        "crisis_liquidation_cost": crisis_liquidation_cost(liq_rows),
        "regulatory_compliance": [{"ticker": r["ticker"], "bucket": regulatory_classification(float(r[dtl_col]))} for r in liq_rows],
    }
    charts = {"liquidation_schedule": schedule, "liquidity_rank": table.sort_values(dtl_col, ascending=False).head(50).to_dict("records"), "liquidity_frontier": liquidity_frontier(liq_rows)}
    return response(FEATURE_ID, [{"label": "Max DTL", "value": float(table[dtl_col].max())}, {"label": "Median ADV $", "value": float(table["adv_dollars"].median()), "format": "currency"}], charts, tables, meta=feature_meta(ctx))
