"""Price-only screens for crypto, forex, futures and hourly index bars. No fundamentals exist for these, so none are shown."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data_loader import BACKEND_DATA

CANONICAL = BACKEND_DATA / "canonical"
DAILY = {"crypto": "crypto_daily", "fx": "fx_daily", "futures": "futures_daily"}


def _num(v):
    return float(v) if v is not None and np.isfinite(v) else None


def _daily_row(ticker: str, g: pd.DataFrame) -> dict:
    close = g.sort_values("Date").set_index("Date").Close.astype(float).dropna()
    n = len(close)

    def ret(days):
        return _num(close.iloc[-1] / close.iloc[-1 - days] - 1) if n > days else None

    r = close.pct_change().dropna()
    last = close.iloc[-1]
    window = close.iloc[-252:]
    ma50, ma200 = (close.iloc[-50:].mean(), close.iloc[-200:].mean()) if n >= 200 else (None, None)
    # Chart patterns: mechanical rules on closes, weak evidence of future returns.
    pattern = "Unknown" if n < 200 else "New 252-day high" if last >= window.max() else "New 252-day low" if last <= window.min() else "50-day above 200-day" if ma50 > ma200 else "50-day below 200-day"
    return {"ticker": ticker, "last_close": _num(last), "last_date": str(close.index[-1])[:10], "observations": n,
            "return_1d": ret(1), "return_1m": ret(21), "return_6m": ret(126), "return_12m": ret(252),
            "realized_vol_63d": _num(r.iloc[-63:].std() * math.sqrt(252)) if len(r) >= 63 else None,
            "max_drawdown_252d": _num((window / window.cummax() - 1).min()) if n >= 252 else None,
            "pattern": pattern}


def screen(asset: str) -> list[dict]:
    if asset not in DAILY:
        raise KeyError(f"Unknown asset class: {asset}")
    frame = pd.read_parquet(CANONICAL / f"{DAILY[asset]}.parquet", columns=["Ticker", "Date", "Close"])
    return [_daily_row(t, g) for t, g in frame.groupby("Ticker") if len(g) > 1]


def hourly() -> list[dict]:
    frame = pd.read_parquet(CANONICAL / "cross_asset_hourly.parquet", columns=["Market", "Ticker", "Datetime", "Close"]).dropna(subset=["Market", "Close"])
    rows = []
    for market, g in frame.groupby("Market"):
        close = g.sort_values("Datetime").set_index("Datetime").Close.astype(float)
        n = len(close)
        r = close.pct_change().dropna()
        rows.append({"ticker": market, "last_close": _num(close.iloc[-1]), "last_bar": str(close.index[-1]), "bars": n,
                     "return_1h": _num(close.iloc[-1] / close.iloc[-2] - 1) if n > 1 else None,
                     "return_1d": _num(close.iloc[-1] / close.iloc[-8] - 1) if n > 7 else None,
                     "return_5d": _num(close.iloc[-1] / close.iloc[-36] - 1) if n > 35 else None,
                     "realized_vol_20d": _num(r.iloc[-140:].std() * math.sqrt(252 * 7)) if len(r) >= 140 else None})
    return rows
