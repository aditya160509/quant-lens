"""Feature 07: Causal Identification Engine.

Four designs, each on proper estimators:

* Difference-in-differences: TWFE (pyfixest), Callaway-Sant'Anna (differences),
  Sun-Abraham interaction-weighted and Gardner two-stage (pyfixest), a
  Goodman-Bacon decomposition, a parallel-trends Wald pre-test, placebo
  treatment dates, propensity-score matched controls and covariate balance.
* Event study with abnormal returns: market / FF3 / FF5 / Dimson models, CAR
  and BHAR, cross-sectional t, Patell, BMP and Kolari-Pynnonen tests,
  pre-event drift, post-event continuation and a calendar-time alpha.
* Regression discontinuity on a cross-sectional running variable: rdrobust
  (CCT MSE-optimal bandwidth, robust bias-corrected inference), rddensity
  manipulation test, covariate continuity, placebo cutoffs, bandwidth
  sensitivity and donut holes.
* Instrumental variables: 2SLS / LIML (linearmodels) with first-stage
  diagnostics, Staiger-Stock and Lee et al. (2022) thresholds, a weak-IV-robust
  Anderson-Rubin confidence set, over-identification and endogeneity tests.
"""

from __future__ import annotations

import contextlib
import io
import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .data_loader import (
    UnknownSymbolsError,
    load_event_upload,
    load_factor_returns,
    load_instrument_upload,
    normalize_symbol,
    ohlcv_matrices,
    parse_symbols,
    point_in_time_fundamental,
    static_sectors,
)
from .panel import build_panel, compute_control, compute_signal

DESIGNS = ["did", "event_study", "rdd", "iv"]
OUTCOMES = ["return", "realized_vol", "dollar_volume", "spread"]


def run_causal(payload: dict[str, Any]) -> dict[str, Any]:
    raw = str(payload.get("identification_design") or "event_study").lower()
    designs = DESIGNS if raw == "all" else [d.strip() for d in raw.split(",") if d.strip()]
    bad = [d for d in designs if d not in DESIGNS]
    if bad:
        raise ValueError(f"identification_design must be any of {DESIGNS} or 'all'")
    runners = {"did": run_did, "event_study": run_event_study, "rdd": run_rdd, "iv": run_iv}
    summary: list[dict[str, Any]] = []
    charts: dict[str, Any] = {}
    tables: dict[str, Any] = {}
    caveats: list[str] = []
    for d in designs:
        try:
            out = runners[d](payload)
        except (ValueError, UnknownSymbolsError) as exc:
            tables[f"{d}_status"] = [{"design": d, "status": "not run", "reason": str(exc)}]
            continue
        summary += out["summary"]
        charts.update(out["charts"])
        tables.update(out["tables"])
        caveats += out.get("caveats", [])
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"designs": designs, "research_caveats": caveats}}


# ---------------------------------------------------------------------------
# shared data


def _events(payload: dict[str, Any]) -> pd.DataFrame:
    """Treatment events from an uploaded file, or treated tickers + one date."""

    ev = load_event_upload(payload.get("event_csv_path") or payload.get("event_upload_path"))
    if not ev.empty:
        return ev[["ticker", "treatment_date"]].drop_duplicates()
    units = payload.get("treated_units") or payload.get("treated_unit")
    date = payload.get("treatment_date")
    if not units or not date:
        raise ValueError("Provide an event file (ticker, treatment_date) or treated unit(s) with a treatment date.")
    tickers = [normalize_symbol(u) for u in (units if isinstance(units, list) else str(units).replace(";", ",").split(",")) if str(u).strip()]
    return pd.DataFrame({"ticker": tickers, "treatment_date": pd.Timestamp(date)})


def _monthly_outcome(daily: dict[str, pd.DataFrame], outcome: str) -> pd.DataFrame:
    close = daily["Close"]
    if outcome == "return":
        return close.resample("ME").last().pct_change(fill_method=None)
    if outcome == "realized_vol":
        return close.pct_change(fill_method=None).resample("ME").std() * math.sqrt(21)
    if outcome == "dollar_volume":
        return np.log((close * daily["Volume"]).resample("ME").sum().replace(0, np.nan))
    if outcome == "spread":
        from .panel import _corwin_schultz
        return _corwin_schultz(daily["High"], daily["Low"]).resample("ME").mean()
    raise ValueError(f"outcome must be one of {OUTCOMES}")


def _characteristics(daily: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Pre-treatment covariates available for every asset and period."""

    close_m = daily["Close"].resample("ME").last()
    rets = close_m.pct_change(fill_method=None)
    symbols = list(close_m.columns)
    ctx = {"close_m": close_m, "returns": rets, "daily": daily, "market_cap": pd.DataFrame(index=rets.index, columns=symbols), "factors": _monthly_ff(rets.index), "symbols": symbols, "dates": rets.index}
    shares = point_in_time_fundamental("Ordinary Shares Number", rets.index, symbols)
    ctx["market_cap"] = close_m * shares
    out = {
        "log_dollar_volume": np.log((daily["Close"] * daily["Volume"]).resample("ME").sum().replace(0, np.nan)),
        "momentum": compute_signal("momentum", ctx),
        "volatility": rets.rolling(12, min_periods=8).std(),
        "beta": compute_control("beta", ctx),
        "size": compute_control("size", ctx),
    }
    return out


def _monthly_ff(index: pd.DatetimeIndex) -> pd.DataFrame:
    f = load_factor_returns()
    if f.empty:
        return pd.DataFrame(index=index)
    return f.set_index("date").resample("ME").apply(lambda x: (1 + x).prod() - 1).reindex(index)


# ---------------------------------------------------------------------------
# difference-in-differences


def run_did(payload: dict[str, Any]) -> dict[str, Any]:
    import pyfixest as pf

    events = _events(payload)
    outcome = str(payload.get("outcome_variable") or "return").lower()
    controls_pool = parse_symbols({**payload, "max_symbols": payload.get("max_symbols") or 300}, default_limit=300)
    treated = sorted(set(events["ticker"]))
    missing = [t for t in treated if t not in set(parse_symbols({"universe": ",".join(treated)}))]
    if missing:
        raise UnknownSymbolsError(missing)
    symbols = sorted(set(controls_pool) | set(treated))
    lookback = int(payload.get("lookback_days") or 3650)
    daily = ohlcv_matrices(symbols, lookback)
    y = _monthly_outcome(daily, outcome)
    months = y.index
    pre, post = int(payload.get("pre_period_months") or 12), int(payload.get("post_period_months") or 12)
    anticipation = int(payload.get("anticipation_months") or 0)

    first = events.groupby("ticker")["treatment_date"].min()
    cohort = pd.Series(0, index=y.columns, dtype=int)
    tpos = {m: i + 1 for i, m in enumerate(months)}
    for tk, d in first.items():
        pos = months.searchsorted(pd.Timestamp(d) + pd.offsets.MonthEnd(0))
        if 0 < pos < len(months):
            cohort[tk] = pos + 1 - anticipation
    treated_units = cohort[cohort > 0].index.tolist()
    if not treated_units:
        raise ValueError("No treated unit has a treatment date inside the data window.")
    lo = max(1, cohort[cohort > 0].min() - pre)
    hi = min(len(months), cohort[cohort > 0].max() + post)

    chars = _characteristics(daily)
    matching = str(payload.get("control_group") or "all_untreated").lower()
    never = [c for c in y.columns if cohort[c] == 0]
    balance_before = _balance(chars, treated_units, never, cohort, months)
    if matching == "matched":
        never = _propensity_match(chars, treated_units, never, cohort, months, int(payload.get("matches_per_treated") or 5))
    balance_after = _balance(chars, treated_units, never, cohort, months) if matching == "matched" else pd.DataFrame()

    units = treated_units + never
    long = y[units].iloc[lo - 1:hi].stack().rename("y").reset_index()
    long.columns = ["date", "unit", "y"]
    long["time"] = long["date"].map(tpos)
    long["g"] = long["unit"].map(cohort).astype(int)
    long["treat"] = ((long["g"] > 0) & (long["time"] >= long["g"])).astype(int)
    long = long.dropna(subset=["y"])
    long["unit_id"] = pd.factorize(long["unit"])[0]
    vcov = {"CRV1": "unit_id"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        twfe = pf.feols("y ~ treat | unit_id + time", data=long, vcov=vcov)
    twfe_row = _pf_row(twfe, "treat", "TWFE")

    rel = np.where(long["g"] > 0, (long["time"] - long["g"]).clip(-pre, post), -1)
    long["rel"] = rel
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dyn = pf.feols("y ~ i(rel, ref=-1) | unit_id + time", data=long, vcov=vcov)
    dyn_t = dyn.tidy()
    event_rows = [{"event_time": int(float(i.split("::")[1])), "estimate": r["Estimate"], "se": r["Std. Error"], "lower_95": r["2.5%"], "upper_95": r["97.5%"], "estimator": "TWFE dynamic"} for i, r in dyn_t.iterrows() if i.startswith("rel::")]
    pre_names = [i for i in dyn_t.index if i.startswith("rel::") and int(float(i.split("::")[1])) <= -2]
    parallel = {"available": False}
    n_treated = len(treated_units)
    if pre_names and n_treated < 2 * len(pre_names):
        # A cluster-robust covariance built from fewer treated clusters than restrictions is
        # rank-deficient and the joint Wald test over-rejects; fall back to heteroskedasticity-robust.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dyn = pf.feols("y ~ i(rel, ref=-1) | unit_id + time", data=long, vcov="hetero")
        pretest_vcov = "heteroskedasticity-robust (too few treated clusters for a clustered joint test)"
    else:
        pretest_vcov = "clustered by unit"
    if pre_names:
        coef_names = list(dyn.coef().index)
        r_mat = np.zeros((len(pre_names), len(coef_names)))
        for j, name in enumerate(pre_names):
            r_mat[j, coef_names.index(name)] = 1
        w = dyn.wald_test(R=r_mat, distribution="chi2")
        parallel = {"available": True, "chi2_stat": float(w["statistic"]), "p_value": float(w["pvalue"]), "pre_periods": len(pre_names), "vcov": pretest_vcov, "verdict": "parallel pre-trends not rejected" if float(w["pvalue"]) >= 0.05 else "pre-trends differ: parallel trends violated"}

    estimates = [twfe_row]
    cs_event = pd.DataFrame()
    staggered = long.loc[long["g"] > 0, "g"].nunique() > 1
    try:
        cs_simple, cs_event, cs_group = _callaway_santanna(long, str(payload.get("cs_control_group") or "never_treated"))
        estimates.append({"estimator": "Callaway-Sant'Anna (simple ATT)", **cs_simple})
    except Exception as exc:  # the estimator needs >= 2 periods per cohort and a valid control group
        cs_group = pd.DataFrame()
        estimates.append({"estimator": "Callaway-Sant'Anna", "status": f"not estimable: {exc}"})
    sa_event = pd.DataFrame()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sa = pf.event_study(data=long.assign(g=long["g"]), yname="y", idname="unit_id", tname="time", gname="g", estimator="saturated", cluster="unit_id")
            agg = sa.aggregate(weighting="shares")
        sa_event = agg.reset_index().rename(columns={"period": "event_time", "Estimate": "estimate", "Std. Error": "se", "2.5%": "lower_95", "97.5%": "upper_95"})
        post_rows = sa_event[sa_event["event_time"] >= 0]
        estimates.append({"estimator": "Sun-Abraham (IW, post average)", "estimate": float(post_rows["estimate"].mean()), "se": float(np.sqrt((post_rows["se"] ** 2).mean() / max(len(post_rows), 1))), "note": "average of post-period interaction-weighted effects"})
    except Exception as exc:
        estimates.append({"estimator": "Sun-Abraham", "status": f"not estimable: {exc}"})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g2 = pf.did2s(long, yname="y", first_stage="~ 0 | unit_id + time", second_stage="~ treat", treatment="treat", cluster="unit_id")
        estimates.append(_pf_row(g2, "treat", "Gardner two-stage (did2s)"))
    except Exception as exc:
        estimates.append({"estimator": "did2s", "status": f"not estimable: {exc}"})

    bacon = goodman_bacon(long) if staggered or len(never) else pd.DataFrame()
    placebo = _did_placebo(long, int(payload.get("bootstrap_replications") or 500), twfe_row["estimate"])

    tables = {
        "did_estimates": estimates,
        "twfe_regression": [twfe_row],
        "parallel_trends_pretest": [parallel],
        "callaway_santanna_att": cs_group,
        "goodman_bacon_decomposition": bacon,
        "did_placebo_treatment": [placebo["summary"]],
        "covariate_balance": balance_before,
        "covariate_balance_matched": balance_after,
        "did_sample": [{"treated_units": len(treated_units), "control_units": len(never), "cohorts": int(long.loc[long["g"] > 0, "g"].nunique()), "periods": int(long["time"].nunique()), "outcome": outcome, "control_group": matching, "anticipation_months": anticipation, "staggered": bool(staggered)}],
    }
    charts = {
        "did_event_study": pd.DataFrame(event_rows),
        "callaway_santanna_event": cs_event,
        "sun_abraham_event": sa_event,
        "goodman_bacon_scatter": bacon,
        "did_placebo_distribution": [{"estimate": v} for v in placebo["null"]],
    }
    summary = [{"label": "DiD (TWFE)", "value": twfe_row["estimate"]}, {"label": "DiD t", "value": twfe_row["t_stat"]}, {"label": "Pre-trend p", "value": parallel.get("p_value")}]
    return {"summary": summary, "charts": charts, "tables": tables, "caveats": []}


def _pf_row(fit: Any, term: str, name: str) -> dict[str, Any]:
    t = fit.tidy().loc[term]
    return {"estimator": name, "estimate": float(t["Estimate"]), "se": float(t["Std. Error"]), "t_stat": float(t["t value"]), "p_value": float(t["Pr(>|t|)"]), "lower_95": float(t["2.5%"]), "upper_95": float(t["97.5%"]), "nobs": int(fit._N)}


def _callaway_santanna(long: pd.DataFrame, control: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    from differences import ATTgt

    data = long.assign(cohort=long["g"].where(long["g"] > 0)).set_index(["unit_id", "time"])[["y", "cohort"]]
    att = ATTgt(data=data, cohort_column="cohort")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        att.fit(formula="y", est_method="reg", control_group=control, progress_bar=False)
        simple = att.aggregate("simple")
        event = att.aggregate("event")
        group = att.aggregate("cohort")

    def flat(df: pd.DataFrame, index_name: str) -> pd.DataFrame:
        out = pd.DataFrame({index_name: df.index, "estimate": df.iloc[:, 0].to_numpy(), "se": df.iloc[:, 1].to_numpy(), "lower_95": df.iloc[:, 2].to_numpy(), "upper_95": df.iloc[:, 3].to_numpy()})
        return out

    s = simple.iloc[0]
    return (
        {"estimate": float(s.iloc[0]), "se": float(s.iloc[1]), "t_stat": float(s.iloc[0] / s.iloc[1]) if s.iloc[1] else np.nan, "lower_95": float(s.iloc[2]), "upper_95": float(s.iloc[3]), "control_group": control},
        flat(event, "event_time"),
        flat(group, "cohort"),
    )


def goodman_bacon(long: pd.DataFrame) -> pd.DataFrame:
    """Goodman-Bacon (2021) decomposition of TWFE into 2x2 DiDs (balanced panel, no covariates).

    Weights follow equations (10a)-(10c) of the paper and are normalised to
    sum to one; each 2x2 estimate is the simple difference of pre/post mean
    differences over that comparison's window.
    """

    wide = long.pivot_table(index="unit", columns="time", values="y")
    wide = wide.dropna()  # balanced panel required
    if wide.empty:
        return pd.DataFrame()
    g = long.drop_duplicates("unit").set_index("unit")["g"].reindex(wide.index)
    times = np.array(sorted(wide.columns))
    groups = sorted(x for x in g.unique() if x > 0)
    share = {k: float((g == k).mean()) for k in [0, *groups]}
    dbar = {k: float(np.mean(times >= k)) for k in groups}

    def mean_y(k: int, mask: np.ndarray) -> float:
        return float(wide.loc[g == k, times[mask]].to_numpy().mean())

    rows = []
    for k in groups:
        if share[0] > 0:
            pre, post = times < k, times >= k
            est = (mean_y(k, post) - mean_y(k, pre)) - (mean_y(0, post) - mean_y(0, pre))
            nk = share[k] / (share[k] + share[0])
            w = (share[k] + share[0]) ** 2 * nk * (1 - nk) * dbar[k] * (1 - dbar[k])
            rows.append({"comparison": "treated vs never treated", "treated_cohort": k, "control_cohort": "never", "estimate": est, "raw_weight": w})
        for l in groups:
            if l <= k:
                continue
            nkl = share[k] / (share[k] + share[l])
            # early k vs late l (l not yet treated): window before l
            win = times < l
            pre, post = win & (times < k), win & (times >= k)
            if pre.any() and post.any():
                est = (mean_y(k, post) - mean_y(k, pre)) - (mean_y(l, post) - mean_y(l, pre))
                w = ((share[k] + share[l]) * (1 - dbar[l])) ** 2 * nkl * (1 - nkl) * ((dbar[k] - dbar[l]) / (1 - dbar[l])) * ((1 - dbar[k]) / (1 - dbar[l]))
                rows.append({"comparison": "early vs late (late as control)", "treated_cohort": k, "control_cohort": l, "estimate": est, "raw_weight": w})
            # late l vs early k (k already treated): window after k
            win = times >= k
            pre, post = win & (times < l), win & (times >= l)
            if pre.any() and post.any():
                est = (mean_y(l, post) - mean_y(l, pre)) - (mean_y(k, post) - mean_y(k, pre))
                w = ((share[k] + share[l]) * dbar[k]) ** 2 * nkl * (1 - nkl) * (dbar[l] / dbar[k]) * ((dbar[k] - dbar[l]) / dbar[k])
                rows.append({"comparison": "late vs early (already-treated as control)", "treated_cohort": l, "control_cohort": k, "estimate": est, "raw_weight": w})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["weight"] = out["raw_weight"] / out["raw_weight"].sum()
    out["contribution"] = out["weight"] * out["estimate"]
    out["twfe_implied"] = out["contribution"].sum()
    out["forbidden_comparison"] = out["comparison"].str.startswith("late vs early")
    return out.drop(columns="raw_weight")


def _did_placebo(long: pd.DataFrame, reps: int, real: float, seed: int = 5) -> dict[str, Any]:
    """Assign fake treatment dates to control units only and re-estimate TWFE."""

    import pyfixest as pf

    controls = long[long["g"] == 0].copy()
    units = controls["unit"].unique()
    n_treat = max(1, int(long.loc[long["g"] > 0, "unit"].nunique()))
    if len(units) < 2 * n_treat + 2:
        return {"summary": {"available": False, "reason": "not enough control units for placebo treatment"}, "null": []}
    times = np.sort(controls["time"].unique())
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(min(int(reps), 500)):
        fake = rng.choice(units, size=n_treat, replace=False)
        date = int(rng.choice(times[len(times) // 4: 3 * len(times) // 4]))
        df = controls.assign(treat=(controls["unit"].isin(fake) & (controls["time"] >= date)).astype(int))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            null.append(float(pf.feols("y ~ treat | unit_id + time", data=df, vcov="iid").coef()["treat"]))
    null_arr = np.asarray(null)
    p = float((1 + np.sum(np.abs(null_arr) >= abs(real))) / (1 + len(null_arr)))
    return {"summary": {"available": True, "real_estimate": real, "placebo_p_value": p, "replications": len(null_arr), "placebo_mean": float(null_arr.mean()), "placebo_sd": float(null_arr.std())}, "null": null_arr.tolist()}


def _pre_values(chars: dict[str, pd.DataFrame], units: list[str], cohort: pd.Series, months: pd.DatetimeIndex, default_pos: int) -> pd.DataFrame:
    rows = {}
    for u in units:
        pos = (cohort[u] - 2) if cohort.get(u, 0) > 0 else default_pos
        pos = int(min(max(pos, 0), len(months) - 1))
        rows[u] = {name: mat[u].reindex(months).iloc[pos] if u in mat else np.nan for name, mat in chars.items()}
    return pd.DataFrame(rows).T


def _balance(chars: dict[str, pd.DataFrame], treated: list[str], controls: list[str], cohort: pd.Series, months: pd.DatetimeIndex) -> pd.DataFrame:
    ref = int(np.median([cohort[t] for t in treated])) - 2
    tv = _pre_values(chars, treated, cohort, months, ref)
    cv = _pre_values(chars, controls, cohort, months, ref)
    rows = []
    for c in tv.columns:
        a, b = pd.to_numeric(tv[c], errors="coerce").dropna(), pd.to_numeric(cv[c], errors="coerce").dropna()
        if len(a) == 0 or len(b) == 0:
            continue
        pooled = math.sqrt((a.var(ddof=1) if len(a) > 1 else 0) / 2 + b.var(ddof=1) / 2) if len(b) > 1 else np.nan
        smd = (a.mean() - b.mean()) / pooled if pooled else np.nan
        rows.append({"covariate": c, "treated_mean": a.mean(), "control_mean": b.mean(), "standardized_mean_difference": smd, "imbalanced": bool(abs(smd) > 0.1) if np.isfinite(smd) else None})
    return pd.DataFrame(rows)


def _propensity_match(chars: dict[str, pd.DataFrame], treated: list[str], pool: list[str], cohort: pd.Series, months: pd.DatetimeIndex, k: int) -> list[str]:
    """Nearest-neighbour propensity-score matching (logit, without replacement)."""

    import statsmodels.api as sm

    ref = int(np.median([cohort[t] for t in treated])) - 2
    x = pd.concat([_pre_values(chars, treated, cohort, months, ref), _pre_values(chars, pool, cohort, months, ref)]).apply(pd.to_numeric, errors="coerce")
    usable = [c for c in x.columns if x[c].notna().mean() > 0.8]
    x = x[usable].dropna()
    d = pd.Series([1.0 if u in treated else 0.0 for u in x.index], index=x.index)
    if d.sum() == 0 or (1 - d).sum() < k:
        return pool
    z = (x - x.mean()) / x.std().replace(0, 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ps = sm.Logit(d, sm.add_constant(z)).fit(disp=0, maxiter=200).predict(sm.add_constant(z))
    available = set(d[d == 0].index)
    chosen: list[str] = []
    for t in d[d == 1].index:
        cands = ps[list(available)].sub(ps[t]).abs().nsmallest(k).index.tolist()
        chosen += cands
        available -= set(cands)
    return chosen


# ---------------------------------------------------------------------------
# event study with abnormal returns

MODELS = {"market": ["mkt"], "ff3": ["mkt_rf", "smb", "hml"], "ff5": ["mkt_rf", "smb", "hml", "rmw", "cma"], "dimson": ["mkt", "mkt_lag"]}


def _parse_window(raw: Any) -> tuple[int, int]:
    if isinstance(raw, (list, tuple)):
        return int(raw[0]), int(raw[1])
    text = str(raw or "-1,1").strip("()[] ")
    a, b = (int(x) for x in text.split(","))
    return a, b


def run_event_study(payload: dict[str, Any]) -> dict[str, Any]:
    events = _events(payload)
    model = str(payload.get("benchmark_model") or "market").lower()
    if model not in MODELS:
        raise ValueError(f"benchmark_model must be one of {list(MODELS)}")
    est_len = int(payload.get("estimation_window") or 250)
    win = _parse_window(payload.get("event_window") or "-1,1")
    contamination = int(payload.get("contamination_days") or 0)
    ar_type = str(payload.get("abnormal_return_type") or "car").lower()
    weighting = str(payload.get("aggregation") or "equal").lower()

    tickers = sorted(set(events["ticker"]))
    missing = [t for t in tickers if t not in set(parse_symbols({"universe": ",".join(tickers)}))]
    if missing:
        raise UnknownSymbolsError(missing)
    daily = ohlcv_matrices(tickers, int(payload.get("lookback_days") or 7300))
    rets = daily["Close"].pct_change(fill_method=None)
    ff = load_factor_returns().set_index("date")
    ff["mkt"] = ff["mkt_rf"] + ff["rf"]
    ff["mkt_lag"] = ff["mkt"].shift(1)

    events = events.sort_values(["ticker", "treatment_date"])
    if contamination:
        gap = events.groupby("ticker")["treatment_date"].diff().dt.days
        events = events[gap.isna() | (gap > contamination)]
    span = (-20, 20)
    lo, hi = min(span[0], win[0]), max(span[1], win[1])
    records_ = []
    for _, ev in events.iterrows():
        r = rets[ev["ticker"]].dropna()
        if r.empty:
            continue
        day0 = r.index.searchsorted(pd.Timestamp(ev["treatment_date"]))
        est_end = day0 + lo - 11
        est_start = est_end - est_len
        if est_start < 0 or day0 + hi >= len(r):
            continue
        idx = r.index
        cols = MODELS[model]
        fac = ff.reindex(idx)
        y_all = r - (0 if model in {"market", "dimson"} else fac["rf"])
        x_all = fac[cols]
        est = pd.concat([y_all.iloc[est_start:est_end].rename("y"), x_all.iloc[est_start:est_end]], axis=1).dropna()
        if len(est) < est_len * 0.7:
            continue
        xm = np.column_stack([np.ones(len(est)), est[cols].to_numpy()])
        beta, *_ = np.linalg.lstsq(xm, est["y"].to_numpy(), rcond=None)
        resid = est["y"].to_numpy() - xm @ beta
        k = xm.shape[1]
        s2 = float(resid @ resid) / (len(est) - k)
        xtx_inv = np.linalg.pinv(xm.T @ xm)
        ev_idx = idx[day0 + lo: day0 + hi + 1]
        xe = np.column_stack([np.ones(len(ev_idx)), x_all.loc[ev_idx, cols].to_numpy()])
        expected = xe @ beta
        ar = y_all.loc[ev_idx].to_numpy() - expected
        # Patell forecast-error adjustment: var(AR_t) = s2 (1 + x_t'(X'X)^-1 x_t)
        c = np.einsum("ij,jk,ik->i", xe, xtx_inv, xe)
        sar = ar / np.sqrt(s2 * (1 + c))
        rel = np.arange(lo, hi + 1)
        mcap = np.nan
        if weighting == "value":
            sh = point_in_time_fundamental("Ordinary Shares Number", pd.DatetimeIndex([idx[day0]]), [ev["ticker"]]).iloc[0, 0]
            mcap = float(sh * daily["Close"][ev["ticker"]].iloc[day0]) if np.isfinite(sh) else np.nan
        records_.append({"ticker": ev["ticker"], "event_date": idx[day0], "rel": rel, "ar": ar, "sar": sar, "raw": r.loc[ev_idx].to_numpy(), "expected": expected + (0 if model in {"market", "dimson"} else fac.loc[ev_idx, "rf"].to_numpy()), "resid_est": pd.Series(resid, index=est.index), "L": len(est), "k": k, "mcap": mcap})
    if len(records_) < 2:
        raise ValueError("Fewer than 2 events have a complete estimation and event window in the data.")

    n = len(records_)
    w = np.array([e["mcap"] for e in records_], dtype=float)
    weights = w / np.nansum(w) if weighting == "value" and np.isfinite(w).sum() == n else np.full(n, 1 / n)
    rbar = _cross_correlation(records_)

    def window_tests(a: int, b: int) -> dict[str, Any]:
        sel = [(e["rel"] >= a) & (e["rel"] <= b) for e in records_]
        car = np.array([e["ar"][m].sum() for e, m in zip(records_, sel)])
        bhar = np.array([np.prod(1 + e["raw"][m]) - np.prod(1 + e["expected"][m]) for e, m in zip(records_, sel)])
        lw = b - a + 1
        scar = np.array([e["sar"][m].sum() / math.sqrt(lw) for e, m in zip(records_, sel)])
        adj = np.array([(e["L"] - e["k"]) / (e["L"] - e["k"] - 2) for e in records_])
        stat = car if ar_type == "car" else bhar
        mean = float(np.sum(weights * stat))
        t_cs = mean / (stat.std(ddof=1) / math.sqrt(n)) if stat.std(ddof=1) > 0 else np.nan
        z_patell = float(scar.sum() / math.sqrt(adj.sum()))
        t_bmp = float(scar.mean() / (scar.std(ddof=1) / math.sqrt(n))) if scar.std(ddof=1) > 0 else np.nan
        t_kp = t_bmp * math.sqrt((1 - rbar) / (1 + (n - 1) * rbar)) if np.isfinite(t_bmp) and rbar > -1 / (n - 1) else np.nan
        tests = [
            {"test": "cross-sectional t", "statistic": t_cs, "p_value": float(2 * stats.t.sf(abs(t_cs), n - 1)) if np.isfinite(t_cs) else np.nan},
            {"test": "Patell (1976)", "statistic": z_patell, "p_value": float(2 * stats.norm.sf(abs(z_patell)))},
            {"test": "Boehmer-Musumeci-Poulsen (1991)", "statistic": t_bmp, "p_value": float(2 * stats.t.sf(abs(t_bmp), n - 1)) if np.isfinite(t_bmp) else np.nan},
            {"test": "Kolari-Pynnonen (2010) adjusted BMP", "statistic": t_kp, "p_value": float(2 * stats.t.sf(abs(t_kp), n - 1)) if np.isfinite(t_kp) else np.nan},
        ]
        return {"window": f"({a},{b})", "mean": mean, "measure": ar_type.upper(), "events": n, "car": car, "tests": tests}

    main = window_tests(*win)
    pre = window_tests(-20, -2)
    post = window_tests(2, 20)
    sig = [t["test"] for t in main["tests"] if t["p_value"] < 0.05]
    verdict = f"{len(sig)} of 4 tests reject zero at 5%" + (f" ({', '.join(sig)})." if sig else ".")
    if 0 < len(sig) < 4:
        verdict += " Disagreement usually means event-induced variance (BMP) or clustering in calendar time (KP) matters here."

    path_rows = []
    ars = np.vstack([e["ar"] for e in records_])
    cum = np.cumsum(ars, axis=1)
    rel = records_[0]["rel"]
    for j, day in enumerate(rel):
        col = cum[:, j]
        m = float(np.sum(weights * col))
        se = float(col.std(ddof=1) / math.sqrt(n))
        path_rows.append({"event_day": int(day), "mean_car": m, "lower_95": m - 1.96 * se, "upper_95": m + 1.96 * se, "mean_ar": float(np.sum(weights * ars[:, j]))})

    calendar = _event_calendar_alpha(records_, rets, int(payload.get("calendar_holding_months") or 12))
    tables = {
        "event_study_tests": [{"window": main["window"], "measure": main["measure"], "mean": main["mean"], **t} for t in main["tests"]],
        "pre_event_drift": [{"window": pre["window"], "mean": pre["mean"], **t} for t in pre["tests"]],
        "post_event_continuation": [{"window": post["window"], "mean": post["mean"], "interpretation": "continuation (underreaction)" if np.sign(post["mean"]) == np.sign(main["mean"]) else "reversal (overreaction)", **t} for t in post["tests"]],
        "event_study_verdict": [{"verdict": verdict, "events": n, "benchmark_model": model, "estimation_window_days": est_len, "average_cross_correlation": rbar}],
        "calendar_time_portfolio_alpha": [calendar],
        "event_list": [{"ticker": e["ticker"], "event_date": e["event_date"], "car": float(c)} for e, c in zip(records_, main["car"])],
    }
    charts = {"car_event_path": path_rows, "car_distribution": [{"car": float(c)} for c in main["car"]]}
    summary = [{"label": f"Mean {main['measure']} {main['window']}", "value": main["mean"]}, {"label": "BMP t", "value": main["tests"][2]["statistic"]}, {"label": "Events", "value": n}]
    return {"summary": summary, "charts": charts, "tables": tables, "caveats": []}


def _cross_correlation(recs: list[dict[str, Any]]) -> float:
    """Average pairwise correlation of estimation-window residuals over overlapping dates (Kolari-Pynnonen)."""

    series = pd.concat([e["resid_est"].rename(i) for i, e in enumerate(recs)], axis=1, sort=True)
    if series.shape[1] < 2:
        return 0.0
    corr = series.corr(min_periods=60)
    vals = corr.to_numpy()[np.triu_indices(len(corr), 1)]
    vals = vals[np.isfinite(vals)]
    return float(vals.mean()) if len(vals) else 0.0


def _event_calendar_alpha(recs: list[dict[str, Any]], rets: pd.DataFrame, holding: int) -> dict[str, Any]:
    """Monthly calendar-time portfolio of event firms over the ``holding`` months after each event, FF5+UMD alpha."""

    from .stats import ols

    monthly = (1 + rets).resample("ME").prod() - 1
    held = pd.DataFrame(False, index=monthly.index, columns=monthly.columns)
    for e in recs:
        start = monthly.index.searchsorted(e["event_date"] + pd.offsets.MonthEnd(1))
        held.iloc[start:start + holding, held.columns.get_loc(e["ticker"])] = True
    port = monthly.where(held).mean(axis=1)
    count = held.sum(axis=1)
    ffm = _monthly_ff(monthly.index)
    ex = (port - ffm["rf"]).where(count > 0).dropna()
    cols = [c for c in ["mkt_rf", "smb", "hml", "rmw", "cma"] if c in ffm]
    if len(ex) < 24:
        return {"available": False, "reason": "fewer than 24 calendar months with event firms"}
    fit = ols(ex, ffm.loc[ex.index, cols], cov="hac", lags=4)
    return {"available": True, "alpha_monthly": float(fit["params"]["const"]), "alpha_t": float(fit["tvalues"]["const"]), "alpha_p": float(fit["pvalues"]["const"]), "months": fit["nobs"], "mean_firms": float(count[count > 0].mean()), **{f"beta_{c}": float(fit["params"][c]) for c in cols}}


# ---------------------------------------------------------------------------
# regression discontinuity

RUNNING_VARIABLES = {"market_cap": "size", "size_rank": "size", "leverage": "leverage", "beta": "beta", "momentum": "momentum", "volatility": "ivol", "value": "value", "profitability": "profitability"}


def _rd_data(payload: dict[str, Any]) -> tuple[pd.DataFrame, str, dict[str, Any]]:
    running = str(payload.get("running_variable") or "market_cap").lower()
    if running not in RUNNING_VARIABLES:
        raise ValueError(f"running_variable must be one of {list(RUNNING_VARIABLES)}")
    covariates = ["size", "value", "beta", "momentum", "ivol", "profitability", "leverage"]
    panel = build_panel({**payload, "signal": "momentum", "controls": covariates, "min_assets": 20})
    stacked = panel.stacked(covariates)
    if running == "market_cap":
        x = panel.market_cap.stack().rename("x") / 1e9  # billions of dollars
    elif running == "size_rank":
        x = panel.market_cap.rank(axis=1, ascending=False).stack().rename("x")
    else:
        x = stacked[RUNNING_VARIABLES[running]].rename("x")
    x.index = x.index.set_names(["date", "ticker"])
    df = stacked.join(x, how="inner").dropna(subset=["x", "y"])
    df = df.reset_index()
    df["cluster"] = pd.factorize(df["ticker"])[0]
    return df, running, {"caveats": panel.caveats, "unit": "USD billions" if running == "market_cap" else ("rank (1 = largest)" if running == "size_rank" else running)}


def run_rdd(payload: dict[str, Any]) -> dict[str, Any]:
    from rddensity import rddensity
    from rdrobust import rdrobust

    df, running, info = _rd_data(payload)
    if payload.get("cutoff") in (None, ""):
        raise ValueError("Set the RD cutoff on the running variable (e.g. 5 for a $5bn market-cap threshold, 500 for a size rank).")
    c = float(payload["cutoff"])
    kernel = {"triangular": "tri", "uniform": "uni", "epanechnikov": "epa"}.get(str(payload.get("kernel") or "triangular").lower(), "tri")
    p = int(payload.get("polynomial_order") or 1)
    h_user = float(payload["bandwidth"]) if payload.get("bandwidth") not in (None, "", "auto") else None
    fuzzy = None
    ev = load_event_upload(payload.get("event_csv_path"))
    if str(payload.get("rd_design") or "sharp").lower() == "fuzzy":
        if ev.empty:
            raise ValueError("A fuzzy RD needs an event file marking actual treatment (ticker, treatment_date).")
        first = ev.groupby("ticker")["treatment_date"].min()
        fuzzy = np.array([1.0 if t in first.index and d >= first[t] else 0.0 for t, d in zip(df["ticker"], df["date"])])
    if not ((df["x"] < c).sum() > 30 and (df["x"] >= c).sum() > 30):
        raise ValueError(f"The cutoff {c:g} leaves fewer than 30 observations on one side of the running variable.")

    def est(y: np.ndarray, x: np.ndarray, cl: np.ndarray, cutoff: float, h: float | None = None, fz: np.ndarray | None = None) -> dict[str, Any]:
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):  # rdrobust prints mass-point notices
            warnings.simplefilter("ignore")
            r = rdrobust(y, x, c=cutoff, p=p, kernel=kernel, h=h, cluster=cl, fuzzy=fz, vce="hc1")
        return {"estimate": float(r.coef.iloc[0, 0]), "se_conventional": float(r.se.iloc[0, 0]), "estimate_bias_corrected": float(r.coef.iloc[1, 0]), "se_robust": float(r.se.iloc[2, 0]), "p_value_robust": float(r.pv.iloc[2, 0]), "ci_robust_low": float(r.ci.iloc[2, 0]), "ci_robust_high": float(r.ci.iloc[2, 1]), "bandwidth": float(r.bws.iloc[0, 0]), "n_left": int(r.N_h[0]), "n_right": int(r.N_h[1])}

    y, x, cl = df["y"].to_numpy(), df["x"].to_numpy(), df["cluster"].to_numpy()
    main = est(y, x, cl, c, h_user, fuzzy)
    h = main["bandwidth"]

    sensitivity = []
    for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        try:
            sensitivity.append({"bandwidth_multiple": mult, **est(y, x, cl, c, h * mult, fuzzy)})
        except Exception:
            continue
    placebo = []
    for pct in [-0.25, -0.2, -0.15, -0.1, -0.05, 0.05, 0.1, 0.15, 0.2, 0.25]:
        fake = c * (1 + pct) if c else pct
        side = (x < c) if fake < c else (x >= c)  # use only observations on the fake cutoff's side
        try:
            placebo.append({"cutoff": fake, "shift_pct": pct * 100, **est(y[side], x[side], cl[side], fake)})
        except Exception:
            continue
    placebo.append({"cutoff": c, "shift_pct": 0.0, "real_cutoff": True, **main})
    donut = []
    for frac in [0.05, 0.1, 0.2]:
        keep = np.abs(x - c) >= frac * h
        try:
            donut.append({"donut_fraction_of_h": frac, "donut_radius": frac * h, **est(y[keep], x[keep], cl[keep], c, h)})
        except Exception:
            continue
    covs = []
    for name in [col for col in ["size", "value", "beta", "momentum", "ivol", "profitability", "leverage"] if col in df and col != RUNNING_VARIABLES.get(running)]:
        sub = df[[name, "x", "cluster"]].dropna()
        if len(sub) < 200:
            continue
        try:
            res = est(sub[name].to_numpy(), sub["x"].to_numpy(), sub["cluster"].to_numpy(), c, h)
            covs.append({"covariate": name, **res, "discontinuity": bool(res["p_value_robust"] < 0.05)})
        except Exception:
            continue
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        dens = rddensity(X=x, c=c)
    manip = {"test": "Cattaneo-Jansson-Ma (rddensity), the modern McCrary test", "t_stat": float(dens.test["t_jk"]), "p_value": float(dens.test["p_jk"]), "manipulation_detected": bool(float(dens.test["p_jk"]) < 0.05)}

    tables = {
        "rd_estimate": [{"running_variable": running, "running_unit": info["unit"], "cutoff": c, "design": "fuzzy" if fuzzy is not None else "sharp", "kernel": kernel, "polynomial_order": p, "bandwidth_selector": "CCT MSE-optimal (mserd)" if h_user is None else "user", **main}],
        "rd_bandwidth_sensitivity": sensitivity,
        "rd_placebo_cutoffs": placebo,
        "rd_donut_hole": donut,
        "rd_covariate_continuity": covs,
        "rd_density_test": [manip],
    }
    charts = {"rd_plot": _rd_plot(df, c, h, p), "rd_density": _rd_density(x, c), "rd_placebo_chart": placebo, "rd_bandwidth_chart": sensitivity}
    summary = [{"label": "RD effect (bias-corrected)", "value": main["estimate_bias_corrected"]}, {"label": "RD robust p", "value": main["p_value_robust"]}, {"label": "Density test p", "value": manip["p_value"]}]
    caveats = info["caveats"] + ["Bandwidth uses the Calonico-Cattaneo-Titiunik MSE-optimal selector, the successor to Imbens-Kalyanaraman; inference is robust bias-corrected."]
    return {"summary": summary, "charts": charts, "tables": tables, "caveats": caveats}


def _rd_plot(df: pd.DataFrame, c: float, h: float, p: int, bins: int = 20) -> pd.DataFrame:
    rows = []
    for side, mask in (("left", df["x"] < c), ("right", df["x"] >= c)):
        sub = df.loc[mask & ((df["x"] - c).abs() <= 2 * h), ["x", "y"]]
        if len(sub) < bins:
            continue
        sub = sub.assign(bin=pd.qcut(sub["x"].rank(method="first"), bins, labels=False))
        g = sub.groupby("bin").agg(x=("x", "mean"), y=("y", "mean"), n=("y", "size"))
        local = sub[(sub["x"] - c).abs() <= h]
        if len(local) > p + 2:
            w = np.clip(1 - np.abs(local["x"] - c) / h, 0, None)
            coef = np.polyfit(local["x"] - c, local["y"], p, w=np.sqrt(w))
            g["fit"] = np.where((g["x"] - c).abs() <= h, np.polyval(coef, g["x"] - c), np.nan)
        g["side"] = side
        rows.append(g.reset_index(drop=True))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _rd_density(x: np.ndarray, c: float, bins: int = 30) -> pd.DataFrame:
    span = np.quantile(np.abs(x - c), 0.5)
    edges = np.linspace(c - span, c + span, bins + 1)
    counts, _ = np.histogram(x, bins=edges)
    mids = (edges[:-1] + edges[1:]) / 2
    return pd.DataFrame({"x": mids, "count": counts, "side": np.where(mids < c, "left", "right")})


# ---------------------------------------------------------------------------
# instrumental variables


def run_iv(payload: dict[str, Any]) -> dict[str, Any]:
    from linearmodels.iv import IV2SLS, IVLIML

    endog_names = [str(payload.get("endogenous_variable") or payload.get("signal") or "momentum").lower()]
    extra = payload.get("additional_endogenous") or []
    if isinstance(extra, str):
        extra = [e.strip() for e in extra.split(",") if e.strip()]
    endog_names += [e.lower() for e in extra][:3]
    instrument_kind = str(payload.get("instrument") or "lag_3").lower()
    controls = payload.get("iv_controls") or payload.get("controls") or "none"
    panel = build_panel({**payload, "signal": endog_names[0], "controls": controls, "min_assets": 20})
    ctx = panel.context
    endog = {endog_names[0]: panel.signal}
    for name in endog_names[1:]:
        endog[name] = compute_signal(name, ctx).reindex(index=panel.dates, columns=panel.symbols)

    instruments: dict[str, pd.DataFrame] = {}
    upload = load_instrument_upload(payload.get("instrument_csv_path"))
    if instrument_kind == "uploaded":
        if upload.empty:
            raise ValueError("Upload an instrument file (date, ticker, instrument) or pick a built-in instrument.")
        wide = upload.pivot_table(index="date", columns="ticker", values="instrument", aggfunc="last").resample("ME").last()
        instruments["z_uploaded"] = wide.reindex(index=panel.dates, columns=panel.symbols)
    for name in endog_names:
        full = compute_signal(name, ctx).reindex(columns=panel.symbols)
        if instrument_kind.startswith("lag_"):
            lag = int(instrument_kind.split("_")[1])
            instruments[f"z_{name}_lag{lag}"] = full.shift(lag).reindex(panel.dates)
        elif instrument_kind == "industry_mean":
            sectors = static_sectors().reindex(panel.symbols)
            vals = full.reindex(panel.dates)
            z = pd.DataFrame(index=vals.index, columns=vals.columns, dtype=float)
            for sec in sectors.dropna().unique():
                members = sectors[sectors == sec].index
                block = vals[members]
                total, count = block.sum(axis=1, min_count=1), block.notna().sum(axis=1)
                z[members] = block.apply(lambda col: (total - col.fillna(0)) / (count - col.notna().astype(int)).replace(0, np.nan))
            instruments[f"z_{name}_industry_loo_mean"] = z
        elif instrument_kind != "uploaded":
            raise ValueError("instrument must be lag_1, lag_3, lag_6, industry_mean or uploaded")

    parts = [panel.dependent.stack().rename("y")]
    parts += [m.stack().rename(f"x_{n}") for n, m in endog.items()]
    parts += [m.stack().rename(n) for n, m in instruments.items()]
    parts += [panel.controls[c].stack().rename(f"c_{c}") for c in panel.controls]
    df = pd.concat(parts, axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    df.index = df.index.set_names(["date", "ticker"])
    df = df - df.groupby(level="date").transform("mean")  # time fixed effects
    if len(df) < 200:
        raise ValueError("Fewer than 200 complete observations for the IV regression.")
    xn = [f"x_{n}" for n in endog]
    zn = list(instruments)
    cn = [f"c_{c}" for c in panel.controls]
    if len(zn) < len(xn):
        raise ValueError("The model needs at least as many instruments as endogenous variables.")
    exog = df[cn] if cn else None
    cluster_by = str(payload.get("cluster") or "date").lower()
    clusters = pd.Series(pd.factorize(df.index.get_level_values("date" if cluster_by == "date" else "ticker"))[0], index=df.index)
    cov = {"cov_type": "clustered", "clusters": clusters}
    estimator = str(payload.get("iv_estimator") or "2sls").lower()
    model_cls = IVLIML if estimator == "liml" else IV2SLS
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        iv = model_cls(df["y"], exog, df[xn], df[zn]).fit(**cov)
        ols_fit = IV2SLS(df["y"], pd.concat([df[xn], df[cn]], axis=1) if cn else df[xn], None, None).fit(**cov)
        unadj = IV2SLS(df["y"], exog, df[xn], df[zn]).fit(cov_type="unadjusted")
    fs = iv.first_stage.diagnostics
    first_stage = [{"endogenous": n, "partial_r2": float(fs.loc[n, "partial.rsquared"]), "shea_r2": float(fs.loc[n, "shea.rsquared"]), "f_stat": float(fs.loc[n, "f.stat"]), "f_p_value": float(fs.loc[n, "f.pval"]), "staiger_stock_pass_F>10": bool(fs.loc[n, "f.stat"] > 10), "lee_et_al_2022_pass_F>104.7": bool(fs.loc[n, "f.stat"] > 104.7)} for n in xn]
    second = [{"term": k.replace("x_", "").replace("c_", ""), "iv_coefficient": float(iv.params[k]), "iv_se": float(iv.std_errors[k]), "iv_t": float(iv.tstats[k]), "iv_p": float(iv.pvalues[k]), "ols_coefficient": float(ols_fit.params.get(k, np.nan)), "ols_se": float(ols_fit.std_errors.get(k, np.nan))} for k in iv.params.index]
    tests = []
    for label, fn in [("Wu-Hausman (F)", lambda: iv.wu_hausman()), ("Durbin (chi2)", lambda: iv.durbin())]:
        try:
            t = fn()
            tests.append({"test": label, "statistic": float(t.stat), "p_value": float(t.pval), "verdict": "endogenous: IV required" if t.pval < 0.05 else "exogeneity not rejected: OLS is consistent and more efficient"})
        except Exception as exc:
            tests.append({"test": label, "statistic": None, "p_value": None, "verdict": f"not available: {exc}"})
    if len(zn) > len(xn):
        for label, fn in [("Sargan (homoskedastic)", lambda: unadj.sargan), ("Wooldridge score (robust)", lambda: iv.wooldridge_overid)]:
            t = fn()
            tests.append({"test": label, "statistic": float(t.stat), "p_value": float(t.pval), "verdict": "at least one instrument invalid" if t.pval < 0.05 else "over-identifying restrictions not rejected"})
    else:
        tests.append({"test": "Sargan-Hansen", "statistic": None, "p_value": None, "verdict": "not computable: model is just-identified"})
    ar = _anderson_rubin(df, xn, zn, cn, clusters, float(iv.params[xn[0]]), float(iv.std_errors[xn[0]])) if len(xn) == 1 else {"available": False, "reason": "AR set reported for a single endogenous variable"}
    strong = all(r["staiger_stock_pass_F>10"] for r in first_stage)
    assessment = ("Instruments are strong (F > 10)" if strong else "Instruments are weak (F < 10): rely on the Anderson-Rubin set, not the 2SLS t-test") + ("; they also pass the Lee et al. (2022) F > 104.7 bar." if all(r["lee_et_al_2022_pass_F>104.7"] for r in first_stage) else ".") + (" Built-in lagged instruments are relevant by construction but the exclusion restriction (the lag affects returns only through the current value) must be argued, not tested." if instrument_kind.startswith("lag_") else "")
    tables = {
        "iv_first_stage": first_stage,
        "iv_second_stage": second,
        "iv_tests": tests,
        "anderson_rubin_confidence_set": [ar],
        "iv_assessment": [{"estimator": estimator.upper(), "instrument": instrument_kind, "instruments": zn, "observations": int(iv.nobs), "cluster": cluster_by, "assessment": assessment}],
    }
    summary = [{"label": f"IV β ({endog_names[0]})", "value": float(iv.params[xn[0]])}, {"label": "First-stage F", "value": first_stage[0]["f_stat"]}, {"label": "AR 95% set", "value": ar.get("description")}]
    return {"summary": summary, "charts": {"iv_ar_pvalue_curve": ar.pop("curve", [])}, "tables": tables, "caveats": panel.caveats}


def _anderson_rubin(df: pd.DataFrame, xn: list[str], zn: list[str], cn: list[str], clusters: pd.Series, b_iv: float, se_iv: float) -> dict[str, Any]:
    """Anderson-Rubin (1949) confidence set by test inversion, cluster-robust.

    For each beta0 regress y - beta0 x on the instruments (and controls) and
    test the instruments jointly; the 95% set collects every beta0 not rejected.
    Valid whatever the instrument strength; may be unbounded or disjoint.
    """

    import statsmodels.api as sm

    width = max(20 * se_iv, abs(b_iv) * 5, 1e-3) if np.isfinite(se_iv) else 1.0
    grid = np.linspace(b_iv - width, b_iv + width, 201)
    x = df[xn[0]].to_numpy()
    rhs = sm.add_constant(df[zn + cn])
    groups = clusters.to_numpy()
    curve = []
    for b0 in grid:
        yy = df["y"].to_numpy() - b0 * x
        fit = sm.OLS(yy, rhs).fit(cov_type="cluster", cov_kwds={"groups": groups})
        r = np.zeros((len(zn), rhs.shape[1]))
        for j, name in enumerate(zn):
            r[j, list(rhs.columns).index(name)] = 1
        w = fit.wald_test(r, scalar=True)
        curve.append({"beta0": float(b0), "p_value": float(w.pvalue)})
    cv = pd.DataFrame(curve)
    accepted = cv[cv["p_value"] >= 0.05]["beta0"]
    if accepted.empty:
        desc, lo, hi = "empty (every value rejected: instruments likely invalid)", None, None
    else:
        lo, hi = float(accepted.min()), float(accepted.max())
        unbounded = bool(cv["p_value"].iloc[0] >= 0.05 or cv["p_value"].iloc[-1] >= 0.05)
        gaps = bool((np.diff(accepted.index) > 1).any())
        desc = ("unbounded (weak instruments)" if unbounded else f"[{lo:.4f}, {hi:.4f}]") + (" with gaps (disjoint set)" if gaps else "")
    return {"available": True, "description": desc, "low": lo, "high": hi, "grid_low": float(grid[0]), "grid_high": float(grid[-1]), "curve": curve}
