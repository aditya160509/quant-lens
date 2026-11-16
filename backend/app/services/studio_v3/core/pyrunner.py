"""Child process for Python strategies. Run as `python -I pyrunner.py <in.npz> <out.npz>`, code on stdin.

Stand-alone on purpose (numpy only): it never imports the app, so user code cannot reach it.
"""

import json
import math
import sys
import traceback

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
            return self._a[max(lo, 0):hi].tolist()
        if k >= 0:
            raise IndexError("use negative indexes: close[-1] is this bar")
        i = t + 1 + k
        return float(self._a[i]) if i >= 0 else float("nan")

    def __len__(self):
        return self._ctx.t + 1


class Ctx:
    def __init__(self, cols, values, params, symbol, dates):
        self.t = 0
        self.symbol, self.position, self.params = symbol, 0, params
        self._cols, self._values, self._dates = cols, values, dates
        self.open, self.high, self.low, self.close, self.volume = (History(cols[f], self) for f in ("open", "high", "low", "close", "volume"))
        self.orders = []

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


def main():
    src = sys.stdin.read()
    z = np.load(sys.argv[1], allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    fields = {f: z[f] for f in ("open", "high", "low", "close", "volume")}
    values = {e: z[f"v{i}"] for i, e in enumerate(meta["exprs"])}
    T, N = fields["close"].shape
    entries, exits = np.zeros((T, N), np.int8), np.zeros((T, N), np.int8)
    g = {"__builtins__": SAFE_BUILTINS, "__name__": "strategy", "math": math}
    try:
        exec(compile(src, "<strategy>", "exec"), g)  # noqa: S102 the point of this process; checked by pycode.check first
        cls = g.get("Strategy")
        if cls is None:
            raise NameError("define class Strategy with on_bar(self, ctx)")
        for j in range(N):
            col = {f: a[:, j] for f, a in fields.items()}
            ctx = Ctx(col, {e: a[:, j] for e, a in values.items()}, meta["params"], meta["symbols"][j], meta["dates"])
            s = cls()
            if hasattr(s, "init"):
                s.init(ctx)
            live = np.flatnonzero(np.isfinite(col["close"]))
            for t in live:
                ctx.t = int(t)
                ctx.orders.clear()
                s.on_bar(ctx)
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
    except BaseException as e:  # noqa: BLE001 report to the parent with the user's line
        tb = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == "<strategy>"]
        line = tb[-1].lineno if tb else getattr(e, "lineno", None)
        sys.stdout.write(json.dumps({"error": f"{type(e).__name__}: {e}", "line": line}))
        return
    np.savez(sys.argv[2], entries=entries, exits=exits)
    sys.stdout.write(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
