"""S3 Composite Quant Score Engine."""

from __future__ import annotations

from typing import Any

from ..core.analytics import access_meta, component_ic_leaderboard, component_scores, effective_num_factors, matrix_records, metric_panel, records, response, score_backtest, score_decomposition_for_ticker
from ..core.data_loader import parse_symbols


FEATURE_ID = "03"
FEATURE_NAME = "Composite Quant Score Engine"

INPUTS = [
    {"key": "universe", "type": "ticker_list", "default": "master"},
    {"key": "components", "type": "json", "default": None},
    {"key": "lookback_days", "type": "number", "default": 756},
    {"key": "top_n", "type": "number", "default": 50},
]

OUTPUTS = [
    "composite_score_universe_ranking",
    "score_transparency_decomposition",
    "per_stock_score_decomposition",
    "component_ic_ir_leaderboard",
    "factor_correlation_heatmap",
    "composite_vs_factor_backtest",
    "regime_conditional_composite_breakdown",
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    symbols = parse_symbols(payload, default_limit=int(payload.get("max_symbols") or 500), max_symbols=5000)
    panel = metric_panel(payload, symbols=symbols)
    scored = component_scores(
        panel,
        payload.get("components")
        or {
            "preset": payload.get("preset"),
            "sector_neutral": payload.get("sector_neutral"),
            "beta_neutral": payload.get("beta_neutral"),
            "winsorize": payload.get("winsorize"),
            "signed_rank": payload.get("signed_rank"),
            "weighting_mode": payload.get("weighting_mode"),
            "ic_target_field": payload.get("ic_target_field"),
            "ridge_lambda": payload.get("ridge_lambda"),
            "output_scale": payload.get("output_scale"),
        },
    )
    leaderboard = component_ic_leaderboard(panel)
    component_cols = [c for c in ["Value", "Quality", "Momentum", "Low Vol", "Liquidity", "composite_score"] if c in scored.columns]
    corr = scored[component_cols].corr() if component_cols else scored.select_dtypes("number").corr()
    backtest = score_backtest(
        list(scored["ticker"]),
        scored.set_index("ticker")["composite_score"],
        int(payload.get("lookback_days") or 756),
        int(payload.get("top_n") or 50),
        long_short=bool(payload.get("long_short")),
        score_weighted=bool(payload.get("score_weighted")),
    )
    regime_breakdown = panel.groupby("sector").agg(avg_composite=("core_quant_score", "mean"), count=("ticker", "count")).reset_index().rename(columns={"sector": "regime_proxy"})
    redundancy = []
    for row in matrix_records(corr):
        if row["row"] != row["col"] and abs(row["value"]) > 0.6:
            redundancy.append({"pair": f"{row['row']} / {row['col']}", "correlation": row["value"], "alert": "redundant_factor_pair"})
    focus = payload.get("focus_ticker") or (scored.iloc[0]["ticker"] if not scored.empty else None)
    weights = {item["component"]: item["weight"] for item in scored.attrs.get("decomposition", []) if item.get("component") in corr.columns}
    n_eff = effective_num_factors(weights, corr)
    meta_issues = ["Regime breakdown uses current sector grouping unless a future server-side regime/portfolio state is provided."]
    if scored.attrs.get("weighting_diagnostics"):
        meta_issues.append(scored.attrs["weighting_diagnostics"])
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Composite universe", "value": len(scored)},
            {"label": "Top composite", "value": float(scored["composite_score"].max()) if not scored.empty else None},
            {"label": "Backtest Sharpe", "value": backtest.get("stats", {}).get("sharpe")},
            {"label": "Effective factors", "value": n_eff},
        ],
        charts={
            "factor_correlation_heatmap": matrix_records(corr),
            "composite_vs_factor_backtest": backtest.get("equity_curve", []),
            "regime_conditional_composite_breakdown": records(regime_breakdown),
        },
        tables={
            "composite_score_universe_ranking": records(scored.head(int(payload.get("top_n") or 50))),
            "score_transparency_decomposition": scored.attrs.get("decomposition", []),
            "per_stock_score_decomposition": score_decomposition_for_ticker(scored, focus),
            "component_ic_ir_leaderboard": records(leaderboard),
            "factor_correlation_redundancy_alerts": redundancy,
            "effective_number_of_factors": [{"n_eff": n_eff, "component_count": len(weights)}],
        },
        meta=access_meta(payload, meta_issues),
    )
