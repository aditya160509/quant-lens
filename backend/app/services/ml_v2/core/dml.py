"""ML V2 dml implementation."""
from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from .validation import purged_date_folds
from .common import date_str, response, summary
from .panel import load_context, make_feature_panel, numeric_xy


def _nuisance_regressor(kind: str, seed: int = 7):
    kind = str(kind or "ridge").lower()
    if "lightgbm" in kind or "lgbm" in kind:
        try:
            from lightgbm import LGBMRegressor

            return LGBMRegressor(n_estimators=80, max_depth=3, learning_rate=0.05, min_child_samples=20, random_state=seed, n_jobs=1, verbose=-1)
        except ImportError as exc:
            raise ValueError("LightGBM nuisance model is unavailable") from exc
    if "forest" in kind:
        return RandomForestRegressor(n_estimators=80, max_depth=4, min_samples_leaf=12, random_state=seed, n_jobs=1)
    if kind == "elastic_net":
        return ElasticNet(alpha=.0001, l1_ratio=.5, max_iter=5000)
    if kind != "ridge":
        raise ValueError(f"Unknown nuisance model {kind}")
    return Ridge(alpha=2.0)



def dml_cross_fit(x: pd.DataFrame, y: pd.Series, factor: str, k_folds: int = 5,
                  nuisance_model: str = "ridge", *, dates=None, horizon=5, embargo=5) -> tuple[float, float, float]:
    """Chronological cross-fitting with HC3 inference on held-out residuals.

    Effects are conditional associations unless identification assumptions hold.
    """
    import statsmodels.api as sm
    others = [c for c in x.columns if c != factor]
    if not others:
        raise ValueError("DML requires at least one nuisance covariate")
    if dates is None:
        raise ValueError("DML requires observation dates for purged cross-fitting")
    valid = x[factor].notna() & y.notna()
    observed_dates = pd.Series(pd.to_datetime(dates).to_numpy()).loc[valid.to_numpy()].reset_index(drop=True)
    x = x.loc[valid].reset_index(drop=True); y = y.loc[valid].reset_index(drop=True)
    if len(x)<40:
        raise ValueError("Insufficient observed treatment/outcome rows")
    folds = purged_date_folds(pd.DataFrame({"date": observed_dates.to_numpy()}),
                             n_splits=k_folds, horizon=horizon, embargo=embargo)
    treatments, outcomes = [], []
    for train_idx, test_idx in folds:
        x_tr, x_te = x.iloc[train_idx], x.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        from sklearn.impute import SimpleImputer
        imputer = SimpleImputer(strategy="median",keep_empty_features=True)
        observed_others = [col for col in others if x_tr[col].notna().any()]
        if not observed_others:
            raise ValueError("No observed training nuisance covariates")
        train_covariates = imputer.fit_transform(x_tr[observed_others])
        test_covariates = imputer.transform(x_te[observed_others])
        m_f = _nuisance_regressor(nuisance_model, seed=11).fit(train_covariates, x_tr[factor])
        m_y = _nuisance_regressor(nuisance_model, seed=17).fit(train_covariates, y_tr)
        treatments.extend(x_te[factor].to_numpy() - m_f.predict(test_covariates))
        outcomes.extend(y_te.to_numpy() - m_y.predict(test_covariates))
    residual_treatment = np.asarray(treatments)
    if len(residual_treatment) < 20 or np.dot(residual_treatment, residual_treatment) < 1e-12:
        raise ValueError("Insufficient residual treatment variation for DML inference")
    fit = sm.OLS(np.asarray(outcomes), residual_treatment[:, None]).fit(cov_type="HC3")
    return float(fit.params[0]), float(fit.bse[0]), float(fit.tvalues[0])



def hc3_univariate_inference(treatment: pd.Series, y: pd.Series) -> tuple[float, float, float]:
    """Fast HC3 robust slope/se/t-stat for a univariate factor relation."""

    x = pd.to_numeric(treatment, errors="coerce").replace([np.inf, -np.inf], np.nan)
    yy = pd.to_numeric(y, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = x.notna() & yy.notna()
    if valid.sum() < 12:
        return 0.0, 0.0, 0.0
    xv = x[valid].to_numpy(dtype=float)
    yv = yy[valid].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(xv)), xv])
    try:
        xtx_inv = np.linalg.pinv(X.T @ X)
        beta = xtx_inv @ X.T @ yv
        resid = yv - X @ beta
        hat = np.sum((X @ xtx_inv) * X, axis=1)
        scale = (resid / np.maximum(1.0 - hat, 1e-6)) ** 2
        cov = xtx_inv @ (X.T @ (scale[:, None] * X)) @ xtx_inv
        se = math.sqrt(max(float(cov[1, 1]), 0.0))
        slope = float(beta[1])
        return slope, se, slope / max(se, 1e-12)
    except Exception:
        return 0.0, 0.0, 0.0



def run_causal_dml(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    ctx = load_context(request)
    horizon = int(request.get("prediction_horizon", 5))
    panel, y = make_feature_panel(ctx, horizon=horizon)
    x, y = numeric_xy(panel, y)
    folds = int(request.get("dml_folds", 5))
    nuisance = str(request.get("nuisance_model", "ridge"))
    significance = float(request.get("significance_threshold", .95))
    threshold = stats.norm.ppf((1 + significance) / 2)
    rows, unavailable = [], []
    for factor in x.columns:
        try:
            ape, se, t = dml_cross_fit(x, y, factor, k_folds=folds, nuisance_model=nuisance,
                                    dates=panel["date"], horizon=horizon)
        except ValueError as exc:
            unavailable.append({"factor": factor, "status": "unidentified", "reason": str(exc)})
            continue
        ols_slope, ols_se, ols_t = hc3_univariate_inference(x[factor], y)
        rows.append({"factor": factor, "dml_ape": ape, "dml_se": se, "ape_t_stat": t,
                     "lower": ape - threshold * se, "upper": ape + threshold * se,
                     "univariate_slope": ols_slope, "hc3_se": ols_se, "hc3_t_stat": ols_t,
                     "adjustment_vs_univariate_slope": ols_slope - ape,
                     "classification": "significant_conditional_association" if abs(t) > threshold else "not_significant",
                     "signed_weight": ape})
    if not rows:
        raise ValueError("No factors have identifiable held-out residual variation")
    history = []
    dates = pd.DatetimeIndex(pd.to_datetime(panel.date).unique()).sort_values()
    window = int(request.get("rolling_window", 252))
    for end in range(max(80, window), len(dates), 63):
        mask = pd.to_datetime(panel.date).isin(dates[max(0, end-window):end])
        snap, target = x.loc[mask].reset_index(drop=True), y.loc[mask].reset_index(drop=True)
        snap_dates = panel.loc[mask, "date"].reset_index(drop=True)
        for factor in [row["factor"] for row in rows[:6]]:
            try:
                ape, se, _ = dml_cross_fit(snap, target, factor, k_folds=min(3, folds),
                                         nuisance_model=nuisance, dates=snap_dates, horizon=horizon)
            except ValueError:
                continue
            history.append({"date": date_str(dates[end]), "factor": factor, "ape": ape, "se": se})
    robust = [{"factor": row["factor"], "dml_ape": row["dml_ape"], "dml_se": row["dml_se"],
               "univariate_slope": row["univariate_slope"], "hc3_se": row["hc3_se"]} for row in rows]
    return response("11", [summary("Identified factors", len(rows)), summary("Unidentified factors", len(unavailable))],
        charts={"conditional_ape_leaderboard": rows, "ape_time_series": history,
                "adjustment_vs_univariate_slope": rows, "robust_inference_table": robust},
        tables={"conditional_ape_table": rows, "unidentified_factors": unavailable, "robust_inference_table": robust},
        status="warning" if unavailable else "ok",
        alerts=[{"level": "warning", "message": "Some factors are unidentified; see unidentified_factors"}] if unavailable else [],
        meta={"cross_fitting": "purged_expanding_date_folds", "robust_inference": "HC3_on_held_out_residuals",
              "causal_identification": "Not established by observational OHLCV; estimates are conditional associations",
              "as_of_date": date_str(ctx.returns.index.max()), "nuisance_model": nuisance,
              "sector_basis": "time_invariant_current_snapshot"})
