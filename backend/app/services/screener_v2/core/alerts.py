"""Screener V2 alerts computations."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import close_matrix, load_macro
from .common import clean_json, number_like
from .stats import TRADING_DAYS, _wilder_smooth
from .estimators import sma_cross_event


def alert_precision_backtest(panel: pd.DataFrame, alert_type_field_map: dict[str, str], forward_days: tuple[int, ...] = (1, 5, 21)) -> list[dict[str, Any]]:
    symbols = list(panel["ticker"].dropna().astype(str)) if "ticker" in panel.columns else []
    prices = close_matrix(symbols, lookback_days=1512)
    if prices.empty:
        return []
    rows = []
    for alert_type, condition_field in alert_type_field_map.items():
        if condition_field == "golden_cross":
            trigger_dates = sma_cross_event(prices.rolling(50).mean(), prices.rolling(200).mean()) == 1
        elif condition_field == "rsi_extreme":
            delta = prices.diff()
            gain = delta.clip(lower=0).apply(lambda col: _wilder_smooth(col, 14))
            loss = (-delta.clip(upper=0)).apply(lambda col: _wilder_smooth(col, 14))
            rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
            rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((gain == 0) & (loss > 0), 0).mask((gain == 0) & (loss == 0), 50)
            trigger_dates = (rsi >= 75) | (rsi <= 25)
        else:
            continue
        hit_rates = {}
        sample_sizes = {}
        for horizon in forward_days:
            forward = prices.shift(-horizon-1) / prices.shift(-1) - 1.0
            triggered = trigger_dates & forward.notna()
            total = int(triggered.to_numpy().sum())
            hits = int(((forward > 0) & triggered).to_numpy().sum())
            hit_rates[f"{horizon}d"] = hits / total if total else None
            sample_sizes[f"{horizon}d"] = total
        rows.append({"alert_type": alert_type, "hit_rates": hit_rates, "sample_sizes": sample_sizes, "method": "historical condition replay; next-session entry; positive forward-return rate, not delivered-alert precision"})
    return clean_json(rows)


def regime_performance_from_returns(strategy: pd.Series) -> list[dict[str, Any]]:
    regimes = regime_context()
    if strategy.empty or regimes.empty:
        return []
    df = pd.DataFrame({"date": strategy.index, "strategy_return": strategy.values})
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    regimes = regimes.copy()
    regimes["date"] = pd.to_datetime(regimes["date"]).dt.normalize()
    merged = df.merge(regimes[["date", "regime"]], on="date", how="left").ffill()
    rows = []
    for regime, g in merged.dropna(subset=["regime"]).groupby("regime"):
        r = g["strategy_return"]
        rows.append(
            {
                "regime": regime,
                "days": int(len(r)),
                "annualized_return": float((1 + r).prod() ** (TRADING_DAYS / max(len(r), 1)) - 1),
                "annualized_vol": float(r.std() * math.sqrt(TRADING_DAYS)),
                "sharpe": float(r.mean() / (r.std() or np.nan) * math.sqrt(TRADING_DAYS)),
            }
        )
    return clean_json(rows)


def fundamental_change_rows(panel: pd.DataFrame, threshold: float = 0.20) -> list[dict[str, Any]]:
    from .common import records
    fields = [field for field in ["revenue_growth_yoy", "eps_growth_yoy"] if field in panel]
    if not fields:
        return []
    rows = panel[["ticker", *fields]].melt(id_vars="ticker", var_name="metric", value_name="value")
    rows = rows[rows.value.abs() > threshold].assign(type="FUNDAMENTAL_CHANGE")
    rows["severity"] = np.where(rows.value.abs() >= threshold * 2, "high", "medium")
    return records(rows)


def regime_context() -> pd.DataFrame:
    macro = load_macro()
    if macro.empty:
        return pd.DataFrame()
    df = macro.copy()
    vix_col = next((c for c in ["vix_close", "vixcls"] if c in df.columns), None)
    slope_col = next((c for c in ["yc_slope_10y_2y", "yield_slope"] if c in df.columns), None)
    df["vix"] = pd.to_numeric(df[vix_col], errors="coerce") if vix_col else np.nan
    df["slope"] = pd.to_numeric(df[slope_col], errors="coerce") if slope_col else np.nan
    vix_q = df["vix"].quantile([0.33, 0.66]).to_list() if df["vix"].notna().sum() else [15, 25]
    df["regime"] = np.where(df["vix"] >= vix_q[1], "High Vol", np.where(df["vix"] <= vix_q[0], "Low Vol", "Normal"))
    if slope_col:
        df.loc[df["slope"] < 0, "regime"] = "Inverted Curve"
    return df[["date", "regime", "vix", "slope"]].dropna(subset=["date"]).tail(1500)



def current_alerts(panel, payload):
    from .formula import evaluate_formula
    from .common import records
    alerts = []
    def field(name):
        return pd.to_numeric(panel.get(name, pd.Series(np.nan, index=panel.index)), errors='coerce')
    def append(mask, kind, values, message, severity='low', direction=None, metric=None):
        rows = pd.DataFrame({'ticker': panel.ticker, 'type': kind, 'value': values, 'message': message, 'severity': severity})
        if direction is not None:
            rows['direction'] = direction
        if metric:
            rows['metric'] = metric
        alerts.extend(records(rows[mask.fillna(False)]))
    score = field('core_quant_score')
    append(score.ge(float(payload.get('alert_score_min', 80))), 'SCORE_THRESHOLD', score, 'Quant score is above the configured threshold.', 'high', 1)
    move = field('return_1d')
    append(move.abs().ge(float(payload.get('alert_return_1d_abs', .05))), 'PRICE_MOVE', move, 'Observed one-day move exceeds the absolute threshold.', 'medium')
    rsi = field('rsi_14')
    append(rsi.ge(75) | rsi.le(25), 'RSI_EXTREME', rsi, 'RSI is in an extreme band.', direction=pd.Series(np.where(rsi >= 75, -1, 1), index=panel.index))
    metric = payload.get('metric', 'core_quant_score')
    if payload.get('metric_threshold') is not None:
        if metric not in panel:
            raise ValueError(f'Unknown alert metric: {metric}')
        append(field(metric).ge(float(payload['metric_threshold'])), 'METRIC_THRESHOLD', field(metric), 'Metric is above the configured threshold.', 'medium', metric=metric)
    if payload.get('formula_threshold') is not None:
        if not payload.get('formula'):
            raise ValueError('formula_threshold requires an explicit formula')
        result = evaluate_formula(panel, payload['formula']).values
        append(result.ge(float(payload['formula_threshold'])), 'FORMULA_THRESHOLD', result, 'Formula is above the configured threshold.', 'medium', 1)
    volume = field('vratio')
    append(volume.ge(float(payload.get('volume_spike_multiple', 2))), 'VOLUME_SPIKE', volume, 'Observed volume exceeds the configured trailing-average multiple.', 'high')
    for window in [20, 50, 100, 200]:
        for side, direction in [('above', 1), ('below', -1)]:
            name = f'crossed_{side}_sma_{window}_today'
            mask = panel.get(name, pd.Series(False, index=panel.index)).fillna(False).eq(True)
            append(mask, f'PRICE_CROSS_SMA_{"UP" if direction == 1 else "DOWN"}', pd.Series(window, index=panel.index), f'Price crossed {side} SMA-{window} today.', direction=direction, metric=f'sma_{window}')
    append(field('macd_bullish').eq(1) | field('sma50_above_sma200').eq(1) | field('bollinger_pct_b').ge(.95), 'BULLISH_TECHNICAL_CONDITION', field('macd_histogram'), 'Observed bullish SMA, MACD or Bollinger condition.', direction=1)
    streak = pd.concat([field('consecutive_up_days'), field('consecutive_down_days')], axis=1).max(axis=1)
    append(streak.ge(5), 'CONSECUTIVE_DAYS', streak, 'Observed consecutive-day threshold reached.')
    return alerts + fundamental_change_rows(panel, float(payload.get('fundamental_change_threshold', .2)))


def realized_alert_precision(screen_id, horizons=(1, 5, 21)):
    from .state import alert_history
    events = alert_history(screen_id)
    if not events:
        return []
    symbols = sorted({row['ticker'] for row in events})
    prices = close_matrix(symbols, 10000)
    totals = {}
    for row in events:
        if row.get('direction') not in {-1, 1} or prices.empty:
            continue
        entry = prices.index.searchsorted(pd.Timestamp(row['date']), side='right')
        for horizon in horizons:
            key = (row['type'], horizon)
            item = totals.setdefault(key, {'alert_type': row['type'], 'forward_sessions': horizon, 'matured_count': 0, 'hits': 0, 'pending_count': 0, 'missing_price_count': 0})
            exit_index = entry + horizon
            if exit_index >= len(prices):
                item['pending_count'] += 1
                continue
            start, end = prices.iloc[entry][row['ticker']], prices.iloc[exit_index][row['ticker']]
            if not np.isfinite(start) or not np.isfinite(end) or start <= 0:
                item['missing_price_count'] += 1
                continue
            item['matured_count'] += 1
            item['hits'] += int(row['direction'] * (end / start - 1) > 0)
    return [{**item, 'realized_precision': item['hits'] / item['matured_count'] if item['matured_count'] else None,
             'method': 'persisted directional alerts, next-session entry, fully matured observed exits'} for item in totals.values()]
