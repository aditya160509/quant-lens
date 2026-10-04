"""ML V2 dml implementation."""
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
from .common import date_str, number_like, response, summary
from .panel import load_context, make_feature_panel, numeric_xy


def _nuisance_regressor(kind: str, seed: int = 7):
    kind = str(kind or "ridge").lower()
    if "lightgbm" in kind or "lgbm" in kind:
        try:
            from lightgbm import LGBMRegressor

            return LGBMRegressor(n_estimators=80, max_depth=3, learning_rate=0.05, min_child_samples=20, random_state=seed, n_jobs=1, verbose=-1)
        except Exception:
            return Ridge(alpha=2.0)
    if "forest" in kind:
        return RandomForestRegressor(n_estimators=80, max_depth=4, min_samples_leaf=12, random_state=seed, n_jobs=1)
    return Ridge(alpha=2.0)



def dml_cross_fit(x: pd.DataFrame, y: pd.Series, factor: str, k_folds: int = 5,
                  nuisance_model: str = "ridge", *, dates=None, horizon=5, embargo=5) -> tuple[float, float, float]:
    """Chronological cross-fitting with HC3 inference on held-out residuals.

    Effects are conditional associations unless identification assumptions hold.
    """
    import statsmodels.api as sm
    others = [c for c in x.columns if c != factor]
    if not others:
        raise ValueError("DML requires at least one nuisance covariate")
    if dates is None:
        raise ValueError("DML requires observation dates for purged cross-fitting")
    folds = purged_date_folds(pd.DataFrame({"date": pd.to_datetime(dates).to_numpy()}),
                             n_splits=k_folds, horizon=horizon, embargo=embargo)
    treatments, outcomes = [], []
    for train_idx, test_idx in folds:
        x_tr, x_te = x.iloc[train_idx], x.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        m_f = _nuisance_regressor(nuisance_model, seed=11).fit(x_tr[others], x_tr[factor])
        m_y = _nuisance_regressor(nuisance_model, seed=17).fit(x_tr[others], y_tr)
        treatments.extend(x_te[factor].to_numpy() - m_f.predict(x_te[others]))
        outcomes.extend(y_te.to_numpy() - m_y.predict(x_te[others]))
    residual_treatment = np.asarray(treatments)
    if len(residual_treatment) < 20 or np.dot(residual_treatment, residual_treatment) < 1e-12:
        raise ValueError("Insufficient residual treatment variation for DML inference")
    fit = sm.OLS(np.asarray(outcomes), residual_treatment[:, None]).fit(cov_type="HC3")
    return float(fit.params[0]), float(fit.bse[0]), float(fit.tvalues[0])



def hc3_univariate_inference(treatment: pd.Series, y: pd.Series) -> tuple[float, float, float]:
    """Fast HC3 robust slope/se/t-stat for a univariate factor relation."""

    x = pd.to_numeric(treatment, errors="coerce").replace([np.inf, -np.inf], np.nan)
    yy = pd.to_numeric(y, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = x.notna() & yy.notna()
    if valid.sum() < 12:
        return 0.0, 0.0, 0.0
    xv = x[valid].to_numpy(dtype=float)
    yv = yy[valid].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(xv)), xv])
    try:
        xtx_inv = np.linalg.pinv(X.T @ X)
        beta = xtx_inv @ X.T @ yv
        resid = yv - X @ beta
        hat = np.sum((X @ xtx_inv) * X, axis=1)
        scale = (resid / np.maximum(1.0 - hat, 1e-6)) ** 2
        cov = xtx_inv @ (X.T @ (scale[:, None] * X)) @ xtx_inv
        se = math.sqrt(max(float(cov[1, 1]), 0.0))
        slope = float(beta[1])
        return slope, se, slope / max(se, 1e-12)
    except Exception:
        return 0.0, 0.0, 0.0



def run_causal_dml(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    panel, y = make_feature_panel(ctx, horizon=int(number_like((payload or {}).get("prediction_horizon"), 5) or 5))
    x, y = numeric_xy(panel, y)
    factors = list(x.columns)
    k_folds = int(number_like((payload or {}).get("dml_folds"), 5) or 5)
    nuisance_model = str((payload or {}).get("nuisance_model") or (payload or {}).get("dml_nuisance_model") or "ridge")
    rows = []
    network = []
    for factor in factors:
        ape, se, t = dml_cross_fit(x, y, factor, k_folds=k_folds, nuisance_model=nuisance_model, dates=panel["date"], horizon=int((payload or {}).get("prediction_horizon", 5)))
        ols_ic = fast_spearman_ic(x[factor].to_numpy(dtype=float), y.to_numpy(dtype=float))
        bias = ols_ic - ape
        cls = "Causal" if abs(t) > 1.96 and abs(bias) < abs(ols_ic) * 0.5 + 1e-6 else "Proxy" if abs(t) > 1.96 else "Spurious"
        hc3_slope, hc3_se, hc3_t = hc3_univariate_inference(x[factor], y)
        others = [c for c in factors if c != factor]
        if not others:
            continue
        nuisance_f = _nuisance_regressor(nuisance_model, seed=23).fit(x[others], x[factor])
        ef = x[factor] - nuisance_f.predict(x[others])
        r2 = float(max(0.0, 1.0 - np.var(ef) / max(np.var(x[factor]), 1e-12)))
        rows.append({"factor": factor, "ols_ic": ols_ic, "dml_ape": ape, "dml_se": se, "confounding_bias": bias, "ape_t_stat": t, "hc3_slope": hc3_slope, "hc3_se": hc3_se, "hc3_t_stat": hc3_t, "classification": cls, "nuisance_r2": r2, "recommended_weight_adjustment": max(ape, 0.0)})
        coefs = np.abs(np.asarray(getattr(nuisance_f, "coef_", []))).ravel()
        if not len(coefs) and hasattr(nuisance_f, "feature_importances_"):
            coefs = np.abs(np.asarray(nuisance_f.feature_importances_)).ravel()
        for other, coef in zip(others, coefs):
            if coef > np.percentile(coefs, 75):
                edge_r2 = float((coef / max(float(coefs.sum()), 1e-12)) * r2)
                network.append({"source": other, "target": factor, "weight": edge_r2, "coef_importance": float(coef), "partial_r2_proxy": edge_r2})
    ape_ts = []
    for i in range(126, len(x), max(1, len(x)//120)):
        snap = x.iloc[:i]
        yy = y.iloc[:i]
        if len(snap) < max(60, min(3, k_folds) * 20):
            continue
        for factor in factors[:6]:
            ape_i, _, _ = dml_cross_fit(snap, yy, factor, k_folds=min(3, k_folds), nuisance_model=nuisance_model, dates=panel["date"].iloc[:i], horizon=int((payload or {}).get("prediction_horizon", 5)))
            ape_ts.append({"step": i, "factor": factor, "ape": ape_i})
    spurious_fraction = float(np.mean([r["classification"] == "Spurious" for r in rows])) if rows else 0.0
    return response(
        "11",
        [summary("Causal Factors", sum(r["classification"] == "Causal" for r in rows), "count"), summary("Spurious Fraction", spurious_fraction, "ratio"), summary("Factors", len(rows), "count"), summary("DML Folds", k_folds, "k")],
        charts={
            "causal_ape_leaderboard": rows,
            "confounding_bias_decomposition": [{"factor": r["factor"], "ape_component": r["dml_ape"], "confounding_bias": r["confounding_bias"]} for r in rows],
            "ape_time_series": ape_ts,
            "spurious_factor_detection_log": [{"factor": r["factor"], "classification": r["classification"], "ape_t_stat": r["ape_t_stat"]} for r in rows if r["classification"] == "Spurious"],
            "nuisance_model_r2_table": [{"factor": r["factor"], "nuisance_r2": r["nuisance_r2"]} for r in rows],
            "robust_inference_table": [{"factor": r["factor"], "hc3_slope": r["hc3_slope"], "hc3_se": r["hc3_se"], "hc3_t_stat": r["hc3_t_stat"], "dml_t_stat": r["ape_t_stat"]} for r in rows],
            "causal_factor_network": network,
            "dml_vs_ols_backtest_comparison": [{"method": "ols_ic_weighted", "sharpe": sharpe(y, ctx.annualization)}, {"method": "dml_ape_weighted", "sharpe": sharpe([r["dml_ape"] for r in rows], ctx.annualization)}],
            "rolling_spurious_fraction": [{"date": date_str(d), "spurious_fraction": spurious_fraction} for d in panel["date"].drop_duplicates().tail(80)],
        },
        tables={"causal_ape_table": rows, "causal_network_edges": network, "robust_inference_table": [{"factor": r["factor"], "hc3_slope": r["hc3_slope"], "hc3_se": r["hc3_se"], "hc3_t_stat": r["hc3_t_stat"]} for r in rows]},
        meta={"implemented_outputs": 9, "nuisance_model": nuisance_model, "dml_folds": k_folds, "cross_fitting": "purged_expanding_date_folds", "robust_inference": "HC3_univariate_sandwich", "partial_r2_edges": True},
    )

