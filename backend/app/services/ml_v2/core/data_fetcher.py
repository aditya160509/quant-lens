"""Append-only data fetch plan for ML V2.

This module is intentionally inert unless an operator runs it manually. Feature
runners never fetch network data. The functions below describe exactly which
free data sources fill optional gaps and write by appending/deduplicating.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .data_loader import CATEGORY7_MACRO, MARKET_UNIVERSE, MARKET_UNIVERSE_HOURLY, ROOT


FRED_SERIES = {
    "VIXCLS": "Daily CBOE VIX close for regime/volatility features.",
    "DGS2": "2-year Treasury yield for 2s10s slope.",
    "DGS10": "10-year Treasury yield for 2s10s slope.",
    "DTB3": "3-month Treasury bill secondary-market rate.",
    "TEDRATE": "TED spread stress proxy when available.",
}

YFINANCE_OPTIONAL = {
    "^VIX9D": "9-day VIX for term-structure inputs.",
    "^VIX3M": "3-month VIX for term-structure inputs.",
    "SPY": "Market benchmark fallback.",
}


def append_dedup_parquet(existing_path: Path, new_rows: pd.DataFrame, subset: Iterable[str]) -> None:
    """Append rows to a parquet file with stable de-duplication.

    This is not called automatically; it is provided for the future data pooling
    job so it never overwrites existing panels.
    """

    existing = pd.read_parquet(existing_path) if existing_path.exists() else pd.DataFrame()
    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined = combined.drop_duplicates(list(subset), keep="last")
    combined.to_parquet(existing_path, index=False)


def missing_data_plan() -> dict:
    return {
        "do_not_fetch_automatically": True,
        "append_only_targets": {
            "daily_ohlcv": str(MARKET_UNIVERSE),
            "hourly_ohlcv": str(MARKET_UNIVERSE_HOURLY),
            "macro_regime": str(CATEGORY7_MACRO),
        },
        "fred_series": FRED_SERIES,
        "yfinance_optional": YFINANCE_OPTIONAL,
        "ken_french": {
            "ff3_daily": "factors/data/raw/fama_french/F-F_Research_Data_Factors_daily.csv",
            "ff5_daily": "factors/data/raw/fama_french/F-F_Research_Data_5_Factors_2x3_daily.csv",
            "momentum_daily": "factors/data/raw/fama_french/F-F_Momentum_Factor_daily.csv",
        },
        "missing_if_absent": [
            "True options/implied-volatility chains are not required by this ML spec.",
            "True tick-level bid/ask/order-book data is absent; Feature 10 uses daily OHLCV microstructure estimators.",
            "Company event/earnings calendars are absent; Feature 12 uses date-cycle proxies only if requested.",
        ],
        "repo_root": str(ROOT),
    }

