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
    if end_line is not None and end_column is not None and end_line >= line:
        actions.extend(_extract_actions(tree, code, line, column, end_line, end_column))
    actions.extend(_refactor_actions(tree, line))
    organised = organise_imports(code)
    if organised != code:
        actions.append({"title": "Organise imports", "kind": "source.organizeImports",
                        "edits": [{"line": 1, "column": 1, "end_line": len(lines) + 1, "end_column": 1, "text": organised}]})
    strategy = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Strategy"), None)
    if strategy and not any(isinstance(n, ast.FunctionDef) and n.name == "on_fill" for n in strategy.body):
        last = strategy.body[-1]
        actions.append({"title": "Add on_fill", "kind": "quickfix",
                        "edits": [{"line": last.end_lineno + 1, "column": 1, "end_line": last.end_lineno + 1, "end_column": 1,
                                   "text": "\n    def on_fill(self, ctx, fill):\n        pass\n"}]})
    return actions


class RefactorError(ValueError):
    """An unsafe or impossible refactoring; the message says why."""


def _offsets(code: str):
    starts = [0]
    for ln in code.splitlines(keepends=True):
        starts.append(starts[-1] + len(ln))
    lines = code.splitlines()

    def at(line: int, col: int) -> int:  # ast columns are UTF-8 bytes
        return starts[line - 1] + len(lines[line - 1].encode()[:col].decode(errors="ignore"))
    return at


def _splice(code: str, edits: list[tuple[int, int, str]]) -> str:
    for a, b, text in sorted(edits, reverse=True):
        code = code[:a] + text + code[b:]
    return code


def _module(file: str) -> str:
    return file.removesuffix(".py")


def _scope_of(tree: ast.Module, node: ast.AST) -> ast.AST:
    best: ast.AST = tree
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= node.lineno and node.end_lineno <= n.end_lineno:  # type: ignore[attr-defined]
            best = n
    return best


def _inline(files: dict[str, str], file: str, line: int, column: int) -> dict[str, str]:
    code = files[file]
    tree = _tree(code)
    stmt = next((n for n in ast.walk(tree) if isinstance(n, ast.Assign) and n.lineno <= line <= n.end_lineno), None) if tree else None
    if stmt is None or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
        raise RefactorError("Put the cursor on a simple assignment such as `x = expression`.")
    name, scope = stmt.targets[0].id, _scope_of(tree, stmt)
    nodes = [n for n in ast.walk(scope) if isinstance(n, ast.Name)]
    if sum(isinstance(n.ctx, (ast.Store, ast.Del)) and n.id == name for n in nodes) != 1 or any(isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names for n in ast.walk(scope)):
        raise RefactorError(f"`{name}` is assigned more than once, so it cannot be inlined.")
    uses = [n for n in nodes if n.id == name and isinstance(n.ctx, ast.Load)]
    if not uses or any(u.lineno <= stmt.end_lineno for u in uses):
        raise RefactorError(f"`{name}` is not read after this line.")
    if any(isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) and any(u in set(ast.walk(n)) for u in uses) for n in ast.walk(scope)):
        raise RefactorError(f"`{name}` is read inside a lambda or comprehension.")
    value = ast.get_source_segment(code, stmt.value) or ""
    if len(uses) > 1 and any(isinstance(n, (ast.Call, ast.Await, ast.Yield, ast.NamedExpr)) for n in ast.walk(stmt.value)):
        raise RefactorError(f"`{name}` is read {len(uses)} times and its value calls a function; inlining would repeat the call.")
    if any(isinstance(n, ast.Name) and n.id != name and any(isinstance(m, ast.Name) and m.id == n.id and isinstance(m.ctx, ast.Store) for m in nodes) for n in ast.walk(stmt.value)):
        raise RefactorError("A name used in the value is reassigned, so inlining could change the result.")
    atom = isinstance(stmt.value, (ast.Name, ast.Constant, ast.Attribute, ast.Call, ast.Subscript))
    at = _offsets(code)
    lines = code.splitlines(keepends=True)
    edits = [(at(u.lineno, u.col_offset), at(u.end_lineno, u.end_col_offset), value if atom else f"({value})") for u in uses]
    edits.append((at(stmt.lineno, 0), at(stmt.end_lineno, 0) + len(lines[stmt.end_lineno - 1]), ""))
    return {file: _splice(code, edits)}


def _bound(tree: ast.Module) -> dict[str, ast.stmt]:
    out: dict[str, ast.stmt] = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = n
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out[(a.asname or a.name).split(".")[0]] = n
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for m in ast.walk(t):
                    if isinstance(m, ast.Name):
                        out[m.id] = n
    return out


def _stmt_range(code: str, node: ast.stmt) -> tuple[int, int]:
    at = _offsets(code)
    first = min([node.lineno, *[d.lineno for d in getattr(node, "decorator_list", [])]])
    end = at(node.end_lineno + 1, 0) if node.end_lineno < len(code.splitlines()) else len(code)
    return at(first, 0), end


def _move(files: dict[str, str], file: str, symbol: str, target: str) -> dict[str, str]:
    if not target.endswith(".py") or "/" in target or target == file:
        raise RefactorError("Choose another file in the project, such as helpers.py.")
    if target == "main.py":
        raise RefactorError("Moving into main.py is not supported.")
    code, tree = files[file], _tree(files[file])
    node = tree and next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == symbol), None)
    if not node:
        raise RefactorError(f"`{symbol}` is not a top-level function or class in {file}.")
    src, dst = _module(file), _module(target)
    bound = _bound(tree)
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} | {n.value.id for n in ast.walk(node) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    local = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)} | {a.arg for a in ast.walk(node) if isinstance(a, ast.arg)}
    imports, tied = [], sorted(x for x in used - local - {symbol} if x in bound and not isinstance(bound[x], (ast.Import, ast.ImportFrom)))
    if tied:
        raise RefactorError(f"`{symbol}` uses {', '.join(tied)} from {file}; move those too, or pass them in.")
    for x in sorted(used - local):
        imp = bound.get(x)
        if isinstance(imp, (ast.Import, ast.ImportFrom)) and (text := ast.get_source_segment(code, imp)) not in imports:
            imports.append(text)
    dst_code = files.get(target, "")
    dst_tree = _tree(dst_code)
    if dst_tree is None:
        raise RefactorError(f"{target} does not parse.")
    if any((isinstance(n, ast.ImportFrom) and n.module == src) or (isinstance(n, ast.Import) and any(a.name == src for a in n.names)) for n in ast.walk(dst_tree)):
        raise RefactorError(f"{target} imports {file}; moving `{symbol}` would create a circular import.")
    if symbol in _bound(dst_tree):
        raise RefactorError(f"{target} already defines `{symbol}`.")
    out: dict[str, str] = {}
    body = code[slice(*_stmt_range(code, node))].rstrip("\n")
    head = "\n".join(i for i in imports if i not in dst_code)
    out[target] = (dst_code.rstrip("\n") + "\n\n\n" if dst_code.strip() else "") + (head + "\n\n\n" if head else "") + body + "\n"
    rest = _splice(code, [(*_stmt_range(code, node), "")])
    for name, text in {**files, file: rest}.items():
        t = _tree(text)
        if t is None or name == target:
            continue
        if name != file:
            if any(isinstance(n, ast.Attribute) and n.attr == symbol and isinstance(n.value, ast.Name) and n.value.id == src for n in ast.walk(t)):
                raise RefactorError(f"{name} uses `{src}.{symbol}`; change it to import the symbol first.")
            hits = [n for n in t.body if isinstance(n, ast.ImportFrom) and n.module == src and any(a.name == symbol and a.asname is None for a in n.names)]
        else:
            hits = []
            if any(isinstance(n, ast.Name) and n.id == symbol for n in ast.walk(t)):
                after = [n for n in t.body if isinstance(n, (ast.Import, ast.ImportFrom))]
                at = _offsets(text)
                pos = at(after[-1].end_lineno + 1, 0) if after and after[-1].end_lineno < len(text.splitlines()) else (len(text) if after else 0)
                text = text[:pos] + (("\n" if after and not text[:pos].endswith("\n") else "") + f"from {dst} import {symbol}\n" + ("" if after else "\n\n")) + text[pos:]
                out[name] = text
                continue
        if hits:
            at = _offsets(text)
            edits = []
            for h in hits:
                keep = [a for a in h.names if a.name != symbol]
                new = (f"from {src} import " + ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in keep) + "\n") if keep else ""
                edits.append((at(h.lineno, 0), at(h.end_lineno + 1, 0) if h.end_lineno < len(text.splitlines()) else len(text), new + f"from {dst} import {symbol}\n"))
            text = _splice(text, edits)
        if text != files[name]:
            out[name] = text
    out.setdefault(file, rest)
    return out


def _signature(files: dict[str, str], file: str, symbol: str, params: list[dict]) -> dict[str, str]:
    """params is the new parameter list in order: {name, default?}. A name the function lacks is added (it needs a default); a name left out is removed."""
    tree = _tree(files[file])
    fn = tree and next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbol), None)
    if not fn:
        raise RefactorError(f"`{symbol}` is not a top-level function in {file}; methods are not supported.")
    a = fn.args
    if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs:
        raise RefactorError("Functions with *args, **kwargs, keyword-only or positional-only parameters are not supported.")
    old = [x.arg for x in a.args]
    defaults = dict(zip(reversed(old), reversed(a.defaults), strict=False))
    names = [p["name"] for p in params]
    if len(set(names)) != len(names) or not all(re.fullmatch(r"[A-Za-z_]\w*", n) for n in names):
        raise RefactorError("Parameter names must be unique identifiers.")
    new_defaults: dict[str, str | None] = {p["name"]: p.get("default") or (ast.unparse(defaults[p["name"]]) if p["name"] in defaults else None) for p in params}
    added = [n for n in names if n not in old]
    if any(new_defaults[n] is None for n in added):
        raise RefactorError("A new parameter needs a default value so existing calls stay valid.")
    seen = False
    for n in names:
        seen = seen or new_defaults[n] is not None
        if seen and new_defaults[n] is None:
            raise RefactorError("A parameter without a default cannot follow one with a default.")
    removed = [n for n in old if n not in names]
    body_names = {m.id for s in fn.body for m in ast.walk(s) if isinstance(m, ast.Name)}
    if used := [n for n in removed if n in body_names]:
        raise RefactorError(f"`{symbol}` still uses {', '.join(used)}; remove that code first.")
    src = _module(file)
    out: dict[str, str] = {}
    for name, text in files.items():
        t = _tree(text)
        if t is None:
            continue
        direct = name == file or any(isinstance(n, ast.ImportFrom) and n.module == src and any(x.name == symbol and x.asname is None for x in n.names) for n in t.body)
        viaattr = any(isinstance(n, ast.Import) and any(x.name == src and x.asname is None for x in n.names) for n in t.body)
        at, edits = _offsets(text), []
        for c in (n for n in ast.walk(t) if isinstance(n, ast.Call)):
            hit = (direct and isinstance(c.func, ast.Name) and c.func.id == symbol) or (viaattr and isinstance(c.func, ast.Attribute) and c.func.attr == symbol and isinstance(c.func.value, ast.Name) and c.func.value.id == src)
            if not hit:
                continue
            if any(isinstance(x, ast.Starred) for x in c.args) or any(k.arg is None for k in c.keywords) or len(c.args) > len(old):
                raise RefactorError(f"A call in {name}:{c.lineno} uses */** or too many arguments; edit it by hand first.")
            given = {**dict(zip(old, c.args, strict=False)), **{k.arg: k.value for k in c.keywords}}
            if bad := [k for k in given if k not in old]:
                raise RefactorError(f"A call in {name}:{c.lineno} passes unknown argument {bad[0]}.")
            miss = [n for n in old if n not in given and n in names and n not in defaults]
            if miss:
                raise RefactorError(f"A call in {name}:{c.lineno} omits {miss[0]}, which has no default.")
            parts, positional = [], True
            for n in names:
                if n not in given:
                    positional = False
                    continue
                v = ast.get_source_segment(text, given[n]) or ""
                parts.append(v if positional else f"{n}={v}")
            end = at(c.end_lineno, c.end_col_offset)
            edits.append((at(c.lineno, c.col_offset), end, (ast.get_source_segment(text, c.func) or "") + f"({', '.join(parts)})"))
        if name == file:
            def_start = at(fn.lineno, fn.col_offset)
            m = re.compile(rf"def\s+{symbol}\s*\(").search(text, def_start)
            depth, i = 1, m.end()
            while depth:
                depth += (text[i] in "([{") - (text[i] in ")]}")
                i += 1
                if i > len(text):
                    raise RefactorError("Could not read the parameter list.")
            def_text = ", ".join(n + (f": {ast.unparse(next(x.annotation for x in a.args if x.arg == n))}" if n in old and next(x for x in a.args if x.arg == n).annotation else "") + (f"={new_defaults[n]}" if new_defaults[n] is not None else "") for n in names)
            edits.append((m.end(), i - 1, def_text))
        if edits:
            out[name] = _splice(text, edits)
    return out


def refactor(files: dict[str, str], file: str, op: str, *, line: int = 1, column: int = 1, symbol: str = "", target: str = "", params: list[dict] | None = None) -> dict[str, str]:
    """Inline variable, move symbol to another file, or change a function's signature across the project. Returns only the files that change;
    raises RefactorError when the change is unsafe. shortcut: calls are matched by name (a local that shadows the function is not detected)."""
    if file not in files or _tree(files[file]) is None:
        raise RefactorError("Fix the syntax errors in this file first.")
    if op == "inline":
        return _inline(files, file, line, column)
    if op == "move":
        return _move(files, file, symbol, target)
    if op == "signature":
        return _signature(files, file, symbol, params or [])
    raise RefactorError(f"Unknown refactoring {op}.")


def _refactor_actions(tree: ast.Module, line: int) -> list[dict]:
    out = []
    stmt = next((n for n in ast.walk(tree) if isinstance(n, ast.Assign) and n.lineno == line and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)), None)
    if stmt:
        out.append({"title": f"Inline variable {stmt.targets[0].id}", "kind": "refactor.inline", "edits": [], "refactor": {"op": "inline", "line": line}})
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.lineno == line:
            out.append({"title": f"Move {n.name} to another file", "kind": "refactor.move", "edits": [], "refactor": {"op": "move", "symbol": n.name}})
            if not isinstance(n, ast.ClassDef):
                out.append({"title": f"Change signature of {n.name}", "kind": "refactor.rewrite", "edits": [], "refactor": {"op": "signature", "symbol": n.name, "params": [a.arg for a in n.args.args]}})
    return out


def _fresh(tree: ast.AST, base: str) -> str:
    taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    name, i = base, 1
    while name in taken:
        i += 1
        name = f"{base}_{i}"
    return name


def _extract_actions(tree: ast.Module, code: str, line: int, column: int, end_line: int, end_column: int) -> list[dict]:
    """Extract variable (selected expression) and extract function (selected whole statements of a function body).
    shortcut: columns are read as character offsets (ast uses UTF-8 bytes) and extracted code takes every outer name it reads
    as a parameter; an expression inside a lambda or comprehension, or statements with return/yield/break/continue, are left alone."""
    lines = code.splitlines()
    out: list[dict] = []
    first, last = lines[line - 1], lines[end_line - 1]
    col, end_col = column, end_column
    while col <= len(first) and first[col - 1].isspace():
        col += 1
    while end_col > 1 and end_col - 2 < len(last) and last[end_col - 2].isspace():
        end_col -= 1
    parents = {id(c): p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    expr = next((n for n in ast.walk(tree) if isinstance(n, ast.expr) and (n.lineno, n.col_offset + 1, n.end_lineno, n.end_col_offset + 1) == (line, col, end_line, end_col)), None)
    if expr is not None and not isinstance(getattr(expr, "ctx", None), (ast.Store, ast.Del)):
        chain, node = [], expr
        while id(node) in parents:
            node = parents[id(node)]
            chain.append(node)
        stmt = next((n for n in chain if isinstance(n, ast.stmt)), None)
        scoped = any(isinstance(n, (ast.Lambda, ast.comprehension, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for n in chain[: chain.index(stmt)]) if stmt else True
        if stmt is not None and not scoped and not isinstance(stmt, (ast.While, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = _fresh(tree, "value")
            text = ast.get_source_segment(code, expr) or ""
            out.append({"title": f"Extract variable {name}", "kind": "refactor.extract", "edits": [
                {"line": stmt.lineno, "column": 1, "end_line": stmt.lineno, "end_column": 1, "text": " " * stmt.col_offset + f"{name} = {text}\n"},
                _edit(expr, name)]})
    func = next((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.body[0].lineno <= line and end_line <= n.end_lineno), None)
    if func is not None:
        inner = [n for n in ast.walk(func) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not func and n.body[0].lineno <= line and end_line <= n.end_lineno]
        func = inner[-1] if inner else func
        body = next((b for n in ast.walk(func) for f in ("body", "orelse", "finalbody") if isinstance(b := getattr(n, f, None), list) and b and any(
            isinstance(x, ast.stmt) and x.lineno >= line for x in b)
            and (picked := [x for x in b if isinstance(x, ast.stmt) and line <= x.lineno and x.end_lineno <= end_line]) and picked[0].lineno == line and picked[-1].end_lineno == end_line), None)
        picked = [x for x in body or [] if line <= x.lineno and x.end_lineno <= end_line]
        nodes = [m for x in picked for m in ast.walk(x)]
        if picked and not any(isinstance(m, (ast.Return, ast.Yield, ast.YieldFrom, ast.Await, ast.Break, ast.Continue)) for m in nodes):
            bound = {a.arg for a in ast.walk(func.args) if isinstance(a, ast.arg)} | {m.id for m in ast.walk(func) if isinstance(m, ast.Name) and isinstance(m.ctx, ast.Store)
                     and not line <= m.lineno <= end_line}
            stored = {m.id for m in nodes if isinstance(m, ast.Name) and isinstance(m.ctx, ast.Store)}
            args = sorted({m.id for m in nodes if isinstance(m, ast.Name) and isinstance(m.ctx, ast.Load) and m.id in bound})
            after = {m.id for m in ast.walk(func) if isinstance(m, ast.Name) and isinstance(m.ctx, ast.Load) and m.lineno > end_line}
            returns = sorted(stored & after)
            name = _fresh(tree, "extracted")
            indent = picked[0].col_offset
            call = f"{name}({', '.join(args)})"
            if returns:
                call = f"{', '.join(returns)} = {call}"
            body_text = "\n".join(("    " + x[indent:]) if x.strip() else x for x in lines[line - 1:end_line])
            tail = f"\n    return {', '.join(returns)}" if returns else ""
            top = next(n for n in tree.body if n.lineno <= line <= n.end_lineno)
            top_line = min([top.lineno, *[d.lineno for d in getattr(top, "decorator_list", [])]])
            out.append({"title": f"Extract function {name}", "kind": "refactor.extract", "edits": [
                {"line": top_line, "column": 1, "end_line": top_line, "end_column": 1, "text": f"def {name}({', '.join(args)}):\n{body_text}{tail}\n\n\n"},
                {"line": line, "column": 1, "end_line": end_line, "end_column": len(last) + 1, "text": " " * indent + call}]})
    return out


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
