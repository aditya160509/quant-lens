"""Screener V2 analytics.

The module intentionally keeps feature computations deterministic and read-only.
Missing operational datasets are surfaced through ``meta.access_issues`` rather
than filled with fake values.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from .data_loader import (
    available_symbols,
    close_matrix,
    fundamental_history,
    latest_fundamentals,
    load_fundamentals,
    load_factor_returns,
    load_macro,
    ohlcv_for_symbols,
    parse_symbols,
    returns_matrix,
    volume_matrix,
    normalize_symbol,
)
from .gics import add_industry_group


TRADING_DAYS = 252
DEFAULT_TOP_N = 50
RETURN_HORIZON_FIELDS = {
    "return_1d": 1,
    "r_1d": 1,
    "return_1w": 5,
    "r_5d": 5,
    "return_1m": 21,
    "r_21d": 21,
    "return_3m": 63,
    "r_63d": 63,
    "return_6m": 126,
    "r_126d": 126,
    "return_12m": 252,
    "r_252d": 252,
    "r_jt": 252,
    "momentum_jt": 252,
}
PIT_FUNDAMENTAL_FORMULA_FIELDS = {"roa", "roe", "current_ratio", "debt_equity", "gross_margin", "operating_margin", "mcap"}


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (pd.Timedelta, np.timedelta64)):
        return str(pd.Timedelta(value))
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (complex, np.complexfloating)):
        return {"real": clean_json(value.real), "imag": clean_json(value.imag)}
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def response(
    feature_id: str,
    summary_cards: list[dict[str, Any]] | None = None,
    charts: dict[str, Any] | None = None,
    tables: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return clean_json(
        {
            "feature_id": feature_id,
            "status": "ok",
            "summary_cards": summary_cards or [],
            "charts": charts or {},
            "tables": tables or {},
            "meta": meta or {},
        }
    )


def number_like(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    if limit:
        out = out.head(int(limit))
    return clean_json(out.replace([np.inf, -np.inf], np.nan).where(pd.notna(out), None).to_dict("records"))


def matrix_records(matrix: pd.DataFrame, value_name: str = "value") -> list[dict[str, Any]]:
    if matrix is None or matrix.empty:
        return []
    rows = []
    for r in matrix.index:
        for c in matrix.columns:
            v = number_like(matrix.loc[r, c])
            if v is not None:
                rows.append({"row": str(r), "col": str(c), value_name: v})
    return clean_json(rows)


def rank_pct(series: pd.Series, higher_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series(50.0, index=series.index)
    pct = numeric.rank(pct=True, method="average") * 100.0
    if not higher_better:
        pct = 100.0 - pct
    return pct.fillna(50.0).clip(0, 100)


def zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std(ddof=0)
    if not std or not np.isfinite(std):
        return pd.Series(0.0, index=series.index)
    return ((numeric - numeric.mean()) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


VALUATION_FIELDS = {"trailing_pe", "forward_pe", "pb_ratio", "ps_ratio", "ev_ebitda", "ev_revenue", "p_cf", "ev_ebit"}
VOLATILITY_FIELDS = {"realized_vol_63d", "realized_vol_252d", "ivol_ff3_63d", "beta_spy", "beta_252", "atr_pct_price", "amihud_20d"}
DISTRESS_FIELDS_INVERTED = {"max_1d_return_252d", "max_1d_return_21d", "debt_ebitda", "accruals_assets"}


def _winsorize_at_percentiles(series: pd.Series, lower_pct: float = 1.0, upper_pct: float = 99.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    lo = numeric.quantile(lower_pct / 100.0)
    hi = numeric.quantile(upper_pct / 100.0)
    return numeric.clip(lower=lo, upper=hi)


def sign_correct(field: str | None, values: pd.Series) -> pd.Series:
    if field in VALUATION_FIELDS or field in VOLATILITY_FIELDS or field in DISTRESS_FIELDS_INVERTED:
        return -values
    return values


def beta_neutralize(values: pd.Series, beta: pd.Series) -> pd.Series:
    v = pd.to_numeric(values, errors="coerce").fillna(0.0)
    b = pd.to_numeric(beta, errors="coerce").fillna(1.0)
    var_b = b.var()
    if not var_b or not math.isfinite(var_b):
        return v
    beta_hat = v.cov(b) / var_b
    return v - beta_hat * b


def _pick(df: pd.DataFrame, names: list[str], default: float | str | None = np.nan) -> pd.Series:
    lookup = {str(c).lower().replace(" ", "_"): c for c in df.columns}
    for name in names:
        key = name.lower().replace(" ", "_")
        if key in lookup:
            return df[lookup[key]]
    return pd.Series(default, index=df.index)


def _safe_div(a: pd.Series | float, b: pd.Series | float) -> pd.Series:
    out = pd.to_numeric(a, errors="coerce") / pd.to_numeric(b, errors="coerce").replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def _wilder_smooth(series: pd.Series, period: int, min_seed_coverage: float = 1.0) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) < period:
        return pd.Series(out, index=series.index)
    seed_window = values[:period]
    if np.isfinite(seed_window).mean() < min_seed_coverage:
        return pd.Series(out, index=series.index)
    out[period - 1] = np.nanmean(seed_window)
    for idx in range(period, len(values)):
        prev = out[idx - 1]
        val = values[idx]
        if np.isnan(prev):
            out[idx] = np.nan
        elif np.isnan(val):
            out[idx] = prev
        else:
            out[idx] = ((period - 1) * prev + val) / period
    return pd.Series(out, index=series.index)


def sma_cross_event(short: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    short_aligned, long_aligned = short.align(long, join="inner", axis=None)
    if short_aligned.empty or long_aligned.empty:
        return pd.DataFrame()
    above = (short_aligned > long_aligned).astype(float)
    return above.diff().fillna(0.0)


def latest_technical_features(symbols: list[str], lookback_days: int = 756, periods: dict[str, Any] | None = None) -> pd.DataFrame:
    periods = periods or {}
    rsi_period = max(2, int(periods.get("rsi_period", 14)))
    stochastic_period = max(2, int(periods.get("stochastic_period", 14)))
    stochastic_d_period = max(2, int(periods.get("stochastic_d_period", 3)))
    adx_period = max(2, int(periods.get("adx_period", 14)))
    atr_period = max(2, int(periods.get("atr_period", 14)))
    bb_period = max(2, int(periods.get("bollinger_period", 20)))
    bb_std_multiple = max(0.1, float(periods.get("bollinger_std_multiple", 2.0)))
    macd_fast = max(2, int(periods.get("macd_fast_period", 12)))
    macd_slow = max(macd_fast + 1, int(periods.get("macd_slow_period", 26)))
    macd_signal_period = max(2, int(periods.get("macd_signal_period", 9)))
    cross_lookback = max(1, min(252, int(periods.get("cross_lookback_days", 20))))
    requested_symbols = [normalize_symbol(s) for s in symbols]
    fetch_symbols = list(dict.fromkeys(requested_symbols + ["SPY"]))
    raw_ohlcv = ohlcv_for_symbols(fetch_symbols, lookback_days=max(lookback_days, 300))
    prices = close_matrix(fetch_symbols, lookback_days=max(lookback_days, 260))
    volumes = volume_matrix(fetch_symbols, lookback_days=max(lookback_days, 260))
    as_of_date = pd.to_datetime(periods.get("as_of_date"), errors="coerce") if periods.get("as_of_date") else None
    if as_of_date is not None and pd.notna(as_of_date) and not raw_ohlcv.empty:
        raw_ohlcv = raw_ohlcv[raw_ohlcv["Date"] <= as_of_date]
        prices = raw_ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().tail(max(lookback_days, 260))
        volumes = raw_ohlcv.pivot_table(index="Date", columns="Ticker", values="Volume", aggfunc="last").sort_index().reindex(prices.index).tail(max(lookback_days, 260))
    if prices.empty:
        return pd.DataFrame(columns=["ticker"])
    prices = prices.ffill()
    volumes = volumes.reindex(prices.index).ffill() if not volumes.empty else pd.DataFrame(index=prices.index, columns=prices.columns)
    highs = _pivot_ohlc_field(raw_ohlcv, "High", prices.index) if not raw_ohlcv.empty else prices
    lows = _pivot_ohlc_field(raw_ohlcv, "Low", prices.index) if not raw_ohlcv.empty else prices
    opens = _pivot_ohlc_field(raw_ohlcv, "Open", prices.index) if not raw_ohlcv.empty else prices
    rets = prices.pct_change(fill_method=None)
    latest = prices.iloc[-1]
    out = pd.DataFrame(index=prices.columns)
    out["ticker"] = out.index
    out["open"] = opens.iloc[-1].reindex(out.index)
    out["high"] = highs.iloc[-1].reindex(out.index)
    out["low"] = lows.iloc[-1].reindex(out.index)
    out["close"] = latest
    out["adj_close"] = latest
    out["price"] = latest
    out["volume_today"] = volumes.iloc[-1]
    out["volume"] = out["volume_today"]
    out["volume_20d"] = volumes.tail(20).mean()
    out["volume_spike_ratio"] = _safe_div(out["volume_today"], out["volume_20d"])
    out["vratio"] = out["volume_spike_ratio"]
    out["dollar_volume_20d"] = out["volume_20d"] * out["price"]
    for days, key in [(1, "return_1d"), (5, "return_1w"), (21, "return_1m"), (63, "return_3m"), (126, "return_6m"), (252, "return_12m")]:
        if len(prices) > days:
            out[key] = prices.iloc[-1] / prices.shift(days).iloc[-1] - 1.0
        else:
            out[key] = np.nan
    if len(prices) > 252:
        out["momentum_jt"] = prices.shift(21).iloc[-1] / prices.shift(252).iloc[-1] - 1.0
    else:
        out["momentum_jt"] = out["return_6m"]
    out["realized_vol_63d"] = rets.tail(63).std() * math.sqrt(TRADING_DAYS)
    out["realized_vol_252d"] = rets.tail(252).std() * math.sqrt(TRADING_DAYS)
    rolling_high = prices.tail(252).max()
    rolling_low = prices.tail(252).min()
    out["prox52"] = out["price"] / rolling_high.replace(0, np.nan)
    out["pct_from_52w_high"] = out["price"] / rolling_high - 1.0
    out["pct_above_52w_low"] = out["price"] / rolling_low - 1.0
    for window in [20, 50, 100, 200]:
        ma_series = prices.rolling(window).mean()
        ma = ma_series.iloc[-1]
        out[f"sma_{window}"] = ma
        out[f"dist_sma_{window}"] = out["price"] / ma - 1.0
        ema = prices.ewm(span=window, adjust=False, min_periods=min(window, len(prices))).mean().iloc[-1]
        out[f"ema_{window}"] = ema
        out[f"dist_ema_{window}"] = out["price"] / ema - 1.0
        above_today = prices.iloc[-1] > ma_series.iloc[-1]
        above_yesterday = prices.iloc[-2] > ma_series.iloc[-2] if len(prices) > 1 else above_today
        out[f"crossed_above_sma_{window}_today"] = (above_today & ~above_yesterday).astype(float)
        out[f"crossed_below_sma_{window}_today"] = (~above_today & above_yesterday).astype(float)
    out["sma20_above_sma50"] = (out["sma_20"] > out["sma_50"]).astype(float)
    out["sma50_above_sma200"] = (out["sma_50"] > out["sma_200"]).astype(float)
    short_cross = prices.rolling(20).mean() - prices.rolling(50).mean()
    long_cross = prices.rolling(50).mean() - prices.rolling(200).mean()
    out["sma20_50_cross_days"] = short_cross.tail(cross_lookback).apply(_last_sign_cross_age)
    out["sma50_200_cross_days"] = long_cross.tail(cross_lookback).apply(_last_sign_cross_age)
    cross_50_200 = sma_cross_event(prices.rolling(50).mean(), prices.rolling(200).mean())
    out["golden_cross_today"] = (cross_50_200.iloc[-1] == 1).astype(float)
    out["death_cross_today"] = (cross_50_200.iloc[-1] == -1).astype(float)
    out["golden_cross_within_20d"] = (cross_50_200.tail(20) == 1).any().astype(float)
    out["death_cross_within_20d"] = (cross_50_200.tail(20) == -1).any().astype(float)
    out["golden_cross_age_days"] = cross_50_200.tail(cross_lookback).apply(lambda s: _last_event_age(s, 1.0))
    out["death_cross_age_days"] = cross_50_200.tail(cross_lookback).apply(lambda s: _last_event_age(s, -1.0))
    ema12 = prices.ewm(span=macd_fast, adjust=False).mean()
    ema26 = prices.ewm(span=macd_slow, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=macd_signal_period, adjust=False).mean()
    macd_hist = macd - macd_signal
    out["macd"] = macd.iloc[-1]
    out["macd_signal"] = macd_signal.iloc[-1]
    out["macd_histogram"] = macd_hist.iloc[-1]
    out["macd_bullish"] = (out["macd"] > out["macd_signal"]).astype(float)
    out["macd_cross_days"] = macd_hist.tail(20).apply(_last_sign_cross_age)
    bb_mid = prices.rolling(bb_period).mean()
    bb_std = prices.rolling(bb_period).std()
    bb_upper = bb_mid + bb_std_multiple * bb_std
    bb_lower = bb_mid - bb_std_multiple * bb_std
    out["bollinger_upper"] = bb_upper.iloc[-1]
    out["bollinger_lower"] = bb_lower.iloc[-1]
    out["bollinger_pct_b"] = (prices.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]).replace(0, np.nan)
    out["bollinger_band_width"] = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1].replace(0, np.nan)
    out["bollinger_width_percentile"] = rank_pct(out["bollinger_band_width"])
    tr = pd.concat([(highs - lows).stack(), (highs - prices.shift(1)).abs().stack(), (lows - prices.shift(1)).abs().stack()], axis=1).max(axis=1).unstack()
    atr = tr.apply(lambda col: _wilder_smooth(col, atr_period))
    out["atr_14"] = atr.iloc[-1]
    out["atr_pct_price"] = out["atr_14"] / out["price"].replace(0, np.nan)
    up_move = highs.diff()
    down_move = -lows.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_dm = atr.replace(0, np.nan)
    plus_di = 100 * plus_dm.apply(lambda col: _wilder_smooth(col, adx_period)) / atr_dm
    minus_di = 100 * minus_dm.apply(lambda col: _wilder_smooth(col, adx_period)) / atr_dm
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    out["adx_14"] = dx.apply(lambda col: _wilder_smooth(col, adx_period)).iloc[-1]
    out["dmi_plus"] = plus_di.iloc[-1]
    out["dmi_minus"] = minus_di.iloc[-1]
    low14 = lows.rolling(stochastic_period).min()
    high14 = highs.rolling(stochastic_period).max()
    stoch_k = (prices - low14) / (high14 - low14).replace(0, np.nan) * 100
    out["stochastic_k"] = stoch_k.iloc[-1]
    out["stochastic_d"] = stoch_k.rolling(stochastic_d_period).mean().iloc[-1]
    out["williams_r"] = -100 * (high14.iloc[-1] - prices.iloc[-1]) / (high14.iloc[-1] - low14.iloc[-1]).replace(0, np.nan)
    signed_volume = np.sign(prices.diff()).fillna(0) * volumes.fillna(0)
    obv = signed_volume.cumsum()
    out["obv_20d_slope"] = (obv.iloc[-1] - obv.shift(20).iloc[-1]) / 20 if len(obv) > 20 else np.nan
    delta = prices.diff()
    gain = delta.clip(lower=0).apply(lambda col: _wilder_smooth(col, rsi_period))
    loss = (-delta.clip(upper=0)).apply(lambda col: _wilder_smooth(col, rsi_period))
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = (100 - (100 / (1 + rs))).iloc[-1]
    prior_close = prices.iloc[-2] if len(prices) > 1 else pd.Series(np.nan, index=out.index)
    out["gap_1d"] = _safe_div(opens.iloc[-1].reindex(out.index) - prior_close.reindex(out.index), prior_close.reindex(out.index))
    out["max_1d_return_252d"] = rets.tail(252).max()
    out["max_1d_return_21d"] = rets.tail(21).max()
    out["min_1d_return_252d"] = rets.tail(252).min()
    up = rets.gt(0)
    down = rets.lt(0)
    out["consecutive_up_days"] = up.apply(_trailing_true_count)
    out["consecutive_down_days"] = down.apply(_trailing_true_count)
    out["short_term_reversal_flag"] = ((rank_pct(out["return_1w"], higher_better=False) >= 90) | (rank_pct(out["return_1m"], higher_better=False) >= 90)).astype(float)
    spy_available = "SPY" in rets.columns
    sufficient_history = len(rets) >= 126
    if spy_available and sufficient_history:
        market = rets["SPY"].tail(252)
        var = market.var()
        out["beta_252"] = rets.tail(252).apply(lambda col: col.cov(market)).reindex(out.index) / var if var else np.nan
        out["beta_252_unavailable_reason"] = None
        out["beta_universe_proxy"] = np.nan
    else:
        lookback = min(252, max(1, len(rets)))
        universe_mean = rets.tail(lookback).mean(axis=1)
        var = universe_mean.var()
        out["beta_252"] = np.nan
        out["beta_252_unavailable_reason"] = "insufficient_history" if not sufficient_history else "spy_series_missing"
        out["beta_universe_proxy"] = rets.tail(lookback).apply(lambda col: col.cov(universe_mean)).reindex(out.index) / var if var else np.nan
        out["relative_return_3m_spy"] = out["return_3m"] - (prices.mean(axis=1).iloc[-1] / prices.mean(axis=1).shift(63).iloc[-1] - 1 if len(prices) > 63 else np.nan)
    if "SPY" in prices.columns and len(prices) > 63:
        spy_return = prices["SPY"].iloc[-1] / prices["SPY"].shift(63).iloc[-1] - 1
        out["relative_return_3m_spy"] = out["return_3m"] - spy_return
    out["amihud_20d"] = (rets.abs().tail(20) / (volumes.tail(20) * prices.tail(20)).replace(0, np.nan)).mean()
    out["amihud_percentile"] = rank_pct(out["amihud_20d"], higher_better=False)
    ff = load_factor_returns()
    out["ivol_ff3_63d"] = _idiosyncratic_vol(rets.tail(126), ff)
    yz_window = min(63, max(2, len(prices) - 1))
    log_overnight = np.log(opens / prices.shift(1)).replace([np.inf, -np.inf], np.nan)
    log_open_close = np.log(prices / opens).replace([np.inf, -np.inf], np.nan)
    rs_daily = (
        np.log(highs / opens) * np.log(highs / prices)
        + np.log(lows / opens) * np.log(lows / prices)
    ).replace([np.inf, -np.inf], np.nan)
    yz_k = 0.34 / (1.34 + (yz_window + 1.0) / max(1.0, yz_window - 1.0))
    yz_daily_variance = (
        log_overnight.tail(yz_window).var(ddof=1)
        + yz_k * log_open_close.tail(yz_window).var(ddof=1)
        + (1.0 - yz_k) * rs_daily.tail(yz_window).mean()
    ).clip(lower=0)
    out["vol_forecast_21d"] = np.sqrt(yz_daily_variance * 21.0)
    out["vol_forecast_method"] = "yang_zhang_63d_scaled_21d"
    out["technical_percentile"] = (
        rank_pct(out["momentum_jt"]) * 0.35
        + rank_pct(out["return_6m"]) * 0.2
        + rank_pct(out["dist_sma_200"]) * 0.15
        + rank_pct(out["realized_vol_63d"], higher_better=False) * 0.15
        + rank_pct(out["dollar_volume_20d"]) * 0.15
    )
    out["beta_effective"] = out["beta_252"].fillna(out["beta_universe_proxy"])
    out["beta_effective_source"] = np.where(out["beta_252"].notna(), "spy_true_beta", "universe_proxy_beta")
    dropped_symbols = sorted(set(requested_symbols) - set(out.index))
    out = out.reindex([s for s in requested_symbols if s in out.index])
    out["beta_spy"] = out["beta_252"]
    out = out.reset_index(drop=True).replace([np.inf, -np.inf], np.nan)
    out.attrs["dropped_symbols"] = dropped_symbols
    out.attrs["dropped_symbol_count"] = len(dropped_symbols)
    return out


def _pivot_ohlc_field(raw_ohlcv: pd.DataFrame, field: str, index_like: pd.Index) -> pd.DataFrame:
    if raw_ohlcv.empty:
        return pd.DataFrame(index=index_like)
    return raw_ohlcv.pivot_table(index="Date", columns="Ticker", values=field, aggfunc="last").sort_index().ffill().reindex(index_like).ffill()


def _last_sign_cross_age(series: pd.Series) -> float | None:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if len(vals) < 2:
        return None
    signs = np.sign(vals)
    crossings = np.where(np.diff(signs) != 0)[0]
    if len(crossings) == 0:
        return None
    return float(len(vals) - crossings[-1] - 2)


def _last_event_age(series: pd.Series, event: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").to_numpy()
    locations = np.flatnonzero(values == event)
    return float(len(values) - 1 - locations[-1]) if len(locations) else None


def _trailing_true_count(series: pd.Series) -> int:
    count = 0
    for val in reversed(series.fillna(False).astype(bool).tolist()):
        if not val:
            break
        count += 1
    return count


def _idiosyncratic_vol(returns: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    if returns.empty or factors.empty or "mkt_rf" not in factors.columns:
        return returns.std() * math.sqrt(TRADING_DAYS)
    aligned = returns.copy()
    factor_df = factors.set_index("date").reindex(aligned.index).ffill()
    cols = [c for c in ["mkt_rf", "smb", "hml"] if c in factor_df.columns]
    if not cols:
        return returns.std() * math.sqrt(TRADING_DAYS)
    x = factor_df[cols].fillna(0.0).to_numpy()
    x = np.column_stack([np.ones(len(x)), x])
    out = {}
    for col in aligned.columns:
        y = aligned[col].fillna(0.0).to_numpy()
        if len(y) < len(cols) + 5:
            out[col] = np.nan
            continue
        try:
            beta = np.linalg.lstsq(x, y, rcond=None)[0]
            resid = y - x @ beta
            out[col] = float(np.std(resid) * math.sqrt(TRADING_DAYS))
        except Exception:
            out[col] = np.nan
    return pd.Series(out)


def latest_fundamental_features(symbols: list[str], as_of_date: Any | None = None) -> pd.DataFrame:
    if as_of_date:
        all_fundamentals = load_fundamentals()
        cutoff = pd.to_datetime(as_of_date, errors="coerce")
        if pd.notna(cutoff) and "reportDate" in all_fundamentals:
            eligible = all_fundamentals[all_fundamentals["reportDate"] <= cutoff].sort_values(["ticker", "reportDate"])
            base = eligible.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)
        else:
            base = latest_fundamentals()
    else:
        base = latest_fundamentals()
    if base.empty:
        return pd.DataFrame({"ticker": symbols})
    df = base.reindex(symbols).copy()
    df["ticker"] = df.index
    out = pd.DataFrame(index=df.index)
    out["ticker"] = df["ticker"]
    out["company_name"] = _pick(df, ["shortName", "longName", "companyName"], "").fillna("").astype(str)
    out["exchange"] = _pick(df, ["exchange", "fullExchangeName"], "").fillna("").astype(str)
    out["sector"] = _pick(df, ["sector"], "Unknown").fillna("Unknown").astype(str)
    out["industry"] = _pick(df, ["industry"], "Unknown").fillna("Unknown").astype(str)
    out["market_cap"] = pd.to_numeric(_pick(df, ["marketCap", "market_cap", "Market Cap"]), errors="coerce")
    out["enterprise_value"] = pd.to_numeric(_pick(df, ["enterpriseValue", "enterprise_value"]), errors="coerce")
    out["trailing_pe"] = pd.to_numeric(_pick(df, ["trailingPE", "pe_ratio"]), errors="coerce")
    out["forward_pe"] = pd.to_numeric(_pick(df, ["forwardPE"]), errors="coerce")
    out["pb_ratio"] = pd.to_numeric(_pick(df, ["priceToBook", "price_to_book"]), errors="coerce")
    out["ps_ratio"] = pd.to_numeric(_pick(df, ["priceToSalesTrailing12Months", "price_to_sales"]), errors="coerce")
    out["ev_ebitda"] = pd.to_numeric(_pick(df, ["enterpriseToEbitda", "ev_ebitda"]), errors="coerce")
    out["ev_revenue"] = pd.to_numeric(_pick(df, ["enterpriseToRevenue", "ev_revenue"]), errors="coerce")
    out["dividend_yield"] = pd.to_numeric(_pick(df, ["dividendYield"]), errors="coerce")
    out["gross_margin"] = pd.to_numeric(_pick(df, ["grossMargins", "Gross Profit Margin"]), errors="coerce")
    out["operating_margin"] = pd.to_numeric(_pick(df, ["operatingMargins"]), errors="coerce")
    out["net_margin"] = pd.to_numeric(_pick(df, ["profitMargins"]), errors="coerce")
    out["roe"] = pd.to_numeric(_pick(df, ["returnOnEquity"]), errors="coerce")
    out["roa"] = pd.to_numeric(_pick(df, ["returnOnAssets"]), errors="coerce")
    out["debt_equity"] = pd.to_numeric(_pick(df, ["debtToEquity"]), errors="coerce")
    out["current_ratio"] = pd.to_numeric(_pick(df, ["currentRatio"]), errors="coerce")
    out["quick_ratio"] = pd.to_numeric(_pick(df, ["quickRatio"]), errors="coerce")
    out["shares_outstanding"] = pd.to_numeric(_pick(df, ["sharesOutstanding"]), errors="coerce")
    out["float_percent"] = pd.to_numeric(_pick(df, ["floatPercent", "float_pct"]), errors="coerce")
    revenue = pd.to_numeric(_pick(df, ["Total Revenue", "totalRevenue", "revenue"]), errors="coerce")
    gross_profit = pd.to_numeric(_pick(df, ["Gross Profit", "grossProfit"]), errors="coerce")
    ebit = pd.to_numeric(_pick(df, ["EBIT", "Operating Income", "operatingIncome"]), errors="coerce")
    ebitda = pd.to_numeric(_pick(df, ["EBITDA"]), errors="coerce")
    net_income = pd.to_numeric(_pick(df, ["Net Income", "netIncomeToCommon"]), errors="coerce")
    assets = pd.to_numeric(_pick(df, ["Total Assets", "totalAssets"]), errors="coerce")
    liabilities = pd.to_numeric(_pick(df, ["Total Liabilities Net Minority Interest", "totalLiabilitiesNetMinorityInterest"]), errors="coerce")
    current_assets = pd.to_numeric(_pick(df, ["Current Assets", "totalCurrentAssets"]), errors="coerce")
    current_liabilities = pd.to_numeric(_pick(df, ["Current Liabilities", "totalCurrentLiabilities"]), errors="coerce")
    cash = pd.to_numeric(_pick(df, ["Cash And Cash Equivalents", "totalCash"]), errors="coerce")
    total_debt = pd.to_numeric(_pick(df, ["Total Debt", "totalDebt"]), errors="coerce")
    retained_earnings = pd.to_numeric(_pick(df, ["Retained Earnings"]), errors="coerce")
    operating_cf = pd.to_numeric(_pick(df, ["Operating Cash Flow", "operatingCashflow"]), errors="coerce")
    free_cf = pd.to_numeric(_pick(df, ["Free Cash Flow", "freeCashflow"]), errors="coerce")
    interest_expense = pd.to_numeric(_pick(df, ["Interest Expense", "Interest Expense Non Operating"]), errors="coerce").abs()
    inventory = pd.to_numeric(_pick(df, ["Inventory"]), errors="coerce")
    dividends_paid = pd.to_numeric(_pick(df, ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividend Paid Cfo"]), errors="coerce").abs()
    repurchase = pd.to_numeric(_pick(df, ["Repurchase Of Capital Stock"]), errors="coerce").abs()
    avg_shares = pd.to_numeric(_pick(df, ["Diluted Average Shares", "Basic Average Shares", "Ordinary Shares Number"]), errors="coerce")
    out["gross_margin_calc"] = _safe_div(gross_profit, revenue)
    out["current_assets"] = current_assets
    out["total_liabilities"] = liabilities
    out["ebitda_margin"] = _safe_div(ebitda, revenue)
    out["operating_margin_calc"] = _safe_div(ebit, revenue)
    out["net_margin_calc"] = _safe_div(net_income, revenue)
    out["roa_calc"] = _safe_div(net_income, assets)
    tax_rate = pd.to_numeric(_pick(df, ["taxRate", "effectiveTaxRate"]), errors="coerce").clip(lower=0, upper=0.6).fillna(0.21)
    invested_capital = out.get("total_equity", pd.Series(np.nan, index=out.index))
    if invested_capital.isna().all():
        invested_capital = assets - liabilities
    invested_capital = invested_capital + total_debt - cash
    out["roic"] = _safe_div(ebit * (1.0 - tax_rate), invested_capital)
    out["asset_turnover"] = _safe_div(revenue, assets)
    out["gpa"] = _safe_div(gross_profit, assets)
    out["debt_assets"] = _safe_div(total_debt, assets)
    out["working_capital_assets"] = _safe_div(current_assets - current_liabilities, assets)
    out["retained_earnings_assets"] = _safe_div(retained_earnings, assets)
    out["ebit_assets"] = _safe_div(ebit, assets)
    out["sales_assets"] = _safe_div(revenue, assets)
    out["market_value_liabilities"] = _safe_div(out["market_cap"], liabilities)
    out["ocf_net_income"] = _safe_div(operating_cf, net_income.abs())
    out["fcf_yield"] = _safe_div(free_cf, out["market_cap"])
    out["p_cf"] = _safe_div(out["market_cap"], operating_cf.abs())
    out["cash_debt"] = _safe_div(cash, total_debt)
    out["ev_ebit"] = _safe_div(out["enterprise_value"], ebit)
    out["interest_coverage"] = _safe_div(ebit, interest_expense)
    out["debt_ebitda"] = _safe_div(total_debt, ebitda)
    out["payout_ratio"] = _safe_div(dividends_paid, net_income.abs())
    out["net_payout_yield"] = _safe_div(dividends_paid + repurchase, out["market_cap"])
    out["accruals_assets"] = _safe_div(net_income - operating_cf, assets)
    out["inventory_assets"] = _safe_div(inventory, assets)
    out["shares_from_statements"] = avg_shares
    out["earnings_yield"] = _safe_div(pd.Series(1.0, index=out.index), out["trailing_pe"])
    growth = _fundamental_growth_metrics(symbols, as_of_date)
    if not growth.empty:
        out = out.join(growth.reindex(out.index), how="left")
    out["valuation_percentile"] = (
        rank_pct(out["earnings_yield"]) * 0.35
        + rank_pct(out["fcf_yield"]) * 0.25
        + rank_pct(out["pb_ratio"], higher_better=False) * 0.2
        + rank_pct(out["ev_ebitda"], higher_better=False) * 0.2
    )
    out["quality_percentile"] = (
        rank_pct(out["roe"].fillna(out["roa_calc"])) * 0.3
        + rank_pct(out["gpa"]) * 0.25
        + rank_pct(out["debt_assets"], higher_better=False) * 0.2
        + rank_pct(out["ocf_net_income"]) * 0.15
        + rank_pct(out["gross_margin"].fillna(out["gross_margin_calc"])) * 0.1
    )
    return out.reset_index(drop=True).replace([np.inf, -np.inf], np.nan)


def _fundamental_growth_metrics(symbols: list[str], as_of_date: Any | None = None) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        hist = fundamental_history(symbol)
        if as_of_date and not hist.empty and "reportDate" in hist:
            cutoff = pd.to_datetime(as_of_date, errors="coerce")
            if pd.notna(cutoff):
                hist = hist[pd.to_datetime(hist["reportDate"], errors="coerce") <= cutoff]
        if hist.empty:
            rows.append({"ticker": symbol})
            continue
        revenue = pd.to_numeric(_pick(hist, ["Total Revenue", "totalRevenue", "revenue"]), errors="coerce")
        eps = pd.to_numeric(_pick(hist, ["Diluted EPS", "Basic EPS"]), errors="coerce")
        ebit = pd.to_numeric(_pick(hist, ["EBIT", "Operating Income", "operatingIncome"]), errors="coerce")
        assets = pd.to_numeric(_pick(hist, ["Total Assets", "totalAssets"]), errors="coerce")
        row = {"ticker": symbol}
        if revenue.dropna().shape[0] >= 2:
            row["revenue_growth_yoy"] = revenue.dropna().iloc[-1] / revenue.dropna().iloc[-2] - 1
        if eps.dropna().shape[0] >= 2:
            row["eps_growth_yoy"] = eps.dropna().iloc[-1] / abs(eps.dropna().iloc[-2] or np.nan) - 1
        if revenue.dropna().shape[0] >= 4:
            start, end = revenue.dropna().iloc[-4], revenue.dropna().iloc[-1]
            row["revenue_growth_3y_cagr"] = (end / start) ** (1 / 3) - 1 if start and start > 0 and end > 0 else np.nan
        if ebit.dropna().shape[0] >= 4 and assets.dropna().shape[0] >= 4:
            roc = ebit / assets.replace(0, np.nan)
            row["roc_5y_avg_proxy"] = roc.dropna().tail(20).mean()
            row["ebit_ev_5y_avg_proxy"] = ebit.dropna().tail(20).mean()
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).set_index("ticker")
    out.index = out.index.map(str)
    return out


def metric_panel(payload: dict | None, symbols: list[str] | None = None) -> pd.DataFrame:
    payload = payload or {}
    symbols = symbols or parse_symbols(payload, default_limit=int(payload.get("default_limit") or 500))
    lookback = int(payload.get("lookback_days") or 756)
    tech = latest_technical_features(symbols, lookback_days=lookback, periods=payload)
    dropped = tech.attrs.get("dropped_symbols", [])
    fund = latest_fundamental_features(symbols, payload.get("as_of_date"))
    if tech.empty:
        panel = fund
    else:
        panel = tech.merge(fund, on="ticker", how="left", suffixes=("", "_fund"), validate="one_to_one")
    if "ticker" in panel.columns and panel["ticker"].duplicated().any():
        dupes = panel.loc[panel["ticker"].duplicated(), "ticker"].astype(str).unique().tolist()[:10]
        raise ValueError(f"Duplicate ticker rows after metric panel merge: {dupes}")
    panel.attrs["dropped_symbols"] = dropped
    panel.attrs["dropped_symbol_count"] = len(dropped)
    if panel.empty:
        return panel
    panel["industry_group"] = add_industry_group(panel, industry_col="industry") if "industry" in panel.columns else "Unclassified"
    ff = load_factor_returns()
    if not ff.empty:
        latest_factors = ff.tail(1).iloc[0].to_dict()
        for key in ["mkt_rf", "smb", "hml", "rmw", "cma", "mom", "rf"]:
            if key in latest_factors:
                panel[key] = latest_factors[key]
    panel["liquidity_percentile"] = rank_pct(panel.get("dollar_volume_20d", pd.Series(index=panel.index)))
    panel["size_percentile"] = rank_pct(panel.get("market_cap", pd.Series(index=panel.index)))
    panel["momentum_percentile"] = rank_pct(panel.get("momentum_jt", pd.Series(index=panel.index)))
    panel["low_vol_percentile"] = rank_pct(panel.get("realized_vol_63d", pd.Series(index=panel.index)), higher_better=False)
    panel["prox52_percentile"] = rank_pct(panel.get("prox52", pd.Series(index=panel.index)))
    if "trailing_pe" in panel:
        positive_pe = pd.to_numeric(panel["trailing_pe"], errors="coerce").where(lambda s: s > 0)
        panel["pe_percentile"] = rank_pct(positive_pe, higher_better=False)
        panel["pe_sector_percentile"] = positive_pe.groupby(panel["sector"]).rank(pct=True, ascending=False) * 100.0 if "sector" in panel else panel["pe_percentile"]
    panel["core_quant_score"] = (
        panel["valuation_percentile"].fillna(50) * 0.25
        + panel["quality_percentile"].fillna(50) * 0.25
        + panel["momentum_percentile"].fillna(50) * 0.25
        + panel["low_vol_percentile"].fillna(50) * 0.15
        + panel["liquidity_percentile"].fillna(50) * 0.10
    )
    panel["sector_relative_score"] = panel.groupby("sector")["core_quant_score"].transform(lambda s: rank_pct(s)) if "sector" in panel.columns else rank_pct(panel["core_quant_score"])
    panel["industry_group_relative_score"] = panel.groupby("industry_group")["core_quant_score"].transform(lambda s: rank_pct(s)) if "industry_group" in panel.columns else rank_pct(panel["core_quant_score"])
    panel["industry_relative_score"] = panel.groupby("industry")["core_quant_score"].transform(lambda s: rank_pct(s)) if "industry" in panel.columns else rank_pct(panel["core_quant_score"])
    for col in [
        "valuation_percentile",
        "quality_percentile",
        "momentum_percentile",
        "low_vol_percentile",
        "liquidity_percentile",
    ]:
        if col in panel.columns:
            panel[f"sector_relative_{col}"] = panel.groupby("sector")[col].transform(lambda s: rank_pct(s)) if "sector" in panel.columns else rank_pct(panel[col])
            panel[f"industry_group_relative_{col}"] = panel.groupby("industry_group")[col].transform(lambda s: rank_pct(s)) if "industry_group" in panel.columns else rank_pct(panel[col])
            panel[f"industry_relative_{col}"] = panel.groupby("industry")[col].transform(lambda s: rank_pct(s)) if "industry" in panel.columns else rank_pct(panel[col])
    panel["rank"] = panel["core_quant_score"].rank(ascending=False, method="first").astype(int)
    return panel.sort_values(["core_quant_score", "dollar_volume_20d"], ascending=False).reset_index(drop=True)


def _range_filter(df: pd.DataFrame, col: str, min_value: Any = None, max_value: Any = None) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    if col not in df.columns:
        return mask
    numeric = pd.to_numeric(df[col], errors="coerce")
    lo = number_like(min_value)
    hi = number_like(max_value)
    if lo is not None:
        mask &= numeric >= lo
    if hi is not None:
        mask &= numeric <= hi
    return mask


def apply_filters(panel: pd.DataFrame, payload: dict | None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    payload = payload or {}
    if panel.empty:
        return panel, []
    payload = dict(payload)
    preset = str(payload.get("dollar_volume_preset") or "").lower()
    if preset and "dollar_volume_min" not in payload:
        preset_map = {
            "micro": 250_000,
            "small": 1_000_000,
            "institutional": 10_000_000,
            "large": 25_000_000,
            "very_liquid": 100_000_000,
        }
        if preset in preset_map:
            payload["dollar_volume_min"] = preset_map[preset]
    stages: list[dict[str, Any]] = [{"stage": "Initial universe", "remaining": int(len(panel)), "removed": 0}]
    filtered = panel.copy()

    def apply(stage: str, mask: pd.Series) -> None:
        nonlocal filtered
        before = len(filtered)
        filtered = filtered[mask.reindex(filtered.index).fillna(True)]
        stages.append({"stage": stage, "remaining": int(len(filtered)), "removed": int(before - len(filtered))})

    sectors = payload.get("sectors") or payload.get("sector")
    if sectors and str(sectors).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (sectors if isinstance(sectors, list) else re.split(r"[,;]", str(sectors))) if str(s).strip()}
        apply("Sector filter", filtered["sector"].astype(str).str.lower().isin(allowed))
    industries = payload.get("industries") or payload.get("industry")
    if industries and str(industries).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (industries if isinstance(industries, list) else re.split(r"[,;]", str(industries))) if str(s).strip()}
        apply("Industry filter", filtered["industry"].astype(str).str.lower().isin(allowed))
    industry_groups = payload.get("industry_groups") or payload.get("industry_group")
    if industry_groups and str(industry_groups).lower() not in {"all", "any"} and "industry_group" in filtered:
        allowed = {str(s).strip().lower() for s in (industry_groups if isinstance(industry_groups, list) else re.split(r"[,;]", str(industry_groups))) if str(s).strip()}
        apply("Industry group filter", filtered["industry_group"].astype(str).str.lower().isin(allowed))
    for col, lo_key, hi_key, label in [
        ("market_cap", "market_cap_min", "market_cap_max", "Market cap"),
        ("price", "price_min", "price_max", "Price"),
        ("dollar_volume_20d", "dollar_volume_min", "dollar_volume_max", "Dollar volume"),
        ("trailing_pe", "pe_min", "pe_max", "P/E"),
        ("roic", "roic_min", "roic_max", "ROIC"),
        ("bollinger_width_percentile", "bollinger_width_percentile_min", "bollinger_width_percentile_max", "Bollinger width percentile"),
        ("prox52_percentile", "prox52_percentile_min", "prox52_percentile_max", "PROX52 percentile"),
        ("pb_ratio", "pb_min", "pb_max", "P/B"),
        ("forward_pe", "forward_pe_min", "forward_pe_max", "Forward P/E"),
        ("p_cf", "p_cf_min", "p_cf_max", "P/CF"),
        ("ev_ebit", "ev_ebit_min", "ev_ebit_max", "EV/EBIT"),
        ("interest_coverage", "interest_coverage_min", "interest_coverage_max", "Interest coverage"),
        ("revenue_growth_yoy", "revenue_growth_yoy_min", "revenue_growth_yoy_max", "Revenue growth YoY"),
        ("eps_growth_yoy", "eps_growth_yoy_min", "eps_growth_yoy_max", "EPS growth YoY"),
        ("revenue_growth_3y_cagr", "revenue_growth_3y_cagr_min", "revenue_growth_3y_cagr_max", "Revenue 3Y CAGR"),
        ("debt_ebitda", "debt_ebitda_min", "debt_ebitda_max", "Debt/EBITDA"),
        ("payout_ratio", "payout_ratio_min", "payout_ratio_max", "Payout ratio"),
        ("roe", "roe_min", "roe_max", "ROE"),
        ("debt_equity", "debt_equity_min", "debt_equity_max", "Debt/equity"),
        ("shares_outstanding", "shares_outstanding_min", "shares_outstanding_max", "Shares outstanding"),
        ("float_percent", "float_percent_min", "float_percent_max", "Float percent"),
        ("atr_pct_price", "atr_pct_min", "atr_pct_max", "ATR %"),
        ("adx_14", "adx_min", "adx_max", "ADX"),
        ("stochastic_k", "stochastic_min", "stochastic_max", "Stochastic"),
        ("williams_r", "williams_r_min", "williams_r_max", "Williams %R"),
        ("ivol_ff3_63d", "ivol_min", "ivol_max", "FF3 IVOL"),
        ("max_1d_return_21d", "max_factor_min", "max_factor_max", "MAX factor"),
        ("prox52", "prox52_min", "prox52_max", "PROX52"),
        ("pct_from_52w_high", "high_proximity_min", "high_proximity_max", "52W high proximity"),
        ("vratio", "vratio_min", "vratio_max", "Volume ratio"),
        ("vol_forecast_21d", "vol_forecast_min", "vol_forecast_max", "Vol forecast"),
        ("amihud_percentile", "amihud_percentile_min", "amihud_percentile_max", "Amihud percentile"),
        ("core_quant_score", "score_min", "score_max", "Quant score"),
    ]:
        if lo_key not in payload and hi_key not in payload:
            continue
        mask = _range_filter(filtered, col, payload.get(lo_key), payload.get(hi_key))
        if not mask.all():
            apply(label, mask)
    exchanges = payload.get("exchange") or payload.get("exchanges")
    if exchanges and "exchange" in filtered.columns and str(exchanges).lower() not in {"all", "any"}:
        allowed = {str(s).strip().lower() for s in (exchanges if isinstance(exchanges, list) else re.split(r"[,;]", str(exchanges))) if str(s).strip()}
        apply("Exchange", filtered["exchange"].astype(str).str.lower().isin(allowed))
    if payload.get("dividend_paying_only"):
        apply("Dividend payers", pd.to_numeric(filtered.get("dividend_yield", 0), errors="coerce").fillna(0) > 0)
    if payload.get("exclude_negative_pe") and "trailing_pe" in filtered:
        apply("Negative P/E exclusion", pd.to_numeric(filtered["trailing_pe"], errors="coerce") > 0)
    if payload.get("exclude_penny_stocks", True):
        apply("Penny stock exclusion", pd.to_numeric(filtered.get("price", 0), errors="coerce").fillna(0) >= 1.0)
    if payload.get("sma_bullish_only"):
        apply("SMA bullish", pd.to_numeric(filtered.get("sma50_above_sma200", 0), errors="coerce").fillna(0) > 0)
    if payload.get("golden_cross_within_n_days"):
        n_days = max(1, int(payload.get("golden_cross_within_n_days")))
        apply("Golden cross recent", pd.to_numeric(filtered.get("golden_cross_age_days", np.nan), errors="coerce").le(n_days))
    if payload.get("death_cross_within_n_days"):
        n_days = max(1, int(payload.get("death_cross_within_n_days")))
        apply("Death cross recent", pd.to_numeric(filtered.get("death_cross_age_days", np.nan), errors="coerce").le(n_days))
    if payload.get("macd_bullish_only"):
        apply("MACD bullish", pd.to_numeric(filtered.get("macd_bullish", 0), errors="coerce").fillna(0) > 0)
    if payload.get("obv_positive_only"):
        apply("OBV positive", pd.to_numeric(filtered.get("obv_20d_slope", 0), errors="coerce").fillna(0) > 0)
    return filtered.reset_index(drop=True), stages


def top_table(panel: pd.DataFrame, n: int = DEFAULT_TOP_N) -> pd.DataFrame:
    cols = [
        "rank",
        "ticker",
        "company_name",
        "sector",
        "industry_group",
        "industry",
        "exchange",
        "price",
        "market_cap",
        "shares_outstanding",
        "float_percent",
        "dollar_volume_20d",
        "vratio",
        "core_quant_score",
        "valuation_percentile",
        "quality_percentile",
        "momentum_percentile",
        "low_vol_percentile",
        "trailing_pe",
        "forward_pe",
        "pb_ratio",
        "ps_ratio",
        "p_cf",
        "ev_ebit",
        "ev_ebitda",
        "roe",
        "revenue_growth_yoy",
        "eps_growth_yoy",
        "interest_coverage",
        "return_6m",
        "prox52",
        "beta_252",
        "beta_universe_proxy",
        "beta_effective",
        "beta_effective_source",
        "beta_252_unavailable_reason",
        "realized_vol_63d",
        "atr_pct_price",
        "adx_14",
        "macd_histogram",
        "bollinger_pct_b",
        "amihud_percentile",
    ]
    keep = [c for c in cols if c in panel.columns]
    return panel[keep].head(n).copy()


def heatmap_view(panel: pd.DataFrame, metric: str = "core_quant_score") -> list[dict[str, Any]]:
    if panel.empty or metric not in panel.columns:
        return []
    grouped = (
        panel.groupby("sector", dropna=False)
        .agg(value=(metric, "mean"), count=("ticker", "count"), median_market_cap=("market_cap", "median"), total_market_cap=("market_cap", "sum"))
        .reset_index()
        .sort_values("value", ascending=False)
    )
    return [
        {"row": "Sector", "col": str(r["sector"]), "value": float(r["value"]), "size": number_like(r["total_market_cap"]), "metric": metric, "count": int(r["count"]), "median_market_cap": number_like(r["median_market_cap"])}
        for _, r in grouped.iterrows()
    ]


def quick_look(panel: pd.DataFrame, ticker: str | None = None, price_history_days: int = 2520) -> dict[str, Any]:
    if panel.empty:
        return {}
    symbol = ticker.upper() if ticker else str(panel.iloc[0]["ticker"])
    row = panel[panel["ticker"].eq(symbol)]
    if row.empty:
        row = panel.head(1)
        symbol = str(row.iloc[0]["ticker"])
    r = row.iloc[0].to_dict()
    prices = close_matrix([symbol], lookback_days=price_history_days)
    chart_series = []
    if not prices.empty and symbol in prices.columns:
        chart_series = [{"date": d.strftime("%Y-%m-%d"), "close": float(v)} for d, v in prices[symbol].dropna().items()]
    windows = {"1M": 21, "3M": 63, "1Y": 252, "3Y": 756, "10Y": 2520}
    chart_windows = {label: chart_series[-n:] for label, n in windows.items() if chart_series}
    return clean_json(
        {
            "ticker": r.get("ticker"),
            "sector": r.get("sector"),
            "score": r.get("core_quant_score"),
            "valuation": r.get("valuation_percentile"),
            "quality": r.get("quality_percentile"),
            "momentum": r.get("momentum_percentile"),
            "low_vol": r.get("low_vol_percentile"),
            "price": r.get("price"),
            "market_cap": r.get("market_cap"),
            "thesis": _thesis_line(r),
            "chart_full": chart_series,
            "chart_windows": chart_windows,
        }
    )


def _thesis_line(row: dict[str, Any]) -> str:
    parts = []
    for key, label in [
        ("valuation_percentile", "valuation"),
        ("quality_percentile", "quality"),
        ("momentum_percentile", "momentum"),
        ("low_vol_percentile", "low-vol"),
    ]:
        v = number_like(row.get(key))
        if v is not None and v >= 70:
            parts.append(f"strong {label}")
        elif v is not None and v <= 30:
            parts.append(f"weak {label}")
    return ", ".join(parts[:3]) or "balanced cross-sectional profile"


class FormulaError(ValueError):
    pass


@dataclass
class FormulaResult:
    values: pd.Series
    diagnostics: list[dict[str, Any]]


class FormulaEngine:
    def __init__(self, panel: pd.DataFrame):
        self.panel = panel
        self.names = {self._sanitize(c): c for c in panel.columns}
        self.diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _sanitize(name: str) -> str:
        return re.sub(r"[^0-9a-zA-Z_]", "_", str(name)).lower()

    def eval(self, expression: str) -> FormulaResult:
        expr = (expression or "core_quant_score").replace("^", "**")
        expr = re.sub(r"\bif\s*\(", "where(", expr)
        try:
            tree = ast.parse(expr, mode="eval")
            values = self._node(tree.body)
        except Exception as exc:
            raise FormulaError(str(exc)) from exc
        if not isinstance(values, pd.Series):
            values = pd.Series(float(values), index=self.panel.index)
        values = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return FormulaResult(values=values, diagnostics=self.diagnostics)

    def _node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            key = self._sanitize(node.id)
            if key not in self.names:
                raise FormulaError(f"Unknown field '{node.id}'")
            return pd.to_numeric(self.panel[self.names[key]], errors="coerce")
        if isinstance(node, ast.UnaryOp):
            val = self._node(node.operand)
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return val
        if isinstance(node, ast.BinOp):
            left, right = self._node(node.left), self._node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                denominator = right.replace(0, np.nan) if isinstance(right, pd.Series) else right
                if not isinstance(denominator, pd.Series) and denominator == 0:
                    raise FormulaError("Division by zero")
                return left / denominator
            if isinstance(node.op, ast.Pow):
                return left ** right
        if isinstance(node, ast.Compare):
            left = self._node(node.left)
            result = pd.Series(True, index=self.panel.index)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._node(comparator)
                if isinstance(op, ast.Gt):
                    result &= left > right
                elif isinstance(op, ast.GtE):
                    result &= left >= right
                elif isinstance(op, ast.Lt):
                    result &= left < right
                elif isinstance(op, ast.LtE):
                    result &= left <= right
                elif isinstance(op, ast.Eq):
                    result &= left == right
                elif isinstance(op, ast.NotEq):
                    result &= left != right
                else:
                    raise FormulaError("Unsupported comparator")
                left = right
            return result.astype(float)
        if isinstance(node, ast.BoolOp):
            vals = [self._node(v).astype(bool) for v in node.values]
            result = vals[0]
            for val in vals[1:]:
                result = result & val if isinstance(node.op, ast.And) else result | val
            return result.astype(float)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id.lower()
            if name in {"lag", "rolling_mean", "rolling_std", "rolling_max", "rolling_min"}:
                field_name = node.args[0].id if node.args and isinstance(node.args[0], ast.Name) else None
                if field_name is None:
                    raise FormulaError(f"{name}() requires a field name as its first argument")
                if len(node.args) > 1 and not isinstance(node.args[1], ast.Constant):
                    raise FormulaError(f"{name}() period must be a numeric constant")
                if field_name and self._sanitize(field_name) not in self.names:
                    tickers = list(self.panel["ticker"]) if "ticker" in self.panel.columns else []
                    matrix = self._field_time_matrix(field_name, tickers, int(number_like(node.args[1].value) or 1) if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else 1)
                    current = matrix.iloc[-1].reindex(tickers).reset_index(drop=True).set_axis(self.panel.index) if matrix is not None and not matrix.empty else pd.Series(0.0, index=self.panel.index)
                    args = [current] + [self._node(a) for a in node.args[1:]]
                else:
                    args = [self._node(a) for a in node.args]
                return self._time_series_call(name, field_name, args)
            args = [self._node(a) for a in node.args]
            return self._call(name, args)
        raise FormulaError(f"Unsupported expression node {type(node).__name__}")

    def _call(self, name: str, args: list[Any]) -> Any:
        if name == "rank":
            return rank_pct(args[0])
        if name == "zscore":
            return zscore(args[0])
        if name == "abs":
            return args[0].abs() if isinstance(args[0], pd.Series) else abs(args[0])
        if name == "log":
            if isinstance(args[0], pd.Series):
                return np.log(args[0].where(args[0] > 0))
            value = number_like(args[0])
            if value is None or value <= 0:
                raise FormulaError("log() requires a positive numeric value")
            return math.log(value)
        if name == "sqrt":
            return np.sqrt(args[0])
        if name == "min":
            return pd.concat([self._as_series(a) for a in args], axis=1).min(axis=1)
        if name == "max":
            return pd.concat([self._as_series(a) for a in args], axis=1).max(axis=1)
        if name == "where":
            if len(args) != 3:
                raise FormulaError("where(condition, true_value, false_value) requires three arguments")
            return pd.Series(np.where(self._as_series(args[0]).astype(bool), self._as_series(args[1]), self._as_series(args[2])), index=self.panel.index)
        if name == "sector_rank":
            series = self._as_series(args[0])
            return series.groupby(self.panel["sector"]).rank(pct=True) * 100.0
        if name == "sector_zscore":
            series = self._as_series(args[0])
            return series.groupby(self.panel["sector"]).transform(lambda s: zscore(s))
        raise FormulaError(f"Unsupported function '{name}'")

    def _as_series(self, value: Any) -> pd.Series:
        if isinstance(value, pd.Series):
            return value.reindex(self.panel.index)
        return pd.Series(value, index=self.panel.index)

    def _field_time_matrix(self, field_key: str | None, tickers: list[str], periods: int) -> pd.DataFrame | None:
        if not field_key:
            return None
        lookback = max(periods * 3, 60)
        key = self._sanitize(field_key)
        if key in {"price", "close", "adj_close", "open", "high", "low"}:
            return close_matrix(tickers, lookback_days=lookback)
        horizon = RETURN_HORIZON_FIELDS.get(key)
        if horizon:
            prices = close_matrix(tickers, lookback_days=lookback + horizon + 5)
            if prices.empty:
                return prices
            if key in {"r_jt", "momentum_jt"}:
                return prices.shift(21) / prices.shift(252) - 1.0
            return prices.pct_change(periods=horizon, fill_method=None)
        return None

    def _fundamental_field_series(self, field_key: str, ticker: str) -> pd.Series:
        hist = fundamental_history(ticker)
        if hist.empty or "reportDate" not in hist.columns:
            return pd.Series(dtype=float)
        hist = hist.sort_values("reportDate")
        mapping: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
            "roa": lambda h: _safe_div(_pick(h, ["Net Income", "netIncomeToCommon"]), _pick(h, ["Total Assets", "totalAssets"])),
            "roe": lambda h: _safe_div(_pick(h, ["Net Income", "netIncomeToCommon"]), _pick(h, ["Total Equity", "totalStockholdersEquity"])),
            "current_ratio": lambda h: _safe_div(_pick(h, ["Current Assets", "totalCurrentAssets"]), _pick(h, ["Current Liabilities", "totalCurrentLiabilities"])),
            "debt_equity": lambda h: _safe_div(_pick(h, ["Total Debt", "totalDebt"]), _pick(h, ["Total Equity", "totalStockholdersEquity"])),
            "gross_margin": lambda h: _safe_div(_pick(h, ["Gross Profit", "grossProfit"]), _pick(h, ["Total Revenue", "totalRevenue", "revenue"])),
            "operating_margin": lambda h: _safe_div(_pick(h, ["EBIT", "Operating Income", "operatingIncome"]), _pick(h, ["Total Revenue", "totalRevenue", "revenue"])),
            "mcap": lambda h: pd.to_numeric(_pick(h, ["marketCap", "market_cap", "Market Cap"]), errors="coerce"),
        }
        fn = mapping.get(field_key)
        if fn is None:
            return pd.Series(dtype=float)
        series = pd.to_numeric(fn(hist), errors="coerce")
        series.index = pd.to_datetime(hist["reportDate"], errors="coerce")
        return series.dropna()

    def _time_series_call(self, name: str, field_name: str | None, args: list[Any]) -> pd.Series:
        current = self._as_series(args[0])
        periods = int(number_like(args[1]) or 1) if len(args) > 1 else 1
        tickers = list(self.panel["ticker"]) if "ticker" in self.panel.columns else []
        key = self._sanitize(field_name or "")
        if key in PIT_FUNDAMENTAL_FORMULA_FIELDS:
            values: dict[str, float] = {}
            for ticker in tickers:
                series = self._fundamental_field_series(key, ticker)
                if series.empty:
                    values[ticker] = np.nan
                    continue
                if name == "lag":
                    idx = len(series) - 1 - periods
                    values[ticker] = float(series.iloc[idx]) if 0 <= idx < len(series) else np.nan
                else:
                    window = series.tail(max(1, periods))
                    method = {"rolling_mean": "mean", "rolling_std": "std", "rolling_max": "max", "rolling_min": "min"}[name]
                    values[ticker] = float(getattr(window, method)()) if len(window) else np.nan
            self.diagnostics.append({"level": "ok", "message": f"{name}() evaluated on true PIT fundamental history for '{field_name}' using reported filing periods."})
            return pd.Series(values).reindex(tickers).reset_index(drop=True).set_axis(self.panel.index)
        matrix = self._field_time_matrix(field_name, tickers, periods)
        if matrix is not None and not matrix.empty:
            if name == "lag":
                values = matrix.shift(periods).iloc[-1]
            else:
                method = {"rolling_mean": "mean", "rolling_std": "std", "rolling_max": "max", "rolling_min": "min"}[name]
                values = getattr(matrix.rolling(periods, min_periods=1), method)().iloc[-1]
            self.diagnostics.append({"level": "ok", "message": f"{name}() evaluated on true local time series for {field_name}."})
            return values.reindex(tickers).reset_index(drop=True).set_axis(self.panel.index)
        self.diagnostics.append(
            {
                "level": "warning",
                "message": f"{name}() on '{field_name}' has no true local time-series reconstruction. Exact evaluation currently supports price/OHLC fields, return horizons, momentum_jt, and PIT fundamentals: roa, roe, current_ratio, debt_equity, gross_margin, operating_margin, mcap. Falling back to panel-order approximation.",
            }
        )
        if name == "lag":
            return current.shift(periods).bfill().fillna(0)
        if name == "rolling_mean":
            return current.rolling(periods, min_periods=1).mean()
        if name == "rolling_std":
            return current.rolling(periods, min_periods=2).std().fillna(0)
        if name == "rolling_max":
            return current.rolling(periods, min_periods=1).max()
        if name == "rolling_min":
            return current.rolling(periods, min_periods=1).min()
        return current


def evaluate_formula(panel: pd.DataFrame, expression: str) -> FormulaResult:
    return FormulaEngine(panel).eval(expression)


def formula_templates() -> list[dict[str, str]]:
    return [
        {"name": "Value Momentum Quality", "expression": "0.35*rank(earnings_yield)+0.35*rank(momentum_jt)+0.30*rank(roe)"},
        {"name": "Sector Neutral Value", "expression": "sector_rank(earnings_yield)+0.5*sector_rank(fcf_yield)"},
        {"name": "Low Vol Momentum", "expression": "0.55*rank(momentum_jt)+0.45*rank(-realized_vol_63d)"},
        {"name": "Technical Breakout", "expression": "rank(dist_sma_200)+rank(macd_histogram)+rank(bollinger_pct_b)"},
        {"name": "Quality Balance Sheet", "expression": "rank(roe)+rank(gpa)+rank(interest_coverage)-rank(debt_ebitda)"},
        {"name": "Piotroski Style", "expression": "if(roa>0,1,0)+if(ocf_net_income>1,1,0)+if(current_ratio>1,1,0)+if(gross_margin>0,1,0)"},
        {"name": "Altman Style", "expression": "1.2*working_capital_assets+1.4*retained_earnings_assets+3.3*ebit_assets+0.6*market_value_liabilities+sales_assets"},
        {"name": "Magic Formula", "expression": "rank(earnings_yield)+rank(roic)"},
        {"name": "Acquirers Multiple", "expression": "rank(-ev_ebit)"},
        {"name": "Shareholder Yield", "expression": "rank(net_payout_yield)+rank(dividend_yield)"},
        {"name": "Quality Minus Junk", "expression": "rank(gpa)+rank(roe)+rank(interest_coverage)-rank(debt_ebitda)-rank(realized_vol_63d)"},
        {"name": "Trending Value", "expression": "rank(earnings_yield)+rank(fcf_yield)+rank(momentum_jt)"},
        {"name": "Conservative Formula", "expression": "rank(-realized_vol_63d)+rank(momentum_jt)+rank(net_payout_yield)"},
        {"name": "ERP5", "expression": "rank(earnings_yield)+rank(roic)+rank(roc_5y_avg_proxy)+rank(ebit_ev_5y_avg_proxy)"},
        {"name": "Graham Quality Value", "expression": "rank(-pb_ratio)+rank(current_ratio)+rank(interest_coverage)"},
    ]


def _rolling_ic_ir(panel: pd.DataFrame, field: str, target_field: str = "return_1m", window_quarters: int = 8) -> float | None:
    values = pd.to_numeric(panel.get(field, pd.Series(index=panel.index)), errors="coerce")
    target = pd.to_numeric(panel.get(target_field, pd.Series(index=panel.index)), errors="coerce")
    valid = values.notna() & target.notna()
    if int(valid.sum()) < 15:
        return None
    idx = panel.index[valid]
    rng = np.random.default_rng(17)
    arr_idx = np.array(idx)
    ics = []
    for _ in range(max(2, int(window_quarters) * 2)):
        draw = rng.choice(arr_idx, size=max(10, int(len(arr_idx) * 0.75)), replace=True)
        ic = values.reindex(draw).corr(target.reindex(draw), method="spearman")
        if ic is not None and math.isfinite(ic):
            ics.append(float(ic))
    if not ics:
        return None
    mean_ic = float(np.mean(ics))
    std_ic = float(np.std(ics, ddof=1)) if len(ics) > 1 else None
    return mean_ic / std_ic if std_ic else None


def component_scores(panel: pd.DataFrame, components: list[dict[str, Any]] | dict[str, Any] | None = None) -> pd.DataFrame:
    config = components if isinstance(components, dict) else {}
    preset = str(config.get("preset") or "").lower() if isinstance(config, dict) else ""
    weighting_mode = str(config.get("weighting_mode") or "manual").lower() if isinstance(config, dict) else "manual"
    defaults = [
        {"name": "Value", "field": "valuation_percentile", "weight": 0.25},
        {"name": "Quality", "field": "quality_percentile", "weight": 0.25},
        {"name": "Momentum", "field": "momentum_percentile", "weight": 0.25},
        {"name": "Low Vol", "field": "low_vol_percentile", "weight": 0.15},
        {"name": "Liquidity", "field": "liquidity_percentile", "weight": 0.10},
    ]
    presets = {
        "aqr_quality_value": [{"name": "Value", "field": "valuation_percentile", "weight": 0.50}, {"name": "Quality", "field": "quality_percentile", "weight": 0.50}],
        "momentum_quality": [{"name": "Momentum", "field": "momentum_percentile", "weight": 0.55}, {"name": "Quality", "field": "quality_percentile", "weight": 0.45}],
        "low_vol_quality": [{"name": "Low Vol", "field": "low_vol_percentile", "weight": 0.55}, {"name": "Quality", "field": "quality_percentile", "weight": 0.45}],
        "vmq": [{"name": "Value", "field": "valuation_percentile", "weight": 0.34}, {"name": "Momentum", "field": "momentum_percentile", "weight": 0.33}, {"name": "Quality", "field": "quality_percentile", "weight": 0.33}],
        "ff5_screen": [{"name": "Value", "field": "valuation_percentile", "weight": 0.30}, {"name": "Profitability", "field": "quality_percentile", "weight": 0.30}, {"name": "Investment", "field": "debt_assets", "weight": -0.20}, {"name": "Size", "field": "size_percentile", "weight": -0.20}],
        "conservative_formula": [{"name": "Low Vol", "field": "low_vol_percentile", "weight": 0.35}, {"name": "Momentum", "field": "momentum_percentile", "weight": 0.35}, {"name": "Payout", "field": "net_payout_yield", "weight": 0.30}],
        "trending_value": [{"name": "Value", "field": "valuation_percentile", "weight": 0.50}, {"name": "Momentum", "field": "momentum_percentile", "weight": 0.50}],
    }
    rows = config.get("components") if isinstance(config, dict) else components
    rows = [dict(row) for row in (rows or presets.get(preset) or defaults)]
    target_field = str(config.get("ic_target_field") or "return_1m") if isinstance(config, dict) else "return_1m"
    diagnostics_note = None
    if weighting_mode == "ic_ir":
        computed = {}
        for item in rows:
            field = item.get("field")
            icir = _rolling_ic_ir(panel, field, target_field) if field in panel.columns else None
            computed[item.get("name", field)] = max(icir or 0.0, 0.0)
        total = sum(computed.values()) or 1.0
        for item in rows:
            item["weight"] = computed.get(item.get("name", item.get("field")), 0.0) / total
        diagnostics_note = "IC-IR weights use bootstrap cross-sectional proxy. True walk-forward IC-IR requires stored historical score snapshots."
    elif weighting_mode == "ridge":
        fields = [item.get("field") for item in rows if item.get("field") in panel.columns]
        target = pd.to_numeric(panel.get(target_field, pd.Series(index=panel.index)), errors="coerce")
        valid = target.notna()
        for field in fields:
            valid &= pd.to_numeric(panel[field], errors="coerce").notna()
        if fields and int(valid.sum()) > len(fields) + 5:
            z = np.column_stack([pd.to_numeric(panel.loc[valid, field], errors="coerce").to_numpy() for field in fields])
            z = (z - z.mean(axis=0)) / (z.std(axis=0) + 1e-9)
            y = target.loc[valid].to_numpy()
            lam = float(config.get("ridge_lambda") or 1.0)
            beta = np.linalg.solve(z.T @ z + lam * np.eye(z.shape[1]), z.T @ y)
            beta = np.clip(beta, 0, None)
            total = beta.sum() or 1.0
            by_field = {field: float(weight) for field, weight in zip(fields, beta / total)}
            for item in rows:
                if item.get("field") in by_field:
                    item["weight"] = by_field[item.get("field")]
            diagnostics_note = f"Ridge weights fit current cross-section against {target_field} with lambda={lam}. This is not a walk-forward fit."
        else:
            diagnostics_note = "Ridge weighting requested but insufficient valid observations; configured weights were used."
    out = pd.DataFrame(index=panel.index)
    out["ticker"] = panel["ticker"]
    total_weight = sum(abs(float(r.get("weight", 0))) for r in rows) or 1.0
    out["composite_score"] = 0.0
    decomposition = []
    for item in rows:
        field = item.get("field")
        name = str(item.get("name") or field)
        weight = float(item.get("weight", 0)) / total_weight
        if field not in panel.columns:
            values = pd.Series(50.0, index=panel.index)
        else:
            raw = pd.to_numeric(panel[field], errors="coerce")
            values = raw.fillna(raw.median() if raw.notna().any() else 50.0)
            values = sign_correct(field, values)
            if weight < 0:
                values = -values
                weight = abs(weight)
            if isinstance(config, dict) and config.get("winsorize"):
                values = _winsorize_at_percentiles(values, 1.0, 99.0)
            if isinstance(config, dict) and config.get("sector_neutral") and "sector" in panel.columns:
                values = values - values.groupby(panel["sector"]).transform("median")
            beta_col = "beta_252" if "beta_252" in panel.columns else "beta_spy"
            if isinstance(config, dict) and config.get("beta_neutral") and beta_col in panel.columns:
                values = beta_neutralize(values, pd.to_numeric(panel[beta_col], errors="coerce").fillna(1.0))
            if isinstance(config, dict) and config.get("signed_rank"):
                values = (rank_pct(values) / 50.0) - 1.0
            else:
                values = rank_pct(values)
        out[name] = values
        out["composite_score"] += values * weight
        decomposition.append({"component": name, "field": field, "weight": weight, "mean_score": float(values.mean())})
    out["rank"] = out["composite_score"].rank(ascending=False, method="first").astype(int)
    output_scale = str(config.get("output_scale") or "percentile").lower() if isinstance(config, dict) else "percentile"
    if output_scale in {"zscore", "z", "-3_3"}:
        out["composite_score"] = zscore(out["composite_score"]).clip(-3, 3)
    elif output_scale in {"signed_rank", "signed", "-1_1"}:
        out["composite_score"] = out["composite_score"].rank(pct=True) * 2.0 - 1.0
    else:
        out["composite_score"] = out["composite_score"].rank(pct=True) * 100.0
    out["rank"] = out["composite_score"].rank(ascending=False, method="first").astype(int)
    out.attrs["decomposition"] = decomposition
    out.attrs["weighting_mode"] = weighting_mode
    if diagnostics_note:
        out.attrs["weighting_diagnostics"] = diagnostics_note
    return out.sort_values("composite_score", ascending=False).reset_index(drop=True)


def component_ic_leaderboard(panel: pd.DataFrame, horizon: str = "return_1m", n_boot: int = 16) -> pd.DataFrame:
    fields = ["valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile", "liquidity_percentile", "core_quant_score"]
    rows = []
    target = pd.to_numeric(panel.get(horizon, pd.Series(index=panel.index)), errors="coerce")
    n = len(panel)
    rng = np.random.default_rng(0)
    boot_indices = rng.integers(0, max(1, n), size=(max(1, int(n_boot)), max(1, int(n * 0.8)))) if n else np.empty((0, 0), dtype=int)
    for field in fields:
        values = pd.to_numeric(panel.get(field, pd.Series(index=panel.index)), errors="coerce")
        boot_ics = []
        valid = values.notna() & target.notna()
        if int(valid.sum()) > 10:
            v_arr = values.to_numpy()
            t_arr = target.to_numpy()
            for draw in boot_indices:
                sub_v = v_arr[draw]
                sub_t = t_arr[draw]
                mask = np.isfinite(sub_v) & np.isfinite(sub_t)
                if mask.sum() <= 10:
                    continue
                ic = pd.Series(sub_v[mask]).corr(pd.Series(sub_t[mask]), method="spearman")
                if ic is not None and math.isfinite(ic):
                    boot_ics.append(float(ic))
        ic_series = pd.Series(boot_ics, dtype=float)
        mean_ic = float(ic_series.mean()) if len(ic_series) else None
        ic_vol = float(ic_series.std(ddof=1)) if len(ic_series) > 1 else None
        rows.append(
            {
                "component": field,
                "horizon": horizon,
                "mean_ic": mean_ic,
                "ic_ir": float(mean_ic / ic_vol) if mean_ic is not None and ic_vol not in {None, 0} else None,
                "ic_volatility": ic_vol,
                "bootstrap_windows": int(len(ic_series)),
                "method": "bootstrap_cross_section_proxy",
            }
        )
    out = pd.DataFrame(rows).sort_values("ic_ir", ascending=False, na_position="last")
    out.attrs["note"] = "Bootstrap-resampled cross-sectional IC-IR proxy; true rolling PIT IC-IR requires stored historical score snapshots."
    return out


def score_decomposition_for_ticker(scored: pd.DataFrame, ticker: str | None = None) -> list[dict[str, Any]]:
    if scored.empty:
        return []
    symbol = str(ticker or scored.iloc[0].get("ticker") or "").upper()
    row = scored[scored["ticker"].astype(str).str.upper().eq(symbol)]
    if row.empty:
        row = scored.head(1)
    r = row.iloc[0]
    rows = []
    for item in scored.attrs.get("decomposition", []):
        component = item.get("component")
        if component not in scored.columns:
            continue
        weight = number_like(item.get("weight")) or 0.0
        component_value = number_like(r.get(component))
        if component_value is None:
            continue
        rows.append(
            {
                "ticker": r.get("ticker"),
                "component": component,
                "field": item.get("field"),
                "weight": weight,
                "component_score": component_value,
                "weighted_contribution": component_value * weight,
                "mean_universe_score": item.get("mean_score"),
            }
        )
    return clean_json(sorted(rows, key=lambda x: abs(number_like(x.get("weighted_contribution")) or 0.0), reverse=True))


def effective_num_factors(weights: dict[str, float], corr_matrix: pd.DataFrame) -> float | None:
    if not weights or corr_matrix.empty:
        return None
    fields = [f for f in weights if f in corr_matrix.columns]
    if len(fields) < 2:
        return float(len(fields)) if fields else None
    w = np.array([weights[f] for f in fields], dtype=float)
    sub_corr = corr_matrix.loc[fields, fields].to_numpy(dtype=float)
    n = len(fields)
    off_diag = sub_corr[~np.eye(n, dtype=bool)]
    avg_rho = float(np.nanmean(off_diag)) if len(off_diag) else 0.0
    denominator = float((w**2).sum())
    base = float((w.sum() ** 2) / denominator) if denominator else float(n)
    return float(base / (1.0 + avg_rho)) if (1.0 + avg_rho) else None


def greenblatt_roic(panel: pd.DataFrame, symbols: list[str]) -> pd.Series:
    rows = {}
    for symbol in symbols:
        hist = fundamental_history(symbol)
        if hist.empty:
            rows[symbol] = np.nan
            continue
        latest = pd.DataFrame([hist.iloc[-1]])
        ebit = number_like(_pick(latest, ["EBIT", "Operating Income", "operatingIncome"]).iloc[0])
        current_assets = number_like(_pick(latest, ["Current Assets", "totalCurrentAssets"]).iloc[0])
        current_liabilities = number_like(_pick(latest, ["Current Liabilities", "totalCurrentLiabilities"]).iloc[0])
        cash = number_like(_pick(latest, ["Cash And Cash Equivalents", "totalCash"]).iloc[0]) or 0.0
        total_assets = number_like(_pick(latest, ["Total Assets", "totalAssets"]).iloc[0])
        goodwill = number_like(_pick(latest, ["Goodwill"]).iloc[0]) or 0.0
        intangibles = number_like(_pick(latest, ["Other Intangible Assets", "intangibleAssets"]).iloc[0]) or 0.0
        if None in (ebit, current_assets, current_liabilities, total_assets):
            rows[symbol] = np.nan
            continue
        excess_cash = max(cash - max(0.0, current_liabilities - (current_assets - cash)), 0.0)
        net_working_capital = (current_assets - excess_cash) - current_liabilities
        net_fixed_assets = total_assets - current_assets - goodwill - intangibles
        denominator = net_working_capital + net_fixed_assets
        rows[symbol] = ebit / denominator if denominator else np.nan
    return pd.Series(rows)


def spec_net_payout_yield(panel: pd.DataFrame, symbols: list[str]) -> pd.Series:
    rows = {}
    panel_by_ticker = panel.set_index("ticker") if "ticker" in panel.columns else pd.DataFrame()
    for symbol in symbols:
        hist = fundamental_history(symbol)
        if hist.empty or len(hist) < 2 or symbol not in panel_by_ticker.index:
            rows[symbol] = np.nan
            continue
        current = panel_by_ticker.loc[symbol]
        shares_t = number_like(_pick(pd.DataFrame([hist.iloc[-1]]), ["sharesOutstanding", "Ordinary Shares Number", "Diluted Average Shares"]).iloc[0])
        shares_prior = number_like(_pick(pd.DataFrame([hist.iloc[-2]]), ["sharesOutstanding", "Ordinary Shares Number", "Diluted Average Shares"]).iloc[0])
        price = number_like(current.get("price"))
        market_cap = number_like(current.get("market_cap"))
        dividend_yield = number_like(current.get("dividend_yield")) or 0.0
        if None in (shares_t, shares_prior, price, market_cap) or not market_cap:
            rows[symbol] = np.nan
            continue
        buyback_yield = max(shares_prior - shares_t, 0.0) * price / market_cap
        rows[symbol] = dividend_yield + buyback_yield
    return pd.Series(rows)


def qmj_composite(panel: pd.DataFrame) -> pd.DataFrame:
    idx = panel.index

    def z(col: str) -> pd.Series:
        return zscore(pd.to_numeric(panel.get(col, pd.Series(index=idx)), errors="coerce"))

    profitability = z("gpa") + z("roe") + z("roa_calc") + z("operating_margin_calc") + z("ocf_net_income")
    roa_delta = pd.Series(index=idx, dtype=float)
    if "ticker" in panel.columns:
        for pos, ticker in panel["ticker"].items():
            hist = fundamental_history(ticker)
            if hist.empty or len(hist) < 2:
                roa_delta.loc[pos] = np.nan
                continue
            ni = pd.to_numeric(_pick(hist, ["Net Income", "netIncomeToCommon"]), errors="coerce")
            assets = pd.to_numeric(_pick(hist, ["Total Assets", "totalAssets"]), errors="coerce")
            roa_series = _safe_div(ni, assets.replace(0, np.nan)).dropna()
            roa_delta.loc[pos] = roa_series.iloc[-1] - roa_series.iloc[-2] if len(roa_series) >= 2 else np.nan
    growth = z("revenue_growth_yoy") + z("eps_growth_yoy") + zscore(roa_delta)
    safety = z("beta_252") * -1 + z("ivol_ff3_63d") * -1 + z("amihud_20d") * -1 + z("debt_ebitda") * -1 + z("interest_coverage")
    payout = z("ocf_net_income") + z("payout_ratio") * -1
    out = pd.DataFrame(index=idx)
    out["ticker"] = panel.get("ticker")
    out["qmj_profitability"] = profitability
    out["qmj_growth"] = growth
    out["qmj_safety"] = safety
    out["qmj_payout"] = payout
    out["quality_minus_junk"] = zscore(profitability) + zscore(growth) + zscore(safety) + zscore(payout)
    return out


def momentum_smoothness(symbols: list[str], lookback_days: int = 300) -> pd.Series:
    prices = close_matrix(symbols, lookback_days=max(lookback_days, 280))
    if prices.empty:
        return pd.Series(dtype=float)
    if len(prices) > 273:
        window = prices.iloc[-273:-21]
    elif len(prices) > 21:
        window = prices.iloc[:-21]
    else:
        window = prices
    if window.empty:
        return pd.Series(np.nan, index=prices.columns)
    monthly = window.resample("21D").last().pct_change(fill_method=None).dropna(how="all")
    return (1.0 / monthly.std().replace(0, np.nan)).reindex(symbols)


def dual_momentum(panel: pd.DataFrame) -> pd.Series:
    rf_trailing_252 = risk_free_annual()
    abs_mom = pd.to_numeric(panel.get("return_12m", pd.Series(index=panel.index)), errors="coerce")
    jt_rank = pd.to_numeric(panel.get("momentum_percentile", pd.Series(index=panel.index)), errors="coerce").fillna(0)
    return pd.Series(np.where(abs_mom > rf_trailing_252, jt_rank, 0.0), index=panel.index)


def academic_strategy_scores(panel: pd.DataFrame) -> pd.DataFrame:
    if "ticker" in panel.columns and panel["ticker"].astype(str).duplicated().any():
        dupes = sorted(panel.loc[panel["ticker"].astype(str).duplicated(keep=False), "ticker"].astype(str).unique().tolist())[:10]
        raise ValueError(f"academic_strategy_scores requires one row per ticker; duplicate tickers found: {dupes}")
    out = panel[["ticker", "sector", "industry"]].copy()
    ev_ebitda_rank = rank_pct(panel.get("ev_ebitda", pd.Series(index=panel.index)), higher_better=False)
    ev_ebit_rank = rank_pct(panel.get("ev_ebit", pd.Series(index=panel.index)), higher_better=False)
    pe_rank = rank_pct(panel.get("trailing_pe", pd.Series(index=panel.index)), higher_better=False)
    ps_rank = rank_pct(panel.get("ps_ratio", pd.Series(index=panel.index)), higher_better=False)
    pcf_rank = rank_pct(panel.get("p_cf", pd.Series(index=panel.index)), higher_better=False)
    symbols = list(dict.fromkeys(panel["ticker"].astype(str)))
    roic_series = greenblatt_roic(panel, symbols).reindex(symbols)
    out["greenblatt_roic"] = roic_series.to_numpy()
    roic_rank = rank_pct(pd.Series(out["greenblatt_roic"].to_numpy(), index=panel.index).fillna(panel.get("roa_calc", pd.Series(index=panel.index))))
    out["magic_formula"] = (ev_ebit_rank + roic_rank) / 2
    out["acquirers_multiple"] = ev_ebit_rank.fillna(ev_ebitda_rank)
    out["value_composite_two"] = (ev_ebitda_rank + pe_rank + ps_rank + pcf_rank) / 4
    out["erp5_proxy"] = (ev_ebit_rank + roic_rank + rank_pct(panel.get("roc_5y_avg_proxy", pd.Series(index=panel.index))) + rank_pct(panel.get("ebit_ev_5y_avg_proxy", pd.Series(index=panel.index)))) / 4
    out["deep_value_yield"] = (ev_ebit_rank + rank_pct(panel.get("dividend_yield", pd.Series(index=panel.index)))) / 2
    out["novy_marx_gpa"] = rank_pct(panel.get("gpa", pd.Series(index=panel.index)))
    out["momentum_jt"] = panel.get("momentum_percentile", 50)
    out["low_vol"] = panel.get("low_vol_percentile", 50)
    out["dual_momentum"] = dual_momentum(panel)
    out["twin_momentum"] = (rank_pct(panel.get("revenue_growth_yoy", pd.Series(index=panel.index))) + out["momentum_jt"]) / 2
    mom_smooth = momentum_smoothness(symbols).reindex(symbols)
    mom_smooth_rank = rank_pct(pd.Series(mom_smooth.to_numpy(), index=panel.index))
    out["momentum_smoothness"] = mom_smooth.to_numpy()
    out["quantitative_momentum"] = (out["momentum_jt"] + mom_smooth_rank) / 2
    qmj = qmj_composite(panel)
    out["quality_minus_junk"] = qmj["quality_minus_junk"]
    out["qmj_profitability"] = qmj["qmj_profitability"]
    out["qmj_growth"] = qmj["qmj_growth"]
    out["qmj_safety"] = qmj["qmj_safety"]
    out["qmj_payout"] = qmj["qmj_payout"]
    spec_npy = spec_net_payout_yield(panel, symbols).reindex(symbols)
    out["net_payout_yield_spec"] = spec_npy.to_numpy()
    out["shareholder_yield_proxy"] = rank_pct(pd.Series(out["net_payout_yield_spec"].to_numpy(), index=panel.index).fillna(panel.get("dividend_yield", pd.Series(index=panel.index)).fillna(0) + panel.get("fcf_yield", pd.Series(index=panel.index)).fillna(0)))
    out["meb_faber_shareholder_yield"] = rank_pct(pd.Series(out["net_payout_yield_spec"].to_numpy(), index=panel.index).fillna(panel.get("dividend_yield", pd.Series(index=panel.index)).fillna(0) + panel.get("net_payout_yield", pd.Series(index=panel.index)).fillna(0)))
    out["conservative_formula"] = (out["low_vol"] * 0.35 + out["momentum_jt"] * 0.35 + out["meb_faber_shareholder_yield"] * 0.30)
    out["trending_value"] = out["value_composite_two"] * 0.5 + panel.get("momentum_percentile", 50) * 0.5
    out["sloan_accruals"] = rank_pct(panel.get("accruals_assets", pd.Series(index=panel.index)), higher_better=False)
    out["mohanram_g_score_proxy"] = (
        rank_pct(panel.get("revenue_growth_yoy", pd.Series(index=panel.index)))
        + rank_pct(panel.get("eps_growth_yoy", pd.Series(index=panel.index)))
        + rank_pct(panel.get("gross_margin_calc", pd.Series(index=panel.index)))
        + rank_pct(panel.get("asset_turnover", pd.Series(index=panel.index)))
        + rank_pct(panel.get("accruals_assets", pd.Series(index=panel.index)), higher_better=False)
        + rank_pct(panel.get("realized_vol_63d", pd.Series(index=panel.index)), higher_better=False)
    ) / 6
    net_current_asset_value = pd.to_numeric(panel.get("current_assets", pd.Series(index=panel.index)), errors="coerce") - pd.to_numeric(panel.get("total_liabilities", pd.Series(index=panel.index)), errors="coerce")
    out["graham_net_net"] = (net_current_asset_value > pd.to_numeric(panel.get("market_cap", pd.Series(index=panel.index)), errors="coerce")).astype(float) * 100
    out["high_dividend_low_payout"] = (rank_pct(panel.get("dividend_yield", pd.Series(index=panel.index))) + rank_pct(panel.get("payout_ratio", pd.Series(index=panel.index)), higher_better=False)) / 2
    market_cap = pd.to_numeric(panel.get("market_cap", pd.Series(index=panel.index)), errors="coerce")
    large_cap = market_cap >= market_cap.quantile(0.8) if market_cap.notna().any() else pd.Series(False, index=panel.index)
    dividend_rank = rank_pct(panel.get("dividend_yield", pd.Series(index=panel.index)))
    out["dogs_of_dow"] = dividend_rank.where(large_cap, 0.0)
    out["dogs_of_dow_proxy"] = out["dogs_of_dow"]
    out["interest_coverage_distress"] = rank_pct(panel.get("interest_coverage", pd.Series(index=panel.index)), higher_better=False)
    spec_piotroski = piotroski_criteria_spec(panel, symbols)
    if not spec_piotroski.empty:
        if spec_piotroski["ticker"].astype(str).duplicated().any():
            dupes = sorted(spec_piotroski.loc[spec_piotroski["ticker"].astype(str).duplicated(keep=False), "ticker"].astype(str).unique().tolist())[:10]
            raise ValueError(f"Piotroski spec output must be one row per ticker; duplicate tickers found: {dupes}")
        out = out.merge(spec_piotroski, on="ticker", how="left", validate="one_to_one")
    out["piotroski_f_score_proxy"] = piotroski_score(panel)
    out["piotroski_f_score"] = out.get("piotroski_f_score_spec", out["piotroski_f_score_proxy"]).fillna(out["piotroski_f_score_proxy"])
    criteria = piotroski_criteria(panel)
    for key, val in criteria.items():
        out[f"piotroski_{key}"] = val
    out["altman_z_score"] = altman_z_score(panel)
    out["altman_z_double_prime"] = altman_z_double_prime(panel)
    out["altman_status"] = pd.cut(out["altman_z_score"], bins=[-np.inf, 1.81, 2.99, np.inf], labels=["Distress", "Grey", "Safe"], right=False).astype(str)
    out["altman_piotroski_overlay"] = out["piotroski_f_score"] * 10 + rank_pct(out["altman_z_score"]) * 0.1
    out["best_strategy_score"] = out.drop(columns=["ticker", "sector", "industry", "altman_status"]).select_dtypes(include=[np.number]).max(axis=1)
    out["best_strategy"] = out.drop(columns=["ticker", "sector", "industry", "altman_status"]).select_dtypes(include=[np.number]).idxmax(axis=1)
    return out.sort_values("best_strategy_score", ascending=False).reset_index(drop=True)


def piotroski_score(panel: pd.DataFrame) -> pd.Series:
    criteria = piotroski_criteria(panel)
    return sum(criteria.values()).clip(0, 9)


def piotroski_criteria_spec(panel: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    rows = []
    panel_by_ticker = panel.set_index("ticker") if "ticker" in panel.columns else pd.DataFrame()
    for symbol in symbols:
        row = {"ticker": symbol}
        hist = fundamental_history(symbol)
        if hist.empty or symbol not in panel_by_ticker.index:
            rows.append(row)
            continue
        current = panel_by_ticker.loc[symbol]
        latest = pd.DataFrame([hist.iloc[-1]])
        prior = pd.DataFrame([hist.iloc[-2]]) if len(hist) >= 2 else pd.DataFrame()

        assets_t = number_like(_pick(latest, ["Total Assets", "totalAssets"]).iloc[0])
        assets_prior = number_like(_pick(prior, ["Total Assets", "totalAssets"]).iloc[0]) if not prior.empty else None
        long_term_debt_t = number_like(_pick(latest, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation", "longTermDebt"]).iloc[0])
        long_term_debt_prior = number_like(_pick(prior, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation", "longTermDebt"]).iloc[0]) if not prior.empty else None
        total_debt_t = number_like(_pick(latest, ["Total Debt", "totalDebt"]).iloc[0])
        total_debt_prior = number_like(_pick(prior, ["Total Debt", "totalDebt"]).iloc[0]) if not prior.empty else None
        current_assets_t = number_like(_pick(latest, ["Current Assets", "totalCurrentAssets"]).iloc[0])
        current_assets_prior = number_like(_pick(prior, ["Current Assets", "totalCurrentAssets"]).iloc[0]) if not prior.empty else None
        current_liabilities_t = number_like(_pick(latest, ["Current Liabilities", "totalCurrentLiabilities"]).iloc[0])
        current_liabilities_prior = number_like(_pick(prior, ["Current Liabilities", "totalCurrentLiabilities"]).iloc[0]) if not prior.empty else None
        shares_t = number_like(_pick(latest, ["sharesOutstanding", "Ordinary Shares Number", "Diluted Average Shares"]).iloc[0])
        shares_prior = number_like(_pick(prior, ["sharesOutstanding", "Ordinary Shares Number", "Diluted Average Shares"]).iloc[0]) if not prior.empty else None
        revenue_t = number_like(_pick(latest, ["Total Revenue", "totalRevenue", "revenue"]).iloc[0])
        revenue_prior = number_like(_pick(prior, ["Total Revenue", "totalRevenue", "revenue"]).iloc[0]) if not prior.empty else None
        gross_profit_t = number_like(_pick(latest, ["Gross Profit", "grossProfit"]).iloc[0])
        gross_profit_prior = number_like(_pick(prior, ["Gross Profit", "grossProfit"]).iloc[0]) if not prior.empty else None
        operating_cf_t = number_like(_pick(latest, ["Operating Cash Flow", "operatingCashflow"]).iloc[0])

        roa_t = number_like(current.get("roa_calc"))
        roa_prior = None
        if not prior.empty:
            ni_prior = number_like(_pick(prior, ["Net Income", "netIncomeToCommon"]).iloc[0])
            roa_prior = ni_prior / assets_prior if ni_prior is not None and assets_prior else None
        ocf_assets = operating_cf_t / assets_t if operating_cf_t is not None and assets_t else None
        if long_term_debt_t is not None and long_term_debt_prior is not None:
            leverage_t = long_term_debt_t / assets_t if assets_t else None
            leverage_prior = long_term_debt_prior / assets_prior if assets_prior else None
            leverage_field_used = "long_term_debt"
        else:
            leverage_t = total_debt_t / assets_t if total_debt_t is not None and assets_t else None
            leverage_prior = total_debt_prior / assets_prior if total_debt_prior is not None and assets_prior else None
            leverage_field_used = "total_debt_fallback"
        current_ratio_t = current_assets_t / current_liabilities_t if current_assets_t is not None and current_liabilities_t else None
        current_ratio_prior = current_assets_prior / current_liabilities_prior if current_assets_prior is not None and current_liabilities_prior else None
        gross_margin_t = gross_profit_t / revenue_t if gross_profit_t is not None and revenue_t else None
        gross_margin_prior = gross_profit_prior / revenue_prior if gross_profit_prior is not None and revenue_prior else None
        asset_turnover_t = revenue_t / assets_t if revenue_t is not None and assets_t else None
        asset_turnover_prior = revenue_prior / assets_prior if revenue_prior is not None and assets_prior else None

        tests = {
            "f1_positive_roa": roa_t is not None and roa_t > 0,
            "f2_positive_cfo_assets": ocf_assets is not None and ocf_assets > 0,
            "f3_roa_improving": roa_t is not None and roa_prior is not None and roa_t > roa_prior,
            "f4_cfo_exceeds_roa": ocf_assets is not None and roa_t is not None and ocf_assets > roa_t,
            "f5_leverage_declining": leverage_t is not None and leverage_prior is not None and leverage_t < leverage_prior,
            "f6_liquidity_improving": current_ratio_t is not None and current_ratio_prior is not None and current_ratio_t > current_ratio_prior,
            "f7_no_dilution": shares_t is not None and shares_prior is not None and shares_t <= shares_prior,
            "f8_margin_improving": gross_margin_t is not None and gross_margin_prior is not None and gross_margin_t > gross_margin_prior,
            "f9_turnover_improving": asset_turnover_t is not None and asset_turnover_prior is not None and asset_turnover_t > asset_turnover_prior,
        }
        for key, passed in tests.items():
            row[key] = float(bool(passed))
        row["f5_leverage_field_used"] = leverage_field_used
        row["piotroski_f_score_spec"] = sum(row.get(key, 0.0) for key in tests)
        rows.append(row)
    return pd.DataFrame(rows)


def piotroski_criteria(panel: pd.DataFrame) -> dict[str, pd.Series]:
    idx = panel.index
    criteria = {
        "positive_roa": (pd.to_numeric(panel.get("roa_calc"), errors="coerce") > 0).astype(float),
        "positive_cfo": (pd.to_numeric(panel.get("ocf_net_income"), errors="coerce") > 0).astype(float),
        "positive_margin": (pd.to_numeric(panel.get("operating_margin_calc"), errors="coerce") > 0).astype(float),
        "positive_turnover": (pd.to_numeric(panel.get("asset_turnover"), errors="coerce") > 0).astype(float),
        "low_leverage": (pd.to_numeric(panel.get("debt_assets"), errors="coerce") < panel.get("debt_assets", pd.Series(index=idx)).median()).astype(float),
        "current_ratio_gt_one": (pd.to_numeric(panel.get("current_ratio"), errors="coerce") > 1).astype(float),
        "high_gross_margin": (pd.to_numeric(panel.get("gross_margin_calc"), errors="coerce") > panel.get("gross_margin_calc", pd.Series(index=idx)).median()).astype(float),
        "positive_momentum": (pd.to_numeric(panel.get("return_12m"), errors="coerce") > 0).astype(float),
        "positive_fcf_yield": (pd.to_numeric(panel.get("fcf_yield"), errors="coerce") > 0).astype(float),
    }
    return criteria


def _old_piotroski_score(panel: pd.DataFrame) -> pd.Series:
    score = pd.Series(0, index=panel.index, dtype=float)
    score += (pd.to_numeric(panel.get("roa_calc"), errors="coerce") > 0).astype(float)
    score += (pd.to_numeric(panel.get("ocf_net_income"), errors="coerce") > 0).astype(float)
    score += (pd.to_numeric(panel.get("operating_margin_calc"), errors="coerce") > 0).astype(float)
    score += (pd.to_numeric(panel.get("asset_turnover"), errors="coerce") > 0).astype(float)
    score += (pd.to_numeric(panel.get("debt_assets"), errors="coerce") < panel.get("debt_assets", pd.Series(index=panel.index)).median()).astype(float)
    score += (pd.to_numeric(panel.get("current_ratio"), errors="coerce") > 1).astype(float)
    score += (pd.to_numeric(panel.get("gross_margin_calc"), errors="coerce") > panel.get("gross_margin_calc", pd.Series(index=panel.index)).median()).astype(float)
    score += (pd.to_numeric(panel.get("return_12m"), errors="coerce") > 0).astype(float)
    score += (pd.to_numeric(panel.get("fcf_yield"), errors="coerce") > 0).astype(float)
    return score.clip(0, 9)


def altman_z_score(panel: pd.DataFrame) -> pd.Series:
    components = pd.concat(
        [pd.to_numeric(panel.get(field), errors="coerce") for field in ["working_capital_assets", "retained_earnings_assets", "ebit_assets", "market_value_liabilities", "sales_assets"]],
        axis=1,
    )
    components.columns = ["wc", "re", "ebit", "mv", "sales"]
    score = 1.2 * components["wc"] + 1.4 * components["re"] + 3.3 * components["ebit"] + 0.6 * components["mv"] + components["sales"]
    return score.where(components.notna().all(axis=1))


def altman_z_double_prime(panel: pd.DataFrame) -> pd.Series:
    components = pd.concat(
        [pd.to_numeric(panel.get(field), errors="coerce") for field in ["working_capital_assets", "retained_earnings_assets", "ebit_assets", "market_value_liabilities"]],
        axis=1,
    )
    components.columns = ["wc", "re", "ebit", "mv"]
    score = 6.56 * components["wc"] + 3.26 * components["re"] + 6.72 * components["ebit"] + 1.05 * components["mv"]
    return score.where(components.notna().all(axis=1))


def eligible_at_date(prices: pd.DataFrame, date: Any, min_history_days: int = 252) -> list[str]:
    if prices.empty:
        return []
    if date not in prices.index:
        idx_pos = prices.index.searchsorted(date)
        if idx_pos >= len(prices.index):
            return []
        date = prices.index[idx_pos]
    counts = prices.loc[:date].notna().sum()
    return counts[counts >= min_history_days].index.tolist()


def risk_free_annual() -> float:
    ff = load_factor_returns()
    if ff.empty or "rf" not in ff.columns:
        return 0.0
    rf = pd.to_numeric(ff["rf"], errors="coerce").dropna().tail(TRADING_DAYS)
    return float(rf.mean() * TRADING_DAYS) if len(rf) else 0.0


def sortino_ratio_spec(strategy: pd.Series, annualized_return: float | None, rf_annual: float = 0.0) -> float | None:
    if strategy.empty or annualized_return is None:
        return None
    rf_daily = rf_annual / TRADING_DAYS
    shortfall = (strategy - rf_daily).clip(upper=0)
    downside_var = float((shortfall**2).mean()) * TRADING_DAYS
    if downside_var <= 0:
        return None
    return float((annualized_return - rf_annual) / math.sqrt(downside_var))


def score_backtest(
    symbols: list[str],
    scores: pd.Series,
    lookback_days: int = 756,
    top_n: int = 50,
    cost_bps: float = 10.0,
    long_short: bool = False,
    score_weighted: bool = False,
    rebalance_days: int = 21,
    rebalance_offset_days: int = 0,
    sector_neutral: bool = False,
    sector_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    prices = close_matrix(symbols, lookback_days=lookback_days)
    if prices.empty or scores.empty:
        return {"equity_curve": [], "stats": {}, "rolling": [], "turnover": []}
    ranked = scores.sort_values(ascending=False)
    eligible = set(eligible_at_date(prices, prices.index[0], min_history_days=min(252, max(30, len(prices) // 3))))
    selected = [s for s in ranked.index[: max(1, min(top_n, len(ranked)))] if s in prices.columns and s in eligible]
    if not selected:
        selected = [s for s in prices.columns[: max(1, min(top_n, len(prices.columns)))] if s in eligible] or list(prices.columns[: max(1, min(top_n, len(prices.columns)))])
    returns = prices.pct_change(fill_method=None).fillna(0)
    if rebalance_offset_days:
        returns = returns.iloc[int(rebalance_offset_days):]
    if score_weighted:
        positive_scores = ranked.reindex(selected).clip(lower=0)
        if positive_scores.sum() > 0:
            weights = positive_scores / positive_scores.sum()
            daily = returns[selected].mul(weights, axis=1).sum(axis=1)
        else:
            daily = returns[selected].mean(axis=1)
    else:
        daily = returns[selected].mean(axis=1)
    if sector_neutral and sector_map:
        sector_legs = []
        for _, names in pd.Series(selected).groupby([sector_map.get(s, "Unknown") for s in selected]):
            cols = [s for s in names.tolist() if s in returns.columns]
            if cols:
                sector_legs.append(returns[cols].mean(axis=1))
        if sector_legs:
            daily = pd.concat(sector_legs, axis=1).mean(axis=1)
    short_selected: list[str] = []
    if long_short:
        short_selected = [s for s in ranked.index[-len(selected):] if s in prices.columns]
        if short_selected:
            daily = daily - returns[short_selected].mean(axis=1)
    universe = prices.pct_change(fill_method=None).mean(axis=1).fillna(0)
    cost = float(cost_bps) / 10000.0
    strategy = daily.copy()
    rebalance_step = max(1, int(rebalance_days))
    rebalance_locs = np.arange(0, len(strategy), rebalance_step, dtype=int)
    if len(rebalance_locs):
        strategy.iloc[rebalance_locs] = strategy.iloc[rebalance_locs] - cost
    equity = (1 + strategy).cumprod()
    benchmark = (1 + universe).cumprod()
    drawdown = equity / equity.cummax() - 1
    excess = strategy - universe
    avg_drawdown = drawdown[drawdown < 0].mean()
    years = strategy.groupby(strategy.index.year).apply(lambda s: float((1 + s).prod() - 1)) if len(strategy) else pd.Series(dtype=float)
    position_returns = prices[selected].pct_change(fill_method=None).add(1).prod() - 1 if selected else pd.Series(dtype=float)
    annualized_return = float(equity.iloc[-1] ** (TRADING_DAYS / max(len(equity), 1)) - 1) if len(equity) else None
    ann_vol = float(strategy.std() * math.sqrt(TRADING_DAYS))
    rf_annual = risk_free_annual()
    sharpe = float(((strategy.mean() * TRADING_DAYS) - rf_annual) / (ann_vol or np.nan))
    stats = {
        "selected_count": len(selected),
        "eligible_count": len(eligible),
        "short_count": len(short_selected),
        "long_short": bool(long_short),
        "score_weighted": bool(score_weighted),
        "rebalance_days": int(rebalance_days),
        "rebalance_offset_days": int(rebalance_offset_days),
        "sector_neutral": bool(sector_neutral),
        "total_return": float(equity.iloc[-1] - 1) if len(equity) else None,
        "annualized_return": annualized_return,
        "annualized_vol": ann_vol,
        "risk_free_annual": rf_annual,
        "sharpe": sharpe,
        "sortino": sortino_ratio_spec(strategy, annualized_return, rf_annual),
        "calmar": float((annualized_return or np.nan) / abs(drawdown.min() or np.nan)) if len(equity) else None,
        "max_drawdown": float(drawdown.min()),
        "average_drawdown": float(avg_drawdown) if pd.notna(avg_drawdown) else None,
        "hit_rate": float((position_returns > 0).mean()) if len(position_returns) else None,
        "average_gain": float(position_returns[position_returns > 0].mean()) if len(position_returns[position_returns > 0]) else None,
        "average_loss": float(position_returns[position_returns < 0].mean()) if len(position_returns[position_returns < 0]) else None,
        "best_calendar_year": int(years.idxmax()) if len(years) else None,
        "best_calendar_year_return": float(years.max()) if len(years) else None,
        "worst_calendar_year": int(years.idxmin()) if len(years) else None,
        "worst_calendar_year_return": float(years.min()) if len(years) else None,
        "information_ratio": float(excess.mean() / (excess.std() or np.nan) * math.sqrt(TRADING_DAYS)),
        "survivorship_bias_warning": (
            "This backtest uses currently-listed tickers in the local market universe. Delisted, bankrupt, and merged securities are excluded, "
            "which can inflate results versus a survivorship-bias-corrected backtest. True correction requires delisted-security history not present locally."
        ),
    }
    curve = pd.DataFrame({"date": equity.index, "strategy": equity.values, "benchmark": benchmark.reindex(equity.index).values, "drawdown": drawdown.values})
    rolling = pd.DataFrame(
        {
            "date": strategy.index,
            "rolling_63d_return": (1 + strategy).rolling(63).apply(np.prod, raw=True) - 1,
            "rolling_63d_vol": strategy.rolling(63).std() * math.sqrt(TRADING_DAYS),
            "rolling_63d_sharpe": strategy.rolling(63).mean() / strategy.rolling(63).std() * math.sqrt(TRADING_DAYS),
        }
    ).dropna()
    return {"equity_curve": records(curve), "stats": clean_json(stats), "rolling": records(rolling.tail(250)), "selected": selected, "short_selected": short_selected}


def score_backtest_by_weekday(symbols: list[str], scores: pd.Series, lookback_days: int = 756, top_n: int = 50, cost_bps: float = 10.0) -> list[dict[str, Any]]:
    prices = close_matrix(symbols, lookback_days=int(lookback_days))
    if prices.empty or scores.empty:
        return []
    ranked = scores.sort_values(ascending=False)
    selected = [symbol for symbol in ranked.index[: max(1, min(int(top_n), len(ranked)))] if symbol in prices.columns]
    if not selected:
        return []
    weekday_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}
    rf_annual = risk_free_annual()
    rows = []
    for weekday, label in weekday_names.items():
        rebal_dates = prices.index[prices.index.weekday == weekday]
        if len(rebal_dates) < 4:
            rows.append({"weekday": label, "sharpe": None, "rebalance_count": int(len(rebal_dates))})
            continue
        returns = prices[selected].pct_change(fill_method=None).reindex(rebal_dates).dropna(how="all")
        strategy = returns.mean(axis=1) - (float(cost_bps) / 10000.0) / max(1, len(returns))
        if strategy.empty:
            rows.append({"weekday": label, "sharpe": None, "rebalance_count": int(len(rebal_dates))})
            continue
        annualized_return = float((1 + strategy).prod() ** (52 / max(len(strategy), 1)) - 1)
        annualized_vol = float(strategy.std() * math.sqrt(52))
        sharpe = float((annualized_return - rf_annual) / (annualized_vol or np.nan))
        rows.append({"weekday": label, "sharpe": sharpe if math.isfinite(sharpe) else None, "rebalance_count": int(len(rebal_dates))})
    return clean_json(rows)


def alert_precision_backtest(panel: pd.DataFrame, alert_type_field_map: dict[str, str], forward_days: tuple[int, ...] = (1, 5, 21)) -> list[dict[str, Any]]:
    symbols = list(panel["ticker"].dropna().astype(str)) if "ticker" in panel.columns else []
    prices = close_matrix(symbols, lookback_days=1512)
    if prices.empty:
        return []
    rows = []
    for alert_type, condition_field in alert_type_field_map.items():
        if condition_field == "golden_cross":
            trigger_dates = sma_cross_event(prices.rolling(50).mean(), prices.rolling(200).mean()) == 1
        elif condition_field == "rsi_extreme":
            delta = prices.diff()
            gain = delta.clip(lower=0).apply(lambda col: _wilder_smooth(col, 14))
            loss = (-delta.clip(upper=0)).apply(lambda col: _wilder_smooth(col, 14))
            rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
            trigger_dates = (rsi >= 75) | (rsi <= 25)
        else:
            continue
        hit_rates = {}
        sample_sizes = {}
        for horizon in forward_days:
            forward = prices.shift(-horizon) / prices - 1.0
            triggered = trigger_dates & forward.notna()
            total = int(triggered.to_numpy().sum())
            hits = int(((forward > 0) & triggered).to_numpy().sum())
            hit_rates[f"{horizon}d"] = hits / total if total else None
            sample_sizes[f"{horizon}d"] = total
        rows.append({"alert_type": alert_type, "hit_rates": hit_rates, "sample_sizes": sample_sizes, "method": "same_session_historical_replay"})
    return clean_json(rows)


def regime_performance_from_returns(strategy: pd.Series) -> list[dict[str, Any]]:
    regimes = regime_context()
    if strategy.empty or regimes.empty:
        return []
    df = pd.DataFrame({"date": strategy.index, "strategy_return": strategy.values})
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    regimes = regimes.copy()
    regimes["date"] = pd.to_datetime(regimes["date"]).dt.normalize()
    merged = df.merge(regimes[["date", "regime"]], on="date", how="left").ffill()
    rows = []
    for regime, g in merged.dropna(subset=["regime"]).groupby("regime"):
        r = g["strategy_return"]
        rows.append(
            {
                "regime": regime,
                "days": int(len(r)),
                "annualized_return": float((1 + r).prod() ** (TRADING_DAYS / max(len(r), 1)) - 1),
                "annualized_vol": float(r.std() * math.sqrt(TRADING_DAYS)),
                "sharpe": float(r.mean() / (r.std() or np.nan) * math.sqrt(TRADING_DAYS)),
            }
        )
    return clean_json(rows)


def altman_history(symbol: str, quarters: int = 8) -> list[dict[str, Any]]:
    hist = fundamental_history(symbol)
    if hist.empty or "reportDate" not in hist.columns:
        return []
    rows = []
    for _, item in hist.tail(quarters).iterrows():
        one = pd.DataFrame([item])
        current_assets = pd.to_numeric(_pick(one, ["Current Assets", "totalCurrentAssets"]), errors="coerce")
        current_liabilities = pd.to_numeric(_pick(one, ["Current Liabilities", "totalCurrentLiabilities"]), errors="coerce")
        assets = pd.to_numeric(_pick(one, ["Total Assets", "totalAssets"]), errors="coerce")
        liabilities = pd.to_numeric(_pick(one, ["Total Liabilities Net Minority Interest", "totalLiabilitiesNetMinorityInterest"]), errors="coerce")
        retained = pd.to_numeric(_pick(one, ["Retained Earnings"]), errors="coerce")
        ebit = pd.to_numeric(_pick(one, ["EBIT", "Operating Income", "operatingIncome"]), errors="coerce")
        revenue = pd.to_numeric(_pick(one, ["Total Revenue", "totalRevenue", "revenue"]), errors="coerce")
        market_cap = pd.to_numeric(_pick(one, ["marketCap"]), errors="coerce")
        wc_assets = _safe_div(current_assets - current_liabilities, assets).iloc[0]
        re_assets = _safe_div(retained, assets).iloc[0]
        ebit_assets = _safe_div(ebit, assets).iloc[0]
        mv_liab = _safe_div(market_cap, liabilities).iloc[0]
        sales_assets = _safe_div(revenue, assets).iloc[0]
        z = 1.2 * (wc_assets or 0) + 1.4 * (re_assets or 0) + 3.3 * (ebit_assets or 0) + 0.6 * (mv_liab or 0) + 1.0 * (sales_assets or 0)
        z2 = 6.56 * (wc_assets or 0) + 3.26 * (re_assets or 0) + 6.72 * (ebit_assets or 0) + 1.05 * (mv_liab or 0)
        rows.append({"ticker": symbol, "date": item.get("reportDate"), "altman_z_score": z, "altman_z_double_prime": z2})
    return records(pd.DataFrame(rows))


def fundamental_change_rows(panel: pd.DataFrame, threshold: float = 0.20) -> list[dict[str, Any]]:
    rows = []
    for _, row in panel.iterrows():
        for field in ["revenue_growth_yoy", "eps_growth_yoy"]:
            value = number_like(row.get(field))
            if value is not None and abs(value) > threshold:
                rows.append({"ticker": row.get("ticker"), "type": "FUNDAMENTAL_CHANGE", "metric": field, "value": value, "severity": "medium" if abs(value) < threshold * 2 else "high"})
    return clean_json(rows)


def regime_context() -> pd.DataFrame:
    macro = load_macro()
    if macro.empty:
        return pd.DataFrame()
    df = macro.copy()
    vix_col = next((c for c in ["vix_close", "vixcls"] if c in df.columns), None)
    slope_col = next((c for c in ["yc_slope_10y_2y", "yield_slope"] if c in df.columns), None)
    df["vix"] = pd.to_numeric(df[vix_col], errors="coerce") if vix_col else np.nan
    df["slope"] = pd.to_numeric(df[slope_col], errors="coerce") if slope_col else np.nan
    vix_q = df["vix"].quantile([0.33, 0.66]).to_list() if df["vix"].notna().sum() else [15, 25]
    df["regime"] = np.where(df["vix"] >= vix_q[1], "High Vol", np.where(df["vix"] <= vix_q[0], "Low Vol", "Normal"))
    if slope_col:
        df.loc[df["slope"] < 0, "regime"] = "Inverted Curve"
    return df[["date", "regime", "vix", "slope"]].dropna(subset=["date"]).tail(1500)


def strategy_leaderboard(strategy_df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = _strategy_score_columns(strategy_df)
    rows = []
    for col in numeric_cols:
        values = pd.to_numeric(strategy_df[col], errors="coerce")
        rows.append(
            {
                "strategy": col,
                "avg_score": float(values.mean()),
                "top_decile_count": int((values >= values.quantile(0.9)).sum()) if values.notna().sum() else 0,
                "coverage": float(values.notna().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("avg_score", ascending=False)


def _strategy_score_columns(strategy_df: pd.DataFrame) -> list[str]:
    if strategy_df.empty:
        return []
    explicit_exclude = {
        "altman_z_score",
        "altman_z_double_prime",
        "altman_piotroski_overlay",
        "best_strategy_score",
    }
    prefixes_exclude = (
        "f1_",
        "f2_",
        "f3_",
        "f4_",
        "f5_",
        "f6_",
        "f7_",
        "f8_",
        "f9_",
        "piotroski_",
    )
    suffixes_exclude = ("_proxy", "_spec")
    cols = []
    for col in strategy_df.select_dtypes(include=[np.number]).columns:
        name = str(col)
        if name in explicit_exclude:
            continue
        if name.startswith(prefixes_exclude):
            continue
        if name.endswith(suffixes_exclude):
            continue
        cols.append(name)
    return cols


def _select_strategies_for_backtest(strategy_df: pd.DataFrame, max_strategies: int = 24) -> tuple[list[str], list[str]]:
    eligible = _strategy_score_columns(strategy_df)
    limit = max(1, int(max_strategies or 1))
    selected = eligible[:limit]
    return selected, eligible


def full_strategy_performance_metadata(strategy_df: pd.DataFrame, max_strategies: int = 24) -> dict[str, Any]:
    selected, eligible = _select_strategies_for_backtest(strategy_df, max_strategies)
    return {
        "eligible_strategy_count": len(eligible),
        "evaluated_strategy_count": len(selected),
        "evaluated_strategies": selected,
        "excluded_due_to_limit": eligible[len(selected) :],
        "excluded_helper_patterns": ["f*_criteria", "piotroski_*", "*_proxy", "*_spec", "altman_z_score", "best_strategy_score"],
    }


def full_strategy_performance_table(
    strategy_df: pd.DataFrame,
    lookback_days: int = 756,
    top_n: int = 50,
    max_strategies: int = 24,
) -> list[dict[str, Any]]:
    if strategy_df.empty or "ticker" not in strategy_df:
        return []
    numeric_cols, _eligible = _select_strategies_for_backtest(strategy_df, max_strategies)
    symbols = list(strategy_df["ticker"].dropna().astype(str))
    strategy_by_ticker = strategy_df.set_index("ticker", drop=False)
    rows = []
    for col in numeric_cols:
        scores = pd.to_numeric(strategy_by_ticker[col], errors="coerce").dropna()
        if scores.empty:
            continue
        stats = score_backtest(symbols, scores, lookback_days=int(lookback_days), top_n=int(top_n)).get("stats", {})
        rows.append({"strategy": col, **stats})
    return clean_json(rows)


def compute_turnover_series(
    symbols: list[str],
    scores: pd.Series,
    lookback_days: int = 756,
    top_n: int = 50,
    rebalance_days: int = 21,
) -> list[dict[str, Any]]:
    prices = close_matrix(symbols, lookback_days=int(lookback_days))
    if prices.empty:
        return []
    returns = prices.pct_change(fill_method=None).dropna(how="all")
    if len(returns) < max(30, int(rebalance_days) * 2):
        return []
    static_rank = pd.to_numeric(scores, errors="coerce").reindex(prices.columns)
    prior_selection: set[str] | None = None
    rows = []
    step = max(1, int(rebalance_days))
    for point in range(min(252, len(returns) - 1), len(returns), step):
        window = returns.iloc[max(0, point - 252) : point]
        if window.empty:
            continue
        # Rank drift blends current score with realized 12M momentum, producing a deterministic
        # rebalance-selection path from local price history instead of a static turnover ratio.
        momentum_rank = rank_pct((1 + window).prod() - 1)
        blended = static_rank.rank(pct=True) * 50.0 + momentum_rank.reindex(static_rank.index).fillna(50.0) * 50.0
        selection = set(blended.sort_values(ascending=False).dropna().index[: max(1, int(top_n))])
        if prior_selection is not None and selection:
            replaced = len(prior_selection - selection)
            union = len(prior_selection | selection)
            rows.append(
                {
                    "date": str(pd.Timestamp(returns.index[point]).date()),
                    "turnover": replaced / max(1, len(prior_selection)),
                    "jaccard_turnover": 1.0 - (len(prior_selection & selection) / max(1, union)),
                    "names_replaced": replaced,
                    "selected_count": len(selection),
                    "rebalance_days": step,
                }
            )
        prior_selection = selection
    return clean_json(rows)


def monte_carlo_pbo(
    symbols: list[str],
    scores: pd.Series,
    lookback_days: int = 756,
    top_n: int = 50,
    n_trials: int = 60,
    benchmark_symbol: str = "SPY",
) -> dict[str, Any]:
    prices = close_matrix(list(dict.fromkeys(symbols + [benchmark_symbol])), lookback_days=int(lookback_days))
    if prices.empty or benchmark_symbol not in prices.columns:
        return {"trials": [], "pbo": None, "benchmark_sharpe": None, "reason": "benchmark_unavailable"}
    bench_returns = prices[benchmark_symbol].pct_change(fill_method=None).dropna()
    rf_annual = risk_free_annual()
    bench_vol = bench_returns.std() * math.sqrt(TRADING_DAYS)
    benchmark_sharpe = float(((bench_returns.mean() * TRADING_DAYS) - rf_annual) / (bench_vol or np.nan))
    trials = []
    for trial in range(max(1, int(n_trials))):
        offset = int(np.random.default_rng(trial).integers(0, 21))
        stats = score_backtest(symbols, scores, lookback_days=lookback_days, top_n=top_n, rebalance_offset_days=offset).get("stats", {})
        sharpe = number_like(stats.get("sharpe"))
        if sharpe is not None and math.isfinite(sharpe):
            trials.append({"trial": trial, "rebalance_offset_days": offset, "sharpe": sharpe})
    if not trials:
        return {"trials": [], "pbo": None, "benchmark_sharpe": benchmark_sharpe}
    beat_fraction = sum(1 for row in trials if row["sharpe"] > benchmark_sharpe) / len(trials)
    sharpes = [row["sharpe"] for row in trials]
    return {
        "trials": trials,
        "pbo": 1.0 - beat_fraction,
        "benchmark_sharpe": benchmark_sharpe,
        "sharpe_5th_pct": float(np.percentile(sharpes, 5)),
        "sharpe_95th_pct": float(np.percentile(sharpes, 95)),
    }


def relative_valuation(panel: pd.DataFrame, ticker: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if panel.empty:
        return {"card": {}, "sector_heatmap": [], "peer_table": [], "history": [], "universe_cards": []}
    symbol = (ticker or panel.iloc[0]["ticker"]).upper()
    row = panel[panel["ticker"].eq(symbol)]
    if row.empty:
        row = panel.head(1)
    r = row.iloc[0]
    sector = r.get("sector", "Unknown")
    industry = r.get("industry", "Unknown")
    custom_peers = payload.get("peers") or payload.get("custom_peers")
    if custom_peers:
        peer_symbols = {s.strip().upper() for s in re.split(r"[,;\s]+", str(custom_peers)) if s.strip()}
        peers = panel[panel["ticker"].isin(peer_symbols | {symbol})].copy()
        peer_scope = "custom"
    elif payload.get("peer_scope") == "industry" and "industry" in panel.columns:
        peers = panel[panel["industry"].eq(industry)].copy()
        peer_scope = "industry"
    elif payload.get("peer_scope") == "market_cap_bucket":
        cap = pd.to_numeric(panel["market_cap"], errors="coerce")
        bucket = pd.qcut(cap.rank(method="first"), q=min(5, max(1, cap.notna().sum())), labels=False, duplicates="drop")
        row_bucket = bucket.reindex(row.index).iloc[0]
        peers = panel[bucket.eq(row_bucket)].copy()
        peer_scope = "market_cap_bucket"
    else:
        peers = panel[panel["sector"].eq(sector)].copy()
        peer_scope = "sector"
    metrics = ["trailing_pe", "forward_pe", "pb_ratio", "ps_ratio", "p_cf", "ev_ebit", "ev_ebitda", "fcf_yield"]
    peer_rows = []
    universe_rows = []
    for metric in metrics:
        higher_better = metric in {"fcf_yield"}
        val = number_like(r.get(metric))
        med = number_like(peers[metric].median()) if metric in peers else None
        pct = number_like(rank_pct(peers[metric], higher_better=higher_better).reindex(row.index).iloc[0]) if metric in peers else None
        universe_pct = number_like(rank_pct(panel[metric], higher_better=higher_better).reindex(row.index).iloc[0]) if metric in panel else None
        peer_rows.append({"metric": metric, "ticker_value": val, "peer_median": med, "cheapness_percentile": pct, "vs_peer_median": val - med if val is not None and med is not None else None, "peer_scope": peer_scope})
        universe_rows.append(
            {
                "metric": metric,
                "ticker": r.get("ticker"),
                "ticker_value": val,
                "universe_percentile": universe_pct,
                "universe_median": number_like(panel[metric].median()) if metric in panel else None,
                "universe_coverage": float(panel[metric].notna().mean()) if metric in panel else None,
            }
        )
    history_window = payload.get("history_window")
    history_metric = payload.get("history_metric")
    history_frame = _history_window(fundamental_history(symbol), history_window)
    history_series_rows = own_history_series_from_history(history_frame, history_metric)
    history_percentile = (
        own_history_percentile_blended_from_history(history_frame)
        if not history_metric
        else own_history_percentile_from_series([row.get("valuation_metric") for row in history_series_rows])
    )
    slope_info = re_rating_slope_from_series(history_series_rows)
    card = {
        "ticker": r.get("ticker"),
        "sector": sector,
        "industry": industry,
        "peer_scope": peer_scope,
        "absolute_percentile": r.get("valuation_percentile"),
        "sector_percentile": np.nanmean([x.get("cheapness_percentile") for x in peer_rows if x.get("cheapness_percentile") is not None]),
        "universe_percentile": np.nanmean([x.get("universe_percentile") for x in universe_rows if x.get("universe_percentile") is not None]),
        "own_history_percentile": history_percentile,
        "re_rating_slope": slope_info,
        "momentum_percentile": r.get("momentum_percentile"),
    }
    sector_heat = []
    for sec, g in panel.groupby("sector"):
        for metric in metrics:
            if metric in g.columns:
                sector_heat.append({"row": str(sec), "col": metric, "value": float(rank_pct(g[metric], higher_better=metric in {"fcf_yield"}).mean()), "count": int(len(g)), "median_market_cap": number_like(g["market_cap"].median()) if "market_cap" in g else None})
    universe_cards = []
    for _, item in panel.head(int(payload.get("card_limit") or 100)).iterrows():
        universe_cards.append(
            {
                "ticker": item.get("ticker"),
                "sector": item.get("sector"),
                "absolute_percentile": item.get("valuation_percentile"),
                "momentum_percentile": item.get("momentum_percentile"),
                "price": item.get("price"),
            }
        )
    return {
        "card": clean_json(card),
        "sector_heatmap": clean_json(sector_heat),
        "peer_table": clean_json(peer_rows),
        "universe_table": clean_json(universe_rows),
        "history": clean_json(history_series_rows),
        "universe_cards": clean_json(universe_cards),
    }


def own_history_percentile(symbol: str, metric_name: str | None = None, window: str | int | None = None) -> float | None:
    hist = fundamental_history(symbol)
    if hist.empty:
        return None
    hist = _history_window(hist, window)
    if not metric_name:
        return own_history_percentile_blended_from_history(hist)
    return own_history_percentile_from_series(_own_history_metric_series(hist, metric_name))


def own_history_percentile_from_series(values: Any) -> float | None:
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if len(series) < 4:
        return None
    latest = series.iloc[-1]
    reference = series.iloc[:-1]
    if reference.empty:
        return None
    return float((reference < latest).mean() * 100)


def own_history_percentile_blended_from_history(hist: pd.DataFrame) -> float | None:
    if hist.empty:
        return None
    scores = []
    for metric in _default_valuation_metric_priority():
        score = own_history_percentile_from_series(_own_history_metric_series(hist, metric))
        if score is not None:
            scores.append(score)
    if not scores:
        return None
    return float(np.nanmean(scores))


def own_history_series(symbol: str, metric_name: str | None = None, window: str | int | None = None) -> list[dict[str, Any]]:
    hist = fundamental_history(symbol)
    hist = _history_window(hist, window)
    return own_history_series_from_history(hist, metric_name)


def own_history_series_from_history(hist: pd.DataFrame, metric_name: str | None = None) -> list[dict[str, Any]]:
    if hist.empty or "reportDate" not in hist.columns:
        return []
    metric = pd.to_numeric(_own_history_metric_series(hist, metric_name), errors="coerce")
    df = pd.DataFrame({"date": hist["reportDate"], "valuation_metric": metric, "metric": metric_name or "valuation_blend"})
    df["history_percentile"] = df["valuation_metric"].expanding().apply(lambda x: (x <= x.iloc[-1]).mean() * 100 if len(x.dropna()) else np.nan)
    if len(df.dropna()) >= 4:
        df["trend"] = np.where(df["valuation_metric"].diff(4) > 0, "re-rating", "de-rating")
    else:
        df["trend"] = "insufficient_history"
    return records(df.dropna().tail(80))


def re_rating_slope(symbol: str, metric_name: str | None = None, window: str | int | None = None, trailing_periods: int = 21) -> dict[str, Any]:
    series = own_history_series(symbol, metric_name, window)
    return re_rating_slope_from_series(series, trailing_periods=trailing_periods)


def re_rating_slope_from_series(series: list[dict[str, Any]], trailing_periods: int = 21) -> dict[str, Any]:
    recent = series[-trailing_periods:] if len(series) >= trailing_periods else series
    y = np.array([number_like(r.get("history_percentile")) for r in recent], dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < 3:
        return {"slope_per_period": None, "slope_per_month": None, "interpretation": "insufficient_history"}
    x = np.arange(len(y), dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    return {"slope_per_period": slope, "slope_per_month": slope * 21.0, "interpretation": "re-rating" if slope > 0 else "de-rating" if slope < 0 else "flat"}


def _default_valuation_metric_priority() -> list[str]:
    """Default valuation blend inputs, ordered from most directly comparable to broadest fallback."""
    return ["pe", "pb", "ps", "ev_ebitda", "ev_sales"]


def _own_history_metric_series(hist: pd.DataFrame, metric_name: str | None) -> pd.Series:
    if hist.empty:
        return pd.Series(dtype=float)
    if metric_name:
        return pd.to_numeric(_pick(hist, _valuation_metric_names(metric_name)), errors="coerce")
    frames = []
    for metric in _default_valuation_metric_priority():
        values = pd.to_numeric(_pick(hist, _valuation_metric_names(metric)), errors="coerce")
        if values.notna().sum() >= 4:
            reference = values.expanding().apply(lambda x: (x.dropna() <= x.iloc[-1]).mean() * 100 if x.dropna().shape[0] else np.nan)
            frames.append(reference)
    if not frames:
        return pd.to_numeric(_pick(hist, _valuation_metric_names(None)), errors="coerce")
    return pd.concat(frames, axis=1).mean(axis=1)


def _valuation_metric_names(metric_name: str | None) -> list[str]:
    mapping = {
        "pe": ["trailingPE"],
        "forward_pe": ["forwardPE"],
        "pb": ["priceToBook"],
        "ps": ["priceToSalesTrailing12Months"],
        "ev_ebitda": ["enterpriseToEbitda"],
        "ev_sales": ["enterpriseToRevenue"],
    }
    if metric_name:
        return mapping.get(str(metric_name).lower(), ["trailingPE", "priceToBook", "priceToSalesTrailing12Months"])
    names: list[str] = []
    for metric in _default_valuation_metric_priority():
        names.extend(mapping.get(metric, []))
    return names


def _history_window(hist: pd.DataFrame, window: str | int | None) -> pd.DataFrame:
    if hist.empty or "reportDate" not in hist.columns or not window:
        return hist
    text = str(window).lower()
    years = None
    if text.endswith("y"):
        years = number_like(text[:-1])
    else:
        years = number_like(text)
    if not years:
        return hist
    cutoff = hist["reportDate"].max() - pd.DateOffset(years=int(years))
    return hist[hist["reportDate"] >= cutoff]


def build_export_payload(feature_id: str, payload: dict[str, Any], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cols = list(result_rows[0].keys()) if result_rows else []
    tsv = "\t".join(cols)
    for row in result_rows:
        tsv += "\n" + "\t".join("" if row.get(c) is None else str(row.get(c)) for c in cols)
    csv_text = pd.DataFrame(result_rows).to_csv(index=False) if result_rows else ""
    tickers = [str(row.get("ticker")) for row in result_rows if row.get("ticker")]
    return {
        "feature_id": feature_id,
        "row_count": len(result_rows),
        "columns": cols,
        "tsv_preview": tsv[:5000],
        "tsv": tsv,
        "csv": csv_text,
        "ticker_list": ",".join(tickers),
        "json_payload": {"payload": payload, "rows": result_rows[:1000]},
    }


def access_meta(payload: dict | None = None, issues: list[str] | None = None) -> dict[str, Any]:
    return {
        "compute_mode": (payload or {}).get("compute_mode", "realtime"),
        "data_policy": "read_only_local_parquet",
        "access_issues": issues or [],
    }
