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


from .data_loader import load_category7_macro, ohlcv_for_symbols, resolve_symbols
from .performance import (
    newey_west_lrv_jit,
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
ESTIMATORS = ["cc", "parkinson", "garman_klass", "rogers_satchell", "yang_zhang"]
ESTIMATOR_LABELS = {
    "cc": "Close-Close",
    "parkinson": "Parkinson",
    "garman_klass": "Garman-Klass",
    "rogers_satchell": "Rogers-Satchell",
    "yang_zhang": "Yang-Zhang",
}
MODEL_PARAMS = {
    "GARCH": (0.07, 0.90, 0.0),
    "EGARCH": (0.09, 0.88, -0.10),
    "GJR-GARCH": (0.06, 0.88, 0.08),
    "APARCH": (0.08, 0.86, 0.06),
    "FIGARCH": (0.04, 0.94, 0.0),
}
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
_MLE_STATE_STORE: dict[str, np.ndarray] = {}


def clean_json(value: Any) -> Any:
    t = type(value)
    if t is float:
        return value if math.isfinite(value) else None
    if t is int or t is str or t is bool or value is None:
        return value
    if t is list:
        return [clean_json(v) for v in value]
    if t is dict:
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.DataFrame):
        return clean_json(value.to_dict("records"))
    if isinstance(value, pd.Series):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


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


def compact_records(df: pd.DataFrame, limit: int = 420) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.copy()
    if len(out) > limit:
        idx = np.unique(np.round(np.linspace(0, len(out) - 1, limit)).astype(int))
        out = out.iloc[idx]
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].to_numpy(dtype="datetime64[D]").astype(str)
    return clean_json(out.to_dict("records"))


def _latest_percentile(series: pd.Series, value: float | None = None) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if not len(s):
        return 0.0
    v = float(s[-1] if value is None else value)
    return float(np.searchsorted(np.sort(s), v, side="right") / len(s) * 100.0)


def _rolling_mean_np(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).mean().to_numpy()


def _rolling_var_np(arr: np.ndarray, window: int, ddof: int = 1) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).var(ddof=ddof).to_numpy()


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
    try:
        px = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    except ValueError:
        px = ohlcv.pivot_table(
            index="Date", columns="Ticker", values="Close", aggfunc="last"
        ).sort_index()
    ret_panel = (
        np.log(px / px.shift(1)).replace([np.inf, -np.inf], np.nan).dropna(how="all")
    )
    cached = {"prices": px, "ret_panel": ret_panel}
    _PRIM_CACHE[key] = cached
    if len(_PRIM_CACHE) > 16:
        _PRIM_CACHE.pop(next(iter(_PRIM_CACHE)))
    return cached


def response(
    feature_id: str,
    summary_cards: list[dict],
    charts: dict,
    tables: dict,
    alerts: list[dict] | None = None,
    meta: dict | None = None,
) -> dict:
    return clean_json(
        {
            "feature_id": f"feature_{feature_id}",
            "status": "ok",
            "summary_cards": summary_cards,
            "charts": charts,
            "tables": tables,
            "alerts": alerts or [],
            "meta": {
                "engine": "volatility_v2",
                "data_policy": "local parquet only; no runtime mutation",
                **(meta or {}),
            },
        }
    )


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


def volatility_estimators(
    ohlcv: pd.DataFrame, window: int = 21, annualization: int = 252
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        close = g["Close"].to_numpy(dtype=float)
        open_ = g["Open"].to_numpy(dtype=float)
        high = g["High"].to_numpy(dtype=float)
        low = g["Low"].to_numpy(dtype=float)
        prev_close = np.roll(close, 1)
        prev_close[0] = np.nan
        log_cc = np.log(close / prev_close)
        log_oc = np.log(close / open_)
        log_overnight = np.log(open_ / prev_close)
        log_hl = np.log(high / low)
        log_hl_sq = log_hl * log_hl
        log_oc_sq = log_oc * log_oc
        rs_daily = np.log(high / close) * np.log(high / open_) + np.log(
            low / close
        ) * np.log(low / open_)
        cc_var = _rolling_mean_np(log_cc * log_cc, window)
        park_var = _rolling_mean_np(log_hl_sq, window) / (4.0 * math.log(2.0))
        gk_var = _rolling_mean_np(
            0.5 * log_hl_sq - (2.0 * math.log(2.0) - 1.0) * log_oc_sq, window
        )
        rs_var = _rolling_mean_np(rs_daily, window)
        k = 0.34 / (1.34 + ((window + 1) / max(window - 1, 1)))
        yz_var = (
            _rolling_var_np(log_overnight, window)
            + k * _rolling_var_np(log_oc, window)
            + (1 - k) * rs_var
        )
        tmp = pd.DataFrame(
            {
                "date": g["Date"],
                "asset": ticker,
                "cc": np.sqrt(np.maximum(cc_var, 0.0) * annualization),
                "parkinson": np.sqrt(np.maximum(park_var, 0.0) * annualization),
                "garman_klass": np.sqrt(np.maximum(gk_var, 0.0) * annualization),
                "rogers_satchell": np.sqrt(np.maximum(rs_var, 0.0) * annualization),
                "yang_zhang": np.sqrt(np.maximum(yz_var, 0.0) * annualization),
                "return": log_cc,
                "jump_proxy": np.maximum(yz_var - rs_var, 0.0),
            }
        )
        frames.append(tmp)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    out["estimator_spread"] = out[ESTIMATORS].max(axis=1) - out[ESTIMATORS].min(axis=1)
    for col in [*ESTIMATORS, "return", "jump_proxy", "estimator_spread"]:
        if col in out.columns:
            out[col] = out[col].astype(np.float32)
    return out.dropna(subset=["yang_zhang"])


def volatility_estimators_multi(
    ohlcv: pd.DataFrame, windows: Iterable[int], annualization: int = 252
) -> dict[int, pd.DataFrame]:
    """Compute the five daily volatility estimators for many windows in one group scan."""
    frames_by_window: dict[int, list[pd.DataFrame]] = {int(w): [] for w in windows}
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        close = g["Close"].to_numpy(dtype=float)
        open_ = g["Open"].to_numpy(dtype=float)
        high = g["High"].to_numpy(dtype=float)
        low = g["Low"].to_numpy(dtype=float)
        prev_close = np.roll(close, 1)
        prev_close[0] = np.nan
        log_cc = np.log(close / prev_close)
        log_oc = np.log(close / open_)
        log_overnight = np.log(open_ / prev_close)
        log_hl = np.log(high / low)
        log_hl_sq = log_hl * log_hl
        log_oc_sq = log_oc * log_oc
        rs_daily = np.log(high / close) * np.log(high / open_) + np.log(
            low / close
        ) * np.log(low / open_)
        for window in frames_by_window:
            k = 0.34 / (1.34 + ((window + 1) / max(window - 1, 1)))
            cc_var = _rolling_mean_np(log_cc * log_cc, window)
            park_var = _rolling_mean_np(log_hl_sq, window) / (4.0 * math.log(2.0))
            gk_var = _rolling_mean_np(
                0.5 * log_hl_sq - (2.0 * math.log(2.0) - 1.0) * log_oc_sq, window
            )
            rs_var = _rolling_mean_np(rs_daily, window)
            yz_var = (
                _rolling_var_np(log_overnight, window)
                + k * _rolling_var_np(log_oc, window)
                + (1 - k) * rs_var
            )
            frames_by_window[window].append(
                pd.DataFrame(
                    {
                        "date": g["Date"],
                        "asset": ticker,
                        "cc": np.sqrt(np.maximum(cc_var, 0.0) * annualization),
                        "parkinson": np.sqrt(np.maximum(park_var, 0.0) * annualization),
                        "garman_klass": np.sqrt(
                            np.maximum(gk_var, 0.0) * annualization
                        ),
                        "rogers_satchell": np.sqrt(
                            np.maximum(rs_var, 0.0) * annualization
                        ),
                        "yang_zhang": np.sqrt(np.maximum(yz_var, 0.0) * annualization),
                        "return": log_cc,
                        "jump_proxy": np.maximum(yz_var - rs_var, 0.0),
                    }
                )
            )
    out: dict[int, pd.DataFrame] = {}
    for window, frames in frames_by_window.items():
        if not frames:
            out[window] = pd.DataFrame()
            continue
        df = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
        df["estimator_spread"] = df[ESTIMATORS].max(axis=1) - df[ESTIMATORS].min(axis=1)
        for col in [*ESTIMATORS, "return", "jump_proxy", "estimator_spread"]:
            if col in df.columns:
                df[col] = df[col].astype(np.float32)
        out[window] = df.dropna(subset=["yang_zhang"])
    return out


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


def newey_west_lrv(values: np.ndarray, bandwidth: int | None = None) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return 0.0
    n = len(x)
    bandwidth = int(bandwidth if bandwidth is not None else max(1, n ** (1 / 3)))
    return float(newey_west_lrv_jit(x, bandwidth))


def model_confidence_set(
    losses: dict[str, pd.Series], alpha: float = 0.10, reps: int = 200
) -> list[str]:
    from arch.bootstrap import MCS

    aligned = pd.concat(losses, axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if aligned.empty:
        return []
    if len(aligned.columns) == 1:
        return list(aligned.columns)
    if len(aligned) < 30:
        raise ValueError("MCS requires at least 30 aligned held-out losses")
    mcs = MCS(
        aligned,
        size=alpha,
        reps=reps,
        block_size=max(2, int(len(aligned) ** (1 / 3))),
        method="R",
        bootstrap="stationary",
        seed=17,
    )
    mcs.compute()
    return list(mcs.included)


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


_GARCH_CACHE: dict[str, tuple[list[dict], pd.DataFrame, str]] = {}


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
    try:
        px = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    except ValueError:
        px = ohlcv.pivot_table(
            index="Date", columns="Ticker", values="Close", aggfunc="last"
        ).sort_index()
    mom_raw = px / px.shift(lookback) - 1
    try:
        yz = vol_panel.pivot(index="date", columns="asset", values="yang_zhang")
    except ValueError:
        yz = vol_panel.pivot_table(
            index="date", columns="asset", values="yang_zhang", aggfunc="last"
        )
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


def matrix_records(
    mat: pd.DataFrame, value_name: str = "value"
) -> list[dict[str, Any]]:
    rows = []
    for r in mat.index:
        for c in mat.columns:
            rows.append(
                {"row": str(r), "col": str(c), value_name: float(mat.loc[r, c])}
            )
    return clean_json(rows)


def parse_weights(payload: dict[str, Any] | None, assets: list[str]) -> pd.Series:
    import json

    payload = payload or {}
    raw = payload.get("weights", payload.get("portfolio_weights"))
    if raw is None:
        return pd.Series(1 / len(assets), index=assets, dtype=float)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            try:
                raw = dict(part.strip().split(":", 1) for part in raw.split(","))
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
        vals[name] = val
    weights = pd.Series({a: vals.get(a, 0.0) for a in assets}, dtype=float)
    if weights.abs().sum() == 0:
        raise ValueError("Portfolio weights must have positive gross exposure")
    return weights


def summary_card(
    label: str, value: Any, unit: str = "", **extra: Any
) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, **extra}
