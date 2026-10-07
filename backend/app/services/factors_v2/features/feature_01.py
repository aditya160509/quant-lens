"""Feature 1: Factor Valuation Spread Monitor."""

from typing import Any, Dict

from app.services.factors_v2.core.analytics import (
    DEFAULT_FACTORS,
    compact_series,
    matrix_records,
    response,
    valuation_spread,
)
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
    if not requested_factors and not valuation_payload.get("factor"):
        valuation_payload["factors"] = DEFAULT_FACTORS
    data = valuation_spread(valuation_payload)
    rows = [_complete_valuation_row(r) for r in data["rows"]]
    series = data["series"]
    crisis_rows = _crisis_anchor_percentiles(data["spread_series"])
    status = "ok" if rows else "warning"
    alerts = [
        {
            "level": "high",
            "status": "open",
            "factor": r["factor"],
            "percentile": r.get("percentile"),
            "message": "Characteristic spread is in the upper historical tail",
        }
        for r in rows
        if r.get("percentile") is not None
        and r["percentile"] >= float(payload.get("alert_percentile") or 70)
    ]
    cheap_alerts = [
        {
            "level": "medium",
            "status": "open",
            "factor": r["factor"],
            "percentile": r.get("percentile"),
            "message": "Characteristic spread is in the lower historical tail",
        }
        for r in rows
        if r.get("percentile") is not None
        and r["percentile"] <= float(payload.get("cheap_percentile") or 30)
    ]
    alert_feed = [
        {
            **alert,
            "status": alert.get("status", "open"),
            "triggered_at": payload.get("as_of_date"),
        }
        for alert in alerts + cheap_alerts
    ]
    return response(
        "feature_01",
        status=status,
        summary_cards=[
            {
                "label": r["factor"],
                "value": r.get("percentile"),
                "unit": "percentile",
                "detail": "Historical characteristic-spread percentile",
            }
            for r in rows
        ],
        charts={
            "gauge_panel": rows,
            "percentile_series": {c: compact_series(series[c]) for c in series.columns},
            "spread_percentile_timeseries": {
                c: compact_series(series[c]) for c in series.columns
            },
            "valuation_correlation": matrix_records(series.corr())
            if len(series.columns) > 1
            else [],
            "valuation_correlation_matrix": matrix_records(series.corr())
            if len(series.columns) > 1
            else [],
            "crisis_anchors": crisis_rows,
            "expected_return_regression": [
                {
                    "factor": r.get("factor"),
                    "percentile": r.get("percentile"),
                    "expected_12m_return": _expected_return_value(r),
                    "regression_beta": r.get("regression_beta")
                    if r.get("regression_beta") is not None
                    else None,
                    "r_squared": r.get("r_squared")
                    if r.get("r_squared") is not None
                    else None,
                    "ci_low_90": r.get("ci_90_low"),
                    "ci_high_90": r.get("ci_90_high"),
                }
                for r in rows
                if r.get("percentile") is not None
            ],
        },
        tables={
            "valuation_spreads": rows,
            "sector_contribution": [
                {"factor": row.get("factor"), **item}
                for row in rows
                for item in row.get("sector_contributors", [])
            ],
            "cross_sector_table": [
                {"factor": row.get("factor"), **item}
                for row in rows
                for item in row.get("sector_contributors", [])
            ],
            "crisis_anchor_percentiles": crisis_rows,
            "crisis_anchor_table": crisis_rows,
            "valuation_spread_detail": rows,
            "alert_feed": alert_feed,
        },
        alerts=alert_feed,
        meta={
            "source": "formation-date prices and 90-day-lagged annual statements",
            "audit_closures": [
                "unavailable predictions remain null, without synthetic coefficients",
                "crisis anchors use only observations available on or before the anchor",
            ],
            "alert_delivery": "in_app only; email/webhook delivery is unavailable",
        },
    )


def _expected_return_value(row):
    return row.get("expected_12m_return")


def _complete_valuation_row(row):
    out = dict(row)
    out["implied_return"] = out.get("expected_12m_return")
    pct = out.get("percentile")
    out["status"] = (
        "unavailable"
        if pct is None or pd.isna(pct)
        else "upper_tail"
        if pct >= 70
        else "lower_tail"
        if pct <= 30
        else "neutral"
    )
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
            available = (
                s.loc[s.index <= anchor] if isinstance(s.index, pd.DatetimeIndex) else s
            )
            if available.empty:
                rows.append(
                    {
                        "factor": factor,
                        "anchor": label,
                        "anchor_date": date_text,
                        "used_date": None,
                        "spread": None,
                        "percentile": None,
                        "status": "unavailable_before_observed_history",
                    }
                )
                continue
            else:
                value = float(available.iloc[-1])
                used_date = str(pd.Timestamp(available.index[-1]).date())
            hist = s.loc[:used_date] if isinstance(s.index, pd.DatetimeIndex) else s
            pct = float((hist < value).mean() * 100.0) if len(hist) else None
            rows.append(
                {
                    "factor": factor,
                    "anchor": label,
                    "anchor_date": date_text,
                    "used_date": used_date,
                    "spread": value,
                    "percentile": pct,
                }
            )
    return rows


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("01")
OUTPUTS = _outputs("01")
