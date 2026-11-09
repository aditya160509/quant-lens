"""Run-scoped sharing for point-in-time panels; every formula stays in its original module.

EMA, Wilder and OBV values are seeded at the start of each formation date's window,
so one whole-history pass would change them. Only repeated work is removed here.
"""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import pandas as pd

from . import estimators, fundamentals
from .performance import _PIT_MEMO as _MEMO
from .stats import TRADING_DAYS

_idiosyncratic_vol = estimators._idiosyncratic_vol
_statement_snapshots = fundamentals.statement_snapshots


@contextmanager
def pit_scope(memo: dict):
    token = _MEMO.set(memo)
    try:
        yield
    finally:
        _MEMO.reset(token)


def _shared_statements(symbols):
    memo = _MEMO.get()
    if memo is None:
        return _statement_snapshots(symbols)
    # Date-independent: callers apply the 90-day lag afterwards through eligible_reports.
    key = ("statements", tuple(symbols))
    if key not in memo:
        memo[key] = _statement_snapshots(symbols)
    return memo[key]


def batched_idiosyncratic_vol(returns: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """One least-squares projection for all tickers; a ticker needs all 63 rows, so X is shared."""
    required = ["mkt_rf", "smb", "hml", "rf"]
    if len(returns) != 63 or not set(required).issubset(factors.columns) or np.isinf(returns.to_numpy(dtype=float)).any():
        return _idiosyncratic_vol(returns, factors)
    out = pd.Series(np.nan, index=returns.columns, dtype=float)
    aligned = factors.set_index("date")[required].reindex(returns.index).to_numpy(dtype=float)
    complete = returns.notna().all().to_numpy()
    if np.isnan(aligned).any() or not complete.any():
        return out
    y = returns.to_numpy(dtype=float)[:, complete] - aligned[:, 3:]
    x = np.column_stack([np.ones(63), aligned[:, :3]])
    residuals = y - x @ (np.linalg.pinv(x) @ y)
    out.iloc[np.flatnonzero(complete)] = np.sqrt((residuals**2).mean(axis=0) * TRADING_DAYS)
    return out


def _dispatch_idiosyncratic_vol(returns, factors):
    return (_idiosyncratic_vol if _MEMO.get() is None else batched_idiosyncratic_vol)(returns, factors)


# shortcut: rebinds names inside estimators and fundamentals, which this work could not edit; move into them when free.
estimators._idiosyncratic_vol = _dispatch_idiosyncratic_vol
fundamentals.statement_snapshots = _shared_statements
