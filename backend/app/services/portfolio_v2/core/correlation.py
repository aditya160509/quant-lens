"""Portfolio V2 correlation engine."""

from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from .performance import (
    cached_correlation_frame,
    fast_network_edges_from_corr,
    rolling_diversification_ratio,
    rolling_leading_eigenvalue,
    safe_inverse,
)
from .covariance import covariance_matrix


def network_edges(
    returns: pd.DataFrame, threshold: float = 0.45
) -> list[dict[str, Any]]:
    edges = fast_network_edges_from_corr(
        cached_correlation_frame(returns), threshold=threshold, max_edges=500
    )
    return [
        {"source": e["source"], "target": e["target"], "weight": e["correlation"]}
        for e in edges
    ]


def mantegna_mst(corr: pd.DataFrame) -> list[dict[str, Any]]:
    """Minimum spanning tree under Mantegna correlation distance."""
    cols = list(corr.columns)
    if len(cols) < 2:
        return []
    c = np.clip(
        corr.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float), -1, 1
    )
    distance = np.sqrt(np.maximum(2.0 * (1.0 - c), 0.0))
    visited = {0}
    edges: list[dict[str, Any]] = []
    while len(visited) < len(cols):
        best = None
        for i in visited:
            for j in range(len(cols)):
                if j in visited or i == j:
                    continue
                candidate = (distance[i, j], i, j)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            break
        d, i, j = best
        visited.add(j)
        edges.append(
            {
                "source": cols[i],
                "target": cols[j],
                "distance": float(d),
                "correlation": float(c[i, j]),
            }
        )
    return edges


def correlation_hierarchy(corr: pd.DataFrame) -> list[dict[str, Any]]:
    cols = list(corr.columns)
    if len(cols) < 2:
        return []
    c = np.clip(
        corr.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float), -1, 1
    )
    z = linkage(
        squareform(np.sqrt(np.maximum(2.0 * (1.0 - c), 0.0)), checks=False),
        method="average",
    )
    return [
        {
            "left": int(row[0]),
            "right": int(row[1]),
            "distance": float(row[2]),
            "count": int(row[3]),
        }
        for row in z
    ]


def precision_matrix_network(
    returns: pd.DataFrame, threshold: float = 0.05
) -> list[dict[str, Any]]:
    cov, _ = covariance_matrix(returns, "ledoit_wolf")
    if cov.empty:
        return []
    theta = safe_inverse(cov.to_numpy(dtype=float))
    d = np.sqrt(np.maximum(np.diag(theta), 1e-12))
    partial = -theta / np.outer(d, d)
    np.fill_diagonal(partial, 1.0)
    partial_df = pd.DataFrame(partial, index=cov.columns, columns=cov.columns)
    edges = fast_network_edges_from_corr(partial_df, threshold=threshold, max_edges=500)
    return [
        {"source": e["source"], "target": e["target"], "partial_corr": e["correlation"]}
        for e in edges
    ]


def leading_eigenvalue_series(
    returns: pd.DataFrame, window: int = 126
) -> list[dict[str, Any]]:
    rows = rolling_leading_eigenvalue(returns, window=window, step=max(5, window // 12))
    return [
        {
            "date": str(pd.Timestamp(r["date"]).date()),
            "leading_eigenvalue_ratio": r["leading_eigenvalue_share"],
        }
        for r in rows
    ]


def diversification_ratio_series(
    returns: pd.DataFrame, weights: pd.Series, window: int = 126
) -> list[dict[str, Any]]:
    rows = rolling_diversification_ratio(
        returns, weights, window=window, step=max(5, window // 12)
    )
    return [
        {
            "date": str(pd.Timestamp(r["date"]).date()),
            "diversification_ratio": r["diversification_ratio"],
        }
        for r in rows
    ]


def chow_test_breakpoints(series, min_window=63):
    import statsmodels.api as sm

    y = series.dropna()
    if len(y) < 3 * min_window:
        return []
    time = np.arange(len(y), dtype=float) / len(y)
    rows = []
    for split in range(min_window, len(y) - min_window, min_window):
        post = (np.arange(len(y)) >= split).astype(float)
        design = np.column_stack([np.ones(len(y)), time, post, post * time])
        fit = sm.OLS(y.to_numpy(), design).fit(
            cov_type="HAC", cov_kwds={"maxlags": min_window}
        )
        restriction = np.zeros((2, 4))
        restriction[:, 2:] = np.eye(2)
        test = fit.wald_test(restriction, use_f=True, scalar=True)
        rows.append(
            {
                "date": y.index[split],
                "hac_wald_f": float(test.statistic),
                "p_value": float(test.pvalue),
                "method": "HAC Wald break in intercept and time trend; asymptotic inference on rolling correlations",
                "tested_observations": len(y),
            }
        )
    for row in rows:
        row["bonferroni_p_value"] = min(1, row["p_value"] * len(rows))
    return rows


def sector_block_analysis(
    returns: pd.DataFrame, sectors: dict[str, str]
) -> list[dict[str, Any]]:
    corr = cached_correlation_frame(returns)
    rows = []
    groups = sorted(set(sectors.values()))
    for a in groups:
        ca = [c for c in returns.columns if sectors.get(c, "Unknown") == a]
        for b in groups:
            cb = [c for c in returns.columns if sectors.get(c, "Unknown") == b]
            if ca and cb:
                rows.append(
                    {
                        "row": a,
                        "col": b,
                        "value": float(corr.loc[ca, cb].abs().mean().mean()),
                    }
                )
    return rows


def marchenko_pastur_threshold(n_assets: int, n_obs: int, sigma2: float = 1.0) -> float:
    q = n_assets / max(n_obs, 1)
    return float(sigma2 * (1 + math.sqrt(q)) ** 2)
