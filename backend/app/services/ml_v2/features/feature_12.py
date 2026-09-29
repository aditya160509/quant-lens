"""Feature 12: Deep Sequence Alpha Engine."""

from __future__ import annotations

from typing import Any

from app.services.ml_v2.core.analytics import merge_feature_contract, normalize_payload, run_sequence_alpha


FEATURE_ID = "12"
FEATURE_TITLE = "Deep Sequence Alpha Engine"

DEFAULTS: dict[str, Any] = {
    "architectures": ["patchtst_proxy", "itransformer_proxy", "tft_proxy", "gbt"],
    "input_feature_set": ["ohlcv_factor_library", "fama_french", "macro"],
    "patch_length": 21,
    "lookback_days": 756,
    "prediction_horizon": 5,
    "transformer_depth": 2,
    "attention_heads": 4,
    "dropout_rate": 0.1,
    "max_symbols": 80,
    "compute_mode": "realtime",
}

ALIASES = {"models": "architectures", "features": "input_feature_set", "horizon": "prediction_horizon"}

INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list", "required": False},
    {"key": "architectures", "type": "multi_select", "options": ["patchtst", "itransformer", "tft", "mamba", "lstm", "gbt"], "default": DEFAULTS["architectures"]},
    {"key": "input_feature_set", "type": "multi_select", "options": ["ohlcv_factor_library", "microstructure", "regime_probabilities", "fama_french", "macro"], "default": DEFAULTS["input_feature_set"]},
    {"key": "patch_length", "type": "integer", "options": [5, 10, 21], "default": 21},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63], "default": 5},
    {"key": "transformer_depth", "type": "integer", "options": [2, 4, 6], "default": 2},
    {"key": "attention_heads", "type": "integer", "options": [4, 8], "default": 4},
    {"key": "dropout_rate", "type": "float", "options": [0.0, 0.1, 0.2, 0.3], "default": 0.1},
]

OUTPUT_CONTRACT = [
    {"key": "architecture_comparison_ic_table", "location": "charts", "renderer": "table", "status": "live_proxy"},
    {"key": "multi_horizon_ic_decay_panel", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "patchtst_attention_heatmap", "location": "charts", "renderer": "heatmap", "status": "live_diagnostic"},
    {"key": "itransformer_cross_sectional_attention_map", "location": "charts", "renderer": "heatmap", "status": "live_diagnostic"},
    {"key": "tft_variable_selection_weights", "location": "charts", "renderer": "bar", "status": "live_diagnostic"},
    {"key": "integrated_gradients_attribution", "location": "charts", "renderer": "bar", "status": "live_proxy"},
    {"key": "patchtst_vs_itransformer_regime_split", "location": "charts", "renderer": "line", "status": "live_proxy"},
    {"key": "ensemble_contribution_chart", "location": "charts", "renderer": "bar", "status": "live_proxy"},
    {"key": "compute_cost_vs_ic_gain_table", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "architecture_comparison", "location": "tables", "renderer": "table", "status": "live_proxy"},
    {"key": "variable_selection", "location": "tables", "renderer": "table", "status": "live_diagnostic"},
]

RESEARCH_ONLY = ["full PatchTST training", "full iTransformer training", "full TFT training", "Mamba sequence model", "GPU training cache"]
IMPLEMENTATION_NOTES = [
    "Realtime output provides deterministic architecture diagnostics and proxy model comparisons from local panels.",
    "Full deep training is explicitly research-mode only because it needs GPU/job orchestration and cached artifacts.",
]


def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["patchtst_full", "itransformer_full", "tft_full", "mamba", "gpu_training"])


def run(payload=None):
    normalized = normalize_feature_payload(payload)
    result = run_sequence_alpha(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)

