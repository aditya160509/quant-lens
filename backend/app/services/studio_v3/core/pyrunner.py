"""Child process for Python strategies. Run as `python -I pyrunner.py <in.npz> <out.npz>`, code on stdin.

The child runs user callbacks with restricted builtins. Event runs use Studio's shared fill engine.
"""

import copy
import importlib
import importlib.util
import inspect
import json
import math
import operator
import re
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType, MethodType, ModuleType

import numpy as np

# A7: the same allow-list pycode.check enforces, enforced again where the import actually happens.
ALLOWED_IMPORTS = (
    "math", "statistics", "numpy", "pandas", "scipy.stats", "scipy.optimize",
    "sklearn.linear_model", "sklearn.ensemble", "sklearn.preprocessing", "sklearn.pipeline", "sklearn.metrics",
    "sklearn.tree", "sklearn.neighbors", "sklearn.cluster", "sklearn.decomposition",
)
ALLOWED_ROOTS = {name.split(".")[0] for name in ALLOWED_IMPORTS}
# Stdlib modules that pandas and numpy C code load lazily through the caller's builtins. A strategy cannot name them: pycode.check refuses the import.
LAZY_LIBRARY_MODULES = {"time", "datetime", "_strptime", "decimal", "calendar", "locale", "zoneinfo"}
INDICATOR_NAMES = ("sma", "ema", "rsi", "atr", "std", "roc", "highest", "lowest")
SAFE_BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k) for k in (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max", "min", "range", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    "isinstance", "print", "ValueError", "Exception", "object", "super", "property", "staticmethod", "__build_class__")}


class History:
    """`h[-1]` is this bar, `h[-2]` the one before. Positive indexes and later bars are refused (no look-ahead)."""

    __slots__ = ("_a", "_ctx")

    def __init__(self, a, ctx):
        self._a, self._ctx = a, ctx

    def __getitem__(self, k):
        t = self._ctx.t
        if isinstance(k, slice):
            if (k.start is not None and k.start >= 0) or (k.stop is not None and k.stop > 0) or k.step not in (None, 1):
                raise IndexError("use negative slices like close[-20:] (no look-ahead)")
            lo = t + 1 + (k.start or -(t + 1))
            hi = t + 1 + (k.stop or 0)
            return self._a[max(lo, 0):max(hi, 0)].tolist()
        if k >= 0:
            raise IndexError("use negative indexes: close[-1] is this bar")
        i = t + 1 + k
        return float(self._a[i]) if i >= 0 else float("nan")

    def __len__(self):
        return self._ctx.t + 1


class HistoryWindow:
    """A bounded numeric snapshot. Offset zero is current and negative offsets are past."""

    __slots__ = ("_values",)

    def __init__(self, values):
        self._values = values

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return (float(value) for value in self._values[::-1])

    def to_numpy(self):
        """A copy of the window, oldest bar first."""
        return np.array(self._values, dtype=float)

    def __array__(self, dtype=None, copy=None):
        return np.asarray(self.to_numpy(), dtype=dtype)

    def __getitem__(self, offset):
        if type(offset) is not int:
            raise TypeError("History offsets must be integers")
        if offset > 0:
            raise IndexError(f"history[{offset}] reads a future bar; use 0 for current or a negative offset")
        if -offset >= len(self):
            raise IndexError(f"history[{offset}] is outside the requested window")
        return float(self._values[len(self) - 1 + offset])


def indicator_formula(expr, period):
    if period is None:
        return expr
    if type(period) is not int or period < 1 or expr not in {"sma", "ema", "rsi", "atr", "std", "roc", "highest", "lowest"}:
        raise ValueError("Use a supported indicator name and a positive integer period")
    return f"atr({period})" if expr == "atr" else f"{expr}(close, {period})"


class Indicator:
    """A live indicator handle bound to the strategy's current bar."""

    __slots__ = ("_ctx", "_expr", "_period", "_values")

    def __init__(self, ctx, expr, values, period):
        self._ctx, self._expr, self._values, self._period = ctx, expr, values, period

    @property
    def value(self):
        if self._values is None:
            raise ValueError("Select a symbol to read an indicator value in portfolio mode")
        return float(self._values[self._ctx.t])

    @property
    def ready(self):
        return math.isfinite(self.value)

    def history(self, n):
        if type(n) is not int or n < 1:
            raise ValueError("Indicator history requires a positive integer window")
        if self._values is None:
            raise ValueError("Select a symbol to read indicator history in portfolio mode")
        end = self._ctx.t + 1
        return HistoryWindow(self._values[max(end - n, 0):end])

    @property
    def window(self):
        return self.history(self._period or self._ctx.t + 1)


def _user_site():
    """(file, line) of the nearest strategy frame that called into the API."""
    frame = sys._getframe(2)
    while frame is not None:
        name = frame.f_code.co_filename
        if name.startswith("<studio:"):
            return name[8:-1], frame.f_lineno
        frame = frame.f_back
    return None


class _LineProfiler:
    """Seconds per strategy line (callees included) and per function, from sys.settrace on strategy frames only. Opt-in: it slows the run."""

    def __init__(self):
        self.lines, self.functions, self.stacks, self._stack, self._last = {}, {}, {}, [], None

    def _charge(self, now):
        if self._last is not None:
            key, t0 = self._last
            self.lines[key] = self.lines.get(key, 0.0) + now - t0

    def _global(self, frame, event, arg):
        code = frame.f_code
        if not code.co_filename.startswith("<studio:"):
            return None
        now = time.perf_counter()
        self._charge(now)
        self._stack.append((self._last, (code.co_filename[8:-1], code.co_name), now))
        self._last = None
        return self._local

    def _local(self, frame, event, arg):
        now = time.perf_counter()
        name = frame.f_code.co_filename[8:-1]
        if event == "line":
            self._charge(now)
            self._last = ((name, frame.f_lineno), now)
        elif event == "return":
            self._charge(now)
            caller, function, started = self._stack.pop()
            row = self.functions.setdefault(function, [0, 0.0])
            row[0] += 1
            row[1] += now - started
            path = tuple(f[1][1] for f in self._stack[-23:]) + (function[1],)  # shortcut: depth capped at 24 frames, 500 distinct stacks
            if path in self.stacks or len(self.stacks) < 500:
                self.stacks[path] = self.stacks.get(path, 0.0) + now - started
            self._last = None if caller is None else (caller[0], now)
        return self._local

    def run(self, call):
        sys.settrace(self._global)
        try:
            return call()
        finally:
            sys.settrace(None)

    def report(self, sources):
        top = sorted(self.lines.items(), key=lambda item: -item[1])[:10]
        text = lambda f, n: (sources.get(f, "").splitlines() + [""] * n)[n - 1].strip()[:200]
        stacks = sorted(self.stacks.items(), key=lambda item: -item[1])[:200]
        return {"lines": [{"file": f, "line": n, "seconds": round(sec, 6), "text": text(f, n)} for (f, n), sec in top],
                "stacks": [{"path": list(path), "seconds": round(sec, 6)} for path, sec in stacks],
                "functions": [{"file": f, "name": name, "calls": c, "seconds": round(sec, 6)}
                              for (f, name), (c, sec) in sorted(self.functions.items(), key=lambda item: -item[1][1])[:20]]}


class _Logpoints:
    """Logpoints: log a message when a strategy line runs, without stopping. `{expr}` parts are evaluated; a message without braces is one expression, logged as `expr = value`.
    With `coverage`, it also records every strategy line that ran (the coverage gutter)."""

    def __init__(self, points, context, coverage=False):
        self.points = {(str(p["file"]), int(p["line"])): str(p["message"])[:500] for p in points}
        self.files = {f"<studio:{f}>" for f, _ in self.points}
        self.context = context
        self.hit = set() if coverage else None

    def _global(self, frame, event, arg):
        name = frame.f_code.co_filename
        return self._local if name in self.files or (self.hit is not None and name.startswith("<studio:")) else None

    def _local(self, frame, event, arg):
        if self.hit is not None and event == "line":
            self.hit.add((frame.f_code.co_filename[8:-1], frame.f_lineno))
        message = self.points.get((frame.f_code.co_filename[8:-1], frame.f_lineno)) if event == "line" else None
        if message is None:
            return self._local
        try:
            ctx = self.context()
        except NameError:  # before the first context exists
            return self._local
        try:
            value = eval(f"f{message!r}" if "{" in message else message, frame.f_globals, frame.f_locals)
            text, level = (value if "{" in message else f"{message} = {value!r}"), "info"
        except Exception as e:  # noqa: BLE001 a bad expression is logged, never stops the run
            text, level = f"{message}: {type(e).__name__}: {e}", "warning"
        ctx._log(text, level, frame.f_lineno)
        return self._local

    def run(self, call):
        sys.settrace(self._global)
        try:
            return call()
        finally:
            sys.settrace(None)

    def coverage(self, codes):
        """{file: {"hit": lines that ran, "lines": every executable line}} for the compiled strategy files."""
        def lines(code):
            found = {n for _, _, n in code.co_lines() if n}
            for const in code.co_consts:
                if hasattr(const, "co_lines"):
                    found |= lines(const)
            return found
        return {name: {"hit": sorted(n for f, n in self.hit if f == name), "lines": sorted(lines(code))} for name, code in codes.items()}


class _Log:
    """ctx.log(...) plus ctx.log.info/warning/error with key values (B-80)."""

    def __init__(self, ctx):
        self._ctx = ctx

    def __call__(self, message, level="info", **fields):
        self._ctx._log(message, level, sys._getframe(1).f_lineno, fields)

    def info(self, message, **fields):
        self._ctx._log(message, "info", sys._getframe(1).f_lineno, fields)

    def warning(self, message, **fields):
        self._ctx._log(message, "warning", sys._getframe(1).f_lineno, fields)

    def error(self, message, **fields):
        self._ctx._log(message, "error", sys._getframe(1).f_lineno, fields)


_COLOR = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-z]{3,20})$")


def _color(value):
    """Accept #hex or a CSS colour name; None keeps the default."""
    if value is None:
        return None
    value = str(value).strip()
    if not _COLOR.match(value):
        raise ValueError("Colour must be #hex or a colour name")
    return value


class Ctx:
    def __init__(self, cols, values, params, symbol, dates):
        self._t = 0
        self.symbol, self.position, self.params = symbol, 0, params
        self._cols, self._values, self._dates = cols, values, dates
        self.open, self.high, self.low, self.close, self.volume = (History(cols[f], self) for f in ("open", "high", "low", "close", "volume"))
        self.orders = []
        self._order_lines = None
        self._invariants = None
        self.log = _Log(self)

    @property
    def t(self):
        return self._t

    @property
    def date(self):
        return str(self._dates[self.t])

    @property
    def bar(self):
        return self.t

    def history(self, fields, n, pandas=False):
        """Read a bounded history window. Offset zero is the current bar. `.to_numpy()` gives an array; pandas=True gives a Series or DataFrame indexed by date, oldest first."""
        if type(n) is not int or n < 1:
            raise ValueError("history requires a positive integer window")
        if pandas:
            import pandas as pd

            names = [fields] if isinstance(fields, str) else list(fields)
            if any(name not in self._cols for name in names):
                raise ValueError(f"Unknown history field in {names}")
            end = self.t + 1
            frame = pd.DataFrame({name: self._cols[name][max(0, end - n):end] for name in names}, index=pd.to_datetime(self._dates[max(0, end - n):end]))
            return frame[fields] if isinstance(fields, str) else frame
        if not isinstance(fields, str):
            return MappingProxyType({field: self.history(field, n) for field in fields})
        if fields not in self._cols:
            raise ValueError(f"Unknown history field: {fields}")
        end = self.t + 1
        return HistoryWindow(self._cols[fields][max(0, end - n):end])

    @property
    def market(self):
        if self._benchmark is None:
            return None
        close = float(self._benchmark[self.t])
        return MarketBar(close) if math.isfinite(close) else None

    def indicator(self, expr, symbol=None, period=None):
        """Create a reusable handle for a literal formula or named indicator."""
        if symbol is not None and symbol != self.symbol:
            raise ValueError("Per-symbol strategies can inspect only their current symbol")
        formula = indicator_formula(expr, period)
        return Indicator(self, formula, self._values[formula], period)

    def timeframe(self, tf):
        """Completed weekly ("W"), monthly ("M"), quarterly ("Q") or yearly ("Y") bars as of this bar, like Pine's request.security
        without look-ahead: `ctx.timeframe("W").close[0]` is last week's close; the week still forming is never included."""
        if tf not in ("W", "M", "Q", "Y"):
            raise ValueError('timeframe takes "W", "M", "Q" or "Y"')
        cache = self.__dict__.setdefault("_tf", {})
        if tf not in cache:
            days = np.array(self._dates, dtype="datetime64[D]")
            period = {"W": (days.astype("int64") + 3) // 7, "M": days.astype("datetime64[M]").astype("int64"),
                      "Q": days.astype("datetime64[M]").astype("int64") // 3, "Y": days.astype("datetime64[Y]").astype("int64")}[tf]
            live = np.isfinite(self._cols["close"])
            ids = np.unique(period[live])
            agg = {f: np.full(len(ids), np.nan) for f in ("open", "high", "low", "close", "volume")}
            for i, pid in enumerate(ids):
                rows = np.flatnonzero((period == pid) & live)
                agg["open"][i], agg["close"][i] = self._cols["open"][rows[0]], self._cols["close"][rows[-1]]
                agg["high"][i], agg["low"][i] = np.nanmax(self._cols["high"][rows]), np.nanmin(self._cols["low"][rows])
                agg["volume"][i] = np.nansum(self._cols["volume"][rows])
            cache[tf] = (agg, np.searchsorted(ids, period))  # completed periods before each bar's own period
        agg, done = cache[tf]
        k = int(done[self.t])
        return MappingProxyType({f: HistoryWindow(a[:k]) for f, a in agg.items()})

    def fit_every(self, n):
        """True on every n-th bar: refit a model there and reuse it in between."""
        if type(n) is not int or n < 1:
            raise ValueError("fit_every needs a positive integer")
        return self.t % n == 0

    def feature_matrix(self, exprs, n, symbol=None):
        """The last n bars (this one included) of each literal formula as an (n, features) array, oldest row first; early rows are NaN."""
        if type(n) is not int or not 1 <= n <= 5000:
            raise ValueError("feature_matrix needs a window from 1 to 5000 bars")
        columns = []
        for expr in exprs:
            series = self._feature_series(expr, symbol)
            window = series[max(0, self.t + 1 - n):self.t + 1]
            columns.append(np.concatenate([np.full(n - len(window), np.nan), window]))
        return np.column_stack(columns)

    def _feature_series(self, expr, symbol):
        if symbol is not None and symbol != self.symbol:
            raise ValueError("Per-symbol strategies can read only their current symbol")
        if expr not in self._values:
            raise KeyError(f"ctx.feature_matrix needs literal formula strings; {expr!r} was not precomputed")
        return self._values[expr]

    def value(self, expr):
        """A formula's value on this bar, e.g. ctx.value("rsi(close, 14)")."""
        a = self._values.get(expr)
        if a is None:
            raise KeyError(f"ctx.value/ctx.rule need a literal string; {expr!r} was not precomputed")
        v = a[self.t]
        return float(v) if np.isfinite(v) else float("nan")

    def rule(self, expr):
        v = self.value(expr)
        return bool(v > 0) if not math.isnan(v) else False

    def param(self, name):
        return self.params[name]

    def _log(self, message, level, line, fields=None):
        if self._logs is None or len(self._logs) > 50_000:
            return
        text = str(message)[:1024] if len(self._logs) < 50_000 else "Output truncated after 50000 lines"
        row = {"date": self.date, "symbol": self.symbol, "line": line, "text": text, "level": str(level)[:32]}
        clean = {}
        for key, value in list((fields or {}).items())[:32]:
            name = str(key)[:64]
            if isinstance(value, (bool, str)):
                clean[name] = value[:256] if isinstance(value, str) else value
            elif isinstance(value, (int, float)) and math.isfinite(float(value)):
                clean[name] = float(value)
        if clean:
            row["fields"] = clean
        self._logs.append(row)

    _default_chart = "own"  # an Indicator with overlay = True draws on price by default

    def plot(self, name, value, chart=None, color=None, width=None, style=None):
        chart = chart or self._default_chart
        """Record a value in a named plot on the main chart or in a separate pane."""
        if chart not in ("main", "own"):
            raise ValueError("Plot chart must be main or own")
        value = float(value)
        name = str(name)[:128]
        if self._plots is not None and (color is not None or width is not None or style is not None):
            if style not in (None, "line", "step", "histogram", "area", "dots"):
                raise ValueError("Plot style must be line, step, histogram, area or dots")
            self._draw["styles"][name] = {"color": _color(color), "width": max(1, min(int(width or 1), 6)), "style": style or "line"}
        if self._plots is not None and self._plot_count[0] < 50_000:
            if self._plot_charts.setdefault(name, chart) != chart:
                raise ValueError("A named plot must keep the same chart")
            self._plots.setdefault(name, []).append({
                "date": self.date, "symbol": self.symbol, "value": value if math.isfinite(value) else None,
            })
            self._plot_count[0] += 1

    def hline(self, value, chart="own", color=None, name=""):
        """Draw a flat level line once, e.g. RSI 70."""
        if chart not in ("main", "own"):
            raise ValueError("Line chart must be main or own")
        line = {"value": float(value), "chart": chart, "color": _color(color), "name": str(name)[:64]}
        if self._plots is not None and line not in self._draw["hlines"] and len(self._draw["hlines"]) < 50:
            self._draw["hlines"].append(line)

    def fill(self, a, b, color=None):
        """Shade the area between two named plots."""
        pair = {"a": str(a)[:128], "b": str(b)[:128], "color": _color(color)}
        if self._plots is not None and pair not in self._draw["fills"] and len(self._draw["fills"]) < 50:
            self._draw["fills"].append(pair)

    def bgcolor(self, color):
        """Colour the background of the current bar."""
        if self._plots is not None and color and len(self._draw["bg"]) < 50_000:
            self._draw["bg"].append({"date": self.date, "color": _color(color)})

    def mark(self, symbol, label):
        """Attach a labeled marker to a symbol on the current bar."""
        if symbol not in self._symbols:
            raise ValueError("Marker symbol must be in the strategy universe")
        if self._marks is not None and len(self._marks) < 5_000:
            self._marks.append({"date": self.date, "symbol": symbol, "label": str(label)[:256]})

    def table(self, name, row):
        """Append a dictionary of scalar cells to a named results table."""
        if not isinstance(row, dict) or len(row) > 32:
            raise ValueError("Table rows must be dictionaries with at most 32 columns")
        cells = {}
        for key, value in row.items():
            if type(key) is not str or len(key) > 128:
                raise ValueError("Table column names must be strings up to 128 characters")
            if value is None or type(value) is bool:
                cells[key] = value
            elif type(value) is str:
                cells[key] = value[:512]
            elif type(value) in (int, float):
                cells[key] = value if -sys.float_info.max <= value <= sys.float_info.max else None
            else:
                raise ValueError("Table cells must be strings, numbers, booleans or None")
        if self._tables is not None and self._table_count[0] < 5_000:
            self._tables.setdefault(str(name)[:128], []).append({"date": self.date, "symbol": self.symbol, "cells": cells})
            self._table_count[0] += 1

    def assert_invariant(self, condition, message=""):
        """Record a violation (date, symbol, line, message) instead of stopping; Validate fails while any exist (B-39)."""
        if condition or self._invariants is None:
            return
        self._invariants["count"] += 1
        if len(self._invariants["rows"]) < 500:
            site = _user_site()
            self._invariants["rows"].append({"date": self.date, "symbol": self.symbol, "file": site[0] if site else "main.py", "line": site[1] if site else 0,
                                             "text": str(message)[:300]})

    def _note_order(self):
        """Count the strategy line that placed an order, with the first five dates (B-74)."""
        if self._order_lines is None:
            return
        site = _user_site()
        if site is not None:
            row = self._order_lines.setdefault(site, {"file": site[0], "line": site[1], "count": 0, "dates": []})
            row["count"] += 1
            if len(row["dates"]) < 5 and self.date not in row["dates"]:
                row["dates"].append(self.date)

    def _order(self, action):
        self._note_order()
        self.orders.append((self.t, action))

    def buy(self):
        self._order(1)

    def sell(self):
        self._order(2)

    def short(self):
        self._order(-1)

    def cover(self):
        self._order(3)


@dataclass(frozen=True, slots=True)
class Execution:
    symbol: str
    side: str
    quantity: float
    price: float
    date: str
    fee: float


@dataclass(frozen=True, slots=True)
class MarketBar:
    close: float


@dataclass(frozen=True, slots=True)
class Bar:
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class Holding:
    quantity: float = 0
    average_price: float = 0
    unrealized_profit: float = 0
    bars_held: int = 0
    entry_date: str | None = None

    @property
    def invested(self):
        return self.quantity != 0


@dataclass(frozen=True, slots=True)
class Portfolio:
    cash: float
    total_value: float
    leverage: float
    gross_exposure: float
    net_exposure: float
    positions: MappingProxyType

    def __getitem__(self, symbol):
        return self.positions[symbol]

    @property
    def invested(self):
        """True while any position is open (LEAN's `Portfolio.Invested`)."""
        return any(position.quantity for position in self.positions.values())


class PortfolioContext(Ctx):
    def __init__(self, contexts, bars, values):
        first = contexts[0]
        super().__init__(first._cols, first._values, first.params.copy(), None, first._dates)
        self._benchmark = first._benchmark
        self._symbols, self._marks = first._symbols, first._marks
        self._tables, self._table_count = first._tables, first._table_count
        self._plot_charts = first._plot_charts
        self._draw = first._draw
        self._order_lines = first._order_lines
        self._invariants = first._invariants
        self._logs, self._plots, self._plot_count = first._logs, first._plots, first._plot_count
        self._contexts = {ctx.symbol: ctx for ctx in contexts}
        self._columns = {symbol: i for i, symbol in enumerate(self._contexts)}
        self._bars = bars
        self._matrix_values = values
        self._weeks = [date.fromisoformat(d).isocalendar()[:2] for d in self._dates]
        self.symbols = tuple(self._contexts)

    @property
    def bar_index(self):
        return self.t

    @property
    def is_month_start(self):
        return self.t == 0 or self._dates[self.t][:7] != self._dates[self.t - 1][:7]

    @property
    def is_week_start(self):
        return self.t == 0 or self._weeks[self.t] != self._weeks[self.t - 1]

    @property
    def is_quarter_start(self):
        if self.t == 0:
            return True
        previous, current = (date.fromisoformat(self._dates[i]) for i in (self.t - 1, self.t))
        return (previous.year, (previous.month - 1) // 3) != (current.year, (current.month - 1) // 3)

    @property
    def is_year_start(self):
        return self.t == 0 or self._dates[self.t][:4] != self._dates[self.t - 1][:4]

    @property
    def rebalancing(self):
        return self._rebalancing

    def every(self, n):
        if type(n) is not int or n <= 0:
            raise ValueError("every(n) needs a positive integer")
        return self.t % n == 0

    def bar(self, symbol):
        column = self._columns[symbol]
        if not math.isfinite(self._bars["close"][self.t, column]):
            return None
        return Bar(*(float(self._bars[f][self.t, column]) for f in ("open", "high", "low", "close", "volume")))

    def history(self, fields, n, sym=None, pandas=False):
        """Read bounded history for one symbol or for the entire universe. pandas=True with no symbol and one field gives a DataFrame with a column per symbol."""
        if sym is None:
            if pandas:
                if not isinstance(fields, str):
                    raise ValueError("pandas=True without sym needs one field name")
                import pandas as pd

                return pd.DataFrame({symbol: self.history(fields, n, symbol, pandas=True) for symbol in self.symbols})
            return MappingProxyType({symbol: self.history(fields, n, symbol) for symbol in self.symbols})
        ctx = self._contexts[sym]
        ctx._t = self.t
        return ctx.history(fields, n, pandas=pandas)

    def _feature_series(self, expr, symbol):
        if symbol is None or symbol not in self._columns:
            raise ValueError("ctx.feature_matrix(exprs, n, symbol) needs a symbol in the run universe in on_data")
        if expr not in self._matrix_values:
            raise KeyError(f"ctx.feature_matrix needs literal formula strings; {expr!r} was not precomputed")
        return self._matrix_values[expr][:, self._columns[symbol]]

    def value(self, expr, symbol=None):
        if symbol is None:
            raise ValueError("ctx.value(formula, symbol) needs a symbol in on_data")
        ctx = self._contexts[symbol]
        ctx._t = self.t
        return ctx.value(expr)

    def rule(self, expr, symbol=None):
        return self.value(expr, symbol) > 0

    def indicator(self, expr, symbol=None, period=None):
        """Create an indicator for a symbol, or a portfolio-wide handle for ranking."""
        formula = indicator_formula(expr, period)
        values = self._matrix_values[formula]
        return Indicator(self, formula, values[:, self._columns[symbol]] if symbol is not None else None, period)

    def _cross_section(self, expr):
        if isinstance(expr, Indicator):
            expr = expr._expr
        series = self._matrix_values[expr][self.t]
        present = np.isfinite(series) & np.isfinite(self._bars["close"][self.t])
        return series, present

    def rank(self, expr, *, top=None, bottom=None, where=None):
        """Rank observed symbols on a formula, optionally filtered by another formula."""
        if top is not None and bottom is not None:
            raise ValueError("Choose either top or bottom")
        count = top if bottom is None else bottom
        if count is not None and (type(count) is not int or count < 1):
            raise ValueError("Rank count must be a positive integer")
        values, present = self._cross_section(expr)
        if where is not None:
            condition = self._matrix_values[where][self.t]
            present &= np.isfinite(condition) & (condition > 0)
        columns = np.flatnonzero(present)
        scores = values[columns]
        order = np.argsort(-scores if bottom is None else scores, kind="stable")[:count]
        return [(self.symbols[columns[i]], float(scores[i])) for i in order]

    def zscore(self, expr):
        """Return population z-scores by symbol for this bar."""
        values, present = self._cross_section(expr)
        samples = values[present]
        if not len(samples) or (spread := samples.std()) == 0:
            return MappingProxyType({})
        scores = (samples - samples.mean()) / spread
        return MappingProxyType({self.symbols[i]: float(score) for i, score in zip(np.flatnonzero(present), scores, strict=True)})

    def buy(self, symbol):
        self._note_order()
        self.orders.append((symbol, 1))

    def sell(self, symbol):
        self._note_order()
        self.orders.append((symbol, 2))

    def short(self, symbol):
        self._note_order()
        self.orders.append((symbol, -1))

    def cover(self, symbol):
        self._note_order()
        self.orders.append((symbol, 3))

    def market_order(self, symbol, quantity):
        """Submit a signed share quantity. Positive buys and negative sells."""
        self._submit(symbol, quantity)

    def limit_order(self, symbol, quantity, price):
        self._submit(symbol, quantity, limit=float(price))

    def stop_order(self, symbol, quantity, price):
        self._submit(symbol, quantity, stop=float(price))

    def stop_limit_order(self, symbol, quantity, stop_price, limit_price):
        self._submit(symbol, quantity, limit=float(limit_price), stop=float(stop_price))

    def bracket(self, symbol, quantity, stop=None, target=None, trail=None):
        """Enter with a market order and attach exits as fractions of the fill price: stop (loss), target (gain) and trail. Whichever hits first closes the
        position and the other is gone (one-cancels-other); a bar that touches both takes the stop first."""
        levels = []
        for name, value in (("stop", stop), ("target", target), ("trail", trail)):
            if value is not None and (not math.isfinite(float(value)) or not 0 < float(value) < 1):
                raise ValueError(f"bracket {name} is a fraction of the entry price between 0 and 1, like 0.05")
            levels.append(math.nan if value is None else float(value))
        if all(math.isnan(level) for level in levels):
            raise ValueError("bracket needs at least one of stop, target or trail")
        self._submit(symbol, quantity, bracket=tuple(levels))

    def order_value(self, symbol, value):
        current = self.bar(symbol)
        if current is not None:
            self.market_order(symbol, float(value) / current.close)

    def target_weights(self, weights, corridor=0.0):
        """Set each name to its target share of equity. With `corridor`, a name whose current weight is within that distance of its target is left alone (threshold rebalancing)."""
        if corridor < 0 or not math.isfinite(corridor):
            raise ValueError("corridor must be a nonnegative number")
        total = self._account._mark()[0] if corridor else 0.0
        for symbol, weight in weights.items():
            if corridor and total:
                current = self.bar(symbol)
                held = self.pos(symbol).quantity * (current.close if current else 0.0) / total
                if abs(held - float(weight)) <= corridor and not (float(weight) == 0 and held):
                    continue
            self.set_holdings(symbol, weight)

    order = market_order
    limit = limit_order
    stop = stop_order
    stop_limit = stop_limit_order

    def _submit(self, symbol, quantity, *, limit=None, stop=None, bracket=None):
        self._columns[symbol]
        quantity = float(quantity)
        if not math.isfinite(quantity):
            raise ValueError("Order quantity must be finite")
        if any(price is not None and (not math.isfinite(price) or price <= 0) for price in (limit, stop)):
            raise ValueError("Order price must be positive and finite")
        if quantity:
            self._note_order()
            self.orders.append((symbol, (quantity, limit, stop, bracket)))

    def set_holdings(self, symbol, weight):
        weight = float(weight)
        if not math.isfinite(weight):
            raise ValueError("Target weight must be finite")
        current = self.bar(symbol)
        if current is not None:
            total, _, _, _ = self._account._mark()
            self.market_order(symbol, weight * total / current.close - self.pos(symbol).quantity)

    set_weight = set_holdings

    def liquidate(self, symbol=None):
        for name in (self.symbols if symbol is None else (symbol,)):
            self.cancel(name)
            self.market_order(name, -self.pos(name).quantity)

    def cancel(self, symbol):
        self._columns[symbol]
        self.orders.append((symbol, None))

    def cancel_all(self):
        for symbol in self.symbols:
            self.cancel(symbol)

    def pos(self, symbol):
        if symbol not in self._columns:
            raise ValueError(
                f"Unknown symbol {symbol!r}; in on_data use ctx.symbols or one name from the run universe"
            )
        pos = self._account.positions.get(self._columns[symbol])
        if pos is None:
            return Holding()
        return Holding(float(pos.shares), float(pos.entry_px), float(pos.shares * (pos.last - pos.entry_px)),
                       self.t - pos.entry_bar + 1, self._dates[pos.entry_bar])

    @property
    def portfolio(self):
        """Read the marked cash, equity, exposure and positions for this bar."""
        equity, gross, net, _ = self._account._mark()
        positions = {symbol: self.pos(symbol) for symbol in self.symbols}
        return Portfolio(float(self._account.cash), float(equity), float(gross / equity) if equity else 0,
                         float(gross), float(net), MappingProxyType(positions))


class PortfolioStrategy:
    def __init__(self, cls, ctx, warmup, use_context, submitted, market_filter):
        self.strategy = bind_indicators(cls())
        self.ctx = ctx
        self.warmup = warmup
        self.use_context = use_context
        self.submitted = submitted
        self.market_filter = market_filter
        self.max_entries = getattr(cls, "max_entries", 0)
        if type(self.max_entries) is not int or self.max_entries < 0:
            raise ValueError("Strategy.max_entries must be a nonnegative integer")
        self.rebalance = getattr(self.strategy, "rebalance", None)
        self.schedule = getattr(self.strategy, "rebalance_schedule", "daily")
        if self.schedule not in (None, "daily", "week_start", "month_start", "quarter_start", "year_start") and (
            type(self.schedule) is not int or self.schedule < 1
        ):
            raise ValueError("rebalance_schedule needs a calendar interval, a positive bar count, or None")
        self.end_of_day = getattr(self.strategy, "on_end_of_day", None)
        self.warmup_done = getattr(self.strategy, "on_warmup_done", None)
        self.stop = getattr(self.strategy, "on_stop", None)
        self.callback = getattr(self.strategy, "on_fill", None)
        self.legacy_fill = self.callback is not None and len(inspect.signature(self.callback).parameters) == 1

    def _context(self, engine_ctx):
        self.ctx._t = engine_ctx.t
        self.ctx._account = engine_ctx._e
        self.strategy._studio_ctx = self.ctx
        self.ctx._rebalancing = self._scheduled(self.ctx)
        self.use_context(self.ctx)
        return self.ctx

    def on_bar(self, engine_ctx):
        ctx = self._context(engine_ctx)
        engine_ctx._e.max_entries = self.max_entries
        if ctx.t == 0 and hasattr(self.strategy, "init"):
            self.strategy.init(ctx)
            ctx.orders.clear()
        if ctx.t == self.warmup and self.warmup_done is not None:
            self.warmup_done(ctx)
        if self.rebalance is not None and ctx.rebalancing:
            self.rebalance(ctx)
        self.strategy.on_data(ctx)
        if self.end_of_day is not None:
            self.end_of_day(ctx)
        if ctx.t >= self.warmup:
            for symbol, action in ctx.orders:
                n = ctx._columns[symbol]
                qty = engine_ctx.position(n)
                if action is None:
                    engine_ctx._e.orders.pop(n, None)
                    self.submitted[ctx.t, n, 4] = 1
                    continue
                if self.market_filter is not None and not self.market_filter[ctx.t, n]:
                    continue
                if isinstance(action, tuple):
                    quantity, limit, stop, bracket = action
                    engine_ctx._e.pending.pop(n, None)
                    if bracket is None:
                        engine_ctx._e.brackets.pop(n, None)
                    else:
                        engine_ctx._e.brackets[n] = bracket
                    engine_ctx._e.wants.pop(n, None)
                    engine_ctx._e.orders[n] = (quantity, math.nan if limit is None else limit, math.nan if stop is None else stop, ctx.t)
                    self.submitted[ctx.t, n, [0, 2, 3]] = quantity, limit or 0, stop or 0
                elif n in engine_ctx._e.orders:
                    continue
                elif action == 1 and qty <= 0:
                    engine_ctx.enter(n, 1)
                    self.submitted[ctx.t, n, 0] = 1
                elif action == -1 and qty >= 0:
                    engine_ctx.enter(n, -1)
                    self.submitted[ctx.t, n, 0] = -1
                elif (action == 2 and qty > 0) or (action == 3 and qty < 0):
                    engine_ctx.exit(n)
                    self.submitted[ctx.t, n, 1] = 1 if qty > 0 else 2
        if self.market_filter is not None:
            for n in tuple(engine_ctx._e.orders):
                if not self.market_filter[ctx.t, n]:
                    del engine_ctx._e.orders[n]
            for n in engine_ctx._e.positions:
                if not self.market_filter[ctx.t, n]:
                    engine_ctx.exit(n)
        ctx.orders.clear()

    def finish(self):
        if self.stop is not None:
            self.use_context(self.ctx)
            self.stop(self.ctx)

    def _scheduled(self, ctx):
        if self.schedule is None:
            return False
        if self.schedule == "daily":
            return True
        if self.schedule == "month_start":
            return ctx.is_month_start
        if self.schedule == "week_start":
            return ctx.is_week_start
        if self.schedule == "quarter_start":
            return ctx.is_quarter_start
        if self.schedule == "year_start":
            return ctx.is_year_start
        return ctx.every(self.schedule)

    def on_fill(self, engine_ctx, fill):
        if self.callback is not None:
            ctx = self._context(engine_ctx)
            if self.legacy_fill:
                self.callback(ctx)
            else:
                self.callback(ctx, Execution(ctx.symbols[fill.symbol], fill.side, float(fill.quantity), float(fill.price), ctx.date, float(fill.fee)))

    def on_risk_event(self, engine_ctx, event):
        callback = getattr(self.strategy, "on_risk_event", None)
        if callback is not None:
            ctx = self._context(engine_ctx)
            callback(ctx, {**event, "date": ctx.date})


class EventStrategy:
    def __init__(self, cls, contexts, available, warmup, use_context, market_filter, submitted):
        self.contexts = contexts
        self.strategies = [bind_indicators(cls()) for _ in contexts]
        self.available = available
        self.warmup = warmup
        self.seen = [0] * len(contexts)
        self.use_context = use_context
        self.market_filter = market_filter
        self.submitted = submitted
        self.end_of_day = [getattr(strategy, "on_end_of_day", None) for strategy in self.strategies]
        self.warmup_done = [getattr(strategy, "on_warmup_done", None) for strategy in self.strategies]
        self.stops = [getattr(strategy, "on_stop", None) for strategy in self.strategies]
        self.callbacks = []
        for strategy in self.strategies:
            callback = getattr(strategy, "on_fill", None)
            self.callbacks.append((callback, callback is not None and len(inspect.signature(callback).parameters) == 1))

    def _context(self, engine_ctx, symbol):
        ctx = self.contexts[symbol]
        ctx._t = engine_ctx.t
        self.strategies[symbol]._studio_ctx = ctx
        qty = engine_ctx.position(symbol)
        ctx.position = int(qty > 0) - int(qty < 0)
        self.use_context(ctx)
        return ctx

    def on_fill(self, engine_ctx, fill):
        callback, legacy = self.callbacks[fill.symbol]
        if callback is not None:
            ctx = self._context(engine_ctx, fill.symbol)
            if legacy:
                callback(ctx)
            else:
                callback(ctx, Execution(ctx.symbol, fill.side, float(fill.quantity), float(fill.price), ctx.date, float(fill.fee)))

    def on_risk_event(self, engine_ctx, event):
        for n, strategy in enumerate(self.strategies):
            callback = getattr(strategy, "on_risk_event", None)
            if callback is not None:
                ctx = self._context(engine_ctx, n)
                callback(ctx, {**event, "date": ctx.date})

    def on_bar(self, engine_ctx):
        t = engine_ctx.t
        for n in self.available[t]:
            ctx = self._context(engine_ctx, n)
            strategy = self.strategies[n]
            if self.seen[n] == 0 and hasattr(strategy, "init"):
                strategy.init(ctx)
                ctx.orders.clear()
            if self.seen[n] == self.warmup and self.warmup_done[n] is not None:
                self.warmup_done[n](ctx)
            strategy.on_bar(ctx)
            if self.end_of_day[n] is not None:
                self.end_of_day[n](ctx)
            can_order = self.seen[n] >= self.warmup
            self.seen[n] += 1
            if self.market_filter is not None and not self.market_filter[t, n]:
                engine_ctx.exit(n)
                self.submitted[t, n, 1] = 3
            elif can_order:
                for _, action in ctx.orders:
                    if action == 1 and ctx.position <= 0:
                        engine_ctx.enter(n, 1)
                        self.submitted[t, n, 0] = 1
                    elif action == -1 and ctx.position >= 0:
                        engine_ctx.enter(n, -1)
                        self.submitted[t, n, 0] = -1
                    elif (action == 2 and ctx.position > 0) or (action == 3 and ctx.position < 0):
                        engine_ctx.exit(n)
                        self.submitted[t, n, 1] = 1 if action == 2 else 2
            ctx.orders.clear()

    def finish(self):
        for n, callback in enumerate(self.stops):
            if callback is not None and self.seen[n]:
                ctx = self.contexts[n]
                self.use_context(ctx)
                callback(ctx)


def _indicator_method(name):
    def indicator(self, symbol_or_period, period=None):
        ctx = getattr(self, "_studio_ctx", None)
        if ctx is None:
            raise RuntimeError("Indicator helpers are available inside init, on_bar, on_data and rebalance")
        if period is None:
            symbol_or_period, period = None, symbol_or_period
        return ctx.indicator(name, symbol_or_period, period)

    indicator.__name__, indicator.__doc__ = name, f"A {name.upper()} handle: .value, .ready, .window, .history(n)."
    return indicator


class UsedIndicator:
    """A user indicator class run by `self.use(...)`: `update(self, ctx)` returns a number or a {name: number} dict each bar,
    before the strategy's on_bar sees it; every output is plotted, so the chart and the backtest read the same numbers.
    Class attributes: `inputs = {"n": (20, 5, 100, 1)}` (tuples join Build's Inputs as `Class_n`), `chart = "main"` or "own",
    `plots = {"upper": {"color": "#f80", "style": "line"}}` ({"display": "none"} keeps an output off the chart), `fills = [("upper", "lower")]`,
    `levels = {"overbought": 70}` (flat lines in the indicator's pane).
    Instead of `update`, `compute(self, bars)` may return {name: array} for the whole history at once (bars: open, high, low, close,
    volume, date and, when the run has a benchmark, market arrays); the value at each bar is read from it, so vectorised `ta` functions run once. Only causal maths belongs
    there: the look-ahead check replays the run on cut history and reports any value that changes."""

    def __init__(self, cls, params, kwargs):
        declared = getattr(cls, "inputs", {}) or {}
        unknown = set(kwargs) - set(declared)
        if unknown:
            raise ValueError(f"{cls.__name__} has no input {min(unknown)!r}; declare it in {cls.__name__}.inputs")
        inputs = {}
        for k, v in declared.items():
            default = v[0] if isinstance(v, tuple) else v
            got = kwargs.get(k, params.get(f"{cls.__name__}_{k}", default))
            # Build's Inputs send floats; an input declared as an integer (a window length) stays one.
            inputs[k] = int(got) if isinstance(default, int) and isinstance(got, float) and got.is_integer() else got
        self.impl = cls()
        self.impl.inputs = inputs
        self.name = cls.__name__ + (f"({', '.join(f'{v:g}' if isinstance(v, (int, float)) else str(v) for v in inputs.values())})" if inputs else "")
        self.chart = getattr(cls, "chart", "own")
        self.styles = getattr(cls, "plots", {}) or {}
        self.fills = getattr(cls, "fills", []) or []
        self.levels = getattr(cls, "levels", {}) or {}
        self.out, self._t, self._series = {}, None, None

    def step(self, ctx):
        if self._t == ctx.t:
            return
        self._t = ctx.t
        if hasattr(self.impl, "compute"):
            if self._series is None:
                n = len(ctx._dates)
                cols = {f: np.asarray(ctx._cols[f], dtype=float) for f in ("open", "high", "low", "close", "volume")} | {"date": np.asarray(ctx._dates)}
                if getattr(ctx, "_benchmark", None) is not None:
                    cols["market"] = np.asarray(ctx._benchmark, dtype=float)
                bars = MappingProxyType(cols)
                got = self.impl.compute(bars)
                if not isinstance(got, dict):
                    raise ValueError(f"{self.name}.compute must return a dict of arrays")
                self._series = {str(k): np.broadcast_to(np.asarray(v, dtype=float), (n,)) for k, v in got.items()}
                # Warm once every output has had a value; outputs that are NaN by design on some bars (Supertrend's up/down) stay ready.
                self._warm = max((int(np.argmax(np.isfinite(v))) if np.isfinite(v).any() else n for v in self._series.values()), default=0)
                for label, level in self.levels.items():
                    ctx.hline(level, chart=self.chart, name=f"{self.name} {label}")
            self.out = {k: float(v[ctx.t]) for k, v in self._series.items()}
        else:
            got = self.impl.update(ctx)
            self.out = {k: float(v) for k, v in got.items()} if isinstance(got, dict) else {"": float(got)}
            if self.levels and ctx.t == 0:
                for label, level in self.levels.items():
                    ctx.hline(level, chart=self.chart, name=f"{self.name} {label}")
        for key, value in self.out.items():
            style = self.styles.get(key, {}) if key else next(iter(self.styles.values()), {})
            if style.get("display") == "none":
                continue
            ctx.plot(f"{self.name}.{key}" if key else self.name, value, chart=style.get("chart", self.chart), color=style.get("color"), width=style.get("width"), style=style.get("style"))
        for a, b in self.fills:
            ctx.fill(f"{self.name}.{a}", f"{self.name}.{b}")

    @property
    def value(self):
        if len(self.out) != 1:
            raise ValueError(f"{self.name} has several outputs; read one with [name]")
        return next(iter(self.out.values()))

    def __getitem__(self, key):
        return self.out[key]

    @property
    def ready(self):
        if self._series is not None:
            return self._t >= self._warm
        return bool(self.out) and all(math.isfinite(v) for v in self.out.values())


def bind_indicators(strategy):
    """LEAN's `self.sma(symbol, 50)` form next to `ctx.indicator`; a method the user wrote wins.
    Also `self.use(IndicatorClass, **inputs)`: the indicator updates and plots itself before every on_bar."""
    for name in INDICATOR_NAMES:
        if not hasattr(type(strategy), name):
            setattr(strategy, name, MethodType(_indicator_method(name), strategy))
    used = []

    def use(self, cls, **inputs):
        ctx = getattr(self, "_studio_ctx", None)
        handle = UsedIndicator(cls, ctx.params if ctx is not None else {}, inputs)
        used.append(handle)
        if ctx is not None:
            handle.step(ctx)
        return handle

    if not hasattr(type(strategy), "use"):
        strategy.use = MethodType(use, strategy)
    on_bar = getattr(strategy, "on_bar", None)
    if on_bar is not None:  # portfolio strategies may only rebalance

        def stepped(ctx):
            for handle in used:
                handle.step(ctx)
            return on_bar(ctx)

        strategy.on_bar = stepped
    return strategy


def _debug_table(value):
    """A DataFrame, Series or array for the debugger's variable explorer: first 5 and last 50 rows of up to 20 columns,
    column types, a min/max/mean/missing summary, and a 60-point sparkline of each numeric column."""
    if isinstance(value, np.ndarray) and 1 <= value.ndim <= 2:
        grid = value.reshape(-1, 1) if value.ndim == 1 else value
        grid = grid[:, :20]
        columns, index, dtypes = [str(i) for i in range(grid.shape[1])], list(range(len(grid))), [str(value.dtype)] * grid.shape[1]
    elif hasattr(value, "iloc") and hasattr(value, "columns"):  # pandas DataFrame, without importing pandas here
        part = value.iloc[:, :20]
        grid, columns, index, dtypes = part.to_numpy(), [str(c)[:64] for c in part.columns], [str(i)[:32] for i in part.index], [str(d) for d in part.dtypes]
    elif hasattr(value, "iloc") and hasattr(value, "index") and hasattr(value, "to_numpy"):  # pandas Series
        grid, columns, index, dtypes = value.to_numpy().reshape(-1, 1), [str(value.name if value.name is not None else "value")[:64]], [str(i)[:32] for i in value.index], [str(value.dtype)]
    else:
        return None
    cell = lambda x: _debug_value(x.item() if isinstance(x, np.generic) else x, 3)
    n = len(grid)
    head = [] if n <= 55 else [[cell(x) for x in row] for row in grid[:5]]
    summary, spark = [], []
    for k in range(grid.shape[1]):
        try:
            col = np.asarray(grid[:, k], dtype=float)
        except (TypeError, ValueError):  # text or object column
            summary.append(None)
            spark.append(None)
            continue
        ok = col[np.isfinite(col)]
        summary.append({"min": _debug_value(float(ok.min())), "max": _debug_value(float(ok.max())), "mean": _debug_value(float(ok.mean())), "missing": int(n - len(ok))} if len(ok) else {"missing": int(n)})
        picks = col[np.linspace(0, n - 1, min(n, 60)).astype(int)] if n else col
        spark.append([_debug_value(float(x)) for x in picks])
    return {"__table__": {"shape": list(np.shape(value)), "columns": columns, "dtypes": dtypes, "summary": summary, "spark": spark,
                          "head": head, "head_index": [index[i] for i in range(len(head))],
                          "index": index[max(0, n - 50):], "rows": [[cell(x) for x in row] for row in grid[-50:]]}}


_MISSING = object()


def _watched(frame, path):
    """The value of `name` or `self.name` in this frame, or _MISSING when it is not in scope."""
    if path.startswith("self."):
        owner = frame.f_locals.get("self", _MISSING)
        return _MISSING if owner is _MISSING else getattr(owner, path[5:], _MISSING)
    return frame.f_locals.get(path, _MISSING)


def _changed(old, new):
    try:
        return bool(np.any(np.asarray(old != new)))
    except (TypeError, ValueError):  # shapes or types that do not compare
        return repr(old) != repr(new)


def _debug_value(value, depth=0):
    if isinstance(value, np.generic):
        value = value.item()
    if type(value) is str:
        return value[:512]
    if value is None or type(value) is bool:
        return value
    if type(value) in (int, float):
        return value if -sys.float_info.max <= value <= sys.float_info.max else None
    if depth < 3 and type(value) in (list, tuple):
        return [_debug_value(item, depth + 1) for item in value[:20]]
    if depth < 3 and type(value) is dict:
        return {key[:128]: _debug_value(item, depth + 1) for key, item in list(value.items())[:20] if type(key) is str}
    return _debug_table(value) if depth < 3 else None


def _debug_snapshot(adapter, account, submitted, bars, dates, symbols, n, captured_fills):
    t = len(submitted) - 1
    is_portfolio = isinstance(adapter, PortfolioStrategy)
    strategy = adapter.strategy if is_portfolio else adapter.strategies[n]
    state = _debug_value({key: value for key, value in vars(strategy).items()
                          if not key.startswith("_") and not callable(value)} if hasattr(strategy, "__dict__") else {})
    holding = account.positions.get(n)
    equity, _, _, _ = account._mark()
    orders = []
    for column, (quantity, exit_side, limit, stop, canceled) in enumerate(submitted[t]):
        if quantity or exit_side or canceled:
            orders.append({
                "symbol": symbols[column], "quantity_or_direction": float(quantity),
                "exit_side": int(exit_side), "limit": float(limit) or None, "stop": float(stop) or None, "canceled": bool(canceled),
            })
    return {
        "date": dates[t], "symbol": symbols[n], "bar_index": t, "state": state,
        "context": {"cash": _debug_value(float(account.cash)), "total_value": _debug_value(float(equity)),
                    "quantity": float(holding.shares) if holding else 0,
                    **{field: _debug_value(float(series[t, n])) for field, series in bars.items()}},
        "orders": orders, "fills": captured_fills,
    }


def event_run(z, meta, load_strategy, make_contexts, use_context, values, current_context):
    # Isolated mode excludes the repository from sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    try:
        from app.services.studio_v3.core import engine
    finally:
        sys.path.pop(0)
    bars = {field: z[f"raw_{field}"] for field in ("open", "high", "low", "close", "volume")}
    available = [np.flatnonzero(row).tolist() for row in np.isfinite(bars["close"])]
    shape = bars["close"].shape
    params = engine.Params(**meta["event_settings"])
    gate, stop_dist, size_vol = (z.get(name) for name in ("market_filter", "stop_dist", "size_vol"))

    def run_to(end, collect):
        use_context(None)
        cls, warmup = load_strategy()
        submitted = np.zeros((end, shape[1], 5))
        contexts = make_contexts(collect)
        if hasattr(cls, "on_data"):
            adapter = PortfolioStrategy(cls, PortfolioContext(contexts, bars, values), warmup, use_context, submitted, gate)
        else:
            adapter = EventStrategy(cls, contexts, available, warmup, use_context, gate, submitted)
        account = engine.EventEngine({k: v[:end] for k, v in bars.items()}, params, stop_dist=stop_dist, size_vol=size_vol)
        target = meta["debug_symbol"]
        after, event = meta["debug_after"], meta["debug_event"]
        captured_fills = {}
        paused = None
        hit = None
        hit_count = 0
        prior_equity = None
        equity_change = None
        bp = meta["debug_breakpoint"]
        comparisons = {"Eq": operator.eq, "NotEq": operator.ne, "Lt": operator.lt, "LtE": operator.le,
                       "Gt": operator.gt, "GtE": operator.ge}

        armed = False
        trigger = bp.get("trigger") if bp else None
        triggered = trigger is None
        need = (bp or {}).get("hit") or 1
        watched = [_MISSING]

        def trace(frame, trace_event, arg):
            nonlocal hit, hit_count, armed, triggered
            name = frame.f_code.co_filename
            if bp.get("step"):  # F11: after the given line runs on the paused bar, stop at the next line of any strategy file
                if not name.startswith("<studio:"):
                    return None
                ctx = current_context() if trace_event == "line" else None
                if ctx is not None and hit is None and ctx.t == after and (ctx.symbol is None or ctx.symbol == target) and column in available[ctx.t]:
                    if armed:
                        hit = {"file": name[8:-1], "line": frame.f_lineno, "hit_count": 1, "bar": ctx.t, "locals": _debug_value(frame.f_locals)}
                    elif name == f"<studio:{bp['file']}>" and frame.f_lineno == bp["line"]:
                        armed = True
                return trace
            if bp.get("watch"):  # data breakpoint: stop at the first line where the watched value differs from its last seen value
                if not name.startswith("<studio:"):
                    return None
                if trace_event == "line" and hit is None:
                    value = _watched(frame, bp["watch"])
                    if value is not _MISSING:
                        ctx = current_context()
                        if watched[0] is not _MISSING and _changed(watched[0], value) and ctx is not None and (ctx.symbol is None or ctx.symbol == target) and column in available[ctx.t]:
                            hit_count += 1
                            if ctx.t > after and hit_count >= need:
                                hit = {"file": name[8:-1], "line": frame.f_lineno, "hit_count": hit_count, "bar": ctx.t, "locals": _debug_value(frame.f_locals),
                                       "watch": {"name": bp["watch"], "before": _debug_value(watched[0]), "after": _debug_value(value)}}
                        watched[0] = copy.copy(value)
                return trace
            if name != f"<studio:{bp['file']}>" and not (trigger and name == f"<studio:{trigger['file']}>"):
                return None
            if trace_event == "line" and trigger and not triggered and name == f"<studio:{trigger['file']}>" and frame.f_lineno == trigger["line"]:
                ctx = current_context()
                triggered = ctx is not None and (ctx.symbol is None or ctx.symbol == target) and column in available[ctx.t]
            if trace_event == "line" and triggered and name == f"<studio:{bp['file']}>" and frame.f_lineno == bp["line"]:
                ctx = current_context()
                if ctx is not None and (ctx.symbol is None or ctx.symbol == target) and column in available[ctx.t]:
                    values = {"date": ctx.date, "symbol": ctx.symbol or target}
                    if all(comparisons[op](values[name], expected) for name, op, expected in bp["condition"]):
                        hit_count += 1
                        if ctx.t > after and hit is None and hit_count >= need:
                            hit = {"file": bp["file"], "line": bp["line"], "hit_count": hit_count, "bar": ctx.t,
                                   "locals": _debug_value(frame.f_locals)}
            return trace

        def stop_at_event(t, equity):
            nonlocal paused, prior_equity, equity_change
            equity_change = float((equity - prior_equity) / prior_equity) if prior_equity and prior_equity > 0 else None
            prior_equity = equity
            executions = captured_fills.pop(t, [])
            if t < after + (not (bp and bp.get("step"))) or column not in available[t]:
                return False
            if event == "breakpoint":
                matched = hit is not None and hit["bar"] == t
            elif event == "equity":
                matched = equity_change is not None and equity_change <= -meta["debug_loss"]
            elif event == "fill":
                matched = any(fill["symbol"] == target for fill in executions)
            else:
                quantity, exit_side = submitted[t, column, :2]
                matched = bool(quantity or exit_side in (1, 2))
            if matched:
                paused = (t, executions)
            return matched

        if target is not None:
            column = meta["symbols"].index(target)
            on_fill = adapter.on_fill

            def capture_fill(ctx, fill):
                if (after is None and fill.bar == end - 1) or (after is not None and fill.bar > after):
                    captured_fills.setdefault(fill.bar, []).append({
                        "symbol": meta["symbols"][fill.symbol], "side": fill.side,
                        "quantity": float(fill.quantity), "price": float(fill.price), "fee": float(fill.fee),
                    })
                on_fill(ctx, fill)

            adapter.on_fill = capture_fill
        if bp:
            sys.settrace(trace)
        try:
            result = account.run(adapter, stop_after=stop_at_event if event else None)
        finally:
            if bp:
                sys.settrace(None)
        if collect and target is None:
            adapter.finish()
        if target is not None and event is None:
            paused = (end - 1, captured_fills.get(end - 1, []))
        debug = None
        if paused is not None:
            t, executions = paused
            debug = _debug_snapshot(adapter, account, submitted[:t + 1], bars, meta["dates"], meta["symbols"], column, executions)
            if event == "equity":
                debug["equity_change"] = equity_change
            if hit is not None:
                debug["breakpoint"] = {key: value for key, value in hit.items() if key != "bar"}
        return engine.Result(*result[:7], unfilled=int(result[7]), risk_events=account.risk_events, orders=account.order_log), submitted, warmup, isinstance(adapter, PortfolioStrategy), debug

    result, submitted, warmup, is_portfolio, debug = run_to(shape[0], True)
    dates = meta["dates"]
    start_dates = {}
    if is_portfolio:
        starts = dates[warmup] if warmup < len(dates) else None
    else:
        for n, symbol in enumerate(meta["symbols"]):
            observed = np.flatnonzero(np.isfinite(bars["close"][:, n]))
            start_dates[symbol] = dates[int(observed[warmup])] if warmup < len(observed) else None
        starts = min((day for day in start_dates.values() if day is not None), default=None)
    warmup_report = {"bars": warmup, "first_eligible_date": starts, "first_eligible_by_symbol": start_dates}
    cuts, changed = meta["repaint_bars"], []
    for t in cuts:
        _, cut, _, _, _ = run_to(t + 1, False)
        if not np.array_equal(cut[-1], submitted[t]):
            changed.append(meta["dates"][t])
    repaint = {"cuts": len(cuts), "changed": len(changed), "dates": changed[:5]} if cuts else None
    return vars(result), repaint, int(np.count_nonzero(submitted[:, :, 0])), warmup_report, debug


def main():
    src = sys.stdin.read()
    z = np.load(sys.argv[1], allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    fields = {f: z[f] for f in ("open", "high", "low", "close", "volume")}
    values = {e: z[f"v{i}"] for i, e in enumerate(meta["exprs"])}
    benchmark = z.get("benchmark")
    T, N = fields["close"].shape
    logs, plots, plot_charts, marks, tables = [], {}, {}, [], {}
    draw = {"styles": {}, "hlines": [], "fills": [], "bg": []}
    order_lines = {}
    invariants = {"count": 0, "rows": []}
    ctx = None

    def use_context(value):
        nonlocal ctx
        ctx = value

    def capture_print(*values, sep=" ", end="\n"):
        if ctx is not None and ctx._logs is not None and len(logs) <= 50_000:
            for line in (sep.join(str(v) for v in values) + end).splitlines():
                ctx._log(line, "info", sys._getframe(1).f_lineno)
                if len(logs) > 50_000:
                    break

    def load_strategy():
        modules = {}
        builtins = {**SAFE_BUILTINS, "print": capture_print}

        imported = {}

        def project_import(name, globals_=None, locals_=None, fromlist=(), level=0):
            fromlist = tuple(fromlist or ())
            if not level and (name == "studio.ta" or (name == "studio" and fromlist == ("ta",))):
                if "studio" not in imported:
                    spec = importlib.util.spec_from_file_location("studio.ta", Path(__file__).with_name("ta.py"))
                    ta = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(ta)
                    imported["studio"] = ModuleType("studio")
                    imported["studio"].ta = ta
                return imported["studio"]
            if name in helper_code and not level:
                if any(item == "*" or item.startswith("_") for item in fromlist):
                    raise ImportError("Only named imports from saved project modules are allowed")
            elif not level and (name in ALLOWED_IMPORTS or (name == "scipy" and fromlist == ("stats",))
                                # C code (ndarray.mean, ...) imports its own helpers lazily through the caller's builtins, with an empty fromlist and a
                                # dotted name. A user statement for such a module is refused earlier by pycode.check; this layer keeps the root allow-list.
                                or name in LAZY_LIBRARY_MODULES
                                or (name.split(".")[0] in ALLOWED_ROOTS and not set(name.split(".")) & {"ctypeslib", "f2py", "distutils", "testing"})):
                if name not in imported:
                    imported[name] = importlib.import_module(name)
                return imported[name]
            else:
                raise ImportError(f"Import '{name}' is not allowed; allowed: {', '.join(ALLOWED_IMPORTS)} and saved project modules")
            if name not in modules:
                module = modules[name] = ModuleType(name)
                module.__dict__.update({"__builtins__": builtins, "math": math})
                try:
                    exec(helper_code[name], module.__dict__)  # noqa: S102 project source was checked by pycode.check_project
                except BaseException:
                    del modules[name]
                    raise
            return modules[name]

        builtins["__import__"] = project_import
        g = {"__builtins__": builtins, "__name__": "strategy", "math": math}
        exec(compiled, g)  # noqa: S102 source was checked by pycode.check
        cls = g.get("Strategy") or g.get("Indicator")
        if cls is None:
            raise NameError("define class Strategy (or class Indicator) with on_bar(self, ctx)")
        if cls is g.get("Indicator") and "Strategy" not in g:
            Ctx._default_chart = "main" if getattr(cls, "overlay", False) is True else "own"
        warmup = getattr(cls, "warmup", 0)
        if type(warmup) is not int or warmup < 0:
            raise ValueError("Strategy.warmup must be a nonnegative integer")
        return cls, warmup

    def make_contexts(collect):
        contexts = [
            Ctx({f: a[:, j] for f, a in fields.items()}, {e: a[:, j] for e, a in values.items()},
                meta["params"].copy(), symbol, meta["dates"])
            for j, symbol in enumerate(meta["symbols"])
        ]
        plot_count, table_count = [0], [0]
        for item in contexts:
            item._benchmark = benchmark
            item._logs = logs if collect else None
            item._plots = plots if collect else None
            item._plot_count = plot_count
            item._plot_charts = plot_charts
            item._draw = draw
            item._symbols = meta["symbols"]
            item._marks = marks if collect else None
            item._tables = tables if collect else None
            item._table_count = table_count
            item._order_lines = order_lines if collect else None
            item._invariants = invariants if collect else None
        return contexts

    repaint = None
    entry_signals = None
    warmup_report = debug = None
    try:
        compiled = compile(src, "<studio:main.py>", "exec")
        profiler = _LineProfiler() if meta.get("profile") else None
        logpoints = _Logpoints(meta["logpoints"], lambda: ctx, meta.get("coverage")) if (meta.get("logpoints") or meta.get("coverage")) and not profiler else None
        helper_code = {name[:-3]: compile(source, f"<studio:{name}>", "exec") for name, source in meta["modules"].items()}
        if meta["event_settings"] is not None:
            def run_events():
                return event_run(z, meta, load_strategy, make_contexts, use_context, values, lambda: ctx)

            arrays, repaint, entry_signals, warmup_report, debug = profiler.run(run_events) if profiler else logpoints.run(run_events) if logpoints else run_events()
        else:
            cls, warmup = load_strategy()
            entries, exits = np.zeros((T, N), np.int8), np.zeros((T, N), np.int8)
            contexts = make_contexts(True)
            for j, ctx in enumerate(contexts):
                s = bind_indicators(cls())
                s._studio_ctx = ctx
                if hasattr(s, "init"):
                    s.init(ctx)
                live = np.flatnonzero(np.isfinite(fields["close"][:, j]))
                for index, t in enumerate(live):
                    ctx._t = int(t)
                    ctx.orders.clear()
                    s.on_bar(ctx)
                    if index < warmup:
                        continue
                    for _, a in ctx.orders:
                        if a == 1 and ctx.position <= 0:
                            entries[t, j], ctx.position = 1, 1
                        elif a == -1 and ctx.position >= 0:
                            entries[t, j], ctx.position = -1, -1
                        elif a == 2 and ctx.position > 0:
                            exits[t, j] |= 1
                            ctx.position = 0
                        elif a == 3 and ctx.position < 0:
                            exits[t, j] |= 2
                            ctx.position = 0
                        else:
                            continue
                        if hasattr(s, "on_fill"):
                            s.on_fill(ctx)
            arrays = {"entries": entries, "exits": exits}
    except BaseException as e:  # noqa: BLE001 report to the parent with the user's line
        tb = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.startswith("<studio:")]
        line = tb[-1].lineno if tb else getattr(e, "lineno", None)
        column = ((tb[-1].colno or 0) + 1) if tb else getattr(e, "offset", None)
        frames = [{"file": f.filename[8:-1], "line": f.lineno, "column": (f.colno or 0) + 1, "function": f.name} for f in tb[-8:]]
        filename = getattr(e, "filename", "") or ""
        source_file = frames[-1]["file"] if frames else filename[8:-1] if filename.startswith("<studio:") else "main.py"
        walked = [frame for frame, _ in traceback.walk_tb(e.__traceback__) if frame.f_code.co_filename.startswith("<studio:")]
        failing = walked[-1] if walked else None
        owner = failing.f_locals.get("self") if failing is not None else None
        at_bar = {"symbol": getattr(ctx, "symbol", None), "date": ctx.date if ctx is not None and ctx.t < len(ctx._dates) else None, "bar_index": getattr(ctx, "t", None),
                  "variables": _debug_value({k: v for k, v in (failing.f_locals if failing else {}).items() if not k.startswith("_") and k not in ("self", "ctx")}),
                  "state": _debug_value({k: v for k, v in vars(owner).items() if not k.startswith("_") and not callable(v)} if hasattr(owner, "__dict__") else {})}
        sys.stdout.write(json.dumps({"error": f"{type(e).__name__}: {e}"[:1024], "problem": {
            "file": source_file, "line": line, "column": column, "exception_type": type(e).__name__, "traceback": frames, "locals": at_bar,
        }}))
        return
    risk_events = arrays.pop("risk_events", [])
    orders = arrays.pop("orders", [])
    np.savez(sys.argv[2], **arrays)
    sys.stdout.write(json.dumps({"ok": True, "logs": logs, "plots": plots, "plot_charts": plot_charts, "draw": draw, "marks": marks, "tables": tables, "repaint": repaint, "entry_signals": entry_signals, "warmup": warmup_report, "debug": debug, "risk_events": risk_events, "orders": orders,
                                "order_lines": sorted(order_lines.values(), key=lambda r: (r["file"], r["line"])), "invariants": invariants,
                                "profile": profiler.report({"main.py": src, **meta["modules"]}) if profiler else None,
                                "coverage": logpoints.coverage({"main.py": compiled, **{f"{k}.py": v for k, v in helper_code.items()}}) if logpoints and logpoints.hit is not None else None}))


if __name__ == "__main__":
    main()
