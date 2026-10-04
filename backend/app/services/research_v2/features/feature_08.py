"""F08 Signal Decay and Arbitrage Clock."""

from __future__ import annotations

from typing import Any

from .merge import merged_inputs, merged_outputs, run_merged
from .inputs import SIGNAL, UNIVERSE, field, output

FEATURE_ID = "08"
FEATURE_NAME = "Signal Decay and Arbitrage Clock"
DESCRIPTION = "Pre/post discovery comparison, decay-curve fits with a bootstrap half-life, the Andrews arbitrage-arrival date, vitality, arbitrage vs data-mining evidence and international replication."

INPUTS = UNIVERSE + SIGNAL + [
    field("discovery_date", "Discovery date", "date", None, "Timeline", help_="When the anomaly was first documented. Required."),
    field("publication_date", "Publication date", "date", None, "Timeline"),
    field("performance_metric", "Performance metric", "select", "ic", "Metric", ["ic", "ls_sharpe", "ls_mean", "fm_lambda"]),
    field("forward_months", "Evaluation horizon (months)", "select", 1, "Metric", [1, 3, 6, 12]),
    field("rolling_window", "Rolling window (months)", "select", 12, "Metric", [12, 24, 36]),
    field("decay_model", "Decay model", "select", "all", "Metric", ["all", "exponential", "linear", "hyperbolic"]),
    field("bootstrap_replications", "Half-life bootstrap", "select", 1000, "Metric", [500, 1000]),
    field("international_replication", "International replication", "boolean", True, "Metric"),
]

OUTPUTS = [
    output("vitality_gauge", "Signal vitality", "tables", "vitalityGauge", primary=True),
    output("anomaly_lifecycle_summary", "Life-cycle summary", "tables", "summaryLine"),
    output("mclean_pontiff_comparison", "McLean-Pontiff comparison", "tables", "dataTable"),
    output("decay_curve", "Decay curve", "charts", "decayCurve"),
    output("half_life_output", "Half-life", "tables", "keyValue"),
    output("decay_model_comparison", "Decay models", "tables", "dataTable"),
    output("andrews_break_chart", "Arbitrage arrival scan", "charts", "breakScan"),
    output("arbitrage_arrival", "Arbitrage arrival date", "tables", "keyValue"),
    output("long_short_sharpe_decay", "Rolling long-short Sharpe", "charts", "lineChart"),
    output("sharpe_life_cycle", "Sharpe by life-cycle period", "tables", "dataTable"),
    output("arbitrage_vs_datamining", "Arbitrage vs data mining", "tables", "keyValue"),
    output("international_replication", "International replication", "tables", "dataTable"),
]
INPUTS = merged_inputs(INPUTS, "11", "Factor zoo")
OUTPUTS = merged_outputs(OUTPUTS, "11", "factor_zoo", "Factor zoo")


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from ..core.common import response
    from ..core.decay import run_decay

    out = run_decay(payload or {})
    result = response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
    return run_merged(result, "11", payload or {}, "factor_zoo", "Factor zoo")
