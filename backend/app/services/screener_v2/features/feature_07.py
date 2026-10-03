"""S7 Comparative Relative Valuation Screener."""

from __future__ import annotations

from typing import Any
from .inputs import shared_inputs, filter_inputs, enrich, merge_inputs

from ..core.common import access_meta, records, response
from ..core.panel import metric_panel
from ..core.screener import apply_filters
from ..core.valuation import relative_valuation
from ..core.data_loader import parse_symbols


FEATURE_ID = "07"
FEATURE_NAME = "Comparative Relative Valuation Screener"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master'}, {'key': 'focus_ticker', 'type': 'ticker', 'default': None}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'peers', 'type': 'ticker_list', 'default': None}, {'key': 'peer_scope', 'type': 'select', 'default': 'sector', 'options': ['sector', 'industry', 'universe', 'market_cap_bucket']}, {'key': 'history_window', 'type': 'select', 'default': 756, 'options': [252, 756, 2520]}, {'key': 'history_metric', 'type': 'select', 'default': 'trailing_pe', 'options': ['trailing_pe', 'pb_ratio', 'ps_ratio', 'p_cf', 'ev_ebit', 'ev_ebitda', 'fcf_yield']}, {'key': 'card_limit', 'type': 'number', 'default': 100, 'min': 1, 'max': 5000}]))

OUTPUTS = [{'key': 'four_dimension_valuation_card', 'source': 'charts', 'render': 'metrics', 'primary': True, 'label': 'Four Dimension Valuation Card'}, {'key': 'sector_valuation_landscape_heatmap', 'source': 'charts', 'render': 'heatmap', 'primary': False, 'label': 'Sector Valuation Landscape Heatmap'}, {'key': 'own_history_percentile_time_series', 'source': 'charts', 'render': 'lineChart', 'primary': False, 'label': 'Own History Percentile Time Series'}, {'key': 'universe_wide_four_dimension_cards', 'source': 'charts', 'render': 'metrics', 'primary': False, 'label': 'Universe Wide Four Dimension Cards'}, {'key': 'peer_comparison_table', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Peer Comparison Table'}, {'key': 'universe_percentile_table', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Universe Percentile Table'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    panel, _ = apply_filters(panel, payload)
    rel = relative_valuation(panel, payload.get("focus_ticker"), payload)
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Focus ticker", "value": rel.get("card", {}).get("ticker")},
            {"label": "Sector percentile", "value": rel.get("card", {}).get("sector_percentile")},
            {"label": "Own history percentile", "value": rel.get("card", {}).get("own_history_percentile")},
        ],
        charts={
            "four_dimension_valuation_card": rel.get("card", {}),
            "sector_valuation_landscape_heatmap": rel.get("sector_heatmap", []),
            "own_history_percentile_time_series": rel.get("history", []),
            "universe_wide_four_dimension_cards": rel.get("universe_cards", []),
        },
        tables={
            "peer_comparison_table": rel.get("peer_table", []),
            "universe_percentile_table": rel.get("universe_table", []),
        },
        meta=access_meta(payload, []),
    )
