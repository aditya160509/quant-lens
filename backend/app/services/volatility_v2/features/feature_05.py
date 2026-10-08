"""Feature 05: observed IV, integrated conditional variance, and BTZ inference."""

from __future__ import annotations
from .inputs import field
import numpy as np
import pandas as pd
from app.services.volatility_v2.core.analytics import (
    load_assets,
    returns_panel,
    volatility_estimators,
    compact_records,
    response,
    summary_card,
)
from app.services.volatility_v2.core.vrp import (
    observed_iv,
    integrated_garch_variance,
    physical_har_variance,
    predictive_regression,
    mean_reversion_half_life,
)
from app.services.volatility_v2.core.har import expanding_forecasts
from app.services.volatility_v2.core.regimes import (
    regime_features,
    filtered_regimes,
    state_names,
)

MATURITIES = {30: 21, 90: 63, 180: 126}


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=["^GSPC"])
    display = str(payload.get("display_mode", "raw"))
    if display not in ("raw", "variance", "zscore"):
        raise ValueError("display_mode must be raw, variance, or zscore")
    return_horizons = payload.get("return_horizons", [21, 63, 126, 252])
    if isinstance(return_horizons, str):
        return_horizons = [int(h.strip()) for h in return_horizons.split(",")]
    if not return_horizons or any(not 1 <= int(h) <= 252 for h in return_horizons):
        raise ValueError("return_horizons must be integers from 1 to 252")
    min_train = int(payload.get("min_train", 252))
    refit = int(payload.get("refit_interval", 21))
    lookback = payload.get("zscore_lookback", 1260)
    if isinstance(lookback, str) and lookback.endswith("d"):
        lookback = int(lookback[:-1])
    if lookback != "full" and int(lookback) not in (252, 504, 1260):
        raise ValueError("zscore_lookback must be 252, 504, 1260, or full")
    ret = returns_panel(ohlcv)
    vol = volatility_estimators(ohlcv, 21)
    (
        series_rows,
        term_rows,
        comparison,
        regressions,
        regime_rows,
        forecast_rows,
        zscores,
        gaps,
        halflives,
    ) = [], [], [], [], [], [], [], [], []
    for asset in assets:
        returns = ret[asset].dropna()
        iv, source = observed_iv(asset, returns.index, payload.get("iv_upload_id"))
        daily = (
            vol.loc[vol.asset.eq(asset)]
            .set_index("date")
            .yang_zhang.reindex(returns.index)
        )
        physical = integrated_garch_variance(
            returns,
            tuple(MATURITIES.values()),
            min_train,
            refit,
            str(payload.get("physical_model", "GARCH")),
            str(payload.get("physical_distribution", "Student-t")),
        )
        frame = pd.DataFrame(
            {
                "return": returns,
                "iv_ann": iv[30],
                "physical_garch_variance": physical[21],
                "physical_historical_variance": returns.pow(2).rolling(252).mean()
                * 252,
            },
            index=returns.index,
        )
        har = {}
        for maturity, horizon in MATURITIES.items():
            prediction, _, _ = physical_har_variance(
                returns, daily, horizon, min_train, refit
            )
            har[maturity] = prediction
            observed = (
                float(iv[maturity].iloc[-1])
                if maturity in iv and pd.notna(iv[maturity].iloc[-1])
                else None
            )
            har_latest = (
                float(prediction.iloc[-1]) if pd.notna(prediction.iloc[-1]) else None
            )
            garch_latest = float(physical[horizon].iloc[-1])
            term_rows.append(
                {
                    "asset": asset,
                    "maturity_days": maturity,
                    "trading_horizon": horizon,
                    "date": returns.index[-1],
                    "implied_vol": observed,
                    "physical_garch_ann_variance": garch_latest,
                    "physical_har_ann_variance": har_latest,
                    "vrp_garch": observed - np.sqrt(garch_latest)
                    if observed is not None
                    else None,
                    "implied_source": source if observed is not None else None,
                    "unavailable_reason": None
                    if observed is not None
                    else "No observed implied volatility for this maturity at the selected price date",
                }
            )
        frame["physical_har_variance"] = har[30]
        for method in ("garch", "har", "historical"):
            variance = frame[f"physical_{method}_variance"]
            frame[f"physical_{method}"] = np.sqrt(variance)
            frame[f"vrp_{method}"] = frame.iv_ann - frame[f"physical_{method}"]
            frame[f"vrp_{method}_monthly_variance"] = (
                frame.iv_ann.pow(2) - variance
            ) / 12
        value = frame.vrp_garch
        moments = (
            value.expanding(min_periods=60)
            if lookback == "full"
            else value.rolling(int(lookback), min_periods=int(lookback))
        )
        frame["vrp_zscore"] = (value - moments.mean()) / moments.std(ddof=1).replace(
            0, np.nan
        )
        for label, window in (
            ("252d", 252),
            ("504d", 504),
            ("1260d", 1260),
            ("full", None),
        ):
            moment = (
                value.expanding(min_periods=60)
                if window is None
                else value.rolling(window, min_periods=window)
            )
            z = (value - moment.mean()) / moment.std(ddof=1).replace(0, np.nan)
            zscores.append(
                {
                    "asset": asset,
                    "lookback": label,
                    "current_zscore": float(z.iloc[-1])
                    if pd.notna(z.iloc[-1])
                    else None,
                    "available_observations": int(value.notna().sum()),
                }
            )
        probabilities = None
        try:
            fitted = filtered_regimes(
                regime_features(ohlcv.loc[ohlcv.Ticker.eq(asset)], asset),
                states=int(payload.get("states", 4)),
                min_train=min_train,
                refit_interval=int(payload.get("regime_refit_interval", 126)),
                restarts=int(payload.get("hmm_restarts", 3)),
            )
            probabilities = fitted["probabilities"][
                state_names(fitted["selected_states"])
            ]
            if not fitted["probabilities"].hmm_converged.all():
                gaps.append(
                    {
                        "asset": asset,
                        "output": "regime_conditional_btz",
                        "reason": "Some selected HMM fits did not satisfy likelihood convergence; inspect Feature 04",
                    }
                )
        except ValueError as exc:
            gaps.append(
                {"asset": asset, "output": "regime_conditional_btz", "reason": str(exc)}
            )
        for horizon in return_horizons:
            horizon = int(horizon)
            result = predictive_regression(
                frame.vrp_garch_monthly_variance, returns, horizon, probabilities
            )
            regressions.extend(
                {"asset": asset, **row} for row in result["coefficients"]
            )
            regime_rows.extend(
                {"asset": asset, **row} for row in result["regime_coefficients"]
            )
            if "unavailable_reason" in result:
                gaps.append(
                    {
                        "asset": asset,
                        "output": f"BTZ horizon {horizon}",
                        "reason": result["unavailable_reason"],
                    }
                )
            predictions, accuracy, _, _ = expanding_forecasts(
                frame[["vrp_garch_monthly_variance"]],
                returns.rolling(horizon).sum().shift(-horizon),
                horizon,
                min_train,
                refit,
            )
            forecasts = predictions.loc[predictions.forecast.notna()].copy()
            forecasts["asset"], forecasts["horizon"] = asset, horizon
            forecast_rows.extend(compact_records(forecasts, limit=420))
            regressions.append(
                {
                    "asset": asset,
                    "horizon": horizon,
                    "model": "expanding_OOS_BTZ",
                    "r2_oos": accuracy["r2_oos"],
                    "rmse": accuracy["rmse"],
                    "observations": accuracy["observations"],
                    "current_predicted_log_return": float(predictions.forecast.iloc[-1])
                    if pd.notna(predictions.forecast.iloc[-1])
                    else None,
                }
            )
        frame["vrp_half_life_252d"] = value.rolling(252, min_periods=252).apply(
            mean_reversion_half_life, raw=False
        )
        half = (
            float(frame.vrp_half_life_252d.iloc[-1])
            if pd.notna(frame.vrp_half_life_252d.iloc[-1])
            else None
        )
        halflives.append({"asset": asset, "half_life_days": half})
        history = value.dropna()
        current = float(value.iloc[-1])
        percentile = float(history.le(current).mean() * 100)
        comparison.append(
            {
                "asset": asset,
                "date": returns.index[-1],
                "vrp": current,
                "percentile": percentile,
                "rich_cheap": "rich"
                if percentile > 70
                else "cheap"
                if percentile < 30
                else "neutral",
                "implied_source": source,
                "physical_model": payload.get("physical_model", "GARCH"),
                "physical_distribution": payload.get(
                    "physical_distribution", "Student-t"
                ),
            }
        )
        frame["asset"] = asset
        frame["display_value"] = (
            frame.vrp_garch
            if display == "raw"
            else frame.vrp_garch_monthly_variance
            if display == "variance"
            else frame.vrp_zscore
        )
        series_rows.extend(
            compact_records(
                frame.reset_index().rename(columns={"Date": "date", "index": "date"}),
                limit=420,
            )
        )
    primary = comparison[0]
    result = response(
        "05",
        [
            summary_card("VRP", primary["vrp"], "ann"),
            summary_card("VRP Percentile", primary["percentile"], "pct"),
            summary_card(
                "Mean-Reversion Half-Life", halflives[0]["half_life_days"], "days"
            ),
        ],
        charts={
            "vrp_time_series": series_rows,
            "vrp_zscore_panel": [
                {"date": r["date"], "asset": r["asset"], "vrp_zscore": r["vrp_zscore"]}
                for r in series_rows
            ],
            "vrp_term_structure": term_rows,
            "vrp_component_attribution": [
                {
                    "date": r["date"],
                    "asset": r["asset"],
                    "risk_neutral_monthly_variance": r["iv_ann"] ** 2 / 12
                    if r["iv_ann"] is not None
                    else None,
                    "physical_monthly_variance": r["physical_garch_variance"] / 12
                    if r["physical_garch_variance"] is not None
                    else None,
                    "vrp_monthly_variance": r["vrp_garch_monthly_variance"],
                }
                for r in series_rows
            ],
            "btz_expanding_forecasts": forecast_rows,
        },
        tables={
            "cross_asset_vrp_comparison": comparison,
            "return_predictability_regression": regressions,
            "regime_conditional_btz": regime_rows,
            "vrp_zscore_lookback_comparison": zscores,
            "vrp_mean_reversion_speed": halflives,
            "data_gaps": gaps,
        },
        meta={
            "assets": assets,
            "display_mode": display,
            "physical_expectation": "Past-only fitted GARCH horizon-integrated variance, direct log-HAR integrated-variance forecasts, and observed trailing squared returns",
            "variance_units": "Annualized decimal squared volatility; BTZ uses monthly variance /12",
            "horizon_convention": "30/90/180 calendar-day IV matched approximately to 21/63/126 observed trading sessions; actual venue holiday calendars not supplied",
            "component_identity": "Risk-neutral variance = physical expectation + VRP. The physical component is not part of VRP itself.",
            "hodrick_inference": "Hodrick (1992) 1B lagged-predictor covariance tests the no-predictability null only; Newey-West SE reported separately",
            "regime_conditioning": "WLS weights are causal Feature 04 HMM filtered probabilities, not volatility ranks",
            "implied_vol_policy": "Exact observed dates and matching benchmark; no stale fill, interpolation, synthetic IV, or non-US VIX substitution",
            "data_gaps": gaps,
        },
    )
    if gaps:
        result["status"] = "warning"
    return result


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field("assets", ["^GSPC"], kind="symbols", group="Data"),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("return_horizons", [21, 63, 126, 252], kind="list", group="Model"),
    field("zscore_lookback", 1260, kind="integer", group="Model"),
    field("display_mode", "raw", kind=None, group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 21, kind=None, group="Model"),
    field("iv_upload_id", None, kind=None, group="Data"),
    field("physical_model", "GARCH", kind=None, group="Model"),
    field("physical_distribution", "Student-t", kind=None, group="Model"),
    field("states", 4, kind=None, group="Model"),
    field("regime_refit_interval", 126, kind=None, group="Model"),
    field("hmm_restarts", 3, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "vrp_time_series",
        "source": "charts",
        "label": "Vrp time series",
        "render": "line",
        "primary": True,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "vrp_zscore_panel",
        "source": "charts",
        "label": "Vrp zscore panel",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "vrp_term_structure",
        "source": "charts",
        "label": "Vrp term structure",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "vrp_component_attribution",
        "source": "charts",
        "label": "Vrp component attribution",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "btz_expanding_forecasts",
        "source": "charts",
        "label": "Btz expanding forecasts",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "cross_asset_vrp_comparison",
        "source": "tables",
        "label": "Cross asset vrp comparison",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "return_predictability_regression",
        "source": "tables",
        "label": "Return predictability regression",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "regime_conditional_btz",
        "source": "tables",
        "label": "Regime conditional btz",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "vrp_zscore_lookback_comparison",
        "source": "tables",
        "label": "Vrp zscore lookback comparison",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "vrp_mean_reversion_speed",
        "source": "tables",
        "label": "Vrp mean reversion speed",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "data_gaps",
        "source": "tables",
        "label": "Data gaps",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
]
