"""Feature 05: Diagnostic Center.

Two objects are diagnosed, each with the tests that are valid for it:

* the time series of monthly Fama-MacBeth premia (serial correlation,
  normality, structural breaks, influential months), which is what the
  Feature 1 inference is built on;
* the pooled cross-sectional regression after removing date means (VIF,
  heteroskedasticity, functional form, observation-level influence, and the
  Wooldridge panel serial-correlation test).
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from .estimators import fama_macbeth
from .panel import Panel, build_panel
from .performance import acf_frame
from .stats import andrews_sup_f, chow_test

MAX_POOLED_ROWS = 40000


def run_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    import statsmodels.api as sm
    from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan, het_white, linear_reset
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.stats.stattools import durbin_watson, jarque_bera

    panel = build_panel(payload)
    alpha = float(payload.get("significance_level") or 0.05)
    top_n = int(payload.get("influential_top") or 10)
    controls = list(panel.controls)
    _, slopes = fama_macbeth(panel, controls)
    lam = slopes["signal"].dropna()

    pooled = _time_demeaned(panel, controls)
    fit = sm.OLS(pooled["y"], sm.add_constant(pooled.drop(columns="y"))).fit()
    resid = fit.resid
    xcols = [c for c in pooled.columns if c != "y"]

    card: list[dict[str, Any]] = []

    # --- premia time series -------------------------------------------------
    dw = float(durbin_watson(lam - lam.mean()))
    card.append(_row("Durbin-Watson (FM premia)", dw, np.nan, dw < 1.5 or dw > 2.5, "d near 2 means no first-order autocorrelation in the monthly premia.", "Use Newey-West standard errors with at least the significant Ljung-Box lag.", threshold="flag if d < 1.5 or d > 2.5"))
    lags = [lag for lag in (1, 5, 12, 21) if lag < len(lam) // 2]
    lb = acorr_ljungbox(lam - lam.mean(), lags=lags, return_df=True) if lags else pd.DataFrame()
    for lag, row in lb.iterrows():
        card.append(_row(f"Ljung-Box lag {lag} (FM premia)", float(row["lb_stat"]), float(row["lb_pvalue"]), row["lb_pvalue"] < alpha, f"Tests autocorrelation up to lag {lag} in the monthly premia.", f"Set the Newey-West lag to at least {lag}."))
    jb_stat, jb_p, skew, kurt = jarque_bera(lam)
    card.append(_row("Jarque-Bera (FM premia)", float(jb_stat), float(jb_p), jb_p < alpha, f"Skewness {skew:.2f}, kurtosis {kurt:.2f}; non-normality matters mainly in small samples.", "Use bootstrap standard errors" + (" (T < 60)." if len(lam) < 60 else "; with T >= 60 the t-test is asymptotically fine.")))
    brk = andrews_sup_f(lam)
    if np.isfinite(brk.get("sup_f", np.nan)):
        card.append(_row("Andrews sup-F break (FM premia)", brk["sup_f"], brk["p_value"], brk["p_value"] < alpha, f"Most likely break {pd.Timestamp(brk['break_date']).date()} (90% CI {pd.Timestamp(brk['break_ci90_low']).date()} to {pd.Timestamp(brk['break_ci90_high']).date()}); premium {brk['pre_mean']:.4f} before vs {brk['post_mean']:.4f} after.", "Report sub-period results; the full-sample premium averages two regimes.", threshold=f"5% critical value {brk['critical_5pct']:.2f}"))
    chow_date = payload.get("break_date")
    chow_res: dict[str, Any] = {}
    if chow_date:
        split = pd.Series((lam.index >= pd.Timestamp(chow_date)).astype(float), index=lam.index)
        chow_res = chow_test(lam, pd.DataFrame(index=lam.index), split)
        if not np.isfinite(chow_res["f_stat"]):
            chow_res["note"] = f"{chow_date} leaves fewer than 3 months on one side of the sample ({lam.index.min().date()} to {lam.index.max().date()})."
        else:
            card.append(_row(f"Chow test at {chow_date} (FM premia)", chow_res["f_stat"], chow_res["p_value"], chow_res["p_value"] < alpha, "Tests whether the mean premium differs before and after the chosen date.", "Report the two sub-periods separately."))

    # --- pooled cross-section ------------------------------------------------
    exog = sm.add_constant(pooled[xcols]).to_numpy()
    vif_rows = []
    if len(xcols) > 1:
        for i, name in enumerate(xcols, start=1):
            v = float(variance_inflation_factor(exog, i))
            vif_rows.append({"variable": name, "vif": v, "flag": "red" if v > 10 else "amber" if v > 5 else "green"})
            if v > 5:
                card.append(_row(f"VIF {name}", v, np.nan, True, "Collinearity inflates this regressor's standard error.", "Drop or orthogonalize the most collinear control.", threshold="amber > 5, red > 10"))
    else:
        vif_rows.append({"variable": xcols[0], "vif": 1.0, "flag": "green"})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        white = het_white(resid, exog) if exog.shape[1] <= 8 else (np.nan, np.nan, np.nan, np.nan)
        bp = het_breuschpagan(resid, exog)
        reset = linear_reset(fit, power=[2, 3], use_f=True)
    if np.isfinite(white[0]):
        card.append(_row("White heteroskedasticity", float(white[0]), float(white[1]), white[1] < alpha, "nR² from regressing squared residuals on regressors, squares and cross-products.", "Use heteroskedasticity-robust or clustered standard errors."))
    card.append(_row("Breusch-Pagan heteroskedasticity", float(bp[0]), float(bp[1]), bp[1] < alpha, "nR² from regressing squared residuals on the regressors.", "Use heteroskedasticity-robust or clustered standard errors."))
    card.append(_row("Ramsey RESET (powers 2, 3)", float(reset.statistic), float(reset.pvalue), reset.pvalue < alpha, "Tests for missing nonlinear structure in the fitted values.", "Add squared or interaction terms, or rank-transform the signal."))
    wooldridge = _wooldridge_serial(panel, controls)
    if wooldridge:
        card.append(_row("Wooldridge panel serial correlation", wooldridge["f_stat"], wooldridge["p_value"], wooldridge["p_value"] < alpha, "Tests AR(1) errors within assets (Wooldridge 2002).", "Cluster standard errors by asset or use Driscoll-Kraay."))
    card.append(_row("Jarque-Bera (pooled residuals)", float(jarque_bera(resid)[0]), float(jarque_bera(resid)[1]), jarque_bera(resid)[1] < alpha, "Cross-sectional return residuals are almost always fat-tailed.", "Winsorize the dependent variable or use rank-based robustness checks."))

    influence = _month_influence(lam, top_n)
    obs_influence = _observation_influence(fit, pooled, top_n) if payload.get("extended_influence", True) else pd.DataFrame()
    fragile = influence["fragile"].any() if not influence.empty else False
    if fragile:
        card.append(_row("Influential months (Cook's distance)", float(influence["cooks_distance"].max()), np.nan, True, "Removing a single month moves the premium by more than 20%.", "Report results excluding the flagged months; check for data errors.", threshold="flag if one month moves the premium > 20%"))

    partial = _partial_residuals(fit, pooled, xcols) if payload.get("partial_residual_plots", True) else pd.DataFrame()
    heteroskedasticity_plot = pd.DataFrame({"fitted": fit.fittedvalues, "squared_residual": resid ** 2}).sample(min(2000, len(resid)), random_state=1)

    card_df = pd.DataFrame(card)
    red = int(card_df["flag"].eq("red").sum()) if not card_df.empty else 0
    tables = {
        "diagnostic_report_card": card_df,
        "vif_table": vif_rows,
        "serial_correlation_tests": [{"test": f"ljung_box_lag_{lag}", "statistic": float(r["lb_stat"]), "p_value": float(r["lb_pvalue"])} for lag, r in lb.iterrows()] + [{"test": "durbin_watson", "statistic": dw, "p_value": None}] + ([{"test": "wooldridge_panel_ar1", "statistic": wooldridge["f_stat"], "p_value": wooldridge["p_value"]}] if wooldridge else []),
        "heteroskedasticity_tests": [{"test": "white", "statistic": white[0], "p_value": white[1]}, {"test": "breusch_pagan", "statistic": float(bp[0]), "p_value": float(bp[1])}],
        "reset_test": [{"test": "ramsey_reset", "f_stat": float(reset.statistic), "p_value": float(reset.pvalue), "flag": bool(reset.pvalue < alpha)}],
        "structural_break_tests": [{k: v for k, v in brk.items() if k != "path"}] + ([{"test": "chow", **chow_res}] if chow_res else []),
        "influential_observation_table": influence,
        "dfbeta_dffits_table": obs_influence,
        "normality_tests": [{"series": "fm_premia", "jarque_bera": float(jb_stat), "p_value": float(jb_p), "skewness": float(skew), "kurtosis": float(kurt)}],
    }
    charts = {
        "residual_autocorrelation_correlogram": _correlogram(lam),
        "heteroskedasticity_plot": heteroskedasticity_plot,
        "andrews_structural_break": brk.get("path", pd.DataFrame()),
        "partial_residual_plots": partial,
        "residual_distribution": [{"residual": float(v)} for v in (lam - lam.mean())],
        "qq_plot": _qq(lam - lam.mean()),
    }
    summary = [
        {"label": "Red flags", "value": red},
        {"label": "Months", "value": len(lam)},
        {"label": "Durbin-Watson", "value": dw},
        {"label": "Break p", "value": brk.get("p_value")},
        {"label": "Max VIF", "value": max((r["vif"] for r in vif_rows), default=None)},
    ]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"config": panel.config, "research_caveats": panel.caveats, "pooled_rows": int(len(pooled))}}


def _row(test: str, statistic: float, p: float, flagged: bool, explanation: str, recommendation: str, threshold: str | None = None) -> dict[str, Any]:
    return {"test": test, "statistic": statistic, "p_value_or_threshold": p if np.isfinite(p) else threshold, "flag": "red" if flagged else "green", "explanation": explanation, "recommendation": recommendation if flagged else "No action needed."}


def _time_demeaned(panel: Panel, controls: list[str]) -> pd.DataFrame:
    stacked = panel.stacked(controls)
    within = stacked - stacked.groupby(level="date").transform("mean")
    if len(within) > MAX_POOLED_ROWS:  # keep whole months so the within-date structure survives
        dates = within.index.get_level_values("date").unique()
        keep = dates[np.linspace(0, len(dates) - 1, max(12, int(len(dates) * MAX_POOLED_ROWS / len(within)))).astype(int)]
        within = within[within.index.get_level_values("date").isin(keep)]
    return within.sort_index()


def _wooldridge_serial(panel: Panel, controls: list[str]) -> dict[str, Any]:
    import statsmodels.api as sm

    """Wooldridge (2002) test: in first differences, corr(de_t, de_{t-1}) = -0.5 under no serial correlation."""

    stacked = panel.stacked(controls).swaplevel().sort_index()
    diff = stacked.groupby(level="ticker").diff().dropna()
    if len(diff) < 100:
        return {}
    fit = sm.OLS(diff["y"], diff.drop(columns="y")).fit()
    e = fit.resid.groupby(level="ticker")
    lagged = e.shift(1)
    df = pd.concat([fit.resid.rename("e"), lagged.rename("e_lag")], axis=1).dropna()
    groups = df.index.get_level_values("ticker")
    ar = sm.OLS(df["e"], df[["e_lag"]]).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(groups)[0]})
    f = float(((ar.params["e_lag"] + 0.5) / ar.bse["e_lag"]) ** 2)
    return {"f_stat": f, "p_value": float(stats.f.sf(f, 1, len(set(groups)) - 1)), "rho": float(ar.params["e_lag"])}


def _month_influence(lam: pd.Series, top_n: int) -> pd.DataFrame:
    """Cook's distance of each month for the FM premium (a regression on a constant)."""

    t = len(lam)
    if t < 6:
        return pd.DataFrame()
    mean = lam.mean()
    s2 = lam.var(ddof=1)
    h = 1 / t
    cooks = (lam - mean) ** 2 * h / (s2 * (1 - h) ** 2)
    without = (lam.sum() - lam) / (t - 1)
    out = pd.DataFrame({"date": lam.index, "cooks_distance": cooks.values, "premium_with": mean, "premium_without": without.values})
    out["change_pct"] = (out["premium_without"] - mean) / abs(mean) * 100 if mean else np.nan
    out["fragile"] = out["change_pct"].abs() > 20
    return out.sort_values("cooks_distance", ascending=False).head(top_n).reset_index(drop=True)


def _observation_influence(fit: Any, pooled: pd.DataFrame, top_n: int) -> pd.DataFrame:
    from statsmodels.stats.outliers_influence import OLSInfluence

    infl = OLSInfluence(fit)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cooks = pd.Series(infl.cooks_distance[0], index=pooled.index)
    top = cooks.nlargest(top_n).index
    # Closed-form leave-one-out DFBETAS for the top rows only (the statsmodels
    # path refits the model once per observation).
    pos = pooled.index.get_indexer(top)
    exog = np.asarray(fit.model.exog, dtype=float)
    xtxi = np.asarray(fit.normalized_cov_params, dtype=float)
    h = infl.hat_matrix_diag
    e = np.asarray(fit.resid, dtype=float)
    n, k = exog.shape
    s2_i = (float(fit.ssr) - e ** 2 / (1 - h)) / (n - k - 1)
    sig = list(fit.params.index).index("signal")
    dfbeta_signal = (exog[pos] @ xtxi[:, sig]) * e[pos] / (1 - h[pos]) / np.sqrt(s2_i[pos] * xtxi[sig, sig])
    dfbetas_top = pd.Series(dfbeta_signal, index=top)
    dffits = pd.Series(e / np.sqrt(s2_i * (1 - h)) * np.sqrt(h / (1 - h)), index=pooled.index)
    out = pd.DataFrame({
        "date": [d for d, _ in top],
        "ticker": [tk for _, tk in top],
        "cooks_distance": cooks.loc[top].values,
        "dffits": dffits.loc[top].values,
        "dfbeta_signal": dfbetas_top.values,
    })
    n, k = len(pooled), len(fit.params)
    out["dffits_threshold"] = 2 * np.sqrt(k / n)
    out["dfbeta_threshold"] = 2 / np.sqrt(n)
    return out


def _partial_residuals(fit: Any, pooled: pd.DataFrame, xcols: list[str], bins: int = 20) -> pd.DataFrame:
    """Binned component-plus-residual points for each regressor."""

    rows = []
    for name in xcols:
        comp = fit.params[name] * pooled[name] + fit.resid
        frame = pd.DataFrame({"x": pooled[name], "cpr": comp})
        frame["bin"] = pd.qcut(frame["x"].rank(method="first"), bins, labels=False)
        g = frame.groupby("bin").agg(x=("x", "mean"), component_plus_residual=("cpr", "mean"))
        g["linear_fit"] = fit.params[name] * g["x"]
        g["regressor"] = name
        rows.append(g.reset_index(drop=True))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _correlogram(series: pd.Series, max_lag: int = 24) -> pd.DataFrame:
    acf = acf_frame(series, max_lag)
    band = 1.96 / np.sqrt(max(len(series.dropna()), 1))
    acf["upper_95"] = band
    acf["lower_95"] = -band
    acf["significant"] = acf["acf"].abs() > band
    return acf


def _qq(resid: pd.Series) -> pd.DataFrame:
    r = np.sort(resid.dropna().to_numpy())
    if len(r) < 3:
        return pd.DataFrame()
    theo = stats.norm.ppf((np.arange(1, len(r) + 1) - 0.5) / len(r))
    return pd.DataFrame({"theoretical": theo, "sample": (r - r.mean()) / r.std()})
