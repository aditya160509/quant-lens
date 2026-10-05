"""Feature 12: actual sequence-model training and held-out evaluation."""
from .inputs import inputs, outputs, validate

FEATURE_ID = "12"
FEATURE_TITLE = "Sequence Alpha: Patch and Inverted Transformers, LSTM and MLP"
DEFAULTS = {"architectures": ["patchtst"], "sequence_length": 63, "patch_length": 21,
            "transformer_depth": 2, "attention_heads": 4, "dropout_rate": .1,
            "epochs": 15, "prediction_horizon": 5, "lookback_days": 756, "max_symbols": 20,
            "embargo_period": 5, "random_seed": 7, "compute_mode": "research"}
ALIASES = {"models": "architectures", "horizon": "prediction_horizon"}
INPUT_CONTRACT = [
    {"key": "symbols", "type": "ticker_list"},
    {"key": "architectures", "type": "multi_select", "options": ["patchtst", "itransformer", "lstm", "mlp"], "default": ["patchtst"]},
    {"key": "sequence_length", "type": "integer", "min": 5, "max": 252, "default": 63},
    {"key": "patch_length", "type": "integer", "options": [5, 10, 21], "default": 21},
    {"key": "transformer_depth", "type": "integer", "min": 1, "max": 4, "default": 2},
    {"key": "attention_heads", "type": "integer", "options": [2, 4, 8], "default": 4},
    {"key": "dropout_rate", "type": "number", "min": 0, "max": .5, "default": .1},
    {"key": "epochs", "type": "integer", "min": 1, "max": 100, "default": 15},
    {"key": "prediction_horizon", "type": "integer", "options": [1, 5, 21, 63], "default": 5}]
OUTPUT_CONTRACT = [
    {"key": "architecture_comparison", "location": "charts", "renderer": "table", "status": "live"},
    {"key": "monthly_oos_ic", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "training_loss", "location": "charts", "renderer": "line", "status": "live"},
    {"key": "architecture_comparison", "location": "tables", "renderer": "table", "status": "live"}]
RESEARCH_ONLY = ["TFT, Mamba, integrated gradients and trained attention visualizations are not implemented and are not selectable"]
IMPLEMENTATION_NOTES = ["Actual CPU PyTorch training, with measured durations and training-only normalization."]
INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload):
    from app.services.ml_v2.core.performance import normalize_payload
    return validate(normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES), INPUTS)

def run(payload=None):
    from app.services.ml_v2.core.sequence import run_sequence_alpha
    return run_sequence_alpha(normalize_feature_payload(payload))
