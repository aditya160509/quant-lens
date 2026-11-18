"""Python strategies (PAGES §2 Code): static checks with line numbers, then a sandboxed child process that turns on_bar orders into signal arrays.

shortcut: subprocess + resource limits + AST allow-list, not a container; switch to the Docker sandbox once its daemon runs on the host.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine, formula, pyrunner

RUNNER = Path(__file__).with_name("pyrunner.py")
TIMEOUT_S = 120
BANNED_NAMES = {"eval", "exec", "compile", "open", "globals", "locals", "vars", "getattr", "setattr", "delattr", "input", "breakpoint", "help", "memoryview", "type"}
TEMPLATE = '''class Strategy:
    def init(self, ctx):
        self.bars_held = 0

    def on_bar(self, ctx):
        if ctx.position == 0 and ctx.rule("crosses_above(sma(close, 50), sma(close, 200))"):
            ctx.buy()
        elif ctx.position > 0:
            self.bars_held += 1
            if ctx.close[-1] < ctx.value("sma(close, 200)") or self.bars_held > 120:
                ctx.sell()

    def on_fill(self, ctx):
        self.bars_held = 0
'''


def _finding(line: int, col: int, end: int, msg: str, token: str = "", severity: str = "error") -> dict:
    return {"severity": severity, "role": "code", "line": line, "start": col, "end": end, "token": token, "message": msg}


def _formula_args(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return ()
    if node.func.attr in ("value", "rule"):
        return (node.args[0] if node.args else None,)
    if isinstance(node.func.value, ast.Name) and node.func.value.id == "ctx" and node.func.attr in ("rank", "zscore"):
        first = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "expr"), None)
        return (first, *(kw.value for kw in node.keywords if kw.arg == "where"))
    return ()


def _literal_formula(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def exprs(code: str) -> list[str]:
    """Literal strategy formulas evaluated once before the event loop."""
    return list(dict.fromkeys(
        arg.value for node in ast.walk(ast.parse(code)) for arg in _formula_args(node) if _literal_formula(arg)
    ))


def check(code: str, params: dict[str, float]) -> list[dict]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [_finding(e.lineno or 1, (e.offset or 1) - 1, (e.end_offset or e.offset or 1) - 1, f"Syntax: {e.msg}")]
    found = []
    for n in ast.walk(tree):
        at = (getattr(n, "lineno", 1), getattr(n, "col_offset", 0), getattr(n, "end_col_offset", 0))
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            found.append(_finding(*at, "Imports are not allowed: math is already there, formulas come from ctx.value()", "import"))
        elif isinstance(n, ast.Name) and (n.id in BANNED_NAMES or n.id.startswith("__")):
            found.append(_finding(*at, f"'{n.id}' is not allowed in a strategy", n.id))
        elif isinstance(n, ast.Attribute) and (n.attr.startswith("_") or n.attr in ("format", "format_map")):
            found.append(_finding(*at, f"'.{n.attr}' is not allowed in a strategy (use f-strings)", n.attr))
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            found.append(_finding(*at, "global and nonlocal are not allowed", "global"))
        elif any(not _literal_formula(arg) for arg in _formula_args(n)):
            found.append(_finding(*at, f"ctx.{n.func.attr}() needs a literal formula string", n.func.attr))
    if not any(isinstance(n, ast.ClassDef) and n.name == "Strategy" for n in tree.body):
        found.append(_finding(1, 0, 0, "Define class Strategy with on_bar(self, ctx)"))
    for e in exprs(code):
        try:
            formula.parse(e, params)
        except Exception as x:  # noqa: BLE001 SignalError and parser errors both read as text
            line = next((i + 1 for i, s in enumerate(code.splitlines()) if e in s), 1)
            col = code.splitlines()[line - 1].find(e)
            found.append(_finding(line, col, col + len(e), f"Formula: {getattr(x, 'message', x)}", e))
    return found


@lru_cache(maxsize=16)
def _api_members(scope: str):
    classes = {
        "ctx": pyrunner.Ctx, "portfolio_ctx": pyrunner.PortfolioContext,
        "portfolio": pyrunner.Portfolio, "position": pyrunner.Holding,
        "bar": pyrunner.Bar, "fill": pyrunner.Execution, "market": pyrunner.MarketBar,
        "history": pyrunner.HistoryWindow,
    }
    cls = classes.get(scope)
    if cls is None:
        return {}
    members = {}
    for name, member in inspect.getmembers_static(cls):
        if name.startswith("_"):
            continue
        sig = None
        if inspect.isfunction(member):
            call = inspect.signature(member)
            sig = f"{name}{call.replace(parameters=list(call.parameters.values())[1:])}"
        docs = inspect.getdoc(member) if inspect.isfunction(member) or isinstance(member, property) else None
        members[name] = {"name": name, "kind": "method" if sig else "field", "signature": sig, "documentation": docs}
    if scope in {"ctx", "portfolio_ctx"}:
        for name in ("open", "high", "low", "close", "volume", "symbol", "position", "params"):
            members.setdefault(name, {"name": name, "kind": "field", "signature": None, "documentation": None})
    return members


def editor_members(scope: str, code: str, prefix: str = "") -> list[dict]:
    if scope == "self":
        members = {}
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        strategy = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Strategy"), None)
        if strategy is None:
            return []
        for method in strategy.body:
            if isinstance(method, ast.FunctionDef) and not method.name.startswith("_"):
                args = ast.unparse(method.args)
                args = args.removeprefix("self, ") if args != "self" else ""
                members[method.name] = {"name": method.name, "kind": "method", "signature": f"{method.name}({args})",
                                        "documentation": ast.get_docstring(method)}
        for node in ast.walk(strategy):
            if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name) and node.value.id == "self" and not node.attr.startswith("_")):
                members.setdefault(node.attr, {"name": node.attr, "kind": "field", "signature": None, "documentation": None})
    else:
        if scope == "ctx" and "def on_data(" in code:
            scope = "portfolio_ctx"
        members = _api_members(scope)
    return [member for name, member in sorted(members.items()) if name.startswith(prefix)]


def lint(code: str, params: dict[str, float]) -> list[dict]:
    problems = [
        {"severity": f["severity"], "line": f["line"], "column": f["start"] + 1, "end_column": f["end"] + 1,
         "code": "studio-check", "message": f["message"]}
        for f in check(code, params)
    ]
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return problems
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr in {"open", "high", "low", "close", "volume"}:
            index = node.slice
            if isinstance(index, ast.UnaryOp) and isinstance(index.op, ast.UAdd):
                index = index.operand
            if isinstance(index, ast.Constant) and type(index.value) is int and index.value >= 0:
                problems.append({"severity": "error", "line": node.lineno, "column": node.col_offset + 1,
                                 "end_column": node.end_col_offset + 1, "code": "look-ahead",
                                 "message": "Use a negative offset for OHLCV series, with -1 for the current bar."})
    try:
        result = subprocess.run(
            [str(Path(sys.executable).with_name("ruff")), "check", "--isolated", "--ignore-noqa",
             "--config", 'builtins = ["math"]', "--select", "F821,F841", "--output-format", "json",
             "--stdin-filename", "main.py", "-"], input=code, capture_output=True, text=True, check=False, timeout=0.1,
        )
        rows = json.loads(result.stdout) if result.returncode in (0, 1) else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        rows = []
    for row in rows:
        location, end = row["location"], row["end_location"]
        problems.append({"severity": "warning" if row["code"] == "F841" else "error", "line": location["row"],
                         "column": location["column"], "end_column": end["column"],
                         "code": row["code"], "message": row["message"]})
    return sorted(problems, key=lambda problem: (problem["line"], problem["column"], problem["code"]))


class CodeError(Exception):
    def __init__(self, message: str, problem: dict | None = None):
        super().__init__(message)
        self.message, self.problem = message, problem or {}
        self.line = self.problem.get("line")


def run(code: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float], symbols: list[str] | None = None, cache: dict | None = None, *, output: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    arrays = _execute(code, bars, dates, params, symbols, cache, output)
    return arrays["entries"], arrays["exits"]


def run_event(code: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float],
              symbols: list[str], settings: engine.Params, *, output: dict | None = None,
              signal_bars: dict[str, np.ndarray] | None = None, stop_dist: np.ndarray | None = None,
              size_vol: np.ndarray | None = None, market_filter: np.ndarray | None = None, repaint_bars: list[int] | None = None,
              benchmark: np.ndarray | None = None) -> engine.Result:
    extras = {}
    for name, array in (("stop_dist", stop_dist), ("size_vol", size_vol), ("market_filter", market_filter)):
        if array is not None:
            extras[name] = array
    if benchmark is None and signal_bars is not None and "market" in signal_bars:
        benchmark = signal_bars["market"][:, 0]
    if benchmark is not None:
        extras["benchmark"] = benchmark
    arrays = _execute(code, signal_bars if signal_bars is not None else bars, dates, params, symbols, None, output,
                      event_settings=asdict(settings), repaint_bars=repaint_bars, extras={**extras, **{f"raw_{k}": v for k, v in bars.items()}})
    return engine.Result(*(arrays[name] for name in (
        "trades", "equity", "gross_equity", "gross_exposure", "net_exposure", "positions", "traded",
    )), unfilled=int(arrays["unfilled"].item()))


def _execute(code, bars, dates, params, symbols, cache, output, *, event_settings=None, repaint_bars=None, extras=None):
    findings = check(code, params)
    if findings:
        first = findings[0]
        raise CodeError(first["message"], {"file": "main.py", "line": first["line"], "column": first["start"] + 1})
    ex = exprs(code)
    vals = {f"v{i}": np.asarray(formula.evaluate(e, bars, dates, params, cache), dtype=float) for i, e in enumerate(ex)}
    n = bars["close"].shape[1]
    meta = {"exprs": ex, "params": params, "symbols": symbols or [str(i) for i in range(n)], "dates": [str(d.date()) for d in dates],
            "event_settings": event_settings, "repaint_bars": repaint_bars or []}
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.npz", Path(d) / "out.npz"
        np.savez(src, meta=np.array(json.dumps(meta)), **{f: np.asarray(bars[f], dtype=float) for f in ("open", "high", "low", "close", "volume")}, **vals, **(extras or {}))
        try:
            p = subprocess.run([sys.executable, "-I", str(RUNNER), str(src), str(dst)], check=False, input=code, capture_output=True, text=True, timeout=TIMEOUT_S,
                               preexec_fn=_limits, cwd=d, env={"PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired as e:
            raise CodeError(f"Stopped after {TIMEOUT_S} s", None) from e
        try:
            res = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
        except json.JSONDecodeError:
            res = {}
        if not res.get("ok"):
            raise CodeError(res.get("error") or (p.stderr.strip().splitlines() or ["the strategy process died"])[-1], res.get("problem"))
        if output is not None:
            output.update(logs=res["logs"], plots=res["plots"])
            if res.get("entry_signals") is not None:
                output["entry_signals"] = res["entry_signals"]
            if res.get("warmup") is not None:
                output["warmup"] = res["warmup"]
            if res.get("repaint") is not None:
                output["repaint"] = res["repaint"]
        with np.load(dst) as z:
            return dict(z)


def _limits() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_S, TIMEOUT_S))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
    except (ValueError, OSError):  # macOS ignores address-space limits
        pass
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def from_formulas(spec) -> str:
    """Formula -> Python, one way; the formulas stay on the spec untouched."""
    lines = ["class Strategy:", "    def on_bar(self, ctx):"]
    body = []
    for role, act, cond in (("entry_long", "buy", "ctx.position <= 0"), ("entry_short", "short", "ctx.position >= 0"), ("exit_long", "sell", "ctx.position > 0"), ("exit_short", "cover", "ctx.position < 0")):
        t = getattr(spec, role).strip()
        if t:
            body.append(f"        {'if' if not body else 'elif'} {cond} and ctx.rule({json.dumps(t)}):\n            ctx.{act}()")
    return "\n".join(lines + (body or ["        pass"])) + "\n"
