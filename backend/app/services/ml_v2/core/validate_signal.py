"""Signal-to-return plumbing for Validate: weights, portfolio returns, model refits, controls, meta-labelling.

All functions work on wide (date x ticker) numpy arrays so that hundreds of permutations stay cheap.
"""
from __future__ import annotations

import hashlib
import math
from itertools import combinations
from typing import Callable

import numpy as np
import pandas as pd

from .cpcv import purged_complement
from .performance import sharpe

DEFAULT_Q = 0.3


def wide(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    return panel.pivot(index="date", columns="ticker", values=column).sort_index()


def weights_from_scores(scores: np.ndarray, q: float = DEFAULT_Q) -> np.ndarray:
    """Dollar-neutral long top / short bottom q-fraction per row, gross exposure 1; missing scores get no weight."""
    s = np.asarray(scores, dtype=float)
    valid = np.isfinite(s)
    n = valid.sum(1)
    k = np.minimum(np.maximum(1, np.round(q * n).astype(int)), n // 2)
    order = np.argsort(np.where(valid, s, np.nan), axis=1)
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.arange(s.shape[1])[None, :].repeat(s.shape[0], 0), axis=1)
    w = np.zeros_like(s)
    long = valid & (ranks >= (n - k)[:, None]) & (k[:, None] > 0)
    short = valid & (ranks < k[:, None]) & (k[:, None] > 0)
    kk = np.maximum(k, 1)[:, None]
    w[long] = np.broadcast_to(0.5 / kk, s.shape)[long]
    w[short] = -np.broadcast_to(0.5 / kk, s.shape)[short]
    return w


def portfolio_returns(weights: np.ndarray, outcomes: np.ndarray, horizon: int = 1, cost_bps: float = 0.0, lag: int = 0):
    """Per-period net returns and turnover. Signal at row t-lag is used on row t; rebalance every `horizon` rows."""
    w = weights
    if lag:
        w = np.vstack([np.zeros((lag, w.shape[1])), w[:-lag]])
    w, o = w[::horizon], np.nan_to_num(outcomes[::horizon], nan=0.0)
    gross = (w * o).sum(1)
    turnover = np.abs(np.diff(w, axis=0, prepend=np.zeros((1, w.shape[1])))).sum(1)
    return gross - turnover * cost_bps / 1e4, turnover


def strategy_series(pred: pd.DataFrame, out: pd.DataFrame, horizon: int, cost_bps: float, q: float = DEFAULT_Q, lag: int = 0):
    w = weights_from_scores(pred.to_numpy(), q)
    net, turnover = portfolio_returns(w, out.to_numpy(), horizon, cost_bps, lag)
    return pd.Series(net, index=pred.index[::horizon]), turnover


def ann(horizon: int) -> float:
    return 252.0 / max(horizon, 1)


def sharpe_of(series, horizon: int = 1) -> float:
    return sharpe(np.asarray(series, dtype=float), ann(horizon))


def ticker_half(ticker: str) -> int:
    return int(hashlib.sha1(ticker.encode()).hexdigest(), 16) % 2


# ---------------------------------------------------------------- controls

def buy_and_hold(out: pd.DataFrame, horizon: int) -> pd.Series:
    """Equal weights set on the first date and left to drift (no rebalancing)."""
    r = np.nan_to_num(out.to_numpy()[::horizon], nan=0.0)
    wealth = np.cumprod(1 + r, axis=0)
    prev = np.vstack([np.ones((1, r.shape[1])), wealth[:-1]])
    weight = prev / prev.sum(1, keepdims=True)
    return pd.Series((weight * r).sum(1), index=out.index[::horizon])


def equal_weight(out: pd.DataFrame, horizon: int) -> pd.Series:
    return out.iloc[::horizon].mean(axis=1).fillna(0.0)


def constant_exposure(strategy_weights: np.ndarray, out: pd.DataFrame, horizon: int) -> pd.Series:
    """Same average net exposure as the strategy, held constantly in the equal-weight universe (no signal)."""
    exposure = float(strategy_weights.sum(1).mean())
    return equal_weight(out, horizon) * exposure


def shuffled_controls(pred: pd.DataFrame, out: pd.DataFrame, horizon: int, cost_bps: float, q: float,
                      n_perm: int, seed: int) -> np.ndarray:
    """Sharpe of the same construction after permuting scores across tickers within each date."""
    rng = np.random.default_rng(seed)
    p, o = pred.to_numpy(), out.to_numpy()
    sharpes = np.empty(n_perm)
    for i in range(n_perm):
        shuffled = np.take_along_axis(p, rng.permuted(np.tile(np.arange(p.shape[1]), (p.shape[0], 1)), axis=1), axis=1)
        net, _ = portfolio_returns(weights_from_scores(shuffled, q), o, horizon, cost_bps)
        sharpes[i] = sharpe(net, ann(horizon))
    return sharpes


def lag_outcome_controls(out: pd.DataFrame, horizon: int, cost_bps: float, q: float) -> dict[str, pd.Series]:
    """Simple model control: yesterday's realised outcome (known by now) as momentum or reversal score."""
    known = out.shift(horizon)
    result = {}
    for name, sign in (("lag_momentum", 1.0), ("lag_reversal", -1.0)):
        result[name], _ = strategy_series(sign * known, out, horizon, cost_bps, q)
    return result


# ---------------------------------------------------------------- model refits

def make_model(name: str, seed: int):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if name == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(n_estimators=40, max_depth=4, min_samples_leaf=20, max_features=0.7, n_jobs=1, random_state=seed)
    return make_pipeline(StandardScaler(), Ridge(alpha=10.0))


def _fit_predict(factory: Callable[[], object], X: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray) -> np.ndarray:
    ok = train[np.isfinite(y[train]) & np.isfinite(X[train]).all(1)]
    if len(ok) < 30:
        raise ValueError("Too few purged training rows to fit the model")
    model = factory()
    model.fit(X[ok], y[ok])
    clean = np.nan_to_num(X[test], nan=0.0)
    return model.predict(clean)


def cpcv_model_paths(panel: pd.DataFrame, features: list[str], model: str, seed: int, horizon: int, embargo: int,
                     n_groups: int, k_test: int):
    """True CPCV: every split trains on the purged complement; each group's predictions are assembled into paths."""
    dates = pd.DatetimeIndex(panel["date"].unique()).sort_values()
    groups = np.array_split(dates.to_numpy(), n_groups)
    X = panel[features].to_numpy(dtype=float)
    y = panel["outcome"].to_numpy(dtype=float)
    stamp = pd.to_datetime(panel["date"])
    n_paths = math.comb(n_groups - 1, k_test - 1)
    paths = np.full((n_paths, len(panel)), np.nan)
    seen = np.zeros(n_groups, dtype=int)
    splits = 0
    for combo in combinations(range(n_groups), k_test):
        held = np.concatenate([groups[g] for g in combo])
        test = np.flatnonzero(stamp.isin(held).to_numpy())
        train = purged_complement(panel["date"], held, horizon, embargo)
        prediction = _fit_predict(lambda: make_model(model, seed), X, y, train, test)
        pos = pd.Series(prediction, index=test)
        for g in combo:
            rows = np.flatnonzero(stamp.isin(groups[g]).to_numpy())
            paths[seen[g], rows] = pos.loc[rows].to_numpy()
            seen[g] += 1
        splits += 1
    return paths, splits


def oos_predictions(panel: pd.DataFrame, features: list[str], model: str, seed: int, horizon: int, embargo: int, folds: int = 5) -> np.ndarray:
    """Single purged K-fold out-of-sample prediction per row (cheaper than CPCV; used for seed reruns and controls)."""
    dates = pd.DatetimeIndex(panel["date"].unique()).sort_values()
    X = panel[features].to_numpy(dtype=float)
    y = panel["outcome"].to_numpy(dtype=float)
    stamp = pd.to_datetime(panel["date"])
    out = np.full(len(panel), np.nan)
    for part in np.array_split(dates.to_numpy(), folds):
        test = np.flatnonzero(stamp.isin(part).to_numpy())
        train = purged_complement(panel["date"], part, horizon, embargo)
        out[test] = _fit_predict(lambda: make_model(model, seed), X, y, train, test)
    return out


def ols_control_predictions(panel: pd.DataFrame, features: list[str], horizon: int, embargo: int) -> np.ndarray:
    return oos_predictions(panel, features[:3], "ridge", 0, horizon, embargo)


# ---------------------------------------------------------------- meta-labelling ("Improve my strategy")

def meta_label_overlay(pred: pd.DataFrame, out: pd.DataFrame, horizon: int, embargo: int, cost_bps: float, q: float, seed: int = 7):
    """Meta-label filter and probability sizing on top of the primary signal, always beside the unfiltered strategy.

    Features known at formation: score z-score and rank, trailing realised volatility of the ticker's outcomes
    (lagged by the horizon), and whether the last known outcome agrees with the side. Out-of-fold purged fits.
    """
    from sklearn.linear_model import LogisticRegression
    p, o = pred.to_numpy(), out.to_numpy()
    w = weights_from_scores(p, q)
    z = (pred.sub(pred.mean(axis=1), axis=0)).div(pred.std(axis=1).replace(0, np.nan), axis=0)
    known = out.shift(horizon)
    vol = known.rolling(20, min_periods=5).std()
    side = np.sign(w)
    agree = np.sign(known.fillna(0).to_numpy()) * side
    feats = np.stack([np.abs(z.to_numpy()), vol.to_numpy(), agree], axis=-1)
    n_dates = p.shape[0]
    probability = np.full(p.shape, np.nan)
    active = side != 0
    dates = np.array_split(np.arange(n_dates), 5)
    flat_idx = np.arange(n_dates)[:, None].repeat(p.shape[1], 1)
    target = ((side * np.nan_to_num(o)) > 0).astype(int)
    index = pd.DatetimeIndex(pred.index)
    for part in dates:
        lo, hi = part.min(), part.max()
        banned = (flat_idx >= lo - horizon) & (flat_idx <= hi + horizon + embargo)
        train = active & ~banned & np.isfinite(feats).all(-1)
        test = active & (flat_idx >= lo) & (flat_idx <= hi) & np.isfinite(feats).all(-1)
        if train.sum() < 50 or len(np.unique(target[train])) < 2 or not test.any():
            continue
        model = LogisticRegression(max_iter=300, C=1.0, random_state=seed).fit(feats[train], target[train])
        probability[test] = model.predict_proba(feats[test])[:, 1]
    have = np.isfinite(probability)
    if not have.any():
        return {"status": "unavailable", "reason": "Too few active positions to fit the meta-label model"}
    keep = np.where(have, probability >= 0.5, True)
    size = np.where(have, probability, 1.0)
    variants = {"unfiltered": w, "meta_filter": w * keep, "meta_sized": w * size}
    rows, series = [], {}
    for name, weights in variants.items():
        net, turnover = portfolio_returns(weights, o, horizon, cost_bps)
        s = pd.Series(net, index=index[::horizon])
        series[name] = s
        rows.append({"variant": name, "sharpe": sharpe_of(net, horizon), "mean_return": float(net.mean()),
                     "total_return": float(np.prod(1 + net) - 1), "avg_turnover": float(turnover.mean()),
                     "positions_kept": float((np.abs(weights) > 0).sum() / max(1, (np.abs(w) > 0).sum()))})
    base = rows[0]["sharpe"]
    best = max(rows[1:], key=lambda r: -np.inf if not np.isfinite(r["sharpe"]) else r["sharpe"])
    delta = (best["sharpe"] - base) if np.isfinite(best["sharpe"]) and np.isfinite(base) else None
    sample = probability[have]
    sample = sample[np.linspace(0, len(sample) - 1, min(500, len(sample))).astype(int)]
    return {"status": "ok", "probabilities": [{"meta_probability": float(x)} for x in sample], "rows": rows, "best_variant": best["variant"], "sharpe_delta": delta,
            "improved": bool(delta is not None and delta > 0.15),
            "features": ["abs_score_zscore", "trailing_outcome_vol_20", "last_outcome_agrees_with_side"],
            "probability_share_available": float(have[active].mean()) if active.any() else 0.0,
            "note": "Out-of-fold purged fits; the unfiltered strategy is always shown beside the filtered and sized variants."}
