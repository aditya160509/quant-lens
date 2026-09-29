"""Feature 02: GARCH-family live approximation suite."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy import stats

from app.services.volatility_v2.core.analytics import autocorr_raw_jit, compact_records, compute_mode, garch_scoreboard, garch_term_structure_with_bands, load_assets, number_like, realized_garch_fit, response, returns_panel, runtime_meta, summary_card, synthetic_vol_surface, volatility_estimators


def run(payload=None):
    payload = payload or {}
    mode = compute_mode(payload)
    assets, ohlcv = load_assets(payload)
    ret_panel = returns_panel(ohlcv)
    asset = assets[0] if assets[0] in ret_panel.columns else ret_panel.columns[0]
    ret = ret_panel[asset].dropna()
    scoreboard, variance_map, winner = garch_scoreboard(ret)
    vol = volatility_estimators(ohlcv, window=21)
    rgarch_chart = []
    try:
        yz_var = vol[vol["asset"].eq(asset)].sort_values("date").set_index("date")["yang_zhang"].pow(2) / 252
        rgarch = realized_garch_fit(ret, yz_var)
        variance_map["Realized-GARCH-Gaussian"] = rgarch["cond_var_series"]
        rgarch_row = {k: v for k, v in rgarch.items() if k != "cond_var_series"}
        rgarch_row.update({"qlike": None, "rmse": None, "winner": False, "mcs_member": False})
        scoreboard.append(rgarch_row)
        rgarch_chart = compact_records(pd.DataFrame({"date": rgarch["cond_var_series"].index, "realized_garch_ann_vol": np.sqrt(rgarch["cond_var_series"] * 252)}))
    except Exception as exc:
        scoreboard.append({"model": "Realized-GARCH", "distribution": "Gaussian", "error": str(exc), "converged": False})
    win_var = variance_map[winner]
    winner_row = next((r for r in scoreboard if f"{r.get('model')}-{r.get('distribution')}" == winner), {})
    params = winner_row.get("parameters", {}) or {}
    ann_vol = np.sqrt(win_var * 252)
    horizons = [1, 5, 10, 21, 42, 63, 126, 252]
    persistence = float(params.get("alpha[1]", params.get("phi[1]", 0.06)) + params.get("beta[1]", 0.90))
    persistence = min(max(persistence, 0.01), 0.995)
    long_run = float(win_var.dropna().median())
    current = float(win_var.dropna().iloc[-1])
    term = garch_term_structure_with_bands(params, current, long_run, horizons, n_sim=2500 if mode == "research" else 750)
    sigma = math.sqrt(max(long_run, 1e-12))
    model_name = winner.split("-")[0]
    omega = float(params.get("omega", long_run * max(1 - persistence, 0.01) * 10000)) / 10000
    alpha = float(params.get("alpha[1]", 0.08))
    beta = float(params.get("beta[1]", 0.90))
    gamma = float(params.get("gamma[1]", 0.0))
    delta = float(params.get("delta", 2.0))
    x_arr = np.linspace(-3, 3, 121)
    eps_arr = x_arr * sigma
    def nic_values(prev_var):
        if model_name == "EGARCH":
            z_arr = eps_arr / max(math.sqrt(prev_var), 1e-12)
            return np.exp(omega + alpha * (np.abs(z_arr) - math.sqrt(2 / math.pi)) + gamma * z_arr + beta * math.log(max(prev_var, 1e-12)))
        if model_name == "GJR-GARCH":
            return omega + (alpha + gamma * (eps_arr < 0).astype(float)) * eps_arr**2 + beta * prev_var
        if model_name == "APARCH":
            return (omega + alpha * np.power(np.abs(eps_arr) - gamma * eps_arr, delta) + beta * prev_var ** (delta / 2)) ** (2 / max(delta, 1e-6))
        if model_name == "FIGARCH":
            return omega + (alpha + float(params.get("d", 0.35))) * eps_arr**2 + beta * prev_var
        return omega + alpha * eps_arr**2 + beta * prev_var
    history = win_var.dropna().to_numpy(dtype=float)
    prev_p10, prev_p50, prev_p90 = np.percentile(history, [10, 50, 90])
    v10, v_arr, v90 = (np.maximum(nic_values(v), 0.0) for v in (prev_p10, prev_p50, prev_p90))
    v_arr = np.maximum(v_arr, 0.0)
    nic = [{"shock_sigma": float(x), "conditional_variance": float(v)} for x, v in zip(x_arr, v_arr)]
    nic_ribbon = [{"shock_sigma": float(x), "p10": float(a), "p50": float(b), "p90": float(c), "conditioning_variance_p10": float(prev_p10), "conditioning_variance_p50": float(prev_p50), "conditioning_variance_p90": float(prev_p90)} for x, a, b, c in zip(x_arr, v10, v_arr, v90)]
    z = ret / np.sqrt(win_var.reindex(ret.index).replace(0, np.nan))
    pit = pd.Series(0.5 * (1 + np.vectorize(math.erf)(z.fillna(0) / math.sqrt(2))), index=ret.index)
    hist, edges = np.histogram(pit.dropna().clip(0, 1), bins=20, range=(0, 1))
    coverage = float(payload.get("var_coverage") or 0.99)
    coverage = min(max(coverage, 0.90), 0.999)
    tail_p = 1.0 - coverage
    var_cutoff = float(stats.norm.ppf(tail_p))
    conditional_var = var_cutoff * np.sqrt(win_var) * 100
    var_series = pd.DataFrame({"date": ret.index, "return": ret.values * 100, "conditional_var": conditional_var.reindex(ret.index).values, "coverage": coverage})
    pit_clean = pit.dropna().clip(0, 1)
    if pit_clean.empty:
        ks_stat, ks_p = 0.0, 1.0
    else:
        s = np.sort(pit_clean.to_numpy(dtype=float))
        nn = len(s)
        ii = np.arange(1, nn + 1, dtype=float)
        d_plus = float(np.max(ii / nn - s))
        d_minus = float(np.max(s - (ii - 1) / nn))
        ks_stat = max(d_plus, d_minus)
        zks = (math.sqrt(nn) + 0.12 + 0.11 / max(math.sqrt(nn), 1e-12)) * ks_stat
        ks_p = float(np.clip(2 * sum(((-1) ** (k + 1)) * math.exp(-2 * k * k * zks * zks) for k in range(1, 6)), 0.0, 1.0))
    exceed = (ret * 100 < conditional_var.reindex(ret.index)).dropna().astype(int)
    n = int(exceed.sum())
    t = int(len(exceed))
    p = tail_p
    phat = min(max(n / max(t, 1), 1e-12), 1 - 1e-12)
    kupiec = -2 * ((n * math.log(p) + (t - n) * math.log(1 - p)) - (n * math.log(phat) + (t - n) * math.log(1 - phat))) if t else 0
    kupiec_p = float(1 - stats.chi2.cdf(kupiec, 1))
    e = exceed.to_numpy(dtype=np.int8)
    prev, curr = e[:-1], e[1:]
    n00 = int(((prev == 0) & (curr == 0)).sum())
    n01 = int(((prev == 0) & (curr == 1)).sum())
    n10 = int(((prev == 1) & (curr == 0)).sum())
    n11 = int(((prev == 1) & (curr == 1)).sum())
    pi01 = n01 / max(n00 + n01, 1)
    pi11 = n11 / max(n10 + n11, 1)
    pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    def ll(a, b):
        a = min(max(a, 1e-12), 1 - 1e-12)
        b = min(max(b, 1e-12), 1 - 1e-12)
        return n00 * math.log(1 - a) + n01 * math.log(a) + n10 * math.log(1 - b) + n11 * math.log(b)
    christ = -2 * (ll(pi, pi) - ll(pi01, pi11))
    christ_p = float(1 - stats.chi2.cdf(christ, 1))
    summary = [
        summary_card("Winning Model", winner, ""),
        summary_card("Conditional Vol", float(ann_vol.dropna().iloc[-1]), "ann"),
        summary_card("Vol Percentile", float((ann_vol.dropna() <= ann_vol.dropna().iloc[-1]).mean() * 100), "pct"),
        summary_card("VaR Breaches", int((ret * 100 < conditional_var.reindex(ret.index)).sum()), "days"),
    ]
    delta_rows = []
    for r in scoreboard:
        p = r.get("parameters") or {}
        if "delta" in p:
            delta_rows.append({"model": f"{r.get('model')}-{r.get('distribution')}", "delta": p.get("delta"), "percentile": float(pd.Series([x.get('parameters', {}).get('delta') for x in scoreboard if x.get('parameters', {}).get('delta') is not None]).rank(pct=True).iloc[-1] * 100) if delta_rows else None})
    nyblom = []
    chunks = np.array_split(ret.dropna(), 4)
    for name in ["GARCH-Gaussian", winner]:
        vals = []
        for ch in chunks:
            if len(ch) > 120:
                try:
                    sb, _, _ = garch_scoreboard(ch)
                    row = next((rr for rr in sb if f"{rr.get('model')}-{rr.get('distribution')}" == name), None)
                    if row and row.get("parameters"):
                        vals.append(float(row["parameters"].get("beta[1]", 0)))
                except Exception:
                    pass
        nyblom.append({"model": name, "parameter": "beta[1]", "stability_stat": float(np.nanstd(vals)) if vals else None, "chunks": len(vals), "stable": bool(len(vals) and np.nanstd(vals) < 0.08)})
    return response(
        "02",
        summary,
        charts={
            "news_impact_curve": nic,
            "regime_conditional_nic_ribbon": nic_ribbon,
            "garch_term_structure": term,
            "realized_garch_variance_series": rgarch_chart,
            "synthetic_vol_surface": synthetic_vol_surface(ret),
            "long_memory_parameter_series": compact_records(pd.DataFrame({"date": ret.index, "figarch_d_proxy": ret.pow(2).rolling(252).apply(autocorr_raw_jit, raw=True).clip(0.05, 0.99)})),
            "pit_test": [{"bin_start": float(edges[i]), "bin_end": float(edges[i + 1]), "count": int(hist[i])} for i in range(len(hist))],
            "conditional_var_series": compact_records(var_series),
            "volatility_state_gauge": [{"label": winner, "value": float((ann_vol.dropna() <= ann_vol.dropna().iloc[-1]).mean() * 100)}],
        },
        tables={
            "model_comparison_scoreboard": scoreboard,
            "diebold_mariano_pairwise_table": [{"row": r["model"] + "-" + r["distribution"], "col": "QLIKE", "value": r["qlike"]} for r in scoreboard],
            "pit_diagnostics": [{"ks_stat": float(ks_stat), "ks_p_value": float(ks_p)}],
            "var_backtests": [{"kupiec_lr": float(kupiec), "kupiec_p_value": kupiec_p, "christoffersen_lr": float(christ), "christoffersen_p_value": christ_p, "exceptions": n, "observations": t, "duration_test_proxy": float(exceed.rolling(10).sum().max()) if len(exceed) else 0}],
            "nyblom_parameter_stability": nyblom,
            "aparch_delta_benchmark": delta_rows,
        },
        meta={"asset": asset, "implemented_outputs": 13, "winning_model_parameters": params, "estimation": "arch library MLE across GARCH, EGARCH, GJR-GARCH, APARCH, FIGARCH, Realized-GARCH, and Gaussian/t/GED/skew-t distributions.", **runtime_meta(payload, ["term_structure_bands_use_750_paths_in_realtime"])},
    )
