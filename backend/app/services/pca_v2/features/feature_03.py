"""Feature 03: PCA risk decomposition and factor risk attribution."""

from __future__ import annotations

import pandas as pd
import numpy as np

from app.services.pca_v2.core.analytics import (
    active_risk_attribution,
    compact_records,
    metadata,
    factor_returns,
    portfolio_weights,
    response,
    risk_decomposition,
    rolling_risk_decomposition,
    rmt_model,
)


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    risk = risk_decomposition(model, payload)
    active = active_risk_attribution(model, payload)
    tail_decomp = _historical_tail_decomposition(model, risk, payload)

    # Rolling per-factor decomposition (stacked attribution, not just rolling vol)
    roll_window = int(payload.get("rolling_decomp_window") or 21)
    try:
        roll_decomp = rolling_risk_decomposition(model, payload, window=roll_window)
        roll_records = compact_records(
            roll_decomp.rename(columns={"date": "date"}) if "date" in roll_decomp.columns else roll_decomp.reset_index(names="date"),
            limit=300,
        )
    except Exception:
        # Fallback: simple rolling vol
        returns = risk["portfolio_returns"]
        rolling = returns.rolling(21).std().mul(252 ** 0.5).reset_index()
        rolling.columns = ["date", "portfolio_vol"]
        roll_records = compact_records(rolling, limit=300)

    system_pct = sum(r["pct_total_variance"] for r in risk["factor_rows"] if r["component"] != "Idiosyncratic")
    idio_pct = 100 - system_pct

    return response(
        "03",
        [
            {"label": "Annualized Vol", "value": risk["portfolio_vol_annualized"], "unit": "vol"},
            {"label": "Systematic Risk", "value": system_pct, "unit": "pct"},
            {"label": "Idiosyncratic", "value": idio_pct, "unit": "pct"},
            {"label": "CF VaR", "value": risk["var"]["cornish_fisher_var"], "unit": "return"},
            {"label": "Tracking Error", "value": active["tracking_error_annualized"], "unit": "ann"},
        ],
        charts={
            "risk_attribution_stacked_bar": risk["factor_rows"],
            "factor_var_waterfall": tail_decomp["var_rows"],
            "cvar_decomposition": tail_decomp["cvar_rows"],
            "systematic_vs_idiosyncratic_pie": [{"name": "Systematic", "value": system_pct}, {"name": "Idiosyncratic", "value": idio_pct}],
            "rolling_risk_decomposition": roll_records,
            "benchmark_correlation_by_pc": _benchmark_pc_correlations(model, payload),
            "tracking_error_by_factor": [{"component": r["component"], "te_contribution_bps": r["annualized_te_contribution_bps"]} for r in active["attribution_rows"]],
        },
        tables={
            "marginal_risk_contribution": risk["position_rows"],
            "active_risk_attribution": active["attribution_rows"],
            "var_cvar_table": [risk["var"]],
            "active_risk_attribution_table": active["attribution_rows"],
        },
        meta=metadata(model, {
            "implemented_outputs": 10,
            "tracking_error_annualized": active["tracking_error_annualized"],
            "factor_tilt_share_pct": active["factor_tilt_share"],
            "selection_share_pct": active["selection_share"],
        }),
    )


def _historical_tail_decomposition(model, risk, payload):
    k = model["k"]
    factors = factor_returns(model, k).to_numpy(dtype=float)
    exposures = np.asarray(risk["factor_exposures"], dtype=float)
    factor_components = factors * exposures
    portfolio = risk["portfolio_returns"].to_numpy(dtype=float)
    idiosyncratic = portfolio - factor_components.sum(axis=1)
    components = np.column_stack([factor_components, idiosyncratic])
    names = [f"PC{i+1}" for i in range(k)] + ["Idiosyncratic"]
    losses = -components
    total_losses = -portfolio
    confidence = float(payload.get("var_confidence", 0.95))
    threshold = float(np.quantile(total_losses, confidence))
    var_idx = int(np.argmin(np.abs(total_losses - threshold)))
    tail = total_losses >= threshold
    var_values = losses[var_idx]
    cvar_values = losses[tail].mean(axis=0) if tail.any() else np.full(len(names), np.nan)
    return {
        "var_rows": [{"component": name, "measure": "Historical VaR", "value": float(var_values[i]), "portfolio_total": float(total_losses[var_idx])} for i, name in enumerate(names)],
        "cvar_rows": [{"component": name, "measure": "Historical CVaR", "value": float(cvar_values[i]), "portfolio_total": float(total_losses[tail].mean()) if tail.any() else None} for i, name in enumerate(names)],
    }


def _benchmark_pc_correlations(model, payload):
    symbols = model["symbols"]
    benchmark_payload = {"weights": payload.get("benchmark_weights") or {symbol: 1.0 / len(symbols) for symbol in symbols}}
    benchmark_weights = portfolio_weights(symbols, benchmark_payload).reindex(symbols).fillna(0).to_numpy(dtype=float)
    benchmark_returns = model["returns"].reindex(columns=symbols).fillna(0).to_numpy(dtype=float) @ benchmark_weights
    factors = factor_returns(model, model["k"])
    return [{"component": col, "correlation": float(pd.Series(factors[col].to_numpy()).corr(pd.Series(benchmark_returns)))} for col in factors.columns]
