"""Sandboxed project runs in a child process: strategy tests and research cells.

Tests: `run(files, file, name)` runs `def test_*()` from test_*.py files; `from studio.testing import bars` gives fake OHLCV.
Cells: `run_cells(files, file, upto, only)` runs the `# %%` cells of one file; `from studio.research import load` gives real bars.
Child: `python -I strategy_tests.py`, JSON on stdin, one JSON line per test or cell on stdout.
"""

import ast
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType

THIS = Path(__file__)
FIXTURE = "studio.testing"
RESEARCH = "studio.research"
CELL = "# %%"


def cells(source: str) -> list[dict]:
    """`# %%` splits a file into cells; text before the first marker is cell 0. Lines are 1-based and inclusive."""
    lines, starts = source.splitlines(), [0]
    starts += [i for i, line in enumerate(lines) if line.lstrip().startswith(CELL) and i]
    ends = starts[1:] + [len(lines)]
    return [{"index": k, "line": a + 1, "end": max(a + 1, b), "title": lines[a].strip()[len(CELL):].strip() if lines and lines[a].lstrip().startswith(CELL) else ""}
            for k, (a, b) in enumerate(zip(starts, ends, strict=True))]


def run_cells(files: dict[str, str], file: str, upto: int, only: bool = False, symbols: list[str] | None = None) -> dict:
    """Runs cells 0..upto of `file` in one fresh namespace and returns each cell's printout and last value.
    `only` returns just the last cell's output (Run cell); otherwise every cell's (Run above and this).
    shortcut: each request re-runs from the top (no live kernel), so a slow cell above slows every run; keep a kernel when that bites."""
    import numpy as np

    from . import data, pycode

    start = time.perf_counter()
    sources = {n: s for n, s in files.items() if n.endswith(".py")}
    if file not in sources:
        raise KeyError(f"No file {file}")
    parts = cells(sources[file])
    upto = max(0, min(upto, len(parts) - 1))
    problems = pycode.check(sources[file], {}, modules={n[:-3] for n in sources} | {RESEARCH, FIXTURE}, entry=False)
    if problems:
        p = problems[0]
        return {"cells": parts, "outputs": [{"index": upto, "error": p["message"], "error_line": p["line"], "stdout": "", "value": None, "seconds": 0.0}], "seconds": 0.0}
    bars = {}
    for sym in (["SPY"] if symbols is None else symbols)[:5]:
        panel = data.panel([sym], None, None)
        if len(panel.dates):
            bars[sym] = {"dates": [str(d.date()) for d in panel.dates], **{k: [float(v) if np.isfinite(v) else None for v in getattr(panel, k)[:, 0]] for k in ("open", "high", "low", "close", "volume") if hasattr(panel, k)}}
    payload = {"files": sources, "fixture": FIXTURE, "cells": {"file": file, "parts": parts[:upto + 1], "only": only, "bars": bars}}
    outputs = _child(payload, [])
    return {"cells": parts, "outputs": outputs, "seconds": round(time.perf_counter() - start, 3)}


def discover(source: str) -> list[tuple[str, int]]:
    return [(n.name, n.lineno) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]


def run(files: dict[str, str], file: str | None = None, name: str | None = None) -> dict:
    from . import pycode

    start = time.perf_counter()
    sources = {n: s for n, s in files.items() if n.endswith(".py")}
    modules = {n[:-3] for n in sources} | {FIXTURE}
    rows, todo = [], []
    problems = {f: pycode.check(s, {}, modules=modules, entry=False) for f, s in sources.items()}
    bad = next(((f, p[0]) for f, p in problems.items() if p), None)
    for test_file in sorted(n for n in sources if Path(n).name.startswith("test_") and (file is None or n == file)):
        try:
            tests = [t for t in discover(sources[test_file]) if name is None or t[0] == name]
        except SyntaxError as e:
            rows.append({"file": test_file, "name": "<module>", "line": e.lineno or 1, "status": "error", "seconds": 0.0, "message": f"Syntax: {e.msg}", "error_line": e.lineno or 1})
            continue
        for test, line in tests:
            if bad:
                rows.append({"file": test_file, "name": test, "line": line, "status": "error", "seconds": 0.0,
                             "message": f"{bad[0]}: {bad[1]['message']}", "error_line": bad[1]["line"] if bad[0] == test_file else None})
            else:
                todo.append((test_file, test, line))
    if todo:
        rows += _child({"files": sources, "tests": todo, "fixture": FIXTURE}, todo)
    return {"tests": rows, "seconds": round(time.perf_counter() - start, 3)}


def _child(payload: dict, todo: list) -> list[dict]:
    from .pycode import TIMEOUT_S, _limits

    out: list[dict] = []
    try:
        p = subprocess.run([sys.executable, "-I", str(THIS)], input=json.dumps(payload), capture_output=True, text=True, timeout=TIMEOUT_S,
                           preexec_fn=_limits, env={"PATH": "/usr/bin:/bin"}, check=False)
        stdout, stderr = p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        stdout, stderr = (e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout) or "", f"Stopped after {TIMEOUT_S} s"
    for line in stdout.splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if not todo and not out:  # a cells run that died before its first cell finished
        out.append({"index": None, "stdout": "", "value": None, "error": (stderr.strip().splitlines() or ["the cell process died"])[-1], "error_line": None, "seconds": 0.0})
    seen = {(r.get("file"), r.get("name")) for r in out}
    for f, n, line in todo:  # the child died or timed out before reaching these
        if (f, n) not in seen:
            out.append({"file": f, "name": n, "line": line, "status": "error", "seconds": 0.0,
                        "message": (stderr.strip().splitlines() or ["the test process died"])[-1], "error_line": None})
    return out


def _bars(n=100, seed=0, symbol="TEST"):
    import numpy as np

    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.005, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.005, n))
    return {"open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(1_000, 100_000, n).astype(float)}


def _child_main() -> None:
    spec = importlib.util.spec_from_file_location("pyrunner", THIS.with_name("pyrunner.py"))
    pyrunner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pyrunner)
    payload = json.loads(sys.stdin.read())
    sources, fixture = payload["files"], payload["fixture"]
    builtins = {**pyrunner.SAFE_BUILTINS, "AssertionError": AssertionError}
    cache: dict[str, ModuleType] = {}
    libs: dict = {}

    def load(stem: str) -> ModuleType:
        if stem not in cache:
            module = cache[stem] = ModuleType(stem)
            module.__dict__.update({"__builtins__": builtins, "math": pyrunner.math})
            try:
                exec(compile(sources[stem + ".py"], f"<studio:{stem}.py>", "exec"), module.__dict__)  # noqa: S102 checked by pycode.check
            except BaseException:
                del cache[stem]
                raise
        return cache[stem]

    def guarded_import(name, globals_=None, locals_=None, fromlist=(), level=0):
        fromlist = tuple(fromlist or ())
        if not level and name == fixture:
            module = ModuleType(name)
            module.bars = _bars
            return module
        if not level and name + ".py" in sources and not any(i == "*" or i.startswith("_") for i in fromlist):
            return load(name)
        if not level and (name in pyrunner.ALLOWED_IMPORTS or name in pyrunner.LAZY_LIBRARY_MODULES or name.split(".")[0] in pyrunner.ALLOWED_ROOTS
                          and not set(name.split(".")) & {"ctypeslib", "f2py", "distutils", "testing"}):
            return libs.setdefault(name, __import__("importlib").import_module(name))
        raise ImportError(f"Import '{name}' is not allowed; allowed: {', '.join(pyrunner.ALLOWED_IMPORTS)} and saved project modules")

    if payload.get("cells"):
        _cells_main(payload["cells"], sources, builtins, guarded_import, pyrunner)
        return
    builtins["__import__"] = guarded_import
    loaded: dict[str, ModuleType | BaseException] = {}
    for file, test, line in payload["tests"]:
        t0 = time.perf_counter()
        row = {"file": file, "name": test, "line": line, "status": "passed", "seconds": 0.0}
        try:
            if file not in loaded:
                try:
                    loaded[file] = load(file[:-3])
                except BaseException as e:  # noqa: BLE001 a failing import fails each test of the file
                    loaded[file] = e
            if isinstance(loaded[file], BaseException):
                raise loaded[file]
            loaded[file].__dict__[test]()
        except BaseException as e:  # noqa: BLE001 report to the parent
            frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.startswith("<studio:")]
            row["status"] = "failed" if isinstance(e, AssertionError) else "error"
            row["error_line"] = frames[-1].lineno if frames else None
            text = str(e)
            if isinstance(e, AssertionError) and not text and frames:
                text = frames[-1].line or (sources.get(frames[-1].filename[8:-1], "").splitlines() or [""])[frames[-1].lineno - 1].strip()
            row["message"] = (text if isinstance(e, AssertionError) else f"{type(e).__name__}: {text}")[:1024]
        row["seconds"] = round(time.perf_counter() - t0, 4)
        sys.stdout.write(json.dumps(row) + "\n")
        sys.stdout.flush()


def _cells_main(job: dict, sources: dict, builtins: dict, guarded_import, pyrunner) -> None:
    import numpy as np
    import pandas as pd

    def load_bars(symbol: str = "") -> "pd.DataFrame":
        name = symbol or next(iter(job["bars"]), "")
        if name not in job["bars"]:
            raise KeyError(f"{name or 'No symbol'} is not loaded; pick it in the cell bar (loaded: {', '.join(job['bars']) or 'none'})")
        b = job["bars"][name]
        return pd.DataFrame({k: np.array(v, dtype=float) for k, v in b.items() if k != "dates"}, index=pd.to_datetime(b["dates"]))

    def cell_import(name, globals_=None, locals_=None, fromlist=(), level=0):
        if not level and name == RESEARCH:
            module = ModuleType(name)
            module.load = load_bars
            return module
        return guarded_import(name, globals_, locals_, fromlist, level)

    builtins["__import__"] = cell_import
    builtins["print"] = print
    namespace = {"__builtins__": builtins, "math": pyrunner.math}
    lines = sources[job["file"]].splitlines()
    real_stdout, last = sys.stdout, len(job["parts"]) - 1
    for part in job["parts"]:
        t0, buf = time.perf_counter(), io.StringIO()
        row = {"index": part["index"], "line": part["line"], "stdout": "", "value": None, "error": None, "error_line": None}
        try:
            tree = ast.parse("\n".join(lines[part["line"] - 1:part["end"]]))
            ast.increment_lineno(tree, part["line"] - 1)
            tail = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            with contextlib.redirect_stdout(buf):
                exec(compile(tree, f"<studio:{job['file']}>", "exec"), namespace)  # noqa: S102 checked by pycode.check
                if tail is not None:
                    value = eval(compile(ast.Expression(tail.value), f"<studio:{job['file']}>", "eval"), namespace)
                    row["value"] = pyrunner._debug_value(value) if value is not None else None
                    if row["value"] is None and value is not None:
                        row["value"] = repr(value)[:2000]
        except BaseException as e:  # noqa: BLE001 report the failing line
            frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.startswith("<studio:")]
            row["error"] = f"{type(e).__name__}: {e}"[:1024]
            row["error_line"] = frames[-1].lineno if frames else getattr(e, "lineno", None)
        row["stdout"] = buf.getvalue()[-20_000:]
        row["seconds"] = round(time.perf_counter() - t0, 4)
        if not job["only"] or part["index"] == last or row["error"]:
            real_stdout.write(json.dumps(row) + "\n")
            real_stdout.flush()
        if row["error"]:
            break


if __name__ == "__main__":
    _child_main()
