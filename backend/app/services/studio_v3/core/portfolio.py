"""st04 Portfolio: combine saved strategies, compare allocation methods, and switch between two by a market rule (meta strategy, P-2)."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from app.services.shared import metrics as M

from . import compile as C
from . import formula, limits, store
from .backtest import Refusal, prepare, simulate
from .spec import Settings, Strategy

METHODS = ("equal", "inverse_vol", "min_variance")


def _weights(r: pd.DataFrame, method: str) -> np.ndarray:
    n = r.shape[1]
    if method == "inverse_vol":
        v = r.std().to_numpy()
        w = np.where(v > 0, 1 / np.where(v > 0, v, 1), 0)
    elif method == "min_variance":
        cov = r.cov().to_numpy() + np.eye(n) * 1e-10
        w = np.linalg.solve(cov, np.ones(n))
        w = np.clip(w, 0, None)  # long-only
    else:
        w = np.ones(n)
    return w / w.sum() if w.sum() > 0 else np.ones(n) / n


def _curve(eq: np.ndarray, dates: pd.DatetimeIndex, key: str) -> list[dict]:
    step = max(1, len(eq) // 1500)
    return [{"date": str(dates[i].date()), key: float(eq[i])} for i in sorted(set(range(0, len(eq), step)) | {len(eq) - 1})]


def switch_series(rule: str, bench_close: np.ndarray, dates: pd.DatetimeIndex) -> np.ndarray:
    """The rule on the benchmark, known at the close, acted on at the next open: shifted one bar (no look-ahead, P-2)."""
    on = formula.evaluate(rule, {f: bench_close[:, None] for f in ("open", "high", "low", "close")} | {"volume": np.zeros((len(bench_close), 1))}, dates)[:, 0]
    on = np.nan_to_num(on.astype(float)) > 0
    out = np.zeros_like(on)
    out[1:] = on[:-1]
    return out


def run_portfolio(members: list[tuple[str, int, Strategy]], settings: Settings, method: str = "equal", switch: str = "", switch_off: str | None = None, progress=None) -> dict:
    """members: (strategy id, version, spec). With `switch`, the first member is held while the rule is true and `switch_off` (an id among members) otherwise."""
    stage = progress or (lambda *_: None)
    if len(members) < (1 if switch else 2):
        raise Refusal("Add two strategies.", ["pick at least two saved strategies"])
    if len(members) > 8:
        raise Refusal("At most 8 strategies.", ["remove some"])
    stage("load", 5)
    prep = prepare(settings)
    dates, cap = prep.panel.dates, settings.capital
    curves, failed = {}, []
    for i, (sid, ver, spec) in enumerate(members):
        stage(f"{spec.name}", 10 + 60 * i / len(members))
        try:
            if not C.compile_spec(spec)["ok"]:
                raise Refusal("does not compile", [])
            curves[f"{spec.name} v{ver}"] = (sid, simulate(spec, prep, settings, magnifier=False).equity)
        except Refusal as e:
            failed.append({"strategy": spec.name, "reason": e.reason})
    if len(curves) < (1 if switch else 2):
        raise Refusal("Fewer than two members ran.", [f"{f['strategy']}: {f['reason']}" for f in failed] or ["no common period"])
    names = list(curves)
    rets = pd.DataFrame({n: pd.Series(eq, index=dates).pct_change().fillna(0.0) for n, (_, eq) in curves.items()})

    stage("combine", 75)
    by_method = {}
    for m in METHODS:
        w = _weights(rets, m)
        by_method[m] = (w, cap * np.cumprod(1 + rets.to_numpy() @ w))
    w, combined = by_method.get(method, by_method["equal"])
    switch_info = None
    if switch:
        if prep.benchmark is None:
            raise Refusal("The switch rule needs a benchmark.", ["set a benchmark symbol"])
        off = next((n for n in names if curves[n][0] == switch_off), names[-1])
        on_name = names[0]
        state = switch_series(switch, prep.benchmark, dates)
        r = np.where(state, rets[on_name].to_numpy(), rets[off].to_numpy() if off != on_name else 0.0)
        combined = cap * np.cumprod(1 + r)
        switch_info = {"rule": switch, "on": on_name, "off": off if off != on_name else "cash", "share_on": float(state.mean()), "switches": int(np.abs(np.diff(state.astype(int))).sum())}

    cm = M.return_metrics(combined, dates)
    each = {n: M.return_metrics(eq, dates) for n, (_, eq) in curves.items()}
    best_single = max(names, key=lambda n: each[n].get("sharpe") or -1e9)
    marginal = []
    if not switch and len(names) > 2:
        for k, n in enumerate(names):
            keep = [j for j in range(len(names)) if j != k]
            wk = _weights(rets.iloc[:, keep], method)
            eq = cap * np.cumprod(1 + rets.iloc[:, keep].to_numpy() @ wk)
            marginal.append({"strategy": n, "sharpe_without": M.return_metrics(eq, dates).get("sharpe"), "sharpe_with": cm.get("sharpe")})
    in_mkt = rets.ne(0)
    overlap = [{"a": a, "b": b, "both_active": float((in_mkt[a] & in_mkt[b]).mean()), "correlation": float(rets[a].corr(rets[b]))} for i, a in enumerate(names) for b in names[i + 1:]]
    corr = rets.corr()
    curve = pd.DataFrame({"date": [str(d.date()) for d in dates], "combined": combined, **{n: eq for n, (_, eq) in curves.items()}})
    step = max(1, len(curve) // 1500)
    sh = cm.get("sharpe")
    dd = cm.get("max_drawdown")
    head = f"{'Switch' if switch else 'Together'}: Sharpe {sh:.2f} vs best single {each[best_single].get('sharpe') or 0:.2f}, drawdown {dd * 100:.0f}% vs {each[best_single]['max_drawdown'] * 100:.0f}%" if sh is not None and dd is not None else "Combined"
    return {
        "feature_id": "st04", "status": "ok",
        "summary_cards": [{"label": "Sharpe", "value": sh}, {"label": "CAGR", "value": cm.get("cagr"), "unit": "%"}, {"label": "Max drawdown", "value": dd, "unit": "%"},
                          {"label": "Members", "value": len(names)}],
        "charts": {"combined": curve.iloc[::step].to_dict("records") + ([curve.iloc[-1].to_dict()] if (len(curve) - 1) % step else [])},
        "tables": {"weights": [{"strategy": n, **{m: float(by_method[m][0][i]) for m in METHODS}} for i, n in enumerate(names)],
                   "methods": [{"method": m, **{k: M.return_metrics(eq, dates).get(k) for k in ("sharpe", "cagr", "max_drawdown")}} for m, (_, eq) in by_method.items()],
                   "members": [{"strategy": n, **{k: each[n].get(k) for k in ("sharpe", "cagr", "max_drawdown")}} for n in names],
                   "correlation": [{"strategy": a, **{b: float(corr.loc[a, b]) for b in names}} for a in names],
                   "marginal": marginal, "overlap": overlap, "failed": failed},
        "meta": {"headline": head, "method": method, "names": names, "switch": switch_info, "total_return": float(combined[-1] / cap - 1), "metrics": {"sharpe": sh, "trades": None},
                 "run_hash": hashlib.sha256(f"st04:{[m[0] for m in members]}:{[m[2].hash() for m in members]}:{settings.hash()}:{method}:{switch}:{switch_off}".encode()).hexdigest()[:16],
                 "result_hash": hashlib.sha256(np.round(combined, 6).tobytes()).hexdigest()[:16], "freshness": limits.freshness(), "verdict_chip": "not validated",
                 "weights_note": "inverse-vol and min-variance weights use the whole development period (in-sample)",
                 "period": [str(dates[0].date()), str(dates[-1].date())], "settings": settings.model_dump()},
    }


def members_from(ids: list[str]) -> list[tuple[str, int, Strategy]]:
    out = []
    for sid in ids:
        s = store.get(sid)
        out.append((sid, s["version"], Strategy(**s["spec"])))
    return out
