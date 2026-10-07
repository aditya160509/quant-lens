"""Exact-date macro change analogs and a continuous ellipsoidal stress search."""

from __future__ import annotations

import json
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.covariance import GraphicalLasso
from sklearn.exceptions import ConvergenceWarning
from sklearn.preprocessing import StandardScaler
from .analytics import macro_frame
from .data_loader import ohlcv_for_symbols

COLUMNS = (
    "vix_change",
    "yield_10y_change",
    "credit_change",
    "dxy_return",
    "equity_return",
)


def macro_changes(index, horizon=30):
    """Five real inputs; dollar index is DX-Y.NYB, not a currency basket proxy."""
    if not 5 <= horizon <= 126:
        raise ValueError("analog_horizon must be between 5 and 126 aligned sessions")
    macro = macro_frame().set_index("date").reindex(index)
    prices = ohlcv_for_symbols(["DX_Y_NYB", "^GSPC"], lookback_days=10000)
    closes = prices.pivot(index="Date", columns="Ticker", values="Close").reindex(index)
    frame = pd.DataFrame(
        {
            "vix_change": macro.vix.diff(horizon),
            "yield_10y_change": macro.dgs10.diff(horizon),
            "credit_change": macro.credit.diff(horizon),
            "dxy_return": closes.DX_Y_NYB / closes.DX_Y_NYB.shift(horizon) - 1,
            "equity_return": closes["^GSPC"] / closes["^GSPC"].shift(horizon) - 1,
        },
        index=index,
    )
    return frame.replace([np.inf, -np.inf], np.nan)


def selected_precision(standardized):
    """Library GLASSO on standardized inputs, selected by explicit Gaussian BIC."""
    data = np.asarray(standardized, dtype=float)
    if len(data) < 100 or not np.isfinite(data).all():
        raise ValueError("Macro analogs require 100 complete historical change vectors")
    fits, diagnostics = [], []
    for alpha in np.geomspace(0.001, 0.5, 24):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                model = GraphicalLasso(alpha=float(alpha), max_iter=500, tol=1e-5).fit(
                    data
                )
            edges = np.count_nonzero(np.triu(np.abs(model.precision_) > 1e-8, 1))
            degrees = data.shape[1] + int(edges)
            bic = float(
                -2 * len(data) * model.score(data) + np.log(len(data)) * degrees
            )
            diagnostics.append(
                {"alpha": float(alpha), "bic": bic, "precision_parameters": degrees}
            )
            fits.append((bic, model))
        except (ValueError, FloatingPointError, ConvergenceWarning) as exc:
            diagnostics.append({"alpha": float(alpha), "error": str(exc)})
    if not fits:
        raise ValueError("All graphical LASSO precision candidates failed")
    _, selected = min(fits, key=lambda item: item[0])
    return selected, diagnostics


def analyze(returns, weights, payload, changes=None):
    horizon = int(payload.get("analog_horizon", 30))
    if not 5 <= horizon <= 126:
        raise ValueError("analog_horizon must be between 5 and 126 aligned sessions")
    k = int(payload.get("analog_k", 10))
    radius = float(payload.get("adversarial_c", 2))
    if not 1 <= k <= 50 or not 0 < radius <= 10:
        raise ValueError("Invalid analog count or adversarial radius")
    changes = macro_changes(returns.index, horizon) if changes is None else changes
    changes = changes.reindex(returns.index).reindex(columns=COLUMNS)
    raw = payload.get("macro_scenario")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if raw is None:
        complete = changes.dropna()
        if complete.empty:
            raise ValueError("No complete exact-date macro query vector")
        query = complete.iloc[-1]
        query_end = complete.index[-1]
        query_position = returns.index.get_loc(query_end)
        query_start = returns.index[query_position - horizon]
        # Exclude the current reference episode and all overlapping windows.
        candidates = changes.loc[:query_start].dropna()
    else:
        if not isinstance(raw, dict) or set(raw) != set(COLUMNS):
            raise ValueError(
                "macro_scenario must declare all five exact macro change inputs"
            )
        query = pd.Series(raw).reindex(COLUMNS).astype(float)
        candidates = changes.dropna()
        query_end, query_start = None, None
    if not np.isfinite(query.to_numpy()).all():
        raise ValueError("Macro scenario inputs must be finite")
    scaler = StandardScaler().fit(candidates)
    if (scaler.var_ <= 1e-14).any():
        raise ValueError("Macro scenario dimensions have zero observed variance")
    standardized = scaler.transform(candidates)
    query_z = scaler.transform(query.to_frame().T)[0]
    precision, diagnostics = selected_precision(standardized)
    diff = standardized - query_z
    distances = np.einsum("ij,jk,ik->i", diff, precision.precision_, diff)
    portfolio = returns @ weights
    daily = portfolio.to_numpy()
    # Every observed ending date is a candidate. No 21-session sampling grid.
    if (daily <= -1).any():
        raise ValueError("Analog portfolio NAV became nonpositive")
    cumulative_log = np.r_[0, np.log1p(daily).cumsum()]
    positions = returns.index.get_indexer(candidates.index)
    if (positions < horizon).any() or (daily <= -1).any():
        raise ValueError("Analog portfolio returns or window endpoints are invalid")
    window_returns = np.expm1(
        cumulative_log[positions + 1] - cumulative_log[positions - horizon + 1]
    )
    ranking = np.argsort(distances)[: min(k, len(distances))]
    asset_vol = returns.rolling(21, min_periods=21).std(ddof=1) * np.sqrt(
        int(payload.get("annualization", 252))
    )
    rows, paths = [], []
    for rank in ranking:
        position = positions[rank]
        start = position - horizon + 1
        nav = np.cumprod(1 + daily[start : position + 1])
        drawdown = nav / np.maximum.accumulate(np.r_[1, nav])[1:] - 1
        rows.append(
            {
                "window_start": returns.index[start],
                "window_end": returns.index[position],
                "distance_squared": float(distances[rank]),
                "distance": float(np.sqrt(distances[rank])),
                "portfolio_return": float(window_returns[rank]),
                "maximum_drawdown": float(drawdown.min()),
                **{column: float(candidates.iloc[rank][column]) for column in COLUMNS},
            }
        )
        observed = asset_vol.iloc[start : position + 1]
        for day, (_, row) in enumerate(observed.iterrows()):
            paths.extend(
                {
                    "window_end": returns.index[position],
                    "day": day + 1,
                    "asset": asset,
                    "annualized_volatility": float(row[asset])
                    if pd.notna(row[asset])
                    else None,
                }
                for asset in returns.columns
            )
    fit = sm.OLS(
        window_returns, sm.add_constant(standardized, has_constant="add")
    ).fit()
    beta = np.asarray(fit.params[1:])
    covariance_direction = np.linalg.solve(precision.precision_, beta)
    direction_variance = float(beta @ covariance_direction)
    if direction_variance <= 1e-16:
        adversarial = {
            "status": "unavailable",
            "reason": "Conditional-mean loss surface is flat",
        }
    else:
        delta = -radius * covariance_direction / np.sqrt(direction_variance)
        worst_z = query_z + delta
        predicted = float(np.r_[1, worst_z] @ fit.params)
        distance = float(delta @ precision.precision_ @ delta)
        if not np.isclose(distance, radius**2, rtol=1e-6):
            raise ValueError("Adversarial scenario failed its ellipsoidal constraint")
        worst = scaler.inverse_transform(worst_z[None, :])[0]
        nearest = np.argmin(
            np.einsum(
                "ij,jk,ik->i",
                standardized - worst_z,
                precision.precision_,
                standardized - worst_z,
            )
        )
        adversarial = {
            "status": "ok",
            "scenario": dict(zip(COLUMNS, map(float, worst))),
            "predicted_portfolio_return": predicted,
            "distance_squared_from_query": distance,
            "radius": radius,
            "nearest_observed_window_end": candidates.index[nearest],
            "observed_windows_within_query_radius": int((distances <= radius**2).sum()),
            "conditional_mean_model": "Descriptive OLS on completed overlapping macro-change windows; not a held-out forecasting claim",
            "optimizer": "Exact linear-objective solution on the fitted GLASSO ellipsoid",
        }
    return {
        "analogs": rows,
        "volatility_paths": paths,
        "precision_matrix": pd.DataFrame(
            precision.precision_, index=COLUMNS, columns=COLUMNS
        ),
        "volatility_bands": pd.DataFrame(paths)
        .groupby(["day", "asset"])["annualized_volatility"]
        .agg(
            mean="mean",
            lower=lambda values: values.quantile(0.05),
            upper=lambda values: values.quantile(0.95),
            observed_analog_count="count",
        )
        .reset_index()
        .to_dict("records"),
        "adversarial": adversarial,
        "meta": {
            "candidate_windows": len(candidates),
            "excluded_missing_macro_windows": int(changes.isna().any(axis=1).sum()),
            "horizon_sessions": horizon,
            "reference_window_start": query_start,
            "reference_window_end": query_end,
            "query": query.to_dict(),
            "selected_alpha": float(precision.alpha),
            "precision_candidates": diagnostics,
            "scale": dict(zip(COLUMNS, map(float, scaler.scale_))),
            "center": dict(zip(COLUMNS, map(float, scaler.mean_))),
            "conditional_mean_coefficients": dict(
                zip(("intercept", *COLUMNS), map(float, fit.params))
            ),
            "conditional_mean_r2_in_sample": float(fit.rsquared),
            "selection": "Gaussian BIC with diagonal and unique nonzero off-diagonal precision parameters; overlapping-window IID approximation",
            "sources": {
                "vix": "observed primary VIX",
                "yield": "DGS10",
                "credit": "observed primary credit series",
                "dxy": "DX_Y_NYB Close",
                "equity": "^GSPC Close",
            },
            "macro_vintages": "Retrospective scenario matching only; release vintages are unavailable",
        },
    }
