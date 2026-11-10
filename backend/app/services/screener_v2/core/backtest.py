"""Point-in-time selection and self-financing, drifted-weight execution.

Signals at close t are executed at close t+1. Returns earned on the execution
session belong to the old holdings. Costs are proportional to traded notional.
"""
from collections.abc import Callable

import numpy as np
import pandas as pd


def simulate(prices: pd.DataFrame, score_at: Callable, top_n: int = 50,
             rebalance_days: int = 21, cost_bps: float = 10,
             offset: int = 0, long_short: bool = False,
             score_weighted: bool = False, weekday: int | None = None,
             min_history: int = 252) -> dict:
    if top_n < 1 or rebalance_days < 1 or cost_bps < 0 or offset < 0:
        raise ValueError('Invalid backtest size, frequency, offset or costs')
    if min_history < 1 or offset >= len(prices) - min_history - 1:
        raise ValueError("Insufficient history for the requested rebalance offset")
    prices = prices.sort_index().astype(float)
    if (prices <= 0).any().any():
        raise ValueError("Backtest requires strictly positive observed prices")
    if prices.empty or len(prices) < min_history + 2:
        raise ValueError('Insufficient price history for formation and execution')
    if prices.index.has_duplicates or prices.columns.has_duplicates:
        raise ValueError('Backtest prices must have unique dates and tickers')
    start = min_history - 1 + offset
    formations = list(range(start, len(prices) - 1, rebalance_days))
    if weekday is not None:
        formations = sorted({next((j for j in range(i, min(i + 7, len(prices) - 1))
                                  if prices.index[j].weekday() == weekday), -1)
                             for i in formations} - {-1})
    pending = {}
    counts = prices.notna().cumsum()
    for i in formations:
        eligible = prices.columns[(counts.iloc[i] >= min_history) & prices.iloc[i].notna()]
        scores = pd.to_numeric(score_at(prices.index[i]), errors='coerce').reindex(eligible)
        ranked = scores.replace([np.inf, -np.inf], np.nan).dropna().sort_values(ascending=False, kind='stable')
        target = pd.Series(0.0, index=prices.columns)
        long = ranked.head(top_n)
        if len(long):
            if score_weighted:
                positive = long.clip(lower=0)
                if positive.sum() <= 0:
                    raise ValueError('Score-weighted portfolio requires positive selected scores')
                target.loc[long.index] = positive / positive.sum()
            else:
                target.loc[long.index] = 1 / len(long)
            if long_short:
                short = ranked.drop(long.index).tail(top_n)
                if len(short) < len(long):
                    raise ValueError('Long-short selection requires disjoint, equally sized eligible legs')
                target.loc[short.index] = -1 / len(short)
        pending[i + 1] = (target.to_numpy(), prices.index[i])
    # Arrays, not Series, in the daily loop: same elementwise operations and the same NumPy sums
    # pandas uses for float Series, so every number is unchanged.
    values, columns, dates = prices.to_numpy(), prices.columns, prices.index
    weights = np.zeros(len(columns))
    equity = 1.0
    curve, trades, positions = [], [], []
    attribution, episodes = {}, {}
    def attribute(ticker, pnl=0.0, fee=0.0):
        item = attribution.setdefault(ticker, {"ticker": ticker, "gross_pnl_contribution": 0.0, "cost_contribution": 0.0})
        item["gross_pnl_contribution"] += pnl
        item["cost_contribution"] += fee
        if ticker in episodes:
            episodes[ticker]["gross_pnl_contribution"] += pnl
            episodes[ticker]["cost_contribution"] += fee
    for i in range(start + 1, len(prices)):
        held = weights != 0
        if held.any() and (np.isnan(values[i, held]).any() or np.isnan(values[i - 1, held]).any()):
            raise ValueError(f'Missing observed price for held position on {dates[i].date()}; no stale-price substitution')
        returns = values[i] / values[i - 1] - 1
        contribution = weights[held] * returns[held]
        gross = float(contribution.sum())
        for ticker, value in zip(columns[held], contribution):
            attribute(ticker, pnl=equity * float(value))
        if 1 + gross <= 0:
            raise ValueError('Portfolio equity exhausted')
        drifted = weights.copy()
        drifted[held] = weights[held] * (1 + returns[held]) / (1 + gross)
        cost = 0.0
        if i in pending:
            target, formation = pending[i]
            if np.isnan(values[i][target != 0]).any():
                raise ValueError(f"Missing execution price on {dates[i].date()}")
            # Cost fraction c solves c = k * sum(|(1-c)target - drifted|).
            # Fixed point is a contraction for normal commission rates.
            k = cost_bps / 10000
            if k >= 0.1:
                raise ValueError('Transaction costs must be below 1000 basis points')
            for _ in range(50):
                updated = k * float(np.abs((1 - cost) * target - drifted).sum())
                if abs(updated - cost) < 1e-13:
                    cost = updated
                    break
                cost = updated
            traded = (1 - cost) * target - drifted
            turnover = float(np.abs(traded).sum())
            if cost >= 1:
                raise ValueError('Transaction costs exhaust portfolio equity')
            for j in np.flatnonzero(np.abs(traded) > 1e-12):
                ticker = columns[j]
                old, new = float(drifted[j]), float(target[j])
                closing = old != 0 and (new == 0 or np.sign(old) != np.sign(new))
                fee = equity * (1 + gross) * k * abs(float(traded[j]))
                attribute(ticker, fee=fee)
                if closing and ticker in episodes:
                    episode = episodes.pop(ticker)
                    episode.update(exit_date=dates[i], exit_price=float(values[i, j]), status="closed")
                    episode["price_return"] = episode["direction"] * (episode["exit_price"] / episode["entry_price"] - 1)
                    positions.append(episode)
                if new != 0 and (old == 0 or closing):
                    episodes[ticker] = {"ticker": ticker, "entry_date": dates[i], "entry_price": float(values[i, j]),
                                        "exit_date": None, "direction": int(np.sign(new)), "gross_pnl_contribution": 0.0,
                                        "cost_contribution": fee if old == 0 else 0.0, "status": "open"}
                trades.append({'ticker': ticker, 'formation_date': formation, 'execution_date': dates[i],
                               'old_weight': drifted[j], 'new_weight': target[j],
                               'traded_notional_fraction': float(traded[j])})
            weights = target
        else:
            turnover = 0.0
            weights = drifted
        net = (1 + gross) * (1 - cost) - 1
        equity *= 1 + net
        curve.append({'date': dates[i], 'strategy': equity, 'net_return': net,
                      'gross_return': gross, 'turnover': turnover, 'cost_fraction': cost,
                      'rebalance': i in pending, 'selected_count': int((weights > 0).sum())})
    for ticker, episode in episodes.items():
        episode.update(last_mark_date=prices.index[-1], last_mark_price=float(prices.iloc[-1][ticker]))
        episode["price_return"] = episode["direction"] * (episode["last_mark_price"] / episode["entry_price"] - 1)
        positions.append(episode)
    for item in attribution.values():
        item["net_pnl_contribution"] = item["gross_pnl_contribution"] - item["cost_contribution"]
    for episode in positions:
        episode["net_pnl_contribution"] = episode["gross_pnl_contribution"] - episode["cost_contribution"]
    frame = pd.DataFrame(curve)
    frame['drawdown'] = frame.strategy / frame.strategy.cummax().clip(lower=1) - 1
    return {'curve': frame, 'trades': pd.DataFrame(trades), 'attribution': pd.DataFrame(list(attribution.values())), 'positions': pd.DataFrame(positions),
            'selected': columns[weights > 0].tolist(), 'short_selected': columns[weights < 0].tolist()}

