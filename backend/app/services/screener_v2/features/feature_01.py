"""S1 Core Multi-Factor Screener Engine."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.academic import academic_strategy_scores
from ..core.common import access_meta, records, response
from ..core.data_loader import close_matrix, parse_symbols
from ..core.panel import metric_panel
from ..core.screener import apply_filters, heatmap_view, quick_look, top_table
from .inputs import enrich, filter_inputs, merge_inputs, shared_inputs

FEATURE_ID = "01"
FEATURE_NAME = "Core Multi-Factor Screener Engine"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master', 'description': 'Universe symbols or master universe alias.'}, {'key': 'top_n', 'type': 'number', 'default': 5000, 'description': 'Rows returned; the default returns every name that passes.'}, {'key': 'max_symbols', 'type': 'number', 'default': 5000, 'description': 'Maximum symbols loaded from the master universe.'}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'sector', 'type': 'text', 'default': 'all'}, {'key': 'industry_group', 'type': 'text', 'default': 'all'}, {'key': 'market_cap_min', 'type': 'number', 'default': None}, {'key': 'dollar_volume_min', 'type': 'number', 'default': None}, {'key': 'score_min', 'type': 'number', 'default': None}, {'key': 'heatmap_metric', 'type': 'text', 'default': 'core_quant_score'}, {'key': 'include_market_cap_buckets', 'type': 'boolean', 'default': True}]))

OUTPUTS = [{'key': 'metric_coverage', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Metric Coverage'}, {'key': 'filter_funnel_waterfall', 'source': 'charts', 'render': 'table', 'primary': True, 'label': 'Filter Funnel Waterfall'}, {'key': 'cross_sectional_percentile_context', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Cross Sectional Percentile Context'}, {'key': 'heatmap_view', 'source': 'charts', 'render': 'heatmap', 'primary': False, 'label': 'Heatmap View'}, {'key': 'quick_look_card', 'source': 'charts', 'render': 'metrics', 'primary': False, 'label': 'Quick Look Card'}, {'key': 'market_cap_bucket_distribution', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Market Cap Bucket Distribution'}, {'key': 'ranked_screener_table', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Ranked Screener Table'}, {'key': 'saved_screens', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Saved Screens'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    dropped = panel.attrs.get("dropped_symbols", [])
    scores = academic_strategy_scores(panel)[["ticker", "piotroski_passed", "piotroski_available_criteria", "altman_z_score"]]
    panel = panel.merge(scores, on="ticker", how="left", validate="one_to_one")
    closes = close_matrix(symbols, 252)
    panel["max_drawdown_252d"] = panel["ticker"].map((closes / closes.cummax() - 1).min(skipna=True))
    coverage = [{"metric": name, "known": int(panel[name].notna().sum()), "total": len(panel), "share": float(panel[name].notna().mean())}
                for name in panel.select_dtypes("number").columns]
    filtered, funnel = apply_filters(panel, payload)
    bottleneck = max(funnel[1:], key=lambda stage: stage["removed"], default=None)
    bottleneck = bottleneck if bottleneck and bottleneck["removed"] else None
    funnel = [{**stage, "bottleneck": "Most removed" if stage is bottleneck else None} for stage in funnel]
    top_n = int(payload.get("top_n") or 50)
    ranked = top_table(filtered, n=top_n)
    # Dollar bands; names with no market cap stay visible as Unknown.
    bands = pd.cut(pd.to_numeric(filtered["market_cap"], errors="coerce"), [0, 3e8, 2e9, 1e10, 2e11, float("inf")], labels=["Micro", "Small", "Mid", "Large", "Mega"]).astype(object).fillna("Unknown")
    market_cap_bucket_distribution = [{"market_cap_bucket": name, "count": int((bands == name).sum())} for name in ["Mega", "Large", "Mid", "Small", "Micro", "Unknown"]]
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
            {"label": "Bottleneck filter", "value": bottleneck["stage"] if bottleneck else None},
            {"label": "Valuation-ready stocks", "value": int(filtered.valuation_percentile.notna().sum())},
            {"label": "Top score", "value": float(filtered["core_quant_score"].max()) if not filtered.empty else None},
            {"label": "Focus ticker", "value": ql.get("ticker")},
        ],
        charts={
            "filter_funnel_waterfall": funnel,
            "metric_coverage": coverage,
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
