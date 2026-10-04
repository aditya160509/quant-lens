"""Feature 08: PCA residual cross-correlation and contagion monitor.

Rolling group residual correlation is computed as the primary chart (multi-sector time series).
Crisis overlay dates are returned for frontend annotation.
"""

from __future__ import annotations

import numpy as np

from app.services.pca_v2.core.analytics import (
    matrix_records,
    metadata,
    residual_contagion,
    residual_tensor_hosvd,
    response,
    rolling_group_residual_corr,
    rmt_model,
    residual_matrix,
)

# Crisis overlay: annotated date bands for frontend rendering
CRISIS_DATES = [
    {"label": "GFC", "start": "2008-09-01", "end": "2009-03-31", "color": "red"},
    {"label": "Flash Crash", "start": "2010-05-06", "end": "2010-05-10", "color": "red"},
    {"label": "Euro Debt", "start": "2011-07-01", "end": "2012-06-30", "color": "orange"},
    {"label": "Taper Tantrum", "start": "2013-05-22", "end": "2013-09-05", "color": "orange"},
    {"label": "China Devaluation", "start": "2015-08-11", "end": "2016-02-12", "color": "orange"},
    {"label": "Vol Shock", "start": "2018-02-02", "end": "2018-02-09", "color": "purple"},
    {"label": "COVID", "start": "2020-02-01", "end": "2020-05-31", "color": "purple"},
    {"label": "Rate Shock", "start": "2022-01-03", "end": "2022-10-21", "color": "blue"},
    {"label": "Bank Stress", "start": "2023-03-08", "end": "2023-05-05", "color": "blue"},
    {"label": "Liberation Day", "start": "2025-04-02", "end": "2025-04-15", "color": "blue"},
]


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    cont = residual_contagion(model, payload)
    max_group = max(cont["group_rows"], key=lambda r: abs(r["avg_pairwise_residual_corr"])) if cont["group_rows"] else {}
    status = "Factor Model Under-Specified" if cont["lambda1_residual"] > float(payload.get("lambda1_threshold") or 1.3) else "Factor Model Adequate"
    alerts = [{"level": "warning", "message": status, "lambda1_residual": cont["lambda1_residual"]}] if status.endswith("Under-Specified") else []

    # Rolling group residual correlation time series (PRIMARY CHART)
    rolling_group_ts = rolling_group_residual_corr(model, payload, window=int(payload.get("residual_window") or 63))
    rolling_lambda1 = _rolling_residual_lambda1(model, int(payload.get("residual_window") or 63))
    current_percentile = float(np.mean([r["lambda1_residual"] <= cont["lambda1_residual"] for r in rolling_lambda1]) * 100.0) if rolling_lambda1 else None
    tensor = residual_tensor_hosvd(model, payload)

    return response(
        "08",
        [
            {"label": "Residual Lambda1", "value": cont["lambda1_residual"], "unit": "eigenvalue"},
            {"label": "Max Group Corr", "value": max_group.get("avg_pairwise_residual_corr"), "unit": "corr"},
            {"label": "Status", "value": status, "unit": "state"},
        ],
        charts={
            "rolling_group_residual_corr_time_series": rolling_group_ts,
            "residual_correlation_matrix": matrix_records(cont["residual_corr"], limit=90),
            "residual_lambda1_by_k": cont["under_specification"],
            "rolling_residual_lambda1": rolling_lambda1,
            "under_specification_diagnostic": cont["under_specification"],
            "residual_correlation_by_group": cont["group_rows"],
            "crisis_overlay_dates": CRISIS_DATES,
            "residual_frequency_tensor": tensor["core_records"],
            "residual_tensor_group_singular_values": tensor["group_singular_values"],
            "residual_tensor_window_singular_values": tensor["window_singular_values"],
            "residual_tensor_time_singular_values": tensor["time_singular_values"],
        },
        tables={
            "contagion_spike_detector": cont["pairs"],
            "residual_correlation_regime_alert": [{"status": status, "lambda1_residual": cont["lambda1_residual"], "lambda1_historical_percentile": current_percentile, "max_group": max_group}],
            "residual_tensor_summary": tensor["summary"],
        },
        alerts=alerts,
        meta=metadata(model, {"implemented_outputs": 13, "rolling_group_ts_records": len(rolling_group_ts), "residual_tensor": "hosvd_tucker", "residual_fit": "causal_rolling" if payload.get("rolling_refit") else "fixed_full_sample_retrospective"}),
    )


def _rolling_residual_lambda1(model, window):
    resid = residual_matrix(model).fillna(0.0)
    if len(resid) < window:
        return []
    rows = []
    step = max(1, int(window // 10))
    for end in range(window, len(resid) + 1, step):
        corr = resid.iloc[end - window:end].corr().fillna(0.0).to_numpy(dtype=float)
        value = float(np.linalg.eigvalsh((corr + corr.T) / 2.0)[-1])
        rows.append({"date": str(resid.index[end - 1])[:10], "lambda1_residual": value})
    return rows


from .inputs import inputs_for
INPUTS = inputs_for("08")
OUTPUTS = [{'key': 'rolling_group_residual_corr_time_series', 'source': 'charts', 'label': 'Rolling Group Residual Corr Time Series', 'render': 'line', 'primary': True}, {'key': 'residual_correlation_matrix', 'source': 'charts', 'label': 'Residual Correlation Matrix', 'render': 'heatmap', 'primary': False}, {'key': 'residual_lambda1_by_k', 'source': 'charts', 'label': 'Residual Lambda1 By K', 'render': 'bar', 'primary': False}, {'key': 'rolling_residual_lambda1', 'source': 'charts', 'label': 'Rolling Residual Lambda1', 'render': 'line', 'primary': False}, {'key': 'under_specification_diagnostic', 'source': 'charts', 'label': 'Under Specification Diagnostic', 'render': 'bar', 'primary': False}, {'key': 'residual_correlation_by_group', 'source': 'charts', 'label': 'Residual Correlation By Group', 'render': 'bar', 'primary': False}, {'key': 'crisis_overlay_dates', 'source': 'charts', 'label': 'Crisis Overlay Dates', 'render': 'bar', 'primary': False}, {'key': 'residual_frequency_tensor', 'source': 'charts', 'label': 'Residual Frequency Tensor', 'render': 'bar', 'primary': False}, {'key': 'residual_tensor_group_singular_values', 'source': 'charts', 'label': 'Residual Tensor Group Singular Values', 'render': 'bar', 'primary': False}, {'key': 'residual_tensor_window_singular_values', 'source': 'charts', 'label': 'Residual Tensor Window Singular Values', 'render': 'bar', 'primary': False}, {'key': 'residual_tensor_time_singular_values', 'source': 'charts', 'label': 'Residual Tensor Time Singular Values', 'render': 'bar', 'primary': False}, {'key': 'contagion_spike_detector', 'source': 'tables', 'label': 'Contagion Spike Detector', 'render': 'table', 'primary': False}, {'key': 'residual_correlation_regime_alert', 'source': 'tables', 'label': 'Residual Correlation Regime Alert', 'render': 'table', 'primary': False}, {'key': 'residual_tensor_summary', 'source': 'tables', 'label': 'Residual Tensor Summary', 'render': 'table', 'primary': False}]
