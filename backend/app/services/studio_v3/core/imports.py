"""Home import: a CSV of signals (H-20)."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json

from . import data
from .spec import Strategy

CODE = '''SIGNALS = %s

class Strategy:
    def on_bar(self, ctx):
        s = SIGNALS.get(ctx.symbol, {}).get(ctx.date)
        if s is None:
            return
        if s == 1 and ctx.position <= 0:
            ctx.buy()
        elif s == -1 and ctx.position >= 0:
            ctx.short()
        elif s == 0 and ctx.position > 0:
            ctx.sell()
        elif s == 0 and ctx.position < 0:
            ctx.cover()
'''
MAX_ROWS = 200_000


def signals(text: str, name: str = "Imported signals") -> dict:
    """Validate date,symbol,signal rows against the panel; findings come back before anything is saved. shortcut: signals are embedded in the code, upgrade to a stored table past ~200k rows."""
    found: list[dict] = []

    def add(sev: str, msg: str, row: int | None = None) -> None:
        found.append({"severity": sev, "row": row, "message": msg})

    rows = list(csv.reader(io.StringIO(text.strip())))
    head = [h.strip().lower() for h in rows[0]] if rows else []
    if head != ["date", "symbol", "signal"]:
        add("error", f"Columns must be date,symbol,signal; got {','.join(head) or 'nothing'}")
        return {"ok": False, "rows": 0, "symbols": [], "findings": found, "spec": None}
    body = rows[1:]
    if len(body) > MAX_ROWS:
        add("error", f"{len(body)} rows; the limit is {MAX_ROWS}")
        return {"ok": False, "rows": len(body), "symbols": [], "findings": found, "spec": None}
    sig: dict[str, dict[str, int]] = {}
    for i, r in enumerate(body, start=2):
        if len(r) != 3:
            add("error", f"Expected 3 columns, got {len(r)}", i)
            continue
        d, s, v = (x.strip() for x in r)
        try:
            dt.date.fromisoformat(d)
        except ValueError:
            add("error", f"Date {d!r} is not YYYY-MM-DD", i)
            continue
        if v not in ("1", "-1", "0"):
            add("error", f"Signal {v!r} must be 1, -1 or 0", i)
            continue
        if not s:
            add("error", "Symbol is empty", i)
            continue
        s = s.upper()
        if d in sig.get(s, {}):
            add("error", f"{s} has two signals on {d}", i)
            continue
        sig.setdefault(s, {})[d] = int(v)
    if not sig and not found:
        add("error", "No rows")
    if sig:
        panel = data.panel(sorted(sig))
        for s in sorted(set(sig) - set(panel.symbols)):
            add("error", f"{s} is not in the data")
        ds = {str(x.date()) for x in panel.dates}
        lo, hi = (str(panel.dates[0].date()), str(panel.dates[-1].date())) if len(panel.dates) else ("", "")
        off = sum(1 for s in sig for d in sig[s] if s in panel.symbols and d not in ds)
        if off:
            add("warning", f"{off} signals fall on days with no bars (outside {lo} to {hi} or not trading days) and will never fire")
    ok = not any(f["severity"] == "error" for f in found)
    spec = Strategy(name=name, code=CODE % json.dumps(sig, sort_keys=True, separators=(",", ":")), notes="Trades the imported signals: 1 long, -1 short, 0 flat.") if ok else None
    return {"ok": ok, "rows": len(body), "symbols": sorted(sig), "findings": found, "spec": spec.model_dump() if spec else None}
