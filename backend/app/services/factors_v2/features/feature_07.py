"""Feature 7: Factor Backtesting Engine."""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.services.factors_v2.core.backtest import portfolio_backtest as backtest_series
from app.services.factors_v2.core.analytics import compact_series, perf_stats, response


def run(payload):
    bt = backtest_series(payload)
    gross, net = bt["gross"], bt["net"]
    simulations = int(payload.get("mc_simulations", 100))
    paths = _stationary_bootstrap_equity(
        net.to_numpy(),
        simulations,
        np.random.default_rng(1907),
        int(payload.get("mc_block_days", 21)),
    )
    bands = pd.DataFrame(
        dict(
            date=net.index,
            p10=np.percentile(paths, 10, axis=0),
            median=np.percentile(paths, 50, axis=0),
            p90=np.percentile(paths, 90, axis=0),
        )
    )
    equity = bt["equity_net"]
    dd = equity / equity.cummax().clip(lower=1) - 1
    stats_g, stats_n = perf_stats(gross), perf_stats(net)
    return response(
        "feature_07",
        summary_cards=[
            {"label": "Gross Sharpe", "value": stats_g.get("sharpe")},
            {"label": "Net Sharpe", "value": stats_n.get("sharpe")},
            {"label": "Max Drawdown", "value": stats_n.get("max_drawdown")},
        ],
        charts={
            "equity_curve": {
                "gross": compact_series(bt["equity_gross"]),
                "net": compact_series(equity),
            },
            "drawdown": compact_series(dd),
            "monte_carlo_bands": bands.to_dict("records"),
            "quintile_monotonicity": bt["quintiles"],
            "decile_monotonicity": bt["deciles"],
        },
        tables={
            "statistics": [{"type": "gross", **stats_g}, {"type": "net", **stats_n}],
            "transaction_costs": bt["trades"],
            "turnover_analysis": bt["trades"],
            "gross_vs_net_by_year": _annual_gross_net(gross, net),
        },
        meta={
            "factor": bt["factor"],
            "mc_simulations": simulations,
            "bootstrap_method": "arch StationaryBootstrap with geometrically distributed blocks",
            "transaction_cost_model": bt["cost_model"]["cost_formula"],
            "rebalance_days": payload.get("rebalance_days")
            or {"daily": 1, "weekly": 5, "monthly": 21, "quarterly": 63, "annual": 252}[
                payload.get("refit_frequency", "monthly")
            ],
            "missing_output_reasons": {
                "walk_forward_optimization": "Fixed declared factor weights are re-ranked at each formation; trained adaptive composite weights are not offered",
                "impact_costs": "This backtest applies explicit traded-notional bps and borrow bps; capacity scenarios are separate Feature 9 outputs",
            },
            "return_basis": "USD observed stock prices; holdings marked only on available quotes; missing held observations fail",
        },
    )


def _empty_quintile_rows(reason: str) -> List[Dict[str, Any]]:
    return [
        {
            "quintile": f"Q{i + 1}",
            "annual_return": None,
            "avg_period_return": None,
            "n_stocks": 0,
            "warning": reason,
            "method": "unavailable_no_fabrication",
            "monotonicity_score": None,
        }
        for i in range(5)
    ]


def _stationary_bootstrap_equity(returns, simulations, rng, block_size=21):
    from arch.bootstrap import StationaryBootstrap

    values = np.asarray(returns, float)
    if not np.isfinite(values).all():
        raise ValueError("Bootstrap returns must be observed and finite")
    if not len(values):
        return np.empty((simulations, 0))
    boot = StationaryBootstrap(max(1, min(block_size, len(values))), values, seed=rng)
    return np.array(
        [np.cumprod(1 + sample[0][0]) for sample in boot.bootstrap(simulations)]
    )


def _annual_gross_net(gross: pd.Series, net: pd.Series) -> List[Dict[str, Any]]:
    if not isinstance(gross.index, pd.DatetimeIndex):
        return []
    g = (1 + gross).resample("YE").prod() - 1
    n = (1 + net).resample("YE").prod() - 1
    rows = []
    for idx in g.index.union(n.index):
        gross_val = float(g.get(idx, np.nan))
        net_val = float(n.get(idx, np.nan))
        rows.append(
            {
                "year": int(idx.year),
                "gross_return": gross_val,
                "net_return": net_val,
                "implementation_shortfall": gross_val - net_val,
            }
        )
    return rows


def _rolling_premium_spread(gross: pd.Series, net: pd.Series) -> List[Dict[str, Any]]:
    if gross.empty:
        return []
    rows = []
    for window, label in [(252, "12m"), (756, "36m")]:
        spread = (
            gross.rolling(window, min_periods=max(30, window // 4)).sum()
            - net.rolling(window, min_periods=max(30, window // 4)).sum()
        )
        for idx, value in spread.tail(220).dropna().items():
            rows.append(
                {
                    "date": str(pd.Timestamp(idx).date()),
                    "window": label,
                    "gross_net_cost_spread": float(value),
                }
            )
    return rows


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("07")
OUTPUTS = _outputs("07")
