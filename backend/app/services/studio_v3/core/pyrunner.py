"""Child process for Python strategies. Run as `python -I pyrunner.py <in.npz> <out.npz>`, code on stdin.

The child runs user callbacks with restricted builtins. Event runs use Studio's shared fill engine.
"""

import inspect
import json
import math
import sys
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType, ModuleType

import numpy as np

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

    def __getitem__(self, offset):
        if type(offset) is not int:
            raise TypeError("History offsets must be integers")
        if offset > 0:
            raise IndexError(f"history[{offset}] reads a future bar; use 0 for current or a negative offset")
        if -offset >= len(self):
            raise IndexError(f"history[{offset}] is outside the requested window")
        return float(self._values[len(self) - 1 + offset])


class Ctx:
    def __init__(self, cols, values, params, symbol, dates):
        self._t = 0
        self.symbol, self.position, self.params = symbol, 0, params
        self._cols, self._values, self._dates = cols, values, dates
        self.open, self.high, self.low, self.close, self.volume = (History(cols[f], self) for f in ("open", "high", "low", "close", "volume"))
        self.orders = []

    @property
    def t(self):
        return self._t

    @property
    def date(self):
        return str(self._dates[self.t])

    @property
    def bar(self):
        return self.t

    def history(self, fields, n):
        """Read a bounded history window. Offset zero is the current bar."""
        if type(n) is not int or n < 1:
            raise ValueError("history requires a positive integer window")
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

    def log(self, message, level="info"):
        self._log(message, level, sys._getframe(1).f_lineno)

    def _log(self, message, level, line):
        if self._logs is None or len(self._logs) > 50_000:
            return
        text = str(message)[:1024] if len(self._logs) < 50_000 else "Output truncated after 50000 lines"
        self._logs.append({"date": self.date, "symbol": self.symbol, "line": line, "text": text, "level": str(level)[:32]})

    def plot(self, name, value, chart="own"):
        """Record a value in a named plot on the main chart or in a separate pane."""
        if chart not in ("main", "own"):
            raise ValueError("Plot chart must be main or own")
        value = float(value)
        name = str(name)[:128]
        if self._plots is not None and self._plot_count[0] < 50_000:
            if self._plot_charts.setdefault(name, chart) != chart:
                raise ValueError("A named plot must keep the same chart")
            self._plots.setdefault(name, []).append({
                "date": self.date, "symbol": self.symbol, "value": value if math.isfinite(value) else None,
            })
            self._plot_count[0] += 1

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

    def _order(self, action):
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


class PortfolioContext(Ctx):
    def __init__(self, contexts, bars, values):
        first = contexts[0]
        super().__init__(first._cols, first._values, first.params.copy(), None, first._dates)
        self._benchmark = first._benchmark
        self._symbols, self._marks = first._symbols, first._marks
        self._tables, self._table_count = first._tables, first._table_count
        self._plot_charts = first._plot_charts
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

    def history(self, fields, n, sym=None):
        """Read bounded history for one symbol or for the entire universe."""
        if sym is None:
            return MappingProxyType({symbol: self.history(fields, n, symbol) for symbol in self.symbols})
        ctx = self._contexts[sym]
        ctx._t = self.t
        return ctx.history(fields, n)

    def value(self, expr, symbol=None):
        if symbol is None:
            raise ValueError("ctx.value(formula, symbol) needs a symbol in on_data")
        ctx = self._contexts[symbol]
        ctx._t = self.t
        return ctx.value(expr)

    def rule(self, expr, symbol=None):
        return self.value(expr, symbol) > 0

    def _cross_section(self, expr):
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
        self.orders.append((symbol, 1))

    def sell(self, symbol):
        self.orders.append((symbol, 2))

    def short(self, symbol):
        self.orders.append((symbol, -1))

    def cover(self, symbol):
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

    def order_value(self, symbol, value):
        current = self.bar(symbol)
        if current is not None:
            self.market_order(symbol, float(value) / current.close)

    def target_weights(self, weights):
        for symbol, weight in weights.items():
            self.set_holdings(symbol, weight)

    order = market_order
    limit = limit_order
    stop = stop_order
    stop_limit = stop_limit_order

    def _submit(self, symbol, quantity, *, limit=None, stop=None):
        self._columns[symbol]
        quantity = float(quantity)
        if not math.isfinite(quantity):
            raise ValueError("Order quantity must be finite")
        if any(price is not None and (not math.isfinite(price) or price <= 0) for price in (limit, stop)):
            raise ValueError("Order price must be positive and finite")
        if quantity:
            self.orders.append((symbol, (quantity, limit, stop)))

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
        self.strategy = cls()
        self.ctx = ctx
        self.warmup = warmup
        self.use_context = use_context
        self.submitted = submitted
        self.market_filter = market_filter
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
        self.ctx._rebalancing = self._scheduled(self.ctx)
        self.use_context(self.ctx)
        return self.ctx

    def on_bar(self, engine_ctx):
        ctx = self._context(engine_ctx)
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
                    quantity, limit, stop = action
                    engine_ctx._e.pending.pop(n, None)
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


class EventStrategy:
    def __init__(self, cls, contexts, available, warmup, use_context, market_filter, submitted):
        self.contexts = contexts
        self.strategies = [cls() for _ in contexts]
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


def event_run(z, meta, load_strategy, make_contexts, use_context, values):
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
        result = engine.EventEngine({k: v[:end] for k, v in bars.items()}, params, stop_dist=stop_dist, size_vol=size_vol).run(adapter)
        if collect:
            adapter.finish()
        return engine.Result(*result[:7], unfilled=int(result[7])), submitted, warmup, isinstance(adapter, PortfolioStrategy)

    result, submitted, warmup, is_portfolio = run_to(shape[0], True)
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
        _, cut, _, _ = run_to(t + 1, False)
        if not np.array_equal(cut[-1], submitted[t]):
            changed.append(meta["dates"][t])
    repaint = {"cuts": len(cuts), "changed": len(changed), "dates": changed[:5]} if cuts else None
    return vars(result), repaint, int(np.count_nonzero(submitted[:, :, 0])), warmup_report


def main():
    src = sys.stdin.read()
    z = np.load(sys.argv[1], allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    fields = {f: z[f] for f in ("open", "high", "low", "close", "volume")}
    values = {e: z[f"v{i}"] for i, e in enumerate(meta["exprs"])}
    benchmark = z.get("benchmark")
    T, N = fields["close"].shape
    logs, plots, plot_charts, marks, tables = [], {}, {}, [], {}
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

        def project_import(name, globals_=None, locals_=None, fromlist=(), level=0):
            if level or name not in helper_code or any(item == "*" or item.startswith("_") for item in (fromlist or ())):
                raise ImportError("Only named imports from saved project modules are allowed")
            if name not in modules:
                module = modules[name] = ModuleType(name)
                module.__dict__.update({"__builtins__": builtins, "math": math})
                try:
                    exec(helper_code[name], module.__dict__)  # noqa: S102 project source was checked by pycode.check_project
                except BaseException:
                    del modules[name]
                    raise
            return modules[name]

        if helper_code:
            builtins["__import__"] = project_import
        g = {"__builtins__": builtins, "__name__": "strategy", "math": math}
        exec(compiled, g)  # noqa: S102 source was checked by pycode.check
        cls = g.get("Strategy")
        if cls is None:
            raise NameError("define class Strategy with on_bar(self, ctx)")
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
            item._symbols = meta["symbols"]
            item._marks = marks if collect else None
            item._tables = tables if collect else None
            item._table_count = table_count
        return contexts

    repaint = None
    entry_signals = None
    warmup_report = None
    try:
        compiled = compile(src, "<studio:main.py>", "exec")
        helper_code = {name[:-3]: compile(source, f"<studio:{name}>", "exec") for name, source in meta["modules"].items()}
        if meta["event_settings"] is not None:
            arrays, repaint, entry_signals, warmup_report = event_run(z, meta, load_strategy, make_contexts, use_context, values)
        else:
            cls, warmup = load_strategy()
            entries, exits = np.zeros((T, N), np.int8), np.zeros((T, N), np.int8)
            contexts = make_contexts(True)
            for j, ctx in enumerate(contexts):
                s = cls()
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
        sys.stdout.write(json.dumps({"error": f"{type(e).__name__}: {e}"[:1024], "problem": {
            "file": source_file, "line": line, "column": column, "exception_type": type(e).__name__, "traceback": frames,
        }}))
        return
    np.savez(sys.argv[2], **arrays)
    sys.stdout.write(json.dumps({"ok": True, "logs": logs, "plots": plots, "plot_charts": plot_charts, "marks": marks, "tables": tables, "repaint": repaint, "entry_signals": entry_signals, "warmup": warmup_report}))


if __name__ == "__main__":
    main()
