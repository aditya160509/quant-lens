"""Feature 09: Portfolio volatility budget and dynamic risk targeting."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.volatility_v2.core.analytics import DEFAULT_ASSETS, almgren_chriss_costs, compact_records, dcc_garch_mle, kelly_vol_target, load_assets, parse_weights, response, returns_panel, summary_card, two_step_rebalance
from app.services.volatility_v2.features.feature_04 import run as run_regime


def run(payload=None):
    payload = payload or {}
    target = float(payload.get("vol_target") or payload.get("target_vol") or 0.10)
    assets, ohlcv = load_assets(payload, default=payload.get("assets") or DEFAULT_ASSETS[:8])
    ret = returns_panel(ohlcv).dropna(axis=1, thresh=120).fillna(0)
    assets_live = list(ret.columns)
    weights = parse_weights(payload, assets_live)
    cov, _, dcc_params = dcc_garch_mle(ret)
    cov = cov.reindex(index=assets_live, columns=assets_live)
    port_var = float(weights.to_numpy() @ cov.to_numpy() @ weights.to_numpy())
    current_vol = float(np.sqrt(max(port_var, 0)))
    try:
        regime = run_regime({**payload, "assets": [assets[0]], "lookback_days": payload.get("lookback_days", 900)})
        probs = {r["regime"]: r["probability"] for r in regime["charts"]["current_regime_dashboard"]}
        targets = payload.get("regime_targets") or {"low_vol": target * 0.85, "transition": target, "high_vol": target * 1.15, "crisis": target * 1.35}
        target = float(sum(probs.get(k, 0) * targets.get(k, target) for k in targets) or target)
    except Exception:
        probs = {}
    gross_cap = float(payload.get("gross_exposure_cap") or 3.0)
    scale = float(min(target / max(current_vol, 1e-12), gross_cap / max(weights.abs().sum(), 1e-12)))
    sigma = current_vol
    contrib = weights * (cov @ weights) / max(sigma, 1e-12)
    budget = pd.DataFrame({"asset": assets_live, "weight": weights.reindex(assets_live).values, "mrc": contrib.reindex(assets_live).values})
    budget["pct_total_vol"] = budget["mrc"] / max(float(budget["mrc"].sum()), 1e-12)
    budget["assigned_budget"] = 1 / max(len(budget), 1)
    budget["budget_deviation"] = budget["pct_total_vol"] - budget["assigned_budget"]
    rec = budget.copy()
    target_budget = np.full(len(rec), 1 / max(len(rec), 1))
    w_iter = weights.reindex(assets_live).to_numpy(dtype=float).copy() * scale
    c = cov.to_numpy()
    for _ in range(50):
        sig = float(np.sqrt(max(w_iter @ c @ w_iter, 1e-12)))
        mrc = w_iter * (c @ w_iter) / max(sig, 1e-12)
        pct = mrc / max(mrc.sum(), 1e-12)
        w_iter *= np.sqrt(np.maximum(target_budget, 1e-8) / np.maximum(np.abs(pct), 1e-8))
        gross = np.abs(w_iter).sum()
        if gross > gross_cap:
            w_iter *= gross_cap / gross
    rec["recommended_weight"] = w_iter
    rec["one_way_turnover"] = (rec["recommended_weight"] - rec["weight"]).abs()
    step1, step2 = two_step_rebalance(weights.reindex(assets_live).to_numpy(dtype=float), c, target, gross_cap=gross_cap)
    rec["uniform_scaled_weight"] = step1
    rec["two_step_qp_weight"] = step2
    rec["two_step_delta"] = step2 - rec["weight"].to_numpy(dtype=float)
    ac_costs = almgren_chriss_costs(assets_live, weights.reindex(assets_live).to_numpy(dtype=float), step2, ohlcv, cov, aum=float(payload.get("aum") or 1e8), gamma=float(payload.get("market_impact_gamma") or 0.1), explicit_bps=float(payload.get("explicit_bps") or 5.0))
    expected_return = float((ret.tail(252).mean() @ weights.reindex(ret.columns).fillna(0)) * 252)
    kelly = kelly_vol_target(expected_return, current_vol, target)
    portfolio_returns = (ret @ weights).fillna(0.0)
    # Strictly ex-ante EWMA variance forecast: information through t-1 sets t exposure.
    forecast_var = portfolio_returns.pow(2).ewm(halflife=int(payload.get("forecast_halflife") or 21), adjust=False).mean().shift(1)
    forecast_vol = np.sqrt(forecast_var.clip(lower=0.0) * 252)
    hist = pd.DataFrame({"date": forecast_vol.index, "portfolio_vol": forecast_vol, "target_vol": target, "scaling_factor": target / forecast_vol.replace(0, np.nan)})
    scaled_gross = (ret @ weights * hist["scaling_factor"].clip(upper=3).shift(1).reindex(ret.index).fillna(1)).fillna(0)
    turnover_proxy = hist["scaling_factor"].diff().abs().reindex(ret.index).fillna(0)
    cost_drag = turnover_proxy * (float(payload.get("explicit_bps") or 5.0) / 10000.0)
    scaled = (scaled_gross - cost_drag).fillna(0)
    base = (ret @ weights).fillna(0)
    backtest = pd.DataFrame({"date": ret.index, "baseline": (1 + base).cumprod(), "vol_targeted_gross": (1 + scaled_gross).cumprod(), "vol_targeted_net": (1 + scaled).cumprod(), "cumulative_cost": cost_drag.cumsum()})
    def stats(x):
        return {"annualized_return": float(x.mean() * 252), "annualized_vol": float(x.std() * np.sqrt(252)), "sharpe": float(x.mean() / max(x.std(), 1e-12) * np.sqrt(252)), "max_drawdown": float(((1+x).cumprod() / (1+x).cumprod().cummax() - 1).min()), "calmar": float((x.mean() * 252) / max(abs(((1+x).cumprod() / (1+x).cumprod().cummax() - 1).min()), 1e-12))}
    perf = [{"portfolio": "baseline", **stats(base)}, {"portfolio": "vol_targeted_gross", **stats(scaled_gross)}, {"portfolio": "vol_targeted_net_of_costs", **stats(scaled)}, {"portfolio": "cost_drag_bps_annualized", "annualized_return": float((scaled_gross.mean() - scaled.mean()) * 252 * 10000), "total_cumulative_cost": float(cost_drag.sum())}]
    breach = hist[(hist["portfolio_vol"] > target * 1.15) | (hist["portfolio_vol"] < target * 0.85)].tail(50)
    return response(
        "09",
        [summary_card("Current Vol", current_vol, "ann"), summary_card("Target Vol", target, "ann"), summary_card("Scaling Factor", scale, "x"), summary_card("Kelly Vol Target", kelly.get("kelly_optimal_vol_target"), "ann"), summary_card("Top Budget Breach", budget.sort_values("budget_deviation", ascending=False)["asset"].iloc[0], "")],
        charts={"portfolio_vol_dashboard": [{"metric": "realized_21d", "value": current_vol}, {"metric": "target", "value": target}, {"metric": "kelly_target", "value": kelly.get("kelly_optimal_vol_target")}, {"metric": "scale", "value": scale}], "kelly_vs_fixed_target": [{"date": row["date"], "fixed_target": target, "kelly_target": kelly.get("kelly_optimal_vol_target")} for row in compact_records(hist[["date"]])], "vol_to_target_gap_gauge": [{"label": "gap", "value": current_vol - target}], "vol_budget_attribution_waterfall": compact_records(budget.sort_values("budget_deviation", ascending=False), limit=200), "scaling_factor_history": compact_records(hist), "regime_conditional_target_evolution": compact_records(hist[["date", "target_vol", "portfolio_vol"]]), "historical_vol_targeting_backtest": compact_records(backtest)},
        tables={"portfolio_vol_budget_table": compact_records(budget.sort_values("budget_deviation", ascending=False), limit=200), "rebalancing_recommendation": compact_records(rec, limit=200), "two_step_rebalancing_detail": [{"step": "uniform_scale", "portfolio_vol": float(np.sqrt(max(step1 @ c @ step1, 0))), "gross": float(np.abs(step1).sum())}, {"step": "qp_budget_align", "portfolio_vol": float(np.sqrt(max(step2 @ c @ step2, 0))), "gross": float(np.abs(step2).sum()), "turnover_vs_current": float(np.abs(step2 - weights.reindex(assets_live).to_numpy(dtype=float)).sum())}], "almgren_chriss_transaction_costs": ac_costs, "kelly_vol_target": [kelly], "vol_budget_breach_log": compact_records(breach), "historical_backtest_performance": perf, "regime_probability_input": [{"regime": k, "probability": v} for k, v in probs.items()]},
        alerts=[{"level": "warning", "message": "Portfolio is above volatility target; reduce gross exposure."}] if current_vol > target * 1.15 else [],
        meta={"assets": assets_live, "implemented_outputs": 11, "covariance_engine": "two_stage_dcc_garch_mle", "rebalancing_engine": "two-step KKT rebalance plus Almgren-Chriss transaction-cost netting and Kelly target", **dcc_params},
    )
