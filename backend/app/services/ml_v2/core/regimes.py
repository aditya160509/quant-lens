"""ML V2 regimes implementation."""
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
from .common import clean_json, date_str, matrix_records, number_like, response, summary
from .panel import MLContext, load_context, make_feature_panel, numeric_xy


def run_regime_engine(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    market = ctx.returns.mean(axis=1)
    feat = pd.DataFrame({"date": ctx.returns.index, "ret": market, "vol": market.rolling(21).std() * math.sqrt(ctx.annualization), "skew": market.rolling(21).skew(), "kurt": market.rolling(21).kurt()}).dropna()
    macro = load_macro()
    if not macro.empty:
        feat = feat.merge(macro, left_on="date", right_on="date", how="left").ffill()
    x = feat.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    n = int(number_like((payload or {}).get("hmm_state_count"), 3) or 3)
    n = max(2, min(4, n))
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)
    framework = "GaussianHMM Baum-Welch"
    model_status = "fit"
    state_names = [f"state_{i+1}" for i in range(n)]
    state_mean_returns: list[float] = []
    transition_source = "model_transmat"
    try:
        from hmmlearn import hmm

        hmm_error: Exception | None = None
        hmm_model = None
        for covariance_type in ("full", "diag"):
            try:
                candidate = hmm.GaussianHMM(
                    n_components=n,
                    covariance_type=covariance_type,
                    n_iter=200,
                    tol=1e-4,
                    random_state=7,
                    min_covar=1e-3,
                    params="stmc",
                    init_params="stmc",
                )
                candidate.fit(x_scaled)
                hmm_model = candidate
                framework = f"GaussianHMM Baum-Welch ({covariance_type})"
                break
            except Exception as exc:
                hmm_error = exc
        if hmm_model is None:
            raise hmm_error or RuntimeError("GaussianHMM failed")
        raw_probs = hmm_model.predict_proba(x_scaled)
        raw_states = hmm_model.predict(x_scaled)
        raw_means = []
        for state in range(n):
            mask = raw_states == state
            raw_means.append(float(feat.loc[mask, "ret"].mean()) if mask.any() else -np.inf)
        order = list(np.argsort(raw_means)[::-1])
        remap = {old: new for new, old in enumerate(order)}
        probs = raw_probs[:, order]
        states = np.array([remap[int(s)] for s in raw_states], dtype=int)
        trans = np.asarray(hmm_model.transmat_, dtype=float)[np.ix_(order, order)]
        state_mean_returns = [float(raw_means[i]) if math.isfinite(raw_means[i]) else 0.0 for i in order]
    except Exception as exc:
        framework = "GaussianMixture fallback"
        model_status = f"hmm_failed: {exc}"
        transition_source = "empirical_state_transitions"
        gmm = GaussianMixture(n_components=n, random_state=7, covariance_type="full").fit(x_scaled)
        raw_probs = gmm.predict_proba(x_scaled)
        raw_states = gmm.predict(x_scaled)
        raw_means = []
        for state in range(n):
            mask = raw_states == state
            raw_means.append(float(feat.loc[mask, "ret"].mean()) if mask.any() else -np.inf)
        order = list(np.argsort(raw_means)[::-1])
        remap = {old: new for new, old in enumerate(order)}
        probs = raw_probs[:, order]
        states = np.array([remap[int(s)] for s in raw_states], dtype=int)
        state_mean_returns = [float(raw_means[i]) if math.isfinite(raw_means[i]) else 0.0 for i in order]
        trans = np.zeros((n, n))
        for a, b in zip(states[:-1], states[1:]):
            trans[a, b] += 1
        trans = trans / np.maximum(trans.sum(axis=1, keepdims=True), 1)
    prob_rows = []
    for i, d in enumerate(feat["date"]):
        row = {"date": date_str(d)}
        for s in range(n):
            row[f"state_{s+1}"] = float(probs[i, s])
        row["dominant_state"] = int(np.argmax(probs[i]) + 1)
        prob_rows.append(row)
    pca = PCA(n_components=min(5, ctx.returns.shape[1])).fit(ctx.returns.tail(min(len(ctx.returns), 252)).fillna(0.0))
    pc1_ts = []
    for i in range(63, len(ctx.returns), max(1, len(ctx.returns)//160)):
        vals = PCA(n_components=1).fit(ctx.returns.iloc[i-63:i].fillna(0.0)).explained_variance_ratio_
        pc1_ts.append({"date": date_str(ctx.returns.index[i]), "pc1_explained_variance": float(vals[0])})
    corr = ctx.returns.tail(126).corr().fillna(0.0)
    threshold = float(number_like((payload or {}).get("random_graph_threshold"), 0.45) or 0.45)
    density = float((np.abs(corr.values[np.triu_indices_from(corr, k=1)]) > threshold).mean()) if corr.shape[0] > 1 else 0.0
    ensemble_result = ensemble_hmm_classifier(feat, states, n)
    gmm_parallel = parallel_gmm_regimes(x_scaled, feat, n)
    regime_ic_rows = regime_factor_forward_ic(ctx, states, feat["date"], horizon=int(number_like((payload or {}).get("prediction_horizon"), 5) or 5))
    return response(
        "06",
        [summary("Current State", int(states[-1] + 1), "state"), summary("PC1 Variance", float(pca.explained_variance_ratio_[0]), "ratio"), summary("Network Density", density, "density"), summary("Ensemble Agreement", ensemble_result.get("agreement_rate", 1.0), "ratio")],
        charts={
            "regime_probability_time_series": prob_rows,
            "regime_transition_heatmap": matrix_records(pd.DataFrame(trans, index=[f"state_{i+1}" for i in range(n)], columns=[f"state_{i+1}" for i in range(n)])),
            "ensemble_vs_hmm_comparison": [ensemble_result],
            "pc1_structural_break_monitor": pc1_ts,
            "regime_conditional_factor_performance": _regime_factor_performance(ctx.returns, states, feat["date"]),
            "strategy_performance_attribution_by_regime": _regime_strategy_attr(market, states[-len(market):]),
            "regime_conditional_vol_term_structure": _regime_vol_term(market, states[-len(market):], ctx.annualization),
            "random_graph_systemic_risk_indicator": [{"date": date_str(ctx.returns.index[-1]), "realized_density_minus_er": density - threshold, "density": density, "threshold": threshold}],
            "parallel_gmm_regime_probabilities": gmm_parallel["probabilities"],
            "hmm_vs_gmm_state_agreement": gmm_parallel["agreement"],
            "regime_factor_forward_ic": regime_ic_rows,
        },
        tables={
            "transition_matrix": matrix_records(pd.DataFrame(trans, index=state_names, columns=state_names)),
            "current_regime_probabilities": [prob_rows[-1]],
            "parallel_gmm_state_diagnostics": gmm_parallel["diagnostics"],
            "hmm_state_diagnostics": [{"state": state_names[i], "mean_return": state_mean_returns[i], "rank": i + 1} for i in range(n)],
            "regime_factor_forward_ic": regime_ic_rows,
        },
        meta={"implemented_outputs": 11, "framework": framework, "model_status": model_status, "transition_source": transition_source, "state_ordering": "descending_mean_return", "ensemble_hmm": ensemble_result.get("method"), "parallel_gmm": gmm_parallel["status"]},
    )



def _regime_factor_performance(returns: pd.DataFrame, states: np.ndarray, dates: pd.Series) -> list[dict[str, Any]]:
    aligned = returns.reindex(pd.to_datetime(dates)).fillna(0.0)
    out = []
    for ticker in aligned.columns[:40]:
        for state in sorted(set(states)):
            vals = aligned[ticker].iloc[np.where(states == state)[0]]
            out.append({"factor": ticker, "regime": f"state_{state+1}", "avg_return": float(vals.mean()), "ic_proxy": sharpe(vals, 252) / 10.0})
    return clean_json(out)



def regime_factor_forward_ic(ctx: MLContext, states: np.ndarray, dates: pd.Series, horizon: int = 5) -> list[dict[str, Any]]:
    try:
        panel, y = make_feature_panel(ctx, horizon=horizon)
        x, y = numeric_xy(panel, y)
    except Exception:
        return []
    if panel.empty or x.empty:
        return []
    state_by_date = pd.Series(states, index=pd.to_datetime(dates)).groupby(level=0).last()
    row_states = pd.to_datetime(panel["date"]).map(state_by_date).fillna(-1).astype(int).to_numpy()
    rows: list[dict[str, Any]] = []
    for state in sorted(set(row_states)):
        if state < 0:
            continue
        mask = row_states == state
        if mask.sum() < 40:
            continue
        for factor in x.columns[:12]:
            ic = fast_spearman_ic(x.loc[mask, factor].to_numpy(dtype=float), y.loc[mask].to_numpy(dtype=float))
            rows.append({"regime": f"state_{state+1}", "factor": factor, "forward_ic": ic, "observations": int(mask.sum()), "horizon": horizon})
    return rows



def _regime_strategy_attr(market: pd.Series, states: np.ndarray) -> list[dict[str, Any]]:
    states = states[-len(market):]
    return [{"regime": f"state_{s+1}", "sharpe_contribution": sharpe(market.iloc[np.where(states == s)[0]], 252)} for s in sorted(set(states))]



def _regime_vol_term(market: pd.Series, states: np.ndarray, ann: float) -> list[dict[str, Any]]:
    states = states[-len(market):]
    rows = []
    for s in sorted(set(states)):
        vals = market.iloc[np.where(states == s)[0]]
        for h in [5, 21, 63]:
            rows.append({"regime": f"state_{s+1}", "horizon": h, "vol": float(vals.rolling(min(h, len(vals))).std().mean() * math.sqrt(ann)) if len(vals) > 2 else 0.0})
    return rows



def ensemble_hmm_classifier(feat: pd.DataFrame, states: np.ndarray, n_states: int) -> dict[str, Any]:
    """Train a fast tree classifier on HMM states and report agreement diagnostics."""
    x = feat.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = np.asarray(states, dtype=int)
    if len(x) < 60 or len(np.unique(y)) < 2:
        return {"agreement_rate": 1.0, "lead_time_days_proxy": 0, "method": "insufficient_data"}
    cut = int(len(x) * 0.7)
    rf = RandomForestRegressor(n_estimators=60, max_depth=4, random_state=7, n_jobs=1)
    rf.fit(x.iloc[:cut], y[:cut])
    rf_pred = np.round(rf.predict(x.iloc[cut:])).astype(int).clip(0, n_states - 1)
    hmm_test = y[cut:]
    agreement = float(np.mean(rf_pred == hmm_test))
    changes_hmm = np.flatnonzero(np.diff(hmm_test, prepend=hmm_test[0]) != 0)
    changes_rf = np.flatnonzero(np.diff(rf_pred, prepend=rf_pred[0]) != 0)
    lead = 0
    if len(changes_hmm) and len(changes_rf):
        nearest = []
        for h in changes_hmm:
            prev = changes_rf[changes_rf <= h]
            if len(prev):
                nearest.append(int(h - prev[-1]))
        lead = int(np.median(nearest)) if nearest else 0
    return {"agreement_rate": agreement, "lead_time_days_proxy": lead, "method": "random_forest_vs_hmm_viterbi"}



def parallel_gmm_regimes(x_scaled: np.ndarray, feat: pd.DataFrame, n_states: int) -> dict[str, Any]:
    try:
        gmm = GaussianMixture(n_components=n_states, covariance_type="full", random_state=29).fit(x_scaled)
        probs = gmm.predict_proba(x_scaled)
        labels = gmm.predict(x_scaled)
        rows = []
        for i, d in enumerate(feat["date"]):
            if i % max(1, len(feat) // 180) and i != len(feat) - 1:
                continue
            row = {"date": date_str(d), "dominant_gmm_state": int(np.argmax(probs[i]) + 1)}
            for s in range(n_states):
                row[f"gmm_state_{s+1}"] = float(probs[i, s])
            rows.append(row)
        diagnostics = []
        for s in range(n_states):
            mask = labels == s
            diagnostics.append({"gmm_state": f"gmm_state_{s+1}", "mean_return": float(feat.loc[mask, "ret"].mean()) if mask.any() else 0.0, "observations": int(mask.sum())})
        return {"status": "fit", "probabilities": rows, "diagnostics": diagnostics, "agreement": [{"gmm_states": n_states, "avg_max_probability": float(np.mean(np.max(probs, axis=1)))}]}
    except Exception as exc:
        return {"status": f"failed: {exc}", "probabilities": [], "diagnostics": [], "agreement": []}

