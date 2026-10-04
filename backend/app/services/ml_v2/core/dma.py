"""ML V2 dma implementation."""
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
from .common import compact_records, date_str, number_like, response, summary
from .estimators import _safe_predict
from .panel import load_context, make_feature_panel, numeric_xy


def run_dma_engine(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=10)
    panel, y = make_feature_panel(ctx, horizon=int(number_like((payload or {}).get("prediction_horizon"), 5) or 5))
    x, y = numeric_xy(panel, y)
    if len(x) < 160:
        return response("07", [summary("Observations", len(x), "rows")], {}, {}, status="error")
    models = {
        "momentum": x["mom_21"].to_numpy(),
        "reversal": x["reversal_5"].to_numpy(),
        "low_vol": -x["vol_21"].to_numpy(),
        "ridge": _safe_predict(Ridge(alpha=5.0), x.iloc[: len(x)//2], y.iloc[: len(x)//2], x),
        "extra_trees": _safe_predict(ExtraTreesRegressor(n_estimators=60, max_depth=4, random_state=9, n_jobs=1), x.iloc[: len(x)//2], y.iloc[: len(x)//2], x),
    }
    lam = float(number_like((payload or {}).get("forgetting_factor"), 0.97) or 0.97)
    eta = float(number_like((payload or {}).get("obs_learning_rate"), 0.01) or 0.01)
    names = list(models)
    w = np.ones(len(names)) / len(names)
    obs_w = np.ones(len(names)) / len(names)
    static_w = np.ones(len(names)) / len(names)
    pred_matrix = np.column_stack([np.asarray(models[n], dtype=float) for n in names])
    warmup_errors = pred_matrix[20 : max(40, min(len(pred_matrix), len(pred_matrix)//2))] - y.iloc[20 : max(40, min(len(pred_matrix), len(pred_matrix)//2))].to_numpy()[:, None]
    model_sigma = np.nanstd(warmup_errors, axis=0)
    model_sigma = np.where(np.isfinite(model_sigma) & (model_sigma > 1e-8), model_sigma, float(np.nanstd(y) or 1.0))
    rows = []
    obs_rows = []
    score_rows = []
    regret_rows = []
    lambda_rows = []
    date_series = pd.to_datetime(panel["date"]).reset_index(drop=True)
    market_vol = ctx.returns.mean(axis=1).rolling(21).std().rank(pct=True)
    vol_by_date = market_vol.groupby(level=0).last()
    obs_loss_cum = 0.0
    best_model_loss_cum = np.zeros(len(names), dtype=float)
    for t in range(20, len(x)):
        pred_vec = pred_matrix[t]
        realized = float(y.iloc[t])
        err = (pred_vec - float(y.iloc[t])) ** 2
        likelihood = np.exp(-err / (np.nanstd(y.iloc[:t]) ** 2 + 1e-8))
        vol_pct = float(vol_by_date.get(date_series.iloc[t], 0.5) or 0.5)
        lam_eff = float(np.clip(lam - 0.04 * max(0.0, vol_pct - 0.7) / 0.3 + 0.015 * max(0.0, 0.3 - vol_pct) / 0.3, 0.88, 0.995))
        w = (w ** lam_eff) * likelihood
        w = w / max(w.sum(), 1e-12)
        gaussian_nll = 0.5 * np.log(2 * math.pi * (model_sigma ** 2)) + 0.5 * ((realized - pred_vec) / model_sigma) ** 2
        obs_loss_cum += float(np.dot(obs_w, gaussian_nll))
        best_model_loss_cum += gaussian_nll
        obs_w = _project_simplex(obs_w - eta * gaussian_nll)
        if t % max(1, len(x)//200) == 0 or t == len(x) - 1:
            for name, weight in zip(names, w):
                rows.append({"step": t, "date": date_str(panel["date"].iloc[t]), "model": name, "weight": float(weight)})
            for name, weight in zip(names, obs_w):
                obs_rows.append({"step": t, "date": date_str(panel["date"].iloc[t]), "model": name, "weight": float(weight)})
            dma_pred = float(np.dot(w, pred_vec))
            obs_pred = float(np.dot(obs_w, pred_vec))
            static_pred = float(np.dot(static_w, pred_vec))
            score_rows.append({
                "date": date_str(panel["date"].iloc[t]),
                "dma_prediction": dma_pred,
                "obs_prediction": obs_pred,
                "static_bma_prediction": static_pred,
                "ensemble_prediction": dma_pred,
                "realized": realized,
                "dma_entropy": float(-(w * np.log(w + 1e-12)).sum()),
                "obs_entropy": float(-(obs_w * np.log(obs_w + 1e-12)).sum()),
                "obs_top_model": names[int(np.argmax(obs_w))],
                "epistemic_std": float(np.nanstd(pred_vec)),
                "aleatoric_abs_error": float(abs(realized - dma_pred)),
                "p05_prediction": float(np.nanpercentile(pred_vec, 5)),
                "p95_prediction": float(np.nanpercentile(pred_vec, 95)),
                "effective_lambda": lam_eff,
                "market_vol_percentile": vol_pct,
            })
            lambda_rows.append({"date": date_str(panel["date"].iloc[t]), "effective_lambda": lam_eff, "market_vol_percentile": vol_pct, "regime": "high_vol" if vol_pct >= 0.7 else "low_vol" if vol_pct <= 0.3 else "normal"})
            regret_rows.append({
                "date": date_str(panel["date"].iloc[t]),
                "obs_cumulative_loss": obs_loss_cum,
                "best_fixed_model_loss": float(np.min(best_model_loss_cum)),
                "obs_regret": float(obs_loss_cum - np.min(best_model_loss_cum)),
            })
    current = [{"model": n, "dma_weight": float(v), "obs_weight": float(o), "weight": float(v), "direction": "rising" if v > 1 / len(names) else "falling"} for n, v, o in zip(names, w, obs_w)]
    perf_tracker = model_performance_tracker(score_rows)
    calibration = prediction_calibration_rows(score_rows)
    pruning_log = model_pruning_reactivation_log(rows, names)
    return response(
        "07",
        [summary("Top DMA Model", max(current, key=lambda r: r["dma_weight"])["model"], "model"), summary("Top OBS Model", max(current, key=lambda r: r["obs_weight"])["model"], "model"), summary("Lambda", lam, "forgetting")],
        charts={
            "live_model_weight_dashboard": current,
            "model_weight_evolution": rows,
            "dma_vs_obs_vs_static_bma": score_rows,
            "model_pruning_log": pruning_log,
            "model_performance_tracker": perf_tracker,
            "prediction_calibration_curve": calibration,
            "obs_weight_evolution": obs_rows,
            "obs_regret_curve": regret_rows,
            "epistemic_vs_aleatoric_uncertainty": [{"date": r["date"], "epistemic": r["dma_entropy"], "aleatoric": abs(r["realized"] - r["dma_prediction"])} for r in score_rows],
            "distributional_uncertainty_panel": [{"date": r["date"], "prediction": r["dma_prediction"], "p05": r["p05_prediction"], "p95": r["p95_prediction"], "epistemic_std": r["epistemic_std"], "aleatoric_abs_error": r["aleatoric_abs_error"]} for r in score_rows],
            "forgetting_factor_sensitivity": [{"lambda": l, "half_life": float(math.log(0.5) / math.log(l))} for l in [0.90, 0.95, 0.97, 0.99]],
            "regime_specific_lambda_path": lambda_rows,
        },
        tables={"current_model_weights": current, "score_log": score_rows[-300:], "obs_regret_log": regret_rows[-300:], "model_performance_tracker": perf_tracker, "model_pruning_log": pruning_log, "regime_specific_lambda_path": lambda_rows[-300:]},
        meta={"implemented_outputs": 13, "obs": "simplex_projected_online_log_score_optimizer", "obs_learning_rate": eta, "regime_lambda": "market_vol_percentile_router"},
    )



def _project_simplex(values: np.ndarray) -> np.ndarray:
    """Project a vector onto the probability simplex."""
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return v
    if np.all(np.isfinite(v)) and np.all(v >= 0) and abs(v.sum() - 1.0) < 1e-10:
        return v
    v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    rho_candidates = u * np.arange(1, len(u) + 1) > (cssv - 1)
    if not rho_candidates.any():
        return np.ones_like(v) / len(v)
    rho = np.nonzero(rho_candidates)[0][-1]
    theta = (cssv[rho] - 1.0) / (rho + 1)
    w = np.maximum(v - theta, 0.0)
    total = w.sum()
    return w / total if total > 0 else np.ones_like(v) / len(v)



def model_performance_tracker(score_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not score_rows:
        return []
    df = pd.DataFrame(score_rows)
    rows = []
    for col in ["dma_prediction", "obs_prediction", "static_bma_prediction"]:
        err = pd.to_numeric(df[col], errors="coerce") - pd.to_numeric(df["realized"], errors="coerce")
        rows.append({"model": col.replace("_prediction", ""), "mae": float(err.abs().mean()), "rmse": float(np.sqrt(np.mean(err ** 2))), "directional_accuracy": float(np.mean(np.sign(df[col]) == np.sign(df["realized"])))})
    return rows



def prediction_calibration_rows(score_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not score_rows:
        return []
    df = pd.DataFrame(score_rows)
    pred = pd.to_numeric(df["dma_prediction"], errors="coerce")
    realized = pd.to_numeric(df["realized"], errors="coerce")
    valid = pred.notna() & realized.notna()
    if valid.sum() < 20:
        return []
    buckets = pd.qcut(pred[valid].rank(method="first"), 5, labels=False, duplicates="drop")
    out = pd.DataFrame({"bucket": buckets, "predicted": pred[valid], "realized": realized[valid]}).groupby("bucket").agg(mean_prediction=("predicted", "mean"), mean_realized=("realized", "mean"), observations=("realized", "size")).reset_index()
    out["bucket"] = out["bucket"].astype(int) + 1
    return compact_records(out)



def model_pruning_reactivation_log(rows: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    events: list[dict[str, Any]] = []
    for model in names:
        g = df[df["model"] == model].sort_values("step")
        if g.empty:
            continue
        low = False
        for _, row in g.iterrows():
            w = float(row["weight"])
            if not low and w < 0.01:
                events.append({"date": row["date"], "model": model, "event": "pruned", "weight": w})
                low = True
            elif low and w > 0.05:
                events.append({"date": row["date"], "model": model, "event": "reactivated", "weight": w})
                low = False
    return events[-120:]

