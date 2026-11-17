"""The one metric set (docs/studio/plan/FEATURES_AND_OUTPUTS.md §4). Every lab imports its Sharpe and drawdown from here.

Unknown stays unknown: a metric that cannot be computed is None, never zero.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

ANN = 252.0


def sharpe(series: np.ndarray | pd.Series | Iterable, ann: float = ANN) -> float:
    arr = np.asarray(series, dtype=np.float64).ravel()
    finite = arr[np.isfinite(arr)]
    if len(finite) < 2:
        return float("nan")  # undefined with fewer than two observations
    sd = finite.std(ddof=1)
    return float(finite.mean() / sd * math.sqrt(ann)) if sd > 1e-12 else float("nan")


def max_drawdown(equity: np.ndarray | pd.Series | Iterable) -> float:
    arr = np.asarray(equity, dtype=np.float64).ravel()
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return 0.0
    running_max = np.maximum.accumulate(arr)
    return float((arr / np.where(running_max > 1e-12, running_max, 1.0) - 1.0).min())


def equity_from_returns(returns: np.ndarray | pd.Series | Iterable) -> np.ndarray:
    arr = np.asarray(returns, dtype=np.float64).ravel()
    return np.cumprod(1.0 + np.where(np.isfinite(arr), arr, 0.0))


def _num(x: Any) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None


def _div(a: float, b: float) -> float | None:
    return _num(a / b) if abs(b) > 1e-12 else None


def drawdowns(equity: np.ndarray) -> list[dict[str, int | float | None]]:
    """Every drawdown episode: peak, trough and recovery bar (None while still under water), depth."""
    eq = np.asarray(equity, dtype=np.float64)
    peak = np.maximum.accumulate(eq)
    under = eq < peak
    edges = np.diff(np.concatenate(([False], under, [False])).astype(np.int8))
    out = []
    for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        trough = int(s + np.argmin(eq[s:e]))
        out.append({"peak": int(s - 1), "trough": trough, "recovery": int(e) if e < len(eq) else None,
                    "depth": float(eq[trough] / peak[trough] - 1), "bars": int(e - s + 1)})
    return out


def return_metrics(equity: np.ndarray, dates: pd.DatetimeIndex | None = None, ann: float = ANN) -> dict[str, Any]:
    """Return and drawdown block from an equity curve that starts at the first bar's close."""
    eq = np.asarray(equity, dtype=np.float64)
    if len(eq) < 3 or not np.isfinite(eq).all() or (eq <= 0).any():
        return {}
    r = eq[1:] / eq[:-1] - 1
    years = len(r) / ann
    total = eq[-1] / eq[0] - 1
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1
    vol = r.std(ddof=1) * math.sqrt(ann)
    downside = math.sqrt(np.mean(np.minimum(r, 0) ** 2)) * math.sqrt(ann)
    dd = eq / np.maximum.accumulate(eq) - 1
    mdd = float(dd.min())
    episodes = drawdowns(eq)
    ulcer = math.sqrt(float(np.mean(dd**2)))
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    q05, q95 = np.quantile(r, 0.05), np.quantile(r, 0.95)
    out: dict[str, Any] = {
        "total_return": _num(total), "cagr": _num(cagr), "annual_vol": _num(vol), "sharpe": _num(sharpe(r, ann)),
        "sortino": _div(r.mean() * ann, downside), "calmar": _div(cagr, abs(mdd)), "mar": _div(cagr, abs(mdd)),
        "omega": _div(gains, losses), "gain_to_pain": _div(r.sum(), losses), "ulcer": _num(ulcer), "upi": _div(cagr, ulcer),
        "tail_ratio": _div(q95, abs(q05)), "skew": _num(stats.skew(r, bias=False)) if vol > 1e-12 else None,
        "kurtosis": _num(stats.kurtosis(r, bias=False)) if vol > 1e-12 else None,
        "var_95": _num(q05), "cvar_95": _num(r[r <= q05].mean()), "best_day": _num(r.max()), "worst_day": _num(r.min()),
        "max_drawdown": mdd, "avg_drawdown": _num(np.mean([e["depth"] for e in episodes])) if episodes else None,
        "max_drawdown_bars": max((e["bars"] for e in episodes), default=0),
        "recovery_bars": next((e["recovery"] - e["trough"] if e["recovery"] is not None else None for e in sorted(episodes, key=lambda e: e["depth"])), None),
        "time_under_water": _num((dd < 0).mean()), "drawdowns_over_10pct": sum(e["depth"] <= -0.10 for e in episodes),
        "years": _num(years), "observations": len(r),
    }
    if dates is not None and len(dates) == len(eq):
        s = pd.Series(eq, index=dates)
        m, y = s.resample("ME").last().pct_change().dropna(), s.resample("YE").last().pct_change().dropna()
        out.update(best_month=_num(m.max()) if len(m) else None, worst_month=_num(m.min()) if len(m) else None,
                   best_year=_num(y.max()) if len(y) else None, worst_year=_num(y.min()) if len(y) else None,
                   positive_months=_num((m > 0).mean()) if len(m) else None)
    return out


def trade_metrics(pnl: np.ndarray, ret: np.ndarray, bars: np.ndarray, mae: np.ndarray | None = None, mfe: np.ndarray | None = None,
                  risk: np.ndarray | None = None, years: float | None = None) -> dict[str, Any]:
    """Trade block. `risk` is the money at risk to the stop per trade (for expectancy in R)."""
    pnl, ret, bars = (np.asarray(a, dtype=np.float64) for a in (pnl, ret, bars))
    n = len(pnl)
    if n == 0:
        return {"trades": 0}
    win, loss = pnl > 0, pnl < 0
    gross_win, gross_loss = pnl[win].sum(), -pnl[loss].sum()
    wr = win.mean()
    avg_win, avg_loss = (pnl[win].mean() if win.any() else 0.0), (pnl[loss].mean() if loss.any() else 0.0)
    payoff = _div(avg_win, abs(avg_loss))

    def streak(mask: np.ndarray) -> int:
        edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
        runs = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
        return int(runs.max()) if len(runs) else 0

    out: dict[str, Any] = {
        "trades": n, "trades_per_year": _div(n, years) if years else None, "win_rate": _num(wr),
        "profit_factor": _div(gross_win, gross_loss), "payoff_ratio": payoff, "expectancy": _num(pnl.mean()),
        "avg_win": _num(avg_win) if win.any() else None, "avg_loss": _num(avg_loss) if loss.any() else None,
        "largest_win": _num(pnl.max()), "largest_loss": _num(pnl.min()), "avg_return": _num(ret.mean()),
        "max_consecutive_wins": streak(win), "max_consecutive_losses": streak(loss), "avg_bars": _num(bars.mean()),
        "avg_bars_win": _num(bars[win].mean()) if win.any() else None, "avg_bars_loss": _num(bars[loss].mean()) if loss.any() else None,
        "sqn": _div(math.sqrt(n) * ret.mean(), ret.std(ddof=1)) if n > 1 else None,
        "kelly": _num(wr - (1 - wr) / payoff) if payoff else None,
    }
    if risk is not None and np.isfinite(risk).any():
        ok = np.isfinite(risk) & (risk > 0)
        out["expectancy_r"] = _num((pnl[ok] / risk[ok]).mean()) if ok.any() else None
    if mae is not None and mfe is not None and len(mae):
        out["edge_ratio"] = _div(float(np.mean(mfe)), float(np.mean(np.abs(mae))))
    return out


def benchmark_metrics(equity: np.ndarray, benchmark: np.ndarray, ann: float = ANN) -> dict[str, Any]:
    eq, bm = np.asarray(equity, dtype=np.float64), np.asarray(benchmark, dtype=np.float64)
    if len(eq) != len(bm) or len(eq) < 3 or not (np.isfinite(bm).all() and (bm > 0).all()):
        return {}
    r, b = eq[1:] / eq[:-1] - 1, bm[1:] / bm[:-1] - 1
    var_b = b.var(ddof=1)
    if var_b <= 1e-18:
        return {}
    beta = np.cov(r, b, ddof=1)[0, 1] / var_b
    corr = np.corrcoef(r, b)[0, 1] if r.std() > 1e-12 else float("nan")
    active = r - b
    up, down = b > 0, b < 0
    years = len(r) / ann
    return {
        "alpha": _num((r.mean() - beta * b.mean()) * ann), "beta": _num(beta), "correlation": _num(corr), "r_squared": _num(corr**2),
        "tracking_error": _num(active.std(ddof=1) * math.sqrt(ann)), "information_ratio": _div(active.mean() * ann, active.std(ddof=1) * math.sqrt(ann)),
        "up_capture": _div(r[up].mean(), b[up].mean()) if up.any() else None, "down_capture": _div(r[down].mean(), b[down].mean()) if down.any() else None,
        "excess_return": _num((eq[-1] / eq[0]) ** (1 / years) - (bm[-1] / bm[0]) ** (1 / years)),
        "benchmark_total_return": _num(bm[-1] / bm[0] - 1), "benchmark_cagr": _num((bm[-1] / bm[0]) ** (1 / years) - 1),
        "benchmark_max_drawdown": max_drawdown(bm), "benchmark_sharpe": _num(sharpe(b, ann)),
    }


def psr(returns: np.ndarray, benchmark_sharpe: float = 0.0, ann: float = ANN) -> float | None:
    """Probabilistic Sharpe ratio (Bailey and Lopez de Prado 2012): P(true Sharpe > benchmark), per-period inside."""
    r = np.asarray(returns, dtype=np.float64)
    r = r[np.isfinite(r)]
    if len(r) < 3 or r.std(ddof=1) <= 1e-12:
        return None
    sr = r.mean() / r.std(ddof=1)
    var = 1 - stats.skew(r, bias=False) * sr + (stats.kurtosis(r, fisher=False, bias=False) - 1) * sr * sr / 4
    if var <= 0:
        return None
    return float(stats.norm.cdf((sr - benchmark_sharpe / math.sqrt(ann)) * math.sqrt(len(r) - 1) / math.sqrt(var)))


def min_track_record(returns: np.ndarray, benchmark_sharpe: float = 0.0, confidence: float = 0.95, ann: float = ANN) -> float | None:
    """Observations needed for PSR to reach `confidence`; None when the Sharpe does not beat the benchmark."""
    r = np.asarray(returns, dtype=np.float64)
    r = r[np.isfinite(r)]
    if len(r) < 3 or r.std(ddof=1) <= 1e-12:
        return None
    sr, sr0 = r.mean() / r.std(ddof=1), benchmark_sharpe / math.sqrt(ann)
    if sr <= sr0:
        return None
    var = 1 - stats.skew(r, bias=False) * sr + (stats.kurtosis(r, fisher=False, bias=False) - 1) * sr * sr / 4
    return float(1 + var * (stats.norm.ppf(confidence) / (sr - sr0)) ** 2)
