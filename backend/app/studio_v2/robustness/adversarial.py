"""Adversarial market-data perturbations with deterministic persistence."""

from __future__ import annotations

import uuid
from typing import Any, Callable

import numpy as np
import pandas as pd

from ..shared.persistence import SQLiteStore


class AdversarialStressTest:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()

    def run(self, returns: Any, evaluate: Callable[[pd.Series], Any] | None = None,
            seed: int = 42, shock_sigma: float = 4.0,
            window: int = 63, max_vol_percentile: float = 95.0,
            max_cost_percentile: float = 95.0,
            min_correlation: float = -0.25) -> dict[str, Any]:
        base = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        if len(base) < 20:
            raise ValueError("at least 20 returns are required")
        resolved_window = min(max(10, int(window)), len(base))

        def metrics(series: pd.Series) -> dict[str, Any]:
            clean = pd.Series(series, dtype=float).dropna()
            wealth = (1.0 + clean).cumprod()
            drawdown = wealth / wealth.cummax() - 1.0
            standard_deviation = float(clean.std(ddof=1))
            sharpe = float(clean.mean() / standard_deviation * np.sqrt(252)) if standard_deviation > 0 else 0.0
            trough = int(np.argmin(drawdown.to_numpy())) if len(drawdown) else 0
            recovery = None
            if len(drawdown):
                prior_peak = float(wealth.iloc[:trough + 1].max())
                later = np.flatnonzero(wealth.iloc[trough:].to_numpy() >= prior_peak)
                recovery = int(later[0]) if len(later) else None
            return {
                "sharpe": sharpe,
                "total_return": float(wealth.iloc[-1] - 1.0),
                "volatility": standard_deviation * np.sqrt(252),
                "max_drawdown": float(drawdown.min()),
                "recovery_days": recovery,
            }

        candidates = []
        rolling_vol = base.rolling(resolved_window).std(ddof=1)
        rolling_cost = base.diff().abs().rolling(resolved_window).mean()
        vol_limit = float(np.nanpercentile(rolling_vol, max_vol_percentile))
        cost_limit = float(np.nanpercentile(rolling_cost, max_cost_percentile))
        reference = base.iloc[-resolved_window:].reset_index(drop=True)
        for start in range(0, len(base) - resolved_window + 1):
            sample = base.iloc[start:start + resolved_window].reset_index(drop=True)
            correlation = float(sample.corr(reference))
            volatility = float(sample.std(ddof=1))
            cost_proxy = float(sample.diff().abs().mean())
            if volatility <= vol_limit and cost_proxy <= cost_limit and correlation >= min_correlation:
                candidates.append({
                    "start_index": start,
                    "end_index": start + resolved_window - 1,
                    "correlation": correlation,
                    "cost_proxy": cost_proxy,
                    "returns": sample,
                    "metrics": metrics(sample),
                })
        if not candidates:
            raise ValueError("no historical window satisfies adversarial constraints")
        worst = min(candidates, key=lambda item: item["metrics"]["sharpe"])
        baseline_metrics = metrics(reference)
        adversarial_metrics = worst["metrics"]
        if evaluate:
            baseline_metrics["evaluation"] = evaluate(reference)
            adversarial_metrics["evaluation"] = evaluate(worst["returns"])
        baseline_sharpe = baseline_metrics["sharpe"]
        degradation = (
            (baseline_sharpe - adversarial_metrics["sharpe"]) / abs(baseline_sharpe)
            if baseline_sharpe != 0 else baseline_sharpe - adversarial_metrics["sharpe"]
        )
        run_id = str(uuid.uuid4())
        result = {
            "run_id": run_id,
            "method": "constrained_historical_window_search",
            "baseline": baseline_metrics,
            "adversarial": adversarial_metrics,
            "degradation_percentage": float(degradation * 100.0),
            "recovery_days": adversarial_metrics["recovery_days"],
            "survival_verdict": (
                "survives" if adversarial_metrics["max_drawdown"] > -0.35
                and adversarial_metrics["sharpe"] > -1.0 else "fails"
            ),
            "selected_window": {
                key: value for key, value in worst.items() if key not in {"returns", "metrics"}
            },
            "constraints": {
                "window": resolved_window,
                "max_vol_percentile": float(max_vol_percentile),
                "max_cost_percentile": float(max_cost_percentile),
                "min_correlation": float(min_correlation),
                "volatility_limit": vol_limit,
                "cost_limit": cost_limit,
            },
            "candidates_evaluated": len(candidates),
        }
        self.store.put("adversarial_runs", run_id, result, create_only=True)
        return result

    def get(self, run_id: str) -> dict[str, Any]:
        return self.store.get("adversarial_runs", run_id)
