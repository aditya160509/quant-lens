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
    assert e.value.problem == {
        "file": "main.py", "line": 3, "column": 9, "exception_type": "IndexError",
        "traceback": [{"file": "main.py", "line": 3, "column": 9, "function": "on_bar"}],
    }


def test_signals_do_not_change_when_later_bars_are_cut():
    bars, dates = _bars(200, 2)
    code = "class Strategy:\n    def on_bar(self, ctx):\n        if ctx.position == 0 and ctx.close[-1] > max(ctx.close[-20:-1] or [1e9]):\n            ctx.buy()\n        elif ctx.position > 0 and ctx.close[-1] < ctx.value(\"sma(close, 20)\"):\n            ctx.sell()\n"
    full, _ = pycode.run(code, bars, dates, {})
    cut, _ = pycode.run(code, {k: v[:120] for k, v in bars.items()}, dates[:120], {})
    assert np.array_equal(full[:120], cut)


def test_runner_output_and_warmup():
    bars, dates = _bars(4, 1)
    output = {}
    entries, _ = pycode.run(
        """class Strategy:
    warmup = 2
    def on_bar(self, ctx):
        print("bar", ctx.bar)
        ctx.log("evaluated", "info")
        ctx.plot("close", ctx.close[-1])
        ctx.buy()
""",
        bars, dates, {}, symbols=["SPY"], output=output,
    )
    assert entries[:, 0].tolist() == [0, 0, 1, 0]
    assert output["logs"][:2] == [
        {"date": "2020-01-01", "symbol": "SPY", "line": 4, "text": "bar 0", "level": "info"},
        {"date": "2020-01-01", "symbol": "SPY", "line": 5, "text": "evaluated", "level": "info"},
    ]
    assert [point["value"] for point in output["plots"]["close"]] == bars["close"][:, 0].tolist()


def test_runner_log_cap():
    bars, dates = _bars(1, 1)
    output = {}
    pycode.run(
        'class Strategy:\n    def on_bar(self, ctx):\n        for i in range(50_003):\n            print(i)\n',
        bars, dates, {}, output=output,
    )
    assert len(output["logs"]) == 50_001
    assert output["logs"][-2]["text"] == "49999"
    assert output["logs"][-1]["text"] == "Output truncated after 50000 lines"


@pytest.mark.parametrize(("expression", "expected"), [
    ("ctx.close[:-50]", "[]"),
    ("ctx.close[-3:0]", "current"),
])
def test_history_slice_uses_only_available_bars(expression, expected):
    bars, dates = _bars(4, 1)
    output = {}
    pycode.run(
        f"class Strategy:\n    def on_bar(self, ctx):\n        if ctx.bar == 0:\n            print({expression})\n",
        bars, dates, {}, output=output,
    )
    assert output["logs"][0]["text"] == (str(bars["close"][0].tolist()) if expected == "current" else expected)


def test_python_event_runner_receives_actual_fill_and_can_exit_from_it():
    from app.services.studio_v3.core import engine, fills

    bars, dates = _bars(4, 1)
    output = {}
    code = """class Strategy:
    def on_bar(self, ctx):
        if ctx.bar == 0:
            ctx.buy()

    def on_fill(self, ctx, fill):
        ctx.log((fill.symbol, fill.side, fill.quantity, fill.price, fill.date, fill.fee))
        if fill.side == "buy":
            ctx.sell()
"""
    settings = engine.Params(size_mode=fills.SHARES, size=2, commission_bps=0,
                             slippage_bps=0, commission_share=0.25)
    result = pycode.run_event(code, bars, dates, {}, ["SPY"], settings, output=output)
    assert [row["date"] for row in output["logs"]] == [str(d.date()) for d in dates[1:3]]
    for i, side in enumerate(("buy", "sell"), 1):
        assert output["logs"][i - 1]["text"] == str(
            ("SPY", side, 2.0, float(bars["open"][i, 0]), str(dates[i].date()), 0.5)
        )
    assert result.trades[0, [engine.T_ENTRY_BAR, engine.T_EXIT_BAR, engine.T_SHARES]].tolist() == [1, 2, 2]


def test_portfolio_callback_sees_all_symbols_and_causal_schedule():
    from app.services.studio_v3.core import engine

    bars, _ = _bars(4, 2)
    dates = pd.DatetimeIndex(["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-04"])
    output = {}
    code = """class Strategy:
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        ctx.log((ctx.bar_index, ctx.symbols, ctx.is_week_start, ctx.is_month_start, ctx.every(2)))
        ctx.plot("value", ctx.portfolio.total_value)
        ctx.plot("BBB", ctx.bar("BBB").close)

    def rebalance(self, ctx):
        ctx.log("rebalance")
"""
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params(), output=output)
    rows = output["logs"]
    assert [row["text"] for row in rows] == [
        "rebalance",
        "(0, ('AAA', 'BBB'), True, True, True)",
        "(1, ('AAA', 'BBB'), False, False, False)",
        "rebalance",
        "(2, ('AAA', 'BBB'), True, True, True)",
        "(3, ('AAA', 'BBB'), False, False, False)",
    ]
    assert [point["value"] for point in output["plots"]["BBB"]] == bars["close"][:, 1].tolist()
    assert [point["value"] for point in output["plots"]["value"]] == [100_000] * 4


def test_portfolio_state_marks_actual_fills_and_is_read_only():
    from app.services.studio_v3.core import engine, fills

    bars, dates = _bars(4, 2)
    output = {}
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            ctx.buy("BBB")
        if ctx.bar_index == 1:
            ctx.plot("quantity", ctx.portfolio["BBB"].quantity)
            ctx.plot("cash", ctx.portfolio.cash)
            ctx.plot("equity", ctx.portfolio.total_value)
            ctx.plot("profit", ctx.pos("BBB").unrealized_profit)
            ctx.plot("gross", ctx.portfolio.gross_exposure)
            ctx.plot("leverage", ctx.portfolio.leverage)
"""
    settings = engine.Params(size_mode=fills.SHARES, size=5, slippage_bps=0, commission_bps=0)
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], settings, output=output)
    points = {name: series[0]["value"] for name, series in output["plots"].items()}
    gross = 5 * bars["open"][1, 1]
    assert points == {"quantity": 5, "cash": 100_000 - gross, "equity": 100_000, "profit": 0,
                      "gross": gross, "leverage": gross / 100_000}

    mutation = code.replace('ctx.buy("BBB")', 'ctx.portfolio["BBB"].quantity = 10')
    with pytest.raises(pycode.CodeError) as error:
        pycode.run_event(mutation, bars, dates, {}, ["AAA", "BBB"], settings)
    assert error.value.line == 4
    assert error.value.problem["exception_type"] == "FrozenInstanceError"


def test_portfolio_current_bar_refuses_indexing_future_sessions():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(3, 2)
    code = """class Strategy:
    def on_data(self, ctx):
        ctx.bar("BBB").close[1]
"""
    with pytest.raises(pycode.CodeError) as error:
        pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params())
    assert error.value.line == 3
    assert error.value.problem["exception_type"] == "TypeError"


def test_portfolio_order_quantity_and_conditional_fills():
    from app.services.studio_v3.core import engine

    dates = pd.bdate_range("2020-01-01", periods=6)
    bars = {field: np.array(values, dtype=float)[:, None] for field, values in {
        "open": [100, 101, 102, 95, 99, 103], "high": [100, 105, 105, 100, 104, 105],
        "low": [100, 99, 100, 92, 97, 102], "close": [100, 104, 102, 97, 103, 104], "volume": [1e6] * 6,
    }.items()}
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            ctx.market_order("SPY", 3)
        if ctx.bar_index == 1:
            ctx.limit_order("SPY", 2, 98)
        if ctx.bar_index == 3:
            ctx.stop_order("SPY", -2, 97)
        if ctx.bar_index == 4:
            ctx.liquidate()

    def on_fill(self, ctx, fill):
        ctx.log((fill.side, fill.quantity, fill.price))
"""
    output = {}
    result = pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(commission_bps=0, slippage_bps=0), output=output)
    assert [row["text"] for row in output["logs"]] == [
        "('buy', 3.0, 101.0)", "('buy', 2.0, 95.0)", "('sell', 2.0, 97.0)", "('sell', 3.0, 103.0)",
    ]
    assert result.equity[-1] == pytest.approx(100_000 + result.trades[:, engine.T_PNL].sum())
    assert result.positions[-1] == 0


def test_stop_limit_waits_when_intrabar_order_is_unknown():
    from app.services.studio_v3.core import engine

    dates = pd.bdate_range("2020-01-01", periods=4)
    bars = {field: np.array(values, dtype=float)[:, None] for field, values in {
        "open": [100, 100, 104, 100], "high": [100, 110, 105, 100],
        "low": [100, 99, 103, 100], "close": [100, 108, 104, 100], "volume": [1e6] * 4,
    }.items()}
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            ctx.stop_limit_order("SPY", 5, 105, 102)

    def on_fill(self, ctx, fill):
        ctx.plot("fill", fill.price)
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    assert output["plots"]["fill"] == [{"date": "2020-01-06", "symbol": None, "value": pytest.approx(100.02)}]


def test_target_weight_and_cancel_orders():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(4, 2)
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            ctx.target_weights({"AAA": 0.25})
            ctx.limit("BBB", 1, 1)
        elif ctx.bar_index == 1:
            ctx.cancel_all()
            ctx.set_weight("AAA", 0)
        elif ctx.bar_index == 2:
            ctx.order_value("BBB", ctx.bar("BBB").close * 2)
            ctx.cancel("BBB")
"""
    result = pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params())
    assert result.trades[:, engine.T_SYM].tolist() == [0]
    assert result.trades[0, engine.T_SHARES] == pytest.approx(25_000 / bars["close"][0, 0])
    assert result.positions.tolist() == [0, 1, 0, 0]


def test_portfolio_history_is_bounded_and_keeps_its_original_bar():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(3, 2)
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            self.saved = ctx.history("close", 3, "BBB")
        if ctx.bar_index == 1:
            history = ctx.history(("close", "open"), 2)["BBB"]
            ctx.plot("current", history["close"][0])
            ctx.plot("previous", history["close"][-1])
            ctx.plot("saved", self.saved[0])
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params(), output=output)
    assert {name: points[0]["value"] for name, points in output["plots"].items()} == {
        "current": bars["close"][1, 1], "previous": bars["close"][0, 1], "saved": bars["close"][0, 1],
    }
    with pytest.raises(pycode.CodeError) as exc:
        pycode.run_event(code.replace('history["close"][0]', 'history["close"][1]'),
                         bars, dates, {}, ["AAA", "BBB"], engine.Params())
    assert exc.value.line == 7
    assert "history[1] reads a future bar" in exc.value.message


def test_benchmark_exposes_only_current_close():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(3, 2)
    benchmark = np.array([np.nan, 121.0, 130.0])
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.market is not None:
            ctx.plot("benchmark", ctx.market.close)
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params(), benchmark=benchmark, output=output)
    assert output["plots"]["benchmark"] == [
        {"date": str(dates[1].date()), "symbol": None, "value": 121},
        {"date": str(dates[2].date()), "symbol": None, "value": 130},
    ]
    with pytest.raises(pycode.CodeError) as exc:
        pycode.run_event(code.replace("ctx.market.close)", "ctx.market.close[1])"),
                         bars, dates, {}, ["AAA", "BBB"], engine.Params(), benchmark=benchmark)
    assert exc.value.line == 4


def test_portfolio_rank_and_zscore_use_observed_symbols_only():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(3, 3)
    bars["close"] = np.array([[10, 20, np.nan], [20, 10, 100], [30, 10, 200]], dtype=float)
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            ctx.log(ctx.rank("close", top=1))
            ctx.log(ctx.rank("close", bottom=1, where="close > 10"))
            ctx.log(tuple(ctx.zscore("close").items()))
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB", "CCC"], engine.Params(), output=output)
    assert [row["text"] for row in output["logs"]] == [
        "[('BBB', 20.0)]", "[('BBB', 20.0)]", "(('AAA', -1.0), ('BBB', 1.0))",
    ]
    with pytest.raises(pycode.CodeError, match="Look-ahead"):
        pycode.run_event(code.replace('where="close > 10"', 'where="future(close)"'),
                         bars, dates, {}, ["AAA", "BBB", "CCC"], engine.Params())
