"""Historical factor weighting and next-close long-short portfolios."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from .common import build_provenance, response, summary, matrix_records
from .data_loader import universe_label
from .panel import load_context, make_feature_panel, numeric_xy
from .performance import fast_spearman_ic
from .portfolio import execute_portfolio


def daily_ic_table(features, targets, dates):
    """Per-date cross-sectional Spearman IC of every feature column against the target (NaN below 4 pairs)."""
    x = features.to_numpy(float)
    y = targets.reindex(features.index).to_numpy(float)
    codes, days = pd.factorize(pd.Series(np.asarray(dates)), sort=True)
    order = np.argsort(codes, kind="stable")
    edges = np.flatnonzero(np.diff(codes[order])) + 1
    rows = []
    for day, idx in zip(days, np.split(order, edges)):
        if len(idx) < 4:
            continue
        rows.append([fast_spearman_ic(x[idx, j], y[idx]) for j in range(x.shape[1])])
        rows[-1] = dict(zip(features.columns, rows[-1]), date=day)
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(columns=features.columns)
