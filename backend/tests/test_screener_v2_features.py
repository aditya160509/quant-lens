"""Acceptance tests for persistent feature state and deterministic exports."""
import pytest

from app.services.screener_v2.core import state


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state, 'STATE_PATH', tmp_path / 'screens.sqlite3')
    return state


def test_first_screen_is_baseline_and_later_membership_is_real(store):
    assert store.compare_and_store('screen', [{'ticker': 'A'}], '2025-01-01') == []
    events = store.compare_and_store('screen', [{'ticker': 'B'}], '2025-01-02')
    assert {(e['ticker'], e['event']) for e in events} == {('A', 'exited'), ('B', 'entered')}
    assert store.compare_and_store('screen', [{'ticker': 'B'}], '2025-01-02') == events
    with pytest.raises(ValueError, match='earlier'):
        store.compare_and_store('screen', [{'ticker': 'A'}], '2024-01-01')


def test_saved_definitions_are_immutable_and_runs_persist(store):
    store.save_screen('x', 'Quality', '01', {'roic_min': .1})
    assert store.get_screen('x')['payload'] == {'roic_min': .1}
    with pytest.raises(ValueError, match='immutable'):
        store.save_screen('x', 'Quality', '01', {'roic_min': .2})
    store.save_run('x', '2025-01-01', {'status': 'ok'})
    assert store.run_history('x')[0]['result'] == {'status': 'ok'}


def test_saved_universe_membership_is_exact(store):
    store.save_universe('u', 'My universe', ['A', 'B'])
    assert store.get_universe('u') == ['A', 'B']
    assert store.list_universes()[0]['count'] == 2
    with pytest.raises(ValueError, match='immutable'):
        store.save_universe('u', 'My universe', ['A'])


@pytest.fixture
def local_data(tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd

    from app.services.screener_v2.core import (
        data_loader,
        estimators,
        fundamentals,
        panel,
        performance,
        validation,
    )
    dates = pd.bdate_range('2023-01-02', periods=800)
    frames = []
    for index, ticker in enumerate(['AAA', 'BBB', 'CCC', 'SPY']):
        close = 100 + np.arange(len(dates)) * (.03 + index * .01) + 2 * np.sin(np.arange(len(dates)) / (7 + index))
        frames.append(pd.DataFrame({'Ticker': ticker, 'Date': dates, 'Open': close * .999, 'High': close * 1.01, 'Low': close * .99, 'Close': close, 'Volume': 100000. + index * 10000}))
    reports = []
    for index, ticker in enumerate(['AAA', 'BBB', 'CCC']):
        for year in [2021, 2022, 2023, 2024]:
            growth = year - 2020 + index
            reports.append({'ticker': ticker, 'reportDate': pd.Timestamp(f'{year}-12-31'), 'periodType': 'annual', 'currency': 'USD', 'quoteCurrency': 'USD', 'financialCurrency': 'USD', 'quoted_units_per_ordinary_share': 1., 'sector': 'Technology', 'industry': 'Software',
                            'Total Assets': 1000. + growth * 100, 'Stockholders Equity': 600., 'Total Equity': 600., 'Total Revenue': 500. + growth * 100,
                            'Net Income': 50. + growth * 20, 'Gross Profit': 200. + growth * 50, 'EBIT': 100., 'EBITDA': 120., 'Operating Cash Flow': 140.,
                            'Free Cash Flow': 100., 'Cash And Cash Equivalents': 100., 'Current Assets': 400., 'Current Liabilities': 200., 'Total Debt': 200.,
                            'Preferred Stock Equity': 0., 'Minority Interest': 0., 'Long Term Debt': 180. - growth * 10, 'Current Portion Of Long Term Debt': 20., 'Ordinary Shares Number': 10., 'Net PPE': 500.,
                            'Retained Earnings': 300., 'Total Liabilities Net Minority Interest': 600., 'Tax Provision': 25., 'Pretax Income': 100.,
                            'Interest Expense': 10., 'Inventory': 50., 'Cash Dividends Paid': -20., 'Repurchase Of Capital Stock': -10., 'Issuance Of Capital Stock': 0.})
    source = {'market': pd.concat(frames, ignore_index=True), 'fund': pd.DataFrame(reports)}
    monkeypatch.setattr(data_loader, 'load_market_ohlcv', lambda: source['market'])
    monkeypatch.setattr(data_loader, 'available_symbols', lambda: ('AAA', 'BBB', 'CCC', 'SPY'))
    monkeypatch.setattr(data_loader, 'load_fundamentals', lambda: source['fund'])
    monkeypatch.setattr(fundamentals, 'load_fundamentals', lambda: source['fund'])
    factors = pd.DataFrame({'date': dates, 'mkt_rf': np.sin(np.arange(800) / 9) * .01, 'smb': np.cos(np.arange(800) / 13) * .005, 'hml': np.sin(np.arange(800) / 17) * .005, 'rf': .0001})
    for module in [data_loader, estimators, panel, validation]:
        monkeypatch.setattr(module, 'load_factor_returns', lambda: factors)
    monkeypatch.setattr(state, 'STATE_PATH', tmp_path / 'screens.sqlite3')
    performance.clear_performance_caches()
    yield source
    performance.clear_performance_caches()


@pytest.mark.parametrize('feature_id', ['01', '02', '03', '04', '05', '06', '07', '08'])
def test_all_feature_outputs_are_json_safe_and_declared(local_data, feature_id):
    import json

    from app.services.screener_v2.registry import get_feature, run_feature
    result = run_feature(feature_id, {'tickers': ['AAA', 'BBB', 'CCC'], 'watchlist': 'AAA BBB CCC', 'lookback_days': 60, 'top_n': 1})
    assert result['status'] == 'ok'
    json.dumps(result, allow_nan=False)
    for output in get_feature(feature_id).outputs:
        if isinstance(output, dict):
            assert output['key'] in result[output['source']]
        else:
            assert output in result['charts'] or output in result['tables']


def test_future_price_and_statement_changes_do_not_change_historical_screen(local_data):
    import pandas as pd

    from app.services.screener_v2.core.performance import clear_performance_caches
    from app.services.screener_v2.registry import run_feature
    cutoff = local_data['market'].Date.sort_values().unique()[-80]
    payload = {'tickers': ['AAA', 'BBB', 'CCC'], 'as_of_date': str(pd.Timestamp(cutoff).date()), 'top_n': 3}
    before = run_feature('01', payload)
    local_data['market'].loc[local_data['market'].Date > cutoff, ['Open', 'High', 'Low', 'Close']] *= 10
    future = local_data['fund'].iloc[-1:].copy()
    future['reportDate'] = pd.Timestamp(cutoff) + pd.Timedelta(days=1)
    future['Net Income'] = 1000000.
    local_data['fund'] = pd.concat([local_data['fund'], future], ignore_index=True)
    clear_performance_caches()
    after = run_feature('01', payload)
    assert before['tables']['ranked_screener_table'] == after['tables']['ranked_screener_table']


def test_export_is_lossless_quoted_and_honors_columns():
    import csv
    import io

    from app.services.screener_v2.core.exports import build_export_payload
    rows = [{'ticker': f'T{i}', 'company': 'Quoted\tcompany\nname', 'score': None} for i in range(1001)]
    result = build_export_payload('08', {'export_format': 'json', 'columns': ['ticker', 'company', 'score']}, rows)
    assert len(result['json_payload']['rows']) == 1001
    assert result['json_payload']['rows'][0]['score'] is None
    parsed = list(csv.DictReader(io.StringIO(result['tsv']), delimiter='\t'))
    assert parsed[0]['company'] == rows[0]['company']
    assert result['ticker_list'].splitlines()[-1] == 'T1000'
    assert result['json_payload']['limits']
    download = build_export_payload('08', {}, rows)['content']
    assert download.startswith('# Fundamentals start in 2021')
    with pytest.raises(ValueError, match='Unknown export columns'):
        build_export_payload('08', {'columns': ['fake']}, rows)


def test_historical_training_labels_never_pass_the_training_date(local_data):
    import pandas as pd

    from app.services.screener_v2.core.composite import historical_weights
    from app.services.screener_v2.core.data_loader import as_of_context
    from app.services.screener_v2.core.panel import metric_panel
    cutoff = local_data['market'].Date.max()
    with as_of_context(cutoff):
        current = metric_panel({'as_of_date': str(cutoff.date())}, ['AAA', 'BBB', 'CCC'])
        rows = [{'field': 'momentum_jt'}, {'field': 'realized_vol_63d'}]
        weights, details = historical_weights(current, rows, {'weighting_mode': 'ridge', 'ic_target_field': 'return_1m'})
    assert pd.Timestamp(details['last_label_end']) <= cutoff
    assert weights.abs().sum() == pytest.approx(1)
    assert details['formation_count'] >= 6


def test_schedules_claim_once_and_publish_dispatch_state(store):
    from app.services.screener_v2.core.scheduler import ScreenScheduler
    store.save_screen('daily', 'Daily', '01', {'tickers': 'A'})
    store.set_schedule('daily', 60, now=1000)
    calls = []
    scheduler = ScreenScheduler(lambda feature, payload, key: calls.append((feature, payload, key)) or {'job_id': 'real-job-id'})
    scheduler.tick(now=1060)
    scheduler.tick(now=1060)
    assert len(calls) == 1
    assert store.list_schedules()[0]['last_job_id'] == 'real-job-id'
    assert store.list_schedules()[0]['next_due'] == 1120


def test_alert_precision_uses_persisted_matured_observations(store, monkeypatch):
    import pandas as pd

    from app.services.screener_v2.core import alerts
    dates = pd.bdate_range('2025-01-01', periods=4)
    prices = pd.DataFrame({'A': [100., 110., 121., 133.1]}, index=dates)
    monkeypatch.setattr(alerts, 'close_matrix', lambda *_args: prices)
    event = {'ticker': 'A', 'type': 'SCORE_THRESHOLD', 'direction': 1}
    store.store_alerts('screen', str(dates[0].date()), [event])
    store.store_alerts('screen', str(dates[-1].date()), [event])
    result = alerts.realized_alert_precision('screen', (1,))[0]
    assert result['matured_count'] == 1
    assert result['pending_count'] == 1
    assert result['realized_precision'] == 1.


@pytest.mark.parametrize('feature_id', ['02', '03', '04'])
def test_current_filters_do_not_shrink_historical_universe(local_data, monkeypatch, feature_id):
    from importlib import import_module

    from app.services.screener_v2.registry import run_feature
    module = import_module(f'app.services.screener_v2.features.feature_{feature_id}')
    original = module.score_backtest
    universes = []
    def observe(symbols, *args, **kwargs):
        universes.append(symbols)
        return original(symbols, *args, **kwargs)
    monkeypatch.setattr(module, 'score_backtest', observe)
    run_feature(feature_id, {'tickers': ['AAA', 'BBB', 'CCC'], 'price_min': 130, 'lookback_days': 60, 'top_n': 1, 'strategy_perf_limit': 1})
    assert universes[0] == ['AAA', 'BBB', 'CCC']


def test_future_as_of_dates_are_rejected(local_data):
    from app.services.screener_v2.registry import run_feature
    with pytest.raises(ValueError, match='latest observed'):
        run_feature('01', {'tickers': ['AAA'], 'as_of_date': '2099-01-01'})


def test_statement_valuation_and_roic_match_independent_numbers(local_data):
    from app.services.screener_v2.core.data_loader import as_of_context
    from app.services.screener_v2.core.fundamentals import latest_fundamental_features
    cutoff = local_data['market'].Date.max()
    price = local_data['market'].query("Ticker == 'AAA'").Close.iloc[-1]
    with as_of_context(cutoff):
        row = latest_fundamental_features(['AAA'], cutoff).iloc[0]
    assert row.market_cap == pytest.approx(price * 10)
    assert row.enterprise_value == pytest.approx(price * 10 + 200 - 100)
    assert row.roic == pytest.approx(100 * (1 - .25) / (600 + 200 - 100))
    assert row.trailing_pe == pytest.approx(price * 10 / 130)
    assert row.revenue_growth_yoy == pytest.approx(900 / 800 - 1)


def test_missing_claims_are_not_assumed_to_be_zero(local_data):
    import pandas as pd

    from app.services.screener_v2.core.data_loader import as_of_context
    from app.services.screener_v2.core.fundamentals import latest_fundamental_features
    local_data['fund']['Preferred Stock Equity'] = float('nan')
    with as_of_context(local_data['market'].Date.max()):
        row = latest_fundamental_features(['AAA']).iloc[0]
    assert pd.isna(row.enterprise_value)
    assert pd.isna(row.ev_ebitda)


def test_owned_job_route_runs_feature_and_publishes_real_result(local_data, monkeypatch, tmp_path):
    import time

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import screener_v2
    from app.services.studio.jobs import JobStore
    monkeypatch.setattr(screener_v2, 'JOBS', JobStore(path=tmp_path / 'jobs.json'))
    monkeypatch.setattr(screener_v2, 'RESULTS_DIR', tmp_path / 'results')
    app = FastAPI()
    app.include_router(screener_v2.router, prefix='/api')
    client = TestClient(app)
    submitted = client.post('/api/screener-v2/feature/01/jobs', json={'payload': {'tickers': ['AAA', 'BBB', 'CCC'], 'top_n': 2}})
    assert submitted.status_code == 200
    job_id = submitted.json()['job_id']
    for _ in range(200):
        status = client.get(f'/api/screener-v2/jobs/{job_id}')
        assert status.status_code == 200
        if status.json()['status'] in {'completed', 'failed'}:
            break
        time.sleep(.01)
    assert status.json()['status'] == 'completed', status.json()
    rows = status.json()['result']['tables']['ranked_screener_table']
    assert len(rows) == 2
    assert {row['ticker'] for row in rows} <= {'AAA', 'BBB', 'CCC'}


def test_zero_variance_pbo_is_disclosed_without_fabricating_a_probability(local_data):
    from app.services.screener_v2.registry import run_feature
    local_data['market'][['Open', 'High', 'Low', 'Close']] = 100.
    result = run_feature('05', {'tickers': ['AAA', 'BBB', 'CCC'], 'lookback_days': 60, 'top_n': 1, 'transaction_cost_bps': 0, 'run_full_pbo': True, 'pbo_partitions': 4, 'run_holding_sensitivity': False})
    assert result['tables']['cscv_pbo'] == []
    assert 'zero return variance' in result['meta']['pbo_status']


def test_valuation_cards_contain_four_real_dimensions_and_honor_window(local_data):
    from app.services.screener_v2.registry import run_feature
    result = run_feature('07', {'tickers': ['AAA', 'BBB', 'CCC'], 'history_window': 252, 'card_limit': 3})
    assert result['meta']['requested_history_sessions'] == 252
    assert result['meta']['observed_history_rows'] <= 252
    cards = result['charts']['universe_wide_four_dimension_cards']
    assert len(cards) == 3
    for card in cards:
        assert {'absolute_valuation', 'sector_percentile', 'universe_percentile', 'own_history_percentile'} <= card.keys()
        assert card['own_history_observations'] <= 252


def test_nonstock_weekends_do_not_change_the_us_backtest_calendar(local_data):
    import pandas as pd

    from app.services.screener_v2.core.performance import clear_performance_caches
    from app.services.screener_v2.core.validation import score_backtest
    dates = pd.date_range(local_data['market'].Date.min(), local_data['market'].Date.max())
    coin = pd.DataFrame({'Ticker': 'COIN_TEST', 'Date': dates, 'Open': 100., 'High': 101., 'Low': 99., 'Close': 100., 'Volume': 1000.})
    local_data['market'] = pd.concat([local_data['market'], coin], ignore_index=True)
    clear_performance_caches()
    from app.services.screener_v2.core.currency import instrument_context
    with instrument_context({'instrument_metadata': {'COIN_TEST': {'quote_currency': 'USD'}}}):
        result = score_backtest(['AAA', 'COIN_TEST'], pd.Series({'AAA': 1.}), lookback_days=60, top_n=1, score_at=lambda date: pd.Series({'AAA': 1.}))
    assert len(result['daily_returns']) == 60
    assert all(date.weekday() < 5 for date in result['daily_returns'].index)


def test_fx_valuation_uses_quote_units_and_reporting_currency(local_data, monkeypatch):
    import pandas as pd

    from app.services.screener_v2.core import data_loader
    from app.services.screener_v2.core.currency import instrument_context
    from app.services.screener_v2.core.fundamentals import latest_fundamental_features
    from app.services.screener_v2.core.valuation import historical_valuation_series
    dates = local_data['market'].query("Ticker == 'AAA'").Date
    monkeypatch.setattr(data_loader, 'load_fx', lambda: pd.DataFrame({'Ticker': 'EURUSD=X', 'Date': dates, 'Close': 3.}))
    payload = {'instrument_metadata': {'AAA': {'quote_currency': 'EUR', 'financial_currency': 'USD', 'quoted_units_per_ordinary_share': .5}}, 'calendar_ticker': 'AAA'}
    date = dates.max()
    price = local_data['market'].query("Ticker == 'AAA'").Close.iloc[-1]
    with data_loader.as_of_context(date), instrument_context(payload):
        row = latest_fundamental_features(['AAA']).iloc[0]
        history = historical_valuation_series('AAA', lookback=252)
    assert row.market_cap == pytest.approx(price * 10 * .5 * 3)
    assert row.enterprise_value == pytest.approx(row.market_cap + 200 - 100)
    assert row.trailing_pe == pytest.approx(row.market_cap / 130)
    assert history[-1]['valuation_metric'] == pytest.approx(row.trailing_pe)


def test_unknown_share_and_currency_metadata_does_not_manufacture_valuation(local_data):
    import pandas as pd

    from app.services.screener_v2.core import data_loader
    from app.services.screener_v2.core.fundamentals import latest_fundamental_features
    local_data['fund'] = local_data['fund'].drop(columns=['financialCurrency', 'quoted_units_per_ordinary_share', 'currency', 'quoteCurrency'])
    with data_loader.as_of_context(local_data['market'].Date.max()):
        row = latest_fundamental_features(['AAA']).iloc[0]
    assert pd.isna(row.market_cap)
    assert pd.isna(row.trailing_pe)
    assert row.roic == pytest.approx(100 * .75 / 700)
    assert row.currency_units_unavailable_reason is not None


def test_foreign_portfolio_returns_include_observed_fx_and_reject_missing_marks(local_data, monkeypatch):
    import numpy as np
    import pandas as pd

    from app.services.screener_v2.core import data_loader
    from app.services.screener_v2.core.currency import instrument_context
    from app.services.screener_v2.core.validation import score_backtest
    stock = local_data['market'].query("Ticker == 'AAA'").reset_index(drop=True)
    fx = pd.DataFrame({'Ticker': 'EURUSD=X', 'Date': stock.Date, 'Close': 1 + np.arange(len(stock)) / 1000})
    monkeypatch.setattr(data_loader, 'load_fx', lambda: fx)
    payload = {'instrument_metadata': {'AAA': {'quote_currency': 'EUR'}}, 'calendar_ticker': 'AAA'}
    with instrument_context(payload):
        result = score_backtest(['AAA'], pd.Series({'AAA': 1.}), lookback_days=60, top_n=1, cost_bps=0, score_at=lambda date: pd.Series({'AAA': 1.}))
        usd = pd.Series(stock.Close.to_numpy() * fx.Close.to_numpy(), index=stock.Date)
        # Initial decision executes on the second simulation session; thereafter the position is held.
        returns = result['daily_returns']
        assert returns.iloc[2:].to_numpy() == pytest.approx(usd.pct_change().reindex(returns.index).iloc[2:].to_numpy())
        assert result['stats']['portfolio_currency'] == 'USD'
        fx = fx.iloc[:-1]
        with pytest.raises(ValueError, match='exact-date FX'):
            score_backtest(['AAA'], pd.Series({'AAA': 1.}), lookback_days=60, top_n=1, score_at=lambda date: pd.Series({'AAA': 1.}))


def test_future_currency_metadata_cannot_change_past_valuation(local_data):
    import pandas as pd

    from app.services.screener_v2.core import data_loader
    from app.services.screener_v2.core.currency import instrument_context
    from app.services.screener_v2.core.fundamentals import latest_fundamental_features
    cutoff = pd.Timestamp('2024-08-01')
    with data_loader.as_of_context(cutoff), instrument_context({}):
        before = latest_fundamental_features(['AAA']).iloc[0]
    future = local_data['fund'].query("ticker == 'AAA'").tail(1).copy()
    future['reportDate'] = pd.Timestamp('2026-01-01')
    future['quoteCurrency'] = 'EUR'
    future['quoted_units_per_ordinary_share'] = .125
    local_data['fund'] = pd.concat([local_data['fund'], future], ignore_index=True)
    with data_loader.as_of_context(cutoff), instrument_context({}):
        after = latest_fundamental_features(['AAA']).iloc[0]
    assert after.market_cap == pytest.approx(before.market_cap)
    assert after.trailing_pe == pytest.approx(before.trailing_pe)


def test_default_date_uses_observed_calendar_not_newer_unrelated_asset(local_data):
    import pandas as pd

    from app.services.screener_v2.core.performance import clear_performance_caches
    from app.services.screener_v2.registry import run_feature
    calendar_date = local_data['market'].Date.max()
    unrelated = local_data['market'].tail(1).copy()
    unrelated['Ticker'] = 'UNRELATED'
    unrelated['Date'] = calendar_date + pd.Timedelta(days=20)
    local_data['market'] = pd.concat([local_data['market'], unrelated], ignore_index=True)
    clear_performance_caches()
    result = run_feature('01', {'tickers': ['AAA']})
    assert result['meta']['as_of_date'] == str(calendar_date.date())


def test_dollar_volume_and_beta_use_usd_rather_than_native_currency(local_data, monkeypatch):
    import numpy as np
    import pandas as pd

    from app.services.screener_v2.core import data_loader
    from app.services.screener_v2.core.currency import instrument_context
    from app.services.screener_v2.core.estimators import latest_technical_features
    stock = local_data['market'].query("Ticker == 'AAA'").reset_index(drop=True)
    fx = pd.DataFrame({'Ticker': 'EURUSD=X', 'Date': stock.Date, 'Close': 2 + .1 * np.sin(np.arange(len(stock)) / 12)})
    monkeypatch.setattr(data_loader, 'load_fx', lambda: fx)
    with instrument_context({'instrument_metadata': {'AAA': {'quote_currency': 'EUR'}}}):
        row = latest_technical_features(['AAA']).iloc[0]
    usd_prices = pd.Series(stock.Close.to_numpy() * fx.Close.to_numpy(), index=stock.Date)
    spy = local_data['market'].query("Ticker == 'SPY'").set_index('Date').Close.pct_change().tail(252)
    usd_return = usd_prices.pct_change().tail(252)
    assert row.dollar_volume_20d == pytest.approx((stock.Close * fx.Close * stock.Volume).tail(20).mean())
    assert row.beta_252 == pytest.approx(usd_return.cov(spy) / spy.var())


def test_explicit_foreign_calendar_controls_indicators_and_execution_sessions(local_data):
    import pandas as pd

    from app.services.screener_v2.core.currency import instrument_context
    from app.services.screener_v2.core.estimators import latest_technical_features
    from app.services.screener_v2.core.performance import clear_performance_caches
    from app.services.screener_v2.core.validation import score_backtest
    stock_mask = local_data['market'].Ticker.eq('AAA')
    friday = stock_mask & local_data['market'].Date.dt.weekday.eq(4)
    local_data['market'].loc[friday, 'Date'] += pd.Timedelta(days=2)
    clear_performance_caches()
    stock = local_data['market'].loc[stock_mask].sort_values('Date')
    with instrument_context({'calendar_ticker': 'AAA'}):
        technical = latest_technical_features(['AAA']).iloc[0]
        result = score_backtest(['AAA'], pd.Series({'AAA': 1.}), lookback_days=60, top_n=1, cost_bps=0, score_at=lambda date: pd.Series({'AAA': 1.}))
    assert technical.sma_20 == pytest.approx(stock.Close.tail(20).mean())
    assert technical.return_1m == pytest.approx(stock.Close.iloc[-1] / stock.Close.iloc[-22] - 1)
    assert len(result['daily_returns']) == 60
    assert any(date.weekday() == 6 for date in result['daily_returns'].index)
    assert not any(date.weekday() == 4 for date in result['daily_returns'].index)


def test_issued_shares_are_not_a_proxy_for_outstanding_ordinary_shares(local_data):
    import pandas as pd

    from app.services.screener_v2.core.data_loader import as_of_context
    from app.services.screener_v2.core.fundamentals import latest_fundamental_features
    local_data['fund']['Share Issued'] = 1000.
    local_data['fund']['Ordinary Shares Number'] = float('nan')
    with as_of_context(local_data['market'].Date.max()):
        row = latest_fundamental_features(['AAA']).iloc[0]
    assert pd.isna(row.market_cap)
    assert pd.isna(row.trailing_pe)
