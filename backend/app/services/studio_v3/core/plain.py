"""Plain English -> strategy fields by fixed phrase rules (no LLM). Words no rule matches are returned, never guessed; nothing runs until the user accepts."""

from __future__ import annotations

import re

_N = r"(\d+(?:\.\d+)?)"
_DAYS = r"(?:[- ]?(?:day|days|bar|bars|d))?"
_MA = r"(?:sma|ema|moving average|ma|average)"

# ordered: longer, more specific phrases first. Each pattern maps to a formula template.
# B-104: words people use that name a rule without a number. Each is read as the formula below and reported back as an assumption.
_WORDS: list[tuple[str, str, str]] = [
    (r"golden cross", "the 50-day average crosses above the 200-day average", "crosses_above(sma(close, 50), sma(close, 200))"),
    (r"death cross", "the 50-day average crosses below the 200-day average", "crosses_below(sma(close, 50), sma(close, 200))"),
    (r"oversold", "RSI(14) is below 30", "(rsi(close, 14) < 30)"),
    (r"overbought", "RSI(14) is above 70", "(rsi(close, 14) > 70)"),
    (r"up-?trend", "the close is above its 200-day average", "(close > sma(close, 200))"),
    (r"down-?trend", "the close is below its 200-day average", "(close < sma(close, 200))"),
    (r"breakout", "the close is above the highest high of the previous 20 bars", "(close > delay(highest(high, 20), 1))"),
    (r"pull-?back", "the close is below its 20-day average while still above its 200-day average", "((close < sma(close, 20)) & (close > sma(close, 200)))"),
    (r"volume spike", "volume is more than twice its 20-day average", "(volume > 2 * sma(volume, 20))"),
]
_CONDS: list[tuple[str, str]] = [(rf"\b{pattern}\b", formula) for pattern, _, formula in _WORDS] + [
    (rf"(?:the )?{_N}{_DAYS} ({_MA}) crosses above (?:the )?{_N}{_DAYS} ({_MA})", "crosses_above({ma2}(close, {1}), {ma4}(close, {3}))"),
    (rf"(?:the )?{_N}{_DAYS} ({_MA}) crosses below (?:the )?{_N}{_DAYS} ({_MA})", "crosses_below({ma2}(close, {1}), {ma4}(close, {3}))"),
    (rf"(?:price |close )?crosses above (?:the )?{_N}{_DAYS} ({_MA})", "crosses_above(close, {ma2}(close, {1}))"),
    (rf"(?:price |close )?crosses below (?:the )?{_N}{_DAYS} ({_MA})", "crosses_below(close, {ma2}(close, {1}))"),
    (rf"(?:price |close )?(?:is )?(?:above|over) (?:the |its )?{_N}{_DAYS} ({_MA})", "(close > {ma2}(close, {1}))"),
    (rf"(?:price |close )?(?:is )?(?:below|under) (?:the |its )?{_N}{_DAYS} ({_MA})", "(close < {ma2}(close, {1}))"),
    (rf"rsi ?\(?{_N}?\)? (?:is )?(?:below|under|less than) {_N}", "(rsi(close, {1|14}) < {2})"),
    (rf"rsi ?\(?{_N}?\)? (?:is )?(?:above|over|greater than) {_N}", "(rsi(close, {1|14}) > {2})"),
    (r"(?:a )?new 52[- ]week high", "(close >= highest(high, 252))"),
    (r"(?:a )?new 52[- ]week low", "(close <= lowest(low, 252))"),
    (rf"(?:a )?new {_N}{_DAYS} high", "(close >= highest(high, {1}))"),
    (rf"(?:a )?new {_N}{_DAYS} low", "(close <= lowest(low, {1}))"),
    (rf"(?:it )?(?:is )?up {_N}% (?:over|in) (?:the last )?{_N}{_DAYS}", "(roc(close, {2}) > {1}/100)"),
    (rf"(?:it )?(?:is )?down {_N}% (?:over|in) (?:the last )?{_N}{_DAYS}", "(roc(close, {2}) < -{1}/100)"),
    (r"(?:the )?weekly trend is up", "(weekly(close) > weekly(sma(close, 30)))"),
    (r"(?:the )?weekly trend is down", "(weekly(close) < weekly(sma(close, 30)))"),
    (r"volume (?:is )?above average", "(volume > sma(volume, 20))"),
]
_EXITS: list[tuple[str, str]] = [
    (rf"trailing stop (?:of )?{_N}%", "trail"),
    (rf"stop(?: loss)? (?:of |at )?{_N}%", "stop"),
    (rf"(?:target|take profit) (?:of |at )?{_N}%", "target"),
    (rf"(?:after|in) {_N} (?:days|bars|day|bar)", "time_stop"),
    (rf"move (?:the )?stop to (?:entry|breakeven) (?:after|at) {_N}%", "breakeven"),
]
FILLER = {"buy", "sell", "short", "cover", "when", "and", "or", "the", "a", "it", "is", "exit", "enter", "go", "long", "with", "if", "then", "use", "on", "price", "stock", "stocks", "of", "at",
          "its", "an", "in", "close", "to", "trades", "trade", "positions", "position", "my", "i", "want", "only", "also"}


def _ma(word: str) -> str:
    return "ema" if word.startswith("ema") else "sma"


def _render(tpl: str, m: re.Match) -> str:
    def sub(k: re.Match) -> str:
        key = k.group(1)
        if key.startswith("ma"):
            return _ma(m.group(int(key[2:])))
        idx, _, default = key.partition("|")
        v = m.group(int(idx))
        return (v if v is not None else default).rstrip("0").rstrip(".") if v and "." in v else (v if v is not None else default)
    return re.sub(r"\{([a-z]*\d+(?:\|\d+)?)\}", sub, tpl)


def _conditions(text: str) -> tuple[str, str]:
    """Clause -> (formula joined with & / |, leftover text)."""
    parts, joins, rest = [], [], text
    for piece in re.split(r"\b(and|or)\b", text):
        if piece in ("and", "or"):
            joins.append("&" if piece == "and" else "|")
            continue
        found, left = [], piece
        while True:
            hits = [(m.start(), m, tpl) for pat, tpl in _CONDS if (m := re.search(pat, left))]
            if not hits:
                break
            _, m, tpl = min(hits, key=lambda h: h[0])
            found.append(_render(tpl, m))
            left = left.replace(m.group(0), " ", 1)
            rest = rest.replace(m.group(0), " ", 1)
        if found:
            parts.append(" & ".join(found))
        elif parts and joins:
            joins.pop()
    out = parts[0] if parts else ""
    for j, p in zip(joins, parts[1:], strict=False):
        out += f" {j} {p}"
    return out, rest


def _assumptions(text: str) -> list[dict]:
    """The ambiguous words found in the user's own text, with offsets into it, what each was taken to mean and the formula used."""
    found = [{"word": m.group(0), "start": m.start(), "end": m.end(), "meaning": meaning, "formula": formula}
             for pattern, meaning, formula in _WORDS for m in re.finditer(rf"\b{pattern}\b", text, re.IGNORECASE)]
    return sorted(found, key=lambda a: a["start"])


def _restate(fields: dict[str, str], exits: dict[str, float]) -> str:
    from . import compile as compiler
    from .spec import Strategy

    try:
        return compiler.describe(Strategy(**fields, exits=exits))
    except ValueError:  # pydantic's ValidationError subclasses it; a proposal that is not a valid spec has nothing to restate
        return ""


def to_spec(text: str) -> dict:
    t = " " + re.sub(r"[^a-z0-9%.()\- ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    exits: dict[str, float] = {}
    for pat, key in _EXITS:
        m = re.search(pat, t)
        if m:
            v = float(m.group(1))
            exits[key] = int(v) if key == "time_stop" else v / 100
            t = t.replace(m.group(0), " ", 1)
    fields: dict[str, str] = {}
    leftover = ""
    clauses = re.split(r"\b(buy|go long|enter long|sell|exit|short|cover)\b(?: when| if)?", t)
    role = None
    for c in clauses:
        key = {"buy": "entry_long", "go long": "entry_long", "enter long": "entry_long", "sell": "exit_long", "exit": "exit_long", "short": "entry_short", "cover": "exit_short"}.get(c)
        if key:
            role = key
            continue
        f, rest = _conditions(c)
        if f and role:
            fields[role] = f"{fields[role]} & {f}" if role in fields else f
        elif f:
            fields["entry_long"] = f
        leftover += " " + (rest if f else c)
    unmatched = [w for w in leftover.split() if w not in FILLER and not re.fullmatch(r"[\d.%()\-]+", w)]
    if not fields and not exits:
        raise ValueError("No rule recognised. Try: buy when the 50 day sma crosses above the 200 day sma; sell when rsi(2) above 70; stop 8%")
    return {"fields": fields, "exits": exits, "unmatched": unmatched, "assumptions": _assumptions(text), "restated": _restate(fields, exits)}
