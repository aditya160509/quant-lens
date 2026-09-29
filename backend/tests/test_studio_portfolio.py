from __future__ import annotations

import asyncio

import httpx
import numpy as np
import pytest
from fastapi import FastAPI

from app.routers.studio import router
from app.services.studio.portfolio import PortfolioOptimizationError, optimize_portfolio


def _payload() -> dict:
    return {
        "assets": ["SPY", "TLT", "GLD"],
        "expected_returns": [0.08, 0.04, 0.05],
        "covariance": [
            [0.04, -0.002, 0.001],
            [-0.002, 0.01, 0.0005],
            [0.001, 0.0005, 0.0225],
        ],
        "current_weights": [0.5, 0.3, 0.2],
        "objective": "min_variance",
        "min_weight": 0.0,
        "max_weight": 0.7,
        "gross_leverage": 1.0,
        "cost_bps": 10,
    }


def test_portfolio_optimizer_reconciles_weights_trades_costs_and_risk() -> None:
    result = optimize_portfolio(_payload())

    weights = np.array(list(result["weights"].values()))
    trades = np.array(list(result["trades"].values()))
    contribution = np.array(list(result["risk_contribution"].values()))
    assert abs(weights.sum() - 1) < 1e-8
    assert np.all(weights >= -1e-10)
    assert np.all(weights <= 0.7 + 1e-10)
    assert np.allclose(trades, weights - np.array([0.5, 0.3, 0.2]))
    assert abs(contribution.sum() - 1) < 1e-8
    assert abs(result["metrics"]["estimated_cost_fraction"] - np.abs(trades).sum() * 0.001) < 1e-10
    assert result["frontier"]
    assert result["artifact_id"].startswith("portfolio_")


def test_portfolio_optimizer_explains_infeasible_bounds() -> None:
    payload = _payload()
    payload.update({"min_weight": 0.5, "max_weight": 0.7})
    try:
        optimize_portfolio(payload)
    except PortfolioOptimizationError as exc:
        assert "cannot satisfy" in str(exc)
    else:
        raise AssertionError("infeasible bounds must fail")


def test_portfolio_optimizer_derives_shrunk_model_from_observed_returns() -> None:
    payload = _payload()
    payload.update({
        "expected_returns": None,
        "covariance": None,
        "expected_return_model": "historical_mean",
        "covariance_model": "diagonal_shrinkage",
        "periods_per_year": 12,
        "shrinkage": 0.35,
        "return_observations": [
            [0.01, 0.002, 0.004], [-0.02, 0.006, 0.001], [0.015, -0.003, 0.008],
            [0.004, 0.002, -0.005], [0.009, 0.001, 0.003], [-0.005, 0.004, 0.002],
        ],
    })
    result = optimize_portfolio(payload)
    assert result["model"]["expected_returns"] == "historical_mean"
    assert result["model"]["covariance"] == "diagonal_shrinkage"
    assert result["model"]["observations"] == 6
    assert result["model"]["shrinkage"] == 0.35
    assert np.isfinite(result["model"]["condition_number"])


def test_portfolio_optimizer_enforces_generic_exposure_and_tracking_contracts() -> None:
    payload = _payload()
    payload.update({
        "objective": "tracking_error",
        "benchmark_weights": [0.4, 0.4, 0.2],
        "linear_constraints": [
            {"name": "equity sleeve", "coefficients": [1, 0, 0], "max": 0.45},
            {"name": "defensive sleeve", "coefficients": [0, 1, 1], "min": 0.55},
        ],
        "scenarios": [{"name": "risk-off", "shocks": [-0.2, 0.04, 0.06]}],
    })
    result = optimize_portfolio(payload)
    assert result["weights"]["SPY"] <= 0.45 + 1e-8
    assert result["weights"]["TLT"] + result["weights"]["GLD"] >= 0.55 - 1e-8
    assert result["metrics"]["tracking_error"] is not None
    assert [item["name"] for item in result["constraint_exposures"]] == ["equity sleeve", "defensive sleeve"]
    scenario = result["scenario_results"][0]
    expected_scenario = sum(result["weights"][asset] * shock for asset, shock in zip(result["assets"], [-0.2, 0.04, 0.06]))
    assert scenario["name"] == "risk-off"
    assert abs(scenario["portfolio_return"] - expected_scenario) < 1e-10


def test_portfolio_api_returns_typed_infeasibility() -> None:
    async def exercise() -> None:
        app = FastAPI()
        app.include_router(router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            good = await client.post("/studio/portfolio/optimize", json=_payload())
            assert good.status_code == 200
            assert good.json()["portfolio"]["metrics"]["net_weight"] == 1.0
            bad_payload = _payload()
            bad_payload["covariance"][0][1] = 0.5
            bad = await client.post("/studio/portfolio/optimize", json=bad_payload)
            assert bad.status_code == 422
            assert bad.json()["detail"]["code"] == "PORTFOLIO_INFEASIBLE"

    asyncio.run(exercise())


def test_portfolio_versions_recompute_persist_and_compare(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("STUDIO_V2_DB_PATH", str(tmp_path / "portfolio.sqlite3"))

    async def exercise() -> None:
        app = FastAPI()
        app.include_router(router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first_portfolio = optimize_portfolio(_payload())
            first = await client.post("/studio/portfolio/versions", json={
                "name": "Defensive baseline", "artifact_id": first_portfolio["artifact_id"], "inputs": _payload(),
            })
            assert first.status_code == 200, first.text
            first_id = first.json()["version"]["version_id"]

            changed_inputs = _payload()
            changed_inputs["objective"] = "max_return"
            second_portfolio = optimize_portfolio(changed_inputs)
            second = await client.post("/studio/portfolio/versions", json={
                "name": "Return tilt", "artifact_id": second_portfolio["artifact_id"], "inputs": changed_inputs,
            })
            second_id = second.json()["version"]["version_id"]

            versions = await client.get("/studio/portfolio/versions")
            assert versions.json()["versions"][0]["version_id"] in {first_id, second_id}
            loaded = await client.get(f"/studio/portfolio/versions/{first_id}")
            assert loaded.json()["version"]["portfolio"]["artifact_id"] == first_portfolio["artifact_id"]
            comparison = await client.get(f"/studio/portfolio/versions/{first_id}/compare/{second_id}")
            assert comparison.status_code == 200
            assert set(comparison.json()["comparison"]["weight_delta"]) == {"SPY", "TLT", "GLD"}

            mismatch = await client.post("/studio/portfolio/versions", json={
                "name": "Tampered", "artifact_id": first_portfolio["artifact_id"], "inputs": changed_inputs,
            })
            assert mismatch.status_code == 409
            assert mismatch.json()["detail"]["code"] == "PORTFOLIO_ARTIFACT_MISMATCH"

    asyncio.run(exercise())
