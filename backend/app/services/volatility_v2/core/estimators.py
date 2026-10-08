"""Daily OHLC volatility estimators with complete-window session rules."""

from __future__ import annotations
import math
from typing import Iterable
import numpy as np
import pandas as pd

ESTIMATORS = ["cc", "parkinson", "garman_klass", "rogers_satchell", "yang_zhang"]


ESTIMATOR_LABELS = {
    "cc": "Close-Close",
    "parkinson": "Parkinson",
    "garman_klass": "Garman-Klass",
    "rogers_satchell": "Rogers-Satchell",
    "yang_zhang": "Yang-Zhang",
}


def _rolling_mean_np(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).mean().to_numpy()


def _rolling_var_np(arr: np.ndarray, window: int, ddof: int = 1) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).var(ddof=ddof).to_numpy()


def volatility_estimators(
    ohlcv: pd.DataFrame,
    window: int = 21,
    annualization: int = 252,
    include_overnight: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        close = g["Close"].to_numpy(dtype=float)
        open_ = g["Open"].to_numpy(dtype=float)
        high = g["High"].to_numpy(dtype=float)
        low = g["Low"].to_numpy(dtype=float)
        prev_close = np.roll(close, 1)
        prev_close[0] = np.nan
        log_cc = np.log(close / prev_close)
        log_oc = np.log(close / open_)
        log_overnight = np.log(open_ / prev_close)
        log_hl = np.log(high / low)
        log_hl_sq = log_hl * log_hl
        log_oc_sq = log_oc * log_oc
        rs_daily = np.log(high / close) * np.log(high / open_) + np.log(
            low / close
        ) * np.log(low / open_)
        cc_var = _rolling_mean_np(log_cc * log_cc, window)
        park_var = _rolling_mean_np(log_hl_sq, window) / (4.0 * math.log(2.0))
        gk_var = _rolling_mean_np(
            0.5 * log_hl_sq - (2.0 * math.log(2.0) - 1.0) * log_oc_sq, window
        )
        rs_var = _rolling_mean_np(rs_daily, window)
        k = 0.34 / (1.34 + ((window + 1) / max(window - 1, 1)))
        yz_var = (
            (_rolling_var_np(log_overnight, window) if include_overnight else 0.0)
            + k * _rolling_var_np(log_oc, window)
            + (1 - k) * rs_var
        )
        tmp = pd.DataFrame(
            {
                "date": g["Date"],
                "asset": ticker,
                "cc": np.sqrt(np.maximum(cc_var, 0.0) * annualization),
                "parkinson": np.sqrt(np.maximum(park_var, 0.0) * annualization),
                "garman_klass": np.sqrt(np.maximum(gk_var, 0.0) * annualization),
                "rogers_satchell": np.sqrt(np.maximum(rs_var, 0.0) * annualization),
                "yang_zhang": np.sqrt(np.maximum(yz_var, 0.0) * annualization),
                "return": log_cc,
            }
        )
        frames.append(tmp)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    out["estimator_spread"] = out[ESTIMATORS].max(axis=1) - out[ESTIMATORS].min(axis=1)
    for col in [*ESTIMATORS, "return", "estimator_spread"]:
        if col in out.columns:
            out[col] = out[col].astype(np.float32)
    return out.dropna(subset=ESTIMATORS)


def volatility_estimators_multi(
    ohlcv: pd.DataFrame,
    windows: Iterable[int],
    annualization: int = 252,
    include_overnight: bool = True,
) -> dict[int, pd.DataFrame]:
    """Compute the five daily volatility estimators for many windows in one group scan."""
    frames_by_window: dict[int, list[pd.DataFrame]] = {int(w): [] for w in windows}
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        close = g["Close"].to_numpy(dtype=float)
        open_ = g["Open"].to_numpy(dtype=float)
        high = g["High"].to_numpy(dtype=float)
        low = g["Low"].to_numpy(dtype=float)
        prev_close = np.roll(close, 1)
        prev_close[0] = np.nan
        log_cc = np.log(close / prev_close)
        log_oc = np.log(close / open_)
        log_overnight = np.log(open_ / prev_close)
        log_hl = np.log(high / low)
        log_hl_sq = log_hl * log_hl
        log_oc_sq = log_oc * log_oc
        rs_daily = np.log(high / close) * np.log(high / open_) + np.log(
            low / close
        ) * np.log(low / open_)
        for window in frames_by_window:
            k = 0.34 / (1.34 + ((window + 1) / max(window - 1, 1)))
            cc_var = _rolling_mean_np(log_cc * log_cc, window)
            park_var = _rolling_mean_np(log_hl_sq, window) / (4.0 * math.log(2.0))
            gk_var = _rolling_mean_np(
                0.5 * log_hl_sq - (2.0 * math.log(2.0) - 1.0) * log_oc_sq, window
            )
            rs_var = _rolling_mean_np(rs_daily, window)
            yz_var = (
                (_rolling_var_np(log_overnight, window) if include_overnight else 0.0)
                + k * _rolling_var_np(log_oc, window)
                + (1 - k) * rs_var
            )
            frames_by_window[window].append(
                pd.DataFrame(
                    {
                        "date": g["Date"],
                        "asset": ticker,
                        "cc": np.sqrt(np.maximum(cc_var, 0.0) * annualization),
                        "parkinson": np.sqrt(np.maximum(park_var, 0.0) * annualization),
                        "garman_klass": np.sqrt(
                            np.maximum(gk_var, 0.0) * annualization
                        ),
                        "rogers_satchell": np.sqrt(
                            np.maximum(rs_var, 0.0) * annualization
                        ),
                        "yang_zhang": np.sqrt(np.maximum(yz_var, 0.0) * annualization),
                        "return": log_cc,
                    }
                )
            )
    out: dict[int, pd.DataFrame] = {}
    for window, frames in frames_by_window.items():
        if not frames:
            out[window] = pd.DataFrame()
            continue
        df = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
        df["estimator_spread"] = df[ESTIMATORS].max(axis=1) - df[ESTIMATORS].min(axis=1)
        for col in [*ESTIMATORS, "return", "estimator_spread"]:
            if col in df.columns:
                df[col] = df[col].astype(np.float32)
        out[window] = df.dropna(subset=ESTIMATORS)
    return out
