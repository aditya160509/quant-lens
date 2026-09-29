"""Feature 07: Bootstrap validation and factor genuineness scorecard.

Block bootstrap: payload["bootstrap_type"] = "block", payload["block_length"] = 21
Subsampling stability is computed automatically alongside bootstrap.
Bai-Ng criteria use proper SSR-based IC1/IC2/IC3 formulas (not scaled proxies).
Principal angles use proper SVD computation between full-sample and bootstrap loading subspaces.
"""

from __future__ import annotations

import numpy as np

from app.services.pca_v2.core.analytics import (
    bai_ng_criteria,
    bootstrap_validation,
    metadata,
    response,
    rmt_model,
)


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    val = bootstrap_validation(model, payload)
    robust = sum(1 for r in val["genuineness_scorecard"] if r["verdict"] == "Statistically Robust")

    # Proper Bai-Ng IC1/IC2/IC3 from SSR
    bng = bai_ng_criteria(model["returns"], k_max=int(payload.get("bai_ng_k_max") or 15))

    # Subsampling stability heatmap (from bootstrap_validation output)
    sub_stability = val.get("subsampling_stability", [])

    return response(
        "07",
        [
            {"label": "Robust PCs", "value": robust, "unit": "count"},
            {"label": "Bootstrap Runs", "value": val["bootstrap_runs"], "unit": "count"},
            {"label": "Retained PCs", "value": model["k"], "unit": "count"},
            {"label": "Bootstrap Type", "value": val.get("bootstrap_type", "case"), "unit": "mode"},
        ],
        charts={
            "bootstrap_scree_plot": val["bootstrap_bands"],
            "eigenvector_cosine_distribution": val["genuineness_scorecard"],
            "subsampling_stability_heatmap": _stability_heatmap(sub_stability if sub_stability else val["genuineness_scorecard"]),
            "bai_ng_criteria_sweep": bng,
            "principal_angle_analysis": val.get("principal_angles") or [],
        },
        tables={
            "factor_genuineness_scorecard": val["genuineness_scorecard"],
            "bootstrap_eigenvalue_bands": val["bootstrap_bands"],
            "bai_ng_ic_table": bng,
            "subsampling_stability_table": sub_stability,
            "principal_angle_table": val.get("principal_angles") or [],
        },
        meta=metadata(model, {
            "implemented_outputs": 10,
            "bootstrap_mode": val.get("bootstrap_type", "case"),
            "bai_ng_min_IC1_k": min(bng, key=lambda r: r["IC1"])["k"] if bng else None,
            "bai_ng_min_IC2_k": min(bng, key=lambda r: r["IC2"])["k"] if bng else None,
            "bai_ng_min_IC3_k": min(bng, key=lambda r: r["IC3"])["k"] if bng else None,
        }),
    )


def _stability_heatmap(rows):
    """Render subsampling stability as heatmap records."""
    matrix = [r for r in rows if r.get("record_type") == "cross_matrix"]
    if matrix:
        return [{"row": r["row"], "col": r["col"], "value": r["cross_cosine"]} for r in matrix]
    if rows and "mean_cosine" in rows[0]:
        # Subsampling stability rows
        return [{"row": r["component"], "col": r["component"], "value": r["mean_cosine"], "min_cosine": r.get("min_cosine"), "std_cosine": r.get("std_cosine")} for r in rows if "component" in r]
    # Fallback: genuineness scorecard cosine
    return [{"row": r["component"], "col": r["component"], "value": r["cosine_mean"]} for r in rows]
