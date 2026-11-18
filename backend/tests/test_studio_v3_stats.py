"""Backtest statistics ported from QuantConnect LEAN, each against a hand-computed value."""

import math

import numpy as np
import pandas as pd
import pytest

from app.services.shared import metrics as M

DATES = pd.bdate_range("2020-01-01", periods=6)
EQ = np.array([100.0, 110.0, 99.0, 99.0, 110.0, 121.0])  # returns +10%, -10%, 0, +11.11%, +10%


def test_var_cvar_historical_and_normal():
    x = M.extra_metrics(EQ, None, DATES)
    r = EQ[1:] / EQ[:-1] - 1
    assert x["var_95"] == pytest.approx(np.quantile(r, 0.05))
    assert x["var_95"] == pytest.approx(-0.08)  # between -0.1 and 0 at 20%
    assert x["cvar_95"] == pytest.approx(-0.1)
    assert x["var_99_normal"] == pytest.approx(r.mean() - 2.3263478740408408 * r.std(ddof=1))


def test_longest_recovery_days():
    assert M.extra_metrics(EQ, None, DATES)["longest_recovery_days"] == (DATES[4] - DATES[1]).days  # peak 110 (bar 1) recovered at bar 4


def test_jensen_treynor_and_no_benchmark():
    bm = EQ * 0 + np.linspace(100, 105, 6)
    x = M.extra_metrics(EQ, bm, DATES)
    n = 5
    cagr, bc = (1.21) ** (252 / n) - 1, 1.05 ** (252 / n) - 1
    b = bm[1:] / bm[:-1] - 1
    r = EQ[1:] / EQ[:-1] - 1
    beta = np.cov(r, b, ddof=1)[0, 1] / b.var(ddof=1)
    assert x["jensen_alpha"] == pytest.approx(cagr - beta * bc)
    assert x["treynor"] == pytest.approx(cagr / beta)
    assert "treynor" not in M.extra_metrics(EQ, None, DATES)


def test_degenerate_inputs():
    assert M.extra_metrics(np.array([]), None, None) == {}
    flat = M.extra_metrics(np.full(6, 100.0), None, DATES)
    assert flat["psr"] is None and flat["var_95_normal"] is None


def test_lean_trade_stats():
    # trades: +10 on 100, -5 on 110, +22 on 105, 0 -> wr .5? wins 2/4, losses 1/4
    s = M.lean_trade_stats(np.array([10.0, -5.0, 21.0, 0.0]), np.array([100.0, 110.0, 105.0, 126.0]))
    assert s["win_rate"] == 0.5 and s["avg_win"] == 15.5 and s["avg_loss"] == -5.0
    plr = ((0.1 + 0.2) / 2) / (5 / 110)
    assert s["profit_loss_ratio"] == pytest.approx(plr)
    assert s["expectancy"] == pytest.approx(0.5 * plr - 0.25)
    assert s["profit_factor"] == pytest.approx(31 / 5)
    assert M.lean_trade_stats(np.array([5.0]), np.array([100.0]))["expectancy"] is None
    assert M.lean_trade_stats(np.array([]), np.array([])) == {"count": 0}


def test_distribution():
    d = M.return_distribution(EQ, DATES, bins=2, top=2)
    assert sum(b["count"] for b in d["bins"]) == 5
    assert d["best"][0]["return"] == pytest.approx(1 / 9) and d["worst"][0]["return"] == pytest.approx(-0.1)
    assert d["mean"] == pytest.approx(np.mean(EQ[1:] / EQ[:-1] - 1))
    assert math.isfinite(d["bins"][0]["normal"])
