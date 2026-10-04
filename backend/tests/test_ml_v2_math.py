"""Golden validation accounting and temporal leakage regressions."""
import pandas as pd
from app.services.ml_v2.core.validation import chronological_purged_split, purged_date_folds

def test_holdout_uses_dates_not_ticker_blocks():
    dates = pd.date_range("2024-01-01", periods=100)
    panel = pd.DataFrame({"date": list(dates) * 3})
    train, test = chronological_purged_split(panel, horizon=5, embargo=3)
    assert len(train) == 67 * 3
    assert len(test) == 25 * 3
    assert panel.date.iloc[train].max() == dates[66]
    assert panel.date.iloc[test].min() == dates[75]

def test_expanding_folds_have_no_future_training():
    panel = pd.DataFrame({"date": list(pd.date_range("2024-01-01", periods=100)) * 2})
    for train, test in purged_date_folds(panel, n_splits=3, horizon=5, embargo=2):
        assert panel.date.iloc[train].max() + pd.Timedelta(days=7) < panel.date.iloc[test].min()

def test_spearman_ties_match_scipy():
    import numpy as np
    from scipy.stats import spearmanr
    from app.services.ml_v2.core.performance import fast_spearman_ic
    x = np.array([1., 1., 2., 3., 3., 4.])
    y = np.array([4., 2., 2., 1., 3., 3.])
    assert abs(fast_spearman_ic(x, y) - spearmanr(x, y).statistic) < 1e-12
