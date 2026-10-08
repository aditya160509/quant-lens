"""Observed hourly sampled variation, explicitly separate from tick estimators."""
from __future__ import annotations
from functools import lru_cache
import numpy as np
import pandas as pd
from . import data_loader


@lru_cache(maxsize=4)
def _bars(version, symbol):
    frame = pd.read_parquet(version[0], filters=[('Ticker', '=', symbol)])
    if frame.empty:
        raise ValueError(f'No exact hourly coverage for {symbol}; no proxy or alias substitution')
    frame['Datetime'] = pd.to_datetime(frame.Datetime, errors='raise')
    if frame.Datetime.isna().any() or frame.duplicated('Datetime').any():
        raise ValueError('Hourly observations require unique, non-null timestamps')
    for field in ['Open', 'High', 'Low', 'Close']:
        frame[field] = pd.to_numeric(frame[field], errors='raise')
        if not np.isfinite(frame[field]).all() or not frame[field].gt(0).all():
            raise ValueError('Hourly prices must be finite and positive')
    if (frame.High < frame[['Open', 'Close', 'Low']].max(axis=1)).any() or (frame.Low > frame[['Open', 'Close', 'High']].min(axis=1)).any():
        raise ValueError('Inconsistent hourly OHLC')
    return frame.sort_values('Datetime')


def sampled_variation(asset, start, end, timezone, session_timezone, minimum_bars=6):
    """Variation of observed consecutive hourly closes within declared dates.

    First-bar and overnight returns are excluded. No missing-hour interpolation,
    market microstructure correction, high-frequency limit or jump significance
    is claimed. The user must declare timezone because storage is naive.
    """
    if not timezone or not session_timezone:
        raise ValueError('hourly_timezone and session_timezone are required; source timestamps are naive')
    if minimum_bars < 3:
        raise ValueError('minimum_hourly_bars must be at least 3')
    path = data_loader.BACKEND_DATA / 'canonical/cross_asset_hourly.parquet'
    bars = _bars(data_loader.file_version(path), asset).copy()
    timestamps = bars.Datetime
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(timezone, ambiguous='raise', nonexistent='raise')
    timestamps = timestamps.dt.tz_convert(session_timezone)
    bars['date'] = timestamps.dt.tz_localize(None).dt.normalize()
    bars['timestamp'] = timestamps
    bars = bars.loc[bars.date.between(pd.Timestamp(start), pd.Timestamp(end).normalize())]
    if bars.empty:
        raise ValueError('No hourly observations within the requested daily date range')
    return variation_from_bars(bars, minimum_bars)


def variation_from_bars(bars, minimum_bars=6):
    rows = []
    for date, group in bars.groupby('date', sort=True):
        group = group.sort_values('timestamp')
        if len(group) < minimum_bars:
            continue
        intervals = group.timestamp.diff().dt.total_seconds()
        if not intervals.iloc[1:].eq(3600).all():
            continue
        returns = np.log(group.Close).diff().dropna().to_numpy()
        rv = returns @ returns
        # Finite sample correction N/(N-1), excluding the unknown opening return.
        n = len(returns)
        bpv = np.pi / 2 * n / (n - 1) * (np.abs(returns[1:]) @ np.abs(returns[:-1]))
        rows.append({'date': date, 'sampled_hourly_variance': rv,
                     'sampled_hourly_bipower': bpv, 'positive_rv_bpv_difference': max(rv - bpv, 0),
                     'observed_bars': len(group), 'observed_returns': n})
    if not rows:
        raise ValueError('No dates have the required consecutive hourly bars')
    return pd.DataFrame(rows)
