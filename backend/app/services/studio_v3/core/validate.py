"""st03 Validate: walk-forward, robustness tiles, luck (DSR, PBO, lottery), sealed hold-out, a server-side grade (PAGES §5).

Every test runs on the development period only, except the hold-out, which is opened on purpose and logged.
"""

from __future__ import annotations

import hashlib
import itertools
import math
from dataclasses import replace

import numpy as np
import pandas as pd

from app.services.research_v2.core.ledger_math import deflated_sharpe_hurdle, haircut_t
from app.services.shared import metrics as M

from . import compile as C
from . import engine, limits, paths, store
from .backtest import FEW_TRADES, Refusal, _simulate_python, prepare, simulate
from .spec import Settings, Strategy

PROFILES = {"quick": {"noise": 20, "mcpt": 20, "random": 300, "windows": 4, "cells": 16},
            "full": {"noise": 100, "mcpt": 200, "random": 1000, "windows": 8, "cells": 49}}
WEIGHTS = {"walk_forward": 3, "vs_random": 2, "noise": 2, "mcpt": 2, "delay": 1, "costs": 2, "parameters": 2, "dsr": 3, "pbo": 2,
           "mc_trades": 1, "skip_trades": 2, "regimes": 2, "sanity": 2, "unseen": 1, "invariants": 3}
NAMES = {"walk_forward": "Walk-forward", "vs_random": "Vs random entries", "noise": "Price noise", "mcpt": "Permutation (MCPT)", "delay": "Delay 1 bar",
         "costs": "Costs 2×", "parameters": "Nearby settings", "dsr": "Deflated Sharpe", "pbo": "Overfitting (PBO)",
         "mc_trades": "Trade Monte Carlo", "skip_trades": "Skipped trades and slippage", "regimes": "Every regime", "sanity": "Look-ahead and one-trade", "unseen": "Unseen symbols", "invariants": "Strategy invariants"}
MAX_SIMS = 100_000
HOLDOUT_AGENT_BUDGET = 3


def _daily(eq: np.ndarray) -> np.ndarray:
    return np.diff(eq) / eq[:-1]


def _sharpe(eq: np.ndarray) -> float:
    s = M.sharpe(_daily(eq)) if len(eq) > 3 else float("nan")
    return float(s) if s is not None and math.isfinite(s) else float("nan")


def _tile(key: str, status: str, value=None, threshold: str = "", finding: str = "", reason: str = "") -> dict:
    return {"test": key, "name": NAMES.get(key, key), "status": status, "value": value, "threshold": threshold, "finding": finding, "reason": reason, "weight": WEIGHTS.get(key, 1)}


def _shift(sig: C.Signals, k: int) -> C.Signals:
    def sh(a):
        if a is None:
            return None
        out = np.zeros_like(a)
        out[k:] = a[:-k]
        return out
    return C.Signals(sh(sig.entries), sh(sig.exits), sig.score, sig.stop_dist, sig.size_vol)


def _cells(spec: Strategy, n: int) -> list[dict[str, float]]:
    ranges = {k: (p.min, p.max, p.step or (1.0 if float(p.value).is_integer() and float(p.min).is_integer() else None))
              for k, p in spec.params.items() if p.min is not None and p.max is not None and p.max > p.min}
    if not ranges:
        return []
    per = max(2, round(n ** (1 / len(ranges))))
    axes = [np.unique([lo + round((v - lo) / st) * st if st else v for v in np.linspace(lo, hi, per)]) for lo, hi, st in ranges.values()]
    return [dict(zip(ranges, (round(float(v), 4) for v in c), strict=True)) for c in itertools.product(*axes)]


def walk_forward(curves: list[tuple[dict, np.ndarray]], dates: pd.DatetimeIndex, windows: int, anchored: bool = False, purge: int = 0, reopt: bool = True,
                 is_mult: int = 1) -> tuple[dict, list[dict], list[dict]]:
    """Optimise on an in-sample window (best Sharpe among the cells), trade the next out-of-sample window with that choice; OOS pieces are stitched.
    Rolling or anchored (in-sample always starts at the first bar); `purge` bars are dropped between in-sample and out-of-sample; without re-optimising the
    first window's choice is kept. In-sample is `is_mult` times the out-of-sample length."""
    n = len(dates) - 1
    oos_len = max(2, n // (windows + is_mult))
    rows, stitched, is_ann, oos_ann = [], [], [], []
    k = None
    for i in range(windows):
        b = (is_mult + i) * oos_len
        c = n if i == windows - 1 else b + oos_len
        a = 0 if anchored else max(0, b - is_mult * oos_len)
        e = max(a + 2, b - purge)
        scores = [_sharpe(eq[a:e + 1]) for _, eq in curves]
        if reopt or k is None:
            k = int(np.nanargmax(scores)) if np.isfinite(scores).any() else 0
        params, eq = curves[k]
        is_r, oos_r = _daily(eq[a:e + 1]), _daily(eq[b:c + 1])
        stitched.append(oos_r)
        ia, oa = float(np.mean(is_r) * 252), float(np.mean(oos_r) * 252)
        is_ann.append(ia)
        oos_ann.append(oa)
        rows.append({"window": i + 1, "is_from": str(dates[a].date()), "is_to": str(dates[b].date()), "oos_from": str(dates[b].date()), "oos_to": str(dates[c].date()),
                     **{f"param_{p}": v for p, v in params.items()}, "is_sharpe": scores[k], "oos_sharpe": _sharpe(eq[b:c + 1]), "oos_return": float(eq[c] / eq[b] - 1)})
    oos = np.concatenate(stitched)
    eq = np.concatenate([[1.0], np.cumprod(1 + oos)])
    step = max(1, len(eq) // 600)
    first = is_mult * oos_len
    curve = [{"date": str(dates[first + i].date()), "oos": float(eq[i])} for i in range(0, len(eq), step) if first + i < len(dates)]
    wfe = float(np.mean(oos_ann) / np.mean(is_ann)) if np.mean(is_ann) > 0 else None
    summary = {"wfe": wfe, "profitable": int(sum(r["oos_return"] > 0 for r in rows)), "windows": len(rows), "oos_sharpe": float(M.sharpe(oos) or 0.0)}
    return summary, rows, curve


def stress(equities: list[np.ndarray], base: np.ndarray, dates: pd.DatetimeIndex, cap: float) -> tuple[list[dict], dict]:
    """Fan of stressed equity curves (5/25/50/75/95th percentile per bar, ~120 points) and how often a stressed run still ends profitable and keeps half the Sharpe."""
    eq = np.vstack(equities) / cap
    idx = sorted(set(np.linspace(0, len(dates) - 1, 120).astype(int)))
    q = np.percentile(eq[:, idx], [5, 25, 50, 75, 95], axis=0)
    fan = [{"date": str(dates[i].date()), "original": float(base[i] / cap), **{k: float(q[j, n]) for j, k in enumerate(("p5", "p25", "p50", "p75", "p95"))}} for n, i in enumerate(idx)]
    sr, b = np.array([_sharpe(e) for e in equities]), _sharpe(base)
    return fan, {"runs": len(equities), "profitable": float((eq[:, -1] > 1).mean()), "half_sharpe": float((sr >= 0.5 * b).mean()) if b > 0 else 0.0}


def vs_random(r: engine.Result, close: np.ndarray, n: int, seed: int) -> dict:
    """Random entries with the strategy's own trade count and holding times: where does the real mean trade return rank?"""
    t = r.trades[r.trades[:, engine.T_REASON] != engine.R_OPEN]
    if len(t) < 10:
        return {"status": "skipped", "reason": "fewer than 10 closed trades"}
    rng = np.random.default_rng(seed)
    hold = np.maximum(1, (t[:, engine.T_EXIT_BAR] - t[:, engine.T_ENTRY_BAR]).astype(int))
    side = np.sign(t[:, engine.T_DIR])
    T, S = close.shape
    means = np.empty(n)
    for i in range(n):
        e = rng.integers(0, T - hold.max() - 1, len(t))
        s = rng.integers(0, S, len(t))
        r0, r1 = close[e, s], close[e + hold, s]
        ok = np.isfinite(r0) & np.isfinite(r1) & (r0 > 0)
        means[i] = np.mean(side[ok] * (r1[ok] / r0[ok] - 1)) if ok.any() else np.nan
    means = means[np.isfinite(means)]
    real = float(np.mean(t[:, engine.T_RET]))
    beat = float((real > means).mean())
    return {"status": "pass" if beat >= 0.95 else "fail", "beats": beat, "real": real, "random_median": float(np.median(means)),
            "hist": np.histogram(means, bins=30)[0].tolist(), "edges": np.histogram(means, bins=30)[1].tolist()}


def _noisy(bars: dict[str, np.ndarray], rng, scale: float) -> dict[str, np.ndarray]:
    c = bars["close"]
    vol = pd.DataFrame(c).pct_change().rolling(20, min_periods=5).std().bfill().to_numpy()
    z = 1 + scale * np.nan_to_num(vol) * rng.standard_normal(c.shape)
    return {k: (v * z if k != "volume" else v) for k, v in bars.items()}


def _permuted(bars: dict[str, np.ndarray], rng) -> dict[str, np.ndarray]:
    """Shuffle each name's daily log returns (open, high, low kept relative to close): same distribution, no order."""
    c = bars["close"]
    lr = np.diff(np.log(c), axis=0)
    out = np.empty_like(c)
    out[0] = c[0]
    for j in range(c.shape[1]):
        col = lr[:, j]
        ok = np.isfinite(col)
        col = col.copy()
        col[ok] = rng.permutation(col[ok])
        out[1:, j] = c[0, j] * np.exp(np.nancumsum(np.where(np.isfinite(col), col, 0.0)))
        out[1:, j][~np.isfinite(c[1:, j])] = np.nan
    ratio = out / c
    return {k: (v * ratio if k != "volume" else v) for k, v in bars.items()}


def trade_mc(pnl: np.ndarray, costs: np.ndarray, cap: float, mode: str, sims: int, seed: int, years: float) -> dict[str, np.ndarray]:
    """Vectorised Monte Carlo over the closed-trade pnl array (no re-simulation): final return, max drawdown (positive share) and trade Sharpe per run.
    Modes: shuffle, resample (with replacement), skip (drop 10% at random), slip (extra 0-2x cost per trade). Chunked to bound memory."""
    n = len(pnl)
    rng = np.random.default_rng([seed, ("shuffle", "resample", "skip", "slip").index(mode)])
    out: dict[str, list] = {"ret": [], "dd": [], "sharpe": []}
    step = max(1, 2_000_000 // n)
    for a in range(0, sims, step):
        b = min(step, sims - a)
        keep = np.ones((b, n))
        if mode == "shuffle":
            x = rng.permuted(np.tile(pnl, (b, 1)), axis=1)
        elif mode == "resample":
            x = pnl[rng.integers(0, n, (b, n))]
        elif mode == "skip":
            keep = (rng.random((b, n)) >= 0.10).astype(float)
            x = pnl * keep
        else:
            x = pnl - rng.uniform(0, 2, (b, n)) * costs
        e = cap + np.cumsum(x, axis=1)
        peak = np.maximum(np.maximum.accumulate(e, axis=1), cap)
        k = np.maximum(keep.sum(1), 1)
        mu = (x.sum(1)) / k
        sd = np.sqrt(np.maximum((keep * (x - mu[:, None]) ** 2).sum(1) / k, 0))
        out["ret"].append(e[:, -1] / cap - 1)
        out["dd"].append(((peak - e) / peak).max(1))
        out["sharpe"].append(np.where(sd > 1e-12, mu / np.where(sd > 1e-12, sd, 1) * np.sqrt(k / max(years, 0.25)), 0.0))
    return {k: np.concatenate(v) for k, v in out.items()}


def regime_tables(daily: np.ndarray, labels: np.ndarray, dates: pd.DatetimeIndex) -> tuple[list[dict], list[dict]]:
    """Strategy performance per benchmark regime (a regime needs 60 bars to be judged) and per calendar year. daily[i] is the return into bar i+1."""
    lab, d = labels[1:], dates[1:]
    reg = []
    for name in sorted(set(lab) - {"warm-up"}):
        r = daily[lab == name]
        reg.append({"regime": name, "days": len(r), "sharpe": float(M.sharpe(r) or 0.0) if len(r) >= 60 else None, "total_return": float(np.prod(1 + r) - 1),
                    "judged": len(r) >= 60})
    years = [{"year": int(y), "days": len(r), "total_return": float(np.prod(1 + r) - 1), "sharpe": float(M.sharpe(r) or 0.0) if len(r) >= 60 else None}
             for y in sorted(set(d.year)) for r in [daily[d.year == y]]]
    return reg, years


def lookahead(spec, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, sig: C.Signals, seed: int, cuts: int = 5) -> list[dict]:
    """Re-run the signals on data cut at random dates: every signal before the cut must equal the full-data signal."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in sorted(int(x) for x in rng.integers(len(dates) // 4, len(dates) - 1, cuts)):
        cut = C.signals(spec, {k: v[:c] for k, v in bars.items()}, dates[:c])
        same = all(a is None and b is None or a is not None and b is not None and np.array_equal(a[:c], b) for a, b in ((sig.entries, cut.entries), (sig.exits, cut.exits)))
        rows.append({"check": f"cut at {dates[c].date()}", "ok": bool(same)})
    return rows


def luck(daily: np.ndarray, years: float, ledger: dict, trial_sharpes: list[float], seed: int) -> dict:
    n_eff = max(1.0, float(ledger.get("effective") or 1.0))
    sr = float(M.sharpe(daily) or 0.0)
    var = float(np.var(trial_sharpes)) if len(trial_sharpes) > 1 else 1.0 / max(years, 0.5)
    hurdle = deflated_sharpe_hurdle(round(n_eff), var) if n_eff >= 2 else 0.0
    dsr = M.psr(daily, benchmark_sharpe=hurdle or 0.0)
    rng = np.random.default_rng(seed)
    noise_best = (rng.standard_normal((2000, max(1, round(n_eff)))) / math.sqrt(max(years, 0.25))).max(axis=1)
    mtr = M.min_track_record(daily)
    hc = haircut_t(sr * math.sqrt(years), max(1, round(n_eff)))
    return {"sharpe": sr, "effective_trials": n_eff, "raw_trials": ledger.get("raw", 1), "hurdle": hurdle, "dsr": dsr, "lottery_p95": float(np.percentile(noise_best, 95)),
            "lottery_hist": np.histogram(noise_best, bins=30)[0].tolist(), "lottery_edges": np.histogram(noise_best, bins=30)[1].tolist(),
            "track_record_years": (mtr / 252) if mtr else None, "haircut": hc["haircut"], "sharpe_after_haircut": sr * (1 - hc["haircut"]) if hc["haircut"] is not None else None}


def pbo_cscv(m: np.ndarray, partitions: int = 8) -> float | None:
    d = pbo_detail(m, partitions)
    return d["pbo"] if d else None


def pbo_detail(m: np.ndarray, partitions: int = 8) -> dict | None:
    """CSCV (Bailey et al. 2015) as in shared.stats, except a setting flat for a whole block (in cash) scores Sharpe 0 there instead of voiding the test."""
    from itertools import combinations

    from scipy import stats as st

    if m.ndim != 2 or m.shape[1] < 8 or m.shape[0] < partitions * 2 or not np.isfinite(m).all():
        return None
    blocks = np.array_split(np.arange(len(m)), partitions)

    def sr(x):
        sd = x.std(0, ddof=1)
        return np.where(sd > 1e-12, x.mean(0) / np.where(sd > 1e-12, sd, 1), 0.0)

    below, logits, pairs = [], [], []
    for train in combinations(range(partitions), partitions // 2):
        tr = np.concatenate([blocks[i] for i in train])
        te = np.concatenate([blocks[i] for i in range(partitions) if i not in train])
        s_tr, s_te = sr(m[tr]), sr(m[te])
        winner = int(np.argmax(s_tr))
        rank = st.rankdata(s_te, method="average")[winner] / (m.shape[1] + 1)
        below.append(rank <= 0.5)
        logits.append(float(np.log(rank / (1 - rank))))
        pairs.append({"is_sharpe": float(s_tr[winner] * math.sqrt(252)), "oos_sharpe": float(s_te[winner] * math.sqrt(252))})
    return {"pbo": float(np.mean(below)), "logits": logits, "pairs": pairs}


def grade(tiles: list[dict], few: bool) -> dict:
    judged = [t for t in tiles if t["status"] in ("pass", "fail")]
    if not judged:
        return {"grade": "—", "score": None, "reason": "no test could run", "cap": None}
    score = sum(t["weight"] for t in judged if t["status"] == "pass") / sum(t["weight"] for t in judged)
    letter = "A" if score >= 0.85 else "B" if score >= 0.7 else "C" if score >= 0.55 else "D" if score >= 0.4 else "F"
    cap = None
    wf = next((t for t in tiles if t["test"] == "walk_forward"), None)
    if few or (wf and wf["status"] == "skipped"):
        cap = "C"
        letter = max(letter, "C")  # letters sort A < F: max() keeps the worse grade
    failed = sorted((t for t in judged if t["status"] == "fail"), key=lambda t: -t["weight"])
    reason = failed[0]["finding"] if failed else "every test that ran passed"
    if any(t["test"] == "invariants" and t["status"] == "fail" for t in judged):
        letter, reason = "F", next(t for t in judged if t["test"] == "invariants")["finding"]
    if any(t["test"] == "dsr" and t["status"] == "fail" for t in judged):
        reason = "luck: " + next(t for t in judged if t["test"] == "dsr")["finding"]
    return {"grade": letter, "score": score, "reason": reason, "cap": cap}


def holdout_looks(sid: str | None) -> list[dict]:
    return store.kv_get(f"holdout:{sid}", []) if sid else []


def open_holdout(sid: str | None, version: int | None, actor: str) -> list[dict]:
    """Log a look before showing anything; agents get three, humans are logged without a limit (V-4, V-5)."""
    if not sid:
        raise Refusal("Save the strategy before opening its hold-out.", ["looks are counted per saved strategy"])
    looks = holdout_looks(sid)
    if actor.startswith("agent") and sum(1 for x in looks if x["actor"].startswith("agent")) >= HOLDOUT_AGENT_BUDGET:
        raise Refusal("Agent hold-out budget spent (3 looks).", ["a human must open it from the Validate page"])
    import time

    looks = [*looks, {"actor": actor, "version": version, "at": time.time()}]
    store.kv_set(f"holdout:{sid}", looks)
    store.log(actor, "open_holdout", sid, {"version": version})
    return looks


def run_validate(spec: Strategy, settings: Settings, sid: str | None = None, version: int | None = None, profile: str = "quick", weights: dict | None = None,
                 show_holdout: bool = False, actor: str = "human", progress=None, anchored: bool = False, purge: int = 5, reopt: bool = True, volume_cap: float = 0.01, sims: int = 1000) -> dict:
    stage = progress or (lambda *_: None)
    sims = max(1, min(int(sims or 1000), MAX_SIMS))
    prof = PROFILES.get(profile, PROFILES["quick"])
    if not C.compile_spec(spec)["ok"]:
        raise Refusal("The strategy does not compile.", ["fix the rule in Build"])
    stage("load", 5)
    prep = prepare(settings)
    p, dates, cap = prep.panel, prep.panel.dates, settings.capital
    sig = C.signals(spec, prep.sig_bars, dates)
    base = simulate(spec, prep, settings, sig=sig)
    closed = base.trades[base.trades[:, engine.T_REASON] != engine.R_OPEN]
    if len(base.trades) == 0:
        raise Refusal("0 trades: nothing to validate.", ["the rule never fires on this universe"])
    years = len(dates) / 252
    base_sr, daily = _sharpe(base.equity), _daily(base.equity)
    few = len(closed) < FEW_TRADES
    tiles: list[dict] = []
    tables: dict[str, list] = {}
    charts: dict[str, list] = {}

    if "assert_invariant" in spec.code:  # B-39: a violated invariant fails the step whatever the other tests say
        found: dict = {}
        _simulate_python(spec, prep, settings, output=found)
        broken = found.get("invariants")
        tiles.append(_tile("invariants", "fail" if broken else "pass", broken["count"] if broken else 0, "no violation",
                           f"{broken['count']} violations, first on {broken['rows'][0]['date']} line {broken['rows'][0]['line']}: {broken['rows'][0]['text']}" if broken else "every assert_invariant held"))
        if broken:
            tables["invariants"] = broken["rows"]

    stage("walk-forward", 15)
    cells = _cells(spec, prof["cells"])
    curves = [(c, simulate(spec, prep, settings, params=c).equity) for c in cells] if cells else [({}, base.equity)]
    if few:
        tiles.append(_tile("walk_forward", "skipped", reason=f"{len(closed)} closed trades; needs {FEW_TRADES}"))
        wf = None
    else:
        wf, rows, curve = walk_forward(curves, dates, prof["windows"], anchored, purge, reopt)
        tables["windows"], charts["walk_forward"] = rows, curve
        if len(curves) > 1:
            tables["wf_matrix"] = wf_matrix(curves, dates, anchored, purge, reopt)
        ok = wf["wfe"] is not None and wf["wfe"] >= 0.5 and wf["oos_sharpe"] > 0
        tiles.append(_tile("walk_forward", "pass" if ok else "fail", wf["wfe"], "efficiency ≥ 50% and out-of-sample Sharpe > 0",
                           f"walk-forward efficiency {wf['wfe'] * 100:.0f}%, {wf['profitable']} of {wf['windows']} windows profitable" if wf["wfe"] is not None
                           else f"in-sample windows lost money; {wf['profitable']} of {wf['windows']} out-of-sample windows profitable"))

    stage("vs random", 30)
    vr = vs_random(base, p.close, prof["random"], settings.seed)
    if vr["status"] == "skipped":
        tiles.append(_tile("vs_random", "skipped", reason=vr["reason"]))
    else:
        tiles.append(_tile("vs_random", vr["status"], vr["beats"], "beats 95%", f"beats {vr['beats'] * 100:.0f}% of {prof['random']} random-entry sets with the same trades and holding times"))
        charts["vs_random"] = [{"bin": (a + b) / 2, "count": c} for a, b, c in zip(vr["edges"][:-1], vr["edges"][1:], vr["hist"], strict=True)]
        tables["vs_random"] = [{"real_mean_trade": vr["real"], "random_median": vr["random_median"], "beats": vr["beats"]}]

    stage("noise", 40)
    rng = np.random.default_rng(settings.seed)
    noise_sr = [_sharpe(simulate(spec, prep, settings, sig=C.signals(spec, _noisy(prep.sig_bars, rng, 0.25), dates)).equity) for _ in range(prof["noise"])]
    med = float(np.nanmedian(noise_sr))
    tiles.append(_tile("noise", "pass" if base_sr > 0 and med >= 0.5 * base_sr else "fail", med, "median Sharpe ≥ half the original",
                       f"with price noise the median Sharpe is {med:.2f} (original {base_sr:.2f})"))
    tables["noise"] = [{"run": i + 1, "sharpe": s} for i, s in enumerate(noise_sr)]

    stage("stress", 50)
    jit = [(k, d) for k, d in spec.parameter_definitions().items() if d.min is not None and d.max is not None and d.max > d.min]
    stressed = []
    for _ in range(prof["noise"]):
        pj = {k: float(np.clip(d.value * (1 + rng.uniform(-0.1, 0.1)), d.min, d.max)) for k, d in jit}
        pj = {k: float(round(v)) if dict(jit)[k].value.is_integer() else v for k, v in pj.items()}
        stressed.append(simulate(spec, prep, settings, sig=C.signals(spec, _noisy(prep.sig_bars, rng, 0.1), dates, pj or None), cost_multiple=float(rng.uniform(1.0, 2.0))).equity)
    charts["stress"], stress_meta = stress(stressed, base.equity, dates, cap)

    stage("permutation", 55)
    perm_sr = [_sharpe(simulate(spec, replace(prep, sig_bars=(pb := _permuted(prep.sig_bars, rng)), panel=_panel_from(p, pb)), settings).equity)
               for _ in range(prof["mcpt"])]
    pval = float((np.array(perm_sr) >= base_sr).mean()) if perm_sr else 1.0
    tiles.append(_tile("mcpt", "pass" if pval <= 0.05 else "fail", pval, "p ≤ 0.05", f"{pval * 100:.0f}% of {len(perm_sr)} shuffled-return markets did as well (p = {pval:.2f})"))
    tables["mcpt"] = [{"run": i + 1, "sharpe": s} for i, s in enumerate(perm_sr)]

    stage("execution", 70)
    d1 = _sharpe(simulate(spec, prep, settings, sig=_shift(sig, 1)).equity)
    d2 = _sharpe(simulate(spec, prep, settings, sig=_shift(sig, 2)).equity)
    d5 = _sharpe(simulate(spec, prep, settings, sig=_shift(sig, 5)).equity)
    tiles.append(_tile("delay", "pass" if base_sr > 0 and d1 >= 0.5 * base_sr else "fail", d1, "Sharpe ≥ half the original",
                       f"one bar late: Sharpe {d1:.2f}; two bars: {d2:.2f}; five bars: {d5:.2f}"))
    ladder = []
    for m in (1, 1.5, 2, 2.5, 3, 5, 8):
        eq = base.equity if m == 1 else simulate(spec, prep, settings, sig=sig, cost_multiple=m).equity
        ladder.append({"multiple": m, "total_return": float(eq[-1] / cap - 1), "sharpe": _sharpe(eq)})
    cross = next((i for i, x in enumerate(ladder) if x["total_return"] <= 0), None)
    breakeven = None if cross is None else ladder[0]["multiple"] if cross == 0 else round(
        ladder[cross - 1]["multiple"] + (ladder[cross]["multiple"] - ladder[cross - 1]["multiple"]) * ladder[cross - 1]["total_return"]
        / (ladder[cross - 1]["total_return"] - ladder[cross]["total_return"]), 1)  # linear between the two sweep points around zero
    tables["cost_sweep"] = [{**x, "break_even": breakeven} for x in ladder]
    c2 = next(x["total_return"] for x in ladder if x["multiple"] == 2)
    tiles.append(_tile("costs", "pass" if c2 > 0 else "fail", c2, "profitable at 2× costs",
                       f"profitable at 2× costs; break-even beyond {ladder[-1]['multiple']}×" if c2 > 0 and breakeven is None else
                       f"costs break it at {breakeven}×" if breakeven else "loses money at 2× costs"))
    capped = settings.model_copy(update={"costs": settings.costs.model_copy(update={"volume_cap": volume_cap})})
    vc = _sharpe(simulate(spec, prep, capped, sig=sig).equity)
    stage("shocks", 74)
    tables["shocks"] = shocks(spec, prep, settings, base)
    tables["shifted"] = shifted_starts(spec, prep, settings)
    stage("other names", 77)
    rel = related(spec, settings)
    tables["related"] = [rel] if rel["status"] == "ok" else []
    tables["execution"] = [{"case": "original", "sharpe": base_sr}, {"case": "delay 1 bar", "sharpe": d1}, {"case": "delay 2 bars", "sharpe": d2}, {"case": "delay 5 bars", "sharpe": d5},
                           {"case": f"volume cap {volume_cap * 100:g}% of the day", "sharpe": vc},
                           *({"case": f"costs {x['multiple']}×", "sharpe": x["sharpe"], "total_return": x["total_return"]} for x in ladder if x["multiple"] > 1)]

    stage("monte carlo", 78)
    pnl, tcost = closed[:, engine.T_PNL], closed[:, engine.T_COSTS]
    q = lambda a, pc: float(np.percentile(a, pc))
    if len(closed) < 10:
        for k in ("mc_trades", "skip_trades"):
            tiles.append(_tile(k, "skipped", reason=f"{len(closed)} closed trades; needs 10"))
    else:
        mc = {m: trade_mc(pnl, tcost, cap, m, sims, settings.seed, years) for m in ("shuffle", "resample", "skip", "slip")}
        tables["mc_trades"] = [{"method": {"shuffle": "reshuffle", "resample": "resample", "skip": "random skip 10%"}[m], "confidence": c, "max_drawdown": q(mc[m]["dd"], c),
                                "final_return": q(mc[m]["ret"], 100 - c)} for m in ("shuffle", "resample", "skip") for c in (80, 90, 95, 99)]
        rs5 = q(mc["resample"]["ret"], 5)
        tiles.append(_tile("mc_trades", "pass" if rs5 > 0 else "fail", rs5, "5th-percentile final return > 0 when trades are resampled",
                           f"resampling the {len(closed)} trades {sims:,} times, 95% of runs end above {rs5 * 100:.1f}%; worst-case drawdown at 95%: {q(mc['resample']['dd'], 95) * 100:.0f}%"))
        tables["skip_trades"] = [{"case": c, "p5_sharpe": q(mc[m]["sharpe"], 5), "median_sharpe": q(mc[m]["sharpe"], 50), "p5_return": q(mc[m]["ret"], 5), "median_return": q(mc[m]["ret"], 50)}
                                 for c, m in (("skip 10% of trades", "skip"), ("slippage + 0 to 2× cost per trade", "slip"))]
        sk5, sl5 = q(mc["skip"]["sharpe"], 5), q(mc["slip"]["sharpe"], 5)
        tiles.append(_tile("skip_trades", "pass" if sk5 > 0 and sl5 > 0 else "fail", min(sk5, sl5), "5th-percentile Sharpe > 0 with 10% of trades skipped and with random extra slippage",
                           f"skipping 10% at random: 5th-percentile Sharpe {sk5:.2f}; random extra slippage: {sl5:.2f}"))

    stage("regimes", 79)
    if prep.benchmark is None:
        tiles.append(_tile("regimes", "skipped", reason="needs a benchmark"))
    else:
        reg, yrs = regime_tables(daily, paths.regimes(pd.Series(prep.benchmark).bfill().to_numpy(), dates), dates)  # bfill only touches the 200-bar warm-up
        tables["regimes"], tables["years"] = reg, yrs
        judged_r = [r for r in reg if r["judged"]]
        if not judged_r:
            tiles.append(_tile("regimes", "skipped", reason="no regime lasts 60 bars"))
        else:
            worst = min(judged_r, key=lambda r: r["sharpe"])
            tiles.append(_tile("regimes", "pass" if worst["sharpe"] > 0 else "fail", worst["sharpe"], "Sharpe > 0 in every regime of 60+ bars",
                               f"worst regime: {worst['regime']} (Sharpe {worst['sharpe']:.2f}, {worst['days']} bars); {sum(r['sharpe'] > 0 for r in judged_r)} of {len(judged_r)} regimes positive"))

    stage("sanity", 79)
    look = lookahead(spec, prep.sig_bars, dates, sig, settings.seed)
    bad = sum(not r["ok"] for r in look)
    rows_s = list(look)
    best_ret = None
    if len(closed) >= 2:
        rest = np.delete(pnl, int(np.argmax(pnl)))
        best_ret = float(rest.sum() / cap)
        sd = rest.std()
        rows_s.append({"check": "best trade removed", "ok": best_ret > 0, "total_return": best_ret, "sharpe": float(rest.mean() / sd * math.sqrt(len(rest) / max(years, 0.25))) if sd > 1e-12 else 0.0})
    tables["sanity"] = rows_s
    one = best_ret is not None and best_ret <= 0
    tiles.append(_tile("sanity", "fail" if bad or one else "pass", bad if bad or best_ret is None else best_ret, "signals identical on truncated data; profitable without the best trade",
                       f"signals changed before {bad} of {len(look)} cut dates: look-ahead" if bad else
                       "without the best trade the strategy loses money" if one else
                       f"signals identical at {len(look)} cut dates" + (f"; without the best trade the return is {best_ret * 100:.1f}%" if best_ret is not None else "")))

    stage("unseen symbols", 79)
    ns = len(p.symbols)
    if ns < 10:
        tiles.append(_tile("unseen", "skipped", reason=f"{ns} symbols; needs 10"))
    else:
        order = np.random.default_rng(settings.seed).permutation(ns)
        halves = []
        for j, idx in enumerate((order[:ns // 2], order[ns // 2:])):
            mask = np.zeros(ns, bool)
            mask[idx] = True
            eq = simulate(spec, prep, settings, sig=sig, mask=mask).equity
            halves.append({"half": "AB"[j], "names": int(mask.sum()), "sharpe": _sharpe(eq), "total_return": float(eq[-1] / cap - 1)})
        tables["unseen"] = halves
        sh = [h["sharpe"] if math.isfinite(h["sharpe"]) else 0.0 for h in halves]
        ok = min(sh) > 0 and min(sh) >= 0.5 * max(sh)
        tiles.append(_tile("unseen", "pass" if ok else "fail", min(sh), "weaker half Sharpe > 0 and ≥ 50% of the stronger",
                           f"two halves of the universe: Sharpe {sh[0]:.2f} and {sh[1]:.2f}"))

    stage("parameters", 80)
    if len(curves) > 1:
        rets = [float(eq[-1] / cap - 1) for _, eq in curves]
        share = float(np.mean([x > 0 for x in rets]))
        tiles.append(_tile("parameters", "pass" if share >= 0.7 else "fail", share, "≥ 70% of nearby settings profitable", f"{share * 100:.0f}% of {len(rets)} settings across the ranges are profitable"))
        tables["parameters"] = [{**c, "total_return": float(eq[-1] / cap - 1), "sharpe": _sharpe(eq)} for c, eq in curves]
    else:
        tiles.append(_tile("parameters", "skipped", reason="no parameter has a range"))

    stage("luck", 88)
    led = store.ledger(sid) if sid else {"raw": 1, "effective": 1.0, "trials": []}
    lk = luck(daily, years, led, [t["sharpe"] for t in led.get("trials", []) if t.get("sharpe") is not None], settings.seed)
    dsr = lk["dsr"]
    tiles.append(_tile("dsr", "skipped" if dsr is None else "pass" if dsr >= 0.95 else "fail", dsr, "≥ 0.95",
                       f"after {lk['raw_trials']:,} tries ({lk['effective_trials']:.0f} effective), noise alone reaches Sharpe {lk['lottery_p95']:.1f}; yours is {lk['sharpe']:.1f}",
                       reason="returns too short or flat" if dsr is None else ""))
    pbo = None
    if len(curves) >= 8:
        m = np.array([_daily(eq) for _, eq in curves]).T
        det = pbo_detail(m)
        if det:
            pbo = det["pbo"]
            tables["pbo_pairs"] = det["pairs"]
            charts["pbo_logits"] = [{"logit": v} for v in det["logits"]]
    cp = cpcv(curves, dates)
    if cp:
        tables["cpcv"] = [{"path": j + 1, "sharpe": s} for j, s in enumerate(cp["sharpes"])]
        charts["cpcv_paths"] = cp.pop("curve")
    hurdle_sr = 1.645 / math.sqrt(max(years, 0.25))
    pw = power(len(dates), len(closed), float(np.mean(np.array(perm_sr) >= hurdle_sr)) if perm_sr else None)
    tiles.append(_tile("pbo", "skipped" if pbo is None else "pass" if pbo <= 0.5 else "fail", pbo, "≤ 50%",
                       f"probability the best in-sample setting underperforms out of sample: {pbo * 100:.0f}%" if pbo is not None else "", reason="needs 8 or more parameter settings" if pbo is None else ""))
    charts["lottery"] = [{"bin": (a + b) / 2, "count": c} for a, b, c in zip(lk["lottery_edges"][:-1], lk["lottery_edges"][1:], lk["lottery_hist"], strict=True)]

    if weights:
        for t in tiles:
            t["weight"] = float(weights.get(t["test"], t["weight"]))
    g = grade(tiles, few)

    stage("hold-out", 94)
    looks = holdout_looks(sid)
    hold = {"status": "sealed", "from": prep.holdout_from, "looks": looks}
    if show_holdout and prep.holdout_from:
        looks = open_holdout(sid, version, actor)
        full = prepare(settings, include_holdout=True)
        eq = simulate(spec, full, settings).equity
        cut = int(full.panel.dates.searchsorted(pd.Timestamp(prep.holdout_from)))
        hold = {"status": "open", "from": prep.holdout_from, "looks": looks, "sharpe": _sharpe(eq[cut:]), "dev_sharpe": base_sr, "return": float(eq[-1] / eq[cut] - 1)}

    nxt = next((t for t in tiles if t["status"] == "skipped"), None)
    change = []
    if few:
        change.append(f"needs {FEW_TRADES - len(closed)} more closed trades")
    if breakeven:
        change.append(f"costs break it at {breakeven}×")
    if lk["track_record_years"]:
        change.append(f"needs {lk['track_record_years']:.1f} years of record for 95% confidence the Sharpe is above 0")
    tile_hash = hashlib.sha256(repr([(t["test"], t["status"], None if t["value"] is None else round(float(t["value"]), 6)) for t in tiles]).encode()).hexdigest()[:16]
    run_hash = hashlib.sha256(f"st03:{spec.hash()}:{settings.hash()}:{profile}:{sims}".encode()).hexdigest()[:16]
    passed = sum(t["status"] == "pass" for t in tiles)
    judged = sum(t["status"] in ("pass", "fail") for t in tiles)
    headline = f"{g['grade']}: {g['reason']}"
    return {
        "feature_id": "st03", "status": "ok",
        "summary_cards": [{"label": "Grade", "value": g["grade"]}, {"label": "Tests passed", "value": f"{passed} of {judged}"}, {"label": "Deflated Sharpe", "value": dsr},
                          {"label": "Effective trials", "value": lk["effective_trials"], "unit": "trials"}],
        "charts": charts,
        "tables": {"tiles": tiles, "verdict": [{"test": t["name"], "weight": t["weight"], "result": t["status"], "value": t["value"], "threshold": t["threshold"]} for t in tiles],
                   "luck": [{"measure": k, "value": v} for k, v in lk.items() if not isinstance(v, list)], **tables},
        "meta": {"headline": headline, "grade": g, "tiles": tiles, "luck": {k: v for k, v in lk.items() if not isinstance(v, list)}, "holdout": hold,
                 "power": pw, "cpcv": cp, "related": rel, "walk_forward_mode": {"anchored": anchored, "purge": purge, "reopt": reopt},
                 "next_test": f"Run: {nxt['name']} ({nxt['reason']})" if nxt else None, "what_would_change": change, "walk_forward": wf, "stress": stress_meta, "profile": profile, "sims": sims, "seed": settings.seed, "cost_breakeven": breakeven,
                 "total_return": float(base.equity[-1] / cap - 1), "metrics": {"sharpe": base_sr, "trades": len(base.trades)},
                 "run_hash": run_hash, "result_hash": tile_hash, "verdict_chip": f"Grade {g['grade']}", "freshness": limits.freshness(),
                 "period": [str(dates[0].date()), str(dates[-1].date())], "spec": spec.model_dump(), "settings": settings.model_dump(), "few_trades": few},
    }


def _panel_from(p, bars: dict[str, np.ndarray]):
    from . import data

    return data.Panel(p.dates, p.symbols, *(bars[f] if f in bars else getattr(p, f) for f in data.FIELDS))


def wf_matrix(curves, dates, anchored: bool, purge: int, reopt: bool) -> list[dict]:
    """Walk-forward across window counts × in-sample lengths: which combinations pass (efficiency ≥ 50% and OOS Sharpe > 0)."""
    out = []
    for w in (3, 4, 5, 6, 8):
        for mult in (1, 2, 3, 4, 5):
            if len(dates) // (w + mult) < 40:
                out.append({"windows": w, "in_sample_x": mult, "pass": None, "wfe": None})
                continue
            s, _, _ = walk_forward(curves, dates, w, anchored, purge, reopt, mult)
            out.append({"windows": w, "in_sample_x": mult, "wfe": s["wfe"], "oos_sharpe": s["oos_sharpe"], "pass": bool(s["wfe"] is not None and s["wfe"] >= 0.5 and s["oos_sharpe"] > 0)})
    return out


def cpcv(curves, dates, groups: int = 6, test: int = 2, purge: int = 5) -> dict | None:
    """Combinatorial purged cross-validation (López de Prado): choose the best cell on the training groups (purged next to each test group),
    keep its test-group returns, and stitch the splits into paths. Returns the out-of-sample Sharpe of each path."""
    from itertools import combinations

    if len(curves) < 2 or len(dates) < groups * 40:
        return None
    rets = np.array([_daily(eq) for _, eq in curves])  # cells × days
    bounds = np.array_split(np.arange(rets.shape[1]), groups)
    splits = list(combinations(range(groups), test))
    taken: dict[int, list[np.ndarray]] = {g: [] for g in range(groups)}
    for tg in splits:
        keep = np.ones(rets.shape[1], bool)
        for g in tg:
            lo, hi = bounds[g][0], bounds[g][-1]
            keep[max(0, lo - purge):hi + purge + 1] = False
        tr = rets[:, keep]
        sd = tr.std(1)
        k = int(np.argmax(np.where(sd > 1e-12, tr.mean(1) / np.where(sd > 1e-12, sd, 1), -np.inf)))
        for g in tg:
            taken[g].append(rets[k, bounds[g]])
    n_paths = len(splits) * test // groups
    paths = [np.concatenate([taken[g][j] for g in range(groups)]) for j in range(n_paths)]
    sharpes = [float(M.sharpe(p) or 0.0) for p in paths]
    step = max(1, rets.shape[1] // 400)
    eq = [np.cumprod(1 + p) for p in paths]
    curve = [{"date": str(dates[i + 1].date()), **{f"p{j}": float(e[i]) for j, e in enumerate(eq)}} for i in range(0, rets.shape[1], step)]
    return {"splits": len(splits), "paths": n_paths, "sharpes": sharpes, "median": float(np.median(sharpes)), "share_positive": float(np.mean([s > 0 for s in sharpes])), "curve": curve}


def power(days: int, trades: int, false_pos: float | None) -> dict:
    """Chance a one-sided 5% test on this many days of returns detects a true annual Sharpe of 0.25, 0.5, 1.0."""
    from scipy.stats import norm

    years = days / 252
    rows = [{"true_sharpe": s, "detected": float(1 - norm.cdf(1.645 - s * math.sqrt(years)))} for s in (0.25, 0.5, 0.75, 1.0)]
    need = {s: (1.645 + 0.842) ** 2 / s**2 for s in (0.5, 1.0)}  # years for 80% power
    return {"rows": rows, "years": years, "trades": trades, "false_positive": false_pos, "years_for_80pct": need}


def shocks(spec, prep, settings, base) -> list[dict]:
    """Shocks applied on the bar the strategy held most positions: a 10% gap down, volatility ×3 for 20 bars, every name moving with the market for 20 bars."""
    t = int(np.argmax(base.positions)) or len(prep.panel.dates) // 2
    out = []
    bars = prep.sig_bars
    rets = {f: bars[f][1:] / bars[f][:-1] for f in ("open", "high", "low", "close")}

    def rebuild(scale):
        nb = dict(bars)
        for f in ("open", "high", "low", "close"):
            r = rets[f].copy()
            r = scale(r, f)
            first = bars[f][:1]
            nb[f] = np.vstack([first, first * np.nancumprod(np.nan_to_num(r, nan=1.0), axis=0)])
            nb[f][np.isnan(bars[f])] = np.nan
        return nb

    def gap(r, f):
        r = r.copy()
        r[t - 1] *= 0.90
        return r

    def vol3(r, f):
        r = r.copy()
        r[t - 1:t + 19] = 1 + 3 * (r[t - 1:t + 19] - 1)
        return r

    mkt = bars["market"][1:, :1] / bars["market"][:-1, :1] if "market" in bars else None

    def corr1(r, f):
        r = r.copy()
        if mkt is not None:
            r[t - 1:t + 19] = np.repeat(mkt[t - 1:t + 19], r.shape[1], axis=1)
        return r

    for name, fn in (("Gap down 10%", gap), ("Volatility ×3 for 20 bars", vol3), ("Everything moves with the market for 20 bars", corr1)):
        if name.startswith("Everything") and mkt is None:
            continue
        nb = rebuild(fn)
        shocked = replace(prep, sig_bars=nb, panel=_panel_from(prep.panel, nb))
        eq = simulate(spec, shocked, settings).equity
        dd = float((eq / np.maximum.accumulate(eq) - 1).min())
        out.append({"shock": name, "on": str(prep.panel.dates[t].date()), "max_drawdown": dd, "base_drawdown": float((base.equity / np.maximum.accumulate(base.equity) - 1).min()),
                    "total_return": float(eq[-1] / eq[0] - 1)})
    return out


def shifted_starts(spec, prep, settings, months=(0, 3, 6, 9, 12)) -> list[dict]:
    """The same rule started later: drops the first k months, nothing else changes."""
    out = []
    for k in months:
        lo = k * 21
        if lo >= len(prep.panel.dates) - 252:
            break
        sl = replace(prep, panel=prep.panel.window(lo, len(prep.panel.dates)), sig_bars={f: v[lo:] for f, v in prep.sig_bars.items()},
                     benchmark=None if prep.benchmark is None else prep.benchmark[lo:])
        eq = simulate(spec, sl, settings).equity
        out.append({"start": str(sl.panel.dates[0].date()), "months_later": k, "sharpe": _sharpe(eq), "total_return": float(eq[-1] / eq[0] - 1)})
    return out


def related(spec, settings) -> dict:
    """The same rule on other names: the next band of liquid names (or the top names not in the list)."""
    from .backtest import _universe

    if settings.symbols:
        alt = [s for s in _universe(settings.model_copy(update={"symbols": [], "top_n": 100})) if s not in set(_universe(settings))][:50]
    else:
        wide = _universe(settings.model_copy(update={"top_n": settings.top_n * 2}))
        alt = wide[settings.top_n:]
    if len(alt) < 5:
        return {"status": "skipped", "reason": "no other names held"}
    st = settings.model_copy(update={"symbols": alt})
    try:
        pr = prepare(st)
        eq = simulate(spec, pr, st).equity
    except Refusal as e:
        return {"status": "skipped", "reason": e.reason}
    return {"status": "ok", "names": len(alt), "sharpe": _sharpe(eq), "total_return": float(eq[-1] / eq[0] - 1), "first": alt[0], "last": alt[-1]}
