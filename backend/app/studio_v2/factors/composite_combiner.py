"""Cross-sectional composite factor construction."""

from __future__ import annotations

import ast
from typing import Any

import numpy as np
import pandas as pd

from .evaluator import (
    DEFAULT_FACTOR_SANDBOX_LIMITS,
    FactorSandboxLimits,
    FactorSandboxValidationError,
    _COMMON_EXPRESSION_NODES,
    _SAFE_METHOD_CALLS,
    _run_in_factor_sandbox,
    _validate_input_frames,
    _validate_output,
    _validate_safe_ast,
    _parse_bounded_source,
)


_SAFE_COMBINER_BUILTINS = {"abs", "len", "max", "min", "sum"}
_SAFE_COMBINER_METHODS = _SAFE_METHOD_CALLS | {"get", "items", "keys", "values"}
_CUSTOM_COMBINER_NODES = _COMMON_EXPRESSION_NODES + (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.AugAssign,
    ast.Expr,
    ast.If,
)


def _validate_custom_combiner(
    code: str, limits: FactorSandboxLimits
) -> ast.AST:
    try:
        tree = _parse_bounded_source(
            code,
            mode="exec",
            label="custom factor code",
            limits=limits,
        )
    except SyntaxError as exc:
        raise FactorSandboxValidationError(
            f"custom factor code syntax error: {exc.msg}"
        ) from exc
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or len(getattr(tree, "body", [])) != 1:
        raise FactorSandboxValidationError(
            "custom factor code must contain only combine(factors_dict)"
        )
    function = functions[0]
    positional = list(function.args.posonlyargs) + list(function.args.args)
    if (
        function.name != "combine"
        or [argument.arg for argument in positional] != ["factors_dict"]
        or function.args.vararg is not None
        or function.args.kwarg is not None
        or function.args.kwonlyargs
        or function.args.defaults
        or function.args.kw_defaults
        or function.decorator_list
        or function.returns is not None
    ):
        raise FactorSandboxValidationError(
            "custom factor code must define combine(factors_dict) without "
            "decorators, defaults, annotations, or variadic arguments"
        )
    if not any(isinstance(node, ast.Return) for node in ast.walk(function)):
        raise FactorSandboxValidationError("custom factor combine() must return a score")
    for node in ast.walk(function):
        if isinstance(node, ast.Expr) and not (
            isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        ):
            raise FactorSandboxValidationError(
                "custom factor code cannot execute standalone expressions"
            )
        if isinstance(node, ast.Assign) and any(
            not isinstance(target, ast.Name) for target in node.targets
        ):
            raise FactorSandboxValidationError(
                "custom factor code can assign only local variables"
            )
        if isinstance(node, ast.AugAssign) and not isinstance(node.target, ast.Name):
            raise FactorSandboxValidationError(
                "custom factor code can update only local variables"
            )
    local_names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    errors = _validate_safe_ast(
        tree,
        label="custom factor code",
        allowed_nodes=_CUSTOM_COMBINER_NODES,
        allowed_load_names={
            "factors_dict", "np", "pd", *_SAFE_COMBINER_BUILTINS, *local_names,
        },
        allowed_name_calls=_SAFE_COMBINER_BUILTINS,
        allowed_method_calls=_SAFE_COMBINER_METHODS,
    )
    if errors:
        raise FactorSandboxValidationError("; ".join(errors))
    return tree


def _custom_combiner_worker(
    normalized: pd.DataFrame,
    code: str,
    limits: FactorSandboxLimits,
) -> pd.Series:
    tree = _validate_custom_combiner(code, limits)
    scope: dict[str, Any] = {}
    exec(
        compile(tree, "<custom-factor-combiner>", "exec"),
        {
            "np": np,
            "pd": pd,
            "__builtins__": {
                "sum": sum,
                "len": len,
                "min": min,
                "max": max,
                "abs": abs,
            },
        },
        scope,
    )
    function = scope.get("combine")
    if not callable(function):
        raise FactorSandboxValidationError(
            "custom factor code must define combine(factors_dict)"
        )
    raw_result = function(
        {column: normalized[column].copy() for column in normalized}
    )
    try:
        result = pd.Series(raw_result, index=normalized.index, dtype=float)
    except (TypeError, ValueError) as exc:
        raise FactorSandboxValidationError(
            "custom factor code must return one numeric score per observation"
        ) from exc
    result = result.replace([np.inf, -np.inf], np.nan)
    _validate_output(result, limits, "custom factor code")
    return result


def _prepare_custom_factors(
    factors: Any,
    method: str,
    winsor_limit: float,
    limits: FactorSandboxLimits,
) -> pd.DataFrame:
    """Construct and normalize untrusted factor input inside the worker."""
    frame = pd.DataFrame(factors, dtype=float).replace([np.inf, -np.inf], np.nan)
    if frame.empty:
        raise FactorSandboxValidationError("factor observations are required")
    _validate_input_frames({"factors": frame}, limits, "custom factor code")
    lower, upper = frame.quantile(winsor_limit), frame.quantile(1 - winsor_limit)
    clipped = frame.clip(lower=lower, upper=upper, axis=1)
    if method == "rank":
        return clipped.rank(pct=True).sub(0.5).mul(2)
    scale = clipped.std(ddof=0).replace(0, np.nan)
    return clipped.sub(clipped.mean()).div(scale).fillna(0.0)


def _custom_combiner_pipeline_worker(
    factors: Any,
    code: str,
    method: str,
    winsor_limit: float,
    limits: FactorSandboxLimits,
) -> tuple[pd.DataFrame, pd.Series]:
    normalized = _prepare_custom_factors(factors, method, winsor_limit, limits)
    return normalized, _custom_combiner_worker(normalized, code, limits)


class CompositeFactorCombiner:
    def __init__(
        self, sandbox_limits: FactorSandboxLimits = DEFAULT_FACTOR_SANDBOX_LIMITS
    ) -> None:
        self.sandbox_limits = sandbox_limits

    @staticmethod
    def _resolve_weights(columns: pd.Index, weighting: str,
                         weights: dict[str, float] | None,
                         ic_history: dict[str, Any] | None) -> pd.Series:
        if weighting in {"ic", "ic_weighted", "ic_ir", "ic_ir_weighted"}:
            if not ic_history:
                raise ValueError(f"{weighting} weighting requires ic_history")
            values = {}
            for column in columns:
                history = pd.Series(ic_history.get(column, []), dtype=float).dropna()
                if history.empty:
                    values[column] = 0.0
                elif weighting in {"ic", "ic_weighted"}:
                    values[column] = float(history.mean())
                else:
                    standard_deviation = float(history.std(ddof=1))
                    values[column] = (
                        float(history.mean() * np.sqrt(len(history)) / standard_deviation)
                        if standard_deviation > 0 else 0.0
                    )
            return pd.Series(values, dtype=float)
        return pd.Series(weights or {column: 1.0 for column in columns}, dtype=float).reindex(columns).fillna(0.0)

    def _custom_combine(self, normalized: pd.DataFrame, code: str) -> pd.Series:
        _validate_custom_combiner(code, self.sandbox_limits)
        return _run_in_factor_sandbox(
            _custom_combiner_worker,
            (normalized, code, self.sandbox_limits),
            self.sandbox_limits,
            "custom factor code",
        )

    def combine(self, factors: Any, weights: dict[str, float] | None = None,
                method: str = "zscore", winsor_limit: float = 0.01,
                weighting: str = "equal", ic_history: dict[str, Any] | None = None,
                custom_code: str | None = None) -> dict[str, Any]:
        if weighting == "custom":
            if not custom_code:
                raise FactorSandboxValidationError(
                    "custom weighting requires custom_code"
                )
            _validate_custom_combiner(custom_code, self.sandbox_limits)
            normalized, score = _run_in_factor_sandbox(
                _custom_combiner_pipeline_worker,
                (
                    factors,
                    custom_code,
                    method,
                    winsor_limit,
                    self.sandbox_limits,
                ),
                self.sandbox_limits,
                "custom factor code",
            )
        else:
            frame = pd.DataFrame(factors, dtype=float).replace([np.inf, -np.inf], np.nan)
            if frame.empty:
                raise ValueError("factor observations are required")
            lower, upper = frame.quantile(winsor_limit), frame.quantile(1 - winsor_limit)
            clipped = frame.clip(lower=lower, upper=upper, axis=1)
            if method == "rank":
                normalized = clipped.rank(pct=True).sub(0.5).mul(2)
            else:
                scale = clipped.std(ddof=0).replace(0, np.nan)
                normalized = clipped.sub(clipped.mean()).div(scale).fillna(0.0)
        raw_weights = self._resolve_weights(normalized.columns, weighting, weights, ic_history)
        gross = raw_weights.abs().sum()
        if gross <= 0:
            raise ValueError("factor weights cannot sum to zero")
        normalized_weights = raw_weights / gross
        if weighting != "custom":
            score = normalized.mul(normalized_weights, axis=1).sum(axis=1)
        return {
            "composite_score": score,
            "normalized_factors": normalized,
            "weights": normalized_weights.to_dict(),
            "coverage": normalized.notna().mean().to_dict(),
            "weighting": weighting,
        }

    def evaluate_composite(self, factors: Any, forward_returns: Any, **kwargs: Any) -> dict[str, Any]:
        result = self.combine(factors, **kwargs)
        scores = pd.DataFrame(factors).copy()
        scores["__composite__"] = result["composite_score"]
        future = pd.DataFrame(forward_returns, dtype=float)
        if "__composite__" in future:
            target = future["__composite__"]
        elif future.shape[1] == 1:
            target = future.iloc[:, 0]
        else:
            target = future.mean(axis=1)
        joined = pd.concat([result["composite_score"].rename("score"), target.rename("forward")], axis=1).dropna()
        rolling = joined["score"].rolling(21, min_periods=5).corr(joined["forward"]).dropna()
        ic = float(joined["score"].corr(joined["forward"], method="spearman")) if len(joined) >= 3 else float("nan")
        ic_std = float(rolling.std(ddof=1)) if len(rolling) > 1 else float("nan")
        ic_ir = float(rolling.mean() / ic_std) if np.isfinite(ic_std) and ic_std > 0 else 0.0
        decay = [{"horizon": horizon, "ic": float(joined["score"].corr(joined["forward"].shift(-horizon), method="spearman"))}
                 for horizon in (1, 5, 10, 21, 63) if len(joined) > horizon + 2]
        valid = [(row["horizon"], abs(row["ic"])) for row in decay if np.isfinite(row["ic"]) and abs(row["ic"]) > 0]
        half_life = next((h for h, value in valid if value <= abs(ic) / 2), None)
        return {
            **result,
            "composite_ic": ic,
            "composite_ic_ir": ic_ir,
            "decay_curve": decay,
            "half_life": half_life,
            "optimal_rebalance_frequency": max(valid, key=lambda item: item[1])[0] if valid else None,
        }
