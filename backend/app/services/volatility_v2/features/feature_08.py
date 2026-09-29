"""Feature 08: Volatility stress testing and scenario engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.volatility_v2.core.analytics import DEFAULT_ASSETS, adversarial_scenario, bootstrap_var_irf_bands, clayton_copula_tail_dependence, compact_records, compute_mode, corr_from_cov, dcc_garch_mle, fit_var, graphical_lasso_analogs, load_assets, macro_frame, parse_weights, response, returns_panel, runtime_meta, summary_card, var_ma_matrices, volatility_estimators


SCENARIOS = {
    "gfc": {"vol_mult": 2.2, "return_shock": -0.18},
    "covid": {"vol_mult": 2.8, "return_shock": -0.22},
    "rate_shock_2022": {"vol_mult": 1.6, "return_shock": -0.10},
    "liberation_day_2025": {"vol_mult": 1.9, "return_shock": -0.13},
    "parametric": {"vol_mult": 1.5, "return_shock": -0.08},
}


def run(payload=None):
    payload = payload or {}
    mode = compute_mode(payload)
    scenario = str(payload.get("scenario") or payload.get("historical_preset") or "liberation_day_2025").lower()
    spec = SCENARIOS.get(scenario, SCENARIOS["liberation_day_2025"])
    assets, ohlcv = load_assets(payload, default=payload.get("assets") or DEFAULT_ASSETS[:8])
    ret = returns_panel(ohlcv).dropna(axis=1, thresh=120).fillna(0)
    assets_live = list(ret.columns)
    weights = parse_weights(payload, assets_live)
    cov, _, dcc_params = dcc_garch_mle(ret)
    cov = cov.reindex(index=assets_live, columns=assets_live)
    corr = corr_from_cov(cov)
    vols = np.sqrt(np.diag(cov))
    stressed_vols = vols * spec["vol_mult"]
    stressed_cov = corr.to_numpy() * np.outer(stressed_vols, stressed_vols)
    if scenario in {"gfc", "covid", "rate_shock_2022", "liberation_day_2025"}:
        stress_dates = {
            "gfc": ("2008-09-01", "2008-12-31"),
            "covid": ("2020-02-15", "2020-03-31"),
            "rate_shock_2022": ("2022-09-01", "2022-11-15"),
            "liberation_day_2025": ("2025-04-01", "2025-05-31"),
        }[scenario]
        hist = ret.loc[stress_dates[0] : stress_dates[1]]
        shock = hist.mean().reindex(assets_live).fillna(spec["return_shock"])
        stressed_vols = hist.std().reindex(assets_live).fillna(pd.Series(stressed_vols, index=assets_live)).to_numpy() * np.sqrt(252)
        stressed_cov = corr.to_numpy() * np.outer(stressed_vols, stressed_vols)
    else:
        shock = pd.Series(spec["return_shock"], index=assets_live) * (vols / max(np.nanmean(vols), 1e-12))
    pnl = weights * shock
    waterfall = [{"component": a, "value": float(v)} for a, v in pnl.items()] + [{"component": "portfolio_total", "value": float(pnl.sum())}]
    vol_bar = [{"asset": a, "current_vol": float(vols[i]), "scenario_vol": float(stressed_vols[i]), "vol_change_bps": float((stressed_vols[i] - vols[i]) * 10000)} for i, a in enumerate(assets_live)]
    macro = macro_frame().set_index("date")
    signal = pd.DataFrame({"ret": ret.mean(axis=1), "vol": ret.std(axis=1) * np.sqrt(252)}).join(macro[["vix", "curve_10y_2y", "credit"]], how="left").ffill()
    recent = signal.tail(30).mean()
    analog_cols = ["ret", "vol", "vix", "curve_10y_2y", "credit"]
    analog_base = signal[analog_cols].replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0.0)
    cov_analog = analog_base.cov().to_numpy(dtype=float)
    cov_analog = np.nan_to_num(cov_analog, nan=0.0, posinf=0.0, neginf=0.0) + np.eye(len(analog_cols)) * 1e-8
    try:
        inv_cov = np.linalg.inv(cov_analog)
    except Exception:
        inv_cov = np.linalg.pinv(cov_analog)
    distances = []
    for i in range(30, len(signal) - 30, 21):
        row = signal.iloc[i : i + 30].mean()
        diff = (row[analog_cols].fillna(0) - recent[analog_cols].fillna(0)).to_numpy(dtype=float)
        d = float(np.sqrt(max(diff @ inv_cov @ diff, 0.0)))
        distances.append({"window_start": signal.index[i].strftime("%Y-%m-%d"), "distance": d, "avg_return": float(signal["ret"].iloc[i : i + 30].sum()), "avg_vol": float(signal["vol"].iloc[i : i + 30].mean())})
    analog = sorted(distances, key=lambda x: x["distance"])[:10]
    analog_glasso = graphical_lasso_analogs(signal, analog_cols, k=int(payload.get("analog_k") or 10))
    loss_threshold = float(payload.get("loss_threshold") or 0.15)
    beta_lev = np.abs(ret.rolling(63).corr(ret.mean(axis=1)).tail(1).iloc[0].reindex(assets_live).fillna(1.0).to_numpy())
    direction = weights.to_numpy() * beta_lev
    omega_vol = np.cov(ret.rolling(21).std().dropna().to_numpy(), rowvar=False)
    denom = float(direction @ omega_vol @ direction)
    delta = loss_threshold * (omega_vol @ direction) / max(denom, 1e-12)
    reverse = [{"asset": a, "required_vol_sigma": float(delta[i] / max(vols[i], 1e-12)), "direction": "vol_spike"} for i, a in enumerate(assets_live)]
    irf = []
    vol = volatility_estimators(ohlcv, window=21)
    try:
        asset0 = assets_live[0]
        vchg = vol[vol["asset"].eq(asset0)].sort_values("date").set_index("date")["yang_zhang"].diff()
        copula = clayton_copula_tail_dependence(ret[asset0], vchg, tail_pct=float(payload.get("clayton_tail_pct") or 0.20))
        for row in reverse:
            row["copula_theta"] = copula.get("theta")
            row["copula_lower_tail_dependence"] = copula.get("lower_tail_dependence")
    except Exception as exc:
        copula = {"error": str(exc)}
    adversarial = adversarial_scenario(weights, ret, signal, analog_cols, c=float(payload.get("adversarial_c") or 2.0))
    try:
        vol_wide = vol.pivot(index="date", columns="asset", values="yang_zhang")
    except ValueError:
        vol_wide = vol.pivot_table(index="date", columns="asset", values="yang_zhang", aggfunc="last")
    vol_panel = np.log(vol_wide.reindex(columns=assets_live).dropna())
    try:
        coefs, sig, _, _ = fit_var(vol_panel, max_lag=5)
        phis = var_ma_matrices(coefs, 22)
        for h in [1, 5, 10, 21]:
            for i, a in enumerate(assets_live):
                irf.append({"horizon": h, "asset": a, "response": float(phis[h][i].sum())})
    except Exception:
        for h in [1, 5, 10, 21]:
            decay = np.exp(-h / 10)
            for i, a in enumerate(assets_live):
                irf.append({"horizon": h, "asset": a, "response": float(stressed_vols[i] * decay - vols[i])})
    irf_bootstrap_reps = 500 if mode == "research" else 120
    irf_bands = bootstrap_var_irf_bands(vol_panel, reps=irf_bootstrap_reps) if not vol_panel.empty else []
    n_paths = 100000 if mode == "research" else 20000
    mc = np.random.default_rng(7).multivariate_normal(mean=shock.to_numpy(), cov=stressed_cov / 252, size=n_paths) @ weights.to_numpy()
    var95 = float(np.quantile(mc, 0.05))
    var99 = float(np.quantile(mc, 0.01))
    cvar95 = float(mc[mc <= var95].mean())
    cvar99 = float(mc[mc <= var99].mean())
    return response(
        "08",
        [summary_card("Scenario", scenario, ""), summary_card("Portfolio PnL", float(pnl.sum()), "return"), summary_card("Stress VaR 95", var95, "return"), summary_card("Stress CVaR 95", cvar95, "return")],
        charts={"vol_shock_bar_chart": vol_bar, "portfolio_pnl_attribution_waterfall": waterfall, "contagion_impulse_response": irf, "contagion_impulse_response_bands": irf_bands, "stress_distribution": [{"bucket": i, "loss": float(v)} for i, v in enumerate(np.quantile(mc, np.linspace(0.01, 0.99, 60)))]},
        tables={"historical_analog_comparison": analog, "historical_analog_glasso": analog_glasso, "reverse_stress_scenario": reverse, "reverse_stress_copula": [copula], "adversarial_scenario": [adversarial], "multi_scenario_comparison": [{"scenario": name, "portfolio_pnl": float(pd.Series(s["return_shock"], index=assets_live).mul(weights).sum()), "max_vol_multiplier": s["vol_mult"], "dcc_avg_corr": float(corr.to_numpy()[np.triu_indices(len(corr), 1)].mean()) if len(corr) > 1 else 1.0, "recovery_time_days": int(21 * s["vol_mult"])} for name, s in SCENARIOS.items()], "stress_var_cvar": [{"var_95": var95, "var_99": var99, "cvar_95": cvar95, "cvar_99": cvar99, "n_paths": n_paths}], "contagion_irf_bootstrap_bands": irf_bands},
        alerts=[{"level": "warning", "message": f"{scenario} stress implies {pnl.sum():.1%} portfolio move."}],
        meta={"assets": assets_live, "implemented_outputs": 12, "mc_paths": n_paths, "irf_bootstrap_reps": irf_bootstrap_reps, "covariance_engine": "two_stage_dcc_garch_mle", "tail_engine": "Clayton copula + graphical LASSO analogs + adversarial historical-plausible scenario", **runtime_meta(payload, ["monte_carlo_uses_20000_paths_and_irf_uses_120_bootstraps_in_realtime"]), **dcc_params},
    )
