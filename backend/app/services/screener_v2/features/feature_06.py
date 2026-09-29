"""S6 Alert Engine and Watchlist Monitor."""

from __future__ import annotations

from typing import Any

from ..core.analytics import access_meta, alert_precision_backtest, fundamental_change_rows, metric_panel, records, response
from ..core.data_loader import parse_symbols


FEATURE_ID = "06"
FEATURE_NAME = "Alert Engine and Watchlist Monitor"

INPUTS = [
    {"key": "watchlist", "type": "ticker_list", "default": "AAPL MSFT NVDA AMZN META GOOGL"},
    {"key": "alert_score_min", "type": "number", "default": 80},
    {"key": "alert_return_1d_abs", "type": "number", "default": 0.05},
]

OUTPUTS = ["alert_feed", "alert_performance_tracker", "alert_performance_tracker_historical", "screen_entry_exit_log"]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    payload = {**payload, "universe": payload.get("watchlist") or payload.get("universe") or "AAPL MSFT NVDA AMZN META GOOGL"}
    symbols = parse_symbols(payload, default_limit=25, max_symbols=250)
    panel = metric_panel(payload, symbols=symbols)
    score_min = float(payload.get("alert_score_min") or 80)
    move_abs = float(payload.get("alert_return_1d_abs") or 0.05)
    spike_threshold = float(payload.get("volume_spike_multiple") or 2.0)
    metric = payload.get("metric") or "core_quant_score"
    metric_threshold = payload.get("metric_threshold")
    formula_threshold = payload.get("formula_threshold")
    alerts = []
    fundamental_alerts = fundamental_change_rows(panel, float(payload.get("fundamental_change_threshold") or 0.20))
    for _, row in panel.iterrows():
        if row.get("core_quant_score", 0) >= score_min:
            alerts.append({"ticker": row["ticker"], "type": "SCREEN_ENTRY", "severity": "high", "value": row.get("core_quant_score"), "message": "Quant score crossed alert threshold."})
        if abs(row.get("return_1d", 0) or 0) >= move_abs:
            alerts.append({"ticker": row["ticker"], "type": "PRICE_MOVE", "severity": "medium", "value": row.get("return_1d"), "message": "One-day move exceeded configured absolute threshold."})
        if row.get("rsi_14", 50) >= 75 or row.get("rsi_14", 50) <= 25:
            alerts.append({"ticker": row["ticker"], "type": "RSI_EXTREME", "severity": "low", "value": row.get("rsi_14"), "message": "RSI moved to an extreme band."})
        if metric in row and metric_threshold is not None and (row.get(metric) or 0) >= float(metric_threshold):
            alerts.append({"ticker": row["ticker"], "type": "METRIC_THRESHOLD", "severity": "medium", "metric": metric, "value": row.get(metric), "message": f"{metric} crossed configured threshold."})
        if formula_threshold is not None and row.get("core_quant_score", 0) >= float(formula_threshold):
            alerts.append({"ticker": row["ticker"], "type": "FORMULA_THRESHOLD", "severity": "medium", "value": row.get("core_quant_score"), "message": "Formula/core score threshold triggered."})
        try:
            spike_ratio = float(row.get("vratio", row.get("volume_spike_ratio")))
        except (TypeError, ValueError):
            spike_ratio = None
        if spike_ratio is not None and spike_ratio >= spike_threshold:
            alerts.append({"ticker": row["ticker"], "type": "VOLUME_SPIKE", "severity": "high" if spike_ratio >= spike_threshold * 1.5 else "medium", "value": spike_ratio, "message": f"Volume {spike_ratio:.2f}x the 20-day average."})
        for window in [20, 50, 100, 200]:
            if row.get(f"crossed_above_sma_{window}_today"):
                alerts.append({"ticker": row["ticker"], "type": "PRICE_CROSS_SMA_UP", "severity": "low", "value": window, "message": f"Price crossed above SMA-{window} today."})
            if row.get(f"crossed_below_sma_{window}_today"):
                alerts.append({"ticker": row["ticker"], "type": "PRICE_CROSS_SMA_DOWN", "severity": "low", "value": window, "message": f"Price crossed below SMA-{window} today."})
        if row.get("macd_bullish") == 1 or row.get("sma50_above_sma200") == 1 or row.get("bollinger_pct_b", 0.5) >= 0.95:
            alerts.append({"ticker": row["ticker"], "type": "TECHNICAL_TRIGGER", "severity": "low", "value": row.get("macd_histogram"), "message": "Price/SMA/MACD/Bollinger condition triggered."})
        if row.get("consecutive_up_days", 0) >= 5 or row.get("consecutive_down_days", 0) >= 5:
            alerts.append({"ticker": row["ticker"], "type": "CONSECUTIVE_DAYS", "severity": "low", "value": max(row.get("consecutive_up_days", 0), row.get("consecutive_down_days", 0)), "message": "Consecutive day trigger fired."})
    alerts.extend(fundamental_alerts)
    entries = panel[panel["core_quant_score"] >= score_min][["ticker", "core_quant_score", "sector"]].copy() if not panel.empty else panel
    entries["event"] = "entered" if not entries.empty else []
    performance = [{"alert_type": t, "count": sum(1 for a in alerts if a["type"] == t), "precision_proxy": None, "forward_window": "requires persistent alert history"} for t in sorted({a["type"] for a in alerts})]
    historical_precision = alert_precision_backtest(panel, {"GOLDEN_CROSS": "golden_cross", "RSI_EXTREME": "rsi_extreme"})
    dashboard_cols = ["ticker", "sector", "core_quant_score", "return_1d", "rsi_14", "macd_histogram", "bollinger_pct_b", "volume_spike_ratio", "consecutive_up_days", "consecutive_down_days"]
    dashboard = records(panel[[c for c in dashboard_cols if c in panel.columns]].head(250)) if not panel.empty else []
    return response(
        FEATURE_ID,
        summary_cards=[
            {"label": "Watchlist symbols", "value": len(panel)},
            {"label": "Alerts", "value": len(alerts)},
        ],
        charts={"alert_feed": alerts, "watchlist_live_monitoring_dashboard": dashboard},
        tables={
            "alert_performance_tracker": performance,
            "alert_performance_tracker_historical": historical_precision,
            "screen_entry_exit_log": records(entries),
        },
        meta=access_meta(payload, ["Persistent alert scheduling, delivery, and realized alert precision require server state and a job runner."]),
    )
