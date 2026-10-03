"""Screener V2 validation computations."""
from __future__ import annotations
import math
from typing import Any, Callable
import numpy as np
import pandas as pd
from .data_loader import as_of_context, close_matrix, load_factor_returns, ohlcv_for_symbols
from .common import clean_json, records
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
    if score_at is None:
        raise ValueError("Historical backtests require a point-in-time score provider; current scores cannot be backfilled")
    if sector_neutral:
        raise ValueError("Sector-neutral execution is unavailable without historical sector membership")
    source_prices = close_matrix(list(dict.fromkeys(symbols + ["SPY"])), lookback_days=(lookback_days + 252) * 2)
    if "SPY" not in source_prices or source_prices["SPY"].notna().sum() < 254:
        raise ValueError("Backtest trading calendar requires at least 254 observed SPY sessions")
    calendar = pd.DatetimeIndex(ohlcv_for_symbols(["SPY"]).Date.drop_duplicates().sort_values().tail(lookback_days + 252))
    prices = source_prices.reindex(index=calendar, columns=symbols)
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


def point_in_time_scorer(symbols, payload, kind="field", field=None, shared_cache=None):
    for key in ["sector", "sectors", "industry", "industries", "industry_group", "industry_groups", "exchange", "exchanges"]:
        if payload.get(key) and str(payload[key]).lower() not in {"all", "any"}:
            raise ValueError(f"Historical {key} filters require dated classification membership unavailable locally")
    if payload.get("sector_neutral") or isinstance(payload.get("components"), dict) and payload["components"].get("sector_neutral"):
        raise ValueError("Historical sector neutralization requires dated sector membership unavailable locally")
    from .panel import metric_panel
    from .screener import apply_filters
    from .formula import evaluate_formula
    from .composite import composite_config, component_scores, InsufficientTrainingData
    from .academic import academic_strategy_scores
    panels = shared_cache if shared_cache is not None else {}
    cache, unavailable_dates = {}, {}
    def panel_at(date):
        key = ("panel", pd.Timestamp(date))
        if key not in panels:
            with as_of_context(date):
                frame = metric_panel({**payload, "as_of_date": str(pd.Timestamp(date).date())}, symbols)
                frame, _ = apply_filters(frame, payload)
                panels[key] = frame
        return panels[key].copy()
    def score_at(date):
        key = pd.Timestamp(date)
        if key not in cache:
            with as_of_context(key):
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
