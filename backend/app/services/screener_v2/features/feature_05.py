"""S5 Screener Backtester with Point-in-Time Validation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.analytics import access_meta, compute_turnover_series, metric_panel, monte_carlo_pbo, records, regime_performance_from_returns, response, score_backtest, score_backtest_by_weekday
from ..core.data_loader import close_matrix, parse_symbols


FEATURE_ID = "05"
FEATURE_NAME = "Screener Backtester with Point-in-Time Validation"


def _rebalance_days(payload: dict[str, Any]) -> int:
    frequency = str(payload.get("rebalance_frequency") or "").lower()
    return {"weekly": 5, "monthly": 21, "quarterly": 63}.get(frequency, max(1, int(payload.get("rebalance_days") or 21)))


def _holding_period_stats(prices: pd.DataFrame, holding_days: int) -> dict[str, Any]:
    if prices.empty or len(prices) <= holding_days:
        return {"holding_days": holding_days, "observations": 0, "mean_forward_return": None, "median_forward_return": None, "hit_rate": None}
    basket = prices.ffill().mean(axis=1)
    forward = basket.shift(-holding_days) / basket - 1.0
    forward = forward.iloc[::holding_days].dropna()
    return {
        "holding_days": holding_days,
        "observations": int(len(forward)),
        "mean_forward_return": float(forward.mean()) if len(forward) else None,
        "median_forward_return": float(forward.median()) if len(forward) else None,
        "forward_return_volatility": float(forward.std(ddof=1)) if len(forward) > 1 else None,
        "hit_rate": float((forward > 0).mean()) if len(forward) else None,
    }

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "score_field", "type": "select", "default": "core_quant_score"},
    {"key": "lookback_days", "type": "number", "default": 756},
    {"key": "top_n", "type": "number", "default": 50},
    {"key": "transaction_cost_bps", "type": "number", "default": 10},
]

OUTPUTS = [
    "equity_curve",
    "full_performance_statistics",
    "rolling_performance",
    "holding_period_sensitivity",
    "rebalancing_date_sensitivity",
    "rebalancing_date_sensitivity_by_weekday",
    "turnover_report",
    "sector_attribution",
    "regime_conditional_performance",
    "monte_carlo_sharpe_distribution",
    "stock_level_attribution",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    score_field = payload.get("score_field") or "core_quant_score"
    if score_field not in panel.columns:
        score_field = "core_quant_score"
    score = panel.set_index("ticker")[score_field]
    backtest = score_backtest(
        symbols,
        score,
        int(payload.get("lookback_days") or 756),
        int(payload.get("top_n") or 50),
        float(payload.get("transaction_cost_bps") or 10),
        long_short=bool(payload.get("long_short")),
        score_weighted=bool(payload.get("score_weighted")),
        rebalance_days=_rebalance_days(payload),
        sector_neutral=bool(payload.get("sector_neutral")),
        sector_map=panel.set_index("ticker")["sector"].to_dict() if "sector" in panel else None,
    )
    selected = backtest.get("selected", [])
    prices = close_matrix(selected, int(payload.get("lookback_days") or 756))
    returns = prices.pct_change(fill_method=None).dropna(how="all") if not prices.empty else pd.DataFrame()
    sector_map = panel.set_index("ticker")["sector"].to_dict() if "sector" in panel else {}
    sector_attr = []
    if not returns.empty:
        for sector, tickers in pd.Series(selected).groupby([sector_map.get(t, "Unknown") for t in selected]):
            cols = [t for t in tickers.tolist() if t in returns.columns]
            if cols:
                sector_attr.append({"sector": sector, "avg_return": float((1 + returns[cols].mean(axis=1)).prod() - 1), "count": len(cols)})
    holding_sensitivity = [_holding_period_stats(prices, hold) for hold in [21, 63, 126, 252]]
    mc = []
    if not returns.empty:
        series = returns.mean(axis=1).dropna()
        rng = pd.Series(range(250))
        for i in rng:
            sample = series.sample(n=len(series), replace=True, random_state=int(i))
            sharpe = sample.mean() / (sample.std() or 1) * (252 ** 0.5)
            mc.append({"simulation": int(i), "sharpe": float(sharpe)})
    pbo_proxy = sum(1 for row in mc if row["sharpe"] < backtest.get("stats", {}).get("sharpe", 0)) / len(mc) if mc else None
    stock_attr = []
    if not returns.empty:
        total = (1 + returns).prod() - 1
        entry = str(returns.index.min().date()) if len(returns.index) else None
        exit_date = str(returns.index.max().date()) if len(returns.index) else None
        stock_attr = [{"ticker": k, "total_return": float(v), "sector": sector_map.get(k, "Unknown"), "entry_date": entry, "exit_date": exit_date} for k, v in total.sort_values(ascending=False).items()]
    turnover_series = compute_turnover_series(
        symbols,
        score,
        int(payload.get("lookback_days") or 756),
        int(payload.get("top_n") or 50),
        _rebalance_days(payload),
    )
    pbo_rebalance = monte_carlo_pbo(
        symbols,
        score,
        int(payload.get("lookback_days") or 756),
        int(payload.get("top_n") or 50),
        int(payload.get("pbo_trials") or 60),
    ) if payload.get("run_full_pbo") else None
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Selected stocks", "value": len(selected)},
            {"label": "Sharpe", "value": backtest.get("stats", {}).get("sharpe")},
            {"label": "Max drawdown", "value": backtest.get("stats", {}).get("max_drawdown")},
        ],
        charts={
            "equity_curve": backtest.get("equity_curve", []),
            "rolling_performance": backtest.get("rolling", []),
            "monte_carlo_sharpe_distribution": mc,
        },
        tables={
            "full_performance_statistics": [backtest.get("stats", {})],
            "holding_period_sensitivity": holding_sensitivity,
            "rebalancing_date_sensitivity_by_weekday": score_backtest_by_weekday(
                symbols,
                score,
                int(payload.get("lookback_days") or 756),
                int(payload.get("top_n") or 50),
                float(payload.get("transaction_cost_bps") or 10),
            ),
            "rebalancing_date_sensitivity": [
                {"rebalance_offset_days": x, **score_backtest(symbols, score, int(payload.get("lookback_days") or 756), int(payload.get("top_n") or 50), float(payload.get("transaction_cost_bps") or 10), long_short=bool(payload.get("long_short")), score_weighted=bool(payload.get("score_weighted")), rebalance_days=_rebalance_days(payload), rebalance_offset_days=x, sector_neutral=bool(payload.get("sector_neutral")), sector_map=panel.set_index("ticker")["sector"].to_dict() if "sector" in panel else None).get("stats", {})}
                for x in [0, 5, 10, 15, 20]
            ],
            "turnover_report": turnover_series
            or [{"period": "insufficient_history", "turnover": None, "selected_count": len(selected), "rebalance_days": _rebalance_days(payload)}],
            "sector_attribution": sector_attr,
            "regime_conditional_performance": regime_performance_from_returns(returns.mean(axis=1)) if not returns.empty else [],
            "pbo_proxy": [{"probability_of_backtest_overfit_proxy": pbo_proxy}],
            "rebalancing_date_pbo": [pbo_rebalance] if pbo_rebalance else [],
            "rebalancing_date_pbo_trials": pbo_rebalance.get("trials", []) if pbo_rebalance else [],
            "stock_level_attribution": stock_attr[:250],
        },
        meta=access_meta(payload, ["True point-in-time fundamentals and delisting bias correction require the append-only PIT/delist fetcher datasets before production use. Turnover uses deterministic rank drift from local price history and current scores. Full rebalancing-date PBO is gated behind run_full_pbo because it re-runs the backtest across offsets."]),
    )
