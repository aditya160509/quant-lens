"""ML V2 volatility implementation."""
from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from scipy.stats import chi2, t as student_t
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge
from .common import build_provenance, date_str, get_artifact, put_artifact, response, summary
from .estimators import garman_klass_vol, yang_zhang_vol
from .data_loader import normalize_symbol, universe_label
from .panel import load_context
from .performance import max_drawdown, sharpe
from .regimes import filtered_stress_probability


def arch_family_vol_models(returns: pd.Series, ann: float, cap: int = 1000) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
    """Fit a capped ARCH-family model grid and return selection/weights/news-impact rows."""

    r = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().tail(cap) * 100.0
    if len(r) < 220:
        return [], [], [], "insufficient_rows"
    try:
        from arch import arch_model
    except Exception as exc:
        return [], [], [], f"arch_unavailable: {exc}"

    specs = [
        ("GARCH", {"vol": "GARCH", "p": 1, "o": 0, "q": 1}),
        ("GJR-GARCH", {"vol": "GARCH", "p": 1, "o": 1, "q": 1}),
        ("EGARCH", {"vol": "EGARCH", "p": 1, "o": 1, "q": 1}),
        ("APARCH", {"vol": "APARCH", "p": 1, "o": 1, "q": 1}),
        ("FIGARCH", {"vol": "FIGARCH", "p": 1, "q": 1}),
    ]
    dists = ["normal", "t", "skewt", "ged"]
    rows: list[dict[str, Any]] = []
    fit_objects: list[tuple[str, str, Any]] = []
    failures = []
    for spec_name, spec_kwargs in specs:
        for dist in dists:
            try:
                model = arch_model(r, mean="Constant", dist=dist, rescale=False, **spec_kwargs)
                fit = model.fit(disp="off", show_warning=False, options={"maxiter": 80})
                if fit.convergence_flag:
                    raise ValueError(f"Optimizer did not converge: code {fit.convergence_flag}")
                forecast = fit.forecast(horizon=1, reindex=False).variance.iloc[-1, 0]
                rows.append({
                    "model": spec_name,
                    "distribution": dist,
                    "aic": float(fit.aic),
                    "bic": float(fit.bic),
                    "loglikelihood": float(fit.loglikelihood),
                    "forecast_vol": float(math.sqrt(max(forecast, 0.0)) / 100.0 * math.sqrt(ann)),
                })
                fit_objects.append((spec_name, dist, fit))
            except Exception as exc:
                failures.append({"model":spec_name,"distribution":dist,"status":"failed","reason":str(exc)[:300]})
    if not rows:
        return [], [], [], "fit_failed"
    aic = np.asarray([row["aic"] for row in rows], dtype=float)
    rel = np.exp(-0.5 * (aic - np.nanmin(aic)))
    weights = rel / max(float(np.nansum(rel)), 1e-12)
    for row, weight in zip(rows, weights):
        row["akaike_weight"] = float(weight)
    weight_rows = [{"model": row["model"], "distribution": row["distribution"], "ensemble_weight": row["akaike_weight"], "forecast_vol": row["forecast_vol"]} for row in rows]
    best = fit_objects[int(np.nanargmin(aic))]
    news_rows = news_impact_curve(best[2], best[0], best[1])
    return rows+failures, weight_rows, news_rows, "partial_fit" if failures else "fit"


def news_impact_curve(fit: Any, model_name: str, dist: str) -> list[dict[str, Any]]:
    if model_name not in {"GARCH","GJR-GARCH","EGARCH","APARCH"}:
        return []
    params = {str(k): float(v) for k, v in fit.params.items()}
    omega = params.get("omega", 0.0)
    alpha = params.get("alpha[1]", params.get("alpha[1]", 0.05))
    gamma = params.get("gamma[1]", params.get("gamma[1]", 0.0))
    beta = params.get("beta[1]", 0.85)
    last_var = float(np.asarray(fit.conditional_volatility)[-1] ** 2) if hasattr(fit, "conditional_volatility") else 1.0
    rows = []
    for shock in np.linspace(-4, 4, 41):
        if "EGARCH" in model_name:
            log_var = omega + beta * math.log(max(last_var, 1e-12)) + alpha * (abs(shock) - math.sqrt(2 / math.pi)) + gamma * shock
            var = math.exp(log_var)
        elif model_name == "APARCH":
            delta = params.get("delta",2.)
            epsilon = shock * math.sqrt(last_var)
            power = omega + alpha * (abs(epsilon)-gamma*epsilon)**delta + beta*last_var**(delta/2)
            var = max(power,0.)**(2/delta)
        else:
            asym = gamma if shock < 0 else 0.0
            var = omega + (alpha + asym) * (shock * math.sqrt(last_var)) ** 2 + beta * last_var
        rows.append({"shock_sigma": float(shock), "next_variance": float(max(var, 0.0)), "model": model_name, "distribution": dist})
    return rows


MAX_WATCHLIST = 50
LEVELS = (0.95, 0.99)
BASELINES = ("HAR-RV", "EWMA", "GJR-GARCH", "Regime-switch")


def diebold_mariano(loss_model: np.ndarray, loss_reference: np.ndarray, horizon: int) -> tuple[float | None, float | None]:
    """Diebold-Mariano test with a Bartlett long-run variance (lag h-1) and the Harvey-Leybourne-Newbold correction.

    A positive statistic means the reference has the lower mean loss; two-sided p-value from Student t.
    """
    d = np.asarray(loss_model, float) - np.asarray(loss_reference, float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 20 or d.std() < 1e-14:
        return None, None
    lags = max(horizon - 1, 0)
    centred = d - d.mean()
    lrv = float(centred @ centred / n)
    for k in range(1, lags + 1):
        lrv += 2 * (1 - k / (lags + 1)) * float(centred[k:] @ centred[:-k] / n)
    if lrv <= 0:
        return None, None
    stat = d.mean() / np.sqrt(lrv / n) * np.sqrt((n + 1 - 2 * horizon + horizon * (horizon - 1) / n) / n)
    return float(stat), float(2 * student_t.sf(abs(stat), n - 1))


def kupiec_pvalue(breaches: int, n: int, level: float) -> float | None:
    """Unconditional-coverage likelihood-ratio test for a VaR breach count."""
    if n < 20:
        return None
    p, x = 1 - level, breaches
    def ll(q):
        return (n - x) * np.log(max(1 - q, 1e-12)) + x * np.log(max(q, 1e-12))
    return float(chi2.sf(max(-2 * (ll(p) - ll(x / n)), 0.0), 1))


def _ewma_next_variance(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """RiskMetrics one-step variance (daily, return units squared) known at each close."""
    r = returns.to_numpy(float)
    out = np.empty(len(r))
    var = float(np.var(r[:min(21, len(r))]))
    for i, value in enumerate(r):
        var = lam * var + (1 - lam) * value * value
        out[i] = var
    return pd.Series(out, index=returns.index)


def _gjr_variance(returns: pd.Series, train_n: int) -> dict[str, Any] | None:
    """GJR-GARCH(1,1) fit on the first ``train_n`` returns; one-step variance known at each close by fixed-parameter recursion."""
    try:
        from arch import arch_model
        fit = arch_model(returns.iloc[:train_n] * 100, mean="Zero", vol="GARCH", p=1, o=1, q=1, dist="normal", rescale=False).fit(
            disp="off", show_warning=False, options={"maxiter": 100})
    except Exception:
        return None
    if fit.convergence_flag:
        return None
    omega, alpha, gamma, beta = (float(fit.params[k]) for k in ("omega", "alpha[1]", "gamma[1]", "beta[1]"))
    persistence = alpha + gamma / 2 + beta
    if not (0 < persistence < 0.9999) or omega <= 0:
        return None
    r = returns.to_numpy(float) * 100
    var = omega / (1 - persistence)
    out = np.empty(len(r))
    for i, value in enumerate(r):
        var = omega + (alpha + (gamma if value < 0 else 0.0)) * value * value + beta * var
        out[i] = var
    return {"omega": omega, "alpha": alpha, "gamma": gamma, "beta": beta, "persistence": persistence,
            "unconditional": omega / (1 - persistence), "next_variance": pd.Series(out, index=returns.index)}


def _gjr_average(gjr: dict[str, Any], horizon: int, ann: float) -> pd.Series:
    """Annualised mean variance over the next ``horizon`` sessions implied by the GJR mean-reversion."""
    p, ubar, nxt = gjr["persistence"], gjr["unconditional"], gjr["next_variance"]
    factor = (1 - p ** horizon) / (horizon * (1 - p))
    return (ubar + (nxt - ubar) * factor) / 1e4 * ann


def _perf(strategy: np.ndarray, ann: float) -> dict[str, Any]:
    s = pd.Series(strategy).dropna()
    return {"annual_return": float(s.mean() * ann), "annual_volatility": float(s.std() * np.sqrt(ann)), "sharpe": sharpe(s.to_numpy(), ann),
            "max_drawdown": max_drawdown(np.exp(s.cumsum()).to_numpy())}


def _forecast_asset(returns: pd.Series, ann: float, horizons: list[int], ml_models: dict[str, Any], peer_variance: pd.Series | None,
                    regime_override: pd.Series | None, target_vol: float, max_size: float, keep_rows: bool = True) -> dict[str, Any]:
    """Forecast tournament for one asset: HAR-type models, EWMA, GJR-GARCH and the regime-switching choice, all purged and out of sample."""
    from sklearn.base import clone
    from .validation import chronological_purged_split
    clean = returns.dropna()
    if len(clean) < 250:
        raise ValueError("Volatility forecasting needs at least 250 observed returns")
    daily_variance = returns.pow(2) * ann
    features = pd.DataFrame({"date": returns.index, "daily_variance": daily_variance, "weekly_variance": daily_variance.rolling(5).mean(),
                             "monthly_variance": daily_variance.rolling(21).mean()})
    if peer_variance is not None:
        features["peer_variance"] = peer_variance
    cols = ["daily_variance", "weekly_variance", "monthly_variance"]
    train_n = int(0.6 * len(clean))
    ewma = _ewma_next_variance(clean).reindex(returns.index) * ann
    gjr = _gjr_variance(clean, train_n)
    own = filtered_stress_probability(clean, train_n)
    notes = []
    if gjr is None:
        notes.append("GJR-GARCH did not converge; the regime choice falls back to HAR-RV")
    if own is None:
        notes.append("Regime filter could not separate two variance states; treated as calm")
    stress = (own if own is not None else pd.Series(0.0, index=clean.index))
    if regime_override is not None:
        stress = regime_override.reindex(clean.index, method="ffill").combine_first(stress)
    stress = stress.reindex(returns.index)
    models = {"HAR-RV": LinearRegression(), **ml_models}
    forecasts, errors, terms, intervals, var_es, calibration = [], [], [], [], [], {}
    sizing = None
    last_formation = features.dropna(subset=cols).tail(1)
    for horizon in horizons:
        target = daily_variance.shift(-horizon).rolling(horizon).mean()
        panel = features.assign(target=target).replace([np.inf, -np.inf], np.nan).dropna(subset=cols + ["target"])
        if "peer_variance" in panel.columns and any(n for n in models if "HAR-X" in n):
            panel = panel.dropna(subset=["peer_variance"])
        if len(panel) < 100:
            raise ValueError(f"Insufficient complete volatility history for horizon {horizon}")
        train, test = chronological_purged_split(panel, horizon, 5)
        inner, cal = chronological_purged_split(panel.iloc[train].reset_index(drop=True), horizon, 5)
        dates = panel["date"]
        actual = panel["target"].to_numpy(float)
        # A negative or near-zero linear forecast would explode standardised returns; floor at 10% of the median realised variance.
        floor = 0.1 * float(np.median(actual))
        sums = returns.shift(-horizon).rolling(horizon).sum().reindex(dates).to_numpy(float)
        preds: dict[str, dict[str, np.ndarray]] = {}
        for name, base in models.items():
            mc = cols + ["peer_variance"] if "HAR-X" in name else cols
            first = clone(base).fit(panel.iloc[train[inner]][mc], actual[train[inner]])
            final = clone(base).fit(panel.iloc[train][mc], actual[train])
            preds[name] = {"cal": first.predict(panel.iloc[train[cal]][mc]), "test": final.predict(panel.iloc[test][mc]),
                           "train": final.predict(panel.iloc[train][mc])}
            formation = features.dropna(subset=mc).tail(1)
            preds[name]["now"] = clone(base).fit(panel[mc], actual).predict(formation[mc]) if len(formation) else np.array([np.nan])
        at = lambda series, idx: series.reindex(dates.iloc[idx]).to_numpy(float)
        gjr_all = _gjr_average(gjr, horizon, ann).reindex(returns.index) if gjr is not None else None
        def baseline(name, series):
            preds[name] = {k: at(series, idx) for k, idx in (("cal", train[cal]), ("test", test), ("train", train))}
            preds[name]["now"] = np.array([series.iloc[-1] if np.isfinite(series.iloc[-1]) else np.nan])
        baseline("EWMA", ewma)
        if gjr_all is not None:
            baseline("GJR-GARCH", gjr_all)
        calm = stress.fillna(0.0).lt(0.5)
        if gjr_all is not None:
            preds["Regime-switch"] = {k: np.where(at(calm.astype(float), idx) > 0.5, preds["HAR-RV"][k], preds["GJR-GARCH"][k])
                                      for k, idx in (("cal", train[cal]), ("test", test), ("train", train))}
            preds["Regime-switch"]["now"] = preds["HAR-RV"]["now"] if bool(calm.iloc[-1]) else np.array([gjr_all.iloc[-1]])
        else:
            preds["Regime-switch"] = {k: v.copy() for k, v in preds["HAR-RV"].items()}
        loss = {}
        for name, p in preds.items():
            var_test = np.maximum(p["test"], floor)
            loss[name] = np.log(var_test) + actual[test] / var_test
        for name, p in preds.items():
            var_cal, var_test = np.maximum(p["cal"], floor), np.maximum(p["test"], floor)
            radius_series = np.abs(np.sqrt(var_cal) - np.sqrt(actual[train[cal]]))
            valid = radius_series[np.isfinite(radius_series)]
            quantile = min(1.0, np.ceil((len(valid) + 1) * 0.9) / max(len(valid), 1))
            radius = float(np.quantile(valid, quantile, method="higher")) if len(valid) else float("nan")
            predicted, realized = np.sqrt(var_test), np.sqrt(actual[test])
            dm = diebold_mariano(loss[name], loss["Regime-switch"], horizon) if name != "Regime-switch" else (None, None)
            errors.append({"model": name, "horizon": horizon, "mae": float(np.nanmean(np.abs(predicted - realized))),
                           "qlike": float(np.nanmean(loss[name])), "interval_coverage": float(np.mean(np.abs(realized - predicted) <= radius)),
                           "dm_stat_vs_regime_switch": dm[0], "dm_p_value": dm[1],
                           "regime_switch_significantly_better": bool(dm[1] is not None and dm[1] < 0.05 and dm[0] > 0)})
            if keep_rows:
                for date, forecast, truth in zip(dates.iloc[test], predicted, realized):
                    forecasts.append({"date": date_str(date), "model": name, "horizon": horizon, "forecast_vol": float(forecast), "realized_vol": float(truth)})
                    intervals.append({"date": date_str(date), "model": name, "horizon": horizon, "lower": max(0.0, float(forecast - radius)), "upper": float(forecast + radius)})
            now = float(np.sqrt(max(p["now"][0], 0.0))) if np.isfinite(p["now"][0]) else None
            terms.append({"model": name, "horizon": horizon, "forecast_vol": now, "formation_date": date_str(last_formation["date"].iloc[0]) if len(last_formation) else None,
                          "interval_radius": radius})
            if name == "Regime-switch":
                # Filtered-historical-simulation quantiles of standardised h-day returns, calibrated on training rows only.
                scale_train = np.sqrt(np.maximum(p["train"], floor) / ann * horizon)
                z_train = sums[train] / scale_train
                z_train = z_train[np.isfinite(z_train)]
                scale_test = np.sqrt(np.maximum(p["test"], floor) / ann * horizon)
                z_test = sums[test] / scale_test
                sigma_now = float(np.sqrt(max(p["now"][0], 0.0) / ann * horizon)) if np.isfinite(p["now"][0]) else float("nan")
                q05, q95 = np.quantile(z_train, [0.05, 0.95])
                calibration[horizon] = {"sigma": sigma_now, "range": (float(sigma_now * q05), float(sigma_now * q95)),
                                        "range_coverage": float(np.mean((z_test >= q05) & (z_test <= q95)))}
                for level in LEVELS:
                    q = float(np.quantile(z_train, 1 - level))
                    tail = z_train[z_train <= q]
                    row = {"horizon": horizon, "level": level, "var": float(-sigma_now * q), "es": float(-sigma_now * tail.mean()) if len(tail) else None,
                           "calibration_obs": int(len(z_train)), "oos_breach_rate": None, "kupiec_p_value": None}
                    if horizon == 1:
                        breaches = int(np.sum(z_test < q))
                        row.update({"oos_breach_rate": breaches / max(len(z_test), 1), "expected_breach_rate": 1 - level, "kupiec_p_value": kupiec_pvalue(breaches, len(z_test), level)})
                    var_es.append(row)
                if horizon == 1:
                    size = np.minimum(max_size, target_vol / np.sqrt(np.maximum(p["test"], floor)))
                    realised = returns.shift(-1).reindex(dates.iloc[test]).to_numpy(float)
                    sizing = {"managed": _perf(size * realised, ann), "unmanaged": _perf(realised, ann), "mean_size": float(np.nanmean(size)),
                              "now": float(min(max_size, target_vol / np.sqrt(max(p["now"][0], floor)))) if np.isfinite(p["now"][0]) else None}
    return {"forecasts": forecasts, "errors": errors, "terms": terms, "intervals": intervals, "var_es": var_es, "calibration": calibration,
            "sizing": sizing, "stress": stress, "notes": notes, "gjr": gjr, "train_n": train_n, "clean": clean}


def _risk_row(asset: str, result: dict[str, Any], target_vol: float, max_size: float) -> dict[str, Any]:
    stress = result["stress"].dropna()
    probability = float(stress.iloc[-1]) if len(stress) else 0.0
    row: dict[str, Any] = {"asset": asset, "regime": "stress" if probability >= 0.5 else "calm", "stress_probability": probability}
    switch = {t["horizon"]: t["forecast_vol"] for t in result["terms"] if t["model"] == "Regime-switch"}
    for h in (1, 5, 21):
        cal = result["calibration"].get(h)
        row[f"vol_{h}d"] = switch.get(h)
        row[f"range_{h}d_low"], row[f"range_{h}d_high"] = (cal["range"] if cal else (None, None))
    one = switch.get(1)
    row["target_volatility"] = target_vol
    row["size_multiple"] = float(min(max_size, target_vol / one)) if one else None
    row["unmanaged_size"] = 1.0
    for level in LEVELS:
        hit = next((v for v in result["var_es"] if v["horizon"] == 1 and v["level"] == level), None)
        row[f"var_{int(level * 100)}"] = hit["var"] if hit else None
        row[f"es_{int(level * 100)}"] = hit["es"] if hit else None
    return row


def run_vol_forecasting(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = dict(payload or {})
    watchlist = request.get("watchlist")
    if watchlist:
        if not isinstance(watchlist, list) or len(watchlist) > MAX_WATCHLIST:
            raise ValueError(f"watchlist must be a list of at most {MAX_WATCHLIST} tickers")
        request["symbols"] = watchlist
        request["max_symbols"] = MAX_WATCHLIST
    ctx = load_context(request, min_symbols=1 if watchlist else 8)
    if ctx.payload.get("macro_features"):
        raise ValueError("Macro forecasting inputs require verified release vintages and are not supported")
    target_vol = float(ctx.payload.get("target_volatility", 0.15))
    max_size = float(ctx.payload.get("max_size", 2.0))
    if not 0 < target_vol <= 2 or not 0 < max_size <= 10:
        raise ValueError("target_volatility must be in (0, 2] and max_size in (0, 10]")
    override = None
    artifact = ctx.payload.get("regime_artifact_id")
    if artifact:
        stored = get_artifact(str(artifact))
        if not stored or stored.get("kind") != "regime":
            raise ValueError("regime_artifact_id is unknown or expired; rerun Regimes and pass the new id")
        override = pd.Series(stored["stress_probability"], dtype=float)
        override.index = pd.to_datetime(override.index)
    horizons = [int(h) for h in ctx.payload.get("forecast_horizons", [1, 5, 21, 63])]
    if set(horizons) - {1, 5, 21, 63}:
        raise ValueError("Unsupported forecast horizon")
    suite = str(ctx.payload.get("model_suite", "har_ml"))
    if suite not in {"har_ml", "har_ridge", "har_gbm", "har_x", "arch_family"}:
        raise ValueError("Unsupported model_suite")
    provenance_args = {"purge": max(horizons), "embargo": 5, "universe": universe_label(ctx.payload, ctx.symbols)}

    if watchlist:
        rows, notes = [], []
        for asset in dict.fromkeys(normalize_symbol(w) for w in watchlist):
            if asset not in ctx.returns:
                notes.append({"asset": asset, "status": "skipped", "reason": "no price history"})
                continue
            try:
                result = _forecast_asset(ctx.returns[asset], ctx.annualization, [1, 5, 21], {}, None, override, target_vol, max_size, keep_rows=False)
            except ValueError as exc:
                notes.append({"asset": asset, "status": "skipped", "reason": str(exc)})
                continue
            rows.append(_risk_row(asset, result, target_vol, max_size))
        if not rows:
            raise ValueError("No watchlist ticker has enough history for a volatility forecast")
        rows.sort(key=lambda r: -(r["stress_probability"] or 0))
        return response("03", [summary(f"Regime: {rows[0]['asset']} (+{len(rows) - 1} more)" if len(rows) > 1 else f"Regime: {rows[0]['asset']}", rows[0]["regime"], "state"),
                                    summary("Next-month vol", rows[0]["vol_21d"], "%"), summary("1-day VaR 99%", rows[0]["var_99"], "%"),
                                    summary("Suggested size", rows[0]["size_multiple"], "×")],
            charts={"vol_forecast_panel": [], "forecast_error_distribution": [], "vol_term_structure": [], "realized_vs_predicted": [],
                    "model_confidence_intervals": [], "realized_vol_estimator_comparison": [], "garch_model_selection": [],
                    "garch_leverage_news_impact_curve": [], "ensemble_vol_forecast_weights": [], "var_es_forecast": [], "regime_probability": []},
            tables={"forecast_tournament": [], "forecast_rows": [], "garch_model_selection": [], "risk_today": rows, "var_es": [], "position_sizing": [],
                    "watchlist_skipped": notes},
            provenance=build_provenance(ctx.closes, calendar=ctx.calendar, train_window=None, test_window=None, **provenance_args),
            meta={"mode": "watchlist", "max_watchlist": MAX_WATCHLIST, "ranges": "90 percent filtered-historical-simulation ranges for the cumulative return",
                  "size": "target volatility divided by forecast volatility, capped, always shown beside unmanaged size 1.0"})

    asset = str(ctx.payload.get("asset") or ctx.symbols[0]).upper().replace("-", "_")
    if asset not in ctx.returns:
        raise ValueError(f"Requested volatility asset {asset} is not in the selected universe")
    returns = ctx.returns[asset]
    peers = ctx.returns.drop(columns=[asset]).pow(2)
    # Average over peers observed that day; a date needs at least two, so one short history cannot void the panel.
    peer_variance = peers.mean(axis=1).where(peers.notna().sum(axis=1) >= 2) * ctx.annualization
    candidates = {"HAR-Ridge": Ridge(alpha=1e-3), "HAR-GBM": GradientBoostingRegressor(n_estimators=80, max_depth=2, random_state=3),
                  "HAR-X-ElasticNet": ElasticNet(alpha=1e-4, l1_ratio=.35, max_iter=3000)}
    ml_models = {"har_ml": candidates, "har_ridge": {"HAR-Ridge": candidates["HAR-Ridge"]}, "har_gbm": {"HAR-GBM": candidates["HAR-GBM"]},
                 "har_x": {"HAR-X-ElasticNet": candidates["HAR-X-ElasticNet"]}, "arch_family": {}}[suite]
    unavailable = []
    if len(ctx.symbols) < 2:
        if suite == "har_x":
            raise ValueError("HAR-X requires at least two observed assets")
        ml_models.pop("HAR-X-ElasticNet", None)
        peer_variance = None
        unavailable.append("HAR-X excluded: no peer asset in the requested universe")
    if suite == "arch_family" and horizons != [1]:
        raise ValueError("ARCH-family selection currently supports forecast_horizons=[1] only")
    result = _forecast_asset(returns, ctx.annualization, horizons, ml_models, peer_variance if "HAR-X-ElasticNet" in ml_models else None, override, target_vol, max_size)
    forecasts, errors, terms, intervals = result["forecasts"], result["errors"], result["terms"], result["intervals"]
    arch_rows, arch_weights, news, status = [], [], [], "not_requested"
    if suite == "arch_family":
        arch_rows, arch_weights, news, status = arch_family_vol_models(returns, ctx.annualization, int(ctx.payload.get("garch_fit_cap", 1000)))
        if status not in {"fit", "partial_fit"}:
            raise ValueError(f"ARCH-family forecasting unavailable: {status}")
        terms = [{"model": row["model"], "distribution": row["distribution"], "horizon": 1, "forecast_vol": row["forecast_vol"]} for row in arch_rows if "forecast_vol" in row]
    estimates = [{"estimator": "close_to_close", "current_vol": float(returns.rolling(21).std().iloc[-1] * np.sqrt(ctx.annualization))}]
    bars = ctx.ohlcv.loc[ctx.ohlcv.Ticker == asset].set_index("Date")
    for name, estimator in [("garman_klass", garman_klass_vol), ("yang_zhang", yang_zhang_vol)]:
        estimates.append({"estimator": name, "current_vol": float(estimator(bars, window=21, ann=ctx.annualization).iloc[-1])})
    risk = _risk_row(asset, result, target_vol, max_size)
    stress = result["stress"].dropna()
    regime_rows = [{"date": date_str(d), "stress_probability": float(v), "regime": "stress" if v >= 0.5 else "calm"} for d, v in stress.items()]
    regime_artifact = put_artifact("regime", {"stress_probability": {date_str(d): float(v) for d, v in stress.items()}, "asset": asset})
    sizing = result["sizing"]
    sizing_rows = ([{"strategy": "unmanaged", **sizing["unmanaged"], "mean_size": 1.0}, {"strategy": "vol_targeted", **sizing["managed"], "mean_size": sizing["mean_size"]}]
                   if sizing else [])
    test_dates = [pd.Timestamp(r["date"]) for r in forecasts]
    provenance = build_provenance(ctx.closes, calendar=ctx.calendar, train_window=(result["clean"].index[0], result["clean"].index[result["train_n"] - 1]),
                                  test_window=(min(test_dates), max(test_dates)) if test_dates else None, **provenance_args)
    tournament_note = "; ".join(result["notes"] + unavailable)
    alerts = [{"level": "warning", "message": m} for m in result["notes"]]
    if status == "partial_fit":
        alerts.append({"level": "warning", "message": "Some ARCH candidates failed; model-selection rows include reasons"})
    return response("03", [summary("Regime", risk["regime"], "state"), summary("Next-month vol", risk["vol_21d"], "%"),
                           summary("1-day VaR 99%", risk["var_99"], "%"), summary("Suggested size", risk["size_multiple"], "×")],
        charts={"vol_forecast_panel": forecasts, "forecast_error_distribution": errors, "vol_term_structure": terms,
            "realized_vs_predicted": forecasts, "model_confidence_intervals": intervals, "realized_vol_estimator_comparison": estimates,
            "garch_model_selection": arch_rows, "garch_leverage_news_impact_curve": news, "ensemble_vol_forecast_weights": arch_weights,
            "var_es_forecast": result["var_es"], "regime_probability": regime_rows},
        tables={"forecast_tournament": errors, "forecast_rows": forecasts, "garch_model_selection": arch_rows,
                "risk_today": [risk], "var_es": result["var_es"], "position_sizing": sizing_rows, "watchlist_skipped": []},
        status="warning" if alerts else "ok", alerts=alerts, provenance=provenance,
        meta={"asset": asset, "regime_artifact_id": regime_artifact, "regime_source": "supplied regime_artifact_id" if override is not None else "own two-state HMM, forward-filtered",
              "forecast_target": "annualized_mean_future_squared_log_returns", "validation": "purged_chronological_per_horizon",
              "regime_switch": "HAR-RV when stress probability < 0.5, GJR-GARCH otherwise; probabilities are forward-filtered from a model fit on the first 60% of returns",
              "dm_test": "Diebold-Mariano on QLIKE losses, Bartlett variance with lag h-1 and the HLN correction; positive statistic favours Regime-switch",
              "intervals": "90_percent_absolute_residual_calibration_before_holdout; dependent data coverage not guaranteed",
              "var_es": "filtered historical simulation: standardised h-day returns from training rows, scaled by the Regime-switch forecast; Kupiec test on 1-day out-of-sample breaches",
              "position_size": "min(max_size, target_volatility / forecast volatility), shown beside unmanaged (size 1); real-time vol-managed portfolios often underperform unmanaged (Cederburg et al., 2020)",
              "notes": tournament_note, "arch_family_status": status, "unavailable_models": unavailable,
              "news_impact": "GARCH/GJR/EGARCH/APARCH only; FIGARCH curve unavailable", "macro": "excluded without verified release vintages",
              "unsupported_removed": ["GINN", "jump_decomposition", "smoothed_vol_regimes", "spillover_causality"]})
