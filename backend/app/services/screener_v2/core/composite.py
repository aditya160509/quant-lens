"""Screener V2 composite computations."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import clean_json, number_like
from .stats import (
    _winsorize_at_percentiles,
    beta_neutralize,
    rank_pct,
    sign_correct,
    zscore,
)


def composite_config(payload):
    nested = payload.get("components")
    return {**payload, **nested} if isinstance(nested, dict) else dict(payload)


def component_scores(panel: pd.DataFrame, components: list[dict[str, Any]] | dict[str, Any] | None = None, history_cache=None) -> pd.DataFrame:
    config = components if isinstance(components, dict) else {}
    preset = str(config.get("preset") or "").lower() if isinstance(config, dict) else ""
    weighting_mode = str(config.get("weighting_mode") or "manual").lower() if isinstance(config, dict) else "manual"
    defaults = [
        {"name": "Value", "field": "valuation_percentile", "weight": 0.25},
        {"name": "Quality", "field": "quality_percentile", "weight": 0.25},
        {"name": "Momentum", "field": "momentum_percentile", "weight": 0.25},
        {"name": "Low Vol", "field": "low_vol_percentile", "weight": 0.15},
        {"name": "Liquidity", "field": "liquidity_percentile", "weight": 0.10},
    ]
    presets = {
        "equal_value_quality": [{"name": "Value", "field": "valuation_percentile", "weight": 0.50}, {"name": "Quality", "field": "quality_percentile", "weight": 0.50}],
        "momentum_quality": [{"name": "Momentum", "field": "momentum_percentile", "weight": 0.55}, {"name": "Quality", "field": "quality_percentile", "weight": 0.45}],
        "low_vol_quality": [{"name": "Low Vol", "field": "low_vol_percentile", "weight": 0.55}, {"name": "Quality", "field": "quality_percentile", "weight": 0.45}],
        "vmq": [{"name": "Value", "field": "valuation_percentile", "weight": 0.34}, {"name": "Momentum", "field": "momentum_percentile", "weight": 0.33}, {"name": "Quality", "field": "quality_percentile", "weight": 0.33}],
    }
    if preset == "ff5_screen":
        raise ValueError("FF5 screen is unavailable: debt/assets is not the investment factor")
    if preset and preset not in presets:
        raise ValueError(f"Unknown composite preset: {preset}")
    rows = config.get("components") if isinstance(config, dict) else components
    rows = [dict(row) for row in (rows or presets.get(preset) or defaults)]
    diagnostics_note = None
    if weighting_mode not in {"manual", "equal", "ic_ir", "ridge"}:
        raise ValueError("Unknown weighting_mode")
    if weighting_mode in {"ic_ir", "ridge"}:
        learned, diagnostics_note = historical_weights(panel, rows, config, history_cache)
        for item in rows:
            item["weight"] = float(learned[item["field"]])
    if weighting_mode == "equal":
        for item in rows:
            item["weight"] = 1.0
    out = pd.DataFrame(index=panel.index)
    out["ticker"] = panel["ticker"]
    total_weight = sum(abs(float(r.get("weight", 0))) for r in rows)
    if not np.isfinite(total_weight) or total_weight <= 0:
        raise ValueError("Composite weights must have a positive finite absolute sum")
    names = [str(row.get("name") or row.get("field")) for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("Composite component names must be unique")
    out["composite_score"] = 0.0
    decomposition = []
    for item in rows:
        field = item.get("field")
        name = str(item.get("name") or field)
        weight = float(item.get("weight", 0)) / total_weight
        if field not in panel.columns:
            raise ValueError(f"Unknown component field: {field}")
        else:
            values = _normalized_component(panel, field, config)
            if weight < 0:
                values = -values
                weight = abs(weight)
        out[name] = values
        out["composite_score"] += values * weight
        decomposition.append({"component": name, "field": field, "weight": weight, "mean_score": float(values.mean())})
    out["rank"] = out["composite_score"].rank(ascending=False, method="first").astype("Int64")
    out["composite_raw_score"] = out["composite_score"]
    output_scale = str(config.get("output_scale") or "percentile").lower() if isinstance(config, dict) else "percentile"
    if output_scale in {"zscore", "z", "-3_3"}:
        out["composite_score"] = zscore(out["composite_score"]).clip(-3, 3)
    elif output_scale in {"signed_rank", "signed", "-1_1"}:
        out["composite_score"] = out["composite_score"].rank(pct=True) * 2.0 - 1.0
    else:
        out["composite_score"] = out["composite_score"].rank(pct=True) * 100.0
    out["rank"] = out["composite_score"].rank(ascending=False, method="first").astype("Int64")
    out.attrs["decomposition"] = decomposition
    out.attrs["weighting_mode"] = weighting_mode
    if diagnostics_note:
        out.attrs["weighting_diagnostics"] = diagnostics_note
    return out.sort_values("composite_score", ascending=False).reset_index(drop=True)


def score_decomposition_for_ticker(scored: pd.DataFrame, ticker: str | None = None) -> list[dict[str, Any]]:
    if scored.empty:
        return []
    symbol = str(ticker or scored.iloc[0].get("ticker") or "").upper()
    row = scored[scored["ticker"].astype(str).str.upper().eq(symbol)]
    if row.empty:
        raise ValueError(f"Focus ticker {symbol} is outside the scored universe")
    r = row.iloc[0]
    rows = []
    for item in scored.attrs.get("decomposition", []):
        component = item.get("component")
        if component not in scored.columns:
            continue
        weight = number_like(item.get("weight")) or 0.0
        component_value = number_like(r.get(component))
        if component_value is None:
            continue
        rows.append(
            {
                "ticker": r.get("ticker"),
                "component": component,
                "field": item.get("field"),
                "weight": weight,
                "component_score": component_value,
                "weighted_contribution": component_value * weight,
                "mean_universe_score": item.get("mean_score"),
            }
        )
    return clean_json(sorted(rows, key=lambda x: abs(number_like(x.get("weighted_contribution")) or 0.0), reverse=True))


def effective_num_factors(weights: dict[str, float], corr_matrix: pd.DataFrame) -> float | None:
    if not weights or corr_matrix.empty:
        return None
    fields = [f for f in weights if f in corr_matrix.columns]
    if len(fields) < 2:
        return float(len(fields)) if fields else None
    w = np.array([weights[f] for f in fields], dtype=float)
    sub_corr = corr_matrix.loc[fields, fields].to_numpy(dtype=float)
    n = len(fields)
    off_diag = sub_corr[~np.eye(n, dtype=bool)]
    avg_rho = float(np.nanmean(off_diag)) if len(off_diag) else 0.0
    denominator = float((w**2).sum())
    base = float((w.sum() ** 2) / denominator) if denominator else float(n)
    return float(np.clip(base / (1.0 + avg_rho), 1, n)) if (1.0 + avg_rho) > 0 else float(n)



class InsufficientTrainingData(ValueError):
    """No learned portfolio is formed until its historical training window exists."""


def _normalized_component(panel, field, config):
    values = sign_correct(field, pd.to_numeric(panel[field], errors='coerce'))
    if config.get('winsorize'):
        values = _winsorize_at_percentiles(values)
    if config.get('sector_neutral'):
        values = values - values.groupby(panel.sector).transform('median')
    if config.get('beta_neutral'):
        values = beta_neutralize(values, pd.to_numeric(panel.beta_252, errors='coerce'))
    return (rank_pct(values) / 50 - 1) if config.get('signed_rank') else rank_pct(values)


def historical_weights(panel, rows, config, history_cache=None):
    """Learn only from monthly formation signals with fully matured forward labels."""
    from sklearn.linear_model import Ridge

    from .data_loader import AS_OF, as_of_context, close_matrix
    from .panel import metric_panel
    fields = [row['field'] for row in rows]
    if len(fields) != len(set(fields)):
        raise ValueError('Learned components require distinct fields')
    horizon = {'return_1m': 21, 'return_3m': 63, 'return_6m': 126}.get(config.get('ic_target_field', 'return_1m'))
    if horizon is None:
        raise ValueError('Training target must be return_1m, return_3m or return_6m')
    prices = close_matrix(panel.ticker.tolist(), 1008)
    cutoff = AS_OF.get() or panel.attrs.get('as_of_date') or (prices.index[-1] if not prices.empty else None)
    if cutoff is None or prices.empty:
        raise InsufficientTrainingData('Historical prices are unavailable for learned weights')
    prices = prices.loc[:pd.Timestamp(cutoff)]
    dates = prices.index[251:-horizon-1:21]
    cache = history_cache if history_cache is not None else {}
    samples, ic_rows = [], []
    for date in dates:
        index = prices.index.get_loc(date)
        entry, exit_date = prices.index[index + 1], prices.index[index + 1 + horizon]
        if exit_date > pd.Timestamp(cutoff):
            continue
        key = ('training', date)
        if key not in cache:
            with as_of_context(date):
                historical = metric_panel({'as_of_date': str(date.date()), 'lookback_days': 756}, panel.ticker.tolist())
            features = pd.DataFrame({'ticker': historical.ticker})
            for field in fields:
                features[field] = _normalized_component(historical, field, config)
            cache[key] = features.set_index('ticker')
        features = cache[key]
        target = prices.loc[exit_date] / prices.loc[entry] - 1
        frame = features.join(target.rename('forward_return')).replace([np.inf, -np.inf], np.nan).dropna()
        if len(frame) < 3:
            continue
        ic_rows.append({'formation_date': date, 'label_end': exit_date, **{field: frame[field].corr(frame.forward_return, method='spearman') for field in fields}})
        frame['forward_return'] -= frame.forward_return.mean()
        samples.append(frame)
    minimum = max(6, int(config.get('min_training_periods', 6)))
    if len(ic_rows) < minimum:
        raise InsufficientTrainingData(f'Learned weights require {minimum} matured monthly samples; available: {len(ic_rows)}')
    ic = pd.DataFrame(ic_rows)
    if config.get('weighting_mode') == 'ic_ir':
        mean = ic[fields].mean()
        deviation = ic[fields].std(ddof=1)
        weights = mean / deviation.where(deviation > 0)
        if weights.isna().any():
            raise InsufficientTrainingData('IC-IR is undefined for a constant or missing historical IC series')
    else:
        alpha = float(config.get('ridge_lambda', 1))
        if not np.isfinite(alpha) or alpha < 0:
            raise ValueError('ridge_lambda must be finite and nonnegative')
        training = pd.concat(samples, ignore_index=True)
        model = Ridge(alpha=alpha).fit(training[fields], training.forward_return)
        weights = pd.Series(model.coef_, index=fields)
    if weights.abs().sum() == 0:
        raise InsufficientTrainingData('All learned component weights are zero')
    weights /= weights.abs().sum()
    diagnostics = {'method': config['weighting_mode'], 'formation_count': len(ic_rows), 'sample_count': sum(len(frame) for frame in samples),
                   'training_as_of': str(pd.Timestamp(cutoff).date()), 'last_label_end': str(ic.label_end.max().date()),
                   'forward_horizon_sessions': horizon, 'execution_lag_sessions': 1, 'purging': 'all labels must mature by training_as_of',
                   'component_ic': [{'field': field, 'mean_ic': number_like(ic[field].mean()), 'ic_ir': number_like(ic[field].mean() / ic[field].std(ddof=1))} for field in fields]}
    return weights, diagnostics
