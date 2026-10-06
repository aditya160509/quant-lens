"""Validate: one-page HELD UP / MIXED / FAILED verdict for a strategy, predictions or model (includes F04 meta-labelling)."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract

FEATURE_ID = "validate"
FEATURE_TITLE = "Validate my strategy or model"

DEFAULTS: dict[str, Any] = {
    "prediction_horizon": 1, "embargo_period": 5, "cost_bps": 5.0, "random_seed": 7,
    "cpcv_n_groups": 6, "cpcv_k_test_groups": 2, "pbo_partitions": 8, "model_type": "ridge",
    "n_seeds": 5, "grid_size": 5, "n_permutations": 100, "trials_are": "configs", "improve_strategy": True,
}
ALIASES = {"horizon": "prediction_horizon", "embargo": "embargo_period", "seed": "random_seed", "upload": "upload_id"}

INPUT_CONTRACT = [
    {"key": "upload_id", "type": "text", "required": False},
    {"key": "trials_upload_id", "type": "text", "required": False},
    {"key": "benchmark_upload_id", "type": "text", "required": False},
    {"key": "source_result", "type": "object", "required": False},
    {"key": "prediction_horizon", "type": "integer", "min": 1, "max": 63, "default": 1},
    {"key": "embargo_period", "type": "integer", "min": 0, "max": 63, "default": 5},
    {"key": "cost_bps", "type": "float", "min": 0, "max": 1000, "default": 5.0},
    {"key": "random_seed", "type": "integer", "min": 0, "max": 2**31 - 1, "default": 7},
    {"key": "trial_count", "type": "integer", "min": 1, "max": 1000000, "required": False},
    {"key": "trials_are", "type": "select", "options": ["configs", "seeds"], "default": "configs"},
    {"key": "selected_strategy", "type": "integer", "min": 0, "max": 199, "required": False},
    {"key": "model_type", "type": "select", "options": ["ridge", "random_forest"], "default": "ridge"},
    {"key": "cpcv_n_groups", "type": "integer", "options": [4, 6, 8], "default": 6},
    {"key": "cpcv_k_test_groups", "type": "integer", "options": [1, 2], "default": 2},
    {"key": "pbo_partitions", "type": "integer", "options": [4, 6, 8, 10, 12], "default": 8},
    {"key": "n_seeds", "type": "integer", "min": 1, "max": 10, "default": 5},
    {"key": "grid_size", "type": "integer", "min": 2, "max": 5, "default": 5},
    {"key": "n_permutations", "type": "integer", "min": 20, "max": 500, "default": 100},
    {"key": "improve_strategy", "type": "boolean", "default": True},
]

SECTIONS = ["cpcv", "pbo", "deflated_sharpe", "min_backtest_length", "controls", "stability", "plateau", "leakage",
            "transfer", "monte_carlo", "autopsy", "improve", "data_quality", "receipt"]
OUTPUT_CONTRACT = [{"key": key, "location": "sections", "renderer": "json_block", "status": "live"} for key in SECTIONS]

RESEARCH_ONLY = ["forward tracking of a frozen model", "shared trial ledger with Research"]
IMPLEMENTATION_NOTES = [
    "The verdict is measured against the best control, not against zero.",
    "Sections that cannot be computed for the supplied input are returned with status 'unavailable' and a reason.",
    "Result carries top-level 'verdict' and 'sections'; every section has a provenance block.",
]

INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT, FEATURE_ID)


def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES)


def run(payload=None):
    from app.services.ml_v2.core.validate_engine import run_validate
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_validate(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT,
                                  research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
