"""Shared panel cache, data audit and transaction-cost analysis for Research V2 results.

``shared_panel`` makes every ``build_panel`` call inside a job return one cached
panel per payload, so a multi-feature job (report card, merged sections) builds
the data once. ``data_audit`` and ``cost_analysis`` read that panel.
"""

from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from typing import Any, Iterator

import numpy as np
import pandas as pd

PANEL_MODULES = ["panel", "canonical", "diagnostics", "regime", "placebo", "decay", "zoo", "robustness", "specification", "causal", "synthetic"]
FUNDAMENTAL = {"size", "value", "quality", "profitability", "investment", "leverage", "asset_growth"}
DEFAULT_COSTS = {"spread_bps": 10.0, "commission_bps": 1.0, "impact": "sqrt"}


@contextmanager
def shared_panel() -> Iterator[list[Any]]:
    """Patch ``build_panel`` in the core modules with a per-payload cache; yields the list of panels built."""

    store: dict[str, Any] = {}
    built: list[Any] = []
    patched: list[tuple[Any, Any]] = []
    for name in PANEL_MODULES:
        try:
            mod = importlib.import_module(f"app.services.research_v2.core.{name}")
        except Exception:
            continue
        original = getattr(mod, "build_panel", None)
        if original is None:
            continue

        def wrapper(payload, *args, _orig=original, **kwargs):
            key = json.dumps([payload, args, kwargs], sort_keys=True, default=str)
            if key not in store:
                store[key] = _orig(payload, *args, **kwargs)
                built.append(store[key])
            return store[key]

        patched.append((mod, original))
        mod.build_panel = wrapper
    try:
        yield built
    finally:
        for mod, original in patched:
            mod.build_panel = original


def data_audit(panel: Any | None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """meta.data_audit: universe size and coverage by month, missing share, survivorship, PIT lag, adjustments."""

    adjustments = ["Monthly returns above 300% in absolute value are treated as bad prints and dropped.", "Prices are the adjusted closes in the local market file; no intraday data is used."]
    if panel is None:
        return {"universe_size_by_month": [], "coverage_by_month": [], "missing_share": None, "survivorship": "not handled", "pit_lag_days": None, "adjustments": adjustments + ["This study does not use a formation-date signal panel."]}
    sig = panel.signal
    n = sig.notna().sum(axis=1)
    total = max(len(panel.symbols), 1)
    cfg = panel.config
    uses_fundamentals = cfg["signal"] in FUNDAMENTAL or any(c in FUNDAMENTAL for c in cfg["controls"]) or cfg["weighting"] == "value" or any(f in {"large_cap", "mid_cap", "small_cap", "ex_microcaps"} for f in cfg["universe_filters"])
    if uses_fundamentals:
        adjustments.append("Fundamentals are lagged 90 days from the report date (point in time); restatements are not versioned.")
    adjustments.append("Delisted names are not in the file and no delisting returns are applied, so results carry survivorship bias.")
    return {
        "universe_size_by_month": [{"month": d.strftime("%Y-%m"), "n": int(v)} for d, v in n.items()],
        "coverage_by_month": [{"month": d.strftime("%Y-%m"), "share": round(float(v) / total, 4)} for d, v in n.items()],
        "missing_share": round(float(sig.isna().to_numpy().mean()), 4) if sig.size else None,
        "survivorship": "not handled",
        "pit_lag_days": 90 if uses_fundamentals else None,
        "adjustments": adjustments,
    }


def cost_model(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("cost_model") or {}
    impact = str(raw.get("impact", DEFAULT_COSTS["impact"])).lower()
    borrow = float(raw.get("borrow_cost_bps", payload.get("borrow_cost_bps", 0.0)) or 0.0)
    return {"borrow_cost_bps": borrow, "spread_bps": float(raw.get("spread_bps", DEFAULT_COSTS["spread_bps"])), "commission_bps": float(raw.get("commission_bps", DEFAULT_COSTS["commission_bps"])), "impact": impact if impact in {"none", "sqrt"} else "sqrt"}


def _leg_weights(rank: pd.DataFrame, top: bool, q: float = 0.2) -> pd.DataFrame:
    mask = (rank > 1 - q) if top else (rank <= q)
    return mask.astype(float).div(mask.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)


def cost_analysis(panel: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Break-even cost, net Sharpe, turnover and square-root-impact capacity of the top-minus-bottom quintile (or top quintile if ``long_only``)."""

    from .core.estimators import sort_portfolios

    cm = cost_model(payload)
    long_only = bool(payload.get("long_only"))
    aum = float(payload.get("aum_usd") or 1e7)
    port = sort_portfolios(panel, 5)
    if port.empty:
        return {"available": False, "reason": "No sort portfolios."}
    gross = (port.iloc[:, -2] if long_only else port["long_short"]).dropna()  # Q5 is the column before long_short
    rank = panel.signal.rank(axis=1, pct=True)
    legs = [_leg_weights(rank, True)] + ([] if long_only else [_leg_weights(rank, False)])
    traded = sum(w.diff().abs().sum(axis=1) for w in legs).iloc[1:]
    traded = traded.reindex(gross.index).dropna()
    gross = gross.reindex(traded.index)
    if len(gross) < 6:
        return {"available": False, "reason": "Too few formation dates."}
    c_lin = (cm["spread_bps"] / 2 + cm["commission_bps"]) / 1e4
    lin = traded * c_lin
    q = pd.Series(0.0, index=traded.index)
    if cm["impact"] == "sqrt":
        daily = panel.context.get("daily", {})
        close, vol = daily.get("Close"), daily.get("Volume")
        if close is not None and vol is not None:
            adv = (close * vol).rolling(63, min_periods=20).mean().reindex(traded.index, method="ffill")
            sig = close.pct_change(fill_method=None).rolling(63, min_periods=20).std().reindex(traded.index, method="ffill")
            adv = adv.apply(lambda r: r.fillna(r.median()), axis=1).replace(0, np.nan)
            for w in legs:
                dw = w.diff().abs().reindex(traded.index)
                cols = [c for c in dw.columns if c in adv.columns]
                q += (dw[cols] ** 1.5 * sig[cols] / np.sqrt(adv[cols])).sum(axis=1, min_count=1).fillna(0.0)
    g_mean, lin_mean, q_mean = float(gross.mean()), float(lin.mean()), float(q.mean())
    h = panel.holding_months
    # Short leg pays the annual borrow fee on its (unit) weight for each holding period; none for long-only.
    borrow = pd.Series(0.0 if long_only else cm["borrow_cost_bps"] / 1e4 * h / 12, index=traded.index)
    net = gross - lin - np.sqrt(aum) * q - borrow
    ann = np.sqrt(12 / h)
    sharpe = lambda s: float(s.mean() / s.std() * ann) if s.std() else None  # noqa: E731
    capacity = None
    if cm["impact"] == "sqrt" and q_mean > 0:
        net0 = g_mean - lin_mean - float(borrow.mean())
        capacity = float((net0 / q_mean) ** 2) if net0 > 0 else 0.0
    turnover = float(traded.mean() / len(legs) / 2)
    return {
        "available": True,
        "cost_model": cm,
        "long_only": long_only,
        "aum_usd": aum,
        "gross_sharpe": sharpe(gross),
        "net_sharpe": sharpe(net),
        "breakeven_bps": float((g_mean - float(borrow.mean())) / traded.mean() * 1e4) if traded.mean() > 0 else None,
        "breakeven_basis": "one-way cost in bps per dollar traded at which the mean return is zero",
        "turnover": turnover,
        "turnover_basis": "mean one-way share of each leg traded per rebalance",
        "annual_turnover": turnover * 12 / max(h, 1),
        "capacity_usd": capacity,
        "capacity_basis": "AUM per leg where square-root-law impact removes the mean return after spread and commission",
        "borrow_cost_per_period": float(borrow.mean()),
        "mean_gross_return": g_mean,
        "mean_net_return": float(net.mean()),
    }


def attach_audit(result: dict[str, Any], panels: list[Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Add meta.data_audit and meta.costs to a feature result using the first panel built during the run."""

    from .core.common import _clean_value

    meta = result.setdefault("meta", {})
    panel = panels[0] if panels else None
    meta.setdefault("data_audit", _clean_value(data_audit(panel, payload)))
    if panel is not None and "costs" not in meta:
        try:
            meta["costs"] = _clean_value(cost_analysis(panel, payload))
        except Exception as exc:  # costs never fail a study
            meta["costs"] = {"available": False, "reason": str(exc)}
    if panel is not None and "return_series" not in meta:
        try:
            from .core.estimators import sort_portfolios

            meta["return_series"] = [round(float(x), 6) for x in sort_portfolios(panel, 5)["long_short"].dropna().to_numpy()]
        except Exception:
            meta["return_series"] = []
    return result
