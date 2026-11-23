"""CH-32: studio.ta matches Pine's reference loops, the formula rules read the same numbers, and ready indicators plot what strategies read."""

import math

import numpy as np
import pandas as pd
import pytest

from app.services.studio_v3.core import formula as F
from app.services.studio_v3.core import ta
from tests.test_studio_v3_backtest import studio  # noqa: F401  (fixture)

rng = np.random.default_rng(7)
N = 400
close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, N)))
high = close * (1 + rng.uniform(0, 0.02, N))
low = close * (1 - rng.uniform(0, 0.02, N))
volume = rng.uniform(1e5, 1e6, N)


def pine_rma(x, n):  # pine_rma from the Pine v6 reference, one bar at a time
    out, s, seen = [], math.nan, []
    for v in x:
        if math.isnan(s):
            seen.append(v)
            s = sum(seen[-n:]) / n if len(seen) >= n else math.nan
        else:
            s = s + (v - s) / n
        out.append(s)
    return np.array(out)


def pine_sma(x, n):
    return np.array([sum(x[t - n + 1:t + 1]) / n if t >= n - 1 else math.nan for t in range(len(x))])


def pine_stdev(x, n):
    m = pine_sma(x, n)
    return np.array([math.sqrt(sum((x[t - i] - m[t]) ** 2 for i in range(n)) / n) if t >= n - 1 else math.nan for t in range(len(x))])


def pine_wma(x, n):
    return np.array([sum(x[t - i] * (n - i) * n for i in range(n)) / sum((n - i) * n for i in range(n)) if t >= n - 1 else math.nan for t in range(len(x))])


def same(a, b, tol=1e-9):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)], rtol=0, atol=tol)


def test_moving_averages_and_bands_match_pine_reference_loops():
    assert same(ta.rma(close, 14), pine_rma(close, 14))
    assert same(ta.sma(close, 20), pine_sma(close, 20))
    assert same(ta.wma(close, 15), pine_wma(close, 15))
    assert same(ta.stdev(close, 20), pine_stdev(close, 20))
    prev = np.r_[math.nan, close[:-1]]
    tr = np.array([h - lo if math.isnan(p) else max(h - lo, abs(h - p), abs(lo - p)) for h, lo, p in zip(high, low, prev, strict=True)])
    assert same(ta.atr(high, low, close, 14), pine_rma(tr, 14))
    u, d = np.maximum(np.diff(close, prepend=math.nan), 0), np.maximum(-np.diff(close, prepend=math.nan), 0)
    assert same(ta.rsi(close, 14)[1:], (100 - 100 / (1 + pine_rma(u[1:], 14) / pine_rma(d[1:], 14))))
    basis, upper, _ = ta.bb(close, 20, 2)
    assert same(upper - basis, 2 * pine_stdev(close, 20)) and same(basis, pine_sma(close, 20))
    hlc3 = (high + low + close) / 3
    dev = np.array([np.mean(np.abs(hlc3[t - 19:t + 1] - hlc3[t - 19:t + 1].mean())) if t >= 19 else math.nan for t in range(N)])
    assert same(ta.cci(hlc3, 20), (hlc3 - pine_sma(hlc3, 20)) / (0.015 * dev))


def test_supertrend_flips_with_price_and_sits_on_the_right_side():
    line, direction = ta.supertrend(high, low, close, 3, 10)
    ok = ~np.isnan(line)
    assert ok.sum() == N - 9 and set(np.unique(direction[ok])) == {-1.0, 1.0}
    assert (line[ok & (direction < 0)] <= high[ok & (direction < 0)]).all()  # uptrend: the line is under price
    p, m, adx = ta.dmi(high, low, close, 14, 14)
    assert np.nanmin(adx) >= 0 and np.nanmax(adx) <= 100 and np.isfinite(p[-1]) and np.isfinite(m[-1])
    s = ta.sar(high, low, close)
    assert np.isfinite(s[1:]).all()


def test_formula_rules_read_the_same_numbers_and_late_listers_warm_up():
    late = np.r_[[math.nan] * 50, close[50:]]
    bars = {"close": np.c_[close, late], "high": np.c_[high, np.r_[[math.nan] * 50, high[50:]]], "low": np.c_[low, np.r_[[math.nan] * 50, low[50:]]]}
    dates = pd.bdate_range("2020-01-01", periods=N)
    for rule, mine in (("ema(close, 20)", ta.ema), ("rsi(close, 14)", ta.rsi), ("sma(close, 20)", ta.sma)):
        got = F.evaluate(rule, bars, dates)
        assert same(got[:, 0], mine(close, int(rule.split(", ")[1][:-1]))), rule
        assert same(got[50:, 1], mine(close[50:], int(rule.split(", ")[1][:-1]))), rule  # a symbol listed later starts on its own first bar
    assert same(F.evaluate("atr(14)", bars, dates)[:, 0], ta.atr(high, low, close, 14))


def test_ready_indicators_plot_what_the_strategy_reads(studio):  # noqa: F811
    code = """from studio import ta

class Strategy:
    def init(self, ctx):
        self.st = self.use(ta.Supertrend, factor=2.5)
        self.rsi = self.use(ta.RSI)

    def on_bar(self, ctx):
        ctx.table("seen", {"rsi": self.rsi.value, "dir": self.st["direction"]})
"""
    result = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": {"code": code}}).json()
    assert result["status"] == "ok", (result.get("reason"), result.get("problem"))
    assert set(result["plot_charts"]) == {"Supertrend(2.5, 10).up", "Supertrend(2.5, 10).down", "RSI(14).rsi"}  # direction stays off the chart
    assert {h["name"] for h in result["draw"]["hlines"]} == {"RSI(14) overbought", "RSI(14) middle", "RSI(14) oversold"}
    plotted = {p["date"]: p["value"] for p in result["plots"]["RSI(14).rsi"]}
    rows = [r for r in result["tables"]["seen"] if r["cells"].get("rsi") is not None]
    assert rows and all(plotted[r["date"]] == pytest.approx(r["cells"]["rsi"]) for r in rows)
    assert {r["cells"].get("dir") for r in result["tables"]["seen"]} - {None} == {-1.0, 1.0}  # None while ATR warms up


def test_candlestick_patterns_fire_on_their_textbook_shapes():
    pad = [[10, 10.5, 9.5, 10.2]] * 10
    cases = {
        "bullish_engulfing": [[10.5, 10.6, 9.8, 9.9], [9.7, 10.9, 9.6, 10.8]],
        "hammer": [[10.1, 10.16, 9.0, 10.15]],
        "morning_star": [[11, 11.1, 9.0, 9.1], [8.9, 8.95, 8.7, 8.92], [9.0, 10.6, 8.95, 10.5]],
        "three_black_crows": [[10.5, 10.55, 9.9, 10.0], [10.2, 10.25, 9.6, 9.7], [9.9, 9.95, 9.3, 9.4]],
        "rising_window": [[10.6, 11, 10.55, 10.9]],
    }
    for name, rows in cases.items():
        o, h, lo, c = np.array(pad + rows, dtype=float).T
        found = ta.candles(o, h, lo, c)
        assert set(found) == set(ta.PATTERN_SIDES) and found[name][-1], name
        assert not any(v[:10].any() for k, v in found.items() if k not in ("doji", "spinning_top", "marubozu")), name  # the flat padding fires nothing directional


def test_patterns_and_relative_strength_run_in_a_strategy(studio):  # noqa: F811
    code = """from studio import ta

class Strategy:
    def init(self, ctx):
        self.patterns = self.use(ta.Patterns)
        self.rs = self.use(ta.RelativeStrength)

    def on_bar(self, ctx):
        ctx.table("seen", {"bull": self.patterns["bullish"], "beta": self.rs["beta"]})
"""
    result = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": {"code": code}}).json()
    assert result["status"] == "ok", (result.get("reason"), result.get("problem"))
    assert {"Patterns.bull", "Patterns.bear", "RelativeStrength(63).rs", "RelativeStrength(63).rs_ma"} == set(result["plot_charts"])
    rows = result["tables"]["seen"]
    assert any(r["cells"].get("bull") for r in rows)
    betas = [r["cells"]["beta"] for r in rows if r["cells"].get("beta") is not None]
    assert betas and all(abs(b - 1) < 1e-6 for b in betas)  # SPY against SPY
