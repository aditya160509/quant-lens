"""F13 Multi-Strategy Portfolio Allocation and Risk Budgeting."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.analytics import build_strategy_returns, capacity_constrained_realloc, cross_strategy_var_attribution, diversification_benefit, feature_meta, kelly_sizing, kill_switch_pnl_calibration, load_context, matrix_records, netting_savings, performance_metrics, regime_conditional_strategy_weights, response, rolling_regimes, sharpe_momentum_realloc
from ..core.performance import cached_correlation_frame

FEATURE_ID = "13"
FEATURE_NAME = "Multi-Strategy Portfolio Allocation and Risk Budgeting Engine"
INPUTS = ["tickers", "lookback_days", "vol_target", "kill_switch_drawdown", "correlation_constraint"]
OUTPUTS = ["strategy_dashboard", "strategy_correlation", "dynamic_allocations", "risk_budget", "kill_switch", "kelly_strategy_weights", "netting_savings"]


def run(payload: dict | None = None) -> dict:
    payload = payload or {}
    ctx = load_context(payload, min_symbols=12, default_limit=100)
    supplied_returns = payload.get("strategy_returns")
    strat = pd.DataFrame()
    if isinstance(supplied_returns, list) and supplied_returns:
        candidate = pd.DataFrame(supplied_returns)
        date_col = next((c for c in ["date", "Date", "timestamp"] if c in candidate.columns), None)
        if date_col:
            candidate[date_col] = pd.to_datetime(candidate[date_col], errors="coerce")
            candidate = candidate.dropna(subset=[date_col]).set_index(date_col)
            numeric = candidate.select_dtypes(include=["number"]).replace([np.inf, -np.inf], np.nan).dropna(how="all")
            if not numeric.empty:
                strat = numeric
    if strat.empty:
        strat = build_strategy_returns(ctx["returns"])
    if strat.empty:
        return response(FEATURE_ID, [], {}, {}, meta=feature_meta(ctx, ["not enough return history to derive strategy proxies"]))
    metrics = []
    for c in strat.columns:
        m = performance_metrics(strat[c], ctx["annualization_factor"])
        dd = m.get("max_drawdown", 0.0)
        metrics.append({"strategy": c, **m, "kill_switch_proximity": abs(dd) / max(float(payload.get("kill_switch_drawdown") or 0.15), 1e-6)})
    corr = cached_correlation_frame(strat)
    invvol = (1 / strat.rolling(63).std().replace(0, np.nan)).div((1 / strat.rolling(63).std().replace(0, np.nan)).sum(axis=1), axis=0).fillna(0.0)
    mu = strat.mean() * ctx["annualization_factor"]
    cov = strat.cov() * ctx["annualization_factor"]
    kelly = kelly_sizing(mu, cov, None, 0.5, 1.0, 5.0)
    regimes = rolling_regimes(strat.mean(axis=1), pd.DataFrame())
    if not regimes.empty:
        rs = regimes.set_index("date")["regime"]
        rs.index = pd.to_datetime(rs.index)
        regime_weights = regime_conditional_strategy_weights(strat, rs)
    else:
        regime_weights = []
    sharpe_mom = sharpe_momentum_realloc(strat)
    cap = pd.Series({c: float(payload.get("capacity_limit") or 0.5) for c in strat.columns})
    current = pd.Series(1 / len(strat.columns), index=strat.columns)
    trade_matrix = pd.DataFrame({
        "from_equal_to_sharpe_momentum": sharpe_mom.reindex(strat.columns).fillna(0.0) - current,
        "from_equal_to_kelly": pd.Series({r["ticker"]: r["constrained_weight"] for r in kelly["table"]}).reindex(strat.columns).fillna(0.0) - current,
    }).T
    risk_budget = [{"strategy": c, "allocated_budget": 1 / len(strat.columns), "consumed_vol": float(strat[c].std() * np.sqrt(ctx["annualization_factor"]))} for c in strat.columns]
    tables = {
        "strategy_dashboard": metrics,
        "risk_budget": risk_budget,
        "kill_switch": [{"strategy": m["strategy"], "action": "cut" if m["kill_switch_proximity"] >= 1 else "watch" if m["kill_switch_proximity"] >= 0.75 else "hold", "proximity": m["kill_switch_proximity"]} for m in metrics],
        "kill_switch_pnl": kill_switch_pnl_calibration(strat),
        "kelly_strategy_weights": kelly["table"],
        "sharpe_momentum_weights": [{"strategy": k, "weight": float(v)} for k, v in sharpe_mom.items()],
        "regime_conditional_strategy_weights": regime_weights,
        "risk_attribution": cross_strategy_var_attribution(strat),
        "capacity_constrained_reallocation": capacity_constrained_realloc(current, cap, corr),
        "diversification_benefit": [diversification_benefit(strat)],
        "netting_savings": netting_savings(trade_matrix.T),
    }
    charts = {"strategy_correlation": matrix_records(corr), "dynamic_allocations": invvol.reset_index().rename(columns={"index": "date"}).tail(500).to_dict("records"), "kelly_growth": kelly["growth_curve"], "all_reallocation_rules": [{"strategy": k, "equal": float(1/len(strat.columns)), "sharpe_momentum": float(sharpe_mom[k])} for k in strat.columns]}
    notes = [] if supplied_returns else ["Strategies are deterministic proxies derived from asset returns. Provide strategy_returns for live strategy-level attribution and netting."]
    return response(FEATURE_ID, [{"label": "Strategy Count", "value": len(strat.columns)}, {"label": "Best Sharpe", "value": max([m.get("sharpe", 0.0) for m in metrics] or [0.0])}], charts, tables, meta=feature_meta(ctx, notes))
