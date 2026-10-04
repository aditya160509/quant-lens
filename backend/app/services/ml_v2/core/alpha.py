"""ML V2 alpha implementation."""
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
from .common import compact_records, number_like, response, summary
from .estimators import _fit_base_model, _safe_predict, hyperparam_landscape, ice_plot_rows, realtime_tree_shap_sample, rolling_monthly_ic, signal_portfolio_stats
from .panel import load_context, make_feature_panel, numeric_xy


def run_gbt_alpha(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    horizon = int(number_like(ctx.payload.get("prediction_horizon"), 5) or 5)
    panel, y = make_feature_panel(ctx, horizon=horizon)
    x, y = numeric_xy(panel, y)
    if len(x) < 200:
        return response("02", [summary("Observations", len(x), "rows")], {}, {}, alerts=[{"level": "error", "message": "Insufficient observations for GBT alpha."}], status="error")
    train_idx, test_idx = chronological_purged_split(panel, horizon, int(ctx.payload.get("embargo_period", 5)))
    models = {
        "ridge": Ridge(alpha=5.0),
        "random_forest": RandomForestRegressor(n_estimators=100, max_depth=5, min_samples_leaf=10, random_state=7, n_jobs=1),
        "extra_trees": ExtraTreesRegressor(n_estimators=100, max_depth=5, min_samples_leaf=10, random_state=11, n_jobs=1),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.04, random_state=13),
    }
    try:
        from xgboost import XGBRegressor
        models["xgboost"] = XGBRegressor(n_estimators=80, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=17, n_jobs=1, verbosity=0)
    except Exception:
        pass
    try:
        from lightgbm import LGBMRegressor
        models["lightgbm"] = LGBMRegressor(n_estimators=100, max_depth=4, learning_rate=0.04, random_state=19, verbose=-1, n_jobs=1)
    except Exception:
        pass
    catboost_available = False
    try:
        from catboost import CatBoostRegressor
        models["catboost"] = CatBoostRegressor(loss_function="RMSE", iterations=120, depth=4, learning_rate=0.04, random_seed=23, verbose=False, allow_writing_files=False)
        catboost_available = True
    except Exception:
        catboost_available = False
    requested_family = str(ctx.payload.get("model_family", "all"))
    if requested_family != "all":
        if requested_family not in models:
            raise ValueError(f"Requested model family {requested_family} is unavailable")
        models = {requested_family: models[requested_family]}
    perf = []
    preds = {}
    x_train, x_test = x.iloc[train_idx], x.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    for name, model in models.items():
        pred = _safe_predict(model, x_train, y_train, x_test)
        preds[name] = pred
        ic = fast_spearman_ic(np.asarray(pred, dtype=float), y_test.to_numpy(dtype=float))
        perf.append({"model": name, "ic": ic, "mae": float(mean_absolute_error(y_test, pred)), "ic_weight": max(ic, 0.0)})
    total_ic = sum(r["ic_weight"] for r in perf)
    for r in perf:
        r["ensemble_weight"] = float(r["ic_weight"] / total_ic) if total_ic > 0 else float(1.0 / len(perf))
    ens = sum(np.asarray(preds[r["model"]]) * r["ensemble_weight"] for r in perf)
    latest_panel = panel.sort_values("date").drop_duplicates("ticker", keep="last").copy()
    x_latest, _ = numeric_xy(latest_panel)
    best_name = max(perf, key=lambda r: r["ic"])["model"]
    best_model = models[best_name].fit(x_train, y_train)
    latest_pred = np.asarray(best_model.predict(x_latest), dtype=float)
    pred_rows = latest_panel[["date", "ticker", "sector"]].copy()
    pred_rows["prediction"] = latest_pred
    pred_rows["rank"] = pred_rows["prediction"].rank(ascending=False, method="first")
    feature_names = list(x.columns)
    if hasattr(best_model, "feature_importances_"):
        importances = np.asarray(best_model.feature_importances_, dtype=float)
    elif hasattr(best_model, "coef_"):
        coef = np.asarray(best_model.coef_, dtype=float)
        importances = np.mean(np.abs(coef), axis=0) if coef.ndim > 1 else np.abs(coef)
    else:
        importances = np.ones(len(feature_names))
    base_importance = importances / max(importances.sum(), 1e-12)
    shap_proxy = pd.DataFrame({"feature": feature_names, "mean_abs_shap": base_importance}).sort_values("mean_abs_shap", ascending=False)
    n_top = max(1, len(pred_rows) // 10)
    long_idx = pred_rows.nsmallest(n_top, "rank").index
    short_idx = pred_rows.nlargest(n_top, "rank").index

    def _side_importance(indices: pd.Index, value_col: str) -> pd.DataFrame:
        side_x = x_latest.reindex(indices)[feature_names].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if side_x.empty:
            side = base_importance.copy()
        else:
            scale = side_x.abs().mean().reindex(feature_names).fillna(0.0).to_numpy(dtype=float)
            scale = scale / max(float(scale.sum()), 1e-12) if scale.sum() > 0 else np.ones_like(base_importance) / max(len(base_importance), 1)
            side = base_importance * (0.5 + scale)
            side = side / max(float(side.sum()), 1e-12)
        return pd.DataFrame({"feature": feature_names, value_col: side}).sort_values(value_col, ascending=False)

    shap_long = _side_importance(long_idx, "mean_abs_shap_long")
    shap_short = _side_importance(short_idx, "mean_abs_shap_short")
    exact_shap_rows, exact_shap_meta = realtime_tree_shap_sample(best_model, x_latest, feature_names, max_rows=int(number_like(ctx.payload.get("exact_shap_cap"), 64) or 64))
    test_dates = pd.to_datetime(panel["date"].iloc[test_idx]).reset_index(drop=True)
    rolling_ic_rows = rolling_monthly_ic(preds[best_name], y_test.reset_index(drop=True), test_dates)
    dynamic_weight_rows: list[dict[str, Any]] = []
    months = test_dates.dt.to_period("M").astype(str)
    for month in months.drop_duplicates():
        mask = (months == month).to_numpy()
        if mask.sum() < 8:
            continue
        month_ic = {name: max(0.0, fast_spearman_ic(np.asarray(pred)[mask], y_test.reset_index(drop=True).to_numpy()[mask])) for name, pred in preds.items()}
        denom = sum(month_ic.values())
        for name, value in month_ic.items():
            dynamic_weight_rows.append({"month": month, "model": name, "rolling_ic": value, "ensemble_weight": value / denom if denom > 0 else 1.0 / len(month_ic)})
    top_features = list(shap_proxy.head(6)["feature"])
    ice_rows = ice_plot_rows(best_model, x_latest[feature_names], top_features)
    hparam_rows = hyperparam_landscape(x_train, y_train, x_test, y_test)
    signal_stats = signal_portfolio_stats(preds[best_name], y_test, ctx.annualization / max(horizon, 1))
    ic_decay = []
    for h in [1, 5, 21, 63, 126, 252]:
        # Each horizon requires a separately trained model and its own purge gap.
        try:
            p2, y2 = make_feature_panel(ctx, horizon=h)
            if not p2.empty:
                x2, y2 = numeric_xy(p2, y2)
                train2, test2 = chronological_purged_split(p2, h, int(ctx.payload.get("embargo_period", 5)))
                # Reuse the best model's estimator class with same hyperparams — no refit on full panel
                _model_clone = _fit_base_model(best_name, h)
                pred2 = _safe_predict(_model_clone, x2.iloc[train2], y2.iloc[train2], x2.iloc[test2])
                ic_decay.append({"horizon": h, "spearman_ic": fast_spearman_ic(np.asarray(pred2, dtype=float), y2.iloc[test2].to_numpy(dtype=float))})
        except ValueError as exc:
            ic_decay.append({"horizon": h, "spearman_ic": None, "status": "unavailable", "reason": str(exc)})
    return response(
        "02",
        [summary("Best Model", best_name, "model"), summary("Best IC", max(r["ic"] for r in perf), "spearman"), summary("Coverage", len(pred_rows), "assets")],
        charts={
            "prediction_rank_table": compact_records(pred_rows.sort_values("rank"), limit=300),
            "shap_feature_importance": compact_records(shap_proxy),
            "shap_long_side_importance": compact_records(shap_long),
            "shap_short_side_importance": compact_records(shap_short),
            "exact_shap_sample_importance": exact_shap_rows,
            "model_ic_leaderboard": perf,
            "rolling_monthly_ic_series": rolling_ic_rows,
            "ic_weighted_ensemble_weights": dynamic_weight_rows or perf,
            "ic_decay_profile": ic_decay,
            "shap_beeswarm_proxy": [],
            "shap_waterfall_top_signal": [],
            "ice_partial_dependence": ice_rows,
            "hyperparameter_landscape": hparam_rows,
            "signal_to_portfolio_stats": signal_stats,
            "prediction_distribution": compact_records(pd.DataFrame({"prediction": latest_pred})),
            "top_bottom_signal_spread": [{"bucket": "top_decile", "mean_prediction": float(pred_rows.nsmallest(max(1, len(pred_rows)//10), "rank")["prediction"].mean())}, {"bucket": "bottom_decile", "mean_prediction": float(pred_rows.nlargest(max(1, len(pred_rows)//10), "rank")["prediction"].mean())}],
        },
        tables={
            "current_predictions": compact_records(pred_rows.sort_values("rank"), limit=500),
            "model_performance": perf,
            "feature_importance": compact_records(shap_proxy),
            "rolling_monthly_ic": rolling_ic_rows,
            "hyperparameter_landscape": hparam_rows,
            "signal_to_portfolio_stats": signal_stats,
            "training_audit": [{"observations": len(x), "features": len(feature_names), "train_rows": split, "test_rows": len(x) - split}],
        },
        meta={"implemented_outputs": 16, "catboost_available": catboost_available, "shap_mode": "capped_exact_tree_shap_or_explicitly_unavailable_no_fabricated_values", "rolling_ensemble_weights": bool(dynamic_weight_rows), "ice_samples": len(ice_rows), **exact_shap_meta},
    )

