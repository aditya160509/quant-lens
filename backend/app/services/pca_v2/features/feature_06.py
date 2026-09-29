"""Feature 06: Constrained PCA portfolio optimization with RMT covariance.

Objectives available via payload["objective"]:
  - "mean_variance" (default): Markowitz mean-variance via CVXPY
  - "erc" / "risk_parity": Equal Risk Contribution (Spinu 2013)
  - "max_sharpe" / "msp": Maximum Sharpe Portfolio (Tobin separation)
  - "pc_factor_risk_parity": equalize retained PC variance contributions

Black-Litterman views: payload["bl_views"] = [{"assets": {"AAPL": 0.5, "MSFT": -0.5}, "return": 0.05, "confidence": 0.7}]
Turnover constraint: payload["previous_weights"] = {"AAPL": 0.1, ...}, payload["turnover_max"] = 0.3
"""

from __future__ import annotations

from app.services.pca_v2.core.analytics import (
    k_sensitivity_sweep,
    metadata,
    optimize_portfolio,
    optimize_portfolio_with_duals,
    pc_factor_risk_parity_portfolio,
    response,
    risk_decomposition,
    robust_frontier_ellipsoidal,
    rmt_model,
)


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    opt = optimize_portfolio_with_duals(model, payload)
    risk = risk_decomposition(model, {**payload, "weights": {r["ticker"]: r["weight"] for r in opt["weights"]}})

    # K-sensitivity sweep (OOS Sharpe vs K)
    try:
        k_sweep = k_sensitivity_sweep(model, payload, oos_fraction=float(payload.get("oos_fraction") or 0.3))
    except Exception:
        k_sweep = []
    robust_frontier = robust_frontier_ellipsoidal(model, payload)
    pc_rp = pc_factor_risk_parity_portfolio(model, payload)
    unconstrained_payload = {**payload}
    unconstrained_payload.pop("turnover_max", None)
    unconstrained_payload.pop("previous_weights", None)
    no_turnover = optimize_portfolio(model, unconstrained_payload)
    sample_model = {**model, "cleaned_cov": model["raw_cov"]}
    sample_opt = optimize_portfolio(sample_model, payload)
    transaction_panel = _allocation_comparison(opt["weights"], no_turnover["weights"], "with_turnover_constraint", "without_turnover_constraint")
    covariance_comparison = _allocation_comparison(opt["weights"], sample_opt["weights"], "rmt_cleaned", "raw_sample")

    return response(
        "06",
        [
            {"label": "Expected Return", "value": opt["expected_return"], "unit": "ann"},
            {"label": "Optimized Vol", "value": opt["annualized_vol"], "unit": "ann"},
            {"label": "Sharpe (Ann)", "value": (opt["expected_return"] / max(opt["annualized_vol"], 1e-6)) if opt["annualized_vol"] else None, "unit": "ratio"},
            {"label": "Objective", "value": opt.get("objective", "mean_variance"), "unit": "type"},
            {"label": "Solver", "value": opt["status"], "unit": "status"},
        ],
        charts={
            "efficient_frontier": opt["frontier"],
            "optimal_weights": opt["weights"],
            "pc_factor_risk_parity": pc_rp["contributions"],
            "pc_factor_risk_parity_weights": pc_rp["weights"],
            "robust_vs_standard_frontier": robust_frontier,
            "k_sensitivity_oos_sharpe": k_sweep,
            "transaction_cost_impact_panel": transaction_panel,
            "rmt_vs_sample_allocation": covariance_comparison,
        },
        tables={
            "optimal_portfolio_weights": opt["weights"],
            "risk_contribution_table": risk["factor_rows"],
            "pc_factor_risk_parity_table": pc_rp["contributions"],
            "pc_factor_risk_parity_weights": pc_rp["weights"],
            "constraint_shadow_prices": opt.get("shadow_prices", []),
            "black_litterman_posterior": [{"note": "BL views applied via payload['bl_views'] if provided; otherwise historical means used."}],
            "k_sensitivity_table": k_sweep,
            "transaction_cost_impact_panel": transaction_panel,
            "rmt_vs_sample_allocation": covariance_comparison,
        },
        meta=metadata(model, {
            "implemented_outputs": 12,
            "cvxpy_status": opt["status"],
            "objective": opt.get("objective"),
            "pc_factor_risk_parity_status": pc_rp["status"],
            "bl_views_count": len(payload.get("bl_views") or []),
            "turnover_constraint": payload.get("turnover_max"),
        }),
    )


def _allocation_comparison(left_rows, right_rows, left_label, right_label):
    left = {row["ticker"]: float(row["weight"]) for row in left_rows}
    right = {row["ticker"]: float(row["weight"]) for row in right_rows}
    return [{"ticker": ticker, left_label: left.get(ticker, 0.0), right_label: right.get(ticker, 0.0), "difference": left.get(ticker, 0.0) - right.get(ticker, 0.0)} for ticker in sorted(set(left) | set(right))]
