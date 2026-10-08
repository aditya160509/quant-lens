"""Feature 03: genuine expanding-window HAR family forecasts."""

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
    model_confidence_set,
)
from app.services.volatility_v2.core.har import expanding_forecasts


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=["SPY", "QQQ", "IWM", "EFA", "EEM"])
    horizons = payload.get("horizons", [1, 5, 10, 21, 42, 63])
    if isinstance(horizons, str):
        horizons = [int(x.strip()) for x in horizons.replace(";", ",").split(",")]
    horizons = list(dict.fromkeys(int(h) for h in horizons))
    if not horizons or any(h < 1 or h > 252 for h in horizons):
        raise ValueError("horizons must contain values from 1 to 252")
    vol = volatility_estimators(ohlcv, window=int(payload.get("rolling_window", 21)))
    asset = assets[0]
    g = vol.loc[vol.asset.eq(asset)].sort_values("date").set_index("date")
    estimator = payload.get("estimator", "yang_zhang")
    if estimator not in (
        "cc",
        "parkinson",
        "garman_klass",
        "rogers_satchell",
        "yang_zhang",
    ):
        raise ValueError("Unknown estimator")
    daily = g[estimator].astype(float)
    ret = returns_panel(ohlcv).reindex(g.index)
    x = pd.DataFrame(
        {
            "daily": daily,
            "weekly": daily.rolling(5).mean(),
            "monthly": daily.rolling(22).mean(),
            "ret_pos": g["return"].clip(lower=0),
            "ret_neg": g["return"].clip(upper=0),
        },
        index=g.index,
    )
    variants = {
        "HAR": ["daily", "weekly", "monthly"],
        "LHAR": ["daily", "weekly", "monthly"],
        "HAR-Leverage": ["daily", "weekly", "monthly", "ret_pos", "ret_neg"],
    }
    if len(assets) >= 2:
        # Cross-sectional variance requires every requested constituent that day.
        x["acsv"] = ret.var(axis=1, ddof=1).where(ret.notna().all(axis=1))
        variants["ACSV-HAR"] = ["daily", "weekly", "monthly", "acsv"]
    requested = payload.get("models")
    if isinstance(requested, str):
        requested = [m.strip() for m in requested.split(",")]
    if requested is not None:
        unknown = set(requested) - set(variants)
        if unknown:
            raise ValueError("Unavailable HAR variants: " + ", ".join(sorted(unknown)))
        variants = {m: variants[m] for m in requested}
    accuracy, parameters, forecasts, mcs_rows = [], [], [], []
    for horizon in horizons:
        losses = {}
        for name, cols in variants.items():
            design = np.log(x[cols].where(x[cols] > 0)) if name == "LHAR" else x[cols]
            rows, metrics, loss, coefficients = expanding_forecasts(
                design,
                daily.shift(-horizon),
                horizon,
                int(payload.get("min_train", 252)),
                int(payload.get("refit_interval", 21)),
                log_target=name == "LHAR",
                bandwidth=int(payload.get("nw_bandwidth", horizon)),
                confidence=float(payload.get("confidence_level", 0.9)),
            )
            if not rows.forecast.notna().any():
                raise ValueError(
                    f"Insufficient complete training history for {name} at horizon {horizon}"
                )
            rows["model"], rows["horizon"] = name, horizon
            forecasts.extend(
                compact_records(rows.loc[rows.forecast.notna()], limit=420)
            )
            accuracy.append({"model": name, "horizon": horizon, **metrics})
            parameters.extend(
                {"model": name, "horizon": horizon, **row} for row in coefficients
            )
            if not loss.empty:
                losses[name] = loss
        members = (
            set(
                model_confidence_set(
                    losses, reps=int(payload.get("bootstrap_reps", 200))
                )
            )
            if losses
            else set()
        )
        mcs_rows.extend(
            {"model": name, "horizon": horizon, "mcs_member": name in members}
            for name in variants
        )
    scored = [r for r in accuracy if r["rmse"] is not None]
    best = min(scored, key=lambda r: r["rmse"]) if scored else None
    return response(
        "03",
        [
            summary_card("Best HAR Variant", best["model"] if best else None),
            summary_card("Best OOS RMSE", best["rmse"] if best else None, "vol"),
        ],
        charts={
            "multi_horizon_forecast_chart": forecasts,
            "walk_forward_forecast_chart": forecasts,
            "forecast_confidence_bands": forecasts,
            "acsv_predictive_contribution": compact_records(x[["acsv"]].reset_index())
            if "acsv" in x
            else [],
        },
        tables={
            "har_parameter_table": parameters,
            "forecast_accuracy_table": accuracy,
            "model_confidence_set": mcs_rows,
            "walk_forward_accuracy": accuracy,
        },
        meta={
            "asset": asset,
            "assets": assets,
            "estimator": estimator,
            "estimation": "statsmodels OLS/HAC with expanding training and matured labels; held-out forecasts for every selected horizon",
            "confidence_bands": f"{float(payload.get('confidence_level', 0.9)):.0%} conditional OLS prediction intervals, transformed for LHAR; exclude parameter selection uncertainty",
            "removed_outputs": {
                "HAR-X": "No macro release vintages or observed asset-specific implied volatility",
                "HAR-J/HAR-J-Signed": "Daily OHLC cannot identify intraday bipower jump variation",
                "MCS combinations": "Full evaluation sample cannot set historical combination weights",
            },
            "acsv_universe": assets,
            "historical_membership": "Explicit fixed constituent universe; no claim of historical index membership",
        },
    )


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field("confidence_level", 0.9),
    field("assets", ["SPY", "QQQ", "IWM", "EFA", "EEM"], kind="symbols", group="Data"),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("horizons", [1, 5, 10, 21, 42, 63], kind="list", group="Model"),
    field("estimator", "yang_zhang", kind=None, group="Model"),
    field(
        "models",
        None,
        kind="list",
        group="Model",
        options=["HAR", "LHAR", "HAR-Leverage", "ACSV-HAR"],
    ),
    field("rolling_window", 21, kind="integer", group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 21, kind=None, group="Model"),
    field("nw_bandwidth", None, kind="integer", group="Model"),
    field("bootstrap_reps", 200, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "multi_horizon_forecast_chart",
        "source": "charts",
        "label": "Multi horizon forecast chart",
        "render": "line",
        "primary": True,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "walk_forward_forecast_chart",
        "source": "charts",
        "label": "Walk forward forecast chart",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "forecast_confidence_bands",
        "source": "charts",
        "label": "Forecast confidence bands",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "acsv_predictive_contribution",
        "source": "charts",
        "label": "Acsv predictive contribution",
        "render": "line",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "har_parameter_table",
        "source": "tables",
        "label": "Har parameter table",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "forecast_accuracy_table",
        "source": "tables",
        "label": "Forecast accuracy table",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "model_confidence_set",
        "source": "tables",
        "label": "Model confidence set",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
    {
        "key": "walk_forward_accuracy",
        "source": "tables",
        "label": "Walk forward accuracy",
        "render": "table",
        "primary": False,
        "help": "Observed or fitted output; empty conditional outputs have an explanation in response metadata.",
    },
]
