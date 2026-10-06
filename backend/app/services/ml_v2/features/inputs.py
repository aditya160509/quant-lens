"""Backend-owned ML V2 form contract: input metadata, output metadata and value validation.

``inputs()`` turns a feature's ``INPUT_CONTRACT`` into the manifest rows the frontend renders
(type, default, options, min/max, required, depends_on, unit, level, help) and ``validate()`` enforces
exactly those rows, so the form and the server cannot disagree. ``outputs()`` publishes every result
panel with its chart type, encoding and column schema.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.services.ml_v2.core.data_loader import UNIVERSE_PRESET_IDS
from typing import Any

# Keys older clients still send; they changed nothing, so they are dropped rather than rejected.
DEPRECATED_INPUTS = ("compute_mode", "research_mode")

# Frontend types. Numeric contract types with a fixed option list render as selects.
_TYPE = {"integer": "number", "float": "number", "number": "number", "multi_select": "multiselect",
         "object": "json", "asset_return_map": "json", "dated_strategy_matrix": "json"}

SHARED: dict[str, dict[str, Any]] = {
    "symbols": {"type": "ticker_list"},
    "universe": {"type": "select", "options": UNIVERSE_PRESET_IDS, "default": "default"},
    "frequency": {"type": "select", "options": ["daily"], "default": "daily"},
    "lookback_days": {"type": "integer", "min": 90, "max": 10000, "default": 756},
    "max_symbols": {"type": "integer", "min": 1, "max": 5000, "default": 120},
    "as_of_date": {"type": "date"},
}


def _m(level: str, help_: str, unit: str = "", depends_on: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {"level": level, "help": help_, "unit": unit, "depends_on": depends_on, **extra}


def _on(field: str, *values: Any) -> dict[str, Any]:
    return {"field": field, "values": list(values)}


def _has(field: str) -> dict[str, Any]:
    return {"field": field, "present": True}

# level: quick (always shown), standard (shown by default in the form), expert (behind "advanced").
INPUT_META: dict[str, dict[str, Any]] = {
    "symbols": _m("quick", "Tickers to study. Leave empty for the most-covered local symbols. Unknown tickers are rejected, never substituted."),
    "universe": _m("quick", "Ticker preset: the default 35 US large caps, one GICS sector, high volatility, ETFs, or all local symbols. Ignored when symbols (or holdings) is set."),
    "frequency": _m("expert", "Daily bars only."),
    "lookback_days": _m("quick", "Trading sessions of history loaded per symbol, counted back from the as-of date.", "sessions"),
    "max_symbols": _m("standard", "Upper bound on the number of symbols; an explicit list longer than this is rejected.", "symbols"),
    "as_of_date": _m("standard", "Pretend the data ends on this date. Nothing observed later is used anywhere in the run.", "date"),
    "embargo_period": _m("standard", "Sessions skipped between training and test labels on top of the label horizon, to stop overlapping labels leaking.", "sessions"),
    "prediction_horizon": _m("quick", "Forward return horizon predicted by the model.", "sessions"),
    "cost_bps": _m("standard", "One-way trading cost applied to turnover in the portfolio simulation.", "bps"),
    # F01
    "model_type": _m("quick", "Estimator evaluated inside every CPCV split."),
    "label_type": _m("expert", "Regression on the forward return is the only supported label."),
    "cpcv_n_groups": _m("standard", "Number of contiguous date groups the sample is cut into (N).", "groups"),
    "cpcv_k_test_groups": _m("standard", "Groups held out as test in each split (k); paths = C(N,k)*k/N.", "groups"),
    "calculate_embargo_sensitivity": _m("expert", "Re-run the whole CPCV at embargo 0/5/10/21 sessions (4x runtime)."),
    "strategy_returns": _m("expert", "Dated time-by-strategy return matrix for CSCV probability of backtest overfitting and deflated Sharpe. Without it both are reported as unavailable."),
    "pbo_partitions": _m("expert", "Even number of time blocks used by CSCV.", "blocks", _has("strategy_returns")),
    "selected_strategy": _m("expert", "Zero-based column of the strategy matrix whose deflated Sharpe is reported.", "column", _has("strategy_returns")),
    # F02
    "model_family": _m("quick", "Model class, or 'all' to compare and ensemble every available class."),
    "feature_set": _m("expert", "Local OHLCV factor library."),
    "prediction_target": _m("expert", "Next-period forward return."),
    "tuning_mode": _m("standard", "platform_defaults, hand-set hyperparameters, or Optuna TPE search on the validation window."),
    "optuna_trials": _m("standard", "TPE trials per model.", "trials", _on("tuning_mode", "optuna_research")),
    "hyperparameters": _m("expert", "JSON object of estimator parameters keyed by model name.", "", _on("tuning_mode", "manual")),
    "sample_weighting": _m("expert", "equal, or exponentially decayed toward the most recent training dates."),
    "sector_filter": _m("expert", "Keep only these sectors (latest-snapshot metadata, time-invariant)."),
    "minimum_formation_notional": _m("expert", "Drop assets whose median formation-window traded value is below this, in the quote currency.", "quote currency"),
    "exact_shap_cap": _m("expert", "Rows used for exact SHAP values.", "rows"),
    # F03
    "asset": _m("quick", "Single asset whose volatility is forecast."),
    "forecast_horizons": _m("quick", "Horizons forecast, each with its own purged validation.", "sessions"),
    "model_suite": _m("standard", "HAR variants, cross-asset HAR-X, or a one-step ARCH-family model selection."),
    "garch_fit_cap": _m("expert", "Most recent returns used to fit ARCH-family models.", "sessions", _on("model_suite", "arch_family", "har_ml")),
    # F04
    "profit_taking_barrier": _m("quick", "Upper barrier. A return fraction in fixed mode; a multiple of horizon volatility in vol_scaled mode (at least 0.25).", "return or sigma"),
    "stop_loss_barrier": _m("quick", "Lower barrier. A return fraction in fixed mode; a multiple of horizon volatility in vol_scaled mode (at least 0.25).", "return or sigma"),
    "max_holding_period": _m("quick", "Vertical barrier.", "sessions"),
    "barrier_mode": _m("standard", "fixed uses return fractions; vol_scaled uses multiples of trailing 21-session volatility times sqrt(horizon)."),
    "barrier_side": _m("expert", "Bilateral barriers only."),
    "primary_side_model": _m("expert", "Primary side is the sign of the trailing 21-session return, known at formation."),
    "position_sizing": _m("standard", "Meta-probability as the position size, or a binary 0/1 at 0.5."),
    "confidence_level": _m("standard", "Target coverage of the conformal return interval.", "probability"),
    # F05
    "optimization_variant": _m("quick", "Hierarchical risk parity, nested clustered optimisation, or constrained minimum variance."),
    "covariance_estimator": _m("standard", "Covariance model fit on each training window."),
    "clustering_linkage": _m("expert", "Linkage used to build the asset tree.", "", _on("optimization_variant", "standard_hrp", "nco")),
    "allocation_window": _m("standard", "Trailing window used to estimate covariance at each monthly refit.", "sessions"),
    "min_weight": _m("standard", "Smallest per-asset weight.", "weight", min=0.0, max=1.0),
    "max_weight": _m("standard", "Largest per-asset weight.", "weight", min=0.0, max=1.0),
    "max_sector_weight": _m("standard", "Largest sector weight; set to 1 to disable. Every asset needs sector metadata when below 1.", "weight", min=0.0, max=1.0),
    "risk_aversion": _m("expert", "Risk-aversion coefficient for minimum variance and Black-Litterman.", "", ),
    "black_litterman_tau": _m("expert", "Scales prior uncertainty in Black-Litterman.", "", min=1e-4, max=1.0),
    "views": _m("expert", "JSON map of asset to expected return; empty means no views (the posterior equals the equal-weight reference prior)."),
    # F06
    "hmm_state_count": _m("quick", "Hidden states in the Gaussian HMM.", "states"),
    "gmm_component_count": _m("standard", "Mixture components in the parallel GMM.", "components"),
    "input_features": _m("standard", "Market features the regime models are trained on."),
    "pc1_window": _m("standard", "Rolling window for first-principal-component variance.", "sessions"),
    "random_graph_threshold": _m("expert", "Absolute correlation threshold defining an edge in the correlation network.", "|rho|", min=0.0, max=1.0),
    "regime_alert_threshold": _m("standard", "Probability above which a regime is flagged.", "probability", min=0.0, max=1.0),
    # Alpha, risk and allocation hand-offs
    "feature_families": _m("standard", "Feature families the models may use; custom formula features are always included."),
    "formulas": _m("standard", "Custom features as a list of {name, expr}, written in the Research formula language and evaluated on daily data (at most 8)."),
    "watchlist": _m("quick", "Up to 50 tickers scored at once for the risk-today card; when set, the single asset is ignored.", "tickers"),
    "target_volatility": _m("standard", "Annualised volatility the position-size helper targets.", "annualised"),
    "max_size": _m("expert", "Cap on the volatility-targeted size multiple.", "x"),
    "regime_artifact_id": _m("expert", "Stress-probability series from a Regimes run (meta.artifact_id); replaces the asset's own regime filter."),
    "holdings": _m("quick", "Current holdings as {ticker: weight} or {ticker: shares}; produces a rebalance trade list with costs and the expected risk change. Becomes the universe when no symbols are given."),
    "holdings_unit": _m("standard", "Whether holdings values are weights or share counts.", "", {"field": "holdings", "present": True}),
    "portfolio_value": _m("standard", "Portfolio value in dollars when holdings are weights.", "USD", {"field": "holdings", "present": True}),
    "alpha_artifact_id": _m("standard", "Id of an Alpha run (meta.artifact_id); its scores become Black-Litterman views by the Grinold rule when its held-out IC is positive."),
    "bootstrap_samples": _m("expert", "Block-bootstrap resamples behind the weight-stability bands (0 turns them off).", "resamples"),
    # Validate
    "random_seed": _m("expert", "Seed for permutations, bootstrap and model refits; recorded in the reproducibility receipt.", "", min=0, max=2**31 - 1),
    "upload_id": _m("quick", "Id returned by POST /api/ml/v2/uploads: returns, predictions with outcomes, feature panel or trial matrix for Validate; a feature panel adds extra features in Alpha; predictions give the primary side in Meta-labelling."),
    "artifact_id": _m("quick", "Hand-off id from an Alpha run (meta.artifact_id: held-out predictions) or an Allocation run (meta.artifact_id: walk-forward net returns); Meta-labelling accepts Alpha ids only and uses the scores as the primary side."),
    "trials_upload_id": _m("standard", "Trial matrix upload holding every configuration you tried; sets the true trial count for PBO and deflated Sharpe."),
    "benchmark_upload_id": _m("expert", "Returns upload used as the buy-and-hold control for a returns-only validation."),
    "source_result": _m("expert", "Result of a feature 01 or feature 02 run to validate instead of an upload."),
    "trial_count": _m("standard", "True number of strategies or settings tried, if larger than the trial matrix columns.", "trials"),
    "trials_are": _m("expert", "Whether trial matrix columns are different configurations or the same model re-run with different seeds."),
    "n_seeds": _m("standard", "Seeds re-run for stability, capped at 10.", "seeds"),
    "grid_size": _m("standard", "Side of the parameter plateau grid, at most 5 (5 x 5).", "cells"),
    "n_permutations": _m("expert", "Shuffled-signal control permutations (seeded).", "permutations"),
    "improve_strategy": _m("standard", "Also report the meta-label filter and sizing beside the unfiltered strategy."),
}

# Extra bounds for float inputs the feature files leave unbounded.
GROUPS = {"quick": "Essentials", "standard": "Model settings", "expert": "Advanced"}


def inputs(contract: list[dict[str, Any]], defaults: dict[str, Any], shared: bool = True) -> list[dict[str, Any]]:
    declared = {item["key"]: dict(item) for item in contract}
    for key, row in (SHARED.items() if shared else ()):
        declared.setdefault(key, {"key": key, **row})
        if key in defaults:
            declared[key]["default"] = defaults[key]
    for key in defaults:
        declared.setdefault(key, {"key": key})
    out = []
    for key, item in declared.items():
        meta = INPUT_META[key]
        raw_type = item.get("type") or ("boolean" if isinstance(item.get("default", defaults.get(key)), bool) else "number")
        default = item.get("default", defaults.get(key))
        lo, hi = item.get("range", (item.get("min"), item.get("max")))
        lo, hi = meta.get("min", lo), meta.get("max", hi)
        options = item.get("options")
        row: dict[str, Any] = {
            "key": key, "label": item.get("label") or key.replace("_", " ").capitalize(),
            "type": "select" if options is not None and raw_type in {"integer", "float", "number", "select"} else _TYPE.get(raw_type, raw_type),
            "default": default, "required": bool(item.get("required", False)),
            "level": meta["level"], "group": GROUPS[meta["level"]], "unit": meta["unit"], "help": meta["help"],
            "depends_on": meta["depends_on"],
        }
        if options is not None:
            row["options"] = options
        if row["type"] == "number":
            row["integer"] = raw_type == "integer"
            if lo is not None:
                row["min"] = lo
            if hi is not None:
                row["max"] = hi
        out.append(row)
    return out


_SCHEMA_FILE = Path(__file__).with_name("output_schemas.json")
_SCHEMAS: dict[str, Any] | None = None

# (chart type, encoding) per feature output. x/y/series/value/facet name columns of the records.
# 'y' may list several columns (wide data). bin=true means raw values the client histograms.
_O = {
    "01": {"cpcv_sharpe_distribution": ("bar", {"x": "sharpe", "bin": True}),
           "purged_vs_naive_cv_comparison": ("bar", {"x": "method", "y": "sharpe"}),
           "backtest_paths_chart": ("timeseries", {"x": "date", "y": "equity", "series": "path"}),
           "probability_of_backtest_overfitting": ("kpi", {"value": ["pbo", "dsr"], "status": "status"}),
           "deflated_sharpe_ratio": ("kpi", {"value": ["pbo", "dsr"], "status": "status"})},
    "02": {"decile_spreads": ("bar", {"x": "bin", "y": "mean_return", "series": "model", "facet": "weighting"}),
           "net_of_cost_curve": ("timeseries", {"x": "date", "y": "equity", "series": "model"}),
           "shap_feature_importance": ("bar", {"x": "feature", "y": "mean_abs_shap"}),
           "shap_beeswarm": ("scatter", {"x": "shap_value", "y": "feature", "color": "feature_value"}),
           "shap_waterfall_top_signal": ("bar", {"x": "feature", "y": "shap_value"}),
           "model_ic_leaderboard": ("bar", {"x": "model", "y": ["validation_ic", "test_ic"]}),
           "rolling_monthly_ic_series": ("timeseries", {"x": "month", "y": "rolling_ic"})},
    "03": {"var_es_forecast": ("table", {}),
           "regime_probability": ("timeseries", {"x": "date", "y": "stress_probability"}),
           "forecast_error_distribution": ("bar", {"x": "model", "y": "mae", "facet": "horizon"}),
           "vol_term_structure": ("timeseries", {"x": "horizon", "y": "forecast_vol", "series": "model"}),
           "model_confidence_intervals": ("timeseries", {"x": "date", "y": ["lower", "upper"], "series": "model", "facet": "horizon"}),
           "realized_vol_estimator_comparison": ("bar", {"x": "estimator", "y": "current_vol"}),
           "garch_leverage_news_impact_curve": ("timeseries", {"x": "shock_sigma", "y": "next_variance"}),
           "ensemble_vol_forecast_weights": ("bar", {"x": "model", "y": "ensemble_weight"})},
    "04": {"triple_barrier_label_distribution": ("bar", {"x": "label", "y": "count"}),
           "event_outcome_timeline": ("scatter", {"x": "date", "y": "forward_return", "color": "label"}),
           "meta_label_probability_distribution": ("bar", {"x": "meta_probability", "bin": True}),
           "cqr_interval_width_distribution": ("bar", {"x": "interval_width", "bin": True}),
           "cqr_coverage_audit": ("timeseries", {"x": "date", "y": ["empirical_coverage", "target_coverage"]}),
           "label_method_comparison": ("bar", {"x": "method", "y": ["positive_rate", "negative_rate", "neutral_rate"]}),
           "barrier_sensitivity_surface": ("heatmap", {"x": "profit_taking", "y": "stop_loss", "value": "positive_rate"})},
    "05": {"controls_equity": ("timeseries", {"x": "date", "y": "equity", "series": "strategy"}),
           "weight_stability": ("bar", {"x": "asset", "y": "weight", "lower": "p05", "upper": "p95"}),
           "hrp_weight_vector": ("bar", {"x": "asset", "y": "weight"}),
           "cluster_dendrograms": ("dendrogram", {"left": "left", "right": "right", "height": "distance", "size": "count"}),
           "quasi_diagonalized_covariance_heatmap": ("heatmap", {"x": "col", "y": "row", "value": "value"}),
           "risk_contribution_decomposition": ("bar", {"x": "asset", "y": "risk_contribution"}),
           "walk_forward_allocation": ("timeseries", {"x": "date", "y": "equity"}),
           "bl_vs_pure_hrp_weight_comparison": ("bar", {"x": "asset", "y": ["allocation_weight", "black_litterman"]})},
    "06": {"regime_probability_time_series": ("timeseries", {"x": "date", "y": ["state_1", "state_2", "state_3", "state_4"]}),
           "regime_transition_heatmap": ("heatmap", {"x": "col", "y": "row", "value": "value"}),
           "ensemble_vs_hmm_comparison": ("kpi", {"value": ["oos_agreement"]}),
           "pc1_variance_monitor": ("timeseries", {"x": "date", "y": "pc1_explained_variance"}),
           "regime_conditional_asset_returns": ("bar", {"x": "asset", "y": "mean_log_return", "series": "regime"}),
           "correlation_network_density": ("kpi", {"value": ["density"]}),
           "parallel_gmm_regime_probabilities": ("timeseries", {"x": "date", "y": ["component_1", "component_2", "component_3", "component_4"]})},
}

# Outputs that stay empty unless an input is set.
_OUTPUT_DEPENDS = {
    ("01", "embargo_sensitivity"): _on("calculate_embargo_sensitivity", True),
    ("01", "probability_of_backtest_overfitting"): _has("strategy_returns"),
    ("01", "deflated_sharpe_ratio"): _has("strategy_returns"),
    ("02", "tuning_trials"): _on("tuning_mode", "optuna_research"),
    ("03", "garch_model_selection"): _on("model_suite", "arch_family"),
    ("03", "garch_leverage_news_impact_curve"): _on("model_suite", "arch_family"),
    ("03", "ensemble_vol_forecast_weights"): _on("model_suite", "arch_family"),
}


def _schemas() -> dict[str, Any]:
    global _SCHEMAS
    if _SCHEMAS is None:
        _SCHEMAS = json.loads(_SCHEMA_FILE.read_text()) if _SCHEMA_FILE.exists() else {}
    return _SCHEMAS


def outputs(contract: list[dict[str, Any]], feature_id: str = "") -> list[dict[str, Any]]:
    out = []
    for i, row in enumerate(contract):
        key, location = row["key"], row["location"]
        kind, encoding = _O.get(feature_id, {}).get(key, ("table", {}))
        out.append({
            "id": key, "title": row.get("title") or key.replace("_", " ").capitalize(), "type": kind,
            "path": f"{location}.{key}", "location": location, "renderer": row["renderer"], "encoding": encoding,
            "schema": _schemas().get(f"{feature_id}.{location}.{key}"), "primary": i == 0,
            "depends_on": _OUTPUT_DEPENDS.get((feature_id, key)),
        })
    return out


def _check_date(key: str, value: Any) -> None:
    import pandas as pd
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {key}") from exc
    if pd.isna(stamp):
        raise ValueError(f"Invalid {key}")


def validate(payload: dict[str, Any], contract: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply defaults and enforce type, options and numeric bounds; unknown keys are rejected."""
    payload = {k: v for k, v in payload.items() if k not in DEPRECATED_INPUTS}
    unknown = set(payload) - {row["key"] for row in contract}
    if unknown:
        raise ValueError("Unsupported inputs: " + ", ".join(sorted(unknown)))
    for row in contract:
        key = row["key"]
        payload.setdefault(key, row.get("default"))
        value = payload[key]
        if value is None:
            if row.get("required"):
                raise ValueError(f"{key} is required")
            continue
        kind = row["type"]
        if kind == "date":
            _check_date(key, value)
        elif kind == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{key} must be boolean")
        elif kind == "multiselect" and not isinstance(value, list):
            raise ValueError(f"{key} must be a list")
        options = row.get("options")
        if options is not None:
            values = value if kind == "multiselect" else [value]
            if any(v not in options for v in values):
                raise ValueError(f"Unsupported {key}={value!r}; supported values: {options}")
        if kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be numeric")
            if not math.isfinite(value) or (row.get("integer") and value != int(value)):
                raise ValueError(f"Invalid numeric {key}")
            if value < row.get("min", -math.inf) or value > row.get("max", math.inf):
                raise ValueError(f"{key} is outside its supported range")
    return payload
