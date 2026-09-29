from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pandas as pd
from fastapi import FastAPI

from app.studio_v2.optimizer.multi_objective import ParetoOptimizer
from app.studio_v2.optimizer.search import BayesianOptimizer, OptimizerResult
from app.studio_v2.optimizer.verdict import TrialRegistry
from app.studio_v2.router import Router
from app.studio_v2.shared.persistence import SQLiteStore


def test_optimizer_registry_persists_study_and_trials_across_store_instances(
    tmp_path: Path,
) -> None:
    database = tmp_path / "optimizer.sqlite3"
    first = TrialRegistry(SQLiteStore(database))
    study = first.start_study(
        session_id="research-session",
        mode="bayesian",
        strategy_file_hash="strategy-hash",
        objective_directions={"sharpe": "maximize"},
        configuration={"trial_budget": 2},
    )
    result = {
        "trials": [
            {"trial_id": 0, "lookback": 10, "objective": 0.8},
            {"trial_id": 1, "lookback": 20, "objective": 1.1},
        ],
        "best_params": {"lookback": 20},
        "best_value": 1.1,
    }
    first.persist_output(
        study["study_id"], result, parameter_names=["lookback"]
    )

    reloaded = TrialRegistry(SQLiteStore(database))
    persisted = reloaded.get_study(study["study_id"])
    trials = reloaded.get_session_trials("research-session")

    assert persisted["status"] == "completed"
    assert persisted["trial_count"] == 2
    assert persisted["result"] == result
    assert {trial.trial_number for trial in trials} == {0, 1}
    assert {trial.parameter_dict["lookback"] for trial in trials} == {10, 20}
    assert reloaded.get_best_trial("strategy-hash", "sharpe").objective_value == 1.1


def test_optimizer_search_outputs_and_typed_reads_persist_across_routers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(tmp_path / "router.sqlite3"))

    def fake_bayesian_run(self, config):
        trials = pd.DataFrame([
            {"trial_id": 0, "lookback": 10, "objective": 0.7},
            {"trial_id": 1, "lookback": 30, "objective": 1.2},
        ])
        return OptimizerResult(
            trials=trials,
            best_params={"lookback": 30},
            best_value=1.2,
            perturbation_results=pd.DataFrame(),
            stability_score=0.75,
            trajectory=[],
        )

    def fake_pareto_optimize(self, config, objectives):
        trials = [
            {"trial_id": 0, "lookback": 12, "return": 0.12, "risk": 0.08},
            {"trial_id": 1, "lookback": 24, "return": 0.16, "risk": 0.11},
        ]
        return {
            "trials": trials,
            "frontier": trials,
            "objectives": objectives,
            "frontier_size": 2,
            "hypervolume": 0.5,
            "hypervolume_progression": [{"trial": 1, "hypervolume": 0.5}],
            "method": "optuna_multi_objective_tpe",
        }

    monkeypatch.setattr(BayesianOptimizer, "run", fake_bayesian_run)
    monkeypatch.setattr(ParetoOptimizer, "optimize", fake_pareto_optimize)

    writer_app = FastAPI()
    writer_app.include_router(Router())

    async def write_and_read() -> None:
        writer_transport = httpx.ASGITransport(
            app=writer_app, raise_app_exceptions=False
        )
        async with httpx.AsyncClient(
            transport=writer_transport, base_url="http://writer"
        ) as client:
            bayesian = await client.post("/api/v2/optimizer/bayesian-search", json={
                "session_id": "persistent-session",
                "parameters": [{
                    "name": "lookback",
                    "type": "continuous",
                    "current_value": 20,
                    "suggested_range": [5, 40],
                }],
                "trial_budget": 2,
                "objective": "sharpe",
            })
            assert bayesian.status_code == 200, bayesian.text
            bayesian_id = bayesian.json()["study_id"]

            pareto = await client.post("/api/v2/optimizer/bayesian-search", json={
                "session_id": "persistent-session",
                "parameters": [{
                    "name": "lookback",
                    "type": "continuous",
                    "current_value": 20,
                    "suggested_range": [5, 40],
                }],
                "trial_budget": 2,
                "objectives": {"return": "max", "risk": "min"},
            })
            assert pareto.status_code == 200, pareto.text
            pareto_id = pareto.json()["study_id"]

        reader_app = FastAPI()
        reader_app.include_router(Router())
        reader_transport = httpx.ASGITransport(
            app=reader_app, raise_app_exceptions=False
        )
        async with httpx.AsyncClient(
            transport=reader_transport, base_url="http://reader"
        ) as client:
            studies = await client.get(
                "/api/v2/optimizer/studies",
                params={"session_id": "persistent-session"},
            )
            assert studies.status_code == 200, studies.text
            assert {row["study_id"] for row in studies.json()} == {
                bayesian_id, pareto_id
            }
            assert all(row["status"] == "completed" for row in studies.json())

            detail = await client.get(f"/api/v2/optimizer/studies/{pareto_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["result"]["frontier_size"] == 2

            trials = await client.get("/api/v2/optimizer/trials", params={
                "session_id": "persistent-session", "study_id": pareto_id,
            })
            assert trials.status_code == 200, trials.text
            assert len(trials.json()) == 2
            assert trials.json()[0]["mode"] == "pareto"
            assert set(trials.json()[0]["objective_values"]) == {"return", "risk"}

    asyncio.run(write_and_read())


def test_failed_optimizer_study_remains_auditable_after_router_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(tmp_path / "failed.sqlite3"))

    def fail_search(self, config):
        raise RuntimeError("optimizer worker unavailable")

    monkeypatch.setattr(BayesianOptimizer, "run", fail_search)
    writer_app = FastAPI()
    writer_app.include_router(Router())

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=writer_app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://writer"
        ) as client:
            response = await client.post("/api/v2/optimizer/bayesian-search", json={
                "session_id": "failed-session",
                "parameters": [{
                    "name": "lookback", "current_value": 20,
                    "suggested_range": [5, 40],
                }],
                "trial_budget": 1,
            })
            assert response.status_code == 409

        reader_app = FastAPI()
        reader_app.include_router(Router())
        reader_transport = httpx.ASGITransport(
            app=reader_app, raise_app_exceptions=False
        )
        async with httpx.AsyncClient(
            transport=reader_transport, base_url="http://reader"
        ) as client:
            studies = await client.get("/api/v2/optimizer/studies", params={
                "session_id": "failed-session", "status": "failed",
            })
            assert studies.status_code == 200
            assert len(studies.json()) == 1
            assert studies.json()[0]["error"].startswith("RuntimeError:")

    asyncio.run(exercise())
