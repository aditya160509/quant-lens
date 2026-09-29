"""Feature 03: Placebo and Falsification Suite."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .estimators import fm_slopes, sort_portfolios
from .holdout import get_window, record_evaluation, reserve_window, study_key
from .panel import PRICE_SIGNALS, Panel, build_panel
from .stats import auto_nw_lag, fisher_stouffer, mean_test, ols, two_sided_power

SIGNAL_LOOKBACK_MONTHS = {"momentum": 12, "reversal": 1, "low_vol": 12, "yang_zhang_vol": 3, "garman_klass_vol": 3, "beta": 36, "ivol": 36}

ADJACENT_CLASSES = {
    "fixed_income": ["TLT", "IEF", "LQD", "HYG"],
    "commodities": ["GLD", "USO", "DBC"],
    "fx": ["UUP", "FXE", "FXY"],
}


def run_placebo(payload: dict[str, Any]) -> dict[str, Any]:
    panel = build_panel(payload)
    controls = list(panel.controls)
    reps = int(payload.get("permutation_replications") or 1000)
    lag = max(auto_nw_lag(len(panel.dates)), panel.holding_months)

    real = _fm_signal(panel, panel.signal, controls, lag)
    null = _permutation_null(panel, controls, reps, lag)
    perm_p = float((1 + np.sum(np.abs(null) >= abs(real["t"]))) / (1 + len(null))) if len(null) else np.nan

    requested = int(payload.get("time_displacement_months") or 12)
    # A return-based signal measured at s uses returns from s - lookback to s. For the
    # future signal to carry no mechanical information about the outcome window
    # (t, t + h], it must start after t + h: displacement >= lookback + h.
    months = max(requested, SIGNAL_LOOKBACK_MONTHS.get(panel.config["signal"], 0) + panel.holding_months)
    shift = max(1, int(np.ceil(months / _step(panel))))  # formation periods
    displaced = _fm_signal(panel, panel.signal.shift(-shift), controls, lag)
    displacement_note = "" if months == requested else f"Displacement raised from {requested} to {months} months so the future signal's return window cannot overlap the outcome window."

    buckets = int(payload.get("sort_portfolios") or 5)
    port = sort_portfolios(panel, buckets)
    flipped_port = sort_portfolios(panel, buckets, signal=-panel.signal)
    wrong = _wrong_direction(port, flipped_port, lag)

    split = float(payload.get("oos_split") or 0.7)
    oos = _mclean_pontiff(panel, controls, split, lag)
    adjacent = _adjacent_classes(payload, panel)

    protected = _protected(payload, panel, controls, lag)

    tests = [
        {"placebo": "permutation", "statistic": real["t"], "p_value": perm_p, "pass": bool(perm_p < 0.05), "criterion": "real |t| beats the permutation null at 5%"},
        {"placebo": "time_displacement", "statistic": displaced["t"], "p_value": displaced["p"], "pass": bool(not displaced["p"] < 0.05 or abs(displaced["t"]) < 0.5 * abs(real["t"])), "criterion": f"signal from {months} months in the future does not predict (insignificant or < half the real |t|)"},
        {"placebo": "wrong_direction", "statistic": wrong.get("mirror_gap_t"), "p_value": wrong.get("mirror_gap_p"), "pass": bool(not np.isfinite(wrong.get("mirror_gap_p", np.nan)) or wrong["mirror_gap_p"] >= 0.05), "criterion": "flipped signal mirrors the original long-short (difference not significant; exact mirror counts as a pass)"},
        {"placebo": "oos_mclean_pontiff", "statistic": oos.get("oos_is_ratio"), "p_value": np.nan, "pass": bool(oos.get("oos_is_ratio", -1) >= 0.3 and np.sign(oos.get("oos_coefficient", 0)) == np.sign(oos.get("is_coefficient", 1))), "criterion": "OOS/IS coefficient ratio >= 0.3 with the same sign"},
    ]
    if adjacent["available"]:
        adj_p = adjacent["summary"]["p_value"]
        tests.append({"placebo": "adjacent_asset_class", "statistic": adjacent["summary"]["t_stat"], "p_value": adj_p, "pass": bool(adj_p >= 0.05), "criterion": "same signal does not predict in bonds, commodities and FX"})
    passed = sum(t["pass"] for t in tests)
    verdict = "green" if passed == len(tests) else "amber" if passed >= len(tests) / 2 else "red"
    # Combined placebo significance: placebos that should be null (displacement, adjacent class, mirror gap).
    null_placebos = [t["p_value"] for t in tests if t["placebo"] in {"time_displacement", "adjacent_asset_class", "wrong_direction"}]
    combined = fisher_stouffer(null_placebos)
    combined["interpretation"] = "Small combined p means the placebos detect effects they should not: evidence the result is spurious." if np.isfinite(combined.get("fisher_p_value", np.nan)) else ""
    power = {
        "power_displacement": two_sided_power(real["t"]),
        "power_adjacent": two_sided_power(real["t"] * np.sqrt(adjacent["summary"]["observations"] / max(real["n"] * np.nanmean(panel.signal.notna().sum(axis=1)), 1))) if adjacent["available"] else np.nan,
        "power_permutation": two_sided_power(real["t"]),
    }
    finite_power = [v for v in power.values() if np.isfinite(v)]
    power["battery_power"] = float(np.mean(finite_power)) if finite_power else np.nan
    power["message"] = f"This placebo battery has about {power['battery_power']:.0%} power to detect a spurious effect as large as the real one (|t| = {abs(real['t']):.2f})." if finite_power else "Power not estimable."

    tables = {
        "permutation_placebo": [{"real_t_stat": real["t"], "real_coefficient": real["coef"], "permutation_p_value": perm_p, "replications": len(null), "null_95th_abs_t": float(np.quantile(np.abs(null), 0.95)) if len(null) else np.nan}],
        "time_displacement_placebo": [{"series": "real", "coefficient": real["coef"], "t_stat": real["t"], "p_value": real["p"], "months": real["n"]}, {"series": f"signal from t+{months}m", "coefficient": displaced["coef"], "t_stat": displaced["t"], "p_value": displaced["p"], "months": displaced["n"], "note": displacement_note}],
        "wrong_direction_placebo": wrong["rows"],
        "mclean_pontiff_oos": [oos],
        "adjacent_asset_class_placebo": adjacent["rows"] if adjacent["available"] else [{"available": False, "reason": adjacent["reason"]}],
        "combined_significance": [combined],
        "power_analysis": [power],
        "protected_oos": [protected],
        "placebo_scorecard": tests,
        "falsification_verdict": [{"verdict": verdict, "passed": passed, "tests": len(tests), "message": {"green": "All placebos pass: the result behaves like a real effect.", "amber": "Some placebos fail: the result is plausible but fragile.", "red": "Most placebos fail: the result is likely spurious."}[verdict]}],
    }
    charts = {
        "permutation_null_histogram": [{"t_stat": float(v)} for v in null],
        "permutation_real_t": [{"t_stat": real["t"]}],
        "oos_coefficient_comparison": [{"sample": "in_sample", "coefficient": oos.get("is_coefficient")}, {"sample": "out_of_sample", "coefficient": oos.get("oos_coefficient")}],
    }
    summary = [
        {"label": "Verdict", "value": verdict},
        {"label": "Real t", "value": real["t"]},
        {"label": "Permutation p", "value": perm_p},
        {"label": "OOS/IS ratio", "value": oos.get("oos_is_ratio")},
        {"label": "Placebos passed", "value": f"{passed}/{len(tests)}"},
    ]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"config": panel.config, "research_caveats": panel.caveats}}


def _step(panel: Panel) -> int:
    return {"monthly": 1, "quarterly": 3, "annual": 12}[panel.config["rebalancing_frequency"]]


def _fm_signal(panel: Panel, signal: pd.DataFrame, controls: list[str], lag: int, dates: pd.Index | None = None) -> dict[str, Any]:
    idx = panel.dates if dates is None else dates
    regs = {"signal": signal.loc[idx], **{c: panel.controls[c].loc[idx] for c in controls}}
    slopes = fm_slopes(panel.dependent.loc[idx], regs)
    test = mean_test(slopes["signal"], lag) if len(slopes) >= 6 else {"mean": np.nan, "se": np.nan, "t": np.nan, "p": np.nan, "n": len(slopes)}
    return {"coef": test["mean"], "se": test["se"], "t": test["t"], "p": test["p"], "n": test["n"], "slopes": slopes}


def _permutation_null(panel: Panel, controls: list[str], reps: int, lag: int, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = panel.signal.to_numpy()
    out = []
    for _ in range(int(reps)):
        shuffled = base.copy()
        for i in range(shuffled.shape[0]):
            row = shuffled[i]
            finite = np.isfinite(row)
            row[finite] = rng.permutation(row[finite])
        res = _fm_signal(panel, pd.DataFrame(shuffled, index=panel.dates, columns=panel.symbols), controls, lag)
        if np.isfinite(res["t"]):
            out.append(res["t"])
    return np.asarray(out)


def _wrong_direction(port: pd.DataFrame, flipped: pd.DataFrame, lag: int) -> dict[str, Any]:
    if port.empty or flipped.empty:
        return {"rows": [], "mirror_gap_p": np.nan}
    ls, fls = port["long_short"], flipped["long_short"]
    gap = (ls + fls).dropna()  # zero if the flipped spread exactly mirrors the original
    real, flip, g = mean_test(ls, lag), mean_test(fls, lag), mean_test(gap, lag)
    rows = [
        {"series": "original_long_short", "mean": real["mean"], "t_stat": real["t"], "p_value": real["p"]},
        {"series": "flipped_long_short", "mean": flip["mean"], "t_stat": flip["t"], "p_value": flip["p"]},
        {"series": "mirror_gap (original + flipped)", "mean": g["mean"], "t_stat": g["t"], "p_value": g["p"]},
        {"series": "long_leg_top_bucket", "mean": float(port.iloc[:, -2].mean()), "t_stat": np.nan, "p_value": np.nan},
        {"series": "short_leg_bottom_bucket", "mean": float(port.iloc[:, 0].mean()), "t_stat": np.nan, "p_value": np.nan},
    ]
    return {"rows": rows, "mirror_gap_t": g["t"], "mirror_gap_p": g["p"]}  # NaN when the mirror is exact


def _mclean_pontiff(panel: Panel, controls: list[str], split: float, lag: int) -> dict[str, Any]:
    cut = panel.dates[int(len(panel.dates) * split)]
    is_dates = panel.dates[panel.dates + pd.DateOffset(months=panel.holding_months) <= cut]
    oos_dates = panel.dates[panel.dates >= cut]
    ins = _fm_signal(panel, panel.signal, controls, lag, is_dates)
    out = _fm_signal(panel, panel.signal, controls, lag, oos_dates)
    # OOS R^2 (Campbell-Thompson): predictions from average IS FM coefficients vs the IS mean return.
    coefs = ins["slopes"].drop(columns=["r2", "n_assets"]).mean()
    stacked = panel.subset_dates(panel.dates.isin(oos_dates)).stacked(controls)
    x = stacked.drop(columns="y")
    pred = coefs.get("intercept", 0) + sum(coefs.get(c, 0) * x[c] for c in x.columns)
    is_mean = float(panel.subset_dates(panel.dates.isin(is_dates)).stacked(controls)["y"].mean())
    y = stacked["y"]
    r2 = 1 - float(((y - pred) ** 2).sum()) / float(((y - is_mean) ** 2).sum()) if len(y) else np.nan
    ratio = out["coef"] / ins["coef"] if ins["coef"] else np.nan
    color = "green" if ratio > 0.7 else "amber" if ratio >= 0.3 else "red"
    return {"split": split, "split_date": cut, "is_coefficient": ins["coef"], "is_t": ins["t"], "is_months": ins["n"], "oos_coefficient": out["coef"], "oos_t": out["t"], "oos_months": out["n"], "oos_is_ratio": ratio, "oos_r2": r2, "color": color}


def _adjacent_classes(payload: dict[str, Any], panel: Panel) -> dict[str, Any]:
    signal = panel.config["signal"]
    if signal not in PRICE_SIGNALS:
        return {"available": False, "reason": f"'{signal}' needs company fundamentals, which do not exist for bonds, commodities or FX."}
    from .panel import compute_signal, ohlcv_matrices

    rows, pooled = [], []
    for cls, tickers in ADJACENT_CLASSES.items():
        daily = ohlcv_matrices(tickers, panel.config["lookback_days"])
        if not daily:
            continue
        close_m = daily["Close"].resample("ME").last()
        rets = close_m.pct_change(fill_method=None)
        ctx = {"close_m": close_m, "returns": rets, "daily": daily, "market_cap": pd.DataFrame(index=rets.index, columns=rets.columns), "factors": panel.factors, "symbols": list(close_m.columns), "dates": rets.index}
        sig = compute_signal(signal, ctx)
        z = sig.sub(sig.mean(axis=1), axis=0).div(sig.std(axis=1).replace(0, np.nan), axis=0)
        h = panel.holding_months
        fwd = ((1 + rets).rolling(h).apply(np.prod, raw=True) - 1).shift(-h)
        fwd = fwd.sub(fwd.mean(axis=1), axis=0)  # time fixed effect: cross-sectional demeaning
        df = pd.concat([fwd.stack().rename("y"), z.stack().rename("signal")], axis=1).dropna()
        if len(df) < 60:
            continue
        df["cls"] = cls
        pooled.append(df)
        fit = ols(df["y"], df[["signal"]], cov="cluster", groups=pd.Series(df.index.get_level_values(0), index=df.index))
        rows.append({"asset_class": cls, "tickers": ",".join(close_m.columns), "coefficient": float(fit["params"]["signal"]), "t_stat": float(fit["tvalues"]["signal"]), "p_value": float(fit["pvalues"]["signal"]), "observations": fit["nobs"]})
    if not pooled:
        return {"available": False, "reason": "No adjacent asset-class ETFs found in the local market data."}
    allp = pd.concat(pooled)
    fit = ols(allp["y"], allp[["signal"]], cov="cluster", groups=pd.Series(allp.index.get_level_values(0), index=allp.index))
    summary = {"asset_class": "all_adjacent", "coefficient": float(fit["params"]["signal"]), "t_stat": float(fit["tvalues"]["signal"]), "p_value": float(fit["pvalues"]["signal"]), "observations": fit["nobs"]}
    return {"available": True, "rows": [*rows, summary], "summary": summary, "reason": ""}


def _protected(payload: dict[str, Any], panel: Panel, controls: list[str], lag: int) -> dict[str, Any]:
    months = int(payload.get("protected_oos_months") or 0)
    key = study_key(panel.config, payload.get("universe"))
    window = get_window(key)
    if months and not window:
        start = panel.dates.max() - pd.DateOffset(months=months)
        window = reserve_window(key, start, months)
        return {"status": "reserved", "study": key, **window, "message": f"The last {months} months are now locked away from every Research V2 feature for this study. Run again with 'Evaluate protected window' when your specification is final."}
    if not window:
        return {"status": "none", "message": "No protected window reserved. Set 'Protected OOS months' to reserve one."}
    if not payload.get("evaluate_protected"):
        return {"status": "locked", "study": key, **window, "message": "Protected window is reserved and excluded from all analyses."}
    full = build_panel({**payload, "_evaluate_protected": True})
    start = pd.Timestamp(window["start"])
    dates = full.dates[full.dates >= start]
    res = _fm_signal(full, full.signal, [c for c in controls if c in full.controls], lag, dates)
    prior = len(window.get("evaluations", []))
    record_evaluation(key)
    return {"status": "evaluated", "study": key, "start": window["start"], "coefficient": res["coef"], "t_stat": res["t"], "p_value": res["p"], "months": res["n"], "genuinely_out_of_sample": prior == 0, "previous_evaluations": prior, "message": "First look at the holdout: a genuine out-of-sample result." if prior == 0 else f"This holdout has been evaluated {prior} time(s) before; treat the result as no longer pristine."}
