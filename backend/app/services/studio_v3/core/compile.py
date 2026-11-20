"""Spec -> findings (compile) and spec + bars -> signal arrays. No LLM anywhere."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.services.shared.formula import SignalError

from . import formula, pycode
from .spec import Strategy

ROLES = ("entry_long", "exit_long", "entry_short", "exit_short", "score", "market_filter")
ROLE_LABEL = {"entry_long": "Buy when", "exit_long": "Sell when", "entry_short": "Short when", "exit_short": "Cover when", "score": "Rank by", "market_filter": "Trade only when"}


def compile_spec(spec: Strategy) -> dict:
    """Findings for every rule, each with the line (role order), character span and token. `ok` is false on any error."""
    findings: list[dict] = []
    definitions = spec.parameter_definitions()
    params = {name: param.value for name, param in definitions.items()}
    used: set[str] = set()
    rule_count = 0
    for line, role in enumerate(ROLES, 1):
        text = getattr(spec, role)
        if not text.strip():
            continue
        try:
            parsed = formula.parse(text, params)
            names, _ = formula.tokens(parsed)
            used |= names
            if role != "score":
                rule_count += 1 + sum(
                    isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr))
                    for node in ast.walk(parsed)
                )
        except SignalError as e:
            findings.append({"severity": "error", "role": role, "line": line, "start": e.start, "end": e.end, "token": text[e.start:e.end], "message": e.message,
                             "lookahead": e.message.startswith("Look-ahead")})
    if spec.code.strip():
        findings += pycode.check_project(spec.code, params, spec.files)
        used |= {n for n in params if f'"{n}"' in spec.code or f"'{n}'" in spec.code}
    else:
        if not (spec.entry_long.strip() or spec.entry_short.strip()):
            findings.append({"severity": "error", "role": "entry_long", "line": 1, "start": 0, "end": 0, "token": "", "message": "No entry rule yet"})
        e = spec.exits
        for side, entry, exit_ in (("long", spec.entry_long, spec.exit_long), ("short", spec.entry_short, spec.exit_short)):
            if entry.strip() and not (exit_.strip() or e.stop or e.stop_atr or e.target or e.trail or e.time_stop):
                findings.append({"severity": "warning", "role": f"exit_{side}", "line": ROLES.index(f"exit_{side}") + 1, "start": 0, "end": 0, "token": "",
                                 "message": f"No exit for {side} positions: they are held to the end"})
        if spec.sizing.mode == "risk" and not (e.stop or e.stop_atr):
            findings.append({"severity": "error", "role": "sizing", "line": 0, "start": 0, "end": 0, "token": "risk", "message": "Risk per trade needs a stop"})
        if spec.sizing.mode == "score" and not spec.score.strip():
            findings.append({"severity": "error", "role": "sizing", "line": 0, "start": 0, "end": 0, "token": "score", "message": "Weight by score needs a Rank by rule"})
        if spec.sizing.mode not in ("equal", "score", "risk_parity") and not spec.sizing.value:
            findings.append({"severity": "error", "role": "sizing", "line": 0, "start": 0, "end": 0, "token": spec.sizing.mode, "message": "Position size is zero"})
        if e.scale_at and not e.scale_frac:
            findings.append({"severity": "warning", "role": "exits", "line": 0, "start": 0, "end": 0, "token": "scale_at", "message": "Scale-out level set without a share to sell"})
        if e.scale_at2 and not e.scale_frac2:
            findings.append({"severity": "warning", "role": "exits", "line": 0, "start": 0, "end": 0, "token": "scale_at2", "message": "Second scale-out level set without a share to sell"})
        if e.scale_at2 and e.scale_at and e.scale_at2 <= e.scale_at:
            findings.append({"severity": "warning", "role": "exits", "line": 0, "start": 0, "end": 0, "token": "scale_at2", "message": "The second scale-out level must be above the first"})
    for name in sorted(set(params) - used):
        findings.append({"severity": "warning", "role": "params", "line": 0, "start": 0, "end": 0, "token": name, "message": f"Parameter '{name}' is not used by any rule"})
    block_count = len(spec.blocks)
    tunable = {
        name for name, param in definitions.items()
        if param.min is not None and param.max is not None and param.min < param.max
    }
    if block_count > 200:
        severity = "error" if block_count > 1000 else "warning"
        message = (
            f"Strategy has {block_count} blocks. Reduce it to 1,000 blocks or fewer."
            if severity == "error" else f"Strategy has {block_count} blocks. Review strategies above 200 blocks."
        )
        findings.append({"severity": severity, "role": "blocks", "line": 0, "start": 0, "end": 0,
                         "token": "blocks", "message": message})
    if len(tunable) > 8:
        findings.append({"severity": "warning", "role": "params", "line": 0, "start": 0, "end": 0,
                         "token": "params", "message": f"Strategy has {len(tunable)} optimisable parameters. Review strategies above eight."})
    complexity = {
        "parameter_count": len(params),
        "formula_rule_count": rule_count,
        "degrees_of_freedom": len(used & tunable),
    }
    return {"ok": not any(f["severity"] == "error" for f in findings), "findings": findings, "hash": spec.hash(),
            "description": describe(spec), "complexity": complexity,
            "parameters": {name: param.model_dump() for name, param in definitions.items()}}


@dataclass
class Signals:
    entries: np.ndarray  # int8: +1 long, -1 short
    exits: np.ndarray  # int8 bits: 1 closes longs, 2 closes shorts
    score: np.ndarray | None
    stop_dist: np.ndarray | None
    size_vol: np.ndarray | None = None  # annualised 20-day volatility, for vol-target sizing


def _bool(expr: str, bars, dates, params, cache) -> np.ndarray:
    out = formula.evaluate(expr, bars, dates, params, cache)
    return out if out.dtype == bool else np.nan_to_num(out) > 0


def signals(spec: Strategy, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float] | None = None, *,
            symbols: list[str] | None = None, output: dict | None = None) -> Signals:
    params = {**spec.values(), **(params or {})}
    cache: dict = {}
    shape = bars["close"].shape
    if spec.code.strip():
        entries, exits = pycode.run(spec.code, bars, dates, params, symbols=symbols, cache=cache, output=output, files=spec.files)
        _gate(spec, entries, exits, bars, dates, params, cache)
        dist = spec.exits.stop_atr * formula.evaluate("atr(14)", bars, dates, params, cache) if spec.exits.stop_atr else None
        return Signals(entries, exits, None, None if dist is None else np.nan_to_num(dist), _vol(spec, bars, dates, params, cache))
    entries, exits = np.zeros(shape, dtype=np.int8), np.zeros(shape, dtype=np.int8)
    shorts = _bool(spec.entry_short, bars, dates, params, cache) if spec.entry_short.strip() else None
    longs = _bool(spec.entry_long, bars, dates, params, cache) if spec.entry_long.strip() else None
    if shorts is not None:
        entries[shorts] = -1
    if longs is not None:
        entries[longs] = 1
    if spec.exit_long.strip():
        exits[_bool(spec.exit_long, bars, dates, params, cache)] |= 1
    if spec.exit_short.strip():
        exits[_bool(spec.exit_short, bars, dates, params, cache)] |= 2
    if spec.exits.opposite_signal:
        if shorts is not None:
            exits[shorts] |= 1  # an exit bit only closes a position of its own side
        if longs is not None:
            exits[longs] |= 2
    if spec.exits.end_of_week:
        exits[_last_week_bars(dates)] |= 3
    if spec.frequency != "daily":
        entries[~_period_starts(dates, "W-FRI" if spec.frequency == "week_start" else "M")] = 0
    _gate(spec, entries, exits, bars, dates, params, cache)
    score = formula.evaluate(spec.score, bars, dates, params, cache).astype(float) if spec.score.strip() else None
    dist = spec.exits.stop_atr * formula.evaluate("atr(14)", bars, dates, params, cache) if spec.exits.stop_atr else None
    return Signals(entries, exits, score, None if dist is None else np.nan_to_num(dist), _vol(spec, bars, dates, params, cache))


def _gate(spec: Strategy, entries, exits, bars, dates, params, cache) -> None:
    """Market rule: no entries while it is false, and everything closes on the bar it turns false."""
    if not spec.market_filter.strip():
        return
    on = _bool(spec.market_filter, bars, dates, params, cache)
    entries[~on] = 0
    exits[~on] |= 3


def market_on(spec: Strategy, bars, dates, params=None) -> np.ndarray:
    """The market rule per bar and name (all true when there is none)."""
    return _bool(spec.market_filter, bars, dates, params, {}) if spec.market_filter.strip() else np.ones(bars["close"].shape, dtype=bool)


def _vol(spec: Strategy, bars, dates, params, cache) -> np.ndarray | None:
    if spec.sizing.mode not in {"vol_target", "risk_parity"}:
        return None
    return formula.evaluate("std(returns, 20)", bars, dates, params, cache) * np.sqrt(252)


def _period_starts(dates: pd.DatetimeIndex, frequency: str) -> np.ndarray:
    """True on the first observed bar of each week or month."""
    periods = dates.to_period(frequency)
    starts = np.ones(len(periods), dtype=bool)
    if len(periods):
        starts[1:] = periods[1:] != periods[:-1]
    return starts


def _last_week_bars(dates: pd.DatetimeIndex) -> np.ndarray:
    """True on the last observed session of each week, which is where an end-of-week exit fires."""
    periods = dates.to_period("W-FRI")
    last = np.ones(len(periods), dtype=bool)
    if len(periods):
        last[:-1] = periods[:-1] != periods[1:]
    return last


_EXTRA_BARS = {"crosses_above": 1, "crosses_below": 1, "weekly": 5, "monthly": 21}


def _bars_needed(node: ast.AST) -> int:
    """Bars a formula needs before every operator has a value."""
    if isinstance(node, ast.Expression):
        return _bars_needed(node.body)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in formula.OPERATORS:
        inner = max((_bars_needed(arg) for arg in node.args), default=0)
        names = formula.OPERATORS[node.func.id][1]
        window = 0
        if "n" in names and names.index("n") < len(node.args):
            arg = node.args[names.index("n")]
            if isinstance(arg, ast.Constant) and type(arg.value) is int:
                window = arg.value
        return inner + max(window, _EXTRA_BARS.get(node.func.id, 0))
    return max((_bars_needed(child) for child in ast.iter_child_nodes(node)), default=0)


def warmup_bars(spec: Strategy) -> int:
    """The bar count the strategy needs before every rule has a value (its class attribute or the longest window)."""
    params = spec.values()
    needs = 0
    for role in ROLES:
        text = getattr(spec, role).strip()
        if text:
            try:
                needs = max(needs, _bars_needed(formula.parse(text, params)))
            except SignalError:
                continue
    if spec.code.strip():
        try:
            tree = ast.parse(spec.code)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == "Strategy":
                    for item in node.body:
                        if (isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant)
                                and type(item.value.value) is int
                                and any(isinstance(t, ast.Name) and t.id == "warmup" for t in item.targets)):
                            needs = max(needs, item.value.value)
        for expression in pycode.exprs(spec.code):
            try:
                needs = max(needs, _bars_needed(formula.parse(expression, params)))
            except SignalError:
                continue
    return needs


def data_used(spec: Strategy) -> list[dict]:
    """Per rule: the price fields it reads and the literal windows it asks for."""
    params = spec.values()
    rows = []
    for role in ROLES:
        text = getattr(spec, role).strip()
        if not text:
            continue
        try:
            parsed = formula.parse(text, params)
        except SignalError:
            continue
        names, _ = formula.tokens(parsed)
        windows = sorted({
            arg.value for node in ast.walk(parsed) if isinstance(node, ast.Call)
            for arg in node.args if isinstance(arg, ast.Constant) and type(arg.value) is int
        })
        rows.append({"role": role, "fields": sorted(names & set(formula.FIELDS)), "windows": windows})
    return rows


def _pct(v: float) -> str:
    return f"{v * 100:g}%"


def describe(spec: Strategy) -> str:
    """"What it does": three plain lines built from the spec alone (B-9)."""
    if spec.code.strip() and not spec.entry_long.strip() and not spec.entry_short.strip():
        hook = "on_data" if re.search(r"def\s+on_data\s*\(", spec.code) else "on_bar"
        return f"Python strategy: orders come from {hook}."
    e, s = spec.exits, spec.sizing
    entry = [f"{ROLE_LABEL[r]} {getattr(spec, r).strip()}" for r in ("entry_long", "entry_short") if getattr(spec, r).strip()]
    out = [f"{ROLE_LABEL[r]} {getattr(spec, r).strip()}" for r in ("exit_long", "exit_short") if getattr(spec, r).strip()]
    out += [t for t in (f"stop {e.stop_atr:g} ATR" if e.stop_atr else f"stop {_pct(e.stop)}" if e.stop else "", f"target {_pct(e.target)}" if e.target else "",
                        f"trailing stop {_pct(e.trail)}" if e.trail else "", f"time stop {e.time_stop} bars" if e.time_stop else "",
                        f"stop to entry after {_pct(e.breakeven)}" if e.breakeven else "",
                        f"sell {_pct(e.scale_frac)} at {_pct(e.scale_at)}" if e.scale_at and e.scale_frac else "",
                        f"then {_pct(e.scale_frac2)} at {_pct(e.scale_at2)}" if e.scale_at2 and e.scale_frac2 else "",
                        "an opposite entry closes the other side" if e.opposite_signal else "",
                        "close on the last bar of the week" if e.end_of_week else "") if t]
    risk = spec.risk
    guard = [t for t in (f"stop everything at {_pct(risk.max_drawdown)} drawdown" if risk.max_drawdown else "",
                         f"stop everything at {_pct(risk.max_daily_loss)} in one session" if risk.max_daily_loss else "",
                         f"at most {_pct(risk.max_position)} of equity per name" if risk.max_position else "",
                         f"at most {_pct(risk.max_gross)} of equity invested" if risk.max_gross else "") if t]
    size = {"shares": f"{s.value:g} shares", "cash": f"${s.value:,.0f}", "pct_equity": f"{_pct(s.value)} of equity", "risk": f"{_pct(s.value)} of equity at risk to the stop",
            "equal": "an equal share of equity", "vol_target": f"an equal share scaled to {_pct(s.value)} annual volatility",
            "score": "an equal share weighted by score", "kelly": f"the Kelly fraction of closed trades, at most {_pct(s.value)}",
            "risk_parity": "an equal-risk share weighted by inverse volatility"}[s.mode]
    cap = f", at most {s.max_positions} positions" if s.max_positions else ""
    rank = f", best {spec.score.strip()} first" if spec.score.strip() else ""
    rank += f". Only while {spec.market_filter.strip()}, else cash" if spec.market_filter.strip() else ""
    when = "" if spec.frequency == "daily" else f" Entries only on the first bar of each {'week' if spec.frequency == 'week_start' else 'month'}."
    return "\n".join([("; ".join(entry) or "No entry rule") + "." + when, "Exit: " + ("; ".join(out) or "none, held to the end") + ".",
                      f"Size: {size} per trade{cap}{rank}." + (f" Risk: {'; '.join(guard)}." if guard else "")])
