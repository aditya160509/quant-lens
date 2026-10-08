"""Future mutation guards for data, walk-forward, regimes and strategy decisions."""

import numpy as np
import pandas as pd
import pytest
from app.services.portfolio_v2.core.backtest import walk_forward
from app.services.portfolio_v2.core.regimes import causal_regimes
from app.services.portfolio_v2.core.strategies import (
    strategy_backtest,
    constrained_allocation,
)
from app.services.portfolio_v2.core.data_loader import returns_matrix, request_scope
from test_portfolio_v2_features import observed_data as _observed_data

observed_data = _observed_data


def test_walk_forward_future_prices_do_not_change_earlier_weights():
    dates = pd.bdate_range("2020-01-01", periods=160)
    r = pd.DataFrame(
        np.random.default_rng(13).normal(0, 0.01, (160, 3)),
        index=dates,
        columns=list("ABC"),
    )
    params = {
        "walk_forward_window": 60,
        "rebalance_days": 20,
        "transaction_cost_bps": 10,
    }
    first, weights, _ = walk_forward(r, params)
    changed = r.copy()
    changed.iloc[120:] *= 3
    second, new_weights, _ = walk_forward(changed, params)
    assert [w for w in weights if w["date"] < dates[120]] == [
        w for w in new_weights if w["date"] < dates[120]
    ]
    pd.testing.assert_frame_equal(
        first.loc[first.date < dates[120]], second.loc[second.date < dates[120]]
    )
    assert all(w["training_end"] < w["date"] for w in weights)


def test_walk_forward_buy_hold_cost_only_when_trading():
    dates = pd.bdate_range("2020-01-01", periods=50)
    r = pd.DataFrame({"A": 0.01, "B": -0.005}, index=dates)
    rows, trades, _ = walk_forward(
        r,
        {
            "weights": {"A": 0.5, "B": 0.5},
            "walk_forward_window": 30,
            "rebalance_days": 100,
            "transaction_cost_bps": 100,
        },
    )
    assert rows.cost.iloc[0] > 0
    assert (rows.cost.iloc[1:] == 0).all()
    expected = (1 - 0.01 / (1 + 0.01)) * ((1 + 0.01) ** 20 + (1 - 0.005) ** 20) / 2
    assert rows.net.iloc[-1] == pytest.approx(expected)
    assert len({r["date"] for r in trades}) == 1


def test_missing_held_return_is_not_zero():
    dates = pd.bdate_range("2020-01-01", periods=60)
    r = pd.DataFrame(
        np.random.default_rng(2).normal(0, 0.01, (60, 2)),
        index=dates,
        columns=list("AB"),
    )
    r.iloc[40, 0] = np.nan
    with pytest.raises(ValueError, match="Missing observed return"):
        walk_forward(
            r,
            {
                "weights": {"A": 0.5, "B": 0.5},
                "walk_forward_window": 30,
                "rebalance_days": 100,
            },
        )


def test_as_of_cutoff_before_lookback(observed_data):
    returns, _ = observed_data
    date = returns.index[200]
    with request_scope({"as_of_date": str(date.date())}):
        result = returns_matrix(["SPY", "QQQ"], 100)
    assert result.index.max() == date
    assert len(result) == 100


def test_hmm_future_mutation_does_not_change_filtered_history():
    dates = pd.bdate_range("2020-01-01", periods=260)
    series = pd.Series(np.random.default_rng(12).normal(0.0002, 0.01, 260), index=dates)
    first, _ = causal_regimes(series, count=2, min_train=60, refit_interval=80)
    changed = series.copy()
    changed.iloc[220:] *= 4
    second, _ = causal_regimes(changed, count=2, min_train=60, refit_interval=80)
    pd.testing.assert_frame_equal(
        first.loc[first.date < dates[220]], second.loc[second.date < dates[220]]
    )
    assert (first.training_end < first.date).all()


def test_strategy_constraints_and_future_mutation():
    dates = pd.bdate_range("2020-01-01", periods=180)
    rng = np.random.default_rng(24)
    r = pd.DataFrame(
        rng.normal(0.0003, 0.01, (180, 3)), index=dates, columns=list("ABC")
    )
    r.B = r.A * 0.95 + r.B * 0.05
    payload = {
        "training_window": 60,
        "rebalance_days": 20,
        "correlation_constraint": 0.8,
        "vol_target": 0.08,
        "capacity_limits": {"A": 0.4, "B": 0.4, "C": 0.5},
        "risk_budgets": {"A": 0.3, "B": 0.3, "C": 0.4},
    }
    weights, detail = constrained_allocation(r.iloc[:60], payload)
    assert not (weights.A > 1e-6 and weights.B > 1e-6)
    assert detail["annual_vol"] <= 0.080001
    assert weights.A <= 0.400001 and weights.C <= 0.500001
    first, allocation, _ = strategy_backtest(r, payload)
    changed = r.copy()
    changed.iloc[140:] *= 3
    second, new_allocation, _ = strategy_backtest(changed, payload)
    assert [x for x in allocation if x["date"] < dates[140]] == [
        x for x in new_allocation if x["date"] < dates[140]
    ]
    pd.testing.assert_frame_equal(
        first.loc[first.date < dates[140]], second.loc[second.date < dates[140]]
    )


def test_monthly_rebalance_uses_calendar_boundary():
    r = pd.DataFrame(
        np.random.default_rng(77).normal(0, 0.01, (90, 2)),
        index=pd.bdate_range("2020-01-01", periods=90),
        columns=list("AB"),
    )
    _, trades, _ = walk_forward(
        r,
        {
            "weights": {"A": 0.5, "B": 0.5},
            "walk_forward_window": 30,
            "rebalance_frequency": "monthly",
        },
    )
    actual = sorted(set(t["date"] for t in trades))
    expected = [r.index[30]] + [
        r.index[t]
        for t in range(31, len(r))
        if r.index[t].month != r.index[t - 1].month
    ]
    assert actual == expected


def test_regime_strategy_rule_uses_only_training_prefix():
    r = pd.DataFrame(
        np.random.default_rng(99).normal(0.0003, 0.01, (180, 3)),
        index=pd.bdate_range("2020-01-01", periods=180),
        columns=list("ABC"),
    )
    payload = {
        "allocation_rule": "regime_conditional",
        "training_window": 126,
        "rebalance_days": 50,
    }
    first, _, audits = strategy_backtest(r, payload)
    changed = r.copy()
    changed.iloc[170:] *= 2
    second, _, _ = strategy_backtest(changed, payload)
    pd.testing.assert_frame_equal(
        first.loc[first.date < r.index[170]], second.loc[second.date < r.index[170]]
    )
    assert all(
        sum(row["next_regime_probabilities"]) == pytest.approx(1) for row in audits
    )
