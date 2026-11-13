"""Screener V2 stats computations."""
from __future__ import annotations

import numba
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def average_rank(values: np.ndarray, groups: np.ndarray | None = None) -> np.ndarray:
    """pandas rank(method="average") within groups, NaN values or groups (code -1) stay NaN.

    One lexsort instead of a pandas groupby: panels of a few names were dominated by pandas overhead.
    """
    values = np.asarray(values, dtype=float)
    groups = np.zeros(len(values), dtype=np.int64) if groups is None else np.asarray(groups, dtype=np.int64)
    out = np.full(len(values), np.nan)
    keep = np.flatnonzero(~np.isnan(values) & (groups >= 0))
    if not len(keep):
        return out
    order = keep[np.lexsort((values[keep], groups[keep]))]
    v, g = values[order], groups[order]
    new_group = np.r_[True, g[1:] != g[:-1]]
    new_tie = new_group | np.r_[True, v[1:] != v[:-1]]
    group_start = np.maximum.accumulate(np.where(new_group, np.arange(len(v)), 0))
    tie_start = np.flatnonzero(new_tie)
    tie_end = np.r_[tie_start[1:], len(v)]
    first, last = tie_start - group_start[tie_start], tie_end - 1 - group_start[tie_start]
    out[order] = np.repeat((first + last) / 2 + 1, tie_end - tie_start)
    return out


def rank_pct(series: pd.Series, higher_better: bool = True) -> pd.Series:
    # numpy end to end: Series.clip and arithmetic dominated panels of a few names.
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    valid = ~np.isnan(values)
    n = int(valid.sum())
    if n <= 1:
        return pd.Series(np.where(valid, 50.0, np.nan), index=series.index)
    pct = (average_rank(values) - 1) / (n - 1) * 100
    if not higher_better:
        pct = 100.0 - pct
    return pd.Series(np.clip(pct, 0, 100), index=series.index)


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

