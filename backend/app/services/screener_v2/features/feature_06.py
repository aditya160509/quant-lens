"""S6 Alert Engine and Watchlist Monitor."""

from __future__ import annotations

from typing import Any
from .inputs import shared_inputs, filter_inputs, enrich, merge_inputs

from ..core.common import access_meta, records, response
from ..core.alerts import alert_precision_backtest, current_alerts, realized_alert_precision
from ..core.panel import metric_panel
from ..core.data_loader import parse_symbols


FEATURE_ID = "06"
FEATURE_NAME = "Alert Engine and Watchlist Monitor"

INPUTS = merge_inputs(shared_inputs(), enrich([{'key': 'watchlist', 'type': 'ticker_list', 'default': 'AAPL MSFT NVDA AMZN META GOOGL'}, {'key': 'alert_score_min', 'type': 'number', 'default': 80}, {'key': 'alert_return_1d_abs', 'type': 'number', 'default': 0.05}, {'key': 'volume_spike_multiple', 'type': 'number', 'default': 2}, {'key': 'metric_threshold', 'type': 'number', 'default': None}, {'key': 'formula_threshold', 'type': 'number', 'default': None}, {'key': 'fundamental_change_threshold', 'type': 'number', 'default': 0.2}, {'key': 'metric', 'type': 'text', 'default': 'core_quant_score'}, {'key': 'formula', 'type': 'text', 'default': None}]))

OUTPUTS = [{'key': 'alert_feed', 'source': 'charts', 'render': 'table', 'primary': True, 'label': 'Alert Feed'}, {'key': 'watchlist_live_monitoring_dashboard', 'source': 'charts', 'render': 'table', 'primary': False, 'label': 'Watchlist Live Monitoring Dashboard'}, {'key': 'alert_performance_tracker', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Alert Performance Tracker'}, {'key': 'alert_performance_tracker_historical', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Alert Performance Tracker Historical'}, {'key': 'screen_entry_exit_log', 'source': 'tables', 'render': 'table', 'primary': False, 'label': 'Screen Entry Exit Log'}]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    payload = {**payload, "universe": payload.get("watchlist") or payload.get("universe") or "AAPL MSFT NVDA AMZN META GOOGL"}
    symbols = parse_symbols(payload, default_limit=25, max_symbols=250)
    panel = metric_panel(payload, symbols=symbols)
    score_min = float(payload.get("alert_score_min", 80))
    alerts = current_alerts(panel, payload)
    entries = panel[panel["core_quant_score"] >= score_min][["ticker", "core_quant_score", "sector"]].copy() if not panel.empty else panel
    from ..core.state import compare_and_store
    from ..core.data_loader import ohlcv_for_symbols
    entries = records(entries)
    changes = compare_and_store(str(payload["screen_id"]), entries, str(ohlcv_for_symbols(symbols).Date.max().date())) if payload.get("screen_id") else []
    from ..core.state import store_alerts
    if payload.get("screen_id"):
        store_alerts(str(payload["screen_id"]), str(ohlcv_for_symbols(symbols).Date.max().date()), alerts)
    performance = realized_alert_precision(str(payload["screen_id"])) if payload.get("screen_id") else []
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
            "screen_entry_exit_log": changes,
        },
        meta=access_meta(payload, ["Realized precision requires screen_id and stored, fully matured directional alerts. Email delivery is unavailable without a configured provider. Condition replay statistics are separate from persisted alert precision."]),
    )
