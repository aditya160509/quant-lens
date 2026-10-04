"""PCA V2 model helpers."""
from __future__ import annotations
from functools import lru_cache
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import annualization_factor, latest_market_caps, parse_symbols, returns_matrix, sector_map


def load_context(payload: dict[str, Any] | None, *, min_symbols: int = 12) -> dict[str, Any]:
    from .analytics import number_like, parse_compute_mode
    payload = payload or {}
    if payload.get("window_type") == "anchored" and not payload.get("anchor_date"):
        raise ValueError("Anchored window requires anchor_date")
    lookback = int(number_like(payload.get("window_length") or payload.get("window_days") or payload.get("lookback_days"), 504) or 504)
    raw_universe = payload.get("tickers") or payload.get("symbols") or payload.get("assets") or payload.get("universe")
    full_requested = str(raw_universe or "").strip().lower() in {"all", "full", "master", "master_universe", "market_universe", "whole"} or bool(payload.get("use_full_master_universe"))
    max_default = 5000 if full_requested else 120
    max_symbols = int(number_like(payload.get("max_symbols") or payload.get("max_tickers"), max_default) or max_default)
    default_limit = max(min_symbols, max_symbols if full_requested or payload.get("max_symbols") or payload.get("max_tickers") else min(max_symbols, 120))
    symbols = [] if payload.get("returns_upload_id") else parse_symbols(payload, default_limit=default_limit, max_symbols=max_symbols)
    frequency = str(payload.get("sampling_frequency") or payload.get("frequency") or "daily").lower()
    if payload.get("returns_upload_id"):
        from .uploads import read_upload
        frame = read_upload(payload["returns_upload_id"], "returns")
        rets = frame.pivot(index="date", columns="ticker", values="return").sort_index()
        symbols = list(rets.columns)
        if raw_universe:
            requested = str(raw_universe).split(",") if isinstance(raw_universe, str) else list(raw_universe)
            missing = set(requested) - set(symbols)
            if missing:
                raise ValueError("Unknown upload symbols: " + ", ".join(sorted(missing)))
            rets = rets[requested]
            symbols = requested
        before = len(rets)
        rets = rets.dropna(how="any")
        rets.attrs["rows_dropped_missing"] = before - len(rets)
        rets.attrs["missing_data_policy"] = "uploaded_complete_case"
    else:
        rets = returns_matrix(symbols, lookback_days=max(lookback, 80) if payload.get("window_type", "rolling") == "rolling" else 1000000, frequency=frequency, end_date=payload.get("end_date") or payload.get("as_of"), start_date=payload.get("start_date") or payload.get("anchor_date"))
    if payload.get("end_date") or payload.get("as_of"):
        rets = rets.loc[:pd.Timestamp(payload.get("end_date") or payload["as_of"])]
    if payload.get("start_date") or payload.get("anchor_date"):
        rets = rets.loc[pd.Timestamp(payload.get("start_date") or payload["anchor_date"]):]
    if payload.get("window_type", "rolling") == "rolling":
        rets = rets.tail(lookback)

    coverage = dict(rets.attrs)
    if rets.shape[1] < 3 or len(rets) < 10:
        raise ValueError(f"Insufficient complete data: requested={len(symbols)}, resolved={rets.shape[1]}, complete observations={len(rets)}; need 3 assets and 10 observations")
    missing = sorted(set(symbols) - set(rets.columns))
    if missing:
        raise ValueError("Requested symbols without usable prices: " + ", ".join(missing))
    symbols = [str(c) for c in rets.columns]
    return {
        "payload": payload,
        "data_coverage": coverage,
        "requested_symbols": symbols,
        "default_universe_rule": "most_observed_history; historical membership unavailable",
        "symbols": symbols,
        "returns": rets,
        "lookback_days": lookback,
        "frequency": frequency,
        "annualization_factor": annualization_factor(frequency),
        "sectors": {s: str(payload.get("groups", {}).get(s, sector_map(symbols).get(s, "Unknown"))) for s in symbols} if payload.get("groups") else sector_map(symbols),
        "market_caps": latest_market_caps(symbols),
        "compute_mode": parse_compute_mode(payload),
    }



def rmt_model(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .analytics import choose_k, covariance_estimator, eig_sorted, fit_mp_sigma2, mp_threshold, number_like, preprocess_returns
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
    matrix_type = str(payload.get("matrix_type") or ("correlation" if payload.get("standardize") else "covariance"))
    if matrix_type not in {"covariance", "cov", "correlation", "corr"}:
        raise ValueError("matrix_type must be covariance or correlation")
    means = cleaned_returns.mean()
    scales = cleaned_returns.std(ddof=1) if matrix_type in {"correlation", "corr"} else pd.Series(1.0, index=returns.columns)
    if (scales <= 0).any():
        raise ValueError("Correlation PCA requires positive variance in every asset")
    analysis_returns = cleaned_returns.sub(means).div(scales)
    cov, cov_meta = covariance_estimator(analysis_returns, method, ewma_lambda=float(number_like(payload.get("ewma_lambda"), 0.94) or 0.94))
    if matrix_type in {"correlation", "corr"}:
        estimator_scales = pd.Series(np.sqrt(np.diag(cov)), index=analysis_returns.columns)
        if (estimator_scales <= 0).any():
            raise ValueError("Estimated correlation requires positive variances")
        cov = cov / np.outer(estimator_scales, estimator_scales)
        scales = scales * estimator_scales
        analysis_returns = cleaned_returns.sub(means).div(scales)
        cov_meta["correlation_diagonal_normalized"] = True
    evals, evecs = eig_sorted(cov)
    # Iterative sigma² fitting (moment-matching) unless user supplies sigma2_noise explicitly
    if payload.get("sigma2_noise") is not None:
        sigma2 = float(payload["sigma2_noise"])
        if not np.isfinite(sigma2) or sigma2 <= 0:
            raise ValueError("sigma2_noise must be positive and finite")
    else:
        sigma2 = fit_mp_sigma2(evals, returns.shape[1], returns.shape[0])
    mp = mp_threshold(evals, returns.shape[1], returns.shape[0], sigma2=sigma2)
    cov_meta["fitted_sigma2"] = sigma2
    k_info = choose_k(evals, mp, {**payload, "matrix_type": matrix_type})
    k = k_info["selected"]
    signal = (evecs[:, :k] * evals[:k]) @ evecs[:, :k].T
    idio = np.maximum(np.diag(cov - signal), 1e-10)
    cleaned = signal + np.diag(idio)
    raw_cov = np.cov(analysis_returns.to_numpy(dtype=float), rowvar=False)
    raw_evals, _ = eig_sorted(raw_cov)
    clean_evals, _ = eig_sorted(cleaned)
    return {
        **ctx,
        "original_returns": returns,
        "returns": cleaned_returns,
        "analysis_returns": analysis_returns,
        "matrix_type": matrix_type,
        "return_means": means,
        "return_scales": scales,
        "outlier_method": outlier_method,
        "pca_cov": cov,
        "pca_cleaned_cov": cleaned,
        "pca_raw_cov": raw_cov,
        "cov": cov * np.outer(scales, scales),
        "raw_cov": raw_cov * np.outer(scales, scales),
        "cleaned_cov": cleaned * np.outer(scales, scales),
        "eigenvalues": evals,
        "orthonormal_eigenvectors": evecs,
        "eigenvectors": evecs * scales.to_numpy()[:, None],
        "raw_eigenvalues": raw_evals,
        "cleaned_eigenvalues": clean_evals,
        "mp": mp,
        "k_info": k_info,
        "k": k,
        "idio_var": idio * scales.to_numpy() ** 2,
        "cov_meta": cov_meta,
    }



@lru_cache(maxsize=32)
def _cached_rmt_key(symbols_key: tuple[str, ...], lookback: int, estimator: str, k: int | None) -> dict[str, Any]:
    payload = {"symbols": list(symbols_key), "lookback_days": lookback, "covariance_estimator": estimator}
    if k:
        payload["k"] = k
    return rmt_model(payload)

