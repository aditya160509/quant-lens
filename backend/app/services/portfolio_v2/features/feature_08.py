"""F08 Correlation, Diversification and Contagion Network."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.analytics import (
    chow_test_breakpoints,
    diversification_ratio_series,
    feature_meta,
    leading_eigenvalue_series,
    load_context,
    marchenko_pastur_threshold,
    mantegna_mst,
    correlation_hierarchy,
    matrix_records,
    network_edges,
    precision_matrix_network,
    response,
    sector_block_analysis,
)
from ..core.performance import cached_correlation_frame

FEATURE_ID = "08"
FEATURE_NAME = "Correlation, Diversification and Contagion Network Engine"
INPUTS = ["tickers", "lookback_days", "correlation_window"]
OUTPUTS = ["correlation_heatmap", "crisis_delta", "eigenvalues", "diversification_report", "contagion_network"]


def run(payload: dict | None = None) -> dict:
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    rets = ctx["returns"]

    # Compute corr once, reuse for stress and diagnostics
    corr = cached_correlation_frame(rets)
    corr_arr = corr.to_numpy(dtype=np.float64)

    # Eigenvalues once from cached corr — no redundant decomposition
    vals = np.linalg.eigvalsh(corr_arr)
    vals_pos = np.maximum(vals, 0.0)
    leading = float(vals_pos[-1])
    enb = float((vals_pos.sum() ** 2) / max((vals_pos ** 2).sum(), 1e-12))
    eigenvalues_desc = vals_pos[::-1]

    # Stress corr vectorized — tail mask without pandas quantile overhead
    ret_arr = rets.to_numpy(dtype=np.float64)
    row_means = ret_arr.mean(axis=1)
    q10 = float(np.quantile(row_means, 0.10))
    stress_mask = row_means <= q10
    if stress_mask.sum() > 10:
        stress_arr = ret_arr[stress_mask].copy()
        stress_arr -= stress_arr.mean(axis=0)
        norms = np.sqrt(np.einsum("ij,ij->j", stress_arr, stress_arr))
        norms[norms < 1e-12] = 1.0
        stress_arr /= norms
        crisis_corr_arr = stress_arr.T @ stress_arr
        np.clip(crisis_corr_arr, -1.0, 1.0, out=crisis_corr_arr)
        np.fill_diagonal(crisis_corr_arr, 1.0)
        crisis_corr = pd.DataFrame(crisis_corr_arr, index=corr.index, columns=corr.columns)
        delta_arr = crisis_corr_arr - corr_arr
    else:
        crisis_corr = corr
        delta_arr = np.zeros_like(corr_arr)
    delta = pd.DataFrame(delta_arr, index=corr.index, columns=corr.columns)

    # Top pairs from all_edges — no redundant sort
    all_edges = network_edges(rets, 0.0)
    top_pairs = sorted(all_edges, key=lambda r: abs(r["weight"]), reverse=True)[:10]

    chow_rows = []
    for edge in top_pairs:
        pair_series = rets[edge["source"]].rolling(126).corr(rets[edge["target"]])
        for row in chow_test_breakpoints(pair_series):
            chow_rows.append({"pair": f"{edge['source']}:{edge['target']}", **row})

    sector_blocks = sector_block_analysis(rets, ctx["sectors"])

    tables = {
        "diversification_report": [{"effective_bets": enb, "leading_eigenvalue": leading, "asset_count": len(rets.columns), "mp_lambda_max": marchenko_pastur_threshold(len(rets.columns), len(rets))}],
        "eigenvalues": [{"rank": i + 1, "eigenvalue": float(v)} for i, v in enumerate(eigenvalues_desc)],
        "pair_redundancy": sorted(network_edges(rets, 0.60), key=lambda r: abs(r["weight"]), reverse=True)[:50],
        "chow_breakpoints": chow_rows,
        "sector_block_analysis": sector_blocks,
        "hierarchy": correlation_hierarchy(corr),
    }
    charts = {
        "correlation_heatmap": matrix_records(corr),
        "crisis_delta": matrix_records(delta),
        "contagion_network": all_edges,
        "mantegna_mst": mantegna_mst(corr),
        "partial_correlation_network": precision_matrix_network(rets),
        "eigenvalues": tables["eigenvalues"],
        "leading_eigenvalue_series": leading_eigenvalue_series(rets),
        "diversification_ratio_series": diversification_ratio_series(rets, ctx["weights"]),
        "sector_block_analysis": sector_blocks,
    }
    return response(
        FEATURE_ID,
        [{"label": "Effective Bets", "value": enb}, {"label": "Lead Eigenvalue", "value": leading}],
        charts, tables, meta=feature_meta(ctx),
    )
