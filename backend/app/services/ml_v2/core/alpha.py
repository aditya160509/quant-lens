"""Cross-sectional alpha: LightGBM and Ridge on rank-scaled features, controls beside the model, exact attributions."""
from __future__ import annotations
import ast
import re
from typing import Any
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from .common import build_provenance, compact_records, put_artifact, report_progress, response, summary
from .composite import daily_ic_table
from .data_loader import point_in_time_fundamentals, universe_label
from .estimators import rolling_monthly_ic
from .microstructure import market_residual_ivol, roll_spread
from .panel import load_context, make_feature_panel
from .performance import fast_spearman_ic
from .validation import chronological_purged_split

FAMILY_FEATURES = {
    "momentum": ["mom_5", "mom_21", "mom_63", "mom_12_1", "reversal_5", "high_52w"],
    "value": ["book_to_market", "earnings_yield"],
    "quality": ["gross_profitability", "leverage"],
    "volatility": ["vol_21", "vol_63", "drawdown_63", "max_factor_21", "ivol_21"],
    "liquidity": ["volume_z_21", "amihud_21", "hl_amihud_21", "corwin_schultz_21", "roll_spread_21", "dollar_vol_mom", "turnover_rate", "size_proxy"],
}
FEATURE_FAMILY = {col: family for family, cols in FAMILY_FEATURES.items() for col in cols}
FUNDAMENTALS = ["Common Stock Equity", "Ordinary Shares Number", "Gross Profit", "Total Assets", "Total Debt", "Net Income Common Stockholders"]
MAX_FORMULAS = 8
PARTICIPATION = 0.10
TREE_MODELS = ("lightgbm", "xgboost", "catboost")


# ---------------------------------------------------------------------------
# features

_CONTROL_LABELS = {"ic_composite": "IC composite", "ols3": "3-factor OLS", "ridge": "Ridge"}

def _apply_universe_filters(ctx):
    sectors = ctx.payload.get("sector_filter")
    minimum = float(ctx.payload.get("minimum_formation_notional") or 0)
    if minimum < 0:
        raise ValueError("minimum_formation_notional must be nonnegative")
    liquidity = (ctx.closes.iloc[:63] * ctx.volumes.iloc[:63]).mean()
    allowed = [s for s in ctx.symbols if (not sectors or ctx.sectors.get(s) in sectors) and liquidity.get(s, 0) >= minimum]
    if not allowed:
        raise ValueError("No assets satisfy formation-history universe filters")
    ctx.symbols = allowed
    ctx.returns, ctx.closes, ctx.volumes = ctx.returns[allowed], ctx.closes[allowed], ctx.volumes[allowed]
    ctx.ohlcv = ctx.ohlcv.loc[ctx.ohlcv.Ticker.isin(allowed)]


def _extra_features(ctx) -> dict[str, pd.DataFrame]:
    """Wide (date x ticker) features the shared panel lacks: 12-1 momentum, size, Roll, idiosyncratic vol, value and quality."""
    dates = ctx.returns.index
    close, volume = ctx.closes.reindex(dates), ctx.volumes.reindex(dates)
    dollar = (close * volume).where(volume > 0)
    wide = {"mom_12_1": np.log(close.shift(21) / close.shift(252)),
            "size_proxy": np.log(dollar.rolling(63, min_periods=21).mean()),
            "roll_spread_21": roll_spread(close),
            "ivol_21": market_residual_ivol(np.expm1(ctx.returns), ctx.annualization)}
    fundamentals = point_in_time_fundamentals(FUNDAMENTALS, ctx.symbols, dates)
    cap = close * fundamentals["Ordinary Shares Number"]
    assets = fundamentals["Total Assets"]
    wide["book_to_market"] = fundamentals["Common Stock Equity"] / cap
    wide["earnings_yield"] = fundamentals["Net Income Common Stockholders"] / cap
    wide["gross_profitability"] = fundamentals["Gross Profit"] / assets
    wide["leverage"] = fundamentals["Total Debt"] / assets
    return {k: v.replace([np.inf, -np.inf], np.nan) for k, v in wide.items()}


def _formula_features(ctx, formulas) -> dict[str, pd.DataFrame]:
    """Evaluate user formulas with the Research signal language (ast whitelist, no eval) on daily frames."""
    if not isinstance(formulas, list) or len(formulas) > MAX_FORMULAS:
        raise ValueError(f"formulas must be a list of at most {MAX_FORMULAS} objects with name and expr")
    from app.services.research_v2.core import signal_lang as sl
    dates, symbols = ctx.returns.index, list(ctx.symbols)
    close, volume = ctx.closes.reindex(dates), ctx.volumes.reindex(dates)
    wide = {f: ctx.ohlcv.pivot(index="Date", columns="Ticker", values=f.capitalize()).reindex(index=dates, columns=symbols) for f in ("open", "high", "low")}
    simple = np.expm1(ctx.returns)
    cache = {"close": close, "volume": volume, "returns": simple, "dollar_volume": close * volume, **wide,
             "rvol": simple.rolling(21).std(), "maxret": simple.rolling(21).max(),
             "amihud_d": (simple.abs() / (close * volume).where(volume > 0) * 1e6).rolling(21).mean(),
             "sector": sl.Groups(pd.Series(ctx.sectors).reindex(symbols))}
    unsupported = {"ivol", "beta", "industry"}
    out: dict[str, pd.DataFrame] = {}
    for item in formulas:
        name, expr = (item.get("name"), item.get("expr")) if isinstance(item, dict) else (None, None)
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}", name) or not isinstance(expr, str):
            raise ValueError("Each formula needs a name (letters, digits, underscore) and an expr string")
        if f"f_{name}" in out:
            raise ValueError(f"Duplicate formula name {name}")
        try:
            used = {n.id for n in ast.walk(sl.parse(expr)) if isinstance(n, ast.Name)} & set(sl.field_names())
            if used & unsupported:
                raise ValueError(f"Formula {name}: fields {sorted(used & unsupported)} are not available in Alpha")
            missing = [f for f in used & set(sl.FUNDAMENTAL_FIELDS) if f not in cache]
            if missing:
                loaded = point_in_time_fundamentals([sl.FUNDAMENTAL_FIELDS[f][0] for f in missing], symbols, dates)
                cache.update({f: loaded[sl.FUNDAMENTAL_FIELDS[f][0]] for f in missing})
            if "mcap" in used and "mcap" not in cache:
                cache["mcap"] = close * point_in_time_fundamentals(["Ordinary Shares Number"], symbols, dates)["Ordinary Shares Number"]
            out[f"f_{name}"] = sl.evaluate(expr, {"dates": dates, "symbols": symbols, "close_m": close, "returns": simple,
                                                  "daily": {}, "market_cap": cache.get("mcap"), "factors": None}, cache)
        except sl.SignalError as exc:
            raise ValueError(f"Formula {name}: {exc.message}") from None
    return out


def _uploaded_features(upload_id: str, panel: pd.DataFrame) -> dict[str, np.ndarray]:
    """Feature columns of an uploaded feature panel, aligned to the panel's (date, ticker) rows.

    Uploads are point-in-time checked on ingest (no future dates, unique keys); rows with no upload value stay missing.
    """
    from .uploads import feature_panel_frame
    extra = feature_panel_frame(str(upload_id))
    index = pd.MultiIndex.from_frame(panel[["date", "ticker"]])
    matched = extra.reindex(index)
    if matched.notna().to_numpy().sum() == 0:
        raise ValueError("The uploaded feature panel shares no (date, ticker) rows with this universe and window")
    return {f"u_{name}": matched[name].to_numpy(dtype=float) for name in matched.columns}


def build_alpha_panel(ctx, horizon: int, formulas, upload_id) -> tuple[pd.DataFrame, list[str]]:
    """Labelled and unlabelled rows with raw features; returns the panel and the feature column names."""
    panel, _ = make_feature_panel(ctx, horizon=horizon, include_unlabelled=True)
    if panel.empty:
        raise ValueError("Insufficient history to build a feature panel")
    index = pd.MultiIndex.from_frame(panel[["date", "ticker"]])
    wide = _extra_features(ctx)
    if formulas:
        wide.update(_formula_features(ctx, formulas))
    for name, frame in wide.items():
        panel[name] = frame.stack(future_stack=True).reindex(index).to_numpy()
    if upload_id:
        for name, values in _uploaded_features(upload_id, panel).items():
            panel[name] = values
    custom = [c for c in panel.columns if c.startswith("f_") or c.startswith("u_")]
    columns = [c for c in FEATURE_FAMILY if c in panel.columns] + custom
    return panel, columns


def _normalise(features: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    """Cross-sectional rank to [-1, 1] within each date (uses same-date rows only); unobserved becomes the median, 0."""
    ranks = features.replace([np.inf, -np.inf], np.nan).groupby(dates.to_numpy()).rank(pct=True)
    return (ranks * 2 - 1).fillna(0.0)


# ---------------------------------------------------------------------------
# models

def _make_model(name: str, params: dict[str, Any] | None = None):
    params = params or {}
    if name == "ridge":
        return Ridge(**{"alpha": 100.0, **params})
    if name == "lightgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(**{"n_estimators": 150, "learning_rate": 0.03, "num_leaves": 15, "max_depth": 4, "min_child_samples": 100,
                                "subsample": 0.7, "subsample_freq": 1, "colsample_bytree": 0.7, "reg_lambda": 5.0,
                                "n_jobs": 1, "random_state": 19, "verbosity": -1, **params})
    if name == "xgboost":
        from xgboost import XGBRegressor
        return XGBRegressor(**{"n_estimators": 120, "max_depth": 3, "learning_rate": 0.04, "subsample": 0.7, "colsample_bytree": 0.7,
                               "n_jobs": 1, "random_state": 17, "verbosity": 0, **params})
    if name == "catboost":
        from catboost import CatBoostRegressor
        return CatBoostRegressor(**{"iterations": 120, "depth": 4, "learning_rate": 0.04, "random_seed": 23, "verbose": False,
                                    "allow_writing_files": False, "thread_count": 1, **params})
    raise ValueError(f"Unsupported model family {name}")


def _available(name: str) -> bool:
    if name == "ridge":
        return True
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _contributions(name: str, model, x: np.ndarray, center: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Exact additive attributions in prediction units: TreeSHAP for trees, coef*(x-mean) for the linear model."""
    if name == "ridge":
        contrib = (x - center) * model.coef_
        return contrib, np.full(len(x), float(model.intercept_ + center @ model.coef_))
    if name == "lightgbm":
        full = model.booster_.predict(x, pred_contrib=True)
    elif name == "xgboost":
        import xgboost
        full = model.get_booster().predict(xgboost.DMatrix(x), pred_contribs=True)
    else:
        from catboost import Pool
        full = model.get_feature_importance(Pool(x), type="ShapValues")
    return np.asarray(full)[:, :-1], np.asarray(full)[:, -1]


def _fit(name, params, x, y, weights):
    model = _make_model(name, params)
    model.fit(x, y, sample_weight=weights)
    return model


def _tune(name, x, y, vx, vy, count):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    def objective(trial):
        if name == "ridge":
            params = {"alpha": trial.suggest_float("alpha", 1.0, 5000.0, log=True)}
        elif name == "lightgbm":
            params = {"num_leaves": trial.suggest_int("num_leaves", 4, 31), "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                      "min_child_samples": trial.suggest_int("min_child_samples", 50, 400)}
        else:
            params = {"max_depth" if name == "xgboost" else "depth": trial.suggest_int("depth", 2, 6)}
        score = _mean_ic(_fit(name, params, x, y, None).predict(vx), vy)
        return -score if np.isfinite(score) else 1.0
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=7))
    study.optimize(objective, n_trials=count)
    best = dict(study.best_params)
    if "depth" in best and name == "xgboost":
        best["max_depth"] = best.pop("depth")
    return best, [{"model": name, "trial": t.number, "validation_ic": -t.value, "parameters": t.params} for t in study.trials]


def _mean_ic(score: np.ndarray, target: np.ndarray, dates: np.ndarray | None = None) -> float:
    """Mean per-date Spearman IC; with no dates, one pooled IC."""
    if dates is None:
        return fast_spearman_ic(np.asarray(score, float), np.asarray(target, float))
    values = [fast_spearman_ic(score[idx], target[idx]) for idx in _by_date(dates)]
    values = [v for v in values if np.isfinite(v)]
    return float(np.mean(values)) if values else float("nan")


def _by_date(dates: np.ndarray) -> list[np.ndarray]:
    order = np.argsort(dates, kind="stable")
    edges = np.flatnonzero(np.diff(dates[order]).astype("int64") != 0) + 1
    return [idx for idx in np.split(order, edges) if len(idx) >= 6]


# ---------------------------------------------------------------------------
# evaluation: IC, decile spreads (equal and value weight), net long-short, turnover, capacity

def _bins_for(n: int) -> int:
    return 10 if n >= 100 else 5 if n >= 30 else 3 if n >= 6 else 2


def evaluate_scores(rows: pd.DataFrame, horizon: int, cost_bps: float) -> dict[str, Any]:
    """rows: date, ticker, score, fwd (simple forward return), dvol (dollar-volume proxy). Everything is out of sample."""
    dates = np.sort(rows["date"].unique())
    ic_dates, ics = [], []
    for date, group in rows.groupby("date", sort=True):
        if len(group) >= 6:
            value = fast_spearman_ic(group["score"].to_numpy(float), group["fwd"].to_numpy(float))
            if np.isfinite(value):
                ic_dates.append(date); ics.append(value)
    ics = np.array(ics)
    independent = ics[::horizon]
    out: dict[str, Any] = {"test_ic": float(ics.mean()) if len(ics) else None,
        "ic_ir": float(ics.mean() / ics.std(ddof=1)) if len(ics) > 2 and ics.std(ddof=1) > 1e-12 else None,
        "ic_tstat": float(independent.mean() / independent.std(ddof=1) * np.sqrt(len(independent))) if len(independent) > 2 and independent.std(ddof=1) > 1e-12 else None,
        "ic_dates": len(ics)}
    ew_bins, vw_bins, gross, costs, turnover, capacity, held = [], [], [], [], [], [], {}
    previous: dict[str, float] = {}
    n_bins = 2
    for date in dates[::horizon]:
        group = rows.loc[rows["date"] == date]
        n = len(group)
        if n < 6:
            continue
        n_bins = _bins_for(n)
        bucket = np.floor((group["score"].rank(method="first").to_numpy() - 1) * n_bins / n).astype(int)
        fwd = group["fwd"].to_numpy(float)
        weight = group["dvol"].fillna(group["dvol"].median()).to_numpy(float)
        ew_bins.append([fwd[bucket == b].mean() for b in range(n_bins)])
        vw_bins.append([np.average(fwd[bucket == b], weights=weight[bucket == b]) if weight[bucket == b].sum() > 0 else fwd[bucket == b].mean() for b in range(n_bins)])
        longs, shorts = group["ticker"].to_numpy()[bucket == n_bins - 1], group["ticker"].to_numpy()[bucket == 0]
        target = {**{t: -0.5 / len(shorts) for t in shorts}, **{t: 0.5 / len(longs) for t in longs}}
        traded = {t: abs(target.get(t, 0.0) - previous.get(t, 0.0)) for t in set(target) | set(previous)}
        adv = dict(zip(group["ticker"], group["dvol"]))
        limits = [PARTICIPATION * adv[t] / d for t, d in traded.items() if d > 1e-9 and np.isfinite(adv.get(t, np.nan)) and adv[t] > 0]
        gross.append(0.5 * (ew_bins[-1][-1] - ew_bins[-1][0]))
        costs.append(cost_bps / 1e4 * sum(traded.values()))
        turnover.append(sum(traded.values()) / 2)
        if limits and previous:
            capacity.append(min(limits))
        previous = target
        held[date] = gross[-1] - costs[-1]
    ew, vw = np.array(ew_bins), np.array(vw_bins)
    def spread(table):
        diff = table[:, -1] - table[:, 0] if len(table) else np.array([])
        t = float(diff.mean() / diff.std(ddof=1) * np.sqrt(len(diff))) if len(diff) > 2 and diff.std(ddof=1) > 1e-12 else None
        return {"spread": float(diff.mean()) if len(diff) else None, "t_stat": t, "bin_returns": [float(v) for v in table.mean(axis=0)] if len(table) else []}
    net = np.array(gross) - np.array(costs)
    periods = 252.0 / horizon
    out.update({"bins": n_bins, "equal_weight": spread(ew), "value_weight": spread(vw), "rebalances": len(gross),
        "gross_return_per_rebalance": float(np.mean(gross)) if gross else None, "cost_per_rebalance": float(np.mean(costs)) if costs else None,
        "net_return_per_rebalance": float(net.mean()) if len(net) else None,
        "net_sharpe": float(net.mean() / net.std(ddof=1) * np.sqrt(periods)) if len(net) > 2 and net.std(ddof=1) > 1e-12 else None,
        "turnover": float(np.mean(turnover[1:])) if len(turnover) > 1 else None,
        "capacity": float(np.median(capacity)) if capacity else None,
        "net_curve": [{"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "equity": float(e)} for d, e in zip(held, np.cumprod(1 + net))]})
    return out


# ---------------------------------------------------------------------------

def _what_changed(live, columns, normalised, contribution_fn, horizon, top_n):
    """Rank moves between the latest rebalance and the one `horizon` sessions earlier, with the largest SHAP deltas."""
    dates = np.sort(live["date"].unique())
    if len(dates) <= horizon:
        return [], {}
    now_date, before_date = dates[-1], dates[-1 - horizon]
    now, before = live["date"] == now_date, live["date"] == before_date
    common = sorted(set(live.loc[now, "ticker"]) & set(live.loc[before, "ticker"]))
    if len(common) < 4:
        return [], {}
    position = {t: i for i, t in enumerate(common)}
    def snapshot(mask):
        index = np.flatnonzero(mask.to_numpy())
        keep = sorted((k for k, t in enumerate(live["ticker"].to_numpy()[index]) if t in position), key=lambda k: position[live["ticker"].to_numpy()[index][k]])
        return normalised[index[keep]]
    x_now, x_before = snapshot(now), snapshot(before)
    score_now, contrib_now = contribution_fn(x_now)
    score_before, contrib_before = contribution_fn(x_before)
    rank_now = pd.Series(score_now, index=common).rank(ascending=False, method="first")
    rank_before = pd.Series(score_before, index=common).rank(ascending=False, method="first")
    top_n = min(top_n, max(1, len(common) // 3))
    rows = []
    for i, ticker in enumerate(common):
        delta = contrib_now[i] - contrib_before[i]
        drivers = np.argsort(-np.abs(delta))[:3]
        entered, exited = rank_now[ticker] <= top_n < rank_before[ticker], rank_before[ticker] <= top_n < rank_now[ticker]
        rows.append({"ticker": ticker, "rank": int(rank_now[ticker]), "previous_rank": int(rank_before[ticker]),
                     "rank_change": int(rank_before[ticker] - rank_now[ticker]), "prediction": float(score_now[i]),
                     "previous_prediction": float(score_before[i]),
                     "move": "entered_top" if entered else "exited_top" if exited else "moved",
                     "top_drivers": [{"feature": columns[j], "delta": float(delta[j])} for j in drivers]})
    rows.sort(key=lambda r: (r["move"] == "moved", -abs(r["rank_change"])))
    return rows[:25], {"previous_date": pd.Timestamp(before_date).strftime("%Y-%m-%d"), "current_date": pd.Timestamp(now_date).strftime("%Y-%m-%d"),
                       "top_n": top_n, "entered": [r["ticker"] for r in rows if r["move"] == "entered_top"],
                       "exited": [r["ticker"] for r in rows if r["move"] == "exited_top"]}


def run_gbt_alpha(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    request = ctx.payload
    _apply_universe_filters(ctx)
    horizon = int(request.get("prediction_horizon", 21))
    embargo = int(request.get("embargo_period", 5))
    cost_bps = float(request.get("cost_bps", 10))
    weighting = request.get("sample_weighting", "equal")
    family = str(request.get("model_family", "ensemble"))
    tuning = str(request.get("tuning_mode", "platform_defaults"))
    if weighting not in {"equal", "time_decay"}:
        raise ValueError("Unsupported sample_weighting")
    if tuning not in {"platform_defaults", "manual", "optuna_research"}:
        raise ValueError("Unsupported tuning_mode")
    unavailable = [m for m in TREE_MODELS if not _available(m)]
    names = ["lightgbm", "ridge"] if family == "ensemble" else [family]
    if family == "ensemble" and "lightgbm" in unavailable:
        names = ["ridge"]
    if family != "ensemble" and not _available(family):
        raise ValueError(f"Requested model family {family} is not installed")
    panel, all_columns = build_alpha_panel(ctx, horizon, request.get("formulas"), request.get("upload_id"))
    chosen_families = request.get("feature_families") or list(FAMILY_FEATURES)
    columns = [c for c in all_columns if FEATURE_FAMILY.get(c, "custom") in set(chosen_families) | {"custom"}]
    labelled = panel.dropna(subset=["target_return"]).sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    columns = [c for c in columns if labelled[c].notna().mean() >= 0.3]
    if len(columns) < 2:
        raise ValueError("Fewer than two features with enough coverage; check the chosen families and history length")
    # Features are rank-scaled within each date; the target is the date-demeaned forward return, so only the cross-section is modelled.
    x_all = _normalise(labelled[columns], labelled["date"])
    fwd_simple = np.expm1(labelled["target_return"])
    y_all = labelled["target_return"] - labelled.groupby("date")["target_return"].transform("mean")
    dvol = (ctx.closes * ctx.volumes).where(ctx.volumes > 0).rolling(63, min_periods=21).mean().stack(future_stack=True)
    labelled["dvol"] = dvol.reindex(pd.MultiIndex.from_frame(labelled[["date", "ticker"]])).to_numpy()
    train, test = chronological_purged_split(labelled, horizon, embargo)
    inner, val = chronological_purged_split(labelled.iloc[train].reset_index(drop=True), horizon, embargo)
    inner, val = train[inner], train[val]
    xv = x_all.to_numpy(float)
    yv = y_all.to_numpy(float)
    dates_np = labelled["date"].to_numpy()

    def sample_weights(index):
        if weighting != "time_decay":
            return None
        age = (labelled["date"].iloc[index].max() - labelled["date"].iloc[index]).dt.days.to_numpy()
        return np.exp(-np.log(2) * age / 252)

    manual = request.get("hyperparameters") or {}
    if tuning == "manual" and (not isinstance(manual, dict) or not manual or set(manual) - set(names)):
        raise ValueError("Manual tuning requires hyperparameters keyed by model name")
    params, trials = {n: dict(manual.get(n, {})) if tuning == "manual" else {} for n in names}, []
    if tuning == "optuna_research":
        count = int(request.get("optuna_trials", 10))
        for n in names:
            params[n], rows = _tune(n, xv[inner], yv[inner], xv[val], yv[val], count)
            trials.extend(rows)
    report_progress(45, "Fitting models")
    try:
        validation, test_scores = {}, {}
        for n in names:
            validation[n] = _fit(n, params[n], xv[inner], yv[inner], sample_weights(inner)).predict(xv[val])
    except TypeError as exc:
        raise ValueError(f"Unknown estimator hyperparameter: {exc}") from None
    # Ensemble weights and the ridge-to-tree scale are locked on the validation window before any holdout outcome is read.
    scale = {n: float(np.std(validation[names[0]]) / max(np.std(validation[n]), 1e-12)) for n in names}
    grid = [{"weights": {names[0]: round(w, 1), names[1]: round(1 - w, 1)}} for w in np.linspace(0, 1, 11)] if len(names) == 2 else [{"weights": {names[0]: 1.0}}]
    for row in grid:
        blend = sum(row["weights"][n] * scale[n] * validation[n] for n in names)
        row["validation_ic"] = _mean_ic(blend, yv[val], dates_np[val])
    best = max(grid, key=lambda r: -np.inf if not np.isfinite(r["validation_ic"]) else r["validation_ic"])
    weights = best["weights"]
    models = {n: _fit(n, params[n], xv[train], yv[train], sample_weights(train)) for n in names}
    test_scores = {n: models[n].predict(xv[test]) for n in names}
    primary = "ensemble" if len(names) == 2 else names[0]
    if len(names) == 2:
        test_scores["ensemble"] = sum(weights[n] * scale[n] * test_scores[n] for n in names)

    report_progress(60, "Scoring controls")
    ols_cols = [next((c for c in options if c in columns), None) for options in (("mom_12_1", "mom_63"), ("size_proxy",), ("book_to_market", "vol_63"))]
    ols_cols = [c for c in ols_cols if c]
    ols = LinearRegression().fit(x_all[ols_cols].to_numpy(float)[train], yv[train])
    ics = daily_ic_table(x_all.iloc[train], labelled["target_return"].iloc[train], labelled["date"].iloc[train])
    ir = (ics.mean() / ics.std(ddof=1).replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    composite_w = ir / max(float(ir.abs().sum()), 1e-12)
    controls = {"ols3": ols.predict(x_all[ols_cols].to_numpy(float)[test]), "ic_composite": x_all.iloc[test].to_numpy(float) @ composite_w.to_numpy()}
    if "ridge" not in names:
        controls["ridge"] = _fit("ridge", {}, xv[train], yv[train], None).predict(xv[test])
    test_frame = labelled.iloc[test][["date", "ticker", "dvol"]].assign(fwd=fwd_simple.iloc[test].to_numpy())
    evaluations = {}
    for name, score in {**{n: test_scores[n] for n in names}, **({"ensemble": test_scores["ensemble"]} if len(names) == 2 else {}), **controls}.items():
        evaluations[name] = evaluate_scores(test_frame.assign(score=score), horizon, cost_bps)
    perf = []
    for name, e in evaluations.items():
        kind = "model" if name == primary else "control" if name in ("ols3", "ic_composite") else "baseline" if name == "ridge" else "component"
        row = {"model": name, "kind": kind, "primary": name == primary, "test_ic": e["test_ic"], "ic_ir": e["ic_ir"], "ic_tstat": e["ic_tstat"],
               "ew_spread": e["equal_weight"]["spread"], "vw_spread": e["value_weight"]["spread"],
               "net_return_per_rebalance": e["net_return_per_rebalance"], "net_sharpe": e["net_sharpe"],
               "turnover": e["turnover"], "capacity_usd": e["capacity"], "ensemble_weight": weights.get(name)}
        if name in validation:
            row["validation_ic"] = _mean_ic(validation[name], yv[val], dates_np[val])
        perf.append(row)
    leaderboard = [{k: r.get(k) for k in ("model", "kind", "validation_ic", "test_ic", "ic_ir", "ic_tstat", "ensemble_weight")} for r in perf]
    decile_bars = [{"model": name, "weighting": wt, "bin": b + 1, "mean_return": r}
                   for name, e in evaluations.items() for wt, key in (("equal", "equal_weight"), ("value", "value_weight"))
                   for b, r in enumerate(e[key]["bin_returns"])]
    decile_summary = [{"model": name, "weighting": wt, "bins": e["bins"], "spread": e[key]["spread"], "t_stat": e[key]["t_stat"], "rebalances": e["rebalances"]}
                      for name, e in evaluations.items() for wt, key in (("equal", "equal_weight"), ("value", "value_weight"))]
    net_curve = [{"model": name, **point} for name, e in evaluations.items() for point in e["net_curve"]]
    monthly = rolling_monthly_ic(test_scores[primary], fwd_simple.iloc[test], pd.to_datetime(labelled["date"].iloc[test]).reset_index(drop=True))

    report_progress(75, "Refitting for live ranking")
    live_all = panel.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    live_x = _normalise(live_all[columns], live_all["date"]).to_numpy(float)
    full = np.arange(len(labelled))
    final = {n: _fit(n, params[n], xv[full], yv[full], sample_weights(full)) for n in names}
    final_centre = xv.mean(axis=0)
    def blend(x):
        score, contrib, base = 0.0, 0.0, 0.0
        for n in names:
            c, b = _contributions(n, final[n], x, final_centre)
            k = weights[n] * scale[n]
            score = score + k * final[n].predict(x); contrib = contrib + k * c; base = base + k * b
        return np.asarray(score), np.asarray(contrib), np.asarray(base)
    latest_date = live_all["date"].max()
    latest_mask = (live_all["date"] == latest_date).to_numpy()
    x_latest = live_x[latest_mask]
    score, contrib, base = blend(x_latest)
    current = live_all.loc[latest_mask, ["date", "ticker", "sector"]].reset_index(drop=True)
    current["prediction"] = score
    current["rank"] = current["prediction"].rank(ascending=False, method="first").astype(int)
    order = current.sort_values("rank").index.to_numpy()
    cap = max(1, min(int(request.get("exact_shap_cap", 64)), len(current)))
    sample = order[np.unique(np.round(np.linspace(0, len(order) - 1, cap)).astype(int))]
    importance = np.abs(contrib).mean(axis=0)
    shap_importance = [{"feature": c, "family": FEATURE_FAMILY.get(c, "custom"), "mean_abs_shap": float(importance[j])} for j, c in enumerate(columns)]
    shap_importance.sort(key=lambda r: -r["mean_abs_shap"])
    beeswarm = [{"ticker": current.ticker.iloc[i], "feature": c, "feature_value": float(x_latest[i, j]), "shap_value": float(contrib[i, j])}
                for i in sample for j, c in enumerate(columns)]
    top = order[0]
    waterfall = [{"feature": c, "shap_value": float(contrib[top, j]), "feature_value": float(x_latest[top, j])} for j, c in enumerate(columns)]
    ticker_contributions = [{"ticker": current.ticker.iloc[i], "rank": int(current["rank"].iloc[i]), "prediction": float(score[i]),
                             "base_value": float(base[i]), "contributions": {c: float(contrib[i, j]) for j, c in enumerate(columns)}} for i in order]
    families = {}
    for row in shap_importance:
        families[row["family"]] = families.get(row["family"], 0.0) + row["mean_abs_shap"]
    family_rows = [{"family": f, "mean_abs_shap": v, "features": [c for c in columns if FEATURE_FAMILY.get(c, "custom") == f]} for f, v in sorted(families.items(), key=lambda kv: -kv[1])]
    changed, changed_meta = _what_changed(live_all, columns, live_x, lambda x: blend(x)[:2], horizon, 10)

    artifact_id = put_artifact("alpha_predictions", {
        "as_of": latest_date, "horizon": horizon, "universe": universe_label(request, ctx.symbols), "model": primary,
        "predictions": {row.ticker: {"score": float(row.prediction), "rank": int(row.rank)} for row in current.itertuples()},
        "heldout": {"date": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in test_frame["date"]], "ticker": test_frame["ticker"].tolist(),
                    "score": [float(v) for v in test_scores[primary]], "forward_return": [float(v) for v in test_frame["fwd"]]}})
    train_dates, test_dates = labelled["date"].iloc[train], labelled["date"].iloc[test]
    provenance = build_provenance(ctx.closes, calendar=ctx.calendar, train_window=(train_dates.min(), train_dates.max()), test_window=(test_dates.min(), test_dates.max()),
                                  purge=horizon, embargo=embargo, universe=universe_label(request, ctx.symbols),
                                  extra={"features": len(columns), "features_dropped_low_coverage": [c for c in all_columns if c not in columns]})
    alerts = []
    if horizon < 21:
        alerts.append({"level": "warning", "message": "Horizons under 21 sessions have weak out-of-sample evidence; the 21-day default matches the published monthly results."})
    if unavailable and family == "ensemble" and "lightgbm" in unavailable:
        alerts.append({"level": "warning", "message": "LightGBM is not installed; the ranking uses the Ridge baseline alone."})
    best_ic = evaluations[primary]["test_ic"]
    control_ics = {n: e["test_ic"] for n, e in evaluations.items() if n in ("ols3", "ic_composite") and e["test_ic"] is not None}
    best_control = max(control_ics, key=control_ics.get) if control_ics else None
    return response("02", [summary("Held-out IC", best_ic, "IC"),
                           summary(f"{_CONTROL_LABELS.get(best_control, best_control)} IC" if best_control else "Best control IC", control_ics.get(best_control), "IC"),
                           summary("Net Sharpe", evaluations[primary]["net_sharpe"], "Sharpe"),
                           summary("Top name", str(current.sort_values("rank").ticker.iloc[0]), "ticker")],
        charts={"prediction_rank_table": compact_records(current.sort_values("rank")), "shap_feature_importance": shap_importance,
                "shap_beeswarm": beeswarm, "shap_waterfall_top_signal": waterfall, "model_ic_leaderboard": leaderboard,
                "rolling_monthly_ic_series": monthly, "decile_spreads": decile_bars, "net_of_cost_curve": net_curve},
        tables={"current_predictions": compact_records(current.sort_values("rank")), "model_performance": perf,
                "controls": [r for r in perf if r["kind"] in ("model", "control", "baseline")],
                "ensemble": [{**row["weights"], "validation_ic": row["validation_ic"], "chosen": row is best} for row in grid], "decile_summary": decile_summary, "what_changed": changed, "ticker_contributions": ticker_contributions,
                "feature_families": family_rows,
                "heldout_predictions": compact_records(test_frame.assign(prediction=test_scores[primary], actual_forward_return=test_frame["fwd"])[["date", "ticker", "prediction", "actual_forward_return"]], limit=10000),
                "tuning_trials": trials,
                "training_audit": [{"train_rows": len(train), "validation_rows": len(val), "test_rows": len(test), "selected_model": primary,
                                    "ensemble_weights": weights, "features": columns, "ols3_columns": ols_cols}]},
        alerts=alerts, provenance=provenance,
        meta={"artifact_id": artifact_id, "selection": "ensemble weights and ridge scale chosen on a purged validation window before the holdout",
              "target": "date-demeaned forward log return over the horizon; features rank-scaled to [-1,1] within each date",
              "attribution": "exact TreeSHAP (pred_contrib) for trees, coefficient times centred feature for Ridge; blended with the ensemble weights, so contributions sum to the prediction minus base_value",
              "decile_weighting": "equal weight and value weight by 63-session average dollar volume (a proxy for market cap)",
              "net_of_cost": f"long-short top and bottom bin, equal weight, rebalanced every {horizon} sessions at {cost_bps} bps per unit traded; turnover = traded notional / (2 x gross)",
              "capacity": f"smallest AUM at which any trade exceeds {int(PARTICIPATION * 100)}% of 63-day average dollar volume, median over rebalances, native currency",
              "optional_libraries_unavailable": unavailable, "live_refit": "all_available_matured_labels",
              "what_changed": changed_meta, "feature_value_scale": "rank-scaled within date, [-1, 1]",
              "sector_metadata": "current_snapshot; not a historical classifier"})
