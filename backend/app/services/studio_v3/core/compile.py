"""Spec -> findings (compile) and spec + bars -> signal arrays. No LLM anywhere."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.services.shared.formula import SignalError

from . import formula, pycode
from .spec import Strategy

ROLES = ("entry_long", "exit_long", "entry_short", "exit_short", "score")
ROLE_LABEL = {"entry_long": "Buy when", "exit_long": "Sell when", "entry_short": "Short when", "exit_short": "Cover when", "score": "Rank by"}


def compile_spec(spec: Strategy) -> dict:
    """Findings for every rule, each with the line (role order), character span and token. `ok` is false on any error."""
    findings: list[dict] = []
    params = spec.values()
    used: set[str] = set()
    for line, role in enumerate(ROLES, 1):
        text = getattr(spec, role)
        if not text.strip():
            continue
        try:
            names, _ = formula.tokens(formula.parse(text, params))
            used |= names
        except SignalError as e:
            findings.append({"severity": "error", "role": role, "line": line, "start": e.start, "end": e.end, "token": text[e.start:e.end], "message": e.message,
                             "lookahead": e.message.startswith("Look-ahead")})
    if spec.code.strip():
        findings += pycode.check(spec.code, params)
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
        if spec.sizing.mode != "equal" and not spec.sizing.value:
            findings.append({"severity": "error", "role": "sizing", "line": 0, "start": 0, "end": 0, "token": spec.sizing.mode, "message": "Position size is zero"})
        if e.scale_at and not e.scale_frac:
            findings.append({"severity": "warning", "role": "exits", "line": 0, "start": 0, "end": 0, "token": "scale_at", "message": "Scale-out level set without a share to sell"})
    for name in sorted(set(params) - used):
        findings.append({"severity": "warning", "role": "params", "line": 0, "start": 0, "end": 0, "token": name, "message": f"Parameter '{name}' is not used by any rule"})
    return {"ok": not any(f["severity"] == "error" for f in findings), "findings": findings, "hash": spec.hash(), "description": describe(spec)}


@dataclass
class Signals:
    entries: np.ndarray  # int8: +1 long, -1 short
    exits: np.ndarray  # int8 bits: 1 closes longs, 2 closes shorts
    score: np.ndarray | None
    stop_dist: np.ndarray | None


def _bool(expr: str, bars, dates, params, cache) -> np.ndarray:
    out = formula.evaluate(expr, bars, dates, params, cache)
    return out if out.dtype == bool else np.nan_to_num(out) > 0


def signals(spec: Strategy, bars: dict[str, np.ndarray], dates: pd.DatetimeIndex, params: dict[str, float] | None = None) -> Signals:
    params = {**spec.values(), **(params or {})}
    cache: dict = {}
    shape = bars["close"].shape
    if spec.code.strip():
        entries, exits = pycode.run(spec.code, bars, dates, params, cache=cache)
        dist = spec.exits.stop_atr * formula.evaluate("atr(14)", bars, dates, params, cache) if spec.exits.stop_atr else None
        return Signals(entries, exits, None, None if dist is None else np.nan_to_num(dist))
    entries, exits = np.zeros(shape, dtype=np.int8), np.zeros(shape, dtype=np.int8)
    if spec.entry_short.strip():
        entries[_bool(spec.entry_short, bars, dates, params, cache)] = -1
    if spec.entry_long.strip():
        entries[_bool(spec.entry_long, bars, dates, params, cache)] = 1
    if spec.exit_long.strip():
        exits[_bool(spec.exit_long, bars, dates, params, cache)] |= 1
    if spec.exit_short.strip():
        exits[_bool(spec.exit_short, bars, dates, params, cache)] |= 2
    score = formula.evaluate(spec.score, bars, dates, params, cache).astype(float) if spec.score.strip() else None
    dist = spec.exits.stop_atr * formula.evaluate("atr(14)", bars, dates, params, cache) if spec.exits.stop_atr else None
    return Signals(entries, exits, score, None if dist is None else np.nan_to_num(dist))


def _pct(v: float) -> str:
    return f"{v * 100:g}%"


def describe(spec: Strategy) -> str:
    """"What it does": three plain lines built from the spec alone (B-9)."""
    if spec.code.strip() and not spec.entry_long.strip() and not spec.entry_short.strip():
        return "Python strategy: orders come from on_bar."
    e, s = spec.exits, spec.sizing
    entry = [f"{ROLE_LABEL[r]} {getattr(spec, r).strip()}" for r in ("entry_long", "entry_short") if getattr(spec, r).strip()]
    out = [f"{ROLE_LABEL[r]} {getattr(spec, r).strip()}" for r in ("exit_long", "exit_short") if getattr(spec, r).strip()]
    out += [t for t in (f"stop {e.stop_atr:g} ATR" if e.stop_atr else f"stop {_pct(e.stop)}" if e.stop else "", f"target {_pct(e.target)}" if e.target else "",
                        f"trailing stop {_pct(e.trail)}" if e.trail else "", f"time stop {e.time_stop} bars" if e.time_stop else "",
                        f"stop to entry after {_pct(e.breakeven)}" if e.breakeven else "",
                        f"sell {_pct(e.scale_frac)} at {_pct(e.scale_at)}" if e.scale_at and e.scale_frac else "") if t]
    size = {"shares": f"{s.value:g} shares", "cash": f"${s.value:,.0f}", "pct_equity": f"{_pct(s.value)} of equity", "risk": f"{_pct(s.value)} of equity at risk to the stop",
            "equal": "an equal share of equity"}[s.mode]
    cap = f", at most {s.max_positions} positions" if s.max_positions else ""
    rank = f", best {spec.score.strip()} first" if spec.score.strip() else ""
    return "\n".join([("; ".join(entry) or "No entry rule") + ".", "Exit: " + ("; ".join(out) or "none, held to the end") + ".", f"Size: {size} per trade{cap}{rank}."])
