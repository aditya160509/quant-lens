"""Feature 08: observed stress episodes and explicitly modeled conditional scenarios."""

from __future__ import annotations
from .inputs import field

import json
import numpy as np
import pandas as pd
from scipy.stats import norm
from app.services.volatility_v2.core.analytics import (
    DEFAULT_ASSETS,
    load_assets,
    parse_weights,
    response,
    summary_card,
    matrix_records,
)
from app.services.volatility_v2.core.currency import portfolio_returns
from app.services.volatility_v2.core.dcc import expanding_dcc, correlation
from app.services.volatility_v2.core.stress import PRESETS, replay, gaussian_stress
from app.services.volatility_v2.core.analogs import analyze
from app.services.volatility_v2.core.tails import rotated_clayton
from app.services.volatility_v2.core.connectedness import (
    fit_volatility_var,
    bootstrap_irf,
)
from app.services.volatility_v2.core.data_loader import resolve_symbols


def _vector(payload, key, assets, default=None):
    raw = payload.get(key)
    if raw is None:
        if default is None:
            raise ValueError(f"{key} must specify each requested asset")
        return pd.Series(default, index=assets, dtype=float)
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError(f"{key} must be a JSON object")
    normalized = {
        resolve_symbols([asset])[0]: float(value) for asset, value in raw.items()
    }
    if (
        set(normalized) != set(assets)
        or not np.isfinite(list(normalized.values())).all()
    ):
        raise ValueError(f"{key} must specify finite values for every requested asset")
    return pd.Series(normalized).reindex(assets)


def run(payload=None):
    payload = payload or {}
    data_request = {"lookback_days": 10000, **payload}
    assets, ohlcv = load_assets(data_request, default=DEFAULT_ASSETS[:8])
    if len(assets) < 2:
        raise ValueError("Multivariate stress requires at least two assets")
    ret, currency_meta = portfolio_returns(ohlcv, payload, log_returns=False)
    ret = ret.reindex(columns=assets)
    weights = parse_weights(payload, assets)
    annualization = int(payload.get("annualization", 252))
    horizon = int(payload.get("stress_horizon", 1))
    if not 1 <= horizon <= 252:
        raise ValueError("stress_horizon must be between 1 and 252 sessions")
    dcc = expanding_dcc(
        ret,
        min_train=int(payload.get("min_train", 252)),
        refit_interval=int(payload.get("refit_interval", 126)),
        annualization=annualization,
        dynamics=payload.get("dynamics", "dcc"),
        midas_k=int(payload.get("midas_k", 36)),
    )
    covariance = dcc["forecast_covariance"]
    current_vol = np.sqrt(np.diag(covariance))
    scenario = str(
        payload.get("scenario", payload.get("historical_preset", "liberation_day_2025"))
    ).lower()
    if scenario == "historical":
        scenario = str(payload.get("historical_preset", "liberation_day_2025")).lower()
    if scenario not in (*PRESETS, "custom", "parametric", "analog"):
        raise ValueError("Unknown stress scenario")
    warnings, episode, scenario_table = [], None, []
    for name, dates in PRESETS.items():
        try:
            historical = replay(ret, weights, *dates, annualization=annualization)
            historical_risk, _ = gaussian_stress(
                historical["covariance"],
                weights,
                historical["daily_mean"],
                horizon=horizon,
                paths=int(payload.get("mc_paths", 20000)),
                aum=float(payload.get("aum", 1e8)),
                annualization=annualization,
                seed=int(payload.get("seed", 7)),
            )
            scenario_table.append(
                {
                    "scenario": name,
                    "status": "ok",
                    "modeled_var_95": historical_risk["var_95"],
                    "modeled_cvar_99": historical_risk["cvar_99"],
                    "risk_horizon_sessions": horizon,
                    "maximum_asset_volatility": float(
                        historical["asset_volatility"].max()
                    ),
                    **{
                        key: historical[key]
                        for key in (
                            "start",
                            "end",
                            "observations",
                            "portfolio_return",
                            "maximum_drawdown",
                            "portfolio_volatility",
                            "nav_recovery_days",
                            "nav_recovery_reason",
                            "volatility_recovery_days",
                            "volatility_recovery_reason",
                        )
                    },
                }
            )
            if scenario == name:
                episode = historical
        except ValueError as exc:
            scenario_table.append(
                {"scenario": name, "status": "unavailable", "reason": str(exc)}
            )
            if scenario == name:
                raise ValueError(
                    f"Selected historical scenario unavailable: {exc}"
                ) from exc
    if scenario == "custom":
        if "scenario_start" not in payload or "scenario_end" not in payload:
            raise ValueError(
                "Custom historical stress requires scenario_start and scenario_end"
            )
        episode = replay(
            ret,
            weights,
            payload["scenario_start"],
            payload["scenario_end"],
            annualization,
        )
    analog = None
    try:
        analog = analyze(ret, weights, payload)
    except (ValueError, np.linalg.LinAlgError) as exc:
        if scenario == "analog":
            raise ValueError(f"Selected analog scenario unavailable: {exc}") from exc
        warnings.append(f"Macro analog/adversarial outputs unavailable: {exc}")
    if scenario == "analog":
        # Equal-weight mixture of actual matched daily returns, not a synthetic mean shock.
        observations = [
            ret.loc[row["window_start"] : row["window_end"]]
            for row in analog["analogs"]
        ]
        sample = pd.concat(observations, ignore_index=True)
        stressed_covariance = sample.cov() * annualization
        daily_mean = sample.mean()
        scenario_pnl = float(
            np.mean([row["portfolio_return"] for row in analog["analogs"]])
        )
        attribution = []
        for asset in assets:
            values = []
            for observed in observations:
                portfolio_nav = (1 + observed @ weights).cumprod()
                before = portfolio_nav.shift(1, fill_value=1)
                values.append(float((observed[asset] * weights[asset] * before).sum()))
            attribution.append(
                {
                    "asset": asset,
                    "cumulative_return_contribution": float(np.mean(values)),
                }
            )
    elif episode is not None:
        stressed_covariance, daily_mean = episode["covariance"], episode["daily_mean"]
        scenario_pnl, attribution = episode["portfolio_return"], episode["attribution"]
    else:
        changes = _vector(payload, "vol_shocks", assets)
        shocked = current_vol + changes.to_numpy()
        if (shocked <= 0).any():
            raise ValueError(
                "Parametric annualized volatility after vol_shocks must be positive"
            )
        stressed_covariance = pd.DataFrame(
            correlation(covariance.to_numpy()) * np.outer(shocked, shocked),
            index=assets,
            columns=assets,
        )
        shocks = _vector(payload, "return_shocks", assets, default=0)
        if (shocks <= -1).any():
            raise ValueError("Parametric return shocks must exceed -100%")
        daily_mean = (1 + shocks) ** (1 / horizon) - 1
        scenario_pnl = float(shocks @ weights)
        attribution = [
            {
                "asset": asset,
                "cumulative_return_contribution": float(shocks[asset] * weights[asset]),
            }
            for asset in assets
        ]
    risk, distribution = gaussian_stress(
        stressed_covariance,
        weights,
        daily_mean,
        horizon=horizon,
        paths=int(payload.get("mc_paths", 20000)),
        aum=float(payload.get("aum", 1e8)),
        annualization=annualization,
        seed=int(payload.get("seed", 7)),
    )
    capital_change = float(
        norm.ppf(0.99)
        * np.sqrt(horizon / annualization)
        * (
            np.sqrt(weights @ stressed_covariance @ weights)
            - np.sqrt(weights @ covariance @ weights)
        )
        * float(payload.get("aum", 1e8))
    )
    portfolio = ret @ weights
    realized_vol = portfolio.rolling(21, min_periods=21).std(ddof=1) * np.sqrt(
        annualization
    )
    reverse_horizon = int(payload.get("reverse_horizon", 30))
    if not 1 <= reverse_horizon <= 252:
        raise ValueError("reverse_horizon must be between 1 and 252 sessions")
    reverse_returns = (1 + portfolio).rolling(
        reverse_horizon, min_periods=reverse_horizon
    ).apply(np.prod, raw=True) - 1
    copula = None
    try:
        copula = rotated_clayton(
            reverse_returns,
            realized_vol.diff(reverse_horizon),
            loss_threshold=float(payload.get("loss_threshold", 0.15)),
            tail_probability=float(payload.get("clayton_tail_pct", 0.20)),
            horizon_sessions=reverse_horizon,
        )
        if copula["near_independence_boundary"]:
            warnings.append(
                "Clayton fit is at its near-independence boundary; no strong fitted tail dependence"
            )
    except (ValueError, np.linalg.LinAlgError) as exc:
        warnings.append(f"Clayton reverse stress unavailable: {exc}")
    vols = ret.rolling(21, min_periods=21).std(ddof=1) * np.sqrt(annualization)
    vol_panel = (
        np.log(vols.where(vols > 0)).dropna().tail(int(payload.get("irf_window", 504)))
    )
    origin = resolve_symbols([payload.get("source_asset", assets[0])])[0]
    if origin not in assets:
        raise ValueError("source_asset must be a requested portfolio asset")
    controls = {
        "max_lag": int(payload.get("var_max_lag", 5)),
        "weighting": payload.get("var_weighting", "ols"),
        "lag_order": int(payload.get("var_lag_order", 1)),
        "delta": float(payload.get("var_decay", 0.99)),
    }
    irfs, irf_meta = [], {}
    try:
        model = fit_volatility_var(vol_panel, **controls)
        if not model.stable:
            raise ValueError("Contagion IRFs require a stable fitted VAR")
        horizons = payload.get("irf_horizons", [1, 5, 10, 21])
        if (
            not isinstance(horizons, list)
            or not horizons
            or any(not isinstance(h, int) or not 1 <= h <= 252 for h in horizons)
        ):
            raise ValueError("irf_horizons must be positive integer horizons up to 252")
        irfs, irf_meta = bootstrap_irf(
            vol_panel,
            model,
            horizons=tuple(horizons),
            reps=int(payload.get("irf_bootstrap_reps", 100)),
            shock_scale="one_residual_sd",
            confidence=float(payload.get("confidence_level", 0.9)),
            **controls,
        )
        irfs = [row for row in irfs if row["source"] == origin]
        if irf_meta.get("unavailable_reason"):
            warnings.append(irf_meta["unavailable_reason"])
        irf_meta.update(
            {
                "source_asset": origin,
                "var_lag": model.lag,
                "var_weighting": model.weighting,
                "series": "Observed USD-return 21-session volatility, in log units",
            }
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        warnings.append(f"Contagion VAR unavailable: {exc}")
    shocked_vol = np.sqrt(np.diag(stressed_covariance))
    waterfall = [
        {"component": row["asset"], "value": row["cumulative_return_contribution"]}
        for row in attribution
    ]
    waterfall.append({"component": "portfolio_total", "value": scenario_pnl})
    result = response(
        "08",
        [
            summary_card("Scenario", scenario),
            summary_card("Scenario Portfolio Return", scenario_pnl, "simple return"),
            summary_card("Stress VaR 95", risk["var_95"], "modeled return"),
            summary_card("Stress CVaR 95", risk["cvar_95"], "modeled return"),
        ],
        charts={
            "vol_shock_bar_chart": [
                {
                    "asset": asset,
                    "current_vol": float(current_vol[i]),
                    "scenario_vol": float(shocked_vol[i]),
                    "vol_change_bps": float((shocked_vol[i] - current_vol[i]) * 10000),
                }
                for i, asset in enumerate(assets)
            ],
            "portfolio_pnl_attribution_waterfall": waterfall,
            "historical_stress_path": episode["path"] if episode else [],
            "contagion_impulse_response": irfs,
            "contagion_impulse_response_bands": irfs,
            "stress_distribution": distribution,
            "scenario_correlation": matrix_records(
                pd.DataFrame(
                    correlation(stressed_covariance.to_numpy()),
                    index=assets,
                    columns=assets,
                )
            ),
            "analog_volatility_paths": analog["volatility_paths"] if analog else [],
            "analog_volatility_bands": analog["volatility_bands"] if analog else [],
            "macro_precision_matrix": matrix_records(analog["precision_matrix"])
            if analog
            else [],
            "reverse_stress_frontier": copula["frontier"] if copula else [],
        },
        tables={
            "historical_analog_comparison": analog["analogs"] if analog else [],
            "historical_analog_glasso": analog["analogs"] if analog else [],
            "reverse_stress_scenario": [copula["reverse_stress"]]
            if copula and copula["reverse_stress"]
            else [],
            "reverse_stress_copula": [
                {key: value for key, value in copula.items() if key != "frontier"}
            ]
            if copula
            else [],
            "adversarial_scenario": [analog["adversarial"]] if analog else [],
            "multi_scenario_comparison": scenario_table,
            "stress_var_cvar": [risk],
            "risk_capital_change": [
                {
                    "var_99_change_usd": capital_change,
                    "interpretation": "Volatility-only 99% Gaussian diffusion risk-capital change; drift excluded, horizon square-root scaling, USD",
                }
            ],
            "contagion_irf_bootstrap_bands": irfs,
        },
        meta={
            "assets": assets,
            **currency_meta,
            "scenario": scenario,
            "historical_replay": episode["replay_policy"] if episode else None,
            "covariance_engine": "causal two-stage DCC/GARCH on USD simple returns",
            "scenario_covariance": "observed historical/analog daily covariance"
            if scenario != "parametric"
            else "declared volatility shocks with current fitted DCC correlation",
            "vol_shocks_unit": "annualized decimal volatility points",
            "parametric_return_shocks": "explicit hypothetical terminal simple returns, zero when omitted",
            "monte_carlo": risk["distribution"],
            "irf": irf_meta,
            "analog": analog["meta"] if analog else None,
            "reverse_stress_unavailable_reason": copula["reverse_stress_reason"]
            if copula
            else "Copula fit unavailable",
            "warnings": warnings,
        },
    )
    if warnings:
        result["status"] = "warning"
    return result


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field(
        "assets",
        ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO"],
        kind="symbols",
        group="Data",
    ),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 10000, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("annualization", 252, kind=None, group="Model"),
    field("stress_horizon", 1, kind=None, group="Model"),
    field("reverse_horizon", 30, kind=None, group="Model"),
    field("var_weighting", "ols", kind=None, group="Model"),
    field("irf_horizons", [1, 5, 10, 21], kind="list", group="Model"),
    field("dynamics", "dcc", kind=None, group="Model"),
    field("irf_window", 504, kind=None, group="Model"),
    field("var_max_lag", 5, kind=None, group="Model"),
    field("var_lag_order", 1, kind=None, group="Model"),
    field("var_decay", 0.99, kind=None, group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 126, kind=None, group="Model"),
    field("midas_k", 36, kind=None, group="Model"),
    field("scenario", None, kind=None, group="Model"),
    field("mc_paths", 20000, kind=None, group="Model"),
    field("aum", 100000000.0, kind=None, group="Portfolio"),
    field("seed", 7, kind=None, group="Model"),
    field("source_asset", None, kind=None, group="Model"),
    field("historical_preset", "liberation_day_2025", kind=None, group="Model"),
    field("loss_threshold", 0.15, kind=None, group="Model"),
    field("clayton_tail_pct", 0.2, kind=None, group="Model"),
    field("irf_bootstrap_reps", 100, kind=None, group="Model"),
    field("quote_currencies", None, kind="object", group="Data"),
    field("weights", None, kind="object", group="Portfolio"),
    field("vol_shocks", None, kind="object", group="Model"),
    field("return_shocks", None, kind="object", group="Model"),
    field("analog_horizon", 30, kind="integer", group="Model"),
    field("analog_k", 10, kind="integer", group="Model"),
    field("adversarial_c", 2.0, kind="number", group="Model"),
    field("confidence_level", 0.9, kind="number", group="Model"),
    field("macro_scenario", kind="object"),
    field("base_currency", "USD", options=["USD"]),
]

OUTPUTS = [
    {
        "key": "vol_shock_bar_chart",
        "source": "charts",
        "label": "Vol shock bar chart",
        "render": "bar",
        "primary": True,
        "help": "Actual observed or fitted vol shock bar chart. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "portfolio_pnl_attribution_waterfall",
        "source": "charts",
        "label": "Portfolio pnl attribution waterfall",
        "render": "waterfall",
        "primary": False,
        "help": "Actual observed or fitted portfolio pnl attribution waterfall. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "historical_stress_path",
        "source": "charts",
        "label": "Historical stress path",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted historical stress path. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "contagion_impulse_response",
        "source": "charts",
        "label": "Contagion impulse response",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted contagion impulse response. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "contagion_impulse_response_bands",
        "source": "charts",
        "label": "Contagion impulse response bands",
        "render": "band",
        "primary": False,
        "help": "Actual observed or fitted contagion impulse response bands. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "stress_distribution",
        "source": "charts",
        "label": "Stress distribution",
        "render": "histogram",
        "primary": False,
        "help": "Actual observed or fitted stress distribution. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "scenario_correlation",
        "source": "charts",
        "label": "Scenario correlation",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted scenario correlation. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "analog_volatility_paths",
        "source": "charts",
        "label": "Analog volatility paths",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted analog volatility paths. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "analog_volatility_bands",
        "source": "charts",
        "label": "Analog volatility bands",
        "render": "band",
        "primary": False,
        "help": "Actual observed or fitted analog volatility bands. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "macro_precision_matrix",
        "source": "charts",
        "label": "Macro precision matrix",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted macro precision matrix. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "reverse_stress_frontier",
        "source": "charts",
        "label": "Reverse stress frontier",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted reverse stress frontier. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "historical_analog_comparison",
        "source": "tables",
        "label": "Historical analog comparison",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted historical analog comparison. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "historical_analog_glasso",
        "source": "tables",
        "label": "Historical analog glasso",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted historical analog glasso. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "reverse_stress_scenario",
        "source": "tables",
        "label": "Reverse stress scenario",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted reverse stress scenario. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "reverse_stress_copula",
        "source": "tables",
        "label": "Reverse stress copula",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted reverse stress copula. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "adversarial_scenario",
        "source": "tables",
        "label": "Adversarial scenario",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted adversarial scenario. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "multi_scenario_comparison",
        "source": "tables",
        "label": "Multi scenario comparison",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted multi scenario comparison. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "stress_var_cvar",
        "source": "tables",
        "label": "Stress var cvar",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted stress var cvar. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "risk_capital_change",
        "source": "tables",
        "label": "Risk capital change",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted risk capital change. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "contagion_irf_bootstrap_bands",
        "source": "tables",
        "label": "Contagion irf bootstrap bands",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted contagion irf bootstrap bands. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
]
