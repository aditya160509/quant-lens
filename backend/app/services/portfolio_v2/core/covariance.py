"""Portfolio V2 covariance engine."""

from __future__ import annotations
from typing import Any
from functools import lru_cache
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf, OAS
from .performance import (
    cached_correlation_frame,
    cached_covariance_frame,
    nearest_psd,
)


@lru_cache(maxsize=128)
def _ewma_weights(lam: float, n: int) -> np.ndarray:
    i = np.arange(n - 1, -1, -1, dtype=np.float64)
    w = (1.0 - lam) * np.power(lam, i)
    w /= w.sum()
    return w


def covariance_matrix(
    returns: pd.DataFrame, method: str = "ledoit_wolf"
) -> tuple[pd.DataFrame, dict[str, Any]]:
    method = str(method or "ledoit_wolf").lower().replace("-", "_")
    if returns.empty:
        return pd.DataFrame(), {"estimator": method}

    def build() -> tuple[pd.DataFrame, dict[str, Any]]:
        complete = returns.dropna()
        if len(complete) < 2:
            raise ValueError("Covariance requires complete observations")
        x = complete.to_numpy(dtype=np.float64, copy=False)
        meta: dict[str, Any] = {"estimator": method}
        if method in {"dcc_garch", "dcc"}:
            out = dcc_garch_cov(returns)
            return out["covariance"], {
                "estimator": "dcc_garch",
                "note": "Two-stage Gaussian GARCH(1,1) and constrained Gaussian DCC MLE; historical fitted path is retrospective",
            }
        if method in {"factor_structured", "ff5", "structured"}:
            return factor_structured_cov(returns), {"estimator": "factor_structured"}
        if method in {"gerber", "gerber_statistic"}:
            return gerber_statistic_cov(returns), {"estimator": "gerber"}
        if method in {"ledoit_wolf", "lw"}:
            x_centered = x - x.mean(axis=0)
            est = LedoitWolf(assume_centered=True).fit(x_centered)
            meta["shrinkage"] = float(est.shrinkage_)
            cov = est.covariance_
        elif method == "eigenvalue_shrinkage":
            # Rotation-equivariant eigenvalue regularisation.  It retains the
            # sample eigenvectors while shrinking noisy small eigenvalues toward
            # their bulk median, unlike the scalar Ledoit-Wolf estimator.
            sample = np.cov(x, rowvar=False)
            vals, vecs = np.linalg.eigh((sample + sample.T) * 0.5)
            bulk = float(np.median(np.maximum(vals, 1e-12)))
            aspect = x.shape[1] / max(x.shape[0], 1)
            strength = min(0.85, max(0.10, aspect))
            shrunk = (1.0 - strength) * np.maximum(vals, 1e-12) + strength * bulk
            cov = (vecs * shrunk) @ vecs.T
            meta.update(
                {
                    "shrinkage": strength,
                    "eigenvalue_floor": bulk,
                    "methodology": "rotation_equivariant_eigenvalue_shrinkage",
                }
            )
        elif method == "oas":
            est = OAS().fit(x)
            meta["shrinkage"] = float(est.shrinkage_)
            cov = est.covariance_
        elif method in {"constant_correlation", "cc"}:
            vols = complete.std()
            corr = cached_correlation_frame(complete)
            avg = (
                float((corr.to_numpy()[np.triu_indices(len(corr), 1)]).mean())
                if len(corr) > 1
                else 0.0
            )
            cov = np.outer(vols, vols) * avg
            np.fill_diagonal(cov, vols.to_numpy() ** 2)
            meta["average_correlation"] = avg
        elif method == "ewma":
            lam = 0.94
            w = _ewma_weights(lam, len(x))
            xc = x - np.average(x, axis=0, weights=w)
            # einsum: cov[j,k] = sum_i w[i] * xc[i,j] * xc[i,k]
            cov = np.einsum("i,ij,ik->jk", w, xc, xc)
            meta["lambda"] = lam
        elif method == "sample":
            cov = np.atleast_2d(np.cov(x, rowvar=False))
        else:
            raise ValueError("Unknown or unavailable covariance estimator: " + method)
        raw_cov = (cov + cov.T) / 2
        cov = nearest_psd(raw_cov)
        meta["psd_projection_frobenius"] = float(np.linalg.norm(cov - raw_cov))
        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns), meta

    return cached_covariance_frame(returns, method, build)


def expected_returns(
    returns: pd.DataFrame, method: str = "shrinkage", ann: float = 252.0
) -> pd.Series:
    if method not in {"sample", "mean", "shrinkage"}:
        raise ValueError("Unknown expected return estimator: " + method)
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Expected returns require complete finite observations")
    mu = returns.mean() * ann
    if method in {"sample", "mean"}:
        return mu
    grand = float(mu.mean()) if len(mu) else 0.0
    n = max(len(returns), 1)
    shrink = min(0.75, max(0.15, 20.0 / n))
    return (1 - shrink) * mu + shrink * grand


def dcc_garch_cov(returns, alpha=0.03, beta=0.94):
    from arch import arch_model
    from scipy.optimize import minimize

    r = returns.dropna()
    if len(r) < 100:
        raise ValueError("DCC-GARCH requires at least 100 complete returns")
    zs = []
    vs = []
    for c in r:
        fit = arch_model(
            r[c] * 100, mean="Constant", vol="GARCH", p=1, q=1, rescale=False
        ).fit(disp="off", show_warning=False)
        if fit.convergence_flag:
            raise ValueError(f"GARCH fit failed for {c}")
        zs.append(np.asarray(fit.std_resid))
        vs.append(np.asarray(fit.conditional_volatility) / 100)
    z = np.column_stack(zs)
    vol = np.column_stack(vs)
    qbar = np.cov(z, rowvar=False)

    def evaluate(parameters, keep=False):
        a, b = parameters
        q = qbar.copy()
        total = 0
        history = []
        for t in range(len(z)):
            if t:
                q = (1 - a - b) * qbar + a * np.outer(z[t - 1], z[t - 1]) + b * q
            diagonal = np.sqrt(np.diag(q))
            corr = q / np.outer(diagonal, diagonal)
            sign, det = np.linalg.slogdet(corr)
            if sign <= 0:
                return np.inf
            total += det + z[t] @ np.linalg.solve(corr, z[t])
            if keep:
                history.append(
                    {
                        "date": r.index[t],
                        "avg_correlation": float(
                            corr[np.triu_indices(len(corr), 1)].mean()
                        )
                        if len(corr) > 1
                        else 1.0,
                    }
                )
        return (corr * np.outer(vol[-1], vol[-1]), history) if keep else total

    fit = minimize(
        evaluate,
        [alpha, beta],
        bounds=[(1e-6, 0.999), (1e-6, 0.999)],
        constraints={"type": "ineq", "fun": lambda p: 0.999 - p.sum()},
        method="SLSQP",
    )
    if not fit.success:
        raise ValueError("DCC MLE failed: " + fit.message)
    cov, history = evaluate(fit.x, True)
    return {
        "covariance": pd.DataFrame(cov, index=r.columns, columns=r.columns),
        "average_correlation_series": history,
        "alpha": float(fit.x[0]),
        "beta": float(fit.x[1]),
    }


def gerber_statistic_cov(returns, threshold=0.5):
    r = returns.dropna()
    sigma = r.std().to_numpy()
    if len(r) < 2 or (sigma <= 0).any():
        raise ValueError(
            "Gerber covariance requires nonconstant complete observed returns"
        )
    values = r.to_numpy()
    positive = (values > threshold * sigma).astype(float)
    negative = (values < -threshold * sigma).astype(float)
    neutral = 1 - positive - negative
    numerator = (
        positive.T @ positive
        + negative.T @ negative
        - positive.T @ negative
        - negative.T @ positive
    )
    denominator = len(r) - neutral.T @ neutral
    if (denominator <= 0).any():
        raise ValueError("No Gerber threshold events for a pair")
    correlation = numerator / denominator
    return pd.DataFrame(
        correlation * np.outer(sigma, sigma), index=r.columns, columns=r.columns
    )


def factor_structured_cov(returns, factors=None):
    from .data_loader import load_factor_returns

    if factors is None:
        factors = load_factor_returns().set_index("date")[
            ["mkt_rf", "smb", "hml", "rmw", "cma"]
        ]
    joined = returns.join(factors, how="inner").dropna()
    if len(joined) < max(30, len(factors.columns) + 2):
        raise ValueError("Insufficient observed FF5 overlap")
    f = joined[factors.columns]
    r = joined[returns.columns]
    X = np.c_[np.ones(len(f)), f.to_numpy()]
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("Factor design is rank-deficient")
    betas = np.linalg.lstsq(X, r.to_numpy(), rcond=None)[0]
    resid = r.to_numpy() - X @ betas
    b = betas[1:].T
    structured = b @ f.cov().to_numpy() @ b.T + np.diag(resid.var(axis=0, ddof=1))
    return pd.DataFrame(structured, index=r.columns, columns=r.columns)
