"""Pure explainers over a panel and a filter payload. Unknown (NaN) values stay unknown, never zero."""
from __future__ import annotations

import math
import threading
from collections import OrderedDict
from contextvars import ContextVar
from typing import Any

import numpy as np
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

# Out-of-sample grade from the product review (section 11): 4 to 5 robust, 3 mixed, 1 to 2 weak. A column with no entry is shown without a badge.
FF92 = ("robust", "Fama and French (1992), Journal of Finance")
JT93 = ("robust", "Jegadeesh and Titman (1993), Journal of Finance")
GH04 = ("robust", "George and Hwang (2004), Journal of Finance")
TECHNICAL = ("weak", "Sullivan, Timmermann and White (1999), Journal of Finance")
EVIDENCE: dict[str, tuple[str, str]] = {
    "trailing_pe": FF92, "pb_ratio": FF92, "ev_ebit": FF92, "earnings_yield": FF92,
    "gpa": ("robust", "Novy-Marx (2013), Journal of Financial Economics"),
    "piotroski_passed": ("robust", "Piotroski (2000), Journal of Accounting Research"),
    "altman_z_score": ("mixed", "Altman (1968), Journal of Finance"),
    "momentum_jt": JT93, "return_12m": JT93, "momentum_percentile": JT93,
    "prox52": GH04, "pct_from_52w_high": GH04, "prox52_percentile": GH04,
    "return_1m": ("mixed", "Jegadeesh (1990), Journal of Finance"),
    "realized_vol_252d": ("robust", "Ang, Hodrick, Xing and Zhang (2006), Journal of Finance"),
    "ivol_ff3_63d": ("weak", "Ang, Hodrick, Xing and Zhang (2006), Journal of Finance"),
    "max_1d_return_21d": ("weak", "Bali, Cakici and Whitelaw (2011), Journal of Financial Economics"),
    "amihud_percentile": ("weak", "Amihud (2002), Journal of Financial Markets"),
    **{c: TECHNICAL for c in ("rsi_14", "macd_histogram", "adx_14", "stochastic_k", "williams_r", "bollinger_pct_b", "obv_20d_slope")},
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
                out.append({"filter": key, "label": label, "column": column, "side": side, "threshold": thr, "evidence": dict(zip(("grade", "cite"), EVIDENCE[column])) if column in EVIDENCE else None})
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
            out.append({"symbol": symbol, "filter": f["filter"], "label": f["label"], "side": f["side"], "value": f["value"], "threshold": f["threshold"],
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


SHIFTS = (-0.1, -0.05, 0.05, 0.1)


def sensitivity(panel: pd.DataFrame, payload: dict | None) -> dict[str, Any]:
    """How many names pass if one threshold moves by a share of its column's interquartile range, the others held."""
    base = eligible(panel, payload)
    bs = bounds(base, payload)
    values = {b["column"]: pd.to_numeric(base[b["column"]], errors="coerce") for b in bs}

    def passes(b: dict, threshold: float) -> pd.Series:
        v = values[b["column"]]
        return (v >= threshold) if b["side"] == "min" else (v <= threshold)

    masks = [passes(b, b["threshold"]) for b in bs]
    count = lambda ms: int(pd.concat(ms, axis=1).all(axis=1).sum()) if ms else len(base)
    now = count(masks)
    rows = []
    for i, b in enumerate(bs):
        v = values[b["column"]].dropna()
        iqr = float(v.quantile(0.75) - v.quantile(0.25)) if len(v) else 0.0
        counts = [count([*masks[:i], passes(b, b["threshold"] + s * iqr), *masks[i + 1:]]) for s in SHIFTS]
        rows.append({"filter": b["filter"], "label": b["label"], "side": b["side"], "threshold": b["threshold"], "iqr": iqr, "counts": counts})
    return {"count": now, "shifts": list(SHIFTS), "filters": rows}


_PREVIEW: OrderedDict[tuple, pd.DataFrame] = OrderedDict()


def _preview_panel(payload: dict) -> pd.DataFrame:
    """Unfiltered panel for the payload's universe, cached so each filter edit costs only the filter pass."""
    from .data_loader import (
        MARKET_UNIVERSE,
        MASTER_FUNDAMENTALS,
        _path_version,
        parse_symbols,
    )
    from .panel import metric_panel
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=1000)
    # shortcut: custom indicator periods are ignored here, so a preview uses default windows; pass them through if users tune periods often.
    base = {k: payload[k] for k in ("lookback_days", "as_of_date") if payload.get(k)}
    key = (_path_version(MARKET_UNIVERSE), _path_version(MASTER_FUNDAMENTALS), tuple(symbols), tuple(sorted(base.items())))
    with _LOCK:
        hit = _PREVIEW.get(key)
    if hit is None:
        hit = metric_panel(base, symbols=symbols)
        with _LOCK:
            _PREVIEW[key] = hit
            while len(_PREVIEW) > 4:
                _PREVIEW.popitem(last=False)
    return hit


def preview(payload: dict, fields: list[str], bins: int = 32) -> dict[str, Any]:
    """Live counts and real distributions for the filter editor, without a full run."""
    panel = _preview_panel(payload)
    filtered, stages = apply_filters(panel, payload)
    dist: dict[str, Any] = {}
    for field in fields:
        if field not in panel:
            continue
        values = pd.to_numeric(panel[field], errors="coerce").dropna()
        if values.empty:
            dist[field] = {"known": 0, "total": len(panel)}
            continue
        lo, hi = float(values.quantile(0.01)), float(values.quantile(0.99))
        width = (hi - lo) / bins or 1.0
        counts = ((values.clip(lo, hi) - lo) / width).astype(int).clip(0, bins - 1).value_counts().reindex(range(bins), fill_value=0)
        kept = pd.to_numeric(filtered[field], errors="coerce").dropna() if field in filtered else values.iloc[:0]
        kept_counts = ((kept.clip(lo, hi) - lo) / width).astype(int).clip(0, bins - 1).value_counts().reindex(range(bins), fill_value=0)
        dist[field] = {"lo": lo, "hi": hi, "bins": counts.tolist(), "kept": kept_counts.tolist(), "known": len(values), "total": len(panel),
                       "median": float(values.median()), "min": float(values.min()), "max": float(values.max())}
    mix = {k: panel[k].replace("", "Unknown").fillna("Unknown").value_counts().head(12).to_dict() for k in ("sector", "country") if k in panel}
    return {"universe": len(panel), "passed": len(filtered), "stages": stages, "dist": dist, "mix": mix}


def breadth(payload: dict) -> dict[str, Any]:
    """Market breadth over the universe: advancers and decliners, names at 52-week highs and lows, median 1-month return by sector."""
    panel = _preview_panel(payload)
    day = pd.to_numeric(panel.get("return_1d"), errors="coerce")
    prox = pd.to_numeric(panel.get("prox52"), errors="coerce")
    month = pd.to_numeric(panel.get("return_1m"), errors="coerce")
    sectors = (pd.DataFrame({"sector": panel["sector"], "r": month}).dropna().query("sector not in ['', 'Unknown']")
               .groupby("sector")["r"].agg(["median", "count"]).sort_values("median", ascending=False))
    cap = pd.to_numeric(panel.get("market_cap"), errors="coerce")
    caps = cap.groupby(panel["sector"]).sum(min_count=1).dropna()
    week = pd.to_numeric(panel.get("return_1w"), errors="coerce")
    tiles = [{"ticker": str(t), "sector": str(sc), "band": _band(float(c)), "market_cap": None if pd.isna(c) else float(c),
              "r1d": None if pd.isna(d) else float(d), "r1w": None if pd.isna(w) else float(w), "r1m": None if pd.isna(m) else float(m)}
             for t, sc, c, d, w, m in zip(panel["ticker"], panel["sector"], cap, day, week, month, strict=True) if sc and sc != "Unknown"]
    return {
        "universe": len(panel), "advancers": int((day > 0).sum()), "decliners": int((day < 0).sum()), "unchanged": int((day == 0).sum()),
        # Within 2% of the 52-week high, or in the bottom 5% of the 52-week range.
        "near_high": int((prox >= 0.98).sum()), "near_low": int((prox <= prox.quantile(0.05)).sum()) if prox.notna().any() else 0,
        "median_1d": float(day.median()) if day.notna().any() else None,
        "sectors": [{"sector": s, "median_1m": float(r["median"]), "count": int(r["count"]), "market_cap": float(caps.get(s, 0.0))} for s, r in sectors.iterrows()],
        "tiles": tiles,
    }


def sparklines(tickers: list[str], days: int, points: int = 60) -> dict[str, list[float]]:
    """Observed closes over the last `days` calendar days per ticker, thinned to about `points` values for a table sparkline."""
    from .data_loader import normalize_symbol, ohlcv_for_symbols
    frame = ohlcv_for_symbols([normalize_symbol(t) for t in tickers[:1000]], lookback_days=days)
    out = {}
    for t, g in frame.dropna(subset=["Close"]).sort_values("Date").groupby("Ticker"):
        close = g["Close"].to_numpy(dtype=float)
        step = max(1, len(close) // points)
        out[str(t)] = [round(float(x), 4) for x in close[::step]]
    return out


_RANGE: dict[str, Any] = {}


def data_range() -> dict[str, Any]:
    """Calendar span from SPY and, per year, how many names have prices that year, so a range picker can show where data thins out."""
    import polars as pl

    from .data_loader import (
        MARKET_UNIVERSE,
        NORMALIZED_TICKER,
        _path_version,
        default_as_of,
        load_market_frame,
    )
    key = _path_version(MARKET_UNIVERSE)
    if _RANGE.get("key") == key:
        return _RANGE["out"]
    spans = (load_market_frame().with_columns(NORMALIZED_TICKER.alias("t")).group_by("t")
             .agg(pl.col("Date").min().dt.year().alias("y0"), pl.col("Date").max().dt.year().alias("y1")).collect())
    spy = spans.filter(pl.col("t") == "SPY")
    first, last = (int(spy["y0"][0]), int(spy["y1"][0])) if len(spy) else (int(spans["y0"].min()), int(spans["y1"].max()))
    years = [{"year": y, "names": int(((spans["y0"] <= y) & (spans["y1"] >= y)).sum())} for y in range(first, last + 1)]
    out = {"first": f"{first}-01-01", "last": default_as_of({}), "names": len(spans), "years": years}
    _RANGE.update(key=key, out=out)
    return out


CAP_BANDS = [("Mega", 200e9), ("Large", 10e9), ("Mid", 2e9), ("Small", 300e6), ("Micro", 0.0)]


def _band(cap: float) -> str | None:
    return next((name for name, floor in CAP_BANDS if cap >= floor), None) if np.isfinite(cap) else None


def breadth_history(payload: dict, days: int = 252) -> dict[str, Any]:
    """Daily advancers, decliners, new 52-week highs and lows across the universe, with SPY's close; observed closes only."""
    import polars as pl

    from .data_loader import NORMALIZED_TICKER, load_market_frame, parse_symbols
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=1000)
    wide = (load_market_frame().with_columns(NORMALIZED_TICKER.alias("t")).filter(pl.col("t").is_in([*symbols, "SPY"]))
            .select("Date", "t", "Close").collect().to_pandas().pivot_table(index="Date", columns="t", values="Close").sort_index())
    spy = wide.pop("SPY") if "SPY" in wide else pd.Series(dtype=float)
    # Sessions where most names have a close; a few stray late or holiday quotes would read as a collapse in breadth.
    seen = wide.notna().sum(axis=1)
    wide = wide[seen >= 0.6 * seen.max()].iloc[-(days + 252):]
    move = wide.pct_change(fill_method=None)
    hi, lo = wide.rolling(252, min_periods=200).max(), wide.rolling(252, min_periods=200).min()
    out = pd.DataFrame({"advancers": (move > 0).sum(axis=1), "decliners": (move < 0).sum(axis=1),
                        "new_highs": (wide >= hi).sum(axis=1), "new_lows": (wide <= lo).sum(axis=1)}).iloc[-days:]
    out["spy"] = spy.reindex(out.index)
    return {"universe": len(symbols), "rows": [{"date": d.strftime("%Y-%m-%d"), **{k: (None if pd.isna(v) else float(v)) for k, v in r.items()}} for d, r in out.iterrows()]}
