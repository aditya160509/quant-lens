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
from app.services.volatility_v2.core.har import (
    expanding_forecasts,
    causal_combination,
    directional_dm_table,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=["SPY", "QQQ", "IWM", "EFA", "EEM"])
    horizons = payload.get("horizons", [1, 5, 10, 21, 42, 63])
    if isinstance(horizons, str):
        horizons = [int(x.strip()) for x in horizons.replace(";", ",").split(",")]
    horizons = list(dict.fromkeys(int(h) for h in horizons))
    if not horizons or any(h < 1 or h > 252 for h in horizons):
        raise ValueError("horizons must contain values from 1 to 252")
    vol = volatility_estimators(
        ohlcv,
        window=int(payload.get("rolling_window", 21)),
        annualization=int(payload.get("annualization", 252)),
    )
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
        # Require the same observed return interval for every constituent.
        # A Friday-to-Monday equity return cannot be compared with a crypto
        # Sunday-to-Monday return just because their endpoint dates match.
        observations = ohlcv.sort_values(["Ticker", "Date"]).copy()
        observations["previous_date"] = observations.groupby("Ticker").Date.shift()
        previous = observations.pivot(
            index="Date", columns="Ticker", values="previous_date"
        ).reindex(index=g.index, columns=assets)
        comparable = (
            ret.notna().all(axis=1)
            & previous.notna().all(axis=1)
            & previous.nunique(axis=1).eq(1)
        )
        x["acsv"] = ret.var(axis=1, ddof=1).where(comparable)
        variants["ACSV-HAR"] = ["daily", "weekly", "monthly", "acsv"]
        centered = ret.sub(ret.mean(axis=1), axis=0)
        x["acsv_positive"] = (
            centered.clip(lower=0).pow(2).mean(axis=1).where(comparable)
        )
        x["acsv_negative"] = (
            centered.clip(upper=0).pow(2).mean(axis=1).where(comparable)
        )
        if len(assets) >= 3:
            variants["A-ACSV-HAR"] = [
                "daily",
                "weekly",
                "monthly",
                "acsv_positive",
                "acsv_negative",
            ]
    requested = payload.get("models")
    if requested and "HAR-X" in requested:
        from app.services.volatility_v2.core.vrp import (
            observed_iv,
            integrated_garch_variance,
        )

        implied, iv_source = observed_iv(asset, g.index, payload.get("iv_upload_id"))
        physical = integrated_garch_variance(
            ret[asset],
            horizons=(21,),
            min_train=int(payload.get("min_train", 252)),
            refit_interval=int(payload.get("refit_interval", 21)),
        )
        x["vrp"] = (implied[30].pow(2) - physical[21]).reindex(x.index)
        variants["HAR-X"] = ["daily", "weekly", "monthly", "vrp"]
    if isinstance(requested, str):
        requested = [m.strip() for m in requested.split(",")]
    if requested is not None:
        unknown = set(requested) - set(variants)
        if unknown:
            raise ValueError("Unavailable HAR variants: " + ", ".join(sorted(unknown)))
        variants = {m: variants[m] for m in requested}
    accuracy, parameters, forecasts, mcs_rows, combinations = [], [], [], [], []
    directional = []
    for horizon in horizons:
        losses, model_rows = {}, {}
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
                loss_function=payload.get("mcs_loss", "qlike"),
                directional_baseline=daily,
            )
            if not rows.forecast.notna().any():
                raise ValueError(
                    f"Insufficient complete training history for {name} at horizon {horizon}"
                )
            model_rows[name] = rows
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
        directional.extend(directional_dm_table(model_rows, daily, horizon))
        combinations.extend(
            causal_combination(model_rows, horizon, payload.get("mcs_loss", "qlike"))
        )
        members = (
            set(
                model_confidence_set(
                    losses,
                    reps=int(payload.get("bootstrap_reps", 200)),
                    alpha=1 - float(payload.get("mcs_confidence", 0.9)),
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
            "causal_forecast_combinations": combinations,
            "walk_forward_forecast_chart": forecasts,
            "forecast_confidence_bands": forecasts,
            "acsv_predictive_contribution": compact_records(x[["acsv"]].reset_index())
            if "acsv" in x
            else [],
        },
        tables={
            "har_parameter_table": parameters,
            "directional_dm_tournament": directional,
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
                "macro HAR-X": "Macroeconomic release vintages are unavailable; supported HAR-X uses the same observed IV and integrated physical-variance engine as Feature 05",
                "HAR-J/HAR-J-Signed": "Daily OHLC cannot identify intraday bipower jump variation",
                "MCS-selected combinations": "Held-out whole-sample MCS membership is retrospective; combinations instead use all requested models and past matured losses",
            },
            "har_x": {
                "source": iv_source,
                "regressor": "30-day observed implied variance minus 21-session integrated physical variance",
            }
            if "HAR-X" in variants
            else {"status": "not requested"},
            "acsv_universe": assets,
            "historical_membership": "Explicit fixed constituent universe; no claim of historical index membership",
        },
    )


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field("annualization", 252, kind="integer"),
    field("iv_upload_id", None, group="Data"),
    field("confidence_level", 0.9),
    field("mcs_loss", "qlike"),
    field("mcs_confidence", 0.9),
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
        options=["HAR", "LHAR", "HAR-Leverage", "ACSV-HAR", "A-ACSV-HAR", "HAR-X"],
    ),
    field("rolling_window", 21, kind="integer", group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 21, kind=None, group="Model"),
    field("nw_bandwidth", None, kind="integer", group="Model"),
    field("bootstrap_reps", 200, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "directional_dm_tournament",
        "source": "tables",
        "label": "Directional accuracy DM tournament",
        "render": "table",
        "primary": False,
        "help": "HAC comparisons of aligned held-out up/down volatility prediction losses.",
        "empty_reason": "Insufficient aligned held-out directional evaluations.",
    },
    {
        "key": "causal_forecast_combinations",
        "source": "charts",
        "label": "Causal forecast combinations",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted causal forecast combinations. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "multi_horizon_forecast_chart",
        "source": "charts",
        "label": "Multi horizon forecast chart",
        "render": "line",
        "primary": True,
        "help": "Actual observed or fitted multi horizon forecast chart. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "walk_forward_forecast_chart",
        "source": "charts",
        "label": "Walk forward forecast chart",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted walk forward forecast chart. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "forecast_confidence_bands",
        "source": "charts",
        "label": "Forecast confidence bands",
        "render": "band",
        "primary": False,
        "help": "Actual observed or fitted forecast confidence bands. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "acsv_predictive_contribution",
        "source": "charts",
        "label": "Acsv predictive contribution",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted acsv predictive contribution. At least two complete explicitly selected constituents are required.",
        "empty_reason": "At least two complete explicitly selected constituents are required.",
    },
    {
        "key": "har_parameter_table",
        "source": "tables",
        "label": "Har parameter table",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted har parameter table. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "forecast_accuracy_table",
        "source": "tables",
        "label": "Forecast accuracy table",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted forecast accuracy table. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "model_confidence_set",
        "source": "tables",
        "label": "Model confidence set",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted model confidence set. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "walk_forward_accuracy",
        "source": "tables",
        "label": "Walk forward accuracy",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted walk forward accuracy. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
]
