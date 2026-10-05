"""Purged alpha evaluation, train-only model selection and genuine SHAP."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from .performance import fast_spearman_ic
from .validation import chronological_purged_split
from .common import compact_records, response, summary
from .estimators import rolling_monthly_ic
from .panel import load_context, make_feature_panel, numeric_xy


def run_gbt_alpha(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    sectors = ctx.payload.get("sector_filter")
    minimum = float(ctx.payload.get("minimum_formation_notional",0))
    if minimum < 0:
        raise ValueError("minimum_formation_notional must be nonnegative")
    liquidity = (ctx.closes.iloc[:63]*ctx.volumes.iloc[:63]).mean()
    allowed = [symbol for symbol in ctx.symbols if (not sectors or ctx.sectors.get(symbol) in sectors) and liquidity.get(symbol,0)>=minimum]
    if not allowed:
        raise ValueError("No assets satisfy formation-history universe filters")
    ctx.symbols = allowed
    ctx.returns = ctx.returns[allowed]; ctx.closes = ctx.closes[allowed]; ctx.volumes = ctx.volumes[allowed]
    ctx.ohlcv = ctx.ohlcv.loc[ctx.ohlcv.Ticker.isin(allowed)]
    horizon = int(ctx.payload.get("prediction_horizon", 5))
    panel, target = make_feature_panel(ctx, horizon=horizon)
    columns = list(numeric_xy(panel, target)[0].columns)
    raw = panel[columns].replace([np.inf, -np.inf], np.nan)
    train, test = chronological_purged_split(panel, horizon, int(ctx.payload.get("embargo_period", 5)))
    inner_train, validation = chronological_purged_split(panel.iloc[train].reset_index(drop=True), horizon, 5)
    weighting = ctx.payload.get("sample_weighting","equal")
    if weighting not in {"equal","time_decay"}:
        raise ValueError("Unsupported sample_weighting")
    def fit(estimator,features,outcomes):
        dates = pd.to_datetime(panel.loc[outcomes.index,"date"])
        age = (dates.max()-dates).dt.days.to_numpy()
        weights = np.exp(-np.log(2)*age/252) if weighting == "time_decay" else np.ones(len(outcomes))
        return estimator.fit(features,outcomes,sample_weight=weights)
    models = {"ridge": Ridge(alpha=5),
        "random_forest": RandomForestRegressor(n_estimators=100, max_depth=5, min_samples_leaf=10, random_state=7, n_jobs=1),
        "extra_trees": ExtraTreesRegressor(n_estimators=100, max_depth=5, min_samples_leaf=10, random_state=11, n_jobs=1),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=.04, random_state=13)}
    missing = []
    for family, module, name, kwargs in [
        ("xgboost", "xgboost", "XGBRegressor", {"n_estimators":80,"max_depth":3,"n_jobs":1,"random_state":17}),
        ("lightgbm", "lightgbm", "LGBMRegressor", {"n_estimators":100,"max_depth":4,"n_jobs":1,"random_state":19,"verbosity":-1}),
        ("catboost", "catboost", "CatBoostRegressor", {"iterations":100,"depth":4,"random_seed":23,"verbose":False,"allow_writing_files":False})]:
        try:
            import importlib
            models[family] = getattr(importlib.import_module(module), name)(**kwargs)
        except ImportError:
            missing.append(family)
    family = str(ctx.payload.get("model_family", "all"))
    if family != "all":
        if family not in models:
            raise ValueError(f"Requested model family {family} is unavailable")
        models = {family: models[family]}
    inner_imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    ix = inner_imputer.fit_transform(raw.iloc[train[inner_train]])
    vx = inner_imputer.transform(raw.iloc[train[validation]])
    iy = target.iloc[train[inner_train]]; vy = target.iloc[train[validation]]
    tuning = str(ctx.payload.get("tuning_mode", "platform_defaults"))
    trials = []
    if tuning == "manual":
        parameters = ctx.payload.get("hyperparameters")
        if not isinstance(parameters, dict) or not parameters or family == "all":
            raise ValueError("Manual tuning requires one model_family and a hyperparameters object")
        if set(parameters) - set(models[family].get_params()):
            raise ValueError("Unknown estimator hyperparameter")
        models[family].set_params(**parameters)
    elif tuning == "optuna_research":
        import optuna
        count = int(ctx.payload.get("optuna_trials", 10))
        if not 1 <= count <= 50:
            raise ValueError("optuna_trials must be between 1 and 50")
        for name, model in models.items():
            def objective(trial):
                params = {"alpha":trial.suggest_float("alpha", .001, 100, log=True)} if name == "ridge" else {
                    "depth" if name == "catboost" else "max_depth":trial.suggest_int("depth" if name == "catboost" else "max_depth", 2, 6)}
                fitted = fit(clone(model).set_params(**params),ix,iy)
                return float(mean_absolute_error(vy, fitted.predict(vx)))
            study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=7))
            study.optimize(objective, n_trials=count)
            model.set_params(**study.best_params)
            trials.extend({"model":name,"trial":t.number,"validation_mae":t.value,"parameters":t.params} for t in study.trials)
    elif tuning != "platform_defaults":
        raise ValueError("Unsupported tuning_mode")
    selection = []
    for name, model in models.items():
        prediction = fit(clone(model),ix,iy).predict(vx)
        selection.append({"model":name,"validation_mae":float(mean_absolute_error(vy,prediction)),
                          "validation_ic":fast_spearman_ic(prediction,vy.to_numpy())})
    best = min(selection,key=lambda row:row["validation_mae"])["model"]
    # Model choice and ensemble weights are locked before observing final holdout outcomes.
    positive = np.array([max(row["validation_ic"],0.) if np.isfinite(row["validation_ic"]) else 0. for row in selection])
    weights = positive / positive.sum() if positive.sum() > 0 else np.array([float(row["model"] == best) for row in selection])
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    tx = imputer.fit_transform(raw.iloc[train]); ex = imputer.transform(raw.iloc[test])
    predictions = {}; performance = []
    for row, weight in zip(selection,weights):
        model = fit(clone(models[row["model"]]),tx,target.iloc[train])
        predictions[row["model"]] = model.predict(ex)
        performance.append({**row,"ensemble_weight":float(weight),"test_ic":fast_spearman_ic(predictions[row["model"]],target.iloc[test].to_numpy()),
                            "test_mae":float(mean_absolute_error(target.iloc[test],predictions[row["model"]]))})
    live, _ = make_feature_panel(ctx,horizon=horizon,include_unlabelled=True)
    live = live.sort_values("date").drop_duplicates("ticker",keep="last")
    live_imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    fit_x = live_imputer.fit_transform(raw); latest_x = live_imputer.transform(live[columns])
    production = fit(clone(models[best]),fit_x,target)
    current = live[["date","ticker","sector"]].copy()
    current["prediction"] = production.predict(latest_x)
    current["rank"] = current.prediction.rank(ascending=False,method="first")
    exact, beeswarm, waterfall = [], [], []
    shap_status = "unavailable"
    try:
        import shap
        cap = int(ctx.payload.get("exact_shap_cap",64))
        if not 1 <= cap <= 256:
            raise ValueError("exact_shap_cap must be between 1 and 256")
        sample = latest_x[:cap]
        explainer = shap.LinearExplainer(production,fit_x[:min(256,len(fit_x))]) if best == "ridge" else shap.TreeExplainer(production)
        explanation = explainer(sample)
        values = np.asarray(explanation.values)
        exact = [{"feature":col,"mean_abs_shap":float(np.abs(values[:,j]).mean())} for j,col in enumerate(columns)]
        beeswarm = [{"ticker":str(current.ticker.iloc[i]),"feature":col,"feature_value":float(sample[i,j]),"shap_value":float(values[i,j])} for i in range(len(sample)) for j,col in enumerate(columns)]
        if len(sample):
            waterfall = [{"feature":col,"shap_value":float(values[0,j])} for j,col in enumerate(columns)]
        shap_status = "exact"
    except ImportError as exc:
        shap_status = f"unavailable: {exc}"
    ensemble = sum(predictions[row["model"]] * weight for row,weight in zip(selection,weights))
    evaluations = panel.iloc[test][["date","ticker"]].copy()
    evaluations["prediction"] = ensemble; evaluations["actual_forward_return"] = target.iloc[test].to_numpy()
    monthly = rolling_monthly_ic(ensemble,target.iloc[test],pd.to_datetime(panel.date.iloc[test]).reset_index(drop=True))
    return response("02",[summary("Selected Model",best,"model"),summary("Coverage",len(current),"assets")],
        charts={"prediction_rank_table":compact_records(current.sort_values("rank")),"shap_feature_importance":exact,
                "shap_beeswarm":beeswarm,"shap_waterfall_top_signal":waterfall,
                "model_ic_leaderboard":performance,"rolling_monthly_ic_series":monthly},
        tables={"current_predictions":compact_records(current.sort_values("rank")),"model_performance":performance,
                "heldout_predictions":compact_records(evaluations,limit=10000),"tuning_trials":trials,
                "training_audit":[{"train_rows":len(train),"test_rows":len(test),"validation_rows":len(validation),"selected_model":best}]},
        meta={"selection":"nested_purged_training_validation_mae","ensemble_weights":"training_validation_positive_ic_or_best_validation_model",
              "shap_status":shap_status,"shap_base_value":float(np.asarray(explanation.base_values).reshape(-1)[0]) if shap_status == "exact" else None,
              "optional_libraries_unavailable":missing,"live_refit":"all_available_matured_labels","imputation":"training_median","sample_weighting":weighting,"universe_filter":"initial_63_observed_rows_notional; native_quote_units",
              "sector_metadata":"current_snapshot; not a historical classifier"})
