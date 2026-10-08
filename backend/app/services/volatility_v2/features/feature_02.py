"""Feature 02: arch GARCH family MLE with true held-out one-step forecasts."""

from __future__ import annotations
from .inputs import field
import numpy as np
import pandas as pd
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
    news_impact_curve,
    nyblom_stability,
    duration_backtest,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload)
    panel = returns_panel(ohlcv)
    returns = panel[assets[0]].dropna()
    frequency = payload.get("return_frequency", "daily")
    if frequency == "weekly":
        # Label a week by its last observed session, never an unobserved Friday.
        groups = [
            (period, group)
            for period, group in returns.groupby(returns.index.to_period("W-FRI"))
            if period.end_time.normalize() <= returns.index[-1].normalize()
        ]
        returns = pd.Series(
            [group.sum() for _, group in groups],
            index=[group.index[-1] for _, group in groups],
        )
    elif frequency != "daily":
        raise ValueError("return_frequency must be daily or weekly")
    if payload.get("structural_break_date"):
        returns = returns.loc[
            returns.index >= pd.Timestamp(payload["structural_break_date"])
        ]
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
        aparch_delta=payload.get("aparch_delta"),
        figarch_d=payload.get("figarch_d"),
        mcs_confidence=float(payload.get("mcs_confidence", 0.9)),
        bootstrap_reps=int(payload.get("bootstrap_reps", 200)),
    )
    selected = next(row for row in rows if row.get("winner"))
    fit = fit_model(
        returns,
        selected["model"],
        selected["distribution"],
        payload.get("aparch_delta"),
        payload.get("figarch_d"),
    )
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
    tests = max(1, len(pairs))
    for record in pairs:
        record["bonferroni_significant"] = (
            record["p_value"] is not None and record["p_value"] < 0.05 / tests
        )
    pairs += [
        {
            **record,
            "row": record["col"],
            "col": record["row"],
            "dm_stat": -record["dm_stat"] if record["dm_stat"] is not None else None,
        }
        for record in list(pairs)
    ]
    pairs += [
        {
            "row": name,
            "col": name,
            "dm_stat": 0.0,
            "p_value": 1.0,
            "observations": len(loss),
            "bonferroni_significant": False,
        }
        for name, loss in losses.items()
    ]
    failed = [row for row in rows if not row["converged"]]
    delta_benchmark, benchmark_failures = [], []
    if payload.get("include_aparch_benchmark", False):
        if len(assets) < 2:
            raise ValueError(
                "Cross-asset APARCH benchmark requires at least two explicit assets"
            )
        for symbol in assets:
            observed = panel[symbol].dropna()
            if frequency == "weekly":
                groups = [
                    (period, group)
                    for period, group in observed.groupby(
                        observed.index.to_period("W-FRI")
                    )
                    if period.end_time.normalize() <= observed.index[-1].normalize()
                ]
                observed = pd.Series(
                    [group.sum() for _, group in groups],
                    index=[group.index[-1] for _, group in groups],
                )
            if payload.get("structural_break_date"):
                observed = observed.loc[
                    observed.index >= pd.Timestamp(payload["structural_break_date"])
                ]
            for distribution in distributions or [
                "Gaussian",
                "Student-t",
                "GED",
                "Skew-t",
            ]:
                try:
                    estimated = fit_model(observed, "APARCH", distribution)
                    delta_benchmark.append(
                        {
                            "asset": symbol,
                            "distribution": distribution,
                            "delta": float(estimated.params["delta"]),
                            "observed_through": observed.index[-1],
                        }
                    )
                except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
                    benchmark_failures.append(
                        {
                            "asset": symbol,
                            "distribution": distribution,
                            "reason": str(exc),
                        }
                    )
        for record in delta_benchmark:
            matched = [
                r["delta"]
                for r in delta_benchmark
                if r["distribution"] == record["distribution"]
            ]
            record["cross_asset_percentile"] = (
                float(np.mean(np.asarray(matched) <= record["delta"]) * 100)
                if len(matched) >= 2
                else None
            )
            record["benchmark_assets"] = len(matched)
            record["unavailable_reason"] = (
                "At least two successful asset fits required"
                if len(matched) < 2
                else None
            )
    term = forecast_term_structure(
        fit,
        payload.get("horizons", [1, 5, 10, 21, 42, 63, 126, 252]),
        int(payload.get("simulations", 1000)),
        annualization=52
        if frequency == "weekly"
        else int(payload.get("annualization", 252)),
    )
    result = response(
        "02",
        [
            summary_card("Winning Model", winner),
            summary_card(
                "Next-period Conditional Vol",
                forecast_term_structure(
                    fit,
                    [1],
                    100,
                    annualization=52
                    if frequency == "weekly"
                    else int(payload.get("annualization", 252)),
                )[0]["expected_ann_vol"],
                "ann",
            ),
            summary_card("Failed Models", len(failed)),
        ],
        charts={
            "garch_term_structure": term,
            "news_impact_curve": news_impact_curve(
                fit,
                annualization=52
                if frequency == "weekly"
                else int(payload.get("annualization", 252)),
            ),
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
                {"date": record["date"], "model": key, "figarch_d": record["d"]}
                for key, fitted_path in paths.items()
                for record in fitted_path.attrs["parameter_history"]
                if "d" in record
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
            "var_backtests": [
                {**var_backtests(path, coverage), **duration_backtest(path)}
            ],
            "nyblom_stability": [nyblom_stability(fit)],
            "aparch_delta_benchmark": delta_benchmark
            or [
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
            "return_frequency": frequency,
            "aparch_benchmark_failures": benchmark_failures,
            "weekly_policy": "Sum log returns within W-FRI weeks; exclude last unfinished calendar week; labels use final observed session",
            "annualization": 52
            if frequency == "weekly"
            else int(payload.get("annualization", 252)),
            "news_impact": "Winner-specific arch volatility recursion, varying the final innovation with fitted past history held fixed; FIGARCH retains long memory",
            "parameter_history": "Past-only estimates dated by final training observation",
            "estimation": "arch MLE, expanding refits and one-step held-out variance forecasts",
            "selection": "Winner chosen retrospectively using held-out QLIKE; historical diagnostics are post-selection, not a tradable winner-switching strategy",
            "scoring_target": "Observed next-day squared close return; noisy daily variance measurement",
            "term_structure": "Terminal daily conditional volatility simulated with the fitted innovation distribution and model recursion",
            "successful_models": len(paths),
            "failed_models": len(failed),
            "removed_outputs": {
                "synthetic_vol_surface": "No observed options surface",
                "Realized-GARCH": "Daily OHLC does not supply the required intraday realized measure",
            },
        },
    )
    if failed or benchmark_failures:
        result["status"] = "warning"
    return result


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field("assets", ["SPY"], kind="symbols", group="Data"),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field(
        "annualization",
        252,
        kind="integer",
        help="Daily variance annualization, 252 or 365 observed sessions; weekly returns explicitly use 52 periods.",
    ),
    field("include_aparch_benchmark", False),
    field("return_frequency", "daily"),
    field("structural_break_date", None, kind="date", group="Data"),
    field(
        "figarch_d",
        None,
        kind="number",
        help="Hold FIGARCH d fixed and re-estimate all other parameters by constrained MLE. Omit to estimate d.",
    ),
    field("aparch_delta", None, kind="number"),
    field("mcs_confidence", 0.9),
    field("bootstrap_reps", 200),
    field("var_coverage", 0.99, kind=None, group="Model"),
    field("models", None, kind="list", group="Model"),
    field("distributions", None, kind="list", group="Model"),
    field("horizons", [1, 5, 10, 21, 42, 63, 126, 252], kind="list", group="Model"),
    field("simulations", 1000, kind=None, group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 63, kind=None, group="Model"),
    field("evaluation_days", 252, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "nyblom_stability",
        "source": "tables",
        "label": "Joint score-process stability",
        "render": "table",
        "primary": False,
        "help": "Individual fitted arch likelihood scores; Brownian-bridge asymptotic inference.",
    },
    {
        "key": "news_impact_curve",
        "source": "charts",
        "label": "Conditional news impact curve",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted conditional news impact curve. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "garch_term_structure",
        "source": "charts",
        "label": "Garch term structure",
        "render": "line",
        "primary": True,
        "help": "Actual observed or fitted garch term structure. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "pit_test",
        "source": "charts",
        "label": "Pit test",
        "render": "bar",
        "primary": False,
        "help": "Actual observed or fitted pit test. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "conditional_var_series",
        "source": "charts",
        "label": "Conditional var series",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted conditional var series. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "long_memory_parameter_series",
        "source": "charts",
        "label": "Long memory parameter series",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted long memory parameter series. No requested FIGARCH model fitted successfully.",
        "empty_reason": "No requested FIGARCH model fitted successfully.",
    },
    {
        "key": "model_comparison_scoreboard",
        "source": "tables",
        "label": "Model comparison scoreboard",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted model comparison scoreboard. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "diebold_mariano_pairwise_table",
        "source": "tables",
        "label": "Diebold mariano pairwise table",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted diebold mariano pairwise table. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "pit_diagnostics",
        "source": "tables",
        "label": "Pit diagnostics",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted pit diagnostics. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "var_backtests",
        "source": "tables",
        "label": "Var backtests",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted var backtests. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "aparch_delta_benchmark",
        "source": "tables",
        "label": "Aparch delta benchmark",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted aparch delta benchmark. No requested APARCH fit has an estimated delta; fixed-delta fits do not estimate this parameter.",
        "empty_reason": "No requested APARCH fit has an estimated delta; fixed-delta fits do not estimate this parameter.",
    },
]
