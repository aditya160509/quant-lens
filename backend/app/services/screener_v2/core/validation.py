"""Screener V2 validation computations."""
from __future__ import annotations

import json
import math
import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from .common import clean_json, records
from .data_loader import (
    as_of_context,
    close_matrix,
    load_factor_returns,
    ohlcv_for_symbols,
)
from .performance import pit_scope
from .stats import TRADING_DAYS


def sortino_ratio_spec(strategy: pd.Series, annualized_return: float | None, rf_annual: float = 0.0) -> float | None:
    if strategy.empty or annualized_return is None:
        return None
    rf_daily = rf_annual / TRADING_DAYS
    shortfall = (strategy - rf_daily).clip(upper=0)
    downside_var = float((shortfall**2).mean()) * TRADING_DAYS
    if downside_var <= 0:
        return None
    return float((annualized_return - rf_annual) / math.sqrt(downside_var))


def score_backtest(
    symbols: list[str],
    scores: pd.Series,
    lookback_days: int = 756,
    top_n: int = 50,
    cost_bps: float = 10.0,
    long_short: bool = False,
    score_weighted: bool = False,
    rebalance_days: int = 21,
    rebalance_offset_days: int = 0,
    sector_neutral: bool = False,
    sector_map: dict[str, str] | None = None,
    score_at: Callable | None = None,
    weekday: int | None = None,
) -> dict[str, Any]:
    from .backtest import simulate
    from .currency import CONFIG, instrument_specs, usd_price_matrix
    if score_at is None:
        raise ValueError("Historical backtests require a point-in-time score provider; current scores cannot be backfilled")
    if sector_neutral:
        raise ValueError("Sector-neutral execution is unavailable without historical sector membership")
    calendar_symbol = CONFIG.get().get("calendar_ticker", "SPY")
    specs = instrument_specs(symbols)
    excluded_non_usd: list[str] = []
    if any(spec.get("quote_currency") != "USD" for spec in specs.values()) and not CONFIG.get().get("explicit_calendar"):
        # A USD session calendar cannot hold foreign quotes without filling them, so test only USD-quoted names.
        excluded_non_usd = [symbol for symbol in symbols if specs[symbol].get("quote_currency") != "USD"]
        symbols = [symbol for symbol in symbols if symbol not in set(excluded_non_usd)]
        specs = {symbol: specs[symbol] for symbol in symbols}
        if not symbols:
            raise ValueError("Non-USD portfolios require explicit instrument_metadata and calendar_ticker")
    source_prices = close_matrix(list(dict.fromkeys(symbols + [calendar_symbol, "SPY"])), lookback_days=(lookback_days + 252) * 2)
    if calendar_symbol not in source_prices or source_prices[calendar_symbol].notna().sum() < 254:
        raise ValueError("Backtest trading calendar requires at least 254 observed calendar instrument sessions")
    calendar = pd.DatetimeIndex(ohlcv_for_symbols([calendar_symbol]).Date.drop_duplicates().sort_values().tail(lookback_days + 252))
    prices = usd_price_matrix(source_prices.reindex(index=calendar, columns=symbols), specs, strict=True)
    result = simulate(prices, score_at, top_n=top_n, rebalance_days=rebalance_days,
                      cost_bps=cost_bps, offset=rebalance_offset_days, long_short=long_short,
                      score_weighted=score_weighted, weekday=weekday)
    frame = result["curve"].set_index("date")
    selected, short_selected = result["selected"], result["short_selected"]
    eligible = selected + short_selected
    strategy = frame.net_return
    spy = close_matrix(["SPY"], lookback_days + 253)
    universe = spy["SPY"].pct_change(fill_method=None).reindex(strategy.index) if "SPY" in spy else pd.Series(np.nan, index=strategy.index)
    benchmark_complete = universe.notna().all()
    if not benchmark_complete:
        universe[:] = np.nan
    equity = (1 + strategy).cumprod()
    benchmark = (1 + universe).cumprod()
    drawdown = equity / equity.cummax().clip(lower=1.0) - 1
    excess = strategy - universe
    avg_drawdown = drawdown[drawdown < 0].mean()
    years = strategy.groupby(strategy.index.year).apply(lambda s: float((1 + s).prod() - 1)) if len(strategy) else pd.Series(dtype=float)
    position_returns = strategy.groupby(np.arange(len(strategy)) // max(1, rebalance_days)).apply(lambda r: (1 + r).prod() - 1)
    annualized_return = float(equity.iloc[-1] ** (TRADING_DAYS / max(len(equity), 1)) - 1) if len(equity) else None
    ann_vol = float(strategy.std() * math.sqrt(TRADING_DAYS))
    factors = load_factor_returns()
    rf_daily = factors.set_index("date")["rf"].reindex(strategy.index) if "rf" in factors else pd.Series(np.nan, index=strategy.index)
    rf_annual = float(rf_daily.mean() * TRADING_DAYS) if rf_daily.notna().all() else np.nan
    sharpe = float(((strategy.mean() * TRADING_DAYS) - rf_annual) / (ann_vol or np.nan))
    stats = {
        "trading_calendar": "observed SPY sessions; US-market schedule, not crypto weekends or other exchange calendars",
        "benchmark": "SPY",
        "benchmark_status": "observed" if benchmark_complete else "unavailable: missing observed SPY returns",
        "selected_count": len(selected),
        "eligible_count": len(eligible),
        "short_count": len(short_selected),
        "long_short": bool(long_short),
        "score_weighted": bool(score_weighted),
        "rebalance_days": int(rebalance_days),
        "rebalance_offset_days": int(rebalance_offset_days),
        "sector_neutral": bool(sector_neutral),
        "total_return": float(equity.iloc[-1] - 1) if len(equity) else None,
        "annualized_return": annualized_return,
        "annualized_vol": ann_vol,
        "risk_free_annual": rf_annual,
        "sharpe": sharpe,
        "sortino": sortino_ratio_spec(strategy, annualized_return, rf_annual),
        "calmar": float((annualized_return or np.nan) / abs(drawdown.min() or np.nan)) if len(equity) else None,
        "max_drawdown": float(drawdown.min()),
        "average_drawdown": float(avg_drawdown) if pd.notna(avg_drawdown) else None,
        "rebalance_period_hit_rate": float((position_returns > 0).mean()) if len(position_returns) else None,
        "rebalance_period_average_gain": float(position_returns[position_returns > 0].mean()) if len(position_returns[position_returns > 0]) else None,
        "rebalance_period_average_loss": float(position_returns[position_returns < 0].mean()) if len(position_returns[position_returns < 0]) else None,
        "best_calendar_year": int(years.idxmax()) if len(years) else None,
        "best_calendar_year_return": float(years.max()) if len(years) else None,
        "worst_calendar_year": int(years.idxmin()) if len(years) else None,
        "worst_calendar_year_return": float(years.min()) if len(years) else None,
        "information_ratio": float(excess.mean() / (excess.std() or np.nan) * math.sqrt(TRADING_DAYS)),
        "unavailable_formation_dates": getattr(score_at, "unavailable_dates", {}),
        "formation_policy": "Signals with no available scores hold cash; learned weights use only matured historical labels",
        "survivorship_bias_warning": (
            "This backtest uses currently-listed tickers in the local market universe. Delisted, bankrupt, and merged securities are excluded, "
            "which can inflate results versus a survivorship-bias-corrected backtest. True correction requires delisted-security history not present locally."
        ),
    }
    stats["portfolio_currency"] = "USD"
    stats["excluded_non_usd_count"] = len(excluded_non_usd)
    stats["calendar_ticker"] = calendar_symbol
    stats["fx_policy"] = "exact-date observed spot rates; no filling; missing conversion invalidates the run"
    curve = pd.DataFrame({"date": equity.index, "strategy": equity.values, "benchmark": benchmark.reindex(equity.index).values, "drawdown": drawdown.values})
    rolling = pd.DataFrame({"date": strategy.index})
    for window in [63, 252, 756]:
        rolling[f"rolling_{window}d_return"] = ((1 + strategy).rolling(window).apply(np.prod, raw=True) - 1).to_numpy()
        rolling[f"rolling_{window}d_vol"] = (strategy.rolling(window).std() * math.sqrt(TRADING_DAYS)).to_numpy()
        rolling[f"rolling_{window}d_sharpe"] = ((strategy - rf_daily).rolling(window).mean() / strategy.rolling(window).std() * math.sqrt(TRADING_DAYS)).to_numpy()
    return {"equity_curve": records(curve), "stats": clean_json(stats), "rolling": records(rolling), "selected": selected, "short_selected": short_selected, "turnover": records(frame.reset_index()[["date", "turnover", "cost_fraction", "rebalance"]]), "trades": records(result["trades"]), "positions": records(result["positions"]), "attribution": records(result["attribution"]), "daily_returns": strategy}


def score_backtest_by_weekday(symbols, scores, lookback_days=756, top_n=50, cost_bps=10.0, **kwargs):
    return [{"weekday": label, **score_backtest(symbols, scores, lookback_days, top_n, cost_bps,
             weekday=day, **kwargs)["stats"]}
            for day, label in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]


# Panels across runs, so changing weights or top N re-scores without rebuilding history.
# Bounded by bytes: one 1,000-name panel is ~2 MB, a 12-name one ~40 kB, so a count cap means nothing.
_PANEL_CACHE: OrderedDict = OrderedDict()
_PANEL_CACHE_MAX_BYTES = 256 * 2**20
_panel_cache_bytes = 0
_PANEL_CACHE_LOCK = threading.Lock()  # jobs run on a thread pool


def _panel_cache_put(key, panel: pd.DataFrame) -> None:
    global _panel_cache_bytes
    size = int(panel.memory_usage(deep=True, index=True).sum())
    if size > _PANEL_CACHE_MAX_BYTES:
        return
    with _PANEL_CACHE_LOCK:
        if key in _PANEL_CACHE:
            _panel_cache_bytes -= _PANEL_CACHE.pop(key)[1]
        _PANEL_CACHE[key] = (panel, size)
        _panel_cache_bytes += size
        while _panel_cache_bytes > _PANEL_CACHE_MAX_BYTES:
            _panel_cache_bytes -= _PANEL_CACHE.popitem(last=False)[1][1]


def _panel_cache_get(key) -> pd.DataFrame | None:
    with _PANEL_CACHE_LOCK:
        entry = _PANEL_CACHE.get(key)
        if entry is None:
            return None
        _PANEL_CACHE.move_to_end(key)
        return entry[0]
# Keys read only after the panel is built; they never change a dated panel.
_SCORE_ONLY_KEYS = {"components", "weights", "top_n", "long_short", "score_weighted", "focus_ticker", "formula", "cost_bps", "score_field"}


def point_in_time_scorer(symbols, payload, kind="field", field=None, shared_cache=None):
    for key in ["sector", "sectors", "industry", "industries", "industry_group", "industry_groups", "exchange", "exchanges"]:
        if payload.get(key) and str(payload[key]).lower() not in {"all", "any"}:
            raise ValueError(f"Historical {key} filters require dated classification membership unavailable locally")
    if payload.get("sector_neutral") or isinstance(payload.get("components"), dict) and payload["components"].get("sector_neutral"):
        raise ValueError("Historical sector neutralization requires dated sector membership unavailable locally")
    from .academic import academic_strategy_scores
    from .composite import InsufficientTrainingData, component_scores, composite_config
    from .formula import evaluate_formula
    from .panel import metric_panel
    from .screener import apply_filters
    panels = shared_cache if shared_cache is not None else {}
    cache, unavailable_dates = {}, {}
    from .data_loader import MARKET_UNIVERSE, MASTER_FUNDAMENTALS, _path_version
    shape = json.dumps({k: v for k, v in payload.items() if k not in _SCORE_ONLY_KEYS}, sort_keys=True, default=str)
    run_key = (_path_version(MARKET_UNIVERSE), _path_version(MASTER_FUNDAMENTALS), tuple(symbols), shape)
    def panel_at(date):
        key = ("panel", pd.Timestamp(date))
        if key not in panels:
            hit = _panel_cache_get((*run_key, key[1]))
            if hit is None:
                with as_of_context(date), pit_scope(panels):
                    hit = metric_panel({**payload, "as_of_date": str(pd.Timestamp(date).date())}, symbols)
                    hit, _ = apply_filters(hit, payload)
                _panel_cache_put((*run_key, key[1]), hit)
            panels[key] = hit
        return panels[key].copy()
    def score_at(date):
        key = pd.Timestamp(date)
        if key not in cache:
            with as_of_context(key), pit_scope(panels):
                panel = panel_at(key)
                if kind == "formula":
                    panel["formation_score"] = evaluate_formula(panel, payload.get("formula") or "core_quant_score").values
                    selected_field = "formation_score"
                elif kind == "composite":
                    try:
                        panel = component_scores(panel, composite_config(payload), history_cache=panels)
                    except InsufficientTrainingData as exc:
                        unavailable_dates[str(key.date())] = str(exc)
                        panel = panel[["ticker"]].assign(composite_score=np.nan)
                    selected_field = "composite_score"
                elif kind == "academic":
                    academic_key = ("academic", key)
                    if academic_key not in panels:
                        panels[academic_key] = academic_strategy_scores(panel)
                    panel = panels[academic_key]
                    selected_field = field
                else:
                    selected_field = field or payload.get("score_field") or "core_quant_score"
                if selected_field not in panel:
                    raise ValueError(f"Unknown score field: {selected_field}")
                cache[key] = panel.set_index("ticker")[selected_field]
                if kind == "academic" and field == "graham_net_net":
                    cache[key] = cache[key].where(cache[key] > 0)
        return cache[key]
    score_at.unavailable_dates = unavailable_dates
    score_at.panel_at = panel_at
    return score_at
