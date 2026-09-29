"""Feature 01: Canonical Test Engine."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import latex_table, stars
from .estimators import (
    benchmark_factors,
    double_sort,
    factor_alpha,
    fama_macbeth,
    fm_validity,
    grs_test,
    panel_regression,
    sort_portfolios,
    sort_table,
    two_pass,
    weak_identification,
)
from .panel import Panel, build_panel, signal_for
from .stats import auto_nw_lag, mean_test, monotonic_relation_test


def run_canonical(payload: dict[str, Any]) -> dict[str, Any]:
    panel = build_panel(payload)
    return canonical_from_panel(panel, payload)


def canonical_from_panel(panel: Panel, payload: dict[str, Any]) -> dict[str, Any]:
    buckets = int(payload.get("sort_portfolios") or 5)
    benchmark = str(payload.get("factor_benchmark") or "ff5_mom").lower()
    reps = int(payload.get("bootstrap_replications") or 1000)
    nw_lag = int(payload["nw_lag"]) if payload.get("nw_lag") not in (None, "", "auto") else None
    controls = list(panel.controls)

    fm, slopes = fama_macbeth(panel, controls, nw_lag)
    validity = fm_validity(slopes, float(slopes["n_assets"].mean()) if not slopes.empty else 0.0, reps, int(fm["nw_lag"].iloc[0]) if not fm.empty else 4)

    port = sort_portfolios(panel, buckets)
    sorts = sort_table(panel, port, benchmark if benchmark in {"capm", "ff3", "ff5", "ff5_mom"} else "ff5", reps) if not port.empty else pd.DataFrame()
    factors = benchmark_factors(panel, benchmark)
    grs = grs_test(port, factors) if not port.empty else {"available": False}
    mr = monotonic_relation_test(port, reps) if not port.empty else {"available": False}

    second_name = panel.config["second_signal"]
    second = signal_for(panel, second_name)
    method = str(payload.get("double_sort_type") or "independent").lower()
    ds_means, ds_series = double_sort(panel, second, 5 if buckets >= 5 else buckets, method)

    lag = max(auto_nw_lag(len(port)), panel.holding_months) if not port.empty else 4
    ls = port["long_short"] if not port.empty else pd.Series(dtype=float)
    spanning = factor_alpha(ls, factors, lag) if len(ls) else {"alpha": np.nan}

    # Two-pass test: signal long-short as a traded factor next to the benchmark,
    # priced on the 25 double-sort portfolios (fall back to the single sort).
    tp: dict[str, Any] = {"available": False}
    weak: dict[str, Any] = {"available": False}
    if not ds_series.empty and len(ls):
        assets = ds_series if ds_series.shape[1] > factors.shape[1] + 1 else port.drop(columns="long_short")
        tp = two_pass(assets, pd.concat([factors, ls.rename("signal_ls")], axis=1), bandwidth=lag)
        if tp.get("available"):
            weak = weak_identification(tp["betas"], "signal_ls")

    rolling = rolling_fm(slopes, int(payload.get("rolling_window") or 36), lag)
    calendar = calendar_time_portfolio(panel, factors, int(payload.get("event_window_months") or 6), float(payload.get("event_quantile") or 0.8), lag)
    panel_fit = panel_regression(panel, controls, str(payload.get("fixed_effects") or "none"), _se_type(payload))
    disagreement = _bootstrap_disagreement(sorts)

    signal_row = fm[fm["term"] == "signal"].iloc[0] if not fm.empty else None
    headline_t = float(signal_row["t_stat"]) if signal_row is not None else np.nan
    fm_export = fm.assign(stars=fm["p_value"].map(stars)) if not fm.empty else fm
    spanning_row = {k: v for k, v in spanning.items() if k not in {"resid", "loadings", "loading_t"}}
    spanning_row.update({f"beta_{k}": v for k, v in spanning.get("loadings", {}).items()})

    tables = {
        "fama_macbeth_regression": fm_export,
        "fm_validity_flag": [validity],
        "panel_ols": panel_fit.get("table", pd.DataFrame()).assign(**{k: panel_fit[k] for k in ["within_r2", "overall_r2", "nobs", "asset_fe", "time_fe", "se_type"]}) if panel_fit.get("available") else [panel_fit],
        "hausman_test": [panel_fit.get("hausman", {})] if panel_fit.get("available") else [],
        "portfolio_sort": sorts,
        "double_sort_matrix": ds_means.reset_index().rename(columns={"index": "signal_bucket"}) if not ds_means.empty else [],
        "grs_test": [grs],
        "monotonicity_test": [mr],
        "factor_spanning": [{"benchmark": benchmark, **spanning_row}],
        "calendar_time_portfolio": [calendar["summary"]],
        "weak_identification_card": [weak],
        "gmm_vs_shanken_comparison": tp.get("table", pd.DataFrame()) if tp.get("available") else [tp],
        "two_pass_model_fit": [{k: tp[k] for k in ["shanken_multiplier", "j_stat", "j_p_value", "periods", "test_assets"]}] if tp.get("available") else [],
        "bootstrap_vs_ttest_disagreement": disagreement,
        "latex_export": [
            {"table": "fama_macbeth", "latex": latex_table("Fama-MacBeth regressions", fm_export)},
            {"table": "portfolio_sort", "latex": latex_table("Single portfolio sort", sorts)},
            {"table": "double_sort", "latex": latex_table("Double sort mean returns", ds_means.reset_index()) if not ds_means.empty else ""},
        ],
        "csv_export": [
            {"name": "fama_macbeth_regression", "csv": fm.to_csv(index=False)},
            {"name": "portfolio_sort", "csv": sorts.to_csv(index=False)},
            {"name": "portfolio_returns", "csv": port.to_csv()},
            {"name": "fm_slopes", "csv": slopes.to_csv()},
        ],
    }
    charts = {
        "rolling_coefficient": rolling,
        "portfolio_return_series": port.reset_index(),
        "double_sort_matrix": ds_means.reset_index().rename(columns={"index": "signal_bucket"}) if not ds_means.empty else [],
        "calendar_time_portfolio": calendar["series"],
        "cumulative_long_short": (1 + ls.fillna(0)).cumprod().rename("growth_of_1").reset_index() if len(ls) else [],
    }
    summary = [
        {"label": "Signal λ", "value": float(signal_row["lambda"]) if signal_row is not None else None},
        {"label": "FM t-stat", "value": headline_t},
        {"label": "L/S t-stat", "value": sorts.loc[sorts["portfolio"] == "long_short", "t_stat"].iloc[0] if not sorts.empty else None},
        {"label": "Spanning α t", "value": spanning.get("t")},
        {"label": "Months", "value": validity["months"]},
        {"label": "Mean assets", "value": validity["mean_assets"]},
        {"label": "FM regime", "value": validity["regime"]},
    ]
    meta = {
        "config": panel.config,
        "symbols": panel.symbols[:200],
        "research_caveats": panel.caveats,
        "headline": f"Signal '{panel.config['signal']}' Fama-MacBeth slope t = {headline_t:.2f} over {validity['months']} formation dates." if np.isfinite(headline_t) else "Insufficient data for the Fama-MacBeth slope.",
    }
    return {"summary": summary, "charts": charts, "tables": tables, "meta": meta}


def _se_type(payload: dict[str, Any]) -> str:
    raw = str(payload.get("se_type") or "clustered_both").lower()
    return {"newey_west": "driscoll_kraay", "double_cluster": "clustered_both", "time_cluster": "clustered_time", "asset_cluster": "clustered_asset", "ols": "unadjusted"}.get(raw, raw)


def rolling_fm(slopes: pd.DataFrame, window: int, lag: int) -> pd.DataFrame:
    """Rolling Fama-MacBeth slope with NW 95% bands and significance flags."""

    if slopes.empty or len(slopes) < window:
        return pd.DataFrame()
    s = slopes["signal"]
    rows = []
    for end in range(window, len(s) + 1):
        chunk = s.iloc[end - window:end]
        test = mean_test(chunk, min(lag, window // 4))
        rows.append({"date": s.index[end - 1], "beta": test["mean"], "lower_95": test["mean"] - 1.96 * test["se"], "upper_95": test["mean"] + 1.96 * test["se"], "t_stat": test["t"]})
    out = pd.DataFrame(rows)
    out["significance"] = np.where(out["lower_95"] > 0, "positive", np.where(out["upper_95"] < 0, "negative", "insignificant"))
    return out


def calendar_time_portfolio(panel: Panel, factors: pd.DataFrame, window: int, quantile: float, lag: int) -> dict[str, Any]:
    """Calendar-time portfolio of assets whose signal entered the top ``quantile`` in the prior ``window`` formation dates.

    The event is "signal rank crosses above ``quantile``". Each month the
    portfolio holds, equally weighted, every asset with such an event in the
    prior ``window`` periods; its excess return is regressed on the benchmark.
    """

    rank = panel.signal.rank(axis=1, pct=True)
    event = (rank >= quantile) & (rank.shift(1) < quantile)
    held = event.rolling(window, min_periods=1).max().astype(bool)
    rets = panel.dependent.where(held)
    port = rets.mean(axis=1)
    count = held.sum(axis=1)
    rf = panel.factors["rf"].reindex(panel.dates).fillna(0) * panel.holding_months if "rf" in panel.factors else 0
    excess = (port - rf).where(count >= 10)
    fit = factor_alpha(excess.dropna(), factors, lag)
    summary = {"event": f"signal rank crosses above {quantile:.0%}", "holding_window": window, "alpha": fit["alpha"], "alpha_t": fit["t"], "alpha_p": fit.get("p"), "r2": fit.get("r2"), "months": fit.get("n"), "mean_holdings": float(count[count > 0].mean()) if (count > 0).any() else 0.0}
    series = pd.DataFrame({"date": panel.dates, "portfolio_return": port.values, "holdings": count.values})
    return {"summary": summary, "series": series}


def _bootstrap_disagreement(sorts: pd.DataFrame) -> pd.DataFrame:
    if sorts.empty:
        return sorts
    out = sorts[["portfolio", "t_stat", "p_value", "bootstrap_p_value"]].copy()
    out["classical_significant"] = out["p_value"] < 0.05
    out["bootstrap_significant"] = out["bootstrap_p_value"] < 0.05
    out["disagreement"] = out["classical_significant"] != out["bootstrap_significant"]
    return out
