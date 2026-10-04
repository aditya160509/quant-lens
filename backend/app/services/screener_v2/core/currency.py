"""Explicit instrument units and observed USD conversion, without rate filling."""
from contextlib import contextmanager
from contextvars import ContextVar
import math
import re
import numpy as np
import pandas as pd
from . import data_loader

CONFIG = ContextVar('screener_instrument_units', default={})


@contextmanager
def instrument_context(payload):
    declarations = payload.get('instrument_metadata')
    if declarations is None:
        declarations = {}
    if not isinstance(declarations, dict) or len(declarations) > 5000:
        raise ValueError('instrument_metadata must be an object with at most 5000 symbols')
    normalized = {}
    for symbol, item in declarations.items():
        if not isinstance(item, dict) or set(item) - {'quote_currency', 'financial_currency', 'quoted_units_per_ordinary_share'}:
            raise ValueError('Instrument metadata requires quote_currency, financial_currency and quoted_units_per_ordinary_share')
        record = dict(item)
        for field in ['quote_currency', 'financial_currency']:
            value = record.get(field)
            if value is not None and (not isinstance(value, str) or not re.fullmatch('[A-Z]{3}|GBp|ZAc|ILA', value)):
                raise ValueError(f'{field} must be a three-letter currency or GBp/ZAc/ILA')
        units = record.get('quoted_units_per_ordinary_share')
        if units is not None and (isinstance(units, bool) or not isinstance(units, (int, float)) or not math.isfinite(units) or units <= 0):
            raise ValueError('quoted_units_per_ordinary_share must be finite and positive')
        key = data_loader.normalize_symbol(symbol)
        if not key:
            raise ValueError("Instrument metadata requires a nonempty ticker")
        if key in normalized:
            raise ValueError('Duplicate normalized instrument metadata ticker')
        normalized[key] = record
    calendar = payload.get('calendar_ticker')
    if calendar is not None and (not isinstance(calendar, str) or not calendar.strip()):
        raise ValueError('calendar_ticker must be a nonempty ticker string')
    token = CONFIG.set({'instruments': normalized, 'calendar_ticker': data_loader.normalize_symbol(calendar) if calendar else 'SPY', 'explicit_calendar': bool(calendar)})
    try:
        yield
    finally:
        CONFIG.reset(token)


def instrument_specs(symbols):
    config = CONFIG.get()
    source = config.get('source_frame')
    if source is None:
        full = data_loader.load_fundamentals()
        columns = [key for key in ['ticker', 'reportDate', 'currency', 'quoteCurrency', 'financialCurrency', 'quoted_units_per_ordinary_share'] if key in full]
        source = full[columns]
        if 'instruments' in config:
            config['source_frame'] = source
    eligible = data_loader.eligible_reports(source.loc[source.ticker.isin(symbols)]) if not source.empty else source
    rows = eligible.sort_values('reportDate').groupby('ticker').tail(1) if not eligible.empty else eligible
    source_specs = rows.set_index('ticker').to_dict('index') if not rows.empty else {}
    declared = CONFIG.get().get('instruments', {})
    result = {}
    for symbol in symbols:
        row = source_specs.get(symbol, {})
        quote = row.get('quoteCurrency')
        # This is only a US quote denomination rule, never a financial-currency or ADR-unit inference.
        if not isinstance(quote, str) and '_' not in symbol and row.get('currency') == 'USD':
            quote = 'USD'
        spec = {'quote_currency': quote if isinstance(quote, str) else None,
                'financial_currency': row.get('financialCurrency') if isinstance(row.get('financialCurrency'), str) else None,
                'quoted_units_per_ordinary_share': row.get('quoted_units_per_ordinary_share')}
        if symbol == 'SPY':
            spec['quote_currency'] = 'USD'
        spec.update(declared.get(symbol, {}))
        result[symbol] = spec
    return result


def usd_rates(currencies, dates):
    """USD per currency unit on exactly observed dates; unsupported/missing is NaN."""
    index = pd.DatetimeIndex(dates).astype('datetime64[ns]')
    unique = list(dict.fromkeys(currencies))
    result = pd.DataFrame(index=index)
    nonusd = [value for value in unique if value not in (None, 'USD')]
    fx = data_loader.load_fx() if nonusd else pd.DataFrame()
    panel = fx.pivot(index='Date', columns='Ticker', values='Close') if not fx.empty else pd.DataFrame()
    panel.index = pd.DatetimeIndex(panel.index).astype('datetime64[ns]')
    units = {'GBp': ('GBP', .01), 'ZAc': ('ZAR', .01), 'ILA': ('ILS', .01)}
    for currency in unique:
        if currency is None:
            continue
        major, scale = units.get(currency, (currency, 1.))
        if major == 'USD':
            result[currency] = scale
        elif f'{major}USD=X' in panel:
            result[currency] = panel[f'{major}USD=X'].reindex(index).to_numpy() * scale
        elif f'USD{major}=X' in panel:
            result[currency] = scale / panel[f'USD{major}=X'].reindex(index).to_numpy()
        else:
            result[currency] = np.nan
    return result


def usd_price_matrix(prices, specs=None, strict=False):
    specs = specs or instrument_specs(list(prices.columns))
    currencies = [specs[symbol].get('quote_currency') for symbol in prices.columns]
    rates = usd_rates(currencies, prices.index)
    converted = prices.copy()
    missing = []
    for symbol, currency in zip(prices.columns, currencies):
        rate = rates[currency] if currency in rates else pd.Series(np.nan, index=prices.index)
        if (prices[symbol].notna() & rate.isna()).any():
            missing.append(symbol)
        converted[symbol] = prices[symbol].to_numpy() * rate.to_numpy()
    if strict and missing:
        raise ValueError('Missing instrument quote currency or exact-date FX observations for: ' + ', '.join(missing) + '. Supply instrument_metadata; stale rates and currency proxies are prohibited.')
    return converted
