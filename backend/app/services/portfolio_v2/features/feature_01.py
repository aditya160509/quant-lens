"""Portfolio construction with solver, covariance and constraint diagnostics."""

import numpy as np
import pandas as pd
from ..core.context import load_context, feature_meta
from ..core.common import response
from ..core.construction import optimize_portfolios, solve_portfolio, OptimizationError
from ..core.covariance import covariance_matrix

from .inputs import inputs_for, output

FEATURE_ID = "01"
FEATURE_NAME = "Portfolio Construction Engine"


def run(payload=None):
    ctx = load_context(payload)
    payload = ctx["payload"]
    rets = ctx["returns"]
    opt = optimize_portfolios(rets, payload)
    objective = payload.get("objective", "global_min_variance")
    selected = opt["weights"][objective]
    ann = ctx["annualization_factor"]
    cov = opt["covariance"] * ann
    variance = float(selected @ cov @ selected)
    sigma = np.sqrt(variance)
    rc = selected * (cov @ selected) / sigma if sigma > 0 else selected * 0
    sample = rets.cov().to_numpy()
    diagnostics = []
    split = max(30, int(len(rets) * 0.8))
    train = rets.iloc[:split]
    test = rets.iloc[split:]
    methods = [
        "sample",
        "ledoit_wolf",
        "oas",
        "ewma",
        "constant_correlation",
        "eigenvalue_shrinkage",
        "dcc_garch",
        "factor_structured",
        "gerber",
    ]
    for method in methods:
        try:
            estimate, meta = covariance_matrix(rets, method)
            values = np.linalg.eigvalsh(estimate)
            row = {
                "estimator": method,
                "status": "ok",
                "condition_number": float(values.max() / values.min()),
                "frobenius_distance": float(
                    np.linalg.norm(estimate.to_numpy() - sample)
                ),
                "eigenvalue_participation_ratio": float(
                    values.sum() ** 2 / (values**2).sum()
                ),
                **meta,
            }
            if len(test) > 1:
                w, _ = solve_portfolio(
                    train,
                    {**payload, "covariance_estimator": method},
                    "global_min_variance",
                )
                row["oos_realized_variance"] = float((test @ w).var() * ann)
                row["oos_training_end"] = train.index[-1]
            diagnostics.append(row)
        except (ValueError, np.linalg.LinAlgError) as exc:
            diagnostics.append(
                {"estimator": method, "status": "unavailable", "reason": str(exc)}
            )
    trade = selected - ctx["weights"]
    tc = float(payload.get("transaction_cost_bps", 5)) / 10000
    history = []
    history_ends = (
        []
        if payload.get("sector_max_weights")
        else list(range(max(60, len(rets) - 12 * 21), len(rets), 21))[-12:]
    )
    for end in history_ends:
        for name in opt["weights"]:
            try:
                w, _ = solve_portfolio(rets.iloc[:end], payload, name)
                history.extend(
                    {
                        "date": rets.index[end - 1],
                        "objective": name,
                        "ticker": c,
                        "weight": float(v),
                    }
                    for c, v in w.items()
                )
            except OptimizationError as exc:
                history.append(
                    {
                        "date": rets.index[end - 1],
                        "objective": name,
                        "success": False,
                        "reason": str(exc),
                    }
                )
    valid = pd.DataFrame([r for r in history if "weight" in r])
    stability = []
    if not valid.empty:
        stability = (
            valid.groupby(["objective", "ticker"])
            .weight.agg(["std", "count"])
            .reset_index()
            .to_dict("records")
        )
    detail = next(d for d in opt["diagnostics"] if d["objective"] == objective)
    tables = {
        "optimized_weights": opt["weight_table"],
        "risk_contribution": [
            {
                "ticker": c,
                "weight": float(selected[c]),
                "risk_contribution": float(rc[c]),
            }
            for c in selected.index
        ],
        "constraint_report": detail["constraints"],
        "solver_diagnostics": opt["diagnostics"],
        "covariance_diagnostics": diagnostics,
        "turnover_costs": [
            {
                "ticker": c,
                "trade_weight": float(trade[c]),
                "estimated_cost_nav_fraction": float(abs(trade[c]) * tc),
                "trade_dollars": float(
                    trade[c] * payload.get("portfolio_nav", 1000000)
                ),
            }
            for c in trade.index
        ],
        "stability_table": stability,
    }
    charts = {
        "efficient_frontier": opt["frontier"],
        "markowitz_trace": opt["markowitz_trace"],
        "weights": opt["weight_table"],
        "risk_contribution": tables["risk_contribution"],
        "weight_history": history,
    }
    issues = [
        f"{d['objective']}: {d['message']}"
        for d in opt["diagnostics"]
        if not d["success"]
    ]
    if payload.get("sector_max_weights"):
        issues.append(
            "Historical weight stability is not produced under current sector caps: point-in-time classifications are unavailable"
        )
    return response(
        FEATURE_ID,
        [
            {"label": "Selected Objective", "value": objective},
            {"label": "Annual Vol", "value": sigma},
        ],
        charts,
        tables,
        meta={
            **feature_meta(ctx, issues),
            "covariance": opt["meta"],
            "black_litterman_prior": "User-provided market_weights or explicitly equal prior, never fabricated market caps",
            "stability": "Expanding observed-prefix allocations at the last twelve 21-observation evaluation dates; retrospective static sector labels excluded from historical backtests",
        },
        alerts=[{"severity": "warning", "message": i} for i in issues],
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("efficient_frontier", "charts", "line", True),
    output("markowitz_trace", "charts", "line", False),
    output("weights", "charts", "bar", False),
    output("risk_contribution", "charts", "bar", False),
    output("weight_history", "charts", "line", False),
    output("optimized_weights"),
    output("risk_contribution"),
    output("constraint_report"),
    output("solver_diagnostics"),
    output("covariance_diagnostics"),
    output("turnover_costs"),
    output("stability_table"),
]
