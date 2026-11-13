"""Plain English to a formula by fixed phrase rules. Words with no rule are returned, never guessed."""
from __future__ import annotations

import re
from typing import Any

# phrase -> (term, higher is better)
RULES = {
    "cheap": ("trailing_pe", False), "value": ("trailing_pe", False), "undervalued": ("pb_ratio", False),
    "profitable": ("roe", True), "quality": ("roe", True), "high roe": ("roe", True),
    "momentum": ("momentum_jt", True), "trending": ("momentum_jt", True),
    "growth": ("revenue_growth_yoy", True), "growing": ("revenue_growth_yoy", True),
    "low volatility": ("realized_vol_63d", False), "stable": ("realized_vol_63d", False), "safe": ("realized_vol_63d", False),
    "small drawdown": ("max_drawdown_252d", True), "yield": ("net_income_yield", True), "earnings yield": ("net_income_yield", True),
}
FILLER = {"find", "show", "me", "stocks", "stock", "companies", "with", "and", "that", "are", "is", "a", "the", "high", "low", "good", "strong", "names", "of", "in", "have", "has", "great"}


def to_formula(text: str) -> dict:
    lowered = re.sub(r"[^a-z ]", " ", text.lower())
    terms, rest = [], lowered
    for phrase in sorted(RULES, key=len, reverse=True):
        if re.search(rf"\b{phrase}\b", rest):
            field, up = RULES[phrase]
            if (field, up) not in [t[:2] for t in terms]:
                terms.append((field, up, phrase))
            rest = re.sub(rf"\b{phrase}\b", " ", rest)
    unmatched = [w for w in rest.split() if w not in FILLER]
    if not terms:
        raise ValueError("No known idea in that sentence; known: " + ", ".join(sorted(RULES)))
    weight = round(1 / len(terms), 2)
    parts = [f"{weight}*{'' if up else '-'}rank({field})" for field, up, _ in terms]
    return {"formula": "+".join(parts).replace("+-", "-"), "matched": [{"phrase": p, "field": f} for f, _, p in terms], "unmatched": unmatched}


SECTOR_ALIASES = {"it": "Technology", "tech": "Technology", "banks": "Financial Services", "banking": "Financial Services", "financials": "Financial Services",
                  "pharma": "Healthcare", "telecom": "Communication Services", "oil": "Energy", "reits": "Real Estate"}
OPERATORS = {"at least": "min", "more than": "min", "greater than": "min", "above": "min", "over": "min", ">": "min", ">=": "min",
             "at most": "max", "less than": "max", "under": "max", "below": "max", "up to": "max", "<": "max", "<=": "max"}
# Fraction-scale metrics: a bare number above 1 means a percentage ("roe above 15" is 15%).
PERCENT_KEYS = {"dividend_yield", "fcf_yield", "roe", "roic", "gross_margin", "operating_margin", "net_margin", "revenue_growth_yoy", "eps_growth_yoy", "realized_vol_63d", "pct_from_52w_high"}
NUMBER = re.compile(r"(\d+(?:\.\d+)?)(%?)")


def _bound_value(base: str, token: str) -> tuple[float, str | None]:
    number = NUMBER.fullmatch(token)
    value = float(number.group(1))
    if number.group(2):
        return value / 100, "read as a percentage"
    if base in PERCENT_KEYS and value > 1:
        return value / 100, "read as a percentage (no % sign)"
    return value, None


def to_filters(text: str) -> dict:
    """Plain English to the filter payload of POST /run/01, using the screener's metric names, operators and sector names. Words with no rule come back as unparsed."""
    from .data_loader import load_fundamentals
    from .screener import RANGE_FILTERS
    metrics: dict[str, str] = {}
    for col, lo, _, label in RANGE_FILTERS:
        for phrase in {lo[:-4], col, label.lower(), lo[:-4].replace("_", " ")}:
            metrics.setdefault(phrase, lo[:-4])
    sectors = {str(s).lower(): str(s) for s in load_fundamentals()["sector"].dropna().unique()} | SECTOR_ALIASES
    tokens = re.findall(r"[a-z0-9][a-z0-9/%.&+-]*|[<>]=?", text.lower())

    def at(i: int, size: int) -> str:
        return " ".join(tokens[i:i + size])

    def longest(i: int, table) -> int:
        return next((n for n in (3, 2, 1) if i + n <= len(tokens) and at(i, n) in table), 0)

    used: set[int] = set()
    clauses: list[dict[str, Any]] = []
    chosen_sectors: list[str] = []
    i = 0
    while i < len(tokens):
        if n := longest(i, sectors):
            chosen_sectors.append(sectors[at(i, n)])
            used.update(range(i, i + n))
            i += n
            continue
        size = longest(i, metrics)
        if not size:
            i += 1
            continue
        base, j = metrics[at(i, size)], i + size
        if j < len(tokens) and tokens[j] in {"is", "of"}:
            j += 1
        pairs: list[tuple[str, str]] = []
        end = j
        if j + 3 < len(tokens) and tokens[j] == "between" and tokens[j + 2] == "and" and NUMBER.fullmatch(tokens[j + 1]) and NUMBER.fullmatch(tokens[j + 3]):
            low, high = sorted([tokens[j + 1], tokens[j + 3]], key=lambda t: float(NUMBER.fullmatch(t).group(1)))
            pairs, end = [(f"{base}_min", low), (f"{base}_max", high)], j + 4
        else:
            op_size = longest(j, OPERATORS)
            if op_size and j + op_size < len(tokens) and NUMBER.fullmatch(tokens[j + op_size]):
                pairs, end = [(f"{base}_{OPERATORS[at(j, op_size)]}", tokens[j + op_size])], j + op_size + 1
        if not pairs:
            i += size
            continue
        used.update(range(i, end))
        for key, token in pairs:
            value, note = _bound_value(base, token)
            clauses.append({"text": at(i, end - i), "key": key, "value": round(value, 6), "note": note})
        i = end
    if not clauses and not chosen_sectors:
        raise ValueError("No metric, operator or sector in that sentence")
    payload: dict[str, Any] = {clause["key"]: clause["value"] for clause in clauses}
    if chosen_sectors:
        payload["sectors"] = sorted(set(chosen_sectors))
    unparsed = [tok for k, tok in enumerate(tokens) if k not in used and tok not in FILLER and tok not in OPERATORS and tok not in {"between", "and", "is", "of"}]
    return {"payload": payload, "clauses": clauses, "unparsed": unparsed}
