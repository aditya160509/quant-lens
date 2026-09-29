"""S7 Comparative Relative Valuation Screener."""

from __future__ import annotations

from typing import Any

from ..core.analytics import access_meta, metric_panel, records, relative_valuation, response
from ..core.data_loader import parse_symbols


FEATURE_ID = "07"
FEATURE_NAME = "Comparative Relative Valuation Screener"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "focus_ticker", "type": "ticker", "default": None},
    {"key": "lookback_days", "type": "number", "default": 756},
]

OUTPUTS = ["four_dimension_valuation_card", "sector_valuation_landscape_heatmap", "own_history_percentile_time_series", "peer_comparison_table", "universe_percentile_table"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
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
