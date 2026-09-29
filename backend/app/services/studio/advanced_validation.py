"""Bounded advanced evidence calculated only from explicitly supplied observations."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats


class AdvancedValidationError(ValueError):
    pass


def _finite(values: list[float], minimum: int = 2) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or len(result) < minimum or not np.isfinite(result).all():
        raise AdvancedValidationError(f"at least {minimum} finite observations are required")
    return result


def sharpe_evidence(returns: list[float], *, trials: int, periods_per_year: int = 252, benchmark_sharpe: float = 0.0) -> dict[str, Any]:
    values = _finite(returns, 30)
    if not 1 <= int(trials) <= 100_000:
        raise AdvancedValidationError("trials must be between 1 and 100000")
    deviation = float(values.std(ddof=1))
    if deviation <= 0:
        raise AdvancedValidationError("returns require positive sample volatility")
    period_sharpe = float(values.mean() / deviation)
    annual_sharpe = period_sharpe * math.sqrt(periods_per_year)
    skew = float(stats.skew(values, bias=False))
    kurtosis = float(stats.kurtosis(values, fisher=False, bias=False))
    variance_term = max(1.0 - skew * period_sharpe + ((kurtosis - 1.0) / 4.0) * period_sharpe**2, 1e-12)
    standard_error = math.sqrt(variance_term / (len(values) - 1))
    benchmark_period = float(benchmark_sharpe) / math.sqrt(periods_per_year)
    psr = float(stats.norm.cdf((period_sharpe - benchmark_period) / standard_error))
    gamma = 0.5772156649015329
    if trials == 1:
        expected_max = benchmark_period
    else:
        expected_max = benchmark_period + standard_error * (
            (1 - gamma) * stats.norm.ppf(1 - 1 / trials)
            + gamma * stats.norm.ppf(1 - 1 / (trials * math.e))
        )
    dsr = float(stats.norm.cdf((period_sharpe - expected_max) / standard_error))
    return {
        "observations": len(values), "periods_per_year": periods_per_year, "trials": int(trials),
        "annualized_sharpe": annual_sharpe, "benchmark_annualized_sharpe": float(benchmark_sharpe),
        "sample_skewness": skew, "sample_kurtosis_pearson": kurtosis,
        "probabilistic_sharpe_probability": psr, "deflated_sharpe_probability": dsr,
        "selection_bias": {
            "expected_max_null_annualized_sharpe": expected_max * math.sqrt(periods_per_year),
            "annualized_haircut": (period_sharpe - expected_max) * math.sqrt(periods_per_year),
        },
        "formulas": {
            "probabilistic_sharpe": "Bailey and Lopez de Prado PSR: Phi((SR-SR*)/sqrt((1-skew*SR+((kurtosis-1)/4)*SR^2)/(n-1)))",
            "deflated_sharpe": "PSR evaluated against the expected maximum null Sharpe across the user-supplied number of trials using the Euler-Mascheroni approximation",
            "annualization": "period Sharpe multiplied by sqrt(periods_per_year)",
        },
    }


def parameter_instability(segments: list[dict[str, Any]], *, periods_per_year: int = 252) -> dict[str, Any]:
    if not 2 <= len(segments) <= 100:
        raise AdvancedValidationError("parameter instability requires 2 to 100 segments")
    rows = []
    for segment in segments:
        values = _finite(segment.get("returns", []), 10)
        deviation = float(values.std(ddof=1))
        sharpe = float(values.mean() / deviation * math.sqrt(periods_per_year)) if deviation > 0 else None
        rows.append({"label": str(segment.get("label") or f"segment_{len(rows) + 1}"), "observations": len(values), "annualized_sharpe": sharpe, "mean_return": float(values.mean()), "volatility": deviation})
    sharpes = np.asarray([row["annualized_sharpe"] for row in rows if row["annualized_sharpe"] is not None])
    return {
        "segments": rows,
        "diagnostics": {
            "sharpe_range": float(sharpes.max() - sharpes.min()) if len(sharpes) else None,
            "sharpe_std": float(sharpes.std(ddof=1)) if len(sharpes) > 1 else None,
            "sign_flip": bool(np.any(sharpes > 0) and np.any(sharpes < 0)),
            "worst_segment": rows[int(np.nanargmin([row["annualized_sharpe"] if row["annualized_sharpe"] is not None else np.nan for row in rows]))]["label"] if len(sharpes) else None,
        },
        "formula": "Dispersion and sign stability of annualized sample Sharpe across user-defined parameter or time segments",
    }


def implementation_feasibility(trades: list[dict[str, Any]], *, impact_coefficient: float = 1.0, participation_limit: float = 0.10, portfolio_value: float | None = None, holding_days: int = 1) -> dict[str, Any]:
    if not trades:
        raise AdvancedValidationError("at least one proposed trade is required")
    rows, skipped = [], set()
    for index, trade in enumerate(trades):
        notional = abs(float(trade.get("notional", 0)))
        adv = trade.get("average_daily_dollar_volume")
        spread = trade.get("spread_bps")
        volatility = trade.get("daily_volatility")
        borrow = trade.get("annual_borrow_rate")
        participation = notional / float(adv) if adv not in (None, 0) else None
        impact = float(impact_coefficient) * float(volatility) * math.sqrt(participation) * 10_000 if participation is not None and volatility is not None else None
        if participation is None: skipped.add("capacity and participation: average_daily_dollar_volume not supplied")
        if impact is None: skipped.add("market impact: daily_volatility and liquidity not supplied")
        if spread is None: skipped.add("spread cost: spread_bps not supplied")
        if str(trade.get("side", "")).lower() == "short" and borrow is None: skipped.add("borrow cost: annual_borrow_rate not supplied for short trade")
        borrow_cost = float(borrow) * holding_days / 365 * 10_000 if str(trade.get("side", "")).lower() == "short" and borrow is not None else 0.0
        spread_cost = float(spread) / 2 if spread is not None else None
        rows.append({
            "trade": index + 1, "asset": trade.get("asset"), "notional": notional,
            "participation": participation, "participation_limit": participation_limit,
            "capacity_breach": participation is not None and participation > participation_limit,
            "estimated_impact_bps": impact, "spread_bps": float(spread) if spread is not None else None,
            "annual_borrow_rate": float(borrow) if borrow is not None else None,
            "holding_period_borrow_cost_bps": borrow_cost,
            "estimated_one_way_cost_bps": impact + spread_cost + borrow_cost if impact is not None and spread_cost is not None else None,
        })
    if portfolio_value is None: skipped.add("turnover: portfolio_value not supplied")
    elif portfolio_value <= 0: raise AdvancedValidationError("portfolio_value must be positive")
    turnover = sum(row["notional"] for row in rows) / portfolio_value if portfolio_value else None
    return {"trades": rows, "summary": {"one_way_turnover": turnover, "capacity_breach_count": sum(row["capacity_breach"] for row in rows)}, "skipped_tests": sorted(skipped), "assumptions": {"impact_coefficient": impact_coefficient, "participation_limit": participation_limit, "holding_days": holding_days, "impact_model": "coefficient * daily_volatility * sqrt(notional / ADV)", "spread_model": "half supplied spread per one-way trade", "borrow_model": "annual borrow rate * holding_days / 365"}}


def data_substitution_sensitivity(primary: list[float], alternatives: dict[str, list[float]], *, periods_per_year: int = 252) -> dict[str, Any]:
    base = _finite(primary, 30)
    base_sr = float(base.mean() / base.std(ddof=1) * math.sqrt(periods_per_year))
    rows = []
    for name, observations in alternatives.items():
        if len(observations) != len(base):
            raise AdvancedValidationError(f"alternative '{name}' must align to the primary observations")
        values = _finite(observations, 30)
        sr = float(values.mean() / values.std(ddof=1) * math.sqrt(periods_per_year))
        rows.append({"source": name, "annualized_sharpe": sr, "sharpe_delta": sr - base_sr, "mean_absolute_return_delta": float(np.mean(np.abs(values - base)))})
    return {"primary_annualized_sharpe": base_sr, "alternatives": rows, "formula": "Aligned source Sharpe delta and mean absolute observation delta; no missing values are imputed"}
