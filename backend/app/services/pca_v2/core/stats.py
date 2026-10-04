"""PCA V2 stats helpers."""
from __future__ import annotations
import numpy as np
import pandas as pd


def pastor_stambaugh_gamma(
    returns: pd.DataFrame,
    dollar_volume: pd.DataFrame,
    market_returns: pd.Series,
    window: int = 21,
) -> pd.DataFrame:
    """Pastor-Stambaugh (2003) rolling liquidity gamma per ticker."""
    gammas: dict[str, pd.Series] = {}
    for ticker in returns.columns:
        r = returns[ticker].dropna()
        dv = dollar_volume[ticker].reindex(r.index)
        rm = market_returns.reindex(r.index)
        r_excess = r - rm
        if len(r_excess) < window + 5:
            continue
        rolling_gammas = []
        for end in range(window, len(r_excess)):
            sub_re = r_excess.iloc[end - window: end]
            sub_r = r.iloc[end - window: end]
            sub_dv = dv.iloc[end - window: end]
            y = sub_re.shift(-1).iloc[:-1].to_numpy(dtype=float)
            x1 = sub_r.iloc[:-1].to_numpy(dtype=float)
            signed_vol = (np.sign(sub_re.iloc[:-1]) * sub_dv.iloc[:-1]).to_numpy(dtype=float)
            X = np.column_stack([np.ones(len(y)), x1, signed_vol])
            valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
            if valid.sum() < 5:
                rolling_gammas.append(np.nan)
                continue
            coef = np.linalg.lstsq(X[valid], y[valid], rcond=None)[0]
            rolling_gammas.append(float(coef[2]))
        gammas[ticker] = pd.Series(rolling_gammas, index=r_excess.index[window:])
    return pd.DataFrame(gammas)



def newey_west_se(
    X: np.ndarray,
    residuals: np.ndarray,
    coef_idx: int = 1,
    n_lags: int = 3,
) -> float:
    """Newey-West HAC standard error for coefficient at coef_idx (Bartlett kernel)."""
    from statsmodels.stats.sandwich_covariance import cov_hac
    scores = np.asarray(X) * np.asarray(residuals)[:, None]
    covariance = cov_hac((scores, np.linalg.pinv(X.T @ X)), nlags=n_lags, use_correction=True)
    return float(np.sqrt(max(covariance[coef_idx, coef_idx], 0.0)))

