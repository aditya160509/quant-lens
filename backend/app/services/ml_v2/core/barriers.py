"""ML V2 barriers implementation."""
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
from .common import clean_json, compact_records, date_str, number_like, response, summary
from .panel import MLContext, load_context


def run_triple_barrier(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=8)
    horizon = int(number_like(ctx.payload.get("max_holding_period"), 21) or 21)
    pt = float(number_like(ctx.payload.get("profit_taking_barrier"), 0.05) or 0.05)
    sl = float(number_like(ctx.payload.get("stop_loss_barrier"), 0.03) or 0.03)
    barrier_mode = str(ctx.payload.get("barrier_mode") or "fixed").lower()
    barrier_side = str(ctx.payload.get("barrier_side") or "bilateral").lower()
    rows = []
    for ticker in ctx.returns.columns:
        rows.extend(high_low_triple_barrier_rows(ctx, ticker, horizon, pt, sl,
                    max_events=600, barrier_mode=barrier_mode, barrier_side=barrier_side))
    labels = pd.DataFrame(rows)
    if labels.empty:
        raise ValueError("No complete OHLC event windows for triple-barrier labeling")
    labels = labels.sort_values(["date", "ticker"]).reset_index(drop=True)
    dist = labels.groupby("label").size().reset_index(name="count")
    # Primary side is observable at event formation, never the future barrier label.
    sides = ctx.returns.rolling(21).sum()
    labels["primary_side"] = [np.sign(sides.loc[pd.Timestamp(d), t])
                              for d, t in zip(labels["date"], labels["ticker"])]
    features = labels[["vol_21", "primary_side"]].astype(float)
    target = (labels["primary_side"] * labels["forward_return"] > 0).astype(int)
    probabilities = np.full(len(labels), np.nan)
    for train_idx, test_idx in purged_date_folds(labels, n_splits=3, horizon=horizon, embargo=5):
        valid_train = features.iloc[train_idx].notna().all(axis=1).to_numpy()
        valid_test = features.iloc[test_idx].notna().all(axis=1).to_numpy()
        train_idx, test_idx = train_idx[valid_train], test_idx[valid_test]
        if len(train_idx) < 30 or target.iloc[train_idx].nunique() < 2:
            continue
        model = LogisticRegression(max_iter=500, random_state=7)
        model.fit(features.iloc[train_idx], target.iloc[train_idx])
        probabilities[test_idx] = model.predict_proba(features.iloc[test_idx])[:, 1]
    labels["meta_probability"] = probabilities
    confidence = float(number_like(ctx.payload.get("confidence_level"), 0.90) or 0.90)
    sizing = str(ctx.payload.get("position_sizing") or "probability").lower()
    edge = (2.0 * labels.get("meta_probability", pd.Series(0.5, index=labels.index)) - 1.0).clip(-1.0, 1.0)
    labels["position_size"] = np.where(sizing == "binary", (labels["meta_probability"] >= 0.5).astype(float), edge if sizing == "kelly" else labels["meta_probability"])
    cqr_meta = {"method": "lightgbm_quantile_cqr", "target_coverage": confidence}
    labels, cqr_meta = _lightgbm_cqr_intervals(labels, confidence=confidence, horizon=horizon, annualization=ctx.annualization)
    coverage = cqr_meta.get("test_empirical_coverage")
    coverage_by_date = _rolling_coverage_audit(labels, confidence)
    label_comparison = label_method_comparison(labels)
    barrier_sensitivity = barrier_sensitivity_rows(ctx, horizon)
    return response(
        "04",
        [summary("Events", len(labels), "labels"), summary("CQR Coverage", coverage, "ratio"), summary("PT/SL", f"{pt:.2%}/{sl:.2%}", "barrier")],
        charts={
            "triple_barrier_label_distribution": compact_records(dist),
            "event_outcome_timeline": compact_records(labels, limit=500),
            "meta_label_probability_distribution": compact_records(labels[["meta_probability"]], limit=500),
            "cqr_interval_width_distribution": compact_records(pd.DataFrame({"interval_width": labels["cqr_upper"] - labels["cqr_lower"]}), limit=500),
            "cqr_coverage_audit": coverage_by_date or [{"target_coverage": confidence, "empirical_coverage": coverage}],
            "barrier_hit_path_examples": compact_records(labels.head(120)),
            "label_method_comparison": label_comparison,
            "barrier_sensitivity_surface": barrier_sensitivity,
        },
        tables={"label_audit": compact_records(labels, limit=800), "barrier_parameters": [{"profit_taking": pt, "stop_loss": sl, "max_holding_period": horizon, "barrier_mode": barrier_mode, "barrier_side": barrier_side}], "label_method_comparison": label_comparison, "barrier_sensitivity": barrier_sensitivity},
        meta={"implemented_outputs": 9, "method": "high_low_path_triple_barrier", **cqr_meta},
    )



def high_low_triple_barrier_rows(ctx: MLContext, ticker: str, horizon: int, pt: float, sl: float, max_events: int = 120, barrier_mode: str = "fixed", barrier_side: str = "bilateral") -> list[dict[str, Any]]:
    if ctx.ohlcv.empty or "Ticker" not in ctx.ohlcv.columns:
        return []
    df = ctx.ohlcv[ctx.ohlcv["Ticker"] == ticker].copy()
    if df.empty:
        return []
    cols = {c.lower(): c for c in df.columns}
    required = ["date", "high", "low", "close"]
    if any(c not in cols for c in required):
        return []
    df = df.sort_values(cols["date"]).tail(max_events + horizon + 5)
    dates = pd.to_datetime(df[cols["date"]]).reset_index(drop=True)
    high = pd.to_numeric(df[cols["high"]], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(df[cols["low"]], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(df[cols["close"]], errors="coerce").to_numpy(dtype=float)
    vol_series = pd.Series(dtype=float)
    if ticker in ctx.returns:
        vol_series = (ctx.returns[ticker].rolling(21).std() * math.sqrt(ctx.annualization)).dropna()
    rows: list[dict[str, Any]] = []
    start = max(0, len(df) - max_events - horizon)
    for i in range(start, max(0, len(df) - horizon)):
        entry = close[i]
        if not math.isfinite(entry) or entry <= 0:
            continue
        event_daily_vol = 0.0
        if not vol_series.empty:
            try:
                event_daily_vol = float(vol_series.reindex([dates.iloc[i]]).iloc[0]) / math.sqrt(ctx.annualization)
            except Exception:
                event_daily_vol = 0.0
        pt_i = max(1e-4, pt * event_daily_vol * math.sqrt(horizon)) if barrier_mode in {"ewma", "vol_scaled", "dynamic"} else pt
        sl_i = max(1e-4, sl * event_daily_vol * math.sqrt(horizon)) if barrier_mode in {"ewma", "vol_scaled", "dynamic"} else sl
        upper = entry * (1 + pt_i) if barrier_side != "short_only" else math.inf
        lower = entry * (1 - sl_i) if barrier_side != "long_only" else -math.inf
        label = 0
        touch_date = dates.iloc[min(i + horizon, len(dates) - 1)]
        touch_type = "vertical"
        for j in range(i + 1, min(i + horizon + 1, len(df))):
            hit_up = math.isfinite(high[j]) and high[j] >= upper
            hit_down = math.isfinite(low[j]) and low[j] <= lower
            if hit_up or hit_down:
                if hit_up and hit_down:
                    label = 1 if abs(high[j] / entry - 1) >= abs(low[j] / entry - 1) else -1
                    touch_type = "both_same_bar"
                else:
                    label = 1 if hit_up else -1
                    touch_type = "profit_taking" if hit_up else "stop_loss"
                touch_date = dates.iloc[j]
                break
        exit_idx = min(i + horizon, len(df) - 1)
        fwd = close[exit_idx] / entry - 1 if math.isfinite(close[exit_idx]) else np.nan
        event_vol = None
        if not vol_series.empty:
            try:
                aligned_vol = vol_series.reindex([dates.iloc[i]]).iloc[0]
                event_vol = float(aligned_vol) if math.isfinite(float(aligned_vol)) else None
            except Exception:
                event_vol = None
        rows.append({"date": date_str(dates.iloc[i]), "ticker": ticker, "forward_return": float(fwd), "label": int(label), "vol_21": event_vol, "touch_date": date_str(touch_date), "touch_type": touch_type, "upper_barrier": upper, "lower_barrier": lower, "barrier_method": "high_low_path"})
    return clean_json(rows[-max_events:])



def label_method_comparison(labels: pd.DataFrame) -> list[dict[str, Any]]:
    if labels.empty:
        return []
    fwd = pd.to_numeric(labels["forward_return"], errors="coerce").fillna(0.0)
    vol = pd.to_numeric(labels.get("vol_21"), errors="coerce").fillna(float(fwd.std() or 0.01))
    fixed = labels["label"].astype(int)
    vol_scaled = np.where(fwd > vol / math.sqrt(252), 1, np.where(fwd < -vol / math.sqrt(252), -1, 0))
    quantile = np.where(fwd >= fwd.quantile(0.67), 1, np.where(fwd <= fwd.quantile(0.33), -1, 0))
    methods = {"fixed_barrier": fixed, "vol_scaled_barrier": vol_scaled, "tercile_return": quantile}
    rows = []
    for name, vals in methods.items():
        vals = np.asarray(vals, dtype=int)
        rows.append({"method": name, "positive_rate": float(np.mean(vals == 1)), "negative_rate": float(np.mean(vals == -1)), "neutral_rate": float(np.mean(vals == 0)), "events": int(len(vals))})
    return rows



def barrier_sensitivity_rows(ctx: MLContext, horizon: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        mean_fwd = ctx.returns.shift(-horizon).rolling(horizon).sum().stack(future_stack=True).dropna()
    except (TypeError, ValueError):
        mean_fwd = ctx.returns.shift(-horizon).rolling(horizon).sum().stack(dropna=True)
    if mean_fwd.empty:
        return rows
    vals = mean_fwd.to_numpy(dtype=float)
    for pt in [0.02, 0.04, 0.06, 0.08]:
        for sl in [0.02, 0.04, 0.06]:
            label = np.where(vals > pt, 1, np.where(vals < -sl, -1, 0))
            rows.append({"profit_taking": pt, "stop_loss": sl, "positive_rate": float(np.mean(label == 1)), "negative_rate": float(np.mean(label == -1)), "neutral_rate": float(np.mean(label == 0))})
    return rows



def _lightgbm_cqr_intervals(labels: pd.DataFrame, confidence: float, horizon: int, annualization: float):
    """Quantile regression with disjoint purged training/calibration/test dates."""
    from sklearn.ensemble import GradientBoostingRegressor
    out = labels.sort_values(["date", "ticker"]).reset_index(drop=True).copy()
    for column in ["cqr_lower", "cqr_upper", "cqr_interval_width"]:
        out[column] = np.nan
    dates = pd.DatetimeIndex(pd.to_datetime(out["date"]).unique()).sort_values()
    train_end, calibration_end = int(len(dates) * .6), int(len(dates) * .8)
    train_dates = dates[:max(0, train_end - horizon - 5)]
    calibration_dates = dates[train_end:max(train_end, calibration_end - horizon - 5)]
    test_dates = dates[calibration_end:]
    features = out[["vol_21", "primary_side"]].astype(float)
    valid = features.notna().all(axis=1) & out["forward_return"].notna()
    masks = [valid & pd.to_datetime(out["date"]).isin(part)
             for part in [train_dates, calibration_dates, test_dates]]
    train, calibration, test = masks
    if train.sum() < 30 or calibration.sum() < 10 or test.sum() < 10:
        return out, {"method": "quantile_cqr", "status": "unavailable", "reason": "Insufficient disjoint event dates"}
    alpha = 1 - confidence
    estimators = [GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=100,
                  max_depth=2, random_state=7) for q in [alpha / 2, 1 - alpha / 2]]
    for model in estimators:
        model.fit(features.loc[train], out.loc[train, "forward_return"])
    lo, hi = [model.predict(features.loc[calibration]) for model in estimators]
    y_cal = out.loc[calibration, "forward_return"].to_numpy()
    scores = np.maximum(lo - y_cal, y_cal - hi)
    level = min(1., np.ceil((len(scores) + 1) * confidence) / len(scores))
    correction = max(0., float(np.quantile(scores, level, method="higher")))
    lo, hi = [model.predict(features.loc[test]) for model in estimators]
    out.loc[test, "cqr_lower"] = np.minimum(lo, hi) - correction
    out.loc[test, "cqr_upper"] = np.maximum(lo, hi) + correction
    out["cqr_interval_width"] = out["cqr_upper"] - out["cqr_lower"]
    coverage = ((out.loc[test, "forward_return"] >= out.loc[test, "cqr_lower"]) &
                (out.loc[test, "forward_return"] <= out.loc[test, "cqr_upper"])).mean()
    return out, {"method": "sklearn_quantile_cqr", "status": "fit",
                 "calibration_qhat": correction, "calibration_rows": int(calibration.sum()),
                 "test_rows": int(test.sum()), "test_empirical_coverage": float(coverage),
                 "coverage_scope": "held_out_test_only", "coverage_guarantee": "Exchangeability not assumed for financial events"}



def _rolling_coverage_audit(labels: pd.DataFrame, confidence: float) -> list[dict[str, Any]]:
    if labels.empty or "date" not in labels:
        return []
    df = labels.dropna(subset=["forward_return", "cqr_lower", "cqr_upper"]).copy()
    df["covered"] = ((df["forward_return"] >= df["cqr_lower"]) & (df["forward_return"] <= df["cqr_upper"])).astype(float)
    grouped = df.groupby("date")["covered"].mean().rolling(21, min_periods=5).mean().dropna()
    return [{"date": date_str(d), "target_coverage": confidence, "empirical_coverage": float(v)} for d, v in grouped.tail(160).items()]

