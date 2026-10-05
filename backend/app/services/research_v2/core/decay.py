"""Feature 08: Signal Decay and Arbitrage Clock."""

from __future__ import annotations

import math
import os
import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize, stats

from .data_loader import available_symbols
from .estimators import fm_slopes, sort_portfolios
from .panel import Panel, build_panel
from .stats import andrews_sup_f, auto_nw_lag, mean_test

MARKETS = {
    "US": None,
    "Europe": ("DE", "PA", "MI", "AS", "MC", "ST", "HE", "SW"),
    "UK": ("L",),
    "Japan": ("T",),
    "Emerging (India, Korea, Taiwan, Indonesia, Thailand)": ("NS", "BO", "KS", "TW", "JK", "BK"),
}
METRICS = {"ic", "ls_sharpe", "ls_mean", "fm_lambda"}


def metric_series(panel: Panel, metric: str) -> pd.Series:
    """Monthly (per formation date) performance of the signal."""

    if metric == "ic":
        return panel.signal.corrwith(panel.dependent, axis=1, method="spearman").dropna()
    if metric == "fm_lambda":
        return fm_slopes(panel.dependent, {"signal": panel.signal})["signal"].dropna()
    port = sort_portfolios(panel, 5)
    return port["long_short"].dropna() if not port.empty else pd.Series(dtype=float)


def run_decay(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("discovery_date"):
        raise ValueError("Set the discovery date: the month the anomaly was first documented.")
    panel = build_panel(payload)
    metric = str(payload.get("performance_metric") or "ic").lower()
    if metric not in METRICS:
        raise ValueError(f"performance_metric must be one of {sorted(METRICS)}")
    discovery = pd.Timestamp(payload["discovery_date"])
    publication = pd.Timestamp(payload["publication_date"]) if payload.get("publication_date") else None
    window = int(payload.get("rolling_window") or 12)
    reps = int(payload.get("bootstrap_replications") or 1000)
    models = str(payload.get("decay_model") or "all").lower()

    series = metric_series(panel, metric)
    lag = max(auto_nw_lag(len(series)), panel.holding_months)
    is_s, oos_s = series[series.index < discovery], series[series.index >= discovery]
    if len(is_s) < 12 or len(oos_s) < 12:
        raise ValueError(f"Need at least 12 months on each side of the discovery date; have {len(is_s)} before and {len(oos_s)} after ({series.index.min():%Y-%m} to {series.index.max():%Y-%m}).")

    mp_rows = [_mp_row("post_discovery", is_s, oos_s, lag, metric, panel)]
    if publication is not None:
        mp_rows.append(_mp_row("post_publication", is_s, series[series.index >= publication], lag, metric, panel))
        mp_rows.append(_mp_row("discovery_to_publication", is_s, series[(series.index >= discovery) & (series.index < publication)], lag, metric, panel))

    rolling = series.rolling(window, min_periods=max(6, window // 2)).mean().dropna()
    post_roll = rolling[rolling.index >= discovery]
    fits = fit_decay_models(post_roll, discovery, models)
    half = fits.get("exponential", {})
    ci = half_life_bootstrap(post_roll, discovery, reps) if half.get("available") else (np.nan, np.nan)
    brk = andrews_sup_f(oos_s)
    is_mean = float(is_s.mean())
    vitality = float(series.iloc[-window:].mean() / is_mean * 100) if is_mean else np.nan
    zone = "deep red" if vitality < 0 else "red" if vitality < 30 else "amber" if vitality < 70 else "green"
    decomposition = arbitrage_decomposition(panel, discovery, metric)
    intl = international_replication(payload, discovery) if payload.get("international_replication", True) else pd.DataFrame()
    sharpe = rolling_sharpe(panel, discovery, publication, brk.get("break_date"))

    curve = pd.DataFrame({"date": rolling.index, "rolling_metric": rolling.values})
    for name, f in fits.items():
        if f.get("available"):
            curve[f"{name}_fit"] = f["fitted"].reindex(rolling.index).values
    curve["floor"] = half.get("params", {}).get("c") if half.get("available") else np.nan
    comp = pd.DataFrame([{"model": n, "aic": f["aic"], "bic": f["bic"], "r2": f["r2"], "params": f["params"]} for n, f in fits.items() if f.get("available")])
    if not comp.empty:
        comp["winner"] = comp["aic"] == comp["aic"].min()
    survival = mp_rows[0]["survival_fraction"]
    hl = half.get("half_life") if half.get("available") else np.nan
    summary_text = (
        f"This signal was discovered in {discovery:%B %Y} with an in-sample {metric.upper()} of {is_mean:.4f}. "
        f"Since discovery, predictive power has {'declined' if survival < 1 else 'risen'} by {abs(1 - survival):.0%}"
        + (f", with an estimated half-life of {hl:.0f} months" + (f" (90% CI {ci[0]:.0f} to {ci[1]:.0f})" if np.isfinite(ci[1]) else " (upper bound not identified)") if np.isfinite(hl) else "")
        + (f". The arbitrage arrival date is estimated at {pd.Timestamp(brk['break_date']):%B %Y} (sup-F p = {brk['p_value']:.2f})" if brk.get("break_date") is not None else "")
        + f". Current vitality is {vitality:.0f}: {zone}."
    )
    tables = {
        "vitality_gauge": [{"vitality_score": vitality, "zone": zone, "recent_window_months": window, "in_sample_mean": is_mean}],
        "mclean_pontiff_comparison": mp_rows,
        "half_life_output": [{"half_life_months": hl, "ci90_low": ci[0], "ci90_high": ci[1], "model": "exponential", "bootstrap": f"moving-block residual bootstrap, block 12, {reps} replications", "statement": (f"The signal's predictive power has a half-life of {hl:.0f} months (90% CI: {ci[0]:.0f} to " + (f"{ci[1]:.0f} months)." if np.isfinite(ci[1]) else "unbounded; the upper end is not identified).")) if np.isfinite(hl) and np.isfinite(ci[0]) else "Exponential decay not identified."}],
        "decay_model_comparison": comp,
        "arbitrage_arrival": [{k: v for k, v in brk.items() if k != "path"}],
        "arbitrage_vs_datamining": [decomposition],
        "international_replication": intl,
        "sharpe_life_cycle": sharpe["periods"],
        "anomaly_lifecycle_summary": [{"summary": summary_text}],
    }
    charts = {
        "decay_curve": curve,
        "andrews_break_chart": brk.get("path", pd.DataFrame()),
        "long_short_sharpe_decay": sharpe["series"],
        "event_markers": [{"event": "discovery", "date": discovery}] + ([{"event": "publication", "date": publication}] if publication is not None else []) + ([{"event": "arbitrage_arrival", "date": brk["break_date"]}] if brk.get("break_date") is not None else []),
    }
    summary = [
        {"label": "Vitality", "value": vitality},
        {"label": "Survival fraction", "value": survival},
        {"label": "Half-life (months)", "value": hl},
        {"label": "Arbitrage arrival", "value": brk.get("break_date")},
    ]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"config": panel.config, "research_caveats": panel.caveats, "metric": metric}}


def _mp_row(label: str, is_s: pd.Series, oos_s: pd.Series, lag: int, metric: str, panel: Panel) -> dict[str, Any]:
    a, b = mean_test(is_s, lag), mean_test(oos_s, lag)
    scale = math.sqrt(12 / panel.holding_months) if metric == "ls_sharpe" else 1.0
    is_v = a["mean"] / is_s.std() * scale if metric == "ls_sharpe" else a["mean"]
    oos_v = b["mean"] / oos_s.std() * scale if metric == "ls_sharpe" and len(oos_s) > 1 else b["mean"]
    se = math.sqrt(a["se"] ** 2 + b["se"] ** 2) if np.isfinite(a["se"]) and np.isfinite(b["se"]) else np.nan
    t = (a["mean"] - b["mean"]) / se if se else np.nan
    return {"split": label, "is_value": is_v, "oos_value": oos_v, "survival_fraction": oos_v / is_v if is_v else np.nan, "decay_t_stat": t, "one_sided_p_value": float(stats.norm.sf(t)) if np.isfinite(t) else np.nan, "is_months": a["n"], "oos_months": b["n"], "oos_t_stat": b["t"]}


def _models() -> dict[str, Any]:
    return {
        "exponential": (lambda x, a, b, c: a * np.exp(-b * x) + c, 3),
        "linear": (lambda x, a, b: a - b * x, 2),
        "hyperbolic": (lambda x, a, b, c: a / (1 + b * x) + c, 3),
    }


def fit_decay_models(rolling: pd.Series, discovery: pd.Timestamp, which: str = "all") -> dict[str, dict[str, Any]]:
    """Nonlinear least squares with time measured in months since discovery."""

    if len(rolling) < 12:
        return {}
    t = ((rolling.index - discovery).days / 30.4375).to_numpy()
    y = rolling.to_numpy(float)
    out: dict[str, dict[str, Any]] = {}
    for name, (fn, k) in _models().items():
        if which not in {"all", name}:
            continue
        p0 = [y[0] - y[-1], 0.05, y[-1]] if k == 3 else [y[0], (y[0] - y[-1]) / max(t[-1], 1)]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                params, _ = optimize.curve_fit(fn, t, y, p0=p0, maxfev=20000, bounds=([-np.inf, 0, -np.inf], [np.inf, 5, np.inf]) if k == 3 else (-np.inf, np.inf))
        except Exception:
            out[name] = {"available": False}
            continue
        fitted = fn(t, *params)
        rss = float(((y - fitted) ** 2).sum())
        n = len(y)
        names = ["a", "b", "c"][:k]
        out[name] = {
            "available": True,
            "params": {p: float(v) for p, v in zip(names, params)},
            "fitted": pd.Series(fitted, index=rolling.index),
            "aic": n * math.log(rss / n) + 2 * k,
            "bic": n * math.log(rss / n) + k * math.log(n),
            "r2": 1 - rss / float(((y - y.mean()) ** 2).sum()),
            "half_life": float(math.log(2) / params[1]) if name == "exponential" and params[1] > 1e-6 else np.nan,
        }
    return out


def _boot_half_lives(draws: list, resid: np.ndarray, fitted: np.ndarray, index: pd.Index, discovery: pd.Timestamp, block: int, n: int) -> list[float]:
    out = []
    for starts in draws:
        boot = np.concatenate([resid[s:s + block] for s in starts])[:n]
        res = fit_decay_models(pd.Series(fitted + boot, index=index), discovery, "exponential").get("exponential", {})
        if res.get("available") and np.isfinite(res.get("half_life", np.nan)):
            out.append(res["half_life"])
    return out


def half_life_bootstrap(rolling: pd.Series, discovery: pd.Timestamp, reps: int, block: int = 12, seed: int = 0) -> tuple[float, float]:
    """90% CI for the exponential half-life from a moving-block bootstrap of the fit residuals."""

    base = fit_decay_models(rolling, discovery, "exponential").get("exponential", {})
    if not base.get("available"):
        return np.nan, np.nan
    fitted = base["fitted"]
    resid = (rolling - fitted).to_numpy()
    n = len(resid)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    draws = [rng.integers(0, max(1, n - block + 1), size=n_blocks) for _ in range(int(reps))]  # drawn serially so results do not depend on worker count
    base_fit = fitted.to_numpy()
    chunks = [draws[i::8] for i in range(8)]
    from joblib import Parallel, delayed
    from joblib.externals.loky import get_reusable_executor

    try:
        parts = Parallel(n_jobs=min(8, os.cpu_count() or 1))(delayed(_boot_half_lives)(c, resid, base_fit, rolling.index, discovery, block, n) for c in chunks)
    finally:  # loky keeps idle workers for 300 s, which stalls the one-shot job process at exit
        get_reusable_executor().shutdown(wait=True)
    halves = [h for part in parts for h in part]
    if len(halves) < 20:
        return np.nan, np.nan
    lo, hi = float(np.percentile(halves, 5)), float(np.percentile(halves, 95))
    # A decay rate near zero implies an unbounded half-life; beyond 5x the sample it is not identified.
    return lo, (hi if hi <= 5 * n else np.inf)


def arbitrage_decomposition(panel: Panel, discovery: pd.Timestamp, metric: str) -> dict[str, Any]:
    """Arbitrage vs data mining, in the spirit of McLean-Pontiff (2016).

    Arbitrage predicts larger post-discovery decay where trading is cheap
    (liquid, low idiosyncratic-volatility stocks); data mining predicts the
    same decay everywhere. The IC is computed separately in the cheap and
    costly halves of the cross-section each month.
    """

    liq = np.log((panel.context["daily"]["Close"] * panel.context["daily"]["Volume"]).resample("ME").sum().replace(0, np.nan)).reindex(index=panel.dates, columns=panel.symbols)
    ivol = panel.context["returns"].rolling(12, min_periods=8).std().reindex(index=panel.dates, columns=panel.symbols)
    cheap = (liq.rank(axis=1, pct=True) > 0.5) & (ivol.rank(axis=1, pct=True) <= 0.5)
    costly = (liq.rank(axis=1, pct=True) <= 0.5) & (ivol.rank(axis=1, pct=True) > 0.5)

    def ic(mask: pd.DataFrame) -> pd.Series:
        return panel.signal.where(mask).corrwith(panel.dependent.where(mask), axis=1, method="spearman").dropna()

    full = panel.signal.corrwith(panel.dependent, axis=1, method="spearman")
    sign = np.sign(full[full.index < discovery].mean()) or 1.0  # measure decay in the signal's own direction
    rows = {}
    for name, mask in (("cheap_to_arbitrage", cheap), ("costly_to_arbitrage", costly)):
        s = ic(mask) * sign
        pre, post = s[s.index < discovery], s[s.index >= discovery]
        decay = float(1 - post.mean() / pre.mean()) if pre.mean() > 0 else np.nan  # undefined if the sub-sample never worked
        rows[name] = {"is": float(pre.mean() * sign), "oos": float(post.mean() * sign), "decay": decay, "series": s}
    dc, dx = rows["cheap_to_arbitrage"]["decay"], rows["costly_to_arbitrage"]["decay"]
    if not (np.isfinite(dc) and np.isfinite(dx)) or dc <= 0:
        arb = np.nan
    else:
        arb = float(np.clip((dc - dx) / dc, 0, 1))
    diff = (rows["cheap_to_arbitrage"]["series"] - rows["costly_to_arbitrage"]["series"]).dropna()
    post_flag = pd.Series((diff.index >= discovery).astype(float), index=diff.index)
    x = np.column_stack([np.ones(len(diff)), post_flag.to_numpy()])
    beta, *_ = np.linalg.lstsq(x, diff.to_numpy(), rcond=None)
    import statsmodels.api as sm
    fit = sm.OLS(diff.to_numpy(), x).fit(cov_type="HAC", cov_kwds={"maxlags": 6}) if len(diff) > 24 else None
    return {
        "cheap_is_ic": rows["cheap_to_arbitrage"]["is"], "cheap_oos_ic": rows["cheap_to_arbitrage"]["oos"], "cheap_decay": dc,
        "costly_is_ic": rows["costly_to_arbitrage"]["is"], "costly_oos_ic": rows["costly_to_arbitrage"]["oos"], "costly_decay": dx,
        "arbitrage_consistent_fraction": arb,
        "data_mining_consistent_fraction": 1 - arb if np.isfinite(arb) else np.nan,
        "differential_decay_t": float(-fit.tvalues[1]) if fit is not None else np.nan,
        "interpretation": "Decay concentrated in cheap-to-arbitrage stocks points to arbitrage capital; uniform decay points to an in-sample (data-mined) artifact." + ("" if np.isfinite(arb) else " Not identified: the signal either did not work in-sample in one half of the cross-section or did not decay among cheap-to-arbitrage stocks."),
        "method": "IC computed within liquid/low-ivol (cheap) and illiquid/high-ivol (costly) halves; arbitrage share = (cheap decay - costly decay) / cheap decay",
        "metric_note": "uses IC regardless of the selected metric" if metric != "ic" else "",
    }


def international_replication(payload: dict[str, Any], discovery: pd.Timestamp) -> pd.DataFrame:
    universe = available_symbols()
    rows = []
    for market, suffixes in MARKETS.items():
        if suffixes is None:
            tickers: Any = "us_equities"
        else:
            tickers = [s for s in universe if "_" in s and s.rsplit("_", 1)[1] in suffixes][:300]
            if len(tickers) < 40:
                rows.append({"market": market, "assets": len(tickers), "status": "fewer than 40 stocks in local data"})
                continue
        try:
            p = build_panel({**payload, "universe": tickers, "max_symbols": 300, "controls": "none", "weighting": "equal", "universe_filters": [], "min_assets": 20})
        except Exception as exc:
            rows.append({"market": market, "status": f"not run: {exc}"})
            continue
        ic = p.signal.corrwith(p.dependent, axis=1, method="spearman").dropna()
        pre, post = ic[ic.index < discovery], ic[ic.index >= discovery]
        if len(pre) < 12 or len(post) < 12:
            rows.append({"market": market, "assets": len(p.symbols), "status": "fewer than 12 months on one side of discovery"})
            continue
        t_post = mean_test(post, auto_nw_lag(len(post)))
        rows.append({"market": market, "assets": len(p.symbols), "is_ic": float(pre.mean()), "oos_ic": float(post.mean()), "survival_fraction": float(post.mean() / pre.mean()) if pre.mean() else np.nan, "vitality_score": float(ic.iloc[-12:].mean() / pre.mean() * 100) if pre.mean() else np.nan, "post_ic_t": t_post["t"], "still_significant": bool(t_post["t"] > 2), "status": "ok"})
    df = pd.DataFrame(rows)
    ok = df[df.get("status") == "ok"] if "status" in df else df
    if len(ok):
        df = pd.concat([df, pd.DataFrame([{"market": "cross-market consistency", "assets": int(ok["assets"].sum()), "status": f"{int(ok['still_significant'].sum())} of {len(ok)} markets still significant post-discovery", "consistency_score": float(ok["still_significant"].mean())}])], ignore_index=True)
    return df


def rolling_sharpe(panel: Panel, discovery: pd.Timestamp, publication: pd.Timestamp | None, arbitrage: Any) -> dict[str, Any]:
    port = sort_portfolios(panel, 5)
    if port.empty:
        return {"series": pd.DataFrame(), "periods": []}
    ls = port["long_short"].dropna()
    scale = math.sqrt(12 / panel.holding_months)
    roll = (ls.rolling(12, min_periods=8).mean() / ls.rolling(12, min_periods=8).std() * scale).dropna()
    marks = [("pre_discovery", None, discovery)]
    if publication is not None:
        marks.append(("discovery_to_publication", discovery, publication))
        start = publication
    else:
        start = discovery
    if arbitrage is not None and pd.Timestamp(arbitrage) > start:
        marks += [("publication_to_arbitrage" if publication is not None else "discovery_to_arbitrage", start, pd.Timestamp(arbitrage)), ("post_arbitrage", pd.Timestamp(arbitrage), None)]
    else:
        marks.append(("post_" + ("publication" if publication is not None else "discovery"), start, None))
    periods = []
    for name, a, b in marks:
        seg = ls[((ls.index >= a) if a is not None else True) & ((ls.index < b) if b is not None else True)]
        periods.append({"period": name, "start": a, "end": b, "months": len(seg), "sharpe": float(seg.mean() / seg.std() * scale) if len(seg) > 2 and seg.std() else np.nan, "mean_return": float(seg.mean()) if len(seg) else np.nan})
    return {"series": roll.rename("rolling_sharpe").reset_index().rename(columns={"index": "date", "Date": "date"}), "periods": periods}
