"""ML V2 panel implementation."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable
import base64
import hashlib
import math
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Lasso, Ridge, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from .data_loader import annualization_factor, close_matrix, data_inventory, load_fama_french, load_macro, market_caps, ohlcv_for_symbols, parse_symbols, returns_matrix, sector_map, volume_matrix
from .performance import ThreadPoolExecutor, as_completed, cache_key, cached_ledoit_cov, data_inventory_cached, disk_get, disk_set, equity_from_returns, fast_spearman_ic, max_drawdown, normalize_payload, precompute_date_strings, ridge_fit_fast, sharpe, sortino, vectorized_ic_series, _CONTEXT_CACHE
from .validation import chronological_purged_split, purged_date_folds
from .common import number_like
from .estimators import corwin_schultz_spread, high_low_amihud


@dataclass
class MLContext:
    payload: dict[str, Any]
    symbols: list[str]
    returns: pd.DataFrame
    closes: pd.DataFrame
    volumes: pd.DataFrame
    ohlcv: pd.DataFrame
    sectors: dict[str, str]
    market_caps: dict[str, float]
    frequency: str
    annualization: float
    compute_mode: str



def load_context(payload: dict[str, Any] | None, *, min_symbols: int = 12) -> MLContext:
    payload = payload or {}
    full = str(payload.get("universe") or payload.get("symbols") or "").strip().lower() in {"all", "full", "master", "master_universe", "whole"}
    max_symbols = int(number_like(payload.get("max_symbols") or payload.get("max_tickers"), 120 if not full else 5000) or 120)
    default_limit = max(min_symbols, min(max_symbols, 160 if not full else max_symbols))
    symbols = parse_symbols(payload, default_limit=default_limit, max_symbols=max_symbols)
    lookback = int(number_like(payload.get("lookback_days") or payload.get("window_days") or payload.get("training_window"), 756) or 756)
    frequency = str(payload.get("frequency") or payload.get("sampling_frequency") or "daily")
    rets = returns_matrix(symbols, lookback_days=max(lookback, 90), frequency=frequency)
    if rets.empty:
        raise ValueError("Insufficient price history for the requested symbols")
    symbols = [str(c) for c in rets.columns]
    closes = close_matrix(symbols, lookback_days=max(lookback, 90), frequency=frequency).reindex(columns=symbols)
    volumes = volume_matrix(symbols, lookback_days=max(lookback, 90), frequency=frequency).reindex(columns=symbols)
    ohlcv = ohlcv_for_symbols(symbols, lookback_days=max(lookback, 90), frequency=frequency)
    return MLContext(
        payload=payload,
        symbols=symbols,
        returns=rets,
        closes=closes,
        volumes=volumes,
        ohlcv=ohlcv,
        sectors=sector_map(symbols),
        market_caps=market_caps(symbols),
        frequency=frequency,
        annualization=annualization_factor(frequency),
        compute_mode="research" if payload.get("research_mode") or str(payload.get("compute_mode", "")).lower() == "research" else "realtime",
    )



def load_context_cached(payload: dict[str, Any] | None, *, min_symbols: int = 12) -> MLContext:
    """A29 — Cache MLContext for identical payloads within a request batch.

    Features 01/02/07/08/11/12 all call load_context with the same payload;
    this eliminates 4 data loading operations per duplicate feature call.
    """
    from .performance import cache_key as _ck
    p = payload or {}
    # Contexts contain request-local settings and data; do not share them between runs.
    return load_context(payload, min_symbols=min_symbols)



def _build_ticker_features(
    ticker: str,
    rets: pd.DataFrame,
    closes: pd.DataFrame,
    vols: pd.DataFrame,
    ohlcv: pd.DataFrame,
    sectors: dict[str, str],
    market_caps_: dict[str, float],
    annualization: float,
    horizon: int,
) -> tuple[list[dict[str, Any]], list[float]]:
    r = rets[ticker]
    c = closes[ticker] if ticker in closes else pd.Series(index=rets.index, dtype=float)
    v = vols[ticker] if ticker in vols else pd.Series(index=rets.index, dtype=float)
    fwd = r.shift(-horizon).rolling(horizon).sum()

    log_v = np.log(v.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    volume_z = (log_v - log_v.rolling(21).mean()) / log_v.rolling(21).std().replace(0, np.nan)
    dollar = (c * v).replace(0, np.nan)
    dollar_vol_mom = np.log(dollar.rolling(63).mean() / dollar.rolling(252).mean().replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    turnover = v / v.rolling(21).mean().replace(0, np.nan)

    cs_spread = pd.Series(np.nan, index=rets.index)
    hl_amihud = pd.Series(np.nan, index=rets.index)
    if "Ticker" in ohlcv.columns:
        ohlcv_t = ohlcv[ohlcv["Ticker"] == ticker]
    elif "ticker" in ohlcv.columns:
        ohlcv_t = ohlcv[ohlcv["ticker"] == ticker]
    else:
        ohlcv_t = pd.DataFrame()
    if not ohlcv_t.empty:
        date_col = "Date" if "Date" in ohlcv_t.columns else "date" if "date" in ohlcv_t.columns else None
        ohlcv_t_idx = ohlcv_t.set_index(date_col) if date_col else ohlcv_t
        try:
            cs_spread = corwin_schultz_spread(ohlcv_t_idx, window=21).reindex(rets.index).ffill()
        except Exception:
            pass
        try:
            hl_amihud = high_low_amihud(ohlcv_t_idx, window=21).reindex(rets.index).ffill()
        except Exception:
            pass

    feat = pd.DataFrame(
        {
            "date": rets.index,
            "ticker": ticker,
            "ret_1d": r,
            "mom_5": r.rolling(5).sum(),
            "mom_21": r.rolling(21).sum(),
            "mom_63": r.rolling(63).sum(),
            "reversal_5": -r.rolling(5).sum(),
            "vol_21": r.rolling(21).std() * math.sqrt(annualization),
            "vol_63": r.rolling(63).std() * math.sqrt(annualization),
            "drawdown_63": c / c.rolling(63).max() - 1.0,
            "volume_z_21": volume_z,
            "amihud_21": (r.abs() / dollar).rolling(21).mean() * 1e8,
            "hl_amihud_21": hl_amihud,
            "corwin_schultz_21": cs_spread,
            "dollar_vol_mom": dollar_vol_mom,
            "turnover_rate": turnover,
            "max_factor_21": r.rolling(21).max(),
            "high_52w": c / c.rolling(252).max(),
            "target_return": fwd,
        }
    )
    feat["sector"] = sectors.get(ticker, "Unknown")
    feat = feat.replace([np.inf, -np.inf], np.nan).dropna(subset=["target_return", "mom_21", "vol_21"])
    if feat.empty:
        return [], []
    return feat.to_dict("records"), feat["target_return"].tolist()



def make_feature_panel(ctx: MLContext, horizon: int = 5) -> tuple[pd.DataFrame, pd.Series]:
    rets = ctx.returns
    closes = ctx.closes.reindex(rets.index)
    vols = ctx.volumes.reindex(rets.index)
    horizon = max(int(horizon), 1)
    rows: list[dict[str, Any]] = []
    y_vals: list[float] = []
    max_workers = max(1, min(8, len(rets.columns)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _build_ticker_features,
                ticker,
                rets,
                closes,
                vols,
                ctx.ohlcv,
                ctx.sectors,
                ctx.market_caps,
                ctx.annualization,
                horizon,
            ): ticker
            for ticker in rets.columns
        }
        for future in as_completed(futures):
            ticker_rows, ticker_y = future.result()
            rows.extend(ticker_rows)
            y_vals.extend(ticker_y)

    panel = pd.DataFrame(rows)
    if panel.empty:
        return pd.DataFrame(), pd.Series(dtype=float)
    panel = panel.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    return panel, panel["target_return"].copy()



def numeric_xy(panel: pd.DataFrame, y: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    cols = [
        "ret_1d", "mom_5", "mom_21", "mom_63", "reversal_5",
        "vol_21", "vol_63", "drawdown_63", "volume_z_21", "amihud_21",
        "hl_amihud_21", "corwin_schultz_21", "dollar_vol_mom",
        "turnover_rate", "max_factor_21", "high_52w",
    ]
    x = panel[[c for c in cols if c in panel.columns]].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    target = y if y is not None else panel.get("target_return", pd.Series(dtype=float))
    return x, pd.to_numeric(target, errors="coerce").fillna(0.0)

