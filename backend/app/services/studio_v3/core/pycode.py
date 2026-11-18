"""Python strategies (PAGES §2 Code): static checks with line numbers, then a sandboxed child process that turns on_bar orders into signal arrays.

shortcut: subprocess + resource limits + AST allow-list, not a container; switch to the Docker sandbox once its daemon runs on the host.
"""

from __future__ import annotations

import ast
import inspect
import json
import keyword
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


def check(code: str, params: dict[str, float], *, modules: set[str] | None = None, entry=True) -> list[dict]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [_finding(e.lineno or 1, (e.offset or 1) - 1, (e.end_offset or e.offset or 1) - 1, f"Syntax: {e.msg}")]
    found = []
    modules = modules or set()
    for n in ast.walk(tree):
        at = (getattr(n, "lineno", 1), getattr(n, "col_offset", 0), getattr(n, "end_col_offset", 0))
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            if isinstance(n, ast.Import):
                allowed = all(alias.name in modules for alias in n.names)
            else:
                allowed = n.level == 0 and n.module in modules and all(
                    alias.name != "*" and not alias.name.startswith("_") for alias in n.names
                )
            if not allowed or any(alias.asname and alias.asname.startswith("_") for alias in n.names):
                found.append(_finding(*at, "Only named imports from saved project modules are allowed", "import"))
        elif isinstance(n, ast.Name) and (n.id in BANNED_NAMES or n.id.startswith("__")):
            found.append(_finding(*at, f"'{n.id}' is not allowed in a strategy", n.id))
        elif isinstance(n, ast.Attribute) and (n.attr.startswith("_") or n.attr in ("format", "format_map")):
            found.append(_finding(*at, f"'.{n.attr}' is not allowed in a strategy (use f-strings)", n.attr))
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            found.append(_finding(*at, "global and nonlocal are not allowed", "global"))
        elif any(not _literal_formula(arg) for arg in _formula_args(n)):
            found.append(_finding(*at, f"ctx.{n.func.attr}() needs a literal formula string", n.func.attr))
    if entry and not any(isinstance(n, ast.ClassDef) and n.name == "Strategy" for n in tree.body):
        found.append(_finding(1, 0, 0, "Define class Strategy with on_bar(self, ctx)"))
    for e in exprs(code):
        try:
            formula.parse(e, params)
        except Exception as x:  # noqa: BLE001 SignalError and parser errors both read as text
            line = next((i + 1 for i, s in enumerate(code.splitlines()) if e in s), 1)
            col = code.splitlines()[line - 1].find(e)
            found.append(_finding(line, col, col + len(e), f"Formula: {getattr(x, 'message', x)}", e))
    return found


def check_project(code: str, params: dict[str, float], files: dict[str, str]) -> list[dict]:
    modules = {name[:-3] for name in files if name.endswith(".py")}
    sources = {"main.py": code, **{name: source for name, source in files.items() if name.endswith(".py") and name != "main.py"}}
    return [
        {**finding, "file": name}
        for name, source in sources.items()
        for finding in check(source, params, modules=modules - {"main"}, entry=name == "main.py")
    ]


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


def _literal_members(scope: str, params: list[str], symbols: list[str]):
    if scope == "formula":
        members = {
            name: {"name": name, "kind": "formula", "signature": f"{name}({', '.join(args)})",
                   "documentation": description, "insert_text": f"{name}({', '.join(f'${{{i}:{arg}}}' for i, arg in enumerate(args, 1))})"}
            for name, (_, args, description, _) in formula.OPERATORS.items()
        }
        members.update({name: {"name": name, "kind": "field", "signature": None, "documentation": description}
                        for name, description in formula.FIELDS.items()})
        return members
    if scope == "history_field":
        return {name: {"name": name, "kind": "field", "signature": None, "documentation": formula.FIELDS[name]}
                for name in ("open", "high", "low", "close", "volume")}
    names = params if scope == "param" else symbols
    return {name: {"name": name, "kind": scope, "signature": None, "documentation": None} for name in names}


def editor_members(scope: str, code: str, prefix: str = "", *, params=None, symbols=None) -> list[dict]:
    if scope in {"formula", "history_field", "param", "symbol"}:
        members = _literal_members(scope, params or [], symbols or [])
    elif scope == "self":
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


def outline(code: str) -> list[dict]:
    """Return the symbols in one document without importing it."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError):
        return []

    def walk(node, in_class=False):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "method" if in_class else "function"
            return [{
                "name": node.name, "kind": kind, "line": node.lineno, "column": node.col_offset + 1,
                "end_line": node.end_lineno, "end_column": node.end_col_offset + 1,
                "children": [item for statement in node.body for item in walk(statement, kind == "class")],
            }]
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call):
            callee = node.value.func
            if (isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name) and callee.value.id == "ctx"
                    and callee.attr in {"indicator", "value", "rule"}):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                return [{
                    "name": ast.unparse(target), "kind": "indicator", "line": node.lineno, "column": node.col_offset + 1,
                    "end_line": node.end_lineno, "end_column": node.end_col_offset + 1, "children": [],
                } for target in targets if isinstance(target, (ast.Name, ast.Attribute))]
        return [item for child in ast.iter_child_nodes(node) for item in walk(child, in_class)]

    try:
        return walk(tree)
    except RecursionError:
        return []


def navigate(code: str, line: int, column: int, *, file: str = "main.py", files: dict[str, str] | None = None,
             references: bool = False, new_name: str | None = None) -> list[dict] | dict[str, str]:
    if new_name is not None and (not new_name.isidentifier() or keyword.iskeyword(new_name)):
        raise ValueError("Use a valid Python identifier.")
    lines = code.split("\n")
    if not 1 <= line <= len(lines) or not 1 <= column <= len(lines[line - 1]) + 1:
        return {} if new_name is not None else []
    try:
        import jedi
    except ImportError:
        if new_name is not None or references:
            raise ValueError("Project references and rename require Jedi.") from None
        return [{**item, "file": file} for item in _local_definition(code, line, column)]

    with tempfile.TemporaryDirectory(prefix="studio-definition-") as directory:
        root = Path(directory).resolve()
        paths = {}
        for name, source in (files or {}).items():
            if not name.endswith(".py"):
                continue
            path = root / name
            if path.parent != root or path.name != name:
                raise ValueError("Use a flat project filename")
            path.write_text(source, encoding="utf-8")
            paths[path] = name
        active = root / file
        if active.parent != root or active.name != file or active.suffix != ".py":
            raise ValueError("Use a flat Python filename")
        paths[active] = file
        project = jedi.Project(path=root, sys_path=[str(root)], smart_sys_path=False)
        script = jedi.Script(code, path=active, project=project)
        position = {"line": line, "column": column - 1}
        if new_name is not None:
            try:
                change = script.rename(**position, new_name=new_name)
            except jedi.RefactoringError:
                raise ValueError("Select a Python symbol declared in this project.") from None
            changed = change.get_changed_files()
            if change.get_renames() or any(path not in paths for path in changed):
                raise ValueError("Only symbol edits within project files are supported.")
            return {paths[path]: item.get_new_code() for path, item in changed.items()}
        matches = script.get_references(**position, scope="project") if references else script.goto(**position, follow_imports=True)
        return [
            {"file": paths[item.module_path], "name": item.name, "line": item.line, "column": item.column + 1}
            for item in matches if item.module_path in paths and item.line is not None and item.column is not None
        ]


def _local_definition(code: str, line: int, column: int) -> list[dict]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    at = column - 1
    reference = next((node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.lineno == line
                      and node.col_offset <= at < node.end_col_offset), None)
    if reference is None:
        return []
    candidates = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == reference.id]
    if len(candidates) != 1:
        return []
    if any(
        (isinstance(node, ast.arg) and node.arg == reference.id)
        or (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == reference.id)
        for node in ast.walk(tree)
    ):
        return []
    node = candidates[0]
    return [{"file": "main.py", "name": node.name, "line": node.lineno,
             "column": node.col_offset + (7 if isinstance(node, ast.ClassDef) else 5)}]


_ORDER_CALLS = {"buy", "sell", "short", "cover", "market_order", "limit_order", "stop_order", "stop_limit_order",
                "order", "order_value", "limit", "stop", "stop_limit", "target_weights", "set_holdings", "set_weight", "liquidate"}


def _unreachable_orders(tree):
    unreachable = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Constant):
            unreachable.extend(node.orelse if bool(node.test.value) else node.body)
        for _, statements in ast.iter_fields(node):
            if isinstance(statements, list):
                for index, statement in enumerate(statements):
                    if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                        unreachable.extend(statements[index + 1:])
                        break
    return {
        node for statement in unreachable for node in ast.walk(statement)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "ctx" and node.func.attr in _ORDER_CALLS
    }


def lint(code: str, params: dict[str, float], *, file: str = "main.py", modules: set[str] | None = None) -> list[dict]:
    problems = [
        {"severity": f["severity"], "line": f["line"], "column": f["start"] + 1, "end_column": f["end"] + 1,
         "code": "studio-check", "message": f["message"]}
        for f in check(code, params, modules=modules, entry=file == "main.py")
    ]
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [{**problem, "file": file} for problem in problems]
    for node in _unreachable_orders(tree):
        problems.append({"severity": "warning", "line": node.lineno, "column": node.col_offset + 1,
                         "end_column": node.end_col_offset + 1, "code": "unreachable-order",
                         "message": "This order cannot be reached."})
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
    return [{**problem, "file": file} for problem in sorted(problems, key=lambda p: (p["line"], p["column"], p["code"]))]


class CodeError(Exception):
    def __init__(self, message: str, problem: dict | None = None):
        super().__init__(message)
        self.message, self.problem = message, problem or {}
        self.line = self.problem.get("line")


def run(code: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float], symbols: list[str] | None = None, cache: dict | None = None, *, output: dict | None = None, files: dict[str, str] | None = None) -> tuple[np.ndarray, np.ndarray]:
    arrays = _execute(code, bars, dates, params, symbols, cache, output, files=files)
    return arrays["entries"], arrays["exits"]


def run_event(code: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float],
              symbols: list[str], settings: engine.Params, *, output: dict | None = None,
              signal_bars: dict[str, np.ndarray] | None = None, stop_dist: np.ndarray | None = None,
              size_vol: np.ndarray | None = None, market_filter: np.ndarray | None = None, repaint_bars: list[int] | None = None,
              benchmark: np.ndarray | None = None, files: dict[str, str] | None = None,
              debug_symbol: str | None = None) -> engine.Result:
    extras = {}
    for name, array in (("stop_dist", stop_dist), ("size_vol", size_vol), ("market_filter", market_filter)):
        if array is not None:
            extras[name] = array
    if benchmark is None and signal_bars is not None and "market" in signal_bars:
        benchmark = signal_bars["market"][:, 0]
    if benchmark is not None:
        extras["benchmark"] = benchmark
    arrays = _execute(code, signal_bars if signal_bars is not None else bars, dates, params, symbols, None, output,
                      event_settings=asdict(settings), files=files, debug_symbol=debug_symbol, repaint_bars=repaint_bars, extras={**extras, **{f"raw_{k}": v for k, v in bars.items()}})
    return engine.Result(*(arrays[name] for name in (
        "trades", "equity", "gross_equity", "gross_exposure", "net_exposure", "positions", "traded",
    )), unfilled=int(arrays["unfilled"].item()))


def _execute(code, bars, dates, params, symbols, cache, output, *, event_settings=None, repaint_bars=None, extras=None, files=None, debug_symbol=None):
    modules = {name: source for name, source in (files or {}).items() if name.endswith(".py") and name != "main.py"}
    findings = check_project(code, params, modules)
    if findings:
        first = findings[0]
        raise CodeError(first["message"], {"file": first["file"], "line": first["line"], "column": first["start"] + 1})
    ex = list(dict.fromkeys(expression for source in (code, *modules.values()) for expression in exprs(source)))
    vals = {f"v{i}": np.asarray(formula.evaluate(e, bars, dates, params, cache), dtype=float) for i, e in enumerate(ex)}
    n = bars["close"].shape[1]
    meta = {"exprs": ex, "params": params, "symbols": symbols or [str(i) for i in range(n)], "dates": [str(d.date()) for d in dates],
            "event_settings": event_settings, "repaint_bars": repaint_bars or [], "modules": modules, "debug_symbol": debug_symbol}
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
            output.update({field: res[field] for field in ("logs", "plots", "plot_charts", "marks", "tables")})
            if res.get("entry_signals") is not None:
                output["entry_signals"] = res["entry_signals"]
            if res.get("debug") is not None:
                output["debug"] = res["debug"]
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
