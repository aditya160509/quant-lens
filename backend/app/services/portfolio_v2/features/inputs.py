"""Backend-owned typed controls, defaults and output declarations."""

import json
import math
import pandas as pd

COMMON = {
    "tickers": (["SPY", "QQQ", "IWM", "EFA", "EEM"], "symbols"),
    "weights": (None, "object"),
    "lookback_days": (756, "integer"),
    "as_of_date": (None, "date"),
    "frequency": ("daily", "select"),
}
CONSTRUCTION = {
    "objective": ("global_min_variance", "select"),
    "covariance_estimator": ("ledoit_wolf", "select"),
    "expected_return_estimator": ("shrinkage", "select"),
    "position_structure": ("long_only", "select"),
    "min_weights": (None, "object_or_number"),
    "max_weights": (None, "object_or_number"),
    "sector_max_weights": ({}, "object"),
    "max_turnover": (None, "number"),
    "current_weights": (None, "object"),
    "leverage_cap": (1.0, "number"),
    "short_symbols": (None, "symbols"),
    "risk_aversion": (2.5, "number"),
    "risk_free_rate": (0.0, "number"),
    "risk_shares": ({}, "object"),
    "kelly_fraction": (1.0, "number"),
    "market_weights": (None, "object"),
    "views": (None, "object"),
    "bl_tau": (0.05, "number"),
    "var_confidence": (0.95, "number"),
}
EXTRA = {
    "01": {
        **CONSTRUCTION,
        "frontier_points": (100, "integer"),
        "transaction_cost_bps": (5.0, "number"),
        "portfolio_nav": (1000000.0, "number"),
    },
    "02": {
        **CONSTRUCTION,
        "rebalance_frequency": ("monthly", "select"),
        "rebalance_days": (None, "integer"),
        "walk_forward_window": (252, "integer"),
        "transaction_cost_bps": (5.0, "number"),
        "cash_rate_annual": (0.0, "number"),
        "benchmark": ("equal_weight", "text"),
        "variant_objectives": (
            ["global_min_variance", "max_sharpe", "risk_parity"],
            "list",
        ),
        "parameter_trials": (None, "integer"),
        "pbo_partitions": (8, "integer"),
        "var_simulations": (10000, "integer"),
        "drift_tolerance": (0.05, "number"),
    },
    "03": {
        "benchmark": ("equal_weight", "text"),
        "benchmark_weights": (None, "object"),
        "factor_model": ("FF5+MOM", "select"),
        "bootstrap_draws": (1000, "integer"),
        "factor_returns": (None, "records"),
    },
    "04": {
        "monte_carlo_paths": (1000, "integer"),
        "horizon_days": (21, "integer"),
        "bootstrap_block_length": (None, "integer"),
        "loss_threshold": (0.15, "number"),
        "hypothetical_shocks": ({}, "object"),
        "crisis_correlation": (0.75, "number"),
    },
    "05": {
        "macro_factors": (["vixcls", "yc_slope_10y_2y", "bamlh0a0hym2"], "list"),
        "rolling_window": (126, "integer"),
        "target_exposures": ({}, "object"),
        "tolerance_bands": ({}, "object"),
        "risk_budget_limits": ({}, "object"),
        "factor_returns": (None, "records"),
    },
    "06": {
        "regime_count": (3, "integer"),
        "regime_min_train": (126, "integer"),
        "regime_refit_interval": (21, "integer"),
        "regime_model": ("hmm", "select"),
        "transition_structure": ("homogeneous", "select"),
        "objective": ("global_min_variance", "select"),
    },
    "07": {
        "portfolio_nav": (1000000.0, "number"),
        "participation_rate": (0.2, "number"),
        "adv_window": (60, "integer"),
        "liquidation_urgency": ("orderly", "select"),
        "stress_volume_multiplier": (0.3, "number"),
    },
    "08": {
        "correlation_window": (126, "integer"),
        "correlation_threshold": (0.6, "number"),
        "crisis_start": ("2020-02-15", "date"),
        "crisis_end": ("2020-04-30", "date"),
        "bond_benchmark": ("AGG", "text"),
        "correlation_dynamics": ("rolling", "select"),
    },
    "09": {
        "factor_taxonomy": ("mechanical", "select"),
        "max_horizon": (63, "integer"),
        "signal_scores": (None, "records"),
        "bootstrap_draws": (200, "integer"),
        "signal_window": (21, "integer"),
        "publication_date": (None, "date"),
    },
    "10": {
        "covariance_estimator": ("ledoit_wolf", "select"),
        "expected_return_estimator": ("shrinkage", "select"),
        "kelly_fraction": (0.5, "number"),
        "leverage_cap": (1.0, "number"),
        "transaction_cost_bps": (10.0, "number"),
        "rebalances_per_year": (12, "integer"),
    },
    "11": {
        "portfolio_nav": (1000000.0, "number"),
        "target_weights": (None, "object"),
        "time_horizon": (5, "integer"),
        "risk_aversion": (0.1, "number"),
        "temporary_impact_coefficient": (None, "object_or_number"),
        "permanent_impact_coefficient": (0.0, "object_or_number"),
        "delay_returns": ({}, "object"),
        "opportunity_cost_bps": (0.0, "number"),
    },
    "12": {
        "portfolio_nav": (1000000.0, "number"),
        "peer_portfolios": (None, "object"),
        "peer_navs": (None, "object"),
        "liquidation_fraction": (0.2, "number"),
        "market_depth_coefficient": (None, "number"),
        "counterparty_exposures": (None, "object"),
        "initial_distress": (None, "object"),
    },
    "13": {
        "strategy_returns": (None, "records"),
        "strategy_trades": (None, "records"),
        "vol_target": (0.1, "number"),
        "kill_switch_drawdown": (0.15, "number"),
        "correlation_constraint": (0.8, "number"),
        "capacity_limits": (None, "object"),
        "risk_budgets": (None, "object"),
        "portfolio_nav": (1000000.0, "number"),
        "transaction_cost_bps": (10.0, "number"),
        "allocation_rule": ("inverse_vol", "select"),
        "rebalance_days": (21, "integer"),
        "training_window": (126, "integer"),
    },
}
OPTIONS = {
    "correlation_dynamics": ["rolling", "dcc_garch"],
    "frequency": ["daily", "weekly", "monthly"],
    "covariance_estimator": [
        "sample",
        "ledoit_wolf",
        "oas",
        "ewma",
        "constant_correlation",
        "eigenvalue_shrinkage",
        "dcc_garch",
        "factor_structured",
        "gerber",
    ],
    "expected_return_estimator": ["sample", "shrinkage"],
    "objective": [
        "markowitz",
        "global_min_variance",
        "max_sharpe",
        "inverse_vol",
        "risk_parity",
        "max_diversification",
        "hrp",
        "growth_optimal",
        "black_litterman",
        "cvar_min",
    ],
    "position_structure": ["long_only", "130_30", "market_neutral", "unconstrained"],
    "rebalance_frequency": [
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "semiannual",
        "annual",
        "threshold",
    ],
    "factor_model": ["FF3", "FF5", "FF5+MOM"],
    "regime_model": ["hmm", "hamilton", "vix"],
    "transition_structure": ["homogeneous", "nonhomogeneous"],
    "liquidation_urgency": ["orderly", "distressed", "crisis"],
    "factor_taxonomy": ["mechanical", "judgment"],
    "allocation_rule": [
        "fixed",
        "inverse_vol",
        "sharpe_momentum",
        "kelly",
        "regime_conditional",
    ],
}
BOUNDS = {
    "lookback_days": (30, 20000),
    "frontier_points": (2, 100),
    "walk_forward_window": (30, 10000),
    "rebalance_days": (1, 10000),
    "pbo_partitions": (2, 16),
    "parameter_trials": (1, 10000),
    "transaction_cost_bps": (0, 2000),
    "var_confidence": (0.5, 0.999),
    "var_simulations": (1000, 50000),
    "portfolio_nav": (1, 1e12),
    "participation_rate": (0.001, 1),
    "adv_window": (2, 2520),
    "monte_carlo_paths": (100, 10000),
    "horizon_days": (1, 2520),
    "time_horizon": (1, 252),
    "bootstrap_draws": (20, 10000),
    "rolling_window": (30, 2520),
    "correlation_window": (30, 2520),
    "regime_count": (2, 8),
    "regime_min_train": (60, 2520),
    "regime_refit_interval": (1, 252),
    "max_horizon": (1, 252),
    "leverage_cap": (0.01, 10),
    "kelly_fraction": (0.05, 1),
    "bl_tau": (0.001, 1),
    "liquidation_fraction": (0.001, 1),
    "vol_target": (0.001, 1),
    "kill_switch_drawdown": (0.01, 0.9),
    "correlation_constraint": (0, 1),
    "training_window": (30, 2520),
}


def inputs_for(fid):
    common = {
        key: value
        for key, value in COMMON.items()
        if fid != "13" or key not in {"tickers", "weights"}
    }
    definitions = {**common, **EXTRA[fid], "upload_id": (None, "text")}
    return [
        {
            "key": key,
            "label": key.replace("_", " ").title(),
            "type": kind,
            "group": "Data" if key in COMMON or key == "upload_id" else "Model",
            "default": value,
            "options": ["daily"]
            if key == "frequency" and fid in {"04", "07", "11", "12"}
            else OPTIONS.get(key, []),
            "min": BOUNDS.get(key, (None, None))[0],
            "max": BOUNDS.get(key, (None, None))[1],
            "help": "Exact observed symbols; no index substitutes"
            if key == "tickers"
            else "Signed exposures preserved without normalization"
            if key == "weights"
            else "Cut off all sources before selecting the estimation window"
            if key == "as_of_date"
            else "Declared assumption"
            if key
            in {
                "risk_free_rate",
                "market_depth_coefficient",
                "temporary_impact_coefficient",
                "permanent_impact_coefficient",
            }
            else key.replace("_", " "),
        }
        for key, (value, kind) in definitions.items()
    ]


def coerce(value, definition):
    if value is None:
        return None
    kind = definition["type"]
    key = definition["key"]
    if kind in {"object", "records", "object_or_number"} and isinstance(value, str):
        value = json.loads(value)
    if kind in {"symbols", "list"} and isinstance(value, str):
        value = [s.strip() for s in value.replace(";", ",").split(",") if s.strip()]
    if kind in {"symbols", "list", "records"} and not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    if kind == "object" and not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    if kind == "object_or_number" and not isinstance(value, (dict, int, float)):
        raise ValueError(f"{key} must be an object or number")
    if kind in {"integer", "number"}:
        if isinstance(value, bool):
            raise ValueError(f"{key} cannot be boolean")
        number = float(value)
        if not math.isfinite(number) or kind == "integer" and number != int(number):
            raise ValueError(f"Invalid {key}")
        value = int(number) if kind == "integer" else number
        low, high = BOUNDS.get(key, (None, None))
        if low is not None and not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
    if kind == "date":
        date = pd.Timestamp(value)
        if pd.isna(date) or date.tzinfo is not None:
            raise ValueError(f"Invalid {key}")
        value = date.strftime("%Y-%m-%d")
    if definition["options"] and value not in definition["options"]:
        raise ValueError(f"Unknown {key}: {value}")

    def finite_nested(item):
        if isinstance(item, (int, float)) and not math.isfinite(item):
            raise ValueError(f"{key} contains a nonfinite value")
        if isinstance(item, dict):
            for nested in item.values():
                finite_nested(nested)
        if isinstance(item, list):
            for nested in item:
                finite_nested(nested)

    finite_nested(value)
    return value


def output(key, source="tables", render="table", primary=False):
    return {
        "key": key,
        "source": source,
        "render": render,
        "render_hint": render,
        "label": key.replace("_", " ").title(),
        "primary": primary,
    }
