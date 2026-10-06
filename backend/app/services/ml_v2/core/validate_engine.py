"""Validate: one-page HELD UP / MIXED / FAILED verdict for a strategy, prediction set or model.

Every section is a plain JSON block carrying its own provenance. Nothing here fits on data after the
test window; model refits use purged CPCV splits from ``core.cpcv``.
"""
from __future__ import annotations

import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import uploads
from .common import clean_json, report_progress
from .cpcv import purged_complement
from .performance import max_drawdown, sharpe
from .stats import cscv_pbo, deflated_sharpe_probability
from . import validate_signal as vs

CODE_FILES = ("validate_engine.py", "validate_signal.py", "cpcv.py", "stats.py", "uploads.py")
Q_GRID = [0.1, 0.2, 0.3, 0.4, 0.5]
LAG_GRID = [0, 1, 2, 3, 4]
COST_GRID = [0, 5, 10, 20, 50]


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _dist(values) -> dict[str, Any]:
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if not len(a):
        return {"n": 0}
    return {"n": int(len(a)), "mean": float(a.mean()), "p5": float(np.percentile(a, 5)), "p50": float(np.percentile(a, 50)),
            "p95": float(np.percentile(a, 95)), "share_positive": float((a > 0).mean())}


# ---------------------------------------------------------------- inputs

class Prepared:
    def __init__(self):
        self.mode = ""                       # returns | fixed_signal | model
        self.frame: pd.DataFrame | None = None
        self.returns: pd.Series | None = None
        self.pred: pd.DataFrame | None = None
        self.out: pd.DataFrame | None = None
        self.panel: pd.DataFrame | None = None
        self.features: list[str] = []
        self.trials: pd.DataFrame | None = None
        self.benchmark: pd.Series | None = None
        self.source = ""


def _from_source_result(result: dict) -> pd.DataFrame | pd.Series:
    rows = (result.get("tables") or {}).get("heldout_predictions")
    if rows:
        frame = pd.DataFrame(rows).rename(columns={"actual_forward_return": "outcome"})
        frame["date"] = pd.to_datetime(frame["date"])
        return frame[["date", "ticker", "prediction", "outcome"]].sort_values(["date", "ticker"])
    curves = (result.get("charts") or {}).get("backtest_paths_chart")
    if curves:
        c = pd.DataFrame(curves)
        c["date"] = pd.to_datetime(c["date"])
        r = c.pivot(index="date", columns="path", values="equity").pct_change().mean(axis=1).dropna()
        return r
    raise ValueError("source_result must be a feature 02 run (heldout_predictions) or a feature 01 run (backtest_paths_chart)")


def prepare(request: dict) -> Prepared:
    p = Prepared()
    horizon = int(request["prediction_horizon"])
    source_result = request.get("source_result")
    if request.get("upload_id"):
        item = uploads.get_upload(request["upload_id"], ("returns", "predictions", "feature_panel", "trial_matrix"))
        frame, kind = item.frame.copy(), item.kind
        p.source = f"upload:{kind}"
    elif source_result:
        got = _from_source_result(source_result)
        frame, kind = (got, "returns") if isinstance(got, pd.Series) else (got, "predictions")
        if kind == "returns":
            frame = got.rename("return").reset_index().rename(columns={"index": "date"})
        p.source = "feature_run"
    else:
        raise ValueError("Provide upload_id (returns, predictions, feature_panel or trial_matrix) or source_result from another ML feature run")

    if request.get("trials_upload_id"):
        p.trials = uploads.get_upload(request["trials_upload_id"], ("trial_matrix",)).frame.set_index("date")
    if request.get("benchmark_upload_id"):
        b = uploads.get_upload(request["benchmark_upload_id"], ("returns",)).frame.set_index("date")["return"]
        p.benchmark = b
    p.frame = frame
    if kind == "trial_matrix":
        matrix = frame.set_index("date")
        p.trials = matrix
        sr = matrix.apply(lambda c: sharpe(c.to_numpy(), 252.0))
        choice = request.get("selected_strategy")
        column = matrix.columns[int(choice)] if choice is not None and int(choice) < matrix.shape[1] else sr.idxmax()
        p.returns = matrix[column].astype(float)
        p.mode = "returns"
        p.source += f":{column}"
    elif kind == "returns":
        p.returns = frame.set_index("date")["return"].astype(float)
        p.mode = "returns"
    elif kind == "predictions":
        if "outcome" not in frame.columns or frame["outcome"].notna().sum() < 30:
            raise ValueError("predictions upload needs an outcome column (realised forward return) to be validated")
        p.pred, p.out = vs.wide(frame, "prediction"), vs.wide(frame, "outcome")
        p.pred = p.pred.reindex(index=p.out.index, columns=p.out.columns)
        p.mode = "fixed_signal"
    else:
        if "outcome" not in frame.columns:
            raise ValueError("feature_panel upload needs an outcome column (realised forward return) to fit and validate a model")
        p.panel = frame.reset_index(drop=True)
        p.features = [c for c in frame.columns if c not in {"date", "ticker", "outcome"}]
        if not p.features:
            raise ValueError("feature_panel has no feature columns")
        p.out = vs.wide(p.panel, "outcome")
        p.mode = "model"
    if p.returns is not None:
        p.returns = p.returns.dropna()
        if len(p.returns) < 40:
            raise ValueError("At least 40 return observations are needed")
    elif len(p.out.index) < 40:
        raise ValueError("At least 40 distinct dates are needed")
    return p


# ---------------------------------------------------------------- core runner

def _wide_from_rows(panel: pd.DataFrame, values: np.ndarray, like: pd.DataFrame) -> pd.DataFrame:
    di = like.index.get_indexer(pd.DatetimeIndex(panel["date"]))
    ti = like.columns.get_indexer(panel["ticker"])
    arr = np.full(like.shape, np.nan)
    arr[di, ti] = values
    return pd.DataFrame(arr, index=like.index, columns=like.columns)


class Run:
    def __init__(self, request: dict, prep: Prepared):
        self.r, self.p = request, prep
        self.h = int(request["prediction_horizon"])
        self.embargo = int(request["embargo_period"])
        self.cost = float(request["cost_bps"])
        self.seed = int(request["random_seed"])
        self.q = vs.DEFAULT_Q
        self.pred = prep.pred
        self.paths = None
        self.series: pd.Series | None = prep.returns
        self.turnover: np.ndarray | None = None
        self.cpcv_paths_sharpe: list[float] = []
        self.splits = 0

    # -- headline series
    def build_series(self):
        p = self.p
        if p.mode == "model":
            n_groups, k = int(self.r["cpcv_n_groups"]), int(self.r["cpcv_k_test_groups"])
            report_progress(20, "CPCV model refits")
            self.paths, self.splits = vs.cpcv_model_paths(p.panel, p.features, self.r["model_type"], self.seed, self.h, self.embargo, n_groups, k)
            for row in self.paths:
                w = _wide_from_rows(p.panel, row, p.out)
                s, _ = vs.strategy_series(w, p.out, self.h, self.cost, self.q)
                self.cpcv_paths_sharpe.append(vs.sharpe_of(s, self.h))
            self.pred = _wide_from_rows(p.panel, np.nanmean(self.paths, axis=0), p.out)
        if self.pred is not None:
            self.series, self.turnover = vs.strategy_series(self.pred, p.out, self.h, self.cost, self.q)

    @property
    def sr(self) -> float:
        return vs.sharpe_of(self.series, self.h)

    def provenance(self, block: str, **extra) -> dict[str, Any]:
        p, s = self.p, self.series
        idx = pd.DatetimeIndex(p.out.index if p.out is not None else p.returns.index)
        missing = 0.0
        if p.frame is not None:
            num = p.frame.drop(columns=[c for c in ("date", "ticker", "outcome_date") if c in p.frame.columns])
            missing = float(num.isna().to_numpy().mean()) if num.size else 0.0
        universe = sorted(p.out.columns.astype(str)) if p.out is not None else ["single return series"]
        out = {"block": block, "input": p.source, "mode": p.mode,
               "date_range": [str(idx.min().date()), str(idx.max().date())], "periods": int(len(s)),
               "train_window": ({"note": "purged complement of each CPCV test group", "start": str(idx.min().date()), "end": str(idx.max().date())}
                                if p.mode == "model" else {"note": "none: signal is fixed, nothing is fitted inside Validate"}),
               "test_window": {"start": str(idx.min().date()), "end": str(idx.max().date())},
               "purge_sessions": self.h if p.mode == "model" else 0, "embargo_sessions": self.embargo if p.mode == "model" else 0,
               "universe": {"count": len(universe), "tickers": universe[:25]}, "missing_data_share": missing,
               "calendar": "Dates used as supplied; no gap filling or forward-fill; returns sampled every "
                           f"{self.h} row(s); gaps over 7 calendar days are reported, not interpolated"}
        out.update(extra)
        return out


# ---------------------------------------------------------------- blocks

def block_cpcv(run: Run) -> dict:
    n, k = int(run.r["cpcv_n_groups"]), int(run.r["cpcv_k_test_groups"])
    paths = math.comb(n - 1, k - 1)
    if run.p.mode == "model":
        sharpes = run.cpcv_paths_sharpe
        body = {"kind": "model_refit_paths", "splits": run.splits, "paths": paths, "path_sharpes": sharpes, "distribution": _dist(sharpes)}
    else:
        series = run.series
        groups = np.array_split(np.arange(len(series)), n)
        rows = []
        for combo in combinations(range(n), k):
            idx = np.concatenate([groups[g] for g in combo])
            rows.append({"test_groups": list(combo), "sharpe": vs.sharpe_of(series.iloc[idx], run.h)})
        body = {"kind": "fixed_signal_splits", "splits": len(rows), "paths": paths,
                "note": "Signal is fixed, so each path equals the full series; the distribution is over every C(N,k) test union.",
                "split_sharpes": [r["sharpe"] for r in rows], "distribution": _dist([r["sharpe"] for r in rows])}
    return {"n_groups": n, "k_test_groups": k, **body, "provenance": run.provenance("cpcv")}


def _trial_count(run: Run) -> int:
    declared = int(run.r.get("trial_count") or 0)
    cols = run.p.trials.shape[1] if run.p.trials is not None else 0
    return max(declared, cols, 1)


def block_pbo(run: Run) -> dict:
    m = run.p.trials
    prov = run.provenance("pbo")
    if m is None or m.shape[1] < 2:
        return {"status": "unavailable", "reason": "Upload a trial matrix (date,trial_1..trial_n) with every configuration you tried", "provenance": prov}
    try:
        res = cscv_pbo(m.fillna(0.0).to_numpy(), int(run.r["pbo_partitions"]))
    except ValueError as exc:
        return {"status": "unavailable", "reason": str(exc), "provenance": prov}
    return {"status": "computed", "pbo": res["pbo"], "combinations": res["combinations"], "trials": int(m.shape[1]),
            "partitions": int(run.r["pbo_partitions"]), "provenance": prov}


def block_dsr(run: Run) -> dict:
    r = run.series.to_numpy(dtype=float)
    trials, m = _trial_count(run), run.p.trials
    if m is not None and m.shape[1] > 1:
        per = m.apply(lambda c: c.mean() / c.std(ddof=1) if c.std(ddof=1) > 1e-12 else np.nan).to_numpy(dtype=float)
        var, source = float(np.nanvar(per, ddof=1)), "trial_matrix"
    else:
        var, source = 1.0 / max(len(r) - 1, 1), "analytic_1_over_T"
    if not var > 0:
        var, source = 1.0 / max(len(r) - 1, 1), "analytic_1_over_T"
    try:
        prob = deflated_sharpe_probability(r, trials, var)
    except ValueError as exc:
        return {"status": "unavailable", "reason": str(exc), "provenance": run.provenance("deflated_sharpe")}
    return {"status": "computed", "dsr": prob, "sharpe": run.sr, "trials": trials, "trial_sharpe_variance": var,
            "variance_source": source, "provenance": run.provenance("deflated_sharpe")}


def block_minbtl(run: Run, dsr: dict) -> dict:
    trials = _trial_count(run)
    sr = run.sr
    years = len(run.series) * run.h / 252.0
    t2 = max(trials, 2)
    emax = (1 - np.euler_gamma) * _z(1 - 1 / t2) + np.euler_gamma * _z(1 - 1 / (t2 * math.e))
    # years needed so that a zero-skill search over `trials` configurations cannot reach the observed annual Sharpe
    need = float((emax / sr) ** 2) if sr and sr > 0 else None
    return {"trials": trials, "observed_years": years, "annual_sharpe": sr, "min_years_required": need,
            "sufficient": bool(need is not None and years >= need), "expected_max_zero_skill_sharpe_unit": float(emax),
            "provenance": run.provenance("min_backtest_length")}


def _z(p: float) -> float:
    from scipy.stats import norm
    return float(norm.ppf(p))


def block_controls(run: Run) -> dict:
    p, h = run.p, run.h
    rows: list[dict] = [{"name": "cash", "sharpe": 0.0, "total_return": 0.0, "status": "computed"}]
    unavailable: list[dict] = []
    best_name, best = "cash", 0.0
    shuffled: dict[str, Any] = {"status": "unavailable"}

    def add(name, series, note=""):
        nonlocal best_name, best
        s = vs.sharpe_of(series, h)
        rows.append({"name": name, "sharpe": _f(s), "total_return": float(np.prod(1 + np.asarray(series, dtype=float)) - 1), "status": "computed", "note": note})
        if np.isfinite(s) and s > best:
            best_name, best = name, float(s)

    if p.mode == "returns":
        if p.benchmark is not None:
            aligned = p.benchmark.reindex(run.series.index).dropna()
            if len(aligned) >= 30:
                add("buy_and_hold", aligned.to_numpy(), "benchmark returns upload")
        for name in ("equal_weight", "constant_exposure", "shuffled_signal", "model_control"):
            unavailable.append({"name": name, "status": "unavailable", "reason": "needs per-ticker predictions or a feature panel"})
    else:
        out = p.out
        add("buy_and_hold", vs.buy_and_hold(out, h).to_numpy(), "equal weights set once, never rebalanced")
        add("equal_weight", vs.equal_weight(out, h).to_numpy(), "equal-weight universe, rebalanced every period")
        w = vs.weights_from_scores(run.pred.to_numpy(), run.q)
        add("constant_exposure", vs.constant_exposure(w, out, h).to_numpy(), "strategy's average net exposure, no signal")
        sh = vs.shuffled_controls(run.pred, out, h, run.cost, run.q, int(run.r["n_permutations"]), run.seed)
        p95 = float(np.nanpercentile(sh, 95))
        pval = float((1 + np.nansum(sh >= run.sr)) / (1 + len(sh)))
        shuffled = {"status": "computed", "permutations": int(len(sh)), "seed": run.seed, "sharpe_distribution": _dist(sh),
                    "p_value": pval, "control_sharpe_p95": p95}
        rows.append({"name": "shuffled_signal", "sharpe": p95, "total_return": None, "status": "computed", "note": "95th percentile over permutations"})
        if p95 > best:
            best_name, best = "shuffled_signal", p95
        if p.mode == "model":
            ols = vs.ols_control_predictions(p.panel, p.features, h, run.embargo)
            s, _ = vs.strategy_series(_wide_from_rows(p.panel, ols, out), out, h, run.cost, run.q)
            add("model_control", s.to_numpy(), "ridge on the first 3 features, purged out-of-fold")
        else:
            for name, s in vs.lag_outcome_controls(out, h, run.cost, run.q).items():
                add(name, s.to_numpy(), "model control: last known outcome as score")
    edge = run.sr - best
    return {"controls": rows, "unavailable": unavailable, "shuffled": shuffled, "best_control": best_name,
            "best_control_sharpe": best, "strategy_sharpe": run.sr, "edge_vs_best": _f(edge), "beats_best_control": bool(np.isfinite(edge) and edge > 0),
            "provenance": run.provenance("controls")}


def block_stability(run: Run) -> dict:
    p, n = run.p, min(int(run.r["n_seeds"]), 10)
    prov = run.provenance("stability", seeds_requested=int(run.r["n_seeds"]), seeds_cap=10)
    sharpes: list[float] = []
    source = ""
    if p.mode == "model" and run.r["model_type"] == "random_forest":
        for i in range(n):
            report_progress(60 + i, f"Seed {i + 1} of {n}")
            pr = vs.oos_predictions(p.panel, p.features, "random_forest", run.seed + i, run.h, run.embargo)
            s, _ = vs.strategy_series(_wide_from_rows(p.panel, pr, p.out), p.out, run.h, run.cost, run.q)
            sharpes.append(vs.sharpe_of(s, run.h))
        source = "model_refit_seeds"
    elif p.mode == "model":
        return {"status": "deterministic", "reason": "ridge has no random state; seed instability is not applicable", "flag": False, "provenance": prov}
    elif run.r.get("trials_are") == "seeds" and p.trials is not None:
        sharpes = [vs.sharpe_of(p.trials[c], run.h) for c in p.trials.columns[:10]]
        source = "trial_matrix_columns_as_seeds"
    else:
        return {"status": "unavailable", "reason": "Upload a feature panel with model_type=random_forest, or a trial matrix of seed reruns with trials_are=seeds", "provenance": prov}
    a = np.asarray([s for s in sharpes if np.isfinite(s)])
    if not len(a):
        return {"status": "unavailable", "reason": "No finite seed Sharpe", "provenance": prov}
    best, median = float(a.max()), float(np.median(a))
    flag = bool(best > 1.25 * median) if median > 0 else bool(best > 0)
    return {"status": "computed", "source": source, "seeds": int(len(a)), "sharpes": [float(x) for x in a], "best": best,
            "median": median, "best_over_median": _f(best / median) if median > 0 else None, "flag": flag,
            "rule": "flag when best seed > 1.25 x median", "provenance": prov}


def block_plateau(run: Run) -> dict:
    p, g = run.p, int(run.r["grid_size"])
    prov = run.provenance("plateau")
    if p.mode == "returns":
        m = p.trials
        if m is None:
            return {"status": "unavailable", "reason": "Needs predictions/features (construction sweep) or a trial matrix (breadth proxy)", "provenance": prov}
        sr = m.apply(lambda c: vs.sharpe_of(c, run.h)).to_numpy(dtype=float)
        best = np.nanmax(sr)
        near = float(np.mean(sr >= 0.8 * best)) if best > 0 else 0.0
        label = "plateau" if near >= 0.2 and best > 0 else "cliff"
        return {"status": "computed", "method": "trial_breadth_proxy", "trials": int(m.shape[1]), "share_within_80pct_of_best": near,
                "label": label, "note": "Without parameters, robustness is the share of trials within 80% of the best", "provenance": prov}
    qs, lags = Q_GRID[:g], LAG_GRID[:g]
    grid = [[vs.sharpe_of(vs.strategy_series(run.pred, p.out, run.h, run.cost, q, lag)[0], run.h) for lag in lags] for q in qs]
    arr = np.asarray(grid, dtype=float)
    base_i = min(range(len(qs)), key=lambda i: abs(qs[i] - run.q))
    base = arr[base_i, 0]
    neigh = [arr[i, j] for i in range(max(0, base_i - 1), min(len(qs), base_i + 2)) for j in range(0, min(len(lags), 2)) if (i, j) != (base_i, 0)]
    med, worst = float(np.nanmedian(arr)), float(np.nanmin(neigh)) if neigh else float("nan")
    ok = bool(np.isfinite(base) and base > 0 and med >= 0.5 * base and worst >= 0.3 * base)
    return {"status": "computed", "method": "construction_sweep", "axes": {"portfolio_fraction_each_side": qs, "signal_delay_periods": lags},
            "sharpe_grid": [[_f(x) for x in row] for row in arr], "baseline": {"fraction": run.q, "delay": 0, "sharpe": _f(base)},
            "grid_median": _f(med), "worst_neighbour": _f(worst), "label": "plateau" if ok else "cliff",
            "rule": "plateau when grid median >= 50% and every neighbour >= 30% of the baseline Sharpe", "provenance": prov}


def block_leakage(run: Run) -> dict:
    p, checks = run.p, []
    series = run.series
    cut = int(len(series) * 0.7)
    if p.mode == "fixed_signal":
        rng = np.random.default_rng(run.seed)
        t = run.pred.index[min(cut * run.h, len(run.pred) - 2)]
        late = run.pred.index > t
        pr, ou = run.pred.copy(), p.out.copy()
        pr.loc[late] = rng.normal(size=pr.loc[late].shape) * 100
        ou.loc[late] = rng.normal(size=ou.loc[late].shape) * 100
        again, _ = vs.strategy_series(pr, ou, run.h, run.cost, run.q)
        same = bool(np.allclose(again.loc[:t].to_numpy(), series.loc[:t].to_numpy(), atol=1e-12))
        checks.append({"name": "perturb_after_t_signal_pipeline", "t": str(t.date()), "unchanged": same, "pass": same})
        ic = float(np.nanmean(run.pred.rank(axis=1).corrwith(p.out.rank(axis=1), axis=1)))
        checks.append({"name": "implausible_same_period_ic", "mean_rank_ic": ic, "threshold": 0.5, "pass": not (np.isfinite(ic) and abs(ic) > 0.5),
                       "note": "A mean daily rank IC above 0.5 almost always means the score contains the outcome"})
    elif p.mode == "model":
        panel = p.panel
        dates = pd.DatetimeIndex(panel["date"].unique()).sort_values()
        groups = np.array_split(dates.to_numpy(), int(run.r["cpcv_n_groups"]))
        held = groups[len(groups) // 2]
        stamp = pd.to_datetime(panel["date"])
        test = np.flatnonzero(stamp.isin(held).to_numpy())
        train = purged_complement(panel["date"], held, run.h, run.embargo)
        lo, hi = pd.Timestamp(held.min()), pd.Timestamp(held.max())
        zone = stamp.iloc[train]
        pos = dates.get_indexer([lo, hi])
        guard_lo = dates[max(0, pos[0] - run.h)]
        guard_hi = dates[min(len(dates) - 1, pos[1] + run.h + run.embargo)]
        clean = not ((zone >= guard_lo) & (zone <= guard_hi)).any()
        checks.append({"name": "purge_embargo_excludes_label_overlap", "guard": [str(guard_lo.date()), str(guard_hi.date())], "pass": bool(clean)})
        X = panel[p.features].to_numpy(dtype=float)
        y = panel["outcome"].to_numpy(dtype=float)
        base = vs._fit_predict(lambda: vs.make_model(run.r["model_type"], run.seed), X, y, train, test)
        y2, X2 = y.copy(), X.copy()
        blocked = np.setdiff1d(np.arange(len(panel)), train)
        y2[blocked] = np.random.default_rng(run.seed).normal(size=len(blocked)) * 100
        zone_rows = np.setdiff1d(blocked, test)
        X2[zone_rows] = np.random.default_rng(run.seed + 1).normal(size=X2[zone_rows].shape) * 100
        again = vs._fit_predict(lambda: vs.make_model(run.r["model_type"], run.seed), X2, y2, train, test)
        same = bool(np.allclose(base, again))
        checks.append({"name": "perturb_test_and_purged_rows", "unchanged": same, "pass": same})
        ic = float(np.nanmean(run.pred.rank(axis=1).corrwith(p.out.rank(axis=1), axis=1)))
        checks.append({"name": "implausible_same_period_ic", "mean_rank_ic": ic, "threshold": 0.5, "pass": not (np.isfinite(ic) and abs(ic) > 0.5)})
    else:
        cut_t = series.index[cut]
        again = series.copy()
        again.loc[again.index > cut_t] = np.random.default_rng(run.seed).normal(size=int((again.index > cut_t).sum()))
        stats_same = bool(np.isclose(vs.sharpe_of(series.loc[:cut_t], run.h), vs.sharpe_of(again.loc[:cut_t], run.h)))
        checks.append({"name": "perturb_after_t_statistics_pipeline", "t": str(cut_t.date()), "unchanged": stats_same, "pass": stats_same,
                       "note": "Returns-only uploads cannot expose model leakage; only Validate's own pipeline is checked"})
    ok = all(c["pass"] for c in checks)
    return {"badge": "pass" if ok else "fail", "checks": checks, "provenance": run.provenance("leakage")}


def block_transfer(run: Run) -> dict:
    p, h = run.p, run.h
    prov = run.provenance("transfer")
    if p.mode == "returns":
        s = run.series
        cut = int(len(s) * 0.6)
        ref, late = vs.sharpe_of(s.iloc[:cut], h), vs.sharpe_of(s.iloc[cut:], h)
        tests = [{"name": "later_period", "sharpe": _f(late)}]
        scope = "later period only (a single return series has no other tickers)"
    else:
        out, cols = p.out, list(p.out.columns)
        half = np.array([vs.ticker_half(str(c)) for c in cols])
        cut = int(len(out) * 0.6)
        early, late_ix = out.index[:cut], out.index[cut:]
        A, B = [c for c, hv in zip(cols, half) if hv == 0], [c for c, hv in zip(cols, half) if hv == 1]
        if len(A) < 4 or len(B) < 4:
            return {"status": "unavailable", "reason": "Need at least 8 tickers to split into two groups", "provenance": prov}
        if p.mode == "model":
            panel = p.panel
            stamp = pd.to_datetime(panel["date"])
            gap = out.index[max(0, cut - h - run.embargo - 1)]
            train = np.flatnonzero(((stamp <= gap) & panel["ticker"].isin(A)).to_numpy())
            X = panel[p.features].to_numpy(dtype=float)
            y = panel["outcome"].to_numpy(dtype=float)
            rest = np.setdiff1d(np.arange(len(panel)), train)
            pr = np.full(len(panel), np.nan)
            pr[rest] = vs._fit_predict(lambda: vs.make_model(run.r["model_type"], run.seed), X, y, train, rest)
            pw = _wide_from_rows(panel, pr, out)
        else:
            pw = run.pred

        def sh(rows, tick):
            s, _ = vs.strategy_series(pw.loc[rows, tick], out.loc[rows, tick], h, run.cost, run.q)
            return vs.sharpe_of(s, h)
        ref = run.sr if p.mode == "model" else sh(early, A)
        tests = [{"name": "other_tickers_same_period", "sharpe": _f(sh(early, B))},
                 {"name": "later_period_same_tickers", "sharpe": _f(sh(late_ix, A))},
                 {"name": "other_tickers_later_period", "sharpe": _f(sh(late_ix, B))}]
        scope = "frozen " + ("model trained on early dates and half the tickers" if p.mode == "model" else "signal, no refit") + "; tickers split by hash into two groups"
    vals = [t["sharpe"] for t in tests]
    ok_all = all(v is not None and v > 0 for v in vals)
    ratio = (min(v for v in vals if v is not None) / ref) if ref and ref > 0 and all(v is not None for v in vals) else None
    status = "pass" if ok_all and ratio is not None and ratio >= 0.5 else ("warn" if ok_all else "fail")
    return {"status": "computed", "scope": scope, "reference_sharpe": _f(ref), "tests": tests, "min_ratio_to_reference": _f(ratio), "min_transfer_sharpe": _f(min(v for v in vals if v is not None)) if any(v is not None for v in vals) else None,
            "outcome": status, "rule": "pass when every transfer Sharpe is positive and at least 50% of the reference", "provenance": prov}


def block_monte_carlo(run: Run) -> dict:
    r = run.series.to_numpy(dtype=float)
    n, draws = len(r), 500
    L = max(2, int(round(math.sqrt(n))))
    rng = np.random.default_rng(run.seed)
    starts = rng.integers(0, n, size=(draws, -(-n // L)))
    idx = ((starts[..., None] + np.arange(L)) % n).reshape(draws, -1)[:, :n]
    sample = r[idx]
    sd = sample.std(axis=1, ddof=1)
    shp = np.where(sd > 1e-12, sample.mean(axis=1) / np.where(sd > 1e-12, sd, 1) * math.sqrt(vs.ann(run.h)), np.nan)
    equity = np.cumprod(1 + sample, axis=1)
    dd = (equity / np.maximum.accumulate(equity, axis=1) - 1).min(axis=1)
    return {"method": "moving_block_bootstrap_numpy", "block_length": L, "draws": draws, "seed": run.seed,
            "sharpe": _dist(shp), "max_drawdown": {**_dist(dd), "worst_5pct": float(np.percentile(dd, 5))},
            "prob_sharpe_not_positive": float(np.nanmean(shp <= 0)), "observed_max_drawdown": max_drawdown(np.cumprod(1 + r)),
            "provenance": run.provenance("monte_carlo")}


# ---------------------------------------------------------------- verdict and autopsy

def _autopsy(run: Run, b: dict, label: str = "") -> dict:
    causes = []
    dsr, trials = b["deflated_sharpe"], _trial_count(run)
    if dsr.get("status") == "computed":
        causes.append({"cause": "trial_count", "severity": float(np.clip(1 - dsr["dsr"], 0, 1)) * (1.0 if trials > 1 else 0.5),
                       "evidence": f"DSR {dsr['dsr']:.2f} at {trials} trial(s)", "phrase": f"{trials} trial{'s' if trials != 1 else ''} (DSR {dsr['dsr']:.2f})"})
    leak = b["leakage"]
    bad = [c["name"] for c in leak["checks"] if not c["pass"]]
    causes.append({"cause": "leakage", "severity": 1.0 if bad else 0.0, "evidence": ("failed: " + ", ".join(bad)) if bad else "all perturbation checks passed",
                   "phrase": "look-ahead leakage (" + ", ".join(bad) + ")" if bad else ""})
    s = run.series
    seg = np.array_split(np.arange(len(s)), 4)
    totals = [float(s.iloc[i].sum()) for i in seg]
    total = sum(totals)
    best_i = int(np.argmax(totals))
    share = totals[best_i] / total if total > 0 else 1.0
    span = f"{s.index[seg[best_i][0]].year}-{s.index[seg[best_i][-1]].year}"
    seg_sr = ", ".join(f"{vs.sharpe_of(s.iloc[i], run.h):.2f}" for i in seg)
    if total > 0:
        causes.append({"cause": "regime_dependence", "severity": float(np.clip((share - 0.5) / 0.4, 0, 1)),
                       "evidence": f"quarter-of-sample {span} supplies {share:.0%} of total profit; segment Sharpes " + seg_sr,
                       "phrase": f"one period ({span}) supplying {share:.0%} of profit"})
    else:
        causes.append({"cause": "regime_dependence", "severity": 0.0, "evidence": f"total P&L is not positive; losses spread across periods (segment Sharpes {seg_sr})", "phrase": ""})
    if run.turnover is not None and float(np.mean(run.turnover)) > 0:
        gross, _ = vs.strategy_series(run.pred, run.p.out, run.h, 0.0, run.q)
        be = float(gross.mean() / (np.mean(run.turnover) / 1e4))
        gsr, turn = vs.sharpe_of(gross, run.h), float(np.mean(run.turnover))
        flips = bool(np.isfinite(gsr) and gsr > 0 and run.sr < 0)
        sev = 1.0 if flips else (float(np.clip(1 - be / 20, 0, 1)) if be > 0 else 1.0)
        phrase = (f"Gross Sharpe {gsr:.2f} turns to {run.sr:.2f} after {run.cost:g} bps costs: breakeven is {be:.1f} bps on {turn:.0%} turnover per period"
                  if flips else f"trading costs (breakeven {be:.0f} bps)")
        causes.append({"cause": "cost_sensitivity", "severity": sev, "gross_sharpe": _f(gsr), "avg_turnover": turn,
                       "evidence": f"breakeven cost {be:.1f} bps per unit turnover; gross Sharpe {gsr:.2f}, net {run.sr:.2f}", "phrase": phrase, "breakeven_bps": be,
                       "sharpe_by_cost_bps": {str(c): _f(vs.sharpe_of(vs.strategy_series(run.pred, run.p.out, run.h, c, run.q)[0], run.h)) for c in COST_GRID}})
    pl = b["plateau"]
    if pl.get("status") == "computed":
        causes.append({"cause": "parameter_cliff", "severity": 0.45 if pl["label"] == "cliff" else 0.05, "evidence": f"neighbourhood label: {pl['label']}",
                       "phrase": "a parameter cliff (nearby settings lose most of the edge)"})
    tr = b["transfer"]
    if tr.get("status") == "computed":
        ratio = tr["min_ratio_to_reference"]
        vals = [t["sharpe"] for t in tr["tests"] if t["sharpe"] is not None]
        weakest = min(vals) if vals else None
        sev = 1.0 if ratio is None else float(np.clip(1 - ratio, 0, 1))
        ev = ("no finite transfer Sharpe" if weakest is None else f"weakest transfer Sharpe {weakest:.2f} vs reference {tr['reference_sharpe'] if tr['reference_sharpe'] is None else round(tr['reference_sharpe'], 2)}"
              + (f" ({ratio:.0%} of reference)" if ratio is not None else ""))
        causes.append({"cause": "single_asset_luck", "severity": sev, "evidence": ev,
                       "phrase": "an edge that does not transfer to other tickers or later dates"})
    st = b["stability"]
    if st.get("status") == "computed":
        causes.append({"cause": "seed_luck", "severity": 0.7 if st["flag"] else 0.05, "evidence": f"best/median seed Sharpe = {st['best_over_median']}",
                       "phrase": f"seed luck (best seed {st['best_over_median']:.2f}x the median)" if st["best_over_median"] else "seed luck"})
    causes = sorted((c for c in causes), key=lambda c: -c["severity"])
    main = [c for c in causes if c["severity"] > 0.5][:2]
    sr = run.sr
    if main and label == "FAILED":
        sentence = "Fails because " + (main[0]["phrase"] if main[0]["cause"] == "cost_sensitivity" else f"Sharpe {sr:.1f} is driven by " + main[0]["phrase"]) + (
            "; also " + main[1]["phrase"] if len(main) > 1 else "") + "."
    elif main:
        sentence = f"Sharpe {sr:.1f} is mostly explained by " + " and ".join(c["phrase"] for c in main) + "."
    else:
        sentence = f"No dominant overfitting cause found: Sharpe {sr:.1f} holds up against trials, regimes, costs and transfer."
    return {"sentence": sentence, "ranked_causes": causes, "provenance": run.provenance("autopsy")}


def _verdict(run: Run, b: dict) -> dict:
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})
    c = b["controls"]
    add("beats_best_control", "pass" if c["beats_best_control"] else "fail",
        f"Sharpe {run.sr:.2f} vs best control {c['best_control']} {c['best_control_sharpe']:.2f}")
    if c["shuffled"]["status"] == "computed":
        pv = c["shuffled"]["p_value"]
        add("shuffled_signal_p", "pass" if pv <= 0.05 else ("warn" if pv <= 0.15 else "fail"), f"p = {pv:.3f} over {c['shuffled']['permutations']} permutations")
    d = b["deflated_sharpe"]
    if d.get("status") == "computed":
        add("deflated_sharpe", "pass" if d["dsr"] >= 0.95 else ("warn" if d["dsr"] >= 0.5 else "fail"), f"DSR {d['dsr']:.2f} at {d['trials']} trial(s)")
    pb = b["pbo"]
    if pb.get("status") == "computed":
        add("pbo", "pass" if pb["pbo"] <= 0.3 else ("warn" if pb["pbo"] <= 0.5 else "fail"), f"PBO {pb['pbo']:.2f}")
    m = b["min_backtest_length"]
    add("min_backtest_length", "pass" if m["sufficient"] else "warn",
        f"{m['observed_years']:.1f} years observed vs {m['min_years_required']:.1f} required" if m["min_years_required"] else "no positive Sharpe to size a minimum length")
    cp = b["cpcv"]["distribution"]
    if cp.get("n"):
        add("cpcv", "pass" if cp["share_positive"] >= 0.8 and cp["p5"] > 0 else ("warn" if cp["share_positive"] >= 0.5 else "fail"),
            f"{cp['share_positive']:.0%} of splits/paths positive, 5th percentile Sharpe {cp['p5']:.2f}")
    st = b["stability"]
    if st.get("status") == "computed":
        add("multi_seed", "warn" if st["flag"] else "pass", f"{st['seeds']} seeds, best/median {st['best_over_median']}")
    pl = b["plateau"]
    if pl.get("status") == "computed":
        add("plateau", "pass" if pl["label"] == "plateau" else "warn", pl["label"])
    add("leakage", "pass" if b["leakage"]["badge"] == "pass" else "fail", "badge " + b["leakage"]["badge"])
    tr = b["transfer"]
    if tr.get("status") == "computed":
        add("transfer", tr["outcome"], f"weakest transfer = {tr['min_ratio_to_reference']:.0%} of reference" if tr["min_ratio_to_reference"] is not None else "a transfer Sharpe was not positive")
    mc = b["monte_carlo"]["sharpe"]
    add("monte_carlo", "pass" if mc.get("p5", -1) > 0 else ("warn" if mc.get("p50", -1) > 0 else "fail"), f"bootstrap Sharpe 5th/50th percentile {mc.get('p5', float('nan')):.2f}/{mc.get('p50', float('nan')):.2f}")
    fails = [x for x in checks if x["status"] == "fail"]
    warns = [x for x in checks if x["status"] == "warn"]
    core = {x["name"]: x["status"] for x in checks}
    if core["leakage"] == "fail" or core["beats_best_control"] == "fail" or len(fails) >= 2:
        label = "FAILED"
    elif not fails and len(warns) <= 1 and core["beats_best_control"] == "pass" and core.get("deflated_sharpe", "pass") == "pass":
        label = "HELD UP"
    else:
        label = "MIXED"
    return {"label": label, "checks": checks, "fails": len(fails), "warnings": len(warns),
            "rule": "FAILED: leakage, cannot beat the best control, or 2+ failed checks. HELD UP: no failed check, at most one warning, beats the best control and DSR passes. Otherwise MIXED."}


def _receipt(run: Run, request: dict) -> dict:
    p = run.p
    data_bytes = p.frame.to_csv(index=False).encode()
    extras = {k: _hash_json(request[k]) for k in ("source_result",) if request.get(k)}
    settings = {k: v for k, v in request.items() if k != "source_result"}
    settings.update({f"{k}_sha256": v for k, v in extras.items()})
    settings_bytes = json.dumps(settings, sort_keys=True, default=str).encode()
    root = Path(__file__).parent
    code = hashlib.sha256(b"".join((root / f).read_bytes() for f in CODE_FILES)).hexdigest()
    data_hash, settings_hash = hashlib.sha256(data_bytes).hexdigest(), hashlib.sha256(settings_bytes).hexdigest()
    total = hashlib.sha256("|".join([data_hash, settings_hash, str(run.seed), code]).encode()).hexdigest()
    return {"receipt_sha256": total, "data_sha256": data_hash, "settings_sha256": settings_hash, "seed": run.seed,
            "code_version_sha256": code, "rerun": "POST the same settings with the same upload to reproduce this hash", "provenance": run.provenance("receipt")}


def _hash_json(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def _improve(run: Run) -> dict:
    p = run.p
    prov = run.provenance("improve")
    if run.pred is None or p.out is None:
        return {"status": "unavailable", "reason": "Improve my strategy needs predictions or a feature panel with outcomes", "provenance": prov}
    if not run.r.get("improve_strategy", True):
        return {"status": "skipped", "provenance": prov}
    out = vs.meta_label_overlay(run.pred, p.out, run.h, run.embargo, run.cost, run.q, run.seed)
    out["provenance"] = prov
    out["feature_id"] = "04"
    return out


def _data_quality(run: Run) -> dict:
    from .uploads import split_anomalies
    warnings = []
    if run.p.mode == "returns":
        warnings += split_anomalies(run.p.returns)
    else:
        for t in run.p.out.columns:
            warnings += split_anomalies(run.p.out[t], str(t))
    idx = pd.DatetimeIndex(run.series.index)
    gaps = pd.Series(idx).diff().dt.days.dropna()
    if len(gaps) and gaps.max() > 7:
        warnings.append(f"Calendar gap of {int(gaps.max())} days present; used as supplied, not filled")
    return {"warnings": warnings[:20], "split_adjustment_rule": "abs daily move > 40% followed by an opposite move of at least a quarter its size",
            "calendar_handling": "No gap filling or forward-fill; periods sampled every horizon rows", "provenance": run.provenance("data_quality")}


def run_validate(request: dict) -> dict:
    report_progress(5, "Preparing inputs")
    prep = prepare(request)
    run = Run(request, prep)
    run.build_series()
    report_progress(40, "Controls")
    b: dict[str, Any] = {}
    b["cpcv"] = block_cpcv(run)
    b["pbo"] = block_pbo(run)
    b["deflated_sharpe"] = block_dsr(run)
    b["min_backtest_length"] = block_minbtl(run, b["deflated_sharpe"])
    b["controls"] = block_controls(run)
    report_progress(55, "Stability and plateau")
    b["stability"] = block_stability(run)
    b["plateau"] = block_plateau(run)
    b["leakage"] = block_leakage(run)
    report_progress(75, "Transfer and Monte Carlo")
    b["transfer"] = block_transfer(run)
    b["monte_carlo"] = block_monte_carlo(run)
    verdict = _verdict(run, b)
    b["autopsy"] = _autopsy(run, b, verdict["label"])
    b["improve"] = _improve(run)
    b["data_quality"] = _data_quality(run)
    b["receipt"] = _receipt(run, request)
    verdict["headline"] = b["autopsy"]["sentence"]
    verdict["strategy_sharpe"] = run.sr
    verdict["best_control"] = b["controls"]["best_control"]
    verdict["leakage_badge"] = b["leakage"]["badge"]
    verdict["provenance"] = run.provenance("verdict")
    cards = [{"label": "Verdict", "value": verdict["label"], "unit": ""}, {"label": "Sharpe", "value": run.sr, "unit": "annualised"},
             {"label": "Best control", "value": b["controls"]["best_control"], "unit": ""},
             {"label": "Leakage", "value": b["leakage"]["badge"], "unit": ""}]
    report_progress(95, "Assembling verdict")
    return clean_json({"feature_id": "feature_validate", "status": "ok", "summary_cards": cards, "charts": {}, "tables": {},
                       "alerts": [{"level": "warning", "message": w} for w in b["data_quality"]["warnings"][:5]],
                       "meta": {"mode": prep.mode, "input": prep.source}, "verdict": verdict, "sections": b})


def run_meta_label_upload(request: dict) -> dict:
    """Feature 04 on an uploaded predictions set: meta-label filter and sizing beside the unfiltered strategy."""
    item = uploads.get_upload(request["upload_id"], ("predictions",))
    frame = item.frame
    if "outcome" not in frame.columns:
        raise ValueError("predictions upload needs an outcome column for meta-labelling")
    h = int(request.get("max_holding_period") or 1)
    pred, out = vs.wide(frame, "prediction"), vs.wide(frame, "outcome")
    pred = pred.reindex(index=out.index, columns=out.columns)
    res = vs.meta_label_overlay(pred, out, h, int(request.get("embargo_period", 5)), float(request.get("cost_bps", 5.0)), vs.DEFAULT_Q)
    if res.get("status") != "ok":
        raise ValueError(res.get("reason", "Meta-labelling unavailable"))
    from .common import response, summary
    base = res["rows"][0]
    return response("04", [summary("Unfiltered Sharpe", base["sharpe"]), summary("Best variant", res["best_variant"]),
                           summary("Sharpe change", res["sharpe_delta"])],
                    charts={"meta_label_probability_distribution": res["probabilities"], "label_method_comparison": res["rows"]},
                    tables={"label_method_comparison": res["rows"]},
                    meta={"method": "meta_label_on_uploaded_predictions", "upload": item.upload_id, "improve": {k: v for k, v in res.items() if k != "probabilities"}})
