"""Real observed strategy returns, binding allocation constraints and causal kill switches."""

import pandas as pd
from ..core.common import response, matrix_records, compact_records
from ..core.data_loader import cutoff, annualization_factor
from ..core.strategies import (
    strategy_backtest,
    netting_savings,
    kill_switch_pnl_calibration,
)
from ..core.stats import performance_metrics

from .inputs import inputs_for, output

FEATURE_ID = "13"
FEATURE_NAME = "Multi-Strategy Portfolio Allocation and Risk Budgeting Engine"


def run(payload=None):
    payload = payload or {}
    if not payload.get("strategy_returns"):
        return response(
            FEATURE_ID,
            [{"label": "Strategy Count", "value": 0}],
            {},
            {
                "strategy_data_requirement": [
                    {
                        "field": "strategy_returns",
                        "reason": "Supply actual observed strategy return histories; stock-derived strategy proxies are not used",
                    }
                ]
            },
            meta={"access_issues": ["Actual strategy_returns are required"]},
        )
    frame = pd.DataFrame(payload["strategy_returns"])
    if "date" not in frame:
        raise ValueError("Strategy returns require date")
    frame.date = pd.to_datetime(frame.date, errors="raise")
    if frame.date.duplicated().any():
        raise ValueError("Duplicate strategy dates")
    if cutoff() is not None:
        frame = frame.loc[frame.date <= cutoff()]
    returns = (
        frame.set_index("date")
        .sort_index()
        .astype(float)
        .tail(int(payload.get("lookback_days", 756)))
    )
    if not 2 <= len(returns.columns) <= 20:
        raise ValueError("Select two to twenty observed strategies")
    rows, allocations, audits = strategy_backtest(returns, payload)
    latest = [r for r in allocations if r["date"] == rows.date.iloc[-1]]
    ann = annualization_factor(payload.get("frequency", "daily"))
    metrics = []
    for c in returns:
        metrics.append(
            {
                "strategy": c,
                **performance_metrics(returns[c], ann),
                "current_allocation": next(
                    r["allocated_weight"] for r in latest if r["strategy"] == c
                ),
            }
        )
    trades = pd.DataFrame(payload.get("strategy_trades", []))
    if not trades.empty:
        trades.date = pd.to_datetime(trades.date)
        if cutoff() is not None:
            trades = trades.loc[trades.date <= cutoff()]
        if set(trades.strategy) - set(returns):
            raise ValueError("Trades contain unknown strategies")
    netting = (
        netting_savings(
            trades,
            float(payload.get("transaction_cost_bps", 10)),
            float(payload.get("portfolio_nav", 1000000)),
        )
        if not trades.empty
        else []
    )
    issues = (
        []
        if not trades.empty
        else [
            "Actual underlying asset strategy_trades are required for netting; allocation differences are not underlying security trades"
        ]
    )
    table = {
        "strategy_dashboard": metrics,
        "risk_budget": audits,
        "kill_switch": latest,
        "kill_switch_pnl": kill_switch_pnl_calibration(returns),
        "netting_savings": netting,
        "portfolio_performance": [
            performance_metrics(rows.set_index("date")["return"], ann)
        ],
    }
    return response(
        FEATURE_ID,
        [{"label": "Strategy Count", "value": len(returns.columns)}],
        {
            "strategy_correlation": matrix_records(returns.corr()),
            "dynamic_allocations": allocations,
            "portfolio_equity": compact_records(rows),
        },
        table,
        meta={
            "access_issues": issues,
            "frequency": payload.get("frequency", "daily"),
            "allocation_rule": payload.get("allocation_rule", "inverse_vol"),
            "risk_policy": "Annual total volatility and component risk caps are verified alongside capacity and correlation constraints. Unallocated capital stays cash.",
            "netting": "Only supplied actual underlying asset trades are netted",
            "look_ahead": "Estimate before holding date; kill switches use prior-close drawdown",
        },
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("strategy_correlation", "charts", "heatmap", True),
    output("dynamic_allocations", "charts", "line", False),
    output("portfolio_equity", "charts", "line", False),
    output("strategy_dashboard"),
    output("risk_budget"),
    output("kill_switch"),
    output("kill_switch_pnl"),
    output("netting_savings"),
    output("portfolio_performance"),
    output("strategy_data_requirement"),
]
