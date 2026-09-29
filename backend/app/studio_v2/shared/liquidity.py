from __future__ import annotations

"""
Almgren-Chriss market impact coefficient calibrator (F6.5).

Computes lambda per liquidity bucket (large/mid/small cap) via
cross-sectional OLS: impact = lambda * sigma * (trade/ADV)^(3/5).
Cached monthly. Consumed by F3.7, F5.2, F1.9.
"""

from datetime import date
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .data_loader import get_all_tickers, get_ohlcv_batch


DEFAULT_LAMBDAS = {"large": 4e-6, "mid": 2.4e-5, "small": 1.2e-4}
ASSET_CLASS_LAMBDAS = {"future": 8e-6, "futures": 8e-6, "fx": 2e-6, "crypto": 4e-5}


def almgren_chriss_impact(trade_size: float, adv: float, sigma: float, lam: float) -> float:
    ratio = abs(float(trade_size)) / float(adv) if np.isfinite(adv) and float(adv) > 0 else 0.0
    return float(lam * max(float(sigma), 1e-4) * ratio ** (3.0 / 5.0) * 10000.0) if ratio else 0.0


class LiquidityCalibrator:
    def __init__(self) -> None:
        self._cache: Dict[str, dict] = {}; self._stats: Dict[str, dict] = {}; self._ohlcv_cache: Dict[str, Dict[str, pd.DataFrame]] = {}; self._adv_cache: Dict[str, Dict[str, float]] = {}; self._bucket_cache: Dict[str, Dict[str, str]] = {}

    def _frame(self, ticker: str, when: date) -> pd.DataFrame:
        key = str(pd.Timestamp(when).date())
        symbol = str(ticker).upper()
        cache = self._ohlcv_cache.setdefault(key, {})
        if symbol not in cache:
            start = pd.Timestamp(when) - pd.Timedelta(days=180)
            cache.update(get_ohlcv_batch([symbol], start, when))
        return cache.get(symbol, pd.DataFrame())

    def _key(self, when: Optional[date]) -> str:
        timestamp = pd.Timestamp(when or pd.Timestamp.utcnow()).tz_localize(None)
        return str(timestamp.to_period("M"))

    def compute_adv(self, ticker: str, date: date) -> float:
        key = str(pd.Timestamp(date).date())
        if key in self._adv_cache and str(ticker).upper() in self._adv_cache[key]: return self._adv_cache[key][str(ticker).upper()]
        frame = self._frame(ticker, date)
        if frame.empty: value = float("nan")
        else:
            values = pd.to_numeric(frame["dollar_volume"], errors="coerce").tail(63).dropna(); value = float(values.mean()) if len(values) else float("nan")
        self._adv_cache.setdefault(key, {})[str(ticker).upper()] = value
        return value

    def compute_realized_vol(self, ticker: str, date: date) -> float:
        frame = self._frame(ticker, date)
        if frame.empty: return float("nan")
        returns = pd.to_numeric(frame["adjusted_close"], errors="coerce").pct_change(fill_method=None).tail(21).dropna(); return float(returns.std(ddof=1) * np.sqrt(252.0)) if len(returns) > 1 else float("nan")

    def estimate_bid_ask_spread(self, ticker: str, date: date) -> float:
        frame = self._frame(ticker, date).tail(21)
        if frame.empty: return float("nan")
        high, low = pd.to_numeric(frame["high"], errors="coerce"), pd.to_numeric(frame["low"], errors="coerce"); denominator = high + low; values = 2 * (high - low).div(denominator.replace(0, np.nan)); return float(values.replace([np.inf, -np.inf], np.nan).mean())

    def get_liquidity_bucket(self, ticker: str, date: date) -> str:
        key = str(pd.Timestamp(date).date())
        if key not in self._bucket_cache:
            self.calibrate(pd.Timestamp(date))
        bucket = self._bucket_cache[key].get(str(ticker).upper())
        if bucket is not None: return bucket
        adv = self.compute_adv(ticker, pd.Timestamp(date))
        valid = pd.Series(self._adv_cache.get(key, {})).replace([np.inf, -np.inf], np.nan).dropna()
        if not np.isfinite(adv) or valid.empty: return "small"
        percentile = float((valid < adv).mean()); return "large" if percentile >= 0.90 else ("mid" if percentile >= 0.50 else "small")

    def calibrate(self, date: Optional[date] = None) -> Dict[str, float]:
        key = self._key(date)
        if key in self._cache: return dict(self._cache[key])
        coefficients = dict(DEFAULT_LAMBDAS); symbols = get_all_tickers()[:500]; rows = []
        when = pd.Timestamp(date or pd.Timestamp.utcnow()).tz_localize(None)
        frames = get_ohlcv_batch(symbols, when - pd.Timedelta(days=180), when)
        computed = []
        for ticker, frame in frames.items():
            recent_63 = frame.tail(63)
            dollar_volume = pd.to_numeric(recent_63.get("dollar_volume"), errors="coerce").dropna()
            adv = float(dollar_volume.mean()) if len(dollar_volume) else float("nan")
            close = pd.to_numeric(frame.get("adjusted_close"), errors="coerce")
            daily = close.pct_change(fill_method=None).tail(21).dropna()
            sigma = float(daily.std(ddof=1) * np.sqrt(252)) if len(daily) > 1 else float("nan")
            recent_21 = frame.tail(21)
            high = pd.to_numeric(recent_21.get("high"), errors="coerce")
            low = pd.to_numeric(recent_21.get("low"), errors="coerce")
            spread_values = 2 * (high - low).div((high + low).replace(0, np.nan))
            spread = float(spread_values.replace([np.inf, -np.inf], np.nan).mean())
            computed.append((ticker, adv, sigma, spread))
        valid_adv = pd.Series({ticker: adv for ticker, adv, _, _ in computed}).dropna()
        quantiles = valid_adv.rank(pct=True)
        for ticker, adv, sigma, spread in computed:
            if np.isfinite(adv) and adv > 0 and np.isfinite(sigma) and np.isfinite(spread):
                percentile = float(quantiles.get(ticker, 0.0))
                bucket = "large" if percentile >= 0.90 else ("mid" if percentile >= 0.50 else "small")
                x = max(sigma, 1e-4) * 0.1 ** (3.0 / 5.0)
                rows.append((bucket, spread / max(x, 1e-12)))
                self._adv_cache.setdefault(str(when.date()), {})[ticker] = adv
                self._bucket_cache.setdefault(str(when.date()), {})[ticker] = bucket
        for bucket in coefficients:
            values = [value for name, value in rows if name == bucket]
            if len(values) >= 30: coefficients[bucket] = float(np.clip(np.median(values), 1e-8, 1.0))
        self._cache[key] = coefficients; self._stats[key] = {bucket: {"n": sum(name == bucket for name, _ in rows)} for bucket in coefficients}; return dict(coefficients)

    def get_lambda(self, ticker: str, date: date, asset_class: str = "equity") -> float:
        normalized = str(asset_class).lower()
        if normalized in ASSET_CLASS_LAMBDAS:
            return float(ASSET_CLASS_LAMBDAS[normalized])
        return float(self.calibrate(date).get(self.get_liquidity_bucket(ticker, date), DEFAULT_LAMBDAS["small"]))

    def estimate_cross_asset_impact(self, trade_size: float, adv: float, sigma: float,
                                    asset_class: str, ticker: str = "",
                                    when: date | None = None) -> dict:
        resolved_date = when or pd.Timestamp.utcnow().date()
        coefficient = self.get_lambda(ticker, resolved_date, asset_class)
        participation = abs(float(trade_size)) / float(adv) if np.isfinite(adv) and adv > 0 else 0.0
        return {
            "asset_class": str(asset_class).lower(),
            "lambda": coefficient,
            "participation": participation,
            "impact_bps": almgren_chriss_impact(trade_size, adv, sigma, coefficient),
        }
    def cache_coefficients(self, date: date, lambda_dict: dict) -> None: self._cache[self._key(date)] = {**DEFAULT_LAMBDAS, **{str(k): float(v) for k, v in lambda_dict.items()}}
    def load_cached_coefficients(self, date: date) -> dict: return dict(self._cache.get(self._key(date), DEFAULT_LAMBDAS))
