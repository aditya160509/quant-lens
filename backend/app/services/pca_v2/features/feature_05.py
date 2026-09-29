"""Feature 05: Rolling eigenvalue stability and regime transition monitor.

Now includes:
- PC1 percentile rank (live alert): current PC1 share as percentile of 252-day history
- PC1 loading evolution heatmap: N×T matrix of loading values across rolling windows
- Principal angles between consecutive K-dim loading subspaces (already in rolling_pca_metrics)
- Blend-gamma covariance toggle: payload["blend_gamma"] in [0,1] (0=RMT-cleaned, 1=raw sample)
"""

from __future__ import annotations

import pandas as pd

from app.services.pca_v2.core.analytics import (
    blend_covariance,
    bai_perron_breakpoints,
    compact_records,
    cusum_table,
    matrix_records,
    metadata,
    pc1_percentile_rank,
    response,
    rolling_loading_evolution,
    rolling_pca_metrics,
    rmt_model,
    tensor_hosvd_proxy,
)


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)

    # Blend-gamma covariance (wires slider to covariance used in the response)
    blend_gamma = float(payload.get("blend_gamma") or 0.0)
    blended_cov = blend_covariance(model, blend_gamma)  # ndarray, used in meta
    blend_note = f"blend_gamma={blend_gamma:.2f}: {'full RMT-cleaned' if blend_gamma == 0 else 'full raw sample' if blend_gamma == 1 else f'{(1-blend_gamma)*100:.0f}% RMT + {blend_gamma*100:.0f}% raw'}"

    roll = rolling_pca_metrics(payload)
    latest = roll.sort_values("date").groupby("window").tail(1) if not roll.empty else pd.DataFrame()
    cusum = cusum_table(
        roll[roll["window"].eq(63)]["pc1_share"] if not roll.empty and (roll["window"] == 63).any() else pd.Series(dtype=float)
    )
    bp_series = roll[roll["window"].eq(63)].sort_values("date").set_index("date")["pc1_share"] if not roll.empty and (roll["window"] == 63).any() else pd.Series(dtype=float)
    bai_perron = bai_perron_breakpoints(bp_series, max_breaks=int(payload.get("max_breaks") or 3), min_segment=int(payload.get("break_min_segment") or 8))
    tensor = tensor_hosvd_proxy(model, payload)

    # PC1 percentile rank per window
    pc1_pct = pc1_percentile_rank(roll, history_window=int(payload.get("percentile_history_window") or 252))

    # PC1 loading evolution (downsampled N×T matrix)
    pc_to_track = int(payload.get("loading_evolution_pc") or 0)  # 0-indexed
    loading_evo = rolling_loading_evolution(
        payload=payload,
        window=int(payload.get("loading_evolution_window") or 126),
        step=int(payload.get("loading_evolution_step") or 21),
        pc_idx=pc_to_track,
        max_dates=int(payload.get("loading_evolution_max_dates") or 60),
    )

    # Alert logic: z-score OR cosine instability OR HIGH percentile (structural jump)
    alert_rows = (
        latest[
            (latest["pc1_zscore"].abs() > 2)
            | (latest["pc1_cosine_stability"] < 0.85)
        ]
        if not latest.empty
        else pd.DataFrame()
    )
    alerts = [
        {"level": "warning", "message": f"PCA regime instability on {int(r.window)}D window", "window": int(r.window)}
        for r in alert_rows.itertuples()
    ]
    # Add HIGH percentile alerts
    for w, pct_info in pc1_pct.items():
        if pct_info["alert"] == "HIGH":
            alerts.append({"level": "alert", "message": f"PC1 share at {pct_info['percentile_rank']:.0f}th percentile of {w}D history", "window": w})

    # Principal angle alert (rolling_pca_metrics already computes max_principal_angle_deg)
    pa_col = "max_principal_angle_deg"
    if not roll.empty and pa_col in roll.columns:
        latest_pa = roll.sort_values("date").groupby("window").tail(1)
        for r in latest_pa.itertuples():
            if getattr(r, pa_col, 0) > 15:
                alerts.append({"level": "warning", "message": f"Large principal angle ({getattr(r, pa_col):.1f}°) on {int(r.window)}D window", "window": int(r.window)})

    return response(
        "05",
        [
            {"label": "PC1 Current", "value": float(latest["pc1_share"].mean()) if not latest.empty else None, "unit": "share"},
            {"label": "Break Alerts", "value": len(alerts), "unit": "count"},
            {"label": "Min Stability", "value": float(latest["pc1_cosine_stability"].min()) if not latest.empty else None, "unit": "cosine"},
            {"label": "PC1 Percentile (63D)", "value": pc1_pct.get(63, {}).get("percentile_rank"), "unit": "pct"},
            {"label": "Blend Gamma", "value": blend_gamma, "unit": "slider"},
        ],
        charts={
            "rolling_pc1_share": compact_records(roll, limit=500),
            "eigenvector_drift": compact_records(roll[["date", "window", "pc1_cosine_stability"]], limit=500) if not roll.empty else [],
            "cusum_structural_break": cusum,
            "eigenvalue_ratio_time_series": compact_records(roll[["date", "window", "eigen_ratio_k"]], limit=500) if not roll.empty else [],
            "pc1_loading_evolution_heatmap": loading_evo,
            "principal_angle_time_series": compact_records(
                roll[["date", "window", "max_principal_angle_deg"]], limit=500
            ) if not roll.empty and "max_principal_angle_deg" in roll.columns else [],
            "multi_eigenvalue_time_series": compact_records(roll[[c for c in roll.columns if c in {"date", "window"} or c.startswith("eigenvalue_pc")]], limit=500) if not roll.empty else [],
            "multi_pc_cosine_drift": compact_records(roll[[c for c in roll.columns if c in {"date", "window"} or c.startswith("cosine_pc")]], limit=500) if not roll.empty else [],
            "crisis_annotation_bands": _crisis_bands(),
            "multi_frequency_regime_tensor": tensor["core_records"],
            "tensor_factor_singular_values": tensor["factor_singular_values"],
            "tensor_window_singular_values": tensor["window_singular_values"],
            "tensor_time_singular_values": tensor["time_singular_values"],
        },
        tables={
            "current_regime_readout": compact_records(latest, limit=20),
            "breakpoint_table": [r for r in cusum if r.get("break")],
            "bai_perron_breakpoint_table": bai_perron,
            "pc1_percentile_rank_table": [{"window": w, **v} for w, v in pc1_pct.items()],
            "regime_summary_table": _regime_summary(roll, bai_perron),
        },
        alerts=alerts,
        meta=metadata(model, {
            "implemented_outputs": 14,
            "blend_gamma": blend_gamma,
            "blend_note": blend_note,
            "blended_cov_trace": float(blended_cov.trace()),
            "tensor_decomposition": "hosvd_tucker",
        }),
    )


def _crisis_bands():
    return [
        {"label": "GFC", "start": "2008-09-01", "end": "2009-03-31"},
        {"label": "Flash Crash", "start": "2010-05-06", "end": "2010-05-10"},
        {"label": "Euro Debt", "start": "2011-07-01", "end": "2012-06-30"},
        {"label": "Taper Tantrum", "start": "2013-05-22", "end": "2013-09-30"},
        {"label": "China Devaluation", "start": "2015-08-10", "end": "2015-09-30"},
        {"label": "Vol Shock", "start": "2018-02-01", "end": "2018-02-15"},
        {"label": "COVID", "start": "2020-02-01", "end": "2020-05-31"},
        {"label": "Rate Shock", "start": "2022-09-01", "end": "2022-11-30"},
        {"label": "Quant Unwind", "start": "2024-08-01", "end": "2024-08-15"},
        {"label": "Liberation Day", "start": "2025-04-02", "end": "2025-04-15"},
    ]


def _regime_summary(roll, breakpoints):
    if roll.empty:
        return []
    base = roll[roll["window"].eq(63)].sort_values("date")
    if base.empty:
        return []
    dates = [pd.Timestamp(base["date"].min())] + sorted(pd.Timestamp(row.get("date")) for row in breakpoints if row.get("date")) + [pd.Timestamp(base["date"].max())]
    rows = []
    for start, end in zip(dates[:-1], dates[1:]):
        sample = base[(pd.to_datetime(base["date"]) >= start) & (pd.to_datetime(base["date"]) <= end)]
        if len(sample):
            rows.append({"start_date": str(start.date()), "end_date": str(end.date()), "duration_days": int((end - start).days), "avg_pc1_share": float(sample["pc1_share"].mean()), "min_cosine_stability": float(sample["pc1_cosine_stability"].min())})
    return rows
