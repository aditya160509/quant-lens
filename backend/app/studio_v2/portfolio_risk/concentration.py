"""Correlation, concentration, marginal-risk, and component-risk analytics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class ConcentrationEngine:
    MIN_OBSERVATIONS = 20

    @staticmethod
    def overlapping_positions(position_maps: dict[str, dict[str, float]] | None,
                              minimum_weight: float = 1e-12) -> list[dict[str, Any]]:
        if not position_maps:
            return []
        holdings: dict[str, list[dict[str, Any]]] = {}
        for strategy_id, positions in position_maps.items():
            for ticker, raw_weight in (positions or {}).items():
                weight = float(raw_weight)
                if np.isfinite(weight) and abs(weight) > minimum_weight:
                    holdings.setdefault(str(ticker).upper(), []).append({
                        "strategy_id": str(strategy_id), "weight": weight,
                    })
        output = []
        for ticker, strategies in holdings.items():
            if len(strategies) >= 2:
                output.append({
                    "ticker": ticker,
                    "strategy_count": len(strategies),
                    "strategies": strategies,
                    "net_weight": float(sum(row["weight"] for row in strategies)),
                    "gross_weight": float(sum(abs(row["weight"]) for row in strategies)),
                    "same_direction": len({np.sign(row["weight"]) for row in strategies}) == 1,
                })
        return sorted(output, key=lambda row: (-row["strategy_count"], -row["gross_weight"], row["ticker"]))

    def compute(self, returns: Any, weights: Any = None,
                position_maps: dict[str, dict[str, float]] | None = None) -> dict[str, Any]:
        frame = pd.DataFrame(returns, dtype=float).replace([np.inf, -np.inf], np.nan)
        if frame.empty or frame.shape[1] == 0:
            raise ValueError("return observations are required")
        input_observations = len(frame)
        frame = frame.dropna(axis=0, how="any")
        if len(frame) < self.MIN_OBSERVATIONS:
            raise ValueError(
                f"at least {self.MIN_OBSERVATIONS} aligned return observations are required"
            )
        vector = np.asarray(
            weights if weights is not None else np.ones(frame.shape[1]), dtype=float
        )
        if vector.size != frame.shape[1]:
            raise ValueError("weights length does not match assets")
        if not np.isfinite(vector).all():
            raise ValueError("weights must be finite")
        gross_weight = float(np.abs(vector).sum())
        if gross_weight <= 0:
            raise ValueError("weights must have positive gross exposure")
        vector = vector / gross_weight
        covariance = frame.cov().to_numpy() * 252
        covariance_rank = int(np.linalg.matrix_rank(covariance))
        variance = float(vector @ covariance @ vector)
        volatility = np.sqrt(max(variance, 0.0))
        marginal = covariance @ vector / volatility if volatility > 0 else np.zeros_like(vector)
        component = vector * marginal
        normalized_component = component / component.sum() if component.sum() else np.zeros_like(component)
        names = list(map(str, frame.columns))
        return {
            "correlation": frame.corr().fillna(0.0),
            "covariance_rank": covariance_rank,
            "singular_covariance": covariance_rank < frame.shape[1],
            "constant_assets": [
                str(column) for column in frame.columns
                if float(frame[column].std(ddof=1)) <= np.finfo(float).eps
            ],
            "observations": len(frame),
            "input_observations": input_observations,
            "observations_dropped": input_observations - len(frame),
            "alignment": "inner",
            "weights": dict(zip(names, map(float, vector))),
            "portfolio_volatility": volatility,
            "marginal_risk": dict(zip(names, map(float, marginal))),
            "component_risk": dict(zip(names, map(float, component))),
            "component_risk_percent": dict(zip(names, map(float, normalized_component))),
            "weight_hhi": float(np.square(vector).sum()),
            "effective_number_of_positions": float(1 / np.square(vector).sum()) if np.square(vector).sum() else 0.0,
            "largest_absolute_weight": float(np.abs(vector).max()) if vector.size else 0.0,
            "overlapping_positions": self.overlapping_positions(position_maps),
        }
