"""st02 Optimise: sweep parameters, find the plateau (not the best cell), rank what matters. Every cell is a trial on the ledger."""

from __future__ import annotations

import hashlib
import itertools
import math

import numpy as np
import pandas as pd

from app.services.shared import metrics as M

from . import compile as C
from . import engine, limits
from .backtest import Refusal, prepare, simulate
from .spec import Settings, Strategy

OBJECTIVES = {"sharpe": "Sharpe", "cagr": "CAGR", "calmar": "Calmar", "sortino": "Sortino"}


def _ranges(spec: Strategy) -> dict[str, tuple[float, float, float | None]]:
    out = {}
    for k, p in spec.params.items():
        if p.min is not None and p.max is not None and p.max > p.min:
            out[k] = (p.min, p.max, p.step)
    if not out:
        raise Refusal("No parameter has a range to search.", ["set Min and Max on a parameter in Build"])
    return out


def _grid(ranges: dict, n_max: int) -> list[dict[str, float]]:
    k = len(ranges)
    per = max(2, int(n_max ** (1 / k)))
    axes = []
    for lo, hi, step in ranges.values():
        if step:
            vals = np.arange(lo, hi + step / 2, step)
            if len(vals) > per:
                vals = vals[np.linspace(0, len(vals) - 1, per).round().astype(int)]
        else:
            vals = np.linspace(lo, hi, per)
        axes.append(np.unique(np.round(vals, 6)))
    return [dict(zip(ranges, c, strict=True)) for c in itertools.product(*axes)][:n_max]


def _snap(v: float, lo: float, step: float | None) -> float:
    return round(lo + round((v - lo) / step) * step, 6) if step else round(v, 6)


def _random(ranges: dict, n: int, seed: int) -> list[dict[str, float]]:
    rng = np.random.default_rng(seed)
    return [{k: _snap(rng.uniform(lo, hi), lo, step) for k, (lo, hi, step) in ranges.items()} for _ in range(n)]


def _score(eq: np.ndarray, dates: pd.DatetimeIndex, objective: str) -> tuple[float | None, dict]:
    m = M.return_metrics(eq, dates)
    if objective == "calmar":
        v = m.get("cagr") / abs(m["max_drawdown"]) if m.get("cagr") is not None and m.get("max_drawdown") else None
    else:
        v = m.get(objective)
    return (None if v is None or not math.isfinite(v) else float(v)), m


def plateau(cells: list[dict], names: list[str], ranges: dict, objective: str = "score") -> dict:
    """Neighbourhood median of the objective in normalised parameter space. The plateau centre maximises it; a best cell whose
    neighbours fall far below it is a spike (O-1)."""
    ok = [c for c in cells if c.get(objective) is not None]
    if len(ok) < 5:
        return {"status": "skipped", "reason": "fewer than 5 cells with a result"}
    x = np.array([[(c[k] - ranges[k][0]) / (ranges[k][1] - ranges[k][0]) for k in names] for c in ok])
    y = np.array([c[objective] for c in ok])
    d = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(-1))
    k = min(len(ok) - 1, 2 * len(names) + 2)
    nbr = np.argsort(d, axis=1)[:, 1:k + 1]
    hood = np.median(y[nbr], axis=1)
    for c, h in zip(ok, hood, strict=True):
        c["neighbourhood"] = float(h)
    best, centre = int(np.argmax(y)), int(np.argmax(hood))
    spread = float(np.std(y)) or 1e-9
    spike = (y[best] - hood[best]) > 1.0 * spread and hood[centre] < y[best] - 0.5 * spread
    keep = hood >= hood[centre] - 0.25 * spread
    region = {n: [float(min(c[n] for c, kk in zip(ok, keep, strict=True) if kk)), float(max(c[n] for c, kk in zip(ok, keep, strict=True) if kk))] for n in names}
    return {"status": "spike" if spike else "plateau", "centre": {n: ok[centre][n] for n in names}, "centre_score": float(hood[centre]), "best": {n: ok[best][n] for n in names},
            "best_score": float(y[best]), "best_neighbourhood": float(hood[best]), "region": region, "share_profitable_nearby": float((y[nbr[centre]] > 0).mean())}


def importance(cells: list[dict], names: list[str], objective: str = "score") -> list[dict]:
    """Share of the objective's variance explained by each parameter's own value (one-way)."""
    df = pd.DataFrame([c for c in cells if c.get(objective) is not None])
    if len(df) < 3 or df[objective].var() == 0:
        return []
    total = df[objective].var()
    out = []
    for n in names:
        bins = df[n] if df[n].nunique() <= 12 else pd.qcut(df[n], 8, duplicates="drop")
        out.append({"parameter": n, "share": float(df.groupby(bins, observed=True)[objective].mean().reindex(bins).var() / total)})
    return sorted(out, key=lambda r: -r["share"])


def pareto(cells: list[dict]) -> list[dict]:
    ok = [c for c in cells if c.get("sharpe") is not None and c.get("max_drawdown") is not None]
    return [c for c in ok if not any(o["sharpe"] >= c["sharpe"] and o["max_drawdown"] >= c["max_drawdown"] and (o["sharpe"] > c["sharpe"] or o["max_drawdown"] > c["max_drawdown"]) for o in ok)]


def run_optimise(spec: Strategy, settings: Settings, method: str = "grid", objective: str = "sharpe", n_max: int = 200, progress=None, cancelled=lambda: False) -> dict:
    stage = progress or (lambda *_: None)
    found = C.compile_spec(spec)
    if not found["ok"]:
        raise Refusal("The strategy does not compile.", ["fix the rule in Build"])
    ranges = _ranges(spec)
    names = list(ranges)
    stage("load", 5)
    prep = prepare(settings)
    dates, cap = prep.panel.dates, settings.capital

    def one(params: dict[str, float]) -> dict:
        sig = C.signals(spec, prep.sig_bars, dates, params)
        r = simulate(spec, prep, settings, sig=sig, params=params, magnifier=False)
        score, m = _score(r.equity, dates, objective)
        monthly = pd.Series(r.equity, index=dates).resample("ME").last().pct_change().dropna().to_numpy()
        return {**params, "score": score, "sharpe": m.get("sharpe"), "cagr": m.get("cagr"), "max_drawdown": m.get("max_drawdown"), "total_return": float(r.equity[-1] / cap - 1),
                "trades": len(r.trades), "_returns": monthly, "_open": int((r.trades[:, engine.T_REASON] == engine.R_OPEN).sum()) if len(r.trades) else 0}

    cells: list[dict] = []
    if method == "optuna":
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=settings.seed))
        for i in range(n_max):
            if cancelled():
                break
            t = study.ask()
            p = {k: (t.suggest_float(k, lo, hi, step=step) if step else t.suggest_float(k, lo, hi)) for k, (lo, hi, step) in ranges.items()}
            c = one(p)
            study.tell(t, c["score"] if c["score"] is not None else -1e9)
            cells.append(c)
            stage(f"cell {i + 1} / {n_max}", 10 + 80 * (i + 1) / n_max)
    else:
        todo = _grid(ranges, n_max) if method == "grid" else _random(ranges, n_max, settings.seed)
        for i, p in enumerate(todo):
            if cancelled():
                break
            cells.append(one(p))
            stage(f"cell {i + 1} / {len(todo)}", 10 + 80 * (i + 1) / len(todo))
    if not cells:
        raise Refusal("No cell finished.", ["the run was cancelled before the first cell"])

    stage("report", 92)
    plat = plateau(cells, names, ranges)
    trials = [{"returns": c.pop("_returns"), "sharpe": c["sharpe"], "hash": hashlib.sha256(f"{spec.hash()}:{settings.hash()}:{sorted(c.items())}".encode()).hexdigest()[:16]} for c in cells]
    for c in cells:
        c.pop("_open", None)
    ranked = sorted(cells, key=lambda c: -(c["score"] if c["score"] is not None else -1e18))
    heat = [{"x": c[names[0]], "y": c[names[1]] if len(names) > 1 else 0.0, "value": c["score"], "neighbourhood": c.get("neighbourhood")} for c in cells]
    label = OBJECTIVES.get(objective, objective)
    if plat["status"] == "plateau":
        region = ", ".join(f"{n} {a:g}-{b:g}" for n, (a, b) in plat["region"].items())
        headline = f"Plateau at {region}: {label} {plat['centre_score']:.2f} around the centre (best single cell {plat['best_score']:.2f})"
    elif plat["status"] == "spike":
        headline = f"Spike only: best cell {label} {plat['best_score']:.2f}, its neighbours {plat['best_neighbourhood']:.2f}"
    else:
        headline = f"{len(cells)} cells; {plat['reason']}"
    run_hash = hashlib.sha256(f"st02:{spec.hash()}:{settings.hash()}:{method}:{objective}:{n_max}".encode()).hexdigest()[:16]
    best = ranked[0]
    return {
        "feature_id": "st02", "status": "ok",
        "summary_cards": [{"label": "Cells", "value": len(cells)}, {"label": f"Plateau {label}", "value": plat.get("centre_score")}, {"label": f"Best cell {label}", "value": best["score"]},
                          {"label": "Profitable nearby", "value": plat.get("share_profitable_nearby"), "unit": "%"}],
        "charts": {"heatmap": heat},
        "tables": {"cells": ranked, "top_sets": ranked[:10], "importance": importance(cells, names), "pareto": pareto(cells)},
        "meta": {"headline": headline, "plateau": plat, "parameters": names, "ranges": {k: list(v) for k, v in ranges.items()}, "objective": objective, "objective_label": label,
                 "method": method, "cells": len(cells), "total_return": best["total_return"], "metrics": {"sharpe": best["sharpe"], "trades": best["trades"]},
                 "run_hash": run_hash, "result_hash": hashlib.sha256(str([c["score"] for c in cells]).encode()).hexdigest()[:16], "period": [str(dates[0].date()), str(dates[-1].date())],
                 "spec": spec.model_dump(), "settings": settings.model_dump(), "freshness": limits.freshness(), "verdict_chip": "not validated"},
        "_trials": trials,
    }
