"""Feature 04: Regime Conditional Analyzer.

Every conditioning variable is measured at the formation date, so a regime is
known before the holding period starts.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd

from .estimators import fama_macbeth, sort_portfolios
from .panel import Panel, build_panel
from .stats import _supf_null, auto_nw_lag, chow_test, mean_test, ols

CONDITIONS = {
    "vix_20": "VIX above 20",
    "vix_30": "VIX above 30",
    "yield_curve_inverted": "10y-2y Treasury slope negative",
    "market_12m_negative": "trailing 12-month market return negative",
    "market_6m_negative": "trailing 6-month market return negative",
    "realized_vol_top_tercile": "market realized vol in top tercile of trailing 5 years",
    "credit_spread_wide": "Baa-Treasury credit spread above its trailing 5-year median",
    "nber_recession": "NBER recession",
    "vol_regime": "4-state VIX regime (low <15, medium 15-25, high 25-35, crisis >35)",
}
CONTINUOUS = {"vix_20": "vix", "vix_30": "vix", "yield_curve_inverted": "slope", "market_12m_negative": "mkt12", "market_6m_negative": "mkt6", "realized_vol_top_tercile": "rv", "credit_spread_wide": "credit"}


def state_variables(panel: Panel) -> pd.DataFrame:
    """Continuous conditioning variables at each formation date."""

    m = panel.macro
    f = panel.factors
    idx = panel.returns.index
    mkt = (f["mkt_rf"] + f.get("rf", 0)).reindex(idx) if "mkt_rf" in f else panel.returns.mean(axis=1)
    vix = m.get("vixcls", m.get("vix_close")) if not m.empty else None
    out = pd.DataFrame(index=idx)
    out["vix"] = vix.reindex(idx) if vix is not None else np.nan
    if {"dgs10", "dgs2"}.issubset(m.columns):
        out["slope"] = (m["dgs10"] - m["dgs2"]).reindex(idx)
    out["mkt12"] = (1 + mkt).rolling(12).apply(np.prod, raw=True) - 1
    out["mkt6"] = (1 + mkt).rolling(6).apply(np.prod, raw=True) - 1
    rv = mkt.rolling(3).std() * np.sqrt(12)
    out["rv"] = rv.rolling(60, min_periods=36).rank(pct=True)
    credit_col = "baa10y" if "baa10y" in m.columns else "bamlc0a0cm" if "bamlc0a0cm" in m.columns else None
    if credit_col:  # Moody's Baa - 10y has full history; ICE BofA IG OAS is licence-limited on FRED
        cs = m[credit_col].reindex(idx)
        out["credit"] = cs - cs.rolling(60, min_periods=36).median()
    if "usrec" in m.columns:
        out["recession"] = m["usrec"].reindex(idx)
    return out.reindex(panel.dates)


def regime_labels(states: pd.DataFrame, condition: str, threshold: float | None = None) -> pd.Series:
    s = states
    if condition == "vol_regime":
        v = s["vix"]
        return pd.Series(np.select([v < 15, v < 25, v < 35, v >= 35], ["low", "medium", "high", "crisis"], default=None), index=s.index).where(v.notna())
    if condition == "nber_recession":
        return s["recession"].map({1.0: "recession", 0.0: "expansion"})
    col = CONTINUOUS[condition]
    default = {"vix_20": 20, "vix_30": 30, "yield_curve_inverted": 0.0, "market_12m_negative": 0.0, "market_6m_negative": 0.0, "realized_vol_top_tercile": 2 / 3, "credit_spread_wide": 0.0}[condition]
    thr = default if threshold is None else threshold
    x = s[col]
    if condition in {"yield_curve_inverted", "market_12m_negative", "market_6m_negative"}:
        on = x < thr
    else:
        on = x > thr
    return pd.Series(np.where(on, "on", "off"), index=s.index).where(x.notna())


def run_regime(payload: dict[str, Any]) -> dict[str, Any]:
    panel = build_panel(payload)
    cond1 = str(payload.get("conditioning_variable") or payload.get("regime_source") or "vix_20").lower()
    cond1 = {"vix": "vix_20", "recession": "nber_recession", "credit_spread": "credit_spread_wide", "realized_vol": "realized_vol_top_tercile"}.get(cond1, cond1)
    cond2 = str(payload.get("second_condition") or "none").lower()
    for c in [cond1] + ([cond2] if cond2 != "none" else []):
        if c not in CONDITIONS:
            raise ValueError(f"conditioning_variable must be one of {list(CONDITIONS)}")
    min_obs = int(payload.get("min_observations") or 24)
    structure = str(payload.get("regime_structure") or "two_state").lower()
    threshold_mode = str(payload.get("threshold_selection") or "fixed").lower()
    controls = list(panel.controls)
    lag = max(auto_nw_lag(len(panel.dates)), panel.holding_months)
    states = state_variables(panel)

    threshold_table = pd.DataFrame()
    threshold = None
    if threshold_mode == "data_driven" and cond1 in CONTINUOUS:
        threshold_table, threshold = threshold_search(panel, states, cond1, controls, min_obs)
    labels = regime_labels(states, cond1, threshold)
    if cond2 != "none":
        l2 = regime_labels(states, cond2)
        both = (labels.isin(["on", "recession", "high", "crisis"])) & (l2.isin(["on", "recession", "high", "crisis"]))
        labels = pd.Series(np.where(both, "both_on", "other"), index=labels.index).where(labels.notna() & l2.notna())

    _, slopes = fama_macbeth(panel, controls)
    lam = slopes["signal"].dropna()
    reg = labels.reindex(lam.index)
    port = sort_portfolios(panel, int(payload.get("sort_portfolios") or 5))
    ls = port["long_short"] if not port.empty else pd.Series(dtype=float)

    cond_rows, skipped = [], []
    for state, group in lam.groupby(reg):
        if len(group) < min_obs:
            skipped.append({"regime": state, "months": len(group), "reason": f"fewer than {min_obs} months"})
            continue
        t = mean_test(group, min(lag, max(1, len(group) // 4)))
        ls_s = ls.reindex(group.index).dropna()
        sd = ls_s.std()
        cond_rows.append({
            "regime": state, "months": t["n"], "coefficient": t["mean"], "se": t["se"], "t_stat": t["t"], "p_value": t["p"],
            "lower_95": t["mean"] - 1.96 * t["se"], "upper_95": t["mean"] + 1.96 * t["se"],
            "ls_annual_return": float(ls_s.mean() * 12 / panel.holding_months) if len(ls_s) else np.nan,
            "ls_sharpe": float(ls_s.mean() / sd * np.sqrt(12 / panel.holding_months)) if sd else np.nan,
        })
    cond = pd.DataFrame(cond_rows)
    valid_states = set(cond["regime"]) if not cond.empty else set()

    stacked = panel.stacked(controls)
    date_state = labels.reindex(stacked.index.get_level_values("date"))
    date_state.index = stacked.index
    on_states = {"on", "recession", "high", "crisis", "both_on"}
    binary = date_state.isin(on_states).astype(float).where(date_state.notna() & date_state.isin(valid_states))
    within = _time_demean(stacked)
    chow = chow_test(within["y"], within.drop(columns="y"), binary) if binary.notna().any() else {}
    chow["verdict"] = ("coefficients differ across regimes" if chow.get("p_value", 1) < 0.05 else "no significant difference") if chow else "not estimable"
    chow["note"] = "Chow test on slopes after removing date means (time fixed effects), so market-wide return shifts between regimes do not count; assumes independent errors, see the interaction regression for time-clustered inference."
    interaction = interaction_regression(stacked, binary)
    diff = premium_difference(lam, labels, on_states, lag)
    amp = amplification(cond)

    qreg = quantile_by_state(lam, states, cond1) if structure in {"quantile", "two_state"} and cond1 in CONTINUOUS else pd.DataFrame()
    markov = markov_switching(lam) if structure in {"markov", "two_state"} else {"summary": {}, "probabilities": pd.DataFrame()}

    tables = {
        "conditional_coefficient_table": cond,
        "chow_test": [chow],
        "premium_difference_test": [diff],
        "interaction_regression": interaction,
        "economic_magnitude_by_regime": [amp],
        "regime_conditional_sharpe": cond[["regime", "ls_sharpe", "ls_annual_return", "months"]] if not cond.empty else [],
        "threshold_search": threshold_table,
        "quantile_regression": qreg,
        "markov_switching_model": [markov["summary"]],
        "skipped_regimes": skipped,
        "regime_definition": [{"condition": cond1, "description": CONDITIONS[cond1], "second_condition": cond2, "threshold": threshold, "threshold_selection": threshold_mode, "minimum_months": min_obs}],
    }
    charts = {
        "coefficient_comparison": cond[["regime", "coefficient", "lower_95", "upper_95"]] if not cond.empty else [],
        "regime_timeline": pd.DataFrame({"date": labels.index, "regime": labels.values}),
        "threshold_search": threshold_table,
        "markov_state_probability": markov["probabilities"],
        "regime_return_chart": cond[["regime", "ls_annual_return", "ls_sharpe"]] if not cond.empty else [],
    }
    summary = [
        {"label": "Condition", "value": CONDITIONS[cond1]},
        {"label": "Chow p", "value": chow.get("p_value")},
        {"label": "Interaction t", "value": next((r["t_stat"] for r in interaction if r["term"] == "signal_x_regime"), None)},
        {"label": "Amplification", "value": amp.get("amplification_factor")},
    ]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"config": panel.config, "research_caveats": list(panel.caveats) + ([markov["caveat"]] if markov.get("caveat") else [])}}


def interaction_regression(stacked: pd.DataFrame, regime: pd.Series) -> list[dict[str, Any]]:
    """y = a + b signal + g regime + d signal x regime + controls, SE clustered by date."""

    df = stacked.assign(regime=regime).dropna()
    if df.empty or df["regime"].nunique() < 2:
        return []
    df["signal_x_regime"] = df["signal"] * df["regime"]
    xcols = [c for c in df.columns if c != "y"]
    fit = ols(df["y"], df[xcols], cov="cluster", groups=pd.Series(df.index.get_level_values("date"), index=df.index))
    return [{"term": k, "coefficient": float(fit["params"][k]), "se": float(fit["bse"][k]), "t_stat": float(fit["tvalues"][k]), "p_value": float(fit["pvalues"][k]), "nobs": fit["nobs"]} for k in fit["params"].index]


def premium_difference(lam: pd.Series, labels: pd.Series, on_states: set[str], lag: int) -> dict[str, Any]:
    """Time-series test on the monthly FM premia: lambda_t = a + d * 1[regime on] with HAC SE."""

    d = labels.reindex(lam.index)
    dummy = d.isin(on_states).astype(float).where(d.notna())
    fit = ols(lam, dummy.rename("regime_on").to_frame(), cov="hac", lags=lag)
    if fit["model"] is None:
        return {"available": False}
    return {"premium_off": float(fit["params"]["const"]), "premium_difference": float(fit["params"]["regime_on"]), "t_stat": float(fit["tvalues"]["regime_on"]), "p_value": float(fit["pvalues"]["regime_on"]), "months": fit["nobs"], "method": "Fama-MacBeth premia regressed on the regime dummy, Newey-West SE"}


def threshold_search(panel: Panel, states: pd.DataFrame, condition: str, controls: list[str], min_obs: int) -> tuple[pd.DataFrame, float | None]:
    """Grid-search the conditioning variable for the threshold maximising the Chow F (Hansen-style)."""

    col = CONTINUOUS[condition]
    x = states[col].dropna()
    stacked = _time_demean(panel.stacked(controls))
    dates = stacked.index.get_level_values("date")
    rows = []
    for q in np.linspace(0.15, 0.85, 15):
        thr = float(x.quantile(q))
        on = (x > thr) if condition not in {"yield_curve_inverted", "market_12m_negative", "market_6m_negative"} else (x < thr)
        if on.sum() < min_obs or (~on).sum() < min_obs:
            continue
        g = pd.Series(on.reindex(dates).astype(float).to_numpy(), index=stacked.index)
        res = chow_test(stacked["y"], stacked.drop(columns="y"), g)
        rows.append({"quantile": q, "threshold": thr, "f_stat": res["f_stat"], "p_value_pointwise": res["p_value"], "months_on": int(on.sum())})
    table = pd.DataFrame(rows)
    if table.empty:
        return table, None
    best = table.loc[table["f_stat"].idxmax()]
    k = len(controls) + 2
    null = _supf_null(k, 0.15)
    table["sup_f_p_value"] = float(np.mean(null >= best["f_stat"]))
    table["selected"] = table["threshold"] == best["threshold"]
    return table, float(best["threshold"])


def quantile_by_state(lam: pd.Series, states: pd.DataFrame, condition: str) -> pd.DataFrame:
    """How the monthly premium varies continuously with the conditioning variable.

    Quantile regressions lambda_t = a_tau + b_tau z_t at tau in {.1,.25,.5,.75,.9}
    with z the standardized conditioning variable.
    """

    from statsmodels.regression.quantile_regression import QuantReg
    import statsmodels.api as sm

    z = states[CONTINUOUS[condition]].reindex(lam.index)
    df = pd.concat([lam.rename("lam"), ((z - z.mean()) / z.std()).rename("z")], axis=1).dropna()
    if len(df) < 36:
        return pd.DataFrame()
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for tau in [0.1, 0.25, 0.5, 0.75, 0.9]:
            fit = QuantReg(df["lam"], sm.add_constant(df[["z"]])).fit(q=tau, max_iter=2000)
            rows.append({"quantile": tau, "intercept": float(fit.params["const"]), "slope_on_condition": float(fit.params["z"]), "se": float(fit.bse["z"]), "t_stat": float(fit.tvalues["z"]), "p_value": float(fit.pvalues["z"])})
    return pd.DataFrame(rows)


def markov_switching(lam: pd.Series) -> dict[str, Any]:
    """Two-state Markov-switching mean/variance model of the monthly premium (Hamilton 1989)."""

    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

    y = lam.dropna()
    if len(y) < 48:
        return {"summary": {"status": "needs at least 48 months"}, "probabilities": pd.DataFrame()}
    # Deterministic start: split months by trailing volatility (no random restarts), so repeated runs give identical fits.
    vol = y.rolling(6, min_periods=3).std().bfill()
    hi = (vol > vol.median()).to_numpy()
    yv = y.to_numpy(float)
    start = np.array([0.9, 0.1, yv[~hi].mean(), yv[hi].mean(), max(yv[~hi].var(), 1e-8), max(yv[hi].var(), 1e-8)])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = MarkovRegression(y.reset_index(drop=True), k_regimes=2, trend="c", switching_variance=True).fit(disp=False, start_params=start)
        params = fit.params
        means = [float(params[f"const[{i}]"]) for i in range(2)]
        high = int(np.argmax(means))
        probs = pd.DataFrame({"date": y.index, "state_high_premium_probability": fit.smoothed_marginal_probabilities[high].to_numpy()})
        durations = fit.expected_durations
        return {"summary": {"premium_state_low": min(means), "premium_state_high": max(means), "expected_duration_high": float(durations[high]), "expected_duration_low": float(durations[1 - high]), "log_likelihood": float(fit.llf), "aic": float(fit.aic), "bic": float(fit.bic)}, "probabilities": probs}
    except Exception as exc:  # LinAlgError or non-convergence: fall back to the volatility split
        hi_s = pd.Series(hi, index=y.index)
        m_hi, m_lo = float(y[hi_s].mean()), float(y[~hi_s].mean())
        high_state = hi_s if m_hi >= m_lo else ~hi_s
        runs = lambda m: float(len(m) / max(int((m != m.shift()).sum()), 1))  # noqa: E731  mean run length
        note = f"Markov-switching fit failed ({exc.__class__.__name__}); showing a simple split of months by trailing 6-month volatility above or below its median instead."
        return {"summary": {"premium_state_low": min(m_hi, m_lo), "premium_state_high": max(m_hi, m_lo), "expected_duration_high": runs(high_state), "expected_duration_low": runs(high_state), "fallback": "volatility_threshold", "caveat": note}, "probabilities": pd.DataFrame({"date": y.index, "state_high_premium_probability": high_state.astype(float).to_numpy()}), "caveat": note}


STRESS_ORDER = ["crisis", "high", "both_on", "on", "recession", "medium", "other", "off", "expansion", "low"]


def amplification(cond: pd.DataFrame) -> dict[str, Any]:
    """Regime amplification factor: long-short spread in the most stressed regime over the calmest one."""

    if cond.empty or cond["ls_annual_return"].isna().all() or len(cond) < 2:
        return {"amplification_factor": np.nan}
    ranked = cond.assign(order=cond["regime"].map(lambda r: STRESS_ORDER.index(r) if r in STRESS_ORDER else 99)).sort_values("order")
    stress, calm = ranked.iloc[0], ranked.iloc[-1]
    factor = stress["ls_annual_return"] / calm["ls_annual_return"] if calm["ls_annual_return"] else np.nan
    return {"stress_regime": stress["regime"], "stress_annual_spread": stress["ls_annual_return"], "calm_regime": calm["regime"], "calm_annual_spread": calm["ls_annual_return"], "amplification_factor": factor, "definition": "stress-regime annual long-short spread divided by calm-regime spread (sign kept)"}


def _time_demean(stacked: pd.DataFrame) -> pd.DataFrame:
    return stacked - stacked.groupby(level="date").transform("mean")
