"""S1 Core Multi-Factor Screener Engine."""

from __future__ import annotations

from typing import Any
from .inputs import shared_inputs, filter_inputs, enrich, merge_inputs

import pandas as pd

from ..core.common import access_meta, records, response
from ..core.screener import apply_filters, heatmap_view, quick_look, top_table
from ..core.panel import metric_panel
from ..core.data_loader import parse_symbols


FEATURE_ID = "01"
FEATURE_NAME = "Core Multi-Factor Screener Engine"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master', 'description': 'Universe symbols or master universe alias.'}, {'key': 'max_symbols', 'type': 'number', 'default': 500, 'description': 'Maximum symbols loaded from the master universe.'}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'sector', 'type': 'text', 'default': 'all'}, {'key': 'industry_group', 'type': 'text', 'default': 'all'}, {'key': 'market_cap_min', 'type': 'number', 'default': None}, {'key': 'dollar_volume_min', 'type': 'number', 'default': None}, {'key': 'score_min', 'type': 'number', 'default': None}, {'key': 'heatmap_metric', 'type': 'text', 'default': 'core_quant_score'}, {'key': 'include_market_cap_buckets', 'type': 'boolean', 'default': True}]))

OUTPUTS = [{'key': 'filter_funnel_waterfall', 'source': 'charts', 'render': 'table', 'primary': True, 'label': 'Filter Funnel Waterfall'}, {'key': 'cross_sectional_percentile_context', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Cross Sectional Percentile Context'}, {'key': 'heatmap_view', 'source': 'charts', 'render': 'heatmap', 'primary': False, 'label': 'Heatmap View'}, {'key': 'quick_look_card', 'source': 'charts', 'render': 'metrics', 'primary': False, 'label': 'Quick Look Card'}, {'key': 'market_cap_bucket_distribution', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Market Cap Bucket Distribution'}, {'key': 'ranked_screener_table', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Ranked Screener Table'}, {'key': 'saved_screens', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Saved Screens'}]


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
        observed_caps = filtered[filtered.market_cap.notna()]
        bucketed = observed_caps.assign(
            market_cap_bucket=pd.qcut(observed_caps["market_cap"].rank(method="first"), q=min(5, max(1, len(observed_caps))), duplicates="drop").astype(str)
        ) if not observed_caps.empty else observed_caps.assign(market_cap_bucket=pd.Series(dtype=str))
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
    from ..core.state import list_screens
    ql = quick_look(filtered, payload.get("focus_ticker"))
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Universe loaded", "value": len(panel)},
            {"label": "After filters", "value": len(filtered)},
            {"label": "Valuation-ready stocks", "value": int(filtered.valuation_percentile.notna().sum())},
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
            "saved_screens": list_screens(),
        },
        meta=access_meta(
            payload,
            [

                *(
                    [f"{len(dropped)} requested ticker(s) had insufficient local price history and were excluded: {', '.join(dropped[:20])}{'...' if len(dropped) > 20 else ''}"]
                    if dropped
                    else []
                ),
            ],
        ),
    )
