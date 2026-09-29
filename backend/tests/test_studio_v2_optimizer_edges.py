from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.studio_v2.optimizer.cross_validation import OptimizerCrossValidation
from app.studio_v2.optimizer.ensemble import ParameterEnsemble
from app.studio_v2.optimizer.multi_objective import ParetoOptimizer
from app.studio_v2.optimizer.search import BayesianOptimizer, OptimizerConfig, SearchParameter
from app.studio_v2.optimizer.verdict import TrialRegistry
from app.studio_v2.shared.persistence import SQLiteStore


def test_preferred_region_comparison_handles_empty_and_disjoint_regions() -> None:
    validator = OptimizerCrossValidation()

    empty = validator.compare_regions([], [])
    assert empty["verdict"] == "insufficient"
    assert empty["overlap_percentage"] == 0.0
    assert empty["overlay"] == []
    assert not empty["comparable"]

    trials = [
        {"trial_id": "a", "lookback": 10, "objective": 2.0},
        {"trial_id": "a-duplicate", "lookback": 10, "objective": 1.9},
        {"trial_id": "b", "lookback": 20, "objective": 1.5},
        {"trial_id": "failed", "lookback": 30, "objective": 100.0, "state": "failed"},
        {"trial_id": "nan", "lookback": 40, "objective": np.nan},
    ]
    windows = [
        {"optimal_params": {"lookback": 50}},
        {"optimal_params": {"lookback": 60}},
        {"optimal_params": {"lookback": 60}},
    ]

    disjoint = validator.compare_regions(trials, windows, top_fraction=1.0)
    assert disjoint["verdict"] == "divergent"
    assert disjoint["overlap_percentage"] == 0.0
    assert disjoint["bayesian_region_size"] == 2
    assert disjoint["walk_forward_region_size"] == 2
    assert disjoint["intersection_size"] == 0
    assert len(disjoint["overlay"]) == 4
    assert disjoint["comparable"]


def test_pareto_frontier_filters_duplicate_failed_and_nan_trials_with_mixed_directions() -> None:
    trials = [
        {"trial_id": "a", "lookback": 10, "return": 0.20, "risk": 0.20},
        {"trial_id": "a-duplicate", "lookback": 10, "return": 0.20, "risk": 0.20},
        {"trial_id": "b", "lookback": 20, "return": 0.15, "risk": 0.10},
        {"trial_id": "dominated", "lookback": 30, "return": 0.10, "risk": 0.30},
        {"trial_id": "failed", "lookback": 40, "return": 99.0, "risk": 0.0, "state": "failed"},
        {"trial_id": "nan", "lookback": 50, "return": np.nan, "risk": 0.05},
    ]

    result = ParetoOptimizer().frontier(trials, {"return": "maximize", "risk": "minimize"})

    assert {row["trial_id"] for row in result["frontier"]} == {"a", "b"}
    assert result["frontier_size"] == 2
    assert result["eligible_trial_count"] == 3
    assert result["duplicate_trial_count"] == 1
    assert result["failed_trial_count"] == 1
    assert result["invalid_objective_count"] == 1
    assert len(result["hypervolume_progression"]) == 3
    by_id = {row["trial_id"]: row for row in result["trials"]}
    assert by_id["a-duplicate"]["duplicate_of"] == "a"
    assert not by_id["failed"]["pareto_optimal"]
    assert not by_id["nan"]["valid_objectives"]


def test_pareto_frontier_returns_empty_result_when_every_trial_is_invalid() -> None:
    result = ParetoOptimizer().frontier(
        [
            {"trial_id": "failed", "return": 1.0, "risk": 0.1, "state": "failed"},
            {"trial_id": "nan", "return": np.nan, "risk": 0.2},
        ],
        {"return": "max", "risk": "min"},
    )

    assert result["frontier"] == []
    assert result["frontier_size"] == 0
    assert result["eligible_trial_count"] == 0
    assert result["hypervolume"] == 0.0
    assert result["hypervolume_progression"] == []


def test_multi_objective_search_continues_after_failed_and_nan_trials() -> None:
    calls = 0

    def evaluate(parameters: dict[str, float]) -> dict[str, float]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("bounded evaluator failure")
        if calls == 2:
            return {"return": np.nan, "risk": 0.2}
        x = float(parameters["lookback"])
        return {"return": x, "risk": x / 100.0}

    result = ParetoOptimizer().optimize(
        OptimizerConfig(
            parameters=[SearchParameter("lookback", current_value=10, suggested_range=(5, 15))],
            trial_budget=4,
            evaluate=evaluate,
        ),
        {"return": "max", "risk": "min"},
    )

    assert len(result["trials"]) == 4
    assert result["failed_trial_count"] == 2
    assert result["eligible_trial_count"] == 2
    assert all(row["state"] == "complete" for row in result["frontier"])


def test_bayesian_search_continues_after_failed_and_nan_trials() -> None:
    calls = 0

    def evaluate(parameters: dict[str, float]) -> float:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("bounded evaluator failure")
        if calls == 2:
            return np.nan
        if calls == 3:
            return 1.25
        return 1.0

    result = BayesianOptimizer().run(OptimizerConfig(
        parameters=[SearchParameter("lookback", current_value=10, suggested_range=(5, 15))],
        trial_budget=3,
        evaluate=evaluate,
    ))

    assert len(result.trials) == 3
    assert result.trials["state"].tolist() == ["failed", "failed", "complete"]
    assert result.trials["objective"].notna().sum() == 1
    assert result.best_value == pytest.approx(1.25)
    assert result.best_params


def test_bayesian_search_returns_an_empty_best_when_every_trial_fails() -> None:
    calls = 0

    def evaluate(parameters: dict[str, float]) -> float:
        nonlocal calls
        calls += 1
        raise RuntimeError("bounded evaluator failure")

    result = BayesianOptimizer().run(OptimizerConfig(
        parameters=[SearchParameter("lookback", current_value=10, suggested_range=(5, 15))],
        trial_budget=3,
        evaluate=evaluate,
    ))

    assert calls == 3
    assert result.trials["state"].tolist() == ["failed", "failed", "failed"]
    assert result.trials["objective"].isna().all()
    assert result.best_params == {}
    assert np.isnan(result.best_value)
    assert result.perturbation_results.empty
    assert result.stability_score == 0.0


def test_parameter_ensemble_excludes_failed_nan_and_duplicate_configurations() -> None:
    result = ParameterEnsemble().build([
        {"trial_id": "a", "lookback": 10, "objective": 2.0},
        {"trial_id": "a-duplicate", "lookback": 10, "objective": 1.9},
        {"trial_id": "b", "lookback": 20, "objective": 1.0},
        {"trial_id": "failed", "lookback": 30, "objective": 100.0, "state": "failed"},
        {"trial_id": "nan", "lookback": 40, "objective": np.nan},
    ], top_n=5)

    assert {row["trial_id"] for row in result["members"]} == {"a", "b"}
    assert result["distribution"]["count"] == 2
    assert sum(row["ensemble_weight"] for row in result["members"]) == pytest.approx(1.0)


def test_trial_registry_rejects_duplicate_ids_and_respects_mixed_directions(
    tmp_path: Path,
) -> None:
    registry = TrialRegistry(SQLiteStore(tmp_path / "optimizer-edges.sqlite3"))
    duplicate_study = registry.start_study(
        session_id="duplicates",
        mode="bayesian",
        strategy_file_hash="duplicate-hash",
        objective_directions={"sharpe": "maximize"},
    )
    with pytest.raises(ValueError, match="duplicate optimizer trial_id"):
        registry.persist_output(duplicate_study["study_id"], {
            "trials": [
                {"trial_id": 1, "lookback": 10, "objective": 1.0},
                {"trial_id": "1", "lookback": 20, "objective": 2.0},
            ]
        }, parameter_names=["lookback"])
    assert registry.list_trials(study_id=duplicate_study["study_id"]) == []

    study = registry.start_study(
        session_id="mixed",
        mode="pareto",
        strategy_file_hash="mixed-hash",
        objective_directions={"return": "maximize", "risk": "minimize"},
    )
    registry.persist_output(study["study_id"], {"trials": [
        {"trial_id": 0, "lookback": 10, "return": 0.20, "risk": 0.20},
        {"trial_id": 1, "lookback": 20, "return": 0.30, "risk": 0.40},
        {"trial_id": 2, "lookback": 30, "return": 99.0, "risk": 0.0, "state": "failed"},
        {"trial_id": 3, "lookback": 40, "return": np.nan, "risk": 0.05},
    ]}, parameter_names=["lookback"])

    persisted = registry.get_session_trials("mixed")
    assert len(persisted) == 4
    assert next(row for row in persisted if row.trial_number == 3).state == "invalid"
    assert registry.get_best_trial("mixed-hash", "return").trial_number == 1
    best_risk = registry.get_best_trial("mixed-hash", "risk")
    assert best_risk.trial_number == 0
    assert best_risk.objective_name == "risk"
    assert best_risk.objective_value == pytest.approx(0.20)
