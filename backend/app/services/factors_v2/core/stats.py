"""Factors V2 stats helpers."""

from __future__ import annotations
from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from .performance import rolling_percentile_numba


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


def predictive_regression(
    signal: pd.Series, returns: pd.Series, horizon: int = 252
) -> Dict[str, Any]:
    df = pd.concat(
        [
            signal.rename("x"),
            (
                (1 + returns).rolling(horizon).apply(np.prod, raw=True).shift(-horizon)
                - 1
            ).rename("y"),
        ],
        axis=1,
    ).dropna()
    if len(df) < 30 or df["x"].std() == 0:
        return {
            "predicted_return": None,
            "beta": None,
            "r_squared": None,
            "ci_90_low": None,
            "ci_90_high": None,
        }
    import statsmodels.api as sm

    x = sm.add_constant(df["x"])
    lag = min(horizon, len(df) - 2)
    fit = sm.OLS(df["y"], x).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    current = signal.dropna().iloc[-1]
    x0 = np.array([1.0, float(current)])
    pred = float(x0 @ fit.params)
    se = float(np.sqrt(max(x0 @ fit.cov_params() @ x0, 0)))
    width = stats.norm.ppf(0.95) * se
    return {
        "predicted_return": pred,
        "beta": float(fit.params.iloc[1]),
        "alpha": float(fit.params.iloc[0]),
        "r_squared": float(fit.rsquared),
        "ci_90_low": pred - width,
        "ci_90_high": pred + width,
        "forecast_standard_error": se,
        "sample_size": len(df),
        "standard_error_method": f"newey_west_hac_lag_{lag}",
    }


def ols_beta(y: pd.Series, x: pd.DataFrame) -> Tuple[pd.Series, pd.Series, float]:
    df = pd.concat([y.rename("y"), x], axis=1).dropna()
    if len(df) < x.shape[1] + 10:
        return pd.Series(dtype=float), pd.Series(dtype=float), np.nan
    import statsmodels.api as sm

    fit = sm.OLS(df["y"], sm.add_constant(df[x.columns], has_constant="add")).fit()
    return (
        fit.params.reindex(x.columns),
        fit.bse.reindex(x.columns),
        float(fit.params["const"]),
    )


def perf_stats(r: pd.Series) -> Dict[str, Any]:
    r = r.dropna()
    if r.empty:
        return {}
    equity = (1 + r).cumprod()
    dd = equity / equity.cummax().clip(lower=1.0) - 1
    ann_ret = float(equity.iloc[-1] ** (252 / len(r)) - 1)
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
    monthly = (
        (1 + r).resample("ME").prod() - 1
        if isinstance(r.index, pd.DatetimeIndex)
        else pd.Series(dtype=float)
    )
    yearly = (
        (1 + r).resample("YE").prod() - 1
        if isinstance(r.index, pd.DatetimeIndex)
        else pd.Series(dtype=float)
    )
    var_5 = float(r.quantile(0.05))
    tail = r[r <= var_5]
    return {
        "annualized_return": ann_ret,
        "annualized_volatility": ann_vol,
        "sharpe": float(r.mean() * 252 / ann_vol) if ann_vol else None,
        "sortino": ann_ret / downside_vol if downside_vol else None,
        "calmar": ann_ret / abs(max_dd) if max_dd else None,
        "max_drawdown": max_dd,
        "max_drawdown_duration_days": int(max(durations)) if durations else 0,
        "average_drawdown_duration_days": float(np.mean(durations))
        if durations
        else 0.0,
        "skewness": float(stats.skew(r, nan_policy="omit")) if len(r) > 2 else None,
        "excess_kurtosis": float(stats.kurtosis(r, fisher=True, nan_policy="omit"))
        if len(r) > 3
        else None,
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
