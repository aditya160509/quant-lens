"""Feature 01: RMT noise-filtered covariance engine.

Iterative σ² fitting (moment-matching) is applied in rmt_model() by default.
Outlier pre-processing (winsorize daily returns with |z| > 4) is controlled via:
  payload["outlier_filter"] = true/false (default: true)
  payload["outlier_z_threshold"] = float (default: 4.0)

The fitted σ² is stored in model["cov_meta"]["fitted_sigma2"] and returned
in the response for full transparency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.pca_v2.core.analytics import blend_covariance, compact_records, matrix_records, metadata, response, rmt_model


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    evals = model["eigenvalues"]
    total = max(float(evals.sum()), 1e-12)
    condition_raw = float(evals[0] / max(evals[-1], 1e-12))
    clean_evals = model["cleaned_eigenvalues"]
    condition_clean = float(clean_evals[0] / max(clean_evals[-1], 1e-12))
    spectrum = pd.DataFrame(
        {
            "rank": np.arange(1, len(evals) + 1),
            "eigenvalue": evals,
            "explained_variance": evals / total,
            "cumulative_variance": np.cumsum(evals) / total,
            "mp_lambda_max": model["mp"]["lambda_max"],
            "classification": np.where(evals > model["mp"]["lambda_max"], "Signal", "Noise"),
            "margin_to_mp": evals - model["mp"]["lambda_max"],
        }
    )
    conditions = [
        {"matrix": "raw", "condition_number": condition_raw},
        {"matrix": "rmt_cleaned", "condition_number": condition_clean},
        {"matrix": "improvement_multiple", "condition_number": condition_raw / max(condition_clean, 1e-12)},
    ]
    blend_gamma = float(payload.get("blend_gamma") or 0.0)
    blended_cov = blend_covariance(model, blend_gamma)
    fitted_sigma2 = model["cov_meta"].get("fitted_sigma2")
    summary = [
        {"label": "Signal PCs", "value": model["k"], "unit": "count", "detail": "Selected by RMT unless overridden"},
        {"label": "MP Lambda Max", "value": model["mp"]["lambda_max"], "unit": "eigenvalue"},
        {"label": "Fitted σ²", "value": fitted_sigma2, "unit": "noise_var", "detail": "Iterative moment-matching"},
        {"label": "Raw Condition", "value": condition_raw, "unit": "ratio"},
        {"label": "Cleaned Condition", "value": condition_clean, "unit": "ratio"},
        {"label": "Outlier Filter", "value": payload.get("outlier_method", "none"), "unit": "mode"},
        {"label": "Blend Gamma", "value": blend_gamma, "unit": "slider", "detail": "0=full RMT, 1=raw sample"},
    ]
    return response(
        "01",
        summary,
        charts={
            "eigenvalue_spectrum_mp": compact_records(spectrum, limit=300),
            "scree_multi_cutoff": compact_records(spectrum, limit=300),
            "raw_covariance_heatmap": matrix_records(pd.DataFrame(model["cov"], index=model["symbols"], columns=model["symbols"]), limit=80),
            "cleaned_covariance_heatmap": matrix_records(pd.DataFrame(model["cleaned_cov"], index=model["symbols"], columns=model["symbols"]), limit=80),
            "blended_covariance_heatmap": matrix_records(pd.DataFrame(blended_cov, index=model["symbols"], columns=model["symbols"]), limit=80),
            "covariance_difference_heatmap": matrix_records(pd.DataFrame(model["cleaned_cov"] - model["cov"], index=model["symbols"], columns=model["symbols"]), limit=80),
            "condition_number_panel": conditions,
        },
        tables={
            "signal_vs_noise_eigenvalue_table": compact_records(spectrum, limit=500),
            "condition_number_table": conditions,
            "ledoit_wolf_shrinkage_diagnostic": [model["cov_meta"]],
            "audit_trail": [metadata(model)],
        },
        meta=metadata(model, {
            "implemented_outputs": 9,
            "fitted_sigma2": fitted_sigma2,
            "outlier_method": payload.get("outlier_method", "none"),
            "outlier_filter_z_threshold": payload.get("outlier_z_threshold", 4.0),
            "condition_number_raw": condition_raw,
            "condition_number_cleaned": condition_clean,
            "q_ratio": model["mp"].get("q"),
            "lambda_max": model["mp"].get("lambda_max"),
            "retained_eigenvectors": model["eigenvectors"][:, :model["k"]].tolist(),
        }),
    )
