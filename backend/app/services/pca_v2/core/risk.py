"""PCA V2 risk primitives."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd
from scipy import stats
from .data_loader import latest_market_caps


def active_risk_attribution(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tracking error decomposition against a benchmark weight vector."""
    from .analytics import model_annualization
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
    from .analytics import eig_sorted
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



def portfolio_weights(symbols: list[str], payload: dict[str, Any] | None = None) -> pd.Series:
    from .analytics import number_like
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
        if raw:
            raise ValueError("Portfolio weights require an object or list of ticker/weight rows")
        return pd.Series(np.ones(len(symbols))/len(symbols), index=symbols)
    missing = sorted(set(weights)-set(symbols))
    if missing:
        raise ValueError("Portfolio symbols outside the resolved universe: " + ", ".join(missing))
    s = pd.Series({sym: weights.get(sym, 0.0) for sym in symbols}, dtype=float)
    total = float(s.abs().sum())
    if not np.isfinite(s).all() or total<=0:
        raise ValueError("Portfolio weights must be finite with positive gross exposure")
    return s / total



def risk_decomposition(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .analytics import model_annualization, number_like
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

