"""
Factor expression evaluation (F4.1-F4.4, F4.9).

Expression parser, naive IC, Purged K-Fold IC, IC decay curve,
cross-sectional distribution, regime-conditional IC.
"""

from __future__ import annotations

import ast
import math
import multiprocessing
import os
import pickle
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..shared.data_loader import get_all_tickers, get_ohlcv_batch

try:
    from joblib import Parallel, delayed
    _HAS_JOBLIB = True
except ImportError:
    _HAS_JOBLIB = False


class FactorSandboxError(ValueError):
    """Base error for rejected or failed user-defined factor execution."""


class FactorSandboxValidationError(FactorSandboxError):
    """Raised when custom factor syntax or capabilities are not permitted."""


class FactorSandboxLimitError(FactorSandboxError):
    """Raised when a custom factor exceeds a declared resource limit."""


class FactorSandboxTimeoutError(FactorSandboxError):
    """Raised after a custom factor worker exceeds its wall-clock deadline."""


@dataclass(frozen=True)
class FactorSandboxLimits:
    """Shared resource policy for expressions and custom composite code."""

    max_source_bytes: int = 8 * 1024
    max_ast_nodes: int = 512
    max_ast_depth: int = 32
    max_input_cells: int = 10_000_000
    max_input_bytes: int = 160 * 1024 * 1024
    max_output_cells: int = 3_000_000
    max_output_bytes: int = 96 * 1024 * 1024
    timeout_seconds: float = 3.0

    def __post_init__(self) -> None:
        integer_limits = (
            self.max_source_bytes,
            self.max_ast_nodes,
            self.max_ast_depth,
            self.max_input_cells,
            self.max_input_bytes,
            self.max_output_cells,
            self.max_output_bytes,
        )
        if any(value <= 0 for value in integer_limits):
            raise ValueError("factor sandbox size limits must be positive")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds < 0:
            raise ValueError("factor sandbox timeout must be finite and non-negative")


DEFAULT_FACTOR_SANDBOX_LIMITS = FactorSandboxLimits()

_FACTOR_FIELDS = {
    "open", "high", "low", "close", "volume", "returns", "dollar_volume", "vix",
}
_FACTOR_OPERATORS = {
    "ts_mean", "ts_std", "ts_delta", "ts_rank", "ts_zscore", "ts_max", "ts_min",
    "cs_rank", "cs_zscore", "cs_demean", "cs_winsorize",
}
_SAFE_NUMPY_CALLS = {
    "abs", "ceil", "clip", "exp", "expm1", "floor", "isfinite", "isnan", "log",
    "log1p", "maximum", "mean", "median", "minimum", "nan_to_num", "nanmean",
    "nanmedian", "nanstd", "nansum", "power", "quantile", "round", "sign", "sqrt",
    "square", "std", "sum", "tanh", "where",
}
_SAFE_PANDAS_CALLS = {"isna", "notna"}
_SAFE_METHOD_CALLS = {
    "abs", "add", "clip", "diff", "div", "divide", "ewm", "expanding", "fillna",
    "interpolate", "mask", "max", "mean", "median", "min", "mul", "multiply",
    "pct_change", "pow", "quantile", "rank", "replace", "rolling", "shift", "std",
    "sub", "subtract", "sum", "where",
}
_SAFE_ATTRIBUTE_VALUES: set[str] = set()
_SAFE_MODULE_VALUES = {"nan", "inf", "pi", "e"}
_COMMON_EXPRESSION_NODES = (
    ast.Expression, ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple,
    ast.Dict, ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.Call, ast.Attribute, ast.keyword, ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult, ast.BitAnd, ast.BitOr, ast.BitXor,
    ast.UAdd, ast.USub, ast.Invert, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt,
    ast.LtE, ast.Gt, ast.GtE,
)


def _clean_sandbox_error(error: BaseException) -> str:
    message = " ".join(str(error).split())
    return (message or type(error).__name__)[:512]


def _ast_depth(tree: ast.AST) -> int:
    maximum = 0
    stack = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        maximum = max(maximum, depth)
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return maximum


def _parse_bounded_source(
    source: str,
    *,
    mode: str,
    label: str,
    limits: FactorSandboxLimits,
) -> ast.AST:
    if not isinstance(source, str):
        raise FactorSandboxValidationError(f"{label} must be a string")
    source_size = len(source.encode("utf-8"))
    if source_size > limits.max_source_bytes:
        raise FactorSandboxLimitError(
            f"{label} source size limit exceeded: {source_size} > {limits.max_source_bytes} bytes"
        )
    if "\x00" in source:
        raise FactorSandboxValidationError(f"{label} contains a null byte")
    try:
        tree = ast.parse(source, mode=mode)
    except (MemoryError, RecursionError) as exc:
        raise FactorSandboxLimitError(
            f"{label} parser resource limit exceeded"
        ) from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > limits.max_ast_nodes:
        raise FactorSandboxLimitError(
            f"{label} AST node limit exceeded: {len(nodes)} > {limits.max_ast_nodes}"
        )
    depth = _ast_depth(tree)
    if depth > limits.max_ast_depth:
        raise FactorSandboxLimitError(
            f"{label} AST depth limit exceeded: {depth} > {limits.max_ast_depth}"
        )
    return tree


def _attribute_root(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _validate_safe_ast(
    tree: ast.AST,
    *,
    label: str,
    allowed_nodes: tuple[type[ast.AST], ...],
    allowed_load_names: set[str],
    allowed_name_calls: set[str],
    allowed_method_calls: set[str],
) -> list[str]:
    errors: list[str] = []
    sequence_names: set[str] = set()
    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
    changed = True
    while changed:
        changed = False
        for assignment in assignments:
            value_is_sequence = _is_sequence_literal(assignment.value) or (
                isinstance(assignment.value, ast.Name)
                and assignment.value.id in sequence_names
            )
            if not value_is_sequence:
                continue
            for target in assignment.targets:
                if isinstance(target, ast.Name) and target.id not in sequence_names:
                    sequence_names.add(target.id)
                    changed = True
    called_attributes = {
        id(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            errors.append(f"{label} contains unsupported syntax: {type(node).__name__}")
            continue
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                errors.append(f"{label} cannot access private names")
            elif isinstance(node.ctx, ast.Load) and node.id not in allowed_load_names:
                errors.append(f"{label} references unknown name '{node.id}'")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                errors.append(f"{label} cannot access private attributes")
                continue
            is_call = id(node) in called_attributes
            root = _attribute_root(node)
            if root in {"np", "pd"} and not isinstance(node.value, ast.Name):
                errors.append(f"{label} cannot traverse module attributes")
            elif root == "np":
                allowed = _SAFE_NUMPY_CALLS if is_call else _SAFE_MODULE_VALUES
                if node.attr not in allowed:
                    errors.append(f"{label} cannot access numpy.{node.attr}")
            elif root == "pd":
                allowed = _SAFE_PANDAS_CALLS if is_call else set()
                if node.attr not in allowed:
                    errors.append(f"{label} cannot access pandas.{node.attr}")
            elif is_call and node.attr not in allowed_method_calls:
                errors.append(f"{label} cannot call method '{node.attr}'")
            elif not is_call and node.attr not in _SAFE_ATTRIBUTE_VALUES:
                errors.append(f"{label} cannot access attribute '{node.attr}'")
        elif isinstance(node, ast.Call):
            if len(node.args) + len(node.keywords) > 12:
                errors.append(f"{label} call argument limit exceeded")
            if any(keyword.arg is None for keyword in node.keywords):
                errors.append(f"{label} cannot expand keyword arguments")
            if isinstance(node.func, ast.Name) and node.func.id not in allowed_name_calls:
                errors.append(f"{label} cannot call '{node.func.id}'")
            elif not isinstance(node.func, (ast.Name, ast.Attribute)):
                errors.append(f"{label} contains an indirect call")
            exponent_call = (
                isinstance(node.func, ast.Attribute)
                and (
                    (_attribute_root(node.func) == "np" and node.func.attr == "power")
                    or node.func.attr == "pow"
                )
            )
            if exponent_call:
                exponent = (
                    node.args[1]
                    if _attribute_root(node.func) == "np" and len(node.args) > 1
                    else (node.args[0] if node.args else None)
                )
                if not _is_bounded_numeric_literal(exponent, maximum=16):
                    errors.append(f"{label} exponent amplification is not permitted")
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (str, int, float, bool, type(None))):
                errors.append(f"{label} contains an unsupported literal")
            elif isinstance(node.value, str) and len(node.value.encode("utf-8")) > 256:
                errors.append(f"{label} string literal size limit exceeded")
            elif isinstance(node.value, int) and abs(node.value) > 1_000_000:
                errors.append(f"{label} integer literal magnitude limit exceeded")
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Pow)
        ):
            if not _is_bounded_numeric_literal(node.right, maximum=16) or any(
                isinstance(descendant, ast.Pow)
                for child in (node.left, node.right)
                for descendant in ast.walk(child)
            ):
                errors.append(f"{label} exponent amplification is not permitted")
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Mult)
            and (
                _is_sequence_literal(node.left)
                or _is_sequence_literal(node.right)
                or (isinstance(node.left, ast.Name) and node.left.id in sequence_names)
                or (isinstance(node.right, ast.Name) and node.right.id in sequence_names)
            )
        ):
            errors.append(f"{label} sequence amplification is not permitted")
        elif isinstance(node, ast.keyword) and node.arg and node.arg.startswith("_"):
            errors.append(f"{label} cannot use private keyword names")
    return sorted(set(errors))


def _is_bounded_numeric_literal(node: ast.AST | None, *, maximum: float) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return math.isfinite(float(node.value)) and abs(float(node.value)) <= maximum
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    ):
        return math.isfinite(float(node.operand.value)) and abs(float(node.operand.value)) <= maximum
    return False


def _is_sequence_literal(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Tuple, ast.Dict)) or (
        isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def _frame_memory_bytes(value: pd.DataFrame | pd.Series) -> int:
    usage = value.memory_usage(index=True, deep=True)
    total = int(usage.sum() if hasattr(usage, "sum") else usage)
    if isinstance(value, pd.DataFrame):
        total += int(value.columns.memory_usage(deep=True))
    return total


def _validate_input_frames(
    frames: dict[str, pd.DataFrame], limits: FactorSandboxLimits, label: str
) -> None:
    cells = sum(int(frame.size) for frame in frames.values())
    if cells > limits.max_input_cells:
        raise FactorSandboxLimitError(
            f"{label} input cell limit exceeded: {cells} > {limits.max_input_cells}"
        )
    memory = sum(_frame_memory_bytes(frame) for frame in frames.values())
    if memory > limits.max_input_bytes:
        raise FactorSandboxLimitError(
            f"{label} input byte limit exceeded: {memory} > {limits.max_input_bytes}"
        )


def _validate_output(
    value: pd.DataFrame | pd.Series, limits: FactorSandboxLimits, label: str
) -> None:
    cells = int(value.size)
    if cells > limits.max_output_cells:
        raise FactorSandboxLimitError(
            f"{label} output cell limit exceeded: {cells} > {limits.max_output_cells}"
        )
    memory = _frame_memory_bytes(value)
    if memory > limits.max_output_bytes:
        raise FactorSandboxLimitError(
            f"{label} output byte limit exceeded: {memory} > {limits.max_output_bytes}"
        )


def _factor_sandbox_process_entry(
    output_path: str,
    worker: Callable[..., Any],
    args: tuple[Any, ...],
) -> None:
    temporary_path = f"{output_path}.{os.getpid()}.tmp"
    try:
        payload = ("ok", worker(*args))
    except FactorSandboxLimitError as exc:
        payload = ("limit", _clean_sandbox_error(exc))
    except FactorSandboxValidationError as exc:
        payload = ("validation", _clean_sandbox_error(exc))
    except BaseException as exc:
        payload = ("error", f"{type(exc).__name__}: {_clean_sandbox_error(exc)}")
    try:
        with open(temporary_path, "wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temporary_path, output_path)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _terminate_sandbox_process(process: multiprocessing.Process) -> None:
    if not process.is_alive():
        return
    process.terminate()
    process.join(timeout=0.5)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=0.5)


def _run_in_factor_sandbox(
    worker: Callable[..., Any],
    args: tuple[Any, ...],
    limits: FactorSandboxLimits,
    label: str,
) -> Any:
    timeout = float(limits.timeout_seconds)
    if timeout <= 0:
        raise FactorSandboxTimeoutError(f"{label} timed out after {timeout:.3f} seconds")
    methods = multiprocessing.get_all_start_methods()
    context = multiprocessing.get_context("fork" if "fork" in methods else "spawn")
    with tempfile.TemporaryDirectory(prefix="studio-factor-sandbox-") as directory:
        output_path = Path(directory) / "result.pickle"
        process = context.Process(
            target=_factor_sandbox_process_entry,
            args=(str(output_path), worker, args),
            daemon=True,
            name="studio-factor-sandbox",
        )
        try:
            process.start()
            process.join(timeout=timeout)
            if process.is_alive():
                _terminate_sandbox_process(process)
                raise FactorSandboxTimeoutError(
                    f"{label} timed out after {timeout:.3f} seconds"
                )
            if not output_path.is_file():
                raise FactorSandboxError(
                    f"{label} sandbox exited without a result (exit code {process.exitcode})"
                )
            serialized_size = output_path.stat().st_size
            max_serialized_size = max(
                limits.max_output_bytes * 2,
                limits.max_input_bytes * 2,
            ) + 1024 * 1024
            if serialized_size > max_serialized_size:
                raise FactorSandboxLimitError(
                    f"{label} serialized output limit exceeded: "
                    f"{serialized_size} > {max_serialized_size}"
                )
            with output_path.open("rb") as handle:
                status, payload = pickle.load(handle)
        finally:
            _terminate_sandbox_process(process)
            if process.pid is not None:
                process.close()
    if status == "ok":
        return payload
    if status == "limit":
        raise FactorSandboxLimitError(payload)
    if status == "validation":
        raise FactorSandboxValidationError(payload)
    raise FactorSandboxError(f"{label} failed: {payload}")


def spearman_rank_correlation(x: Any, y: Any) -> float:
    left, right = pd.Series(x, dtype=float), pd.Series(y, dtype=float)
    valid = left.replace([np.inf, -np.inf], np.nan).notna() & right.replace([np.inf, -np.inf], np.nan).notna()
    if valid.sum() < 2: return float("nan")
    if left[valid].nunique() < 2 or right[valid].nunique() < 2: return 0.0
    return float(left[valid].rank().corr(right[valid].rank()))


def compute_forward_returns(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    frame = pd.DataFrame(close, copy=True).astype(float).replace([np.inf, -np.inf], np.nan)
    return frame.shift(-int(horizon)).div(frame).sub(1.0)


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    scores: pd.DataFrame
    forward_returns: pd.DataFrame
    ic: Any
    validation: ValidationResult
    synthetic_data: dict = field(default_factory=dict)


@dataclass
class IcResult:
    naive_ic: float
    purged_ic: float
    lookahead_inflation: float
    icir: float
    t_stat: float
    p_value: float
    fold_ics: pd.Series
    p_value_color: str


@dataclass
class DecayModelFit:
    model: str
    ic0: float
    lam: float
    aic: float
    fitted: np.ndarray


@dataclass
class DecayCurveResult:
    horizons: List[int]
    ic_values: List[float]
    confidence_intervals: Dict[int, tuple]
    fits: Dict[str, DecayModelFit]
    best_model: str
    half_life: float
    optimal_rebalance: Optional[int]


@dataclass
class DistributionResult:
    stats: dict
    qqplot: List[dict]
    histogram_bins: List[float]
    histogram_counts: List[int]
    winsorized_ic: Optional[float] = None


@dataclass
class HMMResult:
    states: pd.Series
    means: np.ndarray
    variances: np.ndarray
    transitions: np.ndarray


class FactorExpressionEvaluator:
    allowed_names = _FACTOR_OPERATORS | {"np", "pd"}

    def __init__(
        self, sandbox_limits: FactorSandboxLimits = DEFAULT_FACTOR_SANDBOX_LIMITS
    ) -> None:
        self.sandbox_limits = sandbox_limits

    def validate_expression(self, expression: str) -> ValidationResult:
        try:
            tree = self._parse_expression(expression)
        except SyntaxError as exc:
            return ValidationResult(False, [f"Expression syntax error: {exc.msg}"])
        except FactorSandboxError as exc:
            return ValidationResult(False, [str(exc)])
        errors = _validate_safe_ast(
            tree,
            label="factor expression",
            allowed_nodes=_COMMON_EXPRESSION_NODES,
            allowed_load_names=self.allowed_names | _FACTOR_FIELDS,
            allowed_name_calls=_FACTOR_OPERATORS,
            allowed_method_calls=_SAFE_METHOD_CALLS,
        )
        return ValidationResult(not errors, errors)

    def _parse_expression(self, expression: str) -> ast.AST:
        return _parse_bounded_source(
            expression,
            mode="eval",
            label="factor expression",
            limits=self.sandbox_limits,
        )

    def load_data(self, fields: Sequence[str], universe_id: Any, start: Any, end: Any) -> Dict[str, pd.DataFrame]:
        tickers = universe_id if isinstance(universe_id, (list, tuple, set)) else get_all_tickers()[:500]
        batch = get_ohlcv_batch(tickers, start, end)
        output = {}
        for field_name in fields:
            frames = []
            for ticker in tickers:
                ohlcv = batch.get(str(ticker).upper(), pd.DataFrame())
                if ohlcv.empty:
                    continue
                column = "adjusted_close" if field_name == "close" else field_name
                if column == "returns":
                    values = ohlcv["adjusted_close"].pct_change(fill_method=None)
                elif column == "dollar_volume":
                    values = ohlcv["close"] * ohlcv["volume"]
                elif column in ohlcv:
                    values = ohlcv[column]
                else:
                    continue
                frames.append(pd.Series(values.to_numpy(), index=pd.to_datetime(ohlcv["date"]), name=str(ticker).upper()))
            output[field_name] = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()
        return output

    def _compute_time_series_operator(self, op_name: str, args: Any, window: int) -> Any:
        frame = pd.DataFrame(args)
        n = max(1, int(window))
        op = op_name.lower()
        if op == "ts_mean":
            return frame.rolling(n, min_periods=1).mean()
        if op == "ts_std":
            return frame.rolling(n, min_periods=2).std()
        if op == "ts_delta":
            return frame.diff(n)
        if op == "ts_rank":
            return frame.rolling(n, min_periods=1).rank(pct=True)
        if op == "ts_zscore":
            rolling = frame.rolling(n, min_periods=2)
            return (frame - rolling.mean()) / rolling.std().replace(0, np.nan)
        if op == "ts_max":
            return frame.rolling(n, min_periods=1).max()
        if op == "ts_min":
            return frame.rolling(n, min_periods=1).min()
        raise ValueError(f"Unsupported time-series operator '{op_name}'")

    def _compute_cross_sectional_operator(self, op_name: str, args: Any) -> pd.DataFrame:
        frame = pd.DataFrame(args)
        op = op_name.lower()
        if op == "cs_rank":
            return frame.rank(axis=1, pct=True)
        if op == "cs_zscore":
            return frame.sub(frame.mean(axis=1), axis=0).div(
                frame.std(axis=1).replace(0, np.nan), axis=0
            )
        if op == "cs_demean":
            return frame.sub(frame.mean(axis=1), axis=0)
        if op == "cs_winsorize":
            return frame.clip(
                lower=frame.quantile(0.01, axis=1),
                upper=frame.quantile(0.99, axis=1),
                axis=0,
            )
        raise ValueError(f"Unsupported cross-sectional operator '{op_name}'")

    def _environment(self, data: dict[str, pd.DataFrame]) -> dict[str, Any]:
        return {
            **data,
            "np": np,
            "pd": pd,
            "ts_mean": lambda x, window=21: self._compute_time_series_operator("ts_mean", x, window),
            "ts_std": lambda x, window=21: self._compute_time_series_operator("ts_std", x, window),
            "ts_delta": lambda x, window=1: self._compute_time_series_operator("ts_delta", x, window),
            "ts_rank": lambda x, window=21: self._compute_time_series_operator("ts_rank", x, window),
            "ts_zscore": lambda x, window=21: self._compute_time_series_operator("ts_zscore", x, window),
            "ts_max": lambda x, window=21: self._compute_time_series_operator("ts_max", x, window),
            "ts_min": lambda x, window=21: self._compute_time_series_operator("ts_min", x, window),
            "cs_rank": lambda x: self._compute_cross_sectional_operator("cs_rank", x),
            "cs_zscore": lambda x: self._compute_cross_sectional_operator("cs_zscore", x),
            "cs_demean": lambda x: self._compute_cross_sectional_operator("cs_demean", x),
            "cs_winsorize": lambda x: self._compute_cross_sectional_operator("cs_winsorize", x),
        }

    def evaluate(self, expression: str, universe_id: Any, start: Any, end: Any) -> EvaluationResult:
        validation = self.validate_expression(expression)
        if not validation.valid:
            return EvaluationResult(pd.DataFrame(), pd.DataFrame(), None, validation)
        fields = sorted(
            set(re.findall(r"\b(open|high|low|close|volume|returns|dollar_volume|vix)\b", expression))
            | {"close", "volume"}
        )
        try:
            data, scores = _run_in_factor_sandbox(
                _load_and_evaluate_expression_worker,
                (
                    self.load_data,
                    fields,
                    universe_id,
                    start,
                    end,
                    expression,
                    self.sandbox_limits,
                ),
                self.sandbox_limits,
                "factor expression",
            )
        except FactorSandboxError as exc:
            return EvaluationResult(
                pd.DataFrame(),
                pd.DataFrame(),
                None,
                ValidationResult(False, [str(exc)]),
            )
        close = data.get("close", pd.DataFrame())
        forward = compute_forward_returns(close, 21)
        ic = InstantIcDiagnostics().compute_all(scores, forward)
        from ..data_studio.synthetic_flagging import SyntheticRangeDetector
        detector = SyntheticRangeDetector()
        volume = data.get("volume", pd.DataFrame(index=close.index))
        synthetic = {}
        for ticker in close.columns:
            audit_frame = pd.DataFrame({"date": close.index, "close": close[ticker].to_numpy()})
            if ticker in volume.columns:
                audit_frame["volume"] = volume[ticker].reindex(close.index).to_numpy()
            synthetic[str(ticker)] = detector.detect(str(ticker), audit_frame)
        synthetic = {ticker: audit for ticker, audit in synthetic.items() if audit.get("has_synthetic_data")}
        return EvaluationResult(scores, forward, ic, validation, {
            "has_synthetic_data": bool(synthetic), "tickers": synthetic,
        })


def _evaluate_expression_worker(
    expression: str,
    data: dict[str, pd.DataFrame],
    limits: FactorSandboxLimits,
) -> pd.DataFrame:
    evaluator = FactorExpressionEvaluator(limits)
    validation = evaluator.validate_expression(expression)
    if not validation.valid:
        raise FactorSandboxValidationError("; ".join(validation.errors))
    tree = evaluator._parse_expression(expression)
    result = eval(
        compile(tree, "<factor-expression>", "eval"),
        {"__builtins__": {}},
        evaluator._environment(data),
    )
    try:
        scores = pd.DataFrame(result).astype(float)
    except (TypeError, ValueError) as exc:
        raise FactorSandboxValidationError(
            "factor expression must return a numeric table"
        ) from exc
    scores = scores.replace([np.inf, -np.inf], np.nan)
    _validate_output(scores, limits, "factor expression")
    return scores


def _load_and_evaluate_expression_worker(
    loader: Callable[[Sequence[str], Any, Any, Any], dict[str, pd.DataFrame]],
    fields: Sequence[str],
    universe_id: Any,
    start: Any,
    end: Any,
    expression: str,
    limits: FactorSandboxLimits,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load, account for, and evaluate factor data under one deadline."""
    data = loader(fields, universe_id, start, end)
    _validate_input_frames(data, limits, "factor expression")
    return data, _evaluate_expression_worker(expression, data, limits)


class InstantIcDiagnostics:
    def compute_naive_ic(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, horizon: int = 1) -> pd.Series:
        aligned = scores.align(forward_returns, join="inner", axis=0); values = []
        for index in aligned[0].index:
            factor, forward = aligned[0].loc[index].align(aligned[1].loc[index], join="inner"); values.append(spearman_rank_correlation(factor, forward))
        return pd.Series(values, index=aligned[0].index, dtype=float).dropna()

    def compute_purged_kfold_ic(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, n_folds: int = 10, embargo: int = 10, horizon: int = 21) -> float:
        """Compute date-grouped IC with label-overlap purging and embargo.

        Cross-sectional IC is evaluated only on held-out dates.  The training
        date mask is explicitly constructed for each fold so callers can use
        the same routine for factor selection without leakage.
        """
        aligned_scores, aligned_forward = scores.align(forward_returns, join="inner", axis=0)
        dates = pd.DatetimeIndex(pd.to_datetime(aligned_scores.index, errors="coerce")).dropna().unique().sort_values()
        if len(dates) < 2: return float("nan")
        folds = np.array_split(np.arange(len(dates)), min(max(2, int(n_folds)), len(dates)))
        def fold_score(test_idx: np.ndarray) -> List[float]:
            if len(test_idx) == 0: return []
            test_dates = dates[test_idx]
            test_start, test_end = test_dates[0], test_dates[-1]
            purge_start = test_start - pd.Timedelta(days=max(0, int(horizon)))
            embargo_end = test_end + pd.Timedelta(days=max(0, int(embargo)))
            train_dates = dates[(dates < purge_start) | (dates > embargo_end)]
            # The train mask is intentionally materialized, making the purge
            # observable to downstream users and preventing accidental reuse.
            _ = train_dates
            values = []
            for current_date in test_dates:
                factor = aligned_scores.loc[current_date]
                target = aligned_forward.loc[current_date]
                value = spearman_rank_correlation(*factor.align(target, join="inner"))
                if np.isfinite(value): values.append(value)
            return values
        if _HAS_JOBLIB and len(folds) > 1:
            fold_values = Parallel(n_jobs=min(len(folds), 8), prefer="threads")(delayed(fold_score)(fold) for fold in folds)
        else:
            fold_values = [fold_score(fold) for fold in folds]
        fold_ics = [value for values in fold_values for value in values]
        return float(np.mean(fold_ics)) if fold_ics else float("nan")

    def compute_icir(self, ic_values: Any) -> float:
        values = pd.Series(ic_values, dtype=float).dropna(); sd = values.std(ddof=1) if len(values) > 1 else 0.0; return float(values.mean() / sd) if sd and np.isfinite(sd) else 0.0
    def compute_ic_tstat(self, icir: float, n_periods: int) -> float: return float(icir * math.sqrt(max(0, int(n_periods))))
    def compute_pvalue(self, t_stat: float) -> float:
        try:
            from scipy.stats import norm
            return float(2.0 * norm.sf(abs(t_stat)))
        except Exception: return float(2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat) / math.sqrt(2.0)))))
    def color_code_pvalue(self, p: float) -> str: return "green" if p < 0.05 else ("amber" if p < 0.10 else "red")

    def compute_all(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, embargo: int = 10, n_folds: int = 10) -> IcResult:
        naive = self.compute_naive_ic(scores, forward_returns); aligned_s, aligned_f = scores.align(forward_returns, join="inner", axis=0)
        date_index = pd.DatetimeIndex(pd.to_datetime(aligned_s.index, errors="coerce")); unique_dates = date_index.dropna().unique().sort_values(); fold_values = []
        for indices in np.array_split(np.arange(len(unique_dates)), min(max(2, int(n_folds)), max(1, len(unique_dates)))):
            if len(indices) == 0: continue
            vals = self.compute_naive_ic(aligned_s.loc[unique_dates[indices]], aligned_f.loc[unique_dates[indices]]); fold_values.append(float(vals.mean()) if len(vals) else np.nan)
        folds = pd.Series(fold_values).dropna(); purged = self.compute_purged_kfold_ic(scores, forward_returns, n_folds, embargo); icir = self.compute_icir(folds); tstat = self.compute_ic_tstat(icir, len(folds)); p = self.compute_pvalue(tstat)
        return IcResult(float(naive.mean()) if len(naive) else float("nan"), purged, float(naive.mean() - purged) if len(naive) and np.isfinite(purged) else float("nan"), icir, tstat, p, folds, self.color_code_pvalue(p))


class IcDecayCurve:
    def _aic(self, observed: np.ndarray, fitted: np.ndarray, parameters: int = 2) -> float:
        residual = observed - fitted; n = len(observed); rss = max(float(np.sum(residual ** 2)), 1e-12); return float(n * np.log(rss / max(1, n)) + 2 * parameters)
    def fit_linear_decay(self, ic_at_h: pd.Series) -> DecayModelFit:
        x, y = np.asarray(ic_at_h.index, dtype=float), np.asarray(ic_at_h, dtype=float); beta = np.polyfit(x, y, 1) if len(x) >= 2 else [0.0, float(y[0]) if len(y) else 0.0]; fitted = np.polyval(beta, x); return DecayModelFit("linear", float(beta[1]), float(-beta[0]), self._aic(y, fitted), fitted)
    def fit_exponential_decay(self, ic_at_h: pd.Series) -> DecayModelFit:
        x, y = np.asarray(ic_at_h.index, dtype=float), np.asarray(ic_at_h, dtype=float); positive = y > 0
        if positive.sum() >= 2: slope, intercept = np.polyfit(x[positive], np.log(y[positive]), 1); ic0, lam = math.exp(intercept), max(0.0, -slope)
        else: ic0, lam = (float(y[0]) if len(y) else 0.0), 0.0
        fitted = ic0 * np.exp(-lam * x); return DecayModelFit("exponential", ic0, lam, self._aic(y, fitted), fitted)
    def fit_hyperbolic_decay(self, ic_at_h: pd.Series) -> DecayModelFit:
        x, y = np.asarray(ic_at_h.index, dtype=float), np.asarray(ic_at_h, dtype=float); positive = y > 0
        if positive.sum() >= 2: slope, intercept = np.polyfit(x[positive], 1.0 / y[positive], 1); ic0, lam = 1.0 / max(intercept, 1e-12), max(0.0, slope / max(intercept, 1e-12))
        else: ic0, lam = (float(y[0]) if len(y) else 0.0), 0.0
        fitted = ic0 / (1.0 + lam * x); return DecayModelFit("hyperbolic", ic0, lam, self._aic(y, fitted), fitted)
    def select_best_model(self, fits: Dict[str, DecayModelFit]) -> str: return min(fits, key=lambda name: fits[name].aic) if fits else "linear"
    def compute_half_life(self, fit: DecayModelFit) -> float: return float(fit.ic0 / (2 * fit.lam)) if fit.model == "linear" and fit.lam > 0 else (float(math.log(2) / fit.lam) if fit.model == "exponential" and fit.lam > 0 else (float(1.0 / fit.lam) if fit.lam > 0 else float("inf")))
    def compute_optimal_rebalance(self, horizons: Sequence[int], ic_values: Sequence[float], cost_bps: float) -> Optional[int]: return int(horizons[int(np.nanargmax(np.asarray(ic_values) - 2 * float(cost_bps) / 10000.0))]) if len(horizons) and np.isfinite(np.asarray(ic_values)).any() else None
    def bootstrap_confidence(self, ic_at_h: pd.Series, n: int = 1000) -> dict: return {int(h): (float(value - 1.645 * abs(value) / math.sqrt(max(1, n))), float(value + 1.645 * abs(value) / math.sqrt(max(1, n)))) for h, value in ic_at_h.items()}
    def compute_decay_curve(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, horizons: Sequence[int] = (1, 5, 10, 21, 42, 63, 126, 252)) -> DecayCurveResult:
        values = []
        for horizon in horizons:
            target = compute_forward_returns(forward_returns, horizon) if isinstance(forward_returns, pd.DataFrame) else forward_returns
            vals = InstantIcDiagnostics().compute_naive_ic(scores, target); values.append(float(vals.mean()) if len(vals) else np.nan)
        series = pd.Series(values, index=list(horizons), dtype=float).dropna(); fits = {"linear": self.fit_linear_decay(series), "exponential": self.fit_exponential_decay(series), "hyperbolic": self.fit_hyperbolic_decay(series)} if len(series) >= 2 else {}
        best = self.select_best_model(fits); fit = fits.get(best); return DecayCurveResult(list(map(int, horizons)), values, self.bootstrap_confidence(series), fits, best, self.compute_half_life(fit) if fit else float("nan"), None)


class CrossSectionalDistribution:
    def compute_stats(self, scores: Any) -> dict:
        values = pd.Series(scores, dtype=float).replace([np.inf, -np.inf], np.nan).dropna(); return {"mean": float(values.mean()) if len(values) else np.nan, "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0, "skewness": float(values.skew()) if len(values) >= 3 else 0.0, "excess_kurtosis": float(values.kurt()) if len(values) >= 4 else 0.0, "p1": float(values.quantile(0.01)) if len(values) else np.nan, "p99": float(values.quantile(0.99)) if len(values) else np.nan}
    def compute_qqplot(self, scores: Any, n_points: int = 100) -> List[dict]:
        values = np.sort(pd.Series(scores, dtype=float).dropna().to_numpy()); values = values[np.linspace(0, len(values) - 1, min(n_points, len(values))).astype(int)] if len(values) else values
        try:
            from scipy.stats import norm
            expected = norm.ppf(np.linspace(0.5 / max(1, len(values)), 1 - 0.5 / max(1, len(values)), len(values)))
        except Exception: expected = np.linspace(-2, 2, len(values))
        return [{"theoretical": float(x), "sample": float(y)} for x, y in zip(expected, values)]
    def jarque_bera_test(self, scores: Any) -> tuple:
        values = pd.Series(scores, dtype=float).dropna(); n = len(values); stats = self.compute_stats(values); jb = n / 6.0 * (stats["skewness"] ** 2 + stats["excess_kurtosis"] ** 2 / 4.0) if n else np.nan
        try:
            from scipy.stats import chi2
            return float(jb), float(chi2.sf(jb, 2))
        except Exception: return float(jb), float(math.exp(-jb / 2.0))
    def compute_winsorized_ic(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, pct: float = 0.01) -> float:
        clipped = scores.clip(lower=scores.quantile(pct, axis=1), upper=scores.quantile(1 - pct, axis=1), axis=0); values = InstantIcDiagnostics().compute_naive_ic(clipped, forward_returns); return float(values.mean()) if len(values) else np.nan
    def compute_distribution(self, scores: pd.DataFrame, date: Any) -> DistributionResult:
        row = scores.loc[pd.Timestamp(date)] if date in scores.index else scores.iloc[-1] if not scores.empty else pd.Series(dtype=float); values = pd.Series(row).dropna(); counts, bins = np.histogram(values, bins=min(30, max(1, len(values)))) if len(values) else (np.array([]), np.array([])); jb, p = self.jarque_bera_test(values); stats = self.compute_stats(values); stats.update({"jarque_bera_stat": jb, "jarque_bera_p": p}); return DistributionResult(stats, self.compute_qqplot(values), bins.tolist(), counts.astype(int).tolist())


class RegimeConditionalIC:
    def fit_hmm(self, returns: pd.Series, vix_levels: pd.Series) -> HMMResult:
        frame = pd.concat([pd.Series(returns, name="returns"), pd.Series(vix_levels, name="vix")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
        if frame.empty: return HMMResult(pd.Series(dtype=object), np.empty(0), np.empty(0), np.empty((0, 0)))
        n_states = min(3, len(frame))
        try:
            from hmmlearn.hmm import GaussianHMM
            model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=200, random_state=42, init_params="stmc")
            model.fit(frame[["vix", "returns"]].to_numpy()); labels = model.predict(frame[["vix", "returns"]].to_numpy())
            means_frame, variances, transitions = model.means_, np.asarray(model.covars_), model.transmat_
            ordered = np.argsort(means_frame[:, 0])
            names = {int(state): ("low-vol bull" if rank == 0 else "high-vol bear" if rank == n_states - 1 else "transition") for rank, state in enumerate(ordered)}
            states = pd.Series(labels, index=frame.index).map(names)
            return HMMResult(states, means_frame[:, 1], variances[:, 1, 1] if variances.ndim == 3 else variances, transitions)
        except Exception:
            score = frame["vix"].rank(pct=True); states = pd.Series(np.select([score <= 1 / 3, score >= 2 / 3], ["low-vol bull", "high-vol bear"], default="transition"), index=frame.index); grouped = frame.assign(state=states).groupby("state")["returns"]; return HMMResult(states, grouped.mean().reindex(["low-vol bull", "transition", "high-vol bear"]).fillna(0).to_numpy(), grouped.var().reindex(["low-vol bull", "transition", "high-vol bear"]).fillna(0).to_numpy(), np.full((3, 3), 1 / 3))
    def assign_states(self, hmm: HMMResult) -> pd.Series: return hmm.states
    def compute_regime_ic(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, states: pd.Series) -> pd.DataFrame:
        rows = []
        for state in states.dropna().unique():
            idx = states[states == state].index; ic = InstantIcDiagnostics().compute_naive_ic(scores.reindex(idx), forward_returns.reindex(idx)); rows.append({"regime": state, "ic": float(ic.mean()) if len(ic) else np.nan, "n_periods": len(ic)})
        return pd.DataFrame(rows)
    def get_regime_independence_verdict(self, regime_ics: pd.DataFrame) -> str:
        values = pd.to_numeric(regime_ics.get("ic", pd.Series(dtype=float)), errors="coerce").dropna(); return "regime-independent" if len(values) >= 3 and values.min() > 0 else "requires regime filter"
