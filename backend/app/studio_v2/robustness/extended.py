"""Bounded, JSON-safe extended robustness diagnostics."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from .data_source_test import DataSourceRobustnessTest
from .parameter_interaction import ParameterInteractionTest
from .tests import CapacityStressTest, CostBreakEvenTest, RegimeDecompositionTest, TimingPerturbationTest


def _sharpe(values: Any) -> float:
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(series) < 2:
        return 0.0
    deviation = float(series.std(ddof=1))
    return float(series.mean() / deviation * np.sqrt(252.0)) if deviation > 0 else 0.0


class ExtendedRobustnessRunner:
    """Dispatch extended diagnostics without accepting executable callbacks."""

    def run(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
        test = str(payload["test"])
        if test == "parameter":
            grid, observations = payload.get("parameter_grid", {}), payload.get("observations", [])
            if len(grid) < 2 or not observations:
                raise ValueError("parameter test requires a two-dimensional parameter_grid and observations")
            result = ParameterInteractionTest().run(grid, observations=observations)
            stability = float(np.mean(list(result.get("marginal_stability", {}).values())))
            return {"parameter": result}, {"parameter_stability": float(np.clip(stability, 0.0, 1.0))}
        if test == "timing":
            trades = pd.DataFrame(payload.get("trade_log", []))
            if trades.empty:
                raise ValueError("trade_log is required for timing perturbation")
            result = TimingPerturbationTest().run(trades, int(payload.get("n_simulations", 200)))
            score = float(np.clip(result.sensitivity_score, 0.0, 1.0)) if np.isfinite(result.sensitivity_score) else 0.0
            return {"timing": asdict(result)}, {"timing": score}
        if test == "noise":
            result = DataSourceRobustnessTest().perturb(
                payload.get("returns", []),
                noise_std=float(payload.get("noise_bps", 10.0)) / 10_000.0,
                simulations=int(payload.get("n_simulations", 200)),
                seed=int(payload.get("seed", 42)),
            )
            return {"noise": result}, {}
        if test == "universe":
            result = self._universe(payload)
            return {"universe": result}, {}
        if test == "cost":
            frame = pd.DataFrame(payload.get("cost_sharpes", []))
            if not {"cost_bps", "sharpe"}.issubset(frame.columns) or len(frame) < 2:
                raise ValueError("cost_sharpes requires at least two cost_bps/sharpe observations")
            diagnostic = CostBreakEvenTest()
            breakeven = diagnostic.compute_breakeven_cost(frame[["cost_bps", "sharpe"]])
            score = diagnostic.compute_cost_robustness_score(breakeven, tuple(payload.get("realistic_band", [5.0, 15.0])))
            result = {"cost_sharpes": frame.to_dict(orient="records"), "breakeven_bps": breakeven,
                      "robustness_score": score}
            return {"cost": result}, {"cost": float(np.clip(score, 0.0, 1.0))}
        if test == "capacity":
            trades = pd.DataFrame(payload.get("trade_log", []))
            if trades.empty:
                raise ValueError("trade_log is required for capacity stress")
            result = CapacityStressTest().run(
                trades, payload.get("adv_data", {}), payload.get("vol_data", {}),
                payload.get("lambda_by_bucket", {"small": 1.2e-4}),
            )
            serialized = asdict(result)
            finite_ceiling = float(result.capacity_ceiling) if np.isfinite(result.capacity_ceiling) else None
            score = 1.0 if finite_ceiling is None else float(np.clip(np.log10(max(finite_ceiling, 1.0)) / 10.0, 0.0, 1.0))
            return {"capacity": serialized}, {"capacity": score}
        if test == "boundary":
            values = pd.Series(payload.get("oos_sharpes", []), dtype=float).dropna()
            if len(values) < 2:
                raise ValueError("oos_sharpes requires at least two observations")
            sensitivity = float(values.std(ddof=1))
            return {"boundary": {"oos_sharpes": values.tolist(), "sensitivity_score": sensitivity}}, {}
        if test == "regime":
            returns, vix = payload.get("returns", []), payload.get("vix", [])
            if len(returns) < 20 or len(returns) != len(vix):
                raise ValueError("regime test requires equal returns and vix arrays with at least 20 observations")
            result = RegimeDecompositionTest().run(pd.Series(returns), pd.Series(vix))
            return {"regime": asdict(result)}, {}
        raise ValueError(f"unsupported extended robustness test: {test}")

    @staticmethod
    def _universe(payload: dict[str, Any]) -> dict[str, Any]:
        frame = pd.DataFrame(payload.get("returns_by_ticker", {}), dtype=float).replace([np.inf, -np.inf], np.nan)
        if len(frame) < 20 or frame.shape[1] < 3:
            raise ValueError("returns_by_ticker requires at least 20 observations for three tickers")
        dropout = float(payload.get("drop_pct", 0.10))
        keep = max(2, int(round(frame.shape[1] * (1.0 - dropout))))
        count = int(payload.get("n_simulations", 200))
        rng = np.random.default_rng(int(payload.get("seed", 42)))
        baseline = _sharpe(frame.mean(axis=1))
        sharpes = np.empty(count, dtype=float)
        columns = frame.columns.to_numpy()
        for index in range(count):
            chosen = rng.choice(columns, size=keep, replace=False)
            sharpes[index] = _sharpe(frame[chosen].mean(axis=1))
        finite = sharpes[np.isfinite(sharpes)]
        ratio = float(np.median(finite) / baseline) if baseline else 0.0
        return {
            "baseline_sharpe": baseline,
            "median_sharpe": float(np.median(finite)),
            "sharpe_std": float(np.std(finite, ddof=1)),
            "stability_score": float(np.clip(ratio, 0.0, 1.0)),
            "failure_rate": float(np.mean(finite <= 0)),
            "drop_pct": dropout,
            "simulations": count,
            "seed": int(payload.get("seed", 42)),
        }
