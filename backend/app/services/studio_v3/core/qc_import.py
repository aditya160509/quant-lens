"""QuantConnect import (B-163): keep the user's code, swap the QCAlgorithm calls Studio can run, list the rest.

Line-preserving AST edits: only the spans of recognised calls change, so comments, formatting and helper code survive.
Anything Studio cannot express is commented out and returned with a reason before the result is saved.
"""

from __future__ import annotations

import ast
from typing import Any

from . import pycode

INDICATORS = {"SMA": "sma", "EMA": "ema", "RSI": "rsi", "ATR": "atr", "STD": "std", "ROC": "roc",
              "MAX": "highest", "MIN": "lowest", "MOM": "roc"}
ORDERS = {"MarketOrder": "market_order", "LimitOrder": "limit_order", "StopMarketOrder": "stop_order",
          "StopLimitOrder": "stop_limit_order"}
POSITION_FIELDS = {"Quantity": "quantity", "Invested": "invested", "UnrealizedProfit": "unrealized_profit",
                   "AveragePrice": "average_price", "Price": "price"}
FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
DROPPED = {"SetCash", "SetBenchmark", "SetStartDate", "SetEndDate", "SetWarmUp", "AddEquity", "SetBrokerageModel",
           "SetSecurityInitializer", "SetTimeZone", "SetExecution", "SetDataNormalizationMode", "SetAccountType"}
def _call(node: ast.AST) -> str | None:
    """The QC name when `node` is `self.SomeCall(...)`."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"):
        return node.func.attr
    return None


def _is_indicator(node: ast.AST) -> bool:
    return _call(node) in INDICATORS


class _Import:
    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))
        self.edits: list[tuple[int, int, str]] = []
        self.converted: list[dict[str, Any]] = []
        self.unconverted: list[dict[str, Any]] = []
        self.symbols: list[str] = []
        self.settings: dict[str, Any] = {}
        self.warmup: int | None = None
        self.event_name: str | None = None

    # -- source plumbing -------------------------------------------------------

    def segment(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source, node) or ""

    def span(self, node: ast.AST) -> tuple[int, int]:
        return (self.starts[node.lineno - 1] + node.col_offset, self.starts[node.end_lineno - 1] + node.end_col_offset)

    def edit(self, node: ast.AST, text: str) -> None:
        self.edits.append((*self.span(node), text))

    def note(self, node: ast.AST, after: str, reason: str = "") -> None:
        row = {"line": node.lineno, "before": self.segment(node).strip().splitlines()[0][:200], "after": after}
        if reason:
            row["reason"] = reason
        self.converted.append(row)

    def refuse(self, node: ast.AST, reason: str) -> None:
        self.unconverted.append({"line": node.lineno, "source": self.segment(node).strip().splitlines()[0][:200],
                                 "reason": reason})

    def comment_out(self, node: ast.AST, reason: str) -> None:
        first, last = node.lineno - 1, node.end_lineno - 1
        block = "".join(
            self.lines[i] if self.lines[i].lstrip().startswith("#") else f"# {self.lines[i]}"
            for i in range(first, last + 1)
        )
        self.edits.append((self.starts[first], self.starts[last + 1] if last + 1 < len(self.starts) else len(self.source), block))
        self.refuse(node, reason)

    # -- expressions -----------------------------------------------------------

    def render(self, node: ast.AST) -> str:
        text = self.convert(node)
        return text if text is not None else self.segment(node)

    def symbol(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value.upper()
        if isinstance(node, ast.Attribute) and node.attr == "Symbol":
            return self.symbol(node.value)
        if _call(node) == "AddEquity" and node.args:
            return self.symbol(node.args[0])
        return None

    def convert(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Call):
            return self.convert_call(node)
        if isinstance(node, ast.Attribute):
            return self.convert_attribute(node)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in {"data", "slice"}:
            return self.convert_slice(node)
        return None

    def convert_call(self, node: ast.Call) -> str | None:
        name = _call(node)
        if name is None:
            return None
        args = [self.render(arg) for arg in node.args]
        if name in INDICATORS:
            symbol = self.symbol(node.args[0]) if node.args else None
            period = args[1] if len(args) > 1 else None
            if symbol is None or period is None:
                return None
            return f'ctx.indicator("{INDICATORS[name]}", "{symbol}", {period})'
        if name == "SetHoldings" and len(args) >= 2:
            return f"ctx.set_holdings({args[0]}, {args[1]})"
        if name in ORDERS and len(args) >= 2:
            return f"ctx.{ORDERS[name]}({', '.join(args)})"
        if name == "Liquidate":
            return f"ctx.liquidate({args[0]})" if args else "ctx.liquidate()"
        if name in {"Buy", "Sell"} and len(args) >= 2:
            quantity = args[1] if name == "Buy" else f"-{args[1]}"
            return f"ctx.market_order({args[0]}, {quantity})"
        if name == "History" and node.args:
            symbol = self.symbol(node.args[0])
            window = args[1] if len(args) > 1 else "252"
            if symbol is None:
                return None
            return f'ctx.history("close", {window}, "{symbol}")'
        if name in {"Debug", "Log", "Error"} and args:
            level = '' if name != "Error" else ', "error"'
            return f"ctx.log({args[0]}{level})"
        if name == "Plot":
            if len(args) == 3 and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args[:2]):
                return f'ctx.plot("{node.args[0].value}.{node.args[1].value}", {args[2]})'
            return None
        return None

    def convert_attribute(self, node: ast.Attribute) -> str | None:
        if isinstance(node.value, ast.Name) and node.value.id == self.event_name:
            fill = {"FillPrice": "price", "Price": "price", "FillQuantity": "quantity", "Symbol": "symbol", "Fee": "fee"}
            return f"fill.{fill[node.attr]}" if node.attr in fill else None
        # self.Portfolio / self.Time / self.Securities
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            if node.attr == "Time":
                return "ctx.date"
            if node.attr == "Portfolio":
                return "ctx.portfolio"
            return None
        portfolio = {"Cash": "ctx.portfolio.cash", "TotalPortfolioValue": "ctx.portfolio.total_value",
                     "Invested": "ctx.portfolio.invested"}
        if (isinstance(node.value, ast.Attribute) and node.value.attr == "Portfolio"
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "self"):
            return portfolio.get(node.attr)
        # data["SPY"].Close and self.Securities["SPY"].Close
        if node.attr in FIELDS or node.attr == "Price":
            inner = node.value
            if isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name) and inner.value.id in {"data", "slice"}:
                symbol = self.symbol(inner.slice)
                if symbol:
                    return f'ctx.bar("{symbol}").{FIELDS.get(node.attr, "close")}'
        if isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Attribute):
            base = node.value.value
            if isinstance(base.value, ast.Name) and base.value.id == "self" and base.attr in {"Portfolio", "Securities"}:
                key = self.symbol(node.value.slice) or self.render(node.value.slice)
                if base.attr == "Portfolio" and node.attr in POSITION_FIELDS:
                    return f"ctx.pos({key}).{POSITION_FIELDS[node.attr]}"
                if base.attr == "Securities" and node.attr == "Price":
                    return f"ctx.bar({key}).close"
        # indicator.Current.Value and indicator.IsReady, for a call or a self.<name> handle
        if node.attr == "Value" and isinstance(node.value, ast.Attribute) and node.value.attr == "Current":
            inner = node.value.value
            if _is_indicator(inner) or self.handle(inner):
                return f"{self.render(inner)}.value"
        if node.attr == "IsReady" and (_is_indicator(node.value) or self.handle(node.value)):
            return f"{self.render(node.value)}.ready"
        return None

    @staticmethod
    def handle(node: ast.AST) -> bool:
        """`self.sma` when the name is bound to an indicator handle."""
        return (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"
                and node.attr[:1].islower())

    def convert_slice(self, node: ast.Subscript) -> str | None:
        symbol = self.symbol(node.slice)
        if symbol is None:
            return None
        return f'ctx.bar("{symbol}")'


class Converter:
    def __init__(self, source: str):
        self.state = _Import(source)
        try:
            self.tree = ast.parse(source)
        except SyntaxError as e:
            self.tree = None
            self.error = f"SyntaxError: {e.msg}"
        else:
            self.error = ""
        self.parents: dict[ast.AST, ast.AST] = {}
        if self.tree is not None:
            for parent in ast.walk(self.tree):
                for child in ast.iter_child_nodes(parent):
                    self.parents[child] = parent

    def run(self) -> dict[str, Any]:
        state = self.state
        if self.tree is None:
            return {"ok": False, "code": state.source, "symbols": [], "settings": {}, "converted": [], "unconverted": [],
                    "problems": [{"severity": "error", "file": "main.py", "line": 1, "column": 1, "end_column": 1,
                                  "code": "syntax", "message": self.error}]}
        strategy = self.find_strategy()
        if strategy is None:
            return {"ok": False, "code": state.source, "symbols": [], "settings": {}, "converted": [], "unconverted": [],
                    "problems": [{"severity": "error", "file": "main.py", "line": 1, "column": 1, "end_column": 1,
                                  "code": "no-qcalgorithm",
                                  "message": "No class subclassing QCAlgorithm was found. Paste a QuantConnect algorithm."}]}
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.rewrite_statement(node)
        self.rewrite_class(strategy)
        code = self.apply()
        problems = pycode.lint(code, {})
        return {"ok": not any(p["severity"] == "error" for p in problems), "code": code, "symbols": state.symbols,
                "settings": {k: v for k, v in state.settings.items() if v is not None},
                "warmup": state.warmup, "converted": state.converted, "unconverted": state.unconverted,
                "problems": problems}

    def find_strategy(self) -> ast.ClassDef | None:
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef) and any(
                (isinstance(base, ast.Name) and base.id == "QCAlgorithm") for base in node.bases
            ):
                return node
        return None

    def rewrite_class(self, strategy: ast.ClassDef) -> None:
        state = self.state
        header = self.state.lines[strategy.lineno - 1]
        indent = " " * (strategy.col_offset + 4)
        state.edits.append((state.starts[strategy.lineno - 1], state.starts[strategy.lineno - 1] + len(header),
                            f"{' ' * strategy.col_offset}class Strategy:\n"))
        state.note(strategy, "class Strategy", "the Studio entry point")
        if state.lines[strategy.lineno - 1].rstrip().endswith(":"):
            state.edits.append((state.starts[strategy.lineno], state.starts[strategy.lineno], f"{indent}warmup = 0\n"))
        for node in strategy.body:
            self.rewrite_statement(node)

    def rewrite_statement(self, node: ast.stmt) -> None:
        state = self.state
        if isinstance(node, ast.FunctionDef):
            self.rewrite_method(node)
            return
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("AlgorithmImports"):
            state.comment_out(node, "QuantConnect runtime imports are not needed; numpy, pandas, math, statistics and scipy.stats are available")
            return
        if isinstance(node, ast.ImportFrom) and node.module in {"datetime", "dateutil", "System"}:
            state.comment_out(node, "Studio exposes the current bar date as ctx.date (YYYY-MM-DD); datetime is not importable")
            return
        if isinstance(node, ast.Import) and any(alias.name in {"AlgorithmImports", "datetime"} for alias in node.names):
            state.comment_out(node, "This import is not available; ctx.date is an ISO date string")
            return
        self.rewrite_body(node)

    def rewrite_method(self, node: ast.FunctionDef) -> None:
        state = self.state
        rename = {"Initialize": "init", "OnData": "on_data", "OnWarmUpFinished": "on_warmup_done"}
        if node.name in rename:
            state.edits.append((state.starts[node.lineno - 1] + node.col_offset,
                                state.starts[node.lineno - 1] + node.col_offset + len("def ") + len(node.name),
                                f"def {rename[node.name]}"))
            if node.name == "OnData":
                self.rename_first_argument(node, "ctx")
            else:
                self.rename_first_argument(node, "ctx", insert=True)
            for statement in node.body:
                self.rewrite_body(statement)
            return
        if node.name == "OnOrderEvent" and len(node.args.args) >= 2:
            text = state.lines[node.lineno - 1]
            start = state.starts[node.lineno - 1] + node.col_offset
            state.edits.append((start, state.starts[node.lineno - 1] + text.rindex(")") + 1, "def on_fill(self, ctx, fill)"))
            state.note(node, "def on_fill(self, ctx, fill)", "the fill callback")
            state.event_name = node.args.args[1].arg
            for statement in node.body:
                self.rewrite_body(statement)
            state.event_name = None
            return
        if node.name.startswith("On"):
            state.comment_out(node, f"{node.name} has no Studio equivalent yet; the body is kept as comments")
            return
        for statement in node.body:
            self.rewrite_body(statement)

    def rename_first_argument(self, node: ast.FunctionDef, name: str, *, insert: bool = False) -> None:
        state = self.state
        params = node.args.args
        if len(params) >= 2:
            second = params[1]
            state.edits.append((state.starts[second.lineno - 1] + second.col_offset,
                                state.starts[second.lineno - 1] + second.col_offset + len(second.arg), name))
        elif insert:
            text = state.lines[node.lineno - 1]
            close = text.index("):") if "):" in text else text.index(")")
            state.edits.append((state.starts[node.lineno - 1] + close, state.starts[node.lineno - 1] + close, f", {name}"))

    def rewrite_body(self, node: ast.stmt) -> None:
        state = self.state
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            name = _call(node.value)
            if name in DROPPED:
                self.drop_setting(node, node.value, name)
                return
            if name == "Schedule" or (isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Attribute)
                                      and node.value.func.value.attr == "Schedule"):
                state.comment_out(node, "Studio has no scheduler; move this into a rebalance(self, ctx) method")
                return
            if name in {"SetHoldings", "MarketOrder", "LimitOrder", "StopMarketOrder", "StopLimitOrder", "Liquidate",
                        "Buy", "Sell", "Debug", "Log", "Error", "Plot", "History"}:
                text = state.render(node.value)
                state.edit(node.value, text)
                state.note(node.value, text)
                return
            if name and name[0].isupper():
                state.comment_out(node, f"{name} has no Studio equivalent; the call is kept as a comment")
                return
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _call(node.value) in DROPPED:
            self.drop_setting(node, node.value, _call(node.value))
            return
        if isinstance(node, (ast.If, ast.While)) and self.mentions_unknown(node.test):
            state.comment_out(node, "The condition reads a QuantConnect-only value; the block is kept as comments")
            return
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With)):
            for child in node.body + getattr(node, "orelse", []):
                self.rewrite_body(child)
        # expressions inside ordinary statements (assignments, prints, returns)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                self.rewrite_expression(child)

    def mentions_unknown(self, node: ast.AST) -> bool:
        for item in ast.walk(node):
            if (isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id == "self"
                    and item.attr in {"IsWarmingUp", "IsLiveMode", "UtcTime", "Securities", "Schedule"}):
                return True
            if isinstance(item, ast.Name) and item.id in {"data", "slice"}:
                parent = self.parents.get(item)
                if not (isinstance(parent, ast.Subscript) and parent.value is item):
                    return True
        return False

    def rewrite_expression(self, node: ast.expr) -> None:
        state = self.state

        def visit(item: ast.AST, covered: bool) -> None:
            text = state.convert(item) if isinstance(item, ast.expr) else None
            if text is not None:
                if not covered:
                    state.edit(item, text)
                    state.note(item, text)
                return
            for child in ast.iter_child_nodes(item):
                visit(child, covered)

        visit(node, False)

    def drop_setting(self, statement: ast.stmt, call: ast.Call, name: str) -> None:
        state = self.state
        literal = [arg.value for arg in call.args if isinstance(arg, ast.Constant)]
        if name == "SetCash" and literal:
            state.settings["capital"] = float(literal[0])
        elif name == "SetWarmUp" and literal:
            state.warmup = int(literal[0])
            self.replace_warmup(int(literal[0]))
        elif name == "SetBenchmark" and literal:
            state.settings["benchmark"] = str(literal[0]).upper()
        elif name in {"SetStartDate", "SetEndDate"} and len(literal) == 3:
            state.settings["start" if name == "SetStartDate" else "end"] = f"{int(literal[0]):04d}-{int(literal[1]):02d}-{int(literal[2]):02d}"
        elif name == "AddEquity" and call.args:
            symbol = state.symbol(call.args[0])
            if symbol and symbol not in state.symbols:
                state.symbols.append(symbol)
            if len(call.args) > 1 and not (isinstance(call.args[1], ast.Attribute) and call.args[1].attr == "Daily"):
                state.unconverted.append({"line": statement.lineno, "source": state.segment(statement).strip()[:200],
                                          "reason": "Only daily resolution is available; add the symbol to the universe and use daily bars"})
                return
        elif name in {"SetBrokerageModel", "SetSecurityInitializer", "SetTimeZone", "SetExecution",
                      "SetDataNormalizationMode", "SetAccountType"}:
            state.unconverted.append({"line": statement.lineno, "source": state.segment(statement).strip()[:200],
                                      "reason": f"{name} has no Studio setting; costs and fills come from the engine settings"})
        state.edit(statement, "pass")
        state.note(statement, name, "dropped")

    def replace_warmup(self, bars: int) -> None:
        state = self.state
        for index, (start, end, text) in enumerate(state.edits):
            if text.strip() == "warmup = 0":
                indent = text[: len(text) - len(text.lstrip())]
                state.edits[index] = (start, end, f"{indent}warmup = {bars}\n")
                return

    def apply(self) -> str:
        code = self.state.source
        for start, end, text in sorted(self.state.edits, key=lambda item: (item[0], item[1]), reverse=True):
            code = code[:start] + text + code[end:]
        return code


def convert(source: str) -> dict[str, Any]:
    """Convert one QuantConnect algorithm. Nothing is saved; `unconverted` names every line left behind."""
    return Converter(source).run()
