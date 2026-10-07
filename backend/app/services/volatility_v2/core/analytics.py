"""Live analytics for the Volatility V2 service.

The implementation uses local daily OHLCV and macro parquet inputs and fits the
specified volatility models with deterministic, serializable outputs suitable
for the API layer.
"""

from __future__ import annotations

import math
from functools import lru_cache
import hashlib
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy import stats
from scipy.linalg import cho_factor, cho_solve, cholesky, eigh as scipy_eigh, solve as scipy_solve, solve_triangular
from sklearn.cluster import KMeans, MiniBatchKMeans
from numpy.lib.stride_tricks import sliding_window_view

from arch import arch_model
from hmmlearn.hmm import GaussianHMM

from .data_loader import load_category7_macro, ohlcv_for_symbols, resolve_symbols
from .performance import (
    autocorr_raw_jit,
    build_var_design_matrix,
    dcc_correlation_path,
    dcc_neg_ll_jit,
    generalized_fevd_fast,
    garch_loop,
    newey_west_lrv_jit,
    ols_hac_fast,
    realized_garch_nll,
    rolling_rank_pct_last_jit,
    sjm_viterbi,
    stationary_bootstrap_jit,
    var_ma_matrices_fast,
)


DEFAULT_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO", "BTC_USD", "ETH_USD"]
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


def parse_assets(payload: dict[str, Any] | None, default: Iterable[str] = DEFAULT_ASSETS[:1]) -> list[str]:
    payload = payload or {}
    raw = next((payload[key] for key in ("assets", "symbols", "universe", "asset", "symbol", "ticker") if key in payload), list(default))
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


def compute_mode(payload: dict[str, Any] | None) -> str:
    """Normalize runtime compute mode for feature engines.

    Realtime mode keeps output deterministic and fast. Research mode unlocks
    restart-heavy and bootstrap-heavy diagnostics while preserving the same
    response schema.
    """
    payload = payload or {}
    raw = str(payload.get("compute_mode") or payload.get("mode") or "").strip().lower()
    if raw == "research" or payload.get("research_mode") is True or payload.get("research") is True:
        return "research"
    return "realtime"


def is_research(payload: dict[str, Any] | None) -> bool:
    return compute_mode(payload) == "research"


def runtime_meta(payload: dict[str, Any] | None, constraints: list[str] | None = None) -> dict[str, Any]:
    mode = compute_mode(payload)
    return {
        "compute_mode": mode,
        "research_mode": mode == "research",
        "realtime_constraints": [] if mode == "research" else (constraints or []),
    }


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
    digest = hashlib.sha256(pd.util.hash_pandas_object(ohlcv, index=True).values.tobytes()).hexdigest()
    return f"{label}:{digest}"


def _get_or_build_primitives(ohlcv: pd.DataFrame) -> dict[str, Any]:
    key = _frame_cache_key(ohlcv, "ohlcv")
    cached = _PRIM_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        px = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    except ValueError:
        px = ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    ret_panel = np.log(px / px.shift(1)).replace([np.inf, -np.inf], np.nan).dropna(how="all")
    cached = {"prices": px, "ret_panel": ret_panel}
    _PRIM_CACHE[key] = cached
    if len(_PRIM_CACHE) > 16:
        _PRIM_CACHE.pop(next(iter(_PRIM_CACHE)))
    return cached


def _mle_key(prefix: str, series: pd.Series | pd.DataFrame) -> str:
    arr = np.asarray(series.dropna().tail(1500), dtype=np.float32)
    return f"{prefix}:{hashlib.md5(arr.tobytes()).hexdigest()}"


def _remember_mle(key: str, params: np.ndarray) -> None:
    _MLE_STATE_STORE[key] = np.asarray(params, dtype=float)
    if len(_MLE_STATE_STORE) > 64:
        _MLE_STATE_STORE.pop(next(iter(_MLE_STATE_STORE)))


def clear_request_caches() -> None:
    _PRIM_CACHE.clear()
    _MLE_STATE_STORE.clear()
    if "_GARCH_CACHE" in globals():
        _GARCH_CACHE.clear()


def response(feature_id: str, summary_cards: list[dict], charts: dict, tables: dict, alerts: list[dict] | None = None, meta: dict | None = None) -> dict:
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


def load_assets(payload: dict[str, Any] | None, default: Iterable[str] = DEFAULT_ASSETS[:1]) -> tuple[list[str], pd.DataFrame]:
    assets = parse_assets(payload, default=default)
    lookback_days = int(number_like((payload or {}).get("lookback_days")) or number_like((payload or {}).get("window_days")) or 2520)
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


def volatility_estimators(ohlcv: pd.DataFrame, window: int = 21, annualization: int = 252) -> pd.DataFrame:
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
        rs_daily = np.log(high / close) * np.log(high / open_) + np.log(low / close) * np.log(low / open_)
        cc_var = _rolling_mean_np(log_cc * log_cc, window)
        park_var = _rolling_mean_np(log_hl_sq, window) / (4.0 * math.log(2.0))
        gk_var = _rolling_mean_np(0.5 * log_hl_sq - (2.0 * math.log(2.0) - 1.0) * log_oc_sq, window)
        rs_var = _rolling_mean_np(rs_daily, window)
        k = 0.34 / (1.34 + ((window + 1) / max(window - 1, 1)))
        yz_var = _rolling_var_np(log_overnight, window) + k * _rolling_var_np(log_oc, window) + (1 - k) * rs_var
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


def volatility_estimators_multi(ohlcv: pd.DataFrame, windows: Iterable[int], annualization: int = 252) -> dict[int, pd.DataFrame]:
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
        rs_daily = np.log(high / close) * np.log(high / open_) + np.log(low / close) * np.log(low / open_)
        for window in frames_by_window:
            k = 0.34 / (1.34 + ((window + 1) / max(window - 1, 1)))
            cc_var = _rolling_mean_np(log_cc * log_cc, window)
            park_var = _rolling_mean_np(log_hl_sq, window) / (4.0 * math.log(2.0))
            gk_var = _rolling_mean_np(0.5 * log_hl_sq - (2.0 * math.log(2.0) - 1.0) * log_oc_sq, window)
            rs_var = _rolling_mean_np(rs_daily, window)
            yz_var = _rolling_var_np(log_overnight, window) + k * _rolling_var_np(log_oc, window) + (1 - k) * rs_var
            frames_by_window[window].append(
                pd.DataFrame(
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


def estimator_efficiency_table(vol: pd.DataFrame) -> list[dict[str, Any]]:
    latest = vol.sort_values("date").groupby("asset").tail(1)
    rows = []
    theoretical = {"cc": 1.0, "parkinson": 4.9, "garman_klass": 7.4, "rogers_satchell": 6.2, "yang_zhang": 10.0}
    base_var = float(vol["cc"].pow(2).var()) if "cc" in vol else np.nan
    for est in ESTIMATORS:
        emp = base_var / float(vol[est].pow(2).var()) if float(vol[est].pow(2).var() or 0) > 0 else np.nan
        pct_full = _latest_percentile(vol[est])
        pct_252 = _latest_percentile(vol[est].tail(252))
        pct_5y = _latest_percentile(vol[est].tail(1260))
        rows.append(
            {
                "estimator": ESTIMATOR_LABELS[est],
                "key": est,
                "theoretical_efficiency_vs_cc": theoretical[est],
                "empirical_efficiency_vs_cc": emp,
                "current_ann_vol": float(latest[est].median()) if not latest.empty else None,
                "percentile_252d": pct_252,
                "percentile_5y": pct_5y,
                "percentile_full": pct_full,
                "relative_efficiency_deviation": abs(emp / theoretical[est] - 1.0) if np.isfinite(emp) and theoretical[est] else None,
                "fat_tail_warning": bool(np.isfinite(emp) and theoretical[est] and abs(emp / theoretical[est] - 1.0) > 0.30),
                "color_tier": "green" if emp and emp >= 3 else "amber" if emp and emp >= 1.5 else "red",
            }
        )
    return clean_json(rows)


def dm_tournament(vol: pd.DataFrame) -> list[dict[str, Any]]:
    if vol.empty:
        return []
    one = vol.sort_values("date")
    rv = one["return"].pow(2).rolling(5).sum().shift(-5)
    rows = []
    vals: dict[tuple[str, str], tuple[float, float]] = {}
    loss = {}
    rv_np = rv.to_numpy(dtype=float)
    for est in ESTIMATORS:
        va = (one[est].to_numpy(dtype=float) ** 2) / 252.0
        ratio = rv_np / np.where(va == 0, np.nan, va)
        loss[est] = ratio - np.log(np.clip(ratio, 1e-12, None)) - 1.0
    for i, a in enumerate(ESTIMATORS):
        for b in ESTIMATORS[i + 1 :]:
            d = loss[a] - loss[b]
            d = d[np.isfinite(d)]
            if len(d):
                lrv = newey_west_lrv(d, bandwidth=max(1, int(len(d) ** (1 / 3))))
                se = math.sqrt(max(lrv, 1e-18) / max(len(d), 1))
                val = float(-d.mean() / se) if se and math.isfinite(se) and se > 0 else 0.0
            else:
                val = 0.0
            pvalue = float(2 * (1 - stats.norm.cdf(abs(val))))
            vals[(a, b)] = (val, pvalue)
    for a in ESTIMATORS:
        for b in ESTIMATORS:
            if a == b:
                val, pvalue = 0.0, 1.0
            elif (a, b) in vals:
                val, pvalue = vals[(a, b)]
            else:
                val, pvalue = vals[(b, a)]
                val = -val
            rows.append({"row": ESTIMATOR_LABELS[a], "col": ESTIMATOR_LABELS[b], "value": val, "p_value": pvalue, "bonferroni_significant": bool(pvalue < 0.005)})
    return clean_json(rows)


def agreement_index(vol: pd.DataFrame, window: int = 21) -> pd.DataFrame:
    rows = []
    for asset, g in vol.groupby("asset"):
        g = g.sort_values("date")
        est_arr = g[ESTIMATORS].to_numpy(dtype=float)
        vals = np.full(len(g), np.nan, dtype=float)
        if len(g) >= 3:
            pairs = [(i, j) for i in range(len(ESTIMATORS)) for j in range(i + 1, len(ESTIMATORS))]
            corr_sum = np.zeros(len(g), dtype=float)
            corr_count = np.zeros(len(g), dtype=float)
            series = [pd.Series(est_arr[:, i]) for i in range(len(ESTIMATORS))]
            means = [s.rolling(window, min_periods=3).mean().to_numpy(dtype=float) for s in series]
            stds = [s.rolling(window, min_periods=3).std(ddof=0).to_numpy(dtype=float) for s in series]
            for i, j in pairs:
                prod = pd.Series(est_arr[:, i] * est_arr[:, j]).rolling(window, min_periods=3).mean().to_numpy(dtype=float)
                corr = (prod - means[i] * means[j]) / np.maximum(stds[i] * stds[j], 1e-12)
                ok = np.isfinite(corr)
                corr_sum[ok] += corr[ok]
                corr_count[ok] += 1
            vals = corr_sum / np.maximum(corr_count, 1)
            vals[corr_count == 0] = np.nan
        rows.append(pd.DataFrame({"date": g["date"].values, "asset": asset, "agreement": vals}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def disagreement_pair(vol: pd.DataFrame, window: int = 21) -> dict[str, Any] | None:
    sub = vol.sort_values("date").tail(window)[ESTIMATORS]
    arr = sub.to_numpy(dtype=float)
    corr_arr = np.corrcoef(arr, rowvar=False)
    best = None
    for i, a in enumerate(ESTIMATORS):
        for j, b in enumerate(ESTIMATORS[i + 1 :], start=i + 1):
            v = number_like(corr_arr[i, j])
            if v is not None and (best is None or v < best["correlation"]):
                best = {"estimator_a": ESTIMATOR_LABELS[a], "estimator_b": ESTIMATOR_LABELS[b], "correlation": v}
    return best


def newey_west_lrv(values: np.ndarray, bandwidth: int | None = None) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return 0.0
    n = len(x)
    bandwidth = int(bandwidth if bandwidth is not None else max(1, n ** (1 / 3)))
    return float(newey_west_lrv_jit(x, bandwidth))


def stationary_bootstrap_indices(n: int, reps: int = 250, block_p: float | None = None, seed: int = 17) -> np.ndarray:
    p = float(block_p or min(0.25, max(0.02, n ** -0.33)))
    return stationary_bootstrap_jit(n, reps, p, seed)


def model_confidence_set(losses: dict[str, pd.Series], alpha: float = 0.10, reps: int = 200) -> list[str]:
    from arch.bootstrap import MCS
    aligned = pd.concat(losses, axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if aligned.empty:
        return []
    if len(aligned.columns) == 1:
        return list(aligned.columns)
    if len(aligned) < 30:
        raise ValueError("MCS requires at least 30 aligned held-out losses")
    mcs = MCS(aligned, size=alpha, reps=reps, block_size=max(2, int(len(aligned) ** (1 / 3))), method="R", bootstrap="stationary", seed=17)
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
    for col in ["vix", "vix3m", "vix6m", "vix9d", "vix1y", "dgs2", "dgs10", "curve_10y_2y", "credit"]:
        if col not in macro.columns:
            macro[col] = np.nan
    if not pd.api.types.is_datetime64_any_dtype(macro["date"]):
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    if macro["curve_10y_2y"].isna().all():
        macro["curve_10y_2y"] = macro["dgs10"] - macro["dgs2"]
    return macro[["date", "vix", "vix3m", "vix6m", "vix9d", "vix1y", "dgs2", "dgs10", "curve_10y_2y", "credit"]].dropna(subset=["date"]).sort_values("date")


def ewma_variance(ret: pd.Series, half_life: int = 21) -> pd.Series:
    lam = math.exp(math.log(0.5) / max(half_life, 1))
    r2 = pd.to_numeric(ret, errors="coerce").pow(2)
    return r2.ewm(alpha=1 - lam, adjust=False).mean()


def model_variance(ret: pd.Series, model: str = "GARCH", dist: str = "Gaussian") -> pd.Series:
    r = pd.to_numeric(ret, errors="coerce").fillna(0.0)
    unconditional = float(r.var()) if len(r) else 1e-6
    alpha, beta, gamma = MODEL_PARAMS.get(model, MODEL_PARAMS["GARCH"])
    if dist == "Student-t":
        alpha *= 1.05
    elif dist == "GED":
        beta *= 0.98
    elif dist == "Skew-t":
        gamma += 0.03
    omega = max(unconditional * max(1 - alpha - beta - gamma / 2, 0.01), 1e-10)
    vals = r.to_numpy(dtype=float)
    model_id = {"GARCH": 0, "GJR-GARCH": 1, "APARCH": 2, "FIGARCH": 3, "EGARCH": 4}.get(model, 0)
    out = garch_loop(vals, float(omega), float(alpha), float(beta), float(gamma), float(unconditional), int(model_id))
    return pd.Series(out, index=ret.index)


_GARCH_CACHE: dict[str, tuple[list[dict], pd.DataFrame, str]] = {}


def garch_scoreboard(ret: pd.Series) -> tuple[list[dict], pd.DataFrame, str]:
    """Fit the full 5x4 GARCH family with `arch` and score variance forecasts."""
    r = pd.to_numeric(ret, errors="coerce").dropna() * 100.0
    if len(r) < 260:
        raise ValueError("GARCH family suite requires at least 260 daily returns")
    cache_key = hashlib.md5(r.to_numpy(dtype=np.float32).tobytes()).hexdigest()
    if cache_key in _GARCH_CACHE:
        rows, variance_map, winner = _GARCH_CACHE[cache_key]
        return clean_json(rows), variance_map.copy(), winner
    rows = []
    rv_proxy = r.pow(2).rolling(21).mean().shift(-21)
    best_key = None
    best_loss = float("inf")
    variance_map = {}
    fitted_losses: dict[str, pd.Series] = {}
    for model, spec in ARCH_SPECS.items():
        for dist in DISTRIBUTIONS:
            key = f"{model}-{dist}"
            try:
                am = arch_model(r, mean="Constant", dist=ARCH_DISTS[dist], rescale=False, **spec)
                maxiter = 120 if model == "FIGARCH" else 200
                fit = am.fit(disp="off", show_warning=False, options={"maxiter": maxiter, "ftol": 1e-6})
                var_pct = fit.conditional_volatility.pow(2)
                ratio = (rv_proxy / var_pct).replace([np.inf, -np.inf], np.nan)
                loss_series = (ratio - np.log(np.maximum(ratio, 1e-12)) - 1).replace([np.inf, -np.inf], np.nan).dropna()
                qlike = float(loss_series.mean()) if len(loss_series) else float("inf")
                rmse = float(np.sqrt((var_pct.sub(rv_proxy).pow(2)).mean()))
                loss = qlike
                rows.append(
                    {
                        "model": model,
                        "distribution": dist,
                        "log_likelihood": float(fit.loglikelihood),
                        "aic": float(fit.aic),
                        "bic": float(fit.bic),
                        "rmse": rmse,
                        "qlike": qlike,
                        "parameters": {k: float(v) for k, v in fit.params.items()},
                        "converged": bool(getattr(fit, "convergence_flag", 1) == 0),
                    }
                )
                variance_map[key] = (var_pct / 10000.0).reindex(ret.index)
                fitted_losses[key] = loss_series
            except Exception as exc:
                rows.append({"model": model, "distribution": dist, "error": str(exc), "qlike": None, "rmse": None, "mcs_member": False, "converged": False})
                continue
            if loss < best_loss:
                best_loss = loss
                best_key = key
    if not variance_map:
        raise ValueError("All GARCH family fits failed")
    mcs_members = set(model_confidence_set(fitted_losses, alpha=0.10, reps=150)) if fitted_losses else set()
    for row in rows:
        key = f"{row['model']}-{row['distribution']}"
        row["winner"] = key == best_key
        row["mcs_member"] = key in mcs_members
    result = (clean_json(rows), pd.DataFrame(variance_map), str(best_key or "GARCH-Gaussian"))
    _GARCH_CACHE[cache_key] = (result[0], result[1].copy(), result[2])
    if len(_GARCH_CACHE) > 16:
        _GARCH_CACHE.pop(next(iter(_GARCH_CACHE)))
    return result


def garch_fit_for_series(ret: pd.Series, model: str = "GARCH", dist: str = "Student-t"):
    r = pd.to_numeric(ret, errors="coerce").dropna() * 100.0
    spec = ARCH_SPECS.get(model, ARCH_SPECS["GARCH"])
    maxiter = 120 if model == "FIGARCH" else 200
    fit = arch_model(r, mean="Constant", dist=ARCH_DISTS.get(dist, "t"), rescale=False, **spec).fit(disp="off", show_warning=False, options={"maxiter": maxiter, "ftol": 1e-6})
    cond_var = (fit.conditional_volatility.pow(2) / 10000.0).reindex(ret.index)
    std_resid = pd.Series(fit.std_resid, index=r.index).reindex(ret.index)
    return fit, cond_var, std_resid


def fit_hmm_regimes(
    features: pd.DataFrame,
    states: int = 4,
    n_restarts: int = 1,
    select_k_by_bic: bool = False,
    max_k: int | None = None,
) -> pd.DataFrame:
    x = features.replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < max(120, states * 25):
        raise ValueError("HMM regime engine requires more non-null observations")
    arr = (x - x.mean()) / x.std(ddof=0).replace(0, 1)
    values = arr.to_numpy(dtype=float)
    candidates = list(range(2, int(max_k or states) + 1)) if select_k_by_bic else [int(states)]
    n_restarts = max(1, int(n_restarts))
    best = None
    bic_rows = []
    for k in candidates:
        k_best = None
        for restart in range(n_restarts):
            try:
                model = GaussianHMM(n_components=k, covariance_type="diag", n_iter=150, tol=1e-4, random_state=11 + restart * 37 + k)
                model.fit(values)
                ll = float(model.score(values))
                # Means, transition matrix, start probabilities, and diagonal covariances.
                n_features = values.shape[1]
                params = k * n_features + k * k + k + k * n_features
                bic = float(-2 * ll + params * math.log(max(len(values), 2)))
                row = {"states": k, "restart": restart + 1, "log_likelihood": ll, "bic": bic, "converged": bool(getattr(model.monitor_, "converged", True))}
                bic_rows.append(row)
                if k_best is None or bic < k_best[0]:
                    k_best = (bic, model, row)
            except Exception as exc:
                bic_rows.append({"states": k, "restart": restart + 1, "error": str(exc), "converged": False})
        if k_best is not None and (best is None or k_best[0] < best[0]):
            best = k_best
    if best is None:
        raise ValueError("HMM regime engine failed across all restarts")
    hmm = best[1]
    probs = hmm.predict_proba(arr.to_numpy(dtype=float))
    state_order = np.argsort(hmm.means_[:, 0])
    states = int(hmm.n_components)
    names = ["low_vol", "transition", "high_vol", "crisis"][:states] if states <= 4 else [f"state_{i+1}" for i in range(states)]
    ordered = probs[:, state_order]
    out = pd.DataFrame(ordered, index=x.index, columns=names)
    out.attrs["bic_table"] = bic_rows
    out.attrs["selected_states"] = states
    out.attrs["n_restarts"] = n_restarts
    return out


def dcc_garch_mle(ret: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Two-stage DCC-GARCH MLE.

    Stage 1 fits univariate GARCH(1,1)-Student-t to each asset using `arch`.
    Stage 2 maximizes the Engle DCC correlation likelihood over a,b.
    """
    clean = ret.dropna(axis=1, thresh=max(260, int(len(ret) * 0.6))).dropna()
    if clean.shape[1] < 2 or len(clean) < 260:
        raise ValueError("DCC-GARCH requires at least two assets and 260 aligned observations")
    std = []
    cond_vars = {}
    for col in clean.columns:
        _, var, z = garch_fit_for_series(clean[col], "GARCH", "Student-t")
        std.append(z.reindex(clean.index).fillna(0.0).rename(col))
        cond_vars[col] = var.reindex(clean.index).ffill().bfill()
    zmat = pd.concat(std, axis=1).dropna()
    qbar = np.cov(zmat.to_numpy(dtype=float), rowvar=False)

    def neg_ll(params: np.ndarray) -> float:
        a, b = params
        if a < 0 or b < 0 or a + b >= 0.999:
            return 1e10
        return float(dcc_neg_ll_jit(zmat.to_numpy(dtype=float), qbar, float(a), float(b)))

    state_key = _mle_key("dcc", clean)
    x0 = _MLE_STATE_STORE.get(state_key, np.array([0.03, 0.94], dtype=float))
    opt = minimize(neg_ll, x0, method="L-BFGS-B", bounds=[(1e-5, 0.35), (1e-5, 0.984)], options={"maxiter": 150, "ftol": 1e-6, "gtol": 1e-5})
    a, b = opt.x if opt.success else np.array([0.03, 0.94])
    if opt.success:
        _remember_mle(state_key, opt.x)
    z = zmat.to_numpy(dtype=float)
    corr_3d = dcc_correlation_path(z, qbar, float(a), float(b))
    latest_corr = pd.DataFrame(corr_3d[-1], index=zmat.columns, columns=zmat.columns)
    latest_vol = np.sqrt(pd.DataFrame(cond_vars).reindex(zmat.index).iloc[-1].to_numpy(dtype=float) * 252)
    latest_cov = pd.DataFrame(latest_corr.to_numpy() * np.outer(latest_vol, latest_vol), index=zmat.columns, columns=zmat.columns)
    params = {"dcc_alpha": float(a), "dcc_beta": float(b), "dcc_loglik": float(-opt.fun), "dcc_converged": bool(opt.success)}
    return latest_cov, latest_corr, params


def ols_table(x: pd.DataFrame, y: pd.Series, bandwidth: int | None = None) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    data = pd.concat([y.rename("y"), x], axis=1).dropna()
    if len(data) < x.shape[1] + 3:
        beta = np.zeros(x.shape[1] + 1)
        se = np.full_like(beta, np.nan, dtype=float)
        return beta, se, 0.0, np.array([])
    X = np.column_stack([np.ones(len(data)), data[x.columns].to_numpy(dtype=float)])
    yy = data["y"].to_numpy(dtype=float)
    bw = int(bandwidth if bandwidth is not None else max(1, len(yy) ** (1 / 3)))
    return ols_hac_fast(X, yy, bw)


def covariance_methods(ret: pd.DataFrame, half_life: int = 63) -> dict[str, pd.DataFrame]:
    clean = ret.dropna(axis=1, thresh=max(30, int(len(ret) * 0.5))).fillna(0.0)
    sample = clean.cov() * 252
    lam = math.exp(math.log(0.5) / max(half_life, 1))
    weights = np.array([(1 - lam) * lam ** i for i in range(len(clean) - 1, -1, -1)], dtype=float)
    weights /= weights.sum()
    x = clean.to_numpy(dtype=float)
    x = x - np.average(x, axis=0, weights=weights)
    ewma = pd.DataFrame((x * weights[:, None]).T @ x * 252, index=clean.columns, columns=clean.columns)
    target = np.diag(np.diag(sample))
    n = clean.shape[1]
    w = len(clean)
    tr_s2 = float(np.trace(sample.to_numpy() @ sample.to_numpy()))
    tr_s = float(np.trace(sample.to_numpy()))
    denom = max((w + 1 - 2 / max(n, 1)) * (tr_s2 - tr_s**2 / max(n, 1)), 1e-12)
    shrink = float(np.clip(((1 - 2 / max(n, 1)) * tr_s2 + tr_s**2) / denom, 0.0, 1.0))
    lw = pd.DataFrame((1 - shrink) * sample.to_numpy() + shrink * target, index=clean.columns, columns=clean.columns)
    dcc = ewma.copy()
    return {"sample": sample, "ewma": ewma, "ledoit_wolf": lw, "dcc_proxy": dcc}


def fit_var(logv: pd.DataFrame, max_lag: int = 5) -> tuple[list[np.ndarray], np.ndarray, int, float]:
    y = logv.replace([np.inf, -np.inf], np.nan).dropna()
    if len(y) < max_lag + 30 or y.shape[1] < 2:
        raise ValueError("VAR requires at least two complete log-vol series")
    best = None
    arr = np.ascontiguousarray(y.to_numpy(dtype=float))
    for p in range(1, max_lag + 1):
        X, Y = build_var_design_matrix(arr, p)
        try:
            q, r = np.linalg.qr(X)
            B = solve_triangular(r, q.T @ Y, check_finite=False)
        except Exception:
            B = np.linalg.lstsq(X, Y, rcond=None)[0]
        resid = Y - X @ B
        sigma = resid.T @ resid / max(len(resid) - X.shape[1], 1)
        sign, logdet = np.linalg.slogdet(sigma + np.eye(sigma.shape[0]) * 1e-10)
        bic = logdet + (math.log(len(Y)) * (Y.shape[1] * Y.shape[1] * p + Y.shape[1])) / len(Y)
        if best is None or bic < best[0]:
            mats = [B[1 + i * Y.shape[1] : 1 + (i + 1) * Y.shape[1]].T for i in range(p)]
            best = (bic, mats, sigma, p)
    return best[1], best[2], best[3], best[0]


def var_ma_matrices(coefs: list[np.ndarray], horizon: int) -> list[np.ndarray]:
    return list(var_ma_matrices_fast(coefs, horizon))


def generalized_fevd(coefs: list[np.ndarray], sigma: np.ndarray, horizon: int = 10) -> pd.DataFrame:
    return pd.DataFrame(generalized_fevd_fast(coefs, sigma, horizon))


def statistical_jump_model(features: pd.DataFrame, states: int = 4, jump_penalty: float = 15.0, temperature: float = 0.35) -> pd.DataFrame:
    x = features.replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < states * 25:
        raise ValueError("SJM requires more observations")
    z = ((x - x.mean()) / x.std(ddof=0).replace(0, 1)).to_numpy(dtype=float)
    quantile_inits = np.quantile(z, np.linspace(0, 1, states + 2)[1:-1], axis=0)
    try:
        km = KMeans(n_clusters=states, n_init=1, init=quantile_inits, random_state=23, max_iter=200).fit(z)
    except Exception:
        km = MiniBatchKMeans(n_clusters=states, n_init=3, batch_size=256, random_state=23, max_iter=150).fit(z)
    centers = km.cluster_centers_
    dist = ((z[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    path = sjm_viterbi(dist, float(jump_penalty))
    sticky_dist = dist.copy()
    sticky_dist[np.arange(len(z)), path] *= 0.35
    probs = np.exp(-sticky_dist / max(temperature, 1e-6))
    probs = probs / np.maximum(probs.sum(axis=1, keepdims=True), 1e-12)
    order = np.argsort(centers[:, 0])
    names = ["low_vol", "transition", "high_vol", "crisis"][:states] if states <= 4 else [f"state_{i+1}" for i in range(states)]
    return pd.DataFrame(probs[:, order], index=x.index, columns=names)


def bandi_russell_daily_proxy(ohlcv: pd.DataFrame, window: int = 21, annualization: int = 252) -> pd.DataFrame:
    """Bandi-Russell correction: Parkinson variance minus twice noise variance."""
    frames = []
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        squared_return = np.log(g["Close"] / g["Close"].shift(1)).pow(2)
        park_daily = np.log(g["High"] / g["Low"]).pow(2) / (4.0 * math.log(2.0))
        noise_var = (-squared_return.rolling(window).cov(squared_return.shift(1))).clip(lower=0.0)
        dollar_vol = (g["Close"] * g["Volume"]).replace(0, np.nan)
        liq_rank = dollar_vol.rolling(window).mean().rank(pct=True).fillna(0.5)
        corrected = (park_daily.rolling(window).mean() - 2.0 * noise_var).clip(lower=0.0)
        frames.append(pd.DataFrame({"date": g["Date"], "asset": ticker, "bandi_russell_daily_proxy": np.sqrt(corrected * annualization), "microstructure_noise_variance": noise_var, "liquidity_percentile": liq_rank}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def opening_gap_fragility(ohlcv: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    rows = []
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date")
        overnight = np.log(g["Open"] / g["Close"].shift(1)).abs()
        intraday_range = np.log(g["High"] / g["Low"]).abs().replace(0, np.nan)
        fragility = (overnight / intraday_range).replace([np.inf, -np.inf], np.nan)
        pct = pd.Series(rolling_rank_pct_last_jit(fragility.to_numpy(dtype=float), int(window)), index=fragility.index)
        rows.append(pd.DataFrame({"date": g["Date"], "asset": ticker, "opening_gap_fragility": fragility, "ogf_percentile": pct}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def range_correlation_matrix(ohlcv: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    ranges = {}
    for ticker, g in ohlcv.groupby("Ticker", sort=False):
        g = g.sort_values("Date").set_index("Date")
        ranges[ticker] = np.log(g["High"] / g["Low"]).replace([np.inf, -np.inf], np.nan).tail(window)
    panel = pd.DataFrame(ranges).dropna(axis=1, thresh=30).ffill().dropna()
    if panel.empty:
        return pd.DataFrame()
    arr = panel.to_numpy(dtype=float)
    cross = arr.T @ arr
    park_sigma = np.sqrt(np.maximum(np.sum(arr * arr, axis=0) / (4.0 * math.log(2.0)), 1e-12))
    corr = cross / np.maximum(np.outer(park_sigma, park_sigma) * 4.0 * math.log(2.0), 1e-12)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(np.clip(np.nan_to_num(corr, nan=0.0), -1.0, 1.0), index=panel.columns, columns=panel.columns)


def vol_adjusted_momentum(ohlcv: pd.DataFrame, vol_panel: pd.DataFrame, lookback: int = 252) -> pd.DataFrame:
    try:
        px = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    except ValueError:
        px = ohlcv.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index()
    mom_raw = px / px.shift(lookback) - 1
    try:
        yz = vol_panel.pivot(index="date", columns="asset", values="yang_zhang")
    except ValueError:
        yz = vol_panel.pivot_table(index="date", columns="asset", values="yang_zhang", aggfunc="last")
    yz.index = pd.to_datetime(yz.index)
    common = mom_raw.index.intersection(yz.index)
    score = mom_raw.reindex(common) / yz.reindex(common).replace(0, np.nan)
    latest = score.dropna(axis=1, how="all").tail(1).T
    if latest.empty:
        return pd.DataFrame()
    latest.columns = ["vol_adjusted_momentum"]
    latest["raw_momentum"] = mom_raw.reindex(columns=latest.index).tail(1).T.iloc[:, 0]
    latest["yang_zhang_vol"] = yz.reindex(columns=latest.index).tail(1).T.iloc[:, 0]
    latest["rank"] = latest["vol_adjusted_momentum"].rank(ascending=False, method="first")
    latest["quintile"] = pd.qcut(latest["rank"], min(5, len(latest)), labels=False, duplicates="drop") + 1
    return latest.reset_index().rename(columns={"index": "asset"}).sort_values("rank")


def bipower_variation(ret: pd.Series, window: int = 22) -> pd.DataFrame:
    r = pd.to_numeric(ret, errors="coerce")
    abs_ret = r.abs()
    bpv = (math.pi / 2.0) * (abs_ret * abs_ret.shift(1)).rolling(window).sum()
    rv = r.pow(2).rolling(window).sum()
    jump = (rv - bpv).clip(lower=0)
    out = pd.DataFrame({"rv": rv, "bpv": bpv, "jump_bpv": jump})
    out["jump_share_bpv"] = out["jump_bpv"] / out["rv"].replace(0, np.nan)
    return out


def realized_garch_fit(ret: pd.Series, realized_measure: pd.Series) -> dict[str, Any]:
    r = pd.to_numeric(ret, errors="coerce").dropna() * 100.0
    x = pd.to_numeric(realized_measure, errors="coerce").reindex(r.index).ffill().bfill().clip(lower=1e-12)
    common = r.index.intersection(x.dropna().index)
    r, x = r.loc[common], x.loc[common]
    if len(r) < 120:
        raise ValueError("Realized GARCH needs 120+ observations")
    r_np = r.to_numpy(dtype=float)
    log_x = np.log(x.to_numpy(dtype=float))

    def neg_ll(params: np.ndarray) -> float:
        omega, beta, gamma, xi, phi, tau1, tau2, sigma_u = params
        if sigma_u <= 0 or beta < 0 or gamma < 0 or beta + gamma > 1.5:
            return 1e10
        return float(realized_garch_nll(r_np, log_x, omega, beta, gamma, xi, phi, tau1, tau2, sigma_u))

    state_key = _mle_key("realized_garch", r)
    x0 = _MLE_STATE_STORE.get(state_key, np.array([-0.1, 0.70, 0.20, -0.1, 0.8, -0.05, 0.05, 0.5], dtype=float))
    opt = minimize(neg_ll, x0, method="L-BFGS-B", bounds=[(-5, 5), (0.01, 0.999), (0.0, 2), (-5, 5), (0.01, 2), (-2, 2), (-2, 2), (1e-4, 5)], options={"maxiter": 400})
    p = opt.x
    if opt.success:
        _remember_mle(state_key, p)
    log_var = np.empty(len(r_np))
    log_var[0] = np.log(max(float(np.var(r_np)), 1e-10))
    for t in range(1, len(r_np)):
        log_var[t] = p[0] + p[1] * log_var[t - 1] + p[2] * log_x[t - 1]
    cond_var = pd.Series(np.exp(log_var) / 10000.0, index=r.index)
    return {
        "model": "Realized-GARCH",
        "distribution": "Gaussian",
        "parameters": {"omega": p[0], "beta": p[1], "gamma": p[2], "xi": p[3], "phi": p[4], "tau1": p[5], "tau2": p[6], "sigma_u": p[7]},
        "log_likelihood": float(-opt.fun),
        "converged": bool(opt.success),
        "cond_var_series": cond_var,
    }


def hodrick_se(x: np.ndarray, y: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    xtx_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for t in range(max(0, len(X) - horizon)):
        u_sum = resid[t : t + horizon].sum()
        meat += np.outer(X[t], X[t]) * u_sum * u_sum
    cov = xtx_inv @ meat @ xtx_inv / max(len(X) ** 2, 1)
    return beta, np.sqrt(np.maximum(np.diag(cov), 0.0))


def fit_hmm_regimes_adaptive(features: pd.DataFrame, states: int = 4, delta: float = 0.995) -> pd.DataFrame:
    x = features.replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < max(120, states * 25):
        raise ValueError("EW-HMM needs more observations")
    arr = ((x - x.mean()) / x.std(ddof=0).replace(0, 1)).to_numpy(dtype=float)
    hmm = GaussianHMM(n_components=states, covariance_type="diag", n_iter=120, tol=1e-4, random_state=29).fit(arr)
    weights = np.array([delta ** (len(arr) - 1 - t) for t in range(len(arr))], dtype=float)
    for _ in range(8):
        gamma = hmm.predict_proba(arr)
        for k in range(states):
            wk = gamma[:, k] * weights
            denom = max(wk.sum(), 1e-12)
            hmm.means_[k] = (wk[:, None] * arr).sum(axis=0) / denom
            diff = arr - hmm.means_[k]
            hmm.covars_[k] = np.maximum((wk[:, None] * diff**2).sum(axis=0) / denom, 1e-6)
    probs = hmm.predict_proba(arr)
    order = np.argsort(hmm.means_[:, 0])
    names = ["low_vol", "transition", "high_vol", "crisis"][:states] if states <= 4 else [f"state_{i+1}" for i in range(states)]
    return pd.DataFrame(probs[:, order], index=x.index, columns=names)


def hmm_filtered_posterior(features: pd.DataFrame, states: int = 4) -> pd.DataFrame:
    x = features.replace([np.inf, -np.inf], np.nan).dropna()
    arr = ((x - x.mean()) / x.std(ddof=0).replace(0, 1)).to_numpy(dtype=float)
    hmm = GaussianHMM(n_components=states, covariance_type="diag", n_iter=120, tol=1e-4, random_state=31).fit(arr)
    log_emit = np.empty((len(arr), states), dtype=float)
    for k in range(states):
        cov = np.diag(np.ravel(hmm.covars_[k])) if np.ndim(hmm.covars_[k]) == 1 else np.asarray(hmm.covars_[k], dtype=float)
        mean = hmm.means_[k]
        try:
            L = cholesky(cov + np.eye(cov.shape[0]) * 1e-10, lower=True)
            diff = arr - mean
            xsol = solve_triangular(L, diff.T, lower=True, check_finite=False)
            mahal = (xsol**2).sum(axis=0)
            log_det = 2.0 * np.log(np.diag(L)).sum()
            d = arr.shape[1]
            log_emit[:, k] = -0.5 * (d * np.log(2 * np.pi) + log_det + mahal)
        except Exception:
            log_emit[:, k] = stats.multivariate_normal.logpdf(arr, mean=mean, cov=cov, allow_singular=True)
    alpha = np.zeros((len(arr), states))
    alpha[0] = np.exp(np.log(np.maximum(hmm.startprob_, 1e-300)) + log_emit[0])
    alpha[0] /= max(alpha[0].sum(), 1e-300)
    for t in range(1, len(arr)):
        alpha[t] = np.exp(log_emit[t]) * (alpha[t - 1] @ hmm.transmat_)
        alpha[t] /= max(alpha[t].sum(), 1e-300)
    order = np.argsort(hmm.means_[:, 0])
    names = ["low_vol", "transition", "high_vol", "crisis"][:states] if states <= 4 else [f"state_{i+1}" for i in range(states)]
    return pd.DataFrame(alpha[:, order], index=x.index, columns=names)


def weibull_duration_model(regime_sequence: np.ndarray, regime_names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx, name in enumerate(regime_names):
        durs = []
        run = 0
        for s in regime_sequence:
            if int(s) == idx:
                run += 1
            elif run:
                durs.append(run)
                run = 0
        if run:
            durs.append(run)
        if len(durs) < 3:
            out[name] = {"mean_duration_days": float(np.mean(durs)) if durs else None, "n_runs": len(durs)}
            continue
        k, _, scale = stats.weibull_min.fit(np.asarray(durs, dtype=float), floc=0)
        current = durs[-1]
        out[name] = {
            "k": float(k),
            "lambda": float(scale),
            "mean_duration_days": float(scale * math.gamma(1 + 1 / max(k, 1e-6))),
            "hazard_type": "decreasing" if k < 1 else "increasing",
            "current_regime_duration_days": int(current),
            "survival_curve": [{"extra_days": d, "survival_prob": float(np.exp(-(((current + d) / max(scale, 1e-6)) ** k - (current / max(scale, 1e-6)) ** k)))} for d in [1, 5, 10, 21, 42, 63, 126]],
        }
    return clean_json(out)


def fit_var_ew(logv: pd.DataFrame, max_lag: int = 5, delta: float = 0.99) -> tuple[list[np.ndarray], np.ndarray, int, float]:
    y = logv.replace([np.inf, -np.inf], np.nan).dropna()
    if len(y) < max_lag + 30 or y.shape[1] < 2:
        raise ValueError("EW-VAR requires at least two complete log-vol series")
    arr = np.ascontiguousarray(y.to_numpy(dtype=float))
    best = None
    for p in range(1, max_lag + 1):
        X, Y = build_var_design_matrix(arr, p)
        w = np.array([delta ** (len(X) - 1 - i) for i in range(len(X))], dtype=float)
        w /= max(w.sum(), 1e-12)
        xw = X * np.sqrt(w)[:, None]
        yw = Y * np.sqrt(w)[:, None]
        try:
            q, r = np.linalg.qr(xw)
            B = solve_triangular(r, q.T @ yw, check_finite=False)
        except Exception:
            B = np.linalg.lstsq(X.T @ (X * w[:, None]), X.T @ (Y * w[:, None]), rcond=None)[0]
        resid = Y - X @ B
        sigma = (resid * w[:, None]).T @ resid
        sign, logdet = np.linalg.slogdet(sigma + np.eye(sigma.shape[0]) * 1e-10)
        bic = logdet + math.log(len(Y)) * (Y.shape[1] * Y.shape[1] * p + Y.shape[1]) / len(Y)
        if best is None or bic < best[0]:
            mats = [B[1 + i * Y.shape[1] : 1 + (i + 1) * Y.shape[1]].T for i in range(p)]
            best = (bic, mats, sigma, p)
    return best[1], best[2], best[3], best[0]


def barunik_krehlik_connectedness(coefs: list[np.ndarray], sigma: np.ndarray, bands: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    bands = bands or [(1, 5), (5, 21), (21, 252)]
    labels = ["short_run", "medium_run", "long_run"]
    n = sigma.shape[0]
    hmax = 128
    phi = np.asarray(var_ma_matrices(coefs, hmax))
    freqs = np.linspace(0, math.pi, 240, endpoint=False)
    h_idx = np.arange(len(phi), dtype=float)
    response_arr = np.einsum("fh,hnm->fnm", np.exp(-1j * np.outer(freqs, h_idx)), phi, optimize=True)
    full = np.einsum("fij,jk,flk->fil", response_arr, sigma, response_arr.conj(), optimize=True)
    denom = np.maximum(np.real(np.diagonal(full, axis1=1, axis2=2)), 1e-12)
    out = {}
    sig_diag = np.maximum(np.diag(sigma), 1e-12)
    response_sigma = np.einsum("fij,jk->fik", response_arr, sigma, optimize=True)
    num_all = (np.abs(response_sigma) ** 2) / sig_diag[None, None, :]
    for (lo, hi), label in zip(bands, labels):
        mask = (freqs >= 2 * math.pi / hi) & (freqs < 2 * math.pi / lo)
        if mask.any():
            theta = num_all[mask].mean(axis=0) / np.maximum(denom[mask].mean(axis=0)[:, None], 1e-12)
        else:
            theta = np.zeros((n, n), dtype=float)
        theta = theta / np.maximum(theta.sum(axis=1, keepdims=True), 1e-12)
        out[label] = {"connectedness": float((theta.sum() - np.trace(theta)) / n * 100), "theta": theta.tolist()}
    return clean_json(out)


def connectedness_at_risk(conn_df: pd.DataFrame, macro: pd.DataFrame, current: float) -> dict[str, Any] | None:
    if conn_df.empty:
        return None
    try:
        from sklearn.linear_model import QuantileRegressor
    except Exception:
        return None
    c = conn_df.copy()
    c["date"] = pd.to_datetime(c["date"])
    data = c.set_index("date").join(macro.set_index("date")[["vix", "credit", "curve_10y_2y"]], how="left").ffill().dropna()
    if len(data) < 60:
        return None
    y = data["connectedness"].shift(-21).dropna()
    X = data.loc[y.index, ["vix", "credit", "curve_10y_2y"]].fillna(0)
    qr = QuantileRegressor(quantile=0.95, alpha=0.1, solver="highs").fit(X.to_numpy(dtype=float), y.to_numpy(dtype=float))
    cor = float(qr.predict(data[["vix", "credit", "curve_10y_2y"]].tail(1).to_numpy(dtype=float))[0])
    return {"CoR_95": cor, "current_connectedness": float(current), "headroom": cor - float(current), "alert": bool(cor - float(current) < 5)}


def dcc_midas_long_run_corr(ret: pd.DataFrame, k_lags: int = 36) -> pd.DataFrame:
    r = ret.dropna(axis=1, thresh=60).dropna()
    if r.shape[1] < 2:
        return pd.DataFrame()
    weights_x = np.arange(1, k_lags + 1, dtype=float)
    weights = weights_x ** 0.5 * (1 - weights_x / (k_lags + 1)) ** 4
    weights /= max(weights.sum(), 1e-12)
    out = pd.DataFrame(np.eye(r.shape[1]), index=r.columns, columns=r.columns)
    month_ends = pd.date_range(r.index.min(), r.index.max(), freq="ME")
    for i, a in enumerate(r.columns):
        for b in r.columns[i + 1 :]:
            vals = []
            for end in month_ends:
                sub = r.loc[end - pd.offsets.MonthBegin(1) : end, [a, b]].dropna()
                if len(sub) >= 5:
                    vals.append(float(sub.corr().iloc[0, 1]))
            if len(vals) >= k_lags:
                val = float(np.asarray(vals[-k_lags:]) @ weights)
            else:
                val = float(r[[a, b]].corr().iloc[0, 1])
            out.loc[a, b] = out.loc[b, a] = float(np.clip(val, -0.999, 0.999))
    return out


def minimum_torsion(cov: pd.DataFrame, weights: pd.Series | None = None) -> dict[str, Any]:
    s = cov.to_numpy(dtype=float)
    vals, vecs = scipy_eigh(s + np.eye(len(s)) * 1e-10, check_finite=False, driver="evd")
    vals = np.maximum(vals, 1e-12)
    torsion = vecs @ np.diag(np.sqrt(vals)) @ vecs.T
    if weights is None:
        weights_arr = np.ones(len(s)) / max(len(s), 1)
    else:
        weights_arr = weights.reindex(cov.columns).fillna(0).to_numpy(dtype=float)
    exposures = torsion.T @ weights_arr
    contrib = exposures**2
    contrib = contrib / max(contrib.sum(), 1e-12)
    return {
        "torsion_matrix": torsion.tolist(),
        "factor_risk_contributions": [{"factor": i + 1, "primary_asset": str(cov.columns[i]), "pct_total": float(contrib[i] * 100)} for i in range(len(contrib))],
    }


def fisher_z_test_correlation_amplification(ret: pd.DataFrame, normal_mask: pd.Series, crisis_mask: pd.Series) -> list[dict[str, Any]]:
    normal = ret.loc[normal_mask.reindex(ret.index).fillna(False)].dropna()
    crisis = ret.loc[crisis_mask.reindex(ret.index).fillna(False)].dropna()
    if len(normal) < 10 or len(crisis) < 10:
        return [{"error": "insufficient observations for Fisher Z-test"}]
    cn, cc = normal.corr(), crisis.corr()
    rows = []
    for i, a in enumerate(ret.columns):
        for b in ret.columns[i + 1 :]:
            rn = float(np.clip(cn.loc[a, b], -0.9999, 0.9999))
            rc = float(np.clip(cc.loc[a, b], -0.9999, 0.9999))
            zn = 0.5 * math.log((1 + rn) / (1 - rn))
            zc = 0.5 * math.log((1 + rc) / (1 - rc))
            se = math.sqrt(1 / max(len(crisis) - 3, 1) + 1 / max(len(normal) - 3, 1))
            stat = (zc - zn) / max(se, 1e-12)
            p = float(2 * (1 - stats.norm.cdf(abs(stat))))
            rows.append({"asset_a": a, "asset_b": b, "corr_normal": rn, "corr_crisis": rc, "delta_corr": rc - rn, "fisher_z_stat": float(stat), "p_value": p, "significant_amplification": bool(p < 0.05 and rc > rn)})
    return clean_json(sorted(rows, key=lambda x: abs(x["delta_corr"]), reverse=True))


def clayton_copula_tail_dependence(ret: pd.Series, vol_changes: pd.Series, tail_pct: float = 0.20) -> dict[str, Any]:
    r = pd.to_numeric(ret, errors="coerce").dropna()
    dv = pd.to_numeric(vol_changes, errors="coerce").dropna()
    idx = r.index.intersection(dv.index)
    r, dv = r.loc[idx], dv.loc[idx]
    if len(r) < 40:
        return {"error": "insufficient observations"}
    u = pd.Series(stats.rankdata(r.to_numpy()) / (len(r) + 1), index=r.index)
    v = pd.Series(stats.rankdata(dv.to_numpy()) / (len(dv) + 1), index=dv.index)
    mask = (u < tail_pct) & (v > 1 - tail_pct)
    if mask.sum() < 10:
        mask = u < tail_pct
    u_t, v_t = u[mask].clip(1e-6, 1 - 1e-6).to_numpy(), v[mask].clip(1e-6, 1 - 1e-6).to_numpy()
    def nll(theta: float) -> float:
        inner = np.maximum(u_t ** (-theta) + v_t ** (-theta) - 1, 1e-12)
        return -float((math.log(theta + 1) - (theta + 1) * (np.log(u_t) + np.log(v_t)) - (2 + 1 / theta) * np.log(inner)).sum())
    opt = minimize(lambda x: nll(float(x[0])), np.array([1.0]), method="L-BFGS-B", bounds=[(0.01, 20)])
    theta = float(opt.x[0])
    return {"theta": theta, "lower_tail_dependence": float(2 ** (-1 / theta)), "n_tail_obs": int(mask.sum()), "converged": bool(opt.success)}


def graphical_lasso_analogs(signal: pd.DataFrame, analog_cols: list[str], k: int = 10) -> list[dict[str, Any]]:
    try:
        from sklearn.covariance import GraphicalLasso, ledoit_wolf
    except Exception:
        return []
    base = signal[analog_cols].replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0)
    base = base.loc[:, base.std(ddof=0) > 1e-12]
    analog_cols = list(base.columns)
    if len(base) < 60 or len(analog_cols) < 2:
        return []
    try:
        arr = ((base - base.mean()) / base.std(ddof=0).replace(0, 1)).to_numpy(dtype=float)
        gl = GraphicalLasso(alpha=0.1, max_iter=200).fit(arr)
        precision = np.nan_to_num(gl.precision_, nan=0.0, posinf=0.0, neginf=0.0)
    except Exception:
        arr = ((base - base.mean()) / base.std(ddof=0).replace(0, 1)).to_numpy(dtype=float)
        lw_cov, _ = ledoit_wolf(arr)
        try:
            precision = np.linalg.inv(lw_cov + np.eye(len(analog_cols)) * 1e-8)
        except Exception:
            precision = np.linalg.pinv(np.nan_to_num(base.cov().to_numpy(dtype=float), nan=0.0) + np.eye(len(analog_cols)) * 1e-6)
    recent = base.tail(30).mean().to_numpy(dtype=float)
    rows = []
    for i in range(30, len(base) - 30, 21):
        vec = base.iloc[i : i + 30].mean().to_numpy(dtype=float)
        diff = vec - recent
        rows.append({"window_start": base.index[i].strftime("%Y-%m-%d"), "distance_glasso": float(math.sqrt(max(diff @ precision @ diff, 0.0))), "avg_return": float(signal["ret"].iloc[i : i + 30].sum()), "avg_vol": float(signal["vol"].iloc[i : i + 30].mean())})
    return clean_json(sorted(rows, key=lambda x: x["distance_glasso"])[:k])


def adversarial_scenario(weights: pd.Series, ret: pd.DataFrame, signal: pd.DataFrame, analog_cols: list[str], c: float = 2.0) -> dict[str, Any]:
    data = signal[analog_cols].replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0)
    cov = data.cov().to_numpy(dtype=float) + np.eye(len(analog_cols)) * 1e-8
    try:
        c_fac = cho_factor(cov, check_finite=False)
        precision = cho_solve(c_fac, np.eye(len(cov)), check_finite=False)
    except Exception:
        precision = np.linalg.pinv(cov)
    current = data.tail(1).to_numpy(dtype=float).flatten()
    best = None
    for i in range(30, len(data) - 30, 5):
        x = data.iloc[i : i + 30].mean().to_numpy(dtype=float)
        diff = x - current
        dist = float(math.sqrt(max(diff @ precision @ diff, 0.0)))
        if dist <= c:
            pnl = float((ret.reindex(columns=weights.index).iloc[i : i + 30].sum().fillna(0) @ weights))
            if best is None or pnl < best["expected_portfolio_loss"]:
                best = {"window_start": data.index[i].strftime("%Y-%m-%d"), "expected_portfolio_loss": pnl, "mahalanobis_distance": dist, "macro_shocks": {col: float(diff[j]) for j, col in enumerate(analog_cols)}}
    return best or {"error": "no historically plausible window inside constraint", "plausibility_constraint_c": c}


def two_step_rebalance(weights: np.ndarray, cov: np.ndarray, target_vol: float, gross_cap: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    sigma = math.sqrt(max(float(weights @ cov @ weights), 1e-12))
    step1 = weights * min(target_vol / max(sigma, 1e-12), gross_cap / max(np.abs(weights).sum(), 1e-12))
    try:
        c_fac = cho_factor(cov + np.eye(len(cov)) * 1e-10, check_finite=False)
        inv = cho_solve(c_fac, np.eye(len(cov)), check_finite=False)
        ones = np.ones(len(weights))
        omega_w = cov @ step1
        A = np.array([[float(omega_w @ omega_w), float(omega_w @ inv @ ones / 2)], [float(ones @ omega_w), float(ones @ inv @ ones / 2)]])
        b = np.array([float(target_vol**2 - step1 @ cov @ step1) / 2, 0.0])
        lam = scipy_solve(A, b, check_finite=False, assume_a="gen")
        step2 = step1 - lam[0] * step1 - (lam[1] / 2) * (inv @ ones)
    except Exception:
        step2 = step1.copy()
    gross = np.abs(step2).sum()
    if gross > gross_cap:
        step2 *= gross_cap / gross
    return step1, step2


def almgren_chriss_costs(assets: list[str], old_w: np.ndarray, new_w: np.ndarray, ohlcv: pd.DataFrame, cov: pd.DataFrame, aum: float = 1e8, gamma: float = 0.1, explicit_bps: float = 5.0) -> list[dict[str, Any]]:
    dv = ohlcv.assign(dollar_volume=ohlcv["Close"] * ohlcv["Volume"]).sort_values("Date")
    adv = dv.groupby("Ticker")["dollar_volume"].apply(lambda s: float(s.tail(63).mean()))
    daily_vol = np.sqrt(np.maximum(np.diag(cov.reindex(index=assets, columns=assets).to_numpy(dtype=float)), 0) / 252)
    dw = np.abs(new_w - old_w)
    rows = []
    total = 0.0
    for i, a in enumerate(assets):
        trade = float(dw[i] * aum)
        mi = gamma * daily_vol[i] * trade / max(float(adv.get(a, 1e6)), 1e-12)
        cost_bps = explicit_bps + mi * 10000
        total += cost_bps * dw[i]
        rows.append({"asset": a, "trade_size_usd": trade, "market_impact_bps": float(mi * 10000), "explicit_bps": explicit_bps, "total_cost_bps": float(cost_bps)})
    rows.append({"asset": "TOTAL", "total_cost_bps": float(total)})
    return clean_json(rows)


def kelly_vol_target(expected_return: float, portfolio_vol: float, fixed_target: float) -> dict[str, Any]:
    if portfolio_vol <= 0:
        return {"kelly_optimal_vol_target": None, "error": "zero portfolio vol"}
    val = float(np.clip(expected_return / max(portfolio_vol, 1e-12), 0.02, 0.40))
    return {"kelly_optimal_vol_target": val, "btz_implied_return": expected_return, "dcc_portfolio_vol": portfolio_vol, "vs_fixed_target": val - fixed_target, "signal": "risk-return headroom exhausted" if val < fixed_target * 0.8 else "target justified"}


def synthetic_vol_surface(ret: pd.Series) -> list[dict[str, Any]]:
    r = pd.to_numeric(ret, errors="coerce").dropna()
    if r.empty:
        return []
    current = float(r.tail(21).std() * math.sqrt(252))
    long_run = float(r.std() * math.sqrt(252))
    horizons = np.array([5, 10, 21, 42, 63, 126, 252], dtype=float)
    quantiles = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95], dtype=float)
    horizon_vol = np.sqrt(np.maximum(long_run**2 + np.power(0.94, horizons) * (current**2 - long_run**2), 1e-12))
    skew = 1.0 + np.maximum(0.0, -stats.norm.ppf(quantiles)) * 0.02
    surface = np.clip(horizon_vol[:, None] * skew[None, :], 0.01, 2.0)
    rows = [
        {"horizon_days": int(h), "moneyness_quantile": float(q), "synthetic_vol": float(surface[i, j])}
        for i, h in enumerate(horizons)
        for j, q in enumerate(quantiles)
    ]
    return clean_json(rows)


def garch_term_structure_with_bands(
    params: dict[str, Any],
    current_var: float,
    long_run_var: float,
    horizons: Iterable[int],
    n_sim: int = 1000,
    seed: int = 23,
) -> list[dict[str, Any]]:
    """Monte Carlo GARCH term structure bands from fitted one-step variance."""
    alpha = float(params.get("alpha[1]", 0.07) or 0.07)
    beta = float(params.get("beta[1]", 0.90) or 0.90)
    gamma = float(params.get("gamma[1]", 0.0) or 0.0)
    persistence = min(max(alpha + beta + 0.5 * max(gamma, 0.0), 0.02), 0.995)
    omega = max(float(params.get("omega", long_run_var * max(1 - persistence, 0.01)) or 0.0) / 10000.0, long_run_var * max(1 - persistence, 0.005), 1e-12)
    horizons = sorted({int(h) for h in horizons if int(h) > 0})
    if not horizons:
        return []
    rng = np.random.default_rng(seed)
    max_h = max(horizons)
    v = np.full(int(n_sim), max(float(current_var), 1e-12), dtype=float)
    samples = {}
    for t in range(1, max_h + 1):
        z = rng.standard_t(df=7, size=len(v)) / math.sqrt(7 / 5)
        eps2 = v * z * z
        asym = np.where(z < 0, gamma * eps2, 0.0)
        v = np.maximum(omega + alpha * eps2 + asym + beta * v, 1e-12)
        if t in horizons:
            ann = np.sqrt(v * 252)
            point = math.sqrt(max(long_run_var + persistence**t * (current_var - long_run_var), 1e-12) * 252)
            samples[t] = {
                "horizon": t,
                "expected_ann_vol": float(point),
                "p05": float(np.quantile(ann, 0.05)),
                "p25": float(np.quantile(ann, 0.25)),
                "p50": float(np.quantile(ann, 0.50)),
                "p75": float(np.quantile(ann, 0.75)),
                "p95": float(np.quantile(ann, 0.95)),
                "n_sim": int(n_sim),
            }
    return clean_json(list(samples.values()))


def har_bootstrap_forecast_bands(
    x: pd.DataFrame,
    y: pd.Series,
    cols: list[str],
    horizon: int,
    n_boot: int = 250,
    seed: int = 31,
) -> list[dict[str, Any]]:
    frame = pd.concat([y.rename("target"), x[cols]], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < max(80, len(cols) * 10):
        return []
    yy = frame["target"]
    xx = frame[cols]
    beta, _, _, resid = ols_table(xx, yy, bandwidth=horizon)
    design = np.column_stack([np.ones(len(xx)), xx.to_numpy(dtype=float)])
    point = design @ beta
    resid = pd.Series(resid, index=frame.index).fillna(0).to_numpy(dtype=float)
    idx = stationary_bootstrap_indices(len(resid), reps=n_boot, seed=seed)
    draws = point[:, None] + resid[idx].T
    lo = np.quantile(draws, 0.05, axis=1)
    hi = np.quantile(draws, 0.95, axis=1)
    med = np.quantile(draws, 0.50, axis=1)
    out = pd.DataFrame({"date": frame.index, "forecast": point, "p05": lo, "p50": med, "p95": hi, "actual": yy.to_numpy(dtype=float)})
    return compact_records(out)


def bootstrap_var_irf_bands(logv: pd.DataFrame, horizons: Iterable[int] = (1, 5, 10, 21), reps: int = 250, seed: int = 41) -> list[dict[str, Any]]:
    clean = logv.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.shape[1] < 2 or len(clean) < 160:
        return []
    coefs, _, lag, _ = fit_var(clean, max_lag=5)
    if len(coefs) < 2:
        return []
    lag = min(max(1, int(lag)), len(coefs) - 1)
    point = var_ma_matrices(coefs, max(horizons))
    y = clean.to_numpy(dtype=float)
    fitted = []
    for t in range(lag, len(y)):
        pred = coefs[0].copy()
        for l in range(lag):
            pred += coefs[l + 1] @ y[t - l - 1]
        fitted.append(pred)
    resid = y[lag:] - np.asarray(fitted)
    if len(resid) < 80:
        return []
    rng = np.random.default_rng(seed)
    draws: dict[tuple[int, int], list[float]] = {(h, i): [] for h in horizons for i in range(clean.shape[1])}
    for _ in range(int(reps)):
        sampled = resid[rng.integers(0, len(resid), size=len(resid))]
        synth = np.vstack([y[:lag], np.zeros_like(y[lag:])])
        for t in range(lag, len(y)):
            pred = coefs[0].copy()
            for l in range(lag):
                pred += coefs[l + 1] @ synth[t - l - 1]
            synth[t] = pred + sampled[t - lag]
        try:
            bcoef, _, _, _ = fit_var(pd.DataFrame(synth, index=clean.index, columns=clean.columns), max_lag=lag)
            if len(bcoef) < 2:
                continue
            bphis = var_ma_matrices(bcoef, max(horizons))
            for h in horizons:
                for i in range(clean.shape[1]):
                    draws[(h, i)].append(float(bphis[h][i].sum()))
        except Exception:
            continue
    rows = []
    for h in horizons:
        for i, asset in enumerate(clean.columns):
            vals = np.asarray(draws[(h, i)], dtype=float)
            rows.append({
                "horizon": int(h),
                "asset": str(asset),
                "response": float(point[h][i].sum()),
                "p05": float(np.quantile(vals, 0.05)) if len(vals) else None,
                "p50": float(np.quantile(vals, 0.50)) if len(vals) else None,
                "p95": float(np.quantile(vals, 0.95)) if len(vals) else None,
                "reps": int(len(vals)),
            })
    return clean_json(rows)


def matrix_records(mat: pd.DataFrame, value_name: str = "value") -> list[dict[str, Any]]:
    rows = []
    for r in mat.index:
        for c in mat.columns:
            rows.append({"row": str(r), "col": str(c), value_name: float(mat.loc[r, c])})
    return clean_json(rows)


def corr_from_cov(cov: pd.DataFrame) -> pd.DataFrame:
    diag = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    arr = cov.to_numpy(dtype=float) / np.outer(diag, diag)
    return pd.DataFrame(np.clip(arr, -1, 1), index=cov.index, columns=cov.columns)


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
                raise ValueError("weights must be a JSON object or SYMBOL:value pairs") from exc
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


def summary_card(label: str, value: Any, unit: str = "", **extra: Any) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, **extra}
