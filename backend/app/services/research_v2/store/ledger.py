"""Per-project trial ledger built from stored jobs."""
from __future__ import annotations

import numpy as np

from ..core.ledger_math import deflated_sharpe_hurdle, haircut_t, pbo_cscv


def _card(result: dict, needle: str):
    for c in (result or {}).get("summary_cards") or []:
        if needle in str(c.get("label", "")).lower() and isinstance(c.get("value"), (int, float)):
            return float(c["value"])
    return None


def ledger_stats(jobs: list[dict]) -> dict:
    entries = []
    for j in jobs:
        if j["status"] != "completed" or not j["result"]:
            continue
        r = j["result"]
        entries.append({"job_id": j["id"], "feature_id": j["feature_id"], "signal": (j["payload"] or {}).get("signal"),
                        "t_stat": _card(r, "t-stat"), "sharpe": _card(r, "sharpe"), "created_at": j["created_at"],
                        "_returns": (r.get("meta") or {}).get("return_series")})
    n = len(entries)
    sharpes = [e["sharpe"] for e in entries if e["sharpe"] is not None]
    hurdle = deflated_sharpe_hurdle(n, float(np.var(sharpes, ddof=1))) if len(sharpes) >= 2 else None
    ts = [e for e in entries if e["t_stat"] is not None]
    best = max(ts, key=lambda e: abs(e["t_stat"])) if ts else None
    hc = haircut_t(best["t_stat"], n) if best else {"haircut": None}
    out = {"trials": n, "distinct_signals": len({e["signal"] for e in entries if e["signal"]}),
           "deflated_sharpe_hurdle": hurdle,
           "haircut_sharpe": {"observed": (best["sharpe"] if best and best["sharpe"] is not None else best["t_stat"] if best else None), "haircut": hc["haircut"]}}
    series = [e["_returns"] for e in entries if isinstance(e["_returns"], list)]
    if len(series) >= 8 and len({len(s) for s in series}) == 1:
        pbo = pbo_cscv(np.array(series, dtype=float).T)
        if pbo is not None:
            out["pbo"] = pbo
    out["entries"] = [{k: v for k, v in e.items() if k != "_returns"} for e in entries]
    return out
