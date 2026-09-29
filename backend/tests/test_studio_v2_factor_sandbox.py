from __future__ import annotations

import os
import time
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from app.studio_v2.factors import composite_combiner as composite_module
from app.studio_v2.factors.composite_combiner import CompositeFactorCombiner
from app.studio_v2.factors.evaluator import (
    DEFAULT_FACTOR_SANDBOX_LIMITS,
    FactorExpressionEvaluator,
    FactorSandboxError,
    FactorSandboxLimitError,
    FactorSandboxTimeoutError,
    FactorSandboxValidationError,
    _frame_memory_bytes,
    _run_in_factor_sandbox,
    _validate_input_frames,
)


def _sleeping_worker(delay: float) -> str:
    time.sleep(delay)
    return "finished"


@pytest.fixture()
def factor_data() -> dict[str, pd.DataFrame]:
    index = pd.date_range("2024-01-01", periods=8, freq="B")
    close = pd.DataFrame(
        {
            "AAA": np.linspace(100.0, 108.0, len(index)),
            "BBB": np.linspace(80.0, 76.0, len(index)),
        },
        index=index,
    )
    return {
        "close": close,
        "volume": pd.DataFrame(1_000.0, index=index, columns=close.columns),
        "returns": close.pct_change(fill_method=None),
    }


@pytest.mark.parametrize(
    "expression",
    [
        "np.load('/tmp/factor.npy')",
        "np.__dict__",
        "pd.read_pickle('/tmp/factor.pkl')",
        "close.to_pickle('/tmp/factor.pkl')",
        "close.__class__",
        "getattr(close, '__class__')",
        "__import__('os').system('id')",
        "().__class__.__base__.__subclasses__()",
        "[value for value in close]",
        "(lambda value: value)(close)",
    ],
)
def test_expression_sandbox_rejects_escape_and_io_surfaces(expression: str) -> None:
    result = FactorExpressionEvaluator().validate_expression(expression)

    assert result.valid is False
    assert result.errors


@pytest.mark.parametrize(
    "expression",
    [
        "cs_rank(ts_mean(close, 3))",
        "np.where(returns > 0, np.log1p(np.abs(returns)), 0.0)",
        "close.pct_change().rolling(3).mean().fillna(0.0)",
        "pd.notna(close).where(close > 0, False)",
    ],
)
def test_expression_sandbox_preserves_curated_numpy_and_pandas_operations(
    expression: str,
) -> None:
    result = FactorExpressionEvaluator().validate_expression(expression)

    assert result.valid is True
    assert result.errors == []


@pytest.mark.parametrize(
    "expression",
    [
        "[0] * 1000000",
        "1000000 * ('x',)",
        "close ** (16 ** 16)",
        "np.power(close, 16 ** 16)",
        "close.pow(16 ** 16)",
    ],
)
def test_expression_sandbox_rejects_sequence_and_exponent_amplification(
    expression: str,
) -> None:
    result = FactorExpressionEvaluator().validate_expression(expression)

    assert result.valid is False
    assert any("amplification" in error for error in result.errors)


def test_custom_combiner_rejects_aliased_sequence_repetition() -> None:
    code = """def combine(factors_dict):
    payload = [0]
    alias = payload
    return alias * 1000000
"""

    with pytest.raises(FactorSandboxValidationError, match="sequence amplification"):
        CompositeFactorCombiner().combine(
            {"value": [1.0, 2.0], "momentum": [2.0, 1.0]},
            weighting="custom",
            custom_code=code,
        )


@pytest.mark.parametrize(
    "expression",
    [
        "cs_rank(ts_mean(np.log1p(close), 3))",
        "close.pct_change().rolling(3).mean().fillna(0.0)",
    ],
)
def test_expression_evaluation_runs_in_bounded_sandbox(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
    expression: str,
) -> None:
    evaluator = FactorExpressionEvaluator()
    monkeypatch.setattr(evaluator, "load_data", lambda *_args: factor_data)

    result = evaluator.evaluate(
        expression,
        ["AAA", "BBB"],
        "2024-01-01",
        "2024-01-31",
    )

    assert result.validation.valid is True
    assert result.scores.shape == factor_data["close"].shape
    assert np.isfinite(result.scores.to_numpy()).all()


def test_vix_is_discovered_and_loaded_for_expression_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
) -> None:
    evaluator = FactorExpressionEvaluator()

    def load_data(fields, *_args):
        assert "vix" in fields
        return {**factor_data, "vix": factor_data["close"] * 0 + 18.0}

    monkeypatch.setattr(evaluator, "load_data", load_data)
    result = evaluator.evaluate("vix", ["AAA", "BBB"], "2024-01-01", "2024-01-31")

    assert result.validation.valid is True
    assert (result.scores == 18.0).all().all()


def test_factor_data_loading_occurs_inside_timed_worker(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
) -> None:
    evaluator = FactorExpressionEvaluator()
    parent_pid = os.getpid()

    def load_data(*_args):
        return {
            **factor_data,
            "volume": factor_data["volume"] * 0 + float(os.getpid()),
        }

    monkeypatch.setattr(evaluator, "load_data", load_data)
    result = evaluator.evaluate("volume", ["AAA", "BBB"], "2024-01-01", "2024-01-31")

    assert result.validation.valid is True
    assert result.scores.iat[0, 0] != float(parent_pid)


def test_vectorized_time_series_rank_matches_reference() -> None:
    frame = pd.DataFrame(
        {"AAA": [3.0, 1.0, 4.0, 2.0], "BBB": [2.0, 2.0, 1.0, 5.0]}
    )
    evaluator = FactorExpressionEvaluator()
    expected = frame.rolling(3, min_periods=1).apply(
        lambda values: pd.Series(values).rank(pct=True).iloc[-1],
        raw=False,
    )

    actual = evaluator._compute_time_series_operator("ts_rank", frame, 3)

    pd.testing.assert_frame_equal(actual, expected)


def test_expression_source_ast_input_and_output_limits_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
) -> None:
    source_limited = FactorExpressionEvaluator(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_source_bytes=8)
    )
    source = source_limited.validate_expression("ts_mean(close, 20)")
    assert source.valid is False
    assert "source size limit" in source.errors[0]

    ast_limited = FactorExpressionEvaluator(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_ast_nodes=5)
    )
    ast_result = ast_limited.validate_expression("close + volume")
    assert ast_result.valid is False
    assert "AST node limit" in ast_result.errors[0]

    depth_limited = FactorExpressionEvaluator(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_ast_depth=5)
    )
    depth_result = depth_limited.validate_expression("np.abs(np.abs(close))")
    assert depth_result.valid is False
    assert "AST depth limit" in depth_result.errors[0]

    input_limited = FactorExpressionEvaluator(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_input_cells=4)
    )
    monkeypatch.setattr(input_limited, "load_data", lambda *_args: factor_data)
    input_result = input_limited.evaluate(
        "close", ["AAA", "BBB"], "2024-01-01", "2024-01-31"
    )
    assert input_result.validation.valid is False
    assert "input cell limit" in input_result.validation.errors[0]

    output_limited = FactorExpressionEvaluator(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_output_cells=4)
    )
    monkeypatch.setattr(output_limited, "load_data", lambda *_args: factor_data)
    output_result = output_limited.evaluate(
        "close", ["AAA", "BBB"], "2024-01-01", "2024-01-31"
    )
    assert output_result.validation.valid is False
    assert "output cell limit" in output_result.validation.errors[0]

    byte_limited = FactorExpressionEvaluator(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_output_bytes=1)
    )
    monkeypatch.setattr(byte_limited, "load_data", lambda *_args: factor_data)
    byte_result = byte_limited.evaluate(
        "close", ["AAA", "BBB"], "2024-01-01", "2024-01-31"
    )
    assert byte_result.validation.valid is False
    assert "output byte limit" in byte_result.validation.errors[0]


def test_input_byte_accounting_includes_dataframe_column_index() -> None:
    columns = pd.Index([f"column-{index}-{'x' * 128}" for index in range(64)])
    frame = pd.DataFrame(np.zeros((1, len(columns))), columns=columns)
    pandas_reported = int(frame.memory_usage(index=True, deep=True).sum())
    with_columns = _frame_memory_bytes(frame)
    assert with_columns > pandas_reported

    limits = replace(
        DEFAULT_FACTOR_SANDBOX_LIMITS,
        max_input_bytes=pandas_reported + 1,
    )
    with pytest.raises(FactorSandboxLimitError, match="input byte limit"):
        _validate_input_frames({"factors": frame}, limits, "custom factor code")


def test_sandbox_timeout_terminates_worker_deterministically() -> None:
    limits = replace(DEFAULT_FACTOR_SANDBOX_LIMITS, timeout_seconds=0.03)
    started = time.monotonic()

    with pytest.raises(FactorSandboxTimeoutError, match="timed out"):
        _run_in_factor_sandbox(_sleeping_worker, (0.5,), limits, "test factor")

    assert time.monotonic() - started < 0.5


def test_custom_combiner_preprocessing_is_covered_by_worker_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = replace(DEFAULT_FACTOR_SANDBOX_LIMITS, timeout_seconds=0.04)
    factors = {"value": [1.0, 2.0, 3.0], "momentum": [3.0, 2.0, 1.0]}
    real_dataframe = pd.DataFrame

    def slow_dataframe(*args, **kwargs):
        time.sleep(0.4)
        return real_dataframe(*args, **kwargs)

    monkeypatch.setattr(composite_module.pd, "DataFrame", slow_dataframe)
    started = time.monotonic()

    with pytest.raises(FactorSandboxTimeoutError, match="timed out"):
        CompositeFactorCombiner(limits).combine(
            factors,
            weighting="custom",
            custom_code="def combine(factors_dict):\n    return factors_dict['value']\n",
        )

    assert time.monotonic() - started < 0.3


@pytest.mark.parametrize(
    "code",
    [
        "import os\ndef combine(factors_dict):\n    return factors_dict['value']\n",
        "def combine(factors_dict):\n    return np.load('/tmp/factor.npy')\n",
        "def combine(factors_dict):\n    return pd.read_pickle('/tmp/factor.pkl')\n",
        "def combine(factors_dict):\n    return factors_dict['value'].to_pickle('/tmp/x')\n",
        "def combine(factors_dict):\n    return factors_dict['value'].__class__\n",
        "def combine(factors_dict):\n    return __import__('os')\n",
        "def combine(factors_dict):\n    return ().__class__.__base__.__subclasses__()\n",
        "def combine(factors_dict=__import__('os')):\n    return factors_dict\n",
        "def combine(factors_dict):\n    return [x for x in factors_dict['value']]\n",
        "def combine(factors_dict)\n    return factors_dict['value']\n",
    ],
)
def test_custom_combiner_rejects_escape_and_io_surfaces(code: str) -> None:
    factors = {"value": [1.0, 2.0, 3.0], "momentum": [3.0, 2.0, 1.0]}

    with pytest.raises(FactorSandboxValidationError):
        CompositeFactorCombiner().combine(
            factors,
            weighting="custom",
            custom_code=code,
        )


def test_custom_combiner_preserves_vectorized_numpy_and_pandas_operations() -> None:
    factors = {
        "value": [1.0, 2.0, 4.0, 8.0],
        "momentum": [4.0, 3.0, 2.0, 1.0],
    }
    code = """def combine(factors_dict):
    score = np.log1p(np.abs(factors_dict["value"])) - factors_dict["momentum"]
    return score.rank(pct=True).fillna(0.0)
"""

    result = CompositeFactorCombiner().combine(
        factors,
        weighting="custom",
        custom_code=code,
    )

    assert len(result["composite_score"]) == 4
    assert result["composite_score"].between(0.0, 1.0).all()


def test_custom_combiner_requires_code_and_enforces_shared_limits() -> None:
    factors = {"value": [1.0, 2.0, 3.0], "momentum": [3.0, 2.0, 1.0]}

    with pytest.raises(FactorSandboxValidationError, match="requires custom_code"):
        CompositeFactorCombiner().combine(factors, weighting="custom")

    source_limited = CompositeFactorCombiner(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_source_bytes=16)
    )
    with pytest.raises(FactorSandboxLimitError, match="source size limit"):
        source_limited.combine(
            factors,
            weighting="custom",
            custom_code="def combine(factors_dict):\n    return factors_dict['value']\n",
        )

    ast_limited = CompositeFactorCombiner(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_ast_nodes=5)
    )
    with pytest.raises(FactorSandboxLimitError, match="AST node limit"):
        ast_limited.combine(
            factors,
            weighting="custom",
            custom_code="def combine(factors_dict):\n    return factors_dict['value']\n",
        )

    input_limited = CompositeFactorCombiner(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_input_cells=2)
    )
    with pytest.raises(FactorSandboxLimitError, match="input cell limit"):
        input_limited.combine(
            factors,
            weighting="custom",
            custom_code="def combine(factors_dict):\n    return factors_dict['value']\n",
        )

    output_limited = CompositeFactorCombiner(
        replace(DEFAULT_FACTOR_SANDBOX_LIMITS, max_output_cells=2)
    )
    with pytest.raises(FactorSandboxLimitError, match="output cell limit"):
        output_limited.combine(
            factors,
            weighting="custom",
            custom_code="def combine(factors_dict):\n    return factors_dict['value']\n",
        )


def test_factor_entry_points_surface_consistent_timeout_errors(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
) -> None:
    limits = replace(DEFAULT_FACTOR_SANDBOX_LIMITS, timeout_seconds=0.0)
    evaluator = FactorExpressionEvaluator(limits)
    monkeypatch.setattr(evaluator, "load_data", lambda *_args: factor_data)

    expression_result = evaluator.evaluate(
        "close", ["AAA", "BBB"], "2024-01-01", "2024-01-31"
    )
    assert expression_result.validation.valid is False
    assert "timed out" in expression_result.validation.errors[0]

    with pytest.raises(FactorSandboxTimeoutError, match="timed out"):
        CompositeFactorCombiner(limits).combine(
            {"value": [1.0, 2.0], "momentum": [2.0, 1.0]},
            weighting="custom",
            custom_code="def combine(factors_dict):\n    return factors_dict['value']\n",
        )


def test_factor_entry_points_normalize_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
) -> None:
    evaluator = FactorExpressionEvaluator()
    monkeypatch.setattr(evaluator, "load_data", lambda *_args: factor_data)

    expression_result = evaluator.evaluate(
        "close['MISSING']", ["AAA", "BBB"], "2024-01-01", "2024-01-31"
    )
    assert expression_result.validation.valid is False
    assert expression_result.validation.errors[0].startswith(
        "factor expression failed: KeyError:"
    )

    with pytest.raises(
        FactorSandboxError, match="custom factor code failed: KeyError:"
    ):
        CompositeFactorCombiner().combine(
            {"value": [1.0, 2.0], "momentum": [2.0, 1.0]},
            weighting="custom",
            custom_code=(
                "def combine(factors_dict):\n"
                "    return factors_dict['MISSING']\n"
            ),
        )


def test_factor_entry_points_reject_non_numeric_outputs(
    monkeypatch: pytest.MonkeyPatch,
    factor_data: dict[str, pd.DataFrame],
) -> None:
    evaluator = FactorExpressionEvaluator()
    monkeypatch.setattr(evaluator, "load_data", lambda *_args: factor_data)

    expression_result = evaluator.evaluate(
        "close.replace(100.0, 'not-numeric')",
        ["AAA", "BBB"],
        "2024-01-01",
        "2024-01-31",
    )
    assert expression_result.validation.valid is False
    assert "must return a numeric table" in expression_result.validation.errors[0]

    with pytest.raises(
        FactorSandboxValidationError,
        match="must return one numeric score per observation",
    ):
        CompositeFactorCombiner().combine(
            {"value": [1.0, 2.0], "momentum": [2.0, 1.0]},
            weighting="custom",
            custom_code=(
                "def combine(factors_dict):\n"
                "    return 'not-numeric'\n"
            ),
        )
