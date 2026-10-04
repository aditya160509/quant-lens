"""Screener V2 screener computations."""
from __future__ import annotations
import re
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import close_matrix
from .common import records, clean_json, number_like


DEFAULT_TOP_N = 50


def _range_filter(df: pd.DataFrame, col: str, min_value: Any = None, max_value: Any = None) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    if col not in df.columns:
        return mask
    numeric = pd.to_numeric(df[col], errors="coerce")
    lo = number_like(min_value)
    hi = number_like(max_value)
    if lo is not None:
        mask &= numeric >= lo
    if hi is not None:
        mask &= numeric <= hi
    return mask


def apply_filters(panel: pd.DataFrame, payload: dict | None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    payload = payload or {}
    if panel.empty:
        return panel, []
    payload = dict(payload)
    if any(key in payload for key in ("vol_forecast_min", "vol_forecast_max")):
        raise ValueError("HAR forecasts are unavailable; use explicitly named yang_zhang_vol_min/max estimates")
    for key, column in [("industry_group", "industry_group"), ("industry_groups", "industry_group"), ("exchange", "exchange"), ("exchanges", "exchange")]:
        if payload.get(key) and str(payload[key]).lower() not in {"all", "any"} and (column not in panel or panel[column].replace(["", "Unknown", "Unclassified"], np.nan).isna().all()):
            raise ValueError(f"Requested filter {key} is unavailable in the local data")
    preset = str(payload.get("dollar_volume_preset") or "").lower()
    if preset and "dollar_volume_min" not in payload:
        preset_map = {
            "micro": 250_000,
            "small": 1_000_000,
            "institutional": 10_000_000,
            "large": 25_000_000,
            "very_liquid": 100_000_000,
        }
        if preset in preset_map:
            payload["dollar_volume_min"] = preset_map[preset]
    stages: list[dict[str, Any]] = [{"stage": "Initial universe", "remaining": int(len(panel)), "removed": 0}]
    filtered = panel.copy()

    def apply(stage: str, mask: pd.Series) -> None:
        nonlocal filtered
        before = len(filtered)
        filtered = filtered[mask.reindex(filtered.index).fillna(False)]
        stages.append({"stage": stage, "remaining": int(len(filtered)), "removed": int(before - len(filtered))})

    sectors = payload.get("sectors") or payload.get("sector")
    if sectors and str(sectors).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (sectors if isinstance(sectors, list) else re.split(r"[,;]", str(sectors))) if str(s).strip()}
        apply("Sector filter", filtered["sector"].astype(str).str.lower().isin(allowed))
    industries = payload.get("industries") or payload.get("industry")
    if industries and str(industries).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (industries if isinstance(industries, list) else re.split(r"[,;]", str(industries))) if str(s).strip()}
        apply("Industry filter", filtered["industry"].astype(str).str.lower().isin(allowed))
    industry_groups = payload.get("industry_groups") or payload.get("industry_group")
    if industry_groups and str(industry_groups).lower() not in {"all", "any"} and "industry_group" in filtered:
        allowed = {str(s).strip().lower() for s in (industry_groups if isinstance(industry_groups, list) else re.split(r"[,;]", str(industry_groups))) if str(s).strip()}
        apply("Industry group filter", filtered["industry_group"].astype(str).str.lower().isin(allowed))
    for col, lo_key, hi_key, label in [
        ("market_cap", "market_cap_min", "market_cap_max", "Market cap"),
        ("price_usd", "price_min", "price_max", "Price"),
        ("dollar_volume_20d", "dollar_volume_min", "dollar_volume_max", "Dollar volume"),
        ("trailing_pe", "pe_min", "pe_max", "P/E"),
        ("roic", "roic_min", "roic_max", "ROIC"),
        ("bollinger_width_percentile", "bollinger_width_percentile_min", "bollinger_width_percentile_max", "Bollinger width percentile"),
        ("prox52_percentile", "prox52_percentile_min", "prox52_percentile_max", "PROX52 percentile"),
        ("pb_ratio", "pb_min", "pb_max", "P/B"),
        ("forward_pe", "forward_pe_min", "forward_pe_max", "Forward P/E"),
        ("p_cf", "p_cf_min", "p_cf_max", "P/CF"),
        ("ev_ebit", "ev_ebit_min", "ev_ebit_max", "EV/EBIT"),
        ("interest_coverage", "interest_coverage_min", "interest_coverage_max", "Interest coverage"),
        ("revenue_growth_yoy", "revenue_growth_yoy_min", "revenue_growth_yoy_max", "Revenue growth YoY"),
        ("eps_growth_yoy", "eps_growth_yoy_min", "eps_growth_yoy_max", "EPS growth YoY"),
        ("revenue_growth_3y_cagr", "revenue_growth_3y_cagr_min", "revenue_growth_3y_cagr_max", "Revenue 3Y CAGR"),
        ("debt_ebitda", "debt_ebitda_min", "debt_ebitda_max", "Debt/EBITDA"),
        ("payout_ratio", "payout_ratio_min", "payout_ratio_max", "Payout ratio"),
        ("roe", "roe_min", "roe_max", "ROE"),
        ("debt_equity", "debt_equity_min", "debt_equity_max", "Debt/equity"),
        ("shares_outstanding", "shares_outstanding_min", "shares_outstanding_max", "Shares outstanding"),
        ("float_percent", "float_percent_min", "float_percent_max", "Float percent"),
        ("atr_pct_price", "atr_pct_min", "atr_pct_max", "ATR %"),
        ("adx_14", "adx_min", "adx_max", "ADX"),
        ("stochastic_k", "stochastic_min", "stochastic_max", "Stochastic"),
        ("williams_r", "williams_r_min", "williams_r_max", "Williams %R"),
        ("ivol_ff3_63d", "ivol_min", "ivol_max", "FF3 IVOL"),
        ("max_1d_return_21d", "max_factor_min", "max_factor_max", "MAX factor"),
        ("prox52", "prox52_min", "prox52_max", "PROX52"),
        ("pct_from_52w_high", "high_proximity_min", "high_proximity_max", "52W high proximity"),
        ("vratio", "vratio_min", "vratio_max", "Volume ratio"),
        ("yang_zhang_vol_21d_estimate", "yang_zhang_vol_min", "yang_zhang_vol_max", "Yang-Zhang trailing volatility estimate"),
        ("amihud_percentile", "amihud_percentile_min", "amihud_percentile_max", "Amihud percentile"),
        ("core_quant_score", "score_min", "score_max", "Quant score"),
    ]:
        if lo_key not in payload and hi_key not in payload:
            continue
        if col not in filtered or filtered[col].notna().sum() == 0:
            raise ValueError(f"Requested filter {label} is unavailable in the local data")
        for bound in (lo_key, hi_key):
            if bound in payload and number_like(payload[bound]) is None:
                raise ValueError(f"Invalid numeric filter: {bound}")
        mask = _range_filter(filtered, col, payload.get(lo_key), payload.get(hi_key))
        if not mask.all():
            apply(label, mask)
    exchanges = payload.get("exchange") or payload.get("exchanges")
    if exchanges and "exchange" in filtered.columns and str(exchanges).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (exchanges if isinstance(exchanges, list) else re.split(r"[,;]", str(exchanges))) if str(s).strip()}
        apply("Exchange", filtered["exchange"].astype(str).str.lower().isin(allowed))
    if payload.get("dividend_paying_only"):
        apply("Dividend payers", pd.to_numeric(filtered.get("dividend_yield", 0), errors="coerce").fillna(0) > 0)
    if payload.get("exclude_negative_pe") and "trailing_pe" in filtered:
        apply("Negative P/E exclusion", pd.to_numeric(filtered["trailing_pe"], errors="coerce") > 0)
    if payload.get("exclude_penny_stocks", True):
        apply("Penny stock exclusion", pd.to_numeric(filtered["price_usd"], errors="coerce").ge(1.0))
    if payload.get("sma_bullish_only"):
        apply("SMA bullish", pd.to_numeric(filtered.get("sma50_above_sma200", 0), errors="coerce").fillna(0) > 0)
    if payload.get("golden_cross_within_n_days"):
        n_days = max(1, int(payload.get("golden_cross_within_n_days")))
        apply("Golden cross recent", pd.to_numeric(filtered.get("golden_cross_age_days", np.nan), errors="coerce").le(n_days))
    if payload.get("death_cross_within_n_days"):
        n_days = max(1, int(payload.get("death_cross_within_n_days")))
        apply("Death cross recent", pd.to_numeric(filtered.get("death_cross_age_days", np.nan), errors="coerce").le(n_days))
    if payload.get("macd_bullish_only"):
        apply("MACD bullish", pd.to_numeric(filtered.get("macd_bullish", 0), errors="coerce").fillna(0) > 0)
    if payload.get("obv_positive_only"):
        apply("OBV positive", pd.to_numeric(filtered.get("obv_20d_slope", 0), errors="coerce").fillna(0) > 0)
    return filtered.reset_index(drop=True), stages


def top_table(panel: pd.DataFrame, n: int = DEFAULT_TOP_N) -> pd.DataFrame:
    cols = [
        "currency_units_unavailable_reason", "quote_currency", "financial_currency", "market_value_currency", "market_cap_statement_currency", "price_usd", "market_cap_observation_date", "market_cap_basis", "price_observation_date",
        "rank",
        "ticker",
        "company_name",
        "sector",
        "industry_group",
        "industry",
        "exchange",
        "price",
        "market_cap",
        "valuation_score_definition",
        "fundamental_basis",
        "enterprise_value_basis",
        "shares_outstanding",
        "float_percent",
        "dollar_volume_20d",
        "vratio",
        "core_quant_score",
        "valuation_percentile",
        "quality_percentile",
        "momentum_percentile",
        "low_vol_percentile",
        "trailing_pe",
        "forward_pe",
        "pb_ratio",
        "ps_ratio",
        "p_cf",
        "ev_ebit",
        "ev_ebitda",
        "roe",
        "revenue_growth_yoy",
        "eps_growth_yoy",
        "interest_coverage",
        "return_6m",
        "prox52",
        "beta_252",
        "beta_effective",
        "beta_effective_source",
        "beta_252_unavailable_reason",
        "realized_vol_63d",
        "atr_pct_price",
        "adx_14",
        "macd_histogram",
        "bollinger_pct_b",
        "amihud_percentile",
    ]
    keep = [c for c in cols if c in panel.columns]
    return panel[keep].head(n).copy()


def heatmap_view(panel: pd.DataFrame, metric: str = "core_quant_score") -> list[dict[str, Any]]:
    if panel.empty or metric not in panel.columns:
        return []
    grouped = (
        panel.groupby("sector", dropna=False)
        .agg(value=(metric, "mean"), count=("ticker", "count"), median_market_cap=("market_cap", "median"), total_market_cap=("market_cap", "sum"))
        .reset_index()
        .sort_values("value", ascending=False)
    )
    return records(grouped.rename(columns={"sector": "col", "total_market_cap": "size"}).assign(row="Sector", metric=metric))


def quick_look(panel: pd.DataFrame, ticker: str | None = None, price_history_days: int = 2520) -> dict[str, Any]:
    if panel.empty:
        return {}
    symbol = ticker.upper() if ticker else str(panel.iloc[0]["ticker"])
    row = panel[panel["ticker"].eq(symbol)]
    if row.empty:
        raise ValueError(f"Focus ticker {symbol} is outside the selected universe")
    r = row.iloc[0].to_dict()
    prices = close_matrix([symbol], lookback_days=price_history_days)
    chart_series = []
    if not prices.empty and symbol in prices.columns:
        chart_series = [{"date": d.strftime("%Y-%m-%d"), "close": float(v)} for d, v in prices[symbol].dropna().items()]
    windows = {"1M": 21, "3M": 63, "1Y": 252, "3Y": 756, "10Y": 2520}
    chart_windows = {label: chart_series[-n:] for label, n in windows.items() if chart_series}
    return clean_json(
        {
            "ticker": r.get("ticker"),
            "sector": r.get("sector"),
            "score": r.get("core_quant_score"),
            "valuation": r.get("valuation_percentile"),
            "quality": r.get("quality_percentile"),
            "momentum": r.get("momentum_percentile"),
            "low_vol": r.get("low_vol_percentile"),
            "price": r.get("price"),
            "market_cap": r.get("market_cap"),
            "thesis": _thesis_line(r),
            "chart_full": chart_series,
            "chart_windows": chart_windows,
        }
    )


def _thesis_line(row: dict[str, Any]) -> str:
    parts = []
    for key, label in [
        ("valuation_percentile", "valuation"),
        ("quality_percentile", "quality"),
        ("momentum_percentile", "momentum"),
        ("low_vol_percentile", "low-vol"),
    ]:
        v = number_like(row.get(key))
        if v is not None and v >= 70:
            parts.append(f"strong {label}")
        elif v is not None and v <= 30:
            parts.append(f"weak {label}")
    return ", ".join(parts[:3]) or "balanced cross-sectional profile"

