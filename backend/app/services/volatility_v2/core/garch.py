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


def build_model(data, model, distribution, aparch_delta=None):
    """Use arch's volatility process for fixed or estimated APARCH power."""
    am = arch_model(
        data,
        mean="Constant",
        dist=ARCH_DISTS[distribution],
        rescale=False,
        **ARCH_SPECS[model],
    )
    if model == "APARCH" and aparch_delta is not None:
        from arch.univariate import APARCH

        if not 0.05 < float(aparch_delta) < 4:
            raise ValueError("APARCH delta must lie strictly between 0.05 and 4")
        am.volatility = APARCH(p=1, o=1, q=1, delta=float(aparch_delta))
    return am


def fit_model(
    returns, model="GARCH", distribution="Student-t", aparch_delta=None, figarch_d=None
):
    if model not in ARCH_SPECS or distribution not in ARCH_DISTS:
        raise ValueError("Unsupported GARCH model or distribution")
    data = pd.to_numeric(returns, errors="raise").dropna() * 100
    if len(data) < 120:
        raise ValueError("GARCH fitting requires at least 120 observed returns")
    if model == "FIGARCH" and figarch_d is not None:
        return fit_fixed_figarch(data, distribution, float(figarch_d))
    fit = build_model(data, model, distribution, aparch_delta).fit(
        disp="off", show_warning=False, options={"maxiter": 500}
    )
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
    aparch_delta=None,
    figarch_d=None,
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
    records, parameter_history = [], []
    for t in range(start, len(data), refit_interval):
        stop = min(t + refit_interval, len(data))
        # The model contains data only up to the block end; fit restricts the
        # estimation sample to t-1, then forecast filtering uses each prior return.
        am = build_model(data.iloc[:stop] * 100, model, distribution, aparch_delta)
        if model == "FIGARCH" and figarch_d is not None:
            trained = fit_fixed_figarch(
                data.iloc[:t] * 100, distribution, float(figarch_d)
            )
            fit = am.fix(trained.params)
            fit.convergence_flag = 0
        else:
            fit = am.fit(
                last_obs=t, disp="off", show_warning=False, options={"maxiter": 500}
            )
        if fit.convergence_flag != 0:
            raise ValueError(
                f"{model}/{distribution} optimizer failed at {data.index[t]}"
            )
        parameter_history.append(
            {
                "date": data.index[t - 1],
                "model": model,
                "distribution": distribution,
                **fit.params.to_dict(),
            }
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
    frame.attrs["parameter_history"] = parameter_history
    realized = frame["return"].pow(2)
    # QLIKE up to a target-only additive constant, well-defined at zero returns.
    loss = np.log(frame.variance) + realized / frame.variance
    return frame, loss


def evaluate_suite(
    returns,
    models=None,
    distributions=None,
    mcs_confidence=0.9,
    bootstrap_reps=200,
    **controls,
):
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
                latest = fit_model(
                    returns,
                    model,
                    distribution,
                    controls.get("aparch_delta"),
                    controls.get("figarch_d"),
                )
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
                        "aic": float(
                            latest.aic - 2 * getattr(latest, "fixed_parameter_count", 0)
                        ),
                        "bic": float(
                            latest.bic
                            - np.log(len(returns))
                            * getattr(latest, "fixed_parameter_count", 0)
                        ),
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
    mcs = set(
        model_confidence_set(losses, alpha=1 - mcs_confidence, reps=bootstrap_reps)
    )
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
    fit, horizons=(1, 5, 10, 21, 42, 63, 126, 252), simulations=1000, annualization=252
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
            "expected_ann_variance": float(draws[:, h - 1].mean() * annualization),
            "expected_ann_vol": float(np.sqrt(draws[:, h - 1].mean() * annualization)),
            **{
                f"p{int(q * 100):02}": float(
                    np.quantile(np.sqrt(draws[:, h - 1] * annualization), q)
                )
                for q in (0.05, 0.25, 0.5, 0.75, 0.95)
            },
            "n_sim": simulations,
        }
        for h in horizons
    ]


def news_impact_curve(fit, points=81, annualization=252):
    """One-step arch recursion with only the final observed innovation varied.

    FIGARCH retains its fitted full innovation history. The curve is conditional
    on that history, rather than falsely claiming a memory-free NIC.
    """
    process = fit.model.volatility
    residuals = np.asarray(fit.resid.dropna(), dtype=float)
    parameters = fit.params.reindex(process.parameter_names()).to_numpy(dtype=float)
    backcast = process.backcast(residuals)
    base = np.r_[residuals, 0.0]
    bounds = np.vstack([process.variance_bounds(residuals), [0, np.inf]])
    sigma = float(fit.conditional_volatility.dropna().iloc[-1])
    rows = []
    for standardized in np.unique(
        np.r_[np.linspace(-4, 4, points), residuals[-1] / sigma]
    ):
        innovations = base.copy()
        innovations[-2] = standardized * sigma
        variances = np.empty(len(innovations))
        process.compute_variance(parameters, innovations, variances, backcast, bounds)
        rows.append(
            {
                "standardized_shock": float(standardized),
                "innovation": float(innovations[-2] / 100),
                "next_period_variance": float(variances[-1] / 10000),
                "annualized_vol": float(np.sqrt(variances[-1] / 10000 * annualization)),
            }
        )
    return rows


def fit_fixed_figarch(data, distribution, fixed_d):
    """Constrained MLE, holding d fixed while re-estimating all nuisance parameters.

    arch supplies the likelihood, recursion, parameter bounds and linear
    constraints. scipy minimizes only free coordinates; this is not a changed
    parameter vector from an unconstrained fit presented as another MLE.
    """
    from scipy.optimize import minimize

    if not 0 < fixed_d < 1:
        raise ValueError("Fixed FIGARCH d must lie strictly between zero and one")
    am = build_model(data, "FIGARCH", distribution)
    initial = am.fit(disp="off", show_warning=False, options={"maxiter": 500})
    if initial.convergence_flag != 0:
        raise ValueError("Initial FIGARCH fit did not converge")
    names = list(initial.params.index)
    fixed_index = names.index("d")
    free = np.array([i for i in range(len(names)) if i != fixed_index])
    starting = initial.params.to_numpy().copy()
    starting[fixed_index] = fixed_d
    residuals = initial.resid.to_numpy()
    standardized = residuals / initial.conditional_volatility.to_numpy()
    components = [am, am.volatility, am.distribution]
    sizes = [am.num_params, am.volatility.num_params, am.distribution.num_params]
    bounds = [
        *am.bounds(),
        *am.volatility.bounds(residuals),
        *am.distribution.bounds(standardized),
    ]
    matrices, offsets = [], []
    offset = 0
    for component, size in zip(components, sizes):
        a, b = component.constraints()
        full = np.zeros((len(b), len(names)))
        full[:, offset : offset + size] = a
        matrices.append(full)
        offsets.append(b)
        offset += size
    a, b = np.vstack(matrices), np.concatenate(offsets)

    def unpack(values):
        params = starting.copy()
        params[free] = values
        return params

    def objective(values):
        likelihood = am.fix(unpack(values)).loglikelihood
        return -likelihood if np.isfinite(likelihood) else 1e100

    result = minimize(
        objective,
        starting[free],
        method="SLSQP",
        bounds=[bounds[i] for i in free],
        constraints={"type": "ineq", "fun": lambda values: a @ unpack(values) - b},
        options={"maxiter": 500, "ftol": 1e-8},
    )
    if (
        not result.success
        or not np.isfinite(result.fun)
        or np.min(a @ unpack(result.x) - b) < -1e-6
    ):
        raise ValueError(f"Fixed-d FIGARCH MLE failed: {result.message}")
    fitted = am.fix(unpack(result.x))
    fitted.convergence_flag = 0
    fitted.fixed_parameter_count = 1
    return fitted


def nyblom_stability(fit, simulations=2000, seed=29):
    """Joint score-process stability statistic with Brownian-bridge null simulation.

    Individual log likelihoods come from the fitted arch innovation distribution
    and arch's full variance recursion. This is a retrospective asymptotic test,
    not a rolling parameter-dispersion surrogate.
    """
    params = fit.params.to_numpy(dtype=float)
    names = list(fit.params.index)
    free = [
        i
        for i, name in enumerate(names)
        if not (name == "d" and getattr(fit, "fixed_parameter_count", 0))
    ]
    am = fit.model

    def individual(values):
        result = am.fix(values)
        residuals = result.resid.to_numpy(dtype=float)
        variance = result.conditional_volatility.to_numpy(dtype=float) ** 2
        shape = result.params.reindex(am.distribution.parameter_names()).to_numpy(
            dtype=float
        )
        return am.distribution.loglikelihood(
            shape, residuals, variance, individual=True
        )

    offset = am.num_params
    volatility_params = params[offset : offset + am.volatility.num_params]
    a, b = am.volatility.constraints()
    if len(b) and np.min(a @ volatility_params - b) <= 1e-5:
        return {
            "unavailable_reason": "Volatility parameter is on a constraint boundary; regular Nyblom null is inapplicable"
        }
    if am.distribution.num_params:
        distribution_params = params[-am.distribution.num_params :]
        a, b = am.distribution.constraints()
        if len(b) and np.min(a @ distribution_params - b) <= 1e-5:
            return {
                "unavailable_reason": "Innovation parameter is on a constraint boundary; regular Nyblom null is inapplicable"
            }
    base = individual(params)
    if not np.isfinite(base).all() or not np.isclose(
        base.sum(), fit.loglikelihood, rtol=1e-5
    ):
        return {
            "unavailable_reason": "Individual likelihood cannot reproduce the fitted likelihood"
        }
    columns = []
    for index in free:
        step = 1e-5 * max(abs(params[index]), 1e-2)
        upper, lower = params.copy(), params.copy()
        upper[index] += step
        lower[index] -= step
        score = (individual(upper) - individual(lower)) / (2 * step)
        if not np.isfinite(score).all():
            return {
                "unavailable_reason": "Parameter perturbation produces nonfinite scores"
            }
        columns.append(score)
    scores = np.column_stack(columns)
    scales = np.sqrt(np.mean(scores**2, axis=0))
    if (scales <= 0).any():
        return {"unavailable_reason": "Score information is unidentifiable"}
    scores /= scales
    information = scores.T @ scores / len(scores)
    if (
        np.linalg.matrix_rank(information) != len(free)
        or np.linalg.cond(information) > 1e10
    ):
        return {
            "unavailable_reason": "Joint score information is rank-deficient or ill-conditioned"
        }
    # Centering accounts for numerical optimization score residuals.
    cumulative = np.cumsum(scores - scores.mean(axis=0), axis=0)
    statistic = float(
        np.einsum("ti,ij,tj->", cumulative, np.linalg.inv(information), cumulative)
        / len(scores) ** 2
    )
    rng = np.random.default_rng(seed)
    null = np.zeros(simulations)
    # Independent standardized bridges after whitening the score covariance.
    for _ in free:
        increments = rng.normal(size=(simulations, 500)) / np.sqrt(500)
        brownian = np.cumsum(increments, axis=1)
        bridge = brownian - brownian[:, -1, None] * (np.arange(1, 501) / 500)
        null += np.mean(bridge**2, axis=1)
    return {
        "nyblom_joint_statistic": statistic,
        "p_value": float((1 + np.sum(null >= statistic)) / (simulations + 1)),
        "critical_value_95": float(np.quantile(null, 0.95)),
        "parameters": [names[i] for i in free],
        "observations": len(scores),
        "null_simulations": simulations,
        "seed": seed,
        "inference": "Asymptotic joint Brownian-bridge null; conditional on the selected fitted model. Regular interior parameters required; finite-sample and model-selection effects are not calibrated",
    }


def duration_backtest(path):
    """Weibull-versus-exponential exception-duration LR with right censoring."""
    from scipy.stats import CensoredData

    events = np.flatnonzero((path["return"] < path.var_cutoff).to_numpy())
    if len(events) < 6:
        return {
            "duration_unavailable_reason": "At least six exceptions required for duration estimation"
        }
    gaps = np.diff(events).astype(float)
    right = len(path) - 1 - events[-1]
    data = CensoredData(uncensored=gaps, right=[right] if right > 0 else [])
    shape, _, scale = stats.weibull_min.fit(data, floc=0)
    null_scale = (gaps.sum() + right) / len(gaps)
    null_ll = stats.expon.logpdf(gaps, scale=null_scale).sum() + stats.expon.logsf(
        right, scale=null_scale
    )
    alternative_ll = stats.weibull_min.logpdf(
        gaps, shape, scale=scale
    ).sum() + stats.weibull_min.logsf(right, shape, scale=scale)
    lr = max(0.0, float(2 * (alternative_ll - null_ll)))
    return {
        "duration_weibull_shape": float(shape),
        "duration_lr": lr,
        "duration_p_value": float(stats.chi2.sf(lr, 1)),
        "completed_durations": len(gaps),
        "right_censored_sessions": int(right),
        "duration_note": "Retrospective continuous-duration approximation for discrete trading sessions; excludes initial left-censored spell. Tests exponential duration shape with estimated intensity, separate from unconditional VaR coverage",
    }
