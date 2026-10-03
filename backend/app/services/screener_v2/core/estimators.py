"""Screener V2 estimators computations."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import close_matrix, load_factor_returns, ohlcv_for_symbols, volume_matrix, normalize_symbol
from .stats import TRADING_DAYS, _safe_div, _wilder_smooth, rank_pct


def sma_cross_event(short: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    short_aligned, long_aligned = short.align(long, join="inner", axis=None)
    if short_aligned.empty or long_aligned.empty:
        return pd.DataFrame()
    above = (short_aligned > long_aligned).astype(float).where(short_aligned.notna() & long_aligned.notna())
    return above.diff()


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
    volumes = volumes.reindex(prices.index) if not volumes.empty else pd.DataFrame(index=prices.index, columns=prices.columns)
    highs = _pivot_ohlc_field(raw_ohlcv, "High", prices.index) if not raw_ohlcv.empty else pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    lows = _pivot_ohlc_field(raw_ohlcv, "Low", prices.index) if not raw_ohlcv.empty else pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    opens = _pivot_ohlc_field(raw_ohlcv, "Open", prices.index) if not raw_ohlcv.empty else pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    rets = prices.pct_change(fill_method=None)
    latest = prices.iloc[-1]
    out = pd.DataFrame(index=prices.columns)
    out["ticker"] = out.index
    out["open"] = opens.iloc[-1].reindex(out.index)
    out["high"] = highs.iloc[-1].reindex(out.index)
    out["low"] = lows.iloc[-1].reindex(out.index)
    out["close"] = latest
    out["price"] = latest
    out["volume_today"] = volumes.iloc[-1]
    out["volume"] = out["volume_today"]
    out["volume_20d"] = volumes.tail(20).mean().where(volumes.tail(20).count().eq(20))
    out["volume_spike_ratio"] = _safe_div(out["volume_today"], out["volume_20d"])
    out["vratio"] = out["volume_spike_ratio"]
    out["dollar_volume_20d"] = (volumes * prices).tail(20).mean().where((volumes * prices).tail(20).count().eq(20))
    for days, key in [(1, "return_1d"), (5, "return_1w"), (21, "return_1m"), (63, "return_3m"), (126, "return_6m"), (252, "return_12m")]:
        if len(prices) > days:
            out[key] = prices.iloc[-1] / prices.shift(days).iloc[-1] - 1.0
        else:
            out[key] = np.nan
    if len(prices) > 252:
        out["momentum_jt"] = prices.shift(21).iloc[-1] / prices.shift(252).iloc[-1] - 1.0
    else:
        out["momentum_jt"] = np.nan
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
        valid_cross = prices.iloc[-1].notna() & prices.iloc[-2].notna() & ma_series.iloc[-1].notna() & ma_series.iloc[-2].notna() if len(prices) > 1 else pd.Series(False, index=out.index)
        out[f"crossed_above_sma_{window}_today"] = (above_today & ~above_yesterday).astype(float).where(valid_cross)
        out[f"crossed_below_sma_{window}_today"] = (~above_today & above_yesterday).astype(float).where(valid_cross)
    out["sma20_above_sma50"] = (out["sma_20"] > out["sma_50"]).astype(float).where(out["sma_20"].notna() & out["sma_50"].notna())
    out["sma50_above_sma200"] = (out["sma_50"] > out["sma_200"]).astype(float).where(out["sma_50"].notna() & out["sma_200"].notna())
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
    ema12 = prices.ewm(span=macd_fast, adjust=False, min_periods=macd_fast).mean()
    ema26 = prices.ewm(span=macd_slow, adjust=False, min_periods=macd_slow).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=macd_signal_period, adjust=False, min_periods=macd_signal_period).mean()
    macd_hist = macd - macd_signal
    out["macd"] = macd.iloc[-1]
    out["macd_signal"] = macd_signal.iloc[-1]
    out["macd_histogram"] = macd_hist.iloc[-1]
    out["macd_bullish"] = (out["macd"] > out["macd_signal"]).astype(float).where(out["macd"].notna() & out["macd_signal"].notna())
    out["macd_cross_days"] = macd_hist.tail(20).apply(_last_sign_cross_age)
    bb_mid = prices.rolling(bb_period).mean()
    bb_std = prices.rolling(bb_period).std(ddof=0)
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
    plus_dm = plus_dm.where(up_move.notna() & down_move.notna())
    minus_dm = minus_dm.where(up_move.notna() & down_move.notna())
    atr_dm = tr.apply(lambda col: _wilder_smooth(col, adx_period)).replace(0, np.nan)
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
    signed_volume = np.sign(prices.diff()) * volumes
    obv = signed_volume.cumsum()
    from scipy.stats import linregress
    out["obv_20d_slope"] = obv.tail(20).apply(lambda column: linregress(np.arange(len(column)), column).slope if column.notna().all() and len(column) == 20 else np.nan)
    delta = prices.diff()
    gain = delta.clip(lower=0).apply(lambda col: _wilder_smooth(col, rsi_period))
    loss = (-delta.clip(upper=0)).apply(lambda col: _wilder_smooth(col, rsi_period))
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((gain == 0) & (loss > 0), 0).mask((gain == 0) & (loss == 0), 50)
    out["rsi_14"] = rsi.iloc[-1]
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
    sufficient_history = len(rets) >= 252
    if spy_available and sufficient_history:
        market = rets["SPY"].tail(252)
        var = market.var()
        out["beta_252"] = rets.tail(252).apply(lambda col: col.cov(market)).reindex(out.index) / var if var else np.nan
        complete_beta = rets.tail(252).notna().sum().eq(252) & market.notna().all()
        out["beta_252"] = out["beta_252"].where(complete_beta.reindex(out.index))
        out["beta_252_unavailable_reason"] = np.where(out["beta_252"].notna(), None, "missing returns in 252-session window")
    else:
        out["beta_252"] = np.nan
        out["beta_252_unavailable_reason"] = "insufficient_history" if not sufficient_history else "spy_series_missing"
        out["relative_return_3m_spy"] = np.nan
    if "SPY" in prices.columns and len(prices) > 63:
        spy_return = prices["SPY"].iloc[-1] / prices["SPY"].shift(63).iloc[-1] - 1
        out["relative_return_3m_spy"] = out["return_3m"] - spy_return
    out["amihud_20d"] = (rets.abs().tail(20) / (volumes.tail(20) * prices.tail(20)).replace(0, np.nan)).mean()
    out["amihud_percentile"] = rank_pct(out["amihud_20d"], higher_better=False)
    ff = load_factor_returns()
    out["ivol_ff3_63d"] = _idiosyncratic_vol(rets.tail(63), ff)
    yz_window = 63
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
    yz_complete = pd.concat([log_overnight.tail(63).count(), log_open_close.tail(63).count(), rs_daily.tail(63).count()], axis=1).min(axis=1).eq(63)
    out["yang_zhang_vol_21d_estimate"] = np.sqrt(yz_daily_variance * 21.0).where(yz_complete)
    out["vol_estimate_method"] = "yang_zhang_63d_scaled_21d"
    out["technical_percentile"] = (
        rank_pct(out["momentum_jt"]) * 0.35
        + rank_pct(out["return_6m"]) * 0.2
        + rank_pct(out["dist_sma_200"]) * 0.15
        + rank_pct(out["realized_vol_63d"], higher_better=False) * 0.15
        + rank_pct(out["dollar_volume_20d"]) * 0.15
    )
    out["beta_effective"] = out["beta_252"]
    out["beta_effective_source"] = np.where(out["beta_252"].notna(), "spy_true_beta", "unavailable")
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
    return raw_ohlcv.pivot_table(index="Date", columns="Ticker", values=field, aggfunc="last").sort_index().reindex(index_like)


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
    import statsmodels.api as sm
    required = ["mkt_rf", "smb", "hml", "rf"]
    out = pd.Series(np.nan, index=returns.columns, dtype=float)
    if returns.empty or not set(required).issubset(factors.columns):
        return out
    aligned = factors.set_index("date")[required].reindex(returns.index)
    for ticker in returns:
        frame = pd.concat([returns[ticker].rename("y"), aligned], axis=1).dropna()
        if len(frame) < 63:
            continue
        fit = sm.OLS(frame.y - frame.rf, sm.add_constant(frame[["mkt_rf", "smb", "hml"]])).fit()
        out[ticker] = float(np.sqrt(np.mean(fit.resid ** 2) * TRADING_DAYS))
    return out

