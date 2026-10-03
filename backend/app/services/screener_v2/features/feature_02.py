"""S2 Formula Builder and Custom Expression Screener."""

from __future__ import annotations

from typing import Any
from .inputs import shared_inputs, filter_inputs, enrich, merge_inputs

import pandas as pd

from ..core.formula import FormulaError, evaluate_formula, formula_templates, historical_ic_comparison
from ..core.common import access_meta, records, response
from ..core.panel import metric_panel
from ..core.screener import apply_filters
from ..core.validation import point_in_time_scorer, score_backtest
from ..core.data_loader import parse_symbols


FEATURE_ID = "02"
FEATURE_NAME = "Formula Builder and Custom Expression Screener"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master'}, {'key': 'formula', 'type': 'text', 'default': '0.4*rank(earnings_yield)+0.3*rank(momentum_jt)+0.3*rank(roe)'}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'top_n', 'type': 'number', 'default': 50}, {'key': 'as_of_date', 'type': 'date', 'default': None}]))

OUTPUTS = [{'key': 'historical_formula_backtest', 'source': 'charts', 'render': 'lineChart', 'primary': True, 'label': 'Historical Formula Backtest'}, {'key': 'factor_zoo_comparison', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Factor Zoo Comparison'}, {'key': 'formula_result_table', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Formula Result Table'}, {'key': 'formula_validation_panel', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Formula Validation Panel'}, {'key': 'formula_template_library', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Formula Template Library'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    panel, _ = apply_filters(panel, payload)
    formula = payload.get("formula") or "core_quant_score"
    issues: list[str] = []
    result = evaluate_formula(panel, formula)
    panel["formula_score"] = result.values
    diagnostics = result.diagnostics
    panel["formula_rank"] = panel["formula_score"].rank(ascending=False, method="first").astype("Int64")
    ranked = panel.sort_values("formula_score", ascending=False)
    provider = point_in_time_scorer(symbols, payload, "formula")
    backtest = score_backtest(list(ranked["ticker"]), ranked.set_index("ticker")["formula_score"], int(payload.get("lookback_days") or 756), int(payload.get("top_n") or 50), score_at=provider)
    zoo = historical_ic_comparison(symbols, payload, provider)
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Formula rows", "value": len(ranked)},
            {"label": "Top formula score", "value": float(ranked["formula_score"].max()) if not ranked.empty else None},
            {"label": "Backtest Sharpe", "value": backtest.get("stats", {}).get("sharpe")},
        ],
        charts={
            "historical_formula_backtest": backtest.get("equity_curve", []),
            "factor_zoo_comparison": zoo,
        },
        tables={
            "formula_result_table": records(ranked[["formula_rank", "ticker", "sector", "formula_score", "core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile"]].head(int(payload.get("top_n") or 50))),
            "formula_validation_panel": diagnostics or [{"level": "ok", "message": "Formula parsed and evaluated against current local fields."}],
            "formula_template_library": formula_templates(),
        },
        meta=access_meta(payload, issues),
    )
