"""S2 Formula Builder and Custom Expression Screener."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.analytics import FormulaError, access_meta, evaluate_formula, formula_templates, metric_panel, records, response, score_backtest
from ..core.data_loader import parse_symbols


FEATURE_ID = "02"
FEATURE_NAME = "Formula Builder and Custom Expression Screener"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "formula", "type": "text", "default": "0.4*rank(earnings_yield)+0.3*rank(momentum_jt)+0.3*rank(roe)"},
    {"key": "lookback_days", "type": "number", "default": 756},
    {"key": "top_n", "type": "number", "default": 50},
    {"key": "as_of_date", "type": "date", "default": None},
]

OUTPUTS = ["formula_result_table", "formula_validation_panel", "historical_formula_backtest", "factor_zoo_comparison"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    formula = payload.get("formula") or "core_quant_score"
    issues: list[str] = []
    try:
        result = evaluate_formula(panel, formula)
        panel["formula_score"] = result.values
        diagnostics = result.diagnostics
    except FormulaError as exc:
        panel["formula_score"] = panel.get("core_quant_score", pd.Series(index=panel.index)).fillna(0)
        diagnostics = [{"level": "error", "message": str(exc), "fallback": "core_quant_score"}]
        issues.append(f"Formula failed validation and fell back to core_quant_score: {exc}")
    panel["formula_rank"] = panel["formula_score"].rank(ascending=False, method="first").astype(int)
    ranked = panel.sort_values("formula_score", ascending=False)
    backtest = score_backtest(list(ranked["ticker"]), ranked.set_index("ticker")["formula_score"], int(payload.get("lookback_days") or 756), int(payload.get("top_n") or 50))
    zoo_cols = [c for c in ranked.select_dtypes("number").columns if c not in {"formula_rank"}]
    target_fields = [c for c in ["return_1d", "return_1w", "return_1m", "return_3m", "return_6m", "return_12m"] if c in ranked]
    zoo = []
    for col in zoo_cols:
        row = {"factor": col, "mean": float(ranked[col].mean()), "top_decile_cutoff": float(ranked[col].quantile(0.9)), "coverage": float(ranked[col].notna().mean())}
        for target_field in target_fields:
            valid = ranked[col].notna() & ranked[target_field].notna()
            row[f"ic_vs_{target_field}"] = ranked.loc[valid, col].corr(ranked.loc[valid, target_field], method="spearman") if int(valid.sum()) > 3 else None
        zoo.append(row)
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
