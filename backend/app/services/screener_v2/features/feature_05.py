"""S5 Screener Backtester with Point-in-Time Validation."""

from __future__ import annotations

from typing import Any
from .inputs import shared_inputs, filter_inputs, enrich, merge_inputs

import pandas as pd

from ..core.common import access_meta, records, response
from ..core.panel import metric_panel
from ..core.validation import point_in_time_scorer, score_backtest, score_backtest_by_weekday
from ..core.data_loader import close_matrix, parse_symbols


FEATURE_ID = "05"
FEATURE_NAME = "Screener Backtester with Point-in-Time Validation"


def _rebalance_days(payload: dict[str, Any]) -> int:
    frequency = str(payload.get("rebalance_frequency") or "").lower()
    return {"weekly": 5, "monthly": 21, "quarterly": 63}.get(frequency, max(1, int(payload.get("rebalance_days") or 21)))


def _holding_period_stats(prices: pd.DataFrame, holding_days: int) -> dict[str, Any]:
    if prices.empty or len(prices) <= holding_days:
        return {"holding_days": holding_days, "observations": 0, "mean_forward_return": None, "median_forward_return": None, "hit_rate": None}
    basket = prices.ffill().mean(axis=1)
    forward = basket.shift(-holding_days) / basket - 1.0
    forward = forward.iloc[::holding_days].dropna()
    return {
        "holding_days": holding_days,
        "observations": int(len(forward)),
        "mean_forward_return": float(forward.mean()) if len(forward) else None,
        "median_forward_return": float(forward.median()) if len(forward) else None,
        "forward_return_volatility": float(forward.std(ddof=1)) if len(forward) > 1 else None,
        "hit_rate": float((forward > 0).mean()) if len(forward) else None,
    }

INPUTS = merge_inputs(shared_inputs() + filter_inputs(), enrich([{'key': 'universe', 'type': 'ticker_list', 'default': 'master'}, {'key': 'score_field', 'type': 'select', 'default': 'core_quant_score'}, {'key': 'lookback_days', 'type': 'number', 'default': 756}, {'key': 'top_n', 'type': 'number', 'default': 50}, {'key': 'transaction_cost_bps', 'type': 'number', 'default': 10}, {'key': 'long_short', 'type': 'boolean', 'default': False}, {'key': 'score_weighted', 'type': 'boolean', 'default': False}, {'key': 'run_full_pbo', 'type': 'boolean', 'default': False}, {'key': 'rebalance_frequency', 'type': 'select', 'default': 'monthly', 'options': ['weekly', 'monthly', 'quarterly']}, {'key': 'rebalance_days', 'type': 'number', 'default': 21, 'min': 1}, {'key': 'pbo_partitions', 'type': 'select', 'default': 8, 'options': [4, 6, 8, 10, 12]}, {'key': 'run_holding_sensitivity', 'type': 'boolean', 'default': True}]))

OUTPUTS = [{'key': 'equity_curve', 'source': 'charts', 'render': 'lineChart', 'primary': True, 'label': 'Equity Curve'}, {'key': 'rolling_performance', 'source': 'charts', 'render': 'lineChart', 'primary': False, 'label': 'Rolling Performance'}, {'key': 'full_performance_statistics', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Full Performance Statistics'}, {'key': 'rebalancing_date_sensitivity', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Rebalancing Date Sensitivity'}, {'key': 'rebalancing_date_sensitivity_by_weekday', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Rebalancing Date Sensitivity By Weekday'}, {'key': 'turnover_report', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Turnover Report'}, {'key': 'stock_level_attribution', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Stock Level Attribution'}, {'key': 'position_trade_log', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Position Trade Log'}, {'key': 'position_entry_exit_log', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Position Entry Exit Log'}, {'key': 'cscv_pbo', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Cscv Pbo'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    score_field = payload.get("score_field") or "core_quant_score"
    if score_field not in panel:
        raise ValueError(f"Unknown score field: {score_field}")
    score = panel.set_index("ticker")[score_field]
    provider = point_in_time_scorer(symbols, payload, field=score_field)
    kwargs = dict(lookback_days=int(payload.get("lookback_days", 756)), top_n=int(payload.get("top_n", 50)),
                  cost_bps=float(payload.get("transaction_cost_bps", 10)),
                  long_short=bool(payload.get("long_short")), score_weighted=bool(payload.get("score_weighted")),
                  rebalance_days=_rebalance_days(payload), sector_neutral=bool(payload.get("sector_neutral")),
                  score_at=provider)
    backtest = score_backtest(symbols, score, **kwargs)
    selected = backtest.get("selected", [])
    sensitivity = []
    candidates = {}
    for offset in [0, 5, 10, 15, 20]:
        result = backtest if offset == 0 else score_backtest(symbols, score, **kwargs, rebalance_offset_days=offset)
        sensitivity.append({"rebalance_offset_days": offset, **result["stats"]})
        candidates[f"offset_{offset}"] = result["daily_returns"]
    pbo = None
    if payload.get("run_full_pbo"):
        from ..core.backtest import cscv_pbo
        pbo = cscv_pbo(pd.DataFrame(candidates).dropna(), int(payload.get("pbo_partitions", 8)))
    sector_attr = []
    stock_attr = backtest.get("attribution", [])
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Selected stocks", "value": len(selected)},
            {"label": "Sharpe", "value": backtest.get("stats", {}).get("sharpe")},
            {"label": "Max drawdown", "value": backtest.get("stats", {}).get("max_drawdown")},
        ],
        charts={
            "equity_curve": backtest.get("equity_curve", []),
            "rolling_performance": backtest.get("rolling", []),

        },
        tables={
            "full_performance_statistics": [backtest.get("stats", {})],
            "rebalancing_date_sensitivity": sensitivity,
            "rebalancing_date_sensitivity_by_weekday": score_backtest_by_weekday(symbols, score, **kwargs),
            "turnover_report": backtest["turnover"],
            "stock_level_attribution": stock_attr,
            "position_trade_log": backtest["trades"],
            "position_entry_exit_log": backtest["positions"],
            "cscv_pbo": [pbo] if pbo else [],
        },
        meta=access_meta(payload, ["Current local universe has survivorship bias; no delisted-security return data exists. Historical sector-neutral execution is unavailable. Holding-period sensitivity and regime attribution were removed until supported by a valid historical implementation."]),
    )
