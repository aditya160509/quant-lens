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
    from app.services.screener_v2.core import data_loader, performance, fundamentals, estimators, panel, validation
    dates = pd.bdate_range('2023-01-02', periods=800)
    frames = []
    for index, ticker in enumerate(['AAA', 'BBB', 'CCC', 'SPY']):
        close = 100 + np.arange(len(dates)) * (.03 + index * .01) + 2 * np.sin(np.arange(len(dates)) / (7 + index))
        frames.append(pd.DataFrame({'Ticker': ticker, 'Date': dates, 'Open': close * .999, 'High': close * 1.01, 'Low': close * .99, 'Close': close, 'Volume': 100000. + index * 10000}))
    reports = []
    for index, ticker in enumerate(['AAA', 'BBB', 'CCC']):
        for year in [2021, 2022, 2023, 2024]:
            growth = year - 2020 + index
            reports.append({'ticker': ticker, 'reportDate': pd.Timestamp(f'{year}-12-31'), 'periodType': 'annual', 'sector': 'Technology', 'industry': 'Software',
                            'Total Assets': 1000. + growth * 100, 'Stockholders Equity': 600., 'Total Equity': 600., 'Total Revenue': 500. + growth * 100,
                            'Net Income': 50. + growth * 20, 'Gross Profit': 200. + growth * 50, 'EBIT': 100., 'EBITDA': 120., 'Operating Cash Flow': 140.,
                            'Free Cash Flow': 100., 'Cash And Cash Equivalents': 100., 'Current Assets': 400., 'Current Liabilities': 200., 'Total Debt': 200.,
                            'Long Term Debt': 180. - growth * 10, 'Current Portion Of Long Term Debt': 20., 'Ordinary Shares Number': 10., 'Net PPE': 500.,
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
    from app.services.screener_v2.registry import run_feature, get_feature
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
    from app.services.screener_v2.registry import run_feature
    from app.services.screener_v2.core.performance import clear_performance_caches
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
