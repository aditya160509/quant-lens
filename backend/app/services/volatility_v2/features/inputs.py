"""Shared input descriptions and strict coercion for declared feature controls."""

from __future__ import annotations
import json
import math

BOUNDS = {
    "annualization": (1, 366),
    "lookback_days": (2, 20000),
    "rolling_window": (2, 10000),
    "min_train": (120, 10000),
    "refit_interval": (1, 10000),
    "evaluation_days": (30, 10000),
    "states": (2, 4),
    "hmm_restarts": (1, 20),
    "simulations": (100, 10000),
    "bootstrap_reps": (20, 2000),
    "irf_bootstrap_reps": (20, 2000),
    "midas_k": (2, 120),
    "mc_paths": (100, 100000),
    "aum": (1, 1e13),
    "var_coverage": (0.5, 0.9999),
    "confidence_level": (0.5, 0.999),
    "cor_quantile": (0.01, 0.99),
    "transition_alert_threshold": (0, 1),
    "gross_exposure_cap": (0.01, 100),
    "explicit_bps": (0, 10000),
    "market_impact_gamma": (0, 100),
    "nw_bandwidth": (0, 252),
    "seed": (0, 2147483647),
}
OPTIONS = {
    "annualization": [252, 365],
    "states": [2, 3, 4],
    "estimator": ["cc", "parkinson", "garman_klass", "rogers_satchell", "yang_zhang"],
    "range_correlation_method": ["pearson", "uncentered_cosine"],
    "var_weighting": ["ols", "ew"],
    "dynamics": ["dcc", "dcc_midas"],
    "forecast_source": ["dcc", "garch", "ewma"],
    "target_mode": ["fixed", "regime", "kelly"],
    "cost_model": ["flat", "almgren_chriss_temporary"],
    "rebalance_trigger": ["daily", "weekly", "monthly", "signal"],
    "display_mode": ["raw", "variance", "zscore"],
    "models": ["GARCH", "EGARCH", "GJR-GARCH", "APARCH", "FIGARCH"],
    "distributions": ["Gaussian", "Student-t", "GED", "Skew-t"],
    "physical_model": ["GARCH", "EGARCH", "GJR-GARCH", "APARCH", "FIGARCH"],
    "physical_distribution": ["Gaussian", "Student-t", "GED", "Skew-t"],
    "garch_model": ["GARCH", "EGARCH", "GJR-GARCH", "APARCH", "FIGARCH"],
    "garch_distribution": ["Gaussian", "Student-t", "GED", "Skew-t"],
}
LISTS = {
    "assets",
    "models",
    "distributions",
    "horizons",
    "return_horizons",
    "irf_horizons",
    "factor_pair",
}
OBJECTS = {
    "weights",
    "risk_budgets",
    "quote_currencies",
    "volume_units",
    "regime_targets",
    "vol_shocks",
    "mean_shocks",
}
HELP = {
    "assets": "Exact symbols in the local observed daily universe. Unknown symbols fail.",
    "asset": "Primary asset, which must belong to the requested asset list.",
    "as_of_date": "Use only observations dated on or before this date, before truncating history.",
    "lookback_days": "Number of observed sessions per asset, not calendar days.",
    "annualization": "Observed-session variance multiplier. Choose explicitly for the instrument calendar.",
    "weights": "JSON or SYMBOL:value exposures. Signed weights are preserved, never silently normalized.",
    "quote_currencies": "Map exact assets to native quote currencies for observed USD conversion.",
    "volume_units": "Map assets to shares, base_units or quote_currency for USD ADV.",
    "iv_upload_id": "Content-addressed id returned by the validated observed-IV upload route.",
    "hourly_timezone": "Timezone of the stored naive hourly timestamps; required for hourly variation.",
    "session_timezone": "Timezone defining hourly observation dates; required for hourly variation.",
    "min_train": "Minimum past observations before producing held-out forecasts.",
    "refit_interval": "Observed sessions between expanding, past-only model refits.",
    "risk_budgets": "Positive fractions by asset, summing to one.",
    "regime_targets": "Annual volatility preferences for each actual fitted state, not estimated optimum targets.",
    "market_impact_gamma": "Assumed one-day linear temporary-impact coefficient, not a measured calibration.",
    "cash_rate_annual": "Declared annual cash/borrowing rate assumption.",
    "confidence_level": "Conditional confidence level; excludes model-selection uncertainty.",
    "include_hourly_variation": "Use exact observed consecutive hourly closes; no tick-noise correction or jump significance.",
}


def field(key, default=None, kind=None, group="Model", options=None, help=None):
    if key in {
        "gross_exposure_cap",
        "cash_rate_annual",
        "explicit_bps",
        "breach_threshold",
        "sjm_jump_penalty",
    }:
        kind = "number"
    kind = kind or (
        "boolean"
        if isinstance(default, bool)
        else "integer"
        if isinstance(default, int)
        else "number"
        if isinstance(default, float)
        else "symbols"
        if key == "assets"
        else "list"
        if key in LISTS
        else "object"
        if key in OBJECTS
        else "date"
        if key == "as_of_date"
        else "text"
    )
    result = {
        "key": key,
        "label": key.replace("_", " ").capitalize(),
        "type": kind,
        "group": group,
        "default": default,
        "help": help
        or HELP.get(
            key,
            f"{key.replace('_', ' ').capitalize()} used by the selected estimator; unavailable data are never substituted.",
        ),
    }
    if key in BOUNDS:
        result["min"], result["max"] = BOUNDS[key]
    elif kind in {"integer", "number"} and key not in {"cash_rate_annual"}:
        result["min"] = (
            0
            if key in {"sjm_jump_penalty", "breach_threshold", "rebalance_threshold"}
            else 1e-12
        )
    if options is not None or key in OPTIONS:
        result["options"] = options if options is not None else OPTIONS[key]
    return result


def coerce(value, definition):
    kind, key = definition["type"], definition["key"]
    if value is None:
        if key == "assets" or definition["default"] is not None:
            raise ValueError(f"{key} cannot be null")
        return None
    if kind in {"integer", "number"}:
        if isinstance(value, bool):
            raise ValueError(f"{key} must be numeric, not boolean")
        number = float(value)
        if not math.isfinite(number) or (kind == "integer" and number != int(number)):
            raise ValueError(f"{key} must be a finite {kind}")
        value = int(number) if kind == "integer" else number
        if value < definition.get("min", -math.inf) or value > definition.get(
            "max", math.inf
        ):
            raise ValueError(f"{key} is outside declared bounds")
    elif kind == "boolean":
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            value = value.lower() == "true"
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be boolean")
    elif kind in {"symbols", "list"}:
        if isinstance(value, str):
            value = [
                part.strip()
                for part in value.replace(";", ",").split(",")
                if part.strip()
            ]
        if not isinstance(value, (list, tuple)) or not value:
            raise ValueError(f"{key} must be a nonempty list")
        value = list(value)
        if "horizon" in key:
            numbers = [float(v) for v in value]
            if any(
                not math.isfinite(v) or v != int(v) or not 1 <= v <= 252
                for v in numbers
            ):
                raise ValueError(f"{key} requires integer horizons from 1 to 252")
            value = list(dict.fromkeys(int(v) for v in numbers))
    elif kind == "object":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = dict(part.strip().split(":", 1) for part in value.split(","))
        if not isinstance(value, dict):
            raise ValueError(f"{key} must be a mapping")
    elif kind in {"text", "date"} and not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    options = definition.get("options")
    if options and (
        any(v not in options for v in value) if kind == "list" else value not in options
    ):
        raise ValueError(f"{key} must use declared options: {options}")
    return value
