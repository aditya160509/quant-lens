"""PCA V2 pca math primitives."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf, MinCovDet, OAS


def covariance_estimator(returns: pd.DataFrame, method: str = "ledoit_wolf", ewma_lambda: float = 0.94) -> tuple[np.ndarray, dict[str, Any]]:
    x = returns.to_numpy(dtype=float)
    if len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("Covariance requires finite observed returns; missing values must be explicitly removed")
    method = str(method or "ledoit_wolf").lower().replace("-", "_")
    meta: dict[str, Any] = {"estimator": method}
    if method in {"ledoit_wolf", "lw"}:
        est = LedoitWolf().fit(x)
        meta["shrinkage"] = float(est.shrinkage_)
        return est.covariance_, meta
    if method == "oas":
        est = OAS().fit(x)
        meta["shrinkage"] = float(est.shrinkage_)
        return est.covariance_, meta
    if method in {"mcd", "mincovdet", "minimum_covariance_determinant"}:
        if len(x) <= 2 * x.shape[1]:
            raise ValueError("MCD requires more than twice as many observations as assets")
        est = MinCovDet(random_state=7, support_fraction=0.75).fit(x)
        meta["support_fraction"] = float(np.mean(est.support_))
        return est.covariance_, meta
    if method == "ewma":
        lam = min(0.995, max(0.50, float(ewma_lambda)))
        w = np.array([(1 - lam) * lam ** i for i in range(len(x) - 1, -1, -1)], dtype=float)
        w = w / max(w.sum(), 1e-12)
        xc = x - np.average(x, axis=0, weights=w)
        cov = (xc * w[:, None]).T @ xc
        meta["ewma_lambda"] = lam
        meta["half_life"] = float(np.log(0.5) / np.log(lam))
        return cov, meta
    if method not in {"sample", "empirical"}:
        raise ValueError(f"Unknown covariance estimator: {method}")
    return np.atleast_2d(np.cov(x, rowvar=False)), meta



def eig_sorted(cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vals, vecs = np.linalg.eigh((cov + cov.T) / 2)
    idx = np.argsort(vals)[::-1]
    return np.maximum(vals[idx], 0.0), vecs[:, idx]



def mp_threshold(eigenvalues: np.ndarray, n_assets: int, n_obs: int, sigma2: float | None = None) -> dict[str, float]:
    q = max(float(n_assets) / max(float(n_obs), 1.0), 1e-9)
    vals = np.asarray(eigenvalues, dtype=float)
    sigma = float(sigma2) if sigma2 is not None else float(np.nanmedian(vals) if len(vals) else 1.0)
    sigma = max(sigma, 1e-12)
    root = math.sqrt(q)
    return {
        "q_ratio": q,
        "sigma2": sigma,
        "lambda_min": sigma * (1 - root) ** 2,
        "lambda_max": sigma * (1 + root) ** 2,
    }



def scree_elbow(eigenvalues: np.ndarray) -> int:
    vals = np.asarray(eigenvalues, dtype=float)
    if len(vals) < 3:
        return max(1, len(vals))
    second = vals[:-2] - 2 * vals[1:-1] + vals[2:]
    return int(np.argmax(second) + 1)



def choose_k(eigenvalues: np.ndarray, mp: dict[str, float], payload: dict[str, Any] | None = None) -> dict[str, int]:
    from .analytics import number_like
    payload = payload or {}
    vals = np.asarray(eigenvalues, dtype=float)
    total = max(float(vals.sum()), 1e-12)
    variance_threshold = float(number_like(payload.get("variance_threshold"), 0.95) or 0.95)
    k_rmt = int(np.sum(vals > mp["lambda_max"]))
    k_var = int(np.searchsorted(np.cumsum(vals) / total, variance_threshold) + 1)
    correlation = payload.get("matrix_type") in {"correlation", "corr"} or payload.get("standardize") is True
    k_kaiser = int(np.sum(vals > 1.0)) if correlation else None
    k_elbow = scree_elbow(vals)
    manual = payload.get("component_count") or payload.get("k") or payload.get("K")
    k_manual = int(number_like(manual, k_rmt) or k_rmt)
    method = payload.get("k_method", "rmt")
    criteria = {"rmt": k_rmt, "variance": k_var, "variance_threshold": k_var, "kaiser": k_kaiser, "elbow": k_elbow, "scree_elbow": k_elbow, "manual": k_manual}
    if method not in criteria or criteria[method] is None:
        raise ValueError("Kaiser selection requires correlation PCA; select a valid k_method")
    requested_k = k_manual if manual is not None else criteria[method]
    if requested_k <= 0:
        raise ValueError("No eigenvalues satisfy the selected retention rule; choose an explicit manual K to inspect noise components")
    k = int(min(len(vals), requested_k))
    return {"selected": k, "rmt": k_rmt, "variance_threshold": k_var, "kaiser": k_kaiser, "scree_elbow": k_elbow}



def fit_mp_sigma2(eigenvalues: np.ndarray, n_assets: int, n_obs: int, n_iter: int = 50) -> float:
    """Iterative sigma² estimation via Marchenko-Pastur moment matching.

    Fits sigma² so that E[lambda_max_MP] = empirical mean of noise eigenvalues.
    Returns sigma² for the noise floor.
    """
    vals = np.asarray(eigenvalues, dtype=float)
    q = max(float(n_assets) / max(float(n_obs), 1.0), 1e-9)
    # Start: use median of all eigenvalues as initial sigma2
    sigma2 = float(np.median(vals))
    sigma2 = max(sigma2, 1e-12)
    for _ in range(n_iter):
        lam_max = sigma2 * (1 + math.sqrt(q)) ** 2
        # Noise eigenvalues = those below current lam_max
        noise = vals[vals <= lam_max]
        if len(noise) == 0:
            break
        # MP moment: E[lambda] = sigma2 (the mean of MP distribution = sigma2)
        new_sigma2 = float(np.mean(noise))
        new_sigma2 = max(new_sigma2, 1e-12)
        if abs(new_sigma2 - sigma2) < 1e-10:
            break
        sigma2 = new_sigma2
    return sigma2



def preprocess_returns(
    returns: pd.DataFrame,
    method: str = "none",
    z_threshold: float = 4.0,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> pd.DataFrame:
    """Apply an explicit, user-selected robust preprocessing method."""
    x = returns.copy()
    if not np.isfinite(x.to_numpy(dtype=float)).all():
        raise ValueError("Outlier preprocessing requires finite returns")
    method = str(method or "none").lower()
    if method in {"none", "off", "false"}:
        return x
    if method in {"winsorize_1_99", "winsorize", "quantile"}:
        return x.clip(lower=x.quantile(lower_quantile), upper=x.quantile(upper_quantile), axis=1)
    if method in {"winsorize_2_5_97_5", "winsorize_2.5_97.5"}:
        return x.clip(lower=x.quantile(0.025), upper=x.quantile(0.975), axis=1)
    if method in {"trim", "trimming"}:
        lower, upper = x.quantile(lower_quantile), x.quantile(upper_quantile)
        keep = x.ge(lower, axis=1).all(axis=1) & x.le(upper, axis=1).all(axis=1)
        if int(keep.sum()) < max(10, x.shape[1]+2):
            raise ValueError("Trimming leaves insufficient observations")
        return x.loc[keep]
    mean = x.mean()
    std = x.std().replace(0, np.nan).fillna(1.0)
    if method in {"huber", "huber_m", "huber_m_estimation"}:
        center = x.median()
        scale = (x.sub(center).abs().median() * 1.4826).replace(0, np.nan).fillna(std)
        c = max(0.5, float(z_threshold))
        for _ in range(20):
            residual = x.sub(center).div(scale)
            weights = (c / residual.abs().clip(lower=c)).clip(upper=1.0)
            new_center = (x * weights).sum() / weights.sum().replace(0, np.nan)
            if float((new_center - center).abs().max()) < 1e-10:
                break
            center = new_center.fillna(center)
        return center + x.sub(center).clip(lower=-c * scale, upper=c * scale, axis=1)
    if method != "winsorize_z":
        raise ValueError(f"Unknown outlier method: {method}")
    z = (x - mean) / std
    clipped = z.clip(lower=-z_threshold, upper=z_threshold)
    return mean + clipped * std



def blend_covariance(model: dict[str, Any], blend_gamma: float = 0.0) -> np.ndarray:
    """Return a convex blend between the RMT-cleaned covariance (gamma=0)
    and the raw sample covariance (gamma=1).

    C_blend = (1 - gamma) * C_cleaned + gamma * C_sample

    Args:
        model: Output of rmt_model().
        blend_gamma: Float in [0, 1]. 0 = full RMT cleaning, 1 = raw sample cov.

    Returns:
        Blended covariance matrix as ndarray.
    """
    gamma = float(np.clip(blend_gamma, 0.0, 1.0))
    c_clean = model["cleaned_cov"]
    c_sample = model.get("raw_cov")
    if c_sample is None:
        c_sample = np.cov(model["returns"].to_numpy(dtype=float), rowvar=False)
    return (1.0 - gamma) * c_clean + gamma * c_sample



def mp_density(mp, points=200):
    low, high = mp["lambda_min"], mp["lambda_max"]
    x = np.linspace(max(low, 1e-12), high, points)
    density = np.sqrt(np.maximum((high-x)*(x-low), 0)) / (2*np.pi*mp["q_ratio"]*mp["sigma2"]*x)
    return [{"eigenvalue":float(value),"density":float(d)} for value,d in zip(x,density)]
