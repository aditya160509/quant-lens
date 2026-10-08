"""Observed portfolio overlap and exposure-based DebtRank, without probability proxies."""

import numpy as np
import pandas as pd
import networkx as nx


def portfolio_overlap_index(portfolios):
    panel = pd.DataFrame(portfolios).fillna(0)
    if (panel < 0).any().any() or not np.allclose(panel.sum(), 1):
        raise ValueError("Overlap requires normalized long-only books")
    names = list(panel)
    mat = np.minimum(
        panel.to_numpy().T[:, None, :], panel.to_numpy().T[None, :, :]
    ).sum(axis=2)
    return pd.DataFrame(mat, index=names, columns=names)


def debtrank_propagate(exposure, initial_distress, damping=1, max_iter=100):
    if not exposure.index.equals(exposure.columns):
        raise ValueError("Exposure rows and columns must match")
    W = exposure.to_numpy(dtype=float)
    if not np.isfinite(W).all() or (W < 0).any() or (W > 1).any():
        raise ValueError(
            "Exposures must be finite fractions of equity between zero and one"
        )
    h = initial_distress.reindex(exposure.index, fill_value=0).to_numpy(dtype=float)
    if not np.isfinite(h).all() or (h < 0).any() or (h > 1).any():
        raise ValueError("Distress must be in [0,1]")
    active = h > 0
    transmitted = np.zeros(len(h), bool)
    for _ in range(max_iter):
        if not active.any():
            break
        increment = W[:, active] @ h[active]
        updated = np.minimum(1, h + damping * increment)
        transmitted |= active
        active = (updated > h) & ~transmitted
        h = updated
    else:
        raise ValueError("DebtRank propagation did not terminate")
    return pd.Series(h, index=exposure.index)


def overlap_centrality(overlap):
    mat = overlap.copy()
    for node in mat.index:
        mat.loc[node, node] = 0
    graph = nx.from_pandas_adjacency(mat)
    degree = nx.degree_centrality(graph)
    between = nx.betweenness_centrality(graph, weight=None)
    eigen = (
        nx.eigenvector_centrality(graph, max_iter=1000, weight="weight")
        if graph.number_of_edges()
        else {n: 0 for n in graph}
    )
    return [
        {
            "node": n,
            "degree_centrality": degree[n],
            "betweenness_centrality": between[n],
            "eigenvector_centrality": eigen[n],
        }
        for n in overlap.index
    ]


def fire_sale_impact(peer_weights, portfolio_weights, adv, theta, nav, gamma):
    if gamma < 0 or not 0 <= theta <= 1 or nav <= 0 or (adv <= 0).any():
        raise ValueError(
            "Valid observed ADV and explicit fire-sale assumptions required"
        )
    move = -gamma * theta * nav * peer_weights.reindex(adv.index, fill_value=0) / adv
    return portfolio_weights.reindex(adv.index, fill_value=0) * move


def overlap_reducing_trades(weights, peer_average, top_n=5):
    overlap = pd.concat([weights, peer_average], axis=1).min(axis=1)
    return [
        {
            "ticker": c,
            "shared_weight": float(v),
            "current_weight": float(weights[c]),
            "interpretation": "Shared holding ranking; no claim of tracking-error-neutral optimization",
        }
        for c, v in overlap.sort_values(ascending=False).head(top_n).items()
    ]
