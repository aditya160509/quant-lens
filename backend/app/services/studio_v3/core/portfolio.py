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

METHODS = ("equal", "inverse_vol", "min_variance", "risk_parity", "hrp", "max_sharpe")
MAX_MEMBERS = 12


def _weights(r: pd.DataFrame, method: str) -> np.ndarray:
    n = r.shape[1]
    if method == "inverse_vol":
        v = r.std().to_numpy()
        w = np.where(v > 0, 1 / np.where(v > 0, v, 1), 0)
    elif method == "min_variance":
        cov = r.cov().to_numpy() + np.eye(n) * 1e-10
        w = np.linalg.solve(cov, np.ones(n))
        w = np.clip(w, 0, None)  # long-only
    elif method == "risk_parity":  # equal risk contribution, fixed-point iteration
        cov = r.cov().to_numpy() + np.eye(n) * 1e-10
        w = np.ones(n) / n
        for _ in range(500):
            rc = w * (cov @ w)
            w = w * np.sqrt(rc.mean() / np.where(rc > 0, rc, rc.mean() or 1))
            w /= w.sum()
    elif method == "hrp":
        w = _hrp(r)[0]
    elif method == "max_sharpe":
        cov = r.cov().to_numpy() + np.eye(n) * 1e-10
        w = np.clip(np.linalg.solve(cov, r.mean().to_numpy()), 0, None)  # long-only tangency
    else:
        w = np.ones(n)
    return w / w.sum() if w.sum() > 0 else np.ones(n) / n


def _hrp(r: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Hierarchical risk parity (López de Prado 2016): cluster on correlation distance, order by the tree, split risk by inverse variance down the tree."""
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform

    corr, cov = r.corr().fillna(0).to_numpy(), r.cov().to_numpy()
    dist = np.sqrt(np.clip((1 - corr) / 2, 0, None))
    np.fill_diagonal(dist, 0)
    link = linkage(squareform(dist, checks=False), "single")
    order = [int(i) for i in leaves_list(link)]
    w = pd.Series(1.0, index=order)
    stack = [order]
    while stack:
        items = stack.pop()
        if len(items) < 2:
            continue
        a, b = items[: len(items) // 2], items[len(items) // 2:]

        def var(c):
            sub = cov[np.ix_(c, c)]
            iv = 1 / np.where(np.diag(sub) > 0, np.diag(sub), 1)
            iv /= iv.sum()
            return float(iv @ sub @ iv)

        va, vb = var(a), var(b)
        alpha = 1 - va / (va + vb) if va + vb > 0 else 0.5
        w[a] *= alpha
        w[b] *= 1 - alpha
        stack += [a, b]
    return w.sort_index().to_numpy(), link, order


def _fixed(names: list[str], fixed: dict | None) -> np.ndarray | None:
    if not fixed:
        return None
    w = np.array([max(0.0, float(fixed.get(n, fixed.get(n.rsplit(" v", 1)[0], 0)) or 0)) for n in names])
    return w / w.sum() if w.sum() > 0 else None


def rolling(rets: pd.DataFrame, method: str, every: int = 63, lookback: int = 252) -> tuple[np.ndarray, list[dict]]:
    """Out-of-sample weights: re-estimated every `every` bars on the trailing `lookback`, applied from the next bar; equal weight until enough history."""
    T, n = rets.shape
    W = np.full((T, n), 1 / n)
    hist = []
    for t in range(lookback, T, every):
        w = _weights(rets.iloc[t - lookback:t], method)
        W[t + 1:] = w
        hist.append({"date": str(rets.index[min(t + 1, T - 1)].date()), **{c: float(w[i]) for i, c in enumerate(rets.columns)}})
    return (rets.to_numpy() * W).sum(1), hist


def rotate(rets: pd.DataFrame, top: int, every: int = 21, lookback: int = 63) -> tuple[np.ndarray, list[dict]]:
    """Hold the `top` members with the best trailing return, re-ranked every `every` bars, acted on the next bar."""
    T, n = rets.shape
    W = np.zeros((T, n))
    W[:] = 1 / n
    hist = []
    growth = (1 + rets).cumprod().to_numpy()
    for t in range(lookback, T, every):
        trail = growth[t] / growth[t - lookback] - 1
        pick = np.argsort(-trail)[:top]
        w = np.zeros(n)
        w[pick] = 1 / len(pick)
        W[t + 1:] = w
        hist.append({"date": str(rets.index[min(t + 1, T - 1)].date()), **{c: float(w[i]) for i, c in enumerate(rets.columns)}})
    return (rets.to_numpy() * W).sum(1), hist


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


def run_portfolio(members: list[tuple[str, int, Strategy]], settings: Settings, method: str = "equal", switch: str = "", switch_off: str | None = None, progress=None,
                  rebalance: str = "in_sample", fixed: dict | None = None, rotate_top: int = 0) -> dict:
    """members: (strategy id, version, spec). With `switch`, the first member is held while the rule is true and `switch_off` (an id among members) otherwise."""
    stage = progress or (lambda *_: None)
    if len(members) < (1 if switch else 2):
        raise Refusal("Add two strategies.", ["pick at least two saved strategies"])
    if len(members) > MAX_MEMBERS:
        raise Refusal(f"At most {MAX_MEMBERS} strategies.", ["remove some"])
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
    fw = _fixed(names, fixed)
    if fw is not None:
        by_method["fixed"] = (fw, cap * np.cumprod(1 + rets.to_numpy() @ fw))
    w, combined = by_method.get(method, by_method["equal"])
    over_time = []
    if rotate_top:
        r, over_time = rotate(rets, min(rotate_top, len(names)))
        combined = cap * np.cumprod(1 + r)
    elif rebalance == "quarterly" and method in METHODS and len(dates) > 300:
        r, over_time = rolling(rets, method)
        combined = cap * np.cumprod(1 + r)
    tree = None
    if len(names) > 2:
        _, link, order = _hrp(rets)
        tree = {"link": link.tolist(), "order": order}
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
        "tables": {"weights": [{"strategy": n, **{m: float(by_method[m][0][i]) for m in by_method}} for i, n in enumerate(names)], "weights_over_time": over_time,
                   "methods": [{"method": m, **{k: M.return_metrics(eq, dates).get(k) for k in ("sharpe", "cagr", "max_drawdown")}} for m, (_, eq) in by_method.items()],
                   "members": [{"strategy": n, "weight": float(w[i]), **{k: each[n].get(k) for k in ("sharpe", "cagr", "max_drawdown")}} for i, n in enumerate(names)],
                   "correlation": [{"strategy": a, **{b: float(corr.loc[a, b]) for b in names}} for a in names],
                   "marginal": marginal, "overlap": overlap, "failed": failed},
        "meta": {"headline": head, "method": "rotate" if rotate_top else method, "rebalance": rebalance, "tree": tree, "names": names, "switch": switch_info, "total_return": float(combined[-1] / cap - 1), "metrics": {"sharpe": sh, "trades": None},
                 "run_hash": hashlib.sha256(f"st04:{[m[0] for m in members]}:{[m[2].hash() for m in members]}:{settings.hash()}:{method}:{switch}:{switch_off}:{rebalance}:{fixed}:{rotate_top}".encode()).hexdigest()[:16],
                 "result_hash": hashlib.sha256(np.round(combined, 6).tobytes()).hexdigest()[:16], "freshness": limits.freshness(), "verdict_chip": "not validated",
                 "weights_note": None if rebalance == "quarterly" or rotate_top else "weights use the whole development period (in-sample)",
                 "period": [str(dates[0].date()), str(dates[-1].date())], "settings": settings.model_dump()},
    }


def members_from(ids: list[str]) -> list[tuple[str, int, Strategy]]:
    out = []
    for sid in ids:
        s = store.get(sid)
        out.append((sid, s["version"], Strategy(**s["spec"])))
    return out
