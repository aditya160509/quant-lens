"""S4 Academic Strategy Screener Library."""

from __future__ import annotations

from typing import Any

from ..core.academic import (
    academic_strategy_scores,
    altman_history,
)
from ..core.common import access_meta, records, response
from ..core.data_loader import parse_symbols
from ..core.panel import metric_panel
from ..core.screener import apply_filters
from .inputs import enrich, filter_inputs, merge_inputs, shared_inputs

FEATURE_ID = "04"
FEATURE_NAME = "Academic Strategy Screener Library"

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master'}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'top_n', 'type': 'number', 'default': 50}, {'key': 'strategy', 'type': 'select', 'default': 'magic_formula', 'options': ['magic_formula', 'acquirers_multiple', 'value_composite', 'novy_marx_gpa', 'momentum_jt', 'low_vol', 'sloan_accruals', 'graham_net_net', 'high_dividend_low_payout', 'interest_coverage_distress', 'piotroski_f_score', 'altman_z_score', 'altman_z_double_prime']}, {'key': 'long_short', 'type': 'boolean', 'default': False}]))

OUTPUTS = [{'key': 'per_strategy_stock_list', 'source': 'tables', 'render': 'table', 'primary': True, 'label': 'Per Strategy Stock List'}, {'key': 'piotroski_breakdown', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Piotroski Breakdown'}, {'key': 'altman_z_score_status', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Altman Z Score Status'}, {'key': 'altman_z_score_8q_trend', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Altman Z Score 8Q Trend'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=1000)
    panel = metric_panel(payload, symbols=symbols)
    panel, _ = apply_filters(panel, payload)
    strategies = academic_strategy_scores(panel)
    strategy = payload.get("strategy") or "magic_formula"
    if strategy not in strategies.columns:
        raise ValueError(f"Unknown or unsupported academic strategy: {strategy}")
    ranked = strategies.sort_values(strategy, ascending=False)
    focus = str(payload.get("focus_ticker") or ranked.iloc[0]["ticker"]) if not ranked.empty else ""
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Selected strategy", "value": strategy},
            {"label": "Top score", "value": float(ranked[strategy].max()) if not ranked.empty else None},
        ],
        charts={},
        tables={
            "per_strategy_stock_list": records(ranked.head(int(payload.get("top_n") or 50))),
            "piotroski_breakdown": records(strategies[[c for c in strategies.columns if c.startswith("piotroski_") or (c.startswith("f") and c[1:2].isdigit()) or c in {"ticker", "sector"}]].sort_values("piotroski_f_score", ascending=False).head(100)),
            "altman_z_score_status": records(strategies[["ticker", "sector", "altman_z_score", "altman_z_double_prime", "altman_status", "altman_piotroski_overlay"]].sort_values("altman_z_score", ascending=False).head(100)),
            "altman_z_score_8q_trend": altman_history(focus, 8) if focus else [],
        },
        meta=access_meta(payload, ["Every strategy is rebuilt on its formation date. Conservative 90-day statement availability does not reconstruct filing vintages or revisions. Unsupported named approximations were removed; missing criteria remain unknown."]),
    )
