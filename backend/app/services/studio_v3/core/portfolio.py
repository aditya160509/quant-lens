"""st04 Portfolio: combine saved strategies, compare allocation methods, and switch between two by a market rule (meta strategy, P-2)."""

from __future__ import annotations

import hashlib
import itertools
from math import sqrt

import numpy as np
import pandas as pd

from app.services.shared import metrics as M

from . import compile as C
from . import formula, limits, store
from .backtest import Refusal, prepare, simulate
from .spec import Settings, Strategy

METHODS = ("equal", "inverse_vol", "min_variance", "risk_parity", "hrp", "max_sharpe", "max_diversification")
MAX_MEMBERS = 12


def _cap(w: np.ndarray, cap: float | None) -> np.ndarray:
    """Cap each weight and hand the excess to the uncapped members in proportion (repeat until none exceed)."""
    if not cap or cap * len(w) < 1:
        return w
    w = w / w.sum()
    for _ in range(len(w)):
        over = w > cap + 1e-12
        if not over.any():
            break
        free = ~over & (w < cap)
        excess = (w[over] - cap).sum()
        w[over] = cap
        w[free] += excess * w[free] / w[free].sum() if w[free].sum() > 0 else excess / max(free.sum(), 1)
    return w


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
    elif method == "max_diversification":  # Choueifaty: maximise weighted vol / portfolio vol, long-only
        cov = r.cov().to_numpy() + np.eye(n) * 1e-10
        w = np.clip(np.linalg.solve(cov, np.sqrt(np.diag(cov))), 0, None)
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
                  rebalance: str = "in_sample", fixed: dict | None = None, rotate_top: int = 0, max_weight: float | None = None) -> dict:
    """members: (strategy id, version, spec). With `switch`, the first member is held while the rule is true and `switch_off` (an id among members) otherwise."""
    stage = progress or (lambda *_: None)
    if len(members) < (1 if switch else 2):
        raise Refusal("Add two strategies.", ["pick at least two saved strategies"])
    if len(members) > MAX_MEMBERS:
        raise Refusal(f"At most {MAX_MEMBERS} strategies.", ["remove some"])
    stage("load", 5)
    prep = prepare(settings)
    dates, cap = prep.panel.dates, settings.capital
    curves, failed, results, cost2 = {}, [], {}, {}
    for i, (sid, ver, spec) in enumerate(members):
        stage(f"{spec.name}", 10 + 60 * i / len(members))
        try:
            if not C.compile_spec(spec)["ok"]:
                raise Refusal("does not compile", [])
            res = simulate(spec, prep, settings)
            curves[f"{spec.name} v{ver}"] = (sid, res.equity)
            results[f"{spec.name} v{ver}"] = res
            cost2[f"{spec.name} v{ver}"] = simulate(spec, prep, settings, cost_multiple=2.0).equity
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
    if max_weight:
        by_method = {m: (_cap(wm.copy(), max_weight), None) for m, (wm, _) in by_method.items()}
        by_method = {m: (wm, cap * np.cumprod(1 + rets.to_numpy() @ wm)) for m, (wm, _) in by_method.items()}
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
    extra = analytics(rets, w, combined, dates, cap, prep.benchmark, results, cost2, names, method, switch, len(by_method))
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
                   "marginal": marginal, "overlap": overlap, "failed": failed, **extra["tables"]},
        "meta": {"headline": head, "grade": extra["grade"], "tiles": extra["tiles"], "warnings": extra["warnings"], "stats": extra["stats"], "frontier": extra["frontier"], "method": "rotate" if rotate_top else method, "rebalance": rebalance, "tree": tree, "names": names, "switch": switch_info, "total_return": float(combined[-1] / cap - 1), "metrics": {"sharpe": sh, "trades": None},
                 "run_hash": hashlib.sha256(f"st04:{[m[0] for m in members]}:{[m[2].hash() for m in members]}:{settings.hash()}:{method}:{switch}:{switch_off}:{rebalance}:{fixed}:{rotate_top}:{max_weight}".encode()).hexdigest()[:16],
                 "result_hash": hashlib.sha256(np.round(combined, 6).tobytes()).hexdigest()[:16], "freshness": limits.freshness(), "verdict_chip": f"grade {extra['grade']['grade']}",
                 "weights_note": None if rebalance == "quarterly" or rotate_top else "weights use the whole development period (in-sample)",
                 "period": [str(dates[0].date()), str(dates[-1].date())], "settings": settings.model_dump()},
    }


def members_from(ids: list[str]) -> list[tuple[str, int, Strategy]]:
    out = []
    for sid in ids:
        s = store.get(sid)
        out.append((sid, s["version"], Strategy(**s["spec"])))
    return out


def _dd_series(eq: np.ndarray) -> np.ndarray:
    return eq / np.maximum.accumulate(eq) - 1


def frontier(rets: pd.DataFrame, points: int = 25, samples: int = 4000, seed: int = 7) -> list[dict]:
    """Long-only efficient frontier from random weights (Dirichlet): the best Sharpe-free return per volatility bucket, annualised."""
    mu, cov = rets.mean().to_numpy() * 252, rets.cov().to_numpy() * 252
    W = np.random.default_rng(seed).dirichlet(np.ones(rets.shape[1]), samples)
    vol = np.sqrt(np.einsum("ij,jk,ik->i", W, cov, W))
    ret = W @ mu
    edges = np.linspace(vol.min(), vol.max(), points + 1)
    out = []
    for a, b in itertools.pairwise(edges):
        m = (vol >= a) & (vol <= b)
        if m.any():
            i = np.flatnonzero(m)[np.argmax(ret[m])]
            out.append({"vol": float(vol[i]), "ret": float(ret[i])})
    return out


def analytics(rets: pd.DataFrame, w: np.ndarray, combined: np.ndarray, dates: pd.DatetimeIndex, cap: float, bench: np.ndarray | None, results: dict, cost2: dict,
              names: list[str], method: str, switch: str, trials: int) -> dict:
    """Portfolio risk, stress and the combined grade (P-3, P-8..P-21). Every series is the combined daily return at the chosen weights."""
    from .validate import _tile, grade

    r = rets.to_numpy()
    cov = rets.cov().to_numpy()
    port_vol = float(np.sqrt(w @ cov @ w)) if len(w) == r.shape[1] else float("nan")
    stats: dict = {}
    stats["effective_bets"] = float(1 / np.sum(w**2)) if w.sum() > 0 else None
    stats["diversification_ratio"] = float((w @ np.sqrt(np.diag(cov))) / port_vol) if port_vol > 0 else None
    rc = w * (cov @ w)
    risk = [{"strategy": n, "weight": float(w[i]), "risk_share": float(rc[i] / rc.sum()) if rc.sum() > 0 else None} for i, n in enumerate(names)]
    # drawdown overlap: share of days both members are in a drawdown deeper than 5%
    dd = {n: _dd_series(np.cumprod(1 + rets[n].to_numpy())) < -0.05 for n in names}
    dd_overlap = [{"a": a, "b": b, "both_in_drawdown": float((dd[a] & dd[b]).mean())} for i, a in enumerate(names) for b in names[i + 1:]]
    # rolling 126-day correlation, averaged across pairs
    roll = rets.rolling(126).corr()
    pair_mean = []
    if len(names) > 1:
        iu = np.triu_indices(len(names), 1)
        step = max(1, len(dates) // 400)
        for t in range(126, len(dates), step):
            m = roll.loc[dates[t]].to_numpy()[iu]
            if not np.isfinite(m).any():
                continue
            pair_mean.append({"date": str(dates[t].date()), "avg_corr": float(np.nanmean(m))})
    # turnover and netting from member positions (P-9, P-17): notional each member trades vs the netted book
    gross_traded = sum(float(results[n].traded.sum()) * w[i] for i, n in enumerate(names) if n in results)
    pos = [results[n].positions * w[i] for i, n in enumerate(names) if n in results and results[n].positions.shape == results[names[0]].positions.shape]
    netting = None
    if len(pos) == len(names) and gross_traded > 0:
        per = sum(np.abs(np.diff(p, axis=0)).sum() for p in pos)
        net = np.abs(np.diff(sum(pos), axis=0)).sum()
        netting = {"traded_separately": float(per), "traded_netted": float(net), "saved": float(1 - net / per) if per > 0 else 0.0}
    stats["netting_saves"] = netting["saved"] if netting else None
    # benchmark-relative (P-21)
    if bench is not None and len(bench) == len(combined):
        bm = M.benchmark_metrics(combined, bench)
        stats.update({k: bm.get(k) for k in ("alpha", "beta", "tracking_error", "information_ratio", "correlation")})
    # stress (P-13 correlation shock, P-14 crisis windows from 2015)
    vols = np.sqrt(np.diag(cov))
    shock = np.full_like(cov, 0.8) * np.outer(vols, vols)
    np.fill_diagonal(shock, vols**2)
    stats["vol"] = port_vol * np.sqrt(252) if np.isfinite(port_vol) else None
    stats["vol_at_corr_08"] = float(np.sqrt(w @ shock @ w) * np.sqrt(252))
    from .backtest import CRISES
    crises = []
    cr = pd.Series(np.r_[0.0, combined[1:] / combined[:-1] - 1], index=dates)
    for nm, a, z in CRISES:
        seg = cr[(cr.index >= a) & (cr.index <= z)]
        if len(seg) > 5:
            each = {n: float((1 + rets[n][(rets.index >= a) & (rets.index <= z)]).prod() - 1) for n in names}
            crises.append({"crisis": nm, "from": a, "to": z, "combined_return": float((1 + seg).prod() - 1), "worst_member": min(each, key=each.get), "worst_member_return": min(each.values())})
    # drop-out (P-12): CAGR and drawdown with each member removed
    dropout = []
    if len(names) > 2 and not switch:
        for k, n in enumerate(names):
            keep = [j for j in range(len(names)) if j != k]
            wk = _weights(rets.iloc[:, keep], method if method in METHODS else "equal")
            m = M.return_metrics(cap * np.cumprod(1 + r[:, keep] @ wk), dates)
            dropout.append({"removed": n, "sharpe": m.get("sharpe"), "cagr": m.get("cagr"), "max_drawdown": m.get("max_drawdown")})
    # out-of-sample vs full-sample weights (P-16)
    oos = None
    if len(dates) > 300 and method in METHODS:
        ro, _ = rolling(rets, method)
        oos = {"in_sample_sharpe": M.sharpe(r @ w), "out_of_sample_sharpe": M.sharpe(ro[253:]) if len(ro) > 300 else None}
    # rebalance cost (P-19): daily drift back to target, 10 bps on the notional moved
    drift = (1 + r) * w
    drift = drift / drift.sum(1, keepdims=True)
    reb_turn = float(np.abs(drift - w).sum(1).mean() * 252)
    stats["rebalance_turnover"] = reb_turn
    stats["rebalance_cost"] = reb_turn * 0.001
    # warnings (P-15)
    warnings = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            c = float(rets[a].corr(rets[b]))
            if c > 0.9:
                warnings.append(f"{a} and {b} move together (correlation {c:.2f}): close to one strategy")
            both = float((rets[a].ne(0) & rets[b].ne(0)).mean())
            act = max(float(rets[a].ne(0).mean()), 1e-9)
            if both / act > 0.7 and c > 0.7:
                warnings.append(f"{a} and {b} are both invested on {both / act:.0%} of {a}'s days and correlate {c:.2f}")
    if netting and netting["saved"] > 0.2:
        warnings.append(f"members trade against each other: netting would cut traded notional by {netting['saved']:.0%}")
    # combined grade (P-3): tests that apply to a combined return series
    tiles = []
    dr = cr.to_numpy()[1:]
    psr = M.psr(dr, benchmark_sharpe=0.0)
    e_max = sqrt(2 * np.log(max(trials, 2))) / sqrt(len(dr)) if trials > 1 else 0.0  # expected max daily Sharpe among `trials` methods tried
    dsr = M.psr(dr, benchmark_sharpe=e_max * sqrt(252))
    tiles.append(_tile("dsr", "pass" if (dsr or 0) >= 0.95 else "fail", dsr, "≥ 0.95", f"{(dsr or 0):.0%} chance the Sharpe beats the best of {trials} allocation methods tried by luck"))
    if oos and oos["out_of_sample_sharpe"] is not None:
        ok = oos["out_of_sample_sharpe"] >= 0.5 * (oos["in_sample_sharpe"] or 0) and oos["out_of_sample_sharpe"] > 0
        tiles.append(_tile("walk_forward", "pass" if ok else "fail", oos["out_of_sample_sharpe"], "≥ half the in-sample Sharpe", f"weights set each quarter on the past year give Sharpe {oos['out_of_sample_sharpe']:.2f} vs {oos['in_sample_sharpe']:.2f} in-sample"))
    else:
        tiles.append(_tile("walk_forward", "skipped", reason="needs more than 300 bars and a fitted method"))
    if cost2 and all(n in cost2 for n in names):
        eq2 = cap * np.cumprod(1 + pd.DataFrame({n: pd.Series(cost2[n], index=dates).pct_change().fillna(0.0) for n in names}).to_numpy() @ w)
        s2 = M.return_metrics(eq2, dates).get("sharpe")
        tiles.append(_tile("costs", "pass" if (s2 or 0) > 0.5 else "fail", s2, "Sharpe > 0.5", f"Sharpe {s2 or 0:.2f} with every member's costs doubled"))
    if dropout:
        worst = min(dropout, key=lambda d: d["sharpe"] if d["sharpe"] is not None else 1e9)
        base = M.sharpe(dr)
        ok = (worst["sharpe"] or 0) >= 0.6 * base if base > 0 else False
        tiles.append(_tile("parameters", "pass" if ok else "fail", worst["sharpe"], "≥ 60% of the full Sharpe", f"without {worst['removed']} the Sharpe is {worst['sharpe'] or 0:.2f} vs {base:.2f}: {'no single member carries it' if ok else 'one member carries the result'}"))
        tiles[-1]["name"] = "Drop one member"
    if crises:
        worst_c = min(crises, key=lambda c: c["combined_return"])
        ok = worst_c["combined_return"] > -0.25
        tiles.append(_tile("noise", "pass" if ok else "fail", worst_c["combined_return"], "> −25% in any crisis", f"worst crisis: {worst_c['crisis']} {worst_c['combined_return']:.0%}"))
        tiles[-1]["name"] = "Crisis stress"
    g = grade(tiles, False)
    g["psr"] = psr
    return {"tables": {"risk_share": risk, "drawdown_overlap": dd_overlap, "rolling_correlation": pair_mean, "crises": crises, "dropout": dropout},
            "stats": stats | {"netting": netting, "oos": oos}, "grade": g, "tiles": tiles, "warnings": warnings, "frontier": {"points": frontier(rets), "chosen": {
                "vol": float(np.sqrt(w @ cov @ w) * np.sqrt(252)), "ret": float(rets.mean().to_numpy() @ w * 252)}, "members": [
                {"strategy": n, "vol": float(np.sqrt(cov[i, i] * 252)), "ret": float(rets[n].mean() * 252)} for i, n in enumerate(names)]}}
