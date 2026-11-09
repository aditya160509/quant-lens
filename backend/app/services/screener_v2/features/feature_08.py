"""S8 Screener Result Export and Integration Layer."""

from __future__ import annotations

from typing import Any

from ..core.common import access_meta, records, response
from ..core.data_loader import parse_symbols
from ..core.exports import build_export_payload
from ..core.panel import metric_panel
from ..core.screener import apply_filters, top_table
from .inputs import enrich, filter_inputs, merge_inputs, shared_inputs

FEATURE_ID = "08"
FEATURE_NAME = "Screener Result Export and Integration Layer"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master'}, {'key': 'top_n', 'type': 'number', 'default': 100}, {'key': 'export_format', 'type': 'select', 'default': 'csv', 'options': ['csv', 'tsv', 'json', 'tickers']}, {'key': 'columns', 'type': 'json', 'default': None}, {'key': 'rank_shift', 'type': 'number', 'default': 10, 'min': 1}]))

OUTPUTS = [{'key': 'change_report', 'source': 'charts', 'render': 'table', 'primary': True, 'label': 'Change Report'}, {'key': 'instant_download', 'source': 'tables', 'render': 'download', 'primary': False, 'label': 'Instant Download'}, {'key': 'screen_result_api_endpoint', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Screen Result Api Endpoint'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=1000)
    panel = metric_panel(payload, symbols=symbols)
    panel, _ = apply_filters(panel, payload)
    rows = records(top_table(panel, int(payload.get("top_n") or 100)))
    export_payload = build_export_payload(FEATURE_ID, payload, rows)
    from ..core.data_loader import ohlcv_for_symbols
    from ..core.state import compare_and_store
    change_report = compare_and_store(str(payload["screen_id"]), rows, str(ohlcv_for_symbols(symbols).Date.max().date()), int(payload.get("rank_shift", 10))) if payload.get("screen_id") else []
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
