"""Cross-sectional estimators shared by Research V2 features."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .panel import Panel
from .performance import _fm_kernel, vectorized_portfolio_returns
from .stats import auto_nw_lag, bootstrap_mean_pvalue, mean_test, ols, stationary_bootstrap_means

FACTOR_SETS = {
    "capm": ["mkt_rf"],
    "ff3": ["mkt_rf", "smb", "hml"],
    "ff5": ["mkt_rf", "smb", "hml", "rmw", "cma"],
    "ff5_mom": ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"],
}


# ---------------------------------------------------------------------------
# Fama-MacBeth


def fm_slopes(dependent: pd.DataFrame, regressors: dict[str, pd.DataFrame], min_obs: int = 20, weights: pd.DataFrame | None = None) -> pd.DataFrame:
    """Monthly cross-sectional OLS (or WLS when ``weights`` is given) slopes. One row per date."""

    names = list(regressors)
    idx, cols = dependent.index, dependent.columns
    y = dependent.to_numpy(dtype=np.float64)
    x = np.empty((len(idx), len(cols), len(names) + 1), dtype=np.float64)
    x[:, :, 0] = 1.0
    for j, name in enumerate(names, start=1):
        r = regressors[name]
        if not (r.shape == dependent.shape and r.index.equals(idx) and np.array_equal(np.asarray(r.columns), np.asarray(cols))):
            r = r.reindex(index=idx, columns=cols)
        x[:, :, j] = r.to_numpy(dtype=np.float64)
    if weights is not None:  # WLS: scale each row by sqrt(w); missing or non-positive weights drop the asset
        w = weights.reindex(index=idx, columns=cols).to_numpy(dtype=np.float64)
        root = np.sqrt(np.where(w > 0, w, np.nan))
        y = y * root
        x = x * root[:, :, None]
    coef, r2, nobs = _fm_kernel(y, x, int(min_obs))
    frame = pd.DataFrame(coef[:, 1:], index=idx, columns=names)
    frame["intercept"] = coef[:, 0]
    frame["r2"] = r2
    frame["n_assets"] = nobs
    return frame[frame["n_assets"] >= min_obs]


def fama_macbeth(panel: Panel, control_names: list[str] | None = None, nw_lag: int | None = None, signal: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    regs = {"signal": panel.signal if signal is None else signal}
    for name in (panel.controls if control_names is None else control_names):
        if name in panel.controls:
            regs[name] = panel.controls[name]
    slopes = fm_slopes(panel.dependent, regs)
    if slopes.empty:
        return pd.DataFrame(), slopes
    lag = int(nw_lag) if nw_lag is not None else max(auto_nw_lag(len(slopes)), panel.holding_months)
    rows = []
    for term in [c for c in slopes.columns if c not in {"r2", "n_assets"}]:
        test = mean_test(slopes[term], lag)
        rows.append({"term": term, "lambda": test["mean"], "nw_se": test["se"], "t_stat": test["t"], "p_value": test["p"], "months": test["n"], "nw_lag": lag})
    table = pd.DataFrame(rows)
    table["mean_r2"] = float(slopes["r2"].mean())
    table["mean_assets"] = float(slopes["n_assets"].mean())
    order = {"signal": 0, "intercept": 99}
    return table.sort_values("term", key=lambda s: s.map(lambda v: order.get(v, 1))).reset_index(drop=True), slopes


def fm_validity(slopes: pd.DataFrame, n_assets: float, reps: int = 1000, lag: int = 4) -> dict[str, Any]:
    """Classify the panel and give a bootstrap SE for the signal slope when needed.

    FM standard errors are time-series standard errors of the monthly slopes,
    so their reliability is governed by T (months) and by how noisy each
    cross-section is (small N). Thresholds: valid when T >= 120 and N >= 100;
    conservative when T >= 60 and N >= 30; otherwise invalid. Outside the
    valid regime the stationary-bootstrap SE of the mean slope is reported as
    the corrected SE.
    """

    t = int(slopes["signal"].notna().sum()) if "signal" in slopes else 0
    regime = "valid" if t >= 120 and n_assets >= 100 else "conservative" if t >= 60 and n_assets >= 30 else "invalid"
    boot_se = np.nan
    if t >= 12:
        boot = stationary_bootstrap_means(slopes["signal"].dropna().to_numpy(), reps)
        boot_se = float(boot.std(ddof=1)) if len(boot) else np.nan
    nw = mean_test(slopes["signal"], lag)["se"] if t else np.nan
    return {
        "months": t,
        "mean_assets": float(n_assets),
        "n_over_t": float(n_assets / t) if t else np.nan,
        "regime": regime,
        "reported_se": "newey_west" if regime == "valid" else "stationary_bootstrap",
        "newey_west_se": nw,
        "bootstrap_se": boot_se,
        "corrected_t": float(slopes["signal"].mean() / boot_se) if regime != "valid" and boot_se else np.nan,
        "message": f"T = {t} months and mean N = {n_assets:.0f} put classical FM standard errors in the {regime} regime" + ("." if regime == "valid" else "; the stationary-bootstrap SE is reported instead."),
        "rule": "valid: T>=120 and N>=100; conservative: T>=60 and N>=30; otherwise invalid",
    }


# ---------------------------------------------------------------------------
# portfolio sorts


def sort_portfolios(panel: Panel, buckets: int, signal: pd.DataFrame | None = None) -> pd.DataFrame:
    """Bucket returns over the holding period after each formation date (Q1 = low signal)."""

    pr = vectorized_portfolio_returns(panel.signal if signal is None else signal, panel.dependent, panel.weights, int(buckets))
    if pr.empty:
        return pr
    pr = pr.set_index("date").sort_index()
    pr = pr[[f"Q{i}" for i in range(1, buckets + 1) if f"Q{i}" in pr.columns]]
    pr["long_short"] = pr.iloc[:, -1] - pr.iloc[:, 0]
    return pr


def sort_table(panel: Panel, port: pd.DataFrame, benchmark: str = "ff5", boot_reps: int = 1000) -> pd.DataFrame:
    factors = benchmark_factors(panel, benchmark)
    rf = panel.factors["rf"] if "rf" in panel.factors else pd.Series(0.0, index=panel.factors.index)
    lag = max(auto_nw_lag(len(port)), panel.holding_months)
    rows = []
    h = panel.holding_months
    for col in port.columns:
        r = port[col].dropna()
        excess = r if col == "long_short" else r - rf.reindex(r.index).fillna(0) * h
        test = mean_test(r, lag)
        alpha = factor_alpha(excess, factors, lag)
        vol = float(r.std())
        rows.append({
            "portfolio": col,
            "mean_return": test["mean"],
            "std": vol,
            "sharpe_annual": float(excess.mean() / vol * np.sqrt(12 / h)) if vol else np.nan,
            "t_stat": test["t"],
            "p_value": test["p"],
            "bootstrap_p_value": bootstrap_mean_pvalue(r, boot_reps),
            "alpha": alpha["alpha"],
            "alpha_t": alpha["t"],
            "periods": test["n"],
        })
    return pd.DataFrame(rows)


def double_sort(panel: Panel, second: pd.DataFrame, buckets: int = 5, method: str = "independent") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean returns of K x K portfolios. Sequential sorts sort on ``second`` within signal buckets."""

    s1 = panel.signal.stack().rename("s1")
    s2 = second.reindex_like(panel.signal).stack().rename("s2")
    y = panel.dependent.stack().rename("y")
    w = panel.weights.stack().rename("w")
    df = pd.concat([s1, s2, y, w], axis=1).dropna()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    df.index = df.index.set_names(["date", "ticker"])
    labels = [f"{i}" for i in range(1, buckets + 1)]

    def cut(v: pd.Series) -> pd.Series:
        if v.notna().sum() < buckets * 2:
            return pd.Series(np.nan, index=v.index)
        return pd.qcut(v.rank(method="first"), buckets, labels=labels).astype(float)

    df["row"] = df.groupby(level="date")["s1"].transform(cut)
    if method == "sequential":
        df["col"] = df.groupby([df.index.get_level_values("date"), "row"])["s2"].transform(cut)
    else:
        df["col"] = df.groupby(level="date")["s2"].transform(cut)
    df = df.dropna(subset=["row", "col"])
    df["wy"] = df["y"] * df["w"]
    g = df.groupby([df.index.get_level_values("date"), "row", "col"])
    monthly = (g["wy"].sum() / g["w"].sum()).rename("ret").reset_index()
    monthly.columns = ["date", "row", "col", "ret"]
    series = monthly.pivot_table(index="date", columns=["row", "col"], values="ret")
    means = monthly.groupby(["row", "col"])["ret"].mean().unstack("col")
    means.index = [f"S1_Q{int(i)}" for i in means.index]
    means.columns = [f"S2_Q{int(c)}" for c in means.columns]
    means["row_spread"] = means.iloc[:, -1] - means.iloc[:, 0]
    col_spread = means.iloc[-1] - means.iloc[0]
    means.loc["col_spread"] = col_spread
    series.columns = [f"S1Q{int(r)}_S2Q{int(c)}" for r, c in series.columns]
    return means, series


# ---------------------------------------------------------------------------
# factor regressions


def benchmark_factors(panel: Panel, benchmark: str) -> pd.DataFrame:
    """Factor returns scaled to the panel's holding period, indexed by formation date.

    Holding-period portfolio returns at formation date t cover (t, t+h]; factor
    returns are compounded over the same window so alphas are comparable.
    """

    key = str(benchmark or "ff5").lower()
    cols = FACTOR_SETS.get(key)
    if cols is None:
        raise ValueError(f"factor_benchmark must be one of {list(FACTOR_SETS)}")
    f = panel.factors[[c for c in cols if c in panel.factors.columns]]
    if f.empty:
        return f
    h = panel.holding_months
    compounded = (1 + f).rolling(h).apply(np.prod, raw=True) - 1
    return compounded.shift(-h).reindex(panel.dates)


def factor_alpha(y: pd.Series, factors: pd.DataFrame, lag: int = 4) -> dict[str, Any]:
    frame = pd.concat([y.rename("y"), factors], axis=1, sort=True).dropna()
    if factors.empty or len(frame) < factors.shape[1] + 12:
        return {"alpha": np.nan, "t": np.nan, "p": np.nan, "r2": np.nan, "n": len(frame), "loadings": {}}
    fit = ols(frame["y"], frame[factors.columns], cov="hac", lags=lag)
    return {
        "alpha": float(fit["params"]["const"]),
        "t": float(fit["tvalues"]["const"]),
        "p": float(fit["pvalues"]["const"]),
        "r2": fit["rsquared"],
        "n": fit["nobs"],
        "loadings": {k: float(v) for k, v in fit["params"].items() if k != "const"},
        "loading_t": {k: float(v) for k, v in fit["tvalues"].items() if k != "const"},
        "resid": fit["resid"],
    }


def grs_test(port: pd.DataFrame, factors: pd.DataFrame) -> dict[str, Any]:
    """Gibbons-Ross-Shanken (1989) with MLE covariances."""

    cols = [c for c in port.columns if c != "long_short"]
    frame = pd.concat([port[cols], factors], axis=1).dropna()
    t, n, l = len(frame), len(cols), factors.shape[1]
    if factors.empty or t <= n + l + 1:
        return {"available": False, "reason": f"needs T > N + L + 1 (T={t}, N={n}, L={l})"}
    f = frame[factors.columns].to_numpy(float)
    x = np.column_stack([np.ones(t), f])
    y = frame[cols].to_numpy(float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    alpha = beta[0]
    resid = y - x @ beta
    sigma = resid.T @ resid / t
    mu = f.mean(axis=0)
    omega = np.atleast_2d(np.cov(f, rowvar=False, bias=True))
    quad_a = float(alpha @ np.linalg.pinv(sigma) @ alpha)
    quad_f = float(mu @ np.linalg.pinv(omega) @ mu)
    grs = (t / n) * ((t - n - l) / (t - l - 1)) * quad_a / (1 + quad_f)
    df2 = t - n - l
    return {
        "available": True,
        "grs_stat": float(grs),
        "p_value": float(stats.f.sf(grs, n, df2)),
        "df1": n,
        "df2": int(df2),
        "mean_abs_alpha": float(np.abs(alpha).mean()),
        "pricing_error_sharpe": float(np.sqrt(max(quad_a, 0))),
        "factor_sharpe": float(np.sqrt(max(quad_f, 0))),
        "periods": t,
    }


def two_pass(test_assets: pd.DataFrame, factors: pd.DataFrame, bandwidth: int = 4) -> dict[str, Any]:
    """Two-pass cross-sectional risk premia: Shanken (1992) OLS vs GMM-GLS.

    * Shanken: OLS second pass on time-series betas, with the Shanken EIV
      correction Var(l) = [(B'B)^-1 B'SB (B'B)^-1 (1 + l'Sf^-1 l) + Sf] / T.
    * GMM: linearmodels two-step estimator with GLS second pass (weighting by
      the residual covariance, which changes the estimate itself) and a
      Bartlett-kernel GMM covariance that accounts for estimated betas.
    Both use excess returns and no free intercept (traded-factor pricing).
    """

    from linearmodels.asset_pricing import LinearFactorModel

    frame = pd.concat([test_assets, factors], axis=1).dropna()
    assets = frame[test_assets.columns]
    facs = frame[factors.columns]
    t, n, k = len(frame), assets.shape[1], facs.shape[1]
    if t < 36 or n <= k:
        return {"available": False, "reason": "needs >= 36 periods and more test assets than factors"}
    f = facs.to_numpy(float)
    r = assets.to_numpy(float)
    x = np.column_stack([np.ones(t), f])
    coef, *_ = np.linalg.lstsq(x, r, rcond=None)
    beta = coef[1:].T                                   # n x k
    resid = r - x @ coef
    sigma = resid.T @ resid / t
    sigma_f = np.atleast_2d(np.cov(f, rowvar=False))
    rbar = r.mean(axis=0)
    btb_inv = np.linalg.pinv(beta.T @ beta)
    lam = btb_inv @ beta.T @ rbar
    c = float(lam @ np.linalg.pinv(sigma_f) @ lam)
    var_ols = (btb_inv @ beta.T @ sigma @ beta @ btb_inv) / t
    var_shanken = var_ols * (1 + c) + sigma_f / t
    se_shanken = np.sqrt(np.clip(np.diag(var_shanken), 0, None))
    se_naive = np.sqrt(np.clip(np.diag(var_ols), 0, None))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gls = LinearFactorModel(assets, facs, sigma=sigma).fit(cov_type="kernel", kernel="bartlett", bandwidth=bandwidth)
    rows = []
    for i, name in enumerate(facs.columns):
        g_rp, g_se = float(gls.risk_premia[name]), float(gls.risk_premia_se[name])
        rows.append({
            "factor": name,
            "lambda_ols": float(lam[i]),
            "se_uncorrected": float(se_naive[i]),
            "se_shanken": float(se_shanken[i]),
            "t_shanken": float(lam[i] / se_shanken[i]) if se_shanken[i] else np.nan,
            "lambda_gmm_gls": g_rp,
            "se_gmm": g_se,
            "t_gmm": g_rp / g_se if g_se else np.nan,
            "material_disagreement": bool(abs(lam[i] - g_rp) > max(se_shanken[i], g_se) or ((abs(lam[i] / se_shanken[i]) > 1.96) != (abs(g_rp / g_se) > 1.96))) if se_shanken[i] and g_se else False,
        })
    return {
        "available": True,
        "table": pd.DataFrame(rows),
        "betas": pd.DataFrame(beta, index=assets.columns, columns=facs.columns),
        "shanken_multiplier": float(np.sqrt(1 + c)),
        "j_stat": float(gls.j_statistic.stat),
        "j_p_value": float(gls.j_statistic.pval),
        "periods": t,
        "test_assets": n,
    }


def weak_identification(betas: pd.DataFrame, factor: str, t_beta: pd.Series | None = None) -> dict[str, Any]:
    """Flag weak or useless factors before the premium is reported (Kan-Zhang 1999; Kleibergen 2009).

    A premium is identified only if test-asset betas on the factor are large
    and vary across assets, and the beta matrix is well conditioned.
    """

    if betas is None or betas.empty or factor not in betas.columns:
        return {"available": False}
    b = betas[factor].astype(float)
    x = np.column_stack([np.ones(len(betas)), betas.to_numpy(float)])
    sv = np.linalg.svd(x, compute_uv=False)
    cond = float(sv[0] / sv[-1]) if sv[-1] > 0 else np.inf
    dispersion = float(b.std())
    weak = cond > 30 or dispersion < 0.1
    return {
        "available": True,
        "factor": factor,
        "beta_dispersion": dispersion,
        "beta_range": float(b.max() - b.min()),
        "condition_number": cond,
        "weak_identification_flag": bool(weak),
        "bias_direction": "Premium estimate is biased toward spurious significance and its SE is understated (useless-factor bias)." if weak else "Betas are dispersed and the design is well conditioned.",
        "rule": "flag when condition number > 30 or cross-sectional std of betas < 0.10",
    }


# ---------------------------------------------------------------------------
# panel regressions


def panel_regression(panel: Panel, control_names: list[str], fixed_effects: str = "none", cov: str = "clustered_both", bandwidth: int | None = None, weighted: bool = False) -> dict[str, Any]:
    """Pooled / FE panel OLS (WLS by market cap when ``weighted``) with linearmodels, plus FE-vs-RE Hausman test."""

    from linearmodels.panel import PanelOLS

    df = panel.stacked(control_names)
    if weighted:
        df = df.join(panel.market_cap.stack().rename("__w"), how="inner")
        df = df[df["__w"] > 0]
    if len(df) < 100:
        return {"available": False, "reason": "fewer than 100 panel observations"}
    df = df.swaplevel().sort_index()
    df.index = df.index.set_names(["entity", "time"])
    w = df.pop("__w") if "__w" in df else None
    xcols = [c for c in df.columns if c != "y"]
    entity = fixed_effects in {"asset", "two_way"}
    time = fixed_effects in {"time", "two_way"}
    exog = df[xcols].assign(const=1.0)
    model = PanelOLS(df["y"], exog, weights=w, entity_effects=entity, time_effects=time, drop_absorbed=True, check_rank=False)
    bw = int(bandwidth or max(auto_nw_lag(df.index.get_level_values("time").nunique()), panel.holding_months))
    cov_args = {
        "unadjusted": {"cov_type": "unadjusted"},
        "robust": {"cov_type": "robust"},
        "clustered_time": {"cov_type": "clustered", "cluster_time": True},
        "clustered_asset": {"cov_type": "clustered", "cluster_entity": True},
        "clustered_both": {"cov_type": "clustered", "cluster_entity": True, "cluster_time": True},
        "driscoll_kraay": {"cov_type": "kernel", "kernel": "bartlett", "bandwidth": bw},
    }
    if cov not in cov_args:
        raise ValueError(f"se_type must be one of {list(cov_args)}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = model.fit(**cov_args[cov])
        hausman = _hausman(df, xcols) if entity else {"statistic": np.nan, "p_value": np.nan, "note": "Hausman compares asset FE with random effects; select asset or two-way FE."}
    rows = [{"term": name, "coefficient": float(fit.params[name]), "se": float(fit.std_errors[name]), "t_stat": float(fit.tstats[name]), "p_value": float(fit.pvalues[name])} for name in fit.params.index]
    return {
        "available": True,
        "table": pd.DataFrame(rows),
        "rsquared": float(fit.rsquared),
        "within_r2": float(fit.rsquared_within),
        "between_r2": float(fit.rsquared_between),
        "overall_r2": float(fit.rsquared_overall),
        "nobs": int(fit.nobs),
        "entities": int(fit.entity_info["total"]),
        "periods": int(fit.time_info["total"]),
        "asset_fe": entity,
        "time_fe": time,
        "se_type": cov,
        "hausman": hausman,
    }


def _hausman(df: pd.DataFrame, xcols: list[str]) -> dict[str, Any]:
    from linearmodels.panel import PanelOLS, RandomEffects

    fe = PanelOLS(df["y"], df[xcols], entity_effects=True, check_rank=False).fit()
    re = RandomEffects(df["y"], df[xcols].assign(const=1.0)).fit()
    b = fe.params[xcols] - re.params[xcols]
    v = fe.cov.loc[xcols, xcols] - re.cov.loc[xcols, xcols]
    stat = float(b @ np.linalg.pinv(v.to_numpy()) @ b)
    return {"statistic": stat, "df": len(xcols), "p_value": float(stats.chi2.sf(abs(stat), len(xcols))), "verdict": "asset fixed effects required (RE inconsistent)" if stats.chi2.sf(abs(stat), len(xcols)) < 0.05 else "random effects not rejected"}
