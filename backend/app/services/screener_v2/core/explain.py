"""Pure explainers over a panel and a filter payload. Unknown (NaN) values stay unknown, never zero."""
from __future__ import annotations

import math
import threading
from collections import OrderedDict
from contextvars import ContextVar
from typing import Any

import pandas as pd

from .screener import apply_filters, effective_payload, range_filters

# The unfiltered panel behind a finished run, kept for its last few runs so explaining a row does not rebuild it.
RUN_ID: ContextVar[str | None] = ContextVar("screener_run_id", default=None)
_PANELS: OrderedDict[str, pd.DataFrame] = OrderedDict()
_LOCK = threading.Lock()


def remember(panel: pd.DataFrame) -> None:
    run_id = RUN_ID.get()
    if run_id:
        with _LOCK:
            _PANELS[run_id] = panel
            _PANELS.move_to_end(run_id)
            while len(_PANELS) > 3:
                _PANELS.popitem(last=False)


def panel_for(run_id: str, payload: dict) -> pd.DataFrame:
    """The panel run `run_id` filtered, rebuilt from its stored settings when the server no longer holds it."""
    if run_id not in _PANELS:
        from ..registry import run_feature
        token = RUN_ID.set(run_id)
        try:
            run_feature("01", payload)
        finally:
            RUN_ID.reset(token)
    return _PANELS[run_id].set_index("ticker", drop=False)

# Published support for a panel column. A column with no entry is a rule of thumb, shown as uncited.
EVIDENCE = {
    "momentum_jt": "Jegadeesh and Titman (1993), Journal of Finance", "return_12m": "Jegadeesh and Titman (1993), Journal of Finance",
    "return_1m": "Jegadeesh (1990), Journal of Finance", "piotroski_passed": "Piotroski (2000), Journal of Accounting Research",
    "altman_z_score": "Altman (1968), Journal of Finance", "ivol_ff3_63d": "Ang, Hodrick, Xing and Zhang (2006), Journal of Finance",
    "max_1d_return_21d": "Bali, Cakici and Whitelaw (2011), Journal of Financial Economics", "prox52": "George and Hwang (2004), Journal of Finance",
    "pct_from_52w_high": "George and Hwang (2004), Journal of Finance", "gpa": "Novy-Marx (2013), Journal of Financial Economics",
    "amihud_percentile": "Amihud (2002), Journal of Financial Markets", "beta_252": "Frazzini and Pedersen (2014), Journal of Financial Economics",
    "trailing_pe": "Basu (1977), Journal of Finance", "pb_ratio": "Fama and French (1992), Journal of Finance", "market_cap": "Banz (1981), Journal of Financial Economics",
    "roe": "Fama and French (2015), Journal of Financial Economics", "operating_margin": "Fama and French (2015), Journal of Financial Economics",
    "dividend_yield": "Fama and French (1988), Journal of Financial Economics", "fcf_yield": "Lakonishok, Shleifer and Vishny (1994), Journal of Finance",
    "ev_ebitda": "Loughran and Wellman (2011), Journal of Financial and Quantitative Analysis", "debt_equity": "Bhandari (1988), Journal of Finance",
    "dist_sma_50": "Brock, Lakonishok and LeBaron (1992), Journal of Finance", "dist_sma_200": "Brock, Lakonishok and LeBaron (1992), Journal of Finance",
}


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def bounds(panel: pd.DataFrame, payload: dict | None) -> list[dict[str, Any]]:
    """Every range filter the run applied, whatever its payload key, with its label and published support."""
    payload = effective_payload(payload)
    out = []
    for column, lo, hi, label in range_filters(panel):
        for side, key in (("min", lo), ("max", hi)):
            thr = _num(payload.get(key))
            if thr is not None and not isinstance(payload.get(key), bool) and column in panel.columns:
                out.append({"filter": key, "label": label, "column": column, "side": side, "threshold": thr, "evidence": EVIDENCE.get(column)})
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


def eligible(panel: pd.DataFrame, payload: dict | None) -> pd.DataFrame:
    """The names that clear every filter except the range filters, which `near_misses` and `explain_difference` then judge."""
    spent = {k for _, lo, hi, _ in range_filters(panel) for k in (lo, hi, lo[:-4] + "_top")} | {"screen_template", "dollar_volume_preset"}
    base, _ = apply_filters(panel, {k: v for k, v in effective_payload(payload).items() if k not in spent})
    return base.set_index("ticker", drop=False)


def near_misses(panel: pd.DataFrame, payload: dict | None) -> list[dict[str, Any]]:
    """Names that miss exactly one range filter, nearest first."""
    bs = bounds(panel, payload)
    out = []
    for symbol, row in panel.iterrows():
        fails = [c for c in (_check(row, b) for b in bs) if not c["passes"]]
        if len(fails) == 1:
            f = fails[0]
            out.append({"symbol": symbol, "filter": f["filter"], "label": f["label"], "value": f["value"], "threshold": f["threshold"],
                        "relax_by": None if f["unknown"] else -f["margin"], "unknown": f["unknown"]})
    return sorted(out, key=lambda r: (r["relax_by"] is None, r["relax_by"] or 0))


def explain_difference(panel: pd.DataFrame, payload: dict | None, passed: str, failed: str) -> list[dict[str, Any]]:
    """Filters name `failed` misses, side by side with `passed`."""
    if passed not in panel.index or failed not in panel.index:
        return []
    a, b = panel.loc[passed], panel.loc[failed]
    return [{"filter": x["filter"], "label": x["label"], "passed_value": x["value"], "failed_value": y["value"], "threshold": x["threshold"], "failed_unknown": y["unknown"]}
            for bd in bounds(panel, payload) for x, y in [(_check(a, bd), _check(b, bd))] if not y["passes"]]


def screen_diff(before: list[str], after: list[str]) -> dict[str, Any]:
    pb, pa = {s: i for i, s in enumerate(before)}, {s: i for i, s in enumerate(after)}
    return {"entered": [s for s in after if s not in pb], "left": [s for s in before if s not in pa],
            "moved": [{"symbol": s, "from": pb[s], "to": pa[s]} for s in after if s in pb and pb[s] != pa[s]]}
