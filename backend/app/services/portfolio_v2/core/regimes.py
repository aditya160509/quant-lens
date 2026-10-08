"""Prefix-fitted regime models and filtered probabilities without fallback classifiers."""

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import norm
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from .construction import solve_portfolio, OptimizationError


def causal_regimes(
    portfolio,
    macro=None,
    count=3,
    min_train=126,
    refit_interval=21,
    model="hmm",
    transition_structure="homogeneous",
):
    features = pd.DataFrame(
        {
            "vol": portfolio.rolling(21).std(),
            "momentum": (1 + portfolio).rolling(63).apply(np.prod, raw=True) - 1,
        }
    ).dropna()
    if model == "vix":
        if count != 4:
            raise ValueError("VIX classifier defines exactly four threshold states")
        if macro is None or "vixcls" not in macro:
            raise ValueError("Observed VIX data required")
        levels = macro.set_index("date").vixcls.reindex(features.index)
        rows = []
        for date, value in levels.dropna().items():
            state = int(np.searchsorted([15, 25, 35], value))
            rows.append(
                {
                    "date": date,
                    "regime": state,
                    "vol": features.loc[date, "vol"],
                    **{f"probability_{k}": float(k == state) for k in range(4)},
                }
            )
        return pd.DataFrame(rows), None
    if len(features) <= min_train:
        raise ValueError("Insufficient regime training and held-out observations")
    if model == "hamilton" and transition_structure != "homogeneous":
        raise ValueError("Hamilton nonhomogeneous transitions unavailable; use HMM")
    rows = []
    fit = None
    last_fit = -refit_interval
    transition_fit = {}
    for t in range(min_train, len(features)):
        train = features.iloc[:t]
        if fit is None or t - last_fit >= refit_interval:
            if model == "hamilton":
                from statsmodels.tsa.regime_switching.markov_regression import (
                    MarkovRegression,
                )

                fit = MarkovRegression(
                    portfolio.reindex(train.index) * 100,
                    k_regimes=count,
                    trend="c",
                    switching_variance=True,
                ).fit(disp=False, maxiter=300)
                if not fit.mle_retvals.get("converged", False):
                    raise ValueError("Hamilton regime MLE did not converge")
            else:
                scale = StandardScaler().fit(train)
                X = scale.transform(train)
                candidates = []
                for seed in [7, 17, 27]:
                    candidate = GaussianHMM(
                        count,
                        covariance_type="diag",
                        n_iter=300,
                        tol=0.01,
                        min_covar=1e-5,
                        random_state=seed,
                    ).fit(X)
                    if candidate.monitor_.converged and np.isfinite(candidate.score(X)):
                        candidates.append(candidate)
                if not candidates:
                    raise ValueError(
                        "No converged HMM fit; no surrogate classifier used"
                    )
                fit = max(candidates, key=lambda f: f.score(X))
                order = np.argsort(fit.means_[:, 0])
                transition = fit.transmat_[np.ix_(order, order)]
                means = fit.means_[order]
                variance = fit._covars_[order]
                # Training posterior initializes filtering; all training data precede held-out t.
                probability = fit.predict_proba(X)[-1, order]
                transition_fit = {}
                if transition_structure == "nonhomogeneous":
                    states = np.array(
                        [int(np.where(order == i)[0][0]) for i in fit.predict(X)]
                    )
                    for k in range(count):
                        ids = np.flatnonzero(states[:-1] == k)
                        labels = states[1:][ids]
                        if len(ids) < 10 or len(np.unique(labels)) < 2:
                            raise ValueError(
                                f"Nonhomogeneous transitions not identified for state {k}; no homogeneous-row fallback"
                            )
                        classifier = LogisticRegression(max_iter=1000).fit(
                            X[:-1][ids], labels
                        )
                        transition_fit[k] = classifier
            last_fit = t
        if model == "hamilton":
            from statsmodels.tsa.regime_switching.markov_regression import (
                MarkovRegression,
            )

            filtered = MarkovRegression(
                portfolio.reindex(features.index[: t + 1]) * 100,
                k_regimes=count,
                trend="c",
                switching_variance=True,
            ).filter(fit.params)
            probability = np.asarray(filtered.filtered_marginal_probabilities)[-1]
            transition = np.asarray(filtered.regime_transition)[:, :, 0].T
        else:
            if transition_structure == "nonhomogeneous":
                driver = scale.transform(features.iloc[[t - 1]])
                for k, classifier in transition_fit.items():
                    transition[k] = 0
                    transition[k, classifier.classes_] = classifier.predict_proba(
                        driver
                    )[0]
            value = scale.transform(features.iloc[[t]])[0]
            log_emission = norm.logpdf(value, means, np.sqrt(variance)).sum(axis=1)
            log_probability = (
                np.log(np.maximum(probability @ transition, 1e-300)) + log_emission
            )
            probability = np.exp(log_probability - logsumexp(log_probability))
        rows.append(
            {
                "date": features.index[t],
                "regime": int(np.argmax(probability)),
                "vol": float(features.vol.iloc[t]),
                "training_end": train.index[-1]
                if last_fit == t
                else features.index[last_fit - 1],
                **{f"probability_{k}": float(probability[k]) for k in range(count)},
            }
        )
    return pd.DataFrame(rows), transition


def regime_allocations(returns, records, objective="global_min_variance"):
    dated = records.set_index("date")
    latest = dated.iloc[-1]
    cut = dated.index[-1]
    rows = []
    combined = pd.Series(0.0, index=returns.columns)
    issues = []
    for k in [int(c.rsplit("_", 1)[1]) for c in dated if c.startswith("probability_")]:
        origins = dated.index[(dated.regime == k) & (dated.index < cut)]
        sample = returns.reindex(origins).dropna()
        mass = float(latest[f"probability_{k}"])
        if len(sample) < 30:
            issues.append(
                f"Regime {k} has fewer than 30 prior observed classifications; mixture unavailable"
            )
            continue
        try:
            w, detail = solve_portfolio(sample, {}, objective)
        except OptimizationError as exc:
            issues.append(str(exc))
            continue
        combined += mass * w
        rows.extend(
            {
                "regime": k,
                "ticker": c,
                "weight": float(v),
                "probability": mass,
                "training_end": sample.index[-1],
                "success": detail["success"],
            }
            for c, v in w.items()
        )
    return (
        rows,
        []
        if issues
        else [{"ticker": c, "weight": float(v)} for c, v in combined.items()],
        issues,
    )


def kaplan_meier_survival(regimes):
    values = regimes.dropna().to_numpy()
    rows = []
    if not len(values):
        return []
    starts = np.r_[0, np.flatnonzero(values[1:] != values[:-1]) + 1]
    ends = np.r_[starts[1:], len(values)]
    # First episode is left-censored and omitted; last is right-censored.
    for state in np.unique(values):
        episodes = [
            (end - start, end < len(values))
            for start, end in zip(starts, ends)
            if start > 0 and values[start] == state
        ]
        if not episodes:
            continue
        durations = np.array([d for d, _ in episodes])
        events = np.array([e for _, e in episodes])
        survival = 1.0
        for duration in np.unique(durations):
            risk = int((durations >= duration).sum())
            exits = int(((durations == duration) & events).sum())
            survival *= 1 - exits / risk
            rows.append(
                {
                    "regime": int(state),
                    "duration": int(duration),
                    "survival": float(survival),
                    "at_risk": risk,
                    "events": exits,
                    "censored": int(((durations == duration) & ~events).sum()),
                }
            )
    return rows


def regime_conditional_cov(returns, regimes):
    return {
        str(int(k)): returns.loc[regimes.reindex(returns.index).eq(k)].cov().to_dict()
        for k in regimes.dropna().unique()
    }


def regime_factor_performance(returns, regimes):
    rows = []
    for k in regimes.dropna().unique():
        r = returns.loc[regimes.reindex(returns.index).eq(k)]
        rows.extend(
            {
                "regime": int(k),
                "asset": c,
                "mean": float(r[c].mean()),
                "period_sharpe": float(r[c].mean() / r[c].std())
                if r[c].std() > 0
                else None,
            }
            for c in r
        )
    return rows
