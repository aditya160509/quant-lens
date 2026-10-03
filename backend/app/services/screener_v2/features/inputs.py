"""Shared, typed Screener V2 input declarations for the backend manifest."""


def field(key, type='text', default=None, group='Specification', help='', **constraints):
    return {'key': key, 'label': key.replace('_', ' ').title(), 'type': type, 'default': default,
            'group': group, 'help': help or f'Configure {key.replace("_", " ")}.', **constraints}


def shared_inputs():
    return [field('universe', 'ticker_list', 'master', 'Universe', 'Master local universe or explicit tickers; not historical index membership.'),
            field('max_symbols', 'number', 500, 'Universe', min=1, max=5000),
            field('lookback_days', 'number', 756, 'Window', min=1, max=10000),
            field('top_n', 'number', 50, 'Selection', min=1, max=5000),
            field('as_of_date', 'date', None, 'Window', 'Prices up to this date; reports become available 90 days after period end.'),
            field('focus_ticker', 'ticker', None, 'Selection'), field('universe_id', 'text', None, 'Universe'),
            field('screen_id', 'text', None, 'Persistence', 'Saved definition id for persisted runs and genuine membership differences.')]


RANGE_FILTERS = {
    'market_cap': 'Market capitalization', 'price': 'Observed close', 'dollar_volume': '20-session mean price times volume',
    'pe': 'Trailing twelve month P/E', 'roic': 'Statement-derived return on invested capital', 'pb': 'Price to book',
    'p_cf': 'Price to positive trailing cash flow', 'ev_ebit': 'Enterprise value to EBIT', 'interest_coverage': 'EBIT to interest expense',
    'revenue_growth_yoy': 'Annual revenue growth', 'eps_growth_yoy': 'Annual EPS change scaled by absolute prior EPS',
    'revenue_growth_3y_cagr': 'Revenue CAGR over three fiscal years', 'debt_ebitda': 'Debt to EBITDA', 'payout_ratio': 'Dividends to positive net income',
    'roe': 'Trailing return on equity', 'debt_equity': 'Debt to book equity', 'shares_outstanding': 'Reported ordinary shares',
    'atr_pct': 'ATR as share of observed close', 'adx': 'ADX', 'stochastic': 'Stochastic K', 'williams_r': 'Williams R',
    'ivol': '63-session FF3 residual volatility', 'max_factor': 'Maximum daily return over 21 sessions',
    'prox52': 'Price to 252-session high', 'high_proximity': 'Return from 252-session high', 'vratio': 'Current volume to mean trailing volume',
    'amihud_percentile': 'Amihud liquidity percentile', 'score': 'Core quant score',
    'bollinger_width_percentile': 'Trailing Bollinger width percentile', 'prox52_percentile': 'Cross-sectional proximity percentile',
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
        fields.update({item['key']: item for item in group})
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
    return result
