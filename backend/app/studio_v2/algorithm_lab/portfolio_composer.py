"""Multi-strategy composition and same-process namespace execution."""

from __future__ import annotations

import ast
import importlib.util
import math
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..shared.persistence import SQLiteStore, utc_now
from .repository import StrategyRepository


_ALLOWED_ALLOCATOR_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign,
    ast.Expr, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Dict, ast.List,
    ast.Tuple, ast.Subscript, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub,
    ast.Mult, ast.Div, ast.Pow, ast.USub, ast.Call, ast.Attribute, ast.keyword,
    ast.Compare, ast.If, ast.IfExp, ast.For, ast.comprehension, ast.ListComp,
    ast.DictComp, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq,
)


class PortfolioComposer:
    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        strategies: Optional[StrategyRepository] = None,
    ) -> None:
        self.store = store or SQLiteStore()
        self.strategies = strategies or StrategyRepository(self.store)

    def create(
        self,
        strategy_ids: list[str],
        weight_scheme: str = "equal_weight",
        name: str = "Untitled Portfolio",
        allocator_code: Optional[str] = None,
        custom_weights: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        if not 2 <= len(strategy_ids) <= 10:
            raise ValueError("composition requires between 2 and 10 strategies")
        if len(set(strategy_ids)) != len(strategy_ids):
            raise ValueError("strategy_ids must be unique")
        records: list[dict[str, Any]] = []
        for strategy_id in strategy_ids:
            try:
                record = self.strategies.get(strategy_id)
            except KeyError as exc:
                raise ValueError(f"unknown strategy_id '{strategy_id}'") from exc
            source_path = Path(str(record.get("file_path", "")))
            if not source_path.is_file():
                raise FileNotFoundError(f"strategy source missing: {source_path}")
            records.append(record)
        scheme = weight_scheme.lower().replace("-", "_")
        if scheme not in {"equal", "equal_weight", "risk_parity", "custom"}:
            raise ValueError("weight_scheme must be equal_weight, risk_parity, or custom")
        if custom_weights is not None and scheme != "custom":
            raise ValueError("custom_weights require weight_scheme='custom'")
        if scheme == "custom" and not allocator_code and not custom_weights:
            raise ValueError("custom composition requires allocator_code or custom_weights")
        normalized_weights = (
            self._validate_weights(custom_weights, strategy_ids)
            if custom_weights is not None
            else None
        )
        composition_id = f"comp_{uuid.uuid4().hex[:12]}"
        namespace_map = {
            strategy_id: f"strat_{index}" for index, strategy_id in enumerate(strategy_ids)
        }
        payload = {
            "composition_id": composition_id,
            "portfolio_name": name.strip() or composition_id,
            "strategy_ids": list(strategy_ids),
            "strategies": [
                {"id": row["strategy_id"], "name": row["name"]} for row in records
            ],
            "weight_scheme": scheme,
            "namespace_map": namespace_map,
            "namespace_keys": [
                f"{prefix}_positions" for prefix in namespace_map.values()
            ],
            "allocator_code": allocator_code,
            "custom_weights": normalized_weights,
            "last_execution_at": None,
            "last_result_id": None,
        }
        return self.store.put("compositions", composition_id, payload, create_only=True)

    def get(self, composition_id: str) -> dict[str, Any]:
        return self.store.get("compositions", composition_id)

    @staticmethod
    def _load_strategy(record: dict[str, Any]) -> ModuleType:
        path = Path(record["file_path"])
        if not path.exists():
            raise FileNotFoundError(f"strategy source missing: {path}")
        spec = importlib.util.spec_from_file_location(f"studio_strategy_{record['strategy_id']}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load strategy source: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not callable(getattr(module, "generate_signals", None)):
            raise ValueError(f"strategy '{record['strategy_id']}' has no generate_signals()")
        return module

    @staticmethod
    def _coerce_market_data(market_data: Any) -> pd.DataFrame:
        if isinstance(market_data, pd.DataFrame):
            frame = market_data.copy()
        elif isinstance(market_data, dict):
            frame = pd.DataFrame(market_data)
        elif isinstance(market_data, list):
            frame = pd.DataFrame(market_data)
            if {"date", "ticker", "close"}.issubset(frame.columns):
                frame = frame.pivot(index="date", columns="ticker", values="close")
        else:
            raise ValueError("market_data must be a date x ticker mapping or records")
        if frame.empty:
            raise ValueError("market_data cannot be empty")
        if "date" in frame.columns:
            frame = frame.set_index("date")
        frame.index = pd.to_datetime(frame.index)
        return frame.sort_index().apply(pd.to_numeric, errors="coerce")

    @staticmethod
    def _equal_weight(strategy_ids: list[str]) -> dict[str, float]:
        weight = 1.0 / len(strategy_ids)
        return {strategy_id: weight for strategy_id in strategy_ids}

    @staticmethod
    def _risk_parity(return_series: dict[str, pd.Series]) -> dict[str, float]:
        variances = {
            key: float(pd.Series(value).dropna().var(ddof=1))
            for key, value in return_series.items()
        }
        inverse_vol = {
            key: 1.0 / math.sqrt(value) if np.isfinite(value) and value > 1e-12 else 0.0
            for key, value in variances.items()
        }
        total = sum(inverse_vol.values())
        if total <= 0:
            return PortfolioComposer._equal_weight(list(return_series))
        return {key: value / total for key, value in inverse_vol.items()}

    @staticmethod
    def _validate_weights(weights: dict[str, Any], strategy_ids: list[str]) -> dict[str, float]:
        if set(weights) != set(strategy_ids):
            raise ValueError("allocator weights must contain every strategy exactly once")
        resolved = {key: float(value) for key, value in weights.items()}
        if not all(np.isfinite(value) and value >= 0 for value in resolved.values()):
            raise ValueError("allocator weights must be finite and non-negative")
        total = sum(resolved.values())
        if total <= 0:
            raise ValueError("allocator weights must have positive gross weight")
        return {key: value / total for key, value in resolved.items()}

    def _custom_allocator(
        self,
        code: str,
        context: dict[str, Any],
        strategy_ids: list[str],
    ) -> dict[str, float]:
        tree = ast.parse(code, mode="exec")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_ALLOCATOR_NODES):
                raise ValueError(f"allocator contains unsupported syntax: {type(node).__name__}")
            if isinstance(node, ast.Attribute) and str(node.attr).startswith("_"):
                raise ValueError("private attribute access is not allowed")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError("dunder names are not allowed")
        globals_dict = {"np": np, "pd": pd, "__builtins__": {"len": len, "sum": sum, "min": min, "max": max, "abs": abs, "float": float, "dict": dict}}
        locals_dict: dict[str, Any] = {}
        exec(compile(tree, "<allocator>", "exec"), globals_dict, locals_dict)
        allocator = locals_dict.get("allocate")
        if not callable(allocator):
            raise ValueError("custom allocator must define allocate(context)")
        return self._validate_weights(allocator(context), strategy_ids)

    def execute(
        self,
        composition_id: str,
        market_data: Any,
        *,
        strategy_configs: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        composition = self.get(composition_id)
        prices = self._coerce_market_data(market_data)
        configs = strategy_configs or {}
        individual: dict[str, Any] = {}
        return_series: dict[str, pd.Series] = {}
        signal_frames: dict[str, pd.DataFrame] = {}
        asset_returns = prices.pct_change().fillna(0.0)

        for strategy_id in composition["strategy_ids"]:
            record = self.strategies.get(strategy_id)
            module = self._load_strategy(record)
            config = {**record.get("default_config", {}), **configs.get(strategy_id, {})}
            signals = module.generate_signals(prices.copy(), config)
            signals = pd.DataFrame(signals).reindex_like(prices).fillna(0.0)
            strategy_returns = (signals.shift(1).fillna(0.0) * asset_returns).sum(axis=1)
            namespace = composition["namespace_map"][strategy_id]
            signal_frames[strategy_id] = signals
            return_series[strategy_id] = strategy_returns
            individual[namespace] = {
                "strategy_id": strategy_id,
                "name": record["name"],
                "positions": signals.to_dict(orient="index"),
                "returns": strategy_returns.to_dict(),
                "variables": {
                    f"{namespace}_positions": signals.to_dict(orient="index"),
                    f"{namespace}_signals": signals.to_dict(orient="index"),
                },
            }

        scheme = composition["weight_scheme"]
        if composition.get("custom_weights"):
            weights = self._validate_weights(composition["custom_weights"], composition["strategy_ids"])
        elif scheme == "risk_parity":
            weights = self._risk_parity(return_series)
        elif scheme == "custom":
            context = {
                "returns": pd.DataFrame(return_series),
                "signals": signal_frames,
                "strategy_ids": composition["strategy_ids"],
            }
            weights = self._custom_allocator(
                composition["allocator_code"], context, composition["strategy_ids"]
            )
        else:
            weights = self._equal_weight(composition["strategy_ids"])

        combined_returns = sum(return_series[key] * weights[key] for key in composition["strategy_ids"])
        combined_positions = sum(signal_frames[key] * weights[key] for key in composition["strategy_ids"])
        result_id = f"comp_run_{uuid.uuid4().hex[:12]}"
        result = {
            "result_id": result_id,
            "composition_id": composition_id,
            "executed_at": utc_now(),
            "individual": individual,
            "combined": {
                "weights": weights,
                "returns": combined_returns.to_dict(),
                "positions": combined_positions.to_dict(orient="index"),
                "equity_curve": (1.0 + combined_returns).cumprod().to_dict(),
            },
        }
        self.store.put("composition_results", result_id, result, create_only=True)
        composition["last_execution_at"] = result["executed_at"]
        composition["last_result_id"] = result_id
        self.store.put("compositions", composition_id, composition)
        return result
