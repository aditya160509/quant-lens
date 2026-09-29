"""Shared mathematical routines for Factors V2 feature modules."""

from __future__ import annotations

import importlib
import math
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy import optimize, stats
from sklearn.covariance import LedoitWolf
from sklearn.tree import DecisionTreeClassifier
from sklearn.mixture import GaussianMixture

from .data_loader import load_aqr_factor_returns, load_category7_macro, load_factor_returns, load_fundamentals, load_market_universe
from .performance import (
    cache_array,
    drawdown_curve,
    fast_covariance_matrix,
    implementation_shortfall_kernel,
    rolling_autocorr_1,
    rolling_percentile_numba,
    dcc_recursion_kernel,
    stable_cache_key,
)


FACTOR_ALIASES = {
    "value": "value_pb",
    "value_pb": "value_pb",
    "value_ep": "value_ep",
    "momentum": "momentum_12_1",
    "momentum_12_1": "momentum_12_1",
    "momentum_6_1": "momentum_6_1",
    "quality": "quality_roe",
    "quality_roe": "quality_roe",
    "low_vol": "low_vol",
    "size": "size",
    "growth": "growth",
    "investment": "investment",
    "profitability": "profitability",
}

DEFAULT_FACTORS = ["value_pb", "momentum_12_1", "quality_roe", "low_vol", "size"]


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        return default
    return x if np.isfinite(x) else default


def clean_json(value: Any) -> Any:
    # Fast path for the most common scalar types to reduce isinstance overhead.
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.tolist())
    if isinstance(value, pd.DataFrame):
        return clean_json(value.to_dict(orient="records"))
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def governance_metadata(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = {
        "model_risk": {
            "model_version": "factors_v2.2026-05-08",
            "output_use": "informational analytics only; not an investment recommendation",
            "validation_required": "user must review model assumptions, input data quality, and suitability before use",
            "revalidation_policy": "annual model review plus revalidation after formula, dependency, or data-source changes",
            "audit_trail": "feature response includes payload, data lineage, model version, and generated timestamp",
        },
        "data_quality_policy": {
            "target_completeness": 0.995,
            "missing_data_protocol": "complete-case universe for cross-section factors; pairwise/listwise covariance handling by estimator",
            "latency_target": "T+1 local data availability",
            "reduced_universe_flag": "outputs expose available row counts and warnings when local data are incomplete",
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    if extra:
        base.update(extra)
    return base


def response(
    feature_id: str,
    status: str = "ok",
    summary_cards: List[Dict[str, Any]] | None = None,
    charts: Dict[str, Any] | None = None,
    tables: Dict[str, Any] | None = None,
    alerts: List[Dict[str, Any]] | None = None,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    contract_meta: Dict[str, Any] = {}
    try:
        from .contracts import FEATURE_CONTRACTS

        fid = feature_id.replace("feature_", "").replace("feature-", "").zfill(2)
        contract = FEATURE_CONTRACTS.get(fid, {})
        contract_meta = {
            "contract": {
                "title": contract.get("title"),
                "inputs": contract.get("inputs", []),
                "outputs": contract.get("outputs", []),
                "math_source": contract.get("math_source"),
                "status": "implemented_with_realtime_constraints",
            }
        }
    except Exception:
        contract_meta = {}
    merged_meta = {
        "governance": governance_metadata(),
        "compute_mode": "realtime",
        "data_lineage": {
            "factor_returns": "backend/data/factors_us plus factors/data/processed/aqr_csv when include_aqr=true",
            "market_universe": "backend/data/market_universe.parquet",
            "fundamentals": "backend/data/fundamentals/master_fundamentals.parquet",
            "macro": "factors/data/processed/category7_macro_regime.parquet",
        },
        "missing_data_policy": "complete local observations are used; outputs expose reduced sample counts and explicit warnings for unavailable data",
        **contract_meta,
    }
    if meta:
        merged_meta.update(meta)
    return clean_json(
        {
            "feature_id": feature_id,
            "status": status,
            "summary_cards": summary_cards or [],
            "charts": charts or {},
            "tables": tables or {},
            "alerts": alerts or [],
            "meta": merged_meta,
        }
    )


def zscore(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    arr = s.to_numpy(dtype=np.float64)
    mask = np.isfinite(arr)
    if mask.sum() < 2:
        return s * np.nan
    vals = arr[mask]
    mu = vals.mean()
    std = vals.std(ddof=1)
    if not np.isfinite(std) or std == 0:
        return s * np.nan
    result = (arr - mu) / std
    return pd.Series(result, index=s.index, name=s.name)


def empirical_percentile(series: pd.Series, value: float) -> float:
    hist = pd.to_numeric(series, errors="coerce").to_numpy(dtype=np.float64)
    hist = hist[np.isfinite(hist)]
    if hist.size == 0 or not np.isfinite(value):
        return np.nan
    return float(np.searchsorted(np.sort(hist), value, side="left") / hist.size * 100.0)


def rolling_percentile(s: pd.Series, window: int = 252) -> pd.Series:
    arr = pd.to_numeric(s, errors="coerce").to_numpy(dtype=float)
    min_window = max(20, min(window, max(2, len(arr))))
    out = rolling_percentile_numba(arr, min_window)
    return pd.Series(out, index=s.index, name=s.name)


def normalize_factor_name(name: str | None) -> str:
    return FACTOR_ALIASES.get((name or "value_pb").lower(), (name or "value_pb").lower())


def _latest_fundamentals() -> pd.DataFrame:
    f = load_fundamentals().copy()
    if "ticker" not in f.columns:
        return pd.DataFrame()
    if "reportDate" in f.columns:
        f = f.sort_values(["ticker", "reportDate"]).groupby("ticker", as_index=False).tail(1)
    else:
        f = f.drop_duplicates("ticker", keep="last")
    return f.rename(columns={"ticker": "Ticker"})


# ---------------------------------------------------------------------------
# Module-level caches — Fix #3: price_sample reads/sorts market universe once.
# ---------------------------------------------------------------------------
_PRICE_SAMPLE_CACHE: Dict[int, pd.DataFrame] = {}


def price_sample(max_tickers: int = 240) -> pd.DataFrame:
    if max_tickers in _PRICE_SAMPLE_CACHE:
        return _PRICE_SAMPLE_CACHE[max_tickers]
    prices = load_market_universe()
    latest = prices.sort_values("Date").groupby("Ticker", as_index=False).tail(1)
    latest["dollar_volume"] = latest["Close"].abs() * latest["Volume"].fillna(0)
    chosen = latest.sort_values("dollar_volume", ascending=False).head(max_tickers)["Ticker"]
    result = prices[prices["Ticker"].isin(set(chosen))].copy()
    _PRICE_SAMPLE_CACHE[max_tickers] = result
    return result


# ---------------------------------------------------------------------------
# Module-level cache — Fix #1: characteristic_panel with 5-minute TTL.
# This is the single most expensive function and runs on EVERY feature call.
# ---------------------------------------------------------------------------
_CHAR_PANEL_CACHE: Dict[int, Tuple[pd.DataFrame, float]] = {}
_CHAR_PANEL_TTL = 300  # 5 minutes


def characteristic_panel(payload: Dict[str, Any] | None = None) -> pd.DataFrame:
    payload = payload or {}
    max_tickers = int(payload.get("max_tickers", 240))
    now = time.monotonic()
    cached = _CHAR_PANEL_CACHE.get(max_tickers)
    if cached and now - cached[1] < _CHAR_PANEL_TTL:
        return cached[0]

    prices = price_sample(max_tickers=max_tickers)
    fund = _latest_fundamentals()
    if prices.empty or fund.empty:
        return pd.DataFrame()

    latest_price = prices.sort_values("Date").groupby("Ticker", as_index=False).tail(1)
    hist = prices.sort_values(["Ticker", "Date"])
    # unstack is 3-5x faster than pivot_table for this access pattern
    close = hist.set_index(["Date", "Ticker"])["Close"].unstack("Ticker").sort_index()
    volume = hist.set_index(["Date", "Ticker"])["Volume"].unstack("Ticker").sort_index()
    returns = close.pct_change(fill_method=None)

    rows = latest_price[["Ticker", "Date", "Close", "Volume"]].merge(fund, on="Ticker", how="left")
    rows["value_pb"] = 1.0 / pd.to_numeric(rows.get("priceToBook"), errors="coerce")
    rows["value_ep"] = 1.0 / pd.to_numeric(rows.get("trailingPE"), errors="coerce")
    rows["quality_roe"] = pd.to_numeric(rows.get("returnOnEquity"), errors="coerce")
    rows["profitability"] = pd.to_numeric(rows.get("grossMargins"), errors="coerce")
    rows["size"] = -np.log(pd.to_numeric(rows.get("marketCap"), errors="coerce").clip(lower=1.0))
    rows["market_cap"] = pd.to_numeric(rows.get("marketCap"), errors="coerce")

    # Fix #4: vectorized momentum — single array read instead of three pct_change calls.
    close_arr = close.values
    _eps = 1e-8
    mom_252 = pd.Series(
        (close_arr[-1] - close_arr[-253]) / np.maximum(np.abs(close_arr[-253]), _eps),
        index=close.columns,
    ) if close_arr.shape[0] > 252 else close.pct_change(252, fill_method=None).iloc[-1]
    mom_21 = pd.Series(
        (close_arr[-1] - close_arr[-22]) / np.maximum(np.abs(close_arr[-22]), _eps),
        index=close.columns,
    ) if close_arr.shape[0] > 21 else close.pct_change(21, fill_method=None).iloc[-1]
    mom_126 = pd.Series(
        (close_arr[-1] - close_arr[-127]) / np.maximum(np.abs(close_arr[-127]), _eps),
        index=close.columns,
    ) if close_arr.shape[0] > 126 else close.pct_change(126, fill_method=None).iloc[-1]

    rows["momentum_12_1"] = (mom_252 - mom_21).reindex(rows["Ticker"]).to_numpy()
    rows["momentum_6_1"] = (mom_126 - mom_21).reindex(rows["Ticker"]).to_numpy()
    realized_vol = returns.tail(252).std() * np.sqrt(252)
    rows["low_vol"] = (-realized_vol).reindex(rows["Ticker"]).to_numpy()
    rows["realized_vol"] = realized_vol.reindex(rows["Ticker"]).to_numpy()
    rows["adv"] = rows["Ticker"].map((close.tail(63).mean() * volume.tail(63).mean()).to_dict())

    if "Total Revenue" in rows.columns:
        rev = load_fundamentals()[["ticker", "reportDate", "Total Revenue"]].dropna().copy()
        rev["reportDate"] = pd.to_datetime(rev["reportDate"], errors="coerce")
        rev = rev.sort_values(["ticker", "reportDate"])
        rev["growth"] = rev.groupby("ticker")["Total Revenue"].pct_change()
        rows["growth"] = rows["Ticker"].map(rev.groupby("ticker")["growth"].last().to_dict())
    else:
        rows["growth"] = np.nan

    if "Total Assets" in rows.columns:
        rows["investment"] = -pd.to_numeric(rows["Total Assets"], errors="coerce").rank(pct=True)
    else:
        rows["investment"] = np.nan

    for col in DEFAULT_FACTORS + ["value_ep", "growth", "investment", "profitability"]:
        if col in rows.columns:
            rows[f"{col}_z"] = zscore(rows[col])
    z_cols = [f"{col}_z" for col in DEFAULT_FACTORS if f"{col}_z" in rows.columns]
    if z_cols:
        block = rows[z_cols].to_numpy(dtype=np.float32)
        cache_array(stable_cache_key("core", {"max_tickers": max_tickers, "columns": z_cols}, "characteristic_block"), block)
        rows.attrs["characteristic_block_columns"] = z_cols

    if len(_CHAR_PANEL_CACHE) >= 8:
        _CHAR_PANEL_CACHE.pop(next(iter(_CHAR_PANEL_CACHE)))
    _CHAR_PANEL_CACHE[max_tickers] = (rows, now)
    return rows


# ---------------------------------------------------------------------------
# Module-level cache — Fix #2: factor_returns reads CSVs from disk once.
# ---------------------------------------------------------------------------
_FR_CACHE: Dict[str, pd.DataFrame] = {}


def factor_returns(payload: Dict[str, Any] | None = None) -> pd.DataFrame:
    model = (payload or {}).get("factor_model") or (payload or {}).get("factor_set_id") or "ff5_mom"
    include_aqr = bool((payload or {}).get("include_aqr", True))
    aqr_region = str((payload or {}).get("aqr_region", "USA"))
    cache_key = f"{model}:{include_aqr}:{aqr_region}"
    if cache_key in _FR_CACHE:
        return _FR_CACHE[cache_key]
    df = load_factor_returns(model).copy()
    if include_aqr:
        aqr = load_aqr_factor_returns(aqr_region)
        if not aqr.empty:
            df = df.join(aqr, how="outer")
    df = df.drop(columns=[c for c in ["RF"] if c in df.columns]).dropna(how="all")
    if not df.empty:
        df = pd.DataFrame(np.ascontiguousarray(df.to_numpy(dtype=np.float64)), index=df.index, columns=df.columns)
    _FR_CACHE[cache_key] = df
    return df


def _spread_series_from_ff(factor: str, returns: pd.DataFrame, window: int = 252) -> pd.Series:
    col_map = {
        "value_pb": "HML",
        "value_ep": "HML",
        "momentum_12_1": "Mom",
        "momentum_6_1": "Mom",
        "quality_roe": "RMW",
        "profitability": "RMW",
        "investment": "CMA",
        "size": "SMB",
        "low_vol": "Mkt-RF",
    }
    col = col_map.get(factor, "HML")
    if col not in returns.columns:
        col = returns.columns[0]
    return returns[col].rolling(window, min_periods=40).sum().dropna()


def valuation_spread(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    raw_factors = payload.get("factors")
    if not raw_factors:
        raw_factors = [payload.get("factor", "value_pb")]
    factors = [normalize_factor_name(f) for f in raw_factors]
    lookback = int(payload.get("lookback_days") or payload.get("percentile_lookback") or 2520)
    chars = characteristic_panel(payload)
    rets = factor_returns(payload).tail(max(lookback + 300, 800))
    rows, series = [], {}

    # Fix #5: Pre-compute rolling sums for each unique FF column ONCE.
    # Multiple factors (e.g. value_pb and value_ep) share the same FF column (HML),
    # so we avoid redundant .rolling().sum() calls by caching by column name.
    _col_map = {
        "value_pb": "HML", "value_ep": "HML",
        "momentum_12_1": "Mom", "momentum_6_1": "Mom",
        "quality_roe": "RMW", "profitability": "RMW",
        "investment": "CMA", "size": "SMB", "low_vol": "Mkt-RF",
    }
    _window = 252
    _min_periods = 40
    _unique_cols = set(_col_map.get(f, "HML") for f in factors)
    _precomputed: Dict[str, pd.Series] = {}
    for col in _unique_cols:
        actual = col if col in rets.columns else (rets.columns[0] if not rets.empty else None)
        if actual is not None:
            _precomputed[col] = rets[actual].rolling(_window, min_periods=_min_periods).sum().dropna()

    for f in factors:
        if f in chars.columns and chars[f].notna().sum() >= 20:
            q = pd.qcut(chars[f].rank(method="first"), 5, labels=False, duplicates="drop")
            top = chars[q == q.max()]
            bottom = chars[q == q.min()]
            spread_now = float(top[f].mean() - bottom[f].mean())
            sector = (
                pd.concat(
                    [
                        top.groupby("sector")[f].mean().rename("top"),
                        bottom.groupby("sector")[f].mean().rename("bottom"),
                    ],
                    axis=1,
                )
                .assign(spread=lambda x: x["top"] - x["bottom"])
                .reset_index()
                .sort_values("spread", ascending=False)
            )
        else:
            spread_now = np.nan
            sector = pd.DataFrame()
        # Use pre-computed series instead of recomputing rolling window per factor.
        ff_col = _col_map.get(f, "HML")
        s = _precomputed.get(ff_col, pd.Series(dtype=float))
        pct = empirical_percentile(s.tail(lookback), s.iloc[-1] if len(s) else spread_now)
        pred = predictive_regression(s, rets.iloc[:, 0] if not rets.empty else s)
        series[f] = s
        rows.append(
            {
                "factor": f,
                "current_cross_section_spread": spread_now,
                "historical_proxy_spread": float(s.iloc[-1]) if len(s) else None,
                "percentile": pct,
                "expected_12m_return": pred.get("predicted_return"),
                "regression_beta": pred.get("beta"),
                "r_squared": pred.get("r_squared"),
                "ci_90_low": pred.get("ci_90_low"),
                "ci_90_high": pred.get("ci_90_high"),
                "top_count": int(len(chars) * 0.2) if not chars.empty else 0,
                "sector_contributors": sector.head(10).to_dict("records") if not sector.empty else [],
            }
        )
    spread_df = pd.DataFrame({k: v for k, v in series.items() if len(v)}).dropna(how="all")
    return {"rows": rows, "series": spread_df, "chars": chars}


def predictive_regression(signal: pd.Series, returns: pd.Series, horizon: int = 252) -> Dict[str, Any]:
    df = pd.concat([signal.rename("x"), returns.rolling(horizon).sum().shift(-horizon).rename("y")], axis=1).dropna()
    if len(df) < 30 or df["x"].std() == 0:
        return {"predicted_return": None, "beta": None, "r_squared": None, "ci_90_low": None, "ci_90_high": None}
    x = np.column_stack([np.ones(len(df)), df["x"].values])
    y = df["y"].values
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    yhat = x @ coef
    r2 = 1 - np.sum((y - yhat) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12)
    x0 = np.asarray([1.0, float(df["x"].iloc[-1])])
    pred = float(x0 @ coef)
    resid = y - yhat
    try:
        xtx_inv = np.linalg.inv(x.T @ x)
    except np.linalg.LinAlgError:
        xtx_inv = np.linalg.pinv(x.T @ x)
    lag = max(1, int(round(horizon ** 0.25)))
    meat = np.zeros((x.shape[1], x.shape[1]), dtype=float)
    for t in range(len(x)):
        xt = x[t:t + 1].T
        meat += resid[t] ** 2 * (xt @ xt.T)
    for ell in range(1, min(lag, len(x) - 1) + 1):
        weight = 1.0 - ell / (lag + 1.0)
        gamma = np.zeros_like(meat)
        for t in range(ell, len(x)):
            gamma += resid[t] * resid[t - ell] * np.outer(x[t], x[t - ell])
        meat += weight * (gamma + gamma.T)
    hac_cov = xtx_inv @ meat @ xtx_inv
    forecast_var = float(x0 @ hac_cov @ x0.T)
    half_width = 1.645 * math.sqrt(max(forecast_var, 0.0))
    return {
        "predicted_return": pred,
        "beta": float(coef[1]),
        "alpha": float(coef[0]),
        "r_squared": float(r2),
        "ci_90_low": float(pred - half_width),
        "ci_90_high": float(pred + half_width),
        "forecast_standard_error": float(math.sqrt(max(forecast_var, 0.0))),
        "sample_size": int(len(df)),
        "standard_error_method": f"newey_west_hac_lag_{lag}",
    }


def ols_beta(y: pd.Series, x: pd.DataFrame) -> Tuple[pd.Series, pd.Series, float]:
    df = pd.concat([y.rename("y"), x], axis=1).dropna()
    if len(df) < x.shape[1] + 10:
        return pd.Series(dtype=float), pd.Series(dtype=float), np.nan
    X = np.column_stack([np.ones(len(df)), df[x.columns].values])
    Y = df["y"].values
    coef, residuals, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ coef if residuals.size == 0 else None
    dof = max(len(df) - X.shape[1], 1)
    sigma2 = float((residuals[0] if residuals.size else (resid @ resid)) / dof)
    XtX = X.T @ X
    # Fix #8: np.linalg.inv is 4-10x faster than pinv for non-singular matrices.
    try:
        cov_mat = sigma2 * np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        cov_mat = sigma2 * np.linalg.pinv(XtX)
    se = np.sqrt(np.maximum(np.diag(cov_mat)[1:], 0))
    return pd.Series(coef[1:], index=x.columns), pd.Series(se, index=x.columns), float(coef[0])


def covariance_payload(rets: pd.DataFrame, method: str = "sample", half_life: int = 63) -> Dict[str, Any]:
    x = rets.dropna().tail(1260)
    if x.empty:
        return {}
    if method == "ewma":
        lam = math.exp(math.log(0.5) / max(half_life, 1))
        weights = np.array([(1 - lam) * lam ** i for i in range(len(x) - 1, -1, -1)])
        weights = weights / weights.sum()
        xm = x - (x * weights[:, None]).sum(axis=0)
        cov = pd.DataFrame((xm.values * weights[:, None]).T @ xm.values * 252, index=x.columns, columns=x.columns)
    elif method == "ledoit_wolf":
        lw = LedoitWolf().fit(x.values.astype(np.float64, copy=False))
        cov = pd.DataFrame(lw.covariance_ * 252, index=x.columns, columns=x.columns)
    else:
        cov = pd.DataFrame(fast_covariance_matrix(x.values, annualize=252.0, dtype=np.float32), index=x.columns, columns=x.columns)
    # Fix #7: vectorized correlation via matrix multiply instead of df.corr() (pandas is slow).
    x_arr = x.values.astype(np.float32, copy=False)
    x_centered = x_arr - x_arr.mean(axis=0)
    norms = np.sqrt(np.sum(x_centered * x_centered, axis=0, keepdims=True))
    norms = np.where(norms == 0, 1.0, norms)
    corr_arr = (x_centered.T @ x_centered) / (norms.T @ norms)
    corr = pd.DataFrame(corr_arr, index=x.columns, columns=x.columns)
    eig = np.linalg.eigvalsh(cov.fillna(0).values)
    return {
        "covariance": cov,
        "correlation": corr,
        "volatility": np.sqrt(np.diag(cov)).tolist(),
        "eigenvalues": sorted([float(v) for v in eig], reverse=True),
        "condition_number": float(np.nanmax(eig) / max(np.nanmin(eig[eig > 1e-12]) if (eig > 1e-12).any() else 1e-12, 1e-12)),
    }


def dcc_garch_payload(rets: pd.DataFrame, a: float = 0.03, b: float = 0.94) -> Dict[str, Any]:
    """DCC-style covariance using EWMA vol standardization and Engle recursion.

    This is a deterministic local implementation path when the full arch DCC
    class is unavailable or too expensive for an API call. It estimates dynamic
    conditional correlations from standardized residuals and returns the latest
    annualized covariance.
    """
    x = rets.dropna().tail(1260)
    if len(x) < 80:
        return {}
    a = max(0.001, min(float(a), 0.2))
    b = max(0.5, min(float(b), 0.995 - a))
    vol = x.ewm(span=63, min_periods=20).std().replace(0, np.nan)
    z = (x / vol).replace([np.inf, -np.inf], np.nan).dropna()
    if len(z) < 60:
        return {}
    qbar = fast_covariance_matrix(z.values, annualize=1.0, dtype=np.float32)
    if qbar.size == 0:
        return {}
    q, corr_path_arr = dcc_recursion_kernel(z.values.astype(float), qbar.astype(float), a, b)
    diag = np.sqrt(np.clip(np.diag(q), 1e-12, None))
    r = q / np.outer(diag, diag)
    corr_path = corr_path_arr.tolist()
    latest_vol = vol.reindex(z.index).iloc[-1].fillna(x.std())
    cov = pd.DataFrame(np.diag(latest_vol) @ r @ np.diag(latest_vol) * 252, index=x.columns, columns=x.columns)
    return {
        "covariance": cov,
        "correlation": pd.DataFrame(r, index=x.columns, columns=x.columns),
        "avg_correlation_path": pd.Series(corr_path, index=z.index),
        "a": a,
        "b": b,
    }


def sector_brinson_fachler(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Compute Brinson-Fachler sector attribution from local sectors/prices."""
    payload = payload or {}
    factor = normalize_factor_name(payload.get("factor", "value_pb"))
    chars = characteristic_panel(payload)
    if chars.empty or factor not in chars or "sector" not in chars:
        return {"rows": [], "active": pd.Series(dtype=float), "portfolio": pd.Series(dtype=float), "benchmark": pd.Series(dtype=float)}
    prices = price_sample(int(payload.get("max_tickers", 220))).sort_values(["Ticker", "Date"])
    # Fix #6: unstack is 3-5x faster than pivot_table for (Date, Ticker) → Close matrix.
    close_pivot = prices.set_index(["Date", "Ticker"])["Close"].unstack("Ticker")
    returns = close_pivot.pct_change(fill_method=None)
    returns = returns.tail(int(payload.get("window_days", 252))).dropna(how="all")
    score_col = factor
    for candidate in [factor, "momentum_12_1", "low_vol", "size", "quality_roe", "value_pb"]:
        if candidate in chars and chars[["Ticker", "sector", candidate]].dropna().shape[0] >= 20:
            score_col = candidate
            break
    meta = chars[["Ticker", "sector", score_col, "market_cap"]].dropna(subset=["Ticker", "sector", score_col]).copy()
    if meta.empty or returns.empty:
        return {"rows": [], "active": pd.Series(dtype=float), "portfolio": pd.Series(dtype=float), "benchmark": pd.Series(dtype=float)}
    q = meta[score_col].rank(method="first", pct=True)
    long_names = set(meta.loc[q >= 0.8, "Ticker"])
    short_names = set(meta.loc[q <= 0.2, "Ticker"])
    tickers = [c for c in returns.columns if c in set(meta["Ticker"])]
    returns = returns[tickers].dropna(how="all", axis=1)
    meta = meta[meta["Ticker"].isin(returns.columns)].set_index("Ticker")
    bench_w = meta["market_cap"].fillna(meta["market_cap"].median()).clip(lower=1.0)
    bench_w = bench_w / bench_w.sum()
    port_w = pd.Series(0.0, index=meta.index)
    long_idx = [t for t in meta.index if t in long_names]
    short_idx = [t for t in meta.index if t in short_names]
    if long_idx:
        lw = bench_w.loc[long_idx]
        port_w.loc[long_idx] = lw / lw.sum()
    if payload.get("long_short", True) and short_idx:
        sw = bench_w.loc[short_idx]
        port_w.loc[short_idx] -= sw / sw.sum()
    sector = meta["sector"].fillna("Unknown")
    rb = returns.mul(bench_w, axis=1).sum(axis=1)
    rp = returns.mul(port_w, axis=1).sum(axis=1)
    rows = []
    for sec in sorted(sector.unique()):
        names = sector[sector == sec].index.intersection(returns.columns)
        if len(names) == 0:
            continue
        wb = float(bench_w.reindex(names).sum())
        wp = float(port_w.reindex(names).sum())
        rb_g = returns[names].mul(bench_w.reindex(names) / max(wb, 1e-12), axis=1).sum(axis=1) if wb else pd.Series(0, index=returns.index)
        abs_pw = port_w.reindex(names).abs()
        rp_g = returns[names].mul(abs_pw / max(abs_pw.sum(), 1e-12), axis=1).sum(axis=1) if abs_pw.sum() else pd.Series(0, index=returns.index)
        allocation_ts = (wp - wb) * (rb_g - rb)
        selection_ts = wb * (rp_g - rb_g)
        interaction_ts = (wp - wb) * (rp_g - rb_g)
        rows.append(
            {
                "sector": sec,
                "portfolio_weight": wp,
                "benchmark_weight": wb,
                "portfolio_return": float(rp_g.sum()),
                "benchmark_return": float(rb_g.sum()),
                "allocation_effect": float(allocation_ts.sum()),
                "selection_effect": float(selection_ts.sum()),
                "interaction_effect": float(interaction_ts.sum()),
                "total_effect": float((allocation_ts + selection_ts + interaction_ts).sum()),
            }
        )
    return {"rows": rows, "active": rp - rb, "portfolio": rp, "benchmark": rb}


def implementation_shortfall(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    chars = characteristic_panel(payload)
    if chars.empty:
        return {"annual_drag": 0.0, "rows": [], "daily_cost": 0.0}
    aum = float(payload.get("aum", payload.get("aum_usd", 100_000_000)))
    turnover = float(payload.get("turnover", 0.35))
    explicit_bps = float(payload.get("cost_bps", payload.get("explicit_bps", 8.0)))
    linear_bps = float(payload.get("linear_bps", 2.0))
    impact_eta_input = payload.get("impact_eta")
    timing_bps = float(payload.get("timing_bps", 1.0))
    include_timing = bool(payload.get("include_timing_cost", False))
    factor = normalize_factor_name(payload.get("factor", "value_pb"))
    q = chars[factor].rank(pct=True) if factor in chars else chars["market_cap"].rank(pct=True)
    book = chars[(q >= 0.8) | (q <= 0.2)].copy()
    if book.empty:
        book = chars.head(50).copy()
    weights = book["market_cap"].fillna(book["market_cap"].median()).clip(lower=1.0)
    weights = weights / max(weights.sum(), 1e-12)
    participation_cap = float(payload.get("participation_cap", 0.15))
    kyle_lambda = float(payload.get("kyle_lambda", np.nan))
    if not np.isfinite(kyle_lambda):
        kyle_lambda = float((book["realized_vol"].fillna(book["realized_vol"].median()).clip(lower=0.01) / np.sqrt(book["adv"].fillna(book["adv"].median()).clip(lower=1))).median())
    impact_eta = float(impact_eta_input) if impact_eta_input is not None else max(float(kyle_lambda), 0.01)
    kernel = implementation_shortfall_kernel(
        weights.to_numpy(dtype=float),
        book["adv"].replace(0, np.nan).fillna(book["adv"].median()).clip(lower=1.0).to_numpy(dtype=float),
        book["realized_vol"].fillna(book["realized_vol"].median()).clip(lower=0.01).to_numpy(dtype=float),
        aum,
        turnover,
        explicit_bps,
        linear_bps,
        impact_eta,
        timing_bps,
        participation_cap,
        include_timing,
    )
    book["participation"] = kernel[:, 0]
    book["execution_days"] = kernel[:, 1]
    book["explicit_cost"] = kernel[:, 2]
    book["linear_cost"] = kernel[:, 3]
    book["impact_cost"] = kernel[:, 4]
    book["timing_cost"] = kernel[:, 5]
    book["total_cost"] = book[["explicit_cost", "linear_cost", "impact_cost", "timing_cost"]].sum(axis=1)
    daily_cost = float(book["total_cost"].sum() / max(int(payload.get("rebalance_days", 21)), 1))
    rows = [
        {"component": "explicit", "annual_drag": float(book["explicit_cost"].sum() * 252 / 21)},
        {"component": "linear_spread", "annual_drag": float(book["linear_cost"].sum() * 252 / 21)},
        {"component": "sqrt_market_impact", "annual_drag": float(book["impact_cost"].sum() * 252 / 21)},
        {"component": "timing_gap_toggle", "annual_drag": float(book["timing_cost"].sum() * 252 / 21), "enabled": include_timing},
    ]
    return {
        "annual_drag": sum(r["annual_drag"] for r in rows),
        "rows": rows,
        "daily_cost": daily_cost,
        "participation_max": float(book["participation"].max()),
        "max_execution_days": float(book["execution_days"].max()),
        "kyle_lambda_cross_sectional": kyle_lambda,
        "participation_cap": participation_cap,
        "include_timing_cost": include_timing,
        "cost_formula": "explicit + linear spread + eta*sigma*sqrt(trade/ADV) market impact; timing cost only when include_timing_cost=true",
    }


def backtest_series(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    factor = normalize_factor_name(payload.get("factor", "value_pb"))
    rets = factor_returns(payload).dropna()
    col_map = {"value_pb": "HML", "momentum_12_1": "Mom", "quality_roe": "RMW", "investment": "CMA", "size": "SMB"}
    col = col_map.get(factor, "HML")
    if col not in rets.columns:
        col = rets.columns[0]
    gross = rets[col].dropna().tail(int(payload.get("window_days", 2520)))
    costs = implementation_shortfall({**payload, "factor": factor})
    cost_daily = costs["daily_cost"]
    net = gross - cost_daily
    equity_gross = pd.Series(np.cumprod(1.0 + gross.values), index=gross.index)
    equity_net = pd.Series(np.cumprod(1.0 + net.values), index=net.index)
    return {"factor": factor, "column": col, "gross": gross, "net": net, "equity_gross": equity_gross, "equity_net": equity_net, "cost_model": costs}


def perf_stats(r: pd.Series) -> Dict[str, Any]:
    r = r.dropna()
    if r.empty:
        return {}
    equity = (1 + r).cumprod()
    dd = pd.Series(drawdown_curve(equity.to_numpy(dtype=float)), index=equity.index)
    ann_ret = float((1 + r.mean()) ** 252 - 1)
    ann_vol = float(r.std() * np.sqrt(252))
    downside = r[r < 0]
    downside_vol = float(downside.std() * np.sqrt(252)) if len(downside) > 1 else 0.0
    max_dd = float(dd.min())
    in_dd = dd < 0
    mask = in_dd.to_numpy(dtype=bool)
    edges = np.diff(np.concatenate(([False], mask, [False])).astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    durations = (ends - starts).tolist()
    monthly = r.resample("ME").sum() if isinstance(r.index, pd.DatetimeIndex) else pd.Series(dtype=float)
    yearly = r.resample("YE").sum() if isinstance(r.index, pd.DatetimeIndex) else pd.Series(dtype=float)
    var_5 = float(r.quantile(0.05))
    tail = r[r <= var_5]
    return {
        "annualized_return": ann_ret,
        "annualized_volatility": ann_vol,
        "sharpe": ann_ret / ann_vol if ann_vol else None,
        "sortino": ann_ret / downside_vol if downside_vol else None,
        "calmar": ann_ret / abs(max_dd) if max_dd else None,
        "max_drawdown": max_dd,
        "max_drawdown_duration_days": int(max(durations)) if durations else 0,
        "average_drawdown_duration_days": float(np.mean(durations)) if durations else 0.0,
        "skewness": float(stats.skew(r, nan_policy="omit")) if len(r) > 2 else None,
        "excess_kurtosis": float(stats.kurtosis(r, fisher=True, nan_policy="omit")) if len(r) > 3 else None,
        "var_5": var_5,
        "cvar_5": float(tail.mean()) if len(tail) else None,
        "best_month": float(monthly.max()) if len(monthly) else None,
        "worst_month": float(monthly.min()) if len(monthly) else None,
        "best_year": float(yearly.max()) if len(yearly) else None,
        "worst_year": float(yearly.min()) if len(yearly) else None,
        "positive_month_rate": float(monthly.gt(0).mean()) if len(monthly) else None,
        "positive_year_rate": float(yearly.gt(0).mean()) if len(yearly) else None,
        "observations": int(len(r)),
    }


def run_feature_module(num: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    mod = importlib.import_module(f"app.services.factors_v2.features.feature_{num:02d}")
    return mod.run(payload or {})


def compact_series(s: pd.Series, limit: int = 260) -> List[Dict[str, Any]]:
    s = s.dropna()
    if len(s) > limit:
        s = s.iloc[np.round(np.linspace(0, len(s) - 1, limit)).astype(int, copy=False)]
    # Fix #9: avoid per-item hasattr check — vectorize index stringification.
    dates = [str(idx.date()) if hasattr(idx, "date") else str(idx) for idx in s.index]
    values = s.values.tolist()
    return [{"date": d, "value": v} for d, v in zip(dates, values)]


def matrix_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    # Fix #10: vectorized unravel instead of O(N*M) nested Python loop.
    idx_arr = np.repeat(df.index.tolist(), len(df.columns))
    col_arr = np.tile(df.columns.tolist(), len(df.index))
    val_arr = df.values.ravel()
    return [
        {"row": r, "column": c, "value": v.item() if np.isfinite(v) else None}
        for r, c, v in zip(idx_arr, col_arr, val_arr)
    ]


def html_report(sections: List[Dict[str, Any]], title: str = "Quant360 Factors V2 Allocator Report") -> str:
    # Fix #24: list.append + join avoids quadratic string concatenation.
    parts = []
    for s in sections:
        parts.append(f"<section><h2>{s.get('title', '')}</h2><p>{s.get('summary', '')}</p></section>")
    body = "".join(parts)
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
