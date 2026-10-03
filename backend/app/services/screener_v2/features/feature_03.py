"""S3 Composite Quant Score Engine."""

from __future__ import annotations

from typing import Any
from .inputs import shared_inputs, filter_inputs, enrich, merge_inputs

from ..core.common import access_meta, matrix_records, records, response
from ..core.composite import composite_config, component_scores, effective_num_factors, score_decomposition_for_ticker
from ..core.panel import metric_panel
from ..core.screener import apply_filters
from ..core.validation import point_in_time_scorer, score_backtest
from ..core.data_loader import parse_symbols


FEATURE_ID = "03"
FEATURE_NAME = "Composite Quant Score Engine"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master'}, {'key': 'components', 'type': 'json', 'default': None}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'top_n', 'type': 'number', 'default': 50}, {'key': 'weighting_mode', 'type': 'select', 'default': 'manual', 'options': ['manual', 'equal', 'ic_ir', 'ridge']}, {'key': 'ic_target_field', 'type': 'select', 'default': 'return_1m', 'options': ['return_1m', 'return_3m', 'return_6m']}, {'key': 'ridge_lambda', 'type': 'number', 'default': 1, 'min': 0}, {'key': 'min_training_periods', 'type': 'number', 'default': 6, 'min': 6}, {'key': 'preset', 'type': 'select', 'default': '', 'options': ['', 'aqr_quality_value', 'momentum_quality', 'low_vol_quality', 'vmq']}, {'key': 'output_scale', 'type': 'select', 'default': 'percentile', 'options': ['percentile', 'zscore', 'signed_rank']}, {'key': 'long_short', 'type': 'boolean', 'default': False}, {'key': 'score_weighted', 'type': 'boolean', 'default': False}, {'key': 'sector_neutral', 'type': 'boolean', 'default': False}, {'key': 'beta_neutral', 'type': 'boolean', 'default': False}, {'key': 'winsorize', 'type': 'boolean', 'default': False}, {'key': 'signed_rank', 'type': 'boolean', 'default': False}]))

OUTPUTS = [{'key': 'factor_correlation_heatmap', 'source': 'charts', 'render': 'heatmap', 'primary': True, 'label': 'Factor Correlation Heatmap'}, {'key': 'composite_vs_factor_backtest', 'source': 'charts', 'render': 'lineChart', 'primary': False, 'label': 'Composite Vs Factor Backtest'}, {'key': 'sector_composite_breakdown', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Sector Composite Breakdown'}, {'key': 'composite_score_universe_ranking', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Composite Score Universe Ranking'}, {'key': 'score_transparency_decomposition', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Score Transparency Decomposition'}, {'key': 'per_stock_score_decomposition', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Per Stock Score Decomposition'}, {'key': 'factor_correlation_redundancy_alerts', 'source': 'tables', 'render': 'heatmap', 'primary': False, 'label': 'Factor Correlation Redundancy Alerts'}, {'key': 'historical_weight_training', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Historical Weight Training'}, {'key': 'effective_number_of_factors', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Effective Number Of Factors'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    panel, _ = apply_filters(panel, payload)
    scored = component_scores(panel, composite_config(payload))
    component_cols = [c for c in ["Value", "Quality", "Momentum", "Low Vol", "Liquidity", "composite_score"] if c in scored.columns]
    corr = scored[component_cols].corr() if component_cols else scored.select_dtypes("number").corr()
    backtest = score_backtest(
        list(scored["ticker"]),
        scored.set_index("ticker")["composite_score"],
        int(payload.get("lookback_days") or 756),
        int(payload.get("top_n") or 50),
        long_short=bool(payload.get("long_short")),
        score_weighted=bool(payload.get("score_weighted")),
        score_at=point_in_time_scorer(symbols, payload, "composite"),
    )
    regime_breakdown = panel.groupby("sector").agg(avg_composite=("core_quant_score", "mean"), count=("ticker", "count")).reset_index()
    redundancy = []
    for row in matrix_records(corr):
        if row["row"] != row["col"] and abs(row["value"]) > 0.6:
            redundancy.append({"pair": f"{row['row']} / {row['col']}", "correlation": row["value"], "alert": "redundant_factor_pair"})
    focus = payload.get("focus_ticker") or (scored.iloc[0]["ticker"] if not scored.empty else None)
    weights = {item["component"]: item["weight"] for item in scored.attrs.get("decomposition", []) if item.get("component") in corr.columns}
    n_eff = effective_num_factors(weights, corr)
    meta_issues = ["Sector breakdown uses current industry labels, not macroeconomic regimes."]
    if scored.attrs.get("weighting_diagnostics"):
        meta_issues.append(str(scored.attrs["weighting_diagnostics"]))
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Composite universe", "value": len(scored)},
            {"label": "Top composite", "value": float(scored["composite_score"].max()) if not scored.empty else None},
            {"label": "Backtest Sharpe", "value": backtest.get("stats", {}).get("sharpe")},
            {"label": "Effective factors", "value": n_eff},
        ],
        charts={
            "factor_correlation_heatmap": matrix_records(corr),
            "composite_vs_factor_backtest": backtest.get("equity_curve", []),
            "sector_composite_breakdown": records(regime_breakdown),
        },
        tables={
            "composite_score_universe_ranking": records(scored.head(int(payload.get("top_n") or 50))),
            "score_transparency_decomposition": scored.attrs.get("decomposition", []),
            "per_stock_score_decomposition": score_decomposition_for_ticker(scored, focus),
            "factor_correlation_redundancy_alerts": redundancy,
            "historical_weight_training": [scored.attrs["weighting_diagnostics"]] if scored.attrs.get("weighting_diagnostics") else [],
            "effective_number_of_factors": [{"n_eff": n_eff, "component_count": len(weights)}],
        },
        meta=access_meta(payload, meta_issues),
    )
