"""Feature 3: Factor Return Attribution and Performance Decomposition."""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.services.factors_v2.core.analytics import factor_returns, response, sector_brinson_fachler
from app.services.factors_v2.core.performance import compute_mode, runtime_meta


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    requested_window = int(payload.get("window_days", 252))
    frequency = str(payload.get("frequency", "monthly" if mode == "realtime" and requested_window > 1260 else "daily")).lower()
    raw_rets = factor_returns(payload).dropna()
    if payload.get("start_date"):
        raw_rets = raw_rets.loc[pd.Timestamp(payload["start_date"]):]
    if payload.get("end_date"):
        raw_rets = raw_rets.loc[:pd.Timestamp(payload["end_date"])]
    raw_rets = raw_rets.tail(requested_window)
    if mode == "realtime" and frequency == "daily" and requested_window > 1260:
        raw_rets = raw_rets.tail(252)
        frequency = "daily_trailing_12m"
    frequency_rule = {"weekly": "W-FRI", "monthly": "ME", "quarterly": "QE"}.get(frequency)
    rets = raw_rets.resample(frequency_rule).sum(min_count=1) if frequency_rule and isinstance(raw_rets.index, pd.DatetimeIndex) else raw_rets
    if rets.empty:
        return response("feature_03", "warning", meta={"warning": "No factor returns available"})
    weights = payload.get("factor_exposures") or {c: 1 / len(rets.columns) for c in rets.columns}
    contrib = rets.mul([float(weights.get(c, 0)) for c in rets.columns], axis=1)
    total = contrib.sum(axis=1)
    residual = pd.Series(0.0, index=total.index)
    brinson = sector_brinson_fachler({**payload, "max_tickers": max(int(payload.get("max_tickers", 600)), 600), "window_days": min(requested_window, 1260 if mode == "realtime" else requested_window)})
    if len(brinson["active"]):
        residual = brinson["active"].reindex(total.index).fillna(0) - total.reindex(brinson["active"].index).fillna(0)
    rows = []
    for c in contrib.columns:
        s = contrib[c].dropna()
        t = float(s.mean() / (s.std() / np.sqrt(len(s)))) if len(s) > 2 and s.std() else None
        rows.append({"factor": c, "cumulative_contribution": float(s.sum()), "mean_daily": float(s.mean()), "t_stat": t, "hit_rate": float((s > 0).mean())})
    annualization = {"weekly": 52, "monthly": 12, "quarterly": 4}.get(frequency, 252)
    ir_factor = float(total.mean() / total.std() * np.sqrt(annualization)) if total.std() else None
    ir_selection = float(residual.mean() / residual.std() * np.sqrt(annualization)) if residual.std() else None
    sector_rows = brinson["rows"]
    if not sector_rows:
        return response("feature_03", "warning", meta={"warning": "Sector-level fundamentals or price returns unavailable for Brinson-Fachler attribution"})
    rolling_ir = _rolling_ir(total, residual)
    best_worst = _best_worst_periods(contrib, residual)
    carryover_rows = _carryover_effect(payload.get("rebalancing_history"), raw_rets)
    freshness_rows = _decision_freshness_score(carryover_rows, total, residual)
    stacked_waterfall = _stacked_active_waterfall(sector_rows, carryover_rows)
    reconciliation = [
        {"component": "brinson_active_return", "value": float(sum(r["total_effect"] for r in sector_rows)), "t_stat": _series_t_stat(brinson["active"])},
        {"component": "factor_contribution", "value": float(total.sum()), "t_stat": _series_t_stat(total)},
        {"component": "selection_residual", "value": float(residual.sum()), "t_stat": _series_t_stat(residual)},
    ]
    return response(
        "feature_03",
        "ok",
        summary_cards=[
            {"label": "Factor IR", "value": ir_factor},
            {"label": "Selection IR", "value": ir_selection},
            {"label": "Total Contribution", "value": float(total.sum())},
        ],
        charts={
            "waterfall": rows + [{"factor": "Selection", "cumulative_contribution": float(residual.sum()), "t_stat": _series_t_stat(residual)}],
            "cumulative_contribution": contrib.cumsum().reset_index().to_dict("records"),
            "rolling_information_ratio": rolling_ir,
            "stacked_active_return_waterfall": stacked_waterfall,
            "decision_freshness_score": freshness_rows,
            "ir_by_component": [
                {"component": "factor_harvesting", "information_ratio": ir_factor},
                {"component": "selection_residual", "information_ratio": ir_selection},
            ],
        },
        tables={
            "factor_contribution": rows,
            "factor_hit_rate": [{"factor": row["factor"], "hit_rate": row["hit_rate"], "periods": int(contrib[row["factor"]].dropna().shape[0])} for row in rows],
            "brinson_fachler": sector_rows,
            "attribution_reconciliation": reconciliation,
            "carryover": carryover_rows,
            "stacked_active_return_waterfall": stacked_waterfall,
            "decision_freshness_score": freshness_rows,
            "best_worst_attribution_periods": best_worst,
        },
        alerts=[],
        meta={
            **runtime_meta("feature_03", payload, ["monthly full history by default; daily realtime capped to trailing 12 months"]),
            "frequency": frequency,
            "requested_window_days": requested_window,
            "computed_rows": int(len(rets)),
            "brinson_fachler": "dynamic sector-neutral allocation/selection/interaction from fundamentals sector map and local price universe",
            "audit_closures": ["rolling IR chart", "factor hit-rate table", "best/worst period ranking", "t-stats on attribution reconciliation"],
        },
    )


def _carryover_effect(rebalancing_history, returns: pd.DataFrame):
    if not rebalancing_history or len(rebalancing_history) < 2:
        return _carryover_proxy_fallback(returns)
    try:
        snapshots = []
        for snap in rebalancing_history:
            date = pd.Timestamp(snap["date"])
            holdings = snap.get("holdings", [])
            weights = {str(row["ticker"]): float(row["weight"]) for row in holdings if "ticker" in row and "weight" in row}
            snapshots.append((date, weights))
        snapshots.sort(key=lambda item: item[0])
        bench = returns.mean(axis=1)
        rows = []
        for idx in range(1, len(snapshots)):
            prev_date, prev_w = snapshots[idx - 1]
            curr_date, curr_w = snapshots[idx]
            next_date = snapshots[idx + 1][0] if idx + 1 < len(snapshots) else returns.index[-1]
            period = returns.loc[curr_date:next_date]
            period_bench = bench.loc[curr_date:next_date]
            if period.empty:
                continue
            asset_return = (1 + period).prod() - 1
            bench_return = float((1 + period_bench).prod() - 1)
            tickers = set(prev_w) | set(curr_w)
            idx_tickers = pd.Index(list(tickers))
            prior = pd.Series(prev_w, dtype=float).reindex(idx_tickers).fillna(0.0)
            current = pd.Series(curr_w, dtype=float).reindex(idx_tickers).fillna(0.0)
            active_return = asset_return.reindex(idx_tickers).fillna(0.0).astype(float) - bench_return
            carry = float(prior.dot(active_return))
            active = float((current - prior).dot(active_return))
            total = carry + active
            rows.append({
                "period_start": str(curr_date.date()),
                "period_end": str(pd.Timestamp(next_date).date()),
                "carryover_contribution": float(carry),
                "active_contribution": float(active),
                "total_active_return": float(total),
                "carryover_fraction": float(carry / total) if abs(total) > 1e-8 else None,
                "n_stocks": len(tickers),
                "method": "holdings_level_brinson_carryover",
            })
        if not rows:
            return _carryover_proxy_fallback(returns)
        total_carry = sum(row["carryover_contribution"] for row in rows)
        total_active = sum(row["active_contribution"] for row in rows)
        total_return = sum(row["total_active_return"] for row in rows)
        rows.append({
            "period_start": "aggregate",
            "period_end": "aggregate",
            "carryover_contribution": float(total_carry),
            "active_contribution": float(total_active),
            "total_active_return": float(total_return),
            "carryover_fraction": float(total_carry / total_return) if abs(total_return) > 1e-8 else None,
            "decision_freshness_score": float(total_active / max(abs(total_return), 1e-8)),
            "n_stocks": None,
            "method": "holdings_level_brinson_carryover",
        })
        return rows
    except Exception as exc:
        return _carryover_proxy_fallback(returns, str(exc))


def _carryover_proxy_fallback(returns: pd.DataFrame, error: Optional[str] = None):
    if returns.empty:
        return []
    total = returns.mean(axis=1).dropna()
    autocorr = float(total.autocorr()) if len(total) > 10 else None
    return [{
        "component": "carryover_proxy_autocorrelation",
        "value": autocorr,
        "method": "time_series_autocorrelation_proxy",
        "warning": "PROXY ONLY: rebalancing_history was not provided. This is aggregate factor-return autocorrelation, not the per-holding Brinson carryover decomposition.",
        "spec_definition": "True carryover = sum_i prior_weight_i * (asset_return_i - benchmark_return); requires historical holding snapshots.",
        "error": error,
    }]


def _stacked_active_waterfall(sector_rows, carryover_rows):
    rows = []
    for row in sector_rows[:18]:
        rows.append(
            {
                "sector": row.get("sector") or row.get("name"),
                "allocation_effect": float(row.get("allocation_effect") or 0.0),
                "selection_effect": float(row.get("selection_effect") or 0.0),
                "interaction_effect": float(row.get("interaction_effect") or 0.0),
                "total_effect": float(row.get("total_effect") or 0.0),
                "method": "brinson_fachler_sector_stack",
            }
        )
    aggregate = next((row for row in carryover_rows if row.get("period_start") == "aggregate"), None)
    if aggregate:
        rows.append(
            {
                "sector": "Decision freshness",
                "carryover_contribution": float(aggregate.get("carryover_contribution") or 0.0),
                "active_contribution": float(aggregate.get("active_contribution") or 0.0),
                "total_effect": float(aggregate.get("total_active_return") or 0.0),
                "method": aggregate.get("method"),
            }
        )
    return rows


def _decision_freshness_score(carryover_rows, total: pd.Series, residual: pd.Series):
    aggregate = next((row for row in carryover_rows if row.get("period_start") == "aggregate"), None)
    if aggregate:
        score = float(aggregate.get("decision_freshness_score") or 0.0)
        return [{**aggregate, "component": "decision_freshness_score", "value": score}]
    aligned = pd.concat([total.rename("factor"), residual.rename("selection")], axis=1).dropna()
    if aligned.empty:
        return []
    rolling_change = aligned.diff().abs().rolling(21, min_periods=5).mean().sum(axis=1).dropna()
    level = aligned.abs().rolling(21, min_periods=5).mean().sum(axis=1).dropna()
    ratio = float((rolling_change.iloc[-1] / max(level.iloc[-1], 1e-12))) if len(rolling_change) and len(level) else 0.0
    return [
        {
            "component": "decision_freshness_score",
            "value": float(max(0.0, min(1.0, ratio))),
            "decision_freshness_score": float(max(0.0, min(1.0, ratio))),
            "method": "rolling_change_over_active_risk_proxy",
            "warning": "Uses factor/selection movement proxy when historical holding snapshots are absent.",
        }
    ]


def _series_t_stat(s: pd.Series) -> Optional[float]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) < 3 or not float(s.std()):
        return None
    return float(s.mean() / (s.std() / np.sqrt(len(s))))


def _rolling_ir(total: pd.Series, residual: pd.Series) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    aligned = pd.concat([total.rename("factor_component"), residual.rename("selection_component")], axis=1).dropna()
    if aligned.empty:
        return rows
    for window, label in [(12, "12_period"), (36, "36_period")]:
        for col in aligned.columns:
            mean = aligned[col].rolling(window, min_periods=max(4, window // 3)).mean()
            vol = aligned[col].rolling(window, min_periods=max(4, window // 3)).std()
            ir = (mean / vol).replace([np.inf, -np.inf], np.nan)
            for idx, val in ir.tail(180).dropna().items():
                rows.append({"date": str(pd.Timestamp(idx).date()), "window": label, "component": col, "information_ratio": float(val)})
    return rows


def _best_worst_periods(contrib: pd.DataFrame, residual: pd.Series) -> list[dict[str, Any]]:
    if contrib.empty:
        return []
    total = contrib.sum(axis=1).add(residual.reindex(contrib.index).fillna(0), fill_value=0)
    rows = []
    ranked = pd.concat([total.nlargest(5), total.nsmallest(5)]).drop_duplicates()
    for idx, value in ranked.items():
        parts = contrib.loc[idx].copy()
        parts["Selection"] = float(residual.reindex([idx]).fillna(0).iloc[0])
        driver = str(parts.abs().idxmax())
        rows.append({
            "date": str(pd.Timestamp(idx).date()),
            "total_attribution": float(value),
            "dominant_driver": driver,
            "dominant_driver_value": float(parts[driver]),
            "rank_type": "best" if value >= 0 else "worst",
        })
    return rows
