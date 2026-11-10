"""Screener V2 fundamentals computations."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from .data_loader import (
    AS_OF,
    MASTER_FUNDAMENTALS,
    close_matrix,
    eligible_reports,
    load_fundamentals,
    ohlcv_for_symbols,
)
from .stats import _pick, _safe_div, rank_pct

# Yahoo suffix to venue. Bare US tickers stay Unknown: NYSE versus Nasdaq is not in the local data.
_VENUES = {"NS": "NSE", "BO": "BSE", "KS": "KRX", "AX": "ASX", "SR": "Tadawul", "TW": "TWSE", "TA": "TASE", "JK": "IDX", "T": "TSE",
           "HK": "HKEX", "DE": "XETRA", "TO": "TSX", "BK": "SET", "L": "LSE", "SI": "SGX", "ST": "Nasdaq Stockholm", "SA": "B3",
           "NZ": "NZX", "PA": "Euronext Paris", "HE": "Nasdaq Helsinki", "KL": "Bursa Malaysia", "MI": "Borsa Italiana", "SS": "SSE",
           "MX": "BMV", "SW": "SIX", "SZ": "SZSE", "JO": "JSE"}


def _venue(ticker: str) -> str:
    return _VENUES.get(ticker.rsplit("_", 1)[1], "") if "_" in ticker else ""


@lru_cache(maxsize=1)
def _company_names() -> dict[str, str]:
    # shortcut: SEC and NSE lists only (44% of symbols), add a global source for other markets.
    path = MASTER_FUNDAMENTALS.parent / "company_names.parquet"
    if not path.exists():
        return {}
    names = pd.read_parquet(path, columns=["ticker", "company_name"])
    return dict(zip(names.ticker, names.company_name, strict=True))


def statement_snapshots(symbols):
    """One stock/flow-consistent row per report date; four complete quarters for flows."""
    from .performance import _PIT_MEMO
    memo = _PIT_MEMO.get()
    if memo is None:
        return _statement_snapshots(symbols)
    # Date-independent: callers apply the 90-day lag afterwards through eligible_reports.
    key = ("statements", tuple(symbols))
    if key not in memo:
        memo[key] = _statement_snapshots(symbols)
    return memo[key]


def _statement_snapshots(symbols):
    source = load_fundamentals()
    frame = source[source.ticker.isin(symbols)]
    if frame.empty or "periodType" not in frame:
        return frame
    flow_fields = ["Total Revenue", "Gross Profit", "EBIT", "Operating Income", "EBITDA", "Net Income", "Operating Cash Flow", "Free Cash Flow", "Interest Expense", "Interest Expense Non Operating", "Cash Dividends Paid", "Common Stock Dividend Paid", "Repurchase Of Capital Stock", "Issuance Of Capital Stock", "Tax Provision", "Pretax Income"]
    fields = [field for field in flow_fields if field in frame]
    flows = ["ticker", "reportDate", *fields]  # only flow columns are read from these two; base keeps all 364
    annual = frame.loc[frame.periodType.eq("annual"), flows].sort_values(["ticker", "reportDate"]).drop_duplicates(["ticker", "reportDate"], keep="last").set_index(["ticker", "reportDate"])
    quarters = frame.loc[frame.periodType.eq("quarterly"), flows].sort_values(["ticker", "reportDate"]).drop_duplicates(["ticker", "reportDate"], keep="last")
    base = frame.sort_values(["ticker", "reportDate", "periodType"]).drop_duplicates(["ticker", "reportDate"], keep="last").set_index(["ticker", "reportDate"])
    if not quarters.empty:
        rolling = quarters.groupby("ticker")[fields].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True).reindex(quarters.index)
        gaps = quarters.groupby("ticker").reportDate.diff().dt.days
        contiguous = gaps.between(70, 110).groupby(quarters.ticker).rolling(3, min_periods=3).sum().reset_index(level=0, drop=True).reindex(quarters.index).eq(3)
        rolling = rolling.where(contiguous, axis=0)
        rolling.index = pd.MultiIndex.from_frame(quarters[["ticker", "reportDate"]])
    else:
        rolling = pd.DataFrame(index=base.index, columns=fields, dtype=float)
    for field in fields:
        base[field] = rolling[field].reindex(base.index).fillna(annual[field].reindex(base.index))
    return base.reset_index()


def enterprise_claims(frame):
    """Debt must be observed; the vendor omits preferred and minority rows when a company has none."""
    debt = pd.to_numeric(_pick(frame, ["Total Debt"]), errors="coerce")
    preferred = pd.to_numeric(_pick(frame, ["Preferred Stock Equity", "Preferred Stock"]), errors="coerce")
    minority = pd.to_numeric(_pick(frame, ["Minority Interest"]), errors="coerce")
    gross = pd.to_numeric(_pick(frame, ["Total Equity Gross Minority Interest"]), errors="coerce")
    equity = pd.to_numeric(_pick(frame, ["Stockholders Equity"]), errors="coerce")
    minority = minority.fillna(gross - equity)
    return debt + preferred.fillna(0) + minority.fillna(0)


def latest_fundamental_features(symbols: list[str], as_of_date: Any | None = None) -> pd.DataFrame:
    cutoff = pd.Timestamp(as_of_date) if as_of_date else AS_OF.get()
    if cutoff is None:
        market = ohlcv_for_symbols(symbols, 1)  # only the latest date is read
        cutoff = market.Date.max() if not market.empty else pd.Timestamp.today().normalize()
    eligible = eligible_reports(statement_snapshots(symbols), cutoff)
    base = eligible.sort_values(["ticker", "reportDate"]).groupby("ticker").tail(1).set_index("ticker", drop=False) if not eligible.empty else eligible
    # Vendor .info ratios are current snapshots repeated across historical rows.
    # Only statement-derived fields can be used as point-in-time measurements.
    snapshot_fields = ["marketCap", "trailingPE", "forwardPE", "priceToBook", "dividendYield", "debtToEquity", "returnOnEquity", "grossMargins", "currentRatio"]
    for field in snapshot_fields:
        if field in base:
            base[field] = np.nan
    if base.empty:
        base = pd.DataFrame(index=pd.Index([], name="ticker"))
    df = base.reindex(symbols)
    df["ticker"] = df.index
    out = pd.DataFrame(index=df.index)
    out["ticker"] = df["ticker"]
    out["company_name"] = out["ticker"].map(_company_names()).fillna("Unknown")
    out["exchange"] = _pick(df, ["exchange", "fullExchangeName"], "").fillna("").astype(str)
    out["exchange"] = out["exchange"].where(out["exchange"] != "", out["ticker"].astype(str).map(_venue)).replace("", "Unknown")
    out["sector"] = _pick(df, ["sector"], "Unknown").fillna("Unknown").astype(str)
    out["industry"] = _pick(df, ["industry"], "Unknown").fillna("Unknown").astype(str)
    out["market_cap"] = pd.to_numeric(_pick(df, ["marketCap", "market_cap", "Market Cap"]), errors="coerce")
    out["enterprise_value"] = pd.to_numeric(_pick(df, ["enterpriseValue", "enterprise_value"]), errors="coerce")
    out["trailing_pe"] = pd.to_numeric(_pick(df, ["trailingPE", "pe_ratio"]), errors="coerce")
    out["forward_pe"] = pd.to_numeric(_pick(df, ["forwardPE"]), errors="coerce")
    out["pb_ratio"] = pd.to_numeric(_pick(df, ["priceToBook", "price_to_book"]), errors="coerce")
    out["ps_ratio"] = pd.to_numeric(_pick(df, ["priceToSalesTrailing12Months", "price_to_sales"]), errors="coerce")
    out["ev_ebitda"] = pd.to_numeric(_pick(df, ["enterpriseToEbitda", "ev_ebitda"]), errors="coerce")
    out["ev_revenue"] = pd.to_numeric(_pick(df, ["enterpriseToRevenue", "ev_revenue"]), errors="coerce")
    out["dividend_yield"] = pd.to_numeric(_pick(df, ["dividendYield"]), errors="coerce")
    out["gross_margin"] = pd.to_numeric(_pick(df, ["grossMargins", "Gross Profit Margin"]), errors="coerce")
    out["operating_margin"] = pd.to_numeric(_pick(df, ["operatingMargins"]), errors="coerce")
    out["net_margin"] = pd.to_numeric(_pick(df, ["profitMargins"]), errors="coerce")
    out["roe"] = pd.to_numeric(_pick(df, ["returnOnEquity"]), errors="coerce")
    out["roa"] = pd.to_numeric(_pick(df, ["returnOnAssets"]), errors="coerce")
    out["debt_equity"] = pd.to_numeric(_pick(df, ["debtToEquity"]), errors="coerce")
    out["current_ratio"] = pd.to_numeric(_pick(df, ["currentRatio"]), errors="coerce")
    out["quick_ratio"] = pd.to_numeric(_pick(df, ["quickRatio"]), errors="coerce")
    out["shares_outstanding"] = pd.to_numeric(_pick(df, ["sharesOutstanding"]), errors="coerce")
    out["float_percent"] = np.nan  # No point-in-time float dataset.
    revenue = pd.to_numeric(_pick(df, ["Total Revenue", "totalRevenue", "revenue"]), errors="coerce")
    gross_profit = pd.to_numeric(_pick(df, ["Gross Profit", "grossProfit"]), errors="coerce")
    ebit = pd.to_numeric(_pick(df, ["EBIT", "Operating Income", "operatingIncome"]), errors="coerce")
    ebitda = pd.to_numeric(_pick(df, ["EBITDA"]), errors="coerce")
    net_income = pd.to_numeric(_pick(df, ["Net Income", "netIncomeToCommon"]), errors="coerce")
    assets = pd.to_numeric(_pick(df, ["Total Assets", "totalAssets"]), errors="coerce")
    liabilities = pd.to_numeric(_pick(df, ["Total Liabilities Net Minority Interest", "totalLiabilitiesNetMinorityInterest"]), errors="coerce")
    current_assets = pd.to_numeric(_pick(df, ["Current Assets", "totalCurrentAssets"]), errors="coerce")
    current_liabilities = pd.to_numeric(_pick(df, ["Current Liabilities", "totalCurrentLiabilities"]), errors="coerce")
    cash = pd.to_numeric(_pick(df, ["Cash And Cash Equivalents", "totalCash"]), errors="coerce")
    total_debt = pd.to_numeric(_pick(df, ["Total Debt", "totalDebt"]), errors="coerce")
    retained_earnings = pd.to_numeric(_pick(df, ["Retained Earnings"]), errors="coerce")
    operating_cf = pd.to_numeric(_pick(df, ["Operating Cash Flow", "operatingCashflow"]), errors="coerce")
    free_cf = pd.to_numeric(_pick(df, ["Free Cash Flow", "freeCashflow"]), errors="coerce")
    interest_expense = pd.to_numeric(_pick(df, ["Interest Expense", "Interest Expense Non Operating"]), errors="coerce").abs()
    inventory = pd.to_numeric(_pick(df, ["Inventory"]), errors="coerce")
    dividends_paid = pd.to_numeric(_pick(df, ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividend Paid Cfo"]), errors="coerce").abs()
    repurchase = pd.to_numeric(_pick(df, ["Repurchase Of Capital Stock"]), errors="coerce").abs()
    avg_shares = pd.to_numeric(_pick(df, ["Diluted Average Shares", "Basic Average Shares", "Ordinary Shares Number"]), errors="coerce")
    equity_book = pd.to_numeric(_pick(df, ["Stockholders Equity", "Common Stock Equity"]), errors="coerce")
    shares = pd.to_numeric(_pick(df, ["Ordinary Shares Number"]), errors="coerce")
    prices_at_date = close_matrix(symbols, 1)
    # Each name's own last observed close: a ragged final row (other names trading a later day) must not blank its price.
    last_prices = prices_at_date.apply(lambda c: c.dropna().iloc[-1] if c.notna().any() else np.nan).reindex(out.index) if not prices_at_date.empty else pd.Series(np.nan, index=out.index)
    price_dates = prices_at_date.apply(lambda c: c.last_valid_index()).reindex(out.index) if not prices_at_date.empty else pd.Series(pd.NaT, index=out.index)
    # Recent Indian quarterlies omit the period-end count; the diluted average is the closest reported figure.
    shares = shares.fillna(avg_shares)
    out["shares_outstanding"] = shares
    from .currency import instrument_specs, usd_rates
    specs = instrument_specs(symbols)
    obs_dates = price_dates.dropna().unique().tolist() or [cutoff]
    rates = usd_rates([spec.get(key) for spec in specs.values() for key in ['quote_currency', 'financial_currency']], obs_dates)
    def rate_for(symbol, key):
        currency, day = specs[symbol].get(key), price_dates.get(symbol)
        return rates[currency].get(pd.Timestamp(day), np.nan) if currency in rates and pd.notna(day) else np.nan
    quote_fx = pd.Series({symbol: rate_for(symbol, 'quote_currency') for symbol in symbols})
    financial_fx = pd.Series({symbol: rate_for(symbol, 'financial_currency') for symbol in symbols})
    quote_units = pd.Series({symbol: specs[symbol].get('quoted_units_per_ordinary_share') for symbol in symbols}, dtype=float)
    cap_usd = last_prices * shares * quote_units * quote_fx
    out['market_cap_observation_date'] = price_dates.where(last_prices.notna())
    out['market_cap_basis'] = 'observed quote times lagged statement ordinary shares times declared quote-unit multiplier, converted using observed FX; not a current vendor capitalization snapshot'
    out['market_cap'] = cap_usd / financial_fx
    out['market_cap_statement_currency'] = out['market_cap']
    out['financial_currency'] = [specs[symbol].get('financial_currency') for symbol in out.index]
    out['quote_currency'] = [specs[symbol].get('quote_currency') for symbol in out.index]
    out['currency_units_unavailable_reason'] = np.where(out.market_cap.notna(), None, 'missing reported ordinary shares, verified financial/quote currency, quote share units, or exact-date FX')
    out["enterprise_value"] = out["market_cap"] + enterprise_claims(df) - cash
    out["enterprise_value_basis"] = "observed market cap + debt + preferred equity + noncontrolling interests - cash; missing debt remains unknown, unreported preferred and noncontrolling claims count as zero"
    out["trailing_pe"] = _safe_div(out["market_cap"], net_income.where(net_income > 0))
    out["pb_ratio"] = _safe_div(out["market_cap"], equity_book.where(equity_book > 0))
    out["ps_ratio"] = _safe_div(out["market_cap"], revenue.where(revenue > 0))
    out["ev_ebitda"] = _safe_div(out["enterprise_value"], ebitda.where(ebitda > 0))
    out["ev_revenue"] = _safe_div(out["enterprise_value"], revenue.where(revenue > 0))
    out["roe"] = _safe_div(net_income, equity_book)
    out["roa"] = _safe_div(net_income, assets)
    out["current_ratio"] = _safe_div(current_assets, current_liabilities)
    out["debt_equity"] = _safe_div(total_debt, equity_book)
    out["dividend_yield"] = _safe_div(dividends_paid, out["market_cap"])
    out["gross_margin"] = _safe_div(gross_profit, revenue)
    out["operating_margin"] = _safe_div(ebit, revenue)
    out["net_margin"] = _safe_div(net_income, revenue)
    out["total_equity"] = equity_book
    out["gross_margin_calc"] = _safe_div(gross_profit, revenue)
    out["current_assets"] = current_assets
    out["current_liabilities"] = current_liabilities
    out["cash"] = cash
    out["ebit"] = ebit
    out["net_ppe"] = pd.to_numeric(_pick(df, ["Net PPE"]), errors="coerce")
    out["total_liabilities"] = liabilities
    out["ebitda_margin"] = _safe_div(ebitda, revenue)
    out["operating_margin_calc"] = _safe_div(ebit, revenue)
    out["net_margin_calc"] = _safe_div(net_income, revenue)
    out["roa_calc"] = _safe_div(net_income, assets)
    tax_rate = _safe_div(_pick(df, ["Tax Provision"]), _pick(df, ["Pretax Income"])).clip(lower=0, upper=0.5)
    invested_capital = out.get("total_equity", pd.Series(np.nan, index=out.index))
    if invested_capital.isna().all():
        invested_capital = assets - liabilities
    invested_capital = invested_capital + total_debt - cash
    out["roic"] = _safe_div(ebit * (1.0 - tax_rate), invested_capital)
    out["asset_turnover"] = _safe_div(revenue, assets)
    out["gpa"] = _safe_div(gross_profit, assets)
    out["debt_assets"] = _safe_div(total_debt, assets)
    out["working_capital_assets"] = _safe_div(current_assets - current_liabilities, assets)
    out["retained_earnings_assets"] = _safe_div(retained_earnings, assets)
    out["ebit_assets"] = _safe_div(ebit, assets)
    out["sales_assets"] = _safe_div(revenue, assets)
    out["book_value_liabilities"] = _safe_div(equity_book, liabilities)
    out["market_value_liabilities"] = _safe_div(out["market_cap"], liabilities)
    out["ocf_net_income"] = _safe_div(operating_cf, net_income)
    out["fcf_yield"] = _safe_div(free_cf, out["market_cap"])
    out["p_cf"] = _safe_div(out["market_cap"], operating_cf.where(operating_cf > 0))
    out["cash_debt"] = _safe_div(cash, total_debt)
    out["ev_ebit"] = _safe_div(out["enterprise_value"], ebit)
    out["interest_coverage"] = _safe_div(ebit, interest_expense)
    out["debt_ebitda"] = _safe_div(total_debt, ebitda)
    out["payout_ratio"] = _safe_div(dividends_paid, net_income.where(net_income > 0))
    issuance = pd.to_numeric(_pick(df, ["Issuance Of Capital Stock"]), errors="coerce")
    out["net_payout_yield"] = _safe_div(dividends_paid + repurchase - issuance, out["market_cap"])
    out["accruals_assets"] = _safe_div(net_income - operating_cf, assets)
    out["inventory_assets"] = _safe_div(inventory, assets)
    out["shares_from_statements"] = avg_shares
    out["earnings_yield"] = _safe_div(ebit, out["enterprise_value"].where(out["enterprise_value"] > 0))
    out["net_income_yield"] = _safe_div(net_income, out["market_cap"])
    out["quick_ratio"] = _safe_div(current_assets - inventory, current_liabilities)
    out["fundamental_basis"] = "four complete consecutive quarters or matching fiscal annual report; 90-day availability lag"
    growth = _fundamental_growth_metrics(symbols, as_of_date)
    if not growth.empty:
        out = out.join(growth.reindex(out.index), how="left")
    out["valuation_score_definition"] = "35% net-income yield + 25% free-cash-flow yield + 20% inverse P/B + 20% inverse P/S cross-sectional percentiles; all inputs required"
    out["valuation_percentile"] = (
        rank_pct(out["net_income_yield"]) * 0.35
        + rank_pct(out["fcf_yield"]) * 0.25
        + rank_pct(out["pb_ratio"], higher_better=False) * 0.2
        + rank_pct(out["ps_ratio"], higher_better=False) * 0.2
    )
    out["quality_percentile"] = (
        rank_pct(out["roe"]) * 0.3
        + rank_pct(out["gpa"]) * 0.25
        + rank_pct(out["debt_assets"], higher_better=False) * 0.2
        + rank_pct(out["ocf_net_income"]) * 0.15
        + rank_pct(out["gross_margin"].fillna(out["gross_margin_calc"])) * 0.1
    )
    out['market_cap'] = cap_usd
    out['enterprise_value'] = out['enterprise_value'] * financial_fx
    out['market_value_currency'] = 'USD'
    return out.reset_index(drop=True).replace([np.inf, -np.inf], np.nan)


def _fundamental_growth_metrics(symbols: list[str], as_of_date: Any | None = None) -> pd.DataFrame:
    """Annual revenue/EPS growth for every symbol in one grouped pass over the annual reports."""
    source = load_fundamentals()
    hist = source[source.ticker.isin(symbols)]
    if "periodType" in hist:
        hist = hist[hist.periodType == "annual"]
    for cutoff in [AS_OF.get(), pd.to_datetime(as_of_date, errors="coerce") if as_of_date else None]:
        if cutoff is not None and pd.notna(cutoff) and not hist.empty and "reportDate" in hist:
            hist = hist[pd.to_datetime(hist.reportDate) + pd.Timedelta(days=90) <= cutoff]
    hist = hist.sort_values(["ticker", "reportDate"], kind="stable")
    group = hist.groupby("ticker", sort=False)
    revenue = pd.to_numeric(_pick(hist, ["Total Revenue", "totalRevenue", "revenue"]), errors="coerce")
    eps = pd.to_numeric(_pick(hist, ["Diluted EPS", "Basic EPS"]), errors="coerce")
    gap = pd.to_datetime(hist.reportDate).groupby(hist.ticker, sort=False).diff().dt.days
    annual_gap = gap.between(320, 410)
    lag = lambda series, n: series.groupby(hist.ticker, sort=False).shift(n)
    last = ~hist.ticker.duplicated(keep="last")
    count = group.ticker.transform("size")
    one_year = (count >= 2) & annual_gap
    three_year = (count >= 4) & annual_gap & lag(annual_gap, 1).eq(True) & lag(annual_gap, 2).eq(True)
    prior_revenue, prior_eps, start = lag(revenue, 1), lag(eps, 1), lag(revenue, 3)
    columns = {
        "revenue_growth_yoy": (one_year & (prior_revenue > 0) & revenue.notna(), revenue / prior_revenue - 1),
        "eps_growth_yoy": (one_year & eps.notna() & prior_eps.notna() & prior_eps.ne(0), (eps - prior_eps) / prior_eps.abs()),
        "revenue_growth_3y_cagr": (three_year, ((revenue / start) ** (1 / 3) - 1).where((start > 0) & (revenue > 0))),
    }
    order = pd.Index(symbols, dtype=object).map(str)
    out = pd.DataFrame(index=order)
    out.index.name = "ticker"
    first_seen = {}
    for name, (mask, value) in columns.items():
        keep = (mask & last).to_numpy()
        if keep.any():
            values = pd.Series(value.to_numpy()[keep], index=hist.ticker.to_numpy()[keep])
            out[name] = values.reindex(order).to_numpy(dtype=float)
            first_seen[name] = int(order.get_indexer(values.index).min())
    # Same column order the old row-dict frame produced: first symbol that set each key.
    names = list(columns)
    return out[sorted(first_seen, key=lambda n: (first_seen[n], names.index(n)))]
