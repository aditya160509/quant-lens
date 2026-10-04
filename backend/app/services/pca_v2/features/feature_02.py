"""Feature 02: PCA factor extraction and loading matrix."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from app.services.pca_v2.core.analytics import (
    asset_r2,
    compact_records,
    explained_variance_records,
    factor_returns,
    hierarchical_pca,
    hoyer_sparsity,
    loading_records,
    metadata,
    model_annualization,
    promax,
    response,
    rmt_model,
    varimax,
)


def _stats(series: pd.Series, ann: float) -> dict:
    cum = series.cumsum()
    drawdown = cum - cum.cummax()
    ar1 = float(series.autocorr(1))
    ar1_t = ar1 * np.sqrt(max(len(series) - 2, 1) / max(1.0 - ar1 * ar1, 1e-12)) if np.isfinite(ar1) else None
    return {
        "annualized_sharpe": float(series.mean() / max(series.std(ddof=1), 1e-12) * np.sqrt(ann)),
        "annualized_vol": float(series.std(ddof=1) * np.sqrt(ann)),
        "max_drawdown": float(drawdown.min()),
        "skewness": float(stats.skew(series, nan_policy="omit")),
        "excess_kurtosis": float(stats.kurtosis(series, fisher=True, nan_policy="omit")),
        "ar1": ar1,
        "ar1_t_stat": float(ar1_t) if ar1_t is not None else None,
    }


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    ann = model_annualization(model, payload)
    k = model["k"]
    f = factor_returns(model, k)
    loadings = loading_records(model, k)

    # Rotation: varimax, promax, or none
    rotation_type = str(payload.get("rotation", "none")).lower()
    rotated = []
    rotated_factor_corr = []
    if rotation_type == "varimax":
        rot = varimax(model["orthonormal_eigenvectors"][:, :k])
        for i, ticker in enumerate(model["symbols"]):
            row = {"ticker": ticker, "sector": model["sectors"].get(ticker, "Unknown")}
            for pc in range(k):
                row[f"PC{pc+1}"] = float(rot[i, pc])
            rotated.append(row)
    elif rotation_type == "promax":
        rot = promax(model["orthonormal_eigenvectors"][:, :k])
        rotated_scores = model["analysis_returns"].to_numpy(dtype=float) @ rot
        phi = pd.DataFrame(np.atleast_2d(np.corrcoef(rotated_scores, rowvar=False)), index=[f"PC{i+1}" for i in range(k)], columns=[f"PC{i+1}" for i in range(k)])
        rotated_factor_corr = [{"row": row, "col": col, "value": float(phi.loc[row, col])} for row in phi.index for col in phi.columns]
        for i, ticker in enumerate(model["symbols"]):
            row = {"ticker": ticker, "sector": model["sectors"].get(ticker, "Unknown")}
            for pc in range(k):
                row[f"PC{pc+1}"] = float(rot[i, pc])
            rotated.append(row)

    top_rows = []
    for pc in range(k):
        vals = model["orthonormal_eigenvectors"][:, pc]
        order = np.argsort(vals)
        for side, idxs in (("negative", order[:10]), ("positive", order[-10:][::-1])):
            for idx in idxs:
                top_rows.append({"component": f"PC{pc+1}", "side": side, "ticker": model["symbols"][idx], "sector": model["sectors"].get(model["symbols"][idx], "Unknown"), "loading": float(vals[idx]), "abs_loading": float(abs(vals[idx]))})

    factor_stats = [{"component": col, **_stats(f[col], ann)} for col in f.columns]
    interp = []
    for pc in range(k):
        rows = [r for r in top_rows if r["component"] == f"PC{pc+1}"]
        pos = [r for r in rows if r["side"] == "positive"][:3]
        neg = [r for r in rows if r["side"] == "negative"][:3]
        interp.append({"component": f"PC{pc+1}", "label": f"Long {', '.join(r['ticker'] for r in pos)} vs Short {', '.join(r['ticker'] for r in neg)}", "heuristic": True})

    # Asset-level R²
    r2_table = asset_r2(model)

    # Hoyer sparsity
    hoyer = hoyer_sparsity(model["orthonormal_eigenvectors"][:, :k])

    # Hierarchical PCA (optional toggle via payload; compute always but only expose if requested or as default enrichment)
    hpca = hierarchical_pca(model["returns"], model["sectors"], k_intra=int(payload.get("hpca_k_intra") or 2), k_cross=int(payload.get("hpca_k_cross") or 3))

    return response(
        "02",
        [
            {"label": "Retained PCs", "value": k, "unit": "count"},
            {"label": "PC1 Explained", "value": model["eigenvalues"][0] / max(model["eigenvalues"].sum(), 1e-12), "unit": "share"},
            {"label": "Universe", "value": len(model["symbols"]), "unit": "assets"},
        ],
        charts={
            "pca_biplot": {"scores": [{"date": str(date), "x": float(row.iloc[0]), "y": float(row.iloc[1]) if k > 1 else 0.0} for date, row in f.iterrows()], "loadings": [{"ticker": ticker, "x": float(model["orthonormal_eigenvectors"][i, 0]), "y": float(model["orthonormal_eigenvectors"][i, 1]) if k > 1 else 0.0} for i, ticker in enumerate(model["symbols"])]},
            "loading_matrix_heatmap": loadings,
            "factor_return_time_series": compact_records(f.reset_index(names="date"), limit=500),
            "explained_variance_bar": explained_variance_records(model, limit=30),
            "rotated_loading_matrix": rotated,
            "hierarchical_pca_cluster_map": hpca.get("cluster_loadings", {}),
            "hpca_cross_factor_returns": hpca.get("cross_factor_returns", []),
            "hoyer_sparsity_by_pc": hoyer,
            "promax_factor_correlation": rotated_factor_corr,
        },
        tables={
            "top_n_loading_table": top_rows,
            "factor_return_statistics": factor_stats,
            "pc_interpretation_panel": interp,
            "full_loading_matrix": loadings,
            "eigenvector_json": [{"component": f"PC{i+1}", "eigenvalue": float(model["eigenvalues"][i])} for i in range(k)],
            "asset_r2_table": r2_table,
            "hoyer_sparsity_table": hoyer,
            "promax_factor_correlation": rotated_factor_corr,
        },
        meta=metadata(model, {"rotation": rotation_type, "promax_phi_method": "empirical_score_correlation", "implemented_outputs": 10, "hpca_cluster_count": len(hpca.get("cluster_loadings", {}))}),
    )




from .inputs import inputs_for
INPUTS = inputs_for("02")
OUTPUTS = [{'key': 'pca_biplot', 'source': 'charts', 'label': 'Pca Biplot', 'render': 'biplot', 'primary': True}, {'key': 'loading_matrix_heatmap', 'source': 'charts', 'label': 'Loading Matrix Heatmap', 'render': 'heatmap', 'primary': False}, {'key': 'factor_return_time_series', 'source': 'charts', 'label': 'Factor Return Time Series', 'render': 'line', 'primary': False}, {'key': 'explained_variance_bar', 'source': 'charts', 'label': 'Explained Variance Bar', 'render': 'bar', 'primary': False}, {'key': 'rotated_loading_matrix', 'source': 'charts', 'label': 'Rotated Loading Matrix', 'render': 'bar', 'primary': False}, {'key': 'hierarchical_pca_cluster_map', 'source': 'charts', 'label': 'Hierarchical Pca Cluster Map', 'render': 'bar', 'primary': False}, {'key': 'hpca_cross_factor_returns', 'source': 'charts', 'label': 'Hpca Cross Factor Returns', 'render': 'bar', 'primary': False}, {'key': 'hoyer_sparsity_by_pc', 'source': 'charts', 'label': 'Hoyer Sparsity By Pc', 'render': 'bar', 'primary': False}, {'key': 'promax_factor_correlation', 'source': 'charts', 'label': 'Promax Factor Correlation', 'render': 'bar', 'primary': False}, {'key': 'top_n_loading_table', 'source': 'tables', 'label': 'Top N Loading Table', 'render': 'table', 'primary': False}, {'key': 'factor_return_statistics', 'source': 'tables', 'label': 'Factor Return Statistics', 'render': 'table', 'primary': False}, {'key': 'pc_interpretation_panel', 'source': 'tables', 'label': 'Pc Interpretation Panel', 'render': 'table', 'primary': False}, {'key': 'full_loading_matrix', 'source': 'tables', 'label': 'Full Loading Matrix', 'render': 'table', 'primary': False}, {'key': 'eigenvector_json', 'source': 'tables', 'label': 'Eigenvector Json', 'render': 'table', 'primary': False}, {'key': 'asset_r2_table', 'source': 'tables', 'label': 'Asset R2 Table', 'render': 'table', 'primary': False}, {'key': 'hoyer_sparsity_table', 'source': 'tables', 'label': 'Hoyer Sparsity Table', 'render': 'table', 'primary': False}, {'key': 'promax_factor_correlation', 'source': 'tables', 'label': 'Promax Factor Correlation', 'render': 'table', 'primary': False}]
