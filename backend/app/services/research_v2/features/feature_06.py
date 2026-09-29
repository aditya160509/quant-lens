"""R06 Specification Builder and Publication Output."""

from __future__ import annotations

from typing import Any

from ..core.analytics import response, specification_builder_outputs

FEATURE_ID = "06"
FEATURE_NAME = "Specification Builder and Publication Output"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "max_symbols", "type": "number", "default": 400},
    {"key": "signal", "type": "select", "default": "momentum", "options": ["momentum", "value", "quality", "low_vol", "reversal"]},
    {"key": "signal_csv_path", "type": "file_path", "default": ""},
    {"key": "controls", "type": "select", "default": "size,value", "options": ["none", "size", "value", "size,value", "size,value,momentum", "full"]},
    {"key": "weighting", "type": "select", "default": "equal", "options": ["equal", "value", "rank"]},
    {"key": "max_specifications", "type": "number", "default": 12},
    {"key": "table_columns", "type": "json", "default": ""},
    {"key": "journal_style", "type": "select", "default": "finance", "options": ["finance", "aer", "jfe", "rfs"]},
]

OUTPUTS = [
    "publication_table_manifest",
    "publication_table",
    "journal_table_bundle",
    "specification_grid",
    "coefficient_forest_plot",
    "auto_built_spec_curve_table",
    "spec_curve_auto_table",
    "confirmatory_exploratory_tags",
    "appendix_latex",
    "table_manifest",
    "pdf_report",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = specification_builder_outputs(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out.get("meta"))
