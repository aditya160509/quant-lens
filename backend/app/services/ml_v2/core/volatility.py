"""ML V2 volatility implementation."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable
import base64
import hashlib
import math
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Lasso, Ridge, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from .data_loader import annualization_factor, close_matrix, data_inventory, load_fama_french, load_macro, market_caps, ohlcv_for_symbols, parse_symbols, returns_matrix, sector_map, volume_matrix
from .performance import ThreadPoolExecutor, as_completed, cache_key, cached_ledoit_cov, data_inventory_cached, disk_get, disk_set, equity_from_returns, fast_spearman_ic, max_drawdown, normalize_payload, precompute_date_strings, ridge_fit_fast, sharpe, sortino, vectorized_ic_series, _CONTEXT_CACHE
from .validation import chronological_purged_split, purged_date_folds
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
    for spec_name, spec_kwargs in specs:
        for dist in dists:
            try:
                model = arch_model(r, mean="Constant", dist=dist, rescale=False, **spec_kwargs)
                fit = model.fit(disp="off", show_warning=False, options={"maxiter": 80})
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
            except Exception:
                continue
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
    return rows, weight_rows, news_rows, "fit"



def news_impact_curve(fit: Any, model_name: str, dist: str) -> list[dict[str, Any]]:
    params = {str(k): float(v) for k, v in fit.params.items()}
    omega = params.get("omega", 0.0)
    alpha = params.get("alpha[1]", params.get("alpha[1]", 0.05))
    gamma = params.get("gamma[1]", params.get("gamma[1]", 0.0))
    beta = params.get("beta[1]", 0.85)
    last_var = float(np.nanmean(np.asarray(fit.conditional_volatility)[-63:] ** 2)) if hasattr(fit, "conditional_volatility") else 1.0
    rows = []
    for shock in np.linspace(-4, 4, 41):
        if "EGARCH" in model_name:
            log_var = omega + beta * math.log(max(last_var, 1e-12)) + alpha * (abs(shock) - math.sqrt(2 / math.pi)) + gamma * shock
            var = math.exp(log_var)
        else:
            asym = gamma * shock * shock if shock < 0 else 0.0
            var = omega + (alpha + asym) * shock * shock + beta * last_var
        rows.append({"shock_sigma": float(shock), "next_variance": float(max(var, 0.0)), "model": model_name, "distribution": dist})
    return rows



def vol_spillover_network(rv: pd.DataFrame, max_assets: int = 30) -> list[dict[str, Any]]:
    panel = rv.dropna(axis=1, thresh=max(80, int(len(rv) * 0.5))).iloc[:, :max_assets].dropna(how="all").ffill().dropna()
    if panel.shape[0] < 80 or panel.shape[1] < 3:
        return []
    edges: list[dict[str, Any]] = []
    x_all = panel.shift(1).dropna()
    y_all = panel.reindex(x_all.index)
    for target in panel.columns:
        others = [c for c in panel.columns if c != target]
        if len(others) < 2:
            continue
        model = ElasticNet(alpha=1e-4, l1_ratio=0.4, max_iter=3000).fit(x_all[others], y_all[target])
        coefs = np.asarray(model.coef_, dtype=float)
        cutoff = np.nanpercentile(np.abs(coefs), 85)
        for source, coef in zip(others, coefs):
            if abs(coef) >= cutoff and abs(coef) > 1e-6:
                edges.append({"source": str(source), "target": str(target), "weight": float(coef), "abs_weight": float(abs(coef))})
    edges.sort(key=lambda r: r["abs_weight"], reverse=True)
    return edges[:120]



def vol_hmm_states(s: pd.Series, ann: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    vol = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(vol) < 120:
        return [], []
    x = pd.DataFrame({"vol": vol, "vol_change": vol.diff(), "vol_z": (vol - vol.rolling(63).mean()) / vol.rolling(63).std()}).dropna()
    try:
        from hmmlearn import hmm

        model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=150, random_state=41, min_covar=1e-4)
        arr = StandardScaler().fit_transform(x)
        probs = model.fit(arr).predict_proba(arr)
        labels = np.argmax(probs, axis=1)
        means = [float(x.loc[labels == i, "vol"].mean()) if np.any(labels == i) else 0.0 for i in range(3)]
        order = np.argsort(means)
        rows = []
        for idx, date in enumerate(x.index):
            row = {"date": date_str(date), "dominant_vol_state": int(np.where(order == labels[idx])[0][0] + 1)}
            for rank, state in enumerate(order, start=1):
                row[f"vol_state_{rank}"] = float(probs[idx, state])
            rows.append(row)
        diag = [{"vol_state": f"vol_state_{rank}", "mean_vol": means[state], "rank": rank} for rank, state in enumerate(order, start=1)]
        return rows[-300:], diag
    except Exception:
        return [], []



def batch_universe_vol_heatmap(rv: pd.DataFrame, sectors: dict[str, str], limit: int = 80) -> list[dict[str, Any]]:
    latest = rv.tail(21).mean(axis=0).dropna().sort_values(ascending=False).head(limit)
    return [{"row": sectors.get(str(t), "Unknown"), "col": str(t), "value": float(v)} for t, v in latest.items()]



def rolling_qlike_weights(forecast_rows: list[dict[str, Any]], window: int = 63) -> list[dict[str, Any]]:
    if not forecast_rows:
        return []
    df = pd.DataFrame(forecast_rows)
    if df.empty or not {"date", "model", "forecast_vol", "realized_vol"}.issubset(df.columns):
        return []
    pivot_f = df.pivot_table(index="date", columns="model", values="forecast_vol", aggfunc="last").sort_index()
    realized = df.groupby("date")["realized_vol"].last().reindex(pivot_f.index)
    if len(pivot_f) < max(10, window // 2) or pivot_f.shape[1] < 2:
        return []
    window = min(window, max(10, len(pivot_f) // 2))
    rows: list[dict[str, Any]] = []
    for end in range(window, len(pivot_f) + 1):
        f_win = pivot_f.iloc[end - window:end].astype(float)
        r_win = realized.iloc[end - window:end].astype(float)
        scores: dict[str, float] = {}
        for model in f_win.columns:
            fv = np.maximum(np.asarray(f_win[model], dtype=float) ** 2, 1e-12)
            rv = np.asarray(r_win, dtype=float) ** 2
            q = np.log(fv) + rv / fv
            scores[str(model)] = float(np.nanmean(q))
        finite = {k: v for k, v in scores.items() if math.isfinite(v)}
        if not finite:
            continue
        max_score = max(finite.values())
        inv = {k: math.exp(-(v - max_score)) for k, v in finite.items()}
        total = max(sum(inv.values()), 1e-12)
        row = {"date": date_str(pivot_f.index[end - 1])}
        row.update({f"{k}_weight": float(v / total) for k, v in inv.items()})
        row.update({f"{k}_qlike": float(v) for k, v in finite.items()})
        rows.append(row)
    return rows[-300:]



def run_vol_forecasting(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=8)
    asset = str(ctx.payload.get("asset") or ctx.payload.get("symbol") or (ctx.symbols[0] if ctx.symbols else "")).upper().replace("-", "_")

    ohlcv_asset = ctx.ohlcv[ctx.ohlcv["Ticker"] == asset] if "Ticker" in ctx.ohlcv.columns else pd.DataFrame()
    if ohlcv_asset.empty and ctx.symbols:
        asset = ctx.symbols[0]
        ohlcv_asset = ctx.ohlcv[ctx.ohlcv["Ticker"] == asset] if "Ticker" in ctx.ohlcv.columns else pd.DataFrame()

    rv_close = realized_vol_matrix(ctx, 21).dropna(how="all")
    if asset not in rv_close.columns and len(rv_close.columns):
        asset = str(rv_close.columns[0])
    s_close = rv_close[asset].dropna() if asset in rv_close else pd.Series(dtype=float)

    gk_series = pd.Series(dtype=float)
    yz_series = pd.Series(dtype=float)
    if not ohlcv_asset.empty:
        ohlcv_indexed = ohlcv_asset.set_index("Date") if "Date" in ohlcv_asset.columns else ohlcv_asset
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in ohlcv_indexed.columns:
                ohlcv_indexed[col] = np.nan
        try:
            gk_series = garman_klass_vol(ohlcv_indexed, window=21, ann=ctx.annualization).dropna()
        except Exception:
            gk_series = pd.Series(dtype=float)
        try:
            yz_series = yang_zhang_vol(ohlcv_indexed, window=21, ann=ctx.annualization).dropna()
        except Exception:
            yz_series = pd.Series(dtype=float)

    s = s_close if len(s_close) >= 80 else (gk_series if len(gk_series) >= 80 else yz_series)
    if len(s) < 80:
        return response("03", [summary("Vol Rows", len(s), "rows")], {}, {}, alerts=[{"level": "error", "message": "Insufficient realized volatility history."}], status="error")
    df = pd.DataFrame({"date": s.index, "realized_vol": s.values})
    df["har_daily"] = df["realized_vol"].shift(1)
    df["har_weekly"] = df["realized_vol"].rolling(5).mean().shift(1)
    df["har_monthly"] = df["realized_vol"].rolling(21).mean().shift(1)
    df = df.dropna()
    # HAR-X adds cross-asset volatility spillover and locally available macro columns.
    peer_vol = rv_close.drop(columns=[asset], errors="ignore").mean(axis=1).rename("peer_vol")
    df = df.merge(peer_vol, left_on="date", right_index=True, how="left")
    macro = load_macro()
    if not macro.empty and "date" in macro:
        macro = macro.copy()
        macro["date"] = pd.to_datetime(macro["date"])
        macro_cols = list(macro.select_dtypes(include=[np.number]).columns)[:8]
        df = df.merge(macro[["date", *macro_cols]], on="date", how="left")
    df = df.ffill().fillna(0.0)
    base_cols = ["har_daily", "har_weekly", "har_monthly"]
    x_cols = base_cols + [c for c in ["peer_vol", *list(df.select_dtypes(include=[np.number]).columns)] if c not in base_cols + ["realized_vol"]]
    x_cols = list(dict.fromkeys(x_cols))
    x = df[x_cols]
    y = df["realized_vol"]
    cut = int(len(df) * 0.75)
    models = {"HAR-Ridge": Ridge(alpha=1.0), "HAR-GBM": GradientBoostingRegressor(n_estimators=80, max_depth=2, random_state=3), "HAR-X-ElasticNet": ElasticNet(alpha=1e-4, l1_ratio=0.35, max_iter=3000)}
    forecasts = []
    errors = []
    for name, model in models.items():
        pred = _safe_predict(model, x.iloc[:cut], y.iloc[:cut], x.iloc[cut:])
        for d, p, actual in zip(df["date"].iloc[cut:], pred, y.iloc[cut:]):
            forecasts.append({"date": date_str(d), "model": name, "forecast_vol": float(p), "realized_vol": float(actual), "error": float(p - actual)})
        errors.append({"model": name, "mae": float(mean_absolute_error(y.iloc[cut:], pred)), "bias": float(np.mean(pred - y.iloc[cut:])), "correlation": float(np.corrcoef(pred, y.iloc[cut:])[0, 1])})
    qlike_rows = rolling_qlike_weights(forecasts, window=63)

    r_series = ctx.returns[asset] if asset in ctx.returns else pd.Series(dtype=float)
    jump_rows = []
    if len(r_series) > 42:
        rv_total = r_series.rolling(21).var() * ctx.annualization
        bpv = bipower_variation(r_series, 21) * ctx.annualization
        jump_comp = (rv_total - bpv).clip(lower=0.0)
        jump_df = pd.DataFrame({"date": r_series.index, "rv_total": rv_total, "continuous_component": bpv, "jump_component": jump_comp}).dropna().tail(300)
        jump_rows = compact_records(jump_df, limit=300)

    term = []
    horizons = [int(h) for h in ((payload or {}).get("forecast_horizons") or [1, 5, 21, 63])]
    for h in horizons:
        target_h = pd.Series(s, index=s.index).shift(-h + 1).rolling(h).mean().reindex(pd.to_datetime(df["date"]))
        valid = target_h.notna().to_numpy()
        if valid.sum() < 60:
            continue
        model_h = ElasticNet(alpha=1e-4, l1_ratio=0.35, max_iter=3000).fit(x.loc[valid], target_h.loc[valid].to_numpy())
        term.append({"horizon": h, "forecast_vol": max(0.0, float(model_h.predict(x.tail(1))[0])), "asset": asset, "model": "HAR-X-ElasticNet-direct"})

    estimator_summary = [{"estimator": "close_to_close", "current_vol": float(s_close.iloc[-1]) if len(s_close) else None}]
    if len(gk_series):
        estimator_summary.append({"estimator": "garman_klass", "current_vol": float(gk_series.iloc[-1])})
    if len(yz_series):
        estimator_summary.append({"estimator": "yang_zhang", "current_vol": float(yz_series.iloc[-1])})
    arch_rows, ensemble_rows, news_rows, arch_status = arch_family_vol_models(r_series, ctx.annualization, cap=int(number_like(ctx.payload.get("garch_fit_cap"), 1000) or 1000))
    spillover_rows = vol_spillover_network(rv_close, max_assets=int(number_like(ctx.payload.get("spillover_max_assets"), 30) or 30))
    vol_state_rows, vol_state_diag = vol_hmm_states(s, ctx.annualization)
    batch_heatmap = batch_universe_vol_heatmap(rv_close, ctx.sectors)
    if ensemble_rows:
        errors.extend([{"model": f"{r['model']}-{r['distribution']}", "mae": None, "bias": None, "correlation": None, "forecast_vol": r["forecast_vol"], "akaike_weight": r["ensemble_weight"]} for r in ensemble_rows])

    return response(
        "03",
        [summary("Asset", asset, "ticker"), summary("Next Vol", term[0]["forecast_vol"], "ann"), summary("Best MAE", min(r["mae"] for r in errors if r.get("mae") is not None), "vol")],
        charts={
            "vol_forecast_panel": forecasts,
            "forecast_error_distribution": errors,
            "vol_term_structure": term,
            "realized_vs_predicted": forecasts,
            "model_confidence_intervals": [{"date": r["date"], "lower": r["forecast_vol"] - abs(r["error"]), "upper": r["forecast_vol"] + abs(r["error"]), "model": r["model"]} for r in forecasts[-160:]],
            "vix_yield_macro_overlay": compact_records(load_macro().tail(300), limit=300),
            "jump_component_decomposition": jump_rows,
            "realized_vol_estimator_comparison": estimator_summary,
            "garch_model_selection": arch_rows,
            "garch_leverage_news_impact_curve": news_rows,
            "vol_spillover_network": spillover_rows,
            "ensemble_vol_forecast_weights": ensemble_rows,
            "rolling_qlike_ensemble_weights": qlike_rows,
            "vol_regime_classification": vol_state_rows,
            "batch_universe_vol_heatmap": batch_heatmap,
        },
        tables={"forecast_tournament": errors, "forecast_rows": forecasts[-300:], "garch_model_selection": arch_rows, "vol_regime_diagnostics": vol_state_diag, "vol_spillover_edges": spillover_rows, "rolling_qlike_ensemble_weights": qlike_rows},
        meta={"implemented_outputs": 15, "asset": asset, "models": list(models), "gk_available": len(gk_series) > 0, "yz_available": len(yz_series) > 0, "arch_family_status": arch_status},
    )

