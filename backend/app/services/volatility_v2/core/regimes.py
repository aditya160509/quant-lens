"""Causal HMM filtering and hard statistical jump states from observed prices.

HMM parameters and standardization are estimated before each prediction block.
The output never backfills warmup states or smooths with future observations.
"""

from __future__ import annotations
from collections import OrderedDict
from copy import deepcopy
import hashlib
import math
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy import stats
from scipy.special import logsumexp
from sklearn.cluster import KMeans
from .analytics import volatility_estimators
from .performance import sjm_viterbi

_CACHE = OrderedDict()


def state_names(states):
    return {
        2: ["low_vol", "high_vol"],
        3: ["low_vol", "transition", "high_vol"],
        4: ["low_vol", "transition", "high_vol", "crisis"],
    }[states]


def regime_features(ohlcv, asset):
    vol = volatility_estimators(ohlcv, window=21)
    g = vol.loc[vol.asset.eq(asset)].sort_values("date").set_index("date")
    if g.empty:
        raise ValueError(f"Insufficient volatility history for {asset}")
    return pd.DataFrame(
        {
            "log_vol": np.log(g.yang_zhang.where(g.yang_zhang > 0)),
            "vol_trend": g.yang_zhang.rolling(5).mean()
            / g.yang_zhang.rolling(63).mean(),
            "return_21d": g["return"].rolling(21).sum(),
        },
        index=g.index,
    ).replace([np.inf, -np.inf], np.nan)


def _emissions(model, values):
    cov = model.covars_
    variance = np.diagonal(cov, axis1=1, axis2=2) if cov.ndim == 3 else cov
    return stats.norm.logpdf(
        values[:, None, :],
        loc=model.means_[None, :, :],
        scale=np.sqrt(variance)[None, :, :],
    ).sum(axis=2)


def _filter(model, values, initial=None):
    emission = _emissions(model, values)
    log_transition = np.log(np.maximum(model.transmat_, np.finfo(float).tiny))
    output = np.empty((len(values), model.n_components))
    log_previous = np.log(
        np.maximum(
            initial if initial is not None else model.startprob_, np.finfo(float).tiny
        )
    )
    for t in range(len(values)):
        prior = (
            logsumexp(log_previous[:, None] + log_transition, axis=0)
            if t or initial is not None
            else log_previous
        )
        posterior = prior + emission[t]
        log_previous = posterior - logsumexp(posterior)
        output[t] = np.exp(log_previous)
    return output


def _fit_hmm(values, states, restarts, date):
    candidates, diagnostics = [], []
    for restart in range(restarts):
        model = GaussianHMM(
            n_components=states,
            covariance_type="diag",
            n_iter=250,
            tol=1e-4,
            min_covar=1e-5,
            random_state=31 + states * 17 + restart * 37,
        )
        try:
            model.fit(values)
            ll = float(model.score(values))
            if not np.isfinite(ll):
                raise ValueError("Nonfinite HMM likelihood")
            history = list(model.monitor_.history)
            converged = bool(
                len(history) > 1 and abs(history[-1] - history[-2]) < model.tol
            )
            parameters = (
                (states - 1) + states * (states - 1) + 2 * states * values.shape[1]
            )
            bic = -2 * ll + parameters * math.log(len(values))
            diagnostics.append(
                {
                    "date": date,
                    "states": states,
                    "restart": restart + 1,
                    "log_likelihood": ll,
                    "bic": bic,
                    "converged": converged,
                    "iterations": int(model.monitor_.iter),
                }
            )
            candidates.append((ll, model, bic, converged))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
            diagnostics.append(
                {
                    "date": date,
                    "states": states,
                    "restart": restart + 1,
                    "converged": False,
                    "error": str(exc),
                }
            )
    if not candidates:
        raise ValueError(f"HMM failed for all {restarts} restarts at {date}")
    return max(candidates, key=lambda item: item[0]), diagnostics


def _jump_centers(values, states, penalty):
    centers = (
        KMeans(n_clusters=states, n_init=5, random_state=23)
        .fit(values)
        .cluster_centers_
    )
    previous = None
    converged = False
    for iteration in range(100):
        distances = ((values[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        path = sjm_viterbi(distances, float(penalty))
        objective = float(
            distances[np.arange(len(values)), path].sum()
            + penalty * np.sum(path[1:] != path[:-1])
        )
        if previous is not None and abs(previous - objective) <= 1e-6:
            converged = True
            break
        previous = objective
        for k in range(states):
            if (path == k).any():
                centers[k] = values[path == k].mean(axis=0)
    return centers, {
        "objective": objective,
        "iterations": iteration + 1,
        "converged": converged,
    }


def _jump_filter(values, centers, penalty, cost=None):
    states = len(centers)
    transition = penalty * (1 - np.eye(states))
    result = []
    for value in values:
        distance = ((centers - value) ** 2).sum(axis=1)
        cost = (
            distance
            if cost is None
            else distance + (cost[:, None] + transition).min(axis=0)
        )
        cost -= cost.min()
        result.append(int(cost.argmin()))
    return np.asarray(result), cost


def filtered_regimes(
    features,
    states=4,
    min_train=252,
    refit_interval=126,
    restarts=3,
    select_k=False,
    jump_penalty=15.0,
    training_window=None,
):
    if (
        states not in (2, 3, 4)
        or min_train < 120
        or refit_interval < 1
        or not 1 <= restarts <= 20
        or jump_penalty < 0
    ):
        raise ValueError("Invalid regime controls")
    if training_window is not None and training_window < min_train:
        raise ValueError("training_window must be at least min_train")
    features = features.replace([np.inf, -np.inf], np.nan).dropna()
    if len(features) <= min_train:
        raise ValueError(
            f"Regime filtering requires more than {min_train} complete training observations"
        )
    key = hashlib.sha256(
        pd.util.hash_pandas_object(features, index=True).values.tobytes()
        + repr(
            (
                states,
                min_train,
                refit_interval,
                restarts,
                select_k,
                jump_penalty,
                training_window,
            )
        ).encode()
    ).hexdigest()
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return deepcopy(_CACHE[key])
    blocks, diagnostics, jump_rows = [], [], []
    selected = states
    for t in range(min_train, len(features), refit_interval):
        train = features.iloc[max(0, t - training_window) if training_window else 0 : t]
        center, scale = train.mean(), train.std(ddof=0)
        if (scale <= 1e-12).any():
            raise ValueError("Regime predictors have zero training variance")
        values = ((train - center) / scale).to_numpy(dtype=float)
        candidates = range(2, 5) if select_k and t == min_train else [selected]
        fits = []
        for k in candidates:
            fitted, rows = _fit_hmm(values, k, restarts, train.index[-1])
            fits.append((k, fitted))
            diagnostics.extend(rows)
        selected, fitted = min(fits, key=lambda item: item[1][2])
        _, model, _, converged = fitted
        posterior = _filter(model, values)[-1]
        future = features.iloc[t : min(t + refit_interval, len(features))]
        future_values = ((future - center) / scale).to_numpy(dtype=float)
        probabilities = _filter(model, future_values, posterior)
        order = np.argsort(model.means_[:, 0])
        block = pd.DataFrame(
            probabilities[:, order], index=future.index, columns=state_names(selected)
        )
        block["training_observed_through"] = train.index[-1]
        block["hmm_converged"] = converged
        blocks.append(block)
        centers, jump_info = _jump_centers(values, selected, jump_penalty)
        _, cost = _jump_filter(values, centers, jump_penalty)
        path, _ = _jump_filter(future_values, centers, jump_penalty, cost)
        jump_order = np.argsort(centers[:, 0])
        inverse = np.argsort(jump_order)
        jump_rows.extend(
            {
                "date": date,
                "state": state_names(selected)[inverse[int(state)]],
                "training_observed_through": train.index[-1],
                **jump_info,
            }
            for date, state in zip(future.index, path)
        )
    probabilities = pd.concat(blocks)
    result = {
        "probabilities": probabilities,
        "hmm_diagnostics": diagnostics,
        "jump_states": jump_rows,
        "selected_states": selected,
        "source_fingerprint": key,
    }
    _CACHE[key] = deepcopy(result)
    while len(_CACHE) > 8:
        _CACHE.popitem(last=False)
    return result


def duration_survival(sequence, names):
    """Weibull MLE includes the ongoing spell as right-censored.

    The first observed spell is excluded because its entry predates observation.
    No survival curve is emitted without enough completed spells.
    """
    sequence = np.asarray(sequence, dtype=int)
    if len(sequence) == 0:
        return []
    runs = []
    start = 0
    for i in range(1, len(sequence) + 1):
        if i == len(sequence) or sequence[i] != sequence[start]:
            runs.append(
                (int(sequence[start]), i - start, start == 0, i == len(sequence))
            )
            start = i
    rows = []
    for state, name in enumerate(names):
        complete = [
            float(length)
            for k, length, left, right in runs
            if k == state and not left and not right
        ]
        current = next(
            (
                length
                for k, length, left, right in runs
                if k == state and right and not left
            ),
            None,
        )
        row = {
            "regime": name,
            "completed_spells": len(complete),
            "current_duration_days": current,
            "right_censored_spells": int(current is not None),
            "left_censored_first_spell_excluded": bool(runs[0][0] == state),
            "shape": None,
            "scale": None,
            "mean_duration_days": float(np.mean(complete)) if complete else None,
            "survival_curve": [],
        }
        if len(complete) >= 3:
            censored = stats.CensoredData(
                uncensored=complete, right=[current] if current is not None else []
            )
            shape, _, scale = stats.weibull_min.fit(censored, floc=0)
            row.update(
                shape=float(shape),
                scale=float(scale),
                mean_duration_days=float(stats.weibull_min.mean(shape, scale=scale)),
            )
            if current is not None:
                row["survival_curve"] = [
                    {
                        "extra_days": extra,
                        "survival_prob": float(
                            np.exp(
                                -(
                                    ((current + extra) / scale) ** shape
                                    - (current / scale) ** shape
                                )
                            )
                        ),
                    }
                    for extra in (1, 5, 10, 21, 42, 63, 126)
                ]
        else:
            row["unavailable_reason"] = (
                "Weibull survival requires at least three completed non-left-censored spells"
            )
        rows.append(row)
    return rows


def transition_matrices(probabilities):
    rows = []
    arr = probabilities.to_numpy(dtype=float)
    for horizon, label in ((5, "1w"), (21, "1m"), (63, "3m")):
        before, after = arr[:-horizon], arr[horizon:]
        mass = before.sum(axis=0)
        matrix = (
            before.T @ after
            if len(before)
            else np.zeros((len(probabilities.columns),) * 2)
        )
        matrix = np.divide(
            matrix,
            mass[:, None],
            out=np.full_like(matrix, np.nan),
            where=mass[:, None] > 0,
        )
        rows.extend(
            {"horizon": label, "row": a, "col": b, "value": float(matrix[i, j])}
            for i, a in enumerate(probabilities.columns)
            for j, b in enumerate(probabilities.columns)
        )
    return rows


def transition_alerts(probabilities, asset, threshold=0.30, horizon=5):
    changes = probabilities.diff(horizon).abs().max(axis=1)
    triggered = changes >= threshold
    crossings = triggered & ~triggered.shift(1, fill_value=False)
    rows = []
    for date in probabilities.index[crossings]:
        position = probabilities.index.get_loc(date)
        rows.append(
            {
                "id": hashlib.sha256(
                    f"{asset}:{date.isoformat()}:{threshold}:{horizon}".encode()
                ).hexdigest()[:24],
                "date": date,
                "asset": asset,
                "level": "warning",
                "message": f"Regime probability moved at least {threshold:.0%} over {horizon} observations",
                "max_probability_change": float(changes.loc[date]),
                "previous_probabilities": probabilities.iloc[
                    position - horizon
                ].to_dict(),
                "current_probabilities": probabilities.loc[date].to_dict(),
            }
        )
    return rows
