"""PCA V2 factors primitives."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd


def factor_returns(model: dict[str, Any], k: int | None = None) -> pd.DataFrame:
    k = int(k or model["k"])
    data = model.get("analysis_returns", model["returns"]).to_numpy(dtype=float)
    loadings = model.get("orthonormal_eigenvectors", model["eigenvectors"])[:, :k]
    factors = data @ loadings
    return pd.DataFrame(factors, index=model["returns"].index, columns=[f"PC{i+1}" for i in range(k)])



def loading_records(model: dict[str, Any], k: int | None = None) -> list[dict[str, Any]]:
    k = int(k or model["k"])
    sectors = model["sectors"]
    records = []
    for i, ticker in enumerate(model["symbols"]):
        row = {"ticker": ticker, "sector": sectors.get(ticker, "Unknown")}
        for pc in range(k):
            row[f"PC{pc+1}"] = float(model.get("orthonormal_eigenvectors", model["eigenvectors"])[i, pc])
        records.append(row)
    return records



def explained_variance_records(model: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    vals = model["eigenvalues"]
    total = max(float(vals.sum()), 1e-12)
    cum = np.cumsum(vals) / total
    n = limit or min(len(vals), 50)
    return [
        {"component": f"PC{i+1}", "rank": i + 1, "eigenvalue": float(vals[i]), "explained_variance": float(vals[i] / total), "cumulative_variance": float(cum[i])}
        for i in range(min(n, len(vals)))
    ]



def varimax(loadings: np.ndarray, gamma: float = 1.0, q: int = 80, tol: float = 1e-6) -> np.ndarray:
    p, k = loadings.shape
    r = np.eye(k)
    d = 0.0
    for _ in range(q):
        old = d
        lam = loadings @ r
        u, s, vh = np.linalg.svd(loadings.T @ (lam ** 3 - (gamma / p) * lam @ np.diag(np.diag(lam.T @ lam))))
        r = u @ vh
        d = float(np.sum(s))
        if old and d / old < 1 + tol:
            break
    return loadings @ r



def promax(loadings: np.ndarray, power: int = 3, q: int = 80, tol: float = 1e-6) -> np.ndarray:
    """Promax oblique rotation: varimax then raise to power to sharpen."""
    vm = varimax(loadings, gamma=1.0, q=q, tol=tol)
    # Raise each element to power (preserving sign)
    target = np.sign(vm) * np.abs(vm) ** power
    # Solve for oblique rotation matrix: L @ R = target
    result = np.linalg.lstsq(vm, target, rcond=None)[0]
    rotated = vm @ result
    # Column-normalize
    norms = np.sqrt((rotated ** 2).sum(axis=0))
    norms[norms < 1e-12] = 1.0
    return rotated / norms



def hoyer_sparsity(loadings: np.ndarray) -> list[dict]:
    """Hoyer sparsity score per PC column. Higher = more concentrated = more interpretable."""
    n, k = loadings.shape
    rows = []
    for j in range(k):
        col = loadings[:, j]
        l1 = float(np.sum(np.abs(col)))
        l2 = float(np.sqrt(np.sum(col ** 2)))
        # Hoyer: (sqrt(n) - l1/l2) / (sqrt(n) - 1), in [0,1]
        sparsity = (math.sqrt(n) - l1 / max(l2, 1e-12)) / max(math.sqrt(n) - 1, 1e-12)
        rows.append({"component": f"PC{j+1}", "hoyer_sparsity": float(np.clip(sparsity, 0, 1))})
    return rows



def asset_r2(model: dict[str, Any]) -> list[dict]:
    """Per-asset R² explained by the retained PCs."""
    k = model["k"]
    vecs = model["eigenvectors"][:, :k]
    evals = model["eigenvalues"][:k]
    diag_cov = np.diag(model["cov"])
    r2_vals = np.sum(vecs ** 2 * evals, axis=1) / np.maximum(diag_cov, 1e-12)
    return [
        {
            "ticker": model["symbols"][i],
            "sector": model["sectors"].get(model["symbols"][i], "Unknown"),
            "r2": float(np.clip(r2_vals[i], 0.0, 1.0)),
            "idiosyncratic_share": float(np.clip(1 - r2_vals[i], 0.0, 1.0)),
        }
        for i in range(len(model["symbols"]))
    ]



def hierarchical_pca(
    returns: pd.DataFrame,
    sectors: dict[str, str],
    k_intra: int = 2,
    k_cross: int = 3,
    estimator: str = "ledoit_wolf",
) -> dict:
    """Two-level Hierarchical PCA: intra-cluster then cross-cluster."""
    from .analytics import compact_records, covariance_estimator, eig_sorted
    from collections import defaultdict
    cluster_map: dict[str, list[str]] = defaultdict(list)
    for ticker, sector in sectors.items():
        if ticker in returns.columns:
            cluster_map[sector].append(ticker)

    cluster_factors: dict[str, pd.DataFrame] = {}
    cluster_loadings: dict[str, dict] = {}
    for sector, tickers in cluster_map.items():
        if len(tickers) < 2:
            continue
        sub_rets = returns[tickers]
        cov, _ = covariance_estimator(sub_rets, estimator)
        vals, vecs = eig_sorted(cov)
        kk = min(k_intra, len(tickers) - 1, len(vals))
        f = sub_rets.to_numpy(dtype=float) @ vecs[:, :kk]
        cluster_factors[sector] = pd.DataFrame(
            f, index=returns.index,
            columns=[f"{sector}_PC{i+1}" for i in range(kk)]
        )
        cluster_loadings[sector] = {
            "tickers": tickers,
            "loadings": vecs[:, :kk].tolist(),
            "eigenvalues": vals[:kk].tolist(),
        }

    if len(cluster_factors) < 2:
        return {"cluster_factors": {k: v.to_dict("records") for k, v in cluster_factors.items()}, "cross_loadings": None}

    cross_rets = pd.concat(list(cluster_factors.values()), axis=1).dropna(how="any")
    cov2, _ = covariance_estimator(cross_rets, estimator)
    vals2, vecs2 = eig_sorted(cov2)
    kk2 = min(k_cross, cross_rets.shape[1] - 1)
    cross_factor_rets = pd.DataFrame(
        cross_rets.to_numpy(dtype=float) @ vecs2[:, :kk2],
        index=returns.index,
        columns=[f"Cross_PC{i+1}" for i in range(kk2)]
    )
    return {
        "cluster_loadings": cluster_loadings,
        "cross_factor_returns": compact_records(cross_factor_rets.reset_index(names="date"), limit=500),
        "cross_eigenvalues": vals2[:kk2].tolist(),
        "cross_column_names": list(cross_rets.columns),
    }

