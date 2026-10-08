"""Expanding HAR forecasts whose training labels have matured at formation."""

from __future__ import annotations
import numpy as np
import pandas as pd
import statsmodels.api as sm


def expanding_forecasts(
    x,
    y,
    horizon=1,
    min_train=120,
    refit_interval=21,
    log_target=False,
    bandwidth=None,
    confidence=0.90,
    loss_function="squared_error",
    directional_baseline=None,
):
    """At close t, use only origins s for which s+horizon <= t.

    Forecasts between refits keep the last fitted coefficients. Missing predictors
    are omitted explicitly, never forward/back filled or replaced by zero.
    """
    if horizon < 1 or min_train < 30 or refit_interval < 1 or not 0.5 < confidence < 1:
        raise ValueError("Invalid expanding forecast controls")
    if loss_function not in {"qlike", "squared_error"}:
        raise ValueError("Unknown forecast loss")
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
            design = sm.add_constant(train[x.columns], has_constant="add")
            normalized = design.to_numpy() / np.maximum(
                np.linalg.norm(design.to_numpy(), axis=0), 1e-30
            )
            if np.linalg.matrix_rank(normalized) < design.shape[1]:
                raise ValueError(
                    "Forecast predictors are rank-deficient; coefficients are not identifiable"
                )
            fit = sm.OLS(target, design).fit(
                cov_type="HAC",
                cov_kwds={"maxlags": bandwidth if bandwidth is not None else horizon},
            )
            last_refit, n_train = t, len(train)
            # Most recent observed response is from the matured origin plus h.
            train_end = x.index[x.index.get_loc(train.index[-1]) + horizon]
        design = np.r_[1.0, x.iloc[t].to_numpy()]
        pred = (
            fit.get_prediction(design[None, :])
            .summary_frame(alpha=1 - confidence)
            .iloc[0]
        )
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
            "lower": lower.to_numpy(),
            "upper": upper.to_numpy(),
            "confidence": confidence,
            "p05": lower.to_numpy() if confidence == 0.90 else np.nan,
            "p95": upper.to_numpy() if confidence == 0.90 else np.nan,
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
        if loss_function == "qlike":
            losses = ratio - np.log(ratio) - 1
        accuracy.update(
            rmse=float(np.sqrt(error.pow(2).mean())),
            mae=float(error.abs().mean()),
            r2_oos=float(1 - error.pow(2).sum() / baseline_sse)
            if baseline_sse > 0
            else None,
            qlike=float((ratio - np.log(ratio) - 1).mean()) if len(ratio) else None,
            directional_hit_rate=float(
                (
                    (
                        evaluated.prediction
                        - directional_baseline.reindex(evaluated.index)
                    )
                    * (evaluated.actual - directional_baseline.reindex(evaluated.index))
                    > 0
                ).mean()
            )
            if directional_baseline is not None
            else None,
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


def causal_combination(model_rows, horizon, loss_function="qlike", min_history=30):
    """Combine forecasts with weights learned only from already matured outcomes.

    Equal weights are a separately declared policy; inverse-loss weights are not
    produced until all included models have enough common matured evaluations.
    """
    forecasts = pd.concat(
        {name: rows.set_index("date").forecast for name, rows in model_rows.items()},
        axis=1,
    )
    actual = next(iter(model_rows.values())).set_index("date").actual
    if loss_function == "qlike":
        ratio = (
            forecasts.where(forecasts.gt(0))
            .div(actual.where(actual > 0), axis=0)
            .pow(-2)
        )
        losses = (ratio - np.log(ratio) - 1).where(forecasts.gt(0))
    else:
        losses = forecasts.sub(actual, axis=0).pow(2)
    losses = losses.replace([np.inf, -np.inf], np.nan)
    records = []
    for position, (date, row) in enumerate(forecasts.iterrows()):
        if row.isna().any():
            continue
        records.append(
            {
                "date": date,
                "model": "Equal combination",
                "horizon": horizon,
                "forecast": float(row.mean()),
                "actual": actual.loc[date],
                "weight_policy": "equal across explicitly selected models",
            }
        )
        # The outcome of an origin s matures at s+h, including close t itself.
        matured = losses.iloc[: max(0, position - horizon + 1)].dropna()
        if len(matured) < min_history:
            continue
        means = matured.mean()
        zeros = means.le(np.finfo(float).eps)
        weights = (
            zeros.astype(float) / zeros.sum()
            if zeros.any()
            else (1 / means) / (1 / means).sum()
        )
        records.append(
            {
                "date": date,
                "model": "Inverse-loss combination",
                "horizon": horizon,
                "forecast": float(row @ weights),
                "actual": actual.loc[date],
                "weights": weights.to_dict(),
                "matured_evaluations": len(matured),
                "latest_training_origin": matured.index[-1],
            }
        )
    return records


def directional_dm_table(model_rows, baseline, horizon):
    """HAC loss-difference tests for observed up/down volatility accuracy."""
    from scipy.stats import norm

    losses = {}
    for name, records in model_rows.items():
        rows = records.set_index("date")
        current = baseline.reindex(rows.index)
        complete = rows.forecast.notna() & rows.actual.notna() & current.notna()
        correct = (rows.forecast - current) * (rows.actual - current) > 0
        losses[name] = (1 - correct.astype(float)).where(complete)
    tests = max(1, len(losses) * (len(losses) - 1) // 2)
    output = []
    for a in losses:
        for b in losses:
            difference = (losses[a] - losses[b]).dropna()
            statistic = p_value = None
            reason = None
            if a == b:
                statistic, p_value = 0.0, 1.0
            elif len(difference) < 30:
                reason = "At least 30 aligned directional evaluations required"
            else:
                fit = sm.OLS(difference.to_numpy(), np.ones((len(difference), 1))).fit(
                    cov_type="HAC",
                    cov_kwds={
                        "maxlags": max(horizon - 1, int(len(difference) ** (1 / 3)))
                    },
                )
                if np.isfinite(fit.bse[0]) and fit.bse[0] > 0:
                    statistic = float(fit.params[0] / fit.bse[0])
                    p_value = float(2 * norm.sf(abs(statistic)))
                else:
                    reason = "Directional loss-difference variance is unidentifiable"
            output.append(
                {
                    "row": a,
                    "col": b,
                    "horizon": horizon,
                    "dm_stat": statistic,
                    "p_value": p_value,
                    "observations": len(difference),
                    "bonferroni_significant": p_value is not None
                    and a != b
                    and p_value < 0.05 / tests,
                    "unavailable_reason": reason,
                }
            )
    return output
