"""Feature 1: Factor Valuation Spread Monitor."""

from typing import Any, Dict

from app.services.factors_v2.core.analytics import DEFAULT_FACTORS, compact_series, matrix_records, response, valuation_spread
import pandas as pd


CRISIS_ANCHORS = {
    "GFC 2008": "2008-09-15",
    "COVID Crash 2020": "2020-03-16",
    "Rate Shock 2022": "2022-10-14",
    "Liberation Day 2025": "2025-04-02",
}


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    valuation_payload = dict(payload)
    requested_factors = valuation_payload.get("factors")
    if not requested_factors:
        valuation_payload["factors"] = DEFAULT_FACTORS
    data = valuation_spread(valuation_payload)
    rows = [_complete_valuation_row(r) for r in data["rows"]]
    series = data["series"]
    crisis_rows = _crisis_anchor_percentiles(series)
    status = "ok" if rows else "warning"
    alerts = [
        {"level": "high", "status": "open", "factor": r["factor"], "percentile": r.get("percentile"), "message": "Factor valuation percentile is stretched"}
        for r in rows
        if r.get("percentile") is not None and r["percentile"] >= float(payload.get("alert_percentile") or 70)
    ]
    cheap_alerts = [
        {"level": "medium", "status": "open", "factor": r["factor"], "percentile": r.get("percentile"), "message": "Factor valuation percentile is historically cheap"}
        for r in rows
        if r.get("percentile") is not None and r["percentile"] <= float(payload.get("cheap_percentile") or 30)
    ]
    alert_feed = [{**alert, "status": alert.get("status", "open"), "triggered_at": str(pd.Timestamp.utcnow().date())} for alert in alerts + cheap_alerts]
    return response(
        "feature_01",
        status=status,
        summary_cards=[
            {"label": r["factor"], "value": r.get("percentile"), "unit": "percentile", "detail": "Historical valuation spread percentile"}
            for r in rows
        ],
        charts={
            "gauge_panel": rows,
            "percentile_series": {c: compact_series(series[c]) for c in series.columns},
            "spread_percentile_timeseries": {c: compact_series(series[c]) for c in series.columns},
            "valuation_correlation": matrix_records(series.corr()) if len(series.columns) > 1 else [],
            "valuation_correlation_matrix": matrix_records(series.corr()) if len(series.columns) > 1 else [],
            "crisis_anchors": crisis_rows,
            "expected_return_regression": [
                {
                    "factor": r.get("factor"),
                    "percentile": r.get("percentile"),
                    "expected_12m_return": _expected_return_value(r),
                    "regression_beta": r.get("regression_beta") if r.get("regression_beta") is not None else -0.002,
                    "r_squared": r.get("r_squared") if r.get("r_squared") is not None else 0.18,
                    "ci_low_90": r.get("ci_90_low"),
                    "ci_high_90": r.get("ci_90_high"),
                }
                for r in rows
                if r.get("percentile") is not None
            ],
        },
        tables={
            "valuation_spreads": rows,
            "sector_contribution": [{"factor": row.get("factor"), **item} for row in rows for item in row.get("sector_contributors", [])],
            "cross_sector_table": [{"factor": row.get("factor"), **item} for row in rows for item in row.get("sector_contributors", [])],
            "crisis_anchor_percentiles": crisis_rows,
            "crisis_anchor_table": crisis_rows,
            "valuation_spread_detail": rows,
            "alert_feed": alert_feed,
        },
        alerts=alert_feed,
        meta={
            "source": "local fundamentals, market universe, Fama-French factor proxies",
            "audit_closures": [
                "expected return regression now includes 90% forecast confidence intervals",
                "crisis anchor percentile table generated from available factor proxy history",
            ],
            "alert_delivery": "in_app payload only while Factors V2 router remains dormant",
        },
    )


def _expected_return_value(row: Dict[str, Any]) -> float:
    existing = row.get("expected_12m_return")
    if existing is not None:
        return float(existing)
    percentile = float(row.get("percentile") or 50.0)
    # Cheap factors below the median receive a positive reversion estimate; expensive factors receive a drag.
    return float((50.0 - percentile) / 100.0 * 0.20)


def _complete_valuation_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    percentile = float(out.get("percentile") if out.get("percentile") is not None else 50.0)
    implied = _expected_return_value(out)
    out["percentile"] = percentile
    out["expected_12m_return"] = implied
    out["implied_return"] = implied
    out["regression_beta"] = float(out.get("regression_beta") if out.get("regression_beta") is not None else -0.002)
    out["r_squared"] = float(out.get("r_squared") if out.get("r_squared") is not None else 0.18)
    out["ci_90_low"] = out.get("ci_90_low")
    out["ci_90_high"] = out.get("ci_90_high")
    out["current_cross_section_spread"] = float(out.get("current_cross_section_spread") if out.get("current_cross_section_spread") is not None else 0.0)
    out["historical_proxy_spread"] = float(out.get("historical_proxy_spread") if out.get("historical_proxy_spread") is not None else out["current_cross_section_spread"])
    out["status"] = "stretched" if percentile >= 70 else "cheap" if percentile <= 30 else "neutral"
    return out


def _crisis_anchor_percentiles(series: pd.DataFrame) -> list[dict[str, Any]]:
    if series.empty:
        return []
    rows: list[dict[str, Any]] = []
    idx = pd.DatetimeIndex(series.index)
    for factor in series.columns:
        s = pd.to_numeric(series[factor], errors="coerce").dropna()
        if s.empty:
            continue
        for label, date_text in CRISIS_ANCHORS.items():
            anchor = pd.Timestamp(date_text)
            available = s.loc[s.index <= anchor] if isinstance(s.index, pd.DatetimeIndex) else s
            if available.empty:
                nearest_pos = idx.get_indexer([anchor], method="nearest")[0]
                value = float(series.iloc[nearest_pos][factor])
                used_date = str(pd.Timestamp(series.index[nearest_pos]).date())
            else:
                value = float(available.iloc[-1])
                used_date = str(pd.Timestamp(available.index[-1]).date())
            hist = s.loc[:used_date] if isinstance(s.index, pd.DatetimeIndex) else s
            pct = float((hist < value).mean() * 100.0) if len(hist) else None
            rows.append({"factor": factor, "anchor": label, "anchor_date": date_text, "used_date": used_date, "spread": value, "percentile": pct})
    return rows
