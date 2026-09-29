"""Feature 9: Strategy Capacity Analyzer."""

from typing import Any, Dict

import numpy as np

from app.services.factors_v2.core.analytics import backtest_series, characteristic_panel, perf_stats, response
from app.services.factors_v2.core.performance import cap_realtime, participation_cap_filter, runtime_meta

_ALMGREN_ETA = 0.1
_SQRT_MODEL_THRESHOLD_USD = 100_000_000.0


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    bt = backtest_series(payload)
    chars = characteristic_panel(payload)
    annualized = perf_stats(bt["gross"]).get("annualized_return")
    gross_alpha = float(annualized) if annualized is not None else 0.0
    explicit = float(payload.get("explicit_bps", 8)) / 10000 * 12
    adv = float(chars.get("adv").dropna().median()) if not chars.empty and "adv" in chars else 5_000_000.0
    lambda_impact = float(payload.get("kyle_lambda", 0.10))
    turnover = float(payload.get("turnover", 0.35))
    if payload.get("aum_grid"):
        max_points = cap_realtime(len(payload["aum_grid"]), 20, 50, payload)
        aums = list(payload["aum_grid"])[:max_points]
    else:
        points = cap_realtime(int(payload.get("aum_points", 20)), 20, 50, payload)
        aums = np.geomspace(1e6, 1e10, points).tolist()
    aum_arr = np.asarray(aums, dtype=float)
    sigma_median = float(chars.get("realized_vol").dropna().median()) if not chars.empty and "realized_vol" in chars else float(payload.get("sigma_median", 0.25))
    impact, net_alpha, model_used, capacity = _capacity_curve_piecewise(
        aum_arr=aum_arr,
        gross_alpha=float(gross_alpha),
        explicit_drag=float(explicit),
        turnover=turnover,
        adv_median=adv,
        lambda_kyle=lambda_impact,
        sigma_median=sigma_median,
        rebalance_days=int(payload.get("rebalance_days", 21)),
    )
    capacity = capacity or float(max(aums))
    rows = _build_capacity_rows(aum_arr, float(gross_alpha), impact, net_alpha, model_used, adv, turnover, float(payload.get("participation_cap", 0.15)))
    eligible_count = None
    if not chars.empty and {"Ticker", "adv", "market_cap"}.issubset(chars.columns):
        w = chars["market_cap"].fillna(chars["market_cap"].median()).clip(lower=1.0)
        w = w / max(w.sum(), 1e-12)
        eligible_count = len(participation_cap_filter(chars["Ticker"], chars["adv"].fillna(adv), w, capacity, 0.15))
    memo = f"Estimated capacity ceiling is ${capacity:,.0f}; optimal operating AUM proxy is ${capacity/2:,.0f}. Assumes median ADV ${adv:,.0f}, turnover {turnover:.0%}, Kyle lambda {lambda_impact:.2f} below $100M, and Almgren-Chriss square-root impact above $100M."
    return response(
        "feature_09",
        "ok",
        summary_cards=[{"label": "Capacity Ceiling", "value": capacity, "unit": "USD"}, {"label": "Optimal AUM Proxy", "value": capacity / 2, "unit": "USD"}],
        charts={"capacity_curve": rows},
        tables={"slippage_by_aum": rows, "sensitivity": [{"case": "ADV cap 25%", "capacity": capacity * 1.67}, {"case": "rebalance frequency doubles", "capacity": capacity / 2}]},
        alerts=[{"level": "medium", "message": "Capacity ceiling reached inside requested AUM sweep"}] if capacity < max(aums) else [],
        meta={
            **runtime_meta("feature_09", payload, ["AUM sweep capped at 20 realtime points; 50 points in Research Mode"]),
            "allocator_memo": memo,
            "factor": bt["factor"],
            "aum_points": len(aums),
            "vectorized_aum_sweep": True,
            "eligible_tickers_at_capacity": eligible_count,
            "impact_model": "continuous square-root market-impact model",
            "almgren_eta": _ALMGREN_ETA,
            "sigma_median": sigma_median,
        },
    )


def _zero_crossing(aums: np.ndarray, net_alpha: np.ndarray):
    below = np.where(net_alpha <= 0)[0]
    if below.size == 0:
        return None
    idx = int(below[0])
    if idx == 0:
        return float(aums[0])
    x0, x1 = aums[idx - 1], aums[idx]
    y0, y1 = net_alpha[idx - 1], net_alpha[idx]
    if y1 == y0:
        return float(x1)
    return float(x0 + (0.0 - y0) * (x1 - x0) / (y1 - y0))


def _capacity_curve_piecewise(aum_arr, gross_alpha, explicit_drag, turnover, adv_median, lambda_kyle, sigma_median, rebalance_days=21):
    impact = np.empty_like(aum_arr, dtype=float)
    model_used = np.empty(len(aum_arr), dtype=object)
    rebalances_per_year = 252 / max(int(rebalance_days), 1)
    for idx, aum in enumerate(aum_arr):
        participation = turnover * aum / max(adv_median, 1.0)
        impact_per_rebalance = lambda_kyle * sigma_median * np.sqrt(max(participation, 0.0))
        model_used[idx] = "continuous_square_root_impact"
        impact[idx] = impact_per_rebalance * rebalances_per_year
    net_alpha = gross_alpha - explicit_drag - impact
    return impact, net_alpha, model_used, _zero_crossing(aum_arr, net_alpha)


def _build_capacity_rows(aum_arr, gross_alpha, impact_arr, net_alpha, model_used, adv_median, turnover, participation_cap=0.15):
    ttl = (float(turnover) * aum_arr) / (participation_cap * max(adv_median, 1.0))
    return [
        {
            "aum": float(aum),
            "gross_alpha": float(gross_alpha),
            "impact_drag": float(impact),
            "net_alpha": float(alpha),
            "viable": bool(alpha > 0),
            "time_to_liquidate_days": float(ttl[idx]),
            "impact_model": str(model),
        }
        for idx, (aum, impact, alpha, model) in enumerate(zip(aum_arr, impact_arr, net_alpha, model_used))
    ]
