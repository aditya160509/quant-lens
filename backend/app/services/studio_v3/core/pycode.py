"""Python strategies (PAGES §2 Code): static checks with line numbers, then a sandboxed child process that turns on_bar orders into signal arrays.

shortcut: subprocess + resource limits + AST allow-list, not a container; switch to the Docker sandbox once its daemon runs on the host.
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import io
import json
import keyword
import math
import re
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine, formula, pyrunner

RUNNER = Path(__file__).with_name("pyrunner.py")
TIMEOUT_S = 120
BANNED_NAMES = {"eval", "exec", "compile", "open", "globals", "locals", "vars", "getattr", "setattr", "delattr", "input", "breakpoint", "help", "memoryview", "type"}
# A7: the numerical libraries a strategy may import. Everything else is refused, and the runner repeats the list.
ALLOWED_IMPORTS = {
    "math", "statistics", "numpy", "pandas", "scipy.stats", "scipy.optimize",
    # B-56: models that fit on past bars. No datasets, model_selection or utils (joblib, downloads); `n_jobs` is refused in check().
    "sklearn.linear_model", "sklearn.ensemble", "sklearn.preprocessing", "sklearn.pipeline", "sklearn.metrics",
    "sklearn.tree", "sklearn.neighbors", "sklearn.cluster", "sklearn.decomposition",
}
# Defence in depth: library calls that reach the filesystem or spawn work, banned by name.
BANNED_ATTRS = {
    "read_csv", "read_table", "read_parquet", "read_json", "read_html", "read_excel", "read_sql", "read_sql_query",
    "read_sql_table", "read_clipboard", "read_fwf", "read_orc", "read_feather", "read_hdf", "read_stata", "read_sas",
    "read_spss", "read_xml", "read_gbq", "read_pickle", "to_pickle", "to_csv", "to_parquet", "to_json", "to_excel",
    "to_sql", "to_hdf", "to_feather", "to_stata", "load", "loads", "fromfile", "memmap", "ctypeslib", "savetxt",
    "save", "system", "popen", "spawn", "urlopen", "urlretrieve", "socket", "subprocess", "format", "format_map",
    # file IO and eval reached through numpy and pandas objects
    "loadtxt", "genfromtxt", "fromregex", "savez", "savez_compressed", "tofile", "dump", "dumps", "DataSource",
    "to_clipboard", "to_latex", "to_markdown", "to_xml", "to_html", "to_string", "to_orc", "ExcelWriter", "ExcelFile",
    "HDFStore", "eval", "query", "show_config", "source", "lookfor",
    # submodules that expose os, sys or file readers
    "lib", "io", "testing", "f2py", "distutils", "sys", "os", "compat", "util", "core",
    # reached through sklearn modules
    "joblib", "externals", "utils", "datasets", "fetch_openml", "fetch_20newsgroups", "get_data_home",
}
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
    if isinstance(node.func.value, ast.Name) and node.func.value.id == "self" and node.func.attr in pyrunner.INDICATOR_NAMES:
        period = node.args[-1] if node.args else None
        if isinstance(period, ast.Constant) and type(period.value) is int:
            return (ast.Constant(pyrunner.indicator_formula(node.func.attr, period.value)),)
        return (None,)
    if isinstance(node.func.value, ast.Name) and node.func.value.id == "ctx" and node.func.attr == "indicator":
        expr = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "expr"), None)
        period = node.args[2] if len(node.args) > 2 else next((kw.value for kw in node.keywords if kw.arg == "period"), None)
        if period is None or (isinstance(period, ast.Constant) and period.value is None):
            return (expr,)
        if _literal_formula(expr) and isinstance(period, ast.Constant):
            try:
                return (ast.Constant(pyrunner.indicator_formula(expr.value, period.value)),)
            except ValueError:
                pass
        return (None,)
    if node.func.attr in ("value", "rule"):
        return (node.args[0] if node.args else None,)
    if isinstance(node.func.value, ast.Name) and node.func.value.id == "ctx" and node.func.attr == "feature_matrix":
        first = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "exprs"), None)
        return tuple(first.elts) if isinstance(first, (ast.List, ast.Tuple)) and first.elts else (None,)
    if isinstance(node.func.value, ast.Name) and node.func.value.id == "ctx" and node.func.attr in ("rank", "zscore"):
        first = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "expr"), None)
        return (*([first] if isinstance(first, ast.Constant) else []),
                *(kw.value for kw in node.keywords if kw.arg == "where" and not (isinstance(kw.value, ast.Constant) and kw.value.value is None)))
    return ()


def _literal_formula(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


ENGINE_SETTINGS = {"fill", "commission_bps", "commission_share", "commission_min", "slippage_bps", "slippage_range",
                   "borrow_bps", "max_positions", "leverage"}


def engine_overrides(code: str) -> dict[str, float | str]:
    """Engine settings written as Strategy class attributes (B-63). Literals only, range-checked; the code wins over the card."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return {}
    out: dict[str, float | str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Strategy":
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign) or len(item.targets) != 1 or not isinstance(item.targets[0], ast.Name):
                continue
            name = item.targets[0].id
            if name not in ENGINE_SETTINGS:
                continue
            try:
                value = ast.literal_eval(item.value)
            except (ValueError, SyntaxError, TypeError):
                continue
            if name == "fill":
                if value in ("next_open", "same_close"):
                    out[name] = value
            elif type(value) in (int, float) and math.isfinite(value) and 0 <= value <= (1000 if name == "max_positions" else 10 if name == "leverage" else 1000):
                out[name] = value
    return out


def universe_attribute(code: str) -> list[str] | str | None:
    """`universe = [...]` or `universe = "master"` on class Strategy (B-43): a symbol list, or an index name or library id."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Strategy":
            for item in node.body:
                if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "universe" for t in item.targets):
                    try:
                        value = ast.literal_eval(item.value)
                    except (ValueError, SyntaxError):
                        return None
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    if isinstance(value, (list, tuple)) and value and all(isinstance(x, str) for x in value):
                        return [x.strip().upper() for x in value if x.strip()]
    return None


def exprs(code: str) -> list[str]:
    """Literal strategy formulas evaluated once before the event loop."""
    return list(dict.fromkeys(
        arg.value for node in ast.walk(ast.parse(code)) for arg in _formula_args(node) if _literal_formula(arg)
    ))


def _refused_imports(node: ast.Import | ast.ImportFrom, modules: set[str]) -> list[str]:
    """Imports outside A7's allow-list and the saved project modules."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if alias.name not in ALLOWED_IMPORTS and alias.name not in modules]
    if node.level:
        return [node.module or "."]
    module = node.module or ""
    names = [alias.name for alias in node.names]
    if module in ALLOWED_IMPORTS or module in modules:
        return [name for name in names if name == "*" or name.startswith("_")]
    if names and all(f"{module}.{name}" in ALLOWED_IMPORTS for name in names):
        return []
    return [module or "."]


def _import_message(name: str) -> str:
    allowed = ", ".join(sorted(ALLOWED_IMPORTS))
    return f"Import '{name}' is not allowed. Allowed: {allowed}, and saved project modules"


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
            refused = _refused_imports(n, modules)
            hidden = any(alias.asname and alias.asname.startswith("_") for alias in n.names)
            if refused or hidden:
                name = refused[0] if refused else "import"
                found.append(_finding(*at, f"{_import_message(name)}", name))
        elif isinstance(n, ast.Name) and (n.id in BANNED_NAMES or n.id.startswith("__")):
            found.append(_finding(*at, f"'{n.id}' is not allowed in a strategy", n.id))
        elif isinstance(n, ast.Attribute) and (n.attr.startswith("_") or n.attr in BANNED_ATTRS or "pickle" in n.attr):
            found.append(_finding(*at, f"'.{n.attr}' is not allowed in a strategy", n.attr))
        elif isinstance(n, ast.keyword) and n.arg in {"n_jobs", "backend", "verbose_file"}:
            found.append(_finding(getattr(n.value, "lineno", 1), getattr(n.value, "col_offset", 0), getattr(n.value, "end_col_offset", 0),
                                  f"'{n.arg}' would start other processes; fits run in this one process", n.arg))
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


def _is_cells(source: str) -> bool:
    """A research file split into `# %%` cells; it runs through POST /build/cells, not as part of the strategy."""
    return any(line.lstrip().startswith("# %%") for line in source.splitlines())


def check_project(code: str, params: dict[str, float], files: dict[str, str]) -> list[dict]:
    modules = {name[:-3] for name in files if name.endswith(".py")}
    # test_*.py files are not part of the strategy; POST /build/test checks and runs them
    sources = {"main.py": code, **{name: source for name, source in files.items() if name.endswith(".py") and name != "main.py" and not name.startswith("test_") and not _is_cells(source)}}
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
        "history": pyrunner.HistoryWindow, "indicator": pyrunner.Indicator,
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


# The numerical names an editor offers after `np.` or `pd.`. Curated: the full namespace is thousands of entries.
_LIBRARY_MEMBERS = {
    "numpy": {
        "array": ("array(object, dtype=None)", "Create an array from a list or nested sequence"),
        "arange": ("arange(start, stop=None, step=1)", "Evenly spaced values in a half-open interval"),
        "linspace": ("linspace(start, stop, num=50)", "num evenly spaced values including both ends"),
        "zeros": ("zeros(shape)", "A new array filled with zeros"),
        "ones": ("ones(shape)", "A new array filled with ones"),
        "full": ("full(shape, fill_value)", "A new array filled with one value"),
        "mean": ("mean(a)", "Arithmetic mean"),
        "median": ("median(a)", "Median"),
        "std": ("std(a)", "Standard deviation"),
        "var": ("var(a)", "Variance"),
        "cov": ("cov(m)", "Covariance matrix"),
        "corrcoef": ("corrcoef(x, y=None)", "Pearson correlation coefficients"),
        "sqrt": ("sqrt(x)", "Square root"),
        "log": ("log(x)", "Natural logarithm"),
        "exp": ("exp(x)", "Exponential"),
        "abs": ("abs(x)", "Absolute value"),
        "sign": ("sign(x)", "-1, 0 or 1 by sign"),
        "where": ("where(cond, x, y)", "x where cond holds, else y"),
        "maximum": ("maximum(x1, x2)", "Elementwise maximum that ignores NaN"),
        "minimum": ("minimum(x1, x2)", "Elementwise minimum that ignores NaN"),
        "clip": ("clip(a, a_min, a_max)", "Limit values to an interval"),
        "percentile": ("percentile(a, q)", "q-th percentile"),
        "nanmean": ("nanmean(a)", "Mean ignoring NaN"),
        "isnan": ("isnan(x)", "True where the value is NaN"),
        "isfinite": ("isfinite(x)", "True where the value is finite"),
        "concatenate": ("concatenate(arrays)", "Join arrays along an existing axis"),
        "stack": ("stack(arrays)", "Join arrays along a new axis"),
        "diff": ("diff(a)", "Difference between neighbouring values"),
        "cumsum": ("cumsum(a)", "Cumulative sum"),
        "cumprod": ("cumprod(a)", "Cumulative product"),
        "prod": ("prod(a)", "Product of values"),
        "sum": ("sum(a)", "Sum of values"),
        "argmax": ("argmax(a)", "Index of the largest value"),
        "argmin": ("argmin(a)", "Index of the smallest value"),
        "sort": ("sort(a)", "Sorted copy"),
        "argsort": ("argsort(a)", "Indices that would sort the array"),
        "dot": ("dot(a, b)", "Dot product"),
        "polyfit": ("polyfit(x, y, deg)", "Least-squares polynomial fit"),
        "polyval": ("polyval(p, x)", "Evaluate a polynomial"),
    },
    "pandas": {
        "DataFrame": ("DataFrame(data=None, index=None, columns=None)", "Two-dimensional labelled table"),
        "Series": ("Series(data=None, index=None, name=None)", "One-dimensional labelled array"),
        "concat": ("concat(objs, axis=0)", "Concatenate tables along an axis"),
        "merge": ("merge(left, right, how='inner', on=None)", "Join two tables on keys"),
        "to_numeric": ("to_numeric(arg, errors='raise')", "Coerce values to numbers"),
        "to_datetime": ("to_datetime(arg)", "Coerce values to timestamps"),
        "date_range": ("date_range(start=None, end=None, periods=None, freq=None)", "A fixed-frequency date index"),
        "isna": ("isna(obj)", "True where a value is missing"),
        "notna": ("notna(obj)", "True where a value is present"),
        "cut": ("cut(x, bins)", "Bin values into discrete intervals"),
        "qcut": ("qcut(x, q)", "Bin values into equal-frequency buckets"),
        "get_dummies": ("get_dummies(data)", "One-hot encode categorical columns"),
        "rolling": ("Series.rolling(window)", "Rolling window; then .mean(), .std(), .max()"),
        "ewm": ("Series.ewm(span)", "Exponentially weighted window; then .mean()"),
        "pct_change": ("Series.pct_change()", "Fractional change from the previous value"),
        "rank": ("Series.rank(pct=True)", "Percentile rank"),
    },
}


def _library_members(scope: str) -> dict[str, dict]:
    return {name: {"name": name, "kind": "function" if signature else "field", "signature": signature,
                   "documentation": description}
            for name, (signature, description) in _LIBRARY_MEMBERS[scope].items()}


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
    elif scope in _LIBRARY_MEMBERS:
        members = _library_members(scope)
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
        for name in pyrunner.INDICATOR_NAMES:
            members.setdefault(name, {"name": name, "kind": "method",
                                       "signature": f"{name}(symbol_or_period, period=None)",
                                       "documentation": f"A {name.upper()} handle with .value, .ready, .window and .history(n)"})
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
_SYMBOL_CALLS = _ORDER_CALLS | {"bar", "pos", "quote"}

def _np_random(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) and node.value.attr == "random"
            and isinstance(node.value.value, ast.Name) and node.value.value.id == "np")


def _domain_problems(tree: ast.AST) -> list[dict]:
    """Domain findings in lint (B-38, B-40): hard-coded symbols, print in the bar loop, mutable defaults,
    wall-clock reads, network URLs and unseeded randomness."""
    problems: list[dict] = []

    def add(node: ast.AST, code: str, message: str) -> None:
        problems.append({"severity": "warning", "line": getattr(node, "lineno", 1),
                         "column": getattr(node, "col_offset", 0) + 1, "end_column": getattr(node, "end_col_offset", 0) + 1,
                         "code": code, "message": message})

    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    hot = {id(n) for f in functions if f.name in {"on_bar", "on_data"} for n in ast.walk(f)}
    portfolio = any(f.name == "on_data" for f in functions)
    universe = any(isinstance(n, ast.Attribute) and n.attr == "symbols" for n in ast.walk(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if id(node) in hot and isinstance(node.func, ast.Name) and node.func.id == "print":
                add(node, "print-in-loop", "print runs on every bar; use ctx.log while debugging.")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"now", "today", "utcnow"}:
                add(node, "wall-clock", "Wall-clock time makes a run differ from the next; use ctx.date.")
            if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "ctx"
                    and node.func.attr in _SYMBOL_CALLS and node.args and portfolio and universe
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and node.args[0].value.isupper()):
                add(node, "hard-coded-symbol", f"'{node.args[0].value}' is fixed while the universe is a parameter; use ctx.symbol or ctx.symbols.")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lower().startswith(("http://", "https://")):
            add(node, "network", "Network addresses cannot be read in a backtest; data comes from the saved parquets.")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    add(default, "mutable-default", "A mutable default is shared between calls; build it inside the function.")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _np_random(n.func) and n.func.attr != "seed"]
    seeded = any(isinstance(n, ast.Call) and _np_random(n.func) and n.func.attr in {"seed", "default_rng", "RandomState"} and n.args
                 for n in ast.walk(tree))
    if calls and not seeded:
        add(calls[0], "unseeded-random", "Unseeded randomness makes runs differ; call np.random.seed(7) or np.random.default_rng(7).")
    return problems


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


STUDIO_API = 1  # B-41: the Python API version a strategy is written against, as `# studio-api: 1` in its first lines
_SERIES = {"open", "high", "low", "close", "volume"}


def api_version(code: str) -> int | None:
    for line in code.splitlines()[:5]:
        match = re.fullmatch(r"#\s*studio-api:\s*(\d+)\s*", line)
        if match:
            return int(match.group(1))
    return None


def _positive(node: ast.AST | None, strict: bool) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        node = node.operand
    return isinstance(node, ast.Constant) and type(node.value) is int and (node.value > 0 if strict else node.value >= 0)


def _lookahead_patterns(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """B-35 beyond positive OHLCV indexes: slices that start now or later, history windows read forward, future date literals, negative shifts, next_* reads."""
    found: list[tuple[ast.AST, str]] = []
    windows = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
               and n.value.func.attr == "history" for t in n.targets if isinstance(t, ast.Name)}
    today = dt.date.today().isoformat()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice) and isinstance(node.value, ast.Attribute) and node.value.attr in _SERIES:
            if _positive(node.slice.lower, False) or _positive(node.slice.upper, True):
                found.append((node, "This slice reads the current or a later bar; use negative bounds like close[-20:]."))
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in windows and _positive(node.slice, True):
            found.append((node, "A history window is indexed 0 for now and negative for the past; a positive index reads a future bar."))
        elif isinstance(node, ast.Compare) and any(isinstance(x, ast.Attribute) and x.attr == "date" and isinstance(x.value, ast.Name) and x.value.id == "ctx"
                                                    for x in (node.left, *node.comparators)):
            for x in (node.left, *node.comparators):
                if isinstance(x, ast.Constant) and isinstance(x.value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x.value) and x.value > today:
                    found.append((x, f"{x.value} is in the future; a rule keyed to a later date uses information from after the run."))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "shift" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub) and isinstance(arg.operand, ast.Constant):
                found.append((node, "shift with a negative lag moves later bars onto this one."))
        elif isinstance(node, ast.Attribute) and node.attr.startswith("next_") and isinstance(node.value, ast.Name) and node.value.id == "ctx":
            found.append((node, f"ctx.{node.attr} reads a later bar; strategies see the current bar and the past only."))
    return found


_LEVELS = {"error", "warning", "info", "off"}


def lint(code: str, params: dict[str, float], *, file: str = "main.py", modules: set[str] | None = None,
         strictness: str = "basic", severity: dict[str, str] | None = None) -> list[dict]:
    """strictness "strict" adds unused imports and the API header; `severity` maps a problem code to error, warning, info or off (B-37)."""
    if file.rsplit("/", 1)[-1].startswith("test_") or _is_cells(code):
        modules = (modules or set()) | {"studio.testing", "studio.research"}  # the test fixture and the research-cell data loader
    problems = _lint(code, params, file=file, modules=modules, strict=strictness == "strict")
    for code_name, level in (severity or {}).items():
        if level not in _LEVELS:
            raise ValueError(f"Severity for {code_name} must be one of {', '.join(sorted(_LEVELS))}")
    levels = severity or {}
    ignored = _ignored(code)
    problems = [p for p in problems if not (p["line"] in ignored and (ignored[p["line"]] is None or p["code"] in ignored[p["line"]]))]
    return [{**p, "severity": levels.get(p["code"], p["severity"])} for p in problems if levels.get(p["code"]) != "off"]


def _ignored(code: str) -> dict[int, set[str] | None]:
    """Lines carrying `# studio: ignore` (None = every code) or `# studio: ignore[a,b]`."""
    found: dict[int, set[str] | None] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            m = tok.type == tokenize.COMMENT and re.search(r"#\s*studio:\s*ignore(?:\[([^\]]*)\])?", tok.string)
            if m:
                found[tok.start[0]] = {c.strip() for c in m.group(1).split(",")} if m.group(1) else None
    except (tokenize.TokenError, IndentationError):
        pass
    return found


_ENTRY_CALLS = {"market_order", "limit_order", "buy", "order_value", "bracket"}
_EXIT_CALLS = {"stop_order", "stop_limit_order", "sell", "exit"}


def _strategy_problems(tree: ast.AST, params: dict[str, float], skip: set[int]) -> list[dict]:
    """Unused params, entries without any stop or exit, hard-coded dates (future ones are look-ahead's)."""
    out: list[dict] = []
    nodes = list(ast.walk(tree))
    strings = " ".join(n.value for n in nodes if isinstance(n, ast.Constant) and isinstance(n.value, str))
    if not any(isinstance(n, ast.Attribute) and n.attr == "params" for n in nodes):
        for name in params:
            if not re.search(rf"\b{re.escape(name)}\b", strings):
                out.append({"severity": "warning", "line": 1, "column": 1, "end_column": 1, "code": "studio-unused-param",
                            "message": f"Param {name} is never read."})
    calls = [n for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    entry = next((c for c in calls if c.func.attr in _ENTRY_CALLS), None)
    if entry and not any(c.func.attr in _EXIT_CALLS or any(k.arg in {"stop", "trail"} and not (isinstance(k.value, ast.Constant) and k.value.value is None) for k in c.keywords) for c in calls):
        out.append({"severity": "info", "line": entry.lineno, "column": entry.col_offset + 1, "end_column": (entry.end_col_offset or entry.col_offset) + 1,
                    "code": "studio-no-stop", "message": "Orders are placed but no stop or exit is used."})
    for n in nodes:
        if isinstance(n, ast.Compare):
            for x in (n.left, *n.comparators):
                if isinstance(x, ast.Constant) and isinstance(x.value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x.value) and id(x) not in skip:
                    out.append({"severity": "warning", "line": x.lineno, "column": x.col_offset + 1, "end_column": (x.end_col_offset or x.col_offset) + 1,
                                "code": "studio-hardcoded-date", "message": f"Date {x.value} is hard-coded; make it a param."})
    return out


def _lint(code: str, params: dict[str, float], *, file: str = "main.py", modules: set[str] | None = None, strict: bool = False) -> list[dict]:
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
    problems.extend(_domain_problems(tree))
    ahead = _lookahead_patterns(tree)
    if file == "main.py":
        problems.extend(_strategy_problems(tree, params, {id(n) for n, _ in ahead}))
    for node, message in ahead:
        problems.append({"severity": "error", "line": node.lineno, "column": node.col_offset + 1, "end_column": (node.end_col_offset or node.col_offset) + 1,
                         "code": "look-ahead", "message": message})
    version = api_version(code)
    if version is not None and version > STUDIO_API:
        problems.append({"severity": "error", "line": 1, "column": 1, "end_column": 1, "code": "studio-api",
                         "message": f"This code targets studio-api {version}; this server speaks {STUDIO_API}."})
    elif version is None and strict and file == "main.py":
        problems.append({"severity": "info", "line": 1, "column": 1, "end_column": 1, "code": "studio-api",
                         "message": f"Add # studio-api: {STUDIO_API} so a future API change can migrate this file.",
                         "fix": {"title": f"Add # studio-api: {STUDIO_API}", "edits": [{"line": 1, "column": 1, "end_line": 1, "end_column": 1, "text": f"# studio-api: {STUDIO_API}\n"}]}})
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
             "--config", 'builtins = ["math"]', "--select", "F821,F841,F401" if strict else "F821,F841", "--output-format", "json",
             "--stdin-filename", "main.py", "-"], input=code, capture_output=True, text=True, check=False, timeout=0.1,
        )
        rows = json.loads(result.stdout) if result.returncode in (0, 1) else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        rows = []
    for row in rows:
        location, end = row["location"], row["end_location"]
        problems.append({"severity": "warning" if row["code"] in {"F841", "F401"} else "error", "line": location["row"],
                         "column": location["column"], "end_column": end["column"],
                         "code": row["code"], "message": row["message"],
                         **_ruff_fix(row, code)})
    return [{**problem, "file": file} for problem in sorted(problems, key=lambda p: (p["line"], p["column"], p["code"]))]


def _ruff_fix(row: dict, code: str) -> dict:
    """Quick fix for an unused import (ruff's own edit) or an unused variable (prefix `_`)."""
    if row["code"] == "F841":
        return {"fix": {"title": "Prefix with _", "edits": [{"line": row["location"]["row"], "column": row["location"]["column"],
                                                            "end_line": row["location"]["row"], "end_column": row["location"]["column"], "text": "_"}]}}
    if row["code"] == "F401" and row.get("fix"):
        edits = [{"line": e["location"]["row"], "column": e["location"]["column"], "end_line": e["end_location"]["row"],
                  "end_column": e["end_location"]["column"], "text": e["content"]} for e in row["fix"]["edits"]]
        return {"fix": {"title": "Remove unused import", "edits": edits}}
    return {}


class CodeError(Exception):
    def __init__(self, message: str, problem: dict | None = None):
        super().__init__(message)
        self.message, self.problem = message, problem or {}
        self.line = self.problem.get("line")


def run(code: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float], symbols: list[str] | None = None, cache: dict | None = None, *, output: dict | None = None, files: dict[str, str] | None = None) -> tuple[np.ndarray, np.ndarray]:
    arrays = _execute(code, bars, dates, params, symbols, cache, output, files=files)
    return arrays["entries"], arrays["exits"]


def breakpoint_condition(expression: str | None) -> list[tuple[str, str, str]]:
    if not expression:
        return []
    try:
        test = ast.parse(expression, mode="eval").body
    except SyntaxError:
        raise ValueError("Use comparisons like ctx.date >= '2025-01-01'.") from None
    terms = test.values if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) else [test]
    conditions = []
    for term in terms:
        if (not isinstance(term, ast.Compare) or len(term.ops) != 1
                or not isinstance(term.left, ast.Attribute) or not isinstance(term.left.value, ast.Name)
                or term.left.value.id != "ctx" or term.left.attr not in {"date", "symbol"}
                or not isinstance(term.comparators[0], ast.Constant) or type(term.comparators[0].value) is not str
                or type(term.ops[0]).__name__ not in {"Eq", "NotEq", "Lt", "LtE", "Gt", "GtE"}):
            raise ValueError("Use comparisons of ctx.date or ctx.symbol with strings, joined with and.")
        conditions.append((term.left.attr, type(term.ops[0]).__name__, term.comparators[0].value))
    return conditions


def run_event(code: str, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float],
              symbols: list[str], settings: engine.Params, *, output: dict | None = None,
              signal_bars: dict[str, np.ndarray] | None = None, stop_dist: np.ndarray | None = None,
              size_vol: np.ndarray | None = None, market_filter: np.ndarray | None = None, repaint_bars: list[int] | None = None,
              benchmark: np.ndarray | None = None, files: dict[str, str] | None = None,
              debug_symbol: str | None = None, debug_after: int | None = None, debug_event: str | None = None, debug_breakpoint: dict | None = None,
              debug_loss: float | None = None) -> engine.Result:
    extras = {}
    for name, array in (("stop_dist", stop_dist), ("size_vol", size_vol), ("market_filter", market_filter)):
        if array is not None:
            extras[name] = array
    if benchmark is None and signal_bars is not None and "market" in signal_bars:
        benchmark = signal_bars["market"][:, 0]
    if benchmark is not None:
        extras["benchmark"] = benchmark
    info = {} if output is None else output
    arrays = _execute(code, signal_bars if signal_bars is not None else bars, dates, params, symbols, None, info,
                      event_settings=asdict(settings), files=files, debug_symbol=debug_symbol, debug_after=debug_after, debug_event=debug_event, debug_breakpoint=debug_breakpoint, debug_loss=debug_loss, repaint_bars=repaint_bars, extras={**extras, **{f"raw_{k}": v for k, v in bars.items()}})
    return engine.Result(*(arrays[name] for name in (
        "trades", "equity", "gross_equity", "gross_exposure", "net_exposure", "positions", "traded",
    )), unfilled=int(arrays["unfilled"].item()), risk_events=info.get("risk_events") or [])


def _execute(code, bars, dates, params, symbols, cache, output, *, event_settings=None, repaint_bars=None, extras=None, files=None, debug_symbol=None, debug_after=None, debug_event=None, debug_breakpoint=None, debug_loss=None):
    modules = {name: source for name, source in (files or {}).items() if name.endswith(".py") and name != "main.py"}
    findings = check_project(code, params, modules)
    if findings:
        first = findings[0]
        raise CodeError(first["message"], {"file": first["file"], "line": first["line"], "column": first["start"] + 1})
    ex = list(dict.fromkeys(expression for source in (code, *modules.values()) for expression in exprs(source)))
    vals = {f"v{i}": np.asarray(formula.evaluate(e, bars, dates, params, cache), dtype=float) for i, e in enumerate(ex)}
    n = bars["close"].shape[1]
    meta = {"exprs": ex, "params": params, "symbols": symbols or [str(i) for i in range(n)], "dates": [str(d.date()) for d in dates],
            "event_settings": event_settings, "repaint_bars": repaint_bars or [], "modules": modules, "debug_symbol": debug_symbol, "debug_after": debug_after, "debug_event": debug_event, "debug_breakpoint": debug_breakpoint, "debug_loss": debug_loss,
            "profile": bool(output and output.get("profile") is True), "logpoints": (output or {}).pop("logpoints", None) or []}  # a caller asks for the profiler by seeding output["profile"] = True
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
            output.update({field: res[field] for field in ("logs", "plots", "plot_charts", "draw", "marks", "tables", "risk_events")})
            if res.get("entry_signals") is not None:
                output["entry_signals"] = res["entry_signals"]
            if res.get("debug") is not None:
                output["debug"] = res["debug"]
            if res.get("warmup") is not None:
                output["warmup"] = res["warmup"]
            if res.get("repaint") is not None:
                output["repaint"] = res["repaint"]
            if (res.get("invariants") or {}).get("count"):  # absent unless something broke, so clean reports keep their shape
                output["invariants"] = res["invariants"]
            for key in ("order_lines", "profile"):  # only what the caller seeded with True, so reports keep their shape
                if output.get(key) is True:
                    output[key] = res.get(key) or ([] if key == "order_lines" else None)
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


_TY_LINE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<sev>error|warning)\[(?P<code>[\w-]+)\] (?P<msg>.*)$")
_TY_SKIP = {"unresolved-reference", "unresolved-import"}  # the Studio linter owns undefined names and the import allow-list


def typecheck(files: dict[str, str], file: str = "main.py") -> list[dict]:
    """Run ty on a temp copy of the project; only `file`'s diagnostics come back. A missing or slow ty answers nothing."""
    import shutil
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    ty = shutil.which("ty", path=str(Path(sys.executable).parent)) or shutil.which("ty")
    if not ty:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in files.items():
            if name.endswith(".py") and "/" not in name and ".." not in name:
                (Path(tmp) / name).write_text(text)
        try:
            out = subprocess.run([ty, "check", "--output-format", "concise", "--color", "never", "--python", sys.prefix, tmp], capture_output=True, text=True, timeout=5, check=False).stdout
        except subprocess.TimeoutExpired:
            return []
    problems = []
    for raw in out.splitlines():
        m = _TY_LINE.match(raw)
        if not m or Path(m["file"]).name != file or m["code"] in _TY_SKIP:
            continue
        if "import" in m["code"] and "studio." in m["msg"]:  # studio.testing and studio.research are injected by the sandbox
            continue
        col = int(m["col"]) - 1
        problems.append({"severity": m["sev"], "file": file, "line": int(m["line"]), "column": col, "end_column": col + 1, "code": f"ty-{m['code']}", "message": m["msg"]})
    return problems
