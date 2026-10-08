"""Daily estimator diagnostics with explicit horizons and observed alignment."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from .analytics import ESTIMATORS, ESTIMATOR_LABELS, clean_json


def dm_tournament(vol, annualization=252, horizon=5):
    """Constant-variance h-session forecast vs observed future squared returns.

    Forecasts are formed at the close; their targets contain only the next h
    observations. This is a retrospective predictive comparison, not model
    selection for a trading strategy. Zero realized variance remains valid.
    """
    if annualization <= 0 or horizon < 1:
        raise ValueError("Positive annualization and horizon are required")
    rows = []
    for asset, group in vol.groupby("asset", sort=False):
        group = group.sort_values("date")
        realized = sum(group["return"].shift(-lag).pow(2) for lag in range(1, horizon + 1))
        forecast = group[ESTIMATORS].pow(2) * horizon / annualization
        loss = realized.to_numpy()[:, None] / forecast + np.log(forecast)
        loss = loss.where(forecast > 0).replace([np.inf, -np.inf], np.nan)
        for a in ESTIMATORS:
            for b in ESTIMATORS:
                difference = (loss[a] - loss[b]).dropna()
                value = p_value = None
                reason = None
                if a == b:
                    value, p_value = 0.0, 1.0
                elif len(difference) < 30:
                    reason = "At least 30 complete forecast/target pairs are required"
                else:
                    fit = sm.OLS(difference.to_numpy(), np.ones((len(difference), 1))).fit(
                        cov_type="HAC", cov_kwds={"maxlags": max(horizon - 1, int(len(difference) ** (1 / 3)))},
                    )
                    if np.isfinite(fit.bse[0]) and fit.bse[0] > 0:
                        value = float(-fit.params[0] / fit.bse[0])
                        p_value = float(2 * norm.sf(abs(value)))
                    else:
                        reason = "Loss-difference sampling variance is unidentifiable"
                rows.append({"asset": asset, "row": ESTIMATOR_LABELS[a], "col": ESTIMATOR_LABELS[b],
                             "value": value, "p_value": p_value, "observations": len(difference),
                             "horizon_sessions": horizon, "annualization": annualization,
                             "bonferroni_significant": p_value < .05 / 10 if p_value is not None and a != b else False,
                             "unavailable_reason": reason})
    return clean_json(rows)


def range_correlation_matrix(ohlcv, window=252, method="pearson"):
    """Pearson log-range correlation or explicitly selected uncentered cosine."""
    if method not in {"pearson", "uncentered_cosine"} or window < 30:
        raise ValueError("Range method must be pearson or uncentered_cosine; window >= 30")
    panel = ohlcv.assign(log_range=np.log(ohlcv.High / ohlcv.Low)).pivot(
        index="Date", columns="Ticker", values="log_range"
    ).sort_index().tail(window)
    if method == "pearson":
        return panel.corr(min_periods=30)
    result = pd.DataFrame(np.nan, index=panel.columns, columns=panel.columns)
    for a in panel:
        for b in panel:
            pair = panel[[a, b]].dropna().to_numpy()
            if len(pair) >= 30:
                denominator = np.linalg.norm(pair[:, 0]) * np.linalg.norm(pair[:, 1])
                if denominator > 0:
                    result.loc[a, b] = pair[:, 0] @ pair[:, 1] / denominator
    return result


def estimator_efficiency_table(vol):
    """Observed temporal variance ratios, not sampling efficiency estimates.

    Volatility changes through time, so dispersion of rolling estimates cannot
    identify estimator sampling efficiency or diagnose fat tails.
    """
    rows = []
    for asset, group in vol.groupby("asset", sort=False):
        group = group.sort_values("date")
        for estimator in ESTIMATORS:
            aligned = group[["cc", estimator]].dropna() if estimator != "cc" else group[["cc"]].dropna()
            denominator = aligned[estimator].pow(2).var()
            values = group[estimator].dropna()
            latest = values.iloc[-1] if len(values) else None
            row = {"asset": asset, "key": estimator, "estimator": ESTIMATOR_LABELS[estimator],
                   "current_ann_vol": latest, "temporal_variance_ratio_vs_cc":
                   aligned.cc.pow(2).var() / denominator if denominator > 0 else None,
                   "sampling_efficiency": None,
                   "unavailable_reason": "Time-series dispersion does not identify sampling efficiency or fat tails"}
            for label, count in [("252d", 252), ("5y", 1260), ("full", len(values))]:
                history = values.tail(count)
                row[f"percentile_{label}"] = float(history.le(latest).mean() * 100) if len(history) else None
            rows.append(row)
    return clean_json(rows)
