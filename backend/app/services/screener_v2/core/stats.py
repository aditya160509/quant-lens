"""Screener V2 stats computations."""
from __future__ import annotations

import numba
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def rank_pct(series: pd.Series, higher_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series(50.0, index=series.index).where(numeric.notna())
    pct = (numeric.rank(method="average") - 1) / (numeric.notna().sum() - 1) * 100
    if not higher_better:
        pct = 100.0 - pct
    return pct.clip(0, 100)


def zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std(ddof=0)
    if not std or not np.isfinite(std):
        return pd.Series(0.0, index=series.index).where(numeric.notna())
    return ((numeric - numeric.mean()) / std).replace([np.inf, -np.inf], np.nan)


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
    import statsmodels.api as sm
    v, b = pd.to_numeric(values, errors="coerce"), pd.to_numeric(beta, errors="coerce")
    valid = v.notna() & b.notna()
    result = pd.Series(np.nan, index=v.index)
    if valid.sum() < 3 or b[valid].nunique() < 2:
        return result
    fit = sm.OLS(v[valid], sm.add_constant(b[valid], has_constant="add")).fit()
    result.loc[valid] = fit.resid
    return result


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


@numba.njit(cache=True)
def _wilder_tail(out, values, seed, period):
    for idx in range(seed + 1, len(values)):
        prev, val = out[idx - 1], values[idx]
        out[idx] = ((period - 1) * prev + val) / period if np.isfinite(prev) and np.isfinite(val) else np.nan


def _wilder_smooth(series: pd.Series, period: int, min_seed_coverage: float = 1.0) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) < period:
        return pd.Series(out, index=series.index)
    finite = np.flatnonzero(np.isfinite(values))
    if len(finite) < period:
        return pd.Series(out, index=series.index)
    start = int(finite[0])
    seed = start + period - 1
    seed_window = values[start:seed + 1]
    if np.isfinite(seed_window).mean() < min_seed_coverage:
        return pd.Series(out, index=series.index)
    out[seed] = np.mean(seed_window)
    _wilder_tail(out, values, seed, period)
    return pd.Series(out, index=series.index)

