"""Screener V2 screener computations."""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from .common import clean_json, number_like, records
from .data_loader import close_matrix

DEFAULT_TOP_N = 50

# Ready-made screens: plain filter payloads that any filter the caller sets overrides.
SCREEN_TEMPLATES: dict[str, dict[str, Any]] = {
    "quality_compounders": {"roe_min": 0.15, "net_margin_min": 0.10, "debt_equity_max": 1.0, "piotroski_min": 6},
    "deep_value": {"pe_max": 12, "pb_max": 1.5, "exclude_negative_pe": True},
    "momentum_leaders": {"momentum_percentile_min": 80, "high_proximity_min": -0.10, "dist_sma_200_min": 0},
    "growth_at_a_reasonable_price": {"pe_max": 25, "eps_growth_yoy_min": 0.15, "revenue_growth_yoy_min": 0.10, "roe_min": 0.12},
    "dividend_income": {"dividend_yield_min": 0.03, "payout_ratio_max": 0.7, "debt_equity_max": 1.5, "dividend_paying_only": True},
    "low_volatility": {"realized_vol_max": 0.25, "beta_max": 0.9, "drawdown_min": -0.25},
    "safe_balance_sheet": {"altman_min": 3, "current_ratio_min": 1.5, "interest_coverage_min": 5, "debt_ebitda_max": 3},
    "oversold_quality": {"rsi_max": 30, "roe_min": 0.10, "quality_percentile_min": 60},
    "high_roic_high_earnings_yield": {"roic_min": 0.15, "earnings_yield_min": 0.08},
    "cheap_high_fscore": {"pb_max": 1.5, "piotroski_min": 7},
    "below_book_liquid": {"pb_max": 0.7, "current_ratio_min": 2},
    "shareholder_yield": {"dividend_yield_min": 0.02, "fcf_yield_min": 0.05, "payout_ratio_max": 0.8},
    "fcf_machines": {"fcf_yield_min": 0.06, "operating_margin_min": 0.15, "debt_ebitda_max": 3},
    "high_roic_growth": {"roic_min": 0.15, "revenue_growth_yoy_min": 0.10, "revenue_growth_3y_cagr_min": 0.10},
    "profitable_small_caps": {"market_cap_min": 300_000_000, "market_cap_max": 2_000_000_000, "roe_min": 0.12, "net_margin_min": 0.05},
    "large_cap_value": {"market_cap_min": 10_000_000_000, "pe_max": 15, "pb_max": 2.5, "exclude_negative_pe": True},
    "mega_cap_quality": {"market_cap_min": 200_000_000_000, "roe_min": 0.15},
    "low_pe_growth": {"pe_max": 20, "eps_growth_yoy_min": 0.20},
    "earnings_turnaround": {"eps_growth_yoy_min": 0.5, "qtr_profit_yoy_min": 0.25},
    "sales_acceleration": {"qtr_sales_yoy_min": 0.20, "revenue_growth_yoy_min": 0.15},
    "quiet_compounders": {"realized_vol_max": 0.30, "roe_min": 0.12, "revenue_growth_yoy_min": 0.05, "drawdown_min": -0.30},
    "cheap_and_improving": {"pe_max": 15, "piotroski_min": 7},
    "defensive_dividend_growers": {"dividend_yield_min": 0.02, "beta_max": 0.8, "debt_equity_max": 1.0},
    "beaten_down_quality": {"high_proximity_max": -0.35, "roe_min": 0.12, "piotroski_min": 6},
    "liquid_large": {"dollar_volume_min": 100_000_000},
    "breakout_52w": {"prox52_min": 0.97, "vratio_min": 1.5},
    "uptrend_above_averages": {"dist_sma_50_min": 0, "dist_sma_200_min": 0, "high_proximity_min": -0.25, "momentum_percentile_min": 70, "sma_bullish_only": True},
    "golden_cross_recent": {"golden_cross_within_n_days": 10},
    "volume_surge": {"vratio_min": 3, "dollar_volume_min": 5_000_000},
}
# Rule-of-thumb technical screens with little published evidence; the page says so.
WEAK_EVIDENCE = {"breakout_52w", "uptrend_above_averages", "golden_cross_recent", "volume_surge", "oversold_quality"}


def template_formula(filters: dict[str, Any]) -> str:
    """A template named by what it does: `pe <= 12 and pb <= 1.5`."""
    parts = []
    for key, value in filters.items():
        if value is True:
            parts.append(key)
        elif key.endswith(("_min", "_max")):
            parts.append(f"{key[:-4]} {'>=' if key.endswith('_min') else '<='} {value}")
        else:
            parts.append(f"{key} = {value}")
    return " and ".join(parts)


# Yahoo ticker suffix to country; a bare ticker is a US listing.
COUNTRIES = {"": "United States", "NS": "India", "BO": "India", "KS": "South Korea", "AX": "Australia", "SR": "Saudi Arabia", "TW": "Taiwan", "TA": "Israel", "JK": "Indonesia",
             "T": "Japan", "HK": "Hong Kong", "DE": "Germany", "TO": "Canada", "BK": "Thailand", "L": "United Kingdom", "SI": "Singapore", "ST": "Sweden", "SA": "Brazil",
             "NZ": "New Zealand", "PA": "France", "HE": "Finland", "KL": "Malaysia", "MI": "Italy", "SS": "China", "MX": "Mexico", "SW": "Switzerland", "SZ": "China", "JO": "South Africa"}


def country_of(ticker: str) -> str:
    return COUNTRIES.get(ticker.rsplit("_", 1)[1] if "_" in ticker else "", "Unknown")


# Metrics a name needs for its row to be trusted; the share known is its data coverage.
TRUST_METRICS = ["market_cap", "trailing_pe", "pb_ratio", "roe", "net_margin", "revenue_growth_yoy", "debt_equity", "momentum_jt", "realized_vol_252d", "piotroski_passed", "altman_z_score", "return_1m"]


def data_coverage(panel: pd.DataFrame) -> pd.Series:
    known = [panel[c].notna() for c in TRUST_METRICS if c in panel]
    return (sum(known) / len(TRUST_METRICS) * 100).round(1) if known else pd.Series(np.nan, index=panel.index)


def quarterly_variance(symbols: list[str], cutoff: Any) -> pd.DataFrame:
    """Latest reported quarter against the same quarter a year earlier, for sales and net income."""
    from .data_loader import eligible_reports, load_fundamentals
    frame = load_fundamentals()
    cols = ["Total Revenue", "Net Income"]
    if "periodType" not in frame or any(c not in frame for c in cols):
        return pd.DataFrame(columns=["ticker", "qtr_sales_yoy", "qtr_profit_yoy", "quarter_end"])
    q = frame[frame.ticker.isin(symbols) & frame.periodType.eq("quarterly")][["ticker", "reportDate", *cols]]
    q = eligible_reports(q, cutoff).sort_values("reportDate").drop_duplicates(["ticker", "reportDate"], keep="last")
    if q.empty:
        return pd.DataFrame(columns=["ticker", "qtr_sales_yoy", "qtr_profit_yoy", "quarter_end"])
    cur = q.groupby("ticker").tail(1).assign(prior=lambda d: d.reportDate - pd.Timedelta(days=365)).sort_values("prior")
    merged = pd.merge_asof(cur, q.rename(columns={"reportDate": "prior_date"}), left_on="prior", right_on="prior_date", by="ticker", direction="nearest", tolerance=pd.Timedelta(days=20), suffixes=("", "_prior"))
    for col, name in [("Total Revenue", "qtr_sales_yoy"), ("Net Income", "qtr_profit_yoy")]:
        merged[name] = ((merged[col] - merged[f"{col}_prior"]) / merged[f"{col}_prior"].abs()).replace([np.inf, -np.inf], np.nan)
    merged["quarter_end"] = merged.reportDate.dt.strftime("%Y-%m-%d")
    return merged[["ticker", "qtr_sales_yoy", "qtr_profit_yoy", "quarter_end"]]


# Every numeric range filter: panel column, lower payload key, upper payload key, label. Screening and explaining both read this.
RANGE_FILTERS: list[tuple[str, str, str, str]] = [
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
    ("max_drawdown_252d", "drawdown_min", "drawdown_max", "Max drawdown"),
    ("piotroski_passed", "piotroski_min", "piotroski_max", "Piotroski checks passed"),
    ("piotroski_available_criteria", "piotroski_known_min", "piotroski_known_max", "Piotroski checks known"),
    ("altman_z_score", "altman_min", "altman_max", "Altman Z"),
    ("ps_ratio", "ps_min", "ps_max", "P/S"),
    ("ev_ebitda", "ev_ebitda_min", "ev_ebitda_max", "EV/EBITDA"),
    ("earnings_yield", "earnings_yield_min", "earnings_yield_max", "Earnings yield"),
    ("fcf_yield", "fcf_yield_min", "fcf_yield_max", "FCF yield"),
    ("gpa", "gpa_min", "gpa_max", "GP/A"),
    ("gross_margin", "gross_margin_min", "gross_margin_max", "Gross margin"),
    ("operating_margin", "operating_margin_min", "operating_margin_max", "Operating margin"),
    ("net_margin", "net_margin_min", "net_margin_max", "Net margin"),
    ("roa", "roa_min", "roa_max", "ROA"),
    ("current_ratio", "current_ratio_min", "current_ratio_max", "Current ratio"),
    ("dividend_yield", "dividend_yield_min", "dividend_yield_max", "Dividend yield"),
    ("return_1d", "return_1d_min", "return_1d_max", "1D return"),
    ("return_1m", "return_1m_min", "return_1m_max", "1M return"),
    ("return_3m", "return_3m_min", "return_3m_max", "3M return"),
    ("return_6m", "return_6m_min", "return_6m_max", "6M return"),
    ("return_12m", "return_12m_min", "return_12m_max", "12M return"),
    ("momentum_jt", "momentum_min", "momentum_max", "Momentum 12-1"),
    ("dist_sma_50", "dist_sma_50_min", "dist_sma_50_max", "Distance to SMA 50"),
    ("dist_sma_200", "dist_sma_200_min", "dist_sma_200_max", "Distance to SMA 200"),
    ("rsi_14", "rsi_min", "rsi_max", "RSI"),
    ("macd_histogram", "macd_histogram_min", "macd_histogram_max", "MACD histogram"),
    ("bollinger_pct_b", "bollinger_pct_b_min", "bollinger_pct_b_max", "Bollinger %B"),
    ("obv_20d_slope", "obv_slope_min", "obv_slope_max", "OBV slope"),
    ("realized_vol_252d", "realized_vol_min", "realized_vol_max", "Realised volatility"),
    ("beta_252", "beta_min", "beta_max", "Beta"),
    ("qtr_sales_yoy", "qtr_sales_yoy_min", "qtr_sales_yoy_max", "Quarterly sales YoY"),
    ("qtr_profit_yoy", "qtr_profit_yoy_min", "qtr_profit_yoy_max", "Quarterly profit YoY"),
    ("sector_relative_score", "sector_score_percentile_min", "sector_score_percentile_max", "Sector percentile"),
    ("momentum_percentile", "momentum_percentile_min", "momentum_percentile_max", "Momentum percentile"),
    ("quality_percentile", "quality_percentile_min", "quality_percentile_max", "Quality percentile"),
    ("valuation_percentile", "valuation_percentile_min", "valuation_percentile_max", "Valuation percentile"),
    ("return_1w", "return_1w_min", "return_1w_max", "1W return"),
    ("relative_return_3m_spy", "rel_return_3m_min", "rel_return_3m_max", "3M return vs SPY"),
    ("min_1d_return_252d", "worst_day_min", "worst_day_max", "Worst day, 1Y"),
    ("gap_1d", "gap_min", "gap_max", "Gap %"),
    ("consecutive_up_days", "up_days_min", "up_days_max", "Up days in a row"),
    ("consecutive_down_days", "down_days_min", "down_days_max", "Down days in a row"),
    ("pct_above_52w_low", "above_52w_low_min", "above_52w_low_max", "Above 52W low"),
    ("dist_sma_20", "dist_sma_20_min", "dist_sma_20_max", "Distance to SMA 20"),
    ("dist_sma_100", "dist_sma_100_min", "dist_sma_100_max", "Distance to SMA 100"),
    ("dist_ema_20", "dist_ema_20_min", "dist_ema_20_max", "Distance to EMA 20"),
    ("dist_ema_50", "dist_ema_50_min", "dist_ema_50_max", "Distance to EMA 50"),
    ("dist_ema_200", "dist_ema_200_min", "dist_ema_200_max", "Distance to EMA 200"),
    ("macd_cross_days", "macd_cross_days_min", "macd_cross_days_max", "Days since MACD cross"),
    ("volume_spike_ratio", "relative_volume_min", "relative_volume_max", "Relative volume"),
    ("atr_14", "atr_min", "atr_max", "ATR"),
    ("realized_vol_63d", "realized_vol_3m_min", "realized_vol_3m_max", "Realised volatility 3M"),
    ("low_vol_percentile", "low_vol_percentile_min", "low_vol_percentile_max", "Low-vol percentile"),
    ("liquidity_percentile", "liquidity_percentile_min", "liquidity_percentile_max", "Liquidity percentile"),
    ("size_percentile", "size_percentile_min", "size_percentile_max", "Size percentile"),
    ("pe_sector_percentile", "pe_sector_percentile_min", "pe_sector_percentile_max", "P/E sector percentile"),
    ("industry_relative_score", "industry_score_percentile_min", "industry_score_percentile_max", "Industry percentile"),
    ("enterprise_value", "enterprise_value_min", "enterprise_value_max", "Enterprise value"),
    ("ev_revenue", "ev_sales_min", "ev_sales_max", "EV/Sales"),
    ("ebitda_margin", "ebitda_margin_min", "ebitda_margin_max", "EBITDA margin"),
    ("asset_turnover", "asset_turnover_min", "asset_turnover_max", "Asset turnover"),
    ("quick_ratio", "quick_ratio_min", "quick_ratio_max", "Quick ratio"),
    ("debt_assets", "debt_assets_min", "debt_assets_max", "Debt/assets"),
    ("cash_debt", "cash_debt_min", "cash_debt_max", "Cash/debt"),
    ("accruals_assets", "accruals_min", "accruals_max", "Accruals"),
    ("ocf_net_income", "ocf_net_income_min", "ocf_net_income_max", "Cash flow/net income"),
]


RELATIVE_OPS = {"<": np.less, "<=": np.less_equal, ">": np.greater, ">=": np.greater_equal, "=": np.equal, "!=": np.not_equal}


def _relative_mask(df: pd.DataFrame, universe: pd.DataFrame, node: dict[str, Any], columns: dict[str, str]) -> pd.Series:
    """`{"left": "pe", "op": "<", "right": "pe_sector_median"}` or `{"metric_vs_sector": "pe", "op": "<", "value": 0.8}` (metric over its sector median)."""
    def operand(name: str) -> pd.Series:
        base = name.removesuffix("_sector_median")
        col = columns.get(base)
        if col is None or col not in df:
            raise ValueError(f"Unknown filter field: {name}")
        if base == name:
            return pd.to_numeric(df[col], errors="coerce")
        medians = pd.to_numeric(universe[col], errors="coerce").groupby(universe["sector"]).median()
        return df["sector"].map(medians)
    if node.get("op") not in RELATIVE_OPS:
        raise ValueError(f"Unsupported operator: {node.get('op')}")
    if "metric_vs_sector" in node:
        metric = str(node["metric_vs_sector"])
        bound = number_like(node.get("value"))
        if bound is None:
            raise ValueError("Relative rule on a sector median needs a number value")
        left, right = operand(metric) / operand(f"{metric}_sector_median"), pd.Series(bound, index=df.index)
    else:
        left, right = operand(str(node["left"])), operand(str(node["right"]))
    return RELATIVE_OPS[node["op"]](left, right) & left.notna() & right.notna()


def tree_mask(df: pd.DataFrame, node: dict[str, Any], universe: pd.DataFrame | None = None) -> pd.Series:
    """AND/OR groups of rules (react-querybuilder shape); an unknown value never passes a rule. Sector medians come from `universe`, the whole loaded panel."""
    if "rules" in node:
        masks = [tree_mask(df, r, universe) for r in node["rules"] if not r.get("disabled")]
        if not masks:
            return pd.Series(True, index=df.index)
        out = masks[0]
        for m in masks[1:]:
            out = out & m if str(node.get("combinator", "and")).lower() == "and" else out | m
        return ~out if node.get("not") else out
    columns = {lo[:-4]: col for col, lo, _, _ in RANGE_FILTERS} | {"sector": "sector", "industry": "industry", "industry_group": "industry_group", "exchange": "exchange", "country": "country", "currency": "quote_currency"}
    if "left" in node or "metric_vs_sector" in node:
        return _relative_mask(df, df if universe is None else universe, node, columns)
    field, op, value = node.get("field"), node.get("operator"), node.get("value")
    col = columns.get(field)
    if col == "country" and "country" not in df:
        df = df.assign(country=df["ticker"].map(country_of))
    if col not in df:
        raise ValueError(f"Unknown filter field: {field}")
    items = [str(x).strip() for x in (value if isinstance(value, list) else str(value).split(",")) if str(x).strip()]
    series = df[col]
    if op in {"in", "notIn", "=", "!="} and not pd.api.types.is_numeric_dtype(series):
        hit = series.astype(str).str.lower().isin({i.lower() for i in items})
        return (hit if op in {"in", "="} else ~hit) & series.notna()
    try:
        nums = [float(i) for i in items]
    except ValueError as exc:
        raise ValueError(f"Rule on {field} needs a number") from exc
    numeric = pd.to_numeric(series, errors="coerce")
    if op == "between":
        if len(nums) != 2:
            raise ValueError(f"Rule on {field} needs two numbers")
        return numeric.between(*nums)
    if not nums:
        raise ValueError(f"Rule on {field} has no value")
    compare = {"<": numeric < nums[0], "<=": numeric <= nums[0], ">": numeric > nums[0], ">=": numeric >= nums[0], "=": numeric == nums[0], "!=": numeric.ne(nums[0]) & numeric.notna(), "in": numeric.isin(nums), "notIn": ~numeric.isin(nums) & numeric.notna()}
    if op not in compare:
        raise ValueError(f"Unsupported operator: {op}")
    return compare[op]


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


def effective_payload(payload: dict | None) -> dict[str, Any]:
    """The filters a run really applies: the screen template under the caller's own settings, and the dollar-volume preset."""
    payload = payload or {}
    template = payload.get("screen_template")
    if template and template not in SCREEN_TEMPLATES:
        raise ValueError(f"Unknown screen template: {template}")
    chosen = SCREEN_TEMPLATES.get(template, {})
    # A switch left off in the form is "unset", so a template can turn it on.
    payload = {**chosen, **{k: v for k, v in payload.items() if not (chosen.get(k) is True and v is False)}}
    for name, limits in (payload.get("metric_filters") or {}).items():
        payload.update({f"{name}_{side}": limits[side] for side in ("min", "max") if limits.get(side) is not None})
    preset = str(payload.get("dollar_volume_preset") or "").lower()
    preset_map = {"micro": 250_000, "small": 1_000_000, "institutional": 10_000_000, "large": 25_000_000, "very_liquid": 100_000_000}
    if preset in preset_map and "dollar_volume_min" not in payload:
        payload["dollar_volume_min"] = preset_map[preset]
    return payload


def range_filters(panel: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    """RANGE_FILTERS plus one min/max pair per metric the caller added as a column."""
    return [*RANGE_FILTERS, *((c, f"{c}_min", f"{c}_max", c) for c in panel.attrs.get("metric_columns", []))]


def apply_filters(panel: pd.DataFrame, payload: dict | None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if panel.empty:
        return panel, []
    payload = effective_payload(payload)
    if any(key in payload for key in ("vol_forecast_min", "vol_forecast_max")):
        raise ValueError("HAR forecasts are unavailable; use explicitly named yang_zhang_vol_min/max estimates")
    for key, column in [("industry_group", "industry_group"), ("industry_groups", "industry_group"), ("exchange", "exchange"), ("exchanges", "exchange")]:
        if payload.get(key) and str(payload[key]).lower() not in {"all", "any"} and (column not in panel or panel[column].replace(["", "Unknown", "Unclassified"], np.nan).isna().all()):
            raise ValueError(f"Requested filter {key} is unavailable in the local data")
    stages: list[dict[str, Any]] = [{"stage": "Initial universe", "remaining": len(panel), "removed": 0}]
    filtered = panel.copy()

    def apply(stage: str, mask: pd.Series, key: str | None = None) -> None:
        nonlocal filtered
        before = len(filtered)
        filtered = filtered[mask.reindex(filtered.index).fillna(False)]
        stages.append({"stage": stage, "key": key, "remaining": len(filtered), "removed": int(before - len(filtered))})

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
    for key, label, column in [("country", "Country", filtered["ticker"].map(country_of)), ("currency", "Currency", filtered.get("quote_currency"))]:
        wanted = payload.get(key)
        if wanted and str(wanted).lower() not in {"all", "any"}:
            if column is None or column.isna().all():
                raise ValueError(f"Requested filter {label} is unavailable in the local data")
            allowed = {str(v).strip().lower() for v in (wanted if isinstance(wanted, list) else re.split(r"[,;]", str(wanted))) if str(v).strip()}
            apply(label, column.astype(str).str.lower().isin(allowed), key)
    if payload.get("filter_tree"):
        apply("Filter groups", tree_mask(filtered, payload["filter_tree"], panel), "filter_tree")
    listed = payload.get("ticker_in")
    if listed:
        names = {str(v).strip().upper().replace(".", "_").replace("-", "_") for v in (listed if isinstance(listed, list) else re.split(r"[,;\s]+", str(listed))) if str(v).strip()}
        apply("Watchlist", filtered["ticker"].isin(names), "ticker_in")
    for col, lo_key, hi_key, label in range_filters(panel):
        top_key = lo_key[:-4] + "_top"
        if lo_key not in payload and hi_key not in payload and top_key not in payload:
            continue
        if col not in panel or panel[col].notna().sum() == 0:
            raise ValueError(f"Requested filter {label} is unavailable in the local data")
        for bound in (lo_key, hi_key):
            if bound in payload and number_like(payload[bound]) is None:
                raise ValueError(f"Invalid numeric filter: {bound}")
        mask = _range_filter(filtered, col, payload.get(lo_key), payload.get(hi_key))
        if not mask.all():
            apply(label, mask, lo_key[:-4])
        if top_key in payload:
            n = number_like(payload[top_key])
            if n is None or n != int(n) or n == 0:
                raise ValueError(f"Invalid top N filter: {top_key}")
            # A negative N keeps the lowest names.
            rank = pd.to_numeric(filtered[col], errors="coerce").rank(ascending=n < 0, method="first")
            apply(f"{label} {'bottom' if n < 0 else 'top'} {abs(int(n))}", rank <= abs(n), lo_key[:-4])
    exchanges = payload.get("exchange") or payload.get("exchanges")
    if exchanges and "exchange" in filtered.columns and str(exchanges).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (exchanges if isinstance(exchanges, list) else re.split(r"[,;]", str(exchanges))) if str(s).strip()}
        apply("Exchange", filtered["exchange"].astype(str).str.lower().isin(allowed))
    if payload.get("dividend_paying_only"):
        apply("Dividend payers", pd.to_numeric(filtered.get("dividend_yield", 0), errors="coerce").fillna(0) > 0)
    if payload.get("exclude_negative_pe") and "trailing_pe" in filtered:
        apply("Negative P/E exclusion", pd.to_numeric(filtered["trailing_pe"], errors="coerce") > 0)
    if payload.get("exclude_penny_stocks", True):
        apply("No USD price on this date", pd.to_numeric(filtered["price_usd"], errors="coerce").notna())
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
        "country",
        "data_coverage",
        "statement_age_days",
        "price",
        "market_cap",
        "valuation_score_definition",
        "fundamental_basis",
        "return_1d",
        "return_1m",
        "qtr_sales_yoy",
        "qtr_profit_yoy",
        "max_drawdown_252d",
        "piotroski_passed",
        "piotroski_available_criteria",
        "altman_z_score",
        "enterprise_value_basis",
        "shares_outstanding",
        "float_percent",
        "dollar_volume_20d",
        "vratio",
        "core_quant_score",
        "sector_relative_score",
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
        "rsi_14",
        "adx_14",
        "macd_histogram",
        "bollinger_pct_b",
        "amihud_percentile",
    ]
    keep = [c for c in [*cols, *panel.attrs.get('metric_columns', [])] if c in panel.columns]
    table = panel[keep].head(n).copy()
    # A blank label is an unknown one.
    text = table.select_dtypes("object").columns
    table[text] = table[text].replace("", "Unknown")
    return table


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

