"""Report card, protocol, batch screening, validation, report export and literature match.

Everything here is rule-based: grades come from fixed thresholds on the study
numbers and the explain sentences are filled-in templates (no language model).
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Callable

import numpy as np
import pandas as pd

from .audit import attach_audit, shared_panel

REPORT_FEATURES = ["01", "02", "03", "04", "05", "08", "11"]
BANDS = [("A", 85), ("B", 70), ("C", 55), ("D", 40)]
T_THRESHOLDS = (3.0, 2.5, 2.0, 1.5)  # A, B, C, D: Harvey-Liu-Zhu t = 3.0 bar down to 1.5
GRADING_RULES = {
    "significance": "Fama-MacBeth |t|: A >= 3.0, B >= 2.5, C >= 2.0, D >= 1.5, else F; capped at D if its sign differs from the long-short sort.",
    "robustness": "Share of specifications significant at 5% with the base sign: A >= 80%, B >= 60%, C >= 40%, D >= 20%.",
    "placebo": "Permutation p-value of the real t-statistic: A <= 0.01, B <= 0.05, C <= 0.10, D <= 0.20.",
    "regimes": "Share of regimes whose coefficient has the base sign: A = all and the premium difference is insignificant, B = all, C >= 75%, D >= 50%.",
    "diagnostics": "Number of red or amber diagnostic flags: A = 0, B <= 1, C <= 2, D <= 4.",
    "decay": "Vitality (recent premium as % of in-sample): A >= 80, B >= 50, C >= 25, D >= 0. Not graded without a discovery date.",
    "factor_zoo": "Spanning-alpha |t| against the benchmark library: same bands as significance.",
    "costs": "Net Sharpe as a share of gross Sharpe: A >= 0.8, B >= 0.6, C >= 0.4, D >= 0.2.",
}


def grade_from_thresholds(value: float | None, cuts: tuple[float, ...], higher_better: bool = True) -> str:
    if value is None or not np.isfinite(value):
        return "F"
    v = value if higher_better else -value
    for letter, cut in zip("ABCD", cuts if higher_better else tuple(-c for c in cuts)):
        if v >= cut:
            return letter
    return "F"


def grade_from_score(score: float) -> str:
    for letter, cut in BANDS:
        if score >= cut:
            return letter
    return "F"


def _num(x: Any) -> float | None:
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _first(table: Any) -> dict[str, Any]:
    return table[0] if isinstance(table, list) and table else {}


def bhy_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Yekutieli step-up adjusted p-values, valid under arbitrary dependence."""

    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return []
    c = float(np.sum(1.0 / np.arange(1, m + 1)))
    order = np.argsort(p)
    adj = p[order] * m * c / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(adj, 0, 1)
    return out.tolist()


def _dim(dimension: str, score: float | None, grade: str, summary: str, label: str, value: Any) -> dict[str, Any]:
    return {"dimension": dimension, "grade": grade, "score": None if score is None else round(float(score), 1), "summary": summary, "metric": {"label": label, "value": value}}


def _t_score(t: float | None) -> float:
    return 0.0 if t is None else float(np.clip(abs(t) / T_THRESHOLDS[0] * 100, 0, 100))


def grade_dimensions(res: dict[str, dict[str, Any]], costs: dict[str, Any] | None, decay_ran: bool) -> list[dict[str, Any]]:
    """Apply GRADING_RULES to the component results (feature id -> result dict, absent if it failed)."""

    out: list[dict[str, Any]] = []
    t1 = res.get("01", {}).get("tables", {})
    fm = next((r for r in t1.get("fama_macbeth_regression", []) if r.get("term") == "signal"), {})
    ls = next((r for r in t1.get("portfolio_sort", []) if r.get("portfolio") == "long_short"), {})
    t, lam, ls_mean = _num(fm.get("t_stat")), _num(fm.get("lambda")), _num(ls.get("mean_return"))
    g = grade_from_thresholds(None if t is None else abs(t), T_THRESHOLDS)
    if t is not None and lam is not None and ls_mean is not None and np.sign(lam) != np.sign(ls_mean) and g in "ABC":
        g = "D"
    out.append(_dim("significance", _t_score(t), g, f"Fama-MacBeth t = {t:.2f}." if t is not None else "No Fama-MacBeth estimate.", "FM t-stat", t))

    rows = [r for r in res.get("02", {}).get("tables", {}).get("robustness_matrix", []) if r.get("status") == "ok"]
    if rows:
        base = _num(rows[0].get("coefficient")) or 0.0
        share = float(np.mean([(_num(r.get("p_value")) or 1) < 0.05 and np.sign(_num(r.get("coefficient")) or 0) == np.sign(base) for r in rows]))
        out.append(_dim("robustness", share * 100, grade_from_thresholds(share, (0.8, 0.6, 0.4, 0.2)), f"{share:.0%} of {len(rows)} specifications are significant at 5% with the base sign.", "Significant share", round(share, 3)))
    else:
        out.append(_dim("robustness", None, "F", "No specification ran.", "Significant share", None))

    perm = _first(res.get("03", {}).get("tables", {}).get("permutation_placebo"))
    pp = _num(perm.get("permutation_p_value"))
    out.append(_dim("placebo", None if pp is None else (1 - pp) * 100, grade_from_thresholds(pp, (0.01, 0.05, 0.10, 0.20), higher_better=False), f"Permutation p = {pp:.3f}." if pp is not None else "No permutation test.", "Permutation p", pp))

    reg = res.get("04", {}).get("tables", {}).get("conditional_coefficient_table", [])
    if reg:
        base_sign = np.sign(lam or 0)
        same = float(np.mean([np.sign(_num(r.get("coefficient")) or 0) == base_sign for r in reg]))
        diff_p = _num(_first(res.get("04", {}).get("tables", {}).get("premium_difference_test")).get("p_value"))
        gr = "A" if same == 1 and diff_p is not None and diff_p > 0.05 else "B" if same == 1 else "C" if same >= 0.75 else "D" if same >= 0.5 else "F"
        out.append(_dim("regimes", same * 100, gr, f"{same:.0%} of regimes keep the base sign; the premium difference across regimes has p = {diff_p:.3f}." if diff_p is not None else f"{same:.0%} of regimes keep the base sign.", "Same-sign regimes", round(same, 3)))
    else:
        out.append(_dim("regimes", None, "F", "No regime estimate.", "Same-sign regimes", None))

    card = res.get("05", {}).get("tables", {}).get("diagnostic_report_card", [])
    if card:
        flags = sum(1 for r in card if r.get("flag") in ("red", "amber"))
        out.append(_dim("diagnostics", max(0.0, 100 - 25 * flags), grade_from_thresholds(flags, (0, 1, 2, 4), higher_better=False), f"{flags} of {len(card)} diagnostics flagged.", "Flags", flags))
    else:
        out.append(_dim("diagnostics", None, "F", "No diagnostics ran.", "Flags", None))

    if decay_ran and res.get("08"):
        vit = _num(_first(res["08"]["tables"].get("vitality_gauge")).get("vitality_score"))
        out.append(_dim("decay", None if vit is None else float(np.clip(vit, 0, 100)), grade_from_thresholds(vit, (80, 50, 25, 0)), f"Vitality {vit:.0f}% of the in-sample premium." if vit is not None else "No vitality estimate.", "Vitality %", vit))
    else:
        out.append(_dim("decay", None, "N/A", "Not graded: set a discovery date to measure post-publication decay.", "Vitality %", None))

    zoo = _first(res.get("11", {}).get("tables", {}).get("extended_spanning_test"))
    zt = _num(zoo.get("alpha_t"))
    out.append(_dim("factor_zoo", _t_score(zt), grade_from_thresholds(None if zt is None else abs(zt), T_THRESHOLDS), f"Spanning alpha t = {zt:.2f} against {zoo.get('library', 'the benchmark library')}." if zt is not None else "No spanning estimate.", "Spanning alpha t", zt))

    if costs and costs.get("available") and _num(costs.get("gross_sharpe")):
        gs, ns = _num(costs["gross_sharpe"]) or 0.0, _num(costs.get("net_sharpe")) or 0.0
        ratio = ns / gs if gs > 0 else 0.0
        out.append(_dim("costs", float(np.clip(ratio * 100, 0, 100)), grade_from_thresholds(ratio, (0.8, 0.6, 0.4, 0.2)), f"Net Sharpe {ns:.2f} versus gross {gs:.2f} after {costs['cost_model']['spread_bps']:.0f} bps spread; break-even {costs.get('breakeven_bps') or 0:.0f} bps.", "Net / gross Sharpe", round(ratio, 3)))
    else:
        out.append(_dim("costs", None, "F", "Costs could not be estimated.", "Net / gross Sharpe", None))
    return out


def overall(grades: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [g for g in grades if g["score"] is not None]
    score = float(np.mean([g["score"] for g in scored])) if scored else 0.0
    letter = grade_from_score(score)
    sig = next((g for g in grades if g["dimension"] == "significance"), None)
    if sig and sig["grade"] == "F" and letter in "ABC":
        letter = "D"
    verdict = {"A": "Strong: the signal passes the full battery.", "B": "Solid: passes most tests with minor weaknesses.", "C": "Mixed: some evidence, with material weaknesses to resolve.", "D": "Weak: fails several tests, treat as unproven.", "F": "Fails: the evidence does not support the signal."}[letter]
    return {"grade": letter, "score": round(score, 1), "verdict": verdict}


def _check(cid: str, question: str, ok: bool | None, detail: str) -> dict[str, Any]:
    return {"id": cid, "question": question, "pass": ok, "detail": detail}


def referee_checklist(res: dict[str, dict[str, Any]], costs: dict[str, Any] | None, panel: Any | None) -> list[dict[str, Any]]:
    rows = [r for r in res.get("02", {}).get("tables", {}).get("robustness_matrix", []) if r.get("status") == "ok"]
    base = _num(rows[0].get("coefficient")) if rows else None

    def survives(pred: Callable[[dict[str, Any]], bool]) -> tuple[bool | None, str]:
        sel = [r for r in rows if pred(r)]
        if not sel or base is None:
            return None, "This variant did not run with the available data."
        ok = all((_num(r["p_value"]) or 1) < 0.05 and np.sign(_num(r["coefficient"]) or 0) == np.sign(base) for r in sel)
        return ok, f"{sum((_num(r['p_value']) or 1) < 0.05 for r in sel)} of {len(sel)} variants significant at 5%."

    out = []
    ok, d = survives(lambda r: r.get("universe") == "ex_microcaps")
    out.append(_check("microcaps_excluded", "Does the result survive excluding microcaps?", ok, d))
    out.append(_check("nyse_breakpoints", "Does it hold with NYSE breakpoints?", None, "Not testable: the local data carries no exchange listing field."))
    ok, d = survives(lambda r: r.get("weighting") == "value")
    out.append(_check("value_vs_equal_weight", "Does it hold with value weights, not only equal weights?", ok, d))
    ls_ex = None
    if panel is not None:
        try:
            from .core.estimators import sort_portfolios
            from .core.stats import mean_test

            s = sort_portfolios(panel, 5)["long_short"].dropna()
            held = s.index + pd.DateOffset(months=1)
            kept = s[held.month != 1]
            tt = mean_test(kept, max(panel.holding_months, 4))
            ls_ex = (abs(tt["t"]) >= 2.0, f"Long-short t = {tt['t']:.2f} excluding January returns ({len(kept)} of {len(s)} periods).")
        except Exception as exc:
            ls_ex = (None, f"Could not compute: {exc}")
    out.append(_check("january", "Is the effect more than a January effect?", *(ls_ex or (None, "No panel."))))
    if costs and costs.get("available"):
        out.append(_check("transaction_costs", "Does it survive transaction costs?", (_num(costs.get("net_sharpe")) or 0) > 0, f"Net Sharpe {costs['net_sharpe']:.2f} at {costs['cost_model']['spread_bps']:.0f} bps spread; break-even {costs.get('breakeven_bps') or 0:.0f} bps."))
    else:
        out.append(_check("transaction_costs", "Does it survive transaction costs?", None, "Costs could not be estimated."))
    mp = _first(res.get("08", {}).get("tables", {}).get("mclean_pontiff_comparison")) if res.get("08") else {}
    surv = _num(mp.get("survival_fraction"))
    out.append(_check("post_publication_decay", "Does the premium persist after publication?", None if surv is None else surv >= 0.5, "No discovery date given." if surv is None else f"{surv:.0%} of the in-sample premium remains after discovery."))
    return out


def protocol_steps(res: dict[str, dict[str, Any]], costs: dict[str, Any] | None) -> dict[str, Any]:
    t1 = res.get("01", {}).get("tables", {})
    ls = next((r for r in t1.get("portfolio_sort", []) if r.get("portfolio") == "long_short"), {})
    span = _first(t1.get("factor_spanning"))
    zoo = _first(res.get("11", {}).get("tables", {}).get("extended_spanning_test"))
    hlz = _first(res.get("11", {}).get("tables", {}).get("harvey_liu_zhu_card"))
    mp = _first(res.get("08", {}).get("tables", {}).get("mclean_pontiff_comparison")) if res.get("08") else {}
    lt, at, zt = _num(ls.get("t_stat")), _num(span.get("t")), _num(zoo.get("alpha_t"))
    surv = _num(mp.get("survival_fraction"))
    steps = [
        {"id": "sorts", "label": "Portfolio sorts", "pass": None if lt is None else abs(lt) >= 2.0, "detail": f"Quintile long-short t = {lt:.2f}." if lt is not None else "No sort."},
        {"id": "alphas", "label": "Factor-model alphas (Fama-French five factors plus momentum; q-factors not in local data)", "pass": None if at is None else abs(at) >= 2.0, "detail": f"Alpha t = {at:.2f}." if at is not None else "No alpha."},
        {"id": "spanning", "label": "Spanning against known anomalies", "pass": None if zt is None else abs(zt) >= (_num(hlz.get("required_t")) or 2.0), "detail": f"Alpha t = {zt:.2f} versus the literature-adjusted bar {_num(hlz.get('required_t')) or 2.0:.2f}." if zt is not None else "No spanning test."},
        {"id": "costs", "label": "Transaction costs", "pass": None if not (costs and costs.get("available")) else (_num(costs.get("net_sharpe")) or 0) > 0, "detail": f"Net Sharpe {costs['net_sharpe']:.2f}." if costs and costs.get("available") and costs.get("net_sharpe") is not None else "No cost estimate."},
        {"id": "decay", "label": "Post-publication decay", "pass": None if surv is None else surv >= 0.5, "detail": "Needs a discovery date." if surv is None else f"{surv:.0%} of the in-sample premium survives."},
    ]
    return {"name": "Novy-Marx & Velikov (2023)", "steps": steps}


def explain(res: dict[str, dict[str, Any]], grades: list[dict[str, Any]], ov: dict[str, Any], costs: dict[str, Any] | None) -> list[str]:
    g = {x["dimension"]: x for x in grades}
    out = [f"Overall grade {ov['grade']} ({ov['score']:.0f}/100): {ov['verdict']}"]
    t = g["significance"]["metric"]["value"]
    if t is not None:
        out.append(f"The Fama-MacBeth t-statistic is {t:.2f}, {'above' if abs(t) >= 3.0 else 'below'} the 3.0 hurdle, so the average premium is {'statistically strong' if abs(t) >= 3.0 else 'not strong enough to rule out chance after multiple testing'}.")
    hlz = _first(res.get("11", {}).get("tables", {}).get("harvey_liu_zhu_card"))
    if hlz.get("observed_t") is not None and hlz.get("required_t") is not None:
        out.append(f"Your t of {hlz['observed_t']:.2f} is {'above' if hlz['observed_t'] >= hlz['required_t'] else 'below'} the factor-zoo hurdle of {hlz['required_t']:.2f} for a signal found among many tested.")
    s = g["robustness"]["metric"]["value"]
    if s is not None:
        out.append(f"{s:.0%} of the alternative specifications are significant at 5% with the same sign.")
    pp = g["placebo"]["metric"]["value"]
    if pp is not None:
        out.append(f"Shuffling the signal reproduces a t-statistic this large with probability {pp:.3f}.")
    fl = g["diagnostics"]["metric"]["value"]
    if fl is not None:
        out.append(f"{fl} diagnostic test{'s' if fl != 1 else ''} raised a flag.")
    v = g["decay"]["metric"]["value"]
    if v is not None:
        out.append(f"The recent premium is {v:.0f}% of the in-sample premium.")
    if costs and costs.get("available"):
        cap = costs.get("capacity_usd")
        out.append(f"After a {costs['cost_model']['spread_bps']:.0f} bps spread the Sharpe ratio falls from {costs['gross_sharpe']:.2f} to {costs['net_sharpe']:.2f}; the signal breaks even at {costs.get('breakeven_bps') or 0:.0f} bps per trade" + (f" and capacity is about ${cap / 1e6:,.1f} million per leg." if cap is not None else "."))
    return out


def run_report_card(payload: dict[str, Any]) -> dict[str, Any]:
    """One worker job: features 01, 02, 03, 04, 05, 08, 11 on one payload and one cached panel, then grading."""

    from .registry import _load, FEATURE_MODULES

    base = {**payload, "include_merged": False}
    res: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    decay_ran = bool(payload.get("discovery_date"))
    with shared_panel() as panels:
        for fid in REPORT_FEATURES:
            if fid == "08" and not decay_ran:
                continue
            module = next(m for m in FEATURE_MODULES if m.endswith(f"_{fid}"))
            try:
                res[fid] = _load(module).run(base)
            except Exception as exc:
                errors[fid] = str(exc)
        out: dict[str, Any] = {"feature_id": "report_card", "status": "ok", "summary_cards": [], "charts": {}, "tables": {}, "meta": {"config": {k: v for k, v in payload.items() if not str(k).startswith("_")}, "component_errors": errors}}
        attach_audit(out, panels, payload)
        panel = panels[0] if panels else None
        costs = out["meta"].get("costs")
        grades = grade_dimensions(res, costs, decay_ran)
        ov = overall(grades)
        out.update({"grades": grades, "overall": ov, "checklist": referee_checklist(res, costs, panel), "protocol": protocol_steps(res, costs), "explain": explain(res, grades, ov, costs), "grading_rules": GRADING_RULES})
    out["evidence"] = {fid: {k: v[:30] for k, v in r["tables"].items() if k in EVIDENCE_TABLES and isinstance(v, list)} for fid, r in res.items()}
    from .core.common import _clean_value

    return _clean_value(out)


EVIDENCE_TABLES = {"fama_macbeth_regression", "portfolio_sort", "factor_spanning", "robustness_summary_line", "permutation_placebo", "conditional_coefficient_table", "diagnostic_report_card", "vitality_gauge", "mclean_pontiff_comparison", "harvey_liu_zhu_card", "extended_spanning_test", "curve_level_joint_p_value", "falsification_verdict"}


# ---------------------------------------------------------------------------
# batch screening


def _signal_payload(base: dict[str, Any], signal: str) -> dict[str, Any]:
    from .core.panel import SIGNALS

    s = str(signal).strip()
    if s.lower() in SIGNALS:
        return {**base, "signal": s.lower()}
    return {**base, "signal_expr": s}  # formulas are resolved by the panel (signal_expr support)


def run_batch(payload: dict[str, Any], signals: list[str]) -> dict[str, Any]:
    from .core.estimators import fama_macbeth, sort_portfolios
    from .core.panel import build_panel
    from .core.stats import mean_test

    rows: list[dict[str, Any]] = []
    with shared_panel():
        for s in signals:
            try:
                panel = build_panel(_signal_payload(payload, s))
                fm, _ = fama_macbeth(panel, list(panel.controls), None)
                sig = fm[fm["term"] == "signal"].iloc[0]
                ls = sort_portfolios(panel, 5)["long_short"].dropna()
                ic = panel.signal.corrwith(panel.dependent, axis=1, method="spearman").mean()
                sharpe = float(ls.mean() / ls.std() * np.sqrt(12 / panel.holding_months)) if ls.std() else None
                rows.append({"signal": s, "t_stat": float(sig["t_stat"]), "p": float(sig["p_value"]), "sharpe": sharpe, "ic": float(ic), "months": int(sig["months"]), "ls_t_stat": mean_test(ls, max(panel.holding_months, 4))["t"]})
            except Exception as exc:
                rows.append({"signal": s, "error": str(exc)})
    ok = [r for r in rows if "error" not in r]
    for r, a in zip(ok, bhy_adjust([r["p"] for r in ok])):
        r["p_adj_bhy"] = a
        r["grade"] = grade_from_thresholds(abs(r["t_stat"]), T_THRESHOLDS)
        r["survives"] = bool(a < 0.05)
    ok.sort(key=lambda r: r["p_adj_bhy"])
    from .core.common import _clean_value

    return _clean_value({"feature_id": "batch", "status": "ok", "rows": ok + [r for r in rows if "error" in r], "method": "BHY", "trials": len(signals), "meta": {"config": payload}})


# ---------------------------------------------------------------------------
# walk-forward and combinatorial purged cross-validation


def _sharpe(s: pd.Series, per_year: float) -> float | None:
    s = s.dropna()
    return float(s.mean() / s.std() * np.sqrt(per_year)) if len(s) > 2 and s.std() else None


def _span(s: pd.Series) -> dict[str, Any]:
    return {"start": s.index.min().strftime("%Y-%m-%d") if len(s) else None, "end": s.index.max().strftime("%Y-%m-%d") if len(s) else None, "n": int(len(s))}


def pbo_cscv(returns: pd.DataFrame, parts: int = 8) -> float | None:
    """Probability of backtest overfitting (Bailey et al.): share of half-splits where the in-sample best strategy ranks below the median out of sample."""

    returns = returns.dropna()
    if returns.shape[1] < 2 or len(returns) < parts * 2:
        return None
    chunks = np.array_split(np.arange(len(returns)), parts)
    below = total = 0
    for combo in itertools.combinations(range(parts), parts // 2):
        is_idx = np.concatenate([chunks[i] for i in combo])
        oos_idx = np.concatenate([chunks[i] for i in range(parts) if i not in combo])
        is_s, oos_s = returns.iloc[is_idx], returns.iloc[oos_idx]
        is_sh = is_s.mean() / is_s.std().replace(0, np.nan)
        oos_sh = oos_s.mean() / oos_s.std().replace(0, np.nan)
        best = is_sh.idxmax()
        rank = (oos_sh.rank(pct=True))[best]
        below += rank <= 0.5
        total += 1
    return float(below / total) if total else None


def run_validation(payload: dict[str, Any], method: str = "walk_forward", folds: int = 5, embargo_days: int = 30) -> dict[str, Any]:
    from .core.estimators import sort_portfolios
    from .core.panel import build_panel

    if method not in {"walk_forward", "cpcv"}:
        raise ValueError("method must be walk_forward or cpcv")
    folds = max(3, min(int(folds), 12))
    with shared_panel() as panels:
        panel = build_panel(payload)
        port = sort_portfolios(panel, 5)
        ls = port["long_short"].dropna()
        h = panel.holding_months
        per_year = 12 / h
        gap = pd.Timedelta(days=int(h * 31) + int(embargo_days))
        chunks = np.array_split(np.arange(len(ls)), folds + 1 if method == "walk_forward" else folds)
        out_folds: list[dict[str, Any]] = []

        def purge(train: pd.Series, test_idx: pd.DatetimeIndex) -> pd.Series:
            """Drop training periods whose holding window or embargo touches a test period."""

            keep = np.ones(len(train), dtype=bool)
            for lo, hi in ((test_idx.min(), test_idx.max()),):
                keep &= ~((train.index + gap >= lo) & (train.index <= hi + pd.Timedelta(days=int(embargo_days))))
            return train[keep]

        if method == "walk_forward":
            for i in range(1, len(chunks)):
                test = ls.iloc[chunks[i]]
                train = purge(ls.iloc[np.concatenate(chunks[:i])], test.index)
                out_folds.append({"fold": i, "train": _span(train), "test": _span(test), "is_sharpe": _sharpe(train, per_year), "oos_sharpe": _sharpe(test, per_year)})
        else:
            for combo in itertools.combinations(range(folds), 2):
                test = ls.iloc[np.concatenate([chunks[i] for i in combo])]
                train = ls.iloc[np.concatenate([chunks[i] for i in range(folds) if i not in combo])]
                for i in combo:
                    train = purge(train, ls.iloc[chunks[i]].index)
                out_folds.append({"fold": len(out_folds) + 1, "train": _span(train), "test": _span(test), "test_groups": list(combo), "is_sharpe": _sharpe(train, per_year), "oos_sharpe": _sharpe(test, per_year)})
        q = [c for c in port.columns if c.startswith("Q")]
        strategies = {}
        for a, b in itertools.permutations(q, 2):
            strategies[f"{a}-{b}"] = port[a] - port[b]
        pbo = pbo_cscv(pd.DataFrame(strategies))
        out: dict[str, Any] = {"feature_id": "validation", "status": "ok", "method": method, "folds": out_folds, "pbo": pbo, "meta": {"config": payload, "embargo_days": embargo_days}}
        is_v = [f["is_sharpe"] for f in out_folds if f["is_sharpe"] is not None]
        oos_v = [f["oos_sharpe"] for f in out_folds if f["oos_sharpe"] is not None]
        out["summary"] = {"mean_is_sharpe": float(np.mean(is_v)) if is_v else None, "mean_oos_sharpe": float(np.mean(oos_v)) if oos_v else None, "share_oos_positive": float(np.mean([v > 0 for v in oos_v])) if oos_v else None, "degradation": (1 - float(np.mean(oos_v)) / float(np.mean(is_v))) if is_v and oos_v and np.mean(is_v) else None, "pbo_basis": "CSCV over all ordered quintile spreads", "folds": len(out_folds)}
        attach_audit(out, panels, payload)
    from .core.common import _clean_value

    return _clean_value(out)


# ---------------------------------------------------------------------------
# literature match


def literature_match(expr: str, payload: dict[str, Any] | None = None, limit: int = 10) -> dict[str, Any]:
    """Nearest published anomalies by mean cross-sectional rank correlation of the signal with each library signal."""

    from .core.panel import SIGNALS, build_panel, signal_for

    payload = {"max_symbols": 150, "lookback_days": 3650, **(payload or {})}
    panel = build_panel(_signal_payload(payload, expr))
    cand = panel.signal
    rows = []
    for name in SIGNALS:
        if name == panel.config.get("signal") and str(expr).lower() == name:
            continue
        try:
            other = signal_for(panel, name)
            corr = cand.rank(axis=1).corrwith(other.rank(axis=1), axis=1).mean()
            if np.isfinite(corr):
                rows.append({"library_id": name, "name": name.replace("_", " ").title(), "corr": float(corr)})
        except Exception:
            continue
    rows.sort(key=lambda r: -abs(r["corr"]))
    return {"matches": rows[:limit], "available": True}


# ---------------------------------------------------------------------------
# report export


def _f(x: Any, d: int = 2) -> str:
    v = _num(x)
    return "n/a" if v is None else f"{v:.{d}f}"


def _tex(s: Any) -> str:
    return str(s).replace("\\", " ").replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#").replace("$", "\\$")


def report_markdown(job: dict[str, Any]) -> str:
    cfg = job.get("meta", {}).get("config", {})
    lines = [f"# Signal report: {cfg.get('signal_expr') or cfg.get('signal', 'signal')}", "", f"Overall grade **{job['overall']['grade']}** ({job['overall']['score']:.0f}/100). {job['overall']['verdict']}", "", "## Abstract", ""]
    lines += [f"- {s}" for s in job["explain"]]
    lines += ["", "## Grades", "", "| Dimension | Grade | Score | Metric | Summary |", "|---|---|---|---|---|"]
    lines += [f"| {g['dimension']} | {g['grade']} | {_f(g['score'], 0)} | {g['metric']['label']}: {_f(g['metric']['value'], 3)} | {g['summary']} |" for g in job["grades"]]
    lines += ["", "## Referee checklist", ""] + [f"- [{'x' if c['pass'] else ' '}] {c['question']} ({'pass' if c['pass'] else 'untested' if c['pass'] is None else 'fail'}): {c['detail']}" for c in job["checklist"]]
    lines += ["", f"## Protocol: {job['protocol']['name']}", ""] + [f"- {s['label']}: {'pass' if s['pass'] else 'untested' if s['pass'] is None else 'fail'}. {s['detail']}" for s in job["protocol"]["steps"]]
    lines += ["", "## Robustness appendix", ""] + [f"- {k}: {v}" for k, v in job.get("grading_rules", {}).items()]
    audit = job.get("meta", {}).get("data_audit", {})
    lines += ["", "## Methods", "", f"Survivorship: {audit.get('survivorship')}. Point-in-time lag: {audit.get('pit_lag_days')} days. Missing share {_f(audit.get('missing_share'), 3)}."] + [f"- {a}" for a in audit.get("adjustments", [])]
    return "\n".join(lines) + "\n"


def report_tex(job: dict[str, Any]) -> str:
    cfg = job.get("meta", {}).get("config", {})
    title = _tex(f"Signal report: {cfg.get('signal_expr') or cfg.get('signal', 'signal')}")
    audit = job.get("meta", {}).get("data_audit", {})
    rows = "\n".join(f"{_tex(g['dimension'])} & {g['grade']} & {_f(g['score'], 0)} & {_tex(g['summary'])} \\\\" for g in job["grades"])
    chk = "\n".join(f"\\item {_tex(c['question'])} \\textbf{{{'pass' if c['pass'] else 'untested' if c['pass'] is None else 'fail'}}}. {_tex(c['detail'])}" for c in job["checklist"])
    steps = "\n".join(f"\\item {_tex(s['label'])}: \\textbf{{{'pass' if s['pass'] else 'untested' if s['pass'] is None else 'fail'}}}. {_tex(s['detail'])}" for s in job["protocol"]["steps"])
    abstract = " ".join(_tex(s) for s in job["explain"])
    rules = "\n".join(f"\\item \\textbf{{{_tex(k)}}}: {_tex(v)}" for k, v in job.get("grading_rules", {}).items())
    adj = "\n".join(f"\\item {_tex(a)}" for a in audit.get("adjustments", []))
    return f"""\\documentclass[11pt]{{article}}
\\usepackage{{booktabs,longtable,geometry}}
\\geometry{{margin=1in}}
\\title{{{title}}}
\\date{{}}
\\begin{{document}}
\\maketitle
\\begin{{abstract}}
{abstract}
\\end{{abstract}}
\\section{{Results}}
Overall grade {job['overall']['grade']} ({job['overall']['score']:.0f}/100). {_tex(job['overall']['verdict'])}
\\begin{{table}}[h]
\\centering
\\small
\\begin{{tabular}}{{llrp{{0.55\\textwidth}}}}
\\toprule
Dimension & Grade & Score & Reading \\\\
\\midrule
{rows}
\\bottomrule
\\end{{tabular}}
\\caption{{Grade per dimension. Each grade follows a fixed threshold rule listed in the appendix.}}
\\end{{table}}
\\section{{Referee checklist}}
\\begin{{itemize}}
{chk}
\\end{{itemize}}
\\section{{Protocol: {_tex(job['protocol']['name'])}}}
\\begin{{itemize}}
{steps}
\\end{{itemize}}
\\appendix
\\section{{Robustness appendix: grading rules}}
\\begin{{itemize}}
{rules}
\\end{{itemize}}
\\section{{Methods}}
Survivorship: {_tex(audit.get('survivorship'))}. Point-in-time lag: {_tex(audit.get('pit_lag_days'))} days. Missing share {_f(audit.get('missing_share'), 3)}.
\\begin{{itemize}}
{adj}
\\end{{itemize}}
\\end{{document}}
"""


def report_pdf(job: dict[str, Any]) -> bytes:
    """PDF of the Markdown report via reportlab (raises ImportError if it is not installed)."""

    from io import BytesIO

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    for line in report_markdown(job).splitlines():
        if line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
        elif line.strip() and not line.startswith("|---"):
            story.append(Paragraph(escape(line.replace("**", "")), styles["BodyText"]))
        else:
            story.append(Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()
