"""Shared output and computation contract metadata for Factors V2 features."""

FEATURE_OUTPUT_KEYS = [
    'feature_id',
    'status',
    'summary_cards',
    'charts',
    'tables',
    'alerts',
    'meta',
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
        "title": "Factor Valuation Spread Monitor",
        "inputs": ["factor", "factors", "lookback_days", "max_tickers", "alert_percentile", "factor_model"],
        "outputs": ["valuation gauge summary", "spread percentile time series", "valuation correlation matrix", "sector spread contribution table", "alerts"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 1",
    },
    "02": {
        "title": "Factor Exposure Decomposition",
        "inputs": ["holdings", "factors", "benchmark", "estimation_days", "factor_model", "max_tickers", "compute_mode", "mandate_factors", "rebalancing_history"],
        "outputs": ["portfolio-constituent characteristic exposures", "return-based exposures", "active benchmark exposure", "divergence flags", "static holdings heatmap", "unintended exposure detector", "factor exposure budget", "Research Mode animation export metadata"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 2",
        "realtime_constraint": "full-universe characteristic z-scores above 1000 names must come from nightly cache; realtime computes portfolio constituents only",
    },
    "03": {
        "title": "Factor Return Attribution",
        "inputs": ["factor_exposures", "window_days", "factor_model", "frequency", "benchmark", "compute_mode"],
        "outputs": ["factor contribution table", "waterfall data", "component IR", "dynamic sector-neutral Brinson-Fachler table", "carryover proxy"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 3",
        "realtime_constraint": "monthly full-history attribution by default; daily granularity is trailing 12 months unless Research Mode",
    },
    "04": {
        "title": "Probabilistic Regime Analysis",
        "inputs": ["states", "vix_threshold", "window_days", "factor_model", "include_gmm", "compute_mode"],
        "outputs": ["rules probabilities", "HMM probabilities", "cached/toggled GMM probabilities", "log-space composite probabilities", "conditional factor returns", "transition matrix"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 4",
        "realtime_constraint": "HMM primary and macro rules secondary in realtime; GMM rolling covariance is weekly cached/toggle-only",
    },
    "05": {
        "title": "Alpha Decay and Half-Life",
        "inputs": ["factor", "horizons", "window_days", "factor_model", "selected_sector", "compute_mode"],
        "outputs": ["full-universe IC decay curve", "decay model fits", "half-life confidence interval", "ICIR", "rolling half-life", "optional sector drill-down"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 5",
        "realtime_constraint": "sector-level decay is selected-sector drill-down only, not all-sector realtime grid",
    },
    "06": {
        "title": "Factor Crowding Monitor",
        "inputs": ["factor", "factors", "lookback_days", "alert_threshold", "max_tickers", "factor_model", "compute_mode"],
        "outputs": ["four-metric realtime crowding composite", "metric breakdown", "crowding time series", "Bayesian crash probability", "deleveraging risk", "cross-factor crowding league", "crowding-forward-return scatter"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 6",
        "realtime_constraint": "composite uses valuation spread, return autocorrelation, HHI, and local Roll/Amihud spread proxy; short-interest and institutional-ownership feeds are not claimed",
    },
    "07": {
        "title": "Factor Backtesting Engine",
        "inputs": ["factor", "window_days", "turnover", "cost_bps", "factor_model", "refit_frequency", "mc_simulations", "include_timing_cost", "compute_mode"],
        "outputs": ["gross/net equity curves", "drawdown", "statistics", "trade-level transaction cost decomposition", "realtime compute caps"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 7",
        "realtime_constraint": "weekly refit default; daily refit and >250 Monte Carlo simulations require Research Mode",
    },
    "08": {
        "title": "Factor Covariance Matrix",
        "inputs": ["method", "half_life", "window_days", "stress_vix", "factor_model", "factor_pair", "portfolio_weights", "optimal_weights_from_f10", "compute_mode"],
        "outputs": ["correlation heatmap", "covariance matrix", "volatility table", "eigenvalues", "condition number", "normal/crisis/delta matrices", "minimum variance factor combination", "rolling pair correlation", "optional portfolio risk decomposition", "DCC when allowed"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 8",
        "realtime_constraint": "DCC-GARCH is realtime only for <=15 factors; larger universes default to Ledoit-Wolf unless Research Mode",
    },
    "09": {
        "title": "Strategy Capacity Analyzer",
        "inputs": ["factor", "aum_grid", "turnover", "explicit_bps", "kyle_lambda", "max_tickers", "compute_mode"],
        "outputs": ["capacity curve", "capacity ceiling", "slippage by AUM", "time to liquidate", "allocator memo"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 9",
        "realtime_constraint": "default AUM grid is 20 log-spaced points; 50 points requires Research Mode",
    },
    "10": {
        "title": "Factor-Based Portfolio Optimizer",
        "inputs": ["window_days", "risk_aversion", "robust", "robust_penalty", "long_short", "covariance_method", "alpha_signal", "cardinality", "bl_views", "bl_tau", "compute_mode"],
        "outputs": ["optimal factor allocation", "efficient frontier", "risk contributions", "constraint report", "FAP diagnostic", "greedy cardinality post-processing", "structured factor-level Black-Litterman posterior"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 10",
        "realtime_constraint": "no integer programming live; N>100 realtime robust optimization uses expected-return shrinkage approximation",
    },
    "11": {
        "title": "Stress Testing and Reverse Stress Testing",
        "inputs": ["window_days", "exposures", "shocks", "loss_threshold", "factor_model", "var_lags", "var_bootstrap_samples", "compute_mode"],
        "outputs": ["scenario waterfall", "reverse stress vector", "scenario PnL", "VAR contagion IRF", "stress alerts"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 11",
        "realtime_constraint": "VAR capped at 5 lags and 200 bootstrap reps in realtime; 21 lags/500 reps require Research Mode",
    },
    "12": {
        "title": "Factor DNA Attribution",
        "inputs": ["factor", "analysis_depth", "window_days", "max_tickers", "factor_model"],
        "outputs": ["DNA radar", "classifier probabilities", "return anatomy", "purity regression", "static sector DNA snapshot", "regime DNA bar", "latest correlation DNA bar", "classifier training audit", "diagnostic alerts"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 12",
        "realtime_constraint": "CART classifier uses deterministic 100+ sample academic archetype library",
    },
    "13": {
        "title": "Live Signal Monitoring Dashboard",
        "inputs": ["factor", "window_days", "ic_drift_threshold", "factor_model"],
        "outputs": ["signal health score", "IC drift series", "rolling CUSUM structural break", "crowding velocity", "alert log", "portfolio-weighted health"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 13",
        "realtime_constraint": "single rolling CUSUM test in realtime; Chow diagnostic is weekly cached metadata",
    },
    "14": {
        "title": "Allocator Transparency Report Generator",
        "inputs": ["report_type", "fund_name", "date_range", "portfolio", "factor_model", "max_tickers", "max_pdf_pages", "compute_mode"],
        "outputs": ["report sections", "HTML report", "PDF bytes base64", "AIMA DDQ cross-reference", "audit trail"],
        "math_source": "FACTORS_COMPUTATION_DOCUMENT.md Feature 14",
        "realtime_constraint": "PDF rendering capped at 20 pages by default; longer reports require Research Mode/async",
    },
}
