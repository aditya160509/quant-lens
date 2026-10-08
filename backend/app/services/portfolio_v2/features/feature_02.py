"""Honest walk-forward portfolio evaluation and strategy-selection inference."""

import numpy as np
import pandas as pd
from ..core.context import load_context, feature_meta
from ..core.common import response, compact_records
from ..core.backtest import walk_forward, drawdown_episodes
from ..core.stats import (
    performance_metrics,
    probabilistic_sharpe,
    deflated_sharpe_ratio,
    min_track_record_length,
    harvey_liu_correction,
    pbo_cscv,
    omega_ratio,
    ulcer_index,
    calmar_ratio,
    up_down_capture,
    politis_romano_block,
    value_at_risk_methods,
)
from ..core.data_loader import returns_matrix

from .inputs import inputs_for, output

FEATURE_ID = "02"
FEATURE_NAME = "Honest Backtesting Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    variants = payload.get(
        "variant_objectives", ["global_min_variance", "max_sharpe", "risk_parity"]
    )
    if payload.get("weights") is not None:
        # Manual targets are one strategy, regardless of optimizer labels.
        variants = [payload.get("objective", "global_min_variance")]
    if len(set(variants)) != len(variants) or not variants:
        raise ValueError("Variant objectives must be nonempty and unique")
    selected = payload.get("objective", "global_min_variance")
    if selected not in variants:
        variants = [selected, *variants]
    evaluated = {}
    all_rows = {}
    for name in variants:
        rows, trades, folds = walk_forward(
            ctx["raw_returns"], {**ctx["payload"], "objective": name}
        )
        all_rows[name] = (rows, trades, folds)
        evaluated[name] = rows.set_index("date").net_return
    rows, trades, folds = all_rows[selected]
    net = rows.set_index("date").net_return
    benchmark = payload.get("benchmark", "equal_weight")
    if benchmark == "equal_weight":
        baseline, _, _ = walk_forward(
            ctx["raw_returns"],
            {
                **payload,
                "weights": {c: 1 / len(ctx["symbols"]) for c in ctx["symbols"]},
            },
        )
        bench = baseline.set_index("date").net_return
    else:
        bench = (
            returns_matrix([benchmark], ctx["lookback_days"], ctx["frequency"])
            .iloc[:, 0]
            .reindex(net.index)
        )
        if bench.isna().any():
            raise ValueError("Benchmark has missing observed returns")
    ann = ctx["annualization_factor"]
    metrics = performance_metrics(net, ann)
    if (
        metrics["sharpe"] is None
        or metrics["skew"] is None
        or metrics["kurtosis"] is None
    ):
        raise ValueError("Sharpe inference requires nonconstant observed returns")
    sr = metrics["sharpe"] / np.sqrt(ann)
    sk = metrics["skew"]
    ku = metrics["kurtosis"]
    panel = pd.DataFrame(evaluated).dropna()
    pbo = (
        pbo_cscv(panel, int(payload.get("pbo_partitions", 8)))
        if panel.shape[1] > 1
        else {
            "pbo": None,
            "distribution": [],
            "reason": "At least two distinct evaluated strategies required",
        }
    )
    trials = int(payload.get("parameter_trials", len(variants)))
    if trials < len(variants):
        raise ValueError(
            "parameter_trials cannot be less than evaluated strategy count"
        )
    trial_srs = panel.mean() / panel.std()
    variance = (
        float(trial_srs.var(ddof=1)) if len(trial_srs) > 1 else 1 / (len(net) - 1)
    )
    dsr = deflated_sharpe_ratio(sr, len(net), trials, sk, ku, variance)
    psr = probabilistic_sharpe(sr, len(net), skew=sk, excess_kurtosis=ku)
    monthly = (1 + net).resample("ME").prod() - 1
    active = net - bench
    benchmark_variance = float(bench.var())
    beta = (
        float(net.cov(bench) / benchmark_variance) if benchmark_variance > 0 else None
    )
    metrics.update(
        {
            "benchmark_beta": beta,
            "benchmark_correlation": float(net.corr(bench))
            if benchmark_variance > 0
            else None,
            "annual_arithmetic_alpha": float((net.mean() - beta * bench.mean()) * ann)
            if beta is not None
            else None,
            "treynor_ratio_zero_rf": float(net.mean() * ann / beta)
            if beta not in {None, 0}
            else None,
            "active_annual_mean_return": float(active.mean() * ann),
            "annual_tracking_error": float(active.std() * np.sqrt(ann)),
            "information_ratio": float(active.mean() / active.std() * np.sqrt(ann))
            if active.std() > 0
            else None,
            "omega_ratio": omega_ratio(net),
            "ulcer_index": ulcer_index(net),
            "calmar_ratio": calmar_ratio(net, ann),
            **up_down_capture(net, bench),
            "politis_romano_block_length": politis_romano_block(net),
            "total_turnover": float(rows.turnover.sum()),
            "total_cost_nav_fractions": float(rows.cost.sum()),
        }
    )
    eq = rows.set_index("date").net
    charts = {
        "equity_curve": compact_records(rows),
        "drawdown": compact_records(
            (eq / eq.cummax().clip(lower=1) - 1).rename("drawdown").reset_index()
        ),
        "monthly_heatmap": [
            {
                "date": date,
                "year": date.year,
                "month": date.month,
                "return": float(value),
            }
            for date, value in monthly.items()
        ],
        "pbo_distribution": pbo["distribution"],
        "risk_methods": value_at_risk_methods(
            net,
            float(payload.get("var_confidence", 0.95)),
            int(payload.get("var_simulations", 10000)),
        ),
    }
    tables = {
        "performance_table": [metrics],
        "psr_dsr": [
            {
                "psr": psr,
                "dsr": dsr,
                "pbo": pbo["pbo"],
                "trials": trials,
                "evaluated_variants": len(variants),
                "trial_period_sharpe_variance": variance,
                "min_track_record_length_observations": min_track_record_length(
                    sr, skew=sk, kurtosis=ku + 3
                ),
                "frequency": ctx["frequency"],
                **harvey_liu_correction(
                    sr, trials=trials, n_obs=len(net), skew=sk, excess_kurtosis=ku
                ),
            }
        ],
        "walk_forward": folds,
        "rebalance_trades": trades,
        "drawdown_episodes": drawdown_episodes(net),
        "bias_audit": [
            {
                "test": "survivorship_bias",
                "status": "unavailable",
                "reason": "Historical index membership and complete delisting returns are absent. Explicit fixed universe only.",
            }
        ],
    }
    return response(
        FEATURE_ID,
        [
            {"label": "Net Sharpe", "value": metrics["sharpe"]},
            {"label": "DSR", "value": dsr},
        ],
        charts,
        tables,
        meta={
            **feature_meta(ctx),
            "selection": "Refit on training dates strictly before each holding date; drift positions and charge absolute executed notional, including initial funding",
            "pbo": {k: v for k, v in pbo.items() if k != "distribution"},
            "dsr_assumption": "Trial Sharpes treated as independent; supply the total trial count, including unreported trials",
        },
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("equity_curve", "charts", "line", True),
    output("drawdown", "charts", "line", False),
    output("monthly_heatmap", "charts", "heatmap", False),
    output("pbo_distribution", "charts", "histogram", False),
    output("risk_methods", "charts", "bar", False),
    output("performance_table"),
    output("psr_dsr"),
    output("walk_forward"),
    output("rebalance_trades"),
    output("drawdown_episodes"),
    output("bias_audit"),
]
