"""Studio's daily formula operators over (bars x symbols) arrays, on the shared parser.

Every operator at bar t reads bars up to t only. Anything that could read a later bar is refused at compile time.
"""

from __future__ import annotations

import ast
from typing import Any

import numpy as np
import pandas as pd

from app.services.shared.formula import BINOPS, CMPOPS, SignalError
from app.services.shared.formula import parse as _parse

MAX_WINDOW = 2000
FIELDS = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume", "returns": "Close-to-close return", "market": "SPY close (the market), same on every name"}


def _df(x) -> pd.DataFrame:
    return pd.DataFrame(x)


def _roll(fn):
    return lambda x, n: getattr(_df(x).rolling(n, min_periods=n), fn)().to_numpy()


def _smooth(x, n, alpha, start=0):
    """LEAN's seed: the mean of the first n observations, then exponential smoothing (LEAN_PARITY row 19)."""
    a = np.asarray(x, dtype=float)
    out = np.full_like(a, np.nan, dtype=float)
    if a.shape[0] < start + n:
        return out
    out[start + n - 1] = a[start:start + n].mean(axis=0)
    for t in range(start + n, a.shape[0]):
        previous = out[t - 1]
        out[t] = previous + alpha * (a[t] - previous)
    return out


def _ema(x, n):
    return _smooth(x, n, 2.0 / (n + 1))


def _wilder(x, n):
    return _smooth(x, n, 1.0 / n)


def _delay(x, n):
    out = np.full_like(x, np.nan, dtype=float)
    if n == 0:
        return np.asarray(x, dtype=float)
    out[n:] = x[:-n]
    return out


def _rsi(x, n):
    d = np.diff(np.asarray(x, dtype=float), axis=0, prepend=np.nan)
    up = _smooth(np.where(d > 0, d, 0.0), n, 1.0 / n, start=1)
    down = _smooth(np.where(d < 0, -d, 0.0), n, 1.0 / n, start=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(down == 0, np.where(up == 0, 50.0, 100.0), 100.0 - 100.0 / (1.0 + up / down)) + up * 0


def true_range(high, low, close):
    prev = _delay(close, 1)
    return np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))


def _cross(a, b, up: bool):
    a, b = np.broadcast_arrays(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    pa, pb = _delay(a, 1), _delay(b, 1)
    return ((a > b) & (pa <= pb)) if up else ((a < b) & (pa >= pb))


def _rank(x):
    return _df(x).rank(axis=1, pct=True).to_numpy()


def _for_bars(x, n):
    truth = np.isfinite(x) & (x > 0)
    return _df(truth).rolling(n, min_periods=n).sum().to_numpy() == n


def _zscore(x):
    rows = _df(x)
    return rows.sub(rows.mean(axis=1), axis=0).div(rows.std(axis=1, ddof=0).replace(0, np.nan), axis=0).to_numpy()


_PERIODS = {"weekly": "W-FRI", "monthly": "M"}


def _closed_period(x, dates: pd.DatetimeIndex, frequency: str):
    """Hold the last observed value of the preceding closed period."""
    periods = dates.to_period(frequency)
    last = _df(x).groupby(periods).last()
    return last.shift(1).reindex(periods).to_numpy()


# name -> (callable, arg names, doc, example); window args are named "n"
OPERATORS: dict[str, tuple[Any, list[str], str, str]] = {
    "sma": (_roll("mean"), ["x", "n"], "Simple moving average over n bars", "sma(close, 50)"),
    "ema": (_ema, ["x", "n"], "Exponential moving average, span n", "ema(close, 20)"),
    "std": (lambda x, n: _df(x).rolling(n, min_periods=n).std(ddof=0).to_numpy(), ["x", "n"],
            "Population standard deviation over n bars (LEAN StandardDeviation; Bollinger width)", "std(returns, 20)"),
    "highest": (_roll("max"), ["x", "n"], "Highest value over n bars, this bar included", "highest(high, 20)"),
    "lowest": (_roll("min"), ["x", "n"], "Lowest value over n bars, this bar included", "lowest(low, 20)"),
    "sum": (_roll("sum"), ["x", "n"], "Sum over n bars", "sum(volume, 5)"),
    "rsi": (_rsi, ["x", "n"], "Wilder RSI over n bars", "rsi(close, 14)"),
    "roc": (lambda x, n: x / _delay(x, n) - 1, ["x", "n"], "Rate of change over n bars", "roc(close, 20)"),
    "delay": (_delay, ["x", "n"], "Value n bars ago (n >= 0)", "delay(close, 1)"),
    "crosses_above": (lambda a, b: _cross(a, b, True), ["a", "b"], "a moves above b on this bar", "crosses_above(sma(close, 50), sma(close, 200))"),
    "crosses_below": (lambda a, b: _cross(a, b, False), ["a", "b"], "a moves below b on this bar", "crosses_below(close, sma(close, 50))"),
    "rank": (_rank, ["x"], "Percentile rank across the universe on each bar", "rank(roc(close, 126))"),
    "abs": (np.abs, ["x"], "Absolute value", "abs(returns)"),
    "min": (np.fmin, ["a", "b"], "Smaller of two values", "min(open, close)"),
    "max": (np.fmax, ["a", "b"], "Larger of two values", "max(open, close)"),
    "if_else": (lambda c, a, b: np.where(c, a, b), ["cond", "a", "b"], "a where cond holds, else b", "if_else(close > open, 1, -1)"),
    "atr": (None, ["n"], "Average true range (Wilder) over n bars", "atr(14)"),
    "for_bars": (_for_bars, ["x", "n"], "Condition is true for n consecutive bars", "for_bars(close > open, 3)"),
    "rising": (lambda x, n: _for_bars(x > _delay(x, 1), n), ["x", "n"], "Series rose on each of the last n transitions", "rising(close, 3)"),
    "falling": (lambda x, n: _for_bars(x < _delay(x, 1), n), ["x", "n"], "Series fell on each of the last n transitions", "falling(close, 3)"),
    "zscore": (_zscore, ["x"], "Cross-sectional z-score on this bar", "zscore(roc(close, 20))"),
    "week_start": (None, [], "First observed bar of the week", "week_start()"),
    "month_start": (None, [], "First observed bar of the calendar month", "month_start()"),
    "weekly": (None, ["x"], "x as of the last closed week", "weekly(sma(close, 10))"),
    "monthly": (None, ["x"], "x as of the last closed calendar month", "monthly(close)"),
}
ARITY = {k: (len(v[1]), len(v[1])) for k, v in OPERATORS.items()}
_FORWARD = {"lead", "shift_forward", "future", "center", "centered"}


def parse(expr: str, params: dict[str, float] | None = None) -> ast.Expression:
    """Validate one formula. Look-ahead is refused with the offending token's span."""
    try:
        tree = ast.parse(expr.strip(), mode="eval") if isinstance(expr, str) and expr.strip() else None
    except SyntaxError:
        tree = None
    lead = len(expr) - len(expr.lstrip()) if isinstance(expr, str) else 0
    for n in ast.walk(tree) if tree else ():
        span = (getattr(n, "col_offset", 0) + lead, getattr(n, "end_col_offset", 0) + lead)
        if isinstance(n, ast.Subscript):
            idx = n.slice.operand if isinstance(n.slice, ast.UnaryOp) and isinstance(n.slice.op, ast.UAdd) else n.slice
            ahead = isinstance(idx, ast.Constant) and isinstance(idx.value, (int, float)) and idx.value > 0
            raise SignalError("Look-ahead: this reads a bar after the current one" if ahead else "Use delay(x, n) for earlier bars; subscripts are not part of the language", *span)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id in _FORWARD:
                raise SignalError(f"Look-ahead: '{n.func.id}' reads bars after the current one", *span)
            if n.func.id == "delay" and len(n.args) == 2 and isinstance(n.args[1], ast.UnaryOp) and isinstance(n.args[1].op, ast.USub):
                raise SignalError("Look-ahead: delay with a negative lag reads a later bar", *span)
    return _parse(expr, set(FIELDS) | set(params or {}), OPERATORS, ARITY, max_nodes=1000)


def tokens(tree: ast.Expression) -> tuple[set[str], set[str]]:
    """(fields and parameters, operators) a formula uses."""
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    return names - set(OPERATORS), names & set(OPERATORS)


def _window(v, op: str) -> int:
    if isinstance(v, np.ndarray) or v != int(v) or not 1 <= int(v) <= MAX_WINDOW:
        raise SignalError(f"{op}: the window must be a whole number from 1 to {MAX_WINDOW}")
    return int(v)


class _Eval:
    def __init__(self, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float]):
        self.bars, self.dates, self.params, self.cache = bars, dates, params, {}

    def field(self, name: str):
        if name in self.params:
            return float(self.params[name])
        if name == "returns":
            return self.bars["close"] / _delay(self.bars["close"], 1) - 1
        return self.bars[name]

    def go(self, n: ast.AST):
        if isinstance(n, ast.Expression):
            return self.go(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return self.field(n.id)
        if isinstance(n, ast.UnaryOp):
            v = self.go(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = self.go(n.left), self.go(n.right)
            if isinstance(n.op, (ast.BitAnd, ast.BitOr)):
                a, b = np.asarray(a) > 0, np.asarray(b) > 0
                return (a & b) if isinstance(n.op, ast.BitAnd) else (a | b)
            with np.errstate(divide="ignore", invalid="ignore"):
                return BINOPS[type(n.op)](np.asarray(a, dtype=float) if isinstance(a, np.ndarray) else a, np.asarray(b, dtype=float) if isinstance(b, np.ndarray) else b)
        if isinstance(n, ast.Compare):
            with np.errstate(invalid="ignore"):
                return CMPOPS[type(n.ops[0])](self.go(n.left), self.go(n.comparators[0]))
        if isinstance(n, ast.Call):
            key = ast.dump(n)
            if key not in self.cache:
                self.cache[key] = self.call(n)
            return self.cache[key]
        raise SignalError("Unsupported expression", getattr(n, "col_offset", 0), getattr(n, "end_col_offset", 0))

    def call(self, n: ast.Call):
        name = n.func.id  # type: ignore[union-attr]
        args = [self.go(a) for a in n.args]
        fn, arg_names = OPERATORS[name][0], OPERATORS[name][1]
        try:
            args = [_window(a, name) if arg_names[i] == "n" and not (name == "delay" and a == 0) else a for i, a in enumerate(args)]
            if name == "atr":
                return _wilder(true_range(self.bars["high"], self.bars["low"], self.bars["close"]), args[0])
            if name in {"week_start", "month_start"}:
                periods = self.dates.to_period("W-FRI" if name == "week_start" else "M")
                starts = np.ones(len(periods), dtype=bool)
                starts[1:] = periods[1:] != periods[:-1]
                return np.broadcast_to(starts[:, None], self.bars["close"].shape)
            if name in _PERIODS:
                return _closed_period(self._array(args[0], name), self.dates, _PERIODS[name])
            if "x" in arg_names:
                args[arg_names.index("x")] = self._array(args[arg_names.index("x")], name)
            return fn(*args)
        except SignalError as e:
            if e.start == 0 and e.end == 0:
                e.start, e.end = n.col_offset, n.end_col_offset
            raise

    def _array(self, v, op: str) -> np.ndarray:
        if not isinstance(v, np.ndarray):
            raise SignalError(f"{op} needs a series (for example close), not a number")
        return v.astype(float)


def evaluate(expr: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float] | None = None, cache: dict | None = None) -> np.ndarray:
    """Formula -> (bars x symbols) array. Booleans come back as bool arrays; a bare number is broadcast."""
    params = params or {}
    ev = _Eval(bars, dates, params)
    if cache is not None:
        ev.cache = cache
    out = ev.go(parse(expr, params))
    if not isinstance(out, np.ndarray):
        out = np.full(bars["close"].shape, out, dtype=float)
    return out


def catalogue() -> dict[str, Any]:
    return {"fields": [{"name": k, "doc": v} for k, v in FIELDS.items()],
            "operators": [{"name": k, "args": v[1], "doc": v[2], "example": v[3]} for k, v in OPERATORS.items()]}
