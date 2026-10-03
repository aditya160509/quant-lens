"""Screener V2 valuation computations."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import close_matrix, fundamental_history, parse_symbols, normalize_symbol
from .common import clean_json, number_like, records
from .stats import _pick, rank_pct


def historical_valuation_series(symbol, metric="trailing_pe", lookback=756):
    """Reprice available trailing-twelve-month statements on observed trading dates, never info snapshots."""
    supported = {"trailing_pe", "pb_ratio", "ps_ratio", "p_cf", "ev_ebit", "ev_ebitda", "fcf_yield"}
    if metric not in supported:
        raise ValueError(f"Historical valuation metric unavailable: {metric}")
    from .fundamentals import statement_snapshots, enterprise_claims
    hist = statement_snapshots([symbol])
    prices = close_matrix([symbol], lookback)
    if hist.empty or prices.empty or symbol not in prices:
        return []
    if hist.empty:
        return []
    reports = pd.DataFrame({"available_date": pd.to_datetime(hist.reportDate) + pd.Timedelta(days=90)})
    for key, fields in {
        "shares": ["Ordinary Shares Number", "Share Issued"],
        "income": ["Net Income"], "equity": ["Stockholders Equity", "Total Equity"],
        "revenue": ["Total Revenue"], "ocf": ["Operating Cash Flow"],
        "fcf": ["Free Cash Flow"], "debt": ["Total Debt"],
        "cash": ["Cash And Cash Equivalents"], "ebit": ["EBIT"], "ebitda": ["EBITDA"],
    }.items():
        reports[key] = pd.to_numeric(_pick(hist, fields), errors="coerce")
    reports["enterprise_claims"] = enterprise_claims(hist)
    reports = reports.dropna(subset=["available_date"]).sort_values("available_date").drop_duplicates("available_date", keep="last")
    daily = pd.DataFrame({"date": prices.index, "price": prices[symbol].values})
    reports["available_date"] = reports.available_date.astype("datetime64[ns]")
    daily["date"] = daily.date.astype("datetime64[ns]")
    daily = pd.merge_asof(daily, reports, left_on="date", right_on="available_date", direction="backward", tolerance=pd.Timedelta(days=550))
    market_cap = daily.price * daily.shares
    enterprise = market_cap + daily.enterprise_claims - daily.cash
    if metric == "fcf_yield":
        value = daily.fcf / market_cap.where(market_cap > 0)
    else:
        denominator = daily[{"trailing_pe": "income", "pb_ratio": "equity", "ps_ratio": "revenue", "p_cf": "ocf", "ev_ebit": "ebit", "ev_ebitda": "ebitda"}[metric]]
        value = (enterprise if metric.startswith("ev_") else market_cap) / denominator.where(denominator > 0)
    daily["valuation_metric"] = value.replace([np.inf, -np.inf], np.nan)
    daily["metric"] = metric
    daily["basis"] = "four complete quarters or matching annual report; conservative 90-day lag"
    daily["history_percentile"] = daily.valuation_metric.expanding(min_periods=4).rank(pct=True) * 100
    return records(daily[["date", "valuation_metric", "metric", "basis", "history_percentile"]].dropna())


def relative_valuation(panel: pd.DataFrame, ticker: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if panel.empty:
        return {"card": {}, "sector_heatmap": [], "peer_table": [], "history": [], "universe_cards": []}
    symbol = normalize_symbol(ticker or panel.iloc[0]["ticker"])
    row = panel[panel["ticker"].eq(symbol)]
    if row.empty:
        raise ValueError(f"Focus ticker {symbol} is outside the selected universe")
    r = row.iloc[0]
    sector = r.get("sector", "Unknown")
    industry = r.get("industry", "Unknown")
    custom_peers = payload.get("peers") or payload.get("custom_peers")
    if custom_peers:
        peer_symbols = set(parse_symbols({"tickers": custom_peers}))
        absent = peer_symbols - set(panel.ticker)
        if absent:
            raise ValueError(f"Peers outside selected universe: {sorted(absent)}")
        peers = panel[panel["ticker"].isin(peer_symbols | {symbol})].copy()
        peer_scope = "custom"
    elif payload.get("peer_scope") == "universe":
        peers = panel.copy()
        peer_scope = "universe"
    elif payload.get("peer_scope") == "industry" and "industry" in panel.columns:
        peers = panel[panel["industry"].eq(industry)].copy()
        peer_scope = "industry"
    elif payload.get("peer_scope") == "market_cap_bucket":
        cap = pd.to_numeric(panel["market_cap"], errors="coerce")
        bucket = pd.qcut(cap.rank(method="first"), q=min(5, max(1, cap.notna().sum())), labels=False, duplicates="drop")
        row_bucket = bucket.reindex(row.index).iloc[0]
        peers = panel[bucket.eq(row_bucket)].copy()
        peer_scope = "market_cap_bucket"
    else:
        peers = panel[panel["sector"].eq(sector)].copy()
        peer_scope = "sector"
    metrics = ["trailing_pe", "forward_pe", "pb_ratio", "ps_ratio", "p_cf", "ev_ebit", "ev_ebitda", "fcf_yield"]
    peer_rows = []
    universe_rows = []
    for metric in metrics:
        higher_better = metric in {"fcf_yield"}
        val = number_like(r.get(metric))
        med = number_like(peers[metric].median()) if metric in peers else None
        pct = number_like(rank_pct(peers[metric], higher_better=higher_better).reindex(row.index).iloc[0]) if metric in peers else None
        universe_pct = number_like(rank_pct(panel[metric], higher_better=higher_better).reindex(row.index).iloc[0]) if metric in panel else None
        peer_rows.append({"metric": metric, "ticker_value": val, "peer_median": med, "cheapness_percentile": pct, "vs_peer_median": val - med if val is not None and med is not None else None, "peer_scope": peer_scope})
        universe_rows.append(
            {
                "metric": metric,
                "ticker": r.get("ticker"),
                "ticker_value": val,
                "universe_percentile": universe_pct,
                "universe_median": number_like(panel[metric].median()) if metric in panel else None,
                "universe_coverage": float(panel[metric].notna().mean()) if metric in panel else None,
            }
        )
    history_metric = payload.get("history_metric") or "trailing_pe"
    history_window = int(payload.get("history_window") or payload.get("lookback_days", 756))
    if payload.get("history_window") and history_window not in {252, 756, 2520}:
        raise ValueError("history_window must be 252, 756 or 2520 trading sessions")
    history_series_rows = historical_valuation_series(symbol, history_metric, history_window)
    history_percentile = own_history_percentile_from_series([item.get("valuation_metric") for item in history_series_rows])
    slope_info = re_rating_slope_from_series(history_series_rows)
    universe_ranks = pd.DataFrame({metric: rank_pct(panel[metric], higher_better=metric == "fcf_yield") for metric in metrics if metric in panel}, index=panel.index)
    sector_ranks = pd.DataFrame({metric: panel.groupby("sector")[metric].transform(lambda values: rank_pct(values, higher_better=metric == "fcf_yield")) for metric in metrics if metric in panel}, index=panel.index)
    card = {
        "ticker": r.get("ticker"),
        "sector": sector,
        "industry": industry,
        "peer_scope": peer_scope,
        "absolute_valuation": {metric: number_like(r.get(metric)) for metric in metrics},
        "sector_percentile": number_like(sector_ranks.mean(axis=1).loc[r.name]),
        "peer_percentile": number_like(pd.Series([x.get("cheapness_percentile") for x in peer_rows], dtype=float).mean()),
        "universe_percentile": np.nanmean([x.get("universe_percentile") for x in universe_rows if x.get("universe_percentile") is not None]),
        "own_history_percentile": history_percentile,
        "re_rating_slope": slope_info,
        "momentum_percentile": r.get("momentum_percentile"),
    }
    sector_heat = []
    for sec, g in panel.groupby("sector"):
        for metric in metrics:
            if metric in g.columns:
                sector_heat.append({"row": str(sec), "col": metric, "value": number_like(rank_pct(panel[metric], higher_better=metric in {"fcf_yield"}).reindex(g.index).mean()), "count": int(len(g)), "median_market_cap": number_like(g["market_cap"].median()) if "market_cap" in g else None})
    cards = panel[["ticker", "sector"]].copy()
    cards["sector_percentile"] = sector_ranks.mean(axis=1)
    cards["universe_percentile"] = universe_ranks.mean(axis=1)
    cards["valuation_metric_coverage"] = universe_ranks.notna().sum(axis=1)
    universe_cards = records(cards.head(int(payload.get("card_limit") or 100)))
    absolute = panel.set_index("ticker")
    for item in universe_cards:
        ticker = item["ticker"]
        item["absolute_valuation"] = {metric: number_like(absolute.loc[ticker].get(metric)) for metric in metrics}
        own = history_series_rows if ticker == symbol else historical_valuation_series(ticker, history_metric, history_window)
        item["own_history_percentile"] = own_history_percentile_from_series([row["valuation_metric"] for row in own])
        item["own_history_observations"] = len(own)
        item["own_history_as_of_date"] = own[-1]["date"] if own else None
        item["history_metric"] = history_metric
    return {
        "card": clean_json(card),
        "sector_heatmap": clean_json(sector_heat),
        "peer_table": clean_json(peer_rows),
        "universe_table": clean_json(universe_rows),
        "history": clean_json(history_series_rows),
        "universe_cards": clean_json(universe_cards),
    }


def own_history_percentile_from_series(values: Any) -> float | None:
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if len(series) < 4:
        return None
    latest = series.iloc[-1]
    reference = series.iloc[:-1]
    if reference.empty:
        return None
    return float((reference < latest).mean() * 100)


def re_rating_slope_from_series(series: list[dict[str, Any]], trailing_periods: int = 21) -> dict[str, Any]:
    recent = series[-trailing_periods:] if len(series) >= trailing_periods else series
    y = np.array([number_like(r.get("history_percentile")) for r in recent], dtype=float)
    valid = np.isfinite(y)
    y = y[valid]
    if len(y) < 3:
        return {"slope_per_period": None, "slope_per_month": None, "interpretation": "insufficient_history"}
    from scipy.stats import linregress
    dates = pd.to_datetime([row["date"] for row in recent]).to_numpy(dtype="datetime64[D]")[valid]
    x = np.busday_count(dates[0], dates).astype(float)
    slope = float(linregress(x, y).slope)
    return {"slope_per_weekday": slope, "slope_per_21_weekdays": slope * 21.0, "time_basis": "observed date spacing, weekdays (exchange holidays not removed)", "interpretation": "re-rating" if slope > 0 else "de-rating" if slope < 0 else "flat"}

