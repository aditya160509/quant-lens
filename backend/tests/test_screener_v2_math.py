from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.screener_v2.core import estimators, formula, stats, screener, validation


def test_gap_uses_open_against_prior_close(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.date_range("2025-01-01", periods=300, freq="B")
    close = pd.DataFrame({"AAA": np.full(300, 100.0), "SPY": np.full(300, 100.0)}, index=dates)
    volume = pd.DataFrame({"AAA": np.full(300, 1_000.0), "SPY": np.full(300, 1_000.0)}, index=dates)
    rows = []
    for ticker in ["AAA", "SPY"]:
        for date in dates:
            rows.append({"Ticker": ticker, "Date": date, "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1_000.0})
    rows[299]["Open"] = 110.0
    monkeypatch.setattr(estimators, "ohlcv_for_symbols", lambda *_args, **_kwargs: pd.DataFrame(rows))
    monkeypatch.setattr(estimators, "close_matrix", lambda *_args, **_kwargs: close)
    monkeypatch.setattr(estimators, "volume_matrix", lambda *_args, **_kwargs: volume)
    result = estimators.latest_technical_features(["AAA"], 300).set_index("ticker")
    assert result.loc["AAA", "gap_1d"] == pytest.approx(0.10)


def test_formula_if_alias_and_division_guard() -> None:
    panel = pd.DataFrame({"ticker": ["A", "B"], "roa": [0.1, -0.1], "sector": ["X", "X"]})
    result = formula.evaluate_formula(panel, "if(roa > 0, 1, 0)")
    assert result.values.tolist() == [1.0, 0.0]
    with pytest.raises(formula.FormulaError, match="Division by zero"):
        formula.evaluate_formula(panel, "1/0")


def test_holding_frequency_changes_actual_trade_dates():
    from app.services.screener_v2.core.backtest import simulate
    dates = pd.bdate_range("2025-01-01", periods=12)
    prices = pd.DataFrame({"A": np.arange(100., 112.), "B": np.arange(100., 88., -1)}, index=dates)
    scores = lambda date: pd.Series({"A": 2 if date < dates[4] else 0, "B": 1})
    short = simulate(prices, scores, min_history=2, top_n=1, rebalance_days=3)
    long = simulate(prices, scores, min_history=2, top_n=1, rebalance_days=6)
    assert short['curve'].rebalance.sum() > long['curve'].rebalance.sum()
    assert short['trades'].execution_date.tolist() != long['trades'].execution_date.tolist()


def test_turnover_cost_and_walk_forward_reselection():
    from app.services.screener_v2.core.backtest import simulate
    dates = pd.date_range("2025-01-01", periods=10, freq="B")
    prices = pd.DataFrame({"A": np.full(10, 100.), "B": np.full(10, 100.)}, index=dates)
    calls = []
    def scores(date):
        calls.append(date)
        return pd.Series({"A": 2 if date < dates[5] else 0, "B": 1})
    result = simulate(prices, scores, top_n=1, min_history=2, rebalance_days=4, cost_bps=100)
    curve = result['curve']
    assert calls == [dates[1], dates[5]]
    assert result['trades'].execution_date.tolist() == [dates[2], dates[6], dates[6]]
    assert curve.turnover.iloc[0] == pytest.approx(1 / 1.01)
    assert curve.cost_fraction.iloc[0] == pytest.approx(.01 / 1.01)
    assert curve.turnover.iloc[4] == pytest.approx(2 / 1.01)
    assert curve.loc[~curve.rebalance, 'cost_fraction'].eq(0).all()


def test_static_score_backfill_is_rejected():
    with pytest.raises(ValueError, match='point-in-time score provider'):
        validation.score_backtest(['A'], pd.Series({'A': 1.}))


def test_cscv_partitions_and_rank():
    from app.services.screener_v2.core.backtest import cscv_pbo
    returns = pd.DataFrame({'good': np.tile([.01, .02, .03, .04], 4), 'bad': np.tile([-.04, -.03, -.02, -.01], 4)})
    result = cscv_pbo(returns, 4)
    assert result['split_count'] == 6
    assert result['pbo'] == 0
    assert all(row['winner'] == 'good' for row in result['splits'])


def test_execution_price_gaps_are_rejected():
    from app.services.screener_v2.core.backtest import simulate
    dates = pd.date_range('2025-01-01', periods=6, freq='B')
    prices = pd.DataFrame({'A': [100., 100., np.nan, 100., 100., 100.]}, index=dates)
    with pytest.raises(ValueError, match='Missing execution price'):
        simulate(prices, lambda date: pd.Series({'A': 1.}), min_history=2, top_n=1)


def test_missing_values_do_not_receive_normalized_scores():
    values = pd.Series([1., 2., np.nan])
    assert pd.isna(stats.rank_pct(values).iloc[2])
    assert pd.isna(stats.zscore(values).iloc[2])


def test_requested_unavailable_filter_is_rejected():
    panel = pd.DataFrame({'ticker': ['A'], 'price': [100.], 'forward_pe': [np.nan]})
    with pytest.raises(ValueError, match='unavailable'):
        screener.apply_filters(panel, {'forward_pe_max': 10})


def test_wilder_seed_includes_all_first_valid_observations():
    values = pd.Series([np.nan, 1., 2., 3., 4.])
    result = stats._wilder_smooth(values, 3)
    assert result.iloc[:3].isna().all()
    assert result.iloc[3] == pytest.approx(2.)
    assert result.iloc[4] == pytest.approx(8 / 3)


def test_piotroski_original_criteria_and_missing_inputs(monkeypatch):
    from app.services.screener_v2.core import academic
    history = pd.DataFrame({
        'reportDate': pd.to_datetime(['2021-12-31', '2022-12-31', '2023-12-31']),
        'periodType': ['annual'] * 3, 'Total Assets': [80., 100., 110.],
        'Net Income': [5., 10., 20.], 'Operating Cash Flow': [6., 15., 25.],
        'Long Term Debt': [30., 20., 10.], 'Current Portion Of Long Term Debt': [1., 1., 1.],
        'Current Assets': [20., 30., 40.], 'Current Liabilities': [10., 10., 10.],
        'Gross Profit': [20., 40., 70.], 'Total Revenue': [100., 120., 180.],
        'Issuance Of Capital Stock': [0., 0., 0.],
    })
    monkeypatch.setattr(academic, 'fundamental_history', lambda ticker: history)
    result = academic.piotroski_criteria_spec(pd.DataFrame({'ticker': ['A']}), ['A']).iloc[0]
    assert result.piotroski_f_score_spec == 9
    history.drop(columns='Current Portion Of Long Term Debt', inplace=True)
    missing = academic.piotroski_criteria_spec(pd.DataFrame({'ticker': ['A']}), ['A']).iloc[0]
    assert pd.isna(missing.piotroski_f_score_spec)
    assert 'f5_leverage_declining' in missing.piotroski_missing_criteria


def test_altman_golden_numbers_use_distinct_equity_measures():
    from app.services.screener_v2.core.academic import altman_z_score, altman_z_double_prime
    panel = pd.DataFrame({'working_capital_assets': [.2], 'retained_earnings_assets': [.3], 'ebit_assets': [.1], 'market_value_liabilities': [2.], 'book_value_liabilities': [.5], 'sales_assets': [1.5]})
    assert altman_z_score(panel).iloc[0] == pytest.approx(3.69)
    assert altman_z_double_prime(panel).iloc[0] == pytest.approx(3.487)


def test_attribution_reconciles_to_total_net_return_without_daily_stock_rows():
    from app.services.screener_v2.core.backtest import simulate
    dates = pd.date_range('2025-01-01', periods=10, freq='B')
    prices = pd.DataFrame({'A': np.arange(100., 110.), 'B': np.arange(100., 90., -1)}, index=dates)
    def scores(date):
        return pd.Series({'A': 2 if date < dates[5] else 0, 'B': 1})
    result = simulate(prices, scores, top_n=1, min_history=2, rebalance_days=4, cost_bps=10)
    assert len(result['attribution']) == 2
    assert result['attribution'].net_pnl_contribution.sum() == pytest.approx(result['curve'].strategy.iloc[-1] - 1)
    assert result['positions'].iloc[0].entry_date == dates[2]
    assert result['positions'].iloc[0].exit_date == dates[6]


def test_formula_unknown_input_is_not_zero_and_rank_is_unit_scaled():
    panel = pd.DataFrame({'ticker': ['A', 'B', 'C'], 'roa': [1., 2., np.nan], 'sector': ['X'] * 3})
    result = formula.evaluate_formula(panel, 'rank(roa)')
    assert result.values.iloc[:2].tolist() == [0., 1.]
    assert pd.isna(result.values.iloc[2])
    assert pd.isna(formula.evaluate_formula(panel, 'if(roa > 0, 1, 0)').values.iloc[2])


def test_historical_current_classification_filters_are_rejected():
    with pytest.raises(ValueError, match='dated classification'):
        validation.point_in_time_scorer(['AAA'], {'sector': 'Technology'})
    with pytest.raises(ValueError, match='dated sector'):
        validation.point_in_time_scorer(['AAA'], {'sector_neutral': True}, 'composite')


def test_macro_attribution_uses_only_prior_observations_and_expires(monkeypatch):
    import pandas as pd
    from app.services.screener_v2.core import macro
    frame = pd.DataFrame({'date': pd.to_datetime(['2025-01-01', '2025-01-02']), 'vixcls': [15., 40.]})
    monkeypatch.setattr(macro, 'load_macro', lambda: frame)
    returns = pd.Series([.1, -.2, .03], index=pd.to_datetime(['2025-01-02', '2025-01-03', '2025-01-20']))
    result = macro.macro_regime_attribution(returns).set_index('regime')
    assert result.loc['prior_VIX_below_20', 'sessions'] == 1
    assert result.loc['prior_VIX_below_20', 'compounded_return'] == pytest.approx(.1)
    assert result.loc['prior_VIX_at_least_20', 'compounded_return'] == pytest.approx(-.2)
    assert result.loc['unavailable', 'sessions'] == 1
