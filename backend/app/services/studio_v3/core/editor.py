"""Editor services beyond lint and completion: hover, inlay hints, code lens, code actions, import organising and range formatting.

Positions are 1-based lines and columns, matching `lint`.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

from . import compile as compiler
from . import formula, pycode

_RULE_CALLS = {"value", "rule"}
_FORMULA_CALLS = _RULE_CALLS | {"rank", "zscore"}
_ORDER_SIGNATURES = {"market_order": ("symbol", "quantity"), "limit_order": ("symbol", "quantity", "price"), "stop_order": ("symbol", "quantity", "price"),
                     "stop_limit_order": ("symbol", "quantity", "stop_price", "limit_price"), "set_holdings": ("symbol", "weight"), "order_value": ("symbol", "value")}


def _tree(code: str) -> ast.Module | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _ctx_call(node: ast.AST, names: set[str] | None = None) -> ast.Call | None:
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ctx" and (names is None or node.func.attr in names)):
        return node
    return None


def _literal(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _bars(expression: str, params: dict[str, float]) -> int | None:
    try:
        return compiler._bars_needed(formula.parse(expression, params))
    except Exception:  # noqa: BLE001 a formula that does not parse has no lookback to show
        return None


def formula_literals(code: str) -> list[tuple[ast.Call, str]]:
    """Every ctx.value/ctx.rule call whose first argument is a literal formula."""
    tree = _tree(code)
    if tree is None:
        return []
    out = []
    for node in ast.walk(tree):
        call = _ctx_call(node, _RULE_CALLS)
        if call and call.args and _literal(call.args[0]) is not None:
            out.append((call, call.args[0].value))
    return out


def _contains(node: ast.AST, line: int, column: int) -> bool:
    end_line = getattr(node, "end_lineno", None)
    if end_line is None:
        return False
    return (node.lineno, node.col_offset) <= (line, column - 1) < (end_line, node.end_col_offset)


def _innermost(tree: ast.AST, line: int, column: int) -> list[ast.AST]:
    chain, current = [], tree
    while True:
        child = next((c for c in ast.iter_child_nodes(current) if _contains(c, line, column)), None)
        if child is None:
            return chain
        chain.append(child)
        current = child


# --- hover (B-34) ----------------------------------------------------------------


def hover(code: str, line: int, column: int, params: dict[str, dict] | None = None, last_values: dict[str, float] | None = None) -> dict | None:
    """Docs for the symbol under the cursor: a ctx member, a formula operator or field inside a literal, a parameter, or a local def."""
    tree = _tree(code)
    if tree is None:
        return None
    chain = _innermost(tree, line, column)
    if not chain:
        return None
    node = chain[-1]
    params = params or {}
    portfolio = any(isinstance(n, ast.FunctionDef) and n.name == "on_data" for n in ast.walk(tree))
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.lineno == line:
        text = node.value
        offset = column - 1 - node.col_offset - 1  # inside the opening quote
        for match in re.finditer(r"[A-Za-z_]\w*", text):
            if match.start() <= offset < match.end():
                word = match.group()
                span = {"line": line, "column": node.col_offset + 2 + match.start(), "end_column": node.col_offset + 2 + match.end()}
                if word in formula.OPERATORS:
                    _, args, description, _ = formula.OPERATORS[word]
                    note = _bars(text, {k: v.get("value", 0) for k, v in params.items()})
                    value = (last_values or {}).get(text)
                    body = f"`{word}({', '.join(args)})`\n\n{description}" + (f"\n\nWhole formula needs {note} bars before it has a value." if note else "")
                    return {"contents": body + (f"\n\nLast value: {value:.6g}" if value is not None else ""), "lookback_bars": note, "last_value": value, "range": span}
                if word in formula.FIELDS:
                    return {"contents": f"`{word}`: {formula.FIELDS[word]}", "lookback_bars": 0, "last_value": None, "range": span}
                if word in params:
                    return {"contents": _param_text(word, params[word]), "lookback_bars": None, "last_value": None, "range": span}
        parent = chain[-2] if len(chain) > 1 else None
        name = _literal(node)
        if isinstance(parent, ast.Call) and _ctx_call(parent, {"param"}) and name in params:
            return {"contents": _param_text(name, params[name]), "lookback_bars": None, "last_value": None,
                    "range": {"line": line, "column": node.col_offset + 1, "end_column": node.end_col_offset + 1}}
        return None
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "ctx":
        member = pycode._api_members("portfolio_ctx" if portfolio else "ctx").get(node.attr)
        if member:
            head = f"`ctx.{member['signature'] or member['name']}`"
            return {"contents": head + (f"\n\n{member['documentation']}" if member["documentation"] else ""), "lookback_bars": None, "last_value": None,
                    "range": {"line": line, "column": node.col_offset + 5, "end_column": node.end_col_offset + 1}}
    if isinstance(node, ast.Name):
        for item in tree.body:
            if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.name == node.id:
                args = f"({ast.unparse(item.args)})" if isinstance(item, ast.FunctionDef) else ""
                return {"contents": f"`{item.name}{args}`" + (f"\n\n{ast.get_docstring(item)}" if ast.get_docstring(item) else ""), "lookback_bars": None, "last_value": None,
                        "range": {"line": line, "column": node.col_offset + 1, "end_column": node.end_col_offset + 1}}
    return None


def _param_text(name: str, param: dict) -> str:
    low, high, step = param.get("min"), param.get("max"), param.get("step")
    span = f"range {low:g} to {high:g}" + (f" step {step:g}" if step else "") if low is not None and high is not None else "no search range"
    return f"Parameter `{name}` = {param.get('value')}, {span}."


# --- inlay hints (B-75) ----------------------------------------------------------


def inlay_hints(code: str, params: dict[str, float] | None = None, last_values: dict[str, float] | None = None) -> list[dict]:
    """Small labels after a call: a parameter's value, a formula's warm-up bars and last preview value, argument names for order calls."""
    tree = _tree(code)
    if tree is None:
        return []
    params = params or {}
    hints = []
    for node in ast.walk(tree):
        call = _ctx_call(node)
        if call is None:
            continue
        end = {"line": call.end_lineno, "column": call.end_col_offset + 1}
        first = _literal(call.args[0]) if call.args else None
        if call.func.attr == "param" and first in params:
            hints.append({**end, "label": f"= {params[first]:g}", "kind": "parameter"})
        elif call.func.attr in _FORMULA_CALLS and first is not None:
            value = (last_values or {}).get(first)
            bars = _bars(first, params)
            label = " ".join(x for x in (f"{bars} bars" if bars else "", f"= {value:.6g}" if value is not None else "") if x)
            if label:
                hints.append({**end, "label": label, "kind": "formula"})
        elif call.func.attr in _ORDER_SIGNATURES:
            for arg, name in zip(call.args, _ORDER_SIGNATURES[call.func.attr], strict=False):
                hints.append({"line": arg.lineno, "column": arg.col_offset + 1, "label": f"{name}:", "kind": "name"})
    return sorted(hints, key=lambda h: (h["line"], h["column"]))


# --- code lens (B-76) ------------------------------------------------------------


def code_lens(code: str, symbol: str, rates: dict[str, dict] | None = None, debug_from: str | None = None) -> list[dict]:
    """Run and debug lenses above on_bar and on_data; one per literal ctx.rule with its true-rate when `rates` carries it."""
    tree = _tree(code)
    if tree is None:
        return []
    lenses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {"on_bar", "on_data"}:
            for title, command in ((f"Run on {symbol}", "run_symbol"), ("Run on universe", "run_universe"), (f"Debug from {debug_from}" if debug_from else "Debug", "debug")):
                lenses.append({"line": node.lineno, "title": title, "command": command, "arguments": {"symbol": symbol, "date": debug_from}})
    for call, expression in formula_literals(code):
        if call.func.attr == "rule":
            rate = (rates or {}).get(expression)
            if rate and rate.get("true_rate") is not None:
                last = f", last true {rate['last_true_date']}" if rate.get("last_true_date") else ""
                lenses.append({"line": call.lineno, "title": f"true on {rate['true_rate'] * 100:.0f}% of bars{last}", "command": "inspect_condition",
                               "arguments": {"expression": expression, "symbol": symbol}})
    return sorted(lenses, key=lambda x: x["line"])


# --- code actions (B-24) ---------------------------------------------------------


def _edit(node: ast.AST, text: str) -> dict:
    return {"line": node.lineno, "column": node.col_offset + 1, "end_line": node.end_lineno, "end_column": node.end_col_offset + 1, "text": text}


def code_actions(code: str, line: int, column: int, end_line: int | None = None, end_column: int | None = None) -> list[dict]:
    """Quick fixes at a cursor or selection. Each action carries text edits; extraction also names the parameter to add."""
    tree = _tree(code)
    if tree is None:
        return []
    actions = []
    for call, expression in formula_literals(code):
        literal = call.args[0]
        if not _contains(literal, line, column):
            continue
        number = re.search(r"\b(\d+)\b", expression)
        operator = re.match(r"\s*([a-z_]+)\(", expression)
        if number and operator:
            name = f"{operator.group(1)}_window"
            actions.append({"title": f"Extract {number.group(1)} to parameter {name}", "kind": "refactor.extract",
                            "edits": [_edit(literal, repr(expression[:number.start()] + name + expression[number.end():]))],
                            "parameter": {"name": name, "value": float(number.group(1))}})
        single = re.fullmatch(r"\s*(sma|ema|rsi|atr|std|roc|highest|lowest)\((?:close,\s*)?(\d+)\)\s*", expression)
        if single and call.func.attr == "value":
            actions.append({"title": "Convert to an indicator object", "kind": "refactor.rewrite",
                            "edits": [_edit(call, f'ctx.indicator("{single.group(1)}", period={single.group(2)}).value')]})
    lines = code.splitlines()
    if end_line is not None and end_column is not None and end_line >= line:
        block = lines[line - 1:end_line]
        if block and any(x.strip() for x in block):
            indent = len(block[0]) - len(block[0].lstrip())
            body = "\n".join("    " + x if x.strip() else x for x in block)
            actions.append({"title": "Wrap in if ctx.position == 0", "kind": "refactor.rewrite",
                            "edits": [{"line": line, "column": 1, "end_line": end_line, "end_column": len(lines[end_line - 1]) + 1,
                                       "text": " " * indent + "if ctx.position == 0:\n" + body}]})
    strategy = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Strategy"), None)
    if strategy and not any(isinstance(n, ast.FunctionDef) and n.name == "on_fill" for n in strategy.body):
        last = strategy.body[-1]
        actions.append({"title": "Add on_fill", "kind": "quickfix",
                        "edits": [{"line": last.end_lineno + 1, "column": 1, "end_line": last.end_lineno + 1, "end_column": 1,
                                   "text": "\n    def on_fill(self, ctx, fill):\n        pass\n"}]})
    return actions


# --- imports and formatting (B-21) -----------------------------------------------


def _ruff(*args: str, code: str) -> str:
    ruff = Path(sys.executable).with_name("ruff")
    done = subprocess.run([str(ruff), *args, "--isolated", "--stdin-filename", "main.py", "-"], check=False, input=code, capture_output=True, text=True, timeout=10)
    return done.stdout if done.returncode in (0, 1) else code


def organise_imports(code: str) -> str:
    """Sort imports and drop the unused ones; code that does not parse comes back unchanged."""
    return _ruff("check", "--select", "I001,F401", "--fix", "--quiet", code=code) if _tree(code) else code


def format_range(code: str, start_line: int, end_line: int) -> str:
    """ruff format limited to whole lines; code that does not parse comes back unchanged."""
    return _ruff("format", "--line-length", "110", "--range", f"{start_line}:1-{end_line + 1}:1", code=code) if _tree(code) else code


# --- API version migrator (B-41) -------------------------------------------------


def migrate(code: str) -> dict:
    """Bring code to the current studio-api. Version 0 (no header) to 1 only stamps the header; later versions add rewrites here."""
    version = pycode.api_version(code)
    if version is not None and version >= pycode.STUDIO_API:
        return {"code": code, "from_version": version, "to_version": version, "changes": []}
    header = f"# studio-api: {pycode.STUDIO_API}\n"
    return {"code": header + code, "from_version": version or 0, "to_version": pycode.STUDIO_API, "changes": [f"Added {header.strip()}"]}
