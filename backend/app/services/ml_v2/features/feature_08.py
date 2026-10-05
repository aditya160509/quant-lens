"""Feature 08: Multi-factor IC-weighted composite signal optimizer."""

from __future__ import annotations

from typing import Any
from .inputs import inputs, outputs, validate

from app.services.ml_v2.core.common import merge_feature_contract


FEATURE_ID = "08"
FEATURE_TITLE = "Multi-Factor IC-Weighted Composite Signal Optimizer"

DEFAULTS: dict[str, Any] = {
    "factor_library": "ohlcv_factor_library",
    "weighting_scheme": "ic_ir",
    "orthogonalization": "gram_schmidt",
    "walk_forward_window": 252,
    "prediction_horizon": 5,
    "lookback_days": 756,
    "max_symbols": 120,
    "compute_mode": "realtime",
}

ALIASES = {"factors": "factor_library", "scheme": "weighting_scheme", "horizon": "prediction_horizon"}

INPUT_CONTRACT = [{'key': 'symbols', 'type': 'ticker_list', 'required': False}, {'key': 'factor_library', 'type': 'select', 'options': ['ohlcv_factor_library'], 'default': 'ohlcv_factor_library'}, {'key': 'weighting_scheme', 'type': 'select', 'options': ['ic', 'ic_ir', 'shrinkage'], 'default': 'ic_ir'}, {'key': 'orthogonalization', 'type': 'select', 'options': ['none', 'gram_schmidt'], 'default': 'gram_schmidt'}, {'key': 'walk_forward_window', 'type': 'integer', 'options': [126, 252, 504], 'default': 252}, {'key': 'output_signal_construction', 'type': 'select', 'options': ['long_short_decile', 'zscore', 'signed_rank'], 'default': 'zscore'}, {'key': 'cost_bps', 'type': 'number', 'min': 0, 'max': 1000, 'default': 5}]

OUTPUT_CONTRACT = [{'key': 'ic_weighted_composite_weights', 'location': 'charts', 'renderer': 'bar', 'status': 'live'}, {'key': 'walk_forward_weight_stability', 'location': 'charts', 'renderer': 'line', 'status': 'live'}, {'key': 'composite_signal_distribution', 'location': 'charts', 'renderer': 'table', 'status': 'live'}, {'key': 'long_short_backtest', 'location': 'charts', 'renderer': 'line', 'status': 'live'}, {'key': 'factor_correlation_heatmap', 'location': 'charts', 'renderer': 'heatmap', 'status': 'live'}, {'key': 'factor_weights', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'latest_composite_scores', 'location': 'tables', 'renderer': 'table', 'status': 'live'}, {'key': 'training_audit', 'location': 'tables', 'renderer': 'table', 'status': 'live'}]

RESEARCH_ONLY = ["server-side persistence of Feature 11 DML APE weights", "custom factor CSV ingestion", "nested/full-library Fama-MacBeth model-selection research sweep"]
IMPLEMENTATION_NOTES = ['Historical IC, IC-IR and covariance-shrinkage weights use matured training dates only.', 'Gram-Schmidt and imputation fit within each historical training window; live-tail scores use those past transforms.', 'Interactions, Fama-MacBeth selection and DML artifact routing are not implemented or advertised.']


INPUTS = inputs(INPUT_CONTRACT, DEFAULTS)
OUTPUTS = outputs(OUTPUT_CONTRACT)

def normalize_feature_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.ml_v2.core.performance import normalize_payload
    return normalize_payload(payload, defaults=DEFAULTS, aliases=ALIASES, research_keys=["custom_factor_csv", "fama_macbeth", "dml_ape"])


def run(payload=None):
    from app.services.ml_v2.core.composite import run_composite_optimizer
    normalized = validate(normalize_feature_payload(payload), INPUTS)
    result = run_composite_optimizer(normalized)
    return merge_feature_contract(result, feature_title=FEATURE_TITLE, input_contract=INPUT_CONTRACT, output_contract=OUTPUT_CONTRACT, research_only=RESEARCH_ONLY, implementation_notes=IMPLEMENTATION_NOTES, payload=normalized)
