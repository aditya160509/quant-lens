"""Brinson-Fachler sector attribution and factor exposure decomposition."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class AttributionEngine:
    @staticmethod
    def brinson(rows: Any) -> dict[str, Any]:
        frame = pd.DataFrame(rows).copy()
        if frame.empty:
            raise ValueError("attribution requires at least one sector row")
        required_numeric = {
            "portfolio_weight", "benchmark_weight", "portfolio_return", "benchmark_return"
        }
        required = {"sector", *required_numeric}
        missing = required.difference(frame.columns)
        if missing == {"sector"}:
            frame["sector"] = "Unmapped"
            missing = set()
        if missing:
            raise ValueError(f"attribution rows missing columns: {sorted(missing)}")
        frame["sector"] = frame["sector"].fillna("Unmapped").astype(str).str.strip()
        frame.loc[frame["sector"].eq(""), "sector"] = "Unmapped"
        for column in required_numeric:
            converted = pd.to_numeric(frame[column], errors="coerce")
            invalid = ~np.isfinite(converted.to_numpy(dtype=float))
            if invalid.any():
                bad_rows = np.flatnonzero(invalid).tolist()
                raise ValueError(
                    f"attribution column '{column}' contains non-finite values at rows {bad_rows}"
                )
            frame[column] = converted.astype(float)
        benchmark_total = float((frame.benchmark_weight * frame.benchmark_return).sum())
        portfolio_total = float((frame.portfolio_weight * frame.portfolio_return).sum())
        frame["allocation"] = (frame.portfolio_weight - frame.benchmark_weight) * (
            frame.benchmark_return - benchmark_total
        )
        frame["selection"] = frame.benchmark_weight * (
            frame.portfolio_return - frame.benchmark_return
        )
        frame["interaction"] = (frame.portfolio_weight - frame.benchmark_weight) * (
            frame.portfolio_return - frame.benchmark_return
        )
        frame["total_effect"] = frame[["allocation", "selection", "interaction"]].sum(axis=1)
        explained = float(frame.total_effect.sum())
        active_return = portfolio_total - benchmark_total
        reconciliation_error = explained - active_return
        return {
            "sectors": frame.to_dict(orient="records"),
            "sector_attribution": frame.to_dict(orient="records"),
            "total_allocation_effect": float(frame.allocation.sum()),
            "total_selection_effect": float(frame.selection.sum()),
            "total_interaction_effect": float(frame.interaction.sum()),
            "allocation_effect": float(frame.allocation.sum()),
            "selection_effect": float(frame.selection.sum()),
            "interaction_effect": float(frame.interaction.sum()),
            "active_return_explained": explained,
            "active_return_actual": active_return,
            "portfolio_return": portfolio_total,
            "benchmark_return": benchmark_total,
            "portfolio_weight_total": float(frame.portfolio_weight.sum()),
            "benchmark_weight_total": float(frame.benchmark_weight.sum()),
            "reconciliation_error": reconciliation_error,
            "reconciled": abs(reconciliation_error) <= 1e-10,
        }

    @staticmethod
    def factor_attribution(returns: Any, factor_returns: Any) -> dict[str, Any]:
        y = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan)
        x = pd.DataFrame(factor_returns, dtype=float).replace([np.inf, -np.inf], np.nan)
        x = x.dropna(axis=1, how="all")
        if x.shape[1] == 0:
            return {
                "status": "unavailable", "reason": "no usable factor columns",
                "alpha": None, "betas": {}, "r_squared": None,
                "observations": 0, "factor_count": 0, "rank": 0,
            }
        joined = pd.concat([y.rename("portfolio"), x], axis=1).dropna()
        if len(joined) <= x.shape[1] + 1:
            return {
                "status": "insufficient_observations",
                "reason": "factor regression requires more observations than coefficients",
                "alpha": None, "betas": {}, "r_squared": None,
                "observations": len(joined), "factor_count": x.shape[1], "rank": 0,
            }
        design = np.column_stack([np.ones(len(joined)), joined[x.columns].to_numpy()])
        rank = int(np.linalg.matrix_rank(design))
        if rank < design.shape[1]:
            return {
                "status": "singular",
                "reason": "factor matrix is rank deficient; betas are not identifiable",
                "alpha": None, "betas": {}, "r_squared": None,
                "observations": len(joined), "factor_count": x.shape[1], "rank": rank,
            }
        coefficients, *_ = np.linalg.lstsq(design, joined.portfolio.to_numpy(), rcond=None)
        fitted = design @ coefficients
        residual = joined.portfolio.to_numpy() - fitted
        total = np.square(joined.portfolio.to_numpy() - joined.portfolio.mean()).sum()
        raw_r_squared = 1.0 - np.square(residual).sum() / total if total > 0 else 0.0
        r_squared = float(np.clip(raw_r_squared, 0.0, 1.0))
        return {
            "status": "ok",
            "alpha": float(coefficients[0]),
            "betas": dict(zip(x.columns, map(float, coefficients[1:]))),
            "r_squared": r_squared,
            "observations": len(joined),
            "factor_count": x.shape[1],
            "rank": rank,
        }

    def compute(self, payload: dict[str, Any]) -> dict[str, Any]:
        sector_rows = payload.get("sector_rows", payload.get("rows", []))
        has_sector_rows = sector_rows is not None and len(sector_rows) > 0
        if has_sector_rows:
            output = self.brinson(sector_rows)
            output["attribution_status"] = "ok" if output["reconciled"] else "non_reconciling"
        else:
            output = {
                "sectors": [], "sector_attribution": [],
                "total_allocation_effect": 0.0, "total_selection_effect": 0.0,
                "total_interaction_effect": 0.0, "allocation_effect": 0.0,
                "selection_effect": 0.0, "interaction_effect": 0.0,
                "active_return_explained": 0.0, "active_return_actual": None,
                "portfolio_return": None, "benchmark_return": None,
                "portfolio_weight_total": 0.0, "benchmark_weight_total": 0.0,
                "reconciliation_error": None, "reconciled": False,
                "attribution_status": "benchmark_unavailable",
            }
        benchmark_name = payload.get("benchmark_name", payload.get("benchmark"))
        output["benchmark_name"] = str(benchmark_name) if benchmark_name else None
        output["benchmark_available"] = has_sector_rows
        output["factors"] = []
        if "returns" in payload and "factor_returns" in payload:
            factor_result = self.factor_attribution(
                payload["returns"], payload["factor_returns"]
            )
            output["factor_attribution"] = factor_result
            output["factors"] = [
                {"factor": name, "beta": beta, "alpha": factor_result["alpha"],
                 "r_squared": factor_result["r_squared"]}
                for name, beta in factor_result["betas"].items()
            ]
        return output
