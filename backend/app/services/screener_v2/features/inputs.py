"""Shared, typed Screener V2 input declarations for the backend manifest."""


def field(key, type='text', default=None, group='Specification', help='', **constraints):
    if key in {'max_symbols', 'top_n', 'card_limit', 'strategy_perf_limit'}:
        constraints = {'min': 1, 'max': 5000, **constraints}
    if key == 'lookback_days':
        constraints = {'min': 1, 'max': 10000, **constraints}
    if key == 'transaction_cost_bps':
        constraints = {'min': 0, 'max': 999, **constraints}
    return {'key': key, 'label': key.replace('_', ' ').title(), 'type': type, 'default': default,
            'group': group, 'help': help or f'Configure {key.replace("_", " ")}.', **constraints}


def shared_inputs():
    return [field('instrument_metadata', 'json', None, 'Currency', 'Per ticker: quote_currency, financial_currency and quoted_units_per_ordinary_share. Explicit static declarations apply to the entire requested history; do not supply current-only metadata for changed listings.'),
            field('calendar_ticker', 'ticker', None, 'Currency', 'Observed session calendar instrument. Required for non-USD portfolios; missing held quotes invalidate a run.'),
            field('universe', 'ticker_list', 'master', 'Universe', 'Local equities with observed prices and a fundamentals inventory entry, or explicit eligible tickers; current coverage is not historical index membership.'),
            field('max_symbols', 'number', 5000, 'Universe', min=1, max=5000),
            field('lookback_days', 'number', 756, 'Window', min=1, max=10000),
            field('top_n', 'number', 50, 'Selection', min=1, max=5000),
            field('as_of_date', 'date', None, 'Window', 'Prices up to this date; reports become available 90 days after period end.'),
            field('focus_ticker', 'ticker', None, 'Selection'), field('universe_id', 'text', None, 'Universe'),
            field('screen_id', 'text', None, 'Persistence', 'Saved definition id for persisted runs and genuine membership differences.')]


RANGE_FILTERS = {
    'market_cap': 'Market capitalization', 'price': 'Observed close converted to USD using exact-date FX', 'dollar_volume': '20-session mean price times volume',
    'pe': 'Trailing twelve month P/E', 'roic': 'Statement-derived return on invested capital', 'pb': 'Price to book',
    'p_cf': 'Price to positive trailing cash flow', 'ev_ebit': 'Enterprise value to EBIT', 'interest_coverage': 'EBIT to interest expense',
    'revenue_growth_yoy': 'Annual revenue growth', 'eps_growth_yoy': 'Annual EPS change scaled by absolute prior EPS',
    'revenue_growth_3y_cagr': 'Revenue CAGR over three fiscal years', 'debt_ebitda': 'Debt to EBITDA', 'payout_ratio': 'Dividends to positive net income',
    'roe': 'Trailing return on equity', 'debt_equity': 'Debt to book equity', 'shares_outstanding': 'Reported ordinary shares',
    'atr_pct': 'ATR as share of observed close', 'adx': 'ADX', 'stochastic': 'Stochastic K', 'williams_r': 'Williams R',
    'ivol': '63-session FF3 residual volatility', 'max_factor': 'Maximum daily return over 21 sessions',
    'prox52': 'Price to 252-session high', 'high_proximity': 'Return from 252-session high', 'vratio': 'Current volume to mean trailing volume',
    'yang_zhang_vol': '63-session Yang-Zhang volatility scaled to 21 sessions; historical estimate, not a forecast',
    'amihud_percentile': 'Amihud liquidity percentile', 'score': 'Core quant score',
    'piotroski': 'Piotroski checks passed among those known', 'piotroski_known': 'Piotroski checks with data, 0 to 9', 'altman': 'Altman Z-score',
    'drawdown': 'Worst peak-to-trough fall over 252 sessions, negative',
    'bollinger_width_percentile': 'Trailing Bollinger width percentile', 'prox52_percentile': 'Cross-sectional proximity percentile',
    'ps': 'Price to sales',
    'ev_ebitda': 'Enterprise value to EBITDA',
    'earnings_yield': 'Earnings to market cap',
    'fcf_yield': 'Free cash flow to market cap',
    'gpa': 'Gross profit to assets',
    'gross_margin': 'Gross margin',
    'operating_margin': 'Operating margin',
    'net_margin': 'Net margin',
    'roa': 'Return on assets',
    'current_ratio': 'Current assets to current liabilities',
    'dividend_yield': 'Trailing dividend yield',
    'return_1d': 'One-session return',
    'return_1m': 'One-month return',
    'return_3m': 'Three-month return',
    'return_6m': 'Six-month return',
    'return_12m': 'Twelve-month return',
    'momentum': 'Twelve-month return skipping the last month',
    'dist_sma_50': 'Close relative to 50-session average',
    'dist_sma_200': 'Close relative to 200-session average',
    'rsi': '14-session RSI',
    'macd_histogram': 'MACD less signal',
    'bollinger_pct_b': 'Close position within the bands',
    'obv_slope': '20-session OBV slope',
    'realized_vol': '252-session realised volatility',
    'beta': '252-session beta',
    'sector_score_percentile': 'Score percentile within sector',
    'momentum_percentile': 'Universe momentum percentile',
    'quality_percentile': 'Universe quality percentile',
    'valuation_percentile': 'Universe valuation percentile',
}


def filter_inputs():
    result = [field(key, default='all', group='Filters') for key in ['sector', 'industry', 'industry_group', 'exchange']]
    for key, description in RANGE_FILTERS.items():
        for bound in ['min', 'max']:
            result.append(field(f'{key}_{bound}', 'number', None, 'Filters', description))
    for key, default in [('exclude_penny_stocks', True), ('exclude_negative_pe', False), ('dividend_paying_only', False), ('sma_bullish_only', False), ('macd_bullish_only', False), ('obv_positive_only', False)]:
        result.append(field(key, 'boolean', default, 'Filters'))
    result.append(field('periods', 'json', None, 'Indicators', 'Indicator periods; positive integer windows.'))
    return result


def enrich(inputs):
    return [field(**{**item, 'help': item.get('help', item.get('description', ''))}) for item in inputs]


def merge_inputs(*groups):
    fields = {}
    for group in groups:
        for item in group:
            fields[item['key']] = {**fields.get(item['key'], {}), **item}
    return list(fields.values())


def normalize_payload(inputs, payload):
    import json
    import math
    schema = {item['key']: item for item in inputs}
    result = {key: value for key, value in payload.items() if value is not None and value != ''}
    for key, value in list(result.items()):
        definition = schema.get(key)
        if not definition:
            continue
        kind = definition['type']
        if kind == 'json' and isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{key} requires valid JSON') from exc
        if kind == 'boolean':
            if isinstance(value, str) and value.lower() in {'true', 'false'}:
                value = value.lower() == 'true'
            if not isinstance(value, bool):
                raise ValueError(f'{key} requires a boolean')
        if kind == 'number':
            if isinstance(value, bool):
                raise ValueError(f'{key} requires a number, not a boolean')
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f'{key} must be finite')
            if 'min' in definition and value < definition['min'] or 'max' in definition and value > definition['max']:
                raise ValueError(f'{key} is outside its declared range')
            if key in {'max_symbols', 'lookback_days', 'top_n', 'strategy_perf_limit', 'rebalance_days', 'rank_shift', 'card_limit', 'min_training_periods'}:
                if value != int(value):
                    raise ValueError(f'{key} requires an integer')
                value = int(value)
        if definition.get('options') and value not in definition['options']:
            raise ValueError(f'Unsupported {key}: {value}')
        result[key] = value
    period_keys = {'rsi_period', 'stochastic_period', 'stochastic_d_period', 'adx_period', 'atr_period', 'bollinger_period', 'bollinger_std_multiple', 'macd_fast_period', 'macd_slow_period', 'macd_signal_period', 'cross_lookback_days'}
    direct_periods = {key: result.pop(key) for key in period_keys if key in result}
    if direct_periods:
        if 'periods' in result and not isinstance(result['periods'], dict):
            raise ValueError('periods requires a JSON object')
        result['periods'] = {**direct_periods, **result.get('periods', {})}
    if 'periods' in result:
        if not isinstance(result['periods'], dict):
            raise ValueError('periods requires a JSON object')
        allowed = {'rsi_period', 'stochastic_period', 'stochastic_d_period', 'adx_period', 'atr_period', 'bollinger_period', 'bollinger_std_multiple', 'macd_fast_period', 'macd_slow_period', 'macd_signal_period', 'cross_lookback_days'}
        for key, value in result.pop('periods').items():
            if key not in allowed:
                raise ValueError(f'Unknown indicator period: {key}')
            numeric = float(value)
            if not math.isfinite(numeric) or numeric < (0.1 if key == 'bollinger_std_multiple' else 2) or numeric > 1000:
                raise ValueError(f'Invalid indicator period: {key}')
            if key != 'bollinger_std_multiple' and numeric != int(numeric):
                raise ValueError(f'{key} requires an integer')
            result[key] = numeric if key == 'bollinger_std_multiple' else int(numeric)
    if result.get('macd_slow_period', 26) <= result.get('macd_fast_period', 12):
        raise ValueError('MACD slow period must exceed fast period')
    return result
