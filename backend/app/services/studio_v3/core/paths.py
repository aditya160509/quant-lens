"""Backtest > When and > Paths: P&L by market regime, seasonality, and trade-order Monte Carlo (PAGES §3.2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

RUIN_LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5)


def regimes(bench: np.ndarray, dates: pd.DatetimeIndex) -> np.ndarray:
    """Label each bar from the benchmark known at that bar's close: trend (vs 200-day mean) × volatility (20-day vs its expanding median)."""
    s = pd.Series(bench, index=dates)
    trend = np.where(s >= s.rolling(200, min_periods=200).mean(), "trend up", "trend down")
    vol = s.pct_change().rolling(20, min_periods=20).std()
    high = vol > vol.expanding(min_periods=60).median()
    out = np.array([f"{t}, {'high' if h else 'low'} vol" for t, h in zip(trend, high, strict=True)], dtype=object)
    out[(s.rolling(200, min_periods=200).mean().isna() | vol.expanding(min_periods=60).median().isna()).to_numpy()] = "warm-up"
    return out


def by_regime(labels: np.ndarray, entry_bar: np.ndarray, pnl: np.ndarray, ret: np.ndarray) -> list[dict]:
    rows = []
    at = labels[entry_bar]
    total = float(pnl.sum())
    for lab in sorted(set(at)):
        m = at == lab
        rows.append({"regime": lab, "trades": int(m.sum()), "pnl": float(pnl[m].sum()), "share": float(pnl[m].sum() / total) if total > 0 else None,
                     "win_rate": float((pnl[m] > 0).mean()), "avg_return": float(ret[m].mean()), "days": int((labels == lab).sum())})
    return sorted(rows, key=lambda r: -r["pnl"])


def seasonality(equity: np.ndarray, dates: pd.DatetimeIndex) -> list[dict]:
    m = pd.Series(equity, index=dates).resample("ME").last().pct_change().dropna()
    g = m.groupby(m.index.month)
    return [{"month": pd.Timestamp(2000, k, 1).strftime("%b"), "mean": float(v.mean()), "hit_rate": float((v > 0).mean()), "years": len(v)} for k, v in g]


def trade_monte_carlo(pnl: np.ndarray, capital: float, n: int = 1000, seed: int = 7) -> dict | None:
    """Reshuffle the order of closed trades n times: same trades, different luck of sequence."""
    if len(pnl) < 10:
        return None
    rng = np.random.default_rng(seed)
    paths = capital + np.cumsum(rng.permuted(np.tile(pnl, (n, 1)), axis=1), axis=1)
    paths = np.hstack([np.full((n, 1), capital), paths])
    peak = np.maximum.accumulate(paths, axis=1)
    dd = ((paths - peak) / peak).min(axis=1)
    losing = pnl <= 0
    streaks = np.array([_longest(losing[rng.permutation(len(pnl))]) for _ in range(n)])
    step = max(1, paths.shape[1] // 200)
    cols = sorted(set(range(0, paths.shape[1], step)) | {paths.shape[1] - 1})
    q = np.percentile(paths[:, cols], [5, 25, 50, 75, 95], axis=0)
    fan = [{"trade": c, "p5": q[0, i], "p25": q[1, i], "p50": q[2, i], "p75": q[3, i], "p95": q[4, i]} for i, c in enumerate(cols)]
    return {
        "fan": fan,
        "drawdown_p95": float(np.percentile(dd, 5)), "drawdown_median": float(np.median(dd)),
        "ruin": [{"drawdown": lvl, "probability": float((dd <= -lvl).mean())} for lvl in RUIN_LEVELS],
        "streak_p95": int(np.percentile(streaks, 95)), "streak_actual": _longest(losing),
        "streaks": [{"length": int(k), "share": float((streaks == k).mean())} for k in range(int(streaks.min()), int(streaks.max()) + 1)],
        "paths": n,
    }


def _longest(flags: np.ndarray) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best
