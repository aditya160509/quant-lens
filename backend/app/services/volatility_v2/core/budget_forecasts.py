"""Past-only risk forecasts and matured-label BTZ portfolio return forecasts."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
from .dcc import expanding_dcc, correlation
from .garch import expanding_model, fit_model
from .regimes import filtered_regimes, regime_features, state_names
from .vrp import observed_iv, integrated_garch_variance
from .har import expanding_forecasts


def covariances(returns, payload):
    source = payload.get("forecast_source", "dcc").lower()
    minimum = int(payload.get("min_train", 252))
    refit = int(payload.get("refit_interval", 63))
    annualization = int(payload.get("annualization", 252))
    if minimum < 120 or refit < 1 or annualization <= 0 or len(returns) <= minimum:
        raise ValueError("Invalid risk forecast controls or insufficient observations")
    if source == "dcc":
        result = expanding_dcc(
            returns,
            min_train=minimum,
            refit_interval=refit,
            annualization=annualization,
            dynamics=payload.get("dynamics", "dcc"),
            midas_k=int(payload.get("midas_k", 36)),
        )
        index = pd.DatetimeIndex([row["date"] for row in result["timeline"]])
        return (
            pd.Series(result["covariances"], index=index, dtype=object),
            result["forecast_covariance"],
            {
                "forecast_source": "dcc",
                "forecast_observed_through": returns.index[-1],
                "parameters": result["parameters"],
            },
        )
    if source == "ewma":
        half_life = float(payload.get("forecast_halflife", 21))
        if half_life <= 0:
            raise ValueError("forecast_halflife must be positive")
        decay = np.exp2(-1 / half_life)
        values = returns.to_numpy(dtype=float)
        matrix = np.cov(values[:minimum], rowvar=False, ddof=1)
        matrix = np.atleast_2d(matrix)
        rows = []
        for position in range(minimum, len(values)):
            correlation(matrix)
            rows.append(matrix.copy() * annualization)
            matrix = decay * matrix + (1 - decay) * np.outer(
                values[position], values[position]
            )
        latest = pd.DataFrame(
            matrix * annualization, index=returns.columns, columns=returns.columns
        )
        return (
            pd.Series(rows, index=returns.index[minimum:], dtype=object),
            latest,
            {
                "forecast_source": "ewma",
                "forecast_observed_through": returns.index[-1],
                "conditional_mean_assumption": "zero",
                "half_life": half_life,
            },
        )
    if source != "garch":
        raise ValueError("forecast_source must be dcc, garch or ewma")
    variance = {}
    latest_variance = []
    for asset in returns:
        frame, _ = expanding_model(
            returns[asset],
            min_train=minimum,
            refit_interval=refit,
            evaluation_days=len(returns),
            model=payload.get("garch_model", "GARCH"),
            distribution=payload.get("garch_distribution", "Student-t"),
        )
        variance[asset] = frame.variance
        fit = fit_model(
            returns[asset],
            payload.get("garch_model", "GARCH"),
            payload.get("garch_distribution", "Student-t"),
        )
        latest_variance.append(
            float(fit.forecast(horizon=1).residual_variance.iloc[-1, 0]) / 10000
        )
    variance = pd.DataFrame(variance).dropna()
    window = int(payload.get("correlation_window", 252))
    if window < 30:
        raise ValueError("correlation_window must be at least 30 sessions")
    rows = []
    for date, values in variance.iterrows():
        position = returns.index.get_loc(date)
        corr = returns.iloc[max(0, position - window) : position].corr().to_numpy()
        correlation(corr)
        rows.append(corr * np.sqrt(np.outer(values, values)) * annualization)
    corr = returns.tail(window).corr().to_numpy()
    latest = pd.DataFrame(
        corr * np.sqrt(np.outer(latest_variance, latest_variance)) * annualization,
        index=returns.columns,
        columns=returns.columns,
    )
    return (
        pd.Series(rows, index=variance.index, dtype=object),
        latest,
        {
            "forecast_source": "garch",
            "forecast_observed_through": returns.index[-1],
            "correlation_model": "observed rolling correlation through the prior close, not DCC",
            "correlation_window": window,
        },
    )


def regime_targets(ohlcv, asset, returns, payload, fixed_target):
    ohlcv = ohlcv.loc[ohlcv.Date <= returns.index[-1]]
    fitted = filtered_regimes(
        regime_features(ohlcv, asset),
        states=int(payload.get("states", 4)),
        min_train=int(payload.get("regime_min_train", 252)),
        refit_interval=int(payload.get("regime_refit_interval", 126)),
        restarts=int(payload.get("hmm_restarts", 3)),
    )
    names = state_names(fitted["selected_states"])
    raw = payload.get("regime_targets")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            try:
                raw = dict(part.strip().split(":", 1) for part in raw.split(","))
            except ValueError as exc:
                raise ValueError(
                    "regime_targets must be JSON or regime:value pairs"
                ) from exc
    aliases = {
        "low": "low_vol",
        "normal": "transition",
        "medium": "transition",
        "high": "high_vol",
    }
    if raw is None:
        multipliers = {
            "low_vol": 1.2,
            "transition": 1.0,
            "high_vol": 0.8,
            "crisis": 0.6,
        }
        assigned = {name: fixed_target * multipliers[name] for name in names}
    else:
        if not isinstance(raw, dict):
            raise ValueError("regime_targets must be a mapping")
        assigned = {
            aliases.get(name, name): float(value) for name, value in raw.items()
        }
        if len(assigned) != len(raw):
            raise ValueError("regime_targets contains duplicate regime aliases")
        if set(assigned) != set(names):
            raise ValueError(f"regime_targets must specify exactly: {', '.join(names)}")
    if not np.isfinite(list(assigned.values())).all() or min(assigned.values()) <= 0:
        raise ValueError("Regime targets must be finite and positive")
    probabilities = fitted["probabilities"]
    if not probabilities.hmm_converged.all():
        raise ValueError(
            f"{int((~probabilities.hmm_converged).sum())} HMM forecast dates did not converge; no target is substituted"
        )
    current = probabilities[names].mul(pd.Series(assigned)).sum(axis=1)
    if current.index[-1] != returns.index[-1]:
        raise ValueError("No causal regime target on the final aligned portfolio date")
    # Reindex before shifting: a missing observation cannot become an earlier stale probability.
    historical = current.reindex(returns.index).shift(1)
    return (
        historical,
        float(current.iloc[-1]),
        probabilities[names],
        {
            "assigned_targets": assigned,
            "regime_asset": asset,
            "model": "Feature 04 causal filtered HMM",
            "current_probabilities": probabilities[names].iloc[-1].to_dict(),
            "source_fingerprint": fitted["source_fingerprint"],
        },
    )


def btz_returns(returns, payload, probabilities=None):
    horizon = int(payload.get("kelly_return_horizon", 21))
    annualization = int(payload.get("annualization", 252))
    if not 1 <= horizon <= 252:
        raise ValueError("kelly_return_horizon must be between 1 and 252 sessions")
    if annualization != 252:
        raise ValueError(
            "BTZ IV/physical forecasts currently require the declared 252-session annualization convention"
        )
    observed = {
        asset: observed_iv(asset, returns.index, payload.get("iv_upload_id"))
        for asset in returns
    }
    series, details = {}, []
    for asset in returns:
        log_returns = np.log1p(returns[asset])
        iv, source = observed[asset]
        physical = integrated_garch_variance(
            log_returns,
            (21,),
            int(payload.get("min_train", 252)),
            int(payload.get("refit_interval", 63)),
        )
        vrp = (iv[30].pow(2) - physical[21]) / 12
        predictors = vrp.rename("monthly_variance_vrp").to_frame()
        if probabilities is not None:
            aligned = probabilities.reindex(returns.index)
            # K slopes and K-1 intercept differences avoid the probability-sum collinearity.
            predictors = pd.concat(
                [aligned.iloc[:, 1:], aligned.mul(vrp, axis=0).add_prefix("vrp_")],
                axis=1,
            )
        forward = (
            log_returns.rolling(horizon, min_periods=horizon).sum().shift(-horizon)
        )
        rows, _, _, coefficients = expanding_forecasts(
            predictors,
            forward,
            horizon=horizon,
            min_train=int(payload.get("btz_min_train", 120)),
            refit_interval=int(payload.get("refit_interval", 63)),
        )
        formed = rows.set_index("date").forecast.reindex(returns.index)
        if pd.isna(formed.iloc[-1]):
            raise ValueError(
                f"No current matured-label BTZ expected return for {asset}"
            )
        series[asset] = formed * annualization / horizon
        details.append(
            {
                "asset": asset,
                "iv_source": source,
                "horizon_sessions": horizon,
                "current_annual_log_return_forecast": float(series[asset].iloc[-1]),
                "coefficients": coefficients,
            }
        )
    return pd.DataFrame(series), details


def kelly_target(
    annual_log_means, covariance, weights, gross_cap=3, cash_rate_annual=0
):
    """Nonnegative, gross-bounded continuous-time Kelly in the reference direction."""
    covariance = np.asarray(covariance, dtype=float)
    weights = np.asarray(weights, dtype=float)
    means = np.asarray(annual_log_means, dtype=float)
    if (
        means.shape != weights.shape
        or covariance.shape != (len(weights), len(weights))
        or not np.isfinite(means).all()
        or gross_cap <= 0
    ):
        raise ValueError("Invalid Kelly forecast dimensions or controls")
    variance = float(weights @ covariance @ weights)
    if variance <= 0 or not np.isfinite(variance):
        raise ValueError("Kelly forecast requires positive finite variance")
    arithmetic = means + 0.5 * np.diag(covariance)
    excess = float(weights @ arithmetic - weights.sum() * cash_rate_annual)
    unconstrained = excess / variance
    leverage = min(max(0, unconstrained), gross_cap / np.abs(weights).sum())
    return {
        "btz_implied_annual_excess_return": excess,
        "unconstrained_kelly_leverage": unconstrained,
        "constrained_kelly_leverage": leverage,
        "kelly_optimal_vol_target": float(leverage * np.sqrt(variance)),
    }
