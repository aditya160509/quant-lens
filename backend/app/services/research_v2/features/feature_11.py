"""F11 Cross-Sectional Dependence and Factor Zoo Positioning Engine."""

from __future__ import annotations

from typing import Any

from ..core.common import response
from ..core.zoo import run_zoo
from .inputs import SIGNAL, UNIVERSE, field, output

FEATURE_ID = "11"
FEATURE_NAME = "Factor Zoo Positioning Engine"
DESCRIPTION = "Spans the candidate against FF5+MOM or an extended library (quality, low-vol, BAB, short-term reversal, internal factors, your uploads) and applies the Harvey-Liu-Zhu bar."

INPUTS = UNIVERSE + SIGNAL + [
    field("benchmark_library", "Benchmark library", "select", "extended", "Library", ["ff5_mom", "extended", "user"]),
    field("factor_csv_path", "Factor returns upload", "file", "", "Library", help_="CSV: date column plus one monthly-return column per factor."),
    field("spanning_factors", "Spanning subset", "text", "", "Library", help_="Comma-separated factor names; empty uses the whole library."),
    field("significance_threshold", "Significance bar", "select", "hlz_bhy", "Inference", ["t_2.0", "t_3.0", "hlz_bonferroni", "hlz_holm", "hlz_bhy", "bonferroni_current", "custom"]),
    field("custom_threshold", "Custom t", "number", 3.0, "Inference"),
    field("literature_factor_count", "Factors tested in the literature", "number", 450, "Inference", min=1, max=5000),
]

OUTPUTS = [
    output("harvey_liu_zhu_card", "Literature-adjusted significance", "tables", "testCard", primary=True),
    output("zoo_positioning_chart", "Zoo positioning", "charts", "zooScatter"),
    output("extended_spanning_test", "Extended spanning test", "tables", "keyValue"),
    output("correlation_with_existing_factors", "Correlation with existing factors", "tables", "dataTable"),
    output("factor_correlation_map", "Factor correlation map", "charts", "correlationMatrix"),
    output("candidate_summary", "Candidate summary", "tables", "keyValue"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = run_zoo(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
