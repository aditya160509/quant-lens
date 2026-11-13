"""Screener V2 panel computations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import snapshots
from .data_loader import AS_OF, load_factor_returns, normalize_symbol, parse_symbols
from .estimators import finish_technical
from .fundamentals import fundamental_ranks
from .gics import add_industry_group
from .stats import average_rank, rank_pct


def _group_rank_pct(panel: pd.DataFrame, column: str, key: str, codes: np.ndarray | None = None) -> pd.Series:
    """Per-group rank_pct without a Python call per group."""
    if codes is None:
        codes = pd.factorize(panel[key])[0]
    values = pd.to_numeric(panel[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    valid = (codes >= 0) & ~np.isnan(values)
    counts = np.bincount(codes[valid], minlength=len(codes) + 1)  # extra slot: code -1 reads it, then is masked
    n = np.where(codes >= 0, counts[codes], np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        pct = np.clip((average_rank(values, codes) - 1) / (n - 1) * 100, 0, 100)
    pct = np.where(n <= 1, 50.0, pct)
    return pd.Series(pct, index=panel.index).where(panel[column].notna())


def metric_panel(payload: dict | None, symbols: list[str] | None = None) -> pd.DataFrame:
    payload = payload or {}
    symbols = symbols or parse_symbols(payload, default_limit=int(payload.get("default_limit") or 500))
    lookback = int(payload.get("lookback_days") or 756)
    tech, fund, latest_price_date, feature_source = snapshots.raw_panel_inputs(symbols, lookback, payload)
    tech = finish_technical(tech, [normalize_symbol(s) for s in symbols])
    dropped = tech.attrs.get("dropped_symbols", [])
    fund = fundamental_ranks(fund)
    if tech.empty:
        panel = fund
    else:
        panel = tech.merge(fund, on="ticker", how="left", suffixes=("", "_fund"), validate="one_to_one")
        panel.attrs.clear()  # rebuilt below; pandas deep-copies attrs on every operation
    if "ticker" in panel.columns and panel["ticker"].duplicated().any():
        dupes = panel.loc[panel["ticker"].duplicated(), "ticker"].astype(str).unique().tolist()[:10]
        raise ValueError(f"Duplicate ticker rows after metric panel merge: {dupes}")
    attrs = {"as_of_date": payload.get("as_of_date") or AS_OF.get(), "dropped_symbols": dropped,
             "dropped_symbol_count": len(dropped), "feature_source": feature_source}
    if panel.empty:
        panel.attrs.update(attrs)
        return panel
    panel["industry_group"] = add_industry_group(panel, industry_col="industry") if "industry" in panel.columns else "Unclassified"
    ff = load_factor_returns()
    if payload.get("as_of_date") or AS_OF.get() is not None:
        ff = ff[ff.date <= pd.Timestamp(payload.get("as_of_date") or AS_OF.get())]
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
    group_codes = {key: pd.factorize(panel[key])[0] for key in ("sector", "industry_group", "industry") if key in panel.columns}
    grouped = lambda column, key: _group_rank_pct(panel, column, key, group_codes[key])
    extra = {}  # one concat instead of 18 inserts into a wide frame
    extra["sector_relative_score"] = grouped("core_quant_score", "sector") if "sector" in panel.columns else rank_pct(panel["core_quant_score"])
    extra["industry_group_relative_score"] = grouped("core_quant_score", "industry_group") if "industry_group" in panel.columns else rank_pct(panel["core_quant_score"])
    extra["industry_relative_score"] = grouped("core_quant_score", "industry") if "industry" in panel.columns else rank_pct(panel["core_quant_score"])
    for col in [
        "valuation_percentile",
        "quality_percentile",
        "momentum_percentile",
        "low_vol_percentile",
        "liquidity_percentile",
    ]:
        if col in panel.columns:
            extra[f"sector_relative_{col}"] = grouped(col, "sector") if "sector" in panel.columns else rank_pct(panel[col])
            extra[f"industry_group_relative_{col}"] = grouped(col, "industry_group") if "industry_group" in panel.columns else rank_pct(panel[col])
            extra[f"industry_relative_{col}"] = grouped(col, "industry") if "industry" in panel.columns else rank_pct(panel[col])
    panel = pd.concat([panel, pd.DataFrame(extra, index=panel.index)], axis=1)
    panel["rank"] = panel["core_quant_score"].rank(ascending=False, method="first").astype("Int64")
    panel = panel.sort_values(["core_quant_score", "dollar_volume_20d"], ascending=False).reset_index(drop=True)
    panel.attrs.update(attrs)  # last: pandas deep-copies attrs on every operation
    return panel

