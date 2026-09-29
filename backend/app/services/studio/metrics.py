"""Canonical Studio performance metrics.

Conventions:
- input equity values are positive account-value levels;
- periodic returns are simple returns;
- volatility and ratios use population standard deviation (ddof=0);
- annual return is geometrically annualized using ``periods_per_year``;
- alpha and beta use aligned simple returns and the same periodic risk-free rate;
- unavailable inputs produce explicit unavailable values, never numeric zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import numpy as np

from .conventions import ANNUAL_RISK_FREE_RATE, PERIODS_PER_YEAR
from .schemas import MetricValue, StudioWarning


ENGINE_VERSION = "studio-metrics/1.0.0"


@dataclass(frozen=True)
class MetricBundle:
    metrics: Dict[str, MetricValue]
    warnings: Sequence[StudioWarning]

    def as_dict(self) -> Dict[str, Dict[str, Any]]:
        return {name: metric.model_dump() for name, metric in self.metrics.items()}


def _metric(
    value: Optional[float],
    unit: str,
    sample_size: int,
    methodology: str,
    *,
    estimated: bool = False,
) -> MetricValue:
    finite = value is not None and np.isfinite(value)
    return MetricValue(
        value=float(value) if finite else None,
        unit=unit,
        status=("estimated" if estimated else "observed") if finite else "unavailable",
        sample_size=sample_size,
        methodology=methodology,
    )


def _finite_array(values: Iterable[float]) -> np.ndarray:
    result = np.asarray(list(values), dtype=float)
    return result[np.isfinite(result)]


def _unavailable(name: str, unit: str, reason: str) -> tuple[str, MetricValue]:
    return name, _metric(None, unit, 0, reason)


def calculate_performance_metrics(
    equity_curve: Sequence[float],
    trades: Sequence[Mapping[str, Any]] = (),
    *,
    periods_per_year: int = PERIODS_PER_YEAR,
    annual_risk_free_rate: float = ANNUAL_RISK_FREE_RATE,
    benchmark_returns: Optional[Sequence[float]] = None,
    turnover: Optional[float] = None,
    average_exposure: Optional[float] = None,
    gross_equity_curve: Optional[Sequence[float]] = None,
) -> MetricBundle:
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    if annual_risk_free_rate <= -1:
        raise ValueError("annual_risk_free_rate must be greater than -1")

    equity = np.asarray(equity_curve, dtype=float)
    warnings = []
    if equity.size < 2 or np.any(~np.isfinite(equity)) or np.any(equity <= 0):
        warning = StudioWarning(
            code="INSUFFICIENT_EQUITY",
            message="At least two finite positive equity observations are required.",
            field="equity_curve",
        )
        metrics = dict([
            _unavailable("total_return", "decimal", warning.message),
            _unavailable("annual_return", "decimal", warning.message),
            _unavailable("volatility", "decimal_annualized", warning.message),
            _unavailable("sharpe", "ratio", warning.message),
            _unavailable("sortino", "ratio", warning.message),
            _unavailable("calmar", "ratio", warning.message),
            _unavailable("max_drawdown", "decimal", warning.message),
        ])
        return MetricBundle(metrics=metrics, warnings=[warning])

    returns = np.diff(equity) / equity[:-1]
    n = int(returns.size)
    periodic_rf = (1.0 + annual_risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    excess = returns - periodic_rf
    mean_return = float(np.mean(returns))
    volatility_periodic = float(np.std(returns, ddof=0))
    volatility = volatility_periodic * np.sqrt(periods_per_year)
    sharpe = (
        float(np.mean(excess) / volatility_periodic * np.sqrt(periods_per_year))
        if volatility_periodic > 0
        else None
    )
    downside = np.minimum(excess, 0.0)
    downside_deviation = float(np.sqrt(np.mean(np.square(downside))))
    sortino = (
        float(np.mean(excess) / downside_deviation * np.sqrt(periods_per_year))
        if downside_deviation > 0
        else None
    )
    running_peak = np.maximum.accumulate(equity)
    drawdowns = equity / running_peak - 1.0
    max_drawdown = float(np.min(drawdowns))
    total_return = float(equity[-1] / equity[0] - 1.0)
    annual_return = float((equity[-1] / equity[0]) ** (periods_per_year / n) - 1.0)
    calmar = annual_return / abs(max_drawdown) if max_drawdown < 0 else None

    metrics: Dict[str, MetricValue] = {
        "total_return": _metric(total_return, "decimal", n, "ending equity / starting equity - 1"),
        "annual_return": _metric(annual_return, "decimal_annualized", n, "geometric annualization"),
        "volatility": _metric(volatility, "decimal_annualized", n, "population standard deviation annualized"),
        "sharpe": _metric(sharpe, "ratio", n, "annualized mean excess return / population volatility"),
        "sortino": _metric(sortino, "ratio", n, "annualized mean excess return / lower partial deviation"),
        "calmar": _metric(calmar, "ratio", n, "annual return / absolute maximum drawdown"),
        "max_drawdown": _metric(max_drawdown, "decimal", len(equity), "minimum equity / running peak - 1"),
        "turnover": _metric(turnover, "decimal", n, "provided portfolio turnover"),
        "exposure": _metric(average_exposure, "decimal", n, "provided average gross exposure"),
    }

    pnl = _finite_array(trade.get("pnl") for trade in trades if trade.get("pnl") is not None)
    trade_count = int(pnl.size)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    hit_rate = float(wins.size / trade_count) if trade_count else None
    payoff = float(np.mean(wins) / abs(np.mean(losses))) if wins.size and losses.size else None
    holding = _finite_array(
        trade.get("holding_period") for trade in trades if trade.get("holding_period") is not None
    )
    mae = _finite_array(trade.get("mae") for trade in trades if trade.get("mae") is not None)
    mfe = _finite_array(trade.get("mfe") for trade in trades if trade.get("mfe") is not None)
    metrics.update({
        "hit_rate": _metric(hit_rate, "decimal", trade_count, "profitable closed trades / closed trades"),
        "payoff": _metric(payoff, "ratio", trade_count, "average winning return / absolute average losing return"),
        "average_win": _metric(float(np.mean(wins)) if wins.size else None, "decimal", int(wins.size), "mean profitable closed-trade return"),
        "average_loss": _metric(float(np.mean(losses)) if losses.size else None, "decimal", int(losses.size), "mean losing closed-trade return"),
        "expectancy": _metric(float(np.mean(pnl)) if pnl.size else None, "decimal", trade_count, "mean closed-trade return"),
        "max_win": _metric(float(np.max(wins)) if wins.size else None, "decimal", int(wins.size), "maximum profitable closed-trade return"),
        "max_loss": _metric(float(np.min(losses)) if losses.size else None, "decimal", int(losses.size), "minimum losing closed-trade return"),
        "average_holding_period": _metric(float(np.mean(holding)) if holding.size else None, "bars", int(holding.size), "mean closed-trade holding period"),
        "mae": _metric(float(np.mean(mae)) if mae.size else None, "decimal", int(mae.size), "mean realized maximum adverse excursion"),
        "mfe": _metric(float(np.mean(mfe)) if mfe.size else None, "decimal", int(mfe.size), "mean realized maximum favorable excursion"),
        "total_trades": _metric(float(trade_count), "count", trade_count, "closed trade count"),
    })

    if benchmark_returns is None:
        for name, unit in (("beta", "ratio"), ("alpha", "decimal_annualized"), ("tracking_error", "decimal_annualized"), ("information_ratio", "ratio")):
            metrics[name] = _metric(None, unit, 0, "benchmark returns were not provided")
    else:
        benchmark = np.asarray(benchmark_returns, dtype=float)
        if benchmark.shape != returns.shape or np.any(~np.isfinite(benchmark)):
            raise ValueError("benchmark returns must be finite and aligned with strategy returns")
        benchmark_variance = float(np.var(benchmark, ddof=0))
        beta = float(np.cov(returns, benchmark, ddof=0)[0, 1] / benchmark_variance) if benchmark_variance > 0 else None
        alpha_periodic = mean_return - periodic_rf - (beta * (float(np.mean(benchmark)) - periodic_rf) if beta is not None else 0.0)
        alpha = alpha_periodic * periods_per_year if beta is not None else None
        active = returns - benchmark
        tracking_error = float(np.std(active, ddof=0) * np.sqrt(periods_per_year))
        information_ratio = float(np.mean(active) * periods_per_year / tracking_error) if tracking_error > 0 else None
        metrics.update({
            "beta": _metric(beta, "ratio", n, "population covariance(strategy, benchmark) / benchmark variance"),
            "alpha": _metric(alpha, "decimal_annualized", n, "annualized Jensen alpha"),
            "tracking_error": _metric(tracking_error, "decimal_annualized", n, "annualized population standard deviation of active returns"),
            "information_ratio": _metric(information_ratio, "ratio", n, "annualized active return / tracking error"),
        })

    if gross_equity_curve is None:
        metrics["cost_drag"] = _metric(None, "decimal", 0, "gross equity curve was not provided")
    else:
        gross = np.asarray(gross_equity_curve, dtype=float)
        if gross.shape != equity.shape or np.any(~np.isfinite(gross)) or np.any(gross <= 0):
            raise ValueError("gross equity curve must be finite, positive, and aligned")
        gross_return = float(gross[-1] / gross[0] - 1.0)
        metrics["cost_drag"] = _metric(gross_return - total_return, "decimal", n, "gross total return - net total return")

    unavailable = [name for name, value in metrics.items() if value.status == "unavailable"]
    if unavailable:
        warnings.append(StudioWarning(
            code="METRICS_UNAVAILABLE",
            message=f"Unavailable metrics: {', '.join(sorted(unavailable))}.",
        ))
    return MetricBundle(metrics=metrics, warnings=warnings)


def legacy_metric_aliases(bundle: MetricBundle) -> Dict[str, Any]:
    """Truthful compatibility fields for the current Results component."""

    value = lambda name: bundle.metrics[name].value if name in bundle.metrics else None
    return {
        "sharpe": value("sharpe"),
        "sortino": value("sortino"),
        "calmar": value("calmar"),
        "maxDrawdown": value("max_drawdown"),
        "winRate": value("hit_rate"),
        "profitFactor": value("payoff"),
        "avgWin": value("average_win"),
        "avgLoss": value("average_loss"),
        "mae": value("mae"),
        "mfe": value("mfe"),
        "totalTrades": int(value("total_trades") or 0),
        "avgHoldingPeriod": value("average_holding_period"),
        "expectancy": value("expectancy"),
        "recoveryFactor": None,
        "totalReturn": value("total_return"),
        "annualReturn": value("annual_return"),
        "canonical": bundle.as_dict(),
    }
