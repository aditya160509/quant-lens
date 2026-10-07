"""Authoritative supported inputs, validation and output descriptors."""

from __future__ import annotations
import math
import pandas as pd


def number(key, default, minimum=0, maximum=10000, integer=False):
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "type": "integer" if integer else "number",
        "default": default,
        "min": minimum,
        "max": maximum,
        "group": "configuration",
        "help": "Applied by the backend; invalid or unsupported values fail explicitly.",
    }


def field(key, type="json", default=None, options=None):
    out = {
        "key": key,
        "label": key.replace("_", " ").title(),
        "type": type,
        "default": default,
        "group": "configuration",
        "help": "See module DONE.md for estimator assumptions and source limitations.",
    }
    if options is not None:
        out["options"] = [{"value": v, "label": str(v)} for v in options]
    return out


SHARED = [
    field("tickers", "symbols"),
    field("as_of_date", "date"),
    field("start_date", "date"),
    field("end_date", "date"),
    number("max_tickers", 240, 1, 5000, True),
    field(
        "factor",
        "select",
        "momentum_12_1",
        [
            "momentum_12_1",
            "momentum_6_1",
            "low_vol",
            "value_pb",
            "value_ep",
            "quality_roe",
            "profitability",
            "size",
            "growth",
            "investment",
        ],
    ),
    field("factors"),
    field(
        "factor_model",
        "select",
        "ff5_mom",
        ["ff3", "ff5", "ff5_mom", "carhart", "capm"],
    ),
    field("include_aqr", "boolean", False),
    field("aqr_region", "string", "USA"),
    number("window_days", 756, 90, 20000, True),
    number("lookback_days", 756, 90, 20000, True),
    field("instrument_metadata"),
    field("selected_sector", "string"),
    number("snapshot_step", 21, 1, 252, True),
    field("compute_mode", "select", "realtime", ["realtime", "research"]),
]
SPEC = {
    "01": [
        number("alert_percentile", 70, 0, 100),
        number("cheap_percentile", 30, 0, 100),
    ],
    "02": [
        field("benchmark_holdings"),
        field("sector_neutral", "boolean", False),
        field("holdings"),
        field("holdings_upload_id", "string"),
        number("estimation_days", 252, 30, 10000, True),
        field("rebalancing_history"),
    ],
    "03": [
        field("factor_exposures"),
        field(
            "frequency", "select", "daily", ["daily", "weekly", "monthly", "quarterly"]
        ),
    ],
    "04": [
        number("states", 4, 2, 6, True),
        number("vix_threshold", 25, 1, 100),
        field("include_gmm", "boolean", False),
    ],
    "05": [
        field("horizons", "json", [1, 5, 21, 63, 126]),
        number("bootstrap_samples", 200, 20, 1000, True),
    ],
    "06": [],
    "07": [
        number("bin_bootstrap_samples", 200, 20, 1000, True),
        number("rebalance_days", None, 1, 252, True),
        field(
            "refit_frequency",
            "select",
            "monthly",
            ["daily", "weekly", "monthly", "quarterly", "annual"],
        ),
        number("cost_bps", 8, 0, 100),
        number("borrow_bps", 0, 0, 2000),
        field("long_short", "boolean", True),
        field("factor_weights"),
        number("mc_simulations", 100, 10, 1000, True),
        number("mc_block_days", 21, 1, 252, True),
    ],
    "08": [
        field(
            "method",
            "select",
            "ledoit_wolf",
            ["sample", "ewma", "ledoit_wolf", "dcc_ewma"],
        ),
        number("half_life", 63, 1, 1000, True),
        number("stress_vix", 30, 1, 100),
        number("dcc_a", 0.03, 0, 0.2),
        number("dcc_b", 0.94, 0, 0.995),
        field("factor_pair"),
        number("rolling_corr_window", 252, 60, 2000, True),
        field("portfolio_weights"),
    ],
    "09": [
        field("long_short", "boolean", True),
        field("aum_grid"),
        number("aum_points", 20, 2, 100, True),
        number("turnover", 0.35, 0, 2),
        number("explicit_bps", 8, 0, 100),
        number("impact_eta", 0.1, 0, 10),
        number("participation_cap", 0.15, 0.01, 1),
        number("rebalance_days", 21, 1, 252, True),
    ],
    "10": [
        number("risk_aversion", 5, 0.001, 10000),
        field("robust", "boolean", True),
        number("robust_penalty", 0.25, 0, 10),
        field("long_short", "boolean", False),
        field(
            "covariance_method",
            "select",
            "ledoit_wolf",
            ["sample", "ewma", "ledoit_wolf"],
        ),
        field("expected_returns"),
        field("bl_views"),
        number("bl_tau", 0.05, 0.001, 1),
        field("alpha_signal"),
        field("risk_loadings"),
        number("net_exposure", 1, -2, 2),
        number("gross_limit", 2, 0.01, 10),
        number("position_limit", 1, 0.001, 2),
        field("current_weights"),
        field("benchmark_weights"),
        number("turnover_limit", None, 0, 10),
        number("tracking_error_limit", None, 0, 10),
    ],
    "11": [
        field("exposures"),
        field("shocks"),
        field("scenarios"),
        number("loss_threshold", 0.15, 0.001, 1),
        number("var_lags", 2, 1, 21, True),
        number("var_bootstrap_samples", 50, 20, 500, True),
    ],
    "12": [field("comparison_factors", "json", [])],
    "13": [
        number("recent_observations", 21, 5, 252, True),
        number("baseline_observations", 63, 20, 504, True),
        number("ic_horizon", 21, 1, 252, True),
        number("ic_drift_threshold", -1.5, -10, 10),
    ],
    "14": [
        field("include_sections"),
        field("section_order"),
        field("fund_name", "string", "Factors V2 Report"),
        field("logo_upload_id", "string"),
        field("contact_info", "string"),
        field("disclaimer", "string"),
        field("custom_narrative", "string"),
        field("fund_disclosures", "string"),
        field("report_version", "string", "v1.0"),
        number("max_pdf_pages", 20, 1, 100, True),
        field("feature_payloads"),
    ],
}


COMMON = {"as_of_date", "end_date", "compute_mode"}
STOCK = {
    "tickers",
    "max_tickers",
    "factor",
    "factors",
    "instrument_metadata",
    "selected_sector",
    "snapshot_step",
    "window_days",
    "start_date",
}
RETURNS = {
    "factor_model",
    "include_aqr",
    "aqr_region",
    "window_days",
    "start_date",
    "return_factors",
}
RELEVANT = {
    "01": STOCK,
    "02": (STOCK - {"factor", "window_days", "start_date", "snapshot_step"})
    | RETURNS - {"window_days", "start_date"},
    "03": RETURNS,
    "04": RETURNS,
    "05": STOCK - {"factors"},
    "06": STOCK | RETURNS,
    "07": STOCK,
    "08": RETURNS,
    "09": STOCK - {"factors"},
    "10": RETURNS,
    "11": RETURNS,
    "12": STOCK | RETURNS,
    "13": STOCK,
    "14": STOCK | RETURNS,
}
SHARED.append(field("return_factors"))


def inputs(fid):
    return [s for s in SHARED if s["key"] in COMMON | RELEVANT[fid]] + SPEC[fid]


def finite_inputs(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("All numeric inputs must be finite")
    if isinstance(value, dict):
        for child in value.values():
            finite_inputs(child)
    elif isinstance(value, list):
        for child in value:
            finite_inputs(child)


def validate(fid, payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    finite_inputs(payload)
    declarations = {s["key"]: s for s in inputs(fid)}
    unknown = set(payload) - set(declarations)
    if unknown:
        raise ValueError("Unsupported inputs: " + ", ".join(sorted(unknown)))
    out = {
        s["key"]: s["default"]
        for s in declarations.values()
        if s.get("default") is not None
    }
    out.update({k: v for k, v in payload.items() if v is not None and v != ""})
    if fid == "07" and "rebalance_days" in payload and "refit_frequency" in payload:
        raise ValueError("Supply either rebalance_days or refit_frequency, not both")
    # One cutoff across every source; the end date cannot override an earlier as-of date.
    for key, value in out.items():
        spec = declarations[key]
        kind = spec["type"]
        if kind in {"integer", "number"}:
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                x = float(value)
            except (ValueError, TypeError):
                raise ValueError(f"{key} must be numeric")
            if (
                not math.isfinite(x)
                or x < spec["min"]
                or x > spec["max"]
                or (kind == "integer" and x != int(x))
            ):
                raise ValueError(f"{key} outside supported range")
            out[key] = int(x) if kind == "integer" else x
        elif kind == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")
        elif kind == "select" and value not in [o["value"] for o in spec["options"]]:
            raise ValueError(f"Unsupported {key}: {value}")
        elif kind == "string" and not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        elif kind == "date":
            d = pd.Timestamp(value)
            if pd.isna(d):
                raise ValueError(f"Invalid {key}")
            out[key] = str(d.date())
    if out.get("end_date") and out.get("as_of_date"):
        out["as_of_date"] = min(out["as_of_date"], out["end_date"])
    if (
        out.get("start_date")
        and out.get("as_of_date")
        and out["start_date"] > out["as_of_date"]
    ):
        raise ValueError("start_date is after as_of_date")
    if out.get("dcc_a", 0) + out.get("dcc_b", 0) >= 1:
        raise ValueError("DCC parameters must satisfy a+b<1")
    if fid == "05" and (
        not isinstance(out["horizons"], list)
        or not out["horizons"]
        or any(not isinstance(h, int) or h < 1 or h > 1000 for h in out["horizons"])
    ):
        raise ValueError("horizons must be a nonempty positive integer list")
    if out.get("factors") is not None and (
        not isinstance(out["factors"], list) or not out["factors"]
    ):
        raise ValueError("factors must be a nonempty list")
    for key in (
        "factor_exposures",
        "expected_returns",
        "factor_weights",
        "shocks",
        "exposures",
        "portfolio_weights",
    ):
        if key in out:
            value = out[key]
            if (
                not isinstance(value, dict)
                or not value
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    for v in value.values()
                )
            ):
                raise ValueError(
                    f"{key} requires a nonempty factor-to-finite-number object"
                )
    metadata = out.get("instrument_metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("instrument_metadata must be an object keyed by ticker")
    for symbol, item in metadata.items():
        if not isinstance(item, dict) or set(item) - {
            "quote_currency",
            "financial_currency",
            "quoted_units_per_ordinary_share",
        }:
            raise ValueError("Unsupported instrument metadata")
        unit = item.get("quoted_units_per_ordinary_share", 1)
        if not isinstance(unit, (int, float)) or not math.isfinite(unit) or unit <= 0:
            raise ValueError("Share units must be positive and finite")
    return out


def outputs(fid):
    entries = [
        (source, key) for source, keys in OUTPUT_KEYS[fid].items() for key in keys
    ]
    return [
        {
            "key": key,
            "source": source,
            "render": (
                "download"
                if key == "pdf_base64"
                else "heatmap"
                if "correlation" in key or "covariance" in key
                else "line"
                if any(
                    v in key
                    for v in (
                        "series",
                        "curve",
                        "drift",
                        "probability",
                        "equity",
                        "drawdown",
                    )
                )
                else "table"
            ),
            "primary": index == 0,
            "label": key.replace("_", " ").title(),
        }
        for index, (source, key) in enumerate(entries)
    ]


OUTPUT_KEYS = {
    "01": {
        "charts": [
            "gauge_panel",
            "percentile_series",
            "spread_percentile_timeseries",
            "valuation_correlation",
            "valuation_correlation_matrix",
            "crisis_anchors",
            "expected_return_regression",
        ],
        "tables": [
            "valuation_spreads",
            "sector_contribution",
            "cross_sector_table",
            "crisis_anchor_percentiles",
            "crisis_anchor_table",
            "valuation_spread_detail",
            "alert_feed",
        ],
    },
    "02": {
        "charts": [
            "exposure_bar",
            "static_exposure_heatmap",
            "rolling_exposure_snapshots",
        ],
        "tables": [
            "characteristic_exposures",
            "return_exposures",
            "portfolio_return_exposures",
            "active_characteristic_exposures",
        ],
    },
    "03": {
        "charts": ["waterfall", "cumulative_contribution"],
        "tables": ["factor_contribution", "attribution_reconciliation"],
    },
    "04": {
        "charts": ["hmm_probability", "gmm_probability", "current_regime"],
        "tables": ["transition_matrix", "conditional_returns", "observed_market_rules"],
    },
    "05": {
        "charts": ["ic_decay_curve", "decay_model_fits"],
        "tables": ["ic_by_horizon", "decay_models", "half_life_confidence"],
    },
    "06": {
        "charts": ["crowding_timeseries"],
        "tables": ["crowding_metrics", "bid_ask_detail"],
    },
    "07": {
        "charts": [
            "equity_curve",
            "drawdown",
            "monte_carlo_bands",
            "quintile_monotonicity",
            "decile_monotonicity",
        ],
        "tables": [
            "statistics",
            "transaction_costs",
            "turnover_analysis",
            "gross_vs_net_by_year",
        ],
    },
    "08": {
        "charts": [
            "correlation_heatmap",
            "dcc_correlation_heatmap",
            "dcc_average_correlation",
            "normal_correlation",
            "crisis_correlation",
            "correlation_amplification",
            "normal_vs_crisis",
            "crisis_preset_comparison",
            "rolling_pair_correlation",
            "portfolio_risk_decomposition",
            "eigenvalues",
            "factor_volatility",
        ],
        "tables": [
            "annualized_covariance",
            "dcc_annualized_covariance",
            "volatility",
            "minimum_variance_factor_combination",
            "covariance_stability",
            "portfolio_risk_decomposition",
            "portfolio_pairwise_risk_decomposition",
            "matrix_validation",
            "crisis_preset_comparison",
        ],
    },
    "09": {"charts": ["capacity_curve"], "tables": ["slippage_by_aum", "sensitivity"]},
    "10": {
        "charts": ["efficient_frontier", "optimal_weights"],
        "tables": [
            "optimal_factor_allocation",
            "constraint_binding",
            "fap_diagnostic",
            "robust_vs_standard",
            "black_litterman_posterior",
        ],
    },
    "11": {
        "charts": ["scenario_waterfall", "contagion_irf", "irf_confidence_bands"],
        "tables": [
            "factor_shocks",
            "reverse_stress",
            "reverse_stress_summary",
            "historical_analog",
            "hedging_recommendation",
            "stress_var_cvar",
            "multi_scenario",
            "var_lag_selection",
        ],
    },
    "12": {
        "charts": ["dna_radar", "correlation_dna"],
        "tables": [
            "dna_vector",
            "purity_regression",
            "concentration",
            "comparison_factors",
        ],
    },
    "13": {
        "charts": ["ic_drift"],
        "tables": [
            "signal_health",
            "structural_break_diagnostic",
            "alert_log",
            "alert_policy",
        ],
    },
    "14": {"tables": ["sections", "aima_ddq_cross_reference"]},
}
