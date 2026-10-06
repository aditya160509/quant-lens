"""ML V2 barriers implementation."""
from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from .validation import purged_date_folds
from .common import clean_json, compact_records, date_str, number_like, response, summary
from .panel import MLContext, load_context


def run_triple_barrier(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=8)
    horizon = int(number_like(ctx.payload.get("max_holding_period"), 21) or 21)
    pt = float(number_like(ctx.payload.get("profit_taking_barrier"), 0.05) or 0.05)
    sl = float(number_like(ctx.payload.get("stop_loss_barrier"), 0.03) or 0.03)
    barrier_mode = str(ctx.payload.get("barrier_mode") or "fixed").lower()
    barrier_side = str(ctx.payload.get("barrier_side") or "bilateral").lower()
    if pt <= 0 or sl <= 0 or horizon < 1 or barrier_side != "bilateral":
        raise ValueError("Require positive PT/SL, a positive horizon and bilateral barriers")
    if barrier_mode not in {"fixed", "vol_scaled"}:
        raise ValueError(f"Unsupported barrier_mode: {barrier_mode}")
    if barrier_mode == "vol_scaled" and min(pt, sl) < 0.25:
        raise ValueError("vol_scaled barriers are multiples of horizon volatility (for example 2.0 and 1.5), not return fractions")
    rows = []
    for ticker in ctx.returns.columns:
        rows.extend(high_low_triple_barrier_rows(ctx, ticker, horizon, pt, sl,
                    max_events=600, barrier_mode=barrier_mode))
    labels = pd.DataFrame(rows)
    if labels.empty:
        raise ValueError("No complete OHLC event windows for triple-barrier labeling")
    labels = labels.sort_values(["date", "ticker"]).reset_index(drop=True)
    dist = labels.groupby("label").size().reset_index(name="count")
    # Primary side is observable at event formation, never the future barrier label.
    sides = ctx.returns.rolling(21).sum().stack()
    labels["primary_side"] = np.sign(sides.reindex(pd.MultiIndex.from_arrays([pd.to_datetime(labels["date"]), labels["ticker"]])).to_numpy())
    features = labels[["vol_21", "primary_side"]].astype(float)
    target = (labels["primary_side"] * labels["forward_return"] > 0).astype(int)
    probabilities = np.full(len(labels), np.nan)
    for train_idx, test_idx in purged_date_folds(labels, n_splits=3, horizon=horizon, embargo=int(ctx.payload.get("embargo_period", 5))):
        valid_train = (features.iloc[train_idx].notna().all(axis=1) & labels["forward_return"].iloc[train_idx].notna()).to_numpy()
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
    if sizing not in {"probability", "binary"}:
        raise ValueError("Only probability and binary sizing are supported; calibrated payoff Kelly sizing is unavailable")
    labels["position_size"] = np.where(labels["meta_probability"].isna(), np.nan, np.where(sizing == "binary", (labels["meta_probability"] >= 0.5).astype(float), labels["meta_probability"]))
    cqr_meta = {"method": "lightgbm_quantile_cqr", "target_coverage": confidence}
    labels, cqr_meta = _lightgbm_cqr_intervals(labels, confidence=confidence, horizon=horizon, annualization=ctx.annualization)
    coverage = cqr_meta.get("test_empirical_coverage")
    coverage_by_date = _rolling_coverage_audit(labels, confidence)
    # Compare like with like: the volatility-scaled barrier is set to the same median width as the fixed one.
    horizon_vol = float(np.nanmedian(labels["vol_21"].astype(float))) / math.sqrt(ctx.annualization) * math.sqrt(horizon)
    settings = {"fixed": (pt, sl) if barrier_mode == "fixed" else (pt * horizon_vol, sl * horizon_vol),
                "vol_scaled": (pt, sl) if barrier_mode == "vol_scaled" else (pt / horizon_vol, sl / horizon_vol)}
    label_comparison = []
    for mode, (mode_pt, mode_sl) in settings.items():
        events = [event for ticker in ctx.symbols for event in high_low_triple_barrier_rows(ctx, ticker, horizon, mode_pt, mode_sl, max_events=600, barrier_mode=mode)]
        identified = [event["label"] for event in events if event["label"] is not None]
        label_comparison.append({"method":mode,"events":len(events),"ambiguous":len(events)-len(identified),
            **{name:float(np.mean(np.asarray(identified)==value)) if identified else None for name,value in [("positive_rate",1),("negative_rate",-1),("neutral_rate",0)]}})
    barrier_sensitivity = barrier_sensitivity_rows(ctx, horizon)
    return response(
        "04",
        [summary("Events", len(labels), "labels"), summary(f"Interval coverage (target {confidence:.0%})", coverage, "%"), summary("PT/SL", f"{pt:.2%}/{sl:.2%}", "barrier")],
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



def high_low_triple_barrier_rows(ctx: MLContext, ticker: str, horizon: int, pt: float, sl: float, max_events: int = 120, barrier_mode: str = "fixed") -> list[dict[str, Any]]:
    """Bilateral high/low-path barriers. Fixed mode: pt/sl are return fractions; vol_scaled: multiples of horizon volatility."""
    if barrier_mode not in {"fixed", "vol_scaled"}:
        raise ValueError(f"Unsupported barrier_mode: {barrier_mode}")
    df = ctx.ohlcv[ctx.ohlcv["Ticker"] == ticker].sort_values("Date").tail(max_events + horizon + 5)
    n = len(df)
    if n <= horizon:
        return []
    dates = pd.DatetimeIndex(df["Date"])
    high, low, close = (df[c].to_numpy(dtype=float) for c in ("High", "Low", "Close"))
    daily_vol = (ctx.returns[ticker].rolling(21).std().reindex(dates).to_numpy(dtype=float) if ticker in ctx.returns else np.full(n, np.nan))
    first = max(0, n - max_events - horizon)
    i = np.arange(first, n - horizon)
    if not len(i):
        return []
    path = np.arange(1, horizon + 1)
    H, L, C = (a[i[:, None] + path] for a in (high, low, close))
    entry = close[i]
    ok = np.isfinite(entry) & (entry > 0) & np.isfinite(H).all(1) & np.isfinite(L).all(1) & np.isfinite(C).all(1)
    vol = daily_vol[i]
    if barrier_mode == "vol_scaled":
        ok &= np.isfinite(vol) & (vol > 0)
        pt_i = np.maximum(1e-4, pt * vol * math.sqrt(horizon))
        sl_i = np.maximum(1e-4, sl * vol * math.sqrt(horizon))
    else:
        pt_i = np.full(len(i), pt)
        sl_i = np.full(len(i), sl)
    upper, lower = entry * (1 + pt_i), entry * (1 - sl_i)
    up, down = H >= upper[:, None], L <= lower[:, None]
    touched = up | down
    hit = touched.any(1)
    step = np.where(hit, touched.argmax(1), horizon - 1)  # first barrier bar, else the vertical bar
    row = np.arange(len(i))
    both = up[row, step] & down[row, step] & hit
    label = np.where(hit, np.where(up[row, step], 1, -1), 0)
    forward = np.where(label == 1, upper / entry - 1, np.where(label == -1, lower / entry - 1, C[row, step] / entry - 1))
    forward = np.where(both, np.nan, forward)
    rows = []
    for k in np.flatnonzero(ok):
        touch = dates[i[k] + 1 + step[k]]
        kind = "ambiguous_same_bar_order" if both[k] else "profit_taking" if label[k] == 1 else "stop_loss" if label[k] == -1 else "vertical"
        rows.append({"date": date_str(dates[i[k]]), "ticker": ticker, "forward_return": float(forward[k]),
                     "label": None if both[k] else int(label[k]),
                     "vol_21": float(vol[k] * math.sqrt(ctx.annualization)) if np.isfinite(vol[k]) else None,
                     "touch_date": date_str(touch), "touch_type": kind, "upper_barrier": float(upper[k]),
                     "lower_barrier": float(lower[k]), "barrier_method": "high_low_path"})
    return clean_json(rows[-max_events:])


def barrier_sensitivity_rows(ctx: MLContext, horizon: int) -> list[dict[str, Any]]:
    rows = []
    for pt in [.02,.04,.06,.08]:
        for sl in [.02,.04,.06]:
            events = [event for ticker in ctx.symbols for event in high_low_triple_barrier_rows(ctx,ticker,horizon,pt,sl,max_events=120)]
            labels = np.array([event["label"] for event in events if event["label"] is not None])
            rows.append({"profit_taking":pt,"stop_loss":sl,"events":len(events),"ambiguous_events":len(events)-len(labels),
                "positive_rate":float(np.mean(labels==1)) if len(labels) else None,
                "negative_rate":float(np.mean(labels==-1)) if len(labels) else None,
                "neutral_rate":float(np.mean(labels==0)) if len(labels) else None})
    return rows


def _lightgbm_cqr_intervals(labels: pd.DataFrame, confidence: float, horizon: int, annualization: float):
    """Quantile regression with disjoint purged training/calibration/test dates."""
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

