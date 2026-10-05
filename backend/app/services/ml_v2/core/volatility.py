"""ML V2 volatility implementation."""
from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler
from .data_loader import load_macro
from .common import compact_records, date_str, number_like, response, summary
from .estimators import _safe_predict, bipower_variation, garman_klass_vol, yang_zhang_vol
from .panel import MLContext, load_context


def realized_vol_matrix(ctx: MLContext, window: int = 21) -> pd.DataFrame:
    return ctx.returns.rolling(window).std() * math.sqrt(ctx.annualization)



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



def run_vol_forecasting(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from sklearn.base import clone
    from .validation import chronological_purged_split
    ctx = load_context(payload,min_symbols=8)
    asset = str(ctx.payload.get("asset") or ctx.symbols[0]).upper().replace("-","_")
    if asset not in ctx.returns:
        raise ValueError(f"Requested volatility asset {asset} is not in the selected universe")
    if ctx.payload.get("macro_features"):
        raise ValueError("Macro forecasting inputs require verified release vintages and are not supported")
    returns = ctx.returns[asset]
    daily_variance = returns.pow(2)*ctx.annualization
    features = pd.DataFrame({"date":returns.index,"daily_variance":daily_variance,
        "weekly_variance":daily_variance.rolling(5).mean(),"monthly_variance":daily_variance.rolling(21).mean()})
    features["peer_variance"] = ctx.returns.drop(columns=[asset]).pow(2).mean(axis=1,skipna=False)*ctx.annualization
    suite = str(ctx.payload.get("model_suite","har_ml"))
    models = {"HAR-Ridge":Ridge(alpha=1),"HAR-GBM":GradientBoostingRegressor(n_estimators=80,max_depth=2,random_state=3),
        "HAR-X-ElasticNet":ElasticNet(alpha=1e-4,l1_ratio=.35,max_iter=3000)}
    if suite == "har_ridge": models = {"HAR-Ridge":models["HAR-Ridge"]}
    elif suite == "har_gbm": models = {"HAR-GBM":models["HAR-GBM"]}
    elif suite == "har_x": models = {"HAR-X-ElasticNet":models["HAR-X-ElasticNet"]}
    elif suite not in {"har_ml","arch_family"}: raise ValueError("Unsupported model_suite")
    unavailable = []
    if len(ctx.symbols)<2:
        if suite == "har_x":
            raise ValueError("HAR-X requires at least two observed assets")
        models.pop("HAR-X-ElasticNet",None)
        features["peer_variance"] = 0.
        unavailable.append("HAR-X excluded: no peer asset in the requested universe")
    if suite == "arch_family": models = {}
    horizons = ctx.payload.get("forecast_horizons",[1,5,21,63])
    forecasts, errors, terms, intervals = [], [], [], []
    cols = ["daily_variance","weekly_variance","monthly_variance"]
    for horizon in horizons:
        horizon = int(horizon)
        if horizon not in {1,5,21,63}: raise ValueError("Unsupported forecast horizon")
        # Formation close t predicts average squared returns over t+1,...,t+h.
        target = daily_variance.shift(-horizon).rolling(horizon).mean()
        panel = features.assign(target=target).replace([np.inf,-np.inf],np.nan).dropna()
        if len(panel)<100 and models:
            raise ValueError(f"Insufficient complete volatility history for horizon {horizon}")
        if not models: continue
        train,test = chronological_purged_split(panel,horizon,5)
        inner,calibration = chronological_purged_split(panel.iloc[train].reset_index(drop=True),horizon,5)
        for name,base in models.items():
            model_cols = cols+["peer_variance"] if name == "HAR-X-ElasticNet" else cols
            initial = clone(base).fit(panel.iloc[train[inner]][model_cols],panel.target.iloc[train[inner]])
            cp = np.sqrt(np.maximum(initial.predict(panel.iloc[train[calibration]][model_cols]),0))
            truth = np.sqrt(panel.target.iloc[train[calibration]].to_numpy())
            residual = np.abs(cp-truth)
            quantile = min(1.,np.ceil((len(residual)+1)*.9)/len(residual))
            radius = float(np.quantile(residual,quantile,method="higher"))
            model = clone(base).fit(panel.iloc[train][model_cols],panel.target.iloc[train])
            predicted = np.sqrt(np.maximum(model.predict(panel.iloc[test][model_cols]),0))
            actual = np.sqrt(panel.target.iloc[test].to_numpy())
            for date,forecast,realized in zip(panel.date.iloc[test],predicted,actual):
                forecasts.append({"date":date_str(date),"model":name,"horizon":horizon,"forecast_vol":float(forecast),"realized_vol":float(realized)})
                intervals.append({"date":date_str(date),"model":name,"horizon":horizon,"lower":max(0.,float(forecast-radius)),"upper":float(forecast+radius)})
            errors.append({"model":name,"horizon":horizon,"mae":float(mean_absolute_error(actual,predicted)),
                "qlike":float(np.mean(np.log(np.maximum(predicted**2,1e-12))+actual**2/np.maximum(predicted**2,1e-12))),
                "interval_coverage":float(np.mean(np.abs(actual-predicted)<=radius))})
            production = clone(base).fit(panel[model_cols],panel.target)
            current = features.dropna().tail(1)
            terms.append({"model":name,"horizon":horizon,"forecast_vol":float(np.sqrt(max(production.predict(current[model_cols])[0],0.))),"formation_date":date_str(current.date.iloc[0])})
    arch_rows,arch_weights,news,status = [],[],[],"not_requested"
    if suite == "arch_family":
        if horizons != [1]: raise ValueError("ARCH-family selection currently supports forecast_horizons=[1] only")
        arch_rows,arch_weights,news,status = arch_family_vol_models(returns,ctx.annualization,int(ctx.payload.get("garch_fit_cap",1000)))
        if status not in {"fit","partial_fit"}: raise ValueError(f"ARCH-family forecasting unavailable: {status}")
        terms = [{"model":row["model"],"distribution":row["distribution"],"horizon":1,"forecast_vol":row["forecast_vol"]} for row in arch_rows if "forecast_vol" in row]
    estimates = [{"estimator":"close_to_close","current_vol":float(returns.rolling(21).std().iloc[-1]*np.sqrt(ctx.annualization))}]
    bars = ctx.ohlcv.loc[ctx.ohlcv.Ticker==asset].set_index("Date")
    for name,estimator in [("garman_klass",garman_klass_vol),("yang_zhang",yang_zhang_vol)]:
        series = estimator(bars,window=21,ann=ctx.annualization)
        estimates.append({"estimator":name,"current_vol":float(series.iloc[-1])})
    return response("03",[summary("Asset",asset,"ticker"),summary("Forecasts",len(terms),"models/horizons")],
        charts={"vol_forecast_panel":forecasts,"forecast_error_distribution":errors,"vol_term_structure":terms,
            "realized_vs_predicted":forecasts,"model_confidence_intervals":intervals,"realized_vol_estimator_comparison":estimates,
            "garch_model_selection":arch_rows,"garch_leverage_news_impact_curve":news,"ensemble_vol_forecast_weights":arch_weights},
        tables={"forecast_tournament":errors,"forecast_rows":forecasts,"garch_model_selection":arch_rows},
        status="warning" if status == "partial_fit" else "ok",
        alerts=[{"level":"warning","message":"Some ARCH candidates failed; model-selection rows include reasons"}] if status == "partial_fit" else [],
        meta={"asset":asset,"forecast_target":"annualized_mean_future_squared_log_returns","validation":"purged_chronological_per_horizon",
            "intervals":"90_percent_absolute_residual_calibration_before_holdout; dependent data coverage not guaranteed",
            "arch_family_status":status,"unavailable_models":unavailable,"news_impact":"GARCH/GJR/EGARCH/APARCH only; FIGARCH curve unavailable","macro":"excluded without verified release vintages","unsupported_removed":["GINN","jump_decomposition","smoothed_vol_regimes","spillover_causality"]})
