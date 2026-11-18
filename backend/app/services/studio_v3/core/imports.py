"""Home imports: a QuantConnect algorithm through a small AST shim (H-19) and a CSV of signals (H-20)."""

from __future__ import annotations

import ast
import csv
import datetime as dt
import io
import json
import re

from . import data
from .spec import Strategy

INDICATORS = {"sma": "sma", "ema": "ema", "rsi": "rsi", "roc": "roc", "momp": "roc", "std": "std", "max": "highest", "min": "lowest"}
SETTINGS = {"set_start_date", "set_end_date", "set_cash", "set_warm_up", "set_benchmark", "add_equity", "set_brokerage_model", "set_time_zone"}
QUIET = {"debug", "log", "plot", "error"}
OPS = {ast.Gt: ">", ast.Lt: "<", ast.GtE: ">=", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="}
ARITH = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
FIELDS = {"price": "close", "close": "close", "open": "open", "high": "high", "low": "low", "volume": "volume"}


class Unmapped(Exception):
    pass


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _self_call(n: ast.AST) -> str | None:
    """`self.sma(...)` or `self.SMA(...)` -> 'sma'; the trailing name of `self.schedule.on(...)` -> 'schedule.on'."""
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        parts, f = [], n.func
        while isinstance(f, ast.Attribute):
            parts.append(_snake(f.attr))
            f = f.value
        if isinstance(f, ast.Name) and f.id == "self":
            return ".".join(reversed(parts))
    return None


def _num(n: ast.AST) -> float | None:
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return float(n.value)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        v = _num(n.operand)
        return -v if v is not None else None
    return None


class _Shim:
    def __init__(self, src: str):
        self.src, self.tree = src, ast.parse(src)
        self.ind: dict[str, str] = {}
        self.mapped: list[dict] = []
        self.unmapped: list[dict] = []
        self.roles: dict[str, list[str]] = {}

    def text(self, n: ast.AST) -> str:
        return (ast.get_source_segment(self.src, n) or "").strip().splitlines()[0][:120]

    def miss(self, n: ast.AST, reason: str) -> None:
        self.unmapped.append({"line": n.lineno, "call": self.text(n), "reason": reason})

    def hit(self, n: ast.AST, to: str) -> None:
        self.mapped.append({"line": n.lineno, "call": self.text(n), "to": to})

    def indicator(self, call: ast.Call, name: str) -> str:
        f = INDICATORS.get(name)
        n = _num(call.args[1]) if len(call.args) > 1 else None
        if not f or n is None or n != int(n):
            raise Unmapped(f"indicator {name} with these arguments has no Studio operator (supported: {', '.join(sorted(INDICATORS))} with a literal period)")
        return f"{f}(close, {int(n)})"

    def conv(self, n: ast.AST) -> str:
        if (v := _num(n)) is not None:
            return repr(v)
        if isinstance(n, ast.Attribute):
            if n.attr in FIELDS and not (isinstance(n.value, ast.Attribute) and isinstance(n.value.value, ast.Name) and n.value.value.id == "self" and n.value.attr in self.ind):
                return FIELDS[n.attr]
            base = n.value
            while isinstance(base, ast.Attribute) and base.attr in ("current", "value"):
                base = base.value
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id == "self" and base.attr in self.ind:
                return f"({self.ind[base.attr]})"
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in OPS:
            return f"({self.conv(n.left)} {OPS[type(n.ops[0])]} {self.conv(n.comparators[0])})"
        if isinstance(n, ast.BinOp) and type(n.op) in ARITH:
            return f"({self.conv(n.left)} {ARITH[type(n.op)]} {self.conv(n.right)})"
        if isinstance(n, ast.BoolOp):
            parts = [p for p in n.values if not (isinstance(p, ast.Attribute) and p.attr == "is_ready")]
            return "(" + (" & " if isinstance(n.op, ast.And) else " | ").join(self.conv(p) for p in parts) + ")"
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return f"if_else({self.conv(n.operand)}, 0, 1)"
        raise Unmapped("condition is not a comparison of indicators, prices and numbers")

    def add(self, role: str, cond: str | None) -> None:
        self.roles.setdefault(role, []).append(cond or "1")

    def stmts(self, body: list[ast.stmt], cond: str | None) -> None:
        for s in body:
            if isinstance(s, ast.If):
                try:
                    c = self.conv(s.test)
                except Unmapped as e:
                    self.miss(s, str(e))
                    continue
                self.stmts(s.body, f"({cond} & {c})" if cond else c)
                neg = f"if_else({c}, 0, 1)"
                self.stmts(s.orelse, f"({cond} & {neg})" if cond else neg)
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
                self.call(s.value, cond)
            elif isinstance(s, ast.Pass):
                continue
            else:
                self.miss(s, "statement is not an indicator rule or an order call")

    def call(self, c: ast.Call, cond: str | None) -> None:
        name = _self_call(c)
        if name in ("set_holdings", "liquidate"):
            w = 0.0 if name == "liquidate" else _num(c.args[1]) if len(c.args) > 1 else None
            if w is None:
                return self.miss(c, "set_holdings needs a literal weight")
            role = "exit_long" if w == 0 else "entry_long" if w > 0 else "entry_short"
            self.add(role, cond)
            self.hit(c, f"{role}" + (f" when {cond}" if cond else ""))
        elif name in QUIET:
            return
        else:
            self.miss(c, f"{name or 'call'} is not mapped (Studio rules trade through set_holdings and liquidate)")

    def run(self) -> None:
        for fn in (n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)):
            for a in ast.walk(fn):
                if isinstance(a, ast.Assign) and len(a.targets) == 1 and isinstance(a.targets[0], ast.Attribute) and isinstance(a.targets[0].value, ast.Name) and a.targets[0].value.id == "self":
                    name = _self_call(a.value)
                    if name and name in INDICATORS:
                        try:
                            self.ind[a.targets[0].attr] = self.indicator(a.value, name)
                            self.hit(a, f"{a.targets[0].attr} = {self.ind[a.targets[0].attr]}")
                        except Unmapped as e:
                            self.miss(a, str(e))
                    elif name and name.startswith(("macd", "bb", "atr", "adx", "stoch", "cci")):
                        self.miss(a, f"indicator {name} has no Studio operator")
        for fn in (n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)):
            if fn.name.lower() in ("on_data", "ondata"):
                self.stmts(fn.body, None)
            elif fn.name.lower() == "initialize":
                for s in fn.body:
                    name = _self_call(s.value) if isinstance(s, ast.Expr) else None
                    if name in SETTINGS:
                        self.hit(s, "ignored: dates, cash and universe are Studio Backtest settings")
                    elif name and name.startswith("schedule"):
                        self.miss(s, "schedule: Studio has no calendar rule (month start, week end); the rule fires on every bar it is true")
                    elif name and name not in INDICATORS and not (isinstance(s, ast.Assign)):
                        self.miss(s, f"{name} is not mapped")
        sched = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call) and (_self_call(n) or "").startswith("schedule") and n.lineno not in {u["line"] for u in self.unmapped}]
        for n in sched:
            self.miss(n, "schedule: Studio has no calendar rule (month start, week end); the rule fires on every bar it is true")
        if not {"entry_long", "entry_short"} & self.roles.keys():
            self.unmapped.append({"line": 1, "call": "on_data", "reason": "no entry rule found (needs set_holdings with a weight inside an if on indicators)"})


def quantconnect(source: str, name: str | None = None) -> dict:
    """`{mapped, unmapped, spec}`. Raises ValueError (message with line) when the source is not Python."""
    try:
        shim = _Shim(source)
    except SyntaxError as e:
        raise ValueError(f"line {e.lineno}: {e.msg}") from e
    shim.run()
    roles = {k: " | ".join(v) if len(v) > 1 else v[0] for k, v in shim.roles.items()}
    cls = next((n.name for n in shim.tree.body if isinstance(n, ast.ClassDef)), "QuantConnect import")
    spec = Strategy(name=name or cls, entry_long=roles.get("entry_long", ""), entry_short=roles.get("entry_short", ""), exit_long=roles.get("exit_long", ""),
                    notes="Imported from QuantConnect through the Studio shim.")
    return {"mapped": shim.mapped, "unmapped": sorted(shim.unmapped, key=lambda u: u["line"]), "spec": spec.model_dump()}


CODE = '''SIGNALS = %s

class Strategy:
    def on_bar(self, ctx):
        s = SIGNALS.get(ctx.symbol, {}).get(ctx.date)
        if s is None:
            return
        if s == 1 and ctx.position <= 0:
            ctx.buy()
        elif s == -1 and ctx.position >= 0:
            ctx.short()
        elif s == 0 and ctx.position > 0:
            ctx.sell()
        elif s == 0 and ctx.position < 0:
            ctx.cover()
'''
MAX_ROWS = 200_000


def signals(text: str, name: str = "Imported signals") -> dict:
    """Validate date,symbol,signal rows against the panel; findings come back before anything is saved. shortcut: signals are embedded in the code, upgrade to a stored table past ~200k rows."""
    found: list[dict] = []

    def add(sev: str, msg: str, row: int | None = None) -> None:
        found.append({"severity": sev, "row": row, "message": msg})

    rows = list(csv.reader(io.StringIO(text.strip())))
    head = [h.strip().lower() for h in rows[0]] if rows else []
    if head != ["date", "symbol", "signal"]:
        add("error", f"Columns must be date,symbol,signal; got {','.join(head) or 'nothing'}")
        return {"ok": False, "rows": 0, "symbols": [], "findings": found, "spec": None}
    body = rows[1:]
    if len(body) > MAX_ROWS:
        add("error", f"{len(body)} rows; the limit is {MAX_ROWS}")
        return {"ok": False, "rows": len(body), "symbols": [], "findings": found, "spec": None}
    sig: dict[str, dict[str, int]] = {}
    for i, r in enumerate(body, start=2):
        if len(r) != 3:
            add("error", f"Expected 3 columns, got {len(r)}", i)
            continue
        d, s, v = (x.strip() for x in r)
        try:
            dt.date.fromisoformat(d)
        except ValueError:
            add("error", f"Date {d!r} is not YYYY-MM-DD", i)
            continue
        if v not in ("1", "-1", "0"):
            add("error", f"Signal {v!r} must be 1, -1 or 0", i)
            continue
        if not s:
            add("error", "Symbol is empty", i)
            continue
        s = s.upper()
        if d in sig.get(s, {}):
            add("error", f"{s} has two signals on {d}", i)
            continue
        sig.setdefault(s, {})[d] = int(v)
    if not sig and not found:
        add("error", "No rows")
    if sig:
        panel = data.panel(sorted(sig))
        for s in sorted(set(sig) - set(panel.symbols)):
            add("error", f"{s} is not in the data")
        ds = {str(x.date()) for x in panel.dates}
        lo, hi = (str(panel.dates[0].date()), str(panel.dates[-1].date())) if len(panel.dates) else ("", "")
        off = sum(1 for s in sig for d in sig[s] if s in panel.symbols and d not in ds)
        if off:
            add("warning", f"{off} signals fall on days with no bars (outside {lo} to {hi} or not trading days) and will never fire")
    ok = not any(f["severity"] == "error" for f in found)
    spec = Strategy(name=name, code=CODE % json.dumps(sig, sort_keys=True, separators=(",", ":")), notes="Trades the imported signals: 1 long, -1 short, 0 flat.") if ok else None
    return {"ok": ok, "rows": len(body), "symbols": sorted(sig), "findings": found, "spec": spec.model_dump() if spec else None}
