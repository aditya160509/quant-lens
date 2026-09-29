"""F06 Regime Detection and Regime-Aware Allocation."""

from __future__ import annotations

import pandas as pd

from ..core.analytics import feature_meta, kaplan_meier_survival, load_context, load_macro, nonhomogeneous_transition, performance_metrics, portfolio_return_series, regime_conditional_cov, regime_factor_performance, response, rolling_regimes

FEATURE_ID = "06"
FEATURE_NAME = "Market Regime Detection and Regime-Aware Allocation Engine"
INPUTS = ["tickers", "weights", "lookback_days", "regime_count"]
OUTPUTS = ["regime_timeline", "transition_matrix", "regime_performance", "regime_conditional_weights", "survival_curves"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=8, default_limit=80)
    port = portfolio_return_series(ctx["returns"], ctx["weights"])
    regimes = rolling_regimes(port, load_macro(), int(payload.get("regime_count") or 3))
    if regimes.empty:
        return response(FEATURE_ID, [], {}, {}, meta=feature_meta(ctx, ["not enough return history for regime fit"]))
    trans = pd.crosstab(regimes["regime"].shift(1), regimes["regime"], normalize="index").fillna(0.0)
    perf = []
    for r, idx in regimes.groupby("regime").groups.items():
        dates = regimes.loc[idx, "date"]
        series = port.reindex(pd.to_datetime(dates)).dropna()
        row = {"regime": int(r)}
        row.update(performance_metrics(series, ctx["annualization_factor"]))
        perf.append(row)
    macro = load_macro().set_index("date").reindex(port.index, method="ffill")
    drivers = macro[[c for c in ["vix_close", "vixcls", "bamlh0a0hym2"] if c in macro.columns]].ffill().pct_change(fill_method=None).fillna(0.0)
    regime_series = regimes.set_index("date")["regime"]
    regime_series.index = pd.to_datetime(regime_series.index)
    drivers = drivers.reindex(regime_series.index, method="ffill").fillna(0.0)
    charts = {
        "regime_timeline": regimes.to_dict("records"),
        "transition_matrix": [{"row": str(i), "col": str(j), "value": float(trans.loc[i, j])} for i in trans.index for j in trans.columns],
        "regime_conditional_correlation": regime_conditional_cov(ctx["returns"], regime_series),
    }
    tables = {
        "regime_performance": perf,
        "regime_conditional_weights": [{"regime": r["regime"], "recommended_weight_scale": max(0.25, min(1.5, 1 + r.get("sharpe", 0.0) / 4))} for r in perf],
        "survival_curves": kaplan_meier_survival(regime_series),
        "nonhomogeneous_transition": nonhomogeneous_transition(regime_series, drivers),
        "factor_performance_by_regime": regime_factor_performance(ctx["returns"], regime_series),
        "regime_alerts": [{"state": "watch" if trans.max().max() < 0.55 else "stable", "max_transition_probability": float(trans.max().max())}],
    }
    return response(FEATURE_ID, [{"label": "Current Regime", "value": int(regimes["regime"].iloc[-1])}, {"label": "Regime Count", "value": int(regimes["regime"].nunique())}], charts, tables, meta=feature_meta(ctx))
