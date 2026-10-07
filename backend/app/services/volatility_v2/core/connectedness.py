"""Library-backed VARs with ordering-invariant generalized connectedness."""

from __future__ import annotations
from dataclasses import dataclass
import hashlib
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.api import VAR
from statsmodels.tsa.vector_ar.var_model import ma_rep
from .performance import build_var_design_matrix


@dataclass
class VolatilityVAR:
    coefs: np.ndarray
    covariance: np.ndarray
    intercept: np.ndarray
    lag: int
    bic: float | None
    stable: bool
    weighting: str

    def ma(self, horizon):
        return ma_rep(self.coefs, maxn=horizon)


def _stable(coefs):
    lag, n, _ = coefs.shape
    companion = np.zeros((lag * n, lag * n))
    companion[:n] = np.hstack(coefs)
    if lag > 1:
        companion[n:, :-n] = np.eye((lag - 1) * n)
    return bool(np.max(np.abs(np.linalg.eigvals(companion))) < 1)


def fit_volatility_var(panel, max_lag=5, weighting="ols", lag_order=1, delta=0.99):
    panel = panel.astype(float)
    if (
        panel.shape[1] < 2
        or panel.isna().any().any()
        or not np.isfinite(panel.to_numpy()).all()
    ):
        raise ValueError(
            "VAR requires at least two complete finite log-volatility series"
        )
    if (
        weighting not in ("ols", "ew")
        or not 1 <= max_lag <= 10
        or not 1 <= lag_order <= 10
        or not 0 < delta < 1
    ):
        raise ValueError("Invalid VAR controls")
    if len(panel) < max(30, 2 * (panel.shape[1] * max(max_lag, lag_order) + 1)):
        raise ValueError(
            "Insufficient observations for the requested VAR dimension/lag order"
        )
    if weighting == "ols":
        # statsmodels select_order compares candidates on the same observation range.
        # Restrict to p>=1; p=0 is not a volatility transmission model.
        model = VAR(panel.to_numpy())
        selection = model.select_order(maxlags=max_lag, trend="c")
        lag = min(range(1, max_lag + 1), key=lambda p: selection.ics["bic"][p])
        fit = model.fit(lag, trend="c")
        covariance = np.asarray(fit.sigma_u, dtype=float)
        result = VolatilityVAR(
            fit.coefs,
            covariance,
            np.asarray(fit.intercept),
            lag,
            float(selection.ics["bic"][lag]),
            bool(fit.is_stable()),
            weighting,
        )
    else:
        # Decay-weighted least squares at a declared fixed lag. Do not call an
        # ad hoc weighted likelihood criterion ordinary BIC.
        design, target = build_var_design_matrix(panel.to_numpy(), lag_order)
        weights = delta ** np.arange(len(target) - 1, -1, -1, dtype=float)
        fits = [
            sm.WLS(target[:, i], design, weights=weights).fit()
            for i in range(panel.shape[1])
        ]
        coefficients = np.column_stack([fit.params for fit in fits])
        residual = np.column_stack([fit.resid for fit in fits])
        effective_n = weights.sum() ** 2 / (weights @ weights)
        dof = effective_n - design.shape[1]
        if dof <= 1:
            raise ValueError(
                "EW-VAR has insufficient effective residual degrees of freedom"
            )
        covariance = (
            (residual * weights[:, None]).T
            @ residual
            / weights.sum()
            * effective_n
            / dof
        )
        n = panel.shape[1]
        coefs = np.array(
            [coefficients[1 + i * n : 1 + (i + 1) * n].T for i in range(lag_order)]
        )
        result = VolatilityVAR(
            coefs,
            covariance,
            coefficients[0],
            lag_order,
            None,
            _stable(coefs),
            weighting,
        )
    if np.linalg.eigvalsh(result.covariance).min() <= 0:
        raise ValueError("VAR residual covariance is not positive definite")
    return result


def generalized_decomposition(model, horizon=10):
    if not 1 <= horizon <= 252:
        raise ValueError("fevd_horizon must be between 1 and 252")
    # This is Pesaran-Shin generalized FEVD, not statsmodels' Cholesky FEVD.
    phi = model.ma(horizon - 1)
    sigma = model.covariance
    response = phi @ sigma
    numerator = np.sum(response**2, axis=0) / np.diag(sigma)[None, :]
    denominator = np.einsum("hij,hij->i", response, phi)
    raw = numerator / denominator[:, None]
    return raw / raw.sum(axis=1, keepdims=True)


def spillovers(theta, assets):
    diagonal = np.diag(theta)
    received = theta.sum(axis=1) - diagonal
    sent = theta.sum(axis=0) - diagonal
    return pd.DataFrame(
        {
            "asset": assets,
            "from_spillover": received * 100,
            "to_spillover": sent * 100,
            "net_spillover": (sent - received) * 100,
        }
    )


def frequency_connectedness(model, grid_size=2048):
    """Barunik-Krehlik spectrum; band shares normalize by full-spectrum mass.

    Direct transfer-function inversion avoids a short finite MA truncation.
    Midpoint integration covers all frequencies, with disjoint 2-5, 5-21,
    and >=21 observation-cycle bands. Their frequency contributions add up.
    """
    if not model.stable:
        raise ValueError("Frequency connectedness requires a stable VAR")
    sigma = model.covariance
    n = len(sigma)
    frequencies = (np.arange(grid_size) + 0.5) * np.pi / grid_size
    lags = np.arange(1, len(model.coefs) + 1)
    polynomial = np.eye(n)[None, :, :] - np.einsum(
        "fl,lij->fij", np.exp(-1j * np.outer(frequencies, lags)), model.coefs
    )
    transfer = np.linalg.inv(polynomial)
    response = transfer @ sigma
    numerator = np.abs(response) ** 2 / np.diag(sigma)[None, None, :]
    spectrum = np.einsum("fij,fij->fi", response, transfer.conj()).real
    total_variance = spectrum.sum(axis=0)
    full = numerator.sum(axis=0) / total_variance[:, None]
    row_mass = full.sum(axis=1)
    rows = []
    for name, low, high in (
        ("short_run", 2 * np.pi / 5, np.pi),
        ("medium_run", 2 * np.pi / 21, 2 * np.pi / 5),
        ("long_run", 0, 2 * np.pi / 21),
    ):
        mask = (frequencies >= low) & (frequencies < high)
        theta = (numerator[mask].sum(axis=0) / total_variance[:, None]) / row_mass[
            :, None
        ]
        mass = float(theta.sum())
        off = mass - float(np.trace(theta))
        rows.append(
            {
                "band": name,
                "frequency_connectedness": off / n * 100,
                "within_band_connectedness": off / mass * 100 if mass > 0 else None,
                "variance_mass_share": mass / n,
                "theta": theta.tolist(),
                "integration_grid": grid_size,
            }
        )
    return rows


def rolling_connectedness(
    panel,
    window=252,
    interval=1,
    fevd_horizon=10,
    include_network_history=False,
    **controls,
):
    if window < 60 or interval < 1 or len(panel) < window:
        raise ValueError(
            "Connectedness requires at least rolling_window complete aligned observations (minimum 60)"
        )
    rows, attribution, networks, failures = [], [], [], []
    latest = None
    # Include the final date even if it falls between an explicitly selected cadence.
    ends = list(range(window - 1, len(panel), interval))
    if ends[-1] != len(panel) - 1:
        ends.append(len(panel) - 1)
    for end in ends:
        date = panel.index[end]
        sample = panel.iloc[end - window + 1 : end + 1]
        try:
            model = fit_volatility_var(sample, **controls)
            theta = generalized_decomposition(model, fevd_horizon)
        except (ValueError, np.linalg.LinAlgError) as exc:
            failures.append({"date": date, "reason": str(exc)})
            rows.append(
                {
                    "date": date,
                    "connectedness": None,
                    "var_lag_order": None,
                    "var_stable": None,
                    "error": str(exc),
                }
            )
            continue
        value = float((theta.sum() - np.trace(theta)) / len(theta) * 100)
        rows.append(
            {
                "date": date,
                "connectedness": value,
                "var_lag_order": model.lag,
                "var_stable": model.stable,
            }
        )
        attribution.extend(
            {"date": date, **row}
            for row in spillovers(theta, list(panel.columns)).to_dict("records")
        )
        if include_network_history:
            networks.append(
                {"date": date, "assets": list(panel.columns), "theta": theta.tolist()}
            )
        latest = (date, model, theta)
    if latest is None or latest[0] != panel.index[-1]:
        raise ValueError(
            "Final connectedness model could not be estimated; "
            + (failures[-1]["reason"] if failures else "No models")
        )
    timeline = pd.DataFrame(rows).set_index("date")
    # Compare each reading only with its earlier observed history, up to 2520 rows.
    values = timeline.connectedness.astype(float)
    percentile = []
    for i, value in enumerate(values):
        past = values.iloc[max(0, i - 2520) : i].dropna()
        percentile.append(
            float(past.lt(value).mean() * 100)
            if len(past) and np.isfinite(value)
            else np.nan
        )
    timeline["percentile"] = percentile
    timeline["percentile_history_observations"] = [
        int(values.iloc[max(0, i - 2520) : i].notna().sum()) for i in range(len(values))
    ]
    return {
        "timeline": timeline,
        "attribution": attribution,
        "network_history": networks,
        "failures": failures,
        "latest": latest,
    }


def connectedness_alerts(timeline, theta, assets, threshold=75):
    if not 0 <= threshold <= 100:
        raise ValueError("alert_threshold must be a percentile between 0 and 100")
    high = timeline.percentile.ge(threshold)
    crossings = high & ~high.shift(1, fill_value=False)
    drivers = sorted(
        [
            {"source": assets[j], "target": assets[i], "weight": float(theta[i, j])}
            for i in range(len(assets))
            for j in range(len(assets))
            if i != j
        ],
        key=lambda row: row["weight"],
        reverse=True,
    )[:5]
    rows = []
    for date in timeline.index[crossings]:
        rows.append(
            {
                "id": hashlib.sha256(
                    f"connectedness:{date.isoformat()}:{threshold}".encode()
                ).hexdigest()[:24],
                "date": date,
                "level": "warning",
                "message": f"Connectedness crossed the historical {threshold:g}th percentile",
                "percentile": float(timeline.loc[date, "percentile"]),
                "drivers": drivers if date == timeline.index[-1] else None,
            }
        )
    return rows


def autoregressive_cor(timeline, horizon=21, quantile=0.95):
    """Honest quantile AR CoR alternative when macro release vintages are absent."""
    if not 1 <= horizon <= 252 or not 0 < quantile < 1:
        raise ValueError("Invalid CoR horizon or quantile")
    values = timeline.connectedness.astype(float)
    features = pd.DataFrame(
        {
            "connectedness": values,
            "weekly_mean": values.rolling(5).mean(),
            "monthly_mean": values.rolling(21).mean(),
        }
    )
    target = values.shift(-horizon)
    frame = pd.concat([target.rename("target"), features], axis=1).dropna()
    if len(frame) < 100:
        return {
            "unavailable_reason": "Autoregressive CoR requires 100 matured forward connectedness targets",
            "model": "quantile_AR",
        }
    design = sm.add_constant(frame[features.columns], has_constant="add")
    fit = sm.QuantReg(frame.target, design).fit(q=quantile, max_iter=2000)
    latest = features.iloc[-1]
    if latest.isna().any():
        return {
            "unavailable_reason": "Final autoregressive CoR predictors are incomplete",
            "model": "quantile_AR",
        }
    prediction = float(np.r_[1.0, latest.to_numpy()] @ fit.params.to_numpy())
    return {
        "model": "quantile_AR",
        "quantile": quantile,
        "horizon": horizon,
        "conditional_connectedness_quantile": prediction,
        "current_connectedness": float(values.iloc[-1]),
        "observations": len(frame),
        "converged": int(fit.iterations) < 2000,
        "coefficients": fit.params.to_dict(),
        "standard_errors": fit.bse.to_dict(),
        "inference": "statsmodels heteroskedasticity-robust quantile regression SE; no overlapping-horizon HAC claim",
        "macro_limitation": "Macro-conditioned CoR disabled without release vintages; this explicitly labeled alternative uses observed connectedness only",
    }


def bootstrap_irf(
    panel,
    model,
    horizons=(1, 5, 10, 21),
    reps=100,
    confidence=0.90,
    seed=41,
    **controls,
):
    """Stationary-block residual-vector bootstrap; each draw refits the declared VAR."""
    from arch.bootstrap import StationaryBootstrap

    if not 20 <= reps <= 500 or not 0.5 < confidence < 1:
        raise ValueError("Invalid IRF bootstrap repetitions or confidence")
    values = panel.to_numpy(dtype=float)
    lag = model.lag
    predictions = []
    for t in range(lag, len(values)):
        predictions.append(
            model.intercept
            + sum(model.coefs[k] @ values[t - k - 1] for k in range(lag))
        )
    residuals = values[lag:] - np.asarray(predictions)
    residuals -= residuals.mean(axis=0)
    block = max(2, int(len(residuals) ** (1 / 3)))
    bootstrap = StationaryBootstrap(block, residuals, seed=seed)
    draws, failures = [], []
    for replication, (sample, _) in enumerate(bootstrap.bootstrap(reps)):
        errors = sample[0]
        synthetic = np.zeros_like(values)
        synthetic[:lag] = values[:lag]
        for t in range(lag, len(values)):
            synthetic[t] = (
                model.intercept
                + sum(model.coefs[k] @ synthetic[t - k - 1] for k in range(lag))
                + errors[t - lag]
            )
        try:
            refit = fit_volatility_var(
                pd.DataFrame(synthetic, index=panel.index, columns=panel.columns),
                **controls,
            )
            draws.append(refit.ma(max(horizons)))
        except (ValueError, np.linalg.LinAlgError) as exc:
            failures.append({"replication": replication, "reason": str(exc)})
    if len(draws) < max(20, int(0.8 * reps)):
        return [], {
            "unavailable_reason": "Fewer than 80% of requested VAR bootstrap fits succeeded",
            "successful_replications": len(draws),
            "failed_replications": failures,
        }
    arr = np.asarray(draws)
    point = model.ma(max(horizons))
    alpha = (1 - confidence) / 2
    lower, upper = np.quantile(arr, [alpha, 1 - alpha], axis=0)
    rows = [
        {
            "horizon": h,
            "source": str(panel.columns[j]),
            "target": str(panel.columns[i]),
            "response": float(point[h, i, j]),
            "lower": float(lower[h, i, j]),
            "upper": float(upper[h, i, j]),
            "confidence": confidence,
            "successful_replications": len(draws),
        }
        for h in horizons
        for i in range(panel.shape[1])
        for j in range(panel.shape[1])
    ]
    return rows, {
        "successful_replications": len(draws),
        "failed_replications": failures,
        "bootstrap": "Stationary-block residual vectors, preserving contemporaneous asset dependence; conditional on a stationary fitted VAR",
    }
