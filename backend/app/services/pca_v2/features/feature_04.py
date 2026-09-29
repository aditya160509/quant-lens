"""Feature 04: PCA residual OU statistical arbitrage signal engine.

Estimation methods:
  - OLS (default): AR(1) discretization, fast, standard errors via delta method
  - MLE: exact discrete-time log-likelihood via scipy L-BFGS-B (payload["ou_method"] = "mle")

Volume-time adjustment (Avellaneda-Lee 2010): payload["volume_time"] = true

Signal decay analysis: empirically validates OU mean-reversion assumption by tracking
average forward Z-score at T+1, T+5, T+10, T+21, T+42, T+63 after signal generation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.pca_v2.core.analytics import (
    compact_records,
    metadata,
    ou_mle,
    ou_signal_table,
    residual_ou_backtest,
    residual_matrix,
    response,
    rmt_model,
    signal_decay_analysis,
    model_annualization,
)


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    signals = ou_signal_table(model, payload)
    resid = residual_matrix(model)
    active = signals[signals["direction"].ne("No Signal")] if not signals.empty else pd.DataFrame()
    use_vt = bool(payload.get("volume_time", False))

    # Safe column selection: only pick columns that exist
    ou_cols = [c for c in ["ticker", "kappa", "mu", "sigma_eq", "ou_half_life_days", "se_kappa", "se_b", "breakeven_z"] if c in signals.columns]

    # MLE OU estimation (if requested) — run on top N most active tickers
    mle_rows = []
    if str(payload.get("ou_method", "ols")).lower() == "mle":
        top_tickers = signals.nlargest(min(20, len(signals)), "residual_z" if not signals.empty else []).get("ticker", []) if not signals.empty else []
        window = int(payload.get("ou_window") or 126)
        for ticker in top_tickers:
            if ticker not in resid.columns:
                continue
            x = resid[ticker].tail(window).cumsum().dropna().to_numpy(dtype=float)
            mle_result = ou_mle(x, dt=1.0 / model_annualization(model, payload))
            mle_result["ticker"] = ticker
            mle_result["sector"] = model["sectors"].get(ticker, "Unknown")
            mle_rows.append(mle_result)

    # Signal decay analysis (validates mean-reversion assumption)
    run_decay = bool(payload.get("signal_decay", False))
    decay_rows = signal_decay_analysis(model, payload) if run_decay else []
    backtest = residual_ou_backtest(model, payload)
    calendar_signals = ou_signal_table(model, {**payload, "volume_time": False})
    volume_signals = ou_signal_table(model, {**payload, "volume_time": True})

    return response(
        "04",
        [
            {"label": "Active Signals", "value": len(active), "unit": "count"},
            {"label": "Median Half-Life", "value": float(signals["ou_half_life_days"].median()) if not signals.empty else None, "unit": "days"},
            {"label": "Strongest Z", "value": float(signals["residual_z"].abs().max()) if not signals.empty else None, "unit": "z"},
            {"label": "Volume-Time", "value": "On" if use_vt else "Off", "unit": "mode"},
            {"label": "OU Method", "value": str(payload.get("ou_method", "ols")).upper(), "unit": "method"},
        ],
        charts={
            "residual_zscore_distribution": compact_records(signals[["ticker", "sector", "residual_z", "direction"]], limit=300),
            "residual_spread_timeseries": compact_records(resid.iloc[:, : min(20, resid.shape[1])].cumsum().reset_index(names="date"), limit=400),
            "half_life_vs_zscore": compact_records(signals[["ticker", "ou_half_life_days", "residual_z", "economically_viable"]], limit=300),
            "sector_signal_balance": compact_records(signals.groupby(["sector", "direction"]).size().reset_index(name="count") if not signals.empty else pd.DataFrame()),
            "signal_decay_curve": compact_records(pd.DataFrame(decay_rows), limit=500) if decay_rows else [],
            "residual_ou_backtest_equity": compact_records(backtest["equity_curve"], limit=500),
            "residual_correlation_heatmap": [{"row": row, "col": col, "value": float(resid.corr().loc[row, col])} for row in resid.columns[:60] for col in resid.columns[:60]],
            "ou_half_life_distribution": compact_records(signals[["ticker", "ou_half_life_days"]], limit=500),
            "ou_kappa_distribution": compact_records(signals[["ticker", "kappa"]], limit=500),
            "ou_sigma_eq_distribution": compact_records(signals[["ticker", "sigma_eq"]], limit=500),
            "volume_vs_calendar_time": _volume_time_comparison(calendar_signals, volume_signals),
        },
        tables={
            "ranked_signal_table": compact_records(signals, limit=500),
            "ou_parameter_table": compact_records(signals[ou_cols], limit=500) if ou_cols else [],
            "mle_parameter_table": mle_rows,
            "trade_list": compact_records(active, limit=250),
            "signal_decay_table": decay_rows,
            "residual_ou_backtest_stats": [backtest["stats"]],
        },
        meta=metadata(model, {
            "implemented_outputs": 13,
            "volume_time_adjustment": use_vt,
            "ou_method": str(payload.get("ou_method", "ols")).upper(),
            "mle_tickers_estimated": len(mle_rows),
            "signal_decay_computed": run_decay,
        }),
    )


def _volume_time_comparison(calendar, volume):
    if calendar.empty or volume.empty:
        return []
    merged = calendar[["ticker", "residual_z"]].merge(volume[["ticker", "residual_z"]], on="ticker", suffixes=("_calendar", "_volume"))
    merged["difference"] = merged["residual_z_volume"] - merged["residual_z_calendar"]
    return merged.to_dict("records")
