from __future__ import annotations

"""
AST-based lookahead bias linter (F1.1).

Scans Python AST for patterns like shift(-1) on price data without
forward-fill, hardcoded date ranges, future date references.
Runs automatically on every keystroke.
"""

import ast
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List



_DATE_PATTERN = re.compile(r"(?:['\"])(\d{4}(?:-\d{2}-\d{2})?)(?:['\"])")


@lru_cache(maxsize=256)
def _parse_source(source: str) -> ast.Module:
    return ast.parse(source)


class Warning(str, Enum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class LintDiagnostic:
    line: int
    column: int
    end_line: int
    end_column: int
    message: str
    severity: str
    code: str

    def to_dict(self) -> dict:
        return asdict(self)


def _diagnostic(node: ast.AST, message: str, code: str, severity: str = Warning.WARNING.value) -> LintDiagnostic:
    return LintDiagnostic(
        line=max(1, int(getattr(node, "lineno", 1))),
        column=max(0, int(getattr(node, "col_offset", 0))),
        end_line=max(1, int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))),
        end_column=max(0, int(getattr(node, "end_col_offset", getattr(node, "col_offset", 0)))),
        message=message,
        severity=severity,
        code=code,
    )


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _name_of(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


class LookaheadBiasLinter:
    """Static AST linter for quant-specific look-ahead and reproducibility risks."""

    def __init__(self) -> None:
        self._debounce_cache: Dict[str, tuple[float, List[LintDiagnostic]]] = {}

    def lint_code(self, source: str) -> List[LintDiagnostic]:
        if not source or not source.strip():
            return []
        try:
            tree = _parse_source(source)
        except SyntaxError as exc:
            line = int(exc.lineno or 1)
            column = int(exc.offset or 1) - 1
            return [LintDiagnostic(line, max(0, column), line, max(0, column + 1), f"Syntax error: {exc.msg}", Warning.ERROR.value, "SYNTAX_ERROR")]
        diagnostics = []
        diagnostics.extend(self.check_shift_without_ffill(tree))
        diagnostics.extend(self.check_hardcoded_date_ranges(source))
        diagnostics.extend(self.check_future_date_reference(tree))
        diagnostics.extend(self.check_lookahead_shift(tree))
        diagnostics.extend(self.check_non_deterministic(tree))
        return sorted({(d.line, d.column, d.code, d.message): d for d in diagnostics}.values(), key=lambda d: (d.line, d.column, d.code))

    def lint_code_debounced(self, source: str, debounce_seconds: float = 0.30) -> List[LintDiagnostic]:
        """Return cached diagnostics during rapid editor keystrokes."""
        key = str(source)
        now = time.monotonic(); cached = self._debounce_cache.get(key)
        if cached and now - cached[0] < max(0.0, float(debounce_seconds)):
            return list(cached[1])
        diagnostics = self.lint_code(source); self._debounce_cache = {key: (now, diagnostics)}
        return diagnostics

    def check_shift_without_ffill(self, source_ast: ast.Module) -> List[LintDiagnostic]:
        diagnostics: List[LintDiagnostic] = []
        statements = list(source_ast.body)
        for node in ast.walk(source_ast):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "shift":
                continue
            if not node.args:
                continue
            try:
                periods = ast.literal_eval(node.args[0])
            except (ValueError, TypeError):
                continue
            if not isinstance(periods, (int, float)):
                continue
            source_name = _name_of(node.func.value).lower()
            if periods not in (-1, 1) or not any(token in source_name for token in ("price", "close", "open", "high", "low", "return", "ret", "signal")):
                continue
            statement_index = next((i for i, stmt in enumerate(statements) if stmt.lineno <= node.lineno <= getattr(stmt, "end_lineno", stmt.lineno)), 0)
            nearby = statements[statement_index: statement_index + 3]
            has_fill = any(isinstance(candidate, ast.Call) and ".fill" in _name_of(candidate.func).lower() for stmt in nearby for candidate in ast.walk(stmt))
            if not has_fill:
                direction = "future data" if periods == -1 else "time-series alignment"
                diagnostics.append(_diagnostic(node, f"Potential look-ahead bias: shift({periods}) on {source_name or 'price/return data'} without fill handling within 3 statements ({direction}).", "LOOKAHEAD_SHIFT"))
        return diagnostics

    def check_hardcoded_date_ranges(self, source: str) -> List[LintDiagnostic]:
        diagnostics = []
        lines = source.splitlines()
        for line_number, line in enumerate(lines, 1):
            for match in _DATE_PATTERN.finditer(line):
                if "config" in line.lower() and any(token in line.lower() for token in ("start", "end", "date", "period")):
                    diagnostics.append(LintDiagnostic(line_number, match.start(), line_number, match.end(), "Hardcoded date range in strategy configuration; use a parameterized backtest range.", Warning.WARNING.value, "HARDCODED_DATE"))
        return diagnostics

    def check_future_date_reference(self, source_ast: ast.Module) -> List[LintDiagnostic]:
        diagnostics = []
        signal_scope = False
        for parent in ast.walk(source_ast):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                signal_scope = any(token in parent.name.lower() for token in ("signal", "strategy", "alpha", "predict"))
                if not signal_scope:
                    continue
                for node in ast.walk(parent):
                    if isinstance(node, ast.Name) and any(token in node.id.lower() for token in ("future", "next_week", "next_month", "tomorrow", "forward_return")):
                        diagnostics.append(_diagnostic(node, f"Future-looking variable '{node.id}' used in signal computation.", "FUTURE_REFERENCE"))
        return diagnostics

    def check_lookahead_shift(self, source_ast: ast.Module) -> List[LintDiagnostic]:
        diagnostics = []
        for node in ast.walk(source_ast):
            if not isinstance(node, ast.Attribute) or node.attr != "values":
                continue
            parent = node.value
            if isinstance(parent, ast.Subscript):
                source = parent.value
                if not (isinstance(source, ast.Attribute) and source.attr in {"loc", "iloc", "at", "iat"}):
                    diagnostics.append(_diagnostic(node, "Converting a column slice to .values can discard date alignment; preserve the index explicitly.", "INDEX_ALIGNMENT"))
        return diagnostics

    def check_non_deterministic(self, source_ast: ast.Module) -> List[LintDiagnostic]:
        diagnostics = []
        for function in (node for node in ast.walk(source_ast) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if not any(token in function.name.lower() for token in ("signal", "strategy", "alpha", "predict")):
                continue
            for node in ast.walk(function):
                name = _name_of(node.func) if isinstance(node, ast.Call) else _name_of(node)
                lowered = name.lower()
                if isinstance(node, ast.Call) and (lowered.startswith("random") or lowered.startswith("numpy.random") or lowered.startswith("np.random")):
                    diagnostics.append(_diagnostic(node, "Non-deterministic random operation inside signal logic; inject a seeded RNG explicitly.", "NON_DETERMINISTIC"))
                elif isinstance(node, ast.Call) and lowered in {"datetime.now", "datetime.datetime.now", "date.today", "datetime.today"}:
                    diagnostics.append(_diagnostic(node, "Wall-clock time inside signal logic makes results non-reproducible.", "NON_DETERMINISTIC"))
        return diagnostics

    def register_completion_providers(self, monaco_api: Any) -> None:
        registry = build_function_registry()
        suggestions = [{"label": name, "kind": "Function", "insertText": name, "detail": sig["return_type"], "documentation": sig["docstring"]} for name, sig in registry.items()]
        provider = {"triggerCharacters": [".", "_"], "provideCompletionItems": lambda *_args, **_kwargs: {"suggestions": suggestions}}
        if hasattr(monaco_api, "register_completion_item_provider"):
            monaco_api.register_completion_item_provider("python", provider)
        elif hasattr(monaco_api, "registerCompletionItemProvider"):
            monaco_api.registerCompletionItemProvider("python", provider)
        elif isinstance(monaco_api, dict):
            monaco_api["python_completion_provider"] = provider
        else:
            raise TypeError("monaco_api must expose a completion provider registration method or be a dict")


def build_function_registry() -> Dict[str, dict]:
    """Return the stable public API used by the editor's autocomplete provider."""
    names = {
        "get_returns": ("tickers, start, end", "pandas.DataFrame", "Load adjusted-close returns."),
        "get_ohlcv": ("ticker, start, end", "pandas.DataFrame", "Load normalized OHLCV data."),
        "get_macro": ("series_name, start, end", "pandas.Series", "Load a macro series."),
        "get_factor_returns": ("model='ff5'", "pandas.DataFrame", "Load factor returns."),
        "ts_mean": ("series, window", "pandas.Series", "Rolling time-series mean."),
        "ts_std": ("series, window", "pandas.Series", "Rolling time-series standard deviation."),
        "cs_rank": ("frame", "pandas.DataFrame", "Cross-sectional percentile rank."),
        "compute_sharpe": ("returns", "float", "Annualized Sharpe ratio."),
        "run_backtest": ("config", "SimulationResult", "Run event-driven simulation."),
    }
    return {name: {"params": params, "return_type": return_type, "docstring": docstring} for name, (params, return_type, docstring) in names.items()}
