"""Glue between the formula language, the saved-signal store and the panel."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from . import signal_lang as sl
from .signal_library import BY_ID
from .signal_store import resolve_ref


def payload_expr(payload: dict[str, Any] | None) -> str | None:
    """Formula from ``signal_expr`` or ``signal_ref`` (formula overrides ``signal``)."""

    p = payload or {}
    if p.get("signal_expr"):
        return str(p["signal_expr"])
    if p.get("signal_ref"):
        return resolve_ref(p["signal_ref"])
    return None


def custom_signal(ctx: dict[str, Any], payload: dict[str, Any] | None) -> pd.DataFrame:
    expr = payload_expr(payload)
    if not expr:
        raise ValueError("signal 'custom' needs signal_expr or signal_ref")
    try:
        return sl.evaluate(expr, ctx)
    except sl.SignalError as e:
        raise ValueError(f"Signal formula error: {e.message} (characters {e.start}-{e.end})") from None


def _resolve_other(item: str, ctx: dict[str, Any]) -> pd.DataFrame:
    item = str(item)
    if item in BY_ID:
        return sl.evaluate(BY_ID[item]["formula"], ctx)
    from .panel import SIGNALS, compute_signal

    if item in SIGNALS:
        return compute_signal(item, ctx)
    return sl.evaluate(item, ctx)


def finalize_signal(signal: pd.DataFrame, ctx: dict[str, Any], payload: dict[str, Any] | None) -> pd.DataFrame:
    """Orthogonalise against requested signals and run the look-ahead guard (stored for the response meta)."""

    p = payload or {}
    expr = payload_expr(p)
    others = p.get("orthogonalize_against") or []
    if isinstance(others, str):
        others = [others]
    if others:
        try:
            signal = sl.orthogonalize(signal, [_resolve_other(o, ctx) for o in others])
        except sl.SignalError as e:
            raise ValueError(f"orthogonalize_against error: {e.message}") from None
    if expr or others:
        sl.set_lookahead(sl.lookahead_check(expr, signal, ctx["returns"]))
    else:
        sl.set_lookahead(None)
    return signal


def attach_lookahead(result: dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict) and isinstance(result.get("meta"), dict):
        result["meta"]["lookahead"] = sl.get_lookahead()
    return result


# ---------------------------------------------------------------------------
# preview context (small universe, cached)


@lru_cache(maxsize=2)
def preview_ctx(max_symbols: int = 150, lookback_days: int = 2520) -> dict[str, Any]:
    from .data_loader import ohlcv_matrices, parse_symbols, point_in_time_fundamental
    from .panel import _monthly_factors

    symbols = parse_symbols({"max_symbols": max_symbols}, default_limit=max_symbols)
    daily = ohlcv_matrices(symbols, lookback_days)
    if not daily:
        raise ValueError("No market data available for the preview universe")
    close_m = daily["Close"].resample("ME").last()
    close_m = close_m.loc[:, close_m.notna().sum() >= 24]
    symbols = list(close_m.columns)
    returns = close_m.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() < 3)
    dates = returns.index
    shares = point_in_time_fundamental("Ordinary Shares Number", dates, symbols)
    return {"close_m": close_m, "returns": returns, "daily": daily, "market_cap": close_m * shares, "factors": _monthly_factors(dates), "symbols": symbols, "dates": dates}


def _mean_rank_corr(a: pd.DataFrame, b: pd.DataFrame) -> float:
    c = a.rank(axis=1).corrwith(b.rank(axis=1), axis=1).dropna()
    return float(c.mean()) if len(c) else float("nan")


def validate(expr: str) -> dict[str, Any]:
    try:
        tree = sl.parse(expr)
        msg = sl.references_forward(tree)
        if msg:
            raise sl.SignalError(msg, 0, len(expr))
        ctx = preview_ctx()
        sig = sl.evaluate(expr, ctx)
    except sl.SignalError as e:
        return {"ok": False, "error": e.as_dict()}
    cnt = sig.notna().sum(axis=1)
    valid = sig.loc[cnt >= 10]
    z = sl._zscore(sl._winsorize(valid)) if len(valid) else valid
    vals = z.to_numpy().ravel()
    vals = vals[np.isfinite(vals)]
    hist = []
    if len(vals):
        counts, edges = np.histogram(np.clip(vals, -4, 4), bins=20, range=(-4, 4))
        hist = [{"x0": float(edges[i]), "x1": float(edges[i + 1]), "count": int(counts[i])} for i in range(20)]
    cov = [{"month": d.strftime("%Y-%m"), "share": round(float(s), 4)} for d, s in (sig.notna().mean(axis=1)).items()]
    known = {"momentum": "mom_12_1", "size": "size", "value": "bm", "reversal": "str_1m", "low_vol": "rvol_daily"}
    corr = []
    for name, lid in known.items():
        try:
            c = _mean_rank_corr(sig, sl.evaluate(BY_ID[lid]["formula"], ctx))
        except Exception:
            c = float("nan")
        corr.append({"name": name, "corr": None if not np.isfinite(c) else round(c, 4)})
    return {
        "ok": True,
        "preview": {"n_names": int(sig.notna().any().sum()), "months": int((cnt >= 10).sum()), "histogram": hist, "coverage": cov, "corr_known": corr},
        "lookahead": sl.lookahead_check(expr, sig, ctx["returns"], tree),
    }


def combine(exprs: list[str], method: str) -> str:
    if method in {"equal", "rank_average"}:
        return sl.combine_expr(exprs, method)
    ctx = preview_ctx()
    ics = []
    for e in exprs:
        sl.parse(e)
        ics.append(sl.rank_ic(sl.evaluate(e, ctx), ctx["returns"].shift(-1)).dropna())
    if method == "ic":
        raw = np.array([x.mean() if len(x) else 0.0 for x in ics])
        # a negative-IC signal enters with a flipped sign so every leg predicts in the same direction
        w = raw / max(np.abs(raw).sum(), 1e-12)
        parts = [f"{abs(wi):.4f} * {'-' if wi < 0 else ''}zscore({e})" for wi, e in zip(w, exprs)]
        return " + ".join(parts)
    if method == "inverse_variance":
        inv = np.array([1.0 / v if (v := float(x.var())) > 0 else 0.0 for x in ics])
        w = inv / inv.sum() if inv.sum() > 0 else np.full(len(exprs), 1 / len(exprs))
        return sl.combine_expr(exprs, "equal", list(w))
    raise ValueError("method must be equal, ic, inverse_variance or rank_average")
