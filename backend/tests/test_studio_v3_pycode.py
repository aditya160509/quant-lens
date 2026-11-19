"""Build › Python: static checks, sandboxed run, parity with formulas, no look-ahead."""

import numpy as np
import pandas as pd
import pytest

from app.services.studio_v3.core import compile as C
from app.services.studio_v3.core import formula, pycode
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
    assert {"os", "open", "__class__"} <= lines


def test_positive_index_is_look_ahead_and_reports_its_line():
    bars, dates = _bars(50, 1)
    with pytest.raises(pycode.CodeError) as e:
        pycode.run("class Strategy:\n    def on_bar(self, ctx):\n        ctx.close[0]\n", bars, dates, {})
    assert e.value.line == 3 and "negative" in e.value.message
    assert e.value.problem == {
        "file": "main.py", "line": 3, "column": 9, "exception_type": "IndexError",
        "traceback": [{"file": "main.py", "line": 3, "column": 9, "function": "on_bar"}],
        "locals": {"symbol": "0", "date": "2020-01-01", "bar_index": 0, "variables": {}, "state": {}},
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


@pytest.mark.parametrize(
    ("callback", "order"),
    [("on_bar", "ctx.buy()"), ("on_data", 'ctx.market_order("SPY", 1)')],
)
def test_python_lifecycle_hooks_follow_warmup_and_run_order(callback, order):
    from app.services.studio_v3.core import engine

    bars, dates = _bars(4, 1)
    code = f"""class Strategy:
    warmup = 2
    def on_warmup_done(self, ctx):
        ctx.log("warmup done")
    def {callback}(self, ctx):
        ctx.log("bar")
    def on_end_of_day(self, ctx):
        ctx.log("end of day")
        {order}
    def on_stop(self, ctx):
        ctx.log("stop")
"""
    output = {}
    result = pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    assert [row["text"] for row in output["logs"]] == [
        "bar", "end of day", "bar", "end of day", "warmup done",
        "bar", "end of day", "bar", "end of day", "stop",
    ]
    assert result.trades[0, engine.T_ENTRY_BAR] == 3
    assert output["logs"][4]["date"] == str(dates[2].date())
    assert output["logs"][-1]["date"] == str(dates[-1].date())


def test_warmup_reports_first_observed_trading_eligible_date():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(4, 2)
    bars["close"][:2, 1] = np.nan
    code = """class Strategy:
    warmup = 2
    def on_bar(self, ctx):
        ctx.buy()
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params(), output=output)
    assert output["warmup"] == {
        "bars": 2, "first_eligible_date": str(dates[2].date()),
        "first_eligible_by_symbol": {"AAA": str(dates[2].date()), "BBB": None},
    }


@pytest.mark.parametrize(("schedule", "expected"), [
    ("daily", [0, 1, 2, 3, 4]),
    ("week_start", [0, 2, 4]),
    ("month_start", [0, 1, 2, 3]),
    ("quarter_start", [0, 1, 3]),
    ("year_start", [0, 1]),
    (2, [0, 2, 4]),
    (None, []),
])
def test_rebalance_schedule_and_bar_flag_agree(schedule, expected):
    from app.services.studio_v3.core import engine

    bars, _ = _bars(5, 1)
    dates = pd.DatetimeIndex(["2025-12-31", "2026-01-02", "2026-03-31", "2026-04-01", "2026-04-06"])
    code = f"""class Strategy:
    rebalance_schedule = {schedule!r}

    def rebalance(self, ctx):
        ctx.log(ctx.bar_index)

    def on_data(self, ctx):
        ctx.plot("scheduled", ctx.rebalancing)
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    assert [int(row["text"]) for row in output["logs"]] == expected
    assert [i for i, row in enumerate(output["plots"]["scheduled"]) if row["value"]] == expected


def test_indicator_handle_updates_with_the_current_bar_and_supports_ranking():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(4, 2)
    code = """class Strategy:
    def init(self, ctx):
        self.fast = ctx.indicator("sma", "BBB", 2)
        self.ranked = ctx.indicator("close")

    def on_data(self, ctx):
        if self.fast.ready:
            ctx.plot("average", self.fast.value)
            ctx.plot("current", self.fast.window[0])
            ctx.log(len(self.fast.window))
        if ctx.bar_index == 0:
            ctx.log(ctx.rank(self.ranked, top=1)[0][0])
"""
    output = {}
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params(), output=output)
    expected = [(a + b) / 2 for a, b in zip(bars["close"][:-1, 1], bars["close"][1:, 1], strict=True)]
    assert [row["value"] for row in output["plots"]["average"]] == pytest.approx(expected)
    assert [row["value"] for row in output["plots"]["current"]] == pytest.approx(expected)
    assert [row["text"] for row in output["logs"]] == ["BBB", "2", "2", "2"]


# --- LEAN indicator definitions (LEAN_PARITY row 19) and A4 handles -----------------


def _one(values, field="close"):
    shape = (len(values), 1)
    close = np.asarray(values, dtype=float).reshape(shape)
    bars = {f: close.copy() for f in ("open", "high", "low", "close", "volume")}
    return bars, pd.bdate_range("2020-01-01", periods=len(values))


def test_ema_is_seeded_with_the_sma_and_smooths_with_two_over_n_plus_one():
    bars, dates = _one([10, 12, 11, 15, 14, 16])
    ema = formula.evaluate("ema(close, 3)", bars, dates)[:, 0]
    expected = [np.nan, np.nan, 11.0, 13.0, 13.5, 14.75]
    assert np.allclose(ema, expected, equal_nan=True)
    assert np.isnan(ema[:2]).all()  # not ready before the window is full


def test_rsi_is_wilder_seeded_with_the_mean_of_the_first_gains_and_losses():
    bars, dates = _one([10, 11, 10, 12])
    rsi = formula.evaluate("rsi(close, 2)", bars, dates)[:, 0]
    assert np.allclose(rsi, [np.nan, np.nan, 50.0, 100 - 100 / (1 + 1.25 / 0.25)], equal_nan=True)


def test_atr_is_wilder_on_true_range_seeded_with_the_first_window_mean():
    close = np.array([[10.0], [11.0], [12.0]])
    bars = {"open": close.copy(), "high": np.array([[10.5], [11.5], [12.5]]), "low": np.array([[9.5], [10.5], [11.5]]),
            "close": close, "volume": np.ones((3, 1))}
    atr = formula.evaluate("atr(2)", bars, pd.bdate_range("2020-01-01", periods=3))[:, 0]
    assert np.allclose(atr, [np.nan, 1.25, 1.375], equal_nan=True)


def test_indicator_handle_reads_the_same_values_as_the_formula():
    bars, dates = _one([10, 12, 11, 15, 14, 16])
    code = """class Strategy:
    def init(self, ctx):
        self.average = ctx.indicator("sma", None, 3)

    def on_bar(self, ctx):
        if self.average.ready:
            ctx.plot("value", self.average.value)
            ctx.plot("window", self.average.window[0])
"""
    from app.services.studio_v3.core import engine

    output = {}
    pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    window = pd.Series(bars["close"][:, 0]).rolling(3, min_periods=3).mean().to_numpy()
    assert [row["value"] for row in output["plots"]["value"]] == pytest.approx(window[2:].tolist())
    assert [row["value"] for row in output["plots"]["window"]] == pytest.approx(window[2:].tolist())


def test_lean_style_self_sma_builds_the_same_handle():
    bars, dates = _one([10, 12, 11, 15, 14, 16])
    code = """class Strategy:
    def init(self, ctx):
        self.fast = self.sma("SPY", 2)
        self.own = self.sma(3)

    def on_bar(self, ctx):
        if self.fast.ready and self.own.ready:
            ctx.plot("fast", self.fast.value)
            ctx.plot("own", self.own.value)
"""
    from app.services.studio_v3.core import engine

    output = {}
    pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    close = bars["close"][:, 0]
    assert [row["value"] for row in output["plots"]["fast"]] == pytest.approx([(close[t - 1] + close[t]) / 2 for t in range(2, len(close))])


def test_completion_offers_the_numerical_libraries():
    numpy = {member["name"]: member for member in pycode.editor_members("numpy", "", "")}
    assert {"mean", "nanmean", "where"} <= set(numpy)
    assert numpy["mean"]["signature"] == "mean(a)" and numpy["mean"]["documentation"]
    pandas = {member["name"] for member in pycode.editor_members("pandas", "", "")}
    assert {"DataFrame", "Series", "rolling"} <= pandas


def _long_strategy(hundreds=3):
    body = ["class Strategy:", "    def on_bar(self, ctx):"]
    i = 0
    while len(body) < hundreds * 100:
        body += [f"        value_{i} = ctx.close[-1] * {i}", f"        if value_{i} > {i}:", f"            ctx.log(value_{i}, \"info\")"]
        i += 1
    return "\n".join(body[: hundreds * 100]) + "\n"


def test_lint_p95_under_150_ms_for_300_lines():
    import time

    code = _long_strategy(3)
    timings = []
    for _ in range(20):
        started = time.perf_counter()
        pycode.lint(code, {})
        timings.append(time.perf_counter() - started)
    p95 = sorted(timings)[18]
    assert p95 < 0.15, f"p95 {p95 * 1000:.1f} ms"


def test_completion_p95_under_50_ms():
    import time

    code = _long_strategy(3)
    timings = []
    for _ in range(20):
        started = time.perf_counter()
        pycode.editor_members("ctx", code, "p")
        timings.append(time.perf_counter() - started)
    p95 = sorted(timings)[18]
    assert p95 < 0.05, f"p95 {p95 * 1000:.1f} ms"


# --- B-163: QuantConnect import -----------------------------------------------------

QC_ALGORITHM = '''from AlgorithmImports import *
from datetime import timedelta

class MyAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetCash(100000)
        self.AddEquity("SPY", Resolution.Daily)
        self.SetWarmUp(40)
        self.sma = self.SMA("SPY", 50)

    def OnData(self, data):
        if not self.sma.IsReady:
            return
        if not self.Portfolio.Invested:
            self.SetHoldings("SPY", 1.0)
        elif data["SPY"].Close < self.sma.Current.Value:
            self.Liquidate()

    def OnOrderEvent(self, event):
        self.Log(event.FillPrice)
'''


def test_quantconnect_import_rewrites_calls_and_keeps_user_code():
    from app.services.studio_v3.core import qc_import

    out = qc_import.convert(QC_ALGORITHM)
    assert out["ok"] is True
    assert "class Strategy:" in out["code"] and "def init(self, ctx):" in out["code"]
    assert "warmup = 40" in out["code"]
    assert 'ctx.indicator("sma", "SPY", 50)' in out["code"]
    assert "ctx.set_holdings(\"SPY\", 1.0)" in out["code"]
    assert 'ctx.bar("SPY").close' in out["code"]
    assert "ctx.portfolio.invested" in out["code"]
    assert "def on_fill(self, ctx, fill)" in out["code"] and "fill.price" in out["code"]
    assert out["symbols"] == ["SPY"] and out["settings"]["capital"] == 100000.0
    assert out["problems"] == []


def test_quantconnect_import_lists_every_line_it_could_not_convert():
    from app.services.studio_v3.core import qc_import

    source = QC_ALGORITHM.replace(
        "        self.Liquidate()",
        "        self.Liquidate()\n        self.Schedule.On(self.DateRules.MonthStart(), self.TimeRules.AfterMarketOpen(\"SPY\"), self.Rebalance)",
    )
    out = qc_import.convert(source)
    reasons = {row["source"]: row["reason"] for row in out["unconverted"]}
    assert any("Schedule.On" in source for source in reasons)
    assert any("rebalance" in reason for reason in reasons.values())
    assert out["ok"] is True  # the rest still compiles


def test_quantconnect_import_refuses_a_pasted_non_qc_file():
    from app.services.studio_v3.core import qc_import

    out = qc_import.convert("print('hello')\n")
    assert out["ok"] is False and "QCAlgorithm" in out["problems"][0]["message"]


def test_converted_quantconnect_algorithm_trades_in_the_event_engine():
    from app.services.studio_v3.core import engine, qc_import

    bars, _ = _bars(120, 1)
    dates = pd.bdate_range("2020-01-01", periods=120)
    code = qc_import.convert(QC_ALGORITHM)["code"]
    result = pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params())
    assert len(result.trades) >= 1


def test_python_backtest_budget_500_symbols_by_2500_bars():  # A14, B-65
    """Synthetic engine workload; real-data loading is measured separately in the Backtest suite."""
    import time

    from app.services.studio_v3.core import engine

    bars, dates = _bars(2500, 500)
    code = """class Strategy:
    warmup = 60
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        if not ctx.rebalancing:
            return
        chosen = {symbol for symbol, _ in ctx.rank("roc(close, 60)", top=20)}
        ctx.target_weights({symbol: 0.04 if symbol in chosen else 0 for symbol in ctx.symbols})
"""
    started = time.perf_counter()
    result = pycode.run_event(code, bars, dates, {}, [f"S{i}" for i in range(500)], engine.Params())
    elapsed = time.perf_counter() - started
    assert len(result.trades) > 0
    assert elapsed < 20, f"{elapsed:.1f} s"


def test_std_is_population_and_builds_lean_bollinger_bands():
    values = [10.0, 12.0, 11.0, 15.0, 14.0, 16.0]
    bars, dates = _one(values)
    deviation = formula.evaluate("std(close, 3)", bars, dates)[:, 0]
    expected = pd.Series(values).rolling(3).std(ddof=0).to_numpy()
    assert np.allclose(deviation, expected, equal_nan=True)
    band = formula.evaluate("sma(close, 3) + 2 * std(close, 3)", bars, dates)[:, 0]
    assert np.allclose(band, pd.Series(values).rolling(3).mean().to_numpy() + 2 * expected, equal_nan=True)


def test_self_completion_offers_the_indicator_helpers():
    members = {item["name"]: item for item in pycode.editor_members("self", "class Strategy:\n    def on_bar(self, ctx):\n        pass\n", "sm")}
    assert members["sma"]["signature"] == "sma(symbol_or_period, period=None)"
    assert "ready" in members["sma"]["documentation"]


def test_python_on_risk_event_runs_once_and_stops_trading():
    from app.services.studio_v3.core import engine

    close = np.array([[100.0], [100.0], [96.0], [92.0], [90.0]])
    bars = {k: close for k in ("open", "high", "low", "close")} | {"volume": np.ones_like(close)}
    dates = pd.bdate_range("2021-01-04", periods=len(close))
    output = {}
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.position == 0:
            ctx.set_holdings(ctx.symbols[0], 1.0)

    def on_risk_event(self, ctx, event):
        ctx.log((event["kind"], event["date"], round(event["value"], 4)))
"""
    result = pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(max_daily_loss=0.03, commission_bps=0, slippage_bps=0), output=output)
    assert [row["text"] for row in output["logs"]] == [f"('daily_loss', '{dates[2].date()}', -0.04)"]
    assert result.risk_events and result.risk_events[0]["bar"] == 2
    assert np.allclose(result.equity[3:], 92_000)


def test_lint_flags_domain_and_determinism_problems():
    code = """import numpy as np

class Strategy:
    def __init__(self, tags=[]):
        self.tags = tags

    def on_data(self, ctx):
        if ctx.symbols:
            ctx.buy("SPY")
        print("checking")
        ctx.plot("noise", np.random.rand())
        ctx.log("at", ctx.history("close", 5))
"""
    codes = {problem["code"] for problem in pycode.lint(code, {})}
    assert {"hard-coded-symbol", "print-in-loop", "mutable-default", "unseeded-random"} <= codes
    seeded = code.replace("np.random.rand()", "np.random.default_rng(7).random()")
    assert "unseeded-random" not in {problem["code"] for problem in pycode.lint(seeded, {})}
    network = pycode.lint("class Strategy:\n    def on_bar(self, ctx):\n        ctx.value('close')\n        x = 'https://example.com/a.csv'\n", {})
    assert "network" in {problem["code"] for problem in network}


def test_ctx_log_levels_carry_key_values():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(2, 1)
    output = {}
    code = """class Strategy:
    def on_bar(self, ctx):
        ctx.log.info("entry", symbol="SPY", rsi=41.5)
        ctx.log.warning("thin", volume=1)
        ctx.log.error("bad", code="E1", retries=2)
        ctx.log("plain")
"""
    pycode.run_event(code, bars, dates, {}, ["SPY"], engine.Params(), output=output)
    rows = output["logs"][:4]
    assert [row["level"] for row in rows] == ["info", "warning", "error", "info"]
    assert rows[0]["fields"] == {"symbol": "SPY", "rsi": 41.5}
    assert rows[2]["fields"] == {"code": "E1", "retries": 2.0}
    assert "fields" not in rows[3] and rows[3]["text"] == "plain"
    assert len(output["logs"]) == 8  # the strategy runs the four lines on each of the two bars


def test_formula_named_variables_and_comments_expand_to_the_plain_formula():
    bars, dates = _bars(120, 2)
    text = "# trend\nfast = ema(close, 12)\nslow = sma(close, 50)  # base\nfast > slow"
    assert np.array_equal(formula.evaluate(text, bars, dates), formula.evaluate("ema(close, 12) > sma(close, 50)", bars, dates))
    with pytest.raises(Exception, match="(?i)look-ahead"):
        formula.parse("x = close\nx[1]")


def test_calendar_operators_and_between_read_only_the_bars_own_date():
    bars, dates = _bars(300, 2)
    friday = formula.evaluate("weekday() == 4", bars, dates)
    assert np.array_equal(friday[:, 0], dates.weekday == 4)
    assert np.array_equal(formula.evaluate("month() == 12", bars, dates)[:, 1], dates.month == 12)
    assert formula.evaluate("day_of_month() <= 3", bars, dates)[:, 0].tolist() == (dates.day <= 3).tolist()
    for name, freq in (("quarter_start", "Q"), ("year_start", "Y")):
        expected = np.r_[True, dates.to_period(freq)[1:] != dates.to_period(freq)[:-1]]
        assert np.array_equal(formula.evaluate(f"{name}()", bars, dates)[:, 0], expected)
    inside = formula.evaluate("between(rsi(close, 14), 30, 70)", bars, dates)
    rsi = formula.evaluate("rsi(close, 14)", bars, dates)
    assert np.array_equal(inside, (rsi >= 30) & (rsi <= 70))
    cut = formula.evaluate("weekday() == 4", {k: v[:100] for k, v in bars.items()}, dates[:100])
    assert np.array_equal(cut, friday[:100])


def test_target_weights_corridor_skips_small_drift_but_always_closes():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(8, 2)
    code = """class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 0:
            ctx.target_weights({"AAA": 0.25})
        elif ctx.bar_index in (2, 4):
            ctx.target_weights({"AAA": 0.25}, corridor=0.5)
        elif ctx.bar_index == 6:
            ctx.target_weights({"AAA": 0}, corridor=0.9)
"""
    result = pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params())
    assert len(result.trades) == 1 and result.positions[-1] == 0  # one entry held through two skipped rebalances, then closed
    assert result.trades[0, engine.T_EXIT_BAR] == 7
    with pytest.raises(pycode.CodeError, match="corridor"):
        pycode.run_event(code.replace("corridor=0.9", "corridor=-1"), bars, dates, {}, ["AAA", "BBB"], engine.Params())


def test_history_to_numpy_and_pandas_stay_causal():
    from app.services.studio_v3.core import engine

    bars, dates = _bars(30, 2)
    code = """import numpy as np


class Strategy:
    def on_data(self, ctx):
        if ctx.bar_index == 10:
            window = ctx.history("close", 5, "AAA")
            frame = ctx.history("close", 5, pandas=True)
            both = ctx.history(["open", "close"], 3, "BBB", pandas=True)
            ctx.log("%s|%s|%s|%s" % (np.asarray(window).tolist() == window.to_numpy().tolist(), frame.shape, list(both.columns), frame.index[-1].strftime("%Y-%m-%d")))
"""
    out = {}
    pycode.run_event(code, bars, dates, {}, ["AAA", "BBB"], engine.Params(), output=out)
    assert out["logs"][0]["text"] == f"True|(5, 2)|['open', 'close']|{dates[10].date()}"
    cut = {}
    pycode.run_event(code, {k: v[:11] for k, v in bars.items()}, dates[:11], {}, ["AAA", "BBB"], engine.Params(), output=cut)
    assert cut["logs"] == out["logs"]
