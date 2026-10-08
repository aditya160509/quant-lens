"""Live analytics for the Volatility V2 service.

The implementation uses local daily OHLCV and macro parquet inputs and fits the
specified volatility models with deterministic, serializable outputs suitable
for the API layer.
"""

from __future__ import annotations

import math
import hashlib
from typing import Any, Iterable

import numpy as np
import pandas as pd


from .estimators import (
    ESTIMATORS as ESTIMATORS,
    ESTIMATOR_LABELS as ESTIMATOR_LABELS,
    _rolling_mean_np as _rolling_mean_np,
    _rolling_var_np as _rolling_var_np,
    volatility_estimators as volatility_estimators,
    volatility_estimators_multi as volatility_estimators_multi,
)
from .common import (
    clean_json as clean_json,
    compact_records as compact_records,
    matrix_records as matrix_records,
    response as response,
    summary_card as summary_card,
)
from .stats import (
    model_confidence_set as model_confidence_set,
    newey_west_lrv as newey_west_lrv,
)

from .data_loader import load_category7_macro, ohlcv_for_symbols, resolve_symbols
from .performance import (
    rolling_rank_pct_last_jit,
)


DEFAULT_ASSETS = [
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "TLT",
    "GLD",
    "USO",
    "BTC_USD",
    "ETH_USD",
]
DISTRIBUTIONS = ["Gaussian", "Student-t", "GED", "Skew-t"]
ARCH_DISTS = {"Gaussian": "normal", "Student-t": "t", "GED": "ged", "Skew-t": "skewt"}
ARCH_SPECS = {
    "GARCH": {"vol": "GARCH", "p": 1, "o": 0, "q": 1},
    "EGARCH": {"vol": "EGARCH", "p": 1, "o": 1, "q": 1},
    "GJR-GARCH": {"vol": "GARCH", "p": 1, "o": 1, "q": 1},
    "APARCH": {"vol": "APARCH", "p": 1, "o": 1, "q": 1},
    "FIGARCH": {"vol": "FIGARCH", "p": 1, "q": 1},
}


_PRIM_CACHE: dict[str, dict[str, Any]] = {}


def number_like(value: Any) -> float | None:
    try:
        out = float(value)
    except (ValueError, TypeError):
        return None
    return out if math.isfinite(out) else None


def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper()


def parse_assets(
    payload: dict[str, Any] | None, default: Iterable[str] = DEFAULT_ASSETS[:1]
) -> list[str]:
    payload = payload or {}
    raw = next(
        (
            payload[key]
            for key in ("assets", "symbols", "universe", "asset", "symbol", "ticker")
            if key in payload
        ),
        list(default),
    )
    if isinstance(raw, str):
        parts = raw.replace(";", ",").split(",")
    elif isinstance(raw, (list, tuple, set)):
        parts = list(raw)
    else:
        parts = [raw]
    assets = [normalize_symbol(x) for x in parts if str(x).strip()]
    if not assets:
        raise ValueError("Explicit asset list must not be empty")
    return assets


def _frame_cache_key(ohlcv: pd.DataFrame, label: str) -> str:
    digest = hashlib.sha256(
        pd.util.hash_pandas_object(ohlcv, index=True).values.tobytes()
    ).hexdigest()
    return f"{label}:{digest}"


def _get_or_build_primitives(ohlcv: pd.DataFrame) -> dict[str, Any]:
    key = _frame_cache_key(ohlcv, "ohlcv")
    cached = _PRIM_CACHE.get(key)
    if cached is not None:
        return cached
    px = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    observations = ohlcv.sort_values(["Ticker", "Date"]).copy()
    previous = observations.groupby("Ticker", sort=False).Close.shift(1)
    observations["observed_return"] = np.log(observations.Close / previous)
    ret_panel = (
        observations.pivot(index="Date", columns="Ticker", values="observed_return")
        .sort_index()
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="all")
    )
    cached = {"prices": px, "ret_panel": ret_panel}
    _PRIM_CACHE[key] = cached
    if len(_PRIM_CACHE) > 16:
        _PRIM_CACHE.pop(next(iter(_PRIM_CACHE)))
    return cached


def load_assets(
    payload: dict[str, Any] | None, default: Iterable[str] = DEFAULT_ASSETS[:1]
) -> tuple[list[str], pd.DataFrame]:
    assets = parse_assets(payload, default=default)
    raw_lookback = (payload or {}).get("lookback_days", 2520)
    lookback = number_like(raw_lookback)
    if lookback is None or lookback != int(lookback) or lookback < 2:
        raise ValueError("lookback_days must be an integer >= 2")
    lookback_days = int(lookback)
    df = ohlcv_for_symbols(assets, lookback_days=lookback_days)
    assets = resolve_symbols(assets)
    return assets, _clean_ohlcv(df)


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Open", "High", "Low", "Close", "Volume"]
    out = df.copy()
    out["Ticker"] = out["Ticker"].astype(str)
    if not pd.api.types.is_datetime64_any_dtype(out["Date"]):
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    for col in cols:
        if not pd.api.types.is_numeric_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if out[["Ticker", "Date", "Open", "High", "Low", "Close"]].isna().any().any():
        raise ValueError("Missing OHLC observations")
    return out.sort_values(["Ticker", "Date"])


def returns_panel(ohlcv: pd.DataFrame) -> pd.DataFrame:
    return _get_or_build_primitives(ohlcv)["ret_panel"].copy()


def agreement_index(vol: pd.DataFrame, window: int = 21) -> pd.DataFrame:
    rows = []
    for asset, g in vol.groupby("asset"):
        g = g.sort_values("date")
        est_arr = g[ESTIMATORS].to_numpy(dtype=float)
        vals = np.full(len(g), np.nan, dtype=float)
        if len(g) >= 3:
            pairs = [
                (i, j)
                for i in range(len(ESTIMATORS))
                for j in range(i + 1, len(ESTIMATORS))
            ]
            corr_sum = np.zeros(len(g), dtype=float)
            corr_count = np.zeros(len(g), dtype=float)
            series = [pd.Series(est_arr[:, i]) for i in range(len(ESTIMATORS))]
            means = [
                s.rolling(window, min_periods=3).mean().to_numpy(dtype=float)
                for s in series
            ]
            stds = [
                s.rolling(window, min_periods=3).std(ddof=0).to_numpy(dtype=float)
                for s in series
            ]
            for i, j in pairs:
                prod = (
                    pd.Series(est_arr[:, i] * est_arr[:, j])
                    .rolling(window, min_periods=3)
                    .mean()
                    .to_numpy(dtype=float)
                )
                denominator = stds[i] * stds[j]
                corr = np.divide(
                    prod - means[i] * means[j],
                    denominator,
                    out=np.full(len(g), np.nan),
                    where=denominator > 1e-14,
                )
                ok = np.isfinite(corr)
                corr_sum[ok] += corr[ok]
                corr_count[ok] += 1
            vals = corr_sum / np.maximum(corr_count, 1)
            vals[corr_count == 0] = np.nan
        rows.append(
            pd.DataFrame({"date": g["date"].values, "asset": asset, "agreement": vals})
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def disagreement_pair(vol: pd.DataFrame, window: int = 21) -> dict[str, Any] | None:
    sub = vol.sort_values("date").tail(window)[ESTIMATORS]
    corr_arr = sub.corr(min_periods=3).to_numpy(dtype=float)
    best = None
    for i, a in enumerate(ESTIMATORS):
        for j, b in enumerate(ESTIMATORS[i + 1 :], start=i + 1):
            v = number_like(corr_arr[i, j])
            if v is not None and (best is None or v < best["correlation"]):
                best = {
                    "estimator_a": ESTIMATOR_LABELS[a],
                    "estimator_b": ESTIMATOR_LABELS[b],
                    "correlation": v,
                }
    return best


def macro_frame() -> pd.DataFrame:
    macro = load_category7_macro().copy()
    if macro.empty:
        return macro
    rename = {}
    cols = {c.lower(): c for c in macro.columns}
    for target, candidates in {
        "vix": ["vixcls", "vix_close", "vix", "vix_yahoo"],
        "vix3m": ["vix3m", "vix_3m", "vxmt", "vix3m_close"],
        "vix6m": ["vix6m", "vix_6m", "vix6m_close"],
        "vix9d": ["vix9d", "vix_9d", "vix9d_close"],
        "vix1y": ["vix1y", "vix_1y", "vix1y_close"],
        "dgs2": ["dgs2", "ust_2y"],
        "dgs10": ["dgs10", "ust_10y"],
        "curve_10y_2y": ["yc_slope_10y_2y"],
        "credit": ["bamlc0a0cm", "bamlh0a0hym2", "baa10y", "credit", "baa_spread"],
    }.items():
        for c in candidates:
            if c in cols:
                rename[cols[c]] = target
                break
    macro = macro.rename(columns=rename)
    for col in [
        "vix",
        "vix3m",
        "vix6m",
        "vix9d",
        "vix1y",
        "dgs2",
        "dgs10",
        "curve_10y_2y",
        "credit",
    ]:
        if col not in macro.columns:
            macro[col] = np.nan
    if not pd.api.types.is_datetime64_any_dtype(macro["date"]):
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    if macro["curve_10y_2y"].isna().all():
        macro["curve_10y_2y"] = macro["dgs10"] - macro["dgs2"]
    return (
        macro[
            [
                "date",
                "vix",
                "vix3m",
                "vix6m",
                "vix9d",
                "vix1y",
                "dgs2",
                "dgs10",
                "curve_10y_2y",
                "credit",
            ]
        ]
        .dropna(subset=["date"])
        .sort_values("date")
    )


def opening_gap_fragility(ohlcv: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    rows = []
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        overnight = np.log(g["Open"] / g["Close"].shift(1)).abs()
        intraday_range = np.log(g["High"] / g["Low"]).abs().replace(0, np.nan)
        fragility = (overnight / intraday_range).replace([np.inf, -np.inf], np.nan)
        pct = pd.Series(
            rolling_rank_pct_last_jit(fragility.to_numpy(dtype=float), int(window)),
            index=fragility.index,
        )
        rows.append(
            pd.DataFrame(
                {
                    "date": g["Date"],
                    "asset": ticker,
                    "opening_gap_fragility": fragility,
                    "ogf_percentile": pct,
                }
            )
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def vol_adjusted_momentum(
    ohlcv: pd.DataFrame, vol_panel: pd.DataFrame, lookback: int = 252
) -> pd.DataFrame:
    px = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    mom_raw = px / px.shift(lookback) - 1
    yz = vol_panel.pivot(index="date", columns="asset", values="yang_zhang")
    yz.index = pd.to_datetime(yz.index)
    common = mom_raw.index.intersection(yz.index)
    score = mom_raw.reindex(common) / yz.reindex(common).replace(0, np.nan)
    latest = score.dropna(axis=1, how="all").tail(1).T
    if latest.empty:
        return pd.DataFrame()
    latest.columns = ["vol_adjusted_momentum"]
    latest["raw_momentum"] = mom_raw.reindex(columns=latest.index).tail(1).T.iloc[:, 0]
    latest["yang_zhang_vol"] = yz.reindex(columns=latest.index).tail(1).T.iloc[:, 0]
    latest["rank"] = latest["vol_adjusted_momentum"].rank(
        ascending=False, method="first"
    )
    latest["quintile"] = (
        pd.qcut(latest["rank"], min(5, len(latest)), labels=False, duplicates="drop")
        + 1
    )
    return latest.reset_index().rename(columns={"index": "asset"}).sort_values("rank")


def parse_weights(payload: dict[str, Any] | None, assets: list[str]) -> pd.Series:
    import json
    from .common import mapping_from_pairs

    payload = payload or {}
    raw = payload.get("weights", payload.get("portfolio_weights"))
    if raw is None:
        return pd.Series(1 / len(assets), index=assets, dtype=float)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw, object_pairs_hook=mapping_from_pairs)
        except json.JSONDecodeError:
            try:
                raw = mapping_from_pairs(
                    part.strip().split(":", 1) for part in raw.split(",")
                )
            except ValueError as exc:
                raise ValueError(
                    "weights must be a JSON object or SYMBOL:value pairs"
                ) from exc
    if not isinstance(raw, dict) or not raw:
        raise ValueError("weights must be a nonempty mapping")
    vals = {}
    for key, value in raw.items():
        name = resolve_symbols([key])[0]
        val = number_like(value)
        if name not in assets or val is None:
            raise ValueError(f"Invalid weight for {key}")
        if name in vals:
            raise ValueError(f"Duplicate exposure for {name}")
        vals[name] = val
    weights = pd.Series({a: vals.get(a, 0.0) for a in assets}, dtype=float)
    if weights.abs().sum() == 0:
        raise ValueError("Portfolio weights must have positive gross exposure")
    return weights
