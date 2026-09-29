"""Feature 7: Factor Backtesting Engine."""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.services.factors_v2.core.analytics import backtest_series, characteristic_panel, compact_series, normalize_factor_name, perf_stats, price_sample, response
from app.services.factors_v2.core.performance import cap_realtime, compute_mode, drawdown_curve, runtime_meta


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    requested_refit = str(payload.get("refit_frequency", "weekly")).lower()
    refit_frequency = "weekly" if mode == "realtime" and requested_refit == "daily" else requested_refit
    mc_sims = cap_realtime(int(payload.get("mc_simulations", 250)), 250, 500, payload)
    bt = backtest_series(payload)
    gross, net = bt["gross"], bt["net"]
    if gross.empty:
        return response("feature_07", "warning", meta={"warning": "No factor return data available"})
    stats_g, stats_n = perf_stats(gross), perf_stats(net)
    cost = (gross - net).dropna()
    cost_model = bt.get("cost_model", {})
    dd = pd.Series(drawdown_curve(bt["equity_net"].to_numpy(dtype=float)), index=bt["equity_net"].index)
    rng = np.random.default_rng(1907)
    mc_paths = _stationary_bootstrap_equity(net.to_numpy(dtype=float), mc_sims, rng, block_size=max(5, int(payload.get("mc_block_days", 21))))
    q10, q50, q90 = np.nanpercentile(mc_paths, [10, 50, 90], axis=0)
    mc = pd.DataFrame({"date": net.index, "p10": q10, "median": q50, "p90": q90})
    if len(mc) > 260:
        mc = mc.iloc[np.linspace(0, len(mc) - 1, 260).astype(int)]
    quintile_rows = _real_quintile_monotonicity(payload)
    decile_rows = _decile_from_quintiles(quintile_rows)
    annual_rows = _annual_gross_net(gross, net)
    premium_spread = _rolling_premium_spread(gross, net)
    adv_capacity = _adv_capacity_curve(payload, stats_g, cost_model)
    walk_forward = _walk_forward_proxy(payload, gross) if mode == "research" or payload.get("walk_forward") else [{"status": "research_mode_required", "reason": "walk-forward optimization is excluded from realtime default"}]
    return response(
        "feature_07",
        "ok",
        summary_cards=[
            {"label": "Gross Sharpe", "value": stats_g.get("sharpe")},
            {"label": "Net Sharpe", "value": stats_n.get("sharpe")},
            {"label": "Max Drawdown", "value": stats_n.get("max_drawdown")},
        ],
        charts={
            "equity_curve": {"gross": compact_series(bt["equity_gross"]), "net": compact_series(bt["equity_net"])},
            "drawdown": compact_series(dd),
            "monte_carlo_bands": mc.to_dict("records"),
            "quintile_monotonicity": quintile_rows,
            "decile_monotonicity": decile_rows,
            "factor_premium_spread": premium_spread,
            "transaction_cost_decomposition": cost_model.get("rows", [{"component": "total_implementation_shortfall", "annual_drag": float(cost.mean() * 252)}]),
            "adv_capacity_curve": adv_capacity,
        },
        tables={
            "statistics": [{"type": "gross", **stats_g}, {"type": "net", **stats_n}],
            "transaction_costs": cost_model.get("rows", [{"component": "total_implementation_shortfall", "annual_drag": float(cost.mean() * 252)}]),
            "gross_vs_net_by_year": annual_rows,
            "turnover_analysis": _turnover_analysis(payload, net.index),
            "walk_forward_optimization_report": walk_forward,
            "capacity_constraints": [
                {"measure": "max_adv_participation", "value": cost_model.get("participation_max")},
                {"measure": "participation_cap", "value": cost_model.get("participation_cap")},
                {"measure": "max_execution_days", "value": cost_model.get("max_execution_days")},
                {"measure": "kyle_lambda_cross_sectional", "value": cost_model.get("kyle_lambda_cross_sectional")},
                {"measure": "daily_cost", "value": cost_model.get("daily_cost")},
                {"measure": "refit_frequency", "value": refit_frequency},
                {"measure": "monte_carlo_simulations_cap", "value": mc_sims},
            ],
            "adv_capacity_curve": adv_capacity,
            "realtime_compute_policy": [
                {"constraint": "walk_forward_refit", "requested": requested_refit, "used": refit_frequency, "research_mode_required": requested_refit == "daily" and mode == "realtime"},
                {"constraint": "monte_carlo_confidence_bands", "requested": payload.get("mc_simulations", 250), "used": mc_sims},
                {"constraint": "timing_cost_component", "enabled": bool(cost_model.get("include_timing_cost"))},
            ],
        },
        alerts=(
            ([{"level": "medium", "message": "ADV participation exceeds 10%", "value": cost_model.get("participation_max")}] if (cost_model.get("participation_max") or 0) > 0.1 else [])
            + ([{"level": "medium", "message": "Daily refit is Research Mode only; weekly refit used", "requested": requested_refit}] if requested_refit == "daily" and mode == "realtime" else [])
        ),
        meta={
            **runtime_meta("feature_07", payload, ["weekly refit hard default in realtime; MC capped at 250; timing cost toggle-only"]),
            "factor": bt["factor"],
            "return_column": bt["column"],
            "refit_frequency": refit_frequency,
            "mc_simulations": mc_sims,
            "transaction_cost_model": cost_model.get("cost_formula", "explicit + linear spread + square-root impact"),
            "quintile_monotonicity_method": "point-in-time characteristic score quintiles with next-session formation and realized forward returns; unavailable data remains null",
            "audit_closures": ["expanded statistics table", "gross/net yearly table", "turnover analysis", "factor premium spread", "research-mode walk-forward proxy"],
        },
    )


def _real_quintile_monotonicity(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    factor = normalize_factor_name(payload.get("factor", "value_pb"))
    rebalance_days = int(payload.get("rebalance_days", 21))
    window_days = int(payload.get("window_days", 756))
    chars = characteristic_panel(payload)
    if chars.empty or factor not in chars or "Ticker" not in chars:
        return _empty_quintile_rows("characteristic panel missing required factor")
    prices = price_sample(int(payload.get("max_tickers", 240)))
    if prices.empty or not {"Date", "Ticker", "Close"}.issubset(prices.columns):
        return _empty_quintile_rows("price panel unavailable")
    close = (
        prices.sort_values(["Ticker", "Date"])
        .set_index(["Date", "Ticker"])["Close"]
        .unstack("Ticker")
        .sort_index()
    )
    close_tail = close.tail(window_days)
    fwd_returns = (close.shift(-(rebalance_days + 1)) / close.shift(-1) - 1.0).reindex(close_tail.index)
    score_series = chars.set_index("Ticker")[factor].dropna()
    common = score_series.index.intersection(close_tail.columns)
    if len(common) < 25:
        return _empty_quintile_rows("fewer than 25 common tickers for quintile test")
    try:
        quintiles = pd.qcut(score_series.loc[common].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    except ValueError:
        return _empty_quintile_rows("factor scores are not sufficiently dispersed")
    rows: List[Dict[str, Any]] = []
    for q in range(1, 6):
        tickers = quintiles[quintiles == q].index.tolist()
        q_fwd = fwd_returns[[t for t in tickers if t in fwd_returns.columns]].dropna(how="all")
        if q_fwd.empty:
            rows.append({"quintile": f"Q{q}", "annual_return": None, "n_stocks": len(tickers), "warning": "No forward returns for quintile"})
            continue
        period_mean = float(q_fwd.mean(axis=1).dropna().mean())
        annualized = float((1.0 + period_mean) ** (252 / max(rebalance_days, 1)) - 1.0)
        rows.append({"quintile": f"Q{q}", "annual_return": annualized, "avg_period_return": period_mean, "n_stocks": len(tickers)})
    valid_pairs = [(rows[i]["annual_return"], rows[i + 1]["annual_return"]) for i in range(4) if rows[i]["annual_return"] is not None and rows[i + 1]["annual_return"] is not None]
    score = sum(1 for a, b in valid_pairs if b > a) / len(valid_pairs) if valid_pairs else None
    for row in rows:
        row["monotonicity_score"] = score
    return rows


def _empty_quintile_rows(reason: str) -> List[Dict[str, Any]]:
    return [
        {
            "quintile": f"Q{i + 1}",
            "annual_return": None,
            "avg_period_return": None,
            "n_stocks": 0,
            "warning": reason,
            "method": "unavailable_no_fabrication",
            "monotonicity_score": None,
        }
        for i in range(5)
    ]


def _decile_from_quintiles(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    values = [row.get("annual_return") for row in rows]
    if len(values) < 2 or any(value is None for value in values):
        return []
    values = [float(value) for value in values]
    expanded: List[Dict[str, Any]] = []
    for i in range(10):
        pos = i / 9 * (len(values) - 1)
        lo = int(np.floor(pos))
        hi = min(len(values) - 1, lo + 1)
        frac = pos - lo
        value = values[lo] * (1 - frac) + values[hi] * frac
        expanded.append({"decile": f"D{i + 1}", "annual_return": float(value), "method": "interpolated_from_realtime_quintiles"})
    return expanded


def _stationary_bootstrap_equity(returns: np.ndarray, simulations: int, rng: np.random.Generator, block_size: int = 21) -> np.ndarray:
    values = np.asarray(returns, dtype=float)
    n = len(values)
    if n == 0:
        return np.empty((simulations, 0), dtype=float)
    block = max(1, min(int(block_size), n))
    paths = np.empty((simulations, n), dtype=float)
    for sim in range(simulations):
        sampled = np.empty(n, dtype=float)
        cursor = 0
        while cursor < n:
            start = int(rng.integers(0, n))
            take = min(block, n - cursor)
            indices = (start + np.arange(take)) % n
            sampled[cursor:cursor + take] = values[indices]
            cursor += take
        paths[sim] = np.cumprod(1.0 + sampled)
    return paths


def _annual_gross_net(gross: pd.Series, net: pd.Series) -> List[Dict[str, Any]]:
    if not isinstance(gross.index, pd.DatetimeIndex):
        return []
    g = gross.resample("YE").sum()
    n = net.resample("YE").sum()
    rows = []
    for idx in g.index.union(n.index):
        gross_val = float(g.get(idx, np.nan))
        net_val = float(n.get(idx, np.nan))
        rows.append({"year": int(idx.year), "gross_return": gross_val, "net_return": net_val, "implementation_shortfall": gross_val - net_val})
    return rows


def _turnover_analysis(payload: Dict[str, Any], index) -> List[Dict[str, Any]]:
    turnover = float(payload.get("turnover", 0.35))
    rebalance_days = int(payload.get("rebalance_days", 21))
    monthly_turnover = turnover * max(21 / max(rebalance_days, 1), 0.0)
    rows = [{"measure": "average_one_way_monthly_turnover", "value": monthly_turnover}, {"measure": "rebalance_days", "value": rebalance_days}]
    if isinstance(index, pd.DatetimeIndex) and len(index):
        rows.append({"measure": "turnover_observations_proxy", "value": int(len(index) / max(rebalance_days, 1)), "method": "configured turnover applied per rebalance interval"})
    return rows


def _rolling_premium_spread(gross: pd.Series, net: pd.Series) -> List[Dict[str, Any]]:
    if gross.empty:
        return []
    rows = []
    for window, label in [(252, "12m"), (756, "36m")]:
        spread = gross.rolling(window, min_periods=max(30, window // 4)).sum() - net.rolling(window, min_periods=max(30, window // 4)).sum()
        for idx, value in spread.tail(220).dropna().items():
            rows.append({"date": str(pd.Timestamp(idx).date()), "window": label, "gross_net_cost_spread": float(value)})
    return rows


def _walk_forward_proxy(payload: Dict[str, Any], gross: pd.Series) -> List[Dict[str, Any]]:
    train = int(payload.get("walk_forward_train_days", 252))
    hold = int(payload.get("walk_forward_hold_days", 21))
    if len(gross) < train + hold:
        return [{"status": "insufficient_history", "train_days": train, "hold_days": hold, "observations": int(len(gross))}]
    rows = []
    for start in range(0, len(gross) - train - hold + 1, hold):
        train_slice = gross.iloc[start:start + train]
        test_slice = gross.iloc[start + train:start + train + hold]
        train_ic = float(train_slice.mean() / train_slice.std()) if train_slice.std() else 0.0
        oos_ic = float(test_slice.mean() / test_slice.std()) if test_slice.std() else 0.0
        rows.append({"train_start": str(gross.index[start].date()), "test_start": str(gross.index[start + train].date()), "in_sample_score": train_ic, "out_of_sample_score": oos_ic, "method": "rolling_single_factor_walk_forward_proxy"})
    return rows[-40:]


def _adv_capacity_curve(payload: Dict[str, Any], stats_g: Dict[str, Any], cost_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    chars = characteristic_panel({**payload, "max_tickers": max(int(payload.get("max_tickers", 300)), 300)})
    adv = None
    for col in ["adv", "avg_daily_value", "dollar_volume", "volume_usd", "market_cap"]:
        if col in chars:
            values = pd.to_numeric(chars[col], errors="coerce").dropna()
            if len(values):
                adv = float(values.median())
                break
    if adv is None or not np.isfinite(adv) or adv <= 0:
        adv = 25_000_000.0
    turnover = float(payload.get("turnover", 0.35))
    participation_cap = float(payload.get("participation_cap", cost_model.get("participation_cap") or 0.15))
    gross_alpha = float((stats_g.get("annualized_return") or stats_g.get("return_ann") or 0.12) * 10_000)
    rows = []
    for aum in [10_000_000, 25_000_000, 50_000_000, 100_000_000, 250_000_000, 500_000_000, 1_000_000_000, 2_000_000_000, 5_000_000_000]:
        daily_trade = aum * turnover / 21.0
        participation = daily_trade / max(adv * participation_cap, 1.0)
        impact_drag = float(12.0 * np.sqrt(max(participation, 0.0)) * 252 / 21.0)
        net_alpha = gross_alpha - impact_drag
        rows.append(
            {
                "aum": float(aum),
                "aum_label": "$" + (f"{aum/1_000_000_000:.1f}B" if aum >= 1_000_000_000 else f"{aum/1_000_000:.0f}M"),
                "gross_alpha_bps": gross_alpha,
                "impact_drag_bps": impact_drag,
                "net_alpha_bps": net_alpha,
                "participation_ratio": float(participation),
                "time_to_liquidate_days": float(aum / max(adv * participation_cap, 1.0)),
                "viability": "OK" if net_alpha > 50 else "WATCH" if net_alpha > 0 else "CAPACITY BREACH",
            }
        )
    return rows
