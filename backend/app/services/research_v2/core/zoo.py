"""Feature 11: Cross-Sectional Dependence and Factor Zoo Positioning Engine."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .estimators import benchmark_factors, factor_alpha, sort_portfolios
from .panel import Panel, build_panel, signal_for
from .stats import HLZ_2016_BENCHMARKS, auto_nw_lag, bonferroni_t, mean_test

# Internally built long-short factors (quintile sorts on the same universe).
EXTENDED = {"quality": "profitability", "low_vol": "low_vol", "short_term_reversal": "reversal", "momentum_internal": "momentum", "value_internal": "value", "size_internal": "size", "investment_internal": "investment"}


def run_zoo(payload: dict[str, Any]) -> dict[str, Any]:
    panel = build_panel({**payload, "controls": "none"})
    lag = max(auto_nw_lag(len(panel.dates)), panel.holding_months)
    candidate = sort_portfolios(panel, 5)["long_short"].rename("candidate")
    library = str(payload.get("benchmark_library") or "ff5_mom").lower()
    ff = benchmark_factors(panel, "ff5_mom")
    factors = ff.copy()
    internal_ic: dict[str, pd.Series] = {}
    if library in {"extended", "extended_proxy", "user"}:
        for name, sig_name in EXTENDED.items():
            if sig_name == panel.config["signal"]:
                continue
            try:
                sig = signal_for(panel, sig_name)
            except Exception:
                continue
            factors[name] = sort_portfolios(panel, 5, signal=sig)["long_short"]
            internal_ic[name] = sig.corrwith(panel.dependent, axis=1, method="spearman")
        factors["bab"] = _betting_against_beta(panel)
    if library == "user" or payload.get("factor_csv_path"):
        factors = factors.join(_user_factors(payload, panel), how="left")
    subset = payload.get("spanning_factors")
    if isinstance(subset, str) and subset.strip():
        subset = [s.strip() for s in subset.split(",")]
    if subset:
        factors = factors[[c for c in factors.columns if c in subset]]
    all_factors = factors.copy()
    short = [c for c in factors.columns if factors[c].notna().mean() <= 0.5]
    factors = factors.drop(columns=short)  # keep the spanning sample long; short-history factors are reported separately

    span = factor_alpha(candidate, factors, lag)
    raw = mean_test(candidate, lag)
    corr = pd.concat([candidate, all_factors], axis=1).corr(min_periods=12)["candidate"].drop("candidate")
    max_abs = float(corr.abs().max()) if len(corr) else np.nan
    klass = "near-duplicate" if max_abs > 0.7 else "blend of existing factors" if span.get("r2", 0) > 0.5 else "genuinely new"

    tests = int(payload.get("literature_factor_count") or 450)
    threshold_mode = str(payload.get("significance_threshold") or "hlz_bhy").lower()
    thresholds = {"t_2.0": 2.0, "t_3.0": 3.0, "hlz_bonferroni": HLZ_2016_BENCHMARKS["bonferroni"], "hlz_holm": HLZ_2016_BENCHMARKS["holm"], "hlz_bhy": HLZ_2016_BENCHMARKS["bhy"], "bonferroni_current": bonferroni_t(tests)}
    required = float(payload.get("custom_threshold") or 3.0) if threshold_mode == "custom" else thresholds.get(threshold_mode, thresholds["hlz_bhy"])
    observed = abs(span["t"]) if np.isfinite(span.get("t", np.nan)) else abs(raw["t"])

    ic = panel.signal.corrwith(panel.dependent, axis=1, method="spearman").dropna()
    points = [_zoo_point("candidate", ic, candidate, panel, True)]
    for name, s in internal_ic.items():
        points.append(_zoo_point(name, s.dropna(), all_factors[name].dropna() if name in all_factors else pd.Series(dtype=float), panel, False))
    for name in [c for c in ff.columns if c in factors]:
        f = factors[name].dropna()
        points.append({"factor": name, "ic_ir": None, "sharpe": float(f.mean() / f.std() * np.sqrt(12 / panel.holding_months)) if f.std() else None, "candidate": False, "note": "return factor (no signal IC)"})

    corr_table = pd.DataFrame({"factor": corr.index, "correlation": corr.values, "near_duplicate": (corr.abs() > 0.7).values}).sort_values("correlation", key=lambda s: -s.abs())
    tables = {
        "harvey_liu_zhu_card": [{"observed_t": observed, "observed_t_source": "spanning alpha" if np.isfinite(span.get("t", np.nan)) else "raw long-short mean", "required_t": required, "threshold_rule": threshold_mode, "verdict": "clears the literature-adjusted bar" if observed >= required else "below the literature-adjusted bar", **{f"threshold_{k}": v for k, v in thresholds.items()}, "literature_factor_count": tests, "note": "HLZ (2016) benchmarks are their 5% thresholds for 316 factors through 2012; 'bonferroni_current' uses the factor count you set."}],
        "extended_spanning_test": [{"alpha": span["alpha"], "alpha_t": span["t"], "alpha_p": span.get("p"), "r2": span.get("r2"), "periods": span.get("n"), "library": library, "factor_count": factors.shape[1], "classification": klass, "excluded_short_history_factors": short, **{f"beta_{k}": v for k, v in span.get("loadings", {}).items()}, **{f"t_{k}": v for k, v in span.get("loading_t", {}).items()}}],
        "correlation_with_existing_factors": corr_table,
        "candidate_summary": [{"mean_long_short": raw["mean"], "t_stat": raw["t"], "annual_sharpe": float(candidate.mean() / candidate.std() * np.sqrt(12 / panel.holding_months)) if candidate.std() else np.nan, "ic_mean": float(ic.mean()), "ic_ir_annual": float(ic.mean() / ic.std() * np.sqrt(12 / panel.holding_months)) if ic.std() else np.nan, "months": raw["n"]}],
    }
    charts = {"zoo_positioning_chart": points, "factor_correlation_map": pd.concat([candidate, all_factors], axis=1).corr(min_periods=12).reset_index().rename(columns={"index": "factor"})}
    summary = [{"label": "Spanning α t", "value": span.get("t")}, {"label": "Required t", "value": required}, {"label": "Max |ρ|", "value": max_abs}, {"label": "Verdict", "value": klass}]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"config": panel.config, "research_caveats": panel.caveats}}


def _zoo_point(name: str, ic: pd.Series, ls: pd.Series, panel: Panel, is_candidate: bool) -> dict[str, Any]:
    scale = np.sqrt(12 / panel.holding_months)
    return {"factor": name, "ic_ir": float(ic.mean() / ic.std() * scale) if len(ic) > 2 and ic.std() else None, "sharpe": float(ls.mean() / ls.std() * scale) if len(ls) > 2 and ls.std() else None, "candidate": is_candidate}


def _betting_against_beta(panel: Panel) -> pd.Series:
    """Frazzini-Pedersen (2014) BAB: rank-weighted low- vs high-beta legs, each scaled to beta one."""

    from .panel import control_for

    beta = control_for(panel, "beta")
    rank = beta.rank(axis=1, pct=True)
    centered = rank.sub(rank.mean(axis=1), axis=0)
    k = 2 / centered.abs().sum(axis=1)
    w_low = (-centered).clip(lower=0).mul(k, axis=0)
    w_high = centered.clip(lower=0).mul(k, axis=0)
    b_low = (w_low * beta).sum(axis=1)
    b_high = (w_high * beta).sum(axis=1)
    rf = panel.factors["rf"].reindex(panel.dates).fillna(0) * panel.holding_months if "rf" in panel.factors else 0
    r = panel.dependent
    low = (w_low * r).sum(axis=1, min_count=1) - rf
    high = (w_high * r).sum(axis=1, min_count=1) - rf
    return (low / b_low.replace(0, np.nan) - high / b_high.replace(0, np.nan)).rename("bab")


def _user_factors(payload: dict[str, Any], panel: Panel) -> pd.DataFrame:
    """User factor returns: CSV with a date column and one column per factor (monthly returns)."""

    from .data_loader import _safe_user_path

    path = _safe_user_path(payload.get("factor_csv_path"))
    if path is None:
        return pd.DataFrame(index=panel.dates)
    df = pd.read_csv(path)
    date_col = next((c for c in df.columns if str(c).lower() in {"date", "month"}), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce") + pd.offsets.MonthEnd(0)
    wide = df.set_index(date_col).apply(pd.to_numeric, errors="coerce")
    h = panel.holding_months
    comp = (1 + wide).rolling(h).apply(np.prod, raw=True) - 1
    return comp.shift(-h).reindex(panel.dates).add_prefix("user_")
