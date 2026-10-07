"""Expanding HAR forecasts whose training labels have matured at formation."""

from __future__ import annotations
import numpy as np
import pandas as pd
import statsmodels.api as sm


def expanding_forecasts(
    x, y, horizon=1, min_train=120, refit_interval=21, log_target=False, bandwidth=None
):
    """At close t, use only origins s for which s+horizon <= t.

    Forecasts between refits keep the last fitted coefficients. Missing predictors
    are omitted explicitly, never forward/back filled or replaced by zero.
    """
    if horizon < 1 or min_train < 30 or refit_interval < 1:
        raise ValueError("Invalid expanding forecast controls")
    x = x.astype(float).replace([np.inf, -np.inf], np.nan)
    y = y.astype(float).replace([np.inf, -np.inf], np.nan)
    predictions = pd.Series(np.nan, index=x.index, dtype=float)
    means = pd.Series(np.nan, index=x.index, dtype=float)
    lower, upper = predictions.copy(), predictions.copy()
    train_ends = pd.Series(pd.NaT, index=x.index, dtype="datetime64[ns]")
    sizes = pd.Series(0, index=x.index, dtype=int)
    fit, last_refit, n_train, train_end = None, -refit_interval, 0, None
    for t in range(horizon, len(x)):
        if x.iloc[t].isna().any():
            continue
        if fit is None or t - last_refit >= refit_interval:
            end = t - horizon + 1
            train = pd.concat(
                [y.iloc[:end].rename("target"), x.iloc[:end]], axis=1
            ).dropna()
            if log_target:
                train = train.loc[train.target > 0]
            if len(train) < min_train:
                continue
            target = np.log(train.target) if log_target else train.target
            fit = sm.OLS(
                target, sm.add_constant(train[x.columns], has_constant="add")
            ).fit(
                cov_type="HAC",
                cov_kwds={"maxlags": bandwidth if bandwidth is not None else horizon},
            )
            last_refit, n_train = t, len(train)
            # Most recent observed response is from the matured origin plus h.
            train_end = x.index[x.index.get_loc(train.index[-1]) + horizon]
        design = np.r_[1.0, x.iloc[t].to_numpy()]
        pred = fit.get_prediction(design[None, :]).summary_frame(alpha=0.10).iloc[0]
        correction = float(np.var(fit.resid, ddof=1) / 2) if log_target else 0.0
        value = (
            float(np.exp(pred["mean"] + correction))
            if log_target
            else float(pred["mean"])
        )
        predictions.iloc[t] = value
        lower.iloc[t] = (
            float(np.exp(pred.obs_ci_lower)) if log_target else float(pred.obs_ci_lower)
        )
        upper.iloc[t] = (
            float(np.exp(pred.obs_ci_upper)) if log_target else float(pred.obs_ci_upper)
        )
        means.iloc[t] = float(train.target.mean())
        sizes.iloc[t], train_ends.iloc[t] = n_train, train_end
    rows = pd.DataFrame(
        {
            "date": x.index,
            "forecast": predictions.to_numpy(),
            "actual": y.to_numpy(),
            "p05": lower.to_numpy(),
            "p95": upper.to_numpy(),
            "training_observed_through": train_ends.to_numpy(),
            "train_size": sizes.to_numpy(),
        }
    )
    evaluated = pd.concat(
        [
            predictions.rename("prediction"),
            y.rename("actual"),
            means.rename("baseline"),
        ],
        axis=1,
    ).dropna()
    accuracy = {
        "observations": len(evaluated),
        "rmse": None,
        "mae": None,
        "r2_oos": None,
        "qlike": None,
    }
    losses = pd.Series(dtype=float)
    if len(evaluated):
        error = evaluated.prediction - evaluated.actual
        losses = error.pow(2)
        baseline_sse = float((evaluated.actual - evaluated.baseline).pow(2).sum())
        valid = evaluated.loc[(evaluated.actual > 0) & (evaluated.prediction > 0)]
        ratio = (valid.actual / valid.prediction).pow(2)
        accuracy.update(
            rmse=float(np.sqrt(error.pow(2).mean())),
            mae=float(error.abs().mean()),
            r2_oos=float(1 - error.pow(2).sum() / baseline_sse)
            if baseline_sse > 0
            else None,
            qlike=float((ratio - np.log(ratio) - 1).mean()) if len(ratio) else None,
            invalid_nonpositive_forecasts=int((evaluated.prediction <= 0).sum()),
        )
    coefficients = (
        []
        if fit is None
        else [
            {
                "parameter": name,
                "beta": float(fit.params[name]),
                "std_error": float(fit.bse[name]),
                "t_stat": float(fit.tvalues[name]),
            }
            for name in fit.params.index
        ]
    )
    return rows, accuracy, losses, coefficients
