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
from . import engine, limits, store
from .backtest import FEW_TRADES, Refusal, prepare, simulate
from .spec import Settings, Strategy

PROFILES = {"quick": {"noise": 20, "mcpt": 20, "random": 300, "windows": 4, "cells": 16},
            "full": {"noise": 100, "mcpt": 200, "random": 1000, "windows": 8, "cells": 49}}
WEIGHTS = {"walk_forward": 3, "vs_random": 2, "noise": 2, "mcpt": 2, "delay": 1, "costs": 2, "parameters": 2, "dsr": 3, "pbo": 2}
NAMES = {"walk_forward": "Walk-forward", "vs_random": "Vs random entries", "noise": "Price noise", "mcpt": "Permutation (MCPT)", "delay": "Delay 1 bar",
         "costs": "Costs 2×", "parameters": "Nearby settings", "dsr": "Deflated Sharpe", "pbo": "Overfitting (PBO)"}
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


def walk_forward(curves: list[tuple[dict, np.ndarray]], dates: pd.DatetimeIndex, windows: int) -> tuple[dict, list[dict], list[dict]]:
    """Rolling: optimise on window i (best Sharpe among the cells), trade window i+1 with that choice. OOS pieces are stitched."""
    edges = np.linspace(0, len(dates) - 1, windows + 2).astype(int)
    rows, stitched, is_ann, oos_ann = [], [], [], []
    for i in range(windows):
        a, b, c = edges[i], edges[i + 1], edges[i + 2]
        scores = [_sharpe(eq[a:b + 1]) for _, eq in curves]
        k = int(np.nanargmax(scores)) if np.isfinite(scores).any() else 0
        params, eq = curves[k]
        is_r, oos_r = _daily(eq[a:b + 1]), _daily(eq[b:c + 1])
        stitched.append(oos_r)
        ia, oa = float(np.mean(is_r) * 252), float(np.mean(oos_r) * 252)
        is_ann.append(ia)
        oos_ann.append(oa)
        rows.append({"window": i + 1, "is_from": str(dates[a].date()), "is_to": str(dates[b].date()), "oos_from": str(dates[b].date()), "oos_to": str(dates[c].date()),
                     **{f"param_{p}": v for p, v in params.items()}, "is_sharpe": scores[k], "oos_sharpe": _sharpe(eq[b:c + 1]), "oos_return": float(eq[c] / eq[b] - 1)})
    oos = np.concatenate(stitched)
    eq = np.concatenate([[1.0], np.cumprod(1 + oos)])
    step = max(1, len(eq) // 600)
    curve = [{"date": str(dates[edges[1] + i].date()), "oos": float(eq[i])} for i in range(0, len(eq), step) if edges[1] + i < len(dates)]
    wfe = float(np.mean(oos_ann) / np.mean(is_ann)) if np.mean(is_ann) > 0 else None
    summary = {"wfe": wfe, "profitable": int(sum(r["oos_return"] > 0 for r in rows)), "windows": len(rows), "oos_sharpe": float(M.sharpe(oos) or 0.0)}
    return summary, rows, curve


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
    """CSCV (Bailey et al. 2015) as in shared.stats, except a setting flat for a whole block (in cash) scores Sharpe 0 there instead of voiding the test."""
    from itertools import combinations

    from scipy import stats as st

    if m.ndim != 2 or m.shape[1] < 8 or m.shape[0] < partitions * 2 or not np.isfinite(m).all():
        return None
    blocks = np.array_split(np.arange(len(m)), partitions)

    def sr(x):
        sd = x.std(0, ddof=1)
        return np.where(sd > 1e-12, x.mean(0) / np.where(sd > 1e-12, sd, 1), 0.0)

    below = []
    for train in combinations(range(partitions), partitions // 2):
        tr = np.concatenate([blocks[i] for i in train])
        te = np.concatenate([blocks[i] for i in range(partitions) if i not in train])
        winner = int(np.argmax(sr(m[tr])))
        rank = st.rankdata(sr(m[te]), method="average")[winner] / (m.shape[1] + 1)
        below.append(rank <= 0.5)
    return float(np.mean(below))


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
                 show_holdout: bool = False, actor: str = "human", progress=None) -> dict:
    stage = progress or (lambda *_: None)
    prof = PROFILES.get(profile, PROFILES["quick"])
    if not C.compile_spec(spec)["ok"]:
        raise Refusal("The strategy does not compile.", ["fix the rule in Build"])
    stage("load", 5)
    prep = prepare(settings)
    p, dates, cap = prep.panel, prep.panel.dates, settings.capital
    sig = C.signals(spec, prep.sig_bars, dates)
    base = simulate(spec, prep, settings, sig=sig, magnifier=False)
    closed = base.trades[base.trades[:, engine.T_REASON] != engine.R_OPEN]
    if len(base.trades) == 0:
        raise Refusal("0 trades: nothing to validate.", ["the rule never fires on this universe"])
    years = len(dates) / 252
    base_sr, daily = _sharpe(base.equity), _daily(base.equity)
    few = len(closed) < FEW_TRADES
    tiles: list[dict] = []
    tables: dict[str, list] = {}
    charts: dict[str, list] = {}

    stage("walk-forward", 15)
    cells = _cells(spec, prof["cells"])
    curves = [(c, simulate(spec, prep, settings, params=c, magnifier=False).equity) for c in cells] if cells else [({}, base.equity)]
    if few:
        tiles.append(_tile("walk_forward", "skipped", reason=f"{len(closed)} closed trades; needs {FEW_TRADES}"))
        wf = None
    else:
        wf, rows, curve = walk_forward(curves, dates, prof["windows"])
        tables["windows"], charts["walk_forward"] = rows, curve
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
    noise_sr = [_sharpe(simulate(spec, prep, settings, sig=C.signals(spec, _noisy(prep.sig_bars, rng, 0.25), dates), magnifier=False).equity) for _ in range(prof["noise"])]
    med = float(np.nanmedian(noise_sr))
    tiles.append(_tile("noise", "pass" if base_sr > 0 and med >= 0.5 * base_sr else "fail", med, "median Sharpe ≥ half the original",
                       f"with price noise the median Sharpe is {med:.2f} (original {base_sr:.2f})"))
    tables["noise"] = [{"run": i + 1, "sharpe": s} for i, s in enumerate(noise_sr)]

    stage("permutation", 55)
    perm_sr = [_sharpe(simulate(spec, replace(prep, sig_bars=(pb := _permuted(prep.sig_bars, rng)), panel=_panel_from(p, pb)), settings, magnifier=False).equity)
               for _ in range(prof["mcpt"])]
    pval = float((np.array(perm_sr) >= base_sr).mean()) if perm_sr else 1.0
    tiles.append(_tile("mcpt", "pass" if pval <= 0.05 else "fail", pval, "p ≤ 0.05", f"{pval * 100:.0f}% of {len(perm_sr)} shuffled-return markets did as well (p = {pval:.2f})"))
    tables["mcpt"] = [{"run": i + 1, "sharpe": s} for i, s in enumerate(perm_sr)]

    stage("execution", 70)
    d1 = _sharpe(simulate(spec, prep, settings, sig=_shift(sig, 1), magnifier=False).equity)
    d2 = _sharpe(simulate(spec, prep, settings, sig=_shift(sig, 2), magnifier=False).equity)
    tiles.append(_tile("delay", "pass" if base_sr > 0 and d1 >= 0.5 * base_sr else "fail", d1, "Sharpe ≥ half the original", f"one bar late: Sharpe {d1:.2f}; two bars: {d2:.2f}"))
    ladder = []
    for m in (1, 2, 3, 5, 8):
        eq = simulate(spec, prep, settings, sig=sig, cost_multiple=m, magnifier=False).equity
        ladder.append({"multiple": m, "total_return": float(eq[-1] / cap - 1), "sharpe": _sharpe(eq)})
    breakeven = next((x["multiple"] for x in ladder if x["total_return"] <= 0), None)
    c2 = ladder[1]["total_return"]
    tiles.append(_tile("costs", "pass" if c2 > 0 else "fail", c2, "profitable at 2× costs",
                       f"profitable at 2× costs; break-even beyond {ladder[-1]['multiple']}×" if c2 > 0 and breakeven is None else
                       f"costs break it at {breakeven}×" if breakeven else "loses money at 2× costs"))
    tables["execution"] = [{"case": "original", "sharpe": base_sr}, {"case": "delay 1 bar", "sharpe": d1}, {"case": "delay 2 bars", "sharpe": d2},
                           *({"case": f"costs {x['multiple']}×", "sharpe": x["sharpe"], "total_return": x["total_return"]} for x in ladder[1:])]

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
        pbo = pbo_cscv(m)
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
        eq = simulate(spec, full, settings, magnifier=False).equity
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
    run_hash = hashlib.sha256(f"st03:{spec.hash()}:{settings.hash()}:{profile}".encode()).hexdigest()[:16]
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
                 "next_test": f"Run: {nxt['name']} ({nxt['reason']})" if nxt else None, "what_would_change": change, "walk_forward": wf, "profile": profile,
                 "total_return": float(base.equity[-1] / cap - 1), "metrics": {"sharpe": base_sr, "trades": len(base.trades)},
                 "run_hash": run_hash, "result_hash": tile_hash, "verdict_chip": f"Grade {g['grade']}", "freshness": limits.freshness(),
                 "period": [str(dates[0].date()), str(dates[-1].date())], "spec": spec.model_dump(), "settings": settings.model_dump(), "few_trades": few},
    }


def _panel_from(p, bars: dict[str, np.ndarray]):
    from . import data

    return data.Panel(p.dates, p.symbols, *(bars[f] if f in bars else getattr(p, f) for f in data.FIELDS))
