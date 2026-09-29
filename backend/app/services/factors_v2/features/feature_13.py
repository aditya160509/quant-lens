"""Feature 13: Live Signal Monitoring Dashboard."""

from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats

from app.services.factors_v2.core.analytics import backtest_series, response, run_feature_module
from app.services.factors_v2.core.performance import (
    bitwise_alignment_score,
    cusum_statistic,
    rolling_corr_kernel,
    rolling_std_percentile_kernel,
    runtime_meta,
    stable_cache_key,
    update_cusum_state,
    welford_rolling,
)

_CUSUM_STATE: dict[str, dict[str, float]] = {}


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload.get("factors"), list) and len(payload.get("factors")) > 1:
        return _run_multi_factor(payload)
    bt = backtest_series(payload)
    r = bt["gross"].dropna()
    f6 = run_feature_module(6, payload)
    if r.empty:
        return response("feature_13", "warning", meta={"warning": "No return proxy available"})
    r_arr = r.to_numpy(dtype=float)
    fwd = np.empty_like(r_arr)
    fwd[:] = np.nan
    if len(r_arr) > 21:
        fwd[:-21] = r_arr[21:]
    ic = pd.Series(rolling_corr_kernel(r_arr, fwd, 21), index=r.index).dropna()
    cusum = pd.Series(cusum_statistic(ic.to_numpy(dtype=float)), index=ic.index).dropna() if len(ic) else pd.Series(dtype=float)
    cusum_threshold = float(payload.get("cusum_threshold", 1.36))
    recent = float(ic.tail(63).mean()) if len(ic) else 0
    means, variances = welford_rolling(ic.to_numpy(dtype=float), 252) if len(ic) else (np.asarray([]), np.asarray([]))
    base_mean = float(means[-64]) if len(means) > 64 and np.isfinite(means[-64]) else float(ic.mean() if len(ic) else 0)
    base_std = float(np.sqrt(variances[-64])) if len(variances) > 64 and np.isfinite(variances[-64]) else float(ic.std() if len(ic) else 0)
    z = float((recent - base_mean) / (base_std / np.sqrt(63))) if base_std else 0
    crowd = (f6.get("summary_cards") or [{}])[0].get("value") or 50
    crowd_pct = pd.Series(rolling_std_percentile_kernel(r_arr, 63), index=r.index)
    crowd_velocity = float(crowd_pct.diff(21).iloc[-1])
    break_flag = bool((cusum.iloc[-1] if len(cusum) else 0) > cusum_threshold)
    state_key = stable_cache_key("feature_13", payload, "cusum_state")
    state = _CUSUM_STATE.setdefault(state_key, {})
    incremental_cusum = update_cusum_state(state, recent, base_mean)
    alignment_score = bitwise_alignment_score(ic.to_numpy(dtype=float)[-252:], r_arr[-252:])
    chow = _weekly_chow_proxy(ic)
    thresholds = {
        "ic_drift_z": float(payload.get("ic_drift_threshold", -1.5)),
        "crowding_velocity": float(payload.get("crowding_velocity_threshold", 15.0)),
        "cusum_threshold": cusum_threshold,
        "weekly_chow_cache_key": stable_cache_key("feature_13", payload, "weekly_chow_diagnostic"),
        "cooldown_hours": int(payload.get("alert_cooldown_hours", 24)),
    }
    health = np.nanmean([100 * min(max((z + 3) / 6, 0), 1), 0 if break_flag else 100, max(0, 100 - crowd_velocity), alignment_score * 100])
    rows = [{"factor": bt["factor"], "recent_ic": recent, "ic_z_score": z, "cusum_stat": float(cusum.iloc[-1]) if len(cusum) else None, "incremental_cusum": incremental_cusum, "crowding_percentile": crowd, "crowding_velocity": crowd_velocity, "alignment_score": alignment_score, "health_score": float(health), "break_flag": bool(break_flag)}]
    alerts = []
    if z < thresholds["ic_drift_z"]:
        alerts.append({"level": "high", "type": "ic_drift", "message": "IC drift threshold breached", **rows[0]})
    if crowd_velocity > thresholds["crowding_velocity"]:
        alerts.append({"level": "medium", "type": "crowding_velocity", "message": "Crowding velocity threshold breached", **rows[0]})
    if health < 50 or break_flag:
        alerts.append({"level": "high", "type": "signal_health", "message": "Signal health degraded", **rows[0]})
    alert_policy = [
        {"channel": "in_app", "status": "enabled", "cadence": "immediate"},
        {"channel": "email_digest", "status": payload.get("email_digest", "configurable"), "cadence": payload.get("email_cadence", "daily")},
        {"channel": "slack", "status": "beta_requires_auth", "cadence": "cooldown_guarded"},
        {"channel": "webhook", "status": "ready" if payload.get("webhook_url") else "not_configured", "url_present": bool(payload.get("webhook_url"))},
    ]
    resolution = [{"factor": bt["factor"], "state": "open" if alerts else "clear", "cooldown_hours": thresholds["cooldown_hours"], "resolution_rule": "alert clears when metric recovers inside threshold band"}]
    return response(
        "feature_13",
        "ok",
        summary_cards=[{"label": "Signal Health", "value": float(health)}, {"label": "IC Drift Z", "value": z}],
        charts={"ic_drift": [{"date": k, "value": v} for k, v in ic.tail(260).items()], "cusum_structural_break": [{"date": k, "value": v} for k, v in cusum.tail(260).items()], "crowding_velocity": [{"date": k, "value": v} for k, v in crowd_pct.diff(21).tail(260).items()]},
        tables={"signal_health": rows, "alert_log": alerts, "alert_policy": alert_policy, "alert_resolution_tracking": resolution, "weekly_chow_diagnostic": chow},
        alerts=alerts,
        meta={
            **runtime_meta("feature_13", payload, ["single rolling CUSUM structural-break test in realtime; Chow refreshed weekly/cached"]),
            "portfolio_weighted_health": float(health),
            "method": "factor-return persistence surveillance proxy; true cross-sectional IC drift requires stored point-in-time characteristic snapshots",
            "thresholds": thresholds,
            "chow_policy": "weekly cached diagnostic only; not recomputed at every trailing date",
            "webhook_delivery": "payload generated; router remains dormant until wired and webhook worker is enabled",
            "audit_closures": ["multi-factor library payload support", "weekly cached Chow-style diagnostic", "return-characteristic alignment metric"],
        },
    )


def _run_multi_factor(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    alerts = []
    for factor in payload.get("factors", [])[:25]:
        sub_payload = {**payload, "factor": factor}
        sub_payload.pop("factors", None)
        out = run(sub_payload)
        row = (out.get("tables", {}).get("signal_health") or [{}])[0]
        if row:
            rows.append(row)
        alerts.extend(out.get("alerts", []))
    if not rows:
        return response("feature_13", "warning", meta={"warning": "No factor health rows available"})
    weights = payload.get("factor_weights") or {}
    if weights:
        total_w = sum(abs(float(weights.get(row["factor"], 0.0))) for row in rows) or 1.0
        portfolio_health = sum(float(weights.get(row["factor"], 0.0)) / total_w * float(row.get("health_score", 0.0)) for row in rows)
    else:
        portfolio_health = float(np.nanmean([row.get("health_score", np.nan) for row in rows]))
    return response(
        "feature_13",
        "ok",
        summary_cards=[{"label": "Portfolio Signal Health", "value": portfolio_health}, {"label": "Factors Monitored", "value": len(rows)}],
        charts={},
        tables={"signal_health": rows, "alert_log": alerts[:100]},
        alerts=alerts,
        meta={**runtime_meta("feature_13", payload, ["single rolling CUSUM per factor; multi-factor aggregation loops over factor library"]), "portfolio_weighted_health": portfolio_health},
    )


def _weekly_chow_proxy(ic: pd.Series) -> list[dict[str, Any]]:
    s = pd.to_numeric(ic, errors="coerce").dropna().tail(252)
    if len(s) < 80:
        return [{"status": "insufficient_history", "sample_size": int(len(s))}]
    split = len(s) // 2
    left = s.iloc[:split]
    right = s.iloc[split:]
    pooled_var = float(s.var(ddof=2))
    if pooled_var <= 0:
        return [{"status": "flat_series", "sample_size": int(len(s))}]
    stat = float(((left.mean() - right.mean()) ** 2) / (pooled_var * (1 / len(left) + 1 / len(right))))
    p_value = float(1 - stats.f.cdf(stat, 1, max(len(s) - 2, 1)))
    return [{
        "diagnostic": "weekly_chow_mean_shift_proxy",
        "split_date": str(pd.Timestamp(s.index[split]).date()),
        "statistic": stat,
        "p_value": p_value,
        "significant_5pct": p_value < 0.05,
        "sample_size": int(len(s)),
        "cache_policy": "weekly_cached_not_daily_scan",
    }]
