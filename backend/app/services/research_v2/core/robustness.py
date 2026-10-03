"""Feature 02: Robustness Engine.

Each specification changes the base Feature 1 test along one dimension
(sequential mode) or several at once (specification-curve mode) and re-runs the
Fama-MacBeth slope and the long-short spread on the same point-in-time panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any

import numpy as np
import pandas as pd

from .common import latex_table
from .estimators import fm_slopes, sort_portfolios
from .panel import CONTROL_SETS, Panel, _transform_frame, _weights, build_panel, control_for
from .stats import auto_nw_lag, mean_test

CRISES = {
    "exclude_gfc": ("2008-01-01", "2009-12-31"),
    "exclude_covid": ("2020-03-01", "2020-04-30"),
    "exclude_2022_rates": ("2022-01-01", "2022-12-31"),
    "exclude_liberation_day": ("2025-04-01", "2025-05-31"),
}
SPLITS = ["2008-09-15", "2020-03-01", "2022-01-01"]
TRANSFORMS = ["raw", "winsorize", "rank", "zscore", "decile"]
CONTROL_VARIANTS = ["none", "size", "size,value", "size,value,momentum", "size,value,momentum,volatility", "full"]
NW_LAGS = [3, 6, 12]
WEIGHTINGS = ["equal", "value", "rank"]
UNIVERSES = ["all", "large_cap", "ex_financials", "ex_utilities", "top_500", "top_1000"]
DIMENSIONS = ["time_window", "subsample", "crisis", "universe", "transform", "controls", "standard_errors", "weighting"]


@dataclass
class Spec:
    time_window: str = "full"
    subsample: str = "full"
    crisis: str = "none"
    universe: str = "all"
    transform: str = "raw"
    controls: str = "base"
    standard_errors: str = "nw_auto"
    weighting: str = "equal"
    extra: dict[str, Any] = field(default_factory=dict)

    def name(self) -> str:
        parts = [f"{d}={getattr(self, d)}" for d in DIMENSIONS if getattr(self, d) != Spec.__dataclass_fields__[d].default]
        return "base" if not parts else "; ".join(parts)


def control_variants(panel: Panel) -> list[str]:
    """Base plus each control set that is a distinct regression once the signal itself is removed."""

    seen = {tuple(panel.controls)}
    out = ["base"]
    for v in CONTROL_VARIANTS:
        resolved = tuple(c for c in CONTROL_SETS[v] if c != panel.config["signal"])
        if resolved not in seen:
            seen.add(resolved)
            out.append(v)
    return out


def dimension_values(panel: Panel, payload: dict[str, Any]) -> dict[str, list[str]]:
    custom_split = payload.get("custom_split_date")
    custom_exclusion = payload.get("custom_exclusion_start") and payload.get("custom_exclusion_end")
    values = {
        "time_window": ["full", "last_60m", "last_120m"],
        "subsample": ["full", *[f"pre_{d[:4]}" for d in SPLITS], *[f"post_{d[:4]}" for d in SPLITS], *([f"pre_{custom_split}", f"post_{custom_split}"] if custom_split else [])],
        "crisis": ["none", *CRISES, *(["exclude_custom"] if custom_exclusion else [])],
        "universe": UNIVERSES,
        "transform": TRANSFORMS,
        "controls": control_variants(panel),
        "standard_errors": ["nw_auto", *[f"nw_{l}" for l in NW_LAGS]],
        "weighting": WEIGHTINGS,
    }
    selected = payload.get("dimensions")
    if isinstance(selected, str):
        selected = [d.strip() for d in selected.split(",") if d.strip()]
    if selected:
        values = {k: (v if k in selected else v[:1]) for k, v in values.items()}
    return values


def build_specs(values: dict[str, list[str]], mode: str, cap: int, seed: int = 0) -> tuple[list[Spec], int]:
    """Sequential: base plus one change at a time. Curve: full Cartesian grid (sampled when above ``cap``)."""

    if mode == "specification_curve":
        grid = list(itertools.product(*[values[d] for d in DIMENSIONS]))
        total = len(grid)
        if total > cap:
            rng = np.random.default_rng(seed)
            keep = sorted(rng.choice(total, size=cap - 1, replace=False).tolist())
            grid = [grid[0]] + [grid[i] for i in keep if i != 0][: cap - 1]
        return [Spec(**dict(zip(DIMENSIONS, combo))) for combo in grid], total
    specs = [Spec()]
    for dim in DIMENSIONS:
        for value in values[dim][1:]:
            specs.append(Spec(**{dim: value}))
    return specs[:cap], len(specs)


class SpecEvaluator:
    """Evaluates specifications against one panel, reusing precomputed controls."""

    def __init__(self, panel: Panel, payload: dict[str, Any]):
        self.panel = panel
        self.payload = payload
        needed = sorted({c for key in CONTROL_VARIANTS for c in CONTROL_SETS[key]} | set(panel.controls))
        self.controls = {c: (panel.controls[c] if c in panel.controls else control_for(panel, c)) for c in needed}
        self.base_controls = list(panel.controls)
        rank = panel.market_cap.rank(axis=1, ascending=False)
        self.top = {n: rank <= n for n in (500, 1000)}

    def date_mask(self, spec: Spec) -> pd.Series:
        dates = self.panel.dates
        mask = pd.Series(True, index=dates)
        if spec.time_window.startswith("last_"):
            months = int(spec.time_window.split("_")[1].rstrip("m"))
            mask &= dates >= dates.max() - pd.DateOffset(months=months)
        if spec.subsample != "full":
            side, raw = spec.subsample.split("_", 1)
            cut = pd.Timestamp(next((d for d in SPLITS if d.startswith(raw)), raw))
            mask &= (dates < cut) if side == "pre" else (dates >= cut)
        if spec.crisis != "none":
            if spec.crisis == "exclude_custom":
                lo, hi = pd.Timestamp(self.payload["custom_exclusion_start"]), pd.Timestamp(self.payload["custom_exclusion_end"])
            else:
                lo, hi = (pd.Timestamp(x) for x in CRISES[spec.crisis])
            holding_end = dates + pd.DateOffset(months=self.panel.holding_months)
            mask &= ~((dates <= hi) & (holding_end >= lo))  # drop any holding period overlapping the window
        return mask

    def asset_mask(self, spec: Spec) -> pd.DataFrame | None:
        u = spec.universe
        if u == "all":
            return None
        if u in {"top_500", "top_1000"}:
            return self.top[int(u.split("_")[1])]
        from .panel import _universe_mask
        return _universe_mask([u], self.panel.market_cap, self.panel.symbols)

    def evaluate(self, spec: Spec, signal: pd.DataFrame | None = None, with_spread: bool = True) -> dict[str, Any]:
        p = self.panel
        sig = p.signal if signal is None else signal
        if spec.transform != "raw":
            sig = _transform_frame(sig.reindex_like(p.signal), spec.transform)
        dmask = self.date_mask(spec)
        amask = self.asset_mask(spec)
        if amask is not None:
            sig = sig.where(amask)
        sig = sig.loc[dmask.to_numpy()]
        dep = p.dependent.loc[sig.index]
        names = self.base_controls if spec.controls == "base" else [c for c in CONTROL_SETS[spec.controls] if c != p.config["signal"]]
        regs = {"signal": sig, **{n: self.controls[n].loc[sig.index] for n in names}}
        slopes = fm_slopes(dep, regs)
        row: dict[str, Any] = {"specification": spec.name(), **{d: getattr(spec, d) for d in DIMENSIONS}}
        if len(slopes) < 12:
            return {**row, "coefficient": np.nan, "se": np.nan, "t_stat": np.nan, "months": len(slopes), "status": "insufficient data (< 12 months)"}
        lag = auto_nw_lag(len(slopes)) if spec.standard_errors == "nw_auto" else int(spec.standard_errors.split("_")[1])
        lag = max(lag, p.holding_months)
        test = mean_test(slopes["signal"], lag)
        row.update({
            "coefficient": test["mean"], "se": test["se"], "t_stat": test["t"], "p_value": test["p"],
            "significant_5pct": bool(test["p"] < 0.05), "significant_10pct": bool(test["p"] < 0.10),
            "r2": float(slopes["r2"].mean()), "months": int(len(slopes)), "mean_assets": float(slopes["n_assets"].mean()),
            "nw_lag": lag, "status": "ok",
        })
        if with_spread:
            weights = _weights(spec.weighting, sig, p.market_cap.loc[sig.index])
            local = p.subset_dates(dmask.to_numpy())
            local = Panel(**{**local.__dict__, "signal": sig, "weights": weights})
            port = sort_portfolios(local, int(self.payload.get("sort_portfolios") or 5))
            if not port.empty:
                ls = port["long_short"].dropna()
                ls_test = mean_test(ls, max(auto_nw_lag(len(ls)), p.holding_months))
                row.update({"ls_annual_return": float(ls.mean() * 12 / p.holding_months), "ls_t_stat": ls_test["t"], "ls_sharpe": float(ls.mean() / ls.std() * np.sqrt(12 / p.holding_months)) if ls.std() else np.nan})
        return row


def run_robustness(payload: dict[str, Any]) -> dict[str, Any]:
    panel = build_panel(payload)
    return robustness_from_panel(panel, payload)


def robustness_from_panel(panel: Panel, payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "sequential").lower()
    cap = min(int(payload.get("max_specifications") or (60 if mode == "sequential" else 400)), 5000)
    values = dimension_values(panel, payload)
    specs, total = build_specs(values, mode, cap)
    ev = SpecEvaluator(panel, payload)
    df = pd.DataFrame([ev.evaluate(s) for s in specs])
    ok = df[df["status"] == "ok"].copy()
    base = ok.iloc[0] if not ok.empty and ok.iloc[0]["specification"] == "base" else None
    base_coef = float(base["coefficient"]) if base is not None else np.nan
    ok["sign_flip"] = np.sign(ok["coefficient"]) != np.sign(base_coef)
    ok["within_50pct_of_base"] = (ok["coefficient"] - base_coef).abs() <= 0.5 * abs(base_coef)

    weighting = str(payload.get("weighting_philosophy") or "unweighted").lower()
    w = _spec_weights(ok, weighting, ev)
    joint = joint_permutation_test(ev, [s for s in specs if s.name() in set(ok["specification"])], int(payload.get("permutation_replications") or 200))
    attribution = decision_attribution(ok)
    n_sig = int(ok["significant_5pct"].sum())
    n_sig10 = int(ok["significant_10pct"].sum())
    n_pos = int((ok["coefficient"] > 0).sum())
    weakest = ok.loc[ok["t_stat"].abs().idxmin()] if not ok.empty else None
    strongest = ok.loc[ok["t_stat"].abs().idxmax()] if not ok.empty else None
    q = ok["coefficient"].quantile([0, 0.25, 0.5, 0.75, 1]).tolist() if not ok.empty else [np.nan] * 5
    iqr = q[3] - q[1]
    outliers = ok[(ok["coefficient"] < q[1] - 1.5 * iqr) | (ok["coefficient"] > q[3] + 1.5 * iqr)]["specification"].tolist()

    curve = ok.sort_values("coefficient").reset_index(drop=True)
    curve["rank"] = np.arange(1, len(curve) + 1)
    curve["lower_95"] = curve["coefficient"] - 1.96 * curve["se"]
    curve["upper_95"] = curve["coefficient"] + 1.96 * curve["se"]
    decision_panel = curve[["rank", "specification", *DIMENSIONS]]
    summary_line = f"Result significant in {n_sig} of {len(ok)} specifications ({n_sig / max(len(ok), 1):.0%}) at 5% and {n_sig10} at 10%. Coefficient positive in {n_pos} of {len(ok)} specifications."
    weighted_median = _weighted_median(ok["coefficient"].to_numpy(), w) if len(ok) else np.nan

    tables = {
        "robustness_matrix": ok,
        "robustness_summary_line": [{"summary": summary_line, "significant_5pct": n_sig, "significant_10pct": n_sig10, "positive": n_pos, "specifications": len(ok), "base_coefficient": base_coef, "weighted_median_coefficient": weighted_median, "weighting_philosophy": weighting}],
        "curve_level_joint_p_value": [joint],
        "researcher_degrees_of_freedom": [{"reasonable_specifications": total, "run_specifications": len(df), "usable_specifications": len(ok), "mode": mode, "message": f"You had access to {total} distinct reasonable specifications from the selected dimensions."}],
        "decision_attribution_panel": attribution,
        "weakest_specification": [_explain(weakest, base_coef, "weakest")] if weakest is not None else [],
        "strongest_specification": [_explain(strongest, base_coef, "strongest")] if strongest is not None else [],
        "economic_magnitude_range": [{"min_ls_annual_return": ok["ls_annual_return"].min() if "ls_annual_return" in ok else np.nan, "max_ls_annual_return": ok["ls_annual_return"].max() if "ls_annual_return" in ok else np.nan, "min_coefficient": q[0], "max_coefficient": q[4], "share_within_50pct_of_base": float(ok["within_50pct_of_base"].mean()) if len(ok) else np.nan}],
        "coefficient_stability_stats": [{"min": q[0], "q1": q[1], "median": q[2], "q3": q[3], "max": q[4], "outliers": outliers, "sign_flips": int(ok["sign_flip"].sum())}],
        "skipped_specifications": df[df["status"] != "ok"][["specification", "status"]],
        "latex_export": [{"table": "robustness_matrix", "latex": latex_table("Robustness of the signal slope", ok[["specification", "coefficient", "se", "t_stat", "r2", "months"]])}],
    }
    charts = {
        "specification_curve": curve,
        "decision_panel": decision_panel,
        "coefficient_stability": ok[["specification", "coefficient", "t_stat"]],
        "permutation_null": [{"median_t": v} for v in joint.pop("null_distribution", [])],
    }
    summary = [
        {"label": "Specifications", "value": len(ok)},
        {"label": "Significant 5%", "value": f"{n_sig}/{len(ok)}"},
        {"label": "Positive", "value": f"{n_pos}/{len(ok)}"},
        {"label": "Curve p-value", "value": joint.get("p_value")},
        {"label": "Degrees of freedom", "value": total},
    ]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"config": panel.config, "research_caveats": panel.caveats}}


def joint_permutation_test(ev: SpecEvaluator, specs: list[Spec], reps: int, seed: int = 7) -> dict[str, Any]:
    """Curve-level permutation test (Simonsohn, Simmons & Nelson 2020 style).

    The signal is shuffled across assets within each formation date, which
    destroys any signal-return link while keeping the cross-sectional
    distribution and all controls. Every specification is re-estimated on each
    shuffle; the statistic is the median |t| across specifications.
    """

    specs = specs[:40]
    if not specs or reps <= 0:
        return {"p_value": np.nan, "replications": 0}
    observed = float(np.nanmedian(np.abs([ev.evaluate(s, with_spread=False)["t_stat"] for s in specs])))
    rng = np.random.default_rng(seed)
    base = ev.panel.signal.to_numpy()
    null = []
    for _ in range(int(reps)):
        shuffled = base.copy()
        for i in range(shuffled.shape[0]):
            row = shuffled[i]
            finite = np.isfinite(row)
            row[finite] = rng.permutation(row[finite])
        sig = pd.DataFrame(shuffled, index=ev.panel.dates, columns=ev.panel.symbols)
        null.append(float(np.nanmedian(np.abs([ev.evaluate(s, signal=sig, with_spread=False)["t_stat"] for s in specs]))))
    null_arr = np.asarray(null)
    return {
        "statistic": "median |t| across specifications",
        "observed": observed,
        "p_value": float((1 + np.sum(null_arr >= observed)) / (1 + len(null_arr))),
        "replications": len(null_arr),
        "specifications_in_test": len(specs),
        "null_95th": float(np.quantile(null_arr, 0.95)),
        "null_distribution": null_arr.tolist(),
    }


def decision_attribution(ok: pd.DataFrame) -> list[dict[str, Any]]:
    """Share of the curve's coefficient variance explained by each dimension (eta squared)."""

    if len(ok) < 3 or ok["coefficient"].var() == 0:
        return []
    total = float(((ok["coefficient"] - ok["coefficient"].mean()) ** 2).sum())
    rows = []
    for dim in DIMENSIONS:
        if ok[dim].nunique() < 2:
            continue
        group_means = ok.groupby(dim)["coefficient"].transform("mean")
        between = float(((group_means - ok["coefficient"].mean()) ** 2).sum())
        rows.append({"dimension": dim, "variance_explained": between / total, "choices": int(ok[dim].nunique()), "most_influential_choice": ok.groupby(dim)["coefficient"].mean().sub(ok["coefficient"].mean()).abs().idxmax()})
    return sorted(rows, key=lambda r: -r["variance_explained"])


def _spec_weights(ok: pd.DataFrame, philosophy: str, ev: SpecEvaluator) -> np.ndarray:
    if ok.empty:
        return np.array([])
    if philosophy == "sample_size":
        return (ok["months"] * ok["mean_assets"]).to_numpy(float)
    if philosophy == "inverse_variance":
        return (1 / ok["se"].pow(2)).to_numpy(float)
    if philosophy in {"aic", "bic"}:
        # Information criterion of the pooled cross-sectional regression y ~ signal + controls
        # on each specification's own sample; weights are Akaike/Schwarz weights exp(-delta/2).
        ic = []
        for _, row in ok.iterrows():
            n = row["months"] * row["mean_assets"]
            k = 2 + (len(ev.base_controls) if row["controls"] == "base" else len(CONTROL_SETS[row["controls"]]))
            rss_proxy = n * (1 - row["r2"])
            ic.append(n * np.log(rss_proxy / n) + (2 * k if philosophy == "aic" else k * np.log(n)))
        ic = np.asarray(ic)
        return np.exp(-(ic - ic.min()) / 2)
    return np.ones(len(ok))


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(cum, 0.5)])


def _explain(row: pd.Series, base: float, kind: str) -> dict[str, Any]:
    changed = [f"{d} = {row[d]}" for d in DIMENSIONS if row[d] not in {"full", "none", "all", "raw", "base", "nw_auto", "equal"}]
    what = ", ".join(changed) if changed else "the base specification"
    direction = "shrinks" if abs(row["coefficient"]) < abs(base) else "grows"
    return {
        "specification": row["specification"],
        "coefficient": row["coefficient"],
        "t_stat": row["t_stat"],
        "months": row["months"],
        "explanation": f"The {kind} result comes from {what}: the slope {direction} to {row['coefficient']:.4f} (t = {row['t_stat']:.2f}) versus {base:.4f} in the base, using {int(row['months'])} months.",
    }
