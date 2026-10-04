"""Historical PCA estimates using only observations available at formation."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_residuals(returns: pd.DataFrame, window: int = 126, k: int | None = None, estimator: str = "ledoit_wolf") -> pd.DataFrame:
    """Fit basis and residual betas on [t-window,t), score the observed row t."""
    from .analytics import covariance_estimator, eig_sorted, fit_mp_sigma2, mp_threshold
    if window < 30:
        raise ValueError("pca_window must be at least 30 observations")
    rows = []
    dates = []
    for end in range(window, len(returns)):
        train = returns.iloc[end-window:end]
        cov, _ = covariance_estimator(train, estimator)
        vals, vectors = eig_sorted(cov)
        count = k
        if count is None:
            mp = mp_threshold(vals, len(train.columns), len(train), fit_mp_sigma2(vals, len(train.columns), len(train)))
            count = max(1, int(np.sum(vals > mp["lambda_max"])))
        basis = vectors[:, :min(int(count), len(vectors)-1)]
        x = train.to_numpy(dtype=float)
        factors = x @ basis
        design = np.column_stack([np.ones(len(x)), factors])
        beta = np.linalg.lstsq(design, x, rcond=None)[0]
        today = returns.iloc[end].to_numpy(dtype=float)
        residual = today - np.r_[1.0, today @ basis] @ beta
        rows.append(residual)
        dates.append(returns.index[end])
    return pd.DataFrame(rows, index=pd.Index(dates, name=returns.index.name), columns=returns.columns)
