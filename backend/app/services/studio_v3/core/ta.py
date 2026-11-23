# ruff: noqa: RUF012  (indicator classes declare inputs, plots and levels as plain class dicts, the protocol users copy)
"""TradingView-matching technical analysis for Python strategies and indicators: `from studio import ta`.

Functions take whole arrays (oldest first) and return arrays of the same length, NaN while warming up. Formulas follow Pine's ta.*:
ema and rma seed with the SMA of the first `length` values, atr's first true range is high - low, stdev is the population one,
roc is in percent. Leading NaNs (a symbol that lists later) are skipped, so a series starts warming up on its first real value.
Smoothing functions also accept (bars x symbols) arrays. The backend's formula rules call the same functions, so a rule, a Python
strategy and the chart read one set of numbers.

Ready indicator classes at the bottom (`self.use(ta.Supertrend, factor=3)`) compute once over the whole history with `compute(bars)`.
Standalone on purpose: the strategy sandbox loads this file by path with numpy as its only import.
"""

import math

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

nan = math.nan


def _a(x):
    return np.asarray(x, dtype=float)


def _window(x, n, fn):
    a = _a(x)
    out = np.full(a.shape, nan)
    if n < 1 or a.shape[0] < n:
        return out
    out[n - 1:] = fn(sliding_window_view(a, n, axis=0), -1)
    return out


def _smooth(x, n, alpha):
    """Pine's rma/ema: each column seeds on the mean of its first n finite values, then smooths exponentially.
    A missing value inside the series keeps the last smoothed value (Pine ignores na)."""
    a = _a(x)
    flat = a.ndim == 1
    v = a[:, None] if flat else a
    rows, cols = v.shape
    out = np.full(v.shape, nan)
    fin = np.isfinite(v)
    start = np.where(fin.any(axis=0), fin.argmax(axis=0), rows)
    seed = start + n - 1
    for j in np.flatnonzero(seed < rows):
        out[seed[j], j] = v[start[j]:seed[j] + 1, j].mean()
    live_from = int(seed.min()) + 1 if cols else rows
    for t in range(live_from, rows):
        live = seed < t
        prev, cur = out[t - 1, live], v[t, live]
        out[t, live] = np.where(np.isfinite(cur), prev + alpha * (cur - prev), prev)
    return out[:, 0] if flat else out


def _shift(x, n=1):
    a = _a(x)
    out = np.full_like(a, nan)
    if n == 0:
        return a.copy()
    out[n:] = a[:-n]
    return out


# --- moving averages -----------------------------------------------------------------


def sma(x, length):
    return _window(x, length, np.mean)


def ema(x, length):
    return _smooth(x, length, 2.0 / (length + 1))


def rma(x, length):
    """Wilder's moving average (alpha = 1 / length), used by rsi, atr and dmi."""
    return _smooth(x, length, 1.0 / length)


def wma(x, length):
    w = np.arange(1, length + 1, dtype=float)
    return _window(x, length, lambda v, axis: (v * w).sum(axis=axis) / w.sum())


def hma(x, length):
    return wma(2 * wma(x, length // 2) - wma(x, length), math.isqrt(length))


def vwma(x, volume, length):
    return sma(_a(x) * _a(volume), length) / sma(volume, length)


def alma(x, length, offset=0.85, sigma=6.0):
    m, s = offset * (length - 1), length / sigma
    w = np.exp(-((np.arange(length) - m) ** 2) / (2 * s * s))
    return _window(x, length, lambda v, axis: (v * w).sum(axis=axis) / w.sum())


def swma(x):
    w = np.array([1, 2, 2, 1], dtype=float) / 6
    return _window(x, 4, lambda v, axis: (v * w).sum(axis=axis))


# --- statistics ----------------------------------------------------------------------


def stdev(x, length):
    """Population standard deviation, as Pine's ta.stdev and Bollinger Bands use."""
    return _window(x, length, lambda v, axis: v.std(axis=axis))


def variance(x, length):
    return _window(x, length, lambda v, axis: v.var(axis=axis))


def highest(x, length):
    return _window(x, length, np.max)


def lowest(x, length):
    return _window(x, length, np.min)


def median(x, length):
    return _window(x, length, np.median)


def dev(x, length):
    """Mean absolute deviation from the window's mean (the CCI denominator)."""
    return _window(x, length, lambda v, axis: np.abs(v - v.mean(axis=axis, keepdims=True)).mean(axis=axis))


def linreg(x, length, offset=0):
    """Least-squares line through the last `length` values, read at `length - 1 - offset`."""
    i = np.arange(length, dtype=float)

    def fit(v, axis):
        slope = ((i - i.mean()) * (v - v.mean(axis=axis, keepdims=True))).sum(axis=axis) / ((i - i.mean()) ** 2).sum()
        return v.mean(axis=axis) - slope * i.mean() + slope * (length - 1 - offset)

    return _window(x, length, fit)


def correlation(a, b, length):
    a, b = _a(a), _a(b)
    ma, mb = sma(a, length), sma(b, length)
    cov = sma(a * b, length) - ma * mb
    with np.errstate(invalid="ignore", divide="ignore"):
        return cov / (stdev(a, length) * stdev(b, length))


def percentrank(x, length):
    """Percent of the previous `length` values at or below this one."""
    a = _a(x)
    out = np.full(a.shape, nan)
    for t in range(length, len(a)):
        out[t] = 100.0 * (a[t - length:t] <= a[t]).sum() / length
    return out


# --- changes and crosses ---------------------------------------------------------------


def change(x, length=1):
    return _a(x) - _shift(x, length)


def mom(x, length):
    return change(x, length)


def roc(x, length):
    """Rate of change in percent."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * change(x, length) / _shift(x, length)


def crossover(a, b):
    a, b = np.broadcast_arrays(_a(a), _a(b))
    return (a > b) & (_shift(a) <= _shift(b))


def crossunder(a, b):
    a, b = np.broadcast_arrays(_a(a), _a(b))
    return (a < b) & (_shift(a) >= _shift(b))


def cross(a, b):
    return crossover(a, b) | crossunder(a, b)


def barssince(cond):
    c = np.asarray(cond, dtype=bool)
    out, last = np.full(len(c), nan), None
    for t, hit in enumerate(c):
        last = t if hit else last
        out[t] = nan if last is None else t - last
    return out


def valuewhen(cond, x, occurrence=0):
    c, a = np.asarray(cond, dtype=bool), _a(x)
    out, seen = np.full(len(a), nan), []
    for t in range(len(a)):
        if c[t]:
            seen.append(a[t])
        out[t] = seen[-1 - occurrence] if len(seen) > occurrence else nan
    return out


def pivothigh(x, left, right):
    """The pivot's value on the bar where it is confirmed (`right` bars later), NaN elsewhere; never looks ahead."""
    a = _a(x)
    out = np.full(len(a), nan)
    for t in range(left + right, len(a)):
        c = t - right
        w = a[c - left:t + 1]
        if np.isfinite(a[c]) and a[c] == np.nanmax(w) and (w[:left] < a[c]).all() and (w[left + 1:] < a[c]).all():
            out[t] = a[c]
    return out


def pivotlow(x, left, right):
    return -pivothigh(-_a(x), left, right)


# --- oscillators and volatility ----------------------------------------------------------


def rsi(x, length):
    d = np.diff(_a(x), axis=0, prepend=nan)
    up = rma(np.where(np.isfinite(d), np.maximum(d, 0.0), nan), length)
    down = rma(np.where(np.isfinite(d), np.maximum(-d, 0.0), nan), length)
    with np.errstate(divide="ignore", invalid="ignore"):
        # A window with no moves at all reads 50; Pine would read 100. Prices that never move are rare enough to prefer the neutral value.
        return np.where(down == 0, np.where(up == 0, 50.0, 100.0), 100.0 - 100.0 / (1.0 + up / down)) + up * 0


def tr(high, low, close):
    """True range; the first bar (no previous close) is high - low."""
    prev = _shift(close)
    h, lo = _a(high), _a(low)
    return np.fmax(h - lo, np.fmax(np.abs(h - prev), np.abs(lo - prev)))


def atr(high, low, close, length):
    return rma(tr(high, low, close), length)


def macd(x, fast=12, slow=26, signal=9):
    """(macd, signal, histogram). The signal line seeds on the first `signal` finite MACD values."""
    line = ema(x, fast) - ema(x, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def bb(x, length=20, mult=2.0):
    """Bollinger Bands: (basis, upper, lower)."""
    basis, d = sma(x, length), mult * stdev(x, length)
    return basis, basis + d, basis - d


def bbw(x, length=20, mult=2.0):
    basis, upper, lower = bb(x, length, mult)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * (upper - lower) / basis


def kc(high, low, close, length=20, mult=2.0, use_true_range=True):
    """Keltner Channels: (basis, upper, lower), EMA basis and an EMA of the true range."""
    basis = ema(close, length)
    span = ema(tr(high, low, close) if use_true_range else _a(high) - _a(low), length)
    return basis, basis + mult * span, basis - mult * span


def donchian(high, low, length=20):
    """(middle, upper, lower)."""
    upper, lower = highest(high, length), lowest(low, length)
    return (upper + lower) / 2, upper, lower


def stoch(close, high, low, length=14):
    """Raw %K: 100 * (close - lowest low) / (highest high - lowest low)."""
    lo, hi = lowest(low, length), highest(high, length)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * (_a(close) - lo) / (hi - lo)


def cci(x, length=20):
    with np.errstate(invalid="ignore", divide="ignore"):
        return (_a(x) - sma(x, length)) / (0.015 * dev(x, length))


def wpr(high, low, close, length=14):
    hi, lo = highest(high, length), lowest(low, length)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * (_a(close) - hi) / (hi - lo)


def cmo(x, length):
    m = change(x)
    up, down = _window(np.where(m >= 0, m, 0.0), length, np.sum), _window(np.where(m >= 0, 0.0, -m), length, np.sum)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * (up - down) / (up + down)


def mfi(x, volume, length=14):
    """Money Flow Index on a source (Pine passes hlc3)."""
    a, v, c = _a(x), _a(volume), change(x)
    upper = _window(np.where(c <= 0, 0.0, v * a), length, np.sum)
    lower = _window(np.where(c >= 0, 0.0, v * a), length, np.sum)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 - 100.0 / (1.0 + upper / lower)


def tsi(x, short=13, long=25):
    m = change(x)
    with np.errstate(invalid="ignore", divide="ignore"):
        return ema(ema(m, long), short) / ema(ema(np.abs(m), long), short)


def obv(close, volume):
    c = change(close)
    step = np.where(c > 0, _a(volume), np.where(c < 0, -_a(volume), 0.0))
    return np.cumsum(np.nan_to_num(step))


def vwap(x, volume, anchor=None):
    """Cumulative volume-weighted price, restarting wherever `anchor` is true (for example a new month)."""
    a, v = _a(x), np.nan_to_num(_a(volume))
    out, pv, vol = np.full(len(a), nan), 0.0, 0.0
    for t in range(len(a)):
        if anchor is not None and anchor[t]:
            pv, vol = 0.0, 0.0
        if np.isfinite(a[t]):
            pv, vol = pv + a[t] * v[t], vol + v[t]
        out[t] = pv / vol if vol else nan
    return out


def dmi(high, low, close, di_length=14, adx_smoothing=14):
    """(+DI, -DI, ADX) with Wilder smoothing."""
    h, lo = _a(high), _a(low)
    up, down = change(h), -change(lo)
    plus = np.where((up > down) & (up > 0), up, 0.0)
    minus = np.where((down > up) & (down > 0), down, 0.0)
    plus[~np.isfinite(up)], minus[~np.isfinite(up)] = nan, nan
    r = rma(tr(h, lo, close), di_length)
    with np.errstate(invalid="ignore", divide="ignore"):
        p, m = 100.0 * rma(plus, di_length) / r, 100.0 * rma(minus, di_length) / r
        s = p + m
        adx = 100.0 * rma(np.abs(p - m) / np.where(s == 0, 1.0, s), adx_smoothing)
    return p, m, adx


def supertrend(high, low, close, factor=3.0, atr_period=10):
    """(line, direction); direction -1 is an uptrend (line under price), 1 a downtrend, as in Pine."""
    h, lo, c = _a(high), _a(low), _a(close)
    a = atr(h, lo, c, atr_period)
    src = (h + lo) / 2
    up_band, dn_band = src - factor * a, src + factor * a
    line, direction = np.full(len(c), nan), np.full(len(c), nan)
    lower_prev = upper_prev = st_prev = nan
    for t in range(len(c)):
        if not np.isfinite(a[t]):
            continue
        lower, upper = up_band[t], dn_band[t]
        if np.isfinite(lower_prev):
            lower = lower if lower > lower_prev or c[t - 1] < lower_prev else lower_prev
            upper = upper if upper < upper_prev or c[t - 1] > upper_prev else upper_prev
        if not np.isfinite(st_prev):
            d = 1.0
        elif st_prev == upper_prev:
            d = -1.0 if c[t] > upper else 1.0
        else:
            d = 1.0 if c[t] < lower else -1.0
        line[t], direction[t] = (lower if d < 0 else upper), d
        lower_prev, upper_prev, st_prev = lower, upper, line[t]
    return line, direction


def sar(high, low, close, start=0.02, inc=0.02, maximum=0.2):
    """Wilder's Parabolic SAR, following Pine's reference loop."""
    h, lo, c = _a(high), _a(low), _a(close)
    out = np.full(len(c), nan)
    if len(c) < 2:
        return out
    below = c[1] > c[0]
    extreme, result, accel = (h[1], lo[0], start) if below else (lo[1], h[0], start)
    for t in range(1, len(c)):
        first = t == 1
        result = result + accel * (extreme - result)
        if below and result > lo[t]:
            first, below, result, extreme, accel = True, False, max(h[t], extreme), lo[t], start
        elif not below and result < h[t]:
            first, below, result, extreme, accel = True, True, min(lo[t], extreme), h[t], start
        if not first:
            if below and h[t] > extreme:
                extreme, accel = h[t], min(accel + inc, maximum)
            elif not below and lo[t] < extreme:
                extreme, accel = lo[t], min(accel + inc, maximum)
        if below:
            result = min(result, lo[t - 1], lo[t - 2]) if t > 1 else min(result, lo[t - 1])
        else:
            result = max(result, h[t - 1], h[t - 2]) if t > 1 else max(result, h[t - 1])
        out[t] = result
    return out


def ichimoku(high, low, conversion=9, base=26, span_b=52):
    """(conversion, base, span A, span B) as known on each bar; the chart's 26-bar forward shift is a drawing offset, not data."""
    def mid(n):
        return (highest(high, n) + lowest(low, n)) / 2

    conv, bl = mid(conversion), mid(base)
    return conv, bl, (conv + bl) / 2, mid(span_b)


# --- ready indicators for self.use(...) ----------------------------------------------------------
# Each computes every output once over the full history; values at a bar depend only on that bar and earlier ones.

UP, DOWN, BLUE, ORANGE, GREY = "#22ab94", "#f23645", "#2962ff", "#ff6d00", "#787b86"


class SMA:
    inputs = {"length": (20, 1, 500, 1)}
    chart = "main"
    plots = {"sma": {"color": BLUE}}

    def compute(self, bars):
        return {"sma": sma(bars["close"], self.inputs["length"])}


class EMA:
    inputs = {"length": (20, 1, 500, 1)}
    chart = "main"
    plots = {"ema": {"color": ORANGE}}

    def compute(self, bars):
        return {"ema": ema(bars["close"], self.inputs["length"])}


class HMA:
    inputs = {"length": (9, 2, 500, 1)}
    chart = "main"
    plots = {"hma": {"color": "#7e57c2"}}

    def compute(self, bars):
        return {"hma": hma(bars["close"], self.inputs["length"])}


class BB:
    inputs = {"length": (20, 2, 300, 1), "mult": (2.0, 0.5, 5.0, 0.1)}
    chart = "main"
    plots = {"basis": {"color": ORANGE}, "upper": {"color": BLUE}, "lower": {"color": BLUE}}
    fills = [("upper", "lower")]

    def compute(self, bars):
        b, u, lo = bb(bars["close"], self.inputs["length"], self.inputs["mult"])
        return {"basis": b, "upper": u, "lower": lo}


class KC:
    inputs = {"length": (20, 2, 300, 1), "mult": (2.0, 0.5, 5.0, 0.1)}
    chart = "main"
    plots = {"basis": {"color": BLUE}, "upper": {"color": BLUE}, "lower": {"color": BLUE}}
    fills = [("upper", "lower")]

    def compute(self, bars):
        b, u, lo = kc(bars["high"], bars["low"], bars["close"], self.inputs["length"], self.inputs["mult"])
        return {"basis": b, "upper": u, "lower": lo}


class Donchian:
    inputs = {"length": (20, 2, 300, 1)}
    chart = "main"
    plots = {"middle": {"color": ORANGE}, "upper": {"color": BLUE}, "lower": {"color": BLUE}}
    fills = [("upper", "lower")]

    def compute(self, bars):
        m, u, lo = donchian(bars["high"], bars["low"], self.inputs["length"])
        return {"middle": m, "upper": u, "lower": lo}


class Supertrend:
    inputs = {"factor": (3.0, 0.5, 10.0, 0.1), "atr_period": (10, 1, 100, 1)}
    chart = "main"
    plots = {"up": {"color": UP, "style": "step"}, "down": {"color": DOWN, "style": "step"}, "direction": {"display": "none"}}

    def compute(self, bars):
        line, d = supertrend(bars["high"], bars["low"], bars["close"], self.inputs["factor"], self.inputs["atr_period"])
        return {"up": np.where(d < 0, line, nan), "down": np.where(d > 0, line, nan), "direction": d}


class SAR:
    inputs = {"start": (0.02, 0.001, 0.2, 0.001), "increment": (0.02, 0.001, 0.2, 0.001), "maximum": (0.2, 0.01, 1.0, 0.01)}
    chart = "main"
    plots = {"sar": {"color": BLUE, "style": "dots"}}

    def compute(self, bars):
        return {"sar": sar(bars["high"], bars["low"], bars["close"], self.inputs["start"], self.inputs["increment"], self.inputs["maximum"])}


class VWAP:
    """Anchored to each calendar month on daily bars."""
    chart = "main"
    plots = {"vwap": {"color": "#2196f3"}}

    def compute(self, bars):
        hlc3 = (bars["high"] + bars["low"] + bars["close"]) / 3
        month = np.array([str(d)[:7] for d in bars["date"]])
        return {"vwap": vwap(hlc3, bars["volume"], np.r_[True, month[1:] != month[:-1]])}


class Ichimoku:
    inputs = {"conversion": (9, 1, 100, 1), "base": (26, 1, 200, 1), "span_b": (52, 1, 300, 1)}
    chart = "main"
    plots = {"conversion": {"color": BLUE}, "base": {"color": "#b71c1c"}, "span_a": {"color": UP}, "span_b": {"color": DOWN}}
    fills = [("span_a", "span_b")]

    def compute(self, bars):
        c, b, a, s = ichimoku(bars["high"], bars["low"], self.inputs["conversion"], self.inputs["base"], self.inputs["span_b"])
        return {"conversion": c, "base": b, "span_a": a, "span_b": s}


class RSI:
    inputs = {"length": (14, 2, 100, 1)}
    plots = {"rsi": {"color": "#7e57c2"}}
    levels = {"overbought": 70, "middle": 50, "oversold": 30}

    def compute(self, bars):
        return {"rsi": rsi(bars["close"], self.inputs["length"])}


class MACD:
    inputs = {"fast": (12, 1, 100, 1), "slow": (26, 2, 200, 1), "signal": (9, 1, 50, 1)}
    plots = {"macd": {"color": BLUE}, "signal": {"color": ORANGE}, "hist": {"color": GREY, "style": "histogram"}}
    levels = {"zero": 0}

    def compute(self, bars):
        m, s, h = macd(bars["close"], self.inputs["fast"], self.inputs["slow"], self.inputs["signal"])
        return {"macd": m, "signal": s, "hist": h}


class Stoch:
    inputs = {"k": (14, 1, 100, 1), "smooth_k": (1, 1, 20, 1), "d": (3, 1, 20, 1)}
    plots = {"k": {"color": BLUE}, "d": {"color": ORANGE}}
    levels = {"upper": 80, "lower": 20}

    def compute(self, bars):
        k = sma(stoch(bars["close"], bars["high"], bars["low"], self.inputs["k"]), self.inputs["smooth_k"])
        return {"k": k, "d": sma(k, self.inputs["d"])}


class ATR:
    inputs = {"length": (14, 1, 100, 1)}
    plots = {"atr": {"color": DOWN}}

    def compute(self, bars):
        return {"atr": atr(bars["high"], bars["low"], bars["close"], self.inputs["length"])}


class ADX:
    inputs = {"di_length": (14, 1, 100, 1), "smoothing": (14, 1, 100, 1)}
    plots = {"plus": {"color": BLUE}, "minus": {"color": ORANGE}, "adx": {"color": DOWN}}
    levels = {"trend": 25}

    def compute(self, bars):
        p, m, a = dmi(bars["high"], bars["low"], bars["close"], self.inputs["di_length"], self.inputs["smoothing"])
        return {"plus": p, "minus": m, "adx": a}


class CCI:
    inputs = {"length": (20, 2, 200, 1)}
    plots = {"cci": {"color": BLUE}}
    levels = {"upper": 100, "zero": 0, "lower": -100}

    def compute(self, bars):
        return {"cci": cci((bars["high"] + bars["low"] + bars["close"]) / 3, self.inputs["length"])}


class MFI:
    inputs = {"length": (14, 2, 100, 1)}
    plots = {"mfi": {"color": "#7e57c2"}}
    levels = {"overbought": 80, "oversold": 20}

    def compute(self, bars):
        return {"mfi": mfi((bars["high"] + bars["low"] + bars["close"]) / 3, bars["volume"], self.inputs["length"])}


class WPR:
    inputs = {"length": (14, 2, 100, 1)}
    plots = {"wpr": {"color": "#7e57c2"}}
    levels = {"upper": -20, "lower": -80}

    def compute(self, bars):
        return {"wpr": wpr(bars["high"], bars["low"], bars["close"], self.inputs["length"])}


class OBV:
    plots = {"obv": {"color": BLUE}}

    def compute(self, bars):
        return {"obv": obv(bars["close"], bars["volume"])}


INDICATORS = (SMA, EMA, HMA, BB, KC, Donchian, Supertrend, SAR, VWAP, Ichimoku, RSI, MACD, Stoch, ATR, ADX, CCI, MFI, WPR, OBV)
