"""Feature 02: arch GARCH family MLE with true held-out one-step forecasts."""

from __future__ import annotations
import numpy as np
from scipy import stats
from app.services.volatility_v2.core.analytics import (
    load_assets,
    returns_panel,
    response,
    summary_card,
    compact_records,
    newey_west_lrv,
)
from app.services.volatility_v2.core.garch import (
    evaluate_suite,
    fit_model,
    var_backtests,
    forecast_term_structure,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload)
    returns = returns_panel(ohlcv)[assets[0]].dropna()
    coverage = float(payload.get("var_coverage", 0.99))
    models, distributions = payload.get("models"), payload.get("distributions")
    if isinstance(models, str):
        models = [m.strip() for m in models.split(",")]
    if isinstance(distributions, str):
        distributions = [d.strip() for d in distributions.split(",")]
    rows, paths, losses, winner = evaluate_suite(
        returns,
        models,
        distributions,
        min_train=int(payload.get("min_train", 252)),
        refit_interval=int(payload.get("refit_interval", 63)),
        evaluation_days=int(payload.get("evaluation_days", 252)),
        coverage=coverage,
    )
    selected = next(row for row in rows if row.get("winner"))
    fit = fit_model(returns, selected["model"], selected["distribution"])
    path = paths[winner]
    diagnostic = stats.kstest(path.pit, "uniform")
    hist, edges = np.histogram(path.pit, bins=20, range=(0, 1))
    pairs = []
    for i, a in enumerate(losses):
        for b in list(losses)[i + 1 :]:
            difference = (losses[a] - losses[b]).dropna()
            lrv = newey_west_lrv(difference.to_numpy())
            value = (
                float(difference.mean() / np.sqrt(lrv / len(difference)))
                if lrv > 0
                else None
            )
            pairs.append(
                {
                    "row": a,
                    "col": b,
                    "dm_stat": value,
                    "p_value": float(2 * stats.norm.sf(abs(value)))
                    if value is not None
                    else None,
                    "observations": len(difference),
                }
            )
    failed = [row for row in rows if not row["converged"]]
    term = forecast_term_structure(
        fit,
        payload.get("horizons", [1, 5, 10, 21, 42, 63, 126, 252]),
        int(payload.get("simulations", 1000)),
    )
    result = response(
        "02",
        [
            summary_card("Winning Model", winner),
            summary_card(
                "Next-day Conditional Vol", term[0]["expected_ann_vol"], "ann"
            ),
            summary_card("Failed Models", len(failed)),
        ],
        charts={
            "garch_term_structure": term,
            "pit_test": [
                {
                    "bin_start": float(edges[i]),
                    "bin_end": float(edges[i + 1]),
                    "count": int(count),
                }
                for i, count in enumerate(hist)
            ],
            "conditional_var_series": compact_records(path.reset_index()),
            "long_memory_parameter_series": [
                {
                    "model": f"{r['model']}-{r['distribution']}",
                    "figarch_d": r["parameters"]["d"],
                }
                for r in rows
                if "d" in r.get("parameters", {})
            ],
        },
        tables={
            "model_comparison_scoreboard": rows,
            "diebold_mariano_pairwise_table": pairs,
            "pit_diagnostics": [
                {
                    "ks_stat": float(diagnostic.statistic),
                    "ks_p_value": float(diagnostic.pvalue),
                    "note": "Uniform PIT uses fitted innovation distribution at each forecast origin; KS p-value does not adjust for serial dependence or model selection",
                }
            ],
            "var_backtests": [var_backtests(path, coverage)],
            "aparch_delta_benchmark": [
                {
                    "model": f"{r['model']}-{r['distribution']}",
                    "delta": r["parameters"]["delta"],
                }
                for r in rows
                if "delta" in r.get("parameters", {})
            ],
        },
        alerts=[
            {
                "level": "warning",
                "message": f"{len(failed)} requested model fits failed; see scoreboard",
            }
        ]
        if failed
        else [],
        meta={
            "asset": assets[0],
            "estimation": "arch MLE, expanding refits and one-step held-out variance forecasts",
            "selection": "Winner chosen retrospectively using held-out QLIKE; historical diagnostics are post-selection, not a tradable winner-switching strategy",
            "scoring_target": "Observed next-day squared close return; noisy daily variance measurement",
            "term_structure": "Terminal daily conditional volatility simulated with the fitted innovation distribution and model recursion",
            "successful_models": len(paths),
            "failed_models": len(failed),
            "removed_outputs": {
                "synthetic_vol_surface": "No observed options surface",
                "Nyblom": "Chunk dispersion is not a score-based stability test",
                "duration_test": "Rolling breach count is not a duration test",
                "Realized-GARCH": "Daily OHLC does not supply the required intraday realized measure",
                "news_impact_curve": "One generic recursion cannot represent all five fitted families",
            },
        },
    )
    if failed:
        result["status"] = "warning"
    return result
