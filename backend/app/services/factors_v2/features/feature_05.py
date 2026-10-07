"""Feature 5: Alpha Decay and Factor Half-Life Analysis."""

import numpy as np
import pandas as pd
from scipy import optimize

from app.services.factors_v2.core.analytics import response


def run(payload):
    from app.services.factors_v2.core.panel import cross_sectional_ic
    from arch.bootstrap import StationaryBootstrap

    horizons = payload.get("horizons", [1, 5, 21, 63, 126])
    rows = []
    series = {}
    samples = int(payload.get("bootstrap_samples", 200))
    for h in horizons:
        ic = cross_sectional_ic(payload, int(h), int(payload.get("snapshot_step", 21)))
        v = ic["ic"].dropna() if len(ic) else pd.Series(dtype=float)
        series[int(h)] = (
            ic.set_index("formation_date")["ic"] if len(ic) else pd.Series(dtype=float)
        )
        ci = [None, None]
        if len(v) >= 20:
            boot = StationaryBootstrap(
                max(2, int(np.sqrt(len(v)))), v.to_numpy(), seed=505
            )
            means = [float(data[0][0].mean()) for data in boot.bootstrap(samples)]
            ci = np.quantile(means, [0.025, 0.975]).tolist()
        rows.append(
            {
                "horizon": int(h),
                "mean_ic": float(v.mean()) if len(v) else None,
                "icir": float(v.mean() / v.std())
                if len(v) > 2 and v.std() > 0
                else None,
                "ic_lower_95": ci[0],
                "ic_upper_95": ci[1],
                "observations": len(v),
            }
        )
    valid = [r for r in rows if r["mean_ic"] is not None]
    fits = (
        _fit_decay(
            np.array([r["horizon"] for r in valid], float),
            np.array([r["mean_ic"] for r in valid], float),
        )
        if len(valid) >= 3
        else {}
    )
    winner = max(fits, key=lambda k: fits[k]["r_squared"]) if fits else None
    half = fits[winner]["half_life"] if winner else None
    joint = pd.DataFrame(series).dropna()
    draws = []
    if winner and len(joint) >= 20 and len(joint.columns) >= 3:
        boot = StationaryBootstrap(
            max(2, int(np.sqrt(len(joint)))), joint.to_numpy(), seed=506
        )
        for sample in boot.bootstrap(samples):
            candidate = _fit_decay(
                joint.columns.to_numpy(dtype=float), sample[0][0].mean(axis=0)
            ).get(winner, {})
            value = candidate.get("half_life")
            if value is not None and np.isfinite(value):
                draws.append(value)
    half_ci = (
        np.quantile(draws, [0.025, 0.975]).tolist()
        if len(draws) >= max(20, samples // 2)
        else [None, None]
    )
    return response(
        "feature_05",
        "ok" if valid else "warning",
        summary_cards=[
            {"label": "Winning Decay Model", "value": winner},
            {"label": "Half-Life", "value": half, "unit": "sessions"},
        ],
        charts={
            "ic_decay_curve": rows,
            "decay_model_fits": [{"model": k, **v} for k, v in fits.items()],
        },
        tables={
            "ic_by_horizon": rows,
            "decay_models": [{"model": k, **v} for k, v in fits.items()],
            "half_life_confidence": [
                {
                    "model": winner,
                    "half_life": half,
                    "low_95": half_ci[0],
                    "high_95": half_ci[1],
                    "successful_draws": len(draws),
                    "joint_formation_observations": len(joint),
                    "method": "joint stationary bootstrap and curve refit conditional on selected model",
                }
            ],
        },
        meta={
            "factor": payload.get("factor", "momentum_12_1"),
            "method": "Formation-date cross-sectional Spearman IC; labels dated at actual maturity; stationary-block bootstrap mean intervals",
            "missing_output_reasons": {
                "half_life_ci": "Unavailable unless at least 20 joint matured formation dates and enough positive decay refits exist",
                "post_2015_acceleration_test": "No directional change is labelled a significance test",
                "optimal_rebalancing": "IC is not converted to return units using an assumed volatility",
            },
        },
    )


def _fit_decay(x, y):
    out = {}
    if len(x) < 2:
        return {"linear": {"r_squared": 0, "half_life": None}}
    coef = np.polyfit(x, y, 1)
    yhat = np.polyval(coef, x)
    initial_fitted = float(np.polyval(coef, 1.0))
    target = 0.5 * initial_fitted
    linear_half_life = float((target - coef[1]) / coef[0]) if coef[0] else None
    out["linear"] = {
        "r_squared": _r2(y, yhat),
        "half_life": linear_half_life
        if linear_half_life is not None
        and coef[0] < 0
        and initial_fitted > 0
        and linear_half_life >= 1
        else None,
    }
    for name, fn, p0 in [
        (
            "exponential",
            lambda h, a, b: a * np.exp(np.clip(-b * h, -60, 60)),
            [y[0] or 0.01, 1 / 21],
        ),
        ("hyperbolic", lambda h, a, b: a / (1 + b * h), [y[0] or 0.01, 1 / 21]),
    ]:
        try:
            popt, _ = optimize.curve_fit(fn, x, y, p0=p0, maxfev=5000)
            hl = 1 + np.log(2) / popt[1] if name == "exponential" else 1 / popt[1] + 2
            out[name] = {
                "r_squared": _r2(y, fn(x, *popt)),
                "half_life": float(hl)
                if popt[0] > 0 and popt[1] > 0 and hl >= 1
                else None,
            }
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
            out[name] = {"r_squared": -np.inf, "half_life": None}
    return out


def _r2(y, yhat):
    return float(1 - np.sum((y - yhat) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12))


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("05")
OUTPUTS = _outputs("05")
