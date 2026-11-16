"""Build › Python: static checks, sandboxed run, parity with formulas, no look-ahead."""

import numpy as np
import pandas as pd
import pytest

from app.services.studio_v3.core import compile as C
from app.services.studio_v3.core import pycode
from app.services.studio_v3.core.spec import Strategy


def _bars(n=300, k=3):
    rng = np.random.default_rng(1)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.01, (n, k)), axis=0)
    return {"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": np.ones((n, k))}, pd.bdate_range("2020-01-01", periods=n)


def test_python_matches_the_same_rule_as_formula():
    bars, dates = _bars()
    f = Strategy(entry_long="crosses_above(sma(close, 10), sma(close, 30))", exit_long="crosses_below(sma(close, 10), sma(close, 30))")
    a, b = C.signals(f, bars, dates), C.signals(Strategy(code=pycode.from_formulas(f)), bars, dates)
    # Formula fires every cross; Python only when flat or long, which the engine does anyway.
    assert (b.entries[a.entries == 1] == 1).mean() > 0.9 and not ((b.entries == 1) & (a.entries != 1)).any()


def test_banned_code_is_refused_before_it_runs():
    lines = {f["token"] for f in pycode.check("import os\nclass Strategy:\n    def on_bar(self, ctx):\n        open('x')\n        ctx.close.__class__\n", {})}
    assert {"import", "open", "__class__"} <= lines


def test_positive_index_is_look_ahead_and_reports_its_line():
    bars, dates = _bars(50, 1)
    with pytest.raises(pycode.CodeError) as e:
        pycode.run("class Strategy:\n    def on_bar(self, ctx):\n        ctx.close[0]\n", bars, dates, {})
    assert e.value.line == 3 and "negative" in e.value.message


def test_signals_do_not_change_when_later_bars_are_cut():
    bars, dates = _bars(200, 2)
    code = "class Strategy:\n    def on_bar(self, ctx):\n        if ctx.position == 0 and ctx.close[-1] > max(ctx.close[-20:-1] or [1e9]):\n            ctx.buy()\n        elif ctx.position > 0 and ctx.close[-1] < ctx.value(\"sma(close, 20)\"):\n            ctx.sell()\n"
    full, _ = pycode.run(code, bars, dates, {})
    cut, _ = pycode.run(code, {k: v[:120] for k, v in bars.items()}, dates[:120], {})
    assert np.array_equal(full[:120], cut)
