"""Feature 01: Multi-estimator daily volatility engine."""

from __future__ import annotations

from app.services.volatility_v2.core.analytics import (
    ESTIMATORS,
    agreement_index,
    bandi_russell_daily_proxy,
    clean_json,
    compact_records,
    disagreement_pair,
    dm_tournament,
    estimator_efficiency_table,
    load_assets,
    number_like,
    opening_gap_fragility,
    range_correlation_matrix,
    response,
    summary_card,
    vol_adjusted_momentum,
    volatility_estimators,
    volatility_estimators_multi,
    matrix_records,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload)
    window = int(number_like(payload.get("rolling_window")) or number_like(payload.get("window_days")) or 21)
    annualization = int(number_like(payload.get("annualization")) or 252)
    vol = volatility_estimators(ohlcv, window=window, annualization=annualization)
    multi_window = []
    multi_vol = volatility_estimators_multi(ohlcv, [10, 21, 42, 63, 126, 252], annualization=annualization)
    for w, vw in multi_vol.items():
        last = vw.sort_values("date").groupby("asset").tail(1)
        for _, row in last.iterrows():
            multi_window.append({"asset": row["asset"], "window": w, **{est: row[est] for est in ESTIMATORS}})
    active = str(payload.get("asset") or payload.get("symbol") or assets[0]).upper().replace("-", "_")
    primary = vol[vol["asset"].eq(active)]
    if primary.empty:
        primary = vol[vol["asset"].eq(vol["asset"].iloc[0])]
    latest = primary.sort_values("date").tail(1).iloc[0]
    agree = agreement_index(primary)
    latest_agree = float(agree["agreement"].dropna().iloc[-1]) if not agree["agreement"].dropna().empty else None
    ranked = (
        vol.sort_values("date")
        .groupby("asset")
        .tail(1)[["asset", *ESTIMATORS, "estimator_spread"]]
        .sort_values("yang_zhang", ascending=False)
    )
    for est in ESTIMATORS:
        ranked[f"{est}_percentile"] = ranked["asset"].map(lambda a, est=est: float((vol.loc[vol["asset"].eq(a), est] <= ranked.loc[ranked["asset"].eq(a), est].iloc[0]).mean() * 100))
    comparison = primary[["date", *ESTIMATORS, "estimator_spread"]].copy()
    comparison["min_estimator"] = comparison[ESTIMATORS].min(axis=1)
    comparison["max_estimator"] = comparison[ESTIMATORS].max(axis=1)
    br = bandi_russell_daily_proxy(ohlcv, window=window, annualization=annualization)
    ogf = opening_gap_fragility(ohlcv)
    range_corr = range_correlation_matrix(ohlcv)
    mom_adj = vol_adjusted_momentum(ohlcv, vol)
    if not br.empty:
        comparison = comparison.merge(br[br["asset"].eq(active)][["date", "bandi_russell_daily_proxy"]], on="date", how="left")
    summary = [
        summary_card("Yang-Zhang Vol", float(latest["yang_zhang"]), "ann"),
        summary_card("Estimator Spread", float(latest["estimator_spread"]), "ann"),
        summary_card("Current Percentile", float((primary["yang_zhang"] <= latest["yang_zhang"]).mean() * 100), "pct"),
        summary_card("Agreement", latest_agree, "corr"),
    ]
    alerts = []
    if latest_agree is not None and latest_agree < 0.5:
        pair = disagreement_pair(primary) or {}
        alerts.append({"level": "warning", "message": f"Estimator agreement below 0.50; weakest pair is {pair.get('estimator_a')} vs {pair.get('estimator_b')} at {pair.get('correlation'):.2f}."})
    return response(
        "01",
        summary,
        charts={
            "five_estimator_comparison": compact_records(comparison),
            "estimator_disagreement_band": compact_records(comparison[["date", "min_estimator", "max_estimator", "estimator_spread"]]),
            "estimator_agreement_index": compact_records(agree),
            "annualized_vol_panel": clean_json(estimator_efficiency_table(primary)),
            "multi_window_estimator_panel": clean_json(multi_window),
            "bandi_russell_estimator": compact_records(br[br["asset"].eq(active)]) if not br.empty else [],
            "opening_gap_fragility": compact_records(ogf[ogf["asset"].eq(active)]) if not ogf.empty else [],
            "range_correlation_matrix": matrix_records(range_corr) if not range_corr.empty else [],
            "vol_adjusted_momentum_panel": compact_records(mom_adj, limit=300),
        },
        tables={
            "estimator_efficiency": estimator_efficiency_table(primary),
            "diebold_mariano_tournament": dm_tournament(primary),
            "cross_asset_ranked_panel": compact_records(ranked, limit=200),
            "multi_window_estimator_table": clean_json(multi_window),
            "bandi_russell_liquidity_proxy": compact_records(br, limit=300),
            "opening_gap_fragility_detector": compact_records(ogf.sort_values("date").groupby("asset").tail(1), limit=200) if not ogf.empty else [],
            "vol_adjusted_momentum": compact_records(mom_adj, limit=300),
        },
        alerts=alerts,
        meta={"asset": active, "assets": assets, "window": window, "annualization": annualization, "implemented_outputs": 10},
    )
