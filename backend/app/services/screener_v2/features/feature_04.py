"""S4 Academic Strategy Screener Library."""

from __future__ import annotations

from typing import Any

from ..core.analytics import academic_strategy_scores, access_meta, altman_history, full_strategy_performance_metadata, full_strategy_performance_table, matrix_records, metric_panel, records, response, score_backtest, strategy_leaderboard
from ..core.data_loader import parse_symbols


FEATURE_ID = "04"
FEATURE_NAME = "Academic Strategy Screener Library"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "strategy", "type": "select", "default": "magic_formula"},
    {"key": "lookback_days", "type": "number", "default": 756},
    {"key": "top_n", "type": "number", "default": 50},
]

OUTPUTS = [
    "strategy_leaderboard",
    "per_strategy_stock_list",
    "piotroski_breakdown",
    "altman_z_score_status",
    "strategy_correlation_matrix",
    "historical_strategy_performance",
    "historical_strategy_performance_all",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    strategies = academic_strategy_scores(panel)
    strategy = payload.get("strategy") or "magic_formula"
    if strategy not in strategies.columns:
        strategy = "best_strategy_score"
    ranked = strategies.sort_values(strategy, ascending=False)
    backtest = score_backtest(list(ranked["ticker"]), ranked.set_index("ticker")[strategy], int(payload.get("lookback_days") or 756), int(payload.get("top_n") or 50), long_short=bool(payload.get("long_short")))
    numeric = strategies.select_dtypes("number").drop(columns=["altman_z_score"], errors="ignore")
    focus = str(payload.get("focus_ticker") or ranked.iloc[0]["ticker"]) if not ranked.empty else ""
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Strategies", "value": len(strategy_leaderboard(strategies))},
            {"label": "Selected strategy", "value": strategy},
            {"label": "Top score", "value": float(ranked[strategy].max()) if not ranked.empty else None},
        ],
        charts={
            "strategy_correlation_matrix": matrix_records(numeric.corr()),
            "historical_strategy_performance": backtest.get("equity_curve", []),
        },
        tables={
            "strategy_leaderboard": records(strategy_leaderboard(strategies)),
            "per_strategy_stock_list": records(ranked.head(int(payload.get("top_n") or 50))),
            "piotroski_breakdown": records(strategies[[c for c in strategies.columns if c.startswith("piotroski_") or c in {"ticker", "sector"}]].sort_values("piotroski_f_score", ascending=False).head(100)),
            "altman_z_score_status": records(strategies[["ticker", "sector", "altman_z_score", "altman_z_double_prime", "altman_status", "altman_piotroski_overlay"]].sort_values("altman_z_score", ascending=False).head(100)),
            "altman_z_score_8q_trend": altman_history(focus, 8) if focus else [],
            "historical_strategy_statistics": [backtest.get("stats", {})],
            "historical_strategy_performance_all": full_strategy_performance_table(
                strategies,
                int(payload.get("lookback_days") or 756),
                int(payload.get("top_n") or 50),
                int(payload.get("strategy_perf_limit") or 24),
            ),
            "historical_strategy_performance_metadata": [full_strategy_performance_metadata(strategies, int(payload.get("strategy_perf_limit") or 24))],
        },
        meta=access_meta(payload, ["Academic screens use the latest local fundamentals snapshot; true PIT strategy library requires appended PIT fundamentals. Full strategy performance uses deterministic local price-history backtests for available numeric strategy scores."]),
    )
