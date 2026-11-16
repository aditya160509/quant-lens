"""The one fill model. Plain scalar functions: the vector engine compiles them with numba, the event engine calls them as is.

Rules (printed on every run):
- A signal at close t fills at the open of t+1 (default) or at close t ("same close", optimistic).
- A stop or target gapped through at the open fills at the open, not at its own price.
- When a stop and a target are both inside one bar the stop fills first (worse first).
"""

from __future__ import annotations

import math

NONE, STOP, TARGET = 0, 1, 2


def fill_price(raw: float, direction: float, slip_bps: float, slip_range: float, bar_range: float) -> float:
    """Price after slippage. direction +1 buys (pays more), -1 sells (gets less)."""
    return raw * (1.0 + direction * slip_bps / 1e4) + direction * slip_range * bar_range


def commission(shares: float, price: float, bps: float, per_share: float, minimum: float) -> float:
    if shares <= 0:
        return 0.0
    return max(minimum, shares * price * bps / 1e4 + shares * per_share)


def exit_check(d: float, o: float, h: float, low: float, stop: float, target: float):
    """(reason, raw price) for a position of direction d inside one bar. NaN level = not set."""
    if d > 0:
        hit_stop, hit_target = low <= stop, h >= target
        gap_stop, gap_target = o <= stop, o >= target
    else:
        hit_stop, hit_target = h >= stop, low <= target
        gap_stop, gap_target = o >= stop, o <= target
    if gap_stop:
        return STOP, o
    if gap_target:
        return TARGET, o
    if hit_stop:
        return STOP, stop
    if hit_target:
        return TARGET, target
    return NONE, math.nan


# Sizing modes
SHARES, CASH, PCT_EQUITY, RISK, EQUAL, VOL, SCORE, KELLY = 0, 1, 2, 3, 4, 5, 6, 7


def size_shares(mode: int, value: float, equity: float, price: float, stop_distance: float, slots: float, vol: float = math.nan, mult: float = math.nan) -> float:
    """Shares to order, decided at the signal bar's close. Risk sizing needs a stop; without one it orders nothing.
    SCORE: the slot's share times `mult` (this name's score over the mean score of today's entries, 0 to 3).
    KELLY: `mult` (the Kelly fraction from trades closed so far) capped at `value`, of equity; an equal share until 20 trades have closed.
    VOL: each slot's share of equity scaled so the position's annual volatility is `value` (vol = annualised stdev of daily returns)."""
    if price <= 0 or equity <= 0:
        return 0.0
    if mode == SHARES:
        return value
    if mode == CASH:
        return value / price
    if mode == PCT_EQUITY:
        return equity * value / price
    if mode == RISK:
        return equity * value / stop_distance if stop_distance > 0 else 0.0
    if mode == SCORE:
        return equity / slots * (mult if math.isfinite(mult) else 1.0) / price
    if mode == KELLY:
        return equity * min(max(mult, 0.0), value) / price if math.isfinite(mult) else equity / slots / price
    if mode == VOL:
        return equity / slots * min(value / vol, 1.0) / price if vol > 0 else 0.0
    return equity / slots / price


def kelly(rets, n: int) -> float:
    """Kelly fraction W - (1 - W) / R from the first n closed trade returns; NaN under 20 trades or no losers."""
    if n < 20:
        return math.nan
    wins = losses = 0
    sw = sl = 0.0
    for i in range(n):
        r = rets[i]
        if r > 0:
            wins += 1
            sw += r
        elif r < 0:
            losses += 1
            sl -= r
    if losses == 0 or wins == 0:
        return math.nan
    w = wins / n
    return w - (1.0 - w) / ((sw / wins) / (sl / losses))
