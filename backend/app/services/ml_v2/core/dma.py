"""Date-batched, label-maturity-safe online ensemble evaluation."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from scipy.special import softmax
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from .common import compact_records, date_str, response, summary
from .estimators import _safe_predict
from .panel import load_context, make_feature_panel, numeric_xy
from .validation import chronological_purged_split


def run_dma_engine(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=10)
    horizon = int(ctx.payload.get("prediction_horizon", 5))
    panel, y = make_feature_panel(ctx, horizon=horizon)
    x, y = numeric_xy(panel, y)
    train, test = chronological_purged_split(panel, horizon, int(ctx.payload.get("embargo_period", 5)))
    requested = ctx.payload.get("model_library", ["momentum", "reversal", "low_vol", "ridge", "extra_trees"])
    if not isinstance(requested, list) or not requested or len(set(requested)) != len(requested):
        raise ValueError("model_library must contain distinct supported members")
    factories = {"ridge": lambda: Ridge(alpha=5), "extra_trees": lambda: ExtraTreesRegressor(n_estimators=60, max_depth=4, random_state=9, n_jobs=1)}
    columns = {"momentum": "mom_21", "reversal": "reversal_5", "low_vol": "vol_21"}
    names = list(requested)
    predictions = []
    for name in names:
        if name in factories:
            predictions.append(_safe_predict(factories[name](), x.iloc[train], y.iloc[train], x.iloc[test]))
        elif name in columns:
            # Train-only linear calibration puts each signal in return units.
            col = columns[name]
            predictions.append(_safe_predict(Ridge(alpha=5), x.iloc[train][[col]], y.iloc[train], x.iloc[test][[col]]))
        else:
            raise ValueError(f"Unsupported ensemble member: {name}")
    matrix = np.column_stack(predictions)
    evaluation = panel.iloc[test].reset_index(drop=True)
    outcomes = y.iloc[test].to_numpy()
    sessions = pd.DatetimeIndex(ctx.returns.index).sort_values().unique()
    positions = sessions.get_indexer(pd.to_datetime(evaluation.date))
    if np.any(positions < 0):
        raise ValueError("Formation dates must belong to the observed price calendar")
    lam = float(ctx.payload.get("forgetting_factor", .97))
    eta = float(ctx.payload.get("obs_learning_rate", .01))
    if not 0 < lam <= 1 or not 0 < eta <= 1:
        raise ValueError("Invalid online learning parameters")
    # Fixed scale is estimated exclusively from pre-test training outcomes.
    scale = max(float(y.iloc[train].var()), 1e-10)
    weights = np.full(len(names), 1 / len(names))
    online = weights.copy()
    static = weights.copy()
    pending = []
    weight_rows, online_rows, scores, regret = [], [], [], []
    fixed_loss = np.zeros(len(names)); online_loss = 0.
    method = str(ctx.payload.get("ensemble_method", "dma"))
    if method not in {"dma", "obs", "static_bma", "equal_weight", "all"}:
        raise ValueError("Unsupported ensemble_method")
    for date, group in evaluation.groupby("date", sort=True):
        indices = group.index.to_numpy()
        position = int(positions[indices[0]])
        # Only earlier predictions whose entire outcome window has closed can update weights.
        matured = [item for item in pending if item[0] <= position]
        pending = [item for item in pending if item[0] > position]
        for _, loss, issued_online in matured:
            weights = softmax(lam * np.log(np.maximum(weights, 1e-300)) - loss / scale)
            online_loss += float(issued_online @ loss)
            fixed_loss += loss
            online = _project_simplex(online - eta * loss / scale)
        for name, weight, ow in zip(names, weights, online):
            weight_rows.append({"date": date_str(date), "model": name, "weight": float(weight)})
            online_rows.append({"date": date_str(date), "model": name, "weight": float(ow)})
        for i in indices:
            vector = matrix[i]
            dp, op, sp = float(weights @ vector), float(online @ vector), float(static @ vector)
            selected = op if method == "obs" else sp if method in {"static_bma", "equal_weight"} else dp
            scores.append({"date": date_str(date), "ticker": str(evaluation.ticker.iloc[i]), "dma_prediction": dp,
                           "obs_prediction": op, "static_bma_prediction": sp, "ensemble_prediction": selected,
                           "realized": float(outcomes[i]), "model_dispersion_std": float(vector.std())})
        loss = ((matrix[indices] - outcomes[indices, None]) ** 2).mean(axis=0)
        pending.append((position + horizon, loss, online.copy()))
        regret.append({"date": date_str(date), "obs_cumulative_loss": online_loss,
                       "best_fixed_model_loss": float(fixed_loss.min()), "obs_regret": online_loss - float(fixed_loss.min())})
    current = [{"model": name, "dma_weight": float(w), "obs_weight": float(o)} for name, w, o in zip(names, weights, online)]
    performance = model_performance_tracker(scores)
    return response("07", [summary("Top DMA Model", names[int(weights.argmax())], "model"), summary("OOS predictions", len(scores), "rows")],
        charts={"live_model_weight_dashboard": current, "model_weight_evolution": weight_rows,
                "dma_vs_obs_vs_static_bma": scores, "obs_weight_evolution": online_rows,
                "obs_regret_curve": regret, "model_performance_tracker": performance,
                "prediction_calibration_curve": prediction_calibration_rows(scores)},
        tables={"current_model_weights": current, "score_log": scores, "obs_regret_log": regret,
                "model_performance_tracker": performance,
                "training_audit": [{"train_rows": len(train), "test_rows": len(test), "label_horizon_sessions": horizon}]},
        meta={"update_protocol": "date_batched_after_label_maturity", "ensemble_method": method,
              "scoring_rule": "squared_error", "uncertainty": "model dispersion only; no predictive probability bands",
              "static_bma": "equal prior weights; no fitted marginal likelihood"})


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
