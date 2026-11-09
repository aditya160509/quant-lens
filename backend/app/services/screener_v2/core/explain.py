"""Pure explainers over a panel and a filter payload. Unknown (NaN) values stay unknown, never zero."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

# payload key stem -> panel column, where the stem is not the column name itself
ALIASES = {"pe": "trailing_pe", "pb": "pb_ratio", "price": "price_usd", "dollar_volume": "dollar_volume_20d", "score": "core_quant_score",
           "rsi": "rsi_14", "adx": "adx_14", "momentum": "momentum_jt", "atr_pct": "atr_pct_price", "drawdown": "max_drawdown_252d",
           "ps": "ps_ratio", "altman": "altman_z_score", "ivol": "ivol_ff3_63d", "high_proximity": "pct_from_52w_high"}


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def bounds(panel: pd.DataFrame, payload: dict | None) -> list[dict[str, Any]]:
    out = []
    for key, raw in (payload or {}).items():
        side = "min" if key.endswith("_min") else "max" if key.endswith("_max") else None
        thr = _num(raw)
        if side is None or thr is None or isinstance(raw, bool):
            continue
        stem = key[:-4]
        col = stem if stem in panel.columns else ALIASES.get(stem)
        if col in panel.columns:
            out.append({"filter": key, "column": col, "side": side, "threshold": thr})
    return out


def _check(row: pd.Series, b: dict) -> dict[str, Any]:
    v = _num(row.get(b["column"]))
    if v is None:
        return {**b, "value": None, "margin": None, "passes": False, "unknown": True}
    margin = v - b["threshold"] if b["side"] == "min" else b["threshold"] - v
    return {**b, "value": v, "margin": margin, "passes": margin >= 0, "unknown": False}


def _sector_pct(panel: pd.DataFrame, symbol: str, column: str) -> float | None:
    if "sector" not in panel or symbol not in panel.index:
        return None
    peers = panel[panel["sector"] == panel.at[symbol, "sector"]][column]
    v = _num(panel.at[symbol, column])
    peers = pd.to_numeric(peers, errors="coerce").dropna()
    return None if v is None or peers.empty else float((peers <= v).mean() * 100)


def why_here(panel: pd.DataFrame, payload: dict | None, symbol: str) -> list[dict[str, Any]]:
    if symbol not in panel.index:
        return []
    row = panel.loc[symbol]
    return [{**_check(row, b), "sector_percentile": _sector_pct(panel, symbol, b["column"])} for b in bounds(panel, payload)]


def near_misses(panel: pd.DataFrame, payload: dict | None) -> list[dict[str, Any]]:
    bs = bounds(panel, payload)
    out = []
    for symbol, row in panel.iterrows():
        fails = [c for c in (_check(row, b) for b in bs) if not c["passes"]]
        if len(fails) == 1:
            f = fails[0]
            out.append({"symbol": symbol, "filter": f["filter"], "value": f["value"], "threshold": f["threshold"],
                        "relax_by": None if f["unknown"] else -f["margin"], "unknown": f["unknown"]})
    return sorted(out, key=lambda r: (r["relax_by"] is None, r["relax_by"] or 0))


def explain_difference(panel: pd.DataFrame, payload: dict | None, passed: str, failed: str) -> list[dict[str, Any]]:
    """Filters name `failed` misses, side by side with `passed`."""
    if passed not in panel.index or failed not in panel.index:
        return []
    a, b = panel.loc[passed], panel.loc[failed]
    return [{"filter": x["filter"], "passed_value": x["value"], "failed_value": y["value"], "threshold": x["threshold"], "failed_unknown": y["unknown"]}
            for bd in bounds(panel, payload) for x, y in [(_check(a, bd), _check(b, bd))] if not y["passes"]]


def screen_diff(before: list[str], after: list[str]) -> dict[str, Any]:
    pb, pa = {s: i for i, s in enumerate(before)}, {s: i for i, s in enumerate(after)}
    return {"entered": [s for s in after if s not in pb], "left": [s for s in before if s not in pa],
            "moved": [{"symbol": s, "from": pb[s], "to": pa[s]} for s in after if s in pb and pb[s] != pa[s]]}
