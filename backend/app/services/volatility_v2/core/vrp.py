"""Observed implied volatility versus genuine conditional physical forecasts."""

from __future__ import annotations
import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch import arch_model
from .analytics import macro_frame, ARCH_SPECS, ARCH_DISTS
from .har import expanding_forecasts
from .uploads import load_implied_volatility

BENCHMARKS = {"^GSPC": "vix"}


def observed_iv(asset, index, upload_id=None):
    if (asset in BENCHMARKS or upload_id) and (
        pd.DatetimeIndex(index).dayofweek >= 5
    ).any():
        raise ValueError(
            "Observed IV physical comparison currently supports Monday-Friday sessions and 252-session annualization only; continuous-session calendar mapping is unsupported"
        )
    if upload_id:
        uploaded = load_implied_volatility(upload_id, asset)
        panel = uploaded.pivot(
            index="date", columns="maturity_days", values="implied_vol"
        )
        source = "user-uploaded observed IV: " + ", ".join(
            sorted(uploaded.source.unique())
        )
    elif asset in BENCHMARKS:
        macro = macro_frame().set_index("date")
        panel = (
            macro[["vix", "vix3m", "vix6m"]].rename(
                columns={"vix": 30, "vix3m": 90, "vix6m": 180}
            )
            / 100
        )
        source = "Observed CBOE VIX, VIX3M, VIX6M in the local macro panel; S&P 500 benchmark only"
    else:
        raise ValueError(
            f"No matching observed implied-volatility index for {asset}; upload observed asset-specific IV or select ^GSPC"
        )
    panel = panel.reindex(index)
    if 30 not in panel or panel[30].notna().sum() < 120:
        raise ValueError(
            "At least 120 overlapping observed 30-day IV values are required"
        )
    if pd.isna(panel[30].iloc[-1]):
        raise ValueError(
            "No observed 30-day IV at the final selected price date; choose an earlier as_of_date"
        )
    if (panel.where(panel.notna(), 1) <= 0).any().any():
        raise ValueError("Observed implied volatility must be positive")
    return panel, source


def integrated_garch_variance(
    returns,
    horizons=(21, 63, 126),
    min_train=252,
    refit_interval=21,
    model="GARCH",
    distribution="Student-t",
):
    """Annualized average of next h daily variance forecasts, formed at each close.

    The integrated horizon mean is used, rather than terminal variance times h.
    Parameters are learned only through the first formation date in each block.
    """
    if model not in ("GARCH", "GJR-GARCH") or distribution not in ARCH_DISTS:
        raise ValueError(
            "VRP physical GARCH supports GARCH or GJR-GARCH with a fitted arch distribution"
        )
    returns = returns.dropna().astype(float)
    if min_train < 120 or refit_interval < 1 or len(returns) < min_train:
        raise ValueError("Insufficient returns or invalid physical forecast controls")
    result = pd.DataFrame(np.nan, index=returns.index, columns=list(horizons))
    for t in range(min_train - 1, len(returns), refit_interval):
        stop = min(t + refit_interval, len(returns))
        am = arch_model(
            returns.iloc[:stop] * 100,
            mean="Constant",
            dist=ARCH_DISTS[distribution],
            rescale=False,
            **ARCH_SPECS[model],
        )
        fit = am.fit(
            last_obs=t + 1, disp="off", show_warning=False, options={"maxiter": 500}
        )
        if fit.convergence_flag != 0:
            raise ValueError(f"Physical GARCH fit failed at {returns.index[t]}")
        forecast = (
            fit.forecast(
                start=t, horizon=max(horizons), reindex=False
            ).residual_variance
            / 10000
        )
        for horizon in horizons:
            result.loc[forecast.index, horizon] = (
                forecast.iloc[:, :horizon].mean(axis=1) * 252
            )
    return result


def physical_har_variance(
    returns, daily_vol, horizon, min_train=252, refit_interval=21
):
    # Direct forecast of the integrated next-h annualized squared-return mean.
    # A log target maintains positivity; lognormal bias correction uses only training residuals.
    daily_vol = daily_vol.reindex(returns.index).astype(float)
    x = pd.DataFrame(
        {
            "daily": daily_vol,
            "weekly": daily_vol.rolling(5).mean(),
            "monthly": daily_vol.rolling(22).mean(),
        }
    )
    x = np.log(x.where(x > 0))
    y = returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252
    rows, metrics, _, coefficients = expanding_forecasts(
        x, y, horizon, min_train, refit_interval, log_target=True
    )
    return rows.set_index("date").forecast, metrics, coefficients


def hodrick_null_standard_errors(x, daily_returns, horizon, design):
    """Hodrick (1992) 1B null covariance using lagged sums of predictors.

    Under the no-predictability null, daily demeaned returns replace overlapping
    multi-period residuals. Inference is for the null, not coefficient intervals.
    Missing dates are retained until complete lagged sums are formed.
    """
    predictors = sm.add_constant(x.astype(float), has_constant="add")
    lagged = predictors.rolling(horizon, min_periods=horizon).sum().shift(1)
    errors = daily_returns.astype(float) - daily_returns.mean()
    scores = lagged.mul(errors, axis=0).dropna()
    if len(scores) < 30:
        raise ValueError(
            "Hodrick null covariance requires 30 complete lagged predictor windows"
        )
    xtx = design.to_numpy().T @ design.to_numpy()
    bread = np.linalg.pinv(xtx)
    covariance = bread @ (scores.to_numpy().T @ scores.to_numpy()) @ bread
    return np.sqrt(np.maximum(np.diag(covariance), 0))


def predictive_regression(vrp, daily_returns, horizon, probabilities=None):
    forward = daily_returns.rolling(horizon, min_periods=horizon).sum().shift(-horizon)
    x = vrp.rename("vrp_monthly_variance").to_frame()
    frame = pd.concat([forward.rename("target"), x], axis=1).dropna()
    if len(frame) < 60:
        return {
            "unavailable_reason": "At least 60 matured forward-return observations required",
            "coefficients": [],
            "regime_coefficients": [],
        }
    design = sm.add_constant(frame[x.columns], has_constant="add")
    fit = sm.OLS(frame.target, design).fit(
        cov_type="HAC", cov_kwds={"maxlags": horizon, "kernel": "bartlett"}
    )
    hodrick = hodrick_null_standard_errors(x, daily_returns, horizon, design)
    coefficients = [
        {
            "parameter": name,
            "beta": float(fit.params[name]),
            "std_error_newey_west": float(fit.bse[name]),
            "std_error_hodrick_1992_null": float(hodrick[i]),
            "hodrick_null_t_stat": float(fit.params[name] / hodrick[i])
            if hodrick[i] > 0
            else None,
            "r2_in_sample": float(fit.rsquared),
            "observations": len(frame),
            "horizon": horizon,
        }
        for i, name in enumerate(fit.params.index)
    ]
    conditional = []
    if probabilities is not None:
        for name in probabilities.columns:
            p = probabilities[name].reindex(frame.index)
            usable = p.notna() & p.gt(1e-6)
            if usable.sum() < 60:
                conditional.append(
                    {
                        "regime": name,
                        "unavailable_reason": "Insufficient overlapping causal regime observations",
                    }
                )
                continue
            weighted = sm.WLS(
                frame.loc[usable, "target"], design.loc[usable], weights=p.loc[usable]
            ).fit(cov_type="HAC", cov_kwds={"maxlags": horizon})
            conditional.append(
                {
                    "regime": name,
                    "beta": float(weighted.params.iloc[1]),
                    "std_error_newey_west": float(weighted.bse.iloc[1]),
                    "effective_probability_mass": float(p.loc[usable].sum()),
                    "observations": int(usable.sum()),
                    "horizon": horizon,
                }
            )
    return {"coefficients": coefficients, "regime_coefficients": conditional}


def mean_reversion_half_life(series):
    frame = pd.concat(
        [series.diff().rename("change"), series.shift(1).rename("lag")], axis=1
    ).dropna()
    if len(frame) < 30:
        return np.nan
    slope = float(sm.OLS(frame.change, sm.add_constant(frame.lag)).fit().params.iloc[1])
    phi = 1 + slope
    # Exact discrete AR(1) half-life; negative/unstable phi is not an OU decay.
    return float(np.log(0.5) / np.log(phi)) if 0 < phi < 1 else np.nan
