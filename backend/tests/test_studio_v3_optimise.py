"""Optimise acceptance (PAGES O-1..O-3)."""

import time

import numpy as np

from app.services.studio_v3.core import optimise as O
from app.services.studio_v3.core import store
from app.services.studio_v3.core.spec import Settings, Strategy

RANGES = {"a": (0.0, 10.0, 1.0), "b": (0.0, 10.0, 1.0)}


def _cells(f):
    return [{"a": float(a), "b": float(b), "score": f(a, b)} for a in range(11) for b in range(11)]


def test_spike_is_called_a_spike():  # O-1
    out = O.plateau(_cells(lambda a, b: 3.0 if (a, b) == (7, 2) else 0.1 * np.sin(a * b)), ["a", "b"], RANGES)
    assert out["status"] == "spike" and out["best"] == {"a": 7.0, "b": 2.0}


def test_plateau_is_called_a_plateau():  # O-1
    out = O.plateau(_cells(lambda a, b: 1.0 - 0.02 * ((a - 5) ** 2 + (b - 5) ** 2)), ["a", "b"], RANGES)
    assert out["status"] == "plateau" and 4 <= out["centre"]["a"] <= 6 and 4 <= out["centre"]["b"] <= 6


def test_thousand_cells_one_symbol_under_ten_seconds_and_every_cell_is_a_trial(tmp_path, monkeypatch):  # O-2, O-3
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "studio.sqlite")
    spec = Strategy(entry_long="crosses_above(sma(close, fast), sma(close, slow))", exit_long="crosses_below(sma(close, fast), sma(close, slow))",
                    params={"fast": {"value": 20, "min": 5, "max": 100, "step": 1}, "slow": {"value": 100, "min": 50, "max": 300, "step": 1}})
    t = time.perf_counter()
    out = O.run_optimise(spec, Settings(symbols=["SPY"]), "grid", "sharpe", 1000)
    assert time.perf_counter() - t < 10
    assert out["meta"]["cells"] >= 900 and len(out["_trials"]) == out["meta"]["cells"]
    sid = store.create(spec)["id"]
    for tr in out["_trials"][:50]:
        store.record_trial(sid, tr["hash"], "human", "optimise", tr["sharpe"], tr["returns"])
    led = store.ledger(sid, detail=False)
    assert led["raw"] == 50 and led["effective"] < 50  # neighbouring cells are correlated tries


def test_custom_objective_and_link_rule_are_checked_and_applied():
    import pytest

    from app.services.studio_v3.core import optimise as O
    from app.services.studio_v3.core.backtest import Refusal

    assert O._arith("cagr / abs(max_drawdown)", {"cagr": 0.1, "max_drawdown": -0.2}) == pytest.approx(0.5)
    assert O._arith("fast < slow", {"fast": 10, "slow": 50}) is True
    with pytest.raises(Refusal):
        O.check_expr("__import__('os')", O.METRIC_NAMES)
    cells = [{"a": a, "b": b, "score": float(a + b)} for a in range(5) for b in range(5)]
    st = O.stability(cells, ["a", "b"], {"a": (0, 4, 1), "b": (0, 4, 1)}, {"a": 4, "b": 4})
    assert st["cells"] == 4 and st["within_20pct"] == 0.75  # (3,3)=6 is more than 20% below the best 8


def test_python_declared_parameters_are_used_by_preview_and_grid():
    from app.services.studio_v3.core import backtest
    from app.services.studio_v3.core import compile as C

    spec = Strategy(code="""class Strategy:
    params = {"shares": (2, 1, 3, 1)}
    def on_data(self, ctx):
        if ctx.bar_index == 10:
            ctx.market_order("SPY", ctx.param("shares"))
        elif ctx.bar_index == 11:
            ctx.liquidate("SPY")
""")
    compiled = C.compile_spec(spec)
    assert compiled["ok"] and compiled["parameters"]["shares"]["value"] == 2
    assert O._ranges(spec) == {"shares": (1, 3, 1)}
    prep = backtest.prepare(Settings(symbols=["SPY"]))
    for quantity in (1, 2, 3):
        result = backtest.simulate(spec, prep, Settings(symbols=["SPY"]), params={"shares": quantity})
        assert result.trades[:, backtest.engine.T_SHARES].tolist() == [quantity]
    result = O.run_optimise(spec, Settings(symbols=["SPY"]), "grid", "sharpe", 3)
    assert result["meta"]["cells"] == 3


def test_python_starter_gallery_trades_on_real_market_data():
    from app.services.studio_v3.core import backtest, templates
    from app.services.studio_v3.core import compile as C

    gallery = templates.list_python_templates()
    assert len({item["name"] for item in gallery}) == 11
    prepared = {}
    for item in gallery:
        spec = Strategy(**item["spec"])
        settings = Settings(symbols=item["symbols"], benchmark="")
        key = tuple(settings.symbols)
        if key not in prepared:
            prepared[key] = backtest.prepare(settings)
        assert C.compile_spec(spec)["ok"], item["name"]
        result = backtest.simulate(spec, prepared[key], settings)
        assert len(result.trades) > 0, item["name"]
