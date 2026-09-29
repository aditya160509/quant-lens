from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.studio_v2.algorithm_lab.repository import StrategyRepository
from app.studio_v2.backtest.engine import SimulationResult
from app.studio_v2.contracts import (
    OptimizerCPCVRequest,
    OptimizerWalkForwardRequest,
)
from app.studio_v2.optimizer.validation import TemporalValidationService
from app.studio_v2.router import Router
from app.studio_v2.shared.persistence import SQLiteStore


TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "app/studio_v2/data/templates/time_series_momentum.py"
)


class _DeterministicEngine:
    calls: list[dict[str, Any]] = []

    def run(self, config: Any) -> SimulationResult:
        self.calls.append(dict(config.parameters))
        dates = pd.bdate_range(config.date_start, config.date_end)
        choice = int(config.parameters.get("choice", 1))
        trend = np.where(dates.year <= dates.year.min(), 1.0, -1.0)
        mean = np.where(choice == 1, trend, -trend) * 0.001
        returns = pd.Series(
            mean + np.sin(np.arange(len(dates), dtype=float)) * 0.002,
            index=dates,
            dtype=float,
        )
        nav = (1.0 + returns).cumprod() * float(config.initial_cash)
        return SimulationResult(
            pd.DataFrame(),
            returns,
            nav,
            pd.DataFrame(),
            pd.DataFrame(),
            config,
            0.001,
            [],
        )


def _base_payload(strategy_file: str) -> dict[str, Any]:
    return {
        "strategy_file": strategy_file,
        "backtest_config": {
            "universe_id": ["SPY", "QQQ"],
            "date_start": "2023-01-03",
            "date_end": "2024-06-28",
            "cost_model": "zero",
            "parameters": {"vol_window": 10},
        },
    }


def test_temporal_request_contracts_are_strict_and_combinatorially_bounded() -> None:
    base = _base_payload(str(TEMPLATE))
    with pytest.raises(ValidationError, match="28 combinatorial paths"):
        OptimizerCPCVRequest.model_validate({**base, "n_groups": 8, "k_test": 3})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OptimizerCPCVRequest.model_validate({**base, "unknown": True})
    with pytest.raises(ValidationError, match="exactly one"):
        OptimizerCPCVRequest.model_validate({"backtest_config": base["backtest_config"]})
    with pytest.raises(ValidationError, match="must be unique"):
        OptimizerWalkForwardRequest.model_validate({
            **base,
            "parameters": [
                {"name": "lookback", "current_value": 10},
                {"name": "lookback", "current_value": 20},
            ],
        })


def test_service_uses_stored_strategy_and_one_backtest_for_all_cpcv_paths(
    tmp_path: Path,
) -> None:
    repository = StrategyRepository(
        SQLiteStore(tmp_path / "strategies.sqlite3"),
        source_root=tmp_path / "strategy-files",
    )
    strategy = repository.create(
        "stored temporal strategy",
        "def generate_signals(data, config=None):\n    return {'SPY': 1.0}\n",
    )
    sessions = pd.bdate_range("2024-01-02", "2024-06-28")
    _DeterministicEngine.calls = []
    service = TemporalValidationService(
        repository,
        engine_factory=_DeterministicEngine,
        sessions_loader=lambda: sessions,
    )
    request = OptimizerCPCVRequest.model_validate({
        "strategy_id": strategy["strategy_id"],
        "backtest_config": {
            "universe_id": ["SPY"],
            "date_start": "2024-01-02",
            "date_end": "2024-06-28",
            "cost_model": "zero",
            "parameters": {"choice": 1},
        },
        "n_groups": 4,
        "k_test": 2,
        "purge_days": 5,
        "embargo_days": 2,
    })

    result = service.run_cpcv(request.model_dump(exclude_none=True))

    assert result["strategy_id"] == strategy["strategy_id"]
    assert result["n_splits"] == 6
    assert result["backtests_executed"] == 1
    assert len(_DeterministicEngine.calls) == 1
    assert all(path["observations"] >= 20 for path in result["paths"])
    assert all(path["train_observations"] < result["source_observations"] for path in result["paths"])
    assert result["pbo"] is None
    assert "competing" in result["pbo_reason"]


def test_walk_forward_precomputes_bounded_candidates_and_stitches_real_oos(
    tmp_path: Path,
) -> None:
    repository = StrategyRepository(
        SQLiteStore(tmp_path / "walk.sqlite3"),
        source_root=tmp_path / "walk-strategies",
    )
    strategy = repository.create(
        "walk temporal strategy",
        "def generate_signals(data, config=None):\n    return {'SPY': 1.0}\n",
    )
    sessions = pd.bdate_range("2023-01-03", "2024-06-28")
    _DeterministicEngine.calls = []
    service = TemporalValidationService(
        repository,
        engine_factory=_DeterministicEngine,
        sessions_loader=lambda: sessions,
    )
    request = OptimizerWalkForwardRequest.model_validate({
        "strategy_id": strategy["strategy_id"],
        "backtest_config": {
            "universe_id": ["SPY"],
            "date_start": "2023-01-03",
            "date_end": "2024-06-28",
            "cost_model": "zero",
        },
        "parameters": [{"name": "choice", "type": "discrete", "values": [1, 2]}],
        "is_months": 6,
        "oos_months": 3,
        "trials_per_window": 2,
        "max_windows": 6,
    })

    result = service.run_walk_forward(request.model_dump(exclude_none=True))

    assert result["candidate_count"] == 2
    assert result["backtests_executed"] == 2
    assert len(_DeterministicEngine.calls) == 2
    assert 2 <= result["window_count"] <= 6
    assert result["stitched_oos_curve"]
    assert len({point["date"] for point in result["stitched_oos_curve"]}) == len(
        result["stitched_oos_curve"]
    )
    assert all(window["oos_observations"] >= 5 for window in result["windows"])


def test_temporal_optimizer_routes_execute_real_master_universe_backtests(
    tmp_path: Path,
) -> None:
    studio_router = Router(store=SQLiteStore(tmp_path / "routes.sqlite3"))
    app = FastAPI()
    app.include_router(studio_router)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=30.0
        ) as client:
            cpcv = await client.post(
                "/api/v2/optimizer/cpcv",
                json={
                    "strategy_file": str(TEMPLATE),
                    "backtest_config": {
                        "universe_id": ["SPY", "QQQ"],
                        "date_start": "2024-01-02",
                        "date_end": "2024-06-28",
                        "cost_model": "zero",
                        "parameters": {"lookback": 20, "vol_window": 10},
                    },
                    "n_groups": 4,
                    "k_test": 2,
                    "purge_days": 5,
                    "embargo_days": 2,
                },
            )
            assert cpcv.status_code == 200, cpcv.text
            cpcv_body = cpcv.json()
            assert cpcv_body["n_splits"] == 6
            assert cpcv_body["source_observations"] >= 100
            assert len(cpcv_body["paths"]) == 6
            assert all(path["observations"] > 0 for path in cpcv_body["paths"])

            walk_forward = await client.post(
                "/api/v2/optimizer/walk-forward",
                json={
                    "strategy_file": str(TEMPLATE),
                    "backtest_config": {
                        "universe_id": ["SPY", "QQQ"],
                        "date_start": "2023-01-03",
                        "date_end": "2024-06-28",
                        "cost_model": "zero",
                        "parameters": {"vol_window": 10},
                    },
                    "parameters": [
                        {"name": "lookback", "type": "discrete", "values": [10, 20]}
                    ],
                    "is_months": 6,
                    "oos_months": 3,
                    "trials_per_window": 2,
                    "max_windows": 6,
                },
            )
            assert walk_forward.status_code == 200, walk_forward.text
            walk_body = walk_forward.json()
            assert walk_body["candidate_count"] == 2
            assert walk_body["backtests_executed"] == 2
            assert walk_body["window_count"] >= 2
            assert walk_body["stitched_oos_curve"]

            missing = await client.post(
                "/api/v2/optimizer/cpcv",
                json={"mode": "cpcv"},
            )
            assert missing.status_code == 422
            reversed_dates = await client.post(
                "/api/v2/optimizer/cpcv",
                json={
                    **_base_payload(str(TEMPLATE)),
                    "backtest_config": {
                        **_base_payload(str(TEMPLATE))["backtest_config"],
                        "date_start": "2024-06-28",
                        "date_end": "2024-01-02",
                    },
                },
            )
            assert reversed_dates.status_code == 422
            assert reversed_dates.json()["detail"]["code"] == "invalid_request"

        schema = app.openapi()
        for path, request_name, response_name in (
            ("/api/v2/optimizer/cpcv", "OptimizerCPCVRequest", "OptimizerCPCVResponse"),
            (
                "/api/v2/optimizer/walk-forward",
                "OptimizerWalkForwardRequest",
                "OptimizerWalkForwardResponse",
            ),
        ):
            operation = schema["paths"][path]["post"]
            assert operation["requestBody"]["content"]["application/json"][
                "schema"
            ]["$ref"].endswith(f"/{request_name}")
            assert operation["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["$ref"].endswith(f"/{response_name}")
            assert operation["responses"]["422"]["content"]["application/json"][
                "schema"
            ]["$ref"].endswith("/ErrorResponse")

    try:
        asyncio.run(exercise())
    finally:
        studio_router.robustness_jobs.shutdown()

