"""Date-group validation with label-overlap purging."""
from __future__ import annotations
import numpy as np
import pandas as pd

def chronological_purged_split(panel, horizon=5, embargo=5, train_fraction=0.75):
    """Hold out final dates, leaving a horizon plus embargo gap before test."""
    dates = pd.to_datetime(panel["date"], errors="raise")
    unique = pd.DatetimeIndex(dates.unique()).sort_values()
    if horizon < 1 or embargo < 0 or not 0 < train_fraction < 1:
        raise ValueError("Invalid horizon, embargo, or training fraction")
    cut = int(len(unique) * train_fraction)
    end = cut - horizon - embargo
    if end < 2 or cut >= len(unique):
        raise ValueError("Insufficient distinct dates for purged chronological validation")
    train = np.flatnonzero(dates.isin(unique[:end]).to_numpy())
    test = np.flatnonzero(dates.isin(unique[cut:]).to_numpy())
    return train, test

def purged_date_folds(panel, n_splits=5, horizon=5, embargo=5):
    """Expanding historical training windows; never train on future dates."""
    from sklearn.model_selection import TimeSeriesSplit
    dates = pd.to_datetime(panel["date"], errors="raise")
    unique = pd.DatetimeIndex(dates.unique()).sort_values()
    splitter = TimeSeriesSplit(n_splits=n_splits, gap=horizon + embargo)
    for train_dates, test_dates in splitter.split(unique):
        yield (np.flatnonzero(dates.isin(unique[train_dates]).to_numpy()),
               np.flatnonzero(dates.isin(unique[test_dates]).to_numpy()))
