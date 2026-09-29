"""S1 Core Multi-Factor Screener Engine."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.analytics import access_meta, apply_filters, heatmap_view, metric_panel, quick_look, records, response, top_table
from ..core.data_loader import parse_symbols


FEATURE_ID = "01"
FEATURE_NAME = "Core Multi-Factor Screener Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master", "description": "Universe symbols or master universe alias."},
    {"key": "max_symbols", "type": "number", "default": 500, "description": "Maximum symbols loaded from the master universe."},
    {"key": "lookback_days", "type": "number", "default": 756},
    {"key": "sector", "type": "text", "default": "all"},
    {"key": "industry_group", "type": "text", "default": "all"},
    {"key": "market_cap_min", "type": "number", "default": None},
    {"key": "dollar_volume_min", "type": "number", "default": None},
    {"key": "score_min", "type": "number", "default": None},
]

OUTPUTS = [
    "ranked_screener_table",
    "filter_funnel_waterfall",
    "cross_sectional_percentile_context",
    "heatmap_view",
    "quick_look_card",
    "saved_screens",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    dropped = panel.attrs.get("dropped_symbols", [])
    filtered, funnel = apply_filters(panel, payload)
    top_n = int(payload.get("top_n") or 50)
    ranked = top_table(filtered, n=top_n)
    market_cap_bucket_distribution = []
    if bool(payload.get("include_market_cap_buckets", True)) and not filtered.empty and "market_cap" in filtered:
        bucketed = filtered.assign(
            market_cap_bucket=pd.qcut(filtered["market_cap"].rank(method="first"), q=min(5, max(1, len(filtered))), duplicates="drop").astype(str)
        )
        market_cap_bucket_distribution = records(
            bucketed.groupby("market_cap_bucket").agg(count=("ticker", "count"), avg_score=("core_quant_score", "mean")).reset_index()
        )
    cross_section = filtered[[
        c for c in [
            "ticker",
            "company_name",
            "sector",
            "industry_group",
            "industry",
            "core_quant_score",
            "valuation_percentile",
            "quality_percentile",
            "momentum_percentile",
            "low_vol_percentile",
            "liquidity_percentile",
            "sector_relative_score",
            "industry_group_relative_score",
            "industry_relative_score",
            "prox52",
            "vratio",
            "macd_histogram",
            "adx_14",
            "bollinger_pct_b",
            "atr_pct_price",
            "amihud_percentile",
        ] if c in filtered.columns
    ]].head(250)
    ql = quick_look(filtered, payload.get("focus_ticker"))
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Universe loaded", "value": len(panel)},
            {"label": "After filters", "value": len(filtered)},
            {"label": "Top score", "value": float(filtered["core_quant_score"].max()) if not filtered.empty else None},
            {"label": "Focus ticker", "value": ql.get("ticker")},
        ],
        charts={
            "filter_funnel_waterfall": funnel,
            "cross_sectional_percentile_context": records(cross_section),
            "heatmap_view": heatmap_view(filtered, str(payload.get("heatmap_metric") or "core_quant_score")),
            "quick_look_card": ql,
            "market_cap_bucket_distribution": market_cap_bucket_distribution,
        },
        tables={
            "ranked_screener_table": records(ranked),
            "saved_screens": [],
        },
        meta=access_meta(
            payload,
            [
                "Saved screen persistence is not wired to a server database yet; runtime emits the current result only.",
                *(
                    [f"{len(dropped)} requested ticker(s) had insufficient local price history and were excluded: {', '.join(dropped[:20])}{'...' if len(dropped) > 20 else ''}"]
                    if dropped
                    else []
                ),
            ],
        ),
    )
