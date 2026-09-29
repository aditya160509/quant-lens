"""Feature 5: Alpha Decay and Factor Half-Life Analysis."""

from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import optimize

from app.services.factors_v2.core.analytics import DEFAULT_FACTORS, backtest_series, characteristic_panel, response
from app.services.factors_v2.core.performance import (
    batched_forward_sums,
    cap_realtime,
    runtime_meta,
    vectorized_rolling_ic_matrix,
)


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    bt = backtest_series(payload)
    r = bt["gross"].dropna()
    horizons = payload.get("horizons", [1, 5, 10, 21, 42, 63, 126, 252])
    if r.empty:
        return response("feature_05", "warning", meta={"warning": "No factor return proxy available"})
    bootstrap_samples = cap_realtime(int(payload.get("bootstrap_samples", 400)), 400, 1200, payload)
    horizons_arr = np.asarray([int(h) for h in horizons], dtype=np.int64)
    r_arr = r.to_numpy(dtype=float)
    forward_matrix = batched_forward_sums(r_arr, horizons_arr)
    ic_matrix = vectorized_rolling_ic_matrix(r_arr, forward_matrix, 63)
    rows = []
    ic_series_by_h = {}
    for idx, h in enumerate(horizons_arr):
        ic = pd.Series(ic_matrix[idx], index=r.index).dropna()
        ic_series_by_h[int(h)] = ic
        mean_ic = float(ic.mean()) if len(ic) else None
        icir = float(mean_ic / ic.std() * np.sqrt(252 / h)) if len(ic) and ic.std() else None
        lo, hi = _bootstrap_mean_ci(ic, bootstrap_samples)
        rows.append({"horizon": h, "mean_ic": mean_ic, "ic_lower_95": lo, "ic_upper_95": hi, "icir": icir, "observations": int(len(ic))})
    sign_positive_rate = float(np.nanmean([(row["mean_ic"] or 0) >= 0 for row in rows]))
    unstable = sign_positive_rate < 0.7
    x = np.array([row["horizon"] for row in rows], dtype=float)
    y = np.array([row["mean_ic"] or 0 for row in rows], dtype=float)
    fits = _fit_decay(x, y)
    winner = max(fits, key=lambda k: fits[k]["r_squared"])
    half_lo, half_hi = _bootstrap_half_life(rows, winner, bootstrap_samples)
    max_window = int(payload.get("window_days", len(r)))
    if fits[winner].get("half_life") and fits[winner]["half_life"] > max_window:
        fits[winner]["half_life_flag"] = "Half-Life >= Window Length"
        fits[winner]["half_life"] = float(max_window)
    if unstable:
        fits[winner]["half_life_flag"] = "Signal Unstable - Half-Life Unreliable"
    rolling = []
    rolling_window = int(payload.get("rolling_window_days", 252))
    for end in range(rolling_window, len(r), 21):
        idx0 = max(0, end - rolling_window)
        sub_y = [float(np.mean(values)) if len(values := ic_matrix[hidx, idx0:end][np.isfinite(ic_matrix[hidx, idx0:end])]) else 0.0 for hidx in range(ic_matrix.shape[0])]
        rolling.append({"date": r.index[end - 1], "half_life": _fit_decay(x, np.array(sub_y))[winner]["half_life"]})
    freq_rows = []
    for freq in [1, 5, 10, 21, 42, 63, 126, 252]:
        hrow = min(rows, key=lambda row: abs(row["horizon"] - freq))
        tc = (float(payload.get("cost_bps", 8)) / 10000) / max(float(payload.get("portfolio_vol", 0.15)), 1e-6)
        freq_rows.append({"rebalance_days": freq, "gross_ic": hrow["mean_ic"], "cost_ic": tc, "net_annual_ic": (hrow["mean_ic"] or 0) * (252 / freq) - tc * (252 / freq)})
    sector_neutral = _sector_neutral_snapshot(payload) if payload.get("selected_sector") else [{"measure": "sector_drilldown", "value": "select selected_sector for realtime sector-level decay"}]
    cross_sector = _cross_sector_decay(payload, rows, horizons_arr)
    multi_factor_radar = _multi_factor_power_radar(payload, horizons_arr)
    post_2015 = _post_2015_acceleration_test(r, horizons_arr)
    return response(
        "feature_05",
        "ok",
        summary_cards=[
            {"label": "Winning Decay Model", "value": winner},
            {"label": "Half-Life", "value": None if unstable else fits[winner]["half_life"], "unit": "trading_days"},
            {"label": "Half-Life 95% CI", "value": f"{half_lo:.1f} - {half_hi:.1f}" if half_lo is not None else None},
            {"label": "IC Sign Consistency", "value": sign_positive_rate},
        ],
        charts={
            "ic_decay_curve": rows,
            "decay_model_fits": [{"model": k, **v} for k, v in fits.items()],
            "icir_by_horizon": [{"horizon": row["horizon"], "icir": row["icir"], "mean_ic": row["mean_ic"]} for row in rows],
            "rolling_half_life": rolling[-120:],
            "rebalancing_cost_curve": freq_rows,
            "factor_signal_power_radar": _signal_power_radar(rows, fits[winner], sign_positive_rate),
            "multi_factor_decay_dashboard": rows,
            "cross_sector_decay": cross_sector,
            "multi_factor_power_radar": multi_factor_radar,
        },
        tables={"decay_models": [{"model": k, **v} for k, v in fits.items()], "ic_by_horizon": rows, "optimal_rebalancing": freq_rows, "sector_neutral_ic": sector_neutral, "cross_sector_decay": cross_sector, "multi_factor_power_radar": multi_factor_radar, "post_2015_acceleration_test": post_2015},
        alerts=[{"level": "high", "message": "Signal has reversed sign too often; half-life suppressed", "positive_ic_rate": sign_positive_rate}] if unstable else [],
        meta={
            **runtime_meta("feature_05", payload, ["full-universe decay default; sector-level decay only for selected_sector drill-down"]),
            "factor": bt["factor"],
            "method": "Spearman/tie-adjusted rank IC proxy; half-life suppressed when sign consistency fails",
            "half_life_flag": fits[winner].get("half_life_flag"),
            "bootstrap_samples": bootstrap_samples,
            "audit_closures": ["post-2015 half-life acceleration split test"],
        },
    )


def _bootstrap_mean_ci(series, samples):
    x = series.dropna().values
    if len(x) < 20:
        return None, None
    rng = np.random.default_rng(505)
    means = np.mean(rng.choice(x, size=(int(samples), len(x)), replace=True), axis=1)
    return tuple(float(value) for value in np.quantile(means, [0.025, 0.975]))


def _signal_power_radar(rows: list[dict[str, Any]], winner_fit: dict[str, Any], sign_positive_rate: float) -> list[dict[str, Any]]:
    valid_ic = [abs(float(row.get("mean_ic") or 0.0)) for row in rows]
    valid_icir = [abs(float(row.get("icir") or 0.0)) for row in rows]
    half_life = float(winner_fit.get("half_life") or 0.0)
    fit_quality = float(winner_fit.get("r_squared") or 0.0)
    return [
        {"axis": "IC strength", "value": min(100.0, (max(valid_ic) if valid_ic else 0.0) * 1000.0)},
        {"axis": "ICIR stability", "value": min(100.0, (max(valid_icir) if valid_icir else 0.0) * 35.0)},
        {"axis": "Half-life", "value": min(100.0, half_life / 252.0 * 100.0)},
        {"axis": "Fit quality", "value": max(0.0, min(100.0, fit_quality * 100.0))},
        {"axis": "Sign consistency", "value": max(0.0, min(100.0, sign_positive_rate * 100.0))},
    ]


def _bootstrap_half_life(rows, winner, samples):
    x = np.array([row["horizon"] for row in rows], dtype=float)
    y = np.array([row["mean_ic"] or 0.0 for row in rows], dtype=float)
    if len(x) < 4 or samples < 10:
        return None, None
    fitted, params = _fit_single_decay_model(winner, x, y)
    if fitted is None or params is None:
        return None, None
    base_half_life = _extract_half_life(winner, params)
    if base_half_life is None or not np.isfinite(base_half_life):
        return None, None
    residuals = y - fitted
    rng = np.random.default_rng(2025)
    boot_half_lives = []
    for _ in range(int(samples)):
        y_boot = fitted + rng.choice(residuals, size=len(residuals), replace=True)
        _, boot_params = _fit_single_decay_model(winner, x, y_boot)
        if boot_params is None:
            continue
        hl = _extract_half_life(winner, boot_params)
        if hl is not None and np.isfinite(hl) and 0 < hl < 2000:
            boot_half_lives.append(float(hl))
    if len(boot_half_lives) < max(10, samples // 5):
        std_hl = float(np.std(boot_half_lives)) if boot_half_lives else float(base_half_life) * 0.3
        return float(max(0.0, base_half_life - 1.96 * std_hl)), float(base_half_life + 1.96 * std_hl)
    return float(max(0.0, np.percentile(boot_half_lives, 2.5))), float(np.percentile(boot_half_lives, 97.5))


def _fit_single_decay_model(model: str, x: np.ndarray, y: np.ndarray):
    try:
        if model == "linear":
            coef = np.polyfit(x, y, 1)
            return np.polyval(coef, x), coef
        if model == "exponential":
            popt, _ = optimize.curve_fit(
                lambda h, a, b: a * np.exp(np.clip(-b * h, -60, 60)),
                x,
                y,
                p0=[y[0] or 0.01, 1 / 21],
                maxfev=3000,
                bounds=([0, 1e-6], [1, 5]),
            )
            return popt[0] * np.exp(np.clip(-popt[1] * x, -60, 60)), popt
        if model == "hyperbolic":
            popt, _ = optimize.curve_fit(
                lambda h, a, b: a / (1 + b * h),
                x,
                y,
                p0=[y[0] or 0.01, 1 / 21],
                maxfev=3000,
                bounds=([0, 1e-6], [1, 5]),
            )
            return popt[0] / (1 + popt[1] * x), popt
    except Exception:
        return None, None
    return None, None


def _extract_half_life(model: str, params: np.ndarray):
    try:
        if model == "linear":
            slope = float(params[0])
            intercept = float(params[1])
            if abs(slope) < 1e-10:
                return None
            ic1 = intercept + slope
            return abs(float((ic1 / 2 - intercept) / slope))
        if model == "exponential":
            b = float(params[1])
            return float(1 + np.log(2) / b) if b > 0 else None
        if model == "hyperbolic":
            b = float(params[1])
            return float(1 / b + 2) if b > 0 else None
    except Exception:
        return None
    return None


def _sector_neutral_snapshot(payload):
    chars = characteristic_panel(payload)
    factor = payload.get("factor", "value_pb")
    if chars.empty or factor not in chars or "sector" not in chars:
        return []
    raw = chars[[factor, "momentum_12_1", "sector"]].dropna()
    if len(raw) < 20:
        return []
    neutral = raw[factor].copy()
    sectors = raw["sector"].astype(str).to_numpy()
    vals = raw[factor].to_numpy(dtype=float)
    out = np.empty_like(vals)
    for sector in np.unique(sectors):
        mask = sectors == sector
        out[mask] = vals[mask] - np.nanmean(vals[mask])
    neutral = pd.Series(out, index=raw.index)
    return [
        {"measure": "raw_spearman_proxy", "value": float(raw[factor].corr(raw["momentum_12_1"], method="spearman"))},
        {"measure": "sector_neutral_spearman_proxy", "value": float(neutral.corr(raw["momentum_12_1"], method="spearman"))},
    ]


def _cross_sector_decay(payload: Dict[str, Any], base_rows: list[dict[str, Any]], horizons: np.ndarray) -> list[dict[str, Any]]:
    chars = characteristic_panel({**payload, "max_tickers": max(int(payload.get("max_tickers", 600)), 600)})
    factor = payload.get("factor", "value_pb")
    if chars.empty or "sector" not in chars or factor not in chars:
        return []
    sectors = chars["sector"].dropna().astype(str).value_counts().head(12).index.tolist()
    base_by_h = {int(row["horizon"]): row for row in base_rows}
    rows = []
    for sector in sectors:
        sub = chars[chars["sector"].astype(str) == sector]
        if len(sub) < 12:
            continue
        dispersion = float(pd.to_numeric(sub[factor], errors="coerce").std() or 0.0)
        quality = max(0.55, min(1.35, dispersion / max(float(pd.to_numeric(chars[factor], errors="coerce").std() or 1.0), 1e-12)))
        for horizon in horizons:
            base = base_by_h.get(int(horizon), {})
            mean_ic = float(base.get("mean_ic") or 0.0) * quality
            icir = float(base.get("icir") or 0.0) * np.sqrt(quality)
            rows.append(
                {
                    "sector": sector,
                    "horizon": int(horizon),
                    "mean_ic": mean_ic,
                    "icir": icir,
                    "observations": int(len(sub)),
                    "method": "sector_dispersion_adjusted_decay_from_master_universe",
                }
            )
    return rows


def _multi_factor_power_radar(payload: Dict[str, Any], horizons: np.ndarray) -> list[dict[str, Any]]:
    factors = payload.get("factors") or DEFAULT_FACTORS[:5]
    if isinstance(factors, str):
        factors = [x.strip() for x in factors.split(",") if x.strip()]
    rows = []
    for factor in factors[:6]:
        sub = {**payload, "factor": factor}
        bt = backtest_series(sub)
        r = bt["gross"].dropna()
        if r.empty:
            continue
        arr = r.to_numpy(dtype=float)
        forward = batched_forward_sums(arr, horizons)
        ic_matrix = vectorized_rolling_ic_matrix(arr, forward, 63)
        mean_ics = np.asarray([float(np.mean(row[np.isfinite(row)])) if np.isfinite(row).any() else np.nan for row in ic_matrix])
        icirs = []
        for i, horizon in enumerate(horizons):
            series = pd.Series(ic_matrix[i]).dropna()
            icirs.append(float((series.mean() / series.std()) * np.sqrt(252 / max(int(horizon), 1))) if len(series) > 2 and series.std() else 0.0)
        fit = _fit_decay(horizons.astype(float), np.nan_to_num(mean_ics, nan=0.0)) if np.isfinite(mean_ics).any() else {}
        valid_fits = [value for value in fit.values() if value.get("half_life") is not None and np.isfinite(value.get("r_squared", -np.inf))]
        half_proxy = float(max(valid_fits, key=lambda value: value["r_squared"])["half_life"]) if valid_fits else 0.0
        axes = {
            "IC strength": min(100.0, float(np.nanmax(np.abs(mean_ics))) * 1000.0 if np.isfinite(mean_ics).any() else 0.0),
            "ICIR stability": min(100.0, float(np.nanmax(np.abs(icirs))) * 35.0 if icirs else 0.0),
            "Half-life": min(100.0, half_proxy / 252.0 * 100.0),
            "Positive sign": max(0.0, min(100.0, float(np.nanmean(mean_ics >= 0)) * 100.0 if np.isfinite(mean_ics).any() else 0.0)),
            "Persistence": max(0.0, min(100.0, float(abs(pd.Series(r).autocorr() or 0.0)) * 100.0)),
        }
        rows.extend({"factor": factor, "axis": axis, "value": value} for axis, value in axes.items())
    return rows


def _fit_decay(x, y):
    out = {}
    if len(x) < 2:
        return {"linear": {"r_squared": 0, "half_life": None}}
    coef = np.polyfit(x, y, 1)
    yhat = np.polyval(coef, x)
    initial_fitted = float(np.polyval(coef, 1.0))
    target = 0.5 * initial_fitted
    linear_half_life = float((target - coef[1]) / coef[0]) if coef[0] else None
    out["linear"] = {"r_squared": _r2(y, yhat), "half_life": abs(linear_half_life) if linear_half_life is not None else None}
    for name, fn, p0 in [
        ("exponential", lambda h, a, b: a * np.exp(np.clip(-b * h, -60, 60)), [y[0] or 0.01, 1 / 21]),
        ("hyperbolic", lambda h, a, b: a / (1 + b * h), [y[0] or 0.01, 1 / 21]),
    ]:
        try:
            popt, _ = optimize.curve_fit(fn, x, y, p0=p0, maxfev=5000)
            hl = 1 + np.log(2) / popt[1] if name == "exponential" else 1 / popt[1] + 2
            out[name] = {"r_squared": _r2(y, fn(x, *popt)), "half_life": abs(float(hl))}
        except Exception:
            out[name] = {"r_squared": -np.inf, "half_life": None}
    return out


def _r2(y, yhat):
    return float(1 - np.sum((y - yhat) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12))


def _post_2015_acceleration_test(r: pd.Series, horizons: np.ndarray) -> list[dict[str, Any]]:
    if not isinstance(r.index, pd.DatetimeIndex) or r.empty:
        return [{"status": "unavailable", "reason": "requires dated factor return history"}]
    split_date = pd.Timestamp("2015-01-01")
    before = r.loc[:split_date]
    after = r.loc[split_date:]
    rows = []
    estimates = {}
    for label, series in [("pre_2015", before), ("post_2015", after)]:
        if len(series) < 260:
            rows.append({"period": label, "status": "insufficient_history", "observations": int(len(series))})
            continue
        arr = series.to_numpy(dtype=float)
        forward = batched_forward_sums(arr, horizons)
        ic_matrix = vectorized_rolling_ic_matrix(arr, forward, 63)
        y = np.asarray([np.nanmean(ic_matrix[i]) for i in range(len(horizons))], dtype=float)
        fits = _fit_decay(horizons.astype(float), np.nan_to_num(y, nan=0.0))
        winner = max(fits, key=lambda key: fits[key]["r_squared"])
        half = fits[winner].get("half_life")
        estimates[label] = half
        rows.append({"period": label, "winning_model": winner, "half_life": half, "observations": int(len(series))})
    if estimates.get("pre_2015") and estimates.get("post_2015"):
        diff = float(estimates["post_2015"] - estimates["pre_2015"])
        ratio = float(estimates["post_2015"] / max(estimates["pre_2015"], 1e-12))
        rows.append({"period": "comparison", "half_life_delta": diff, "post_pre_ratio": ratio, "accelerated": bool(diff < 0), "method": "split-sample decay fit; significance proxy based on directional half-life change"})
    return rows
