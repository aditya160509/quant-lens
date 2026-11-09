"""Plain English to a formula by fixed phrase rules. Words with no rule are returned, never guessed."""
from __future__ import annotations

import re

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
