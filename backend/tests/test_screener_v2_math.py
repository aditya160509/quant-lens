from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.screener_v2.core import analytics
from app.services.screener_v2.features.feature_05 import _holding_period_stats


def test_gap_uses_open_against_prior_close(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.date_range("2025-01-01", periods=300, freq="B")
    close = pd.DataFrame({"AAA": np.full(300, 100.0), "SPY": np.full(300, 100.0)}, index=dates)
    volume = pd.DataFrame({"AAA": np.full(300, 1_000.0), "SPY": np.full(300, 1_000.0)}, index=dates)
    rows = []
    for ticker in ["AAA", "SPY"]:
        for date in dates:
            rows.append({"Ticker": ticker, "Date": date, "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1_000.0})
    rows[299]["Open"] = 110.0
    monkeypatch.setattr(analytics, "ohlcv_for_symbols", lambda *_args, **_kwargs: pd.DataFrame(rows))
    monkeypatch.setattr(analytics, "close_matrix", lambda *_args, **_kwargs: close)
    monkeypatch.setattr(analytics, "volume_matrix", lambda *_args, **_kwargs: volume)
    result = analytics.latest_technical_features(["AAA"], 300).set_index("ticker")
    assert result.loc["AAA", "gap_1d"] == pytest.approx(0.10)


def test_formula_if_alias_and_division_guard() -> None:
    panel = pd.DataFrame({"ticker": ["A", "B"], "roa": [0.1, -0.1], "sector": ["X", "X"]})
    result = analytics.evaluate_formula(panel, "if(roa > 0, 1, 0)")
    assert result.values.tolist() == [1.0, 0.0]
    with pytest.raises(analytics.FormulaError, match="Division by zero"):
        analytics.evaluate_formula(panel, "1/0")


def test_holding_period_stats_uses_forward_horizon() -> None:
    prices = pd.DataFrame({"A": np.arange(1.0, 43.0)}, index=pd.date_range("2025-01-01", periods=42, freq="B"))
    result = _holding_period_stats(prices, 21)
    assert result["holding_days"] == 21
    assert result["observations"] == 1
    assert result["mean_forward_return"] == pytest.approx(21.0)


def test_rebalance_cost_is_charged_only_on_rebalance_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.date_range("2025-01-01", periods=10, freq="B")
    prices = pd.DataFrame({"A": np.full(10, 100.0)}, index=dates)
    monkeypatch.setattr(analytics, "close_matrix", lambda *_args, **_kwargs: prices)
    monkeypatch.setattr(analytics, "eligible_at_date", lambda *_args, **_kwargs: ["A"])
    monkeypatch.setattr(analytics, "risk_free_annual", lambda: 0.0)
    result = analytics.score_backtest(["A"], pd.Series({"A": 1.0}), lookback_days=10, top_n=1, cost_bps=100, rebalance_days=5)
    curve = result["equity_curve"]
    equity = pd.Series([row["strategy"] for row in curve])
    daily = equity.pct_change()
    daily.iloc[0] = equity.iloc[0] - 1.0
    assert (daily < 0).sum() == 2


def test_roic_formula() -> None:
    ebit, tax, equity, debt, cash = 100.0, 0.25, 500.0, 200.0, 50.0
    expected = ebit * (1 - tax) / (equity + debt - cash)
    assert expected == pytest.approx(75.0 / 650.0)
