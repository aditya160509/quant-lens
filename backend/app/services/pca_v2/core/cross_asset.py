"""Cross-asset PCA/RMT analytics for Feature 10."""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from sklearn.covariance import MinCovDet, OAS, LedoitWolf

from .analytics import compact_records, matrix_records, mp_threshold, fit_mp_sigma2
from .data_loader import (
    COMMODITY_FUTURES_SYMBOLS,
    CRYPTO_SYMBOLS,
    EQUITY_PROXY_SYMBOLS,
    FX_SYMBOLS,
    RATES_FUTURES_SYMBOLS,
    cross_asset_returns_matrix,
    load_cross_asset_ohlcv,
    load_hourly_ohlcv,
    normalize_symbol,
    available_symbols,
    UnknownSymbolsError,
)
from .performance import batched_corr, fast_cov, frame_fingerprint, safe_pinv


BLOCK_SYMBOLS = {
    "equity": EQUITY_PROXY_SYMBOLS,
    "fx": FX_SYMBOLS,
    "commodities": COMMODITY_FUTURES_SYMBOLS,
    "rates": RATES_FUTURES_SYMBOLS,
    "crypto": CRYPTO_SYMBOLS,
}


def _as_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return default
    if isinstance(value, str):
        return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]
    try:
        return [str(x).strip() for x in value if str(x).strip()]
    except TypeError as exc:
        raise ValueError("Cross-asset symbols must be a list or comma-separated string") from exc


def symbols_from_payload(payload: dict[str, Any] | None) -> dict[str, list[str]]:
    payload = payload or {}
    symbols = {
        "equity": _as_list(payload.get("equity_symbols") or payload.get("equities"), BLOCK_SYMBOLS["equity"]),
        "fx": _as_list(payload.get("fx_symbols"), BLOCK_SYMBOLS["fx"]),
        "commodities": _as_list(payload.get("commodity_symbols") or payload.get("commodities"), BLOCK_SYMBOLS["commodities"]),
        "rates": _as_list(payload.get("rates_symbols") or payload.get("rate_symbols"), BLOCK_SYMBOLS["rates"]),
        "crypto": _as_list(payload.get("crypto_symbols"), BLOCK_SYMBOLS["crypto"]),
    }

    active = payload.get("blocks")
    if active is None:
        return symbols
    if not isinstance(active, list) or not active or any(block not in symbols for block in active):
        raise ValueError("blocks must be a nonempty list of equity, fx, commodities, rates or crypto")
    return {block:symbols[block] for block in active}


def _ewma_cov(rets: pd.DataFrame, lam: float = 0.94) -> np.ndarray:
    x = rets.to_numpy(dtype=float)
    if len(x) < 2:
        return np.zeros((x.shape[1], x.shape[1]))
    w = np.array([(1 - lam) * lam ** i for i in range(len(x) - 1, -1, -1)], dtype=float)
    w = w / max(w.sum(), 1e-12)
    xc = x - np.average(x, axis=0, weights=w)
    return (xc * w[:, None]).T @ xc




def _student_t_em(rets: pd.DataFrame, max_iter: int = 50, tol: float = 1e-6) -> tuple[np.ndarray, dict[str, Any]]:
    """Robust multivariate Student-t covariance EM with a shared fitted degrees of freedom."""
    x = rets.to_numpy(dtype=float)
    if x.shape[0] < 10 or x.shape[1] == 0 or not np.isfinite(x).all():
        raise ValueError("Student-t EM requires at least 10 finite observations")
    mu = np.median(x, axis=0)
    sigma = np.cov(x, rowvar=False) + np.eye(x.shape[1]) * 1e-10
    nu = 8.0
    converged = False
    for iteration in range(max_iter):
        old = sigma.copy()
        delta = x - mu
        inv = safe_pinv(sigma, 1e-8)
        mahal = np.einsum("ij,jk,ik->i", delta, inv, delta)
        weights = (nu + x.shape[1]) / np.maximum(nu + mahal, 1e-12)
        mu = np.average(x, axis=0, weights=weights)
        delta = x - mu
        sigma = (delta * weights[:, None]).T @ delta / len(x)
        sigma = (sigma + sigma.T) / 2 + np.eye(x.shape[1]) * 1e-10
        if np.linalg.norm(sigma - old, ord="fro") <= tol * max(np.linalg.norm(old, ord="fro"), 1e-12):
            converged = True
            break
    return sigma * nu / (nu-2), {"estimator": "student_t_em", "scatter_to_covariance_multiplier": nu/(nu-2), "degrees_of_freedom": nu, "degrees_of_freedom_method": "fixed_8", "iterations": iteration + 1, "converged": converged}


def block_covariance(block: str, rets: pd.DataFrame) -> tuple[np.ndarray, dict[str, Any]]:
    if rets.empty:
        return np.zeros((0, 0)), {"estimator": "empty"}
    if block == "fx":
        return _ewma_cov(rets, 0.94), {"estimator": "ewma", "lambda": 0.94, "volume_note": "FX volume is not meaningful in local Yahoo-style files."}
    if block in {"commodities", "rates"}:
        est = OAS().fit(rets.to_numpy(dtype=float))
        return est.covariance_, {"estimator": "oas", "shrinkage": float(est.shrinkage_)}
    if block == "crypto":
        return _student_t_em(rets)
    est = LedoitWolf().fit(rets.to_numpy(dtype=float))
    return est.covariance_, {"estimator": "ledoit_wolf", "shrinkage": float(est.shrinkage_)}


def _crypto_volume_filter(symbols: list[str], lookback_days: int, min_positive_ratio: float = 0.50) -> list[dict[str, Any]]:
    ohlcv = load_cross_asset_ohlcv(symbols, lookback_days=lookback_days)
    rows = []
    for ticker, group in ohlcv.groupby("Ticker"):
        vol = pd.to_numeric(group["Volume"], errors="coerce").fillna(0.0)
        positive_ratio = float((vol > 0).mean()) if len(vol) else 0.0
        rows.append(
            {
                "ticker": ticker,
                "rows": int(len(group)),
                "positive_volume_ratio": positive_ratio,
                "wash_trading_proxy_flag": bool(positive_ratio < min_positive_ratio),
                "note": "Volume filter is a local-data quality screen, not exchange-level wash-trade proof.",
            }
        )
    return rows


def _cornish_fisher_mp(block: str, rets: pd.DataFrame) -> dict[str, Any] | None:
    if block != "crypto" or rets.empty:
        return None
    cov = fast_cov(rets)
    vals = np.linalg.eigvalsh((cov + cov.T) / 2)
    vals = np.sort(np.maximum(vals, 0))[::-1]
    mp = mp_threshold(vals, rets.shape[1], rets.shape[0])
    k4 = float(np.nanmean(stats.kurtosis(rets.to_numpy(dtype=float), axis=0, fisher=True, nan_policy="omit")))
    cf_adj = 1.0 + max(k4, 0.0) / 24.0
    return {
        "sigma2": mp["sigma2"],
        "lambda_max_mp": mp["lambda_max"],
        "excess_kurtosis": k4,
        "cornish_fisher_adjustment": cf_adj,
        "lambda_max_cf": float(mp["lambda_max"] * cf_adj),
    }


def load_cross_asset_blocks(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    lookback = int(payload.get("lookback_days") or payload.get("window_days") or 756)
    symbols = symbols_from_payload(payload)
    min_coverage = float(payload.get("min_coverage") or 0.55)
    blocks = {}
    coverage_rows = []
    existing = set(available_symbols())
    for block, block_symbols in symbols.items():
        explicit_keys = {"equity": "equity_symbols", "fx": "fx_symbols", "commodities": "commodity_symbols", "rates": "rates_symbols", "crypto": "crypto_symbols"}
        missing = [normalize_symbol(value) for value in block_symbols if normalize_symbol(value) not in existing]
        aliases = {"equity":"equities", "commodities":"commodities", "rates":"rate_symbols"}
        if (payload.get(explicit_keys[block]) or payload.get(aliases.get(block,""))) and missing:
            raise UnknownSymbolsError(missing)
        rets = cross_asset_returns_matrix(block_symbols, lookback_days=lookback, min_coverage=min_coverage)

        blocks[block] = rets
        coverage_rows.append(
            {
                "asset_class": block,
                "requested": len(block_symbols),
                "missing_symbols": missing,
                "data_coverage": dict(rets.attrs),
                "loaded": int(rets.shape[1]),
                "observations": int(rets.shape[0]),
                "start": str(rets.index.min())[:10] if not rets.empty else None,
                "end": str(rets.index.max())[:10] if not rets.empty else None,
            }
        )
    return {"blocks": blocks, "symbols": symbols, "coverage": coverage_rows, "lookback_days": lookback}


def aligned_cross_asset_returns(blocks: dict[str, pd.DataFrame], calendar_mode: str = "equity_day") -> tuple[pd.DataFrame, dict[str, str], list[dict[str, Any]]]:
    frames = []
    class_map = {}
    for block, rets in blocks.items():
        if rets.empty:
            continue
        renamed = rets.copy()
        renamed.columns = [str(c) for c in renamed.columns]
        for col in renamed.columns:
            class_map[col] = block
        frames.append(renamed)
    if not frames:
        return pd.DataFrame(), class_map, []
    joined = pd.concat(frames, axis=1).sort_index()
    if calendar_mode == "seven_day":
        joined = joined.asfreq("D")
    else:
        joined = joined[joined.index.dayofweek < 5]
    before = len(joined)
    joined = joined.dropna(how="any")
    if len(joined) < 30:
        raise ValueError("Cross-asset alignment requires 30 complete observed dates")
    notes = [
        {
            "calendar_mode": calendar_mode,
            "rows": int(len(joined)),
            "assets": int(joined.shape[1]),
            "rows_dropped_missing": before - len(joined),
            "weekend_crypto_policy": "Complete observed dates only; equity_day excludes weekends, seven_day never invents closed-market returns.",
        }
    ]
    class_map = {c: class_map.get(c, "unknown") for c in joined.columns}
    return joined, class_map, notes


def dcc_correlation(rets: pd.DataFrame, max_assets: int = 30) -> dict[str, Any]:
    if rets.empty or rets.shape[1] < 2:
        return {"parameters": {"a": 0.0, "b": 0.0}, "latest_corr": [], "average_corr": []}
    x = rets.iloc[:, :max_assets].copy()
    vol = x.ewm(alpha=0.06, adjust=False).std().replace(0, np.nan).clip(lower=1e-8).shift(1)
    standardized = (x / vol).replace([np.inf, -np.inf], np.nan).dropna(how="any")
    x = x.loc[standardized.index]
    z = standardized.to_numpy(dtype=float)
    train_count = min(126, max(30, len(z)//2))
    training = z[:train_count]
    s = np.cov(training, rowvar=False)
    s = np.nan_to_num(s)

    def nll(params):
        a, b = params
        if a < 0 or b < 0 or a + b >= 0.999:
            return 1e9
        q = s.copy()
        loss = 0.0
        for t in range(1, len(training)):
            q = (1 - a - b) * s + a * np.outer(training[t - 1], training[t - 1]) + b * q
            d = np.sqrt(np.maximum(np.diag(q), 1e-10))
            r = q / np.outer(d, d)
            r = (r + r.T) / 2
            np.fill_diagonal(r, 1.0)
            if not np.isfinite(r).all():
                return 1e9
            try:
                lower = np.linalg.cholesky(r + np.eye(r.shape[0])*1e-8)
            except np.linalg.LinAlgError:
                return 1e9
            from scipy.linalg import solve_triangular
            whitened = solve_triangular(lower, training[t], lower=True, check_finite=False)
            logdet = 2*float(np.log(np.diag(lower)).sum())
            loss += logdet + float(whitened @ whitened)
        return loss

    res = minimize(nll, x0=np.array([0.04, 0.92]), bounds=[(1e-6, 0.30), (1e-6, 0.995)], method="L-BFGS-B")
    if not res.success or not np.isfinite(res.fun) or res.fun >= 1e9:
        raise ValueError(f"DCC parameter fit failed: {res.message}")
    a, b = res.x
    q = s.copy()
    avg_rows = []
    latest_r = None
    for t in range(1, len(z)):
        q = (1 - a - b) * s + a * np.outer(z[t - 1], z[t - 1]) + b * q
        d = np.sqrt(np.maximum(np.diag(q), 1e-10))
        latest_r = q / np.outer(d, d)
        if t >= train_count and (t % max(1, len(z) // 180) == 0 or t == len(z) - 1):
            upper = latest_r[np.triu_indices_from(latest_r, 1)]
            avg_rows.append({"date": str(x.index[t])[:10], "dcc_average_correlation": float(np.nanmean(upper))})
    corr = pd.DataFrame(latest_r, index=x.columns, columns=x.columns) if latest_r is not None else batched_corr(x)
    return {
        "parameters": {"a": float(a), "b": float(b), "converged": bool(res.success), "parameter_training_observations": train_count, "parameter_training_end": str(x.index[train_count-1])[:10], "volatility_floor": 1e-8, "historical_policy": "parameters fitted on initial training window; scored after training only"},
        "latest_corr": matrix_records(corr, limit=80),
        "average_corr": avg_rows,
    }


def fx_hedge_ratios(rets: pd.DataFrame, class_map: dict[str, str]) -> list[dict[str, Any]]:
    fx = [c for c in rets.columns if class_map.get(c) == "fx"]
    eq = [c for c in rets.columns if class_map.get(c) == "equity"]
    if len(fx) < 2 or not eq:
        return []
    cov = rets[fx + eq].cov()
    sigma_fx = cov.loc[fx, fx].to_numpy(dtype=float)
    sigma_fx_eq = cov.loc[fx, eq].to_numpy(dtype=float)
    hedge = safe_pinv(sigma_fx, 1e-8) @ sigma_fx_eq
    rows = []
    for i, f in enumerate(fx):
        for j, e in enumerate(eq):
            rows.append({"fx_pair": f, "equity_asset": e, "min_variance_hedge_ratio": float(hedge[i, j])})
    return rows


def block_correlation_monitor(rets: pd.DataFrame, class_map: dict[str, str], window: int = 63) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    classes = sorted(set(class_map.values()))
    rows = []
    casci = []
    for end in range(window, len(rets) + 1, max(5, window // 4)):
        sub = rets.iloc[end - window : end]
        corr = sub.corr()
        date = str(sub.index[-1])[:10]
        vals_for_casci = []
        for i, a in enumerate(classes):
            for b in classes[i + 1 :]:
                ca = [c for c in sub.columns if class_map.get(c) == a]
                cb = [c for c in sub.columns if class_map.get(c) == b]
                if not ca or not cb:
                    continue
                block_values = corr.loc[ca, cb].to_numpy(dtype=float)
                finite = block_values[np.isfinite(block_values)]
                value = float(finite.mean()) if finite.size else 0.0
                vals_for_casci.append(abs(value))
                rows.append({"date": date, "block_a": a, "block_b": b, "rolling_correlation": value})
        casci_value = float(np.nanmean(vals_for_casci)) if vals_for_casci else 0.0
        casci.append({"date": date, "casci": casci_value if math.isfinite(casci_value) else 0.0})
    return rows, casci


def stress_date_overlay(rets: pd.DataFrame, class_map: dict[str, str]) -> list[dict[str, Any]]:
    if rets.empty:
        return []
    events = {
        "COVID Crash": "2020-03-16",
        "Rate Shock 2022": "2022-06-13",
        "Bank Stress 2023": "2023-03-13",
        "Liberation Day 2025": "2025-04-02",
    }
    rows = []
    for name, date in events.items():
        ts = pd.Timestamp(date)
        if ts < rets.index.min() or ts > rets.index.max():
            continue
        loc = rets.index.get_indexer([ts], method="nearest")[0]
        sub = rets.iloc[max(0, loc - 21) : min(len(rets), loc + 22)]
        if len(sub) < 10:
            continue
        corr = sub.corr()
        for a in sorted(set(class_map.values())):
            for b in sorted(set(class_map.values())):
                if a >= b:
                    continue
                ca = [c for c in sub.columns if class_map.get(c) == a]
                cb = [c for c in sub.columns if class_map.get(c) == b]
                if ca and cb:
                    rows.append({"event": name, "date": date, "block_a": a, "block_b": b, "event_window_corr": float(corr.loc[ca, cb].to_numpy().mean())})
    return rows


def cross_asset_feature_outputs(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    block_data = load_cross_asset_blocks(payload)
    blocks = block_data["blocks"]
    calendar_mode = str(payload.get("calendar_mode") or "equity_day").lower()
    aligned, class_map, calendar_notes = aligned_cross_asset_returns(blocks, calendar_mode)
    if aligned.empty:
        return {"status": "error", "summary": [], "charts": {}, "tables": {"coverage": block_data["coverage"]}, "meta": {"error": "No cross-asset returns available"}}

    block_cov_rows = []
    block_meta = []
    block_diag = {}
    for block, rets in blocks.items():
        columns = [c for c in aligned if class_map[c] == block]
        rets = aligned[columns]
        cov, meta = block_covariance(block, rets)
        block_meta.append({"asset_class": block, "assets": int(rets.shape[1]), "observations": int(rets.shape[0]), **meta})
        block_diag[block] = cov

    sample_cov = aligned.cov()
    cov_values = sample_cov.to_numpy(dtype=float).copy()
    cross_shrink = float(payload.get("gamma_cross", payload.get("cross_block_shrinkage", 0.40)))
    if not 0 <= cross_shrink <= 1:
        raise ValueError("gamma_cross must be in [0,1]")
    dcc = dcc_correlation(aligned, max_assets=aligned.shape[1])
    conditional = {(r["row"], r["col"]): r["value"] for r in dcc["latest_corr"]}
    sample_std = np.sqrt(np.maximum(np.diag(cov_values), 1e-15))
    for i, ci in enumerate(aligned.columns):
        for j, cj in enumerate(aligned.columns):
            if class_map.get(ci) != class_map.get(cj):
                dynamic = conditional.get((ci, cj))
                if dynamic is None:
                    raise ValueError("DCC did not produce full cross-asset covariance")
                cov_values[i, j] = (1-cross_shrink)*dynamic*sample_std[i]*sample_std[j] + cross_shrink*cov_values[i, j]
    # Preserve each block's estimator while shrinking uncertain cross-block covariance.
    for block, cov in block_diag.items():
        cols = [c for c in aligned.columns if class_map.get(c) == block]
        source_cols = list(blocks[block].columns) if block in blocks else []
        common = [c for c in cols if c in source_cols]
        if common and cov.shape == (len(source_cols), len(source_cols)):
            idx_all = [aligned.columns.get_loc(c) for c in common]
            idx_src = [source_cols.index(c) for c in common]
            cov_values[np.ix_(idx_all, idx_all)] = cov[np.ix_(idx_src, idx_src)]
    cov_values = (cov_values + cov_values.T) / 2.0
    vals_raw, vecs_raw = np.linalg.eigh(cov_values)
    psd_adjustment = float(np.minimum(vals_raw, 0.0).sum())
    vals_raw = np.maximum(vals_raw, 0.0)
    mp_all = mp_threshold(vals_raw[::-1], aligned.shape[1], aligned.shape[0], fit_mp_sigma2(vals_raw, aligned.shape[1], aligned.shape[0]))
    noise = vals_raw <= mp_all["lambda_max"]
    cleaned_vals = vals_raw.copy()
    if noise.any():
        cleaned_vals[noise] = float(vals_raw[noise].mean())
    cov_values = (vecs_raw * cleaned_vals) @ vecs_raw.T
    cov_all = pd.DataFrame(cov_values, index=aligned.columns, columns=aligned.columns)
    std = np.sqrt(np.maximum(np.diag(cov_values), 1e-15))
    corr_all = pd.DataFrame(cov_values / np.outer(std, std), index=aligned.columns, columns=aligned.columns).clip(-1, 1)
    vals, vecs = np.linalg.eigh((cov_all.to_numpy(dtype=float) + cov_all.to_numpy(dtype=float).T) / 2)
    order = np.argsort(vals)[::-1]
    vals = np.maximum(vals[order], 0.0)
    vecs = vecs[:, order]
    total = max(float(vals.sum()), 1e-12)

    for a in sorted(set(class_map.values())):
        for b in sorted(set(class_map.values())):
            if a > b:
                continue
            ca = [c for c in aligned.columns if class_map.get(c) == a]
            cb = [c for c in aligned.columns if class_map.get(c) == b]
            if ca and cb:
                block_cov_rows.append(
                    {
                        "block_a": a,
                        "block_b": b,
                        "avg_covariance": float(cov_all.loc[ca, cb].to_numpy().mean()),
                        "avg_correlation": float(corr_all.loc[ca, cb].to_numpy().mean()),
                        "asset_count_a": len(ca),
                        "asset_count_b": len(cb),
                    }
                )

    loading_share = []
    loading_rows = []
    k = min(int(payload.get("k") or 8), len(vals), aligned.shape[1])
    for pc in range(k):
        for i, ticker in enumerate(aligned.columns):
            loading_rows.append({"ticker": ticker, "asset_class": class_map.get(ticker), "component": f"PC{pc+1}", "loading": float(vecs[i, pc])})
        for block in sorted(set(class_map.values())):
            idx = [i for i, c in enumerate(aligned.columns) if class_map.get(c) == block]
            loading_share.append({"component": f"PC{pc+1}", "asset_class": block, "loading_share": float(np.sum(vecs[idx, pc] ** 2)) if idx else 0.0})

    hedge = fx_hedge_ratios(aligned, class_map)
    rolling_block, casci = block_correlation_monitor(aligned, class_map, window=int(payload.get("rolling_window") or 63))
    crypto_filter = _crypto_volume_filter(block_data["symbols"].get("crypto",[]), block_data["lookback_days"])
    cf_mp = _cornish_fisher_mp("crypto", blocks.get("crypto", pd.DataFrame()))
    hourly = load_hourly_ohlcv()
    stress_overlay = stress_date_overlay(aligned, class_map)
    factor_ts = pd.DataFrame(aligned.to_numpy(dtype=float) @ vecs[:, :k], index=aligned.index, columns=[f"PC{i+1}" for i in range(k)])
    block_mp = []
    for block, rets in blocks.items():
        if not rets.empty:
            ev = np.linalg.eigvalsh(fast_cov(rets))[::-1]
            threshold = mp_threshold(ev, rets.shape[1], rets.shape[0], fit_mp_sigma2(ev, rets.shape[1], rets.shape[0]))
            block_mp.append({"asset_class": block, "q": float(rets.shape[1] / max(rets.shape[0], 1)), **threshold})

    coverage = block_data["coverage"]
    loaded_assets = int(aligned.shape[1])
    summary = [
        {"label": "Assets", "value": loaded_assets, "unit": "count"},
        {"label": "Blocks", "value": len(set(class_map.values())), "unit": "classes"},
        {"label": "PC1 Share", "value": float(vals[0] / total * 100) if len(vals) else 0.0, "unit": "%"},
        {"label": "CASCI", "value": casci[-1]["casci"] if casci else 0.0, "unit": "corr"},
        {"label": "Hourly Tickers", "value": int(hourly["Ticker"].nunique()) if not hourly.empty else 0, "unit": "count"},
    ]
    return {
        "status": "ok",
        "summary": summary,
        "charts": {
            "unified_cross_asset_covariance_heatmap": matrix_records(cov_all, limit=120),
            "unified_cross_asset_correlation_heatmap": matrix_records(corr_all, limit=120),
            "block_correlation_monitor": rolling_block,
            "casci_index": casci,
            "asset_class_pc_loading_share": loading_share,
            "unified_spectrum_mp": [{"rank": i+1, "eigenvalue": float(v), "lambda_max": mp_all["lambda_max"]} for i,v in enumerate(vals_raw[::-1])],
            "block_mp_bounds": block_mp,
            "cross_asset_loading_heatmap": loading_rows,
            "cross_asset_factor_returns": compact_records(factor_ts.rename_axis("date").reset_index(), limit=500),
            "dcc_latest_correlation": dcc["latest_corr"],
            "dcc_average_correlation": dcc["average_corr"],
            "stress_date_block_correlation_overlay": stress_overlay,
        },
        "tables": {
            "coverage": coverage,
            "block_decomposition": block_cov_rows,
            "block_estimator_audit": block_meta,
            "fx_hedge_ratio_table": hedge,
            "crypto_volume_filter": crypto_filter,
            "crypto_cornish_fisher_mp": [cf_mp] if cf_mp else [],
            "calendar_alignment_audit": calendar_notes,
            "cross_asset_eigenvalues": [
                {"component": f"PC{i+1}", "eigenvalue": float(vals[i]), "explained_variance": float(vals[i] / total), "cumulative_variance": float(vals[: i + 1].sum() / total)}
                for i in range(min(len(vals), 40))
            ],
            "asset_class_mp_bounds": block_mp,
            "dcc_parameters": [dcc["parameters"]],
            "hourly_data_inventory": [
                {
                    "source": "largest_verified_hourly_parquet",
                    "rows": int(len(hourly)),
                    "tickers": int(hourly["Ticker"].nunique()) if not hourly.empty else 0,
                    "start": str(hourly["Datetime"].min()) if not hourly.empty else None,
                    "end": str(hourly["Datetime"].max()) if not hourly.empty else None,
                }
            ],
        },
        "meta": {
            "returns": frame_fingerprint(aligned),
            "unified_mp": mp_all,
            "gamma_cross": cross_shrink,
            "gamma_cross_semantics": "0=conditional DCC cross-covariance; 1=unconditional sample cross-covariance",
            "negative_eigenvalue_mass_before_psd_projection": psd_adjustment,
            "classes": class_map,
            "data_source": "market_universe.parquet + backend/data/prices + largest verified hourly parquet inventory",
            "futures_roll_status": "raw continuous/proxy futures files are used; independent roll-adjusted methodology is still not verified.",
            "fx_volume_status": "FX volume is expected to be zero/unreliable and is excluded from FX covariance estimation.",
            "status_note": "Feature 10 assembles block-specific estimators, shrinks cross-block covariance, and applies unified RMT eigenvalue cleaning.",
        },
    }
