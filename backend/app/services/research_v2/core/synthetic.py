"""Feature 09: Synthetic Control Engine.

The outcome is each asset's log cumulative return, normalised to zero at the
start of the window, observed monthly. The main fit uses pysyncon (classic
SCM with data-driven predictor weights, augmented SCM with ridge bias
correction, robust SCM with low-rank denoising). Generalized SC is an
interactive-fixed-effects model (Xu 2017) with a cross-validated number of
factors. Placebo loops and conformal inference (Chernozhukov, Wuthrich and
Zhu 2021) use a fast simplex-constrained least-squares solver.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import nnls

from .common import latex_table
from .data_loader import UnknownSymbolsError, load_event_upload, normalize_symbol, ohlcv_matrices, parse_symbols, point_in_time_fundamental, static_sectors

VARIANTS = {"classic", "augmented", "generalized", "robust"}


def simplex_weights(y_pre: np.ndarray, x_pre: np.ndarray, penalty: float = 1e4) -> np.ndarray:
    """min ||y - Xw|| s.t. w >= 0, sum w = 1 via NNLS with a heavily weighted sum-to-one row."""

    a = np.vstack([x_pre, penalty * np.ones(x_pre.shape[1])])
    b = np.concatenate([y_pre, [penalty]])
    w, _ = nnls(a, b, maxiter=50 * x_pre.shape[1])
    s = w.sum()
    return w / s if s > 0 else np.full(x_pre.shape[1], 1 / x_pre.shape[1])


def _outcome_matrix(tickers: list[str], lookback_days: int) -> pd.DataFrame:
    daily = ohlcv_matrices(tickers, lookback_days)
    if not daily:
        raise UnknownSymbolsError(tickers[:5])
    close = daily["Close"].resample("ME").last()
    logret = np.log(close).diff()
    return logret


def _donor_pool(payload: dict[str, Any], treated: str) -> list[str]:
    mode = str(payload.get("donor_pool") or "all_untreated").lower()
    if mode == "user_list":
        donors = parse_symbols({"universe": payload.get("donor_list") or ""}, default_limit=500)
    else:
        donors = parse_symbols({**payload, "max_symbols": payload.get("max_symbols") or 400}, default_limit=400)
    donors = [d for d in donors if d != treated]
    if mode == "same_sector":
        sectors = static_sectors()
        sec = sectors.get(treated)
        if sec is None:
            raise ValueError(f"No sector on file for {treated}; choose another donor pool.")
        donors = [d for d in donors if sectors.get(d) == sec]
    return donors


def run_synthetic(payload: dict[str, Any]) -> dict[str, Any]:
    events = load_event_upload(payload.get("event_csv_path"))
    staggered = str(payload.get("multiple_treated") or "off").lower() == "staggered" and not events.empty
    treated = normalize_symbol(payload.get("treated_unit") or (events["ticker"].iloc[0] if not events.empty else ""))
    if not treated:
        raise ValueError("Set the treated unit (a ticker, sector ETF or country ETF).")
    date = payload.get("treatment_date") or (events.loc[events["ticker"] == treated, "treatment_date"].min() if not events.empty else None)
    if date is None or pd.isna(date):
        raise ValueError("Set the treatment date.")
    tdate = pd.Timestamp(date)
    variant = str(payload.get("scm_variant") or "classic").lower()
    if variant not in VARIANTS:
        raise ValueError(f"scm_variant must be one of {sorted(VARIANTS)}")
    lookback = int(payload.get("lookback_days") or 3650)
    parse_symbols({"universe": treated})  # raises for unknown tickers
    donors = _donor_pool(payload, treated)
    rets = _outcome_matrix([treated, *donors], lookback)
    if payload.get("donor_pool") == "same_size_decile":
        donors = _same_size_decile(treated, donors, rets.index, tdate)
    rets = rets[[c for c in [treated, *donors] if c in rets.columns]]
    pre_mask = rets.index < tdate
    pre_months = int(pre_mask.sum())
    if pre_months < 24:
        raise ValueError(f"Synthetic control needs at least 24 pre-treatment months; the data give {pre_months}.")
    rets = rets.loc[:, rets.loc[pre_mask].notna().mean() > 0.95].iloc[1:].fillna(0.0)
    if treated not in rets:
        raise ValueError(f"{treated} lacks enough pre-treatment history.")
    donors = [c for c in rets.columns if c != treated][: int(payload.get("donor_limit") or 80)]
    y = rets.cumsum()  # log cumulative return path
    pre_mask = y.index < tdate
    n_pre = int(pre_mask.sum())

    fit = _fit_variant(variant, y, treated, donors, pre_mask, payload)
    synth = fit["synthetic"]
    gap = y[treated] - synth
    pre_rmspe = float(np.sqrt((gap[pre_mask] ** 2).mean()))
    post_rmspe = float(np.sqrt((gap[~pre_mask] ** 2).mean()))
    ratio = post_rmspe / pre_rmspe if pre_rmspe else np.nan
    pre_sd = float(y.loc[pre_mask, treated].std())
    weights = fit["weights"]

    placebo = placebo_in_space(y, treated, donors, pre_mask)
    rank = int((placebo["post_pre_ratio"] >= ratio).sum()) + 1
    p_space = rank / (len(placebo) + 1)
    in_time = placebo_in_time(y, treated, donors, pre_mask)
    loo = leave_one_out(y, treated, donors, pre_mask, weights)
    conformal = conformal_band(y, treated, donors, pre_mask, float(payload.get("conformal_alpha") or 0.1))
    stag = staggered_scm(events, payload) if staggered else pd.DataFrame()

    w_sorted = weights[weights > 0.001].sort_values(ascending=False)
    hhi = float((weights ** 2).sum())
    donor_table = pd.DataFrame({"donor": w_sorted.index, "weight": w_sorted.values})
    donor_table = donor_table.merge(_donor_characteristics(list(w_sorted.index) + [treated], y.index[pre_mask]), on="donor", how="left")
    post_gap = gap[~pre_mask]
    effect = float(post_gap.iloc[-1]) if len(post_gap) else np.nan
    loo_range = (float(loo["post_effect"].min()), float(loo["post_effect"].max())) if not loo.empty else (np.nan, np.nan)
    fragile = bool(not loo.empty and (np.sign(loo_range[0]) != np.sign(loo_range[1]) or (loo["post_effect"] - effect).abs().max() > 0.5 * abs(effect)))

    path = pd.DataFrame({"date": y.index, "treated": y[treated].values, "synthetic": synth.values, "gap": gap.values, "post": ~pre_mask})
    tables = {
        "treatment_effect": [{"treated_unit": treated, "treatment_date": tdate, "variant": variant, "cumulative_effect_log": effect, "mean_post_gap": float(post_gap.mean()), "pre_months": n_pre, "post_months": int((~pre_mask).sum()), "donors": len(donors)}],
        "pre_treatment_fit": [{"pre_rmspe": pre_rmspe, "post_rmspe": post_rmspe, "post_pre_rmspe_ratio": ratio, "pre_outcome_sd": pre_sd, "fit_quality": "reliable" if pre_rmspe < 0.25 * pre_sd else "weak: the synthetic control does not track the treated unit before treatment, so the effect is unreliable"}],
        "rmspe_ratio_ranking": [{"treated_ratio": ratio, "rank": rank, "placebos": len(placebo), "placebo_p_value": p_space}],
        "donor_weight_table": donor_table,
        "donor_concentration": [{"hhi": hhi, "effective_donors": 1 / hhi if hhi else np.nan, "top3_share": float(w_sorted.head(3).sum()), "nonzero_donors": int((weights > 0.001).sum()), "concentrated": bool(w_sorted.head(3).sum() > 0.8)}],
        "leave_one_out_sensitivity": loo,
        "leave_one_out_summary": [{"effect_min": loo_range[0], "effect_max": loo_range[1], "fragile": fragile}],
        "in_time_placebo": [in_time],
        "conformal_confidence_band": conformal,
        "variant_details": [fit.get("details", {})],
        "staggered_adoption_scm": stag,
        "latex_export": [{"table": "scm", "latex": latex_table("Synthetic control estimate", pd.DataFrame([{"Treated": treated, "Effect": effect, "Pre-RMSPE": pre_rmspe, "RMSPE ratio": ratio, "Placebo p": p_space}])) + "\n\n" + latex_table("Donor weights", donor_table[["donor", "weight"]])}],
    }
    charts = {
        "treated_vs_synthetic_path": path,
        "gap_plot": path[["date", "gap", "post"]],
        "placebo_gap_paths": placebo.attrs.get("paths", pd.DataFrame()),
        "rmspe_ratio_chart": pd.concat([placebo[["unit", "post_pre_ratio"]], pd.DataFrame([{"unit": treated, "post_pre_ratio": ratio, "treated": True}])], ignore_index=True).sort_values("post_pre_ratio", ascending=False),
        "conformal_band": conformal,
        "staggered_event_study": stag.attrs.get("event_path", pd.DataFrame()) if not stag.empty else [],
    }
    summary = [{"label": "Effect (log cum. return)", "value": effect}, {"label": "Placebo p", "value": p_space}, {"label": "Pre-RMSPE", "value": pre_rmspe}, {"label": "RMSPE ratio", "value": ratio}]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"research_caveats": ["Outcome is the log cumulative return from the start of the window."]}}


def _fast_synth():
    """pysyncon Synth whose inner QP uses the analytic gradient (same optimum, ~20x fewer function calls)."""

    from pysyncon import Synth
    from scipy.optimize import Bounds, LinearConstraint, minimize

    last: dict[str, np.ndarray] = {}  # warm start: consecutive V candidates have nearby optima (strictly convex QP, same solution)

    class FastSynth(Synth):
        @staticmethod
        def w_optimize(V_mat, X0, X1, qp_method="SLSQP", qp_options={"maxiter": 1000}):
            n_c = X0.shape[1]
            P = X0.T @ V_mat @ X0
            q = X1.T @ V_mat @ X0
            res = minimize(lambda x: 0.5 * x @ P @ x - q @ x, last.get("w", np.full(n_c, 1 / n_c)), jac=lambda x: P @ x - q, bounds=Bounds(np.zeros(n_c), np.ones(n_c)), constraints=LinearConstraint(np.ones(n_c), 1.0, 1.0), method=qp_method, options=qp_options)
            last["w"] = np.clip(res["x"], 0.0, 1.0)
            return res["x"], float(res["fun"])

    return FastSynth


def _fit_variant(variant: str, y: pd.DataFrame, treated: str, donors: list[str], pre_mask: np.ndarray, payload: dict[str, Any]) -> dict[str, Any]:
    from pysyncon import AugSynth, Dataprep, RobustSynth, Synth

    if variant == "generalized":
        return generalized_scm(y, treated, donors, pre_mask)
    long = y[[treated, *donors]].stack().rename("y").reset_index()
    long.columns = ["time", "unit", "y"]
    long["time"] = long["time"].map({d: i for i, d in enumerate(y.index)})
    pre_t = [i for i, m in enumerate(pre_mask) if m]
    step = max(1, len(pre_t) // 8)
    special = [("y", [t], "mean") for t in pre_t[::step]]
    dp = Dataprep(foo=long, predictors=[], predictors_op="mean", dependent="y", unit_variable="unit", time_variable="time", treatment_identifier=treated, controls_identifier=donors, time_predictors_prior=pre_t, time_optimize_ssr=pre_t, special_predictors=special)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if variant == "classic":
            model = _fast_synth()()
            model.fit(dataprep=dp)
            w = model.weights(round=6).reindex(donors).fillna(0)
            details = {"method": "classic SCM (Abadie-Diamond-Hainmueller), predictor weights V optimised", "loss_v": float(getattr(model, "loss_V", np.nan))}
        elif variant == "augmented":
            model = AugSynth()
            model.fit(dataprep=dp)
            w = pd.Series(model.W, index=donors) if hasattr(model, "W") else model.weights(round=6).reindex(donors).fillna(0)
            details = {"method": "augmented SCM (Ben-Michael, Feller, Rothstein 2021), ridge bias correction", "lambda": float(getattr(model, "lambda_", np.nan))}
        else:
            lam = float(payload.get("robust_lambda") or 0.1)
            model = RobustSynth()
            model.fit(dataprep=dp, lambda_=lam, sv_count=int(payload.get("robust_rank") or 3))
            w = model.weights(round=6).reindex(donors).fillna(0)
            details = {"method": "robust SCM (Amjad, Shah, Shen 2018), low-rank denoising + ridge", "lambda": lam}
    synth = pd.Series(y[donors].to_numpy() @ w.to_numpy(), index=y.index)
    if variant in {"augmented", "robust"}:
        # both estimators return counterfactual paths that include their correction; use the effect they report
        z0, z1 = dp.make_outcome_mats(time_period=list(range(len(y))))
        cf = pd.Series(np.asarray(model._synthetic(z0)).ravel(), index=y.index) if hasattr(model, "_synthetic") else synth
        synth = cf
    return {"weights": w, "synthetic": synth, "details": details}


def generalized_scm(y: pd.DataFrame, treated: str, donors: list[str], pre_mask: np.ndarray, max_rank: int = 6) -> dict[str, Any]:
    """Interactive fixed effects (Xu 2017): factors from donors, treated loadings from the pre-period, rank by CV."""

    x = y[donors].to_numpy()
    xc = x - x.mean(axis=0)
    u, s, vt = np.linalg.svd(xc, full_matrices=False)
    t_pre = y.loc[pre_mask, treated].to_numpy()
    best, best_err = 1, np.inf
    for r in range(1, min(max_rank, len(s)) + 1):
        f = u[:, :r] * s[:r]
        errs = []
        for hold in range(len(t_pre)):  # leave-one-period-out CV on the pre-period
            keep = np.ones(len(t_pre), bool)
            keep[hold] = False
            a = np.column_stack([np.ones(keep.sum()), f[:len(t_pre)][keep]])
            coef, *_ = np.linalg.lstsq(a, t_pre[keep], rcond=None)
            pred = coef[0] + f[hold] @ coef[1:]
            errs.append((t_pre[hold] - pred) ** 2)
        if np.mean(errs) < best_err:
            best, best_err = r, float(np.mean(errs))
    f = u[:, :best] * s[:best]
    a = np.column_stack([np.ones(len(t_pre)), f[:len(t_pre)]])
    coef, *_ = np.linalg.lstsq(a, t_pre, rcond=None)
    synth = pd.Series(coef[0] + f @ coef[1:], index=y.index)
    loadings_w = simplex_weights(synth[pre_mask].to_numpy(), y.loc[pre_mask, donors].to_numpy())
    return {"weights": pd.Series(loadings_w, index=donors), "synthetic": synth, "details": {"method": "generalized SCM (interactive fixed effects, Xu 2017)", "factors": best, "cv_mse": best_err}}


def _fast_fit(y: pd.DataFrame, unit: str, donors: list[str], pre_mask: np.ndarray) -> pd.Series:
    w = simplex_weights(y.loc[pre_mask, unit].to_numpy(), y.loc[pre_mask, donors].to_numpy())
    return pd.Series(y[donors].to_numpy() @ w, index=y.index)


def placebo_in_space(y: pd.DataFrame, treated: str, donors: list[str], pre_mask: np.ndarray) -> pd.DataFrame:
    rows, paths = [], []
    for d in donors:
        others = [c for c in donors if c != d]
        gap = y[d] - _fast_fit(y, d, others, pre_mask)
        pre = float(np.sqrt((gap[pre_mask] ** 2).mean()))
        post = float(np.sqrt((gap[~pre_mask] ** 2).mean()))
        rows.append({"unit": d, "pre_rmspe": pre, "post_rmspe": post, "post_pre_ratio": post / pre if pre else np.nan})
        paths.append(pd.DataFrame({"date": y.index, "unit": d, "gap": gap.values}))
    out = pd.DataFrame(rows)
    out.attrs["paths"] = pd.concat(paths, ignore_index=True) if paths else pd.DataFrame()
    return out


def placebo_in_time(y: pd.DataFrame, treated: str, donors: list[str], pre_mask: np.ndarray) -> dict[str, Any]:
    pre_idx = np.where(pre_mask)[0]
    fake = pre_idx[len(pre_idx) // 2]
    mask = np.arange(len(y)) < fake
    sub = y.iloc[: pre_idx[-1] + 1]
    gap = sub[treated] - _fast_fit(sub, treated, donors, mask[: len(sub)])
    pre = float(np.sqrt((gap[mask[: len(sub)]] ** 2).mean()))
    post = float(np.sqrt((gap[~mask[: len(sub)]] ** 2).mean()))
    return {"fake_treatment_date": y.index[fake], "pre_rmspe": pre, "post_rmspe": post, "post_pre_ratio": post / pre if pre else np.nan, "fake_effect": float(gap.iloc[-1]), "verdict": "no effect at the fake date" if post / pre < 2 else "an 'effect' appears at the fake date: the real result may be spurious"}


def leave_one_out(y: pd.DataFrame, treated: str, donors: list[str], pre_mask: np.ndarray, weights: pd.Series) -> pd.DataFrame:
    rows = []
    for d in weights[weights > 0.01].index:
        others = [c for c in donors if c != d]
        gap = y[treated] - _fast_fit(y, treated, others, pre_mask)
        rows.append({"excluded_donor": d, "excluded_weight": float(weights[d]), "post_effect": float(gap[~pre_mask].iloc[-1]), "pre_rmspe": float(np.sqrt((gap[pre_mask] ** 2).mean()))})
    return pd.DataFrame(rows)


def conformal_band(y: pd.DataFrame, treated: str, donors: list[str], pre_mask: np.ndarray, alpha: float = 0.1, grid_size: int = 60) -> pd.DataFrame:
    """Chernozhukov-Wuthrich-Zhu (2021) conformal CI for the per-period effect.

    For each post period T and candidate effect theta, subtract theta from the
    treated outcome at T, refit on pre-periods + T, and compare |u_T| with the
    pre-period residuals (permutation p-value). Periods are the monthly
    increments of the gap so residuals are closer to exchangeable.
    """

    inc = y.diff().fillna(y.iloc[0])
    pre_idx = np.where(pre_mask)[0]
    post_idx = np.where(~pre_mask)[0]
    x_all = inc[donors].to_numpy()
    y_all = inc[treated].to_numpy()
    w0 = simplex_weights(y_all[pre_idx], x_all[pre_idx])
    resid_sd = float(np.std(y_all[pre_idx] - x_all[pre_idx] @ w0)) or 1e-4
    rows = []
    for t in post_idx:
        point = float(y_all[t] - x_all[t] @ w0)
        grid = np.linspace(point - 6 * resid_sd, point + 6 * resid_sd, grid_size)
        keep = []
        idx = np.append(pre_idx, t)
        for theta in grid:
            yy = y_all[idx].copy()
            yy[-1] -= theta
            w = simplex_weights(yy, x_all[idx])
            u = np.abs(yy - x_all[idx] @ w)
            p = float(np.mean(u >= u[-1]))
            if p > alpha:
                keep.append(theta)
        rows.append({"date": y.index[t], "effect": point, "lower": min(keep) if keep else np.nan, "upper": max(keep) if keep else np.nan})
    out = pd.DataFrame(rows)
    out["cumulative_effect"] = out["effect"].cumsum()
    out["coverage"] = 1 - alpha
    return out


def staggered_scm(events: pd.DataFrame, payload: dict[str, Any], window: int = 12) -> pd.DataFrame:
    """One SCM per treated unit, aligned in event time; pooled effect with a placebo-based band."""

    rows, paths = [], []
    for _, ev in events.head(int(payload.get("max_events") or 25)).iterrows():
        tk, td = ev["ticker"], pd.Timestamp(ev["treatment_date"])
        try:
            donors = [d for d in _donor_pool(payload, tk) if d not in set(events["ticker"])][:60]
            rets = _outcome_matrix([tk, *donors], int(payload.get("lookback_days") or 3650))
            pre = rets.index < td
            rets = rets.loc[:, rets.loc[pre].notna().mean() > 0.95].iloc[1:].fillna(0.0)
            if tk not in rets or pre.sum() < 24:
                continue
            y = rets.cumsum()
            pre = y.index < td
            dn = [c for c in y.columns if c != tk]
            gap = y[tk] - _fast_fit(y, tk, dn, pre)
            base = gap[pre].iloc[-1]
            pos0 = int(np.argmax(~pre))
            for k in range(-window, window + 1):
                if 0 <= pos0 + k < len(gap):
                    paths.append({"ticker": tk, "event_time": k, "gap": float(gap.iloc[pos0 + k] - base)})
            rows.append({"treated_unit": tk, "treatment_date": td, "donors": len(dn), "pre_rmspe": float(np.sqrt((gap[pre] ** 2).mean())), "effect_12m": float(gap.iloc[min(pos0 + 11, len(gap) - 1)] - base)})
        except Exception as exc:
            rows.append({"treated_unit": tk, "treatment_date": td, "status": f"skipped: {exc}"})
    out = pd.DataFrame(rows)
    if paths:
        p = pd.DataFrame(paths).groupby("event_time")["gap"].agg(["mean", "std", "count"]).reset_index()
        p["lower_95"] = p["mean"] - 1.96 * p["std"] / np.sqrt(p["count"])
        p["upper_95"] = p["mean"] + 1.96 * p["std"] / np.sqrt(p["count"])
        out.attrs["event_path"] = p.rename(columns={"mean": "pooled_effect"})
    return out


def _same_size_decile(treated: str, donors: list[str], dates: pd.DatetimeIndex, tdate: pd.Timestamp) -> list[str]:
    at = pd.DatetimeIndex([dates[dates < tdate][-1]])
    shares = point_in_time_fundamental("Ordinary Shares Number", at, [treated, *donors])
    close = ohlcv_matrices([treated, *donors], 800)["Close"].resample("ME").last().reindex(at)
    mcap = (shares * close).iloc[0].dropna()
    if treated not in mcap:
        raise ValueError(f"No point-in-time market cap for {treated} before treatment; choose another donor pool.")
    dec = pd.qcut(mcap.rank(method="first"), 10, labels=False)
    return [d for d in donors if d in dec.index and dec[d] == dec[treated]]


def _donor_characteristics(units: list[str], pre_dates: pd.DatetimeIndex) -> pd.DataFrame:
    daily = ohlcv_matrices(units, 3650)
    close_m = daily["Close"].resample("ME").last().reindex(pre_dates)
    rets = close_m.pct_change(fill_method=None)
    sectors = static_sectors()
    return pd.DataFrame({
        "donor": units,
        "pre_mean_monthly_return": [float(rets[u].mean()) if u in rets else np.nan for u in units],
        "pre_volatility": [float(rets[u].std()) if u in rets else np.nan for u in units],
        "sector": [sectors.get(u) for u in units],
    })
