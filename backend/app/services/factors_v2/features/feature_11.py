"""Feature 11: Factor Stress Testing and Reverse Stress Testing."""

from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.api import VAR

from app.services.factors_v2.core.analytics import (
    covariance_payload,
    factor_returns,
    response,
)
from app.services.factors_v2.core.performance import runtime_meta


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    if rets.empty:
        return response(
            "feature_11", "warning", meta={"warning": "No factor returns available"}
        )
    names = list(rets.columns)
    for key in ("exposures", "shocks"):
        if set(payload.get(key, {}) or {}) - set(names):
            raise ValueError(f"Unknown factors in {key}")
    beta = np.asarray(
        [float(payload.get("exposures", {}).get(c, 1 / len(names))) for c in names]
    )
    shocks = payload.get("shocks") or {c: -2 * float(rets[c].std()) for c in names}
    shock_vec = np.asarray([float(shocks.get(c, 0)) for c in names])
    pnl = float(beta @ shock_vec)
    cov = covariance_payload(rets, "ledoit_wolf")["covariance"].values / 252
    inv_cov = np.linalg.pinv(cov)
    loss = float(payload.get("loss_threshold", 0.15))
    denom = float(beta @ cov @ beta)
    if denom <= 0:
        raise ValueError("Reverse stress requires positive portfolio variance")
    rev = -loss * (cov @ beta) / denom
    d2 = float(rev @ inv_cov @ rev) if denom else 0
    prob = float(1 - stats.chi2.cdf(d2, len(beta)))
    scenario_series = rets.mul(beta, axis=1).sum(axis=1)
    stress_var_5 = float(scenario_series.quantile(0.05))
    stress_cvar_5 = float(scenario_series[scenario_series <= stress_var_5].mean())
    analog_rows = _historical_analog_search(rets, shock_vec)
    hedge_rows = []
    reverse_text = _plain_reverse_stress(names, rev, loss, prob)
    lag_diagnostics = []
    try:
        var_data = rets.reset_index(drop=True)
        requested_lags = int(payload.get("var_lags", 5))
        max_lags = requested_lags
        bootstrap_samples = int(payload.get("var_bootstrap_samples", 50))
        selector = VAR(var_data).select_order(
            maxlags=min(max_lags, max(1, len(rets) // 80))
        )
        aic_lag = int(selector.selected_orders.get("aic") or 1)
        bic_lag = int(selector.selected_orders.get("bic") or 1)
        chosen_lag = min(max(aic_lag, bic_lag, 1), max_lags)
        lag_diagnostics.append({"criterion": "AIC", "lag": aic_lag})
        lag_diagnostics.append({"criterion": "BIC", "lag": bic_lag})
        lag_diagnostics.append(
            {"criterion": "chosen_conservative_capped", "lag": chosen_lag}
        )
        var = VAR(var_data).fit(maxlags=chosen_lag)
        irf_path = var.irf(21).irfs
        contagion = [
            {
                "shock_factor": names[j],
                "response_factor": names[i],
                "horizon": horizon,
                "response": float(
                    irf_path[horizon, i, j] * np.sqrt(var.sigma_u.iloc[j, j])
                ),
            }
            for horizon in [1, 5, 10, 21]
            for i in range(len(names))
            for j in range(len(names))
        ]
        ci_rows = [
            row
            for h in [1, 5, 10, 21]
            for row in _bootstrap_irf_ci(
                var_data, names, chosen_lag, bootstrap_samples, horizon=h
            )
        ]
    except (ValueError, np.linalg.LinAlgError) as exc:
        contagion = []
        ci_rows = []
        var_error = str(exc)
    scenario_rows = [
        {
            "factor": c,
            "shock": float(shock_vec[i]),
            "pnl_contribution": float(beta[i] * shock_vec[i]),
            "historical_p05": float(rets[c].quantile(0.05)),
            "historical_p95": float(rets[c].quantile(0.95)),
        }
        for i, c in enumerate(names)
    ]
    return response(
        "feature_11",
        "partial" if locals().get("var_error") else "ok",
        summary_cards=[
            {"label": "Scenario PnL", "value": pnl},
            {"label": "Gaussian radial tail diagnostic", "value": prob},
        ],
        charts={
            "scenario_waterfall": scenario_rows,
            "contagion_irf": contagion,
            "irf_confidence_bands": ci_rows,
        },
        tables={
            "factor_shocks": scenario_rows,
            "reverse_stress": [
                {"factor": c, "required_return": float(rev[i])}
                for i, c in enumerate(names)
            ],
            "reverse_stress_summary": [
                {
                    "description": reverse_text,
                    "gaussian_radial_tail": prob,
                    "mahalanobis_distance": d2,
                }
            ],
            "historical_analog": analog_rows,
            "hedging_recommendation": hedge_rows,
            "stress_var_cvar": [
                {
                    "var_5": stress_var_5,
                    "cvar_5": stress_cvar_5,
                    "method": "portfolio_exposure_weighted_factor_history",
                }
            ],
            "multi_scenario": _multi_scenario(payload, names, beta, rets),
            "var_lag_selection": lag_diagnostics,
        },
        alerts=[{"level": "high", "message": "Stress scenario exceeds loss threshold"}]
        if pnl < -loss
        else [],
        meta={
            **runtime_meta(
                "feature_11",
                payload,
                [
                    "validated VAR lags and bootstrap draws are applied without silent caps"
                ],
            ),
            "var_error": locals().get("var_error"),
            "reverse_stress_mahalanobis": d2,
            "missing_output_reasons": {
                "hedging_recommendation": "No executable hedge instrument mapping supplied"
            },
            "irf_shock_units": "One fitted residual standard deviation of the shocked factor; bootstrap refits use the same base shock size",
            "var_method": "automatic AIC/BIC lag selection plus residual-bootstrap 90% confidence bands",
            "requested_var_lags": payload.get("var_lags", 5),
            "max_lags_used": locals().get("max_lags"),
            "bootstrap_samples": locals().get("bootstrap_samples"),
            "audit_closures": [
                "historical analog search",
                "hedging recommendation",
                "stress VaR/CVaR",
                "plain-language reverse stress",
            ],
        },
    )


def _bootstrap_irf_ci(rets, names, lag, samples=200, horizon=21):
    try:
        if len(rets) < lag * 10 or len(names) < 2:
            return []
        base = VAR(rets).fit(maxlags=lag)
        irf = base.irf(horizon).irfs[-1]
        resid = base.resid.values
        coefs = base.coefs
        intercept = base.intercept
        values = rets.values
        t_len, k = values.shape
        y_init = values[:lag]
        rng = np.random.default_rng(1831)
        n_report = len(names)
        boot_irfs = np.full((int(samples), n_report, n_report), np.nan, dtype=float)
        base_effect = (
            irf[:n_report, :n_report]
            if irf.ndim == 2
            else np.zeros((n_report, n_report))
        )
        for sample_idx in range(int(samples)):
            boot_resid = resid[rng.integers(0, len(resid), size=len(resid))]
            y_boot = np.empty((t_len, k), dtype=float)
            y_boot[:lag] = y_init
            for t in range(lag, t_len):
                row = intercept.copy()
                for lag_idx in range(lag):
                    row += coefs[lag_idx] @ y_boot[t - lag_idx - 1]
                y_boot[t] = row + boot_resid[t - lag]
            boot_fit = VAR(y_boot).fit(maxlags=lag)
            boot_irfs[sample_idx] = boot_fit.irf(horizon).irfs[-1]
        rows = []
        for shock_idx, shock_name in enumerate(names[:n_report]):
            for response_idx, response_name in enumerate(names[:n_report]):
                scale = float(np.sqrt(base.sigma_u.iloc[shock_idx, shock_idx]))
                vals = boot_irfs[:, response_idx, shock_idx] * scale
                vals = vals[np.isfinite(vals)]
                if len(vals) < max(10, int(samples) // 5):
                    continue
                rows.append(
                    {
                        "shock_factor": shock_name,
                        "response_factor": response_name,
                        "horizon": horizon,
                        "base_irf": float(irf[response_idx, shock_idx] * scale)
                        if irf.ndim == 2
                        else 0.0,
                        "low_90": float(np.percentile(vals, 5)),
                        "median": float(np.percentile(vals, 50)),
                        "high_90": float(np.percentile(vals, 95)),
                        "bootstrap_samples": int(len(vals)),
                        "method": "recursive_residual_bootstrap_with_var_coefficient_refit",
                    }
                )
        return rows
    except (ValueError, np.linalg.LinAlgError) as exc:
        return [
            {
                "error": str(exc),
                "method": "recursive_residual_bootstrap_with_var_coefficient_refit",
            }
        ]


def _historical_analog_search(
    rets: pd.DataFrame, shock_vec: np.ndarray
) -> list[dict[str, Any]]:
    if len(rets) < 80:
        return []
    cov = np.cov(rets.values.T)
    inv = np.linalg.pinv(cov)
    rows = []
    window = 1
    target = shock_vec
    for end in range(window, len(rets)):
        vec = rets.iloc[end - window : end].sum().to_numpy(dtype=float)
        diff = vec - target
        dist = float(np.sqrt(max(diff @ inv @ diff, 0.0)))
        rows.append(
            {
                "start": str(rets.index[end - window].date()),
                "end": str(rets.index[end - 1].date()),
                "mahalanobis_distance": dist,
                "equal_weight_factor_return": float(vec.mean()),
            }
        )
    return sorted(rows, key=lambda row: row["mahalanobis_distance"])[:10]


def _plain_reverse_stress(names, rev: np.ndarray, loss: float, prob: float) -> str:
    ranked = sorted(zip(names, rev), key=lambda item: abs(item[1]), reverse=True)[:3]
    parts = ", ".join(f"{name} {value:+.2%}" for name, value in ranked)
    return f"Portfolio reaches the {loss:.1%} loss threshold if the dominant factor shocks are approximately {parts}; Gaussian radial tail diagnostic is {prob:.2%}."


def _multi_scenario(
    payload: Dict[str, Any], names, beta: np.ndarray, rets: pd.DataFrame
) -> list[dict[str, Any]]:
    scenarios = payload.get("scenarios")
    if not scenarios:
        scenarios = {
            "parametric_1sigma_down": {
                name: -float(rets[name].std()) for name in names
            },
            "parametric_2sigma_down": {
                name: -2 * float(rets[name].std()) for name in names
            },
            "parametric_upside_rebound": {
                name: float(rets[name].std()) for name in names
            },
        }
    rows = []
    if isinstance(scenarios, dict):
        iterable = scenarios.items()
    else:
        iterable = [
            (item.get("name", f"scenario_{i + 1}"), item.get("shocks", item))
            for i, item in enumerate(scenarios)
        ]
    for name, shocks in list(iterable):
        if set(shocks or {}) - set(names):
            raise ValueError("Unknown factor in scenario shocks")
        vec = np.asarray([float((shocks or {}).get(c, 0.0)) for c in names])
        rows.append(
            {
                "scenario": str(name),
                "pnl": float(beta @ vec),
                "worst_factor": names[int(np.argmin(vec))] if len(vec) else None,
            }
        )
    return rows


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("11")
OUTPUTS = _outputs("11")
