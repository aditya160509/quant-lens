"""Screener V2 panel computations."""
from __future__ import annotations

import pandas as pd

from .data_loader import AS_OF, load_factor_returns, ohlcv_for_symbols, parse_symbols
from .estimators import latest_technical_features
from .fundamentals import latest_fundamental_features
from .gics import add_industry_group
from .stats import rank_pct


def _group_rank_pct(panel: pd.DataFrame, column: str, key: str) -> pd.Series:
    """Per-group rank_pct without a Python call per group."""
    group = panel.groupby(key)[column]
    n = group.transform("count")
    pct = ((group.rank(method="average") - 1) / (n - 1) * 100).clip(0, 100)
    return pct.mask(n <= 1, 50.0).where(panel[column].notna())


def metric_panel(payload: dict | None, symbols: list[str] | None = None) -> pd.DataFrame:
    payload = payload or {}
    symbols = symbols or parse_symbols(payload, default_limit=int(payload.get("default_limit") or 500))
    lookback = int(payload.get("lookback_days") or 756)
    tech = latest_technical_features(symbols, lookback_days=lookback, periods=payload)
    dropped = tech.attrs.get("dropped_symbols", [])
    fund = latest_fundamental_features(symbols, payload.get("as_of_date"))
    if tech.empty:
        panel = fund
    else:
        panel = tech.merge(fund, on="ticker", how="left", suffixes=("", "_fund"), validate="one_to_one")
    if "ticker" in panel.columns and panel["ticker"].duplicated().any():
        dupes = panel.loc[panel["ticker"].duplicated(), "ticker"].astype(str).unique().tolist()[:10]
        raise ValueError(f"Duplicate ticker rows after metric panel merge: {dupes}")
    panel.attrs["as_of_date"] = payload.get("as_of_date") or AS_OF.get()
    panel.attrs["dropped_symbols"] = dropped
    panel.attrs["dropped_symbol_count"] = len(dropped)
    if panel.empty:
        return panel
    panel["industry_group"] = add_industry_group(panel, industry_col="industry") if "industry" in panel.columns else "Unclassified"
    ff = load_factor_returns()
    if payload.get("as_of_date") or AS_OF.get() is not None:
        ff = ff[ff.date <= pd.Timestamp(payload.get("as_of_date") or AS_OF.get())]
    observed = ohlcv_for_symbols(list(dict.fromkeys(symbols + ["SPY"])), 1)
    latest_price_date = observed.Date.max() if not observed.empty else None
    if not ff.empty and ff.date.iloc[-1] == latest_price_date:
        latest_factors = ff.tail(1).iloc[0].to_dict()
        panel["factor_observation_date"] = latest_factors["date"]
        for key in ["mkt_rf", "smb", "hml", "rmw", "cma", "mom", "rf"]:
            if key in latest_factors:
                panel[key] = latest_factors[key]
    panel["liquidity_percentile"] = rank_pct(panel.get("dollar_volume_20d", pd.Series(index=panel.index)))
    panel["size_percentile"] = rank_pct(panel.get("market_cap", pd.Series(index=panel.index)))
    panel["momentum_percentile"] = rank_pct(panel.get("momentum_jt", pd.Series(index=panel.index)))
    panel["low_vol_percentile"] = rank_pct(panel.get("realized_vol_63d", pd.Series(index=panel.index)), higher_better=False)
    panel["prox52_percentile"] = rank_pct(panel.get("prox52", pd.Series(index=panel.index)))
    if "trailing_pe" in panel:
        positive_pe = pd.to_numeric(panel["trailing_pe"], errors="coerce").where(lambda s: s > 0)
        panel["pe_percentile"] = rank_pct(positive_pe, higher_better=False)
        panel["pe_sector_percentile"] = positive_pe.groupby(panel["sector"]).rank(pct=True, ascending=False) * 100.0 if "sector" in panel else panel["pe_percentile"]
    panel["core_quant_score"] = (
        panel["valuation_percentile"] * 0.25
        + panel["quality_percentile"] * 0.25
        + panel["momentum_percentile"] * 0.25
        + panel["low_vol_percentile"] * 0.15
        + panel["liquidity_percentile"] * 0.10
    )
    panel["sector_relative_score"] = _group_rank_pct(panel, "core_quant_score", "sector") if "sector" in panel.columns else rank_pct(panel["core_quant_score"])
    panel["industry_group_relative_score"] = _group_rank_pct(panel, "core_quant_score", "industry_group") if "industry_group" in panel.columns else rank_pct(panel["core_quant_score"])
    panel["industry_relative_score"] = _group_rank_pct(panel, "core_quant_score", "industry") if "industry" in panel.columns else rank_pct(panel["core_quant_score"])
    for col in [
        "valuation_percentile",
        "quality_percentile",
        "momentum_percentile",
        "low_vol_percentile",
        "liquidity_percentile",
    ]:
        if col in panel.columns:
            panel[f"sector_relative_{col}"] = _group_rank_pct(panel, col, "sector") if "sector" in panel.columns else rank_pct(panel[col])
            panel[f"industry_group_relative_{col}"] = _group_rank_pct(panel, col, "industry_group") if "industry_group" in panel.columns else rank_pct(panel[col])
            panel[f"industry_relative_{col}"] = _group_rank_pct(panel, col, "industry") if "industry" in panel.columns else rank_pct(panel[col])
    panel["rank"] = panel["core_quant_score"].rank(ascending=False, method="first").astype("Int64")
    return panel.sort_values(["core_quant_score", "dollar_volume_20d"], ascending=False).reset_index(drop=True)

