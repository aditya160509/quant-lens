"""Strategy tests: run `def test_*()` from the project's test_*.py files in a sandboxed child process.

Parent: `run(files, file, name)`. Child: `python -I strategy_tests.py`, JSON on stdin, one JSON line per test on stdout.
Tests `from studio.testing import bars` for fake OHLCV (dict of float arrays: open, high, low, close, volume).
"""

import ast
import importlib.util
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType

THIS = Path(__file__)
FIXTURE = "studio.testing"


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
    seen = {(r["file"], r["name"]) for r in out}
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


if __name__ == "__main__":
    _child_main()
