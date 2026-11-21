"""st02 Optimise: sweep parameters, find the plateau (not the best cell), rank what matters. Every cell is a trial on the ledger."""

from __future__ import annotations

import ast
import hashlib
import itertools
import math
import operator
import time

import numpy as np
import pandas as pd

from app.services.shared import metrics as M

from . import compile as C
from . import engine, limits
from .backtest import Refusal, prepare, simulate
from .spec import Settings, Strategy
from .store import effective_trials as store_effective

OBJECTIVES = {"sharpe": "Sharpe", "cagr": "CAGR", "calmar": "Calmar", "sortino": "Sortino", "profit_factor": "Profit factor", "ulcer": "Return / Ulcer", "custom": "Custom"}
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
METRIC_NAMES = ("sharpe", "cagr", "max_drawdown", "sortino", "trades", "total_return", "profit_factor", "ulcer", "win_rate")


def _arith(expr: str, names: dict[str, float | None]) -> float | bool | None:
    """Arithmetic and comparisons over named numbers; nothing else parses. None when a name has no value."""
    def go(n):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id not in names:
                raise ValueError(f"unknown name '{n.id}'")
            return names[n.id]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "abs" and len(n.args) == 1:
            v = go(n.args[0])
            return None if v is None else abs(v)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            v = go(n.operand)
            return None if v is None else _OPS[type(n.op)](v)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = go(n.left), go(n.right)
            if a is None or b is None or (isinstance(n.op, ast.Div) and b == 0):
                return None
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _OPS:
            a, b = go(n.left), go(n.comparators[0])
            return None if a is None or b is None else _OPS[type(n.ops[0])](a, b)
        raise ValueError("only numbers, names, + - * / **, abs() and one comparison")
    return go(ast.parse(expr, mode="eval"))


def check_expr(expr: str, names) -> None:
    try:
        _arith(expr, dict.fromkeys(names, 1.0))
    except (SyntaxError, ValueError) as e:
        raise Refusal(f"Cannot read '{expr}': {e}", [f"names allowed: {', '.join(names)}"]) from e


def _ranges(spec: Strategy) -> dict[str, tuple[float, float, float | None]]:
    out = {}
    for k, p in spec.parameter_definitions().items():
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


def _random(ranges: dict, n: int, seed: int, logs: set[str] = frozenset()) -> list[dict[str, float]]:
    rng = np.random.default_rng(seed)
    def draw(k, lo, hi):
        return float(np.exp(rng.uniform(np.log(lo), np.log(hi)))) if k in logs and lo > 0 else rng.uniform(lo, hi)
    return [{k: _snap(draw(k, lo, hi), lo, step) for k, (lo, hi, step) in ranges.items()} for _ in range(n)]


def _score(eq: np.ndarray, dates: pd.DatetimeIndex, objective: str, pnl: np.ndarray, custom: str = "") -> tuple[float | None, dict]:
    m = dict(M.return_metrics(eq, dates))
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    m["profit_factor"] = float(wins / losses) if losses > 0 else None
    m["win_rate"] = float((pnl > 0).mean()) if len(pnl) else None
    dd = eq / np.maximum.accumulate(eq) - 1
    m["ulcer"] = float(np.sqrt((dd**2).mean()))
    m["trades"], m["total_return"] = len(pnl), float(eq[-1] / eq[0] - 1)
    if objective == "calmar":
        v = m.get("cagr") / abs(m["max_drawdown"]) if m.get("cagr") is not None and m.get("max_drawdown") else None
    elif objective == "ulcer":
        v = m.get("cagr") / m["ulcer"] if m.get("cagr") is not None and m["ulcer"] > 0 else None
    elif objective == "custom":
        v = _arith(custom, {k: m.get(k) for k in METRIC_NAMES})
    else:
        v = m.get(objective)
    return (None if v is None or isinstance(v, bool) or not math.isfinite(v) else float(v)), m


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


def stability(cells: list[dict], names: list[str], ranges: dict, centre: dict, radius: int = 1, objective: str = "score") -> dict | None:
    """Cells within `radius` steps of the plateau centre on every axis: their scores, and the share within 20% of the best."""
    ok = [c for c in cells if c.get(objective) is not None]
    if not ok or not centre:
        return None
    def near(c):
        return all(abs(c[n] - centre[n]) <= radius * (ranges[n][2] or (ranges[n][1] - ranges[n][0]) / 10) + 1e-9 for n in names)
    hood = [c[objective] for c in ok if near(c)]
    best = max(c[objective] for c in ok)
    if not hood:
        return None
    within = [v for v in hood if (best - v) <= 0.2 * abs(best)] if best else hood
    return {"radius": radius, "cells": len(hood), "within_20pct": len(within) / len(hood), "scores": hood}


def _partial(cells: list[dict], names: list[str], i: int) -> tuple:
    """Every 5th cell: the finished cells as [x, y, score], so the map fills in while the sweep runs."""
    if i % 5:
        return ()
    return ({"x": names[0], "y": names[1] if len(names) > 1 else None, "cells": [[c[names[0]], c[names[1]] if len(names) > 1 else 0, c["score"]] for c in cells]},)


def run_optimise(spec: Strategy, settings: Settings, method: str = "grid", objective: str = "sharpe", n_max: int = 200, progress=None, cancelled=lambda: False,
                 custom: str = "", link: str = "", min_trades: int = 0, max_dd: float | None = None, radius: int = 1, budget_s: float = 0) -> dict:
    stage = progress or (lambda *_: None)
    found = C.compile_spec(spec)
    if not found["ok"]:
        raise Refusal("The strategy does not compile.", ["fix the rule in Build"])
    ranges = _ranges(spec)
    names = list(ranges)
    if objective == "custom":
        check_expr(custom or "x", METRIC_NAMES)
    if link:
        check_expr(link, list(spec.parameter_definitions()))
    logs = {k for k, p in spec.parameter_definitions().items() if p.log}
    t0 = time.perf_counter()
    stage("load", 5)
    prep = prepare(settings)
    dates, cap = prep.panel.dates, settings.capital

    def one(params: dict[str, float]) -> dict:
        r = simulate(spec, prep, settings, params=params)
        score, m = _score(r.equity, dates, objective, r.trades[:, engine.T_PNL] if len(r.trades) else np.zeros(0), custom)
        monthly = pd.Series(r.equity, index=dates).resample("ME").last().pct_change().dropna().to_numpy()
        excluded = "too few trades" if len(r.trades) < min_trades else "drawdown over limit" if max_dd and m.get("max_drawdown") is not None and m["max_drawdown"] < -max_dd else None
        return {**params, "score": None if excluded else score, "excluded": excluded, "sharpe": m.get("sharpe"), "cagr": m.get("cagr"), "max_drawdown": m.get("max_drawdown"),
                "profit_factor": m.get("profit_factor"), "total_return": float(r.equity[-1] / cap - 1), "trades": len(r.trades), "_returns": monthly, "_equity": r.equity,
                "_open": int((r.trades[:, engine.T_REASON] == engine.R_OPEN).sum()) if len(r.trades) else 0}

    def allowed(p: dict[str, float]) -> bool:
        return not link or bool(_arith(link, {**spec.values(), **p}))

    def out_of_time() -> bool:
        return bool(budget_s) and time.perf_counter() - t0 > budget_s

    cells: list[dict] = []
    if method == "optuna":
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=settings.seed))
        for i in range(n_max):
            if cancelled() or out_of_time():
                break
            t = study.ask()
            p = {k: (t.suggest_float(k, lo, hi, log=True) if k in logs and lo > 0 else t.suggest_float(k, lo, hi, step=step) if step else t.suggest_float(k, lo, hi))
                 for k, (lo, hi, step) in ranges.items()}
            if not allowed(p):
                study.tell(t, -1e9)
                continue
            c = one(p)
            study.tell(t, c["score"] if c["score"] is not None else -1e9)
            cells.append(c)
            stage(f"cell {i + 1} / {n_max}", 10 + 80 * (i + 1) / n_max, *_partial(cells, names, i))
    else:
        todo = [p for p in (_grid(ranges, n_max * 2 if link else n_max) if method == "grid" else _random(ranges, n_max * 2 if link else n_max, settings.seed, logs)) if allowed(p)][:n_max]
        for i, p in enumerate(todo):
            if cancelled() or out_of_time():
                break
            cells.append(one(p))
            stage(f"cell {i + 1} / {len(todo)}", 10 + 80 * (i + 1) / len(todo), *_partial(cells, names, i))
    if not cells:
        raise Refusal("No cell finished.", ["the run was cancelled before the first cell", "the link rule rejects every setting"])

    stage("report", 92)
    plat = plateau(cells, names, ranges)
    stab = stability(cells, names, ranges, plat.get("centre") or {}, radius)
    # Spread: equity of the plateau region's cells (up to 12), best bold
    region = plat.get("region") or {}
    in_region = [c for c in cells if c["score"] is not None and region and all(region[n][0] - 1e-9 <= c[n] <= region[n][1] + 1e-9 for n in names)]
    in_region = sorted(in_region, key=lambda c: -c["score"])[:12]
    step = max(1, len(dates) // 400)
    idx = sorted(set(range(0, len(dates), step)) | {len(dates) - 1})
    spread = [{"date": str(dates[i].date()), **{f"c{j}": float(c["_equity"][i]) for j, c in enumerate(in_region)}} for i in idx]
    spread_labels = [", ".join(f"{n} {c[n]:g}" for n in names) for c in in_region]
    rets = [c["_returns"] for c in cells]
    eff = store_effective(rets)
    trials = [{"returns": c.pop("_returns"), "sharpe": c["sharpe"], "hash": hashlib.sha256(f"{spec.hash()}:{settings.hash()}:{sorted((k, v) for k, v in c.items() if k != '_equity')}".encode()).hexdigest()[:16]} for c in cells]
    for i, c in enumerate(cells):
        c["trial"] = i + 1
        c.pop("_open", None)
        c.pop("_equity", None)
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
        "charts": {"heatmap": heat, "spread": spread},
        "tables": {"cells": ranked, "top_sets": ranked[:20], "stability": [{"score": v} for v in (stab or {}).get("scores", [])], "importance": importance(cells, names), "pareto": pareto(cells)},
        "meta": {"headline": headline, "plateau": plat, "parameters": names, "ranges": {k: list(v) for k, v in ranges.items()}, "objective": objective, "objective_label": label,
                 "method": method, "cells": len(cells), "stability": {k: v for k, v in (stab or {}).items() if k != "scores"} or None, "spread_labels": spread_labels,
                 "trial_cost": {"raw": len(cells), "effective": eff}, "excluded": {k: sum(c.get("excluded") == k for c in cells) for k in ("too few trades", "drawdown over limit")},
                 "stopped_early": len(cells) < n_max and out_of_time(), "custom": custom if objective == "custom" else None, "link": link or None, "total_return": best["total_return"], "metrics": {"sharpe": best["sharpe"], "trades": best["trades"]},
                 "run_hash": run_hash, "result_hash": hashlib.sha256(str([c["score"] for c in cells]).encode()).hexdigest()[:16], "period": [str(dates[0].date()), str(dates[-1].date())],
                 "spec": spec.model_dump(), "settings": settings.model_dump(), "freshness": limits.freshness(), "verdict_chip": "not validated"},
        "_trials": trials,
    }
