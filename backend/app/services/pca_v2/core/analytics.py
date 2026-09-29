"""Shared PCA V2 analytics.

The implementation is designed for real local parquet data and deterministic
JSON output. It avoids placeholders: where the repo lacks true external asset
classes, outputs are marked as proxy/data-constrained in metadata.
"""

from __future__ import annotations

import math
import base64
from io import BytesIO
from functools import lru_cache
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats
from scipy.linalg import subspace_angles
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, MinCovDet, OAS

try:
    import cvxpy as cp
except Exception:  # pragma: no cover
    cp = None

from .data_loader import (
    annualization_factor,
    dollar_volume_matrix,
    latest_market_caps,
    load_category7_macro,
    ohlcv_for_symbols,
    parse_symbols,
    returns_matrix,
    sector_map,
)


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO", "AAPL", "MSFT", "NVDA", "AMZN"]


def model_annualization(model: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> float:
    if model and model.get("annualization_factor"):
        return float(model["annualization_factor"])
    frequency = (model or {}).get("frequency") or (payload or {}).get("sampling_frequency") or (payload or {}).get("frequency") or "daily"
    return float(annualization_factor(frequency))


def clean_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.tolist())
    if isinstance(value, pd.DataFrame):
        return clean_json(value.to_dict("records"))
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    return value


def number_like(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def response(
    feature_id: str,
    summary_cards: list[dict[str, Any]],
    charts: dict[str, Any],
    tables: dict[str, Any],
    alerts: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    return clean_json(
        {
            "feature_id": f"feature_{str(feature_id).zfill(2)}",
            "status": status,
            "summary_cards": summary_cards,
            "charts": charts,
            "tables": tables,
            "alerts": alerts or [],
            "meta": meta or {},
        }
    )


def compact_records(df: pd.DataFrame, limit: int = 500) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    if len(out) > limit:
        idx = np.unique(np.round(np.linspace(0, len(out) - 1, limit)).astype(int))
        out = out.iloc[idx]
    for col in out.columns:
        if np.issubdtype(out[col].dtype, np.datetime64):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return clean_json(out.to_dict("records"))


def matrix_records(matrix: pd.DataFrame | np.ndarray, labels: Iterable[str] | None = None, limit: int = 120) -> list[dict[str, Any]]:
    if isinstance(matrix, pd.DataFrame):
        row_labels = [str(x) for x in matrix.index]
        col_labels = [str(x) for x in matrix.columns]
        arr = matrix.to_numpy(dtype=float)
    else:
        arr = np.asarray(matrix, dtype=float)
        base = list(labels or [f"A{i+1}" for i in range(arr.shape[0])])
        row_labels = base[: arr.shape[0]]
        col_labels = base[: arr.shape[1]]
    n = min(arr.shape[0], limit)
    m = min(arr.shape[1], limit)
    rows = []
    for i in range(n):
        for j in range(m):
            rows.append({"row": row_labels[i], "col": col_labels[j], "value": float(arr[i, j])})
    return clean_json(rows)


def parse_compute_mode(payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    raw = str(payload.get("compute_mode") or payload.get("mode") or "realtime").lower()
    if raw == "research" or payload.get("research_mode") is True:
        return "research"
    return "realtime"


def load_context(payload: dict[str, Any] | None, *, min_symbols: int = 12) -> dict[str, Any]:
    payload = payload or {}
    lookback = int(number_like(payload.get("window_length") or payload.get("window_days") or payload.get("lookback_days"), 504) or 504)
    raw_universe = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("universe")
    full_requested = str(raw_universe or "").strip().lower() in {"all", "full", "master", "master_universe", "market_universe", "whole"} or bool(payload.get("use_full_master_universe"))
    max_default = 5000 if full_requested else 120
    max_symbols = int(number_like(payload.get("max_symbols") or payload.get("max_tickers"), max_default) or max_default)
    default_limit = max(min_symbols, max_symbols if full_requested or payload.get("max_symbols") or payload.get("max_tickers") else min(max_symbols, 120))
    symbols = parse_symbols(payload, default_limit=default_limit, max_symbols=max_symbols)
    frequency = str(payload.get("sampling_frequency") or payload.get("frequency") or "daily").lower()
    rets = returns_matrix(symbols, lookback_days=max(lookback, 80), frequency=frequency)
    if rets.shape[1] < min_symbols:
        symbols = parse_symbols({}, default_limit=max(min_symbols, 80), max_symbols=max_symbols)
        rets = returns_matrix(symbols, lookback_days=max(lookback, 80), frequency=frequency)
    rets = rets.dropna(axis=1, how="all").fillna(0.0)
    symbols = [str(c) for c in rets.columns]
    return {
        "payload": payload,
        "symbols": symbols,
        "returns": rets,
        "lookback_days": lookback,
        "frequency": frequency,
        "annualization_factor": annualization_factor(frequency),
        "sectors": sector_map(symbols),
        "market_caps": latest_market_caps(symbols),
        "compute_mode": parse_compute_mode(payload),
    }


def covariance_estimator(returns: pd.DataFrame, method: str = "ledoit_wolf", ewma_lambda: float = 0.94) -> tuple[np.ndarray, dict[str, Any]]:
    x = returns.fillna(0.0).to_numpy(dtype=float)
    method = str(method or "ledoit_wolf").lower().replace("-", "_")
    meta: dict[str, Any] = {"estimator": method}
    if method in {"ledoit_wolf", "lw"}:
        est = LedoitWolf().fit(x)
        meta["shrinkage"] = float(est.shrinkage_)
        return est.covariance_, meta
    if method == "oas":
        est = OAS().fit(x)
        meta["shrinkage"] = float(est.shrinkage_)
        return est.covariance_, meta
    if method in {"mcd", "mincovdet", "minimum_covariance_determinant"} and len(x) > x.shape[1] + 5:
        est = MinCovDet(random_state=7, support_fraction=0.75).fit(x)
        meta["support_fraction"] = float(np.mean(est.support_))
        return est.covariance_, meta
    if method == "ewma":
        lam = min(0.995, max(0.50, float(ewma_lambda)))
        w = np.array([(1 - lam) * lam ** i for i in range(len(x) - 1, -1, -1)], dtype=float)
        w = w / max(w.sum(), 1e-12)
        xc = x - np.average(x, axis=0, weights=w)
        cov = (xc * w[:, None]).T @ xc
        meta["ewma_lambda"] = lam
        meta["half_life"] = float(np.log(0.5) / np.log(lam))
        return cov, meta
    return np.cov(x, rowvar=False), meta


def eig_sorted(cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vals, vecs = np.linalg.eigh((cov + cov.T) / 2)
    idx = np.argsort(vals)[::-1]
    return np.maximum(vals[idx], 0.0), vecs[:, idx]


def mp_threshold(eigenvalues: np.ndarray, n_assets: int, n_obs: int, sigma2: float | None = None) -> dict[str, float]:
    q = max(float(n_assets) / max(float(n_obs), 1.0), 1e-9)
    vals = np.asarray(eigenvalues, dtype=float)
    sigma = float(sigma2) if sigma2 is not None else float(np.nanmedian(vals) if len(vals) else 1.0)
    sigma = max(sigma, 1e-12)
    root = math.sqrt(q)
    return {
        "q_ratio": q,
        "sigma2": sigma,
        "lambda_min": sigma * (1 - root) ** 2,
        "lambda_max": sigma * (1 + root) ** 2,
    }


def scree_elbow(eigenvalues: np.ndarray) -> int:
    vals = np.asarray(eigenvalues, dtype=float)
    if len(vals) < 3:
        return max(1, len(vals))
    second = vals[:-2] - 2 * vals[1:-1] + vals[2:]
    return int(np.argmax(second) + 1)


def choose_k(eigenvalues: np.ndarray, mp: dict[str, float], payload: dict[str, Any] | None = None) -> dict[str, int]:
    payload = payload or {}
    vals = np.asarray(eigenvalues, dtype=float)
    total = max(float(vals.sum()), 1e-12)
    variance_threshold = float(number_like(payload.get("variance_threshold"), 0.95) or 0.95)
    k_rmt = int(max(1, np.sum(vals > mp["lambda_max"])))
    k_var = int(np.searchsorted(np.cumsum(vals) / total, variance_threshold) + 1)
    k_kaiser = int(max(1, np.sum(vals > 1.0)))
    k_elbow = scree_elbow(vals)
    manual = payload.get("component_count") or payload.get("k") or payload.get("K")
    k_manual = int(number_like(manual, k_rmt) or k_rmt)
    k = int(max(1, min(len(vals), k_manual if manual is not None else k_rmt)))
    return {"selected": k, "rmt": k_rmt, "variance_threshold": k_var, "kaiser": k_kaiser, "scree_elbow": k_elbow}


def rmt_model(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload)
    payload = ctx["payload"]
    returns = ctx["returns"]
    method = payload.get("covariance_estimator") or payload.get("estimator") or "ledoit_wolf"
    outlier_method = str(payload.get("outlier_method") or ("winsorize_z" if payload.get("outlier_filter") else "none")).lower()
    cleaned_returns = preprocess_returns(
        returns,
        method=outlier_method,
        z_threshold=float(number_like(payload.get("outlier_z_threshold"), 4.0) or 4.0),
        lower_quantile=float(number_like(payload.get("winsor_lower"), 0.01) or 0.01),
        upper_quantile=float(number_like(payload.get("winsor_upper"), 0.99) or 0.99),
    )
    cov, cov_meta = covariance_estimator(cleaned_returns, method, ewma_lambda=float(number_like(payload.get("ewma_lambda"), 0.94) or 0.94))
    evals, evecs = eig_sorted(cov)
    # Iterative sigma² fitting (moment-matching) unless user supplies sigma2_noise explicitly
    if payload.get("sigma2_noise") is not None:
        sigma2 = float(payload["sigma2_noise"])
    else:
        sigma2 = fit_mp_sigma2(evals, returns.shape[1], returns.shape[0])
    mp = mp_threshold(evals, returns.shape[1], returns.shape[0], sigma2=sigma2)
    cov_meta["fitted_sigma2"] = sigma2
    k_info = choose_k(evals, mp, payload)
    k = k_info["selected"]
    signal = (evecs[:, :k] * evals[:k]) @ evecs[:, :k].T
    idio = np.maximum(np.diag(cov - signal), 1e-10)
    cleaned = signal + np.diag(idio)
    raw_evals, _ = eig_sorted(np.cov(returns.to_numpy(dtype=float), rowvar=False))
    raw_cov = np.cov(returns.to_numpy(dtype=float), rowvar=False)
    clean_evals, _ = eig_sorted(cleaned)
    return {
        **ctx,
        "cov": cov,
        "raw_cov": raw_cov,
        "cleaned_cov": cleaned,
        "eigenvalues": evals,
        "eigenvectors": evecs,
        "raw_eigenvalues": raw_evals,
        "cleaned_eigenvalues": clean_evals,
        "mp": mp,
        "k_info": k_info,
        "k": k,
        "idio_var": idio,
        "cov_meta": cov_meta,
    }


@lru_cache(maxsize=32)
def _cached_rmt_key(symbols_key: tuple[str, ...], lookback: int, estimator: str, k: int | None) -> dict[str, Any]:
    payload = {"symbols": list(symbols_key), "lookback_days": lookback, "covariance_estimator": estimator}
    if k:
        payload["k"] = k
    return rmt_model(payload)


def factor_returns(model: dict[str, Any], k: int | None = None) -> pd.DataFrame:
    k = int(k or model["k"])
    data = model["returns"].to_numpy(dtype=float)
    loadings = model["eigenvectors"][:, :k]
    factors = data @ loadings
    return pd.DataFrame(factors, index=model["returns"].index, columns=[f"PC{i+1}" for i in range(k)])


def loading_records(model: dict[str, Any], k: int | None = None) -> list[dict[str, Any]]:
    k = int(k or model["k"])
    sectors = model["sectors"]
    records = []
    for i, ticker in enumerate(model["symbols"]):
        row = {"ticker": ticker, "sector": sectors.get(ticker, "Unknown")}
        for pc in range(k):
            row[f"PC{pc+1}"] = float(model["eigenvectors"][i, pc])
        records.append(row)
    return records


def explained_variance_records(model: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    vals = model["eigenvalues"]
    total = max(float(vals.sum()), 1e-12)
    cum = np.cumsum(vals) / total
    n = limit or min(len(vals), 50)
    return [
        {"component": f"PC{i+1}", "rank": i + 1, "eigenvalue": float(vals[i]), "explained_variance": float(vals[i] / total), "cumulative_variance": float(cum[i])}
        for i in range(min(n, len(vals)))
    ]


def varimax(loadings: np.ndarray, gamma: float = 1.0, q: int = 80, tol: float = 1e-6) -> np.ndarray:
    p, k = loadings.shape
    r = np.eye(k)
    d = 0.0
    for _ in range(q):
        old = d
        lam = loadings @ r
        u, s, vh = np.linalg.svd(loadings.T @ (lam ** 3 - (gamma / p) * lam @ np.diag(np.diag(lam.T @ lam))))
        r = u @ vh
        d = float(np.sum(s))
        if old and d / old < 1 + tol:
            break
    return loadings @ r


def promax(loadings: np.ndarray, power: int = 3, q: int = 80, tol: float = 1e-6) -> np.ndarray:
    """Promax oblique rotation: varimax then raise to power to sharpen."""
    vm = varimax(loadings, gamma=1.0, q=q, tol=tol)
    # Raise each element to power (preserving sign)
    target = np.sign(vm) * np.abs(vm) ** power
    # Solve for oblique rotation matrix: L @ R = target
    result = np.linalg.lstsq(vm, target, rcond=None)[0]
    rotated = vm @ result
    # Column-normalize
    norms = np.sqrt((rotated ** 2).sum(axis=0))
    norms[norms < 1e-12] = 1.0
    return rotated / norms


def fit_mp_sigma2(eigenvalues: np.ndarray, n_assets: int, n_obs: int, n_iter: int = 50) -> float:
    """Iterative sigma² estimation via Marchenko-Pastur moment matching.

    Fits sigma² so that E[lambda_max_MP] = empirical mean of noise eigenvalues.
    Returns sigma² for the noise floor.
    """
    vals = np.asarray(eigenvalues, dtype=float)
    q = max(float(n_assets) / max(float(n_obs), 1.0), 1e-9)
    # Start: use median of all eigenvalues as initial sigma2
    sigma2 = float(np.median(vals))
    sigma2 = max(sigma2, 1e-12)
    for _ in range(n_iter):
        lam_max = sigma2 * (1 + math.sqrt(q)) ** 2
        # Noise eigenvalues = those below current lam_max
        noise = vals[vals <= lam_max]
        if len(noise) == 0:
            break
        # MP moment: E[lambda] = sigma2 (the mean of MP distribution = sigma2)
        new_sigma2 = float(np.mean(noise))
        new_sigma2 = max(new_sigma2, 1e-12)
        if abs(new_sigma2 - sigma2) < 1e-10:
            break
        sigma2 = new_sigma2
    return sigma2


def preprocess_returns(
    returns: pd.DataFrame,
    method: str = "none",
    z_threshold: float = 4.0,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> pd.DataFrame:
    """Apply an explicit, user-selected robust preprocessing method."""
    x = returns.fillna(0.0)
    method = str(method or "none").lower()
    if method in {"none", "off", "false"}:
        return x
    if method in {"winsorize_1_99", "winsorize", "quantile"}:
        return x.clip(lower=x.quantile(lower_quantile), upper=x.quantile(upper_quantile), axis=1)
    if method in {"winsorize_2_5_97_5", "winsorize_2.5_97.5"}:
        return x.clip(lower=x.quantile(0.025), upper=x.quantile(0.975), axis=1)
    if method in {"trim", "trimming"}:
        lower, upper = x.quantile(lower_quantile), x.quantile(upper_quantile)
        keep = x.ge(lower, axis=1).all(axis=1) & x.le(upper, axis=1).all(axis=1)
        return x.loc[keep] if int(keep.sum()) >= max(10, x.shape[1] + 2) else x.clip(lower=lower, upper=upper, axis=1)
    mean = x.mean()
    std = x.std().replace(0, np.nan).fillna(1.0)
    if method in {"huber", "huber_m", "huber_m_estimation"}:
        center = x.median()
        scale = (x.sub(center).abs().median() * 1.4826).replace(0, np.nan).fillna(std)
        c = max(0.5, float(z_threshold))
        for _ in range(20):
            residual = x.sub(center).div(scale)
            weights = (c / residual.abs().clip(lower=c)).clip(upper=1.0)
            new_center = (x * weights).sum() / weights.sum().replace(0, np.nan)
            if float((new_center - center).abs().max()) < 1e-10:
                break
            center = new_center.fillna(center)
        return center + x.sub(center).clip(lower=-c * scale, upper=c * scale, axis=1)
    z = (x - mean) / std
    clipped = z.clip(lower=-z_threshold, upper=z_threshold)
    return mean + clipped * std


def hoyer_sparsity(loadings: np.ndarray) -> list[dict]:
    """Hoyer sparsity score per PC column. Higher = more concentrated = more interpretable."""
    n, k = loadings.shape
    rows = []
    for j in range(k):
        col = loadings[:, j]
        l1 = float(np.sum(np.abs(col)))
        l2 = float(np.sqrt(np.sum(col ** 2)))
        # Hoyer: (sqrt(n) - l1/l2) / (sqrt(n) - 1), in [0,1]
        sparsity = (math.sqrt(n) - l1 / max(l2, 1e-12)) / max(math.sqrt(n) - 1, 1e-12)
        rows.append({"component": f"PC{j+1}", "hoyer_sparsity": float(np.clip(sparsity, 0, 1))})
    return rows


def asset_r2(model: dict[str, Any]) -> list[dict]:
    """Per-asset R² explained by the retained PCs."""
    k = model["k"]
    vecs = model["eigenvectors"][:, :k]
    evals = model["eigenvalues"][:k]
    diag_cov = np.diag(model["cov"])
    r2_vals = np.sum(vecs ** 2 * evals, axis=1) / np.maximum(diag_cov, 1e-12)
    return [
        {
            "ticker": model["symbols"][i],
            "sector": model["sectors"].get(model["symbols"][i], "Unknown"),
            "r2": float(np.clip(r2_vals[i], 0.0, 1.0)),
            "idiosyncratic_share": float(np.clip(1 - r2_vals[i], 0.0, 1.0)),
        }
        for i in range(len(model["symbols"]))
    ]


def hierarchical_pca(
    returns: pd.DataFrame,
    sectors: dict[str, str],
    k_intra: int = 2,
    k_cross: int = 3,
    estimator: str = "ledoit_wolf",
) -> dict:
    """Two-level Hierarchical PCA: intra-cluster then cross-cluster."""
    from collections import defaultdict
    cluster_map: dict[str, list[str]] = defaultdict(list)
    for ticker, sector in sectors.items():
        if ticker in returns.columns:
            cluster_map[sector].append(ticker)

    cluster_factors: dict[str, pd.DataFrame] = {}
    cluster_loadings: dict[str, dict] = {}
    for sector, tickers in cluster_map.items():
        if len(tickers) < 2:
            continue
        sub_rets = returns[tickers].fillna(0.0)
        cov, _ = covariance_estimator(sub_rets, estimator)
        vals, vecs = eig_sorted(cov)
        kk = min(k_intra, len(tickers) - 1, len(vals))
        f = sub_rets.to_numpy(dtype=float) @ vecs[:, :kk]
        cluster_factors[sector] = pd.DataFrame(
            f, index=returns.index,
            columns=[f"{sector}_PC{i+1}" for i in range(kk)]
        )
        cluster_loadings[sector] = {
            "tickers": tickers,
            "loadings": vecs[:, :kk].tolist(),
            "eigenvalues": vals[:kk].tolist(),
        }

    if len(cluster_factors) < 2:
        return {"cluster_factors": {k: v.to_dict("records") for k, v in cluster_factors.items()}, "cross_loadings": None}

    cross_rets = pd.concat(list(cluster_factors.values()), axis=1).fillna(0.0)
    cov2, _ = covariance_estimator(cross_rets, estimator)
    vals2, vecs2 = eig_sorted(cov2)
    kk2 = min(k_cross, cross_rets.shape[1] - 1)
    cross_factor_rets = pd.DataFrame(
        cross_rets.to_numpy(dtype=float) @ vecs2[:, :kk2],
        index=returns.index,
        columns=[f"Cross_PC{i+1}" for i in range(kk2)]
    )
    return {
        "cluster_loadings": cluster_loadings,
        "cross_factor_returns": compact_records(cross_factor_rets.reset_index(names="date"), limit=500),
        "cross_eigenvalues": vals2[:kk2].tolist(),
        "cross_column_names": list(cross_rets.columns),
    }


def active_risk_attribution(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tracking error decomposition against a benchmark weight vector."""
    payload = payload or {}
    symbols = model["symbols"]
    w = portfolio_weights(symbols, payload).reindex(symbols).fillna(0.0).to_numpy(dtype=float)
    w_bench_raw = payload.get("benchmark_weights") or {}
    if isinstance(w_bench_raw, dict) and w_bench_raw:
        w_bench = pd.Series({s: float(w_bench_raw.get(s, 0.0)) for s in symbols}, dtype=float)
        w_bench = (w_bench / w_bench.abs().sum()).to_numpy(dtype=float)
    else:
        w_bench = np.ones(len(symbols)) / len(symbols)

    wa = w - w_bench
    cov = model["cleaned_cov"]
    evals = model["eigenvalues"]
    vecs = model["eigenvectors"]
    k = model["k"]

    active_var = float(wa @ cov @ wa)
    ann = model_annualization(model, payload)
    te = float(math.sqrt(max(active_var * ann, 0)))

    factor_active_vars = []
    for i in range(k):
        exposure = float(wa @ vecs[:, i])
        fav = float(evals[i] * exposure ** 2)
        factor_active_vars.append({
            "component": f"PC{i+1}",
            "active_exposure": exposure,
            "active_variance": fav,
            "pct_active_variance": fav / max(active_var, 1e-12) * 100,
            "annualized_te_contribution_bps": float(math.sqrt(max(fav * ann, 0)) * 10000),
        })

    idio_active_var = float(np.sum(model["idio_var"] * wa ** 2))
    factor_active_vars.append({
        "component": "Idiosyncratic",
        "active_exposure": None,
        "active_variance": idio_active_var,
        "pct_active_variance": idio_active_var / max(active_var, 1e-12) * 100,
        "annualized_te_contribution_bps": float(math.sqrt(max(idio_active_var * ann, 0)) * 10000),
    })

    return {
        "active_variance": active_var,
        "tracking_error_annualized": te,
        "factor_tilt_share": sum(r["pct_active_variance"] for r in factor_active_vars if r["component"] != "Idiosyncratic"),
        "selection_share": idio_active_var / max(active_var, 1e-12) * 100,
        "attribution_rows": factor_active_vars,
    }


def rolling_risk_decomposition(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    window: int = 21,
) -> pd.DataFrame:
    """Rolling per-factor risk decomposition (stacked attribution)."""
    symbols = model["symbols"]
    w = portfolio_weights(symbols, payload).reindex(symbols).fillna(0.0).to_numpy(dtype=float)
    rets = model["returns"].reindex(columns=symbols).fillna(0.0)
    k = model["k"]
    rows = []
    for end in range(window, len(rets) + 1):
        sub = rets.iloc[end - window: end]
        cov_sub = np.cov(sub.to_numpy(dtype=float), rowvar=False)
        port_var = max(float(w @ cov_sub @ w), 1e-12)
        evals_sub, evecs_sub = eig_sorted(cov_sub)
        row: dict[str, Any] = {"date": rets.index[end - 1]}
        for i in range(min(k, len(evals_sub))):
            exp = float(w @ evecs_sub[:, i])
            row[f"PC{i+1}_pct"] = float(evals_sub[i] * exp ** 2 / port_var * 100)
        idio = max(0.0, 100.0 - sum(row.get(f"PC{i+1}_pct", 0.0) for i in range(k)))
        row["Idiosyncratic_pct"] = idio
        rows.append(row)
    return pd.DataFrame(rows)


def volume_time_residuals(
    resid: pd.DataFrame,
    dv: pd.DataFrame,
) -> pd.DataFrame:
    """Re-express residuals in volume time per Avellaneda-Lee (2010)."""
    vol_mean = dv.rolling(30, min_periods=5).mean().replace(0, np.nan)
    vol_ratio = (dv / vol_mean).fillna(1.0).clip(lower=0.01)
    scaled = resid / np.sqrt(vol_ratio.reindex(resid.index, method="ffill").reindex(columns=resid.columns).fillna(1.0))
    return scaled


def erc_portfolio(
    cov: np.ndarray,
    symbols: list[str],
    risk_budgets: np.ndarray | None = None,
) -> np.ndarray:
    """Equal Risk Contribution portfolio via Spinu (2013) convex reformulation."""
    n = cov.shape[0]
    c = risk_budgets if risk_budgets is not None else np.ones(n) / n

    def objective(w: np.ndarray) -> float:
        return 0.5 * float(w @ cov @ w) - float(np.sum(c * np.log(np.maximum(w, 1e-12))))

    def gradient(w: np.ndarray) -> np.ndarray:
        return cov @ w - c / np.maximum(w, 1e-12)

    w0 = np.ones(n) / n
    bounds = [(1e-6, None)] * n
    result = minimize(objective, w0, jac=gradient, method="L-BFGS-B", bounds=bounds, options={"maxiter": 1000, "ftol": 1e-12})
    w = np.maximum(np.array(result.x, dtype=float), 0)
    total = w.sum()
    return w / total if total > 1e-12 else np.ones(n) / n


def max_sharpe_portfolio(
    cov: np.ndarray,
    mu: np.ndarray,
    rf: float = 0.0,
    max_weight: float = 0.12,
) -> np.ndarray:
    """Explicit max-Sharpe via Tobin separation trick."""
    n = len(mu)
    excess_mu = mu - rf
    if cp is not None:
        w = cp.Variable(n)
        constraints = [
            cp.sum(cp.multiply(excess_mu, w)) == 1,
            w >= 0,
            w <= max_weight * cp.sum(cp.abs(w)),
        ]
        prob = cp.Problem(cp.Minimize(cp.quad_form(w, cov)), constraints)
        try:
            prob.solve(solver=cp.OSQP, verbose=False)
            raw = np.array(w.value, dtype=float)
        except Exception:
            raw = np.linalg.pinv(cov) @ excess_mu
    else:
        raw = np.linalg.pinv(cov) @ excess_mu
    raw = np.maximum(raw, 0)
    total = raw.sum()
    return raw / total if total > 1e-12 else np.ones(n) / n


def pc_factor_risk_parity_portfolio(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Portfolio whose retained PC variance contributions are as equal as possible."""

    payload = payload or {}
    symbols = model["symbols"]
    n = len(symbols)
    k = int(model["k"])
    vals = model["eigenvalues"][:k]
    vecs = model["eigenvectors"][:, :k]
    max_w = float(number_like(payload.get("max_weight"), 0.12) or 0.12)
    target = np.ones(k) / max(k, 1)

    def contrib_pct(w: np.ndarray) -> np.ndarray:
        exposures = vecs.T @ w
        contrib = vals * exposures ** 2
        total = float(np.sum(contrib))
        return contrib / max(total, 1e-12)

    def objective(w: np.ndarray) -> float:
        c = contrib_pct(w)
        concentration_penalty = 1e-4 * float(np.sum(w ** 2))
        return float(np.sum((c - target) ** 2)) + concentration_penalty

    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    bounds = [(0.0, max_w)] * n
    w0 = np.ones(n) / n
    if max_w * n < 1.0:
        bounds = [(0.0, 1.0)] * n
    try:
        result = minimize(objective, w0, method="SLSQP", bounds=bounds, constraints=constraints, options={"maxiter": 1000, "ftol": 1e-12})
        w = np.asarray(result.x, dtype=float)
        status = "pc_risk_parity_slsqp" if result.success else f"pc_risk_parity_fallback_{result.message}"
    except Exception as exc:
        w = w0
        status = f"pc_risk_parity_fallback_{type(exc).__name__}"
    w = np.maximum(w, 0.0)
    w = w / max(w.sum(), 1e-12)
    c = contrib_pct(w)
    weights = [{"ticker": symbols[i], "weight": float(w[i]), "sector": model["sectors"].get(symbols[i], "Unknown")} for i in np.argsort(w)[::-1]]
    contributions = [{"component": f"PC{i+1}", "pct_systematic_variance": float(c[i] * 100), "target_pct": float(target[i] * 100)} for i in range(k)]
    return {"status": status, "weights": weights, "contributions": contributions, "objective": objective(w)}


def k_sensitivity_sweep(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    oos_fraction: float = 0.3,
) -> list[dict]:
    """Out-of-sample Sharpe vs K sweep for sensitivity analysis."""
    from copy import deepcopy
    rets = model["returns"]
    n_obs = len(rets)
    split = int(n_obs * (1 - oos_fraction))
    rets_is = rets.iloc[:split]
    rets_oos = rets.iloc[split:]
    k_max = int(model["k_info"].get("rmt", 10))
    k_range = range(1, min(k_max + 3, rets.shape[1] - 1))
    ann = model_annualization(model, payload)
    rows = []
    for k in k_range:
        try:
            m_is = deepcopy(model)
            m_is["returns"] = rets_is
            m_is["k"] = k
            cov_is, _ = covariance_estimator(rets_is, "ledoit_wolf")
            evals_is, evecs_is = eig_sorted(cov_is)
            idio_is = np.maximum(np.diag(cov_is) - np.sum(evecs_is[:, :k] ** 2 * evals_is[:k], axis=1), 1e-10)
            signal_is = (evecs_is[:, :k] * evals_is[:k]) @ evecs_is[:, :k].T
            m_is["cov"] = cov_is
            m_is["cleaned_cov"] = signal_is + np.diag(idio_is)
            m_is["eigenvalues"] = evals_is
            m_is["eigenvectors"] = evecs_is
            m_is["idio_var"] = idio_is
            opt = optimize_portfolio(m_is, payload)
            w = np.array(
                [r["weight"] for r in sorted(opt["weights"], key=lambda x: model["symbols"].index(x["ticker"]) if x["ticker"] in model["symbols"] else 9999)],
                dtype=float,
            )
            if len(w) != len(model["symbols"]):
                continue
            oos_rets = rets_oos.reindex(columns=model["symbols"]).fillna(0.0).to_numpy(dtype=float)
            p_rets = oos_rets @ w
            sr = float(p_rets.mean() / max(p_rets.std(ddof=1), 1e-12) * math.sqrt(ann))
            rows.append({"k": k, "oos_sharpe": sr, "oos_vol": float(p_rets.std() * math.sqrt(ann)), "is_k_rmt": k == model["k_info"].get("rmt")})
        except Exception:
            continue
    return rows


def black_litterman_posterior(
    cov: np.ndarray,
    w_market: np.ndarray,
    views: list[dict],
    symbols: list[str],
    tau: float = 0.05,
    risk_aversion: float = 3.0,
) -> np.ndarray:
    """Black-Litterman posterior expected returns."""
    n = len(symbols)
    sym_idx = {s: i for i, s in enumerate(symbols)}
    mu_prior = risk_aversion * cov @ w_market

    if not views:
        return mu_prior

    Q_rows: list[np.ndarray] = []
    q_vals: list[float] = []
    omega_diag: list[float] = []
    for v in views:
        row = np.zeros(n)
        for ticker, loading in (v.get("assets") or {}).items():
            idx = sym_idx.get(ticker)
            if idx is not None:
                row[idx] = float(loading)
        if np.abs(row).sum() < 1e-12:
            continue
        Q_rows.append(row)
        q_vals.append(float(v.get("return", 0.0)))
        conf = float(np.clip(v.get("confidence", 0.5), 0.01, 0.99))
        omega_diag.append(tau * float(row @ cov @ row) / max(conf ** 2, 1e-6))

    if not Q_rows:
        return mu_prior

    P = np.array(Q_rows, dtype=float)
    q = np.array(q_vals, dtype=float)
    Omega = np.diag(omega_diag)

    tau_sigma_inv = np.linalg.pinv(tau * cov)
    omega_inv = np.diag(1.0 / np.maximum(np.diag(Omega), 1e-12))
    precision = tau_sigma_inv + P.T @ omega_inv @ P
    rhs = tau_sigma_inv @ mu_prior + P.T @ omega_inv @ q
    mu_post = np.linalg.pinv(precision) @ rhs
    return mu_post


def bai_ng_criteria(
    returns: pd.DataFrame,
    k_max: int = 15,
) -> list[dict]:
    """Proper Bai-Ng (2002) IC1/IC2/IC3 panel factor number criteria.

    SSR(r) is computed from a rank-r factor model at each candidate K.
    """
    x = returns.fillna(0.0).to_numpy(dtype=float)
    T, N = x.shape
    NT = N * T
    min_NT = min(N, T)
    rows = []
    for r in range(1, min(k_max, min(N, T) - 1) + 1):
        # Fit rank-r factor model and compute SSR
        cov_r = np.cov(x, rowvar=False)
        vals_r, vecs_r = eig_sorted(cov_r)
        k_use = min(r, len(vals_r))
        factors = x @ vecs_r[:, :k_use]  # T x r
        loadings = vecs_r[:, :k_use]     # N x r
        x_hat = factors @ loadings.T     # T x N reconstruction
        ssr = float(np.sum((x - x_hat) ** 2)) / NT
        ssr = max(ssr, 1e-12)
        # Penalty terms
        g_NT = (N + T) / NT
        pen1 = r * g_NT * math.log(NT / max(N + T, 1))
        pen2 = r * g_NT * math.log(min_NT)
        pen3 = r * math.log(min_NT) / min_NT
        rows.append({
            "k": r,
            "SSR": ssr,
            "IC1": math.log(ssr) + pen1,
            "IC2": math.log(ssr) + pen2,
            "IC3": math.log(ssr) + pen3,
        })
    return rows


def block_bootstrap_sample(
    data: np.ndarray,
    block_length: int = 21,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Circular block bootstrap: draw blocks of length block_length to fill T rows."""
    rng = rng or np.random.default_rng()
    T = data.shape[0]
    n_blocks = math.ceil(T / block_length)
    starts = rng.integers(0, T, size=n_blocks)
    rows_list: list[np.ndarray] = []
    for s in starts:
        for t in range(block_length):
            rows_list.append(data[(s + t) % T])
    return np.array(rows_list[:T], dtype=float)


def subsampling_stability(
    model: dict[str, Any],
    n_subsamples: int = 50,
    subsample_fraction: float = 0.7,
    rng_seed: int = 42,
) -> list[dict]:
    """Subsampling stability: cosine similarity between full-sample and subsample loadings."""
    rng = np.random.default_rng(rng_seed)
    rets = model["returns"].fillna(0.0).to_numpy(dtype=float)
    T = rets.shape[0]
    k = model["k"]
    P_full = model["eigenvectors"][:, :k]  # N x K
    sub_size = max(int(T * subsample_fraction), k + 5)
    cosines: list[list[float]] = [[] for _ in range(k)]
    cross = np.zeros((k, k), dtype=float)
    for _ in range(n_subsamples):
        idx = rng.choice(T, size=sub_size, replace=False)
        sub = rets[idx]
        cov_sub = np.cov(sub, rowvar=False)
        _, vecs_sub = eig_sorted(cov_sub)
        P_sub = vecs_sub[:, :k]
        cross += np.abs(P_full.T @ P_sub)
        for j in range(k):
            c = abs(float(P_full[:, j] @ P_sub[:, j]))
            cosines[j].append(min(c, 1.0))
    rows = []
    for j in range(k):
        rows.append({
            "component": f"PC{j+1}",
            "mean_cosine": float(np.mean(cosines[j])),
            "min_cosine": float(np.min(cosines[j])),
            "std_cosine": float(np.std(cosines[j])),
        })
    cross /= max(n_subsamples, 1)
    for i in range(k):
        for j in range(k):
            rows.append({
                "row": f"PC{i+1}", "col": f"PC{j+1}",
                "cross_cosine": float(cross[i, j]), "record_type": "cross_matrix",
            })
    return rows


def subspace_principal_angles(
    P1: np.ndarray,
    P2: np.ndarray,
) -> np.ndarray:
    """Principal angles between two K-dimensional subspaces via SVD of P1^T P2."""
    M = P1.T @ P2
    sv = np.linalg.svd(M, compute_uv=False)
    sv = np.clip(sv, -1.0, 1.0)
    return np.arccos(sv)


def rolling_group_residual_corr(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    window: int = 63,
) -> list[dict]:
    """Rolling daily time series of average pairwise residual correlation per sector."""
    payload = payload or {}
    window = int(number_like((payload or {}).get("residual_window"), window) or window)
    resid = residual_matrix(model)
    sectors = model["sectors"]
    sector_cols: dict[str, list[str]] = {}
    for col in resid.columns:
        s = sectors.get(col, "Unknown")
        sector_cols.setdefault(s, []).append(col)

    rows = []
    for end in range(window, len(resid) + 1):
        sub = resid.iloc[end - window: end]
        date = resid.index[end - 1]
        for sector, cols in sector_cols.items():
            if len(cols) < 2:
                continue
            c = sub[cols].corr().fillna(0.0).to_numpy(dtype=float)
            upper = c[np.triu_indices_from(c, 1)]
            rows.append({
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "sector": sector,
                "avg_residual_corr": float(np.mean(upper)),
            })
    return rows


def historical_worst_day_scenarios(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    n_worst: int = 5,
) -> list[dict]:
    """For each PC, find the n worst historical daily realizations and replay portfolio P&L."""
    payload = payload or {}
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    rows = []
    for j in range(model["k"]):
        worst_idx = f.iloc[:, j].nsmallest(n_worst).index
        for date in worst_idx:
            factor_shock = f.loc[date].to_numpy(dtype=float)
            asset_impacts = model["eigenvectors"][:, :model["k"]] @ factor_shock
            pnl = float(w @ asset_impacts)
            realized_port = float(model["returns"].loc[date].to_numpy(dtype=float) @ w)
            rows.append({
                "component": f"PC{j+1}",
                "date": str(pd.Timestamp(date).date()),
                "factor_return": float(factor_shock[j]),
                "estimated_pnl": pnl,
                "realized_portfolio_return": realized_port,
            })
    return sorted(rows, key=lambda r: r["estimated_pnl"])


def joint_scenario_pnl(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Simultaneously shock multiple PCs with independent magnitudes.

    payload["joint_shocks"] = {"PC1": 2.0, "PC3": -1.5}  (sigma multiples)
    """
    payload = payload or {}
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    stds = f.std().replace(0, np.nan).fillna(1e-6).to_numpy(dtype=float)
    joint_shocks_raw = payload.get("joint_shocks") or {}
    shock = np.zeros(model["k"])
    for label, sigma_mult in (joint_shocks_raw if isinstance(joint_shocks_raw, dict) else {}).items():
        try:
            pc_idx = int(str(label).upper().replace("PC", "")) - 1
            if 0 <= pc_idx < model["k"]:
                shock[pc_idx] = float(sigma_mult) * stds[pc_idx]
        except (ValueError, IndexError):
            continue
    asset_returns = model["eigenvectors"][:, :model["k"]] @ shock
    pnl = float(w @ asset_returns)
    ticker_contributions = [
        {"ticker": model["symbols"][i], "pnl_contribution": float(w[i] * asset_returns[i])}
        for i in range(len(w))
    ]
    return {
        "joint_shocks": joint_shocks_raw,
        "portfolio_pnl": pnl,
        "shock_vector": shock.tolist(),
        "ticker_contributions": sorted(ticker_contributions, key=lambda r: r["pnl_contribution"]),
    }


def pastor_stambaugh_gamma(
    returns: pd.DataFrame,
    dollar_volume: pd.DataFrame,
    market_returns: pd.Series,
    window: int = 21,
) -> pd.DataFrame:
    """Pastor-Stambaugh (2003) rolling liquidity gamma per ticker."""
    gammas: dict[str, pd.Series] = {}
    for ticker in returns.columns:
        r = returns[ticker].dropna()
        dv = dollar_volume[ticker].reindex(r.index).ffill()
        rm = market_returns.reindex(r.index).fillna(0.0)
        r_excess = r - rm
        if len(r_excess) < window + 5:
            continue
        rolling_gammas = []
        for end in range(window, len(r_excess)):
            sub_re = r_excess.iloc[end - window: end]
            sub_r = r.iloc[end - window: end]
            sub_dv = dv.iloc[end - window: end]
            y = sub_re.shift(-1).iloc[:-1].to_numpy(dtype=float)
            x1 = sub_r.iloc[:-1].to_numpy(dtype=float)
            signed_vol = (np.sign(sub_re.iloc[:-1]) * sub_dv.iloc[:-1]).to_numpy(dtype=float)
            X = np.column_stack([np.ones(len(y)), x1, signed_vol])
            valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
            if valid.sum() < 5:
                rolling_gammas.append(np.nan)
                continue
            coef = np.linalg.lstsq(X[valid], y[valid], rcond=None)[0]
            rolling_gammas.append(float(coef[2]))
        gammas[ticker] = pd.Series(rolling_gammas, index=r_excess.index[window:])
    return pd.DataFrame(gammas)


def kyle_lambda_daily(symbols: list[str]) -> pd.DataFrame:
    """Daily approximation of Kyle's lambda from OHLCV (Hasbrouck 2009).

    lambda_i = (High - Low) / (2 * Volume * sqrt(2/pi))
    """
    try:
        ohlcv = ohlcv_for_symbols(symbols)
    except Exception:
        return pd.DataFrame()
    results: dict[str, pd.Series] = {}
    for ticker in symbols:
        sub = ohlcv[ohlcv["Ticker"] == ticker][["Date", "High", "Low", "Volume"]].set_index("Date") if "Ticker" in ohlcv.columns else pd.DataFrame()
        if sub.empty:
            continue
        high = pd.to_numeric(sub["High"], errors="coerce")
        low = pd.to_numeric(sub["Low"], errors="coerce")
        vol = pd.to_numeric(sub["Volume"], errors="coerce").replace(0, np.nan)
        lam = (high - low) / (2 * vol * math.sqrt(2 / math.pi))
        results[ticker] = lam
    return pd.DataFrame(results)


def newey_west_se(
    X: np.ndarray,
    residuals: np.ndarray,
    coef_idx: int = 1,
    n_lags: int = 3,
) -> float:
    """Newey-West HAC standard error for coefficient at coef_idx (Bartlett kernel)."""
    n = X.shape[0]
    XtX_inv = np.linalg.pinv(X.T @ X)
    S = np.zeros((X.shape[1], X.shape[1]))
    for t in range(n):
        S += (residuals[t] ** 2) * np.outer(X[t], X[t])
    S /= n
    for lag in range(1, n_lags + 1):
        w_lag = 1.0 - lag / (n_lags + 1)
        gamma = np.zeros((X.shape[1], X.shape[1]))
        for t in range(lag, n):
            gamma += residuals[t] * residuals[t - lag] * np.outer(X[t], X[t - lag])
        gamma /= n
        S += w_lag * (gamma + gamma.T)
    V = XtX_inv @ S @ XtX_inv / n
    return float(math.sqrt(max(V[coef_idx, coef_idx], 0)))


def portfolio_weights(symbols: list[str], payload: dict[str, Any] | None = None) -> pd.Series:
    payload = payload or {}
    raw = payload.get("weights") or payload.get("portfolio") or payload.get("holdings")
    weights: dict[str, float] = {}
    if isinstance(raw, dict):
        weights = {str(k).upper().replace(".", "_").replace("-", "_"): float(v) for k, v in raw.items()}
    elif isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict):
                t = str(row.get("ticker") or row.get("symbol") or row.get("asset") or "").upper().replace(".", "_").replace("-", "_")
                v = number_like(row.get("weight") or row.get("target_weight") or row.get("value"), None)
                if t and v is not None:
                    weights[t] = float(v)
    if not weights:
        caps = latest_market_caps(symbols)
        vals = np.array([caps.get(s, np.nan) for s in symbols], dtype=float)
        if not np.isfinite(vals).any() or np.nansum(vals) <= 0:
            vals = np.ones(len(symbols), dtype=float)
        vals = np.nan_to_num(vals, nan=np.nanmedian(vals[np.isfinite(vals)]) if np.isfinite(vals).any() else 1.0)
        vals = vals / vals.sum()
        return pd.Series(vals, index=symbols)
    s = pd.Series({sym: weights.get(sym, 0.0) for sym in symbols}, dtype=float)
    total = float(s.abs().sum())
    return s / total if total else pd.Series(np.ones(len(symbols)) / len(symbols), index=symbols)


def risk_decomposition(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    symbols = model["symbols"]
    w = portfolio_weights(symbols, payload).reindex(symbols).fillna(0.0).to_numpy(dtype=float)
    cov = model["cleaned_cov"]
    vals = model["eigenvalues"]
    vecs = model["eigenvectors"]
    k = model["k"]
    port_var = float(w @ cov @ w)
    port_vol = math.sqrt(max(port_var, 1e-16))
    ann = model_annualization(model, payload)
    factor_exposures = vecs[:, :k].T @ w
    factor_vars = vals[:k] * factor_exposures ** 2
    idio_var = float(np.sum(model["idio_var"] * w ** 2))
    total = max(float(factor_vars.sum() + idio_var), 1e-16)
    factor_rows = [
        {"component": f"PC{i+1}", "variance_contribution": float(factor_vars[i]), "pct_total_variance": float(factor_vars[i] / total * 100), "annualized_vol_contribution": float(math.sqrt(max(factor_vars[i], 0)) * math.sqrt(ann))}
        for i in range(k)
    ]
    factor_rows.append({"component": "Idiosyncratic", "variance_contribution": idio_var, "pct_total_variance": float(idio_var / total * 100), "annualized_vol_contribution": float(math.sqrt(max(idio_var, 0)) * math.sqrt(ann))})
    sigma_w = cov @ w
    mrc = w * sigma_w / max(port_vol, 1e-12)
    pos_rows = []
    sectors = model["sectors"]
    for i, ticker in enumerate(symbols):
        pc_drive = int(np.argmax(np.abs(vecs[i, :k] * factor_exposures))) + 1 if k else 1
        pos_rows.append({"ticker": ticker, "sector": sectors.get(ticker, "Unknown"), "weight": float(w[i]), "marginal_risk_contribution": float(mrc[i]), "pct_total_risk": float(mrc[i] / max(port_vol, 1e-12) * 100), "dominant_pc": f"PC{pc_drive}"})
    rets = model["returns"].reindex(columns=symbols).fillna(0.0).to_numpy(dtype=float)
    p_returns = rets @ w
    alpha = float(number_like((payload or {}).get("var_confidence"), 0.95) or 0.95)
    z = stats.norm.ppf(alpha)
    var_gauss = port_vol * z
    cvar_gauss = port_vol * stats.norm.pdf(z) / max(1 - alpha, 1e-6)
    hist_var = -float(np.nanquantile(p_returns, 1 - alpha)) if len(p_returns) else None
    hist_cvar = -float(np.nanmean(p_returns[p_returns <= np.nanquantile(p_returns, 1 - alpha)])) if len(p_returns) else None
    skew = float(stats.skew(p_returns, nan_policy="omit")) if len(p_returns) > 5 else 0.0
    kurt = float(stats.kurtosis(p_returns, fisher=True, nan_policy="omit")) if len(p_returns) > 5 else 0.0
    z_cf = z + (z * z - 1) * skew / 6 + (z ** 3 - 3 * z) * kurt / 24 - (2 * z ** 3 - 5 * z) * skew * skew / 36
    return {
        "portfolio_vol_daily": port_vol,
        "portfolio_vol_annualized": port_vol * math.sqrt(ann),
        "factor_rows": factor_rows,
        "position_rows": sorted(pos_rows, key=lambda r: abs(r["pct_total_risk"]), reverse=True),
        "var": {"confidence": alpha, "gaussian_var": var_gauss, "cornish_fisher_var": port_vol * z_cf, "gaussian_cvar": cvar_gauss, "historical_var": hist_var, "historical_cvar": hist_cvar},
        "portfolio_returns": pd.Series(p_returns, index=model["returns"].index),
        "factor_exposures": factor_exposures,
    }


def residual_matrix(model: dict[str, Any], k: int | None = None) -> pd.DataFrame:
    k = int(k or model["k"])
    rets = model["returns"].fillna(0.0)
    f = factor_returns(model, k)
    x = np.column_stack([np.ones(len(f)), f.to_numpy(dtype=float)])
    y = rets.to_numpy(dtype=float)
    beta = np.linalg.pinv(x.T @ x) @ x.T @ y
    resid = y - x @ beta
    return pd.DataFrame(resid, index=rets.index, columns=rets.columns)


def ou_signal_table(model: dict[str, Any], payload: dict[str, Any] | None = None) -> pd.DataFrame:
    payload = payload or {}
    resid = residual_matrix(model)
    # Volume-time adjustment (Avellaneda-Lee 2010)
    use_volume_time = bool(payload.get("volume_time", False))
    if use_volume_time:
        try:
            dv = dollar_volume_matrix(model["symbols"], lookback_days=model["lookback_days"]).reindex(resid.index).ffill()
            resid = volume_time_residuals(resid, dv)
        except Exception:
            pass  # Fall back to calendar-time residuals if data unavailable
    window = int(number_like(payload.get("ou_window"), 126) or 126)
    entry = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    max_half_life = float(number_like(payload.get("max_half_life"), 60.0) or 60.0)
    sectors = model["sectors"]
    rows = []
    for ticker in resid.columns:
        x = resid[ticker].tail(window).cumsum().dropna().to_numpy(dtype=float)
        if len(x) < 25 or np.nanstd(x) <= 0:
            continue
        y = x[1:]
        lag = x[:-1]
        design = np.column_stack([np.ones(len(lag)), lag])
        a, b = np.linalg.lstsq(design, y, rcond=None)[0]
        b = float(np.clip(b, 1e-6, 0.999999))
        kappa = -math.log(b)
        mu = float(a / (1 - b)) if abs(1 - b) > 1e-8 else float(np.mean(x))
        err = y - (a + b * lag)
        zeta = float(np.std(err, ddof=1))
        sigma = zeta * math.sqrt(max(2 * kappa / max(1 - math.exp(-2 * kappa), 1e-9), 1e-9))
        sigma_eq = sigma / math.sqrt(max(2 * kappa, 1e-9))
        zscore = float((x[-1] - mu) / max(sigma_eq, 1e-9))
        half_life = float(math.log(2) / max(kappa, 1e-9))
        # Standard errors on OU parameters (OLS SE from AR(1) regression)
        n_obs = len(y)
        resid_ols = err
        xtx_inv = np.linalg.pinv(design.T @ design)
        var_resid = float(np.var(resid_ols, ddof=2))
        se_b = float(math.sqrt(max(var_resid * xtx_inv[1, 1], 1e-12)))
        se_kappa = se_b / max(b, 1e-12)  # delta method: SE(kappa) ≈ SE(b) / b
        # Break-even Z: smallest |z| at which expected half-reversion PnL covers 1bp cost
        breakeven_z = float(1.0 / max(sigma_eq * math.sqrt(max(half_life, 0.5)), 1e-9) * 1e-4)
        direction = "Long" if zscore < -entry else "Short" if zscore > entry else "No Signal"
        viable = direction != "No Signal" and half_life <= max_half_life
        z_path = (x - mu) / max(sigma_eq, 1e-9)
        active_path = np.abs(z_path) >= entry
        days_since_trigger = 0
        for is_active in active_path[::-1]:
            if not is_active:
                break
            days_since_trigger += 1
        rows.append({"ticker": ticker, "sector": sectors.get(ticker, "Unknown"), "residual_z": zscore, "ou_half_life_days": half_life, "kappa": kappa, "mu": mu, "sigma_eq": sigma_eq, "se_kappa": se_kappa, "se_b": se_b, "breakeven_z": breakeven_z, "direction": direction, "economically_viable": bool(viable), "estimated_days_to_half_reversion": half_life, "days_since_signal_trigger": days_since_trigger if direction != "No Signal" else 0, "volume_time_adjusted": use_volume_time})
    return pd.DataFrame(rows).sort_values("residual_z", key=lambda s: s.abs(), ascending=False)


def rolling_pca_metrics(payload: dict[str, Any] | None = None, windows: tuple[int, ...] = (21, 63, 126, 252)) -> pd.DataFrame:
    ctx = load_context(payload)
    rets = ctx["returns"]
    rows: list[dict[str, Any]] = []
    for w in windows:
        if len(rets) < w + 5:
            continue
        step = max(1, int(w // 8))
        prior_vec = None
        prior_loading_matrix = None
        series: list[float] = []
        k_used = int(ctx.get("payload", {}).get("k") or 3)
        for end in range(w, len(rets) + 1, step):
            sample = rets.iloc[end - w: end]
            cov, _ = covariance_estimator(sample, (payload or {}).get("covariance_estimator", "ledoit_wolf"))
            vals, vecs = eig_sorted(cov)
            pc1 = float(vals[0] / max(vals.sum(), 1e-12))
            cos = abs(float(vecs[:, 0] @ prior_vec)) if prior_vec is not None else 1.0
            # Principal angles between consecutive loading subspaces
            if prior_loading_matrix is not None and prior_loading_matrix.shape == vecs[:, :k_used].shape:
                try:
                    angles = subspace_principal_angles(prior_loading_matrix, vecs[:, :k_used])
                    max_principal_angle = float(np.degrees(angles[-1]))
                except Exception:
                    max_principal_angle = 0.0
            else:
                max_principal_angle = 0.0
            series.append(pc1)
            row = {"date": sample.index[-1], "window": w, "pc1_share": pc1, "pc1_cosine_stability": cos, "effective_dimensions": float((vals.sum() ** 2) / max(np.sum(vals ** 2), 1e-12)), "eigen_ratio_k": int(np.argmax(vals[:-1] / np.maximum(vals[1:], 1e-12)) + 1) if len(vals) > 2 else 1, "max_principal_angle_deg": max_principal_angle}
            for pc_idx in range(min(5, len(vals))):
                row[f"eigenvalue_pc{pc_idx + 1}"] = float(vals[pc_idx])
                if prior_loading_matrix is not None and pc_idx < prior_loading_matrix.shape[1]:
                    row[f"cosine_pc{pc_idx + 1}"] = abs(float(vecs[:, pc_idx] @ prior_loading_matrix[:, pc_idx]))
                else:
                    row[f"cosine_pc{pc_idx + 1}"] = 1.0
            rows.append(row)
            prior_vec = vecs[:, 0]
            prior_loading_matrix = vecs[:, :k_used]
        if series:
            arr = np.asarray(series)
            mean = float(arr.mean())
            std = float(arr.std(ddof=1) or 1.0)
            for r in rows:
                if r["window"] == w:
                    r["pc1_zscore"] = float((r["pc1_share"] - mean) / std)
    return pd.DataFrame(rows)


def cusum_table(series: pd.Series) -> list[dict[str, Any]]:
    x = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if len(x) < 5:
        return []
    centered = x - x.mean()
    s = x.std(ddof=1) or 1.0
    vals = np.abs(np.cumsum(centered)) / (s * math.sqrt(len(x)))
    return [{"index": i, "cusum": float(v), "critical_90": 1.224, "critical_95": 1.358, "critical_99": 1.628, "break": bool(v > 1.358)} for i, v in enumerate(vals)]


def optimize_portfolio(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = model["symbols"]
    cov = model["cleaned_cov"]
    n = len(symbols)
    ann = model_annualization(model, payload)
    ann = model_annualization(model, payload)
    # Black-Litterman posterior or plain historical mean
    bl_views = payload.get("bl_views") or []
    w_market = np.array([model["market_caps"].get(s, 1.0) for s in symbols], dtype=float)
    w_market /= max(w_market.sum(), 1e-12)
    if bl_views:
        mu = black_litterman_posterior(cov, w_market, bl_views, symbols)
    else:
        mu = model["returns"].mean().reindex(symbols).fillna(0.0).to_numpy(dtype=float) * ann

    objective_type = str(payload.get("objective") or "mean_variance").lower()

    # ERC / Risk Parity
    if objective_type in {"erc", "risk_parity", "equal_risk_contribution"}:
        risk_budgets_raw = payload.get("risk_budgets")
        rb = np.array([float(risk_budgets_raw.get(s, 1.0 / n)) for s in symbols], dtype=float) if isinstance(risk_budgets_raw, dict) else None
        if rb is not None:
            rb = rb / rb.sum()
        w = erc_portfolio(cov, symbols, rb)
        status = "erc_spinu"
    # Max Sharpe
    elif objective_type in {"max_sharpe", "msp", "maximum_sharpe"}:
        rf = float(number_like(payload.get("risk_free_rate"), 0.0) or 0.0)
        max_w = float(number_like(payload.get("max_weight"), 0.12) or 0.12)
        w = max_sharpe_portfolio(cov, mu, rf=rf, max_weight=max_w)
        status = "max_sharpe"
    else:
        # Default: mean-variance via cvxpy or closed-form GMVP
        if cp is None:
            inv = np.linalg.pinv(cov)
            w = inv @ np.ones(n)
            w = np.maximum(w, 0)
            w = w / max(w.sum(), 1e-12)
            status = "cvxpy_unavailable_closed_form_gmvp"
        else:
            w_var = cp.Variable(n)
            risk_aversion = float(number_like(payload.get("risk_aversion"), 5.0) or 5.0)
            objective = cp.Minimize(cp.quad_form(w_var, cov) - (1.0 / max(risk_aversion, 1e-6)) * mu @ w_var)
            constraints: list = [cp.sum(w_var) == 1]
            if bool(payload.get("long_short", False)):
                constraints.append(cp.norm1(w_var) <= float(number_like(payload.get("gross_limit"), 2.0) or 2.0))
            else:
                constraints += [w_var >= 0, w_var <= float(number_like(payload.get("max_weight"), 0.12) or 0.12)]
            # Turnover constraint
            w_prev_raw = payload.get("previous_weights") or {}
            to_max = float(number_like(payload.get("turnover_max"), 1.0) or 1.0)
            if isinstance(w_prev_raw, dict) and w_prev_raw and to_max < 1.0:
                w_prev = np.array([float(w_prev_raw.get(s, 0.0)) for s in symbols], dtype=float)
                w_prev /= max(w_prev.sum(), 1e-12)
                constraints.append(cp.norm1(w_var - w_prev) <= 2 * to_max)
            problem = cp.Problem(objective, constraints)
            try:
                problem.solve(solver=cp.OSQP, warm_start=True, verbose=False)
                w = np.asarray(w_var.value, dtype=float)
                status = str(problem.status)
            except Exception:
                inv = np.linalg.pinv(cov)
                w = inv @ np.ones(n)
                w = np.maximum(w, 0)
                w = w / max(w.sum(), 1e-12)
                status = "fallback_gmvp"

    w = np.nan_to_num(w, nan=0.0)
    if abs(w.sum()) > 1e-12:
        w = w / w.sum()
    frontier = _efficient_frontier_qp(cov, mu, ann, payload, points=int(payload.get("frontier_points") or 100))
    weights = [{"ticker": symbols[i], "weight": float(w[i]), "sector": model["sectors"].get(symbols[i], "Unknown")} for i in np.argsort(np.abs(w))[::-1]]
    return {"status": status, "weights": weights, "frontier": frontier, "expected_return": float(w @ mu), "annualized_vol": float(math.sqrt(max(w @ cov @ w, 0)) * math.sqrt(ann)), "objective": objective_type}


def _efficient_frontier_qp(cov: np.ndarray, mu: np.ndarray, ann: float, payload: dict[str, Any], points: int = 100) -> list[dict[str, Any]]:
    n = len(mu)
    points = max(10, min(int(points), 150))
    lambdas = np.logspace(-3, 4, points)
    rows = []
    if cp is None:
        inv = np.linalg.pinv(cov)
        ones = np.ones(n)
        a = float(ones @ inv @ ones)
        b = float(ones @ inv @ mu)
        for lam in lambdas:
            weights = inv @ (mu / (2 * lam) + ((1 - b / (2 * lam)) / max(a, 1e-12)) * ones)
            rows.append({"risk": float(np.sqrt(max(weights @ cov @ weights, 0)) * np.sqrt(ann)), "return": float(weights @ mu), "lambda": float(lam), "status": "closed_form_unconstrained"})
        return rows
    weights = cp.Variable(n)
    lam_param = cp.Parameter(nonneg=True)
    objective = cp.Maximize(mu @ weights - lam_param * cp.quad_form(weights, cp.psd_wrap(cov)))
    constraints = [cp.sum(weights) == 1]
    if payload.get("long_short", False):
        constraints.append(cp.norm1(weights) <= float(payload.get("gross_limit", 2.0)))
    else:
        constraints.extend([weights >= 0, weights <= float(payload.get("max_weight", 0.12))])
    problem = cp.Problem(objective, constraints)
    for lam in lambdas:
        lam_param.value = float(lam)
        try:
            problem.solve(solver=cp.CLARABEL, warm_start=True, verbose=False)
        except Exception:
            try:
                problem.solve(solver=cp.SCS, warm_start=True, verbose=False)
            except Exception:
                continue
        if weights.value is None:
            continue
        current = np.asarray(weights.value, dtype=float).reshape(-1)
        rows.append({"risk": float(np.sqrt(max(current @ cov @ current, 0)) * np.sqrt(ann)), "return": float(current @ mu), "lambda": float(lam), "status": str(problem.status)})
    return rows


def bootstrap_validation(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    mode = parse_compute_mode(payload)
    b = int(number_like(payload.get("bootstrap_runs"), 80 if mode == "research" else 30) or 30)
    b = min(b, 250 if mode == "research" else 60)
    bootstrap_type = str(payload.get("bootstrap_type") or "case").lower()
    confidence = float(number_like(payload.get("confidence_level"), 0.90) or 0.90)
    confidence = confidence / 100.0 if confidence > 1 else confidence
    confidence = float(np.clip(confidence, 0.50, 0.999))
    tail = 50.0 * (1.0 - confidence)
    block_length = int(number_like(payload.get("block_length"), 21) or 21)
    rng = np.random.default_rng(7)
    rets = model["returns"]
    x = rets.to_numpy(dtype=float)
    k = model["k"]
    evals_list: list[np.ndarray] = []
    cosines: list[list[float]] = [[] for _ in range(k)]
    angle_samples: list[np.ndarray] = []
    full_subspace = model["eigenvectors"][:, :k]
    fitted = x @ full_subspace @ full_subspace.T
    residuals = x - fitted
    for _ in range(b):
        if bootstrap_type == "residual":
            idx = rng.integers(0, len(x), len(x))
            sample_x = fitted + residuals[idx]
            sample = pd.DataFrame(sample_x, columns=rets.columns)
        elif bootstrap_type == "block":
            sample_x = block_bootstrap_sample(x, block_length=block_length, rng=rng)
            sample = pd.DataFrame(sample_x, columns=rets.columns)
        else:
            idx = rng.integers(0, len(x), len(x))
            sample = pd.DataFrame(x[idx], columns=rets.columns)
        cov, _ = covariance_estimator(sample, model["cov_meta"].get("estimator", "ledoit_wolf"))
        vals, vecs = eig_sorted(cov)
        evals_list.append(vals[: len(model["eigenvalues"])])
        for j in range(k):
            cosines[j].append(abs(float(model["eigenvectors"][:, j] @ vecs[:, j])))
        try:
            angle_samples.append(np.degrees(subspace_principal_angles(full_subspace, vecs[:, :k])))
        except Exception:
            pass
    e = np.asarray(evals_list)
    bands = []
    for j in range(e.shape[1]):
        low = float(np.percentile(e[:, j], tail))
        high = float(np.percentile(e[:, j], 100.0 - tail))
        bands.append({"component": f"PC{j+1}", "eigenvalue": float(model["eigenvalues"][j]), "ci_low": low, "ci_high": high, "confidence_level": confidence, "mp_lambda_max": float(model["mp"]["lambda_max"]), "verdict": "robust" if low > model["mp"]["lambda_max"] else "marginal" if high > model["mp"]["lambda_max"] else "noise"})
    scorecard = []
    for j in range(k):
        vals_arr = np.asarray(cosines[j])
        scorecard.append({"component": f"PC{j+1}", "cosine_mean": float(vals_arr.mean()), "cosine_p05": float(np.percentile(vals_arr, 5)), "verdict": "Statistically Robust" if vals_arr.mean() > 0.9 and np.percentile(vals_arr, 5) > 0.8 else "Marginal" if vals_arr.mean() > 0.7 else "Potentially Spurious"})
    # Subsampling stability (distinct from bootstrap)
    sub_stability = subsampling_stability(model, n_subsamples=min(50, b), rng_seed=42)
    principal_angles = []
    if angle_samples:
        arr = np.vstack(angle_samples)
        for j in range(arr.shape[1]):
            principal_angles.append(
                {
                    "component": f"Angle{j+1}",
                    "mean_angle_degrees": float(np.mean(arr[:, j])),
                    "p95_angle_degrees": float(np.percentile(arr[:, j], 95)),
                    "max_angle_degrees": float(np.max(arr[:, j])),
                }
            )
    return {"bootstrap_bands": bands, "genuineness_scorecard": scorecard, "bootstrap_runs": b, "bootstrap_type": bootstrap_type, "confidence_level": confidence, "subsampling_stability": sub_stability, "principal_angles": principal_angles}


def residual_contagion(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    resid = residual_matrix(model)
    window = int(number_like(payload.get("residual_window"), 63) or 63)
    r = resid.tail(window)
    corr = r.corr().fillna(0.0)
    vals, _ = eig_sorted(corr.to_numpy(dtype=float))
    sectors = model["sectors"]
    group_rows = []
    for sector in sorted(set(sectors.values())):
        cols = [s for s in corr.columns if sectors.get(s) == sector]
        if len(cols) < 2:
            continue
        c = corr.loc[cols, cols].to_numpy(dtype=float)
        group_rows.append({"group": sector, "avg_pairwise_residual_corr": float(c[np.triu_indices_from(c, 1)].mean()), "asset_count": len(cols)})
    pairs = []
    arr = corr.to_numpy(dtype=float)
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append({"pair": f"{cols[i]} / {cols[j]}", "ticker_a": cols[i], "ticker_b": cols[j], "sector_a": sectors.get(cols[i], "Unknown"), "sector_b": sectors.get(cols[j], "Unknown"), "residual_corr": float(arr[i, j]), "same_sector": sectors.get(cols[i]) == sectors.get(cols[j])})
    pairs = sorted(pairs, key=lambda x: abs(x["residual_corr"]), reverse=True)[:80]
    under = []
    for kk in range(1, min(12, model["returns"].shape[1] - 1, len(model["eigenvalues"])) + 1):
        rr = residual_matrix(model, kk).tail(window).corr().fillna(0.0).to_numpy(dtype=float)
        upper = rr[np.triu_indices_from(rr, 1)]
        ev, _ = eig_sorted(rr)
        under.append({"k": kk, "avg_abs_residual_corr": float(np.mean(np.abs(upper))), "lambda1_residual": float(ev[0])})
    return {"residual_corr": corr, "lambda1_residual": float(vals[0]), "group_rows": group_rows, "pairs": pairs, "under_specification": under}


def stress_scenarios(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    stds = f.std().replace(0, np.nan).fillna(1e-6).to_numpy(dtype=float)
    magnitude = float(number_like(payload.get("shock_sigma"), 2.0) or 2.0)
    exposures = model["eigenvectors"][:, : model["k"]].T @ w
    rows = []
    waterfall = {}
    for j in range(model["k"]):
        for sign in (1, -1):
            shock = np.zeros(model["k"])
            shock[j] = sign * magnitude * stds[j]
            asset_impacts = model["eigenvectors"][:, : model["k"]] @ shock
            pnl = float(w @ asset_impacts)
            label = f"PC{j+1} {'+' if sign > 0 else '-'}{magnitude:g}sigma"
            rows.append({"scenario": label, "component": f"PC{j+1}", "direction": "positive" if sign > 0 else "negative", "portfolio_pnl_pct": pnl, "shock_sigma": sign * magnitude, "factor_exposure": float(exposures[j])})
            waterfall[label] = sorted([{"ticker": model["symbols"][i], "pnl_contribution": float(w[i] * asset_impacts[i])} for i in range(len(w))], key=lambda r: r["pnl_contribution"])[:80]
    scen = pd.DataFrame(rows).sort_values("portfolio_pnl_pct")
    worst = scen.iloc[0].to_dict() if not scen.empty else {}
    q_hist = f / f.std().replace(0, np.nan)
    analogs = []
    if not scen.empty:
        target = np.zeros(model["k"])
        pc_idx = int(str(worst.get("component", "PC1")).replace("PC", "")) - 1
        target[pc_idx] = float(worst.get("shock_sigma", -magnitude))
        q_arr = q_hist.fillna(0.0).to_numpy(dtype=float)
        factor_corr = np.corrcoef(q_arr, rowvar=False)
        inv_factor_corr = np.linalg.pinv(np.atleast_2d(factor_corr) + np.eye(model["k"]) * 1e-8)
        delta = q_arr - target
        dist = np.einsum("ij,jk,ik->i", delta, inv_factor_corr, delta)
        for idx in np.argsort(dist)[:5]:
            lo, hi = max(0, idx - 30), min(len(model["returns"]), idx + 31)
            window_returns = model["returns"].iloc[lo:hi].to_numpy(dtype=float) @ w
            analogs.append({"date": str(pd.Timestamp(q_hist.index[idx]).date()), "mahalanobis_distance": float(math.sqrt(max(dist[idx], 0.0))), "realized_portfolio_return": float(model["returns"].iloc[idx].to_numpy(dtype=float) @ w), "window_60d_cumulative_return": float(np.prod(1.0 + window_returns) - 1.0)})
    current_factor_z = q_hist.iloc[-1].fillna(0.0) if len(q_hist) else pd.Series(dtype=float)
    for row in rows:
        j = int(row["component"].replace("PC", "")) - 1
        shock = float(row["shock_sigma"])
        hist_col = q_hist.iloc[:, j].dropna() if j < q_hist.shape[1] else pd.Series(dtype=float)
        row["current_factor_zscore"] = float(current_factor_z.iloc[j]) if j < len(current_factor_z) else None
        row["shock_historical_percentile"] = float((hist_col <= shock).mean() * 100.0) if len(hist_col) else None
    # Augmented stress VaR: combine 2K parametric + 10K MC from K-dim Gaussian factor dist
    losses_param = -scen["portfolio_pnl_pct"].to_numpy(dtype=float) if not scen.empty else np.array([])
    rng = np.random.default_rng(42)
    mc_factor_draws = rng.multivariate_normal(np.zeros(model["k"]), np.diag(stds ** 2), size=10_000)
    mc_asset_impacts = mc_factor_draws @ model["eigenvectors"][:, :model["k"]].T
    mc_pnls = mc_asset_impacts @ w
    losses_mc = -mc_pnls
    all_losses = np.concatenate([losses_param, losses_mc])
    stress_var = float(np.percentile(all_losses, 95)) if len(all_losses) else None
    stress_cvar = float(all_losses[all_losses >= stress_var].mean()) if stress_var is not None and np.any(all_losses >= stress_var) else stress_var
    # Historical worst-day scenarios
    hist_worst = historical_worst_day_scenarios(model, payload, n_worst=int(number_like(payload.get("n_worst_days"), 5) or 5))
    # Joint multi-PC shock
    joint_result = joint_scenario_pnl(model, payload) if payload.get("joint_shocks") else None
    return {"scenario_rows": rows, "worst_scenario": worst, "waterfall": waterfall, "analogs": analogs, "stress_var": stress_var, "stress_cvar": stress_cvar, "historical_worst_day_scenarios": hist_worst, "joint_scenario": joint_result}


def liquidity_outputs(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = model["symbols"]
    dv = dollar_volume_matrix(symbols, lookback_days=model["lookback_days"]).reindex(model["returns"].index).ffill()
    rets = model["returns"].reindex(columns=symbols).fillna(0.0)
    illiquidity_measure = str(payload.get("illiquidity_measure") or "amihud").lower()
    illiq_window = int(number_like(payload.get("illiquidity_window"), 21) or 21)

    # Branch on illiquidity measure
    if illiquidity_measure == "kyle_lambda":
        try:
            kyle = kyle_lambda_daily(symbols).reindex(rets.index).ffill()
            amihud = np.log1p(kyle * 1e6).rolling(illiq_window, min_periods=5).mean()
        except Exception:
            # Fallback to Amihud if Kyle's lambda data not available
            amihud_raw = (rets.abs() / dv.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
            amihud = np.log1p(amihud_raw * 1e9).rolling(illiq_window, min_periods=5).mean()
    elif illiquidity_measure == "pastor_stambaugh":
        try:
            mkt_ret = rets.mean(axis=1)  # equal-weight proxy for market return
            ps_gamma = pastor_stambaugh_gamma(rets, dv, mkt_ret, window=illiq_window)
            amihud = ps_gamma.rolling(illiq_window, min_periods=5).mean().reindex(columns=symbols).ffill()
        except Exception:
            amihud_raw = (rets.abs() / dv.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
            amihud = np.log1p(amihud_raw * 1e9).rolling(illiq_window, min_periods=5).mean()
    else:
        # Default: Amihud (2002)
        amihud_raw = (rets.abs() / dv.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        amihud = np.log1p(amihud_raw * 1e9).rolling(illiq_window, min_periods=5).mean()

    normalization = str(payload.get("illiquidity_normalization") or "standardize").lower()
    if normalization in {"rank", "rank_normalization", "percentile"}:
        z = amihud.rank(axis=1, pct=True).sub(0.5).fillna(0.0)
    elif normalization in {"log", "log_transform"}:
        z = np.log1p(amihud.clip(lower=0)).fillna(0.0)
    else:
        z = amihud.sub(amihud.mean(axis=1), axis=0).div(amihud.std(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    cov = np.cov(z.to_numpy(dtype=float), rowvar=False)
    vals, vecs = eig_sorted(cov)
    liq_factor = pd.Series(z.to_numpy(dtype=float) @ vecs[:, 0], index=z.index, name="latent_liquidity")
    dliq = liq_factor.diff().fillna(0.0).to_numpy(dtype=float)
    betas = []
    f1 = factor_returns(model, 1).iloc[:, 0].reindex(rets.index).fillna(0.0).to_numpy(dtype=float)
    x = np.column_stack([np.ones(len(dliq)), dliq, f1])
    xtx_inv = np.linalg.pinv(x.T @ x)
    for ticker in symbols:
        y = rets[ticker].to_numpy(dtype=float)
        beta = xtx_inv @ x.T @ y
        resid = y - x @ beta
        # Newey-West HAC standard errors (3 lags) instead of plain OLS SE
        se = newey_west_se(x, resid, coef_idx=1, n_lags=3)
        current_illiq = float(amihud[ticker].dropna().iloc[-1]) if not amihud[ticker].dropna().empty else None
        pct = float((amihud[ticker].dropna() <= current_illiq).mean() * 100) if current_illiq is not None else None
        betas.append({"ticker": ticker, "sector": model["sectors"].get(ticker, "Unknown"), "current_amihud": current_illiq, "amihud_percentile": pct, "liquidity_beta": float(beta[1]), "beta_se": float(se), "t_stat": float(beta[1] / max(se, 1e-12)), "illiquidity_measure": illiquidity_measure})
    betas = sorted(betas, key=lambda r: r["liquidity_beta"])
    w = portfolio_weights(symbols, payload).reindex(symbols).fillna(0.0)
    beta_map = pd.Series({r["ticker"]: r["liquidity_beta"] for r in betas})
    port_beta = float((w * beta_map.reindex(symbols).fillna(0.0)).sum())
    liq_var = float(np.var(dliq))
    standard = risk_decomposition(model, payload)
    port_value = float(number_like(payload.get("portfolio_value"), 1_000_000.0) or 1_000_000.0)
    adv = dv.tail(21).median().reindex(symbols).fillna(dv.median().median())
    vols = rets.tail(63).std().reindex(symbols).fillna(rets.std().median())
    liquidation = []
    for ticker in symbols:
        pos = abs(float(w.get(ticker, 0.0))) * port_value
        adv_i = max(float(adv.get(ticker, 1.0)), 1.0)
        vol_i = max(float(vols.get(ticker, 0.01)), 1e-6)
        participation_rate = float(np.clip(number_like(payload.get("adv_participation_rate"), 0.15) or 0.15, 0.01, 1.0))
        days = max(1.0, pos / max(participation_rate * adv_i, 1.0))
        cost_bps = vol_i * math.sqrt(max(pos / max(days * adv_i, 1.0), 0.0)) * 10000
        liquidation.append({"ticker": ticker, "position_value": pos, "adv": adv_i, "position_pct_adv": pos / adv_i, "adv_participation_rate": participation_rate, "days_to_liquidate": days, "estimated_cost_bps": cost_bps, "rating": "Red" if days > 5 or cost_bps > 20 else "Amber" if days > 1 or cost_bps > 5 else "Green"})
    quant_unwind_threshold = float(number_like(payload.get("quant_unwind_threshold"), 0.15) or 0.15)
    lavar = (standard["var"]["gaussian_var"] or 0.0) + sum(abs(float(w.get(r["ticker"], 0))) * r["estimated_cost_bps"] / 10000 for r in liquidation)
    quant_unwind_score = (port_beta * port_beta * liq_var) / max(standard["portfolio_vol_daily"] ** 2, 1e-12)
    beta_vec = beta_map.reindex(symbols).fillna(0.0).to_numpy(dtype=float)
    asset_var = np.maximum(np.diag(model["cleaned_cov"]), 1e-15)
    liq_corr = np.outer(beta_vec, beta_vec) * liq_var / np.sqrt(np.outer(asset_var, asset_var))
    liq_corr = pd.DataFrame(np.clip(liq_corr, -1.0, 1.0), index=symbols, columns=symbols)
    factor_rows = [dict(row) for row in standard["factor_rows"] if row.get("component") != "Idiosyncratic"]
    idio_row = next((dict(row) for row in standard["factor_rows"] if row.get("component") == "Idiosyncratic"), {"component": "Idiosyncratic", "variance_contribution": 0.0})
    augmented_rows = factor_rows + [{"component": "Liquidity", "variance_contribution": port_beta * port_beta * liq_var}, idio_row]
    current_liq_percentile = float((liq_factor.dropna() <= liq_factor.dropna().iloc[-1]).mean() * 100.0) if len(liq_factor.dropna()) else None
    top_idx = np.argsort(np.abs(w.to_numpy(dtype=float)))[-min(20, len(symbols)):]
    top_corr = liq_corr.to_numpy(dtype=float)[np.ix_(top_idx, top_idx)]
    avg_top_corr = float(np.mean(top_corr[np.triu_indices_from(top_corr, 1)])) if len(top_idx) > 1 else 0.0
    beta_threshold = float(number_like(payload.get("liquidity_beta_threshold"), 0.5) or 0.5)
    unwind_signals = {"liquidity_factor_above_p90": bool(current_liq_percentile is not None and current_liq_percentile >= 90), "top20_liquidity_corr_above_030": bool(avg_top_corr >= 0.30), "portfolio_beta_above_threshold": bool(abs(port_beta) >= beta_threshold)}
    return {"amihud_panel": z, "latent_liquidity": liq_factor, "liquidity_betas": betas, "portfolio_liquidity_beta": port_beta, "liquidity_variance_contribution": port_beta * port_beta * liq_var, "augmented_risk_decomposition": augmented_rows, "liquidity_driven_corr": liq_corr, "unwind_signals": unwind_signals, "unwind_signal_count": sum(unwind_signals.values()), "liquidity_factor_percentile": current_liq_percentile, "top20_liquidity_corr": avg_top_corr, "liquidation": sorted(liquidation, key=lambda r: r["estimated_cost_bps"], reverse=True), "lavar": lavar, "quant_unwind_score": quant_unwind_score, "quant_unwind_threshold": quant_unwind_threshold, "illiquidity_measure": illiquidity_measure, "illiquidity_normalization": normalization}


def metadata(model: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "symbols": model["symbols"],
        "n_assets": len(model["symbols"]),
        "n_observations": int(model["returns"].shape[0]),
        "date_start": str(pd.Timestamp(model["returns"].index.min()).date()) if len(model["returns"]) else None,
        "date_end": str(pd.Timestamp(model["returns"].index.max()).date()) if len(model["returns"]) else None,
        "k_selected": int(model["k"]),
        "k_criteria": model["k_info"],
        "mp": model["mp"],
        "covariance": model["cov_meta"],
        "frequency": model.get("frequency", "daily"),
        "annualization_factor": model_annualization(model),
        "data_sources": ["backend/data/market_universe.parquet", "backend/data/fundamentals/master_fundamentals.parquet", "factors/data/processed/category7_macro_regime.parquet"],
    }
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------
# Blend-gamma covariance reconstruction
# ---------------------------------------------------------------------------

def blend_covariance(model: dict[str, Any], blend_gamma: float = 0.0) -> np.ndarray:
    """Return a convex blend between the RMT-cleaned covariance (gamma=0)
    and the raw sample covariance (gamma=1).

    C_blend = (1 - gamma) * C_cleaned + gamma * C_sample

    Args:
        model: Output of rmt_model().
        blend_gamma: Float in [0, 1]. 0 = full RMT cleaning, 1 = raw sample cov.

    Returns:
        Blended covariance matrix as ndarray.
    """
    gamma = float(np.clip(blend_gamma, 0.0, 1.0))
    c_clean = model["cleaned_cov"]
    c_sample = model.get("raw_cov")
    if c_sample is None:
        c_sample = np.cov(model["returns"].to_numpy(dtype=float), rowvar=False)
    return (1.0 - gamma) * c_clean + gamma * c_sample


# ---------------------------------------------------------------------------
# CVXPY shadow prices (constraint dual values)
# ---------------------------------------------------------------------------

def optimize_portfolio_with_duals(
    model: dict[str, Any], payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Like optimize_portfolio() but also extracts CVXPY dual values.

    Returns the standard optimize_portfolio dict plus a 'shadow_prices' list.
    Each entry: {"constraint": <name>, "dual_value": <float>}.
    """
    payload = payload or {}
    opt = optimize_portfolio(model, payload)

    if cp is None:
        opt["shadow_prices"] = [{"constraint": "cvxpy_unavailable", "dual_value": None}]
        return opt

    symbols = model["symbols"]
    cov = model["cleaned_cov"]
    n = len(symbols)
    ann = model_annualization(model, payload)

    bl_views = payload.get("bl_views") or []
    w_market = np.array([model.get("market_caps", {}).get(s, 1.0) for s in symbols], dtype=float)
    w_market /= max(w_market.sum(), 1e-12)
    if bl_views:
        mu = black_litterman_posterior(cov, w_market, bl_views, symbols)
    else:
        mu = model["returns"].mean().reindex(symbols).fillna(0.0).to_numpy(dtype=float) * ann

    w_var = cp.Variable(n)
    risk_aversion = float(number_like(payload.get("risk_aversion"), 5.0) or 5.0)
    objective_cp = cp.Minimize(cp.quad_form(w_var, cov) - (1.0 / max(risk_aversion, 1e-6)) * mu @ w_var)

    constraints_named: list[tuple[str, Any]] = [("sum_to_one", cp.sum(w_var) == 1)]
    if bool(payload.get("long_short", False)):
        gross = float(number_like(payload.get("gross_limit"), 2.0) or 2.0)
        constraints_named.append(("gross_limit", cp.norm1(w_var) <= gross))
    else:
        max_w = float(number_like(payload.get("max_weight"), 0.12) or 0.12)
        constraints_named.append(("long_only", w_var >= 0))
        constraints_named.append(("max_weight", w_var <= max_w))

    w_prev_raw = payload.get("previous_weights") or {}
    to_max = float(number_like(payload.get("turnover_max"), 1.0) or 1.0)
    if isinstance(w_prev_raw, dict) and w_prev_raw and to_max < 1.0:
        w_prev = np.array([float(w_prev_raw.get(s, 0.0)) for s in symbols], dtype=float)
        w_prev /= max(w_prev.sum(), 1e-12)
        constraints_named.append(("turnover", cp.norm1(w_var - w_prev) <= 2 * to_max))

    prob = cp.Problem(objective_cp, [c for _, c in constraints_named])
    try:
        prob.solve(solver=cp.OSQP, warm_start=True, verbose=False)
    except Exception:
        pass

    shadow_prices = []
    for name, con in constraints_named:
        try:
            dv = con.dual_value
            shadow_prices.append({"constraint": name, "dual_value": float(dv) if dv is not None else None})
        except Exception:
            shadow_prices.append({"constraint": name, "dual_value": None})

    opt["shadow_prices"] = shadow_prices
    return opt


# ---------------------------------------------------------------------------
# Signal decay analysis (validates mean-reversion assumption)
# ---------------------------------------------------------------------------

def signal_decay_analysis(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    horizons: tuple[int, ...] = (1, 5, 10, 21, 42, 63),
) -> list[dict[str, Any]]:
    """For every ticker that ever had an active signal, compute the average
    residual Z-score at T+h days after signal generation (forward Z-score).

    Empirically validates whether the OU mean-reversion assumption holds.
    A truly mean-reverting residual should show Z decaying toward 0 as h grows.
    """
    payload = payload or {}
    resid = residual_matrix(model)
    entry_z = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    window = int(number_like(payload.get("ou_window"), 126) or 126)
    rows: list[dict[str, Any]] = []
    for ticker in resid.columns:
        z_series = resid[ticker].dropna()
        if len(z_series) < max(horizons) + window + 5:
            continue
        mu_r = z_series.rolling(window, min_periods=30).mean()
        sig_r = z_series.rolling(window, min_periods=30).std().replace(0, np.nan)
        zscores = ((z_series - mu_r) / sig_r).dropna()
        for direction, mask_fn in (
            ("Long", lambda z: z < -entry_z),
            ("Short", lambda z: z > entry_z),
        ):
            signal_dates = zscores.index[mask_fn(zscores)]
            if len(signal_dates) == 0:
                continue
            init_z_mean = float(zscores[signal_dates].mean())
            for h in horizons:
                fwd_z_vals = []
                for dt in signal_dates:
                    try:
                        pos = zscores.index.get_loc(dt)
                        if pos + h < len(zscores):
                            fwd_z_vals.append(float(zscores.iloc[pos + h]))
                    except Exception:
                        continue
                if fwd_z_vals:
                    avg_fwd = float(np.mean(fwd_z_vals))
                    rows.append({
                        "ticker": ticker,
                        "sector": model["sectors"].get(ticker, "Unknown"),
                        "signal_direction": direction,
                        "horizon_days": h,
                        "avg_z_at_horizon": avg_fwd,
                        "n_signals": len(signal_dates),
                        "mean_reverting": bool(
                            direction == "Long" and avg_fwd > init_z_mean
                            or direction == "Short" and avg_fwd < init_z_mean
                        ),
                    })
    return rows


def residual_ou_backtest(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Vectorized residual OU signal backtest with entry/exit thresholds and costs."""

    payload = payload or {}
    resid = residual_matrix(model).cumsum()
    window = int(number_like(payload.get("ou_window"), 126) or 126)
    entry_z = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    exit_z = float(number_like(payload.get("exit_z"), 0.25) or 0.25)
    cost_bps = float(number_like(payload.get("cost_bps"), 2.0) or 2.0)
    max_positions = int(number_like(payload.get("max_positions"), 20) or 20)
    returns = model["returns"].reindex(index=resid.index, columns=resid.columns).fillna(0.0)
    z = resid.sub(resid.rolling(window, min_periods=max(20, window // 4)).mean()).div(
        resid.rolling(window, min_periods=max(20, window // 4)).std().replace(0, np.nan)
    )
    raw_signal = pd.DataFrame(0.0, index=z.index, columns=z.columns)
    raw_signal[z < -entry_z] = 1.0
    raw_signal[z > entry_z] = -1.0
    raw_signal[z.abs() < exit_z] = 0.0
    signal = raw_signal.replace(0, np.nan).ffill().fillna(0.0)
    # Keep only strongest names each day.
    ranks = z.abs().rank(axis=1, ascending=False, method="first")
    signal = signal.where(ranks <= max_positions, 0.0)
    gross_exposure = signal.abs().sum(axis=1).replace(0, np.nan)
    weights = signal.div(gross_exposure, axis=0).fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    gross = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    costs = turnover * cost_bps / 10000.0
    net = gross - costs
    equity = (1.0 + net).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    ann_factor = model_annualization(model, payload)
    ann = math.sqrt(ann_factor)
    sharpe = float(net.mean() / max(net.std(ddof=1), 1e-12) * ann)
    gross_sharpe = float(gross.mean() / max(gross.std(ddof=1), 1e-12) * ann)
    rows = pd.DataFrame(
        {
            "date": net.index,
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": costs,
            "equity": equity,
            "drawdown": drawdown,
            "active_positions": weights.abs().gt(0).sum(axis=1),
        }
    )
    stats_row = {
        "gross_sharpe": gross_sharpe,
        "net_sharpe": sharpe,
        "annualized_return": float(net.mean() * ann_factor),
        "annualized_vol": float(net.std(ddof=1) * ann),
        "max_drawdown": float(drawdown.min()),
        "hit_rate": float((net > 0).mean()),
        "avg_daily_turnover": float(turnover.mean()),
        "total_cost": float(costs.sum()),
        "average_holding_period_days": _average_signal_holding_period(signal),
        "entry_z": entry_z,
        "exit_z": exit_z,
        "cost_bps": cost_bps,
    }
    return {"equity_curve": rows, "stats": stats_row}


def _average_signal_holding_period(signal: pd.DataFrame) -> float | None:
    durations = []
    for column in signal:
        active = signal[column].ne(0).to_numpy()
        start = None
        for idx, value in enumerate(active):
            if value and start is None:
                start = idx
            elif not value and start is not None:
                durations.append(idx - start)
                start = None
        if start is not None:
            durations.append(len(active) - start)
    return float(np.mean(durations)) if durations else None


def bai_perron_breakpoints(
    series: pd.Series,
    max_breaks: int = 3,
    min_segment: int = 20,
) -> list[dict[str, Any]]:
    """Dynamic-programming multiple mean-break search with BIC selection."""

    x = pd.to_numeric(series, errors="coerce").dropna()
    n = len(x)
    if n < min_segment * 2:
        return []
    values = x.to_numpy(dtype=float)

    def sse(i: int, j: int) -> float:
        seg = values[i:j]
        if len(seg) == 0:
            return 0.0
        return float(np.sum((seg - seg.mean()) ** 2))

    candidates: list[tuple[int, list[int], float]] = []
    for breaks in range(0, max_breaks + 1):
        if breaks == 0:
            candidates.append((0, [], sse(0, n)))
            continue
        best = ([], float("inf"))

        def search(start: int, chosen: list[int]):
            nonlocal best
            remaining = breaks - len(chosen)
            if remaining == 0:
                points = [0] + chosen + [n]
                total = sum(sse(points[k], points[k + 1]) for k in range(len(points) - 1))
                if total < best[1]:
                    best = (chosen.copy(), total)
                return
            latest = n - remaining * min_segment
            for bp in range(start + min_segment, latest + 1):
                search(bp, chosen + [bp])

        search(0, [])
        candidates.append((breaks, best[0], best[1]))
    scored = []
    for k, points, loss in candidates:
        bic = n * math.log(max(loss / n, 1e-12)) + (k + 1) * math.log(n)
        scored.append((bic, k, points, loss))
    bic, k, points, loss = min(scored, key=lambda item: item[0])
    rows = []
    all_points = [0] + points + [n]
    for idx, bp in enumerate(points):
        before = values[all_points[idx] : bp]
        after = values[bp : all_points[idx + 2]]
        rows.append(
            {
                "break_index": int(bp),
                "break_date": str(pd.Timestamp(x.index[bp]).date()) if hasattr(x.index[bp], "date") else str(x.index[bp]),
                "mean_before": float(before.mean()) if len(before) else None,
                "mean_after": float(after.mean()) if len(after) else None,
                "selected_break_count": int(k),
                "bic": float(bic),
                "segment_sse": float(loss),
            }
        )
    return rows


def tensor_hosvd_proxy(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    windows: tuple[int, ...] = (21, 63, 126, 252),
) -> dict[str, Any]:
    """HOSVD/Tucker decomposition of eigenvalue-share tensor K x W x T."""

    payload = payload or {}
    rets = model["returns"]
    k = min(int(payload.get("tensor_k") or model["k"] or 3), 8, rets.shape[1])
    step = int(payload.get("tensor_step") or 21)
    time_points = []
    tensors = []
    max_w = max(windows)
    for end in range(max_w, len(rets) + 1, step):
        date = rets.index[end - 1]
        slice_kw = np.zeros((k, len(windows)))
        for wi, w in enumerate(windows):
            sample = rets.iloc[end - w : end]
            cov, _ = covariance_estimator(sample, (payload or {}).get("covariance_estimator", "ledoit_wolf"))
            vals, _ = eig_sorted(cov)
            total = max(float(vals.sum()), 1e-12)
            slice_kw[:, wi] = vals[:k] / total
        tensors.append(slice_kw)
        time_points.append(date)
    if not tensors:
        return {"core_records": [], "factor_singular_values": [], "window_singular_values": [], "time_singular_values": []}
    arr = np.stack(tensors, axis=2)  # K x W x T
    unfold_factor = arr.reshape(k, -1)
    unfold_window = np.moveaxis(arr, 1, 0).reshape(len(windows), -1)
    unfold_time = np.moveaxis(arr, 2, 0).reshape(len(time_points), -1)
    uf, sf, _ = np.linalg.svd(unfold_factor, full_matrices=False)
    uw, sw, _ = np.linalg.svd(unfold_window, full_matrices=False)
    ut, st, _ = np.linalg.svd(unfold_time, full_matrices=False)
    rf = min(3, uf.shape[1])
    rw = min(3, uw.shape[1])
    rt = min(4, ut.shape[1])
    core = np.einsum("ia,jb,kc,ijk->abc", uf[:, :rf], uw[:, :rw], ut[:, :rt], arr)
    core_records = []
    for a in range(core.shape[0]):
        for b in range(core.shape[1]):
            for c in range(core.shape[2]):
                core_records.append({"factor_mode": a + 1, "window_mode": b + 1, "time_mode": c + 1, "value": float(core[a, b, c])})
    return {
        "core_records": core_records,
        "factor_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(sf[:8])],
        "window_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(sw[: len(windows)])],
        "time_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(st[:10])],
        "dates": [str(pd.Timestamp(d).date()) for d in time_points],
    }


def residual_tensor_hosvd(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    windows: tuple[int, ...] = (21, 63, 126, 252),
) -> dict[str, Any]:
    """HOSVD/Tucker decomposition of residual-correlation tensors.

    Tensor dimensions are residual group x window length x time. Each cell is
    the average pairwise residual correlation for one sector/group at a rolling
    date. This is the Feature 08 tensor monitor, using actual residual
    correlations rather than the previous K-diagnostic proxy.
    """

    payload = payload or {}
    resid = residual_matrix(model)
    groups: dict[str, list[str]] = {}
    for ticker in resid.columns:
        groups.setdefault(model["sectors"].get(ticker, "Unknown"), []).append(ticker)
    groups = {name: cols for name, cols in groups.items() if len(cols) >= 2}
    if not groups:
        return {"core_records": [], "group_singular_values": [], "window_singular_values": [], "time_singular_values": [], "summary": []}

    max_steps = int(number_like(payload.get("residual_tensor_max_dates"), 80) or 80)
    min_window = min(windows)
    if len(resid) < min_window + 5:
        return {"core_records": [], "group_singular_values": [], "window_singular_values": [], "time_singular_values": [], "summary": []}
    step = max(1, int((len(resid) - min_window) / max(max_steps, 1)))
    date_ends = list(range(min_window, len(resid) + 1, step))[:max_steps]
    group_names = sorted(groups)
    tensor = np.zeros((len(group_names), len(windows), len(date_ends)), dtype=float)

    for t_idx, end in enumerate(date_ends):
        for w_idx, window in enumerate(windows):
            if end < window:
                continue
            sub = resid.iloc[end - window : end]
            for g_idx, group in enumerate(group_names):
                corr = sub[groups[group]].corr().fillna(0.0).to_numpy(dtype=float)
                upper = corr[np.triu_indices_from(corr, 1)]
                tensor[g_idx, w_idx, t_idx] = float(np.mean(upper)) if len(upper) else 0.0

    centered = tensor - tensor.mean(axis=2, keepdims=True)
    ug, sg, _ = np.linalg.svd(centered.reshape(len(group_names), -1), full_matrices=False)
    uw, sw, _ = np.linalg.svd(np.moveaxis(centered, 1, 0).reshape(len(windows), -1), full_matrices=False)
    ut, st, _ = np.linalg.svd(np.moveaxis(centered, 2, 0).reshape(len(date_ends), -1), full_matrices=False)
    rg = min(4, ug.shape[1])
    rw = min(4, uw.shape[1])
    rt = min(6, ut.shape[1])
    core = np.einsum("ia,jb,kc,ijk->abc", ug[:, :rg], uw[:, :rw], ut[:, :rt], centered)

    core_records = []
    for a in range(core.shape[0]):
        for b in range(core.shape[1]):
            for c in range(core.shape[2]):
                core_records.append({"group_mode": a + 1, "window_mode": b + 1, "time_mode": c + 1, "value": float(core[a, b, c])})

    summary = []
    for g_idx, group in enumerate(group_names):
        current = float(tensor[g_idx, :, -1].mean()) if tensor.shape[2] else 0.0
        history = tensor[g_idx].reshape(-1)
        pct = float(np.mean(history <= current) * 100) if len(history) else 0.0
        summary.append({"group": group, "current_avg_residual_corr": current, "percentile": pct})

    return {
        "core_records": core_records,
        "group_singular_values": [{"group": group_names[i], "singular_value": float(v)} for i, v in enumerate(sg[: len(group_names)])],
        "window_singular_values": [{"window": int(windows[i]), "singular_value": float(v)} for i, v in enumerate(sw[: len(windows)])],
        "time_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(st[:10])],
        "dates": [str(pd.Timestamp(resid.index[end - 1]).date()) for end in date_ends],
        "summary": sorted(summary, key=lambda r: abs(r["current_avg_residual_corr"]), reverse=True),
    }


def robust_frontier_ellipsoidal(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Bertsimas-Brown-style ellipsoidal uncertainty penalty frontier."""

    payload = payload or {}
    symbols = model["symbols"]
    cov = model["cleaned_cov"]
    n = len(symbols)
    ann = model_annualization(model, payload)
    mu = model["returns"].mean().reindex(symbols).fillna(0.0).to_numpy(dtype=float) * ann
    gamma = float(number_like(payload.get("robust_gamma"), 1.0) or 1.0)
    max_w = float(number_like(payload.get("max_weight"), 0.12) or 0.12)
    diag_unc = np.diag(np.maximum(np.diag(cov), 1e-12)) * gamma
    rows = []
    if cp is not None:
        w = cp.Variable(n)
        u_sqrt = np.sqrt(np.diag(diag_unc))
        constraints = [cp.sum(w) == 1, w >= 0, w <= max_w]
        for lam in np.linspace(1.0, 20.0, 30):
            objective = cp.Maximize(mu @ w - float(lam) * cp.quad_form(w, cov) - cp.norm(cp.multiply(u_sqrt, w), 2))
            prob = cp.Problem(objective, constraints)
            try:
                prob.solve(solver=cp.CLARABEL, verbose=False)
            except Exception:
                try:
                    prob.solve(solver=cp.SCS, verbose=False)
                except Exception:
                    continue
            if w.value is None:
                continue
            ww = np.maximum(np.asarray(w.value, dtype=float), 0.0)
            ww = ww / max(ww.sum(), 1e-12)
            rows.append(
                {
                    "risk": float(math.sqrt(max(ww @ cov @ ww, 0.0)) * math.sqrt(ann)),
                    "return": float(ww @ mu),
                    "robust_penalty": float(np.linalg.norm(u_sqrt * ww)),
                    "lambda": float(lam),
                    "frontier": "robust_ellipsoidal",
                }
            )
    if rows:
        return rows
    # deterministic fallback: diagonal uncertainty-augmented covariance
    cov_r = cov + diag_unc
    inv = np.linalg.pinv(cov_r)
    for lam in np.linspace(0.0, 1.0, 30):
        raw = (1 - lam) * (inv @ np.ones(n)) + lam * np.maximum(inv @ mu, 0)
        raw = np.maximum(raw, 0)
        ww = raw / max(raw.sum(), 1e-12)
        rows.append({"risk": float(math.sqrt(max(ww @ cov @ ww, 0.0)) * math.sqrt(ann)), "return": float(ww @ mu), "robust_penalty": float(math.sqrt(max(ww @ diag_unc @ ww, 0.0))), "lambda": float(lam), "frontier": "robust_diagonal_uncertainty_fallback"})
    return rows


def stress_pdf_report_base64(model: dict[str, Any], stress: dict[str, Any]) -> str | None:
    """Generate compact PDF report as base64 when reportlab is available."""

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        return None
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 54
    c.setFont("Helvetica-Bold", 16)
    c.drawString(54, y, "PCA V2 Stress Scenario Report")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(54, y, f"Assets: {len(model['symbols'])} | Observations: {model['returns'].shape[0]} | K: {model['k']}")
    y -= 22
    worst = stress.get("worst_scenario") or {}
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Worst Scenario")
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawString(54, y, f"{worst.get('scenario')} | P&L: {worst.get('portfolio_pnl_pct')}")
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Stress VaR / CVaR")
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawString(54, y, f"VaR: {stress.get('stress_var')} | CVaR: {stress.get('stress_cvar')}")
    y -= 24
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Top Historical Analogs")
    y -= 16
    c.setFont("Helvetica", 8)
    for row in (stress.get("analogs") or [])[:8]:
        c.drawString(54, y, f"{row.get('date')}  distance={row.get('distance')}  realized={row.get('realized_portfolio_return')}")
        y -= 12
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Scenario Table")
    y -= 14
    c.setFont("Helvetica", 8)
    for row in (stress.get("scenario_rows") or [])[:28]:
        c.drawString(54, y, f"{row.get('scenario')}: {row.get('portfolio_pnl_pct')}")
        y -= 10
        if y < 72:
            c.showPage()
            y = height - 54
            c.setFont("Helvetica", 8)
    c.save()
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# MLE OU estimation (full exact discrete-time log-likelihood)
# ---------------------------------------------------------------------------

def ou_mle(x: np.ndarray, dt: float = 1.0 / 252) -> dict[str, float]:
    """Estimate OU parameters {kappa, mu, sigma} by exact discrete-time MLE.

    The discrete-time OU transition density is Gaussian:
        mean_t = mu + (x_{t-1} - mu) * exp(-kappa * dt)
        var_t  = sigma^2 * (1 - exp(-2*kappa*dt)) / (2*kappa)

    Warm-started from the OLS AR(1) solution. Uses scipy L-BFGS-B.
    """
    from scipy.optimize import minimize as _minimize

    x = np.asarray(x, dtype=float)
    if len(x) < 10:
        return {"kappa": float("nan"), "mu": float("nan"), "sigma": float("nan"),
                "half_life_days": float("nan"), "log_likelihood": float("nan")}

    y, lag = x[1:], x[:-1]

    def neg_loglik(params: np.ndarray) -> float:
        kappa_, mu_, log_sigma_ = params
        kappa_ = max(kappa_, 1e-6)
        sigma_ = math.exp(log_sigma_)
        e_kdt = math.exp(-kappa_ * dt)
        cond_mean = mu_ + (lag - mu_) * e_kdt
        cond_var = max(sigma_ ** 2 * (1.0 - math.exp(-2.0 * kappa_ * dt)) / (2.0 * kappa_), 1e-12)
        residuals = y - cond_mean
        n = len(residuals)
        return 0.5 * n * math.log(2 * math.pi * cond_var) + 0.5 * float(np.sum(residuals ** 2)) / cond_var

    # OLS warm start
    design = np.column_stack([np.ones(len(lag)), lag])
    a_ols, b_ols = np.linalg.lstsq(design, y, rcond=None)[0]
    b_ols = float(np.clip(b_ols, 1e-6, 0.999999))
    kappa0 = max(-math.log(b_ols) / dt, 1e-4)
    mu0 = float(a_ols / (1 - b_ols)) if abs(1 - b_ols) > 1e-8 else float(np.mean(x))
    sigma0 = float(np.std(y - (a_ols + b_ols * lag), ddof=1))

    try:
        res = _minimize(
            neg_loglik,
            x0=[kappa0, mu0, math.log(max(sigma0, 1e-8))],
            method="L-BFGS-B",
            bounds=[(1e-6, 500.0), (None, None), (-20.0, 10.0)],
            options={"maxiter": 500, "ftol": 1e-10},
        )
        kappa, mu, log_sigma = res.x
        sigma = math.exp(log_sigma)
        ll = float(-res.fun)
    except Exception:
        kappa, mu, sigma, ll = kappa0, mu0, sigma0, float("nan")

    return {
        "kappa": float(kappa),
        "mu": float(mu),
        "sigma": float(sigma),
        "half_life_days": float(math.log(2) / max(kappa, 1e-9) / max(dt, 1e-12)),
        "log_likelihood": ll,
    }


# ---------------------------------------------------------------------------
# Rolling loading evolution (N×T matrix for heatmap / animated playback)
# ---------------------------------------------------------------------------

def rolling_loading_evolution(
    payload: dict[str, Any] | None = None,
    window: int = 126,
    step: int = 21,
    pc_idx: int = 0,
    max_dates: int = 100,
) -> list[dict[str, Any]]:
    """Compute PC loading vector at each rolling date for heatmap / animation.

    Returns (date, ticker, loading) triples, downsampled to max_dates windows.

    Args:
        payload: Standard payload dict.
        window: Rolling window in trading days.
        step: Step between windows (controls resolution vs payload size).
        pc_idx: Which PC to track (0 = PC1, 1 = PC2, ...).
        max_dates: Hard cap on number of time slices returned.
    """
    ctx = load_context(payload)
    rets = ctx["returns"]
    estimator = (payload or {}).get("covariance_estimator", "ledoit_wolf")
    rows: list[dict[str, Any]] = []
    dates_seen = 0
    for end in range(window, len(rets) + 1, step):
        if dates_seen >= max_dates:
            break
        sample = rets.iloc[end - window: end]
        try:
            cov, _ = covariance_estimator(sample, estimator)
            _, vecs = eig_sorted(cov)
            loading_vec = vecs[:, pc_idx]
        except Exception:
            continue
        date_str = str(pd.Timestamp(sample.index[-1]).date())
        for i, ticker in enumerate(rets.columns):
            rows.append({"date": date_str, "ticker": ticker, "loading": float(loading_vec[i])})
        dates_seen += 1
    return rows


# ---------------------------------------------------------------------------
# PC1 percentile rank (live alert panel enrichment for Feature 05)
# ---------------------------------------------------------------------------

def pc1_percentile_rank(
    rolling_df: pd.DataFrame,
    history_window: int = 252,
) -> dict[str, Any]:
    """Given the output of rolling_pca_metrics(), compute current PC1 share
    as a percentile of its recent history, per rolling window length.

    Args:
        rolling_df: DataFrame from rolling_pca_metrics().
        history_window: Number of most-recent observations for percentile.

    Returns:
        Dict mapping window_days -> {current_pc1_share, percentile_rank, alert}.
        alert is "HIGH" (>=80th pct), "LOW" (<=20th pct), or "NORMAL".
    """
    result: dict[str, Any] = {}
    if rolling_df.empty or "pc1_share" not in rolling_df.columns:
        return result
    for w in rolling_df["window"].unique():
        sub = rolling_df[rolling_df["window"] == w].sort_values("date")
        if sub.empty:
            continue
        series = sub["pc1_share"].to_numpy(dtype=float)
        current = float(series[-1])
        history = series[-history_window:]
        pct_rank = float(np.mean(history <= current) * 100)
        result[int(w)] = {
            "current_pc1_share": current,
            "percentile_rank": pct_rank,
            "history_window": int(len(history)),
            "alert": "HIGH" if pct_rank >= 80 else "LOW" if pct_rank <= 20 else "NORMAL",
        }
    return result
