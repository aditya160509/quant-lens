"""Two engines over one fill model (docs/studio/plan/PLAN.md §5.1).

`vector`: one numba kernel over (bars x symbols) arrays; used for signal strategies, sweeps and robustness repeats.
`event`:  a plain Python bar loop with a strategy hook (`on_bar(ctx)`); used for Python strategies and as the cross-check.
Both take every price decision from `fills.py`; a test asserts they agree trade for trade.

Bar order (both engines):
1. open: pending exits fill, then pending entries in symbol order (next-open mode)
2. inside the bar: stops and targets (scale-out level before the final target)
3. close: time stop, breakeven, trailing stop, exit signal, delisting settle; borrow; mark equity
4. close: entry signals take free slots by score, sized on the equity just marked
5. same-close mode: the orders of steps 3 and 4 fill at this close instead of the next open
"""

from __future__ import annotations

import math
from dataclasses import astuple, dataclass, fields

import numpy as np

from . import fills
from .fills import STOP as F_STOP
from .fills import TARGET as F_TARGET

try:
    from numba import njit
except ImportError:  # pragma: no cover - fallback: the same kernel runs uncompiled
    def njit(*a, **k):
        return (lambda f: f) if not (a and callable(a[0])) else a[0]


@dataclass(frozen=True)
class Params:
    fill: float = 0  # 0 next open, 1 same close
    stop: float = 0.0  # fraction of entry price
    target: float = 0.0
    trail: float = 0.0
    time_stop: float = 0  # bars
    breakeven: float = 0.0  # move the stop to entry after this favourable move
    scale_at: float = 0.0  # take `scale_frac` off at this favourable move
    scale_frac: float = 0.0
    size_mode: float = fills.EQUAL
    size: float = 0.0
    max_positions: float = 0  # 0 = no cap
    commission_bps: float = 1.0
    commission_share: float = 0.0
    commission_min: float = 0.0
    slippage_bps: float = 2.0
    slippage_range: float = 0.0
    borrow_bps: float = 50.0  # a year, on short notional
    volume_cap: float = 0.0  # max share of the fill bar's volume; 0 = off
    delist_haircut: float = 0.0
    leverage: float = 1.0
    capital: float = 100_000.0


(P_FILL, P_STOP, P_TGT, P_TRAIL, P_TIME, P_BE, P_SCALE_AT, P_SCALE_FRAC, P_SIZE_MODE, P_SIZE, P_MAXPOS, P_COMM_BPS, P_COMM_SHARE,
 P_COMM_MIN, P_SLIP_BPS, P_SLIP_RANGE, P_BORROW, P_VOLCAP, P_HAIRCUT, P_LEV, P_CAPITAL) = range(len(fields(Params)))

# exit reasons
R_SIGNAL, R_STOP, R_TARGET, R_TRAIL, R_TIME, R_DELISTED, R_OPEN, R_BREAKEVEN, R_SCALE = 1, 2, 3, 4, 5, 6, 7, 8, 9
REASONS = {R_SIGNAL: "signal", R_STOP: "stop", R_TARGET: "target", R_TRAIL: "trailing stop", R_TIME: "time stop", R_DELISTED: "delisted",
           R_OPEN: "open at end", R_BREAKEVEN: "breakeven stop", R_SCALE: "scale out"}

# trade columns
(T_SYM, T_DIR, T_ENTRY_BAR, T_EXIT_BAR, T_ENTRY_PX, T_EXIT_PX, T_SHARES, T_PNL, T_RET, T_MAE, T_MFE, T_REASON, T_COSTS, T_SIGNAL_BAR,
 T_RISK) = range(15)
NT = 15

# vector-engine state columns per symbol
SH, EPX, EBAR, STOP, TGT, SCL, HW, LO, HI, ECOST, ESLIP, SKIND, PDIR, PSH, PEXIT, SIGBAR, LAST, RISK = range(18)
NS = 18
CASH, COSTS, NTR, UNFILLED, TRADED = range(5)

_fill_price = njit(cache=True)(fills.fill_price)
_commission = njit(cache=True)(fills.commission)
_exit_check = njit(cache=True)(fills.exit_check)
_size_shares = njit(cache=True)(fills.size_shares)
_kelly = njit(cache=True)(fills.kelly)


@njit(cache=True)
def _close(S, acct, trades, P, n, t, raw, reason, frac, bar_range):
    d = 1.0 if S[n, SH] > 0 else -1.0
    sh = abs(S[n, SH]) * frac
    px = _fill_price(raw, -d, P[P_SLIP_BPS], P[P_SLIP_RANGE], bar_range)
    comm = _commission(sh, px, P[P_COMM_BPS], P[P_COMM_SHARE], P[P_COMM_MIN])
    slip = sh * abs(px - raw)
    ecost, eslip, risk = S[n, ECOST] * frac, S[n, ESLIP] * frac, S[n, RISK] * frac
    pnl = d * sh * (px - S[n, EPX]) - comm - ecost
    acct[CASH] += d * sh * px - comm
    acct[COSTS] += comm + slip
    acct[TRADED] += sh * px
    lo, hi = min(S[n, LO], raw), max(S[n, HI], raw)
    k = int(acct[NTR])
    trades[k, T_SYM], trades[k, T_DIR], trades[k, T_ENTRY_BAR], trades[k, T_EXIT_BAR] = n, d, S[n, EBAR], t
    trades[k, T_ENTRY_PX], trades[k, T_EXIT_PX], trades[k, T_SHARES], trades[k, T_PNL] = S[n, EPX], px, sh, pnl
    trades[k, T_RET] = pnl / (sh * S[n, EPX])
    trades[k, T_MAE] = (lo / S[n, EPX] - 1.0) if d > 0 else -(hi / S[n, EPX] - 1.0)
    trades[k, T_MFE] = (hi / S[n, EPX] - 1.0) if d > 0 else -(lo / S[n, EPX] - 1.0)
    trades[k, T_REASON], trades[k, T_COSTS], trades[k, T_SIGNAL_BAR], trades[k, T_RISK] = reason, comm + slip + ecost + eslip, S[n, SIGBAR], risk
    acct[NTR] += 1
    if frac >= 1.0:
        S[n, SH] = 0.0
        S[n, PEXIT] = 0.0
    else:
        S[n, SH] -= d * sh
        S[n, ECOST] -= ecost
        S[n, ESLIP] -= eslip
        S[n, RISK] -= risk


@njit(cache=True)
def _mark(S, acct):
    eq, gross, net, npos = acct[CASH], 0.0, 0.0, 0
    for n in range(S.shape[0]):
        if S[n, SH] != 0.0:
            val = S[n, SH] * S[n, LAST]
            eq += val
            gross += abs(val)
            net += val
            npos += 1
    return eq, gross, net, npos


@njit(cache=True)
def _execute(S, acct, trades, P, t, px, rng, vol, stop_dist, has_dist):
    """Fill pending exits, then pending entries, at this row of prices."""
    N = S.shape[0]
    for n in range(N):
        if S[n, PEXIT] != 0.0 and S[n, SH] != 0.0 and np.isfinite(px[n]):
            _close(S, acct, trades, P, n, t, px[n], S[n, PEXIT], 1.0, rng[n])
    eq, gross, _, _ = _mark(S, acct)
    for n in range(N):
        d = S[n, PDIR]
        if d == 0.0 or not np.isfinite(px[n]):
            continue
        sh = S[n, PSH]
        if P[P_VOLCAP] > 0.0 and np.isfinite(vol[n]) and sh > P[P_VOLCAP] * vol[n]:
            sh = P[P_VOLCAP] * vol[n]
        p = _fill_price(px[n], d, P[P_SLIP_BPS], P[P_SLIP_RANGE], rng[n])
        avail = eq * P[P_LEV] - gross
        if sh * p > avail:
            sh = max(avail, 0.0) / p
        S[n, PDIR] = 0.0
        if sh < S[n, PSH] - 1e-9:
            acct[UNFILLED] += 1
        if sh <= 1e-9:
            continue
        comm = _commission(sh, p, P[P_COMM_BPS], P[P_COMM_SHARE], P[P_COMM_MIN])
        slip = sh * abs(p - px[n])
        acct[CASH] -= d * sh * p + comm
        acct[COSTS] += comm + slip
        acct[TRADED] += sh * p
        gross += sh * p
        dist = stop_dist[int(S[n, SIGBAR]), n] if has_dist else p * P[P_STOP]
        S[n, SH], S[n, EPX], S[n, EBAR], S[n, LAST] = d * sh, p, t, p
        S[n, STOP] = p - d * dist if dist > 0.0 else np.nan
        S[n, TGT] = p * (1.0 + d * P[P_TGT]) if P[P_TGT] > 0.0 else np.nan
        S[n, SCL] = p * (1.0 + d * P[P_SCALE_AT]) if P[P_SCALE_AT] > 0.0 and P[P_SCALE_FRAC] > 0.0 else np.nan
        S[n, HW], S[n, LO], S[n, HI] = p, p, p
        S[n, ECOST], S[n, ESLIP], S[n, SKIND], S[n, PEXIT] = comm, slip, R_STOP, 0.0
        S[n, RISK] = sh * dist if dist > 0.0 else np.nan


@njit(cache=True)
def _vector(o, h, l, c, v, entries, exits, score, has_score, stop_dist, has_dist, size_vol, has_vol, last_bar, P):
    T, N = c.shape
    S = np.zeros((N, NS))
    acct = np.zeros(5)
    acct[CASH] = P[P_CAPITAL]
    trades = np.empty((2 * np.count_nonzero(entries) + N + 1, NT))
    net, gross_eq, gross_x, net_x, npos_t, traded = np.empty(T), np.empty(T), np.empty(T), np.empty(T), np.empty(T), np.empty(T)
    cand = np.empty(N, dtype=np.int64)
    for t in range(T):
        acct[TRADED] = 0.0
        rng = h[t] - l[t]
        if P[P_FILL] == 0.0:
            _execute(S, acct, trades, P, t, o[t], rng, v[t], stop_dist, has_dist)
        for n in range(N):
            if S[n, SH] == 0.0 or not np.isfinite(c[t, n]):
                continue
            d = 1.0 if S[n, SH] > 0 else -1.0
            if S[n, EBAR] < t or P[P_FILL] == 0.0:  # a same-close entry has not lived through this bar
                level = S[n, SCL] if np.isfinite(S[n, SCL]) else S[n, TGT]
                reason, px = _exit_check(d, o[t, n], h[t, n], l[t, n], S[n, STOP], level)
                if reason == F_STOP:
                    _close(S, acct, trades, P, n, t, px, S[n, SKIND], 1.0, rng[n])
                elif reason == F_TARGET:
                    if np.isfinite(S[n, SCL]):
                        _close(S, acct, trades, P, n, t, px, R_SCALE, P[P_SCALE_FRAC], rng[n])
                        S[n, SCL] = np.nan
                        r2, px2 = _exit_check(d, o[t, n], h[t, n], l[t, n], np.nan, S[n, TGT])
                        if r2 == F_TARGET and S[n, SH] != 0.0:
                            _close(S, acct, trades, P, n, t, px2, R_TARGET, 1.0, rng[n])
                    else:
                        _close(S, acct, trades, P, n, t, px, R_TARGET, 1.0, rng[n])
            if S[n, SH] == 0.0:
                continue
            S[n, LO], S[n, HI], S[n, LAST] = min(S[n, LO], l[t, n]), max(S[n, HI], h[t, n]), c[t, n]
            if P[P_TIME] > 0.0 and t + 1 - S[n, EBAR] >= P[P_TIME] and S[n, PEXIT] == 0.0:
                S[n, PEXIT] = R_TIME
            best = h[t, n] if d > 0 else l[t, n]
            if P[P_BE] > 0.0 and S[n, SKIND] != R_BREAKEVEN and d * (best / S[n, EPX] - 1.0) >= P[P_BE] and not d * (S[n, STOP] - S[n, EPX]) >= 0.0:
                S[n, STOP], S[n, SKIND] = S[n, EPX], R_BREAKEVEN
            if P[P_TRAIL] > 0.0:
                S[n, HW] = max(S[n, HW], best) if d > 0 else min(S[n, HW], best)
                ts = S[n, HW] * (1.0 - d * P[P_TRAIL])
                if not d * (S[n, STOP] - ts) >= 0.0:
                    S[n, STOP], S[n, SKIND] = ts, R_TRAIL
            if S[n, PEXIT] == 0.0 and (exits[t, n] & (1 if d > 0 else 2)) != 0:
                S[n, PEXIT] = R_SIGNAL
        for n in range(N):
            if S[n, SH] != 0.0 and t == last_bar[n]:
                _close(S, acct, trades, P, n, t, c[t, n] * (1.0 - P[P_HAIRCUT]), R_DELISTED, 1.0, 0.0)
        if P[P_BORROW] > 0.0:
            for n in range(N):
                if S[n, SH] < 0.0:
                    b = -S[n, SH] * S[n, LAST] * P[P_BORROW] / 1e4 / 252.0
                    acct[CASH] -= b
                    acct[COSTS] += b
                    S[n, ECOST] += b
        eq, gx, nx, npos = _mark(S, acct)
        # entry signals
        k = 0
        held = 0
        for n in range(N):
            if S[n, SH] != 0.0 and S[n, PEXIT] == 0.0:
                held += 1
            if S[n, PDIR] != 0.0:
                held += 1
            if entries[t, n] != 0 and S[n, SH] == 0.0 and S[n, PDIR] == 0.0 and t < last_bar[n] and np.isfinite(c[t, n]):
                cand[k] = n
                k += 1
        if k > 0:
            slots = k if P[P_MAXPOS] <= 0.0 else min(k, max(int(P[P_MAXPOS]) - held, 0))
            order = cand[:k]
            if has_score and slots < k:
                sc = np.empty(k)
                for i in range(k):
                    sc[i] = -score[t, cand[i]] if np.isfinite(score[t, cand[i]]) else np.inf
                order = cand[:k][np.argsort(sc, kind="mergesort")]
            per = min(P[P_MAXPOS], float(N)) if P[P_MAXPOS] > 0.0 else float(N)
            kf = _kelly(trades[:, T_RET], int(acct[NTR])) if int(P[P_SIZE_MODE]) == 7 else np.nan
            mean_sc = np.nan
            if int(P[P_SIZE_MODE]) == 6 and has_score:
                tot, cnt = 0.0, 0
                for i in range(slots):
                    v_ = score[t, order[i]]
                    if np.isfinite(v_) and v_ > 0:
                        tot += v_
                        cnt += 1
                mean_sc = tot / cnt if cnt else np.nan
            for i in range(slots):
                n = order[i]
                dist = stop_dist[t, n] if has_dist else c[t, n] * P[P_STOP]
                mult = kf
                if int(P[P_SIZE_MODE]) == 6:
                    v_ = score[t, n] if has_score else np.nan
                    mult = min(max(v_ / mean_sc, 0.0), 3.0) if np.isfinite(v_) and mean_sc > 0 else 1.0
                sh = _size_shares(int(P[P_SIZE_MODE]), P[P_SIZE], eq, c[t, n], dist, per, size_vol[t, n] if has_vol else np.nan, mult)
                if sh > 0.0:
                    S[n, PDIR], S[n, PSH], S[n, SIGBAR] = entries[t, n], sh, t
        if P[P_FILL] != 0.0:
            _execute(S, acct, trades, P, t, c[t], rng, v[t], stop_dist, has_dist)
            eq, gx, nx, npos = _mark(S, acct)
        net[t], gross_eq[t], gross_x[t], net_x[t], npos_t[t], traded[t] = eq, eq + acct[COSTS], gx / eq, nx / eq, npos, acct[TRADED]
    for n in range(N):  # still open at the end: marked, not sold
        if S[n, SH] != 0.0:
            d = 1.0 if S[n, SH] > 0 else -1.0
            sh, k = abs(S[n, SH]), int(acct[NTR])
            pnl = d * sh * (S[n, LAST] - S[n, EPX]) - S[n, ECOST]
            trades[k, T_SYM], trades[k, T_DIR], trades[k, T_ENTRY_BAR], trades[k, T_EXIT_BAR] = n, d, S[n, EBAR], T - 1
            trades[k, T_ENTRY_PX], trades[k, T_EXIT_PX], trades[k, T_SHARES], trades[k, T_PNL] = S[n, EPX], S[n, LAST], sh, pnl
            trades[k, T_RET] = pnl / (sh * S[n, EPX])
            trades[k, T_MAE] = (S[n, LO] / S[n, EPX] - 1.0) if d > 0 else -(S[n, HI] / S[n, EPX] - 1.0)
            trades[k, T_MFE] = (S[n, HI] / S[n, EPX] - 1.0) if d > 0 else -(S[n, LO] / S[n, EPX] - 1.0)
            trades[k, T_REASON], trades[k, T_COSTS], trades[k, T_SIGNAL_BAR], trades[k, T_RISK] = R_OPEN, S[n, ECOST] + S[n, ESLIP], S[n, SIGBAR], S[n, RISK]
            acct[NTR] += 1
    return trades[: int(acct[NTR])], net, gross_eq, gross_x, net_x, npos_t, traded, acct[UNFILLED]


# ---------------------------------------------------------------------------
# event engine


@dataclass
class Position:
    shares: float  # signed
    entry_px: float
    entry_bar: int
    signal_bar: int
    stop: float
    target: float
    scale: float
    high_water: float
    lo: float
    hi: float
    cost: float  # entry commission and borrow, already paid in cash
    slip: float
    risk: float
    stop_kind: int = R_STOP
    last: float = 0.0
    exit_reason: int = 0  # pending exit at the next fill


class Context:
    """What a strategy sees at the close of bar t: data up to t only, and two order calls."""

    def __init__(self, engine: EventEngine):
        self._e = engine
        self.t = 0

    def history(self, field: str, symbol: int, n: int = 1) -> np.ndarray:
        return self._e.bars[field][max(self.t + 1 - n, 0): self.t + 1, symbol]

    def position(self, symbol: int) -> float:
        p = self._e.positions.get(symbol)
        return p.shares if p else 0.0

    def enter(self, symbol: int, direction: int = 1) -> None:
        self._e.wants[symbol] = direction

    def exit(self, symbol: int) -> None:
        p = self._e.positions.get(symbol)
        if p and not p.exit_reason:
            p.exit_reason = R_SIGNAL


class SignalStrategy:
    """Entry and exit arrays as an `on_bar` strategy."""

    def __init__(self, entries: np.ndarray, exits: np.ndarray):
        self.entries, self.exits = entries, exits

    def on_bar(self, ctx: Context) -> None:
        t = ctx.t
        for n in np.flatnonzero(self.exits[t]):
            pos = ctx.position(int(n))
            if pos and self.exits[t, n] & (1 if pos > 0 else 2):
                ctx.exit(int(n))
        for n in np.flatnonzero(self.entries[t]):
            ctx.enter(int(n), int(self.entries[t, n]))


class EventEngine:
    def __init__(self, bars: dict[str, np.ndarray], params: Params, score=None, stop_dist=None, size_vol=None):
        self.bars, self.p, self.score, self.stop_dist, self.size_vol = bars, params, score, stop_dist, size_vol
        self.positions: dict[int, Position] = {}
        self.pending: dict[int, tuple[int, float, int]] = {}  # symbol -> (direction, shares, signal bar)
        self.wants: dict[int, int] = {}
        self.cash, self.costs, self.unfilled, self.traded = params.capital, 0.0, 0, 0.0
        self.trades: list[tuple] = []

    def _close(self, n: int, t: int, raw: float, reason: int, frac: float, bar_range: float) -> None:
        p, pos = self.p, self.positions[n]
        d = 1.0 if pos.shares > 0 else -1.0
        sh = abs(pos.shares) * frac
        px = fills.fill_price(raw, -d, p.slippage_bps, p.slippage_range, bar_range)
        comm = fills.commission(sh, px, p.commission_bps, p.commission_share, p.commission_min)
        slip = sh * abs(px - raw)
        ecost, eslip, risk = pos.cost * frac, pos.slip * frac, pos.risk * frac
        pnl = d * sh * (px - pos.entry_px) - comm - ecost
        self.cash += d * sh * px - comm
        self.costs += comm + slip
        self.traded += sh * px
        lo, hi = min(pos.lo, raw), max(pos.hi, raw)
        mae = (lo / pos.entry_px - 1.0) if d > 0 else -(hi / pos.entry_px - 1.0)
        mfe = (hi / pos.entry_px - 1.0) if d > 0 else -(lo / pos.entry_px - 1.0)
        self.trades.append((n, d, pos.entry_bar, t, pos.entry_px, px, sh, pnl, pnl / (sh * pos.entry_px), mae, mfe, reason,
                            comm + slip + ecost + eslip, pos.signal_bar, risk))
        if frac >= 1.0:
            del self.positions[n]
        else:
            pos.shares -= d * sh
            pos.cost -= ecost
            pos.slip -= eslip
            pos.risk -= risk

    def _mark(self) -> tuple[float, float, float, int]:
        eq, gross, net = self.cash, 0.0, 0.0
        for n in sorted(self.positions):
            val = self.positions[n].shares * self.positions[n].last
            eq, gross, net = eq + val, gross + abs(val), net + val
        return eq, gross, net, len(self.positions)

    def _execute(self, t: int, px: np.ndarray, rng: np.ndarray) -> None:
        p, vol = self.p, self.bars["volume"][t]
        for n in sorted(self.positions):
            if self.positions[n].exit_reason and math.isfinite(px[n]):
                self._close(n, t, px[n], self.positions[n].exit_reason, 1.0, rng[n])
        eq, gross, _, _ = self._mark()
        for n in sorted(self.pending):
            if not math.isfinite(px[n]):
                continue
            d, want, sigbar = self.pending.pop(n)
            sh = want
            if p.volume_cap > 0 and math.isfinite(vol[n]) and sh > p.volume_cap * vol[n]:
                sh = p.volume_cap * vol[n]
            price = fills.fill_price(px[n], d, p.slippage_bps, p.slippage_range, rng[n])
            avail = eq * p.leverage - gross
            if sh * price > avail:
                sh = max(avail, 0.0) / price
            if sh < want - 1e-9:
                self.unfilled += 1
            if sh <= 1e-9:
                continue
            comm = fills.commission(sh, price, p.commission_bps, p.commission_share, p.commission_min)
            slip = sh * abs(price - px[n])
            self.cash -= d * sh * price + comm
            self.costs += comm + slip
            self.traded += sh * price
            gross += sh * price
            dist = self.stop_dist[sigbar, n] if self.stop_dist is not None else price * p.stop
            self.positions[n] = Position(
                shares=d * sh, entry_px=price, entry_bar=t, signal_bar=sigbar, stop=price - d * dist if dist > 0 else math.nan,
                target=price * (1 + d * p.target) if p.target > 0 else math.nan,
                scale=price * (1 + d * p.scale_at) if p.scale_at > 0 and p.scale_frac > 0 else math.nan,
                high_water=price, lo=price, hi=price, cost=comm, slip=slip, risk=sh * dist if dist > 0 else math.nan, last=price)

    def run(self, strategy) -> tuple:
        p, b = self.p, self.bars
        o, h, l, c = b["open"], b["high"], b["low"], b["close"]
        T, N = c.shape
        last_bar = _last_bar(c)
        ctx = Context(self)
        out = np.empty((6, T))
        for t in range(T):
            self.traded = 0.0
            rng = h[t] - l[t]
            if p.fill == 0:
                self._execute(t, o[t], rng)
            for n in sorted(self.positions):
                pos = self.positions[n]
                if not math.isfinite(c[t, n]):
                    continue
                d = 1.0 if pos.shares > 0 else -1.0
                if pos.entry_bar < t or p.fill == 0:
                    level = pos.scale if math.isfinite(pos.scale) else pos.target
                    reason, px = fills.exit_check(d, o[t, n], h[t, n], l[t, n], pos.stop, level)
                    if reason == fills.STOP:
                        self._close(n, t, px, pos.stop_kind, 1.0, rng[n])
                    elif reason == fills.TARGET:
                        if math.isfinite(pos.scale):
                            self._close(n, t, px, R_SCALE, p.scale_frac, rng[n])
                            pos.scale = math.nan
                            r2, px2 = fills.exit_check(d, o[t, n], h[t, n], l[t, n], math.nan, pos.target)
                            if r2 == fills.TARGET and n in self.positions:
                                self._close(n, t, px2, R_TARGET, 1.0, rng[n])
                        else:
                            self._close(n, t, px, R_TARGET, 1.0, rng[n])
                if n not in self.positions:
                    continue
                pos.lo, pos.hi, pos.last = min(pos.lo, l[t, n]), max(pos.hi, h[t, n]), c[t, n]
                if p.time_stop > 0 and t + 1 - pos.entry_bar >= p.time_stop and not pos.exit_reason:
                    pos.exit_reason = R_TIME
                best = h[t, n] if d > 0 else l[t, n]
                if p.breakeven > 0 and pos.stop_kind != R_BREAKEVEN and d * (best / pos.entry_px - 1.0) >= p.breakeven and not d * (pos.stop - pos.entry_px) >= 0:
                    pos.stop, pos.stop_kind = pos.entry_px, R_BREAKEVEN
                if p.trail > 0:
                    pos.high_water = max(pos.high_water, best) if d > 0 else min(pos.high_water, best)
                    ts = pos.high_water * (1.0 - d * p.trail)
                    if not d * (pos.stop - ts) >= 0:
                        pos.stop, pos.stop_kind = ts, R_TRAIL
            ctx.t = t
            self.wants = {}
            strategy.on_bar(ctx)
            for n in sorted(self.positions):
                if t == last_bar[n]:
                    self._close(n, t, c[t, n] * (1.0 - p.delist_haircut), R_DELISTED, 1.0, 0.0)
            if p.borrow_bps > 0:
                for n in sorted(self.positions):
                    pos = self.positions[n]
                    if pos.shares < 0:
                        fee = -pos.shares * pos.last * p.borrow_bps / 1e4 / 252.0
                        self.cash -= fee
                        self.costs += fee
                        pos.cost += fee
            eq, gx, nx, npos = self._mark()
            cands = [n for n in sorted(self.wants) if n not in self.positions and n not in self.pending and t < last_bar[n] and math.isfinite(c[t, n])]
            if cands:
                held = sum(1 for q in self.positions.values() if not q.exit_reason) + len(self.pending)
                slots = len(cands) if p.max_positions <= 0 else min(len(cands), max(int(p.max_positions) - held, 0))
                if self.score is not None and slots < len(cands):
                    cands.sort(key=lambda n: (-self.score[t, n] if math.isfinite(self.score[t, n]) else math.inf, n))
                per = min(p.max_positions, float(N)) if p.max_positions > 0 else float(N)
                kf = fills.kelly([x[8] for x in self.trades], len(self.trades)) if int(p.size_mode) == fills.KELLY else math.nan
                pos_sc = [self.score[t, n] for n in cands[:slots] if self.score is not None and math.isfinite(self.score[t, n]) and self.score[t, n] > 0]
                mean_sc = sum(pos_sc) / len(pos_sc) if pos_sc else math.nan
                for n in cands[:slots]:
                    dist = self.stop_dist[t, n] if self.stop_dist is not None else c[t, n] * p.stop
                    mult = kf
                    if int(p.size_mode) == fills.SCORE:
                        v_ = self.score[t, n] if self.score is not None else math.nan
                        mult = min(max(v_ / mean_sc, 0.0), 3.0) if math.isfinite(v_) and mean_sc > 0 else 1.0
                    sh = fills.size_shares(int(p.size_mode), p.size, eq, c[t, n], dist, per, self.size_vol[t, n] if self.size_vol is not None else math.nan, mult)
                    if sh > 0:
                        self.pending[n] = (self.wants[n], sh, t)
            if p.fill != 0:
                self._execute(t, c[t], rng)
                eq, gx, nx, npos = self._mark()
            out[:, t] = eq, eq + self.costs, gx / eq, nx / eq, npos, self.traded
        for n in sorted(self.positions):
            pos = self.positions[n]
            d = 1.0 if pos.shares > 0 else -1.0
            sh = abs(pos.shares)
            pnl = d * sh * (pos.last - pos.entry_px) - pos.cost
            mae = (pos.lo / pos.entry_px - 1.0) if d > 0 else -(pos.hi / pos.entry_px - 1.0)
            mfe = (pos.hi / pos.entry_px - 1.0) if d > 0 else -(pos.lo / pos.entry_px - 1.0)
            self.trades.append((n, d, pos.entry_bar, T - 1, pos.entry_px, pos.last, sh, pnl, pnl / (sh * pos.entry_px), mae, mfe, R_OPEN,
                                pos.cost + pos.slip, pos.signal_bar, pos.risk))
        trades = np.array(self.trades, dtype=np.float64).reshape(-1, NT)
        return trades, *out, float(self.unfilled)


# ---------------------------------------------------------------------------


@dataclass
class Result:
    trades: np.ndarray  # (K, NT), in the order they closed
    equity: np.ndarray  # net of costs, marked at each close
    gross_equity: np.ndarray  # equity plus every cost paid so far
    gross_exposure: np.ndarray
    net_exposure: np.ndarray
    positions: np.ndarray
    traded: np.ndarray  # notional traded per bar
    unfilled: int


def _last_bar(close: np.ndarray) -> np.ndarray:
    """Last bar each name trades. A name alive on the final bar never delists inside the test (index T)."""
    ok, T = np.isfinite(close), close.shape[0]
    last = np.where(ok.any(axis=0), T - 1 - np.argmax(ok[::-1], axis=0), -1)
    return np.where(last == T - 1, T, last).astype(np.int64)


_EMPTY2 = np.zeros((1, 1))


def run(bars: dict[str, np.ndarray], entries: np.ndarray, exits: np.ndarray, params: Params, *, engine: str = "vector",
        score: np.ndarray | None = None, stop_dist: np.ndarray | None = None, strategy=None, size_vol: np.ndarray | None = None) -> Result:
    """bars: open, high, low, close, volume as (bars x symbols) float arrays, NaN where a name has no bar.
    entries: int8, +1 long, -1 short. exits: int8 bits, 1 closes longs, 2 closes shorts.
    """
    o, h, l, c, v = (np.ascontiguousarray(bars[k], dtype=np.float64) for k in ("open", "high", "low", "close", "volume"))
    entries, exits = np.ascontiguousarray(entries, dtype=np.int8), np.ascontiguousarray(exits, dtype=np.int8)
    if engine == "event" or strategy is not None:
        eng = EventEngine({"open": o, "high": h, "low": l, "close": c, "volume": v}, params, score, stop_dist, size_vol)
        out = eng.run(strategy or SignalStrategy(entries, exits))
    else:
        out = _vector(o, h, l, c, v, entries, exits, score if score is not None else _EMPTY2, score is not None,
                      stop_dist if stop_dist is not None else _EMPTY2, stop_dist is not None,
                      np.ascontiguousarray(size_vol, dtype=np.float64) if size_vol is not None else _EMPTY2, size_vol is not None,
                      _last_bar(c), np.array(astuple(params), dtype=np.float64))
    return Result(*out[:7], unfilled=int(out[7]))
