"""S8 Screener Result Export and Integration Layer."""

from __future__ import annotations

from typing import Any

from ..core.analytics import access_meta, build_export_payload, metric_panel, records, response, top_table
from ..core.data_loader import parse_symbols


FEATURE_ID = "08"
FEATURE_NAME = "Screener Result Export and Integration Layer"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "export_format", "type": "select", "default": "csv"},
    {"key": "top_n", "type": "number", "default": 100},
]

OUTPUTS = ["instant_download", "screen_result_api_endpoint", "change_report"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    rows = records(top_table(panel, int(payload.get("top_n") or 100)))
    export_payload = build_export_payload(FEATURE_ID, payload, rows)
    change_report = [
        {"field": "row_count", "value": len(rows), "status": "current_run"},
        {"field": "columns", "value": len(export_payload["columns"]), "status": "current_run"},
    ]
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Export rows", "value": len(rows)},
            {"label": "Columns", "value": len(export_payload["columns"])},
            {"label": "Format", "value": payload.get("export_format", "csv")},
        ],
        charts={"change_report": change_report},
        tables={
            "instant_download": [export_payload],
            "screen_result_api_endpoint": [{"method": "POST", "path": f"/api/screener-v2/run/{FEATURE_ID}", "status": "available", "feature_id": FEATURE_ID}],
        },
        meta=access_meta(payload),
    )
