"""Library-backed GARCH forecasts and held-out diagnostics."""

from __future__ import annotations
import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats
from scipy.special import xlogy, xlog1py
from app.services.volatility_v2.core.analytics import (
    ARCH_SPECS,
    ARCH_DISTS,
    model_confidence_set,
)


def fit_model(returns, model="GARCH", distribution="Student-t"):
    if model not in ARCH_SPECS or distribution not in ARCH_DISTS:
        raise ValueError("Unsupported GARCH model or distribution")
    data = pd.to_numeric(returns, errors="raise").dropna() * 100
    if len(data) < 120:
        raise ValueError("GARCH fitting requires at least 120 observed returns")
    fit = arch_model(
        data,
        mean="Constant",
        dist=ARCH_DISTS[distribution],
        rescale=False,
        **ARCH_SPECS[model],
    ).fit(disp="off", show_warning=False, options={"maxiter": 500})
    if fit.convergence_flag != 0:
        raise ValueError(
            f"{model}/{distribution} optimizer did not converge ({fit.convergence_flag})"
        )
    return fit


def expanding_model(
    returns,
    model="GARCH",
    distribution="Student-t",
    min_train=252,
    refit_interval=63,
    evaluation_days=252,
    coverage=0.99,
):
    """One-step variance at t is fitted and filtered using information through t-1."""
    data = pd.to_numeric(returns, errors="raise").dropna()
    if not 0 < coverage < 1 or min_train < 120 or refit_interval < 1:
        raise ValueError("Invalid GARCH evaluation controls")
    start = max(min_train, len(data) - evaluation_days)
    if start >= len(data):
        raise ValueError(
            "Not enough returns for training and held-out GARCH evaluation"
        )
    records = []
    for t in range(start, len(data), refit_interval):
        stop = min(t + refit_interval, len(data))
        # The model contains data only up to the block end; fit restricts the
        # estimation sample to t-1, then forecast filtering uses each prior return.
        am = arch_model(
            data.iloc[:stop] * 100,
            mean="Constant",
            dist=ARCH_DISTS[distribution],
            rescale=False,
            **ARCH_SPECS[model],
        )
        fit = am.fit(
            last_obs=t, disp="off", show_warning=False, options={"maxiter": 500}
        )
        if fit.convergence_flag != 0:
            raise ValueError(
                f"{model}/{distribution} optimizer failed at {data.index[t]}"
            )
        forecast = (
            fit.forecast(horizon=1, start=t - 1, reindex=False).residual_variance.iloc[
                :, 0
            ]
            / 10000
        )
        shape = fit.params.reindex(fit.model.distribution.parameter_names()).to_numpy(
            dtype=float
        )
        mu = float(fit.params.get("mu", 0)) / 100
        cutoff = float(fit.model.distribution.ppf(1 - coverage, shape))
        for pos in range(t, stop):
            variance = float(forecast.loc[data.index[pos - 1]])
            if not np.isfinite(variance) or variance <= 0:
                raise ValueError("Nonpositive GARCH variance forecast")
            observed = float(data.iloc[pos])
            z = (observed - mu) / np.sqrt(variance)
            records.append(
                {
                    "date": data.index[pos],
                    "training_observed_through": data.index[t - 1],
                    "forecast_observed_through": data.index[pos - 1],
                    "variance": variance,
                    "return": observed,
                    "pit": float(fit.model.distribution.cdf(z, shape)),
                    "var_cutoff": mu + cutoff * np.sqrt(variance),
                    "training_size": t,
                }
            )
    frame = pd.DataFrame(records).set_index("date")
    realized = frame["return"].pow(2)
    # QLIKE up to a target-only additive constant, well-defined at zero returns.
    loss = np.log(frame.variance) + realized / frame.variance
    return frame, loss


def evaluate_suite(returns, models=None, distributions=None, **controls):
    models = models or list(ARCH_SPECS)
    distributions = distributions or list(ARCH_DISTS)
    if set(models) - set(ARCH_SPECS) or set(distributions) - set(ARCH_DISTS):
        raise ValueError("Unsupported GARCH family/distribution")
    rows, paths, losses = [], {}, {}
    for model in models:
        for distribution in distributions:
            key = f"{model}-{distribution}"
            try:
                path, loss = expanding_model(returns, model, distribution, **controls)
                latest = fit_model(returns, model, distribution)
                rows.append(
                    {
                        "model": model,
                        "distribution": distribution,
                        "converged": True,
                        "qlike": float(loss.mean()),
                        "rmse": float(
                            np.sqrt(
                                (path.variance - path["return"].pow(2)).pow(2).mean()
                            )
                        ),
                        "observations": len(path),
                        "aic": float(latest.aic),
                        "bic": float(latest.bic),
                        "log_likelihood": float(latest.loglikelihood),
                        "parameters": latest.params.to_dict(),
                    }
                )
                paths[key], losses[key] = path, loss
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
                rows.append(
                    {
                        "model": model,
                        "distribution": distribution,
                        "converged": False,
                        "error": str(exc),
                        "qlike": None,
                        "mcs_member": False,
                    }
                )
    if not paths:
        raise ValueError(
            "All requested GARCH model fits failed: "
            + "; ".join(r["error"] for r in rows)
        )
    winner = min(losses, key=lambda key: losses[key].mean())
    mcs = set(model_confidence_set(losses))
    for row in rows:
        key = f"{row['model']}-{row['distribution']}"
        row.update(winner=key == winner, mcs_member=key in mcs)
    return rows, paths, losses, winner


def var_backtests(path, coverage):
    exceed = (path["return"] < path.var_cutoff).to_numpy(dtype=int)
    n, total = int(exceed.sum()), len(exceed)
    p, phat = 1 - coverage, n / total

    def bin_ll(yes, no, prob):
        return float(xlogy(yes, prob) + xlog1py(no, -prob))

    kupiec = max(0.0, -2 * (bin_ll(n, total - n, p) - bin_ll(n, total - n, phat)))
    counts = np.array(
        [
            ((exceed[:-1] == a) & (exceed[1:] == b)).sum()
            for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))
        ]
    )
    n00, n01, n10, n11 = counts
    if n00 + n01 == 0 or n10 + n11 == 0:
        independence, p_ind = None, None
    else:
        pooled = (n01 + n11) / (total - 1)
        independent = bin_ll(n01 + n11, n00 + n10, pooled)
        markov = bin_ll(n01, n00, n01 / (n00 + n01)) + bin_ll(
            n11, n10, n11 / (n10 + n11)
        )
        independence = max(0.0, -2 * (independent - markov))
        p_ind = float(stats.chi2.sf(independence, 1))
    return {
        "exceptions": n,
        "observations": total,
        "coverage": coverage,
        "kupiec_lr": kupiec,
        "kupiec_p_value": float(stats.chi2.sf(kupiec, 1)),
        "christoffersen_independence_lr": independence,
        "christoffersen_independence_p_value": p_ind,
        "christoffersen_conditional_coverage_lr": kupiec + independence
        if independence is not None
        else None,
        "christoffersen_conditional_coverage_p_value": float(
            stats.chi2.sf(kupiec + independence, 2)
        )
        if independence is not None
        else None,
        "independence_limitation": "Unavailable when either transition origin has no observations"
        if independence is None
        else None,
    }


def forecast_term_structure(
    fit, horizons=(1, 5, 10, 21, 42, 63, 126, 252), simulations=1000
):
    horizons = sorted(set(int(h) for h in horizons))
    if not horizons or min(horizons) < 1 or max(horizons) > 252 or simulations < 100:
        raise ValueError("Invalid GARCH forecast horizons or simulation count")
    dist = type(fit.model.distribution)(seed=23)
    shape = fit.params.reindex(dist.parameter_names()).to_numpy(dtype=float)
    forecast = fit.forecast(
        horizon=max(horizons),
        method="simulation",
        simulations=simulations,
        rng=dist.simulate(shape),
        reindex=False,
    )
    draws = forecast.simulations.residual_variances[-1] / 10000
    # These are terminal-day conditional volatilities, not integrated option IV.
    return [
        {
            "horizon": h,
            "expected_ann_variance": float(draws[:, h - 1].mean() * 252),
            "expected_ann_vol": float(np.sqrt(draws[:, h - 1].mean() * 252)),
            **{
                f"p{int(q * 100):02}": float(
                    np.quantile(np.sqrt(draws[:, h - 1] * 252), q)
                )
                for q in (0.05, 0.25, 0.5, 0.75, 0.95)
            },
            "n_sim": simulations,
        }
        for h in horizons
    ]
