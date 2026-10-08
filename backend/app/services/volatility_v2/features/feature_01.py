"""Feature 01: Multi-estimator daily volatility engine."""

from __future__ import annotations
from .inputs import field
import numpy as np

from app.services.volatility_v2.core.analytics import (
    ESTIMATORS,
    agreement_index,
    clean_json,
    compact_records,
    disagreement_pair,
    load_assets,
    number_like,
    opening_gap_fragility,
    response,
    summary_card,
    vol_adjusted_momentum,
    volatility_estimators,
    volatility_estimators_multi,
    matrix_records,
)

from app.services.volatility_v2.core.estimator_diagnostics import (
    dm_tournament,
    estimator_efficiency_table,
    range_correlation_matrix,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload)
    window = int(
        number_like(payload.get("rolling_window"))
        or number_like(payload.get("window_days"))
        or 21
    )
    annualization = int(number_like(payload.get("annualization")) or 252)
    minimum_volume = float(payload.get("minimum_observed_volume", 0))
    if minimum_volume > 0:
        latest_volume = (
            ohlcv.sort_values("Date")
            .groupby("Ticker")
            .tail(window)
            .groupby("Ticker")
            .Volume.mean()
        )
        unavailable = latest_volume.index[
            latest_volume.isna() | latest_volume.lt(minimum_volume)
        ].tolist()
        if unavailable:
            raise ValueError(
                "Assets below the declared native-unit volume threshold: "
                + ", ".join(unavailable)
            )
    include_overnight = payload.get("include_overnight", True)
    vol = volatility_estimators(
        ohlcv,
        window=window,
        annualization=annualization,
        include_overnight=include_overnight,
    )
    multi_window = []
    multi_vol = volatility_estimators_multi(
        ohlcv,
        [10, 21, 42, 63, 126, 252],
        annualization=annualization,
        include_overnight=include_overnight,
    )
    for w, vw in multi_vol.items():
        last = vw.sort_values("date").groupby("asset").tail(1)
        for _, row in last.iterrows():
            multi_window.append(
                {
                    "asset": row["asset"],
                    "window": w,
                    **{est: row[est] for est in ESTIMATORS},
                }
            )
    active = (
        str(payload.get("asset") or payload.get("symbol") or assets[0])
        .upper()
        .replace("-", "_")
    )
    primary = vol[vol["asset"].eq(active)]
    if primary.empty:
        raise ValueError(
            f"Selected asset {active} has no complete estimator observations"
        )
    latest = primary.sort_values("date").tail(1).iloc[0]
    agree = agreement_index(primary)
    latest_agree = (
        float(agree["agreement"].dropna().iloc[-1])
        if not agree["agreement"].dropna().empty
        else None
    )
    ranked = (
        vol.sort_values("date")
        .groupby("asset")
        .tail(1)[["asset", *ESTIMATORS, "estimator_spread"]]
        .sort_values("yang_zhang", ascending=False)
    )
    for est in ESTIMATORS:
        ranked[f"{est}_percentile"] = ranked["asset"].map(
            lambda a, est=est: float(
                (
                    vol.loc[vol["asset"].eq(a), est]
                    <= ranked.loc[ranked["asset"].eq(a), est].iloc[0]
                ).mean()
                * 100
            )
        )
    comparison = primary[["date", *ESTIMATORS, "estimator_spread"]].copy()
    comparison["min_estimator"] = comparison[ESTIMATORS].min(axis=1)
    comparison["max_estimator"] = comparison[ESTIMATORS].max(axis=1)
    ogf = opening_gap_fragility(ohlcv)
    routing = []
    if payload.get("auto_route_opening_gap", False):
        joined = primary.merge(
            ogf[["date", "asset", "ogf_percentile"]], on=["date", "asset"], how="left"
        )
        joined = joined.dropna(subset=["ogf_percentile"])
        fragile = joined.ogf_percentile >= float(
            payload.get("opening_gap_percentile_threshold", 90)
        )
        joined["selected_estimator"] = np.where(
            fragile, "rogers_satchell", "yang_zhang"
        )
        joined["routed_annualized_vol"] = np.where(
            fragile, joined.rogers_satchell, joined.yang_zhang
        )
        routing = compact_records(
            joined[
                [
                    "date",
                    "asset",
                    "ogf_percentile",
                    "selected_estimator",
                    "routed_annualized_vol",
                ]
            ]
        )
    range_method = str(payload.get("range_correlation_method", "pearson"))
    range_corr = range_correlation_matrix(ohlcv, method=range_method)
    mom_adj = vol_adjusted_momentum(ohlcv, vol)
    hourly = []
    if payload.get("include_hourly_variation", False):
        from app.services.volatility_v2.core.intraday import sampled_variation

        sampled = sampled_variation(
            active,
            primary.date.min(),
            primary.date.max(),
            payload.get("hourly_timezone"),
            payload.get("session_timezone"),
            int(payload.get("minimum_hourly_bars", 6)),
        )
        hourly = compact_records(sampled, limit=len(sampled))
    summary = [
        summary_card("Yang-Zhang Vol", float(latest["yang_zhang"]), "ann"),
        summary_card("Estimator Spread", float(latest["estimator_spread"]), "ann"),
        summary_card(
            "Current Percentile",
            float((primary["yang_zhang"] <= latest["yang_zhang"]).mean() * 100),
            "pct",
        ),
        summary_card("Agreement", latest_agree, "corr"),
    ]
    alerts = []
    if latest_agree is not None and latest_agree < 0.5:
        pair = disagreement_pair(primary) or {}
        alerts.append(
            {
                "level": "warning",
                "message": f"Estimator agreement below 0.50; weakest pair is {pair.get('estimator_a')} vs {pair.get('estimator_b')} at {pair.get('correlation'):.2f}.",
            }
        )
    return response(
        "01",
        summary,
        charts={
            "observed_hourly_variation": hourly,
            "opening_gap_estimator_routing": routing,
            "five_estimator_comparison": compact_records(comparison),
            "estimator_disagreement_band": compact_records(
                comparison[
                    ["date", "min_estimator", "max_estimator", "estimator_spread"]
                ]
            ),
            "estimator_agreement_index": compact_records(agree),
            "annualized_vol_panel": clean_json(estimator_efficiency_table(primary)),
            "multi_window_estimator_panel": clean_json(multi_window),
            "opening_gap_fragility": compact_records(ogf[ogf["asset"].eq(active)])
            if not ogf.empty
            else [],
            "range_correlation_matrix": matrix_records(range_corr)
            if not range_corr.empty
            else [],
            "vol_adjusted_momentum_panel": compact_records(mom_adj, limit=300),
        },
        tables={
            "estimator_efficiency": estimator_efficiency_table(primary),
            "diebold_mariano_tournament": dm_tournament(
                primary,
                annualization=annualization,
                horizon=int(payload.get("dm_horizon", 5)),
            ),
            "cross_asset_ranked_panel": compact_records(ranked, limit=200),
            "multi_window_estimator_table": clean_json(multi_window),
            "opening_gap_fragility_detector": compact_records(
                ogf.sort_values("date").groupby("asset").tail(1), limit=200
            )
            if not ogf.empty
            else [],
            "vol_adjusted_momentum": compact_records(mom_adj, limit=300),
        },
        alerts=alerts,
        meta={
            "asset": active,
            "assets": assets,
            "window": window,
            "annualization": annualization,
            "range_correlation_method": range_method,
            "overnight_policy": "Yang-Zhang overnight component included"
            if include_overnight
            else "Explicit Yang-Zhang intraday-only variant; overnight term excluded. Close-close returns remain unchanged",
            "volume_threshold": {
                "value": minimum_volume,
                "units": "Observed native Volume units, not USD liquidity or comparable units across assets",
            },
            "routing_policy": "User-selected OGF percentile policy routes high-gap dates to observed Rogers-Satchell intraday variance; other dates to Yang-Zhang. This is not an empirically optimal full-session estimator",
            "session_policy": "Daily source OHLC boundaries define sessions. Daily bars cannot reconstruct another exchange calendar or timezone",
            "unsupported_outputs": {
                "bandi_russell_estimator": "Daily OHLC and hourly bars cannot identify optimal microstructure-noise sampling; the dimensionally invalid daily proxy was removed",
                "sampling_efficiency": "Requires repeated sampling under an explicit data-generating model",
            },
            "hourly_measure": "Consecutive hourly close variation within declared session dates; opening and overnight returns excluded. No tick-noise correction or statistical jump significance is claimed",
            "dm_target": "Observed next-h-session sum of squared log returns; forecasts scaled to the same horizon",
        },
    )


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field(
        "include_overnight",
        True,
        help="Include the overnight variance term in Yang-Zhang. Exclusion produces an explicitly disclosed intraday-only variant; other estimators remain unchanged.",
    ),
    field(
        "minimum_observed_volume",
        0.0,
        help="Minimum trailing mean observed Volume in its native units. Selected assets below the threshold fail explicitly.",
    ),
    field(
        "auto_route_opening_gap",
        False,
        help="Declared routing policy, not estimated optimality: choose RS intraday variance above the selected opening-gap percentile.",
    ),
    field("opening_gap_percentile_threshold", 90.0),
    field("assets", ["SPY"], kind="symbols", group="Data"),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("include_hourly_variation", False, kind=None, group="Model"),
    field("range_correlation_method", "pearson", kind=None, group="Model"),
    field("hourly_timezone", None, kind=None, group="Data"),
    field("session_timezone", None, kind=None, group="Data"),
    field("rolling_window", 21, kind="integer", group="Model"),
    field("annualization", 252, kind="integer", group="Model"),
    field("minimum_hourly_bars", 6, kind="integer", group="Model"),
    field("dm_horizon", 5, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "opening_gap_estimator_routing",
        "source": "charts",
        "label": "Declared opening-gap routing policy",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted declared opening-gap routing policy. Routing was not requested, or the trailing opening-gap percentile has not matured.",
        "empty_reason": "Routing was not requested, or the trailing opening-gap percentile has not matured.",
    },
    {
        "key": "observed_hourly_variation",
        "source": "charts",
        "label": "Observed hourly variation",
        "render": "line",
        "primary": True,
        "help": "Actual observed or fitted observed hourly variation. Hourly variation was not requested, or complete consecutive hourly bars with declared timezones are unavailable.",
        "empty_reason": "Hourly variation was not requested, or complete consecutive hourly bars with declared timezones are unavailable.",
    },
    {
        "key": "five_estimator_comparison",
        "source": "charts",
        "label": "Five estimator comparison",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted five estimator comparison. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "estimator_disagreement_band",
        "source": "charts",
        "label": "Estimator disagreement band",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted estimator disagreement band. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "estimator_agreement_index",
        "source": "charts",
        "label": "Estimator agreement index",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted estimator agreement index. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "annualized_vol_panel",
        "source": "charts",
        "label": "Annualized vol panel",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted annualized vol panel. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "multi_window_estimator_panel",
        "source": "charts",
        "label": "Multi window estimator panel",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted multi window estimator panel. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "opening_gap_fragility",
        "source": "charts",
        "label": "Opening gap fragility",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted opening gap fragility. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "range_correlation_matrix",
        "source": "charts",
        "label": "Range correlation matrix",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted range correlation matrix. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "vol_adjusted_momentum_panel",
        "source": "charts",
        "label": "Vol adjusted momentum panel",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted vol adjusted momentum panel. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "estimator_efficiency",
        "source": "tables",
        "label": "Observed estimator diagnostics",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted estimator efficiency. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "diebold_mariano_tournament",
        "source": "tables",
        "label": "Diebold mariano tournament",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted diebold mariano tournament. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "cross_asset_ranked_panel",
        "source": "tables",
        "label": "Cross asset ranked panel",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted cross asset ranked panel. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "multi_window_estimator_table",
        "source": "tables",
        "label": "Multi window estimator table",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted multi window estimator table. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "opening_gap_fragility_detector",
        "source": "tables",
        "label": "Opening gap fragility detector",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted opening gap fragility detector. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "vol_adjusted_momentum",
        "source": "tables",
        "label": "Vol adjusted momentum",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted vol adjusted momentum. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
]
