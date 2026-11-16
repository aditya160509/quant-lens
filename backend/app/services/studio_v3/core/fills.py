"""The one fill model. Plain scalar functions: the vector engine compiles them with numba, the event engine calls them as is.

Rules (printed on every run):
- A signal at close t fills at the open of t+1 (default) or at close t ("same close", optimistic).
- A stop or target gapped through at the open fills at the open, not at its own price.
- When a stop and a target are both inside one bar the stop fills first (worse first), unless hourly bars for that day say otherwise.
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


def magnify(hh, hl, start: int, end: int, d: float, stop: float, target: float) -> int:
    """Walk the day's hourly bars: which level was touched first. Both inside one hour, or neither: the stop (worse first)."""
    for i in range(start, end):
        hit_stop = hl[i] <= stop if d > 0 else hh[i] >= stop
        hit_target = hh[i] >= target if d > 0 else hl[i] <= target
        if hit_stop:
            return STOP
        if hit_target:
            return TARGET
    return STOP


def exit_check(d: float, o: float, h: float, low: float, stop: float, target: float, first: int):
    """(reason, raw price) for a position of direction d inside one bar. NaN level = not set. `first` is the magnifier's answer or NONE."""
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
    if hit_stop and hit_target:
        if first == TARGET:
            return TARGET, target
        return STOP, stop
    if hit_stop:
        return STOP, stop
    if hit_target:
        return TARGET, target
    return NONE, math.nan


# Sizing modes
SHARES, CASH, PCT_EQUITY, RISK, EQUAL = 0, 1, 2, 3, 4


def size_shares(mode: int, value: float, equity: float, price: float, stop_distance: float, slots: float) -> float:
    """Shares to order, decided at the signal bar's close. Risk sizing needs a stop; without one it orders nothing."""
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
    return equity / slots / price
