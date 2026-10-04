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

def test_dml_recovers_known_partial_effect():
    import numpy as np
    from app.services.ml_v2.core.dml import dml_cross_fit
    rng = np.random.default_rng(13)
    z = rng.normal(size=900)
    treatment = 0.7 * z + rng.normal(size=900)
    y = pd.Series(1.8 * treatment + 0.9 * z + rng.normal(scale=0.25, size=900))
    x = pd.DataFrame({"treatment": treatment, "z": z})
    ape, se, _ = dml_cross_fit(x, y, "treatment", dates=pd.date_range("2020-01-01", periods=900))
    assert abs(ape - 1.8) < 0.08
    assert 0 < se < 0.05

def test_cqr_predictions_do_not_use_test_outcomes():
    import numpy as np
    from app.services.ml_v2.core.barriers import _lightgbm_cqr_intervals
    rng = np.random.default_rng(71)
    frame = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=300),
        "ticker": "AAA", "vol_21": rng.uniform(.1, .4, 300),
        "primary_side": rng.choice([-1, 1], 300), "forward_return": rng.normal(0, .02, 300)})
    before, audit = _lightgbm_cqr_intervals(frame, .9, 5, 252)
    changed = frame.copy()
    changed.loc[240:, "forward_return"] += 100
    after, _ = _lightgbm_cqr_intervals(changed, .9, 5, 252)
    np.testing.assert_allclose(before.cqr_lower, after.cqr_lower, equal_nan=True)
    np.testing.assert_allclose(before.cqr_upper, after.cqr_upper, equal_nan=True)
    assert audit["test_rows"] == 60
    assert before.cqr_lower.iloc[:240].isna().all()
