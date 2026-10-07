"""Feature identities; executable descriptors live in features.inputs."""

FEATURE_OUTPUT_KEYS = [
    "feature_id",
    "status",
    "summary_cards",
    "charts",
    "tables",
    "alerts",
    "meta",
]
STANDARD_OUTPUT_SCHEMA = {
    "feature_id": "feature_XX",
    "status": "ok|warning|error|partial",
    "summary_cards": [],
    "charts": {},
    "tables": {},
    "alerts": [],
    "meta": {},
}
FEATURE_MODULES = {
    "01": "factor_valuation_spread_monitor",
    "02": "factor_exposure_decomposition",
    "03": "factor_return_attribution",
    "04": "factor_timing_probabilistic_regime_analysis",
    "05": "alpha_decay_half_life_analysis",
    "06": "factor_crowding_monitor",
    "07": "factor_backtesting_engine",
    "08": "factor_covariance_risk_forecasting",
    "09": "strategy_capacity_analyzer",
    "10": "factor_based_portfolio_optimizer",
    "11": "factor_stress_testing",
    "12": "factor_dna_attribution",
    "13": "live_signal_monitoring_dashboard",
    "14": "allocator_transparency_report_generator",
}
FEATURE_CONTRACTS = {
    "01": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 1",
        "title": "Factor Valuation Spread Monitor",
    },
    "02": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 2",
        "title": "Factor Exposure Decomposition",
    },
    "03": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 3",
        "title": "Factor Return Attribution",
    },
    "04": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 4",
        "title": "Probabilistic Regime Analysis",
    },
    "05": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 5",
        "title": "Alpha Decay and Half-Life",
    },
    "06": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 6",
        "title": "Factor Crowding Monitor",
    },
    "07": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 7",
        "title": "Factor Backtesting Engine",
    },
    "08": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 8",
        "title": "Factor Covariance Matrix",
    },
    "09": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 9",
        "title": "Strategy Capacity Analyzer",
    },
    "10": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 10",
        "title": "Factor-Based Portfolio Optimizer",
    },
    "11": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 11",
        "title": "Stress Testing and Reverse Stress Testing",
    },
    "12": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 12",
        "title": "Factor DNA Attribution",
    },
    "13": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 13",
        "title": "Live Signal Monitoring Dashboard",
    },
    "14": {
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 14",
        "title": "Allocator Transparency Report Generator",
    },
}
