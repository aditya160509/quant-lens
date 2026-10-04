"""PCA V2 bootstrap primitives."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd


def bai_ng_criteria(
    returns: pd.DataFrame,
    k_max: int = 15,
) -> list[dict]:
    """Proper Bai-Ng (2002) IC1/IC2/IC3 panel factor number criteria.

    SSR(r) is computed from a rank-r factor model at each candidate K.
    """
    from .analytics import eig_sorted
    x = returns.sub(returns.mean()).to_numpy(dtype=float)
    T, N = x.shape
    NT = N * T
    min_NT = min(N, T)
    rows = []
    for r in range(1, min(k_max, min(N, T) - 1) + 1):
        # Fit rank-r factor model and compute SSR
        cov_r = np.cov(x, rowvar=False)
        vals_r, vecs_r = eig_sorted(cov_r)
        k_use = min(r, len(vals_r))
        factors = x @ vecs_r[:, :k_use]  # T x r
        loadings = vecs_r[:, :k_use]     # N x r
        x_hat = factors @ loadings.T     # T x N reconstruction
        ssr = float(np.sum((x - x_hat) ** 2)) / NT
        ssr = max(ssr, 1e-12)
        # Penalty terms
        g_NT = (N + T) / NT
        pen1 = r * g_NT * math.log(NT / max(N + T, 1))
        pen2 = r * g_NT * math.log(min_NT)
        pen3 = r * math.log(min_NT) / min_NT
        rows.append({
            "k": r,
            "SSR": ssr,
            "IC1": math.log(ssr) + pen1,
            "IC2": math.log(ssr) + pen2,
            "IC3": math.log(ssr) + pen3,
        })
    return rows



def block_bootstrap_sample(
    data: np.ndarray,
    block_length: int = 21,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Circular block bootstrap: draw blocks of length block_length to fill T rows."""
    rng = rng or np.random.default_rng()
    T = data.shape[0]
    n_blocks = math.ceil(T / block_length)
    starts = rng.integers(0, T, size=n_blocks)
    rows_list: list[np.ndarray] = []
    for s in starts:
        for t in range(block_length):
            rows_list.append(data[(s + t) % T])
    return np.array(rows_list[:T], dtype=float)



def subsampling_stability(
    model: dict[str, Any],
    n_subsamples: int = 50,
    subsample_fraction: float = 0.7,
    rng_seed: int = 42,
) -> list[dict]:
    """Subsampling stability: cosine similarity between full-sample and subsample loadings."""
    from .analytics import eig_sorted
    rng = np.random.default_rng(rng_seed)
    rets = model.get("analysis_returns", model["returns"]).to_numpy(dtype=float)
    T = rets.shape[0]
    k = model["k"]
    P_full = model.get("orthonormal_eigenvectors", model["eigenvectors"])[:, :k]  # N x K
    sub_size = max(int(T * subsample_fraction), k + 5)
    cosines: list[list[float]] = [[] for _ in range(k)]
    cross = np.zeros((k, k), dtype=float)
    for _ in range(n_subsamples):
        idx = rng.choice(T, size=sub_size, replace=False)
        sub = rets[idx]
        cov_sub = np.cov(sub, rowvar=False)
        _, vecs_sub = eig_sorted(cov_sub)
        P_sub = vecs_sub[:, :k]
        cross += np.abs(P_full.T @ P_sub)
        for j in range(k):
            c = abs(float(P_full[:, j] @ P_sub[:, j]))
            cosines[j].append(min(c, 1.0))
    rows = []
    for j in range(k):
        rows.append({
            "component": f"PC{j+1}",
            "mean_cosine": float(np.mean(cosines[j])),
            "min_cosine": float(np.min(cosines[j])),
            "std_cosine": float(np.std(cosines[j])),
        })
    cross /= max(n_subsamples, 1)
    for i in range(k):
        for j in range(k):
            rows.append({
                "row": f"PC{i+1}", "col": f"PC{j+1}",
                "cross_cosine": float(cross[i, j]), "record_type": "cross_matrix",
            })
    return rows



def subspace_principal_angles(
    P1: np.ndarray,
    P2: np.ndarray,
) -> np.ndarray:
    """Principal angles between two K-dimensional subspaces via SVD of P1^T P2."""
    M = P1.T @ P2
    sv = np.linalg.svd(M, compute_uv=False)
    sv = np.clip(sv, -1.0, 1.0)
    return np.arccos(sv)



def bootstrap_validation(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .analytics import covariance_estimator, eig_sorted, number_like, parse_compute_mode
    payload = payload or {}
    mode = parse_compute_mode(payload)
    b = int(payload.get("bootstrap_runs", 500 if mode == "research" else 200))
    if not 2 <= b <= 1000:
        raise ValueError("bootstrap_runs must be between 2 and 1000")
    model["bootstrap_runs_requested"] = b
    model["bootstrap_runs_executed"] = b
    bootstrap_type = str(payload.get("bootstrap_type") or "case").lower()
    confidence = float(number_like(payload.get("confidence_level"), 0.90) or 0.90)
    confidence = confidence / 100.0 if confidence > 1 else confidence
    if not 0 < confidence < 1:
        raise ValueError("confidence_level must be strictly between 0 and 1, or a percentage strictly below 100")
    tail = 50.0 * (1.0 - confidence)
    block_length = int(number_like(payload.get("block_length"), 21) or 21)
    rng = np.random.default_rng(7)
    rets = model.get("analysis_returns", model["returns"])
    x = rets.to_numpy(dtype=float)
    k = model["k"]
    evals_list: list[np.ndarray] = []
    cosines: list[list[float]] = [[] for _ in range(k)]
    angle_samples: list[np.ndarray] = []
    full_subspace = model.get("orthonormal_eigenvectors", model["eigenvectors"])[:, :k]
    fitted = x @ full_subspace @ full_subspace.T
    residuals = x - fitted
    for _ in range(b):
        if bootstrap_type == "residual":
            idx = rng.integers(0, len(x), len(x))
            sample_x = fitted + residuals[idx]
            sample = pd.DataFrame(sample_x, columns=rets.columns)
        elif bootstrap_type == "block":
            sample_x = block_bootstrap_sample(x, block_length=block_length, rng=rng)
            sample = pd.DataFrame(sample_x, columns=rets.columns)
        else:
            idx = rng.integers(0, len(x), len(x))
            sample = pd.DataFrame(x[idx], columns=rets.columns)
        cov, _ = covariance_estimator(sample, model["cov_meta"].get("estimator", "ledoit_wolf"))
        vals, vecs = eig_sorted(cov)
        evals_list.append(vals[: len(model["eigenvalues"])])
        for j in range(k):
            cosines[j].append(abs(float(model.get("orthonormal_eigenvectors", model["eigenvectors"])[:, j] @ vecs[:, j])))
        angle_samples.append(np.degrees(subspace_principal_angles(full_subspace, vecs[:, :k])))
    e = np.asarray(evals_list)
    bands = []
    for j in range(e.shape[1]):
        low = float(np.percentile(e[:, j], tail))
        high = float(np.percentile(e[:, j], 100.0 - tail))
        bands.append({"component": f"PC{j+1}", "eigenvalue": float(model["eigenvalues"][j]), "ci_low": low, "ci_high": high, "confidence_level": confidence, "mp_lambda_max": float(model["mp"]["lambda_max"]), "verdict": "robust" if low > model["mp"]["lambda_max"] else "marginal" if high > model["mp"]["lambda_max"] else "noise"})
    scorecard = []
    for j in range(k):
        vals_arr = np.asarray(cosines[j])
        scorecard.append({"component": f"PC{j+1}", "cosine_mean": float(vals_arr.mean()), "cosine_p05": float(np.percentile(vals_arr, 5)), "verdict": "Statistically Robust" if vals_arr.mean() > 0.9 and np.percentile(vals_arr, 5) > 0.8 else "Marginal" if vals_arr.mean() > 0.7 else "Potentially Spurious"})
    # Subsampling stability (distinct from bootstrap)
    sub_stability = subsampling_stability(model, n_subsamples=min(50, b), rng_seed=42)
    principal_angles = []
    if angle_samples:
        arr = np.vstack(angle_samples)
        for j in range(arr.shape[1]):
            principal_angles.append(
                {
                    "component": f"Angle{j+1}",
                    "mean_angle_degrees": float(np.mean(arr[:, j])),
                    "p95_angle_degrees": float(np.percentile(arr[:, j], 95)),
                    "max_angle_degrees": float(np.max(arr[:, j])),
                }
            )
    return {"bootstrap_bands": bands, "genuineness_scorecard": scorecard, "bootstrap_runs": b, "bootstrap_type": bootstrap_type, "confidence_level": confidence, "subsampling_stability": sub_stability, "principal_angles": principal_angles}

