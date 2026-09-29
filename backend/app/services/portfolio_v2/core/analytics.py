"""Shared Portfolio V2 analytics.

The code here implements live calculations from local parquet data. Advanced
outputs that require missing institutional datasets are returned with explicit
access issues instead of synthetic claims.
"""

from __future__ import annotations

from typing import Any, Iterable
from functools import lru_cache
import hashlib
import json
import math

import numpy as np
import numba as nb
import pandas as pd
from scipy import stats
from scipy.linalg import pinv as scipy_pinv
from scipy.optimize import minimize, linprog
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf, OAS
from sklearn.preprocessing import StandardScaler

try:
    from sklearn.mixture import GaussianMixture
except Exception:  # pragma: no cover
    GaussianMixture = None

try:
    from hmmlearn.hmm import GaussianHMM
except Exception:  # pragma: no cover
    GaussianHMM = None

from .data_loader import (
    annualization_factor,
    close_matrix,
    current_holdings_weights,
    data_inventory,
    dollar_volume_matrix,
    load_macro,
    market_caps,
    normalize_symbol,
    ohlcv_for_symbols,
    parse_symbols,
    returns_matrix,
    sector_map,
)
from .performance import (
    cached_correlation_frame,
    cached_covariance_frame,
    cached_result,
    compact_table,
    covariance_to_correlation,
    dataframe_fingerprint,
    fast_corr,
    fast_matrix_records,
    fast_network_edges_from_corr,
    float_array,
    nearest_psd,
    performance_snapshot,
    rank_ic_curve,
    rolling_diversification_ratio,
    rolling_leading_eigenvalue,
    safe_eigh,
    safe_inverse,
)

_INVENTORY_CACHE: dict[str, Any] | None = None
_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}
_CONTEXT_CACHE_MAX = 8


def fast_pinv(mat: np.ndarray) -> np.ndarray:
    a = np.asfortranarray(mat, dtype=np.float64)
    return scipy_pinv(a, check_finite=False, atol=1e-12, rtol=0.0)


def fast_solve(mat: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    a = np.ascontiguousarray(mat, dtype=np.float64)
    b = np.ascontiguousarray(rhs, dtype=np.float64)
    try:
        return np.linalg.solve(a, b)
    except np.linalg.LinAlgError:
        return fast_pinv(a) @ b


@lru_cache(maxsize=128)
def _ewma_weights(lam: float, n: int) -> np.ndarray:
    i = np.arange(n - 1, -1, -1, dtype=np.float64)
    w = (1.0 - lam) * np.power(lam, i)
    w /= w.sum()
    return w


def _payload_key(payload: dict | None, min_symbols: int, default_limit: int) -> str:
    try:
        canonical = json.dumps(payload or {}, sort_keys=True, default=str)
    except Exception:
        canonical = str(payload or {})
    raw = f"{min_symbols}:{default_limit}:{canonical}"
    return hashlib.blake2b(raw.encode(), digest_size=10).hexdigest()


def _cached_data_inventory() -> dict[str, Any]:
    global _INVENTORY_CACHE
    if _INVENTORY_CACHE is None:
        _INVENTORY_CACHE = data_inventory()
    return _INVENTORY_CACHE


def clean_json(value: Any) -> Any:
    if value is None:
        return None
    t = type(value)
    if t is str or t is bool:
        return value
    if t is int:
        return value
    if t is float:
        return value if math.isfinite(value) else None
    if t is dict:
        return {str(k): clean_json(v) for k, v in value.items()}
    if t is list:
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.to_dict())
    if isinstance(value, pd.DataFrame):
        out = value.copy()
        for col in out.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            out[col] = out[col].dt.strftime("%Y-%m-%d")
        return clean_json(out.to_dict("records"))
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    return value


def number_like(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def compact_records(df: pd.DataFrame, limit: int = 600) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    tbl = compact_table(df, limit)
    dt_cols = [c for c in tbl.columns if pd.api.types.is_datetime64_any_dtype(tbl[c])]
    if dt_cols:
        tbl = tbl.copy()
        for col in dt_cols:
            tbl[col] = tbl[col].dt.strftime("%Y-%m-%d")
    return clean_json(tbl.to_dict("records"))


def matrix_records(matrix: pd.DataFrame | np.ndarray, labels: Iterable[str] | None = None, limit: int = 120) -> list[dict[str, Any]]:
    return clean_json(fast_matrix_records(matrix, labels, limit))


def response(feature_id: str, summary_cards: list[dict[str, Any]], charts: dict[str, Any], tables: dict[str, Any], meta: dict[str, Any] | None = None, alerts: list[dict[str, Any]] | None = None, status: str = "ok") -> dict[str, Any]:
    return clean_json({"feature_id": f"feature_{str(feature_id).zfill(2)}", "status": status, "summary_cards": summary_cards, "charts": charts, "tables": tables, "alerts": alerts or [], "meta": meta or {}})


def parse_compute_mode(payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    return "research" if str(payload.get("compute_mode") or "").lower() == "research" or payload.get("research_mode") is True else "realtime"


def load_context(payload: dict[str, Any] | None, *, min_symbols: int = 12, default_limit: int = 80) -> dict[str, Any]:
    payload = payload or {}
    key = _payload_key(payload, min_symbols, default_limit)
    cached = _CONTEXT_CACHE.get(key)
    if cached is not None:
        return cached
    lookback = int(number_like(payload.get("lookback_days") or payload.get("window_days") or payload.get("window_length"), 756) or 756)
    full = str(payload.get("universe") or payload.get("tickers") or "").lower() in {"all", "full", "master", "master_universe"} or bool(payload.get("use_full_master_universe"))
    max_symbols = int(number_like(payload.get("max_symbols") or payload.get("max_tickers"), 5000 if full else default_limit) or default_limit)
    symbols = parse_symbols(payload, default_limit=max(default_limit, min_symbols), max_symbols=max_symbols)
    frequency = str(payload.get("frequency") or payload.get("sampling_frequency") or "daily")
    rets = returns_matrix(symbols, lookback_days=max(lookback, 90), frequency=frequency)
    if rets.shape[1] < min_symbols:
        symbols = parse_symbols({}, default_limit=max(default_limit, min_symbols), max_symbols=max_symbols)
        rets = returns_matrix(symbols, lookback_days=max(lookback, 90), frequency=frequency)
    rets = rets.dropna(axis=1, how="all").fillna(0.0)
    symbols = [str(c) for c in rets.columns]
    weights = parse_weights(payload, symbols)
    if weights is None:
        weights = current_holdings_weights(symbols).reindex(symbols).fillna(0.0)
        if float(weights.sum()) <= 0:
            weights = pd.Series(np.repeat(1 / max(len(symbols), 1), len(symbols)), index=symbols)
        else:
            weights = weights / weights.sum()
    ctx = {
        "payload": payload,
        "symbols": symbols,
        "returns": rets,
        "weights": weights.reindex(symbols).fillna(0.0).astype(float),
        "lookback_days": lookback,
        "frequency": frequency,
        "annualization_factor": annualization_factor(frequency),
        "sectors": sector_map(symbols),
        "market_caps": market_caps(symbols),
        "compute_mode": parse_compute_mode(payload),
        "inventory": _cached_data_inventory(),
    }
    if len(_CONTEXT_CACHE) >= _CONTEXT_CACHE_MAX:
        _CONTEXT_CACHE.pop(next(iter(_CONTEXT_CACHE)))
    _CONTEXT_CACHE[key] = ctx
    return ctx


def parse_weights(payload: dict[str, Any], symbols: list[str]) -> pd.Series | None:
    raw = payload.get("weights") or payload.get("portfolio_weights")
    if raw is None:
        return None
    out: dict[str, float] = {}
    if isinstance(raw, str):
        for part in raw.replace(";", ",").split(","):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            val = number_like(v)
            if val is not None:
                out[str(k).strip().upper().replace(".", "_").replace("-", "_")] = val
    elif isinstance(raw, dict):
        out = {str(k).strip().upper().replace(".", "_").replace("-", "_"): float(v) for k, v in raw.items() if number_like(v) is not None}
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                s = item.get("ticker") or item.get("symbol") or item.get("asset")
                v = item.get("weight") or item.get("target_weight")
                if s and number_like(v) is not None:
                    out[str(s).strip().upper().replace(".", "_").replace("-", "_")] = float(v)
    if not out:
        return None
    w = pd.Series(out, dtype=float).reindex(symbols).fillna(0.0)
    s = float(np.abs(w).sum())
    return w / s if s > 1e-12 else None


def covariance_matrix(returns: pd.DataFrame, method: str = "ledoit_wolf") -> tuple[pd.DataFrame, dict[str, Any]]:
    method = str(method or "ledoit_wolf").lower().replace("-", "_")
    if returns.empty:
        return pd.DataFrame(), {"estimator": method}

    def build() -> tuple[pd.DataFrame, dict[str, Any]]:
        x = returns.fillna(0.0).to_numpy(dtype=np.float64, copy=False)
        meta: dict[str, Any] = {"estimator": method}
        if method in {"dcc_garch", "dcc"}:
            out = dcc_garch_cov(returns)
            return out["covariance"], {"estimator": "dcc_garch", "note": "DCC-style dynamic covariance with EWMA vol recursion"}
        if method in {"factor_structured", "ff5", "structured"}:
            return factor_structured_cov(returns), {"estimator": "factor_structured"}
        if method in {"gerber", "gerber_statistic"}:
            return gerber_statistic_cov(returns), {"estimator": "gerber"}
        if method in {"ledoit_wolf", "lw"}:
            x_centered = x - x.mean(axis=0)
            est = LedoitWolf(assume_centered=True).fit(x_centered)
            meta["shrinkage"] = float(est.shrinkage_)
            cov = est.covariance_
        elif method in {"nonlinear_shrinkage", "eigenvalue_shrinkage"}:
            # Rotation-equivariant eigenvalue regularisation.  It retains the
            # sample eigenvectors while shrinking noisy small eigenvalues toward
            # their bulk median, unlike the scalar Ledoit-Wolf estimator.
            sample = np.cov(x, rowvar=False)
            vals, vecs = np.linalg.eigh((sample + sample.T) * 0.5)
            bulk = float(np.median(np.maximum(vals, 1e-12)))
            aspect = x.shape[1] / max(x.shape[0], 1)
            strength = min(0.85, max(0.10, aspect))
            shrunk = (1.0 - strength) * np.maximum(vals, 1e-12) + strength * bulk
            cov = (vecs * shrunk) @ vecs.T
            meta.update({"shrinkage": strength, "eigenvalue_floor": bulk, "methodology": "rotation_equivariant_eigenvalue_shrinkage"})
        elif method == "oas":
            est = OAS().fit(x)
            meta["shrinkage"] = float(est.shrinkage_)
            cov = est.covariance_
        elif method in {"constant_correlation", "cc"}:
            vols = returns.std().replace(0, np.nan).fillna(returns.std().mean())
            corr = cached_correlation_frame(returns)
            avg = float((corr.to_numpy()[np.triu_indices(len(corr), 1)]).mean()) if len(corr) > 1 else 0.0
            cov = np.outer(vols, vols) * avg
            np.fill_diagonal(cov, vols.to_numpy() ** 2)
            meta["average_correlation"] = avg
        elif method == "ewma":
            lam = 0.94
            w = _ewma_weights(lam, len(x))
            xc = x - np.average(x, axis=0, weights=w)
            # einsum: cov[j,k] = sum_i w[i] * xc[i,j] * xc[i,k]
            cov = np.einsum("i,ij,ik->jk", w, xc, xc)
            meta["lambda"] = lam
        else:
            cov = np.cov(x, rowvar=False)
        cov = nearest_psd(np.nan_to_num((cov + cov.T) / 2, nan=0.0, posinf=0.0, neginf=0.0))
        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns), meta

    return cached_covariance_frame(returns, method, build)


def expected_returns(returns: pd.DataFrame, method: str = "shrinkage", ann: float = 252.0) -> pd.Series:
    mu = returns.mean() * ann
    if method in {"sample", "mean"}:
        return mu.fillna(0.0)
    grand = float(mu.mean()) if len(mu) else 0.0
    n = max(len(returns), 1)
    shrink = min(0.75, max(0.15, 20.0 / n))
    return ((1 - shrink) * mu + shrink * grand).fillna(0.0)


def portfolio_return_series(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = weights.reindex(returns.columns).fillna(0.0).to_numpy(dtype=np.float64)
    arr = returns.to_numpy(dtype=np.float64)
    np.nan_to_num(arr, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    return pd.Series(arr @ w, index=returns.index)


@nb.njit(cache=True, fastmath=True)
def _jit_portfolio_metrics(r: np.ndarray, ann: float):
    """Full metric set in a single compiled pass — no intermediate arrays."""
    T = r.shape[0]
    mean = 0.0
    for i in range(T):
        mean += r[i]
    mean /= T
    var = 0.0
    for i in range(T):
        d = r[i] - mean
        var += d * d
    var = var / max(T - 1, 1)
    std = math.sqrt(var) if var > 0.0 else 0.0
    vol = std * math.sqrt(ann)
    annual_ret = mean * ann
    sharpe = annual_ret / vol if vol > 1e-12 else 0.0
    neg_ss = 0.0
    neg_n = 0
    for i in range(T):
        if r[i] < 0.0:
            neg_ss += r[i] * r[i]
            neg_n += 1
    downside = math.sqrt(neg_ss / max(neg_n - 1, 1)) * math.sqrt(ann) if neg_n > 1 else 0.0
    sortino = annual_ret / downside if downside > 1e-12 else 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for i in range(T):
        equity *= 1.0 + r[i]
        if equity > peak:
            peak = equity
        dd = equity / peak - 1.0
        if dd < max_dd:
            max_dd = dd
    sorted_r = np.sort(r)
    q05_idx = max(0, int(0.05 * T) - 1)
    q05 = sorted_r[q05_idx]
    cvar_sum = 0.0
    cvar_n = 0
    for i in range(T):
        if r[i] <= q05:
            cvar_sum += r[i]
            cvar_n += 1
    cvar = cvar_sum / max(cvar_n, 1)
    m3 = 0.0
    m4 = 0.0
    for i in range(T):
        d = r[i] - mean
        d2 = d * d
        m3 += d2 * d
        m4 += d2 * d2
    m3 /= T
    m4 /= T
    skew = m3 / max(var ** 1.5, 1e-18)
    kurt = m4 / max(var ** 2, 1e-18) - 3.0
    return annual_ret, vol, sharpe, sortino, max_dd, q05, cvar, skew, kurt


def performance_metrics(series: pd.Series, ann: float = 252.0) -> dict[str, float]:
    r = pd.Series(series).to_numpy(dtype=np.float64)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return {}
    annual_ret, vol, sharpe, sortino, max_dd, q05, cvar, skew, kurt = _jit_portfolio_metrics(r, ann)
    return {
        "annual_return": float(annual_ret),
        "annual_vol": float(vol),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_dd),
        "var_95": float(q05),
        "cvar_95": float(cvar),
        "skew": float(skew),
        "kurtosis": float(kurt),
    }


def optimize_portfolios(returns: pd.DataFrame, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    ann = annualization_factor(payload.get("frequency", "daily"))
    cov, cov_meta = covariance_matrix(returns, payload.get("covariance_estimator", "ledoit_wolf"))
    mu = expected_returns(returns, payload.get("expected_return_estimator", "shrinkage"), ann)
    cols = list(returns.columns)
    n = len(cols)
    if n == 0:
        return {"weights": {}, "frontier": [], "meta": {"access_issues": ["no return matrix"]}}
    cov_ann = cov.to_numpy(dtype=float) * ann
    inv = fast_pinv(cov_ann + np.eye(n) * 1e-10)
    ones = np.ones(n)
    bounds, constraints, constraint_meta = _portfolio_constraints(cols, payload, ctx_weights=payload.get("current_weights") or payload.get("weights"))
    gmv = _solve_constrained(cov_ann, ones, bounds, constraints, objective="min_variance")
    max_sharpe = _solve_constrained(cov_ann, mu.reindex(cols).to_numpy(dtype=float), bounds, constraints, objective="max_sharpe")
    vols = np.sqrt(np.maximum(np.diag(cov_ann), 1e-12))
    invvol = 1 / vols
    invvol /= invvol.sum()
    risk_parity = _risk_parity(cov_ann)
    max_div = _max_diversification(cov_ann)
    hrp = _hrp_weights(cached_correlation_frame(returns), vols, cols, cov_ann)
    frontier = []
    for target in np.linspace(float(mu.min()), float(mu.max()), 100):
        w = _min_var_target(mu.reindex(cols).to_numpy(dtype=float), cov_ann, target, bounds, constraints)
        ret = float(w @ mu.reindex(cols).to_numpy(dtype=float))
        vol = float(math.sqrt(max(w @ cov_ann @ w, 0.0)))
        frontier.append({"target_return": target, "return": ret, "vol": vol, "sharpe": ret / vol if vol > 1e-12 else 0.0})
    weight_map = {
        "global_min_variance": gmv,
        "max_sharpe": max_sharpe,
        "inverse_vol": invvol,
        "risk_parity": risk_parity,
        "max_diversification": max_div,
        "hrp": hrp,
    }
    kelly = kelly_sizing(mu.reindex(cols), pd.DataFrame(cov_ann, index=cols, columns=cols), None, 1.0, float(payload.get("leverage_cap") or 1.0), float(payload.get("transaction_cost_bps") or 10.0))
    weight_map["growth_optimal"] = np.array([r["constrained_weight"] for r in kelly["table"]], dtype=float)
    try:
        bl_w = black_litterman_weights(returns, pd.Series(gmv, index=cols))
        cvar_w = cvar_minimize(returns)
        weight_map["black_litterman"] = bl_w.reindex(cols).fillna(0.0).to_numpy()
        weight_map["cvar_min"] = cvar_w.reindex(cols).fillna(0.0).to_numpy()
    except Exception as exc:
        cov_meta["advanced_objective_warning"] = str(exc)
    rows = []
    for name, w in weight_map.items():
        for symbol, weight in zip(cols, w):
            rows.append({"portfolio": name, "ticker": symbol, "weight": float(weight)})
    return {
        "weights": {k: pd.Series(v, index=cols) for k, v in weight_map.items()},
        "weight_table": rows,
        "frontier": frontier,
        "covariance": cov,
        "mu": mu,
        "meta": {**cov_meta, "constraints": constraint_meta},
    }


def _portfolio_constraints(cols: list[str], payload: dict[str, Any], ctx_weights: Any = None):
    n = len(cols)
    def parse_bound(raw: Any, default: float) -> np.ndarray:
        if isinstance(raw, dict):
            return np.asarray([float(raw.get(c, default)) for c in cols], dtype=float)
        value = number_like(raw)
        return np.repeat(default if value is None else float(value), n)
    lo = parse_bound(payload.get("min_weights"), 0.0)
    hi = parse_bound(payload.get("max_weights"), float(payload.get("max_weight") or 1.0))
    hi = np.maximum(hi, lo)
    constraints: list[dict[str, Any]] = [{"type": "eq", "fun": lambda w: float(w.sum() - 1.0)}]
    sectors = payload.get("sector_map") or {}
    sector_caps = payload.get("sector_max_weights") or {}
    for sector, cap in sector_caps.items() if isinstance(sector_caps, dict) else []:
        idx = np.asarray([i for i, c in enumerate(cols) if sectors.get(c) == sector], dtype=int)
        if idx.size:
            constraints.append({"type": "ineq", "fun": lambda w, idx=idx, cap=float(cap): float(cap - w[idx].sum())})
    current = parse_weights({"weights": ctx_weights}, cols) if ctx_weights else None
    turnover = number_like(payload.get("max_turnover"))
    if current is not None and turnover is not None:
        constraints.append({"type": "ineq", "fun": lambda w, current=current.to_numpy(), turnover=float(turnover): float(turnover - np.abs(w - current).sum() / 2.0)})
    return list(zip(lo, hi)), constraints, {"min_weight": float(lo.min()), "max_weight": float(hi.max()), "sector_caps": sector_caps, "max_turnover": turnover}


def _solve_constrained(cov: np.ndarray, mu: np.ndarray, bounds, constraints, objective: str) -> np.ndarray:
    n = len(mu)
    x0 = np.repeat(1.0 / n, n)
    if objective == "max_sharpe":
        def fun(w):
            vol = math.sqrt(max(float(w @ cov @ w), 1e-12))
            return -float(w @ mu) / vol
    else:
        def fun(w): return float(w @ cov @ w)
    result = minimize(fun, x0, method="SLSQP", bounds=bounds, constraints=constraints, options={"maxiter": 500, "ftol": 1e-10})
    return result.x if result.success else x0


def _min_var_target(mu: np.ndarray, cov: np.ndarray, target: float, bounds=None, base_constraints=None) -> np.ndarray:
    n = len(mu)
    cons = list(base_constraints or [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]) + [{"type": "eq", "fun": lambda w: float(w @ mu) - target}]
    res = minimize(lambda w: float(w @ cov @ w), np.repeat(1 / n, n), bounds=bounds or [(0, 1)] * n, constraints=cons, method="SLSQP", options={"maxiter": 300, "ftol": 1e-9})
    return res.x if res.success else np.repeat(1 / n, n)


def _risk_parity(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    vols = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    w0 = 1.0 / vols
    w0 /= max(float(w0.sum()), 1e-12)

    def obj(w: np.ndarray) -> float:
        Cw = cov @ w
        port_var = float(np.dot(w, Cw))
        port = math.sqrt(max(port_var, 1e-12))
        rc = w * Cw / port
        return float(((rc - rc.mean()) ** 2).sum())

    res = minimize(obj, w0, bounds=[(1e-6, 1)] * n, constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1}, method="SLSQP", options={"maxiter": 300, "ftol": 1e-10})
    return res.x if res.success else w0


def _max_diversification(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    vols = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    w0 = 1.0 / vols
    w0 /= max(float(w0.sum()), 1e-12)
    def obj(w: np.ndarray) -> float:
        return -float((w @ vols) / math.sqrt(max(float(w @ cov @ w), 1e-12)))
    res = minimize(obj, w0, bounds=[(1e-6, 1)] * n, constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1}, method="SLSQP", options={"maxiter": 300, "ftol": 1e-10})
    return res.x if res.success else w0


def _hrp_weights(corr: pd.DataFrame, vols: np.ndarray, cols: list[str], cov: np.ndarray | None = None) -> np.ndarray:
    """Lopez de Prado hierarchical risk parity with recursive bisection."""
    if len(cols) <= 2:
        w = 1 / np.maximum(vols, 1e-12)
        return w / w.sum()
    corr_arr = corr.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float)
    corr_arr = np.clip((corr_arr + corr_arr.T) / 2, -1, 1)
    np.fill_diagonal(corr_arr, 1.0)
    link = linkage(squareform(np.sqrt(np.maximum((1.0 - corr_arr) / 2.0, 0.0)), checks=False), method="single")
    order: list[int] = []
    def leaves(node: int):
        if node < len(cols): order.append(node); return
        left, right = link[node - len(cols), :2].astype(int)
        leaves(left); leaves(right)
    leaves(2 * len(cols) - 2)
    cov_arr = cov if cov is not None else np.outer(vols, vols) * corr_arr
    w = np.ones(len(cols), dtype=float)
    clusters = [order]
    while clusters:
        next_clusters = []
        for cluster in clusters:
            if len(cluster) <= 1: continue
            split = len(cluster) // 2
            left, right = cluster[:split], cluster[split:]
            def cluster_var(index):
                sub = cov_arr[np.ix_(index, index)]
                iv = 1.0 / np.maximum(np.diag(sub), 1e-12); iv /= iv.sum()
                return float(iv @ sub @ iv)
            lv, rv = cluster_var(left), cluster_var(right)
            alpha = 1.0 - lv / max(lv + rv, 1e-12)
            w[left] *= alpha; w[right] *= 1.0 - alpha
            next_clusters.extend([left, right])
        clusters = next_clusters
    return w / max(w.sum(), 1e-12)


def brinson_attribution(returns: pd.DataFrame, weights: pd.Series, sectors: dict[str, str]) -> list[dict[str, Any]]:
    cols = list(returns.columns)
    port_w = weights.reindex(cols).fillna(0.0).to_numpy(dtype=np.float64)
    bench_w = np.repeat(1 / max(len(cols), 1), len(cols))
    mean_ret = returns.mean().to_numpy(dtype=np.float64)
    sector_arr = np.asarray([sectors.get(c, "Unknown") for c in cols], dtype=object)
    unique_sectors = sorted(set(sectors.values()))
    rows = []
    for sector in unique_sectors:
        idx = np.flatnonzero(sector_arr == sector)
        if not idx.size:
            continue
        pw = float(port_w[idx].sum())
        bw = float(bench_w[idx].sum())
        # weighted sector returns — avoid scalar division in a loop
        pr = float(np.dot(port_w[idx], mean_ret[idx]) / max(abs(pw), 1e-12))
        br = float(np.dot(bench_w[idx], mean_ret[idx]) / max(abs(bw), 1e-12))
        rows.append({
            "sector": sector,
            "portfolio_weight": pw,
            "benchmark_weight": bw,
            "allocation_effect": (pw - bw) * br,
            "selection_effect": bw * (pr - br),
            "interaction_effect": (pw - bw) * (pr - br),
        })
    return clean_json(rows)


def rolling_regimes(portfolio_returns: pd.Series, macro: pd.DataFrame, n_regimes: int = 3) -> pd.DataFrame:
    r = portfolio_returns.dropna().rename("portfolio_return").to_frame()
    if r.empty:
        return pd.DataFrame()
    features = pd.DataFrame(index=r.index)
    features["vol_21"] = r["portfolio_return"].rolling(21).std().bfill()
    features["mom_63"] = r["portfolio_return"].rolling(63).sum().fillna(0.0)
    if not macro.empty:
        m = macro.set_index("date").reindex(r.index, method="ffill")
        for col in ["vix_close", "vixcls", "yc_slope_10y_2y", "bamlh0a0hym2"]:
            if col in m.columns:
                features[col] = m[col].ffill().pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x_raw = features.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    x = StandardScaler().fit_transform(x_raw)
    if GaussianHMM is not None and len(x) >= max(90, n_regimes * 25):
        hmm = GaussianHMM(n_components=n_regimes, covariance_type="diag", min_covar=1e-6, n_iter=200, random_state=7).fit(x)
        labels = pd.Series(hmm.predict(x), index=features.index)
    elif GaussianMixture is None or len(x) < 90:
        q = pd.qcut(features["vol_21"].rank(method="first"), q=min(n_regimes, len(features)), labels=False, duplicates="drop")
        labels = pd.Series(q, index=features.index).fillna(0).astype(int)
    else:
        labels = pd.Series(GaussianMixture(n_components=n_regimes, covariance_type="full", random_state=7).fit_predict(x), index=features.index)
    out = features.reset_index()
    out = out.rename(columns={out.columns[0]: "date"})
    out["regime"] = labels.values
    return out


def liquidity_table(symbols: list[str], lookback_days: int = 252, nav: float = 1_000_000.0, weights: pd.Series | None = None) -> list[dict[str, Any]]:
    raw = ohlcv_for_symbols(symbols, lookback_days=lookback_days)
    if raw.empty:
        return []
    w = weights.reindex(symbols).fillna(1 / max(len(symbols), 1)) if weights is not None else pd.Series(np.repeat(1 / max(len(symbols), 1), len(symbols)), index=symbols)
    df = raw.sort_values(["Ticker", "Date"]).copy()
    close_arr = df["Close"].to_numpy(dtype=np.float64)
    vol_arr = df["Volume"].fillna(0.0).to_numpy(dtype=np.float64)
    df["dv"] = close_arr * vol_arr
    df["dv"] = df["dv"].replace(0.0, np.nan)
    prev_close = df.groupby("Ticker", sort=False)["Close"].shift(1).to_numpy(dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret_abs = np.abs(close_arr / prev_close - 1.0)
    df["ret_abs"] = ret_abs
    df["amihud_raw"] = df["ret_abs"] / df["dv"]
    df["amihud_raw"] = df["amihud_raw"].replace([np.inf, -np.inf], np.nan)
    agg = df.groupby("Ticker", sort=False).agg(
        amihud=("amihud_raw", "mean"),
        adv=("dv", lambda x: x.tail(60).mean())
    )
    rows = []
    for s in symbols:
        ns = normalize_symbol(s)
        if ns not in agg.index:
            continue
        amihud = float(agg.at[ns, "amihud"]) if pd.notna(agg.at[ns, "amihud"]) else 0.0
        adv = float(agg.at[ns, "adv"]) if pd.notna(agg.at[ns, "adv"]) else 0.0
        position = float(abs(w.get(ns, 0.0)) * nav)
        days_15 = position / max(adv * 0.15, 1.0)
        days_20 = position / max(adv * 0.20, 1.0)
        rows.append({
            "ticker": ns,
            "amihud": amihud,
            "adv_dollars": adv,
            "position_dollars": position,
            "days_to_liquidate_15pct_adv": days_15,
            "days_to_liquidate_20pct_adv": days_20,
            "liquidity_var_bps": 10000 * math.sqrt(max(amihud, 0.0) * max(position, 1.0))
        })
    return clean_json(rows)


def correlation_diagnostics(returns: pd.DataFrame) -> dict[str, Any]:
    corr = cached_correlation_frame(returns)
    vals = safe_eigh(corr.to_numpy(dtype=np.float64, copy=False))[0] if len(corr) else np.array([])
    vals = np.maximum(vals, 0.0)
    leading = float(vals.max()) if len(vals) else 0.0
    enb = float((vals.sum() ** 2) / max((vals ** 2).sum(), 1e-12)) if len(vals) else 0.0
    return {"corr": corr, "eigenvalues": vals[::-1], "leading_eigenvalue": leading, "effective_bets": enb}


def alpha_decay(returns: pd.DataFrame, factor_returns: pd.Series | None = None, max_horizon: int = 63) -> dict[str, Any]:
    if returns.empty:
        return {"ic_curve": [], "half_life": None}
    rows = cached_result(
        f"rank_ic_curve.{int(max_horizon)}",
        dataframe_fingerprint(returns),
        lambda: rank_ic_curve(returns, max_horizon=int(max_horizon)),
    )
    arr = np.abs([r["ic"] for r in rows])
    base = max(arr[0] if len(arr) else 0.0, 1e-9)
    below = np.where(arr <= base / 2)[0]
    half = int(below[0] + 1) if len(below) else None
    return {"ic_curve": rows, "half_life": half}


def kelly_sizing(mu: pd.Series, cov: pd.DataFrame, current: pd.Series | None = None, fraction: float = 0.5, leverage_cap: float = 1.0, tc_bps: float = 10.0) -> dict[str, Any]:
    cols = list(mu.index)
    n = len(cols)
    mu_arr = mu.to_numpy(dtype=np.float64)
    sigma = cov.reindex(index=cols, columns=cols).to_numpy(dtype=np.float64) + np.eye(n) * 1e-9
    raw = fast_solve(sigma, mu_arr)
    np.nan_to_num(raw, copy=False)
    abs_sum = float(np.abs(raw).sum())
    if abs_sum > 1e-12:
        raw *= min(leverage_cap, abs_sum) / abs_sum
    w = np.clip(raw * fraction, -leverage_cap, leverage_cap)
    wabs = float(np.abs(w).sum())
    if wabs > leverage_cap:
        w *= leverage_cap / wabs
    cur = current.reindex(cols).fillna(0.0).to_numpy(dtype=np.float64) if current is not None else np.zeros(n)
    rows = [
        {"ticker": s, "kelly_weight": float(r), "constrained_weight": float(wi),
         "current_weight": float(ci), "sizing_gap": float(wi - ci)}
        for s, r, wi, ci in zip(cols, raw, w, cur)
    ]
    fracs = np.linspace(0.05, 1.0, 40, dtype=np.float64)
    tc = float(2 * tc_bps / 10000)
    grid = []
    for f in fracs:
        wf = raw * f
        growth = float(wf @ mu_arr) - 0.5 * float(wf @ sigma @ wf)
        cost = tc * float(np.abs(wf - cur).sum())
        grid.append({"kelly_fraction": float(f), "gross_growth": growth, "cost_drag": cost, "net_growth": growth - cost})
    best = max(grid, key=lambda r: r["net_growth"]) if grid else {"kelly_fraction": 0.0}
    return {"table": rows, "growth_curve": grid, "turnover_optimal_fraction": best["kelly_fraction"]}


def stress_scenarios(returns: pd.DataFrame, weights: pd.Series) -> dict[str, Any]:
    w = weights.reindex(returns.columns).fillna(0.0)
    port = portfolio_return_series(returns, w)
    if port.empty:
        return {"scenario_table": [], "waterfall": []}
    port_arr = port.to_numpy(dtype=np.float64)
    quantiles = {
        "covid_like_1pct": 0.01, "gfc_like_5pct": 0.05, "rate_shock_10pct": 0.10,
        "taper_tantrum_15pct": 0.15, "china_devaluation_2015": 0.025,
        "volmageddon_2018": 0.02, "trade_war_2019": 0.05, "svb_2023": 0.03,
        "rate_volatility_2024": 0.08, "liquidity_shock": 0.01,
    }
    table = []
    for name, q in quantiles.items():
        threshold = float(np.quantile(port_arr, q))
        mask = port_arr <= threshold
        loss = float(port_arr[mask].mean()) if mask.any() else threshold
        table.append({"scenario": name, "portfolio_return": loss, "pl_bps": loss * 10000})
    worst_date = port.idxmin()
    w_arr = w.to_numpy(dtype=np.float64)
    worst_row = returns.loc[worst_date].reindex(weights.index).fillna(0.0).to_numpy(dtype=np.float64)
    comp = worst_row * w_arr
    order = np.argsort(comp)[:20]
    waterfall = [{"component": str(weights.index[i]), "value": float(comp[i])} for i in order]
    return {"scenario_table": table, "waterfall": waterfall}


def stationary_block_bootstrap_paths(series: pd.Series, paths: int, horizon: int, block_length: int | None = None, seed: int = 7) -> np.ndarray:
    """Politis-Romano stationary bootstrap preserving short-run dependence."""
    values = series.dropna().to_numpy(dtype=float)
    if values.size == 0:
        return np.zeros((max(paths, 1), max(horizon, 1)))
    length = int(block_length or politis_romano_block(pd.Series(values)))
    restart_probability = 1.0 / max(length, 1)
    rng = np.random.default_rng(seed)
    out = np.empty((paths, horizon), dtype=float)
    for p in range(paths):
        idx = int(rng.integers(values.size))
        for t in range(horizon):
            out[p, t] = values[idx]
            idx = int(rng.integers(values.size)) if rng.random() < restart_probability else (idx + 1) % values.size
    return out


def minimum_mahalanobis_reverse_stress(returns: pd.DataFrame, weights: pd.Series, loss_threshold: float) -> dict[str, Any]:
    """Closest factor/asset return vector causing a target portfolio loss."""
    mu = returns.mean().fillna(0.0).to_numpy(dtype=float)
    cov = nearest_psd(returns.cov().fillna(0.0).to_numpy(dtype=float))
    w = weights.reindex(returns.columns).fillna(0.0).to_numpy(dtype=float)
    denom = float(w @ cov @ w)
    target = -abs(float(loss_threshold))
    if denom <= 1e-14:
        shock = np.repeat(target / max(len(w), 1), len(w))
    else:
        # Projection of mu onto {r: w'r=target} under covariance metric.
        shock = mu + cov @ w * ((target - float(w @ mu)) / denom)
    distance = float((shock - mu) @ fast_pinv(cov + np.eye(len(w)) * 1e-10) @ (shock - mu))
    return {"target_loss": target, "portfolio_loss": float(w @ shock), "mahalanobis_distance": distance, "asset_shocks": [{"ticker": c, "return": float(v)} for c, v in zip(returns.columns, shock)]}


def execution_costs(symbols: list[str], weights_current: pd.Series, weights_target: pd.Series, nav: float = 1_000_000.0, horizon_days: int = 5, risk_aversion: float = 0.1) -> dict[str, Any]:
    liq = pd.DataFrame(liquidity_table(symbols, 252, nav, weights_target - weights_current))
    if liq.empty:
        return {"schedule": [], "cost_table": []}
    rows, schedule = [], []
    tickers = liq["ticker"].astype(str).to_numpy()
    trades = liq["position_dollars"].to_numpy(dtype=np.float64, copy=False)
    advs = np.maximum(liq["adv_dollars"].to_numpy(dtype=np.float64, copy=False), 1.0)
    sigmas = np.clip(liq.get("liquidity_var_bps", pd.Series(20.0, index=liq.index)).to_numpy(dtype=np.float64, copy=False) / 10000, 0.005, 0.10)
    for ticker, trade, adv, sigma in zip(tickers, trades, advs, sigmas):
        impact_bps = 10000 * sigma * math.sqrt(abs(trade) / adv)
        timing_bps = 10000 * sigma * math.sqrt(max(horizon_days, 1) / 252) * risk_aversion
        total_bps = impact_bps + timing_bps
        rows.append({"ticker": ticker, "trade_dollars": float(trade), "adv_dollars": float(adv), "market_impact_bps": float(impact_bps), "timing_risk_bps": float(timing_bps), "expected_is_bps": float(total_bps), "expected_is_dollars": float(total_bps / 10000 * abs(trade))})
        for day in range(1, horizon_days + 1):
            schedule.append({"ticker": ticker, "day": day, "trade_dollars": float(trade / horizon_days), "remaining_dollars": float(trade * (1 - day / horizon_days)), "expected_impact_bps": float(impact_bps / horizon_days)})
    frontier = [{"risk_aversion": float(lam), "expected_cost_bps": float(np.mean([r["market_impact_bps"] for r in rows]) + lam * np.mean([r["timing_risk_bps"] for r in rows])), "risk_bps": float(lam * np.std([r["timing_risk_bps"] for r in rows]))} for lam in np.linspace(0, 1, 25)]
    return {"schedule": schedule, "cost_table": rows, "frontier": frontier}


def network_edges(returns: pd.DataFrame, threshold: float = 0.45) -> list[dict[str, Any]]:
    edges = fast_network_edges_from_corr(cached_correlation_frame(returns), threshold=threshold, max_edges=500)
    return [{"source": e["source"], "target": e["target"], "weight": e["correlation"]} for e in edges]


def mantegna_mst(corr: pd.DataFrame) -> list[dict[str, Any]]:
    """Minimum spanning tree under Mantegna correlation distance."""
    cols = list(corr.columns)
    if len(cols) < 2:
        return []
    c = np.clip(corr.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float), -1, 1)
    distance = np.sqrt(np.maximum(2.0 * (1.0 - c), 0.0))
    visited = {0}
    edges: list[dict[str, Any]] = []
    while len(visited) < len(cols):
        best = None
        for i in visited:
            for j in range(len(cols)):
                if j in visited or i == j:
                    continue
                candidate = (distance[i, j], i, j)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            break
        d, i, j = best
        visited.add(j)
        edges.append({"source": cols[i], "target": cols[j], "distance": float(d), "correlation": float(c[i, j])})
    return edges


def correlation_hierarchy(corr: pd.DataFrame) -> list[dict[str, Any]]:
    cols = list(corr.columns)
    if len(cols) < 2:
        return []
    c = np.clip(corr.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float), -1, 1)
    z = linkage(squareform(np.sqrt(np.maximum(2.0 * (1.0 - c), 0.0)), checks=False), method="average")
    return [{"left": int(row[0]), "right": int(row[1]), "distance": float(row[2]), "count": int(row[3])} for row in z]


def black_litterman(cov: pd.DataFrame, market_weights: pd.Series, views: dict[str, float] | None = None, tau: float = 0.05, risk_aversion: float = 2.5) -> dict[str, Any]:
    cols = list(cov.columns)
    sigma = cov.reindex(index=cols, columns=cols).fillna(0.0).to_numpy(dtype=float)
    w = market_weights.reindex(cols).fillna(0.0).to_numpy(dtype=float)
    if np.abs(w).sum() <= 1e-12:
        w = np.repeat(1 / max(len(cols), 1), len(cols))
    pi = risk_aversion * sigma @ w
    if not views:
        return {"posterior_mu": pd.Series(pi, index=cols), "posterior_cov": cov, "view_count": 0}
    rows, q = [], []
    for key, value in views.items():
        if key not in cols or number_like(value) is None:
            continue
        row = np.zeros(len(cols))
        row[cols.index(key)] = 1.0
        rows.append(row)
        q.append(float(value))
    if not rows:
        return {"posterior_mu": pd.Series(pi, index=cols), "posterior_cov": cov, "view_count": 0}
    P = np.vstack(rows)
    Q = np.asarray(q)
    omega = np.diag(np.maximum(np.diag(P @ (tau * sigma) @ P.T), 1e-8))
    tau_inv = fast_pinv(tau * sigma)
    omega_inv = fast_pinv(omega)
    middle = fast_pinv(tau_inv + P.T @ omega_inv @ P)
    mu_bl = middle @ (tau_inv @ pi + P.T @ omega_inv @ Q)
    cov_bl = sigma + middle
    return {"posterior_mu": pd.Series(mu_bl, index=cols), "posterior_cov": pd.DataFrame(cov_bl, index=cols, columns=cols), "view_count": len(rows)}


def cvar_minimize(returns: pd.DataFrame, alpha: float = 0.95, target_return: float | None = None) -> pd.Series:
    key = f"{dataframe_fingerprint(returns)}:{alpha}:{target_return}"

    def build() -> pd.Series:
        x = returns.fillna(0.0).to_numpy(dtype=float, copy=False)
        n_obs, n = x.shape
        if n == 0:
            return pd.Series(dtype=float)
        # Rockafellar-Uryasev LP: min eta + 1/((1-alpha)T) sum u_t.
        c = np.zeros(n + 1 + n_obs, dtype=np.float64)
        c[n] = 1.0
        c[n + 1:] = 1 / ((1 - alpha) * max(n_obs, 1))
        extra = 1 if target_return is not None else 0
        A_ub = np.zeros((n_obs + extra, n + 1 + n_obs), dtype=np.float64)
        A_ub[:n_obs, :n] = -x
        A_ub[:n_obs, n] = -1.0
        A_ub[np.arange(n_obs), n + 1 + np.arange(n_obs)] = -1.0
        b_ub = np.zeros(n_obs + extra, dtype=np.float64)
        if target_return is not None:
            A_ub[-1, :n] = -returns.mean().to_numpy(dtype=np.float64)
            b_ub[-1] = -float(target_return)
        A_eq = np.zeros((1, n + 1 + n_obs), dtype=np.float64)
        A_eq[0, :n] = 1.0
        bounds = [(0, 1)] * n + [(None, None)] + [(0, None)] * n_obs
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=np.array([1.0]), bounds=bounds, method="highs")
        w = res.x[:n] if res.success else np.repeat(1 / n, n)
        return pd.Series(w, index=returns.columns)

    return cached_result("cvar_minimize", key, build).copy()


def min_cvar_target(returns: pd.DataFrame, target: float) -> pd.Series:
    return cvar_minimize(returns, target_return=target)


@nb.njit(cache=True, fastmath=True)
def _jit_dcc_loop(z_arr: np.ndarray, vol_arr: np.ndarray, qbar: np.ndarray, alpha: float, beta: float):
    """JIT-compiled DCC inner loop — eliminates all per-step Python allocations."""
    T = z_arr.shape[0]
    nc = z_arr.shape[1]
    one_minus = 1.0 - alpha - beta
    q = qbar.copy()
    cov_last = np.empty((nc, nc))
    avg_corrs = np.empty(T)
    d = np.empty(nc)
    corr = np.empty((nc, nc))
    for i in range(T):
        zi = z_arr[i]
        for a in range(nc):
            for b in range(nc):
                q[a, b] = beta * q[a, b] + alpha * zi[a] * zi[b] + one_minus * qbar[a, b]
        for a in range(nc):
            v = q[a, a]
            d[a] = math.sqrt(v if v > 1e-12 else 1e-12)
        for a in range(nc):
            for b in range(nc):
                corr[a, b] = q[a, b] / (d[a] * d[b])
        vi = vol_arr[i]
        for a in range(nc):
            for b in range(nc):
                cov_last[a, b] = corr[a, b] * vi[a] * vi[b]
        upper_sum = 0.0
        upper_n = 0
        for a in range(nc):
            for b in range(a + 1, nc):
                upper_sum += corr[a, b]
                upper_n += 1
        avg_corrs[i] = upper_sum / max(upper_n, 1)
    return cov_last, avg_corrs


def dcc_garch_cov(returns: pd.DataFrame, alpha: float = 0.03, beta: float = 0.94) -> dict[str, Any]:
    """Fast two-stage DCC-style covariance using EWMA vol and JIT DCC recursion."""
    r = returns.fillna(0.0)
    if r.empty:
        return {"covariance": pd.DataFrame(), "average_correlation_series": []}
    vols = r.ewm(alpha=1 - beta, adjust=False).std().replace(0, np.nan).bfill().fillna(r.std())
    z = (r / vols).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    z_arr = np.ascontiguousarray(z.to_numpy(dtype=np.float64))
    vol_arr = np.ascontiguousarray(vols.to_numpy(dtype=np.float64))
    qbar = np.ascontiguousarray(z.cov().to_numpy(dtype=np.float64))
    cov_last, avg_corrs = _jit_dcc_loop(z_arr, vol_arr, qbar, alpha, beta)
    dates = z.index
    avg = [{"date": str(pd.Timestamp(dates[i]).date()), "avg_correlation": float(avg_corrs[i])} for i in range(len(z_arr))]
    return {"covariance": pd.DataFrame(cov_last, index=r.columns, columns=r.columns), "average_correlation_series": avg}


def gerber_statistic_cov(returns: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    r = returns.fillna(0.0)
    sigma = r.std().replace(0, np.nan).fillna(1.0).to_numpy(dtype=np.float64)
    arr = r.to_numpy(dtype=np.float64)
    thresh = threshold * sigma
    above = arr > thresh[None, :]
    below = arr < -thresh[None, :]
    signs = above.astype(np.float64) - below.astype(np.float64)
    norms = np.sqrt(np.einsum("ij,ij->j", signs, signs))
    norms[norms < 1e-12] = 1.0
    signs_n = signs / norms
    g = signs_n.T @ signs_n
    np.clip(g, -1.0, 1.0, out=g)
    np.fill_diagonal(g, 1.0)
    vol = r.std().fillna(0.0).to_numpy(dtype=np.float64)
    return pd.DataFrame(g * np.outer(vol, vol), index=r.columns, columns=r.columns)


def factor_structured_cov(returns: pd.DataFrame, factors: pd.DataFrame | None = None) -> pd.DataFrame:
    r = returns.fillna(0.0)
    if factors is None or factors.empty:
        # Use first PCs as observable factor structure when FF data is not loaded here.
        u, s, vt = np.linalg.svd(r.to_numpy(dtype=float), full_matrices=False)
        k = min(5, vt.shape[0])
        f = pd.DataFrame(u[:, :k] * s[:k], index=r.index)
    else:
        f = factors.reindex(r.index).fillna(0.0)
    X = np.c_[np.ones(len(f)), f.to_numpy(dtype=float)]
    betas = fast_pinv(X) @ r.to_numpy(dtype=float)
    fitted = X @ betas
    resid = r.to_numpy(dtype=float) - fitted
    fcov = np.cov(f.to_numpy(dtype=float), rowvar=False)
    b = betas[1:, :].T
    structured = b @ np.atleast_2d(fcov) @ b.T + np.diag(np.var(resid, axis=0))
    return pd.DataFrame(structured, index=r.columns, columns=r.columns)


def black_litterman_weights(returns: pd.DataFrame, market_weights: pd.Series, views: dict[str, float] | None = None) -> pd.Series:
    cov, _ = covariance_matrix(returns, "ledoit_wolf")
    bl = black_litterman(cov * 252.0, market_weights, views)
    sigma = bl["posterior_cov"].to_numpy(dtype=np.float64, copy=False) + np.eye(len(cov)) * 1e-9
    raw = fast_solve(sigma, bl["posterior_mu"].to_numpy(dtype=np.float64, copy=False))
    raw = np.clip(raw, 0, None)
    raw = raw / max(raw.sum(), 1e-12)
    return pd.Series(raw, index=cov.columns)


def weight_stability_index(weight_history: pd.DataFrame) -> float:
    if weight_history is None or weight_history.empty:
        return 0.0
    return float(weight_history.std().mean())


def pbo_cscv(strategy_returns: pd.DataFrame, n_splits: int = 8, max_combinations: int = 5_000) -> dict[str, Any]:
    """Combinatorially symmetric cross-validation with bounded enumeration.

    Every admissible half-sample is evaluated when feasible.  For larger
    partitions a deterministic sample prevents an exponential request from
    blocking a realtime feature run.
    """
    if strategy_returns.empty or strategy_returns.shape[1] < 2:
        return {"pbo": None, "distribution": []}
    from itertools import combinations
    chunks = np.array_split(strategy_returns, min(max(2, n_splits), len(strategy_returns)))
    half = len(chunks) // 2
    combinations_all = list(combinations(range(len(chunks)), half))
    if len(combinations_all) > max_combinations:
        rng = np.random.default_rng(7)
        selected = rng.choice(len(combinations_all), size=max_combinations, replace=False)
        combinations_all = [combinations_all[int(i)] for i in np.sort(selected)]
    rows, logits = [], []
    for i, train_idx in enumerate(combinations_all):
        train_set = set(train_idx)
        train = pd.concat([chunks[j] for j in train_idx])
        test = pd.concat([chunks[j] for j in range(len(chunks)) if j not in train_set])
        tr = train.mean() / train.std().replace(0, np.nan)
        te = test.mean() / test.std().replace(0, np.nan)
        winner = tr.idxmax()
        rank = te.rank(pct=True).get(winner, 0.5)
        logit = math.log(max(rank, 1e-6) / max(1 - rank, 1e-6))
        logits.append(logit)
        rows.append({"combination": i + 1, "train_blocks": list(train_idx), "train_winner": winner, "test_percentile": float(rank), "logit": float(logit)})
    return {"pbo": float(np.mean(np.asarray(logits) < 0)), "distribution": rows, "combination_count": len(rows), "partition_count": len(chunks)}


def value_at_risk_methods(series: pd.Series, confidence: float = 0.95, simulations: int = 10_000) -> list[dict[str, float | str]]:
    r = series.dropna().to_numpy(dtype=float)
    if not len(r):
        return []
    alpha = 1.0 - float(confidence)
    historical = float(np.quantile(r, alpha))
    hs_tail = r[r <= historical]
    mu, sigma = float(r.mean()), float(r.std(ddof=1))
    parametric = float(stats.norm.ppf(alpha, loc=mu, scale=max(sigma, 1e-12)))
    rng = np.random.default_rng(19)
    simulated = rng.normal(mu, sigma, min(max(int(simulations), 1000), 50_000))
    mc = float(np.quantile(simulated, alpha))
    return [
        {"method": "historical", "var": historical, "cvar": float(hs_tail.mean()) if len(hs_tail) else historical},
        {"method": "parametric_normal", "var": parametric, "cvar": float(mu - sigma * stats.norm.pdf(stats.norm.ppf(alpha)) / alpha)},
        {"method": "monte_carlo_normal", "var": mc, "cvar": float(simulated[simulated <= mc].mean())},
    ]


def deflated_sharpe_ratio(sharpe: float, n_obs: int, trials: int, skew: float = 0.0, excess_kurtosis: float = 0.0) -> float:
    """Bailey-Lopez de Prado DSR probability against the expected max null SR."""
    if n_obs < 2:
        return 0.0
    trials = max(int(trials), 1)
    emax = stats.norm.ppf(1.0 - 1.0 / trials) * math.sqrt(1.0 / max(n_obs - 1, 1)) if trials > 1 else 0.0
    variance = max((1.0 - skew * sharpe + excess_kurtosis * sharpe * sharpe / 4.0) / max(n_obs - 1, 1), 1e-12)
    return float(stats.norm.cdf((sharpe - emax) / math.sqrt(variance)))


def min_track_record_length(sharpe: float, benchmark_sr: float = 0.0, alpha: float = 0.05, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    z = stats.norm.ppf(1 - alpha)
    denom = max((sharpe - benchmark_sr) ** 2, 1e-8)
    adj = max(1e-8, 1 - skew * sharpe + (kurtosis - 1) * sharpe * sharpe / 4)
    return float(1 + adj * z * z / denom)


def harvey_liu_correction(sharpe: float, trials: int = 1, alpha: float = 0.05) -> dict[str, float]:
    adjusted_alpha = 1 - (1 - alpha) ** (1 / max(trials, 1))
    threshold = float(stats.norm.ppf(1 - adjusted_alpha))
    return {"adjusted_alpha": adjusted_alpha, "z_threshold": threshold, "passes": float(abs(sharpe) > threshold)}


def omega_ratio(returns: pd.Series, threshold: float = 0.0) -> float:
    r = returns.dropna() - threshold
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    return float(gains / max(losses, 1e-12))


def ulcer_index(returns: pd.Series) -> float:
    eq = (1 + returns.dropna()).cumprod()
    dd = eq / eq.cummax() - 1
    return float(np.sqrt(np.mean(np.square(dd))))


def calmar_ratio(returns: pd.Series, ann: float = 252.0) -> float:
    m = performance_metrics(returns, ann)
    return float(m.get("annual_return", 0.0) / max(abs(m.get("max_drawdown", 0.0)), 1e-12))


def up_down_capture(portfolio: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    joined = pd.concat([portfolio.rename("p"), benchmark.rename("b")], axis=1).dropna()
    up = joined[joined["b"] > 0]
    down = joined[joined["b"] < 0]
    return {
        "up_capture": float(up["p"].mean() / max(up["b"].mean(), 1e-12)) if not up.empty else 0.0,
        "down_capture": float(down["p"].mean() / min(down["b"].mean(), -1e-12)) if not down.empty else 0.0,
    }


def politis_romano_block(returns: pd.Series) -> int:
    r = returns.dropna()
    if len(r) < 20:
        return max(1, len(r))
    ac1 = abs(float(r.autocorr(1))) if pd.notna(r.autocorr(1)) else 0.0
    return int(max(2, min(len(r) // 3, round(1.5 * (len(r) ** (1 / 3)) * (1 + ac1)))))


def carino_link(period_effects: pd.Series, portfolio_returns: pd.Series) -> pd.Series:
    rp = portfolio_returns.reindex(period_effects.index).fillna(0.0)
    total = float((1 + rp).prod() - 1)
    denom = float(np.log1p(rp).sum())
    k = np.log1p(total) / denom if abs(denom) > 1e-12 and total > -1 else 1.0
    return period_effects * k


def menchero_link(period_effects: pd.Series, portfolio_returns: pd.Series) -> pd.Series:
    rp = portfolio_returns.reindex(period_effects.index).fillna(0.0)
    adj = 1 + rp.cumsum() - rp.mean()
    return period_effects * adj / max(float(adj.mean()), 1e-12)


def grap_link(period_effects: pd.Series, portfolio_returns: pd.Series) -> pd.Series:
    wealth = (1 + portfolio_returns.reindex(period_effects.index).fillna(0.0)).cumprod()
    return period_effects * wealth.shift(1).fillna(1.0)


def brinson_fachler(returns: pd.DataFrame, portfolio_weights: pd.Series, benchmark_weights: pd.Series, groups: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    mean_ret = returns.mean()
    for group in sorted(set(groups.values())):
        names = [c for c in returns.columns if groups.get(c, "Unknown") == group]
        if not names:
            continue
        wp = portfolio_weights.reindex(names).fillna(0.0)
        wb = benchmark_weights.reindex(names).fillna(0.0)
        rp = float((wp * mean_ret.reindex(names)).sum() / max(wp.sum(), 1e-12))
        rb = float((wb * mean_ret.reindex(names)).sum() / max(wb.sum(), 1e-12))
        total_bench = float((benchmark_weights.reindex(returns.columns).fillna(0.0) * mean_ret).sum())
        rows.append({"group": group, "allocation": float((wp.sum() - wb.sum()) * (rb - total_bench)), "selection": float(wb.sum() * (rp - rb)), "interaction": float((wp.sum() - wb.sum()) * (rp - rb))})
    return clean_json(rows)


def risk_attribution_xsr(active_returns: pd.DataFrame, active_weights: pd.Series) -> list[dict[str, Any]]:
    cov = active_returns.cov()
    w = active_weights.reindex(active_returns.columns).fillna(0.0)
    te = math.sqrt(max(float(w @ cov @ w), 1e-12))
    mcte = cov @ w / te
    return [{"ticker": c, "mcte": float(mcte.get(c, 0.0)), "component_te": float(w.get(c, 0.0) * mcte.get(c, 0.0))} for c in active_returns.columns]


def skill_luck_bootstrap(returns: pd.Series, draws: int = 2000) -> dict[str, Any]:
    r = returns.dropna().to_numpy(dtype=float)
    if len(r) < 30:
        return {"p_value": None, "null_distribution": []}
    rng = np.random.default_rng(7)
    obs = float(np.mean(r) / max(np.std(r), 1e-12))
    centered = r - r.mean()
    n_draws = min(int(draws), 10000)
    idx = rng.integers(0, len(centered), size=(n_draws, len(centered)))
    samples = centered[idx]
    boot_arr = samples.mean(axis=1) / np.maximum(samples.std(axis=1), 1e-12)
    boot = boot_arr.tolist()
    return {"observed_t": obs, "p_value": float(np.mean(np.abs(boot) >= abs(obs))), "null_distribution": [{"sample": i, "t": v} for i, v in enumerate(boot[:500])]}


def drawdown_attribution(returns: pd.DataFrame, weights: pd.Series, top_n: int = 5) -> list[dict[str, Any]]:
    port = portfolio_return_series(returns, weights)
    eq = (1 + port).cumprod()
    dd = eq / eq.cummax() - 1
    if dd.empty:
        return []
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    window = returns.loc[peak:trough]
    contrib = (window * weights.reindex(returns.columns).fillna(0.0)).sum().sort_values()
    return [{"ticker": k, "drawdown_contribution": float(v), "episode_start": str(pd.Timestamp(peak).date()), "episode_trough": str(pd.Timestamp(trough).date())} for k, v in contrib.head(top_n).items()]


def historical_crisis_replay(returns: pd.DataFrame, weights: pd.Series) -> list[dict[str, Any]]:
    scenarios = {"gfc_2008": ("2008-09-01", "2009-03-31"), "covid_2020": ("2020-02-15", "2020-04-30"), "rate_shock_2022": ("2022-01-01", "2022-10-31"), "svb_2023": ("2023-03-01", "2023-03-31")}
    out = []
    port = portfolio_return_series(returns, weights)
    for name, (a, b) in scenarios.items():
        s = port.loc[(port.index >= a) & (port.index <= b)]
        if not s.empty:
            out.append({"scenario": name, "return": float((1 + s).prod() - 1), "worst_day": float(s.min())})
    return out


def reverse_stress_test(returns: pd.DataFrame, weights: pd.Series, loss_threshold: float = 0.15) -> dict[str, Any]:
    cov = returns.cov().to_numpy(dtype=float)
    w = weights.reindex(returns.columns).fillna(0.0).to_numpy(dtype=float)
    sigma = math.sqrt(max(float(w @ cov @ w), 1e-12))
    shock = -abs(loss_threshold) * (cov @ w) / max(float(w @ cov @ w), 1e-12)
    d2 = float(shock @ fast_pinv(cov + np.eye(len(cov)) * 1e-9) @ shock)
    return {"loss_threshold": -abs(loss_threshold), "mahalanobis_distance": math.sqrt(max(d2, 0.0)), "plausibility_percentile": float(stats.chi2.cdf(d2, max(len(w), 1))), "shock_vector": [{"ticker": c, "shock": float(v)} for c, v in zip(returns.columns, shock)]}


def correlation_breakdown_stress(returns: pd.DataFrame, weights: pd.Series, crisis_corr: float = 0.75) -> dict[str, float]:
    vols = returns.std().to_numpy(dtype=float)
    corr = np.full((len(vols), len(vols)), crisis_corr)
    np.fill_diagonal(corr, 1.0)
    cov = corr * np.outer(vols, vols)
    w = weights.reindex(returns.columns).fillna(0.0).to_numpy(dtype=float)
    return {"stressed_vol": float(math.sqrt(max(w @ cov @ w, 0.0))), "crisis_corr": crisis_corr}


def newey_west_regression(y: pd.Series, x: pd.DataFrame, lags: int = 4) -> dict[str, Any]:
    df = pd.concat([y.rename("y"), x], axis=1).dropna()
    if len(df) <= x.shape[1] + 2:
        return {"coefficients": [], "r2": 0.0}
    X = np.c_[np.ones(len(df)), df[x.columns].to_numpy(dtype=float)]
    Y = df["y"].to_numpy(dtype=float)
    beta = fast_pinv(X) @ Y
    resid = Y - X @ beta
    xtx_inv = fast_pinv(X.T @ X)
    S = (X * (resid ** 2)[:, None]).T @ X
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        gamma = (X[lag:] * (resid[lag:] * resid[:-lag])[:, None]).T @ X[:-lag]
        S += weight * (gamma + gamma.T)
    cov = xtx_inv @ S @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    ssr = float((resid ** 2).sum())
    tss = float(((Y - Y.mean()) ** 2).sum())
    rows = [{"factor": "intercept", "beta": float(beta[0]), "se": float(se[0]), "t": float(beta[0] / se[0])}]
    rows += [{"factor": c, "beta": float(beta[i + 1]), "se": float(se[i + 1]), "t": float(beta[i + 1] / se[i + 1])} for i, c in enumerate(x.columns)]
    return {"coefficients": rows, "r2": 1 - ssr / max(tss, 1e-12)}


def mcte_per_position(returns: pd.DataFrame, weights: pd.Series) -> list[dict[str, Any]]:
    return risk_attribution_xsr(returns, weights)


def implied_alpha_required(mcte_rows: list[dict[str, Any]], hurdle_ir: float = 0.5) -> list[dict[str, Any]]:
    return [{"ticker": r["ticker"], "required_alpha": abs(float(r.get("mcte", 0.0))) * hurdle_ir} for r in mcte_rows]


def factor_crowding_rank(loadings: pd.Series) -> list[dict[str, Any]]:
    pct = loadings.rank(pct=True)
    return [{"ticker": k, "loading": float(loadings[k]), "crowding_rank": float(pct[k])} for k in loadings.index]


def factor_risk_budget(exposures: pd.DataFrame, returns: pd.DataFrame) -> list[dict[str, Any]]:
    if exposures.empty:
        return []
    totals = exposures.abs().sum()
    denom = max(float(totals.sum()), 1e-12)
    return [{"factor": c, "risk_budget": float(v / denom)} for c, v in totals.items()]


def hmm_regime_fit(features: pd.DataFrame, n_regimes: int = 3) -> pd.DataFrame:
    if GaussianHMM is not None and len(features) >= max(50, n_regimes * 20):
        x = StandardScaler().fit_transform(features.fillna(0.0).to_numpy(dtype=np.float64, copy=False))
        hmm = GaussianHMM(n_components=n_regimes, covariance_type="diag", min_covar=1e-6, n_iter=200, random_state=17).fit(x)
        labels = hmm.predict(x)
    elif GaussianMixture is None or len(features) < 50:
        labels = pd.qcut(features.iloc[:, 0].rank(method="first"), min(n_regimes, len(features)), labels=False, duplicates="drop")
    else:
        x = StandardScaler().fit_transform(features.fillna(0.0).to_numpy(dtype=np.float64, copy=False))
        labels = GaussianMixture(n_components=n_regimes, covariance_type="full", random_state=17).fit_predict(x)
    out = features.copy()
    out["regime"] = np.asarray(labels, dtype=int)
    return out


def nonhomogeneous_transition(regimes: pd.Series, drivers: pd.DataFrame) -> list[dict[str, Any]]:
    joined = pd.concat([regimes.rename("regime"), drivers], axis=1).dropna()
    if joined.empty:
        return []
    driver_score = joined.drop(columns=["regime"]).rank(pct=True).mean(axis=1)
    bucket = pd.qcut(driver_score.rank(method="first"), 3, labels=["low", "mid", "high"])
    rows = []
    for b in sorted(bucket.dropna().unique()):
        sub = joined.loc[bucket == b, "regime"]
        mat = pd.crosstab(sub.shift(1), sub, normalize="index").fillna(0.0)
        for i in mat.index:
            for j in mat.columns:
                rows.append({"driver_bucket": str(b), "from": int(i), "to": int(j), "probability": float(mat.loc[i, j])})
    return rows


def kaplan_meier_survival(regimes: pd.Series) -> list[dict[str, Any]]:
    rows = []
    values = regimes.dropna().to_numpy()
    for r in sorted(pd.unique(values)):
        mask = values == r
        padded = np.r_[False, mask, False]
        starts = np.flatnonzero(~padded[:-1] & padded[1:])
        ends = np.flatnonzero(padded[:-1] & ~padded[1:])
        runs = ends - starts
        if not len(runs):
            continue
        max_run = int(runs.max())
        durations = np.arange(1, max_run + 1)
        at_risk = (runs[:, None] >= durations).sum(axis=0)
        events = (runs[:, None] == durations).sum(axis=0)
        hazards = events / np.maximum(at_risk, 1)
        survival = np.cumprod(1.0 - hazards)
        rows.extend({"regime": int(r), "duration": int(t), "survival": float(s), "at_risk": int(a), "events": int(e)} for t, s, a, e in zip(durations, survival, at_risk, events))
    return rows


def regime_conditional_cov(returns: pd.DataFrame, regimes: pd.Series) -> dict[str, list[dict[str, Any]]]:
    out = {}
    aligned = regimes.reindex(returns.index).ffill()
    for r in sorted(aligned.dropna().unique()):
        out[str(int(r))] = matrix_records(returns[aligned == r].cov().fillna(0.0))
    return out


def regime_factor_performance(returns: pd.DataFrame, regimes: pd.Series) -> list[dict[str, Any]]:
    aligned = regimes.reindex(returns.index).ffill()
    rows = []
    for r in sorted(aligned.dropna().unique()):
        sub = returns[aligned == r]
        for c in returns.columns:
            rows.append({"regime": int(r), "factor": c, "mean": float(sub[c].mean()), "sharpe": float(sub[c].mean() / max(sub[c].std(), 1e-12))})
    return rows


def recency_weighted_amihud(ohlcv: pd.DataFrame) -> pd.Series:
    rows = {}
    for s, g in ohlcv.groupby("Ticker"):
        g = g.sort_values("Date")
        oc_ret = (g["Close"] / g["Open"].replace(0, np.nan) - 1).abs()
        dv = (g["Close"] * g["Volume"].fillna(0)).replace(0, np.nan)
        val = (oc_ret / dv).replace([np.inf, -np.inf], np.nan).dropna()
        if val.empty:
            rows[s] = np.nan
        else:
            w = np.linspace(1, 2, len(val))
            rows[s] = float(np.average(val, weights=w))
    return pd.Series(rows)


def liquidity_adjusted_var(var: float, spread_cost: float, gamma: float, position: float) -> float:
    return float(var + spread_cost + gamma * position * position)


def crisis_liquidation_cost(liq_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**r, "crisis_days_to_liquidate": float(r.get("days_to_liquidate_15pct_adv", 0.0)) / 0.30, "crisis_cost_bps": float(r.get("liquidity_var_bps", 0.0)) * 5} for r in liq_rows]


def liquidity_frontier(liq_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not liq_rows:
        return []
    rows = []
    for cap in [1, 3, 5, 10, 20, 40]:
        eligible = [r for r in liq_rows if float(r.get("days_to_liquidate_15pct_adv", 0.0)) <= cap]
        rows.append({"dtl_cap": cap, "eligible_count": len(eligible), "avg_liquidity_var_bps": float(np.mean([r.get("liquidity_var_bps", 0.0) for r in eligible])) if eligible else None})
    return rows


def liquidity_halflife(series: pd.Series) -> float | None:
    y = np.log(series.replace(0, np.nan).dropna())
    if len(y) < 10:
        return None
    x = np.arange(len(y))
    slope = np.polyfit(x, y, 1)[0]
    return float(np.log(0.5) / slope) if slope < 0 else None


def regulatory_classification(days_to_liquidate: float) -> str:
    if days_to_liquidate <= 3:
        return "highly_liquid"
    if days_to_liquidate <= 7:
        return "moderately_liquid"
    if days_to_liquidate <= 15:
        return "less_liquid"
    return "illiquid"


def precision_matrix_network(returns: pd.DataFrame, threshold: float = 0.05) -> list[dict[str, Any]]:
    cov, _ = covariance_matrix(returns, "ledoit_wolf")
    if cov.empty:
        return []
    theta = safe_inverse(cov.to_numpy(dtype=float))
    d = np.sqrt(np.maximum(np.diag(theta), 1e-12))
    partial = -theta / np.outer(d, d)
    np.fill_diagonal(partial, 1.0)
    partial_df = pd.DataFrame(partial, index=cov.columns, columns=cov.columns)
    edges = fast_network_edges_from_corr(partial_df, threshold=threshold, max_edges=500)
    return [{"source": e["source"], "target": e["target"], "partial_corr": e["correlation"]} for e in edges]


def leading_eigenvalue_series(returns: pd.DataFrame, window: int = 126) -> list[dict[str, Any]]:
    rows = rolling_leading_eigenvalue(returns, window=window, step=max(5, window // 12))
    return [{"date": str(pd.Timestamp(r["date"]).date()), "leading_eigenvalue_ratio": r["leading_eigenvalue_share"]} for r in rows]


def diversification_ratio_series(returns: pd.DataFrame, weights: pd.Series, window: int = 126) -> list[dict[str, Any]]:
    rows = rolling_diversification_ratio(returns, weights, window=window, step=max(5, window // 12))
    return [{"date": str(pd.Timestamp(r["date"]).date()), "diversification_ratio": r["diversification_ratio"]} for r in rows]


def chow_test_breakpoints(series: pd.Series, min_window: int = 63) -> list[dict[str, Any]]:
    y = series.dropna()
    rows = []
    if len(y) < min_window * 3:
        return rows
    x = np.arange(len(y))
    full = np.polyfit(x, y, 1)
    rss_full = float(((y - np.polyval(full, x)) ** 2).sum())
    for bp in range(min_window, len(y) - min_window, min_window):
        left = np.polyfit(x[:bp], y.iloc[:bp], 1)
        right = np.polyfit(x[bp:], y.iloc[bp:], 1)
        rss = float(((y.iloc[:bp] - np.polyval(left, x[:bp])) ** 2).sum() + ((y.iloc[bp:] - np.polyval(right, x[bp:])) ** 2).sum())
        f = ((rss_full - rss) / 2) / max(rss / (len(y) - 4), 1e-12)
        rows.append({"date": str(pd.Timestamp(y.index[bp]).date()), "chow_f": f})
    return rows


def sector_block_analysis(returns: pd.DataFrame, sectors: dict[str, str]) -> list[dict[str, Any]]:
    corr = cached_correlation_frame(returns)
    rows = []
    groups = sorted(set(sectors.values()))
    for a in groups:
        ca = [c for c in returns.columns if sectors.get(c, "Unknown") == a]
        for b in groups:
            cb = [c for c in returns.columns if sectors.get(c, "Unknown") == b]
            if ca and cb:
                rows.append({"row": a, "col": b, "value": float(corr.loc[ca, cb].abs().mean().mean())})
    return rows


def marchenko_pastur_threshold(n_assets: int, n_obs: int, sigma2: float = 1.0) -> float:
    q = n_assets / max(n_obs, 1)
    return float(sigma2 * (1 + math.sqrt(q)) ** 2)


def ic_decay_curve(returns: pd.DataFrame, max_horizon: int = 63) -> list[dict[str, Any]]:
    return alpha_decay(returns, max_horizon=max_horizon)["ic_curve"]


def hyperbolic_decay_fit(ic_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not ic_rows:
        return {"K": None, "lambda": None, "aic": None}
    h = np.array([r["horizon"] for r in ic_rows], dtype=float)
    y = np.abs(np.array([r["ic"] for r in ic_rows], dtype=float))
    def obj(p):
        K, lam = p
        pred = K / (1 + lam * h)
        return float(((y - pred) ** 2).sum())
    res = minimize(obj, [max(y[0], 1e-4), 0.05], bounds=[(0, 1), (1e-6, 10)])
    rss = max(res.fun, 1e-12)
    return {"K": float(res.x[0]), "lambda": float(res.x[1]), "aic": float(len(y) * math.log(rss / len(y)) + 2 * 2)}


def decay_model_selection(ic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fit exponential, hyperbolic and stretched-exponential IC decay models."""
    if len(ic_rows) < 4:
        return []
    h = np.asarray([r["horizon"] for r in ic_rows], dtype=float)
    y = np.abs(np.asarray([r["ic"] for r in ic_rows], dtype=float))
    y = np.maximum(y, 1e-10)
    candidates = []
    models = {
        "exponential": (lambda p: p[0] * np.exp(-h / max(p[1], 1e-9)), [y[0], max(np.median(h), 1.0)]),
        "hyperbolic": (lambda p: p[0] / (1.0 + h / max(p[1], 1e-9)), [y[0], max(np.median(h), 1.0)]),
        "stretched_exponential": (lambda p: p[0] * np.exp(-np.power(h / max(p[1], 1e-9), max(p[2], .05))), [y[0], max(np.median(h), 1.0), 0.8]),
    }
    for name, (func, init) in models.items():
        result = minimize(lambda p: float(np.square(y - func(p)).sum()), init, bounds=[(1e-12, None)] * len(init), method="L-BFGS-B")
        if result.success:
            rss = max(float(result.fun), 1e-18)
            candidates.append({"model": name, "parameters": [float(v) for v in result.x], "aic": float(len(y) * math.log(rss / len(y)) + 2 * len(init)), "rss": rss})
    return sorted(candidates, key=lambda row: row["aic"])


def optimal_rebalance_frequency(ic_rows: list[dict[str, Any]], tc_bps: float = 10.0) -> dict[str, Any]:
    best = None
    for r in ic_rows:
        h = max(float(r["horizon"]), 1.0)
        net = float(abs(r["ic"]) / h - 2 * tc_bps / 10000 / h)
        row = {"horizon": h, "net_alpha_per_day": net}
        if best is None or net > best["net_alpha_per_day"]:
            best = row
    return best or {"horizon": None, "net_alpha_per_day": None}


def alpha_capacity(ic: float, sigma: float, kyle_lambda: float) -> float:
    return float(abs(ic) * sigma / max(2 * kyle_lambda, 1e-12))


def post_publication_chow(ic_series: pd.Series, publication_date: Any) -> dict[str, Any]:
    y = ic_series.dropna()
    pub = pd.Timestamp(publication_date)
    pre, post = y[y.index < pub], y[y.index >= pub]
    if len(pre) < 10 or len(post) < 10:
        return {"status": "insufficient_data"}
    diff = float(pre.mean() - post.mean())
    se = math.sqrt(pre.var() / len(pre) + post.var() / len(post))
    return {"pre_mean": float(pre.mean()), "post_mean": float(post.mean()), "t": diff / max(se, 1e-12)}


def decay_adjusted_weights(weights: pd.Series, ic_rows: list[dict[str, Any]], half_life: int | None) -> list[dict[str, Any]]:
    base = max(abs(ic_rows[0]["ic"]), 1e-12) if ic_rows else 1.0
    rows = []
    for age in range(0, 126, 7):
        ic = next((abs(r["ic"]) for r in ic_rows if r["horizon"] >= max(age, 1)), abs(ic_rows[-1]["ic"]) if ic_rows else base)
        scale = ic / base * math.exp(-age / max(float(half_life or 63), 1.0))
        rows.append({"age_days": age, "weight_scale": float(scale)})
    return rows


def drawdown_constrained_leverage(mu: float, sigma: float, threshold: float) -> float:
    if mu <= 0 or sigma <= 0:
        return 0.25
    return float(min(5.0, max(0.0, math.exp(-2 * mu * threshold / max(sigma * sigma, 1e-12)))))


def geometric_growth_rate(weights: pd.Series | np.ndarray, mu: pd.Series | np.ndarray, cov: pd.DataFrame | np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    m = np.asarray(mu, dtype=float)
    c = np.asarray(cov, dtype=float)
    return float(w @ m - 0.5 * w @ c @ w)


def ruin_probability_surface(mu_values: Iterable[float], sigma_values: Iterable[float], leverage_values: Iterable[float], capital: float = 1.0) -> list[dict[str, Any]]:
    rows = []
    for mu in mu_values:
        for sigma in sigma_values:
            for lev in leverage_values:
                p = math.exp(-2 * max(mu, 1e-9) * capital / max(sigma * sigma * lev * lev, 1e-12))
                rows.append({"mu": float(mu), "sigma": float(sigma), "leverage": float(lev), "ruin_probability": float(min(1, max(0, p)))})
    return rows


def signal_decay_sizing(weights: pd.Series, decay_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"ticker": t, "age_days": d["age_days"], "scaled_weight": float(w * d["weight_scale"])} for t, w in weights.items() for d in decay_rows]


def effective_kelly_fraction(g_constrained: float, g_unconstrained: float) -> float:
    return float(g_constrained / max(g_unconstrained, 1e-12))


def turnover_optimal_kelly(mu: pd.Series, cov: pd.DataFrame, current: pd.Series, tc_bps: float = 10.0) -> dict[str, Any]:
    base = kelly_sizing(mu, cov, current, 1.0, 1.0, tc_bps)
    best = max(base["growth_curve"], key=lambda r: r["net_growth"]) if base["growth_curve"] else {}
    return {"best_fraction": best.get("kelly_fraction"), "curve": base["growth_curve"]}


def almgren_chriss_trajectory(x0: float, sigma: float, eta: float, risk_aversion: float, horizon: int) -> list[dict[str, Any]]:
    T = max(int(horizon), 1)
    if risk_aversion <= 0 or eta <= 0:
        return [{"day": t, "remaining": float(x0 * (1 - t / T)), "trade": float(x0 / T)} for t in range(T + 1)]
    kappa = math.sqrt(max(risk_aversion * sigma * sigma / eta, 1e-12))
    denom = math.sinh(kappa * T)
    rows = []
    prev = x0
    for t in range(T + 1):
        rem = x0 * math.sinh(kappa * (T - t)) / max(denom, 1e-12)
        rows.append({"day": t, "remaining": float(rem), "trade": float(max(prev - rem, 0.0))})
        prev = rem
    return rows


def is_efficient_frontier(trade: float, sigma: float, eta: float) -> list[dict[str, Any]]:
    rows = []
    for lam in np.linspace(0, 1, 31):
        impact = eta * trade * trade
        risk = sigma * abs(trade) * math.sqrt(lam + 1e-9)
        rows.append({"risk_aversion": float(lam), "expected_is": float(impact + lam * risk), "is_vol": float(risk)})
    return rows


def is_decomposition(trade: float, impact_bps: float, timing_bps: float, opportunity_bps: float = 0.0) -> dict[str, float]:
    return {"delay_cost_bps": 0.0, "permanent_impact_bps": float(impact_bps * 0.35), "temporary_impact_bps": float(impact_bps * 0.65), "timing_risk_bps": float(timing_bps), "opportunity_cost_bps": float(opportunity_bps)}


def signal_decay_urgency(alpha0: float, half_life: float, horizon: int) -> list[dict[str, Any]]:
    tau = max(half_life / math.log(2), 1e-12)
    return [{"day": d, "alpha_remaining": float(alpha0 * math.exp(-d / tau))} for d in range(max(int(horizon), 1) + 1)]


def volume_profile_trajectory(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    T = max(len(trajectory) - 1, 1)
    profile = np.array([0.7 + 1.2 * ((i / T) - 0.5) ** 2 for i in range(T + 1)])
    profile = profile / profile.mean()
    out = []
    for row, scale in zip(trajectory, profile):
        out.append({**row, "volume_adjusted_trade": float(row.get("trade", 0.0) * scale)})
    return out


def impact_calibration(adv: float, sigma: float) -> dict[str, float]:
    gamma = sigma / max(math.sqrt(max(adv, 1.0)), 1e-12)
    eta = sigma / max(adv, 1.0)
    return {"gamma": float(gamma), "eta": float(eta)}


def correlated_multiasset_is(trades: pd.Series, corr: pd.DataFrame, gamma: float = 0.1) -> float:
    c = corr.reindex(index=trades.index, columns=trades.index).fillna(0.0).to_numpy(dtype=float)
    t = trades.to_numpy(dtype=float)
    return float(gamma * t @ c @ t)


def portfolio_overlap_index(portfolios: dict[str, pd.Series]) -> pd.DataFrame:
    names = list(portfolios)
    mat = pd.DataFrame(index=names, columns=names, dtype=float)
    for a in names:
        for b in names:
            mat.loc[a, b] = float(pd.concat([portfolios[a], portfolios[b]], axis=1).fillna(0.0).min(axis=1).sum())
    return mat


def fire_sale_impact(peer_weights: pd.Series, portfolio_weights: pd.Series, adv: pd.Series, theta: float, nav: float, gamma: float = 0.10) -> pd.Series:
    impact = -gamma * (theta * nav * peer_weights.reindex(adv.index).fillna(0.0)) / adv.replace(0, np.nan).fillna(1.0)
    return portfolio_weights.reindex(impact.index).fillna(0.0) * impact


def debtrank_propagate(exposure: pd.DataFrame, initial_distress: pd.Series, damping: float = 0.85, max_iter: int = 100) -> pd.Series:
    h = initial_distress.reindex(exposure.index).fillna(0.0).astype(float)
    W = exposure.fillna(0.0).to_numpy(dtype=float)
    W = W / np.maximum(W.sum(axis=1, keepdims=True), 1e-12)
    base = h.to_numpy(dtype=np.float64, copy=False)
    v = base.copy()
    for _ in range(max_iter):
        nxt = np.clip(base + damping * W @ v, 0, 1)
        if np.max(np.abs(nxt - v)) < 1e-6:
            v = nxt
            break
        v = nxt
    return pd.Series(v, index=exposure.index)


@lru_cache(maxsize=16)
def _cascade_thresholds(n: int) -> np.ndarray:
    return np.random.default_rng(17).uniform(0, 1, min(int(n), 10000))


def cascade_probability(connectivity: float, leverage: float, shock: float, simulations: int = 2000) -> float:
    threshold = _cascade_thresholds(int(simulations))
    trigger = shock * leverage * connectivity
    return float(np.mean(trigger > threshold))


def systemic_risk_contribution(overlap: pd.DataFrame, losses: pd.Series) -> list[dict[str, Any]]:
    src = overlap.fillna(0.0).mul(losses.reindex(overlap.columns).fillna(0.0), axis=1).sum(axis=1)
    return [{"node": k, "src": float(v)} for k, v in src.items()]


def overlap_centrality(overlap: pd.DataFrame) -> list[dict[str, Any]]:
    mat = overlap.fillna(0.0).copy()
    degree = (mat > 0.05).sum(axis=1) - 1
    eigvals, eigvecs = np.linalg.eig(mat.to_numpy(dtype=float))
    idx = int(np.argmax(np.real(eigvals)))
    eig = np.abs(np.real(eigvecs[:, idx]))
    eig = eig / max(eig.sum(), 1e-12)
    return [{"node": n, "degree": float(degree.get(n, 0.0)), "eigenvector": float(eig[i])} for i, n in enumerate(mat.index)]


def liquidation_spiral_prob(overlap_mean: float, leverage: float, theta: float) -> float:
    return float(min(1.0, max(0.0, 1 - math.exp(-overlap_mean * leverage * theta * 4))))


def overlap_reducing_trades(weights: pd.Series, peer_average: pd.Series, top_n: int = 5) -> list[dict[str, Any]]:
    overlap = pd.concat([weights, peer_average], axis=1).fillna(0.0).min(axis=1)
    rows = []
    for s, v in overlap.sort_values(ascending=False).head(top_n).items():
        rows.append({"ticker": s, "current_weight": float(weights.get(s, 0.0)), "peer_avg_weight": float(peer_average.get(s, 0.0)), "suggested_trim": float(min(weights.get(s, 0.0), v / 2))})
    return rows


def sharpe_momentum_realloc(strategy_returns: pd.DataFrame) -> pd.Series:
    sharpe = strategy_returns.tail(126).mean() / strategy_returns.tail(126).std().replace(0, np.nan)
    ranks = sharpe.rank(pct=True).fillna(0.5)
    mult = pd.Series(1.0, index=strategy_returns.columns)
    mult[ranks >= 2 / 3] = 1.5
    mult[ranks <= 1 / 3] = 0.5
    return mult / mult.sum()


def regime_conditional_strategy_weights(strategy_returns: pd.DataFrame, regimes: pd.Series) -> list[dict[str, Any]]:
    rows = []
    aligned = regimes.reindex(strategy_returns.index).ffill()
    for r in sorted(aligned.dropna().unique()):
        sub = strategy_returns[aligned == r]
        w = (sub.mean() / sub.var().replace(0, np.nan)).clip(lower=0).fillna(0.0)
        w = w / max(w.sum(), 1e-12) if w.sum() > 0 else pd.Series(np.repeat(1 / len(sub.columns), len(sub.columns)), index=sub.columns)
        for s, val in w.items():
            rows.append({"regime": int(r), "strategy": s, "weight": float(val)})
    return rows


def kill_switch_pnl_calibration(strategy_returns: pd.DataFrame, thresholds: Iterable[float] = (0.05, 0.10, 0.15, 0.20)) -> list[dict[str, Any]]:
    rows = []
    for c in strategy_returns.columns:
        eq = (1 + strategy_returns[c]).cumprod()
        dd = eq / eq.cummax() - 1
        for th in thresholds:
            hit = dd <= -abs(th)
            saved = float(strategy_returns[c][hit].sum()) if hit.any() else 0.0
            rows.append({"strategy": c, "threshold": th, "pnl_saved_after_trigger": -saved, "triggered": bool(hit.any())})
    return rows


def cross_strategy_var_attribution(strategy_returns: pd.DataFrame, weights: pd.Series | None = None) -> list[dict[str, Any]]:
    cols = list(strategy_returns.columns)
    w = weights.reindex(cols).fillna(1 / len(cols)) if weights is not None else pd.Series(np.repeat(1 / len(cols), len(cols)), index=cols)
    cov = strategy_returns.cov()
    port_sigma = math.sqrt(max(float(w @ cov @ w), 1e-12))
    mvar = cov @ w / port_sigma
    rows = []
    for c in cols:
        standalone = float(strategy_returns[c].quantile(0.05))
        rows.append({"strategy": c, "standalone_var": standalone, "marginal_var": float(mvar[c]), "component_var": float(w[c] * mvar[c])})
    return rows


def capacity_constrained_realloc(weights: pd.Series, capacity: pd.Series, corr: pd.DataFrame) -> list[dict[str, Any]]:
    excess = (weights - capacity.reindex(weights.index).fillna(1.0)).clip(lower=0)
    freed = float(excess.sum())
    base = weights - excess
    room = (capacity.reindex(weights.index).fillna(1.0) - base).clip(lower=0)
    low_corr = 1 - corr.abs().mean().reindex(weights.index).fillna(0.5)
    score = (room * low_corr).clip(lower=0)
    add = score / max(score.sum(), 1e-12) * freed if freed > 0 else score * 0
    final = base + add
    return [{"strategy": k, "current_weight": float(weights[k]), "capacity": float(capacity.get(k, 1.0)), "reallocated_weight": float(final[k])} for k in weights.index]


def netting_savings(strategy_trades: pd.DataFrame, tc_bps: float = 10.0, nav: float = 1_000_000.0) -> list[dict[str, Any]]:
    if strategy_trades.empty:
        return []
    gross = strategy_trades.abs().sum(axis=1)
    net = strategy_trades.sum(axis=1).abs()
    savings = (gross - net).clip(lower=0)
    return [{"asset": idx, "gross_trade": float(gross.loc[idx]), "net_trade": float(net.loc[idx]), "netting_ratio": float(savings.loc[idx] / max(gross.loc[idx], 1e-12)), "savings_dollars": float(savings.loc[idx] * nav * tc_bps / 10000)} for idx in strategy_trades.index]


def diversification_benefit(strategy_returns: pd.DataFrame, weights: pd.Series | None = None) -> dict[str, float]:
    cols = list(strategy_returns.columns)
    w = weights.reindex(cols).fillna(1 / len(cols)) if weights is not None else pd.Series(np.repeat(1 / len(cols), len(cols)), index=cols)
    standalone = float((w.abs() * strategy_returns.std()).sum())
    combined = float((strategy_returns @ w).std())
    return {"weighted_avg_sigma": standalone, "combined_sigma": combined, "diversification_ratio": standalone / max(combined, 1e-12), "benefit": standalone - combined}


def build_strategy_returns(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame()
    mom = returns.rolling(21).mean().shift(1).rank(axis=1, pct=True)
    ls_mom = ((mom > 0.8).astype(float) - (mom < 0.2).astype(float))
    val = -returns.rolling(63).sum().shift(1).rank(axis=1, pct=True)
    ls_val = ((val > -0.2).astype(float) - (val < -0.8).astype(float))
    invvol = 1 / returns.rolling(63).std().shift(1).replace(0, np.nan)
    invvol = invvol.div(invvol.sum(axis=1), axis=0)
    strategies = pd.DataFrame(index=returns.index)
    strategies["momentum_ls"] = (ls_mom.div(ls_mom.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0) * returns).sum(axis=1)
    strategies["reversal_ls"] = (ls_val.div(ls_val.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0) * returns).sum(axis=1)
    strategies["risk_parity_proxy"] = (invvol.fillna(0.0) * returns).sum(axis=1)
    strategies["equal_weight"] = returns.mean(axis=1)
    return strategies.dropna(how="all").fillna(0.0)


def feature_meta(ctx: dict[str, Any], access_issues: list[str] | None = None) -> dict[str, Any]:
    return {
        "symbols": ctx["symbols"],
        "lookback_days": ctx["lookback_days"],
        "frequency": ctx["frequency"],
        "compute_mode": ctx["compute_mode"],
        "data_inventory": ctx["inventory"],
        "performance": performance_snapshot(),
        "access_issues": access_issues or [],
    }
