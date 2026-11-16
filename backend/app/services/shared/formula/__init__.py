"""The formula language every lab shares: a strict `ast` whitelist (no eval, no attribute access, no subscripts).

A lab brings its own field names and operator table; Research evaluates over (month x ticker) frames, Studio over daily bars.
"""

from __future__ import annotations

import ast
from typing import Any

MAX_EXPR_LEN = 2000
MAX_NODES = 250


class SignalError(ValueError):
    def __init__(self, message: str, start: int = 0, end: int | None = None):
        super().__init__(message)
        self.message, self.start, self.end = message, start, start if end is None else end

    def as_dict(self) -> dict[str, Any]:
        return {"message": self.message, "start": self.start, "end": self.end}


BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a**b}
CMPOPS = {ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b, ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


def parse(expr: str, names, operators, arity, max_nodes: int = MAX_NODES) -> ast.Expression:
    """Parse and statically validate a formula against a lab's field names and operator table. Raises SignalError with a character span."""

    if not isinstance(expr, str) or not expr.strip():
        raise SignalError("Formula is empty")
    if len(expr) > MAX_EXPR_LEN:
        raise SignalError(f"Formula is longer than {MAX_EXPR_LEN} characters", 0, len(expr))
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        off = max((e.offset or 1) - 1, 0)
        raise SignalError(f"Syntax error: {e.msg}", off, off + 1) from None
    lead = len(expr) - len(expr.lstrip())
    nodes = list(ast.walk(tree))
    if len(nodes) > max_nodes:
        raise SignalError("Formula is too complex", 0, len(expr))
    for n in nodes:
        span = (getattr(n, "col_offset", 0) + lead, getattr(n, "end_col_offset", 0) + lead)
        if isinstance(n, (ast.Expression, ast.Load, ast.operator, ast.unaryop, ast.cmpop)):
            if isinstance(n, ast.operator) and type(n) not in BINOPS and not isinstance(n, (ast.BitAnd, ast.BitOr)):
                raise SignalError(f"Operator {type(n).__name__} is not allowed", *span)
            continue
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
                raise SignalError("Only numeric constants are allowed", *span)
        elif isinstance(n, ast.Name):
            if n.id not in names and n.id not in operators:
                raise SignalError(f"Unknown name '{n.id}'", *span)
        elif isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name):
                raise SignalError("Only calls to named operators are allowed", *span)
            if n.func.id not in operators:
                raise SignalError(f"Unknown operator '{n.func.id}'", *span)
            if n.keywords:
                raise SignalError("Keyword arguments are not supported", *span)
            lo, hi = arity[n.func.id]
            if not lo <= len(n.args) <= hi:
                raise SignalError(f"{n.func.id} takes {lo if lo == hi else f'{lo}-{hi}'} arguments, got {len(n.args)}", *span)
        elif isinstance(n, ast.BinOp):
            if type(n.op) not in BINOPS and not isinstance(n.op, (ast.BitAnd, ast.BitOr)):
                raise SignalError("Operator not allowed", *span)
        elif isinstance(n, ast.UnaryOp):
            if not isinstance(n.op, (ast.USub, ast.UAdd)):
                raise SignalError("Only unary + and - are allowed", *span)
        elif isinstance(n, ast.Compare):
            if len(n.ops) != 1 or type(n.ops[0]) not in CMPOPS:
                raise SignalError("Use a single comparison (>, >=, <, <=, ==, !=)", *span)
        else:
            raise SignalError(f"'{type(n).__name__}' is not allowed in formulas (no attribute access, subscripts, lambdas or strings)", *span)
    # bare operator names (not called) are not values
    called = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    for n in nodes:
        if isinstance(n, ast.Name) and n.id in operators and n.id not in names and id(n) not in called:
            raise SignalError(f"'{n.id}' is an operator; call it like {n.id}(...)", n.col_offset + lead, n.end_col_offset + lead)
    return tree
