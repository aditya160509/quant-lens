"""Holdout seal: hide data after a project's sealed_after date from a job."""
from __future__ import annotations

import pandas as pd


def apply_seal(idx: pd.DatetimeIndex, sealed_after, horizon_months: int = 0) -> pd.DatetimeIndex:
    """Keep formation dates whose outcome window ends on or before sealed_after."""
    if not sealed_after:
        return idx
    cutoff = pd.Timestamp(sealed_after)
    return idx[idx + pd.DateOffset(months=int(horizon_months)) <= cutoff]
