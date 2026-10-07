"""Feature 9: Strategy Capacity Analyzer."""

import numpy as np

from app.services.factors_v2.core.analytics import perf_stats, response

_ALMGREN_ETA = 0.1
_SQRT_MODEL_THRESHOLD_USD = 100_000_000.0


def _zero_crossing(aums, values):
    for i in range(len(values)):
        if values[i] <= 0:
            if i == 0:
                return float(aums[0])
            return float(
                np.interp(0, [values[i], values[i - 1]], [aums[i], aums[i - 1]])
            )
    return None


def run(payload):
    from app.services.factors_v2.core.capacity import cost_sweep
    from app.services.factors_v2.core.backtest import portfolio_backtest

    bt = portfolio_backtest(payload, include_bins=False)
    gross = perf_stats(bt["gross"]).get("annualized_return")
    aums = np.asarray(
        payload.get("aum_grid")
        or np.geomspace(1e6, 1e10, int(payload.get("aum_points", 20))),
        float,
    )
    if (aums <= 0).any() or not np.isfinite(aums).all():
        raise ValueError("AUM points must be finite and positive")
    aums = np.sort(aums)
    rows = cost_sweep(payload, aums)
    for row in rows:
        row.update(
            gross_alpha=gross,
            net_alpha=gross - row["annual_cost"] if gross is not None else None,
        )
    capacity = (
        _zero_crossing(aums, np.array([r["net_alpha"] for r in rows], float))
        if gross is not None
        else None
    )
    sensitivity = []
    for step in [5, 21, 63]:
        for cap in [0.1, 0.15, 0.25]:
            case = cost_sweep(
                {**payload, "rebalance_days": step, "participation_cap": cap}, aums
            )
            c = (
                _zero_crossing(aums, np.array([gross - r["annual_cost"] for r in case]))
                if gross is not None
                else None
            )
            sensitivity.append(
                {
                    "rebalance_days": step,
                    "participation_cap": cap,
                    "capacity": c,
                    "method": "recomputed_per_security_cost_sweep",
                }
            )
    memo = "Capacity is a scenario estimate using observed USD ADV and explicit square-root impact assumptions. Gross return comes from dated stock re-selection and next-close execution. A missing crossing stays unavailable."
    return response(
        "feature_09",
        summary_cards=[
            {"label": "Scenario capacity crossing", "value": capacity, "unit": "USD"}
        ],
        charts={"capacity_curve": rows},
        tables={"slippage_by_aum": rows, "sensitivity": sensitivity},
        meta={
            "allocator_memo": memo,
            "impact_model": "per_security_parameterized_square_root",
            "impact_eta": payload.get("impact_eta", 0.1),
            "factor_return_basis": "dated_stock_portfolio",
            "capacity_status": "crossing_in_grid"
            if capacity is not None
            else "no_crossing_in_grid",
            "missing_output_reasons": {
                "optimal_aum": "Half of capacity is not an optimized AUM estimate"
            },
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("09")
OUTPUTS = _outputs("09")
