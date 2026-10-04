"""ML V2 estimators implementation."""
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
from .common import compact_records


def _fit_base_model(model_type: str = "ridge", random_state: int = 7):  # P10
    """P10 — Uses module-level optional registry to avoid repeated import failures."""
    from .performance import XGBOOST, LGBM, CATBOOST
    mt = str(model_type or "ridge").lower()
    if "xgb" in mt and XGBOOST is not None:
        return XGBOOST(n_estimators=80, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=random_state, n_jobs=1, verbosity=0)
    if ("light" in mt or "lgb" in mt) and LGBM is not None:
        return LGBM(n_estimators=100, max_depth=4, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, random_state=random_state, verbose=-1, n_jobs=1)
    if "cat" in mt and CATBOOST is not None:
        return CATBOOST(loss_function="RMSE", iterations=120, depth=4, learning_rate=0.04, random_seed=random_state, verbose=False, allow_writing_files=False)
    if "random" in mt:
        return RandomForestRegressor(n_estimators=80, max_depth=5, min_samples_leaf=8, random_state=random_state, n_jobs=1)
    if "extra" in mt:
        return ExtraTreesRegressor(n_estimators=80, max_depth=5, min_samples_leaf=8, random_state=random_state, n_jobs=1)
    if "lasso" in mt:
        return Lasso(alpha=1e-4, max_iter=5000)
    if "elastic" in mt:
        return ElasticNet(alpha=1e-4, l1_ratio=0.4, max_iter=5000)
    if "svm" in mt or "svr" in mt:
        from sklearn.svm import LinearSVR
        return LinearSVR(C=0.1, epsilon=0.0, random_state=random_state, max_iter=5000)
    if "mlp" in mt:
        from sklearn.neural_network import MLPRegressor
        return MLPRegressor(hidden_layer_sizes=(32,), max_iter=300, early_stopping=True, random_state=random_state)
    return Ridge(alpha=5.0)



def _safe_predict(model, x_train, y_train, x_test):
    model.fit(x_train, y_train)
    return np.asarray(model.predict(x_test), dtype=float)



def realtime_tree_shap_sample(model: Any, x_latest: pd.DataFrame, feature_names: list[str], *, max_rows: int = 64) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run exact TreeSHAP on a capped latest-book sample when it is cheap."""

    if x_latest.empty or not feature_names:
        return [], {"exact_shap_status": "empty"}
    model_name = model.__class__.__name__.lower()
    tree_like = hasattr(model, "feature_importances_") or any(tag in model_name for tag in ("xgb", "lgbm", "catboost", "forest", "tree", "gradientboosting"))
    if not tree_like:
        return [], {"exact_shap_status": "unsupported_model"}
    try:
        import shap  # type: ignore

        sample = x_latest[feature_names].replace([np.inf, -np.inf], np.nan).fillna(0.0).head(max(1, int(max_rows)))
        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(sample)
        if isinstance(values, list):
            values = values[0]
        arr = np.asarray(values, dtype=float)
        if arr.ndim == 3:
            arr = arr[:, :, 0]
        mean_abs = np.nanmean(np.abs(arr), axis=0)
        denom = max(float(np.nansum(mean_abs)), 1e-12)
        rows = pd.DataFrame({"feature": feature_names, "exact_mean_abs_shap": mean_abs / denom}).sort_values("exact_mean_abs_shap", ascending=False)
        return compact_records(rows), {"exact_shap_status": "fit", "exact_shap_rows": int(len(sample))}
    except Exception as exc:
        return [], {"exact_shap_status": "failed", "exact_shap_error": str(exc)[:180]}



def rolling_monthly_ic(pred: np.ndarray, actual: pd.Series, dates: pd.Series) -> list[dict[str, Any]]:
    df = pd.DataFrame({"date": pd.to_datetime(dates), "prediction": pred, "actual": actual.to_numpy(dtype=float)}).dropna()
    if df.empty:
        return []
    df["month"] = df["date"].dt.to_period("M").astype(str)
    rows: list[dict[str, Any]] = []
    for month, group in df.groupby("month"):
        if len(group) < 8:
            continue
        rows.append({"month": month, "rolling_ic": fast_spearman_ic(group["prediction"].to_numpy(dtype=float), group["actual"].to_numpy(dtype=float)), "observations": int(len(group))})
    return rows[-60:]



def ice_plot_rows(model: Any, x_ref: pd.DataFrame, features: list[str], points: int = 16, samples: int = 32) -> list[dict[str, Any]]:
    if x_ref.empty or not features:
        return []
    base = x_ref.replace([np.inf, -np.inf], np.nan).fillna(0.0).head(max(1, samples)).copy()
    rows: list[dict[str, Any]] = []
    for feature in features[:6]:
        vals = pd.to_numeric(base[feature], errors="coerce")
        lo, hi = float(vals.quantile(0.05)), float(vals.quantile(0.95))
        if not math.isfinite(lo) or not math.isfinite(hi) or abs(hi - lo) < 1e-12:
            continue
        for grid_value in np.linspace(lo, hi, points):
            probe = base.copy()
            probe[feature] = grid_value
            try:
                pred = np.asarray(model.predict(probe), dtype=float)
            except Exception:
                continue
            rows.append({"feature": feature, "value": float(grid_value), "mean_prediction": float(np.nanmean(pred)), "p10_prediction": float(np.nanpercentile(pred, 10)), "p90_prediction": float(np.nanpercentile(pred, 90))})
    return rows



def hyperparam_landscape(x_train: pd.DataFrame, y_train: pd.Series, x_test: pd.DataFrame, y_test: pd.Series) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for depth in [2, 3, 4]:
        for lr in [0.025, 0.05, 0.08]:
            model = GradientBoostingRegressor(n_estimators=60, max_depth=depth, learning_rate=lr, random_state=100 + depth)
            pred = _safe_predict(model, x_train, y_train, x_test)
            rows.append({"max_depth": depth, "learning_rate": lr, "ic": fast_spearman_ic(np.asarray(pred, dtype=float), y_test.to_numpy(dtype=float)), "mae": float(mean_absolute_error(y_test, pred))})
    return rows



def signal_portfolio_stats(pred: np.ndarray, actual: pd.Series, ann: float) -> list[dict[str, Any]]:
    p = np.asarray(pred, dtype=float)
    yv = actual.to_numpy(dtype=float)
    valid = np.isfinite(p) & np.isfinite(yv)
    if valid.sum() < 10:
        return []
    p = p[valid]
    yv = yv[valid]
    signal = np.sign(p)
    ret = signal * yv
    eq = equity_from_returns(ret)
    return [
        {"metric": "annualized_return", "value": float(np.nanmean(ret) * ann)},
        {"metric": "sharpe", "value": sharpe(ret, ann)},
        {"metric": "hit_rate", "value": float(np.mean(np.sign(p) == np.sign(yv)))},
        {"metric": "max_drawdown", "value": max_drawdown(eq)},
        {"metric": "turnover_proxy", "value": float(np.mean(np.abs(np.diff(signal))) if len(signal) > 1 else 0.0)},
        {"metric": "ic", "value": fast_spearman_ic(p, yv)},
    ]



def _ohlcv_lower(ohlcv: pd.DataFrame) -> pd.DataFrame:
    out = ohlcv.copy()
    out.columns = [str(c).lower() for c in out.columns]
    return out



def garman_klass_vol(ohlcv: pd.DataFrame, window: int = 21, ann: float = 252.0) -> pd.Series:
    """Garman-Klass realized volatility estimator from OHLCV."""
    df = _ohlcv_lower(ohlcv)
    h = np.log(df["high"] / df["close"].shift(1)).replace([np.inf, -np.inf], np.nan)
    l = np.log(df["low"] / df["close"].shift(1)).replace([np.inf, -np.inf], np.nan)
    c = np.log(df["close"] / df["open"]).replace([np.inf, -np.inf], np.nan)
    gk = (0.5 * (h - l) ** 2 - (2 * np.log(2) - 1) * c ** 2).rolling(window).mean()
    return (gk * ann).apply(lambda x: math.sqrt(max(x, 0.0)) if math.isfinite(x) else np.nan)



def yang_zhang_vol(ohlcv: pd.DataFrame, window: int = 21, ann: float = 252.0) -> pd.Series:
    """Yang-Zhang realized volatility estimator handling overnight gaps."""
    df = _ohlcv_lower(ohlcv)
    o = np.log(df["open"] / df["close"].shift(1)).replace([np.inf, -np.inf], np.nan)
    c = np.log(df["close"] / df["open"]).replace([np.inf, -np.inf], np.nan)
    h = np.log(df["high"] / df["open"]).replace([np.inf, -np.inf], np.nan)
    l = np.log(df["low"] / df["open"]).replace([np.inf, -np.inf], np.nan)
    k = 0.34 / (1.34 + (window + 1) / max(window - 1, 1))
    rs = h * (h - c) + l * (l - c)
    yz = (o.rolling(window).var(ddof=1) + k * c.rolling(window).var(ddof=1) + (1 - k) * rs.rolling(window).mean()) * ann
    return yz.apply(lambda x: math.sqrt(max(x, 0.0)) if math.isfinite(x) else np.nan)



def corwin_schultz_spread(ohlcv: pd.DataFrame, window: int = 21) -> pd.Series:
    """Corwin-Schultz daily bid-ask spread estimator from high-low ratios."""
    df = _ohlcv_lower(ohlcv)
    h = df["high"].replace(0, np.nan)
    l = df["low"].replace(0, np.nan)
    beta = (np.log(h / l) ** 2).rolling(2).sum()
    gamma = np.log(h.rolling(2).max() / l.rolling(2).min()) ** 2
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / (3 - 2 * np.sqrt(2)) - np.sqrt(gamma / (3 - 2 * np.sqrt(2)))
    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return spread.clip(lower=0.0).rolling(window).mean()



def high_low_amihud(ohlcv: pd.DataFrame, window: int = 21) -> pd.Series:
    """High-low Amihud variant using (high-low)/close as price impact proxy."""
    df = _ohlcv_lower(ohlcv)
    hl_range = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
    dollar = (df["close"] * df["volume"]).replace(0, np.nan)
    return (hl_range / dollar).rolling(window).mean() * 1e8



def bipower_variation(returns: pd.Series, window: int = 21) -> pd.Series:
    """Bi-power variation for jump component decomposition."""
    return (returns.abs() * returns.abs().shift(1)).rolling(window).mean() * math.pi / 2



def ic_decay_ratio(x_col: pd.Series, y: pd.Series, window_short: int = 21, window_long: int = 252) -> float:
    """IC decay ratio: short-window IC-IR divided by long-window IC-IR."""
    vals_short, vals_long = [], []
    step = max(1, len(x_col) // 120)
    for i in range(window_long, len(x_col), step):
        s_short = x_col.iloc[max(0, i - window_short):i]
        y_short = y.iloc[max(0, i - window_short):i]
        s_long = x_col.iloc[max(0, i - window_long):i]
        y_long = y.iloc[max(0, i - window_long):i]
        if len(s_short) > 5:
            vals_short.append(float(stats.spearmanr(s_short, y_short).correlation or 0.0))
        if len(s_long) > 5:
            vals_long.append(float(stats.spearmanr(s_long, y_long).correlation or 0.0))
    ic_ir_short = float(np.nanmean(vals_short) / max(np.nanstd(vals_short), 1e-8)) if vals_short else 0.0
    ic_ir_long = float(np.nanmean(vals_long) / max(np.nanstd(vals_long), 1e-8)) if vals_long else 0.0
    return float(ic_ir_short / max(abs(ic_ir_long), 1e-8))

