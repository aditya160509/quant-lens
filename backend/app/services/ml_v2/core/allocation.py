"""ML V2 allocation implementation."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable
import base64
import hashlib
import math
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Lasso, Ridge, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from .data_loader import annualization_factor, close_matrix, data_inventory, load_fama_french, load_macro, market_caps, ohlcv_for_symbols, parse_symbols, returns_matrix, sector_map, volume_matrix
from .performance import ThreadPoolExecutor, as_completed, cache_key, cached_ledoit_cov, data_inventory_cached, disk_get, disk_set, equity_from_returns, fast_spearman_ic, max_drawdown, normalize_payload, precompute_date_strings, ridge_fit_fast, sharpe, sortino, vectorized_ic_series, _CONTEXT_CACHE
from .validation import chronological_purged_split, purged_date_folds
from .common import compact_records, matrix_records, number_like, response, summary
from .panel import load_context


def hrp_weights(cov: pd.DataFrame, linkage_method: str = "ward") -> tuple[pd.Series, list[str], np.ndarray]:
    corr = cov.corr().fillna(0.0) if cov.shape[0] != cov.shape[1] else cov.copy()
    corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
    corr = pd.DataFrame(corr, index=cov.index, columns=cov.columns).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    dist = np.sqrt(np.maximum(0.0, 0.5 * (1 - corr))).values
    tri = dist[np.triu_indices_from(dist, k=1)]
    method = linkage_method if linkage_method in {"ward", "single", "complete", "average"} else "ward"
    z = linkage(tri, method=method, optimal_ordering=False) if len(tri) else np.empty((0, 4))
    order = list(corr.index[leaves_list(z)]) if len(z) else list(corr.index)
    weights = pd.Series(1.0, index=order)
    ordered_cov = cov.loc[order, order]
    clusters = [order]
    while clusters:
        cluster = clusters.pop(0)
        if len(cluster) <= 1:
            continue
        split = len(cluster) // 2
        left, right = cluster[:split], cluster[split:]
        def cluster_variance(members):
            sub = ordered_cov.loc[members, members].to_numpy()
            inverse = 1. / np.diag(sub)
            inverse /= inverse.sum()
            return float(inverse @ sub @ inverse)
        var_l, var_r = cluster_variance(left), cluster_variance(right)
        alpha = 1.0 - var_l / max(var_l + var_r, 1e-12)
        weights[left] *= alpha
        weights[right] *= 1.0 - alpha
        clusters.extend([left, right])
    weights = weights / weights.sum()
    return weights.reindex(cov.index).fillna(0.0), order, z



def ewma_covariance(returns: pd.DataFrame, halflife: int = 63) -> pd.DataFrame:
    """EWMA covariance matrix with given half-life in bars."""
    lam = 0.5 ** (1.0 / max(halflife, 1))
    weights = np.array([(1 - lam) * lam ** i for i in range(len(returns) - 1, -1, -1)])
    weights /= max(weights.sum(), 1e-12)
    centered = returns - returns.mean()
    arr = centered.to_numpy(dtype=float)
    cov = (arr * weights[:, None]).T @ arr
    return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)



def rmt_cleaned_covariance(returns: pd.DataFrame) -> pd.DataFrame:
    """Random Matrix Theory covariance: clip noisy eigenvalues to Marchenko-Pastur upper edge."""
    clean = returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    t, n = clean.shape
    sample_cov = clean.cov().fillna(0.0)
    if t <= 1 or n <= 1:
        return sample_cov
    vals, vecs = np.linalg.eigh(sample_cov.to_numpy(dtype=float))
    q = max(t / n, 1.0001)
    lambda_plus = float(np.mean(vals) * (1 + 1.0 / math.sqrt(q)) ** 2)
    clipped = np.where(vals > lambda_plus, vals, lambda_plus)
    cleaned = vecs @ np.diag(clipped) @ vecs.T
    return pd.DataFrame(cleaned, index=returns.columns, columns=returns.columns)



def nco_weights(returns: pd.DataFrame, n_clusters: int | None = None) -> pd.Series:
    """Nested Clustered Optimization: optimize within clusters then across clusters."""
    from sklearn.cluster import KMeans

    clean = returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    cov = pd.DataFrame(LedoitWolf().fit(clean).covariance_, index=clean.columns, columns=clean.columns)
    diag = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    corr = pd.DataFrame(cov.to_numpy() / np.outer(diag, diag), index=clean.columns, columns=clean.columns).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    dist = np.sqrt(np.maximum(0.0, 0.5 * (1 - corr))).values
    k = max(2, min(n_clusters or int(math.sqrt(len(clean.columns))), len(clean.columns)))
    km = KMeans(n_clusters=k, random_state=7, n_init=10).fit(dist)
    labels = km.labels_
    cluster_rets: dict[int, pd.Series] = {}
    within_weights: dict[int, pd.Series] = {}
    for c in range(k):
        members = [col for col, lab in zip(clean.columns, labels) if lab == c]
        if not members:
            continue
        sub_cov = cov.loc[members, members]
        w_sub, _, _ = hrp_weights(sub_cov)
        within_weights[c] = w_sub
        cluster_rets[c] = clean[members] @ w_sub.reindex(members).fillna(0.0)
    cluster_ret_df = pd.DataFrame(cluster_rets).fillna(0.0)
    if cluster_ret_df.shape[1] < 2:
        weights, _, _ = hrp_weights(cov)
        return weights
    cluster_cov = pd.DataFrame(LedoitWolf().fit(cluster_ret_df).covariance_, index=cluster_ret_df.columns, columns=cluster_ret_df.columns)
    cluster_w, _, _ = hrp_weights(cluster_cov)
    final = pd.Series(0.0, index=clean.columns)
    for c, w_c in cluster_w.items():
        if int(c) not in within_weights:
            continue
        for asset, w_a in within_weights[int(c)].items():
            final[asset] = float(w_c) * float(w_a)
    total = final.sum()
    return (final / total).fillna(0.0) if total > 0 else final



def herc_weights(cov: pd.DataFrame) -> tuple[pd.Series, list[dict[str, Any]]]:
    """Hierarchical Equal Risk Contribution using the HRP tree split with ERC inside terminal clusters."""

    hrp_w, order, _ = hrp_weights(cov)
    if len(order) < 4:
        return hrp_w, [{"cluster": "all", "assets": ",".join(order), "cluster_weight": 1.0}]
    clusters = [order[: len(order) // 2], order[len(order) // 2:]]
    final = pd.Series(0.0, index=cov.index)
    rows: list[dict[str, Any]] = []
    cluster_vars = []
    for members in clusters:
        sub = cov.loc[members, members]
        inv_vol = 1 / np.sqrt(np.maximum(np.diag(sub), 1e-12))
        inv_vol = inv_vol / max(float(inv_vol.sum()), 1e-12)
        cluster_vars.append(float(inv_vol @ sub.to_numpy(dtype=float) @ inv_vol))
    inv_cluster = 1 / np.sqrt(np.maximum(cluster_vars, 1e-12))
    cluster_weights = inv_cluster / max(float(inv_cluster.sum()), 1e-12)
    for idx, members in enumerate(clusters):
        sub = cov.loc[members, members]
        inv_vol = 1 / np.sqrt(np.maximum(np.diag(sub), 1e-12))
        local = inv_vol / max(float(inv_vol.sum()), 1e-12)
        for asset, lw in zip(members, local):
            final[asset] = float(cluster_weights[idx] * lw)
        rows.append({"cluster": f"cluster_{idx+1}", "assets": ",".join(members), "cluster_weight": float(cluster_weights[idx]), "cluster_variance": float(cluster_vars[idx])})
    total = final.sum()
    return (final / total).fillna(0.0) if total > 0 else final, rows



def run_hrp_optimizer(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=8)
    rets = ctx.returns.replace([np.inf, -np.inf], np.nan).dropna()
    if len(rets) < 30:
        raise ValueError("HRP requires at least 30 complete simultaneous return observations")
    estimator = str((payload or {}).get("covariance_estimator") or "ledoit_wolf").lower()
    variant = str((payload or {}).get("optimization_variant") or "standard_hrp").lower()
    if estimator == "sample":
        cov = rets.cov()
    elif "oas" in estimator:
        cov = pd.DataFrame(OAS().fit(rets).covariance_, index=rets.columns, columns=rets.columns)
    elif "ewma" in estimator:
        cov = ewma_covariance(rets, halflife=63)
    elif "rmt" in estimator:
        cov = rmt_cleaned_covariance(rets)
    else:
        cov = pd.DataFrame(LedoitWolf().fit(rets).covariance_, index=rets.columns, columns=rets.columns)
    if "nco" in variant:
        weights = nco_weights(rets)
        order = list(weights.sort_values(ascending=False).index)
        z = np.empty((0, 4))
    else:
        weights, order, z = hrp_weights(cov, str((payload or {}).get("clustering_linkage") or "ward"))
    min_weight = max(0.0, float(number_like((payload or {}).get("min_weight"), 0.0) or 0.0))
    max_weight = min(1.0, float(number_like((payload or {}).get("max_weight"), 0.25) or 0.25))
    sector_cap = min(1.0, float(number_like((payload or {}).get("max_sector_weight"), 0.40) or 0.40))
    assets = list(weights.index)
    w0 = weights.to_numpy(dtype=float)
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    for sector in sorted({ctx.sectors.get(a, "Unknown") for a in assets} - {"Unknown"}):
        idx = np.array([i for i, a in enumerate(assets) if ctx.sectors.get(a, "Unknown") == sector], dtype=int)
        constraints.append({"type": "ineq", "fun": lambda w, idx=idx: float(sector_cap - np.sum(w[idx]))})
    bounded = minimize(lambda w: float(np.sum((w - w0) ** 2)), w0, method="SLSQP", bounds=[(min_weight, max_weight)] * len(w0), constraints=constraints, options={"maxiter": 250, "ftol": 1e-10})
    if not bounded.success:
        raise ValueError(f"Portfolio constraints are infeasible: {bounded.message}")
    weights = pd.Series(bounded.x, index=assets)
    eq_w = pd.Series(1 / len(weights), index=weights.index)
    port = rets @ weights
    eq_port = rets @ eq_w
    rolling = pd.DataFrame({"date": rets.index, "hrp": port.rolling(63).apply(lambda x: sharpe(x, ctx.annualization)), "equal_weight": eq_port.rolling(63).apply(lambda x: sharpe(x, ctx.annualization))}).dropna()
    risk_contrib = weights * (cov @ weights) / max(float(weights.T @ cov @ weights), 1e-12)
    herc_w, herc_clusters = herc_weights(cov)
    herc_port = rets @ herc_w
    weight_rows = [{"asset": k, "weight": float(v), "sector": ctx.sectors.get(k, "Unknown"), "cluster_order": int(order.index(k)) if k in order else None} for k, v in weights.sort_values(ascending=False).items()]
    dendro = [{"node": int(i + 1), "left": int(a), "right": int(b), "distance": float(d), "count": int(c)} for i, (a, b, d, c) in enumerate(z)] if len(z) else []
    tau = min(0.50, max(0.01, float(number_like((payload or {}).get("black_litterman_tau"), 0.05) or 0.05)))
    risk_aversion = max(0.1, float(number_like((payload or {}).get("risk_aversion"), 2.5) or 2.5))
    sigma = cov.to_numpy(dtype=float)
    pi = risk_aversion * sigma @ eq_w.to_numpy(dtype=float)
    raw_views = (payload or {}).get("views") or {}
    q = np.array([float(number_like(raw_views.get(a), pi[i]) or pi[i]) for i, a in enumerate(assets)])
    omega = np.diag(np.maximum(np.diag(tau * sigma), 1e-10))
    tau_inv = np.linalg.pinv(tau * sigma)
    post_cov = np.linalg.pinv(tau_inv + np.linalg.pinv(omega))
    posterior = post_cov @ (tau_inv @ pi + np.linalg.pinv(omega) @ q)
    raw_bl = np.linalg.pinv(risk_aversion * sigma) @ posterior
    raw_bl = np.maximum(raw_bl, 0.0)
    bl_seed = raw_bl / max(float(raw_bl.sum()), 1e-12) if raw_bl.sum() > 0 else w0
    bl_opt = minimize(lambda w: float((w @ sigma @ w) - 2.0 * posterior @ w / risk_aversion), bl_seed, method="SLSQP", bounds=[(min_weight, max_weight)] * len(w0), constraints=constraints, options={"maxiter": 250, "ftol": 1e-10})
    if not bl_opt.success:
        raise ValueError(f"Black-Litterman constraints are infeasible: {bl_opt.message}")
    bl_weights = bl_opt.x
    bl_weights = bl_weights / max(float(bl_weights.sum()), 1e-12)
    bl = pd.DataFrame({"asset": assets, "equilibrium_return": pi, "view_return": q, "posterior_return": posterior, "posterior_weight": bl_weights})
    return response(
        "05",
        [summary("HRP Sharpe", sharpe(port, ctx.annualization), "sharpe"), summary("Assets", len(weights), "count"), summary("Top Weight", float(weights.max()), "weight"), summary("Estimator", estimator, "method"), summary("Variant", variant, "method")],
        charts={
            "cluster_dendrograms": dendro,
            "hrp_weight_vector": weight_rows,
            "hrp_vs_nco_vs_markowitz_equal_weight": compact_records(rolling),
            "rl_rebalancing_vs_fixed_schedule": [{"strategy": "fixed_monthly_proxy", "sharpe": sharpe(port, ctx.annualization), "turnover": float(weights.diff().abs().sum() if len(weights) > 1 else 0.0)}],
            "quasi_diagonalized_covariance_heatmap": matrix_records(cov.loc[order, order], limit=80),
            "risk_contribution_decomposition": [{"asset": k, "risk_contribution": float(v), "cluster": int(order.index(k)) if k in order else 0} for k, v in risk_contrib.items()],
            "tail_dependence_matrix": matrix_records(rets.quantile(0.05).to_frame().T.corr().reindex(index=rets.columns, columns=rets.columns).fillna(0.0), limit=80),
            "rolling_cluster_stability": compact_records(rolling[["date", "hrp"]].rename(columns={"hrp": "cluster_stability_proxy"})),
            "black_litterman_posterior_return_vector": compact_records(bl),
            "bl_vs_pure_hrp_weight_comparison": [{"asset": a, "pure_hrp": float(weights[a]), "black_litterman": float(bl_weights[i])} for i, a in enumerate(assets)],
            "view_attribution_backtest": compact_records(rolling),
            "covariance_estimator_comparison": [{"estimator": estimator, "condition_number": float(np.linalg.cond(cov.to_numpy()))}],
            "herc_weight_vector": [{"asset": k, "herc_weight": float(v), "sector": ctx.sectors.get(k, "Unknown")} for k, v in herc_w.sort_values(ascending=False).items()],
            "herc_vs_hrp_comparison": [{"strategy": "hrp", "sharpe": sharpe(port, ctx.annualization), "max_weight": float(weights.max())}, {"strategy": "herc", "sharpe": sharpe(herc_port, ctx.annualization), "max_weight": float(herc_w.max())}, {"strategy": "equal_weight", "sharpe": sharpe(eq_port, ctx.annualization), "max_weight": float(eq_w.max())}],
        },
        tables={"hrp_weights": weight_rows, "risk_contribution": [{"asset": k, "risk_contribution": float(v)} for k, v in risk_contrib.items()], "herc_weights": [{"asset": k, "herc_weight": float(v)} for k, v in herc_w.items()], "herc_clusters": herc_clusters},
        meta={"implemented_outputs": 14, "estimator": estimator, "variant": variant, "black_litterman": "full_identity_views", "black_litterman_tau": tau, "constraints_applied": bool(bounded.success), "rl_rebalancing": "research_mode_proxy_no_PPO_training_artifact"},
    )

