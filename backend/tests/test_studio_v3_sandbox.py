"""Build › Python: the A7 import allow-list, enforced in the AST and again at import time, plus known escapes."""

import json
import subprocess
import sys

import numpy as np
import pytest

from app.services.studio_v3.core import engine, formula, pycode
from app.services.studio_v3.core.spec import Strategy


def _bars(n=40, k=2):
    rng = np.random.default_rng(3)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.01, (n, k)), axis=0)
    return {"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": np.ones((n, k))}, None


def _child(code, tmp_path):
    """Run the sandboxed child directly, past the AST screen, to prove the second gate."""
    T, N = 2, 1
    base = np.ones((T, N), dtype=float)
    meta = {"exprs": [], "params": {}, "symbols": ["SPY"], "dates": ["2020-01-01", "2020-01-04"], "event_settings": None,
            "repaint_bars": [], "modules": {}, "debug_symbol": None, "debug_after": None, "debug_event": None,
            "debug_breakpoint": None, "debug_loss": None}
    src, dst = tmp_path / "in.npz", tmp_path / "out.npz"
    np.savez(src, meta=np.array(json.dumps(meta)), **{f: base for f in ("open", "high", "low", "close", "volume")})
    p = subprocess.run([sys.executable, "-I", str(pycode.RUNNER), str(src), str(dst)], check=False, input=code, capture_output=True,
                       text=True, timeout=60, env={"PATH": "/usr/bin:/bin"})
    return json.loads(p.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("line", [
    "import numpy as np",
    "import pandas as pd",
    "import math",
    "import statistics",
    "import scipy.stats",
    "from scipy import stats",
    "from scipy.stats import norm",
    "from math import sqrt",
    "from numpy import mean",
])
def test_allowed_imports_pass_the_static_check(line):
    assert pycode.check(f"{line}\n", {}, entry=False) == []


def test_allowed_imports_run_in_the_sandboxed_child(tmp_path):
    code = """
import math
import statistics
import numpy as np
import pandas as pd
from scipy import stats

class Strategy:
    def on_bar(self, ctx):
        ctx.plot("mean", float(np.mean([1.0, 3.0])))
        ctx.plot("median", float(pd.Series([1.0, 3.0]).median()))
        ctx.plot("z", float(stats.norm.cdf(0.0)))
        ctx.plot("log", math.log(2.0) + statistics.fmean([2.0, 4.0]))
"""
    assert _child(code, tmp_path)["ok"] is True


def test_imports_are_refused_at_import_time_even_past_the_ast_screen(tmp_path):
    result = _child("import os\n\nclass Strategy:\n    def on_bar(self, ctx):\n        pass\n", tmp_path)
    assert "ok" not in result and "Import 'os' is not allowed" in result["error"]


def test_numpy_cannot_reach_the_filesystem():
    """The child only repeats the import gate; file-reaching library calls are refused in the AST."""
    found = pycode.check("import numpy as np\n\nclass Strategy:\n    def on_bar(self, ctx):\n"
                         "        np.load('/etc/passwd')\n", {})
    assert [f["token"] for f in found] == ["load"]


def test_saved_project_modules_import_next_to_the_allow_list():
    code = "from helpers import double\n\nclass Strategy:\n    def on_bar(self, ctx):\n        print(double(2))\n"
    assert pycode.check(code, {}, modules={"helpers"}) == []
    assert pycode.check(code, {})  # without the saved file the import is refused


def test_helper_module_may_import_an_allowed_library():
    helper = "import math\n\ndef double(x):\n    return math.floor(x) * 2\n"
    found = pycode.check_project("from helpers import double\n\nclass Strategy:\n    def on_bar(self, ctx):\n        pass\n", {}, {"helpers.py": helper})
    assert found == []


# A known sandbox breakout each; every one is refused before it can run.
ESCAPES = [
    "import os",
    "import sys",
    "import io",
    "import socket",
    "import subprocess",
    "import importlib",
    "import ctypes",
    "import pickle",
    "import pathlib",
    "import shutil",
    "import sklearn",
    "import numpy.linalg",
    "from os import path",
    "from subprocess import run",
    "from pathlib import Path",
    "from numpy import *",
    "from scipy.stats import *",
    "open('/etc/passwd')",
    "eval('1 + 1')",
    "exec('x = 1')",
    "compile('1', 'x', 'eval')",
    "globals()",
    "locals()",
    "vars()",
    "getattr(ctx, 'close')",
    "setattr(ctx, 'position', 1)",
    "delattr(ctx, 'symbol')",
    "input()",
    "breakpoint()",
    "type(ctx)",
    "__import__('os')",
    "().__class__.__bases__",
    "ctx.close.__class__",
    "ctx.__dict__",
    "global stolen\n",
    "ctx.close.format(1)",
    "np.load('x.npy')",
    "np.fromfile('/etc/passwd')",
    "np.memmap('/etc/passwd')",
    "np.ctypeslib.load_library('x', '.')",
    "pd.read_pickle('x.pkl')",
    "pd.read_csv('/etc/passwd')",
    "pd.DataFrame().to_pickle('x')",
    "np.DataSource().open('/etc/passwd')",
    "np.loadtxt('/etc/passwd')",
    "np.genfromtxt('/etc/passwd')",
    "np.fromregex('/etc/passwd', 'a', [('a', 'S1')])",
    "np.savez('/tmp/x', a=1)",
    "np.array([1]).tofile('/tmp/x')",
    "np.array([1]).dump('/tmp/x')",
    "np.lib.npyio.os",
    "np.sys",
    "np.testing",
    "pd.io",
    "pd.DataFrame().to_latex('/tmp/x')",
    "pd.DataFrame().to_string('/tmp/x')",
    "pd.DataFrame().to_html('/tmp/x')",
    "pd.DataFrame().query('a')",
    "pd.eval('1')",
    "pd.HDFStore('x')",
]


@pytest.mark.parametrize("source", ESCAPES)
def test_known_sandbox_breakouts_are_refused(source):
    assert pycode.check(source, {}, entry=False), source


def test_escape_suite_covers_the_union_of_refusals():
    assert len(ESCAPES) >= 25
    tokens = {f["token"] for source in ESCAPES for f in pycode.check(source, {}, entry=False)}
    assert {"os", "sys", "socket", "subprocess", "importlib", "ctypes", "pickle", "open", "eval", "exec"} <= tokens


def test_a_saved_strategy_using_an_allowed_library_trades():
    bars, _ = _bars(60, 1)
    import pandas as pd

    dates = pd.bdate_range("2020-01-01", periods=60)
    code = """
import numpy as np

class Strategy:
    warmup = 20

    def on_bar(self, ctx):
        if ctx.close[-1] > np.mean(ctx.close[-20:]):
            ctx.buy()
        else:
            ctx.sell()
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    assert output["warmup"]["bars"] == 20
    spec = Strategy(code=code)
    assert pycode.check_project(spec.code, {}, spec.files) == []
    assert formula.evaluate("sma(close, 3)", bars, dates).shape == bars["close"].shape


@pytest.mark.parametrize("source", [
    "from sklearn.datasets import fetch_openml",
    "import sklearn.model_selection",
    "import joblib",
    "from sklearn.utils import check_array",
    "from sklearn.ensemble import RandomForestClassifier\nRandomForestClassifier(n_jobs=4)",
    "from sklearn.ensemble import RandomForestClassifier\nRandomForestClassifier().joblib",
    "from sklearn.linear_model import Ridge\nRidge().__class__",
    "import scipy.io",
    "from scipy import optimize\noptimize.__loader__",
])
def test_models_are_allowed_but_their_escape_routes_are_refused(source):
    assert pycode.check(source, {}, entry=False), source


@pytest.mark.parametrize("source", [
    "from scipy.optimize import minimize",
    "from sklearn.linear_model import Ridge",
    "from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier",
    "from sklearn.preprocessing import StandardScaler",
])
def test_scipy_optimize_and_sklearn_models_pass_the_import_check(source):
    assert pycode.check(source, {}, entry=False) == [], source


def test_a_model_fits_on_past_bars_only_and_trades():
    import pandas as pd

    bars, _ = _bars(200, 2)
    dates = pd.bdate_range("2020-01-01", periods=200)
    code = """import numpy as np
from sklearn.linear_model import Ridge


class Strategy:
    warmup = 60

    def init(self, ctx):
        self.model = None

    def on_data(self, ctx):
        if ctx.fit_every(20) and ctx.t >= 61:
            rows = ctx.feature_matrix(["roc(close, 5)", "rsi(close, 14)"], 60, "AAA")
            past = ctx.history("close", 61, "AAA")
            closes = np.array(list(past))[::-1]
            target = np.append(closes[2:] / closes[1:-1] - 1, np.nan)  # each row's next return; the newest row has none yet
            keep = np.isfinite(rows).all(axis=1) & np.isfinite(target)
            if keep.sum() > 10:
                self.model = Ridge(alpha=1.0).fit(rows[keep], target[keep])
        if self.model is not None:
            now = ctx.feature_matrix(["roc(close, 5)", "rsi(close, 14)"], 1, "AAA")
            if np.isfinite(now).all():
                ctx.set_holdings("AAA", 0.5 if self.model.predict(now)[0] > 0 else 0.0)
"""
    result = pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params())
    assert len(result.trades) >= 1
    # the matrix at bar t is identical whether or not later bars exist
    probe = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 80:
            ctx.log(str(ctx.feature_matrix(["sma(close, 5)"], 3, "AAA").tolist()))
"""
    full, cut = {}, {}
    pycode.run_event(probe, bars, dates, {}, ["AAA", "BBB"], engine.Params(), output=full)
    pycode.run_event(probe, {k: v[:81] for k, v in bars.items()}, dates[:81], {}, ["AAA", "BBB"], engine.Params(), output=cut)
    assert full["logs"][0]["text"] == cut["logs"][0]["text"]
    with pytest.raises(pycode.CodeError, match="literal formula"):
        pycode.run_event("class Strategy:\n    def on_data(self, ctx):\n        ctx.feature_matrix([ctx.symbols[0]], 3, 'AAA')\n", bars, dates, {}, ["AAA", "BBB"], engine.Params())


def test_library_internals_are_not_importable_from_strategy_source():
    assert pycode.check("from numpy._core import _methods", {}, entry=False)
    assert pycode.check("from numpy import __doc__", {}, entry=False)
    assert pycode.check("import numpy.ctypeslib", {}, entry=False)
