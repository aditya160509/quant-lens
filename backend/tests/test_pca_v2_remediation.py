"""Focused regression tests for PCA V2 review remediations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.pca_v2.core.analytics import blend_covariance, preprocess_returns
from app.services.pca_v2.core.cross_asset import _student_t_em


def test_blend_covariance_uses_true_raw_covariance():
    clean = np.eye(2)
    raw = np.array([[2.0, 0.4], [0.4, 3.0]])
    model = {"cleaned_cov": clean, "raw_cov": raw}
    assert np.allclose(blend_covariance(model, 1.0), raw)
    assert np.allclose(blend_covariance(model, 0.0), clean)


def test_outlier_preprocessing_modes_are_finite_and_shape_preserving():
    frame = pd.DataFrame({"a": [0.0, 0.1, 100.0, -0.1], "b": [0.0, 0.2, -90.0, -0.2]})
    for method in ("none", "winsorize_1_99", "winsorize_2_5_97_5", "huber"):
        result = preprocess_returns(frame, method=method)
        assert result.shape == frame.shape
        assert np.isfinite(result.to_numpy()).all()


def test_student_t_em_returns_symmetric_positive_covariance():
    rng = np.random.default_rng(4)
    frame = pd.DataFrame(rng.standard_t(df=5, size=(250, 4)))
    covariance, meta = _student_t_em(frame, max_iter=20)
    assert meta["estimator"] == "student_t_em"
    assert np.allclose(covariance, covariance.T)
    assert np.linalg.eigvalsh(covariance).min() > 0


def test_trim_does_not_silently_switch_to_winsorization():
    with pytest.raises(ValueError, match="insufficient"):
        preprocess_returns(pd.DataFrame({"a":[0,1,2,100]}),method="trim")
