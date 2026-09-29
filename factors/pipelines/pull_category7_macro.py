#!/usr/bin/env python3
"""Category 7 pipeline: pull VIX/rates/CPI from FRED, align to daily, and save."""

from __future__ import annotations

import io
from pathlib import Path
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_PARQUET = ROOT / 'factors/data/processed/category7_macro_regime.parquet'
OUT_CSV = ROOT / 'factors/data/processed/category7_macro_regime.csv'

SERIES = {
    'VIXCLS': 'vix_close',
    'DGS2': 'ust_2y',
    'DGS10': 'ust_10y',
    'FEDFUNDS': 'fed_funds',
    'CPIAUCSL': 'cpi',
}
START_DATE = '2000-01-01'


def pull_fred_csv(series_id: str) -> pd.DataFrame:
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={START_DATE}'
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ['date', series_id]
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df[series_id] = pd.to_numeric(df[series_id].replace('.', pd.NA), errors='coerce')
    return df.dropna(subset=['date'])


def main() -> int:
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    merged = None
    for sid in SERIES:
        df = pull_fred_csv(sid)
        merged = df if merged is None else merged.merge(df, on='date', how='outer')

    merged = merged.sort_values('date').reset_index(drop=True)

    # Build daily calendar and forward-fill lower-frequency series for daily models.
    daily = pd.DataFrame({'date': pd.date_range(merged['date'].min(), merged['date'].max(), freq='D')})
    daily = daily.merge(merged, on='date', how='left').sort_values('date')
    daily[['FEDFUNDS', 'CPIAUCSL']] = daily[['FEDFUNDS', 'CPIAUCSL']].ffill()

    # Trading-day rates may contain missing holidays/weekends; ffill for continuity.
    daily[['VIXCLS', 'DGS2', 'DGS10']] = daily[['VIXCLS', 'DGS2', 'DGS10']].ffill()

    daily = daily.rename(columns=SERIES)
    daily['yc_slope_10y_2y'] = daily['ust_10y'] - daily['ust_2y']

    cols = ['date', 'vix_close', 'ust_2y', 'ust_10y', 'yc_slope_10y_2y', 'fed_funds', 'cpi']
    daily = daily[cols]

    daily.to_parquet(OUT_PARQUET, index=False)
    daily.to_csv(OUT_CSV, index=False)

    print('Saved:', OUT_PARQUET)
    print('Saved:', OUT_CSV)
    print('Rows:', len(daily))
    print('Date range:', daily['date'].min().date(), 'to', daily['date'].max().date())
    print('Null counts:\n', daily.isna().sum())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
