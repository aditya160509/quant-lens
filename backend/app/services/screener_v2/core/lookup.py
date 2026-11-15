"""One-name quick look: price, ratios against sector and own history, scores, Piotroski, Altman, peers, statements, rule-based notes."""
from __future__ import annotations

import itertools
import threading
from typing import Any

import pandas as pd

from .academic import (
    altman_history,
    altman_z_double_prime,
    altman_z_score,
    piotroski_criteria_spec,
)
from .common import clean_json, number_like, records
from .data_loader import (
    MARKET_UNIVERSE,
    MASTER_FUNDAMENTALS,
    as_of_context,
    close_matrix,
    default_as_of,
    fundamental_history,
    normalize_symbol,
)
from .valuation import historical_valuation_series, own_history_percentile_from_series

EXCHANGES = {"": "US", "NS": "NSE", "BO": "BSE", "KS": "KRX", "AX": "ASX", "SR": "Tadawul", "TW": "TWSE", "TA": "TASE", "JK": "IDX", "T": "TSE", "HK": "HKEX", "TO": "TSX",
             "DE": "XETRA", "BK": "SET", "L": "LSE", "SI": "SGX", "ST": "Nasdaq Stockholm", "SA": "B3", "NZ": "NZX", "PA": "Euronext Paris", "HE": "Nasdaq Helsinki",
             "KL": "Bursa Malaysia", "MI": "Borsa Italiana", "SS": "SSE", "MX": "BMV", "SW": "SIX", "SZ": "SZSE", "JO": "JSE"}

# (key, label, group, own-history metric or None)
STATS = [
    ("trailing_pe", "P/E", "Valuation", "trailing_pe"), ("pb_ratio", "P/B", "Valuation", "pb_ratio"), ("ps_ratio", "P/S", "Valuation", "ps_ratio"),
    ("ev_ebitda", "EV/EBITDA", "Valuation", "ev_ebitda"), ("fcf_yield", "FCF yield", "Valuation", "fcf_yield"), ("dividend_yield", "Dividend yield", "Valuation", None),
    ("roe", "ROE", "Quality", None), ("roic", "ROIC", "Quality", None), ("gross_margin", "Gross margin", "Quality", None), ("operating_margin", "Operating margin", "Quality", None),
    ("net_margin", "Net margin", "Quality", None), ("debt_equity", "Debt / equity", "Health", None), ("current_ratio", "Current ratio", "Health", None),
    ("interest_coverage", "Interest coverage", "Health", None), ("revenue_growth_yoy", "Revenue growth", "Growth", None), ("eps_growth_yoy", "EPS growth", "Growth", None),
    ("realized_vol_63d", "Volatility 63d", "Risk", None), ("beta_252", "Beta", "Risk", None), ("pct_from_52w_high", "From 52-week high", "Risk", None),
]
SCORES = [("core_quant_score", "Score"), ("valuation_percentile", "Valuation"), ("quality_percentile", "Quality"), ("momentum_percentile", "Momentum"), ("low_vol_percentile", "Low volatility")]
PIOTROSKI = {"f1_positive_roa": "Positive return on assets", "f2_positive_cfo_assets": "Positive operating cash flow", "f3_roa_improving": "Return on assets rising",
             "f4_cfo_exceeds_roa": "Cash flow exceeds earnings", "f5_leverage_declining": "Leverage falling", "f6_liquidity_improving": "Current ratio rising",
             "f7_no_equity_issuance": "No new shares issued", "f8_margin_improving": "Gross margin rising", "f9_turnover_improving": "Asset turnover rising"}
LINES = [("Total Revenue", "Revenue"), ("Gross Profit", "Gross profit"), ("Operating Income", "Operating income"), ("Net Income", "Net income"), ("Diluted EPS", "Diluted EPS"),
         ("Operating Cash Flow", "Operating cash flow"), ("Free Cash Flow", "Free cash flow"), ("Total Assets", "Total assets"), ("Total Debt", "Total debt"), ("Stockholders Equity", "Equity")]
CHART_DAYS = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260, "10Y": 2520}
PCT = {"dividend_yield", "fcf_yield", "roe", "roic", "gross_margin", "operating_margin", "net_margin", "revenue_growth_yoy", "eps_growth_yoy", "realized_vol_63d", "pct_from_52w_high"}
LIMITS = ["Fundamentals from 2021, statements used 90 days after the period ends", "Today's listed names only: no delisted companies", "Notes are rules on these metrics, not advice"]

_lock = threading.Lock()
_cache: dict[str, Any] = {"key": None, "panel": None}


def _version() -> tuple:
    return tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in (MARKET_UNIVERSE, MASTER_FUNDAMENTALS))


def panel() -> pd.DataFrame:
    """The latest-date panel for the whole universe, rebuilt only when the data files change."""
    from ..features.feature_01 import INPUTS
    from ..features.inputs import normalize_payload
    from .currency import instrument_context
    from .data_loader import parse_symbols
    from .panel import metric_panel

    key = _version()
    with _lock:
        if _cache["key"] != key:
            payload = normalize_payload(INPUTS, {"max_symbols": 5000})
            payload["as_of_date"] = default_as_of(payload)
            with as_of_context(payload["as_of_date"]), instrument_context(payload):
                built = metric_panel(payload, symbols=parse_symbols(payload, default_limit=5000, max_symbols=5000))
            built["exchange"] = built.ticker.map(lambda t: EXCHANGES.get(t.rsplit("_", 1)[1] if "_" in t else "", "Unknown"))
            built.attrs["as_of_date"] = payload["as_of_date"]
            _cache.update(key=key, panel=built)
        return _cache["panel"]


_past: dict[tuple[Any, str], pd.DataFrame] = {}
_past_lock = threading.Lock()  # its own lock: an 8-second past build must not block today's lookups


def past_panel(as_of: str) -> pd.DataFrame:
    """The whole-universe panel as it stood on an earlier date; the last four dates asked for stay cached."""
    from ..features.feature_01 import INPUTS
    from ..features.inputs import normalize_payload
    from .currency import instrument_context
    from .data_loader import parse_symbols
    from .panel import metric_panel

    key = (_version(), as_of)
    with _past_lock:
        if key not in _past:
            payload = normalize_payload(INPUTS, {"max_symbols": 5000})
            payload["as_of_date"] = as_of
            with as_of_context(as_of), instrument_context(payload):
                built = metric_panel(payload, symbols=parse_symbols(payload, default_limit=5000, max_symbols=5000))
            built.attrs["as_of_date"] = as_of
            while len(_past) >= 4:
                _past.pop(next(iter(_past)))
            _past[key] = built
        return _past[key]


def then_and_now(ticker: str, days: int = 365) -> dict[str, Any]:
    """One name today against the same name `days` earlier: every compare metric plus its score rank in the universe."""
    now = panel()
    symbol = normalize_symbol(ticker)
    if symbol not in set(now.ticker):
        raise KeyError(f"{ticker} is not in the universe we hold")
    then_date = (pd.Timestamp(now.attrs["as_of_date"]) - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    old = past_panel(then_date)

    def pick(p: pd.DataFrame) -> dict[str, Any]:
        if symbol not in set(p.ticker):
            return {}
        score = pd.to_numeric(p.get("core_quant_score"), errors="coerce")
        rank = score.rank(ascending=False, method="min")
        i = p.index[p.ticker.eq(symbol)][0]
        return {**{c: number_like(p.at[i, c]) for c in COMPARE_COLUMNS if c in p}, "score_rank": number_like(rank.at[i]), "ranked": int(score.notna().sum())}

    a, b = pick(now), pick(old)
    keys = [*COMPARE_COLUMNS, "score_rank"]
    return clean_json({"ticker": symbol, "now_date": str(now.attrs["as_of_date"]), "then_date": then_date, "ranked": [a.get("ranked"), b.get("ranked")],
                       "rows": [{"key": k, "now": a.get(k), "then": b.get(k)} for k in keys]})


def popular(limit: int = 12) -> dict[str, Any]:
    """Largest names by market cap, plus the exchanges and types we hold, for the search overlay."""
    p = panel()
    top = p[p.market_cap.notna()].nlargest(limit, "market_cap") if p.market_cap.notna().any() else p.nlargest(limit, "dollar_volume_20d")
    facet = lambda col: [{"name": k, "count": int(v)} for k, v in p[col].value_counts().items()]
    return {"results": [_head(r) for r in top.to_dict("records")], "exchanges": facet("exchange"), "types": [{"name": "Stock", "count": len(p)}]}


def _head(r: dict[str, Any]) -> dict[str, Any]:
    return clean_json({"ticker": r["ticker"], "company_name": r.get("company_name") or None, "type": "Stock", "exchange": r.get("exchange"), "sector": r.get("sector") or None})


def _pct_below(series: pd.Series, value: float) -> float | None:
    known = pd.to_numeric(series, errors="coerce").dropna()
    return float((known < value).mean() * 100) if len(known) >= 5 else None


def _stat_rows(p: pd.DataFrame, row: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    sector = p[p.sector.eq(row.get("sector"))] if row.get("sector") else p.iloc[0:0]
    out = []
    for key, label, group, metric in STATS:
        value = number_like(row.get(key))
        own = None
        if value is not None and metric:
            try:
                own = own_history_percentile_from_series([r["valuation_metric"] for r in historical_valuation_series(symbol, metric)])
            except (ValueError, KeyError):
                own = None
        sector_vals = pd.to_numeric(sector[key], errors="coerce").dropna() if key in sector else pd.Series(dtype=float)
        out.append({"key": key, "label": label, "group": group, "unit": "pct" if key in PCT else "x", "value": value,
                    "sector_percentile": _pct_below(sector[key], value) if value is not None and key in sector else None,
                    "sector_median": float(sector_vals.median()) if len(sector_vals) >= 5 else None, "sector_n": len(sector_vals), "own_history_percentile": own})
    return out


def _altman(row: dict[str, Any], symbol: str) -> dict[str, Any]:
    one = pd.DataFrame([row])
    z = number_like(altman_z_score(one).iloc[0])
    zone = None if z is None else "Safe" if z > 2.99 else "Grey" if z >= 1.81 else "Distress"
    try:
        history = altman_history(symbol)
    except (ValueError, KeyError):
        history = []
    return {"z": z, "z_double_prime": number_like(altman_z_double_prime(one).iloc[0]), "zone": zone, "history": clean_json(history)}


def _piotroski(p: pd.DataFrame, symbol: str) -> dict[str, Any]:
    r = piotroski_criteria_spec(p, [symbol]).iloc[0].to_dict()
    checks = [{"key": k, "label": label, "passed": None if r[k] is None or pd.isna(r[k]) else bool(r[k])} for k, label in PIOTROSKI.items()]
    return {"score": number_like(r["piotroski_passed"]), "available": int(r["piotroski_available_criteria"]), "complete": number_like(r["piotroski_f_score_spec"]) is not None, "checks": checks}


def _notes(row: dict[str, Any], pio: dict[str, Any], alt: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Fixed rules on our metrics; every line carries the value that triggered it."""
    pros, cons, flags = [], [], []
    def v(key): return number_like(row.get(key))
    rules = [
        ("roe", lambda x: x >= 0.15, pros, "Return on equity of {:.0%}"), ("roe", lambda x: 0 <= x < 0.05, cons, "Return on equity of only {:.0%}"),
        ("revenue_growth_yoy", lambda x: x >= 0.15, pros, "Revenue up {:.0%} on the year"), ("revenue_growth_yoy", lambda x: x < 0, cons, "Revenue down {:.0%} on the year"),
        ("debt_equity", lambda x: 0 <= x <= 0.5, pros, "Debt is {:.2f}x equity"), ("debt_equity", lambda x: x > 2, cons, "Debt is {:.2f}x equity"),
        ("interest_coverage", lambda x: x >= 8, pros, "Earnings cover interest {:.1f} times"), ("interest_coverage", lambda x: 0 <= x < 1.5, cons, "Earnings cover interest only {:.1f} times"),
        ("current_ratio", lambda x: x >= 2, pros, "Current ratio of {:.2f}"), ("current_ratio", lambda x: x < 1, cons, "Current ratio of {:.2f}, below 1"),
        ("fcf_yield", lambda x: x >= 0.05, pros, "Free cash flow yield of {:.1%}"), ("net_margin", lambda x: x < 0, cons, "Net margin of {:.1%}"),
        ("valuation_percentile", lambda x: x >= 70, pros, "Valuation score of {:.0f} out of 100"), ("momentum_percentile", lambda x: x >= 70, pros, "Momentum score of {:.0f} out of 100"),
        ("momentum_percentile", lambda x: x <= 30, cons, "Momentum score of {:.0f} out of 100"), ("pct_from_52w_high", lambda x: x <= -0.4, cons, "{:.0%} below the 52-week high"),
    ]
    for key, test, bucket, text in rules:
        x = v(key)
        if x is not None and test(x):
            bucket.append({"text": text.format(abs(x) if key == "pct_from_52w_high" else x), "metric": key})
    if pio["score"] is not None and pio["complete"]:
        (pros if pio["score"] >= 7 else cons if pio["score"] <= 3 else []).append({"text": f"Piotroski F-score {pio['score']:.0f} of 9", "metric": "piotroski"})
        if pio["score"] <= 2: flags.append({"text": f"Piotroski F-score {pio['score']:.0f} of 9", "metric": "piotroski"})
    if alt["zone"] == "Safe": pros.append({"text": f"Altman Z of {alt['z']:.2f}, safe zone", "metric": "altman"})
    if alt["zone"] == "Distress": flags.append({"text": f"Altman Z of {alt['z']:.2f}, distress zone", "metric": "altman"})
    if (x := v("net_margin")) is not None and x < 0: flags.append({"text": "Loss-making on the latest year", "metric": "net_margin"})
    if (x := v("interest_coverage")) is not None and x < 1: flags.append({"text": f"Earnings do not cover interest ({x:.1f} times)", "metric": "interest_coverage"})
    if (x := v("ocf_net_income")) is not None and x < 0.5: flags.append({"text": f"Operating cash flow is {x:.0%} of net income", "metric": "ocf_net_income"})
    return {"pros": pros, "cons": cons, "red_flags": flags}


def _peers(p: pd.DataFrame, row: dict[str, Any]) -> dict[str, Any]:
    group = p[p.industry_group.eq(row.get("industry_group"))] if row.get("industry_group") else p.iloc[0:0]
    scope = "industry group"
    if len(group) < 6:
        group, scope = (p[p.sector.eq(row.get("sector"))] if row.get("sector") else p.iloc[0:0]), "sector"
    others = group[group.ticker.ne(row["ticker"])]
    cap = number_like(row.get("market_cap"))
    key = (others.market_cap - cap).abs() if cap is not None and others.market_cap.notna().any() else -others.dollar_volume_20d.fillna(0)
    near = others.loc[key.sort_values().index[:8]]
    cols = ["ticker", "company_name", "market_cap", "trailing_pe", "pb_ratio", "roe", "net_margin", "revenue_growth_yoy", "return_12m", "core_quant_score"]
    median = {c: number_like(near[c].median()) if len(near) else None for c in cols[2:]}
    return {"scope": scope, "scope_n": len(group), "columns": cols, "rows": clean_json(records(pd.concat([group[group.ticker.eq(row["ticker"])], near])[cols])), "median": clean_json(median)}


def chart(symbol: str) -> dict[str, list[dict[str, Any]]]:
    prices = close_matrix([symbol], 2520)
    if prices.empty or symbol not in prices.columns:
        return {}
    series = [{"date": d.strftime("%Y-%m-%d"), "close": float(v)} for d, v in prices[symbol].dropna().items()]
    return {label: series[-n:] for label, n in CHART_DAYS.items()}


def statements(symbol: str, period: str = "annual", all_lines: bool = False) -> dict[str, Any]:
    hist = fundamental_history(symbol, all_columns=all_lines)
    if hist.empty:
        return {"periods": [], "lines": []}
    if "periodType" in hist:
        hist = hist[hist.periodType.eq(period)]
    hist = hist.sort_values("reportDate").drop_duplicates("reportDate", keep="last").tail(6 if period == "annual" else 8)
    skip = {"ticker", "reportDate", "periodType"}
    wanted = [(c, c) for c in hist.columns if c not in skip and pd.to_numeric(hist[c], errors="coerce").notna().any()] if all_lines else [(c, lbl) for c, lbl in LINES if c in hist.columns]
    # A period with none of the lines reported is dropped, not shown as a column of unknowns.
    hist = hist[hist[[c for c, _ in wanted]].apply(pd.to_numeric, errors="coerce").notna().any(axis=1)] if wanted else hist
    periods = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in hist.reportDate]
    lines = [{"key": c, "label": lbl, "values": [number_like(x) for x in pd.to_numeric(hist[c], errors="coerce")]} for c, lbl in wanted]
    return clean_json({"periods": periods, "lines": lines})


def lookup(ticker: str) -> dict[str, Any]:
    symbol = normalize_symbol(ticker)
    p = panel()
    found = p[p.ticker.eq(symbol)]
    if found.empty:
        raise KeyError(f"{ticker} is not in the universe we hold")
    row = found.iloc[0].to_dict()
    with as_of_context(p.attrs.get("as_of_date")):
        pio, alt = _piotroski(p, symbol), _altman(row, symbol)
        stats = _stat_rows(p, row, symbol)
        series = chart(symbol)
    peers = _peers(p, row)
    from .screener import _thesis_line
    return clean_json({
        **_head(row), "industry": row.get("industry") or None, "currency": row.get("quote_currency") or None, "price": number_like(row.get("price")), "market_cap": number_like(row.get("market_cap")), "market_cap_currency": row.get("market_value_currency") or None,
        "price_date": str(row.get("price_observation_date"))[:10], "as_of": str(p.attrs.get("as_of_date")), "chart": series,
        "scores": [{"key": k, "label": label, "value": number_like(row.get(k))} for k, label in SCORES], "thesis": _thesis_line(row),
        "stats": stats, "piotroski": pio, "altman": alt, "peers": peers, "statements": statements(symbol), "notes": _notes(row, pio, alt), "limits": LIMITS,
    })


COMPARE_COLUMNS = ["price", "market_cap", "return_1m", "return_12m", "trailing_pe", "pb_ratio", "ev_ebitda", "fcf_yield", "roe", "net_margin", "debt_equity", "revenue_growth_yoy",
                   "realized_vol_63d", "beta_252", "core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile"]


def compare(tickers: list[str]) -> dict[str, Any]:
    p = panel()
    symbols = list(dict.fromkeys(normalize_symbol(t) for t in tickers))
    missing = [s for s in symbols if s not in set(p.ticker)]
    if missing:
        raise KeyError(f"Not in the universe we hold: {', '.join(missing)}")
    rows = p.set_index("ticker").loc[symbols]
    cols = [c for c in COMPARE_COLUMNS if c in p]
    num = p[cols].apply(pd.to_numeric, errors="coerce")
    # Reference rows: the median of each compared name's sector, then of every name we hold.
    sectors = list(dict.fromkeys(x for x in rows["sector"] if isinstance(x, str) and x))
    medians = [{"label": f"{sec} median", "n": int(p.sector.eq(sec).sum()), **{c: number_like(num.loc[p.sector.eq(sec), c].median()) for c in cols}} for sec in sectors]
    medians.append({"label": "All names median", "n": len(p), **{c: number_like(num[c].median()) for c in cols}})
    return clean_json({"as_of": str(p.attrs.get("as_of_date")), "columns": COMPARE_COLUMNS, "medians": medians,
                       "rows": [{"ticker": s, "company_name": rows.loc[s, "company_name"] or None, "sector": rows.loc[s, "sector"] or None, **{c: number_like(rows.loc[s, c]) if c in rows else None for c in COMPARE_COLUMNS}} for s in symbols]})


# Investor lenses with published, fixed rules (fractions, not percent).
LENSES = [
    {"key": "buffett", "label": "Buffett", "rule": "ROE at least 15%, debt under half of equity, positive free cash flow, net margin at least 10%"},
    {"key": "graham", "label": "Graham", "rule": "P/E at most 15 and P/E times P/B at most 22.5 (the Graham number)"},
    {"key": "dividend", "label": "Dividend safety", "rule": "Pays a dividend, payout at most 60%, debt at most 3 times EBITDA"},
    {"key": "momentum", "label": "Momentum", "rule": "12-month return positive and in the top 30% of every name we hold"},
]
# Multiples whose sector median prices a name: price times sector median over its own multiple.
FAIR_MULTIPLES = ["trailing_pe", "pb_ratio", "ps_ratio"]


def lenses(tickers: list[str]) -> dict[str, Any]:
    """Which lenses each name passes, and a fair-value range from its peers' median P/E, P/B and P/S."""
    p = panel()
    symbols = [s for s in dict.fromkeys(normalize_symbol(t) for t in tickers) if s in set(p.ticker)]
    num = lambda c: pd.to_numeric(p[c], errors="coerce") if c in p else pd.Series(float("nan"), index=p.index)
    roe, de, fcf, nm, pe, pb = num("roe"), num("debt_equity"), num("fcf_yield"), num("net_margin"), num("trailing_pe"), num("pb_ratio")
    dy, payout, debt_ebitda, r12 = num("dividend_yield"), num("payout_ratio"), num("debt_ebitda"), num("return_12m")
    flags = pd.DataFrame({
        "buffett": (roe >= 0.15) & (de <= 0.5) & (fcf > 0) & (nm >= 0.10),
        "graham": (pe > 0) & (pe <= 15) & (pb > 0) & (pe * pb <= 22.5),
        "dividend": (dy > 0) & (payout > 0) & (payout <= 0.6) & (debt_ebitda <= 3),
        "momentum": (r12 > 0) & (r12.rank(pct=True) >= 0.7),
    })
    price = num("price")
    implied = []
    for c in FAIR_MULTIPLES:
        own = num(c).where(num(c) > 0)
        # Peers are the industry when it has 4 or more priced names (true peers beat a wide sector), else the sector.
        by_ind = own.groupby(p.industry).transform("median") if "industry" in p else pd.Series(float("nan"), index=p.index)
        n_ind = own.groupby(p.industry).transform("count") if "industry" in p else pd.Series(0, index=p.index)
        med = by_ind.where(n_ind >= 4, own.groupby(p.sector).transform("median"))
        implied.append(price * med / own)
    fair = pd.concat(implied, axis=1)
    enough = fair.notna().sum(axis=1) >= 2
    lo, mid, hi = fair.min(axis=1).where(enough), fair.median(axis=1).where(enough), fair.max(axis=1).where(enough)
    idx = p.set_index("ticker").index
    pos = {s: i for i, s in enumerate(idx)}
    rows = []
    for s in symbols:
        i = pos[s]
        passed = [k for k in flags if bool(flags[k].iloc[i])]
        rows.append({"ticker": s, "company_name": p.company_name.iloc[i] or None, "sector": p.sector.iloc[i] or None, "price": number_like(price.iloc[i]),
                     **{k: bool(flags[k].iloc[i]) for k in flags}, "passes": len(passed),
                     "fair_low": number_like(lo.iloc[i]), "fair_mid": number_like(mid.iloc[i]), "fair_high": number_like(hi.iloc[i]),
                     "discount": number_like(mid.iloc[i] / price.iloc[i] - 1) if pd.notna(mid.iloc[i]) and price.iloc[i] else None,
                     "fair_basis": int(fair.iloc[i].notna().sum())})
    return clean_json({"as_of": str(p.attrs.get("as_of_date")), "lenses": LENSES, "fair_basis": "Industry median P/E, P/B and P/S (sector when the industry has under 4 priced names) applied to the name's own earnings, book and sales", "rows": rows})


def _flags_for(symbol: str) -> list[dict[str, Any]]:
    """Red flags in the latest four reported quarters: debt jump, income drop, margin collapse, dilution."""
    h = fundamental_history(symbol)
    if h.empty or "periodType" not in h:
        return []
    q = h[h.periodType.eq("quarterly")].sort_values("reportDate").drop_duplicates("reportDate", keep="last").tail(8).reset_index(drop=True)
    col = lambda c: pd.to_numeric(q[c], errors="coerce") if c in q else pd.Series(float("nan"), index=q.index)
    debt, ni, opi, rev, shares = col("Total Debt"), col("Net Income"), col("Operating Income"), col("Total Revenue"), col("Diluted Average Shares")
    margin = opi / rev.where(rev > 0)
    out = []
    for i in range(max(1, len(q) - 4), len(q)):
        when = pd.Timestamp(q.reportDate.iloc[i]).strftime("%Y-%m-%d")
        if debt.iloc[i - 1] > 0 and debt.iloc[i] >= debt.iloc[i - 1] * 1.3:
            out.append({"flag": "Debt jump", "quarter": when, "detail": f"Total debt up {debt.iloc[i] / debt.iloc[i - 1] - 1:.0%} in one quarter"})
        # Against the same quarter a year earlier, so seasonal quarters do not read as drops.
        if i >= 4 and ni.iloc[i - 4] > 0 and (ni.iloc[i] < 0 or ni.iloc[i] <= ni.iloc[i - 4] * 0.5):
            out.append({"flag": "Income drop", "quarter": when, "detail": "Net income turned to a loss" if ni.iloc[i] < 0 else f"Net income down {1 - ni.iloc[i] / ni.iloc[i - 4]:.0%} against the same quarter a year earlier"})
        if i >= 4 and pd.notna(margin.iloc[i]) and pd.notna(margin.iloc[i - 4]) and margin.iloc[i] <= margin.iloc[i - 4] - 0.05:
            out.append({"flag": "Margin collapse", "quarter": when, "detail": f"Operating margin {margin.iloc[i - 4]:.0%} to {margin.iloc[i]:.0%} against the same quarter a year earlier"})
        if i >= 4 and shares.iloc[i - 4] > 0 and shares.iloc[i] >= shares.iloc[i - 4] * 1.05:
            out.append({"flag": "Dilution", "quarter": when, "detail": f"Diluted shares up {shares.iloc[i] / shares.iloc[i - 4] - 1:.0%} in a year"})
    return out


def red_flags(tickers: list[str]) -> dict[str, Any]:
    """P3: warning signs per name with the quarter they appeared, plus Altman distress from the latest statements."""
    p = panel()
    known = set(p.ticker)
    # Altman's Z is built for operating companies; banks, insurers, REITs and utilities sit low by design.
    want = p[p.ticker.isin({normalize_symbol(t) for t in tickers}) & ~p.sector.isin(["Financial Services", "Real Estate", "Utilities"])]
    z = pd.Series(pd.to_numeric(altman_z_score(want), errors="coerce").to_numpy(), index=want.ticker) if len(want) else pd.Series(dtype=float)
    rows = []
    for s in dict.fromkeys(normalize_symbol(t) for t in tickers):
        if s not in known:
            continue
        with as_of_context(p.attrs.get("as_of_date")):  # statements count only 90 days after the period ends
            rows += [{"ticker": s, **f} for f in _flags_for(s)]
        if s in z.index and pd.notna(z.get(s)) and z[s] < 1.81:
            rows.append({"ticker": s, "flag": "Altman distress", "quarter": None, "detail": f"Altman Z {z[s]:.2f}, under the 1.81 distress line"})
    rows.sort(key=lambda r: r["quarter"] or "9999", reverse=True)
    return clean_json({"as_of": str(p.attrs.get("as_of_date")), "rows": rows})


def _t(x: Any) -> str:
    """A Typst string literal."""
    return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fmt(value: float | None, unit: str) -> str:
    return "Unknown" if value is None else f"{value:.1%}" if unit == "pct" else f"{value:,.2f}"


def _whole(value: float | None) -> str:
    return "Unknown" if value is None else f"{value:.0f}"


def pdf(ticker: str) -> bytes:
    """One page: the same facts as the drawer, laid out by Typst."""
    import typst

    d = lookup(ticker)
    year = d["chart"].get("1Y", [])
    pts = year[:: max(1, len(year) // 120)]
    lo, hi = (min(p["close"] for p in pts), max(p["close"] for p in pts)) if pts else (0, 1)
    span = (hi - lo) or 1
    n = max(len(pts) - 1, 1)
    xy = lambda i, p: f"{i * 170 / n:.2f}mm, {18 - (p['close'] - lo) / span * 18:.2f}mm"
    plot = "".join(f"#place(top + left, line(start: ({xy(i, a)}), end: ({xy(i + 1, b)}), stroke: 0.6pt + blue))\n" for i, (a, b) in enumerate(itertools.pairwise(pts)))
    c = lambda x: "[#" + _t(x) + "]"
    rows = "".join(f"{c(s['label'])}, {c(_fmt(s['value'], s['unit']))}, {c(_whole(s['sector_percentile']))}, {c(_whole(s['own_history_percentile']))},\n" for s in d["stats"])
    lists = lambda items: "#list(" + (", ".join(c(i) for i in items) or "[None]") + ")"
    notes = "".join(f"#text(weight: \"bold\")[{t}]\n{lists([x['text'] for x in d['notes'][k]])}\n\n" for k, t in [("pros", "Pros"), ("cons", "Cons"), ("red_flags", "Red flags")])
    mark = {None: "Unknown", True: "Pass", False: "Fail"}
    checks = lists([f"{c['label']}: {mark[c['passed']]}" for c in d["piotroski"]["checks"]])
    pio, alt = d["piotroski"], d["altman"]
    pio_head = "Unknown" if pio["score"] is None else f"{pio['score']:.0f} of 9, {pio['available']} checks known"
    meta = " / ".join(x for x in [d["sector"], d["industry"], d["exchange"]] if x)
    source = f"""#set page(paper: "a4", margin: 14mm)
#set text(size: 8.5pt, font: "Helvetica")
#text(size: 17pt, weight: "bold")[{d['ticker']}] #h(6pt) #{_t(d['company_name'] or 'Unknown')}
#text(fill: gray)[#{_t(meta)} #h(1fr) #{_t('Price ' + _fmt(d['price'], 'x') + ' ' + (d['currency'] or '') + ', ' + d['price_date'])}]
#v(4pt)
#box(width: 170mm, height: 18mm)[
{plot}]
#v(4pt)
#grid(columns: (1fr, 1fr), gutter: 10pt,
  table(columns: (1.4fr, 1fr, 1fr, 1fr), stroke: none, inset: 2.5pt, table.header[*Ratio*][*Value*][*Sector pct*][*Own 3Y pct*],
{rows}),
  [
#text(weight: "bold")[Scores]
{lists([f"{s['label']}: {_whole(s['value'])}" for s in d['scores']])}

#text(weight: "bold")[#{_t('Piotroski F-score ' + pio_head)}]
{checks}

#text(weight: "bold")[#{_t('Altman Z ' + _fmt(alt['z'], 'x') + ', ' + (alt['zone'] or 'Unknown'))}]

{notes}])
#v(4pt)
#text(size: 7pt, fill: gray)[#{_t(' / '.join(d['limits']))}]
"""
    return typst.compile(source.encode())
