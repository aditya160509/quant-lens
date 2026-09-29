"""Stable data and output contracts for Volatility V2 features."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_CONTRACTS: dict[str, dict[str, Any]] = {
    "01": {"title": "Multi-Estimator Daily Volatility", "required_data": ["daily_ohlcv"], "outputs": ["estimator_comparison", "efficiency_table", "dm_tournament", "agreement_index", "range_correlation"]},
    "02": {"title": "GARCH Family Suite", "required_data": ["daily_returns", "realized_volatility"], "outputs": ["model_scoreboard", "news_impact_curve", "term_structure", "pit_test", "conditional_var"]},
    "03": {"title": "HAR Forecasting Suite", "required_data": ["realized_volatility", "daily_returns", "macro_optional"], "outputs": ["har_forecasts", "accuracy_table", "jump_decomposition", "mcs_combination"]},
    "04": {"title": "Volatility Regime Detection", "required_data": ["daily_returns", "realized_volatility", "macro_optional"], "outputs": ["regime_probabilities", "transition_matrix", "method_divergence", "transition_alerts"]},
    "05": {"title": "Volatility Risk Premium Monitor", "required_data": ["implied_volatility", "realized_volatility", "daily_returns"], "outputs": ["vrp_series", "term_structure", "predictability", "regime_conditional_btz"]},
    "06": {"title": "Cross-Asset Volatility Connectedness", "required_data": ["cross_asset_returns"], "outputs": ["connectedness_index", "spillover_network", "fevd", "frequency_decomposition"]},
    "07": {"title": "Multivariate Volatility and DCC", "required_data": ["cross_asset_returns"], "outputs": ["correlation_matrices", "dcc_series", "risk_attribution", "minimum_variance_portfolio"]},
    "08": {"title": "Volatility Stress Testing", "required_data": ["cross_asset_returns", "portfolio_weights", "macro_optional"], "outputs": ["scenario_pnl", "reverse_stress", "contagion_irf", "stress_var_cvar"]},
    "09": {"title": "Portfolio Volatility Budget", "required_data": ["cross_asset_returns", "portfolio_weights"], "outputs": ["portfolio_volatility", "budget_attribution", "scaling_history", "rebalancing", "backtest"]},
}


def contract_for(feature_id: str | int) -> dict[str, Any]:
    """Return an isolated contract for a normalized feature identifier."""
    key = str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)
    if key not in _CONTRACTS:
        raise KeyError(f"Unknown Volatility V2 feature: {feature_id}")
    return deepcopy({"feature_id": key, **_CONTRACTS[key]})


def all_contracts() -> list[dict[str, Any]]:
    return [contract_for(key) for key in sorted(_CONTRACTS)]
