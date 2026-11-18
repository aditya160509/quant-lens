"""Child process for Python strategies. Run as `python -I pyrunner.py <in.npz> <out.npz>`, code on stdin.

The child runs user callbacks with restricted builtins. Event runs use Studio's shared fill engine.
"""

import inspect
import json
import math
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

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

    def plot(self, name, value):
        value = float(value)
        name = str(name)[:128]
        if self._plots is not None and self._plot_count[0] < 50_000:
            self._plots.setdefault(name, []).append({
                "date": self.date, "symbol": self.symbol, "value": value if math.isfinite(value) else None,
            })
            self._plot_count[0] += 1

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
            strategy.on_bar(ctx)
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


def event_run(z, meta, load_strategy, make_contexts, use_context):
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
        submitted = np.zeros((end, shape[1], 2), dtype=np.int8)
        adapter = EventStrategy(cls, make_contexts(collect), available, warmup, use_context, gate, submitted)
        result = engine.EventEngine({k: v[:end] for k, v in bars.items()}, params, stop_dist=stop_dist, size_vol=size_vol).run(adapter)
        return engine.Result(*result[:7], unfilled=int(result[7])), submitted

    result, submitted = run_to(shape[0], True)
    cuts, changed = meta["repaint_bars"], []
    for t in cuts:
        _, cut = run_to(t + 1, False)
        if not np.array_equal(cut[-1], submitted[t]):
            changed.append(meta["dates"][t])
    repaint = {"cuts": len(cuts), "changed": len(changed), "dates": changed[:5]} if cuts else None
    return vars(result), repaint, int(np.count_nonzero(submitted[:, :, 0]))


def main():
    src = sys.stdin.read()
    z = np.load(sys.argv[1], allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    fields = {f: z[f] for f in ("open", "high", "low", "close", "volume")}
    values = {e: z[f"v{i}"] for i, e in enumerate(meta["exprs"])}
    T, N = fields["close"].shape
    logs, plots = [], {}
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
        g = {"__builtins__": {**SAFE_BUILTINS, "print": capture_print}, "__name__": "strategy", "math": math}
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
        plot_count = [0]
        for item in contexts:
            item._logs = logs if collect else None
            item._plots = plots if collect else None
            item._plot_count = plot_count
        return contexts

    repaint = None
    entry_signals = None
    try:
        compiled = compile(src, "<strategy>", "exec")
        if meta["event_settings"] is not None:
            arrays, repaint, entry_signals = event_run(z, meta, load_strategy, make_contexts, use_context)
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
        tb = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == "<strategy>"]
        line = tb[-1].lineno if tb else getattr(e, "lineno", None)
        column = ((tb[-1].colno or 0) + 1) if tb else getattr(e, "offset", None)
        frames = [{"file": "main.py", "line": f.lineno, "column": (f.colno or 0) + 1, "function": f.name} for f in tb[-8:]]
        sys.stdout.write(json.dumps({"error": f"{type(e).__name__}: {e}"[:1024], "problem": {
            "file": "main.py", "line": line, "column": column, "exception_type": type(e).__name__, "traceback": frames,
        }}))
        return
    np.savez(sys.argv[2], **arrays)
    sys.stdout.write(json.dumps({"ok": True, "logs": logs, "plots": plots, "repaint": repaint, "entry_signals": entry_signals}))


if __name__ == "__main__":
    main()
