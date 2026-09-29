// Generated from backend/app/services/ml_v2 feature contracts. Keep keys aligned with Python outputs.

export const ML_V2_FEATURES = [
  {
    "id": "01",
    "slug": "feature-01",
    "title": "Purged K-Fold and Combinatorial Purged Cross-Validation Engine",
    "category": "A",
    "shortTitle": "Purged K-Fold / Combinatoria",
    "description": "Uses local OHLCV-derived feature panel and strict temporal ordering.",
    "defaults": {
      "model_type": "ridge",
      "label_type": "regression_return",
      "prediction_horizon": 5,
      "k_folds": 5,
      "embargo_period": 5,
      "cpcv_n_groups": 6,
      "cpcv_k_test_groups": 2,
      "scoring_metric": "sharpe_ratio",
      "number_of_trials": 20,
      "lookback_days": 756,
      "max_symbols": 80,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false,
        "source": "master_universe.parquet",
        "description": "Any local ticker universe; defaults to the most-covered local symbols."
      },
      {
        "key": "model_type",
        "type": "select",
        "options": [
          "ridge",
          "lasso",
          "elastic_net",
          "random_forest",
          "extra_trees",
          "xgboost",
          "lightgbm"
        ],
        "default": "ridge"
      },
      {
        "key": "label_type",
        "type": "select",
        "options": [
          "regression_return",
          "binary_direction",
          "triple_barrier"
        ],
        "default": "regression_return"
      },
      {
        "key": "prediction_horizon",
        "type": "integer",
        "options": [
          1,
          5,
          21,
          63
        ],
        "default": 5
      },
      {
        "key": "k_folds",
        "type": "integer",
        "options": [
          3,
          5,
          10
        ],
        "default": 5
      },
      {
        "key": "embargo_period",
        "type": "integer",
        "options": [
          0,
          1,
          5,
          10,
          21,
          63
        ],
        "default": 5
      },
      {
        "key": "cpcv_n_groups",
        "type": "integer",
        "options": [
          4,
          6,
          8
        ],
        "default": 6
      },
      {
        "key": "cpcv_k_test_groups",
        "type": "integer",
        "options": [
          1,
          2
        ],
        "default": 2
      },
      {
        "key": "number_of_trials",
        "type": "integer",
        "default": 20,
        "description": "Used for Deflated Sharpe selection-bias correction."
      }
    ],
    "outputs": [
      {
        "key": "cpcv_sharpe_distribution",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "purged_vs_naive_cv_comparison",
        "location": "charts",
        "renderer": "comparison_bar",
        "status": "live"
      },
      {
        "key": "deflated_sharpe_ratio",
        "location": "charts",
        "renderer": "metric_panel",
        "status": "live"
      },
      {
        "key": "backtest_paths_chart",
        "location": "charts",
        "renderer": "line_bundle",
        "status": "live"
      },
      {
        "key": "embargo_sensitivity",
        "location": "charts",
        "renderer": "line_or_table",
        "status": "live"
      },
      {
        "key": "model_performance_vs_embargo",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "probability_of_backtest_overfitting",
        "location": "charts",
        "renderer": "metric_panel",
        "status": "live"
      },
      {
        "key": "dsr_pbo_joint_decision",
        "location": "charts",
        "renderer": "quadrant",
        "status": "live"
      },
      {
        "key": "per_fold_performance",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "label_fractional_uniqueness_audit",
        "location": "tables",
        "renderer": "table",
        "status": "live_proxy"
      },
      {
        "key": "cpcv_path_metrics",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "scikit-learn compatible user model upload",
      "non-uniform event timestamp CSV ingestion",
      "full triple-barrier uniqueness from externally supplied event end-times"
    ],
    "notes": [
      "Uses local OHLCV-derived feature panel and strict temporal ordering.",
      "Purging removes overlapping label-formation windows and applies post-test embargo.",
      "CPCV path count is capped through cpcv_n_groups <= 8 for realtime stability."
    ]
  },
  {
    "id": "02",
    "slug": "feature-02",
    "title": "Gradient-Boosted Tree Alpha Engine with Full Attribution",
    "category": "A",
    "shortTitle": "Gradient-Boosted Tree Alpha ",
    "description": "Fits installed tree/linear model families on OHLCV-derived cross-sectional features.",
    "defaults": {
      "model_family": "all",
      "feature_set": "ohlcv_factor_library",
      "prediction_target": "next_period_return",
      "prediction_horizon": 5,
      "tuning_mode": "platform_defaults",
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false,
        "source": "master_universe.parquet"
      },
      {
        "key": "model_family",
        "type": "select",
        "options": [
          "all",
          "xgboost",
          "lightgbm",
          "catboost",
          "random_forest",
          "extra_trees",
          "ridge"
        ],
        "default": "all"
      },
      {
        "key": "feature_set",
        "type": "select",
        "options": [
          "ohlcv_factor_library",
          "pca_loadings",
          "manual_expression"
        ],
        "default": "ohlcv_factor_library"
      },
      {
        "key": "prediction_target",
        "type": "select",
        "options": [
          "next_period_return",
          "return_sign",
          "return_quintile",
          "triple_barrier"
        ],
        "default": "next_period_return"
      },
      {
        "key": "prediction_horizon",
        "type": "integer",
        "options": [
          1,
          5,
          21,
          63,
          126,
          252
        ],
        "default": 5
      },
      {
        "key": "tuning_mode",
        "type": "select",
        "options": [
          "platform_defaults",
          "manual",
          "optuna_research"
        ],
        "default": "platform_defaults"
      }
    ],
    "outputs": [
      {
        "key": "prediction_rank_table",
        "location": "charts",
        "renderer": "rank_table",
        "status": "live"
      },
      {
        "key": "shap_feature_importance",
        "location": "charts",
        "renderer": "bar",
        "status": "live_importance_proxy"
      },
      {
        "key": "shap_long_side_importance",
        "location": "charts",
        "renderer": "bar",
        "status": "live_importance_proxy"
      },
      {
        "key": "shap_short_side_importance",
        "location": "charts",
        "renderer": "bar",
        "status": "live_importance_proxy"
      },
      {
        "key": "exact_shap_sample_importance",
        "location": "charts",
        "renderer": "bar",
        "status": "live_capped"
      },
      {
        "key": "model_ic_leaderboard",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "rolling_monthly_ic_series",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "ic_weighted_ensemble_weights",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "ic_decay_profile",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "shap_beeswarm_proxy",
        "location": "charts",
        "renderer": "beeswarm",
        "status": "live_proxy"
      },
      {
        "key": "shap_waterfall_top_signal",
        "location": "charts",
        "renderer": "waterfall",
        "status": "live_proxy"
      },
      {
        "key": "ice_partial_dependence",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "hyperparameter_landscape",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live_fast_grid"
      },
      {
        "key": "signal_to_portfolio_stats",
        "location": "charts",
        "renderer": "metric_table",
        "status": "live"
      },
      {
        "key": "prediction_distribution",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "top_bottom_signal_spread",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "current_predictions",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "model_performance",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "feature_importance",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "rolling_monthly_ic",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "hyperparameter_landscape",
        "location": "tables",
        "renderer": "table",
        "status": "live_fast_grid"
      },
      {
        "key": "signal_to_portfolio_stats",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "training_audit",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "Optuna Bayesian hyperparameter search",
      "exact TreeSHAP for every current prediction when universe > realtime cap"
    ],
    "notes": [
      "Fits installed tree/linear model families on OHLCV-derived cross-sectional features.",
      "XGBoost, LightGBM, and CatBoost are used when installed; unavailable optional libraries are skipped with metadata.",
      "Feature attribution falls back to exact model importances/coefficient magnitude when full SHAP is not requested.",
      "Attribution is also split into long-side and short-side importance proxies using the current ranked prediction book.",
      "Realtime exact TreeSHAP is capped to a small latest-book sample and emitted separately as exact_shap_sample_importance."
    ]
  },
  {
    "id": "03",
    "slug": "feature-03",
    "title": "Multi-Horizon Volatility Forecasting Engine",
    "category": "B",
    "shortTitle": "Multi-Horizon Volatility For",
    "description": "Uses HAR-Ridge/HAR-GBM plus capped ARCH-family MLE model selection when arch is installed.",
    "defaults": {
      "asset": "SPY",
      "forecast_horizons": [
        1,
        5,
        21,
        63
      ],
      "model_suite": "har_ml",
      "lookback_days": 756,
      "max_symbols": 80,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "asset",
        "type": "ticker",
        "required": false,
        "source": "master_universe.parquet"
      },
      {
        "key": "forecast_horizons",
        "type": "multi_select",
        "options": [
          1,
          5,
          21,
          63
        ],
        "default": [
          1,
          5,
          21,
          63
        ]
      },
      {
        "key": "model_suite",
        "type": "select",
        "options": [
          "har_ml",
          "har_ridge",
          "har_gbm",
          "arch_family",
          "ginn_research"
        ],
        "default": "har_ml"
      },
      {
        "key": "garch_fit_cap",
        "type": "integer",
        "options": [
          500,
          1000,
          1500
        ],
        "default": 1000
      },
      {
        "key": "macro_features",
        "type": "multi_select",
        "options": [
          "vix",
          "vix9d",
          "vix3m",
          "yc_slope_10y_2y"
        ],
        "default": [
          "vix",
          "yc_slope_10y_2y"
        ]
      }
    ],
    "outputs": [
      {
        "key": "vol_forecast_panel",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "forecast_error_distribution",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "vol_term_structure",
        "location": "charts",
        "renderer": "curve",
        "status": "live"
      },
      {
        "key": "realized_vs_predicted",
        "location": "charts",
        "renderer": "scatter_or_line",
        "status": "live"
      },
      {
        "key": "model_confidence_intervals",
        "location": "charts",
        "renderer": "band",
        "status": "live"
      },
      {
        "key": "vix_yield_macro_overlay",
        "location": "charts",
        "renderer": "macro_overlay",
        "status": "live_if_macro_present"
      },
      {
        "key": "jump_component_decomposition",
        "location": "charts",
        "renderer": "stacked_area",
        "status": "live"
      },
      {
        "key": "realized_vol_estimator_comparison",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "garch_model_selection",
        "location": "charts",
        "renderer": "table",
        "status": "live_if_arch_installed"
      },
      {
        "key": "garch_leverage_news_impact_curve",
        "location": "charts",
        "renderer": "line",
        "status": "live_if_arch_installed"
      },
      {
        "key": "vol_spillover_network",
        "location": "charts",
        "renderer": "network",
        "status": "live"
      },
      {
        "key": "ensemble_vol_forecast_weights",
        "location": "charts",
        "renderer": "bar",
        "status": "live_if_arch_installed"
      },
      {
        "key": "rolling_qlike_ensemble_weights",
        "location": "charts",
        "renderer": "stacked_area",
        "status": "live"
      },
      {
        "key": "vol_regime_classification",
        "location": "charts",
        "renderer": "stacked_area",
        "status": "live"
      },
      {
        "key": "batch_universe_vol_heatmap",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "forecast_tournament",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "forecast_rows",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "vol_regime_diagnostics",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "vol_spillover_edges",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "rolling_qlike_ensemble_weights",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "GINN neural architecture training",
      "Diebold-Mariano full tournament across large model grid",
      "GPU sequence-vol ensemble"
    ],
    "notes": [
      "Uses HAR-Ridge/HAR-GBM plus capped ARCH-family MLE model selection when arch is installed.",
      "Adds close-to-close, Garman-Klass, Yang-Zhang, and bipower jump decomposition where OHLCV fields are present.",
      "Macro overlay is pulled from category7 macro parquet when available."
    ]
  },
  {
    "id": "04",
    "slug": "feature-04",
    "title": "Meta-Labeling and Triple-Barrier Label Engine",
    "category": "C",
    "shortTitle": "Meta-Labeling / Triple-Barri",
    "description": "Labels are generated from forward local returns with explicit PT/SL/max-hold barriers.",
    "defaults": {
      "profit_taking_barrier": 0.05,
      "stop_loss_barrier": 0.03,
      "max_holding_period": 21,
      "primary_side_model": "momentum_sign",
      "confidence_level": 0.9,
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "profit_taking_barrier",
        "type": "float",
        "default": 0.05
      },
      {
        "key": "stop_loss_barrier",
        "type": "float",
        "default": 0.03
      },
      {
        "key": "max_holding_period",
        "type": "integer",
        "options": [
          5,
          10,
          21,
          63
        ],
        "default": 21
      },
      {
        "key": "primary_side_model",
        "type": "select",
        "options": [
          "momentum_sign",
          "external_model_upload",
          "feature_02_predictions"
        ],
        "default": "momentum_sign"
      },
      {
        "key": "confidence_level",
        "type": "select",
        "options": [
          0.8,
          0.9,
          0.95
        ],
        "default": 0.9
      }
    ],
    "outputs": [
      {
        "key": "triple_barrier_label_distribution",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "event_outcome_timeline",
        "location": "charts",
        "renderer": "timeline",
        "status": "live"
      },
      {
        "key": "meta_label_probability_distribution",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "cqr_interval_width_distribution",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "cqr_coverage_audit",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "barrier_hit_path_examples",
        "location": "charts",
        "renderer": "path_table",
        "status": "live"
      },
      {
        "key": "label_method_comparison",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "barrier_sensitivity_surface",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "label_audit",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "barrier_parameters",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "barrier_sensitivity",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "external primary model upload",
      "feature-store event timestamp ingestion"
    ],
    "notes": [
      "Labels are generated from forward local returns with explicit PT/SL/max-hold barriers.",
      "CQR bands use LightGBM lower/upper quantile models with chronological conformal calibration and volatility fallback only when the quantile fit is unavailable."
    ]
  },
  {
    "id": "05",
    "slug": "feature-05",
    "title": "Hierarchical Risk Parity Portfolio Optimizer with RL-Enhanced Rebalancing",
    "category": "D",
    "shortTitle": "Hierarchical Risk Parity Por",
    "description": "Supports Ledoit-Wolf, OAS, EWMA, and RMT-cleaned covariance with standard HRP, HERC, or NCO diagnostics in realtime.",
    "defaults": {
      "covariance_estimator": "ledoit_wolf",
      "clustering_linkage": "ward",
      "optimization_variant": "standard_hrp",
      "max_symbols": 80,
      "lookback_days": 756,
      "rl_rebalancing": false,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "covariance_estimator",
        "type": "select",
        "options": [
          "sample",
          "ledoit_wolf",
          "oas",
          "ewma",
          "rmt_cleaned"
        ],
        "default": "ledoit_wolf"
      },
      {
        "key": "clustering_linkage",
        "type": "select",
        "options": [
          "ward",
          "single",
          "complete",
          "average"
        ],
        "default": "ward"
      },
      {
        "key": "optimization_variant",
        "type": "select",
        "options": [
          "standard_hrp",
          "nco",
          "herc",
          "min_variance"
        ],
        "default": "standard_hrp"
      },
      {
        "key": "max_weight",
        "type": "float",
        "default": 0.25
      },
      {
        "key": "rl_rebalancing",
        "type": "boolean",
        "default": false
      }
    ],
    "outputs": [
      {
        "key": "cluster_dendrograms",
        "location": "charts",
        "renderer": "dendrogram",
        "status": "live"
      },
      {
        "key": "hrp_weight_vector",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "hrp_vs_nco_vs_markowitz_equal_weight",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "rl_rebalancing_vs_fixed_schedule",
        "location": "charts",
        "renderer": "comparison",
        "status": "research_proxy"
      },
      {
        "key": "quasi_diagonalized_covariance_heatmap",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "risk_contribution_decomposition",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "tail_dependence_matrix",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live_proxy"
      },
      {
        "key": "rolling_cluster_stability",
        "location": "charts",
        "renderer": "line",
        "status": "live_proxy"
      },
      {
        "key": "black_litterman_posterior_return_vector",
        "location": "charts",
        "renderer": "bar",
        "status": "live_proxy"
      },
      {
        "key": "bl_vs_pure_hrp_weight_comparison",
        "location": "charts",
        "renderer": "grouped_bar",
        "status": "live_proxy"
      },
      {
        "key": "view_attribution_backtest",
        "location": "charts",
        "renderer": "line",
        "status": "live_proxy"
      },
      {
        "key": "covariance_estimator_comparison",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "herc_weight_vector",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "herc_vs_hrp_comparison",
        "location": "charts",
        "renderer": "comparison",
        "status": "live"
      },
      {
        "key": "hrp_weights",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "risk_contribution",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "herc_weights",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "herc_clusters",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "PPO rebalancing agent training",
      "manual Black-Litterman view editor persistence"
    ],
    "notes": [
      "Supports Ledoit-Wolf, OAS, EWMA, and RMT-cleaned covariance with standard HRP, HERC, or NCO diagnostics in realtime.",
      "RL/BL panels are emitted as clearly marked research proxies unless research jobs are wired."
    ]
  },
  {
    "id": "06",
    "slug": "feature-06",
    "title": "Market Regime Detection and Adaptive Strategy Routing Engine",
    "category": "B",
    "shortTitle": "Market Regime Detection / Ad",
    "description": "Realtime engine fits a Gaussian HMM with Baum-Welch and deterministic state ordering by mean return; Gaussian Mixture is an explicit fallback only if HMM fitting fails.",
    "defaults": {
      "hmm_state_count": 3,
      "gmm_component_count": 3,
      "pc1_window": 63,
      "random_graph_threshold": 0.45,
      "regime_alert_threshold": 0.65,
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "input_features",
        "type": "multi_select",
        "options": [
          "returns",
          "realized_vol",
          "rolling_sharpe",
          "skew",
          "kurtosis",
          "vix",
          "yield_curve"
        ],
        "default": [
          "returns",
          "realized_vol",
          "vix"
        ]
      },
      {
        "key": "hmm_state_count",
        "type": "integer",
        "options": [
          2,
          3,
          4
        ],
        "default": 3
      },
      {
        "key": "gmm_component_count",
        "type": "integer",
        "options": [
          2,
          3,
          4
        ],
        "default": 3
      },
      {
        "key": "pc1_window",
        "type": "integer",
        "options": [
          21,
          63,
          126
        ],
        "default": 63
      },
      {
        "key": "random_graph_threshold",
        "type": "float",
        "default": 0.45
      },
      {
        "key": "regime_alert_threshold",
        "type": "float",
        "default": 0.65
      }
    ],
    "outputs": [
      {
        "key": "regime_probability_time_series",
        "location": "charts",
        "renderer": "stacked_area",
        "status": "live"
      },
      {
        "key": "regime_transition_heatmap",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "ensemble_vs_hmm_comparison",
        "location": "charts",
        "renderer": "metric_panel",
        "status": "live_compatible"
      },
      {
        "key": "pc1_structural_break_monitor",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "regime_conditional_factor_performance",
        "location": "charts",
        "renderer": "heatmap_or_table",
        "status": "live"
      },
      {
        "key": "strategy_performance_attribution_by_regime",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "regime_conditional_vol_term_structure",
        "location": "charts",
        "renderer": "curve",
        "status": "live"
      },
      {
        "key": "random_graph_systemic_risk_indicator",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "parallel_gmm_regime_probabilities",
        "location": "charts",
        "renderer": "stacked_area",
        "status": "live"
      },
      {
        "key": "hmm_vs_gmm_state_agreement",
        "location": "charts",
        "renderer": "metric_panel",
        "status": "live"
      },
      {
        "key": "regime_factor_forward_ic",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "transition_matrix",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "current_regime_probabilities",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "parallel_gmm_state_diagnostics",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "regime_factor_forward_ic",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "Student-t HMM emissions",
      "skewed-t HMM emissions",
      "tree/HMM majority-vote lead-lag validation with labeled external regimes"
    ],
    "notes": [
      "Realtime engine fits a Gaussian HMM with Baum-Welch and deterministic state ordering by mean return; Gaussian Mixture is an explicit fallback only if HMM fitting fails.",
      "PC1 structural-break and random-graph systemic-risk indicators are computed directly from local returns."
    ]
  },
  {
    "id": "07",
    "slug": "feature-07",
    "title": "Bayesian Online Learning and Dynamic Model Averaging Engine",
    "category": "C",
    "shortTitle": "Bayesian Online Learning / D",
    "description": "Realtime DMA updates weights sequentially from recent squared-error likelihood.",
    "defaults": {
      "model_library": [
        "momentum",
        "reversal",
        "low_vol",
        "ridge",
        "extra_trees"
      ],
      "ensemble_method": "dma",
      "forgetting_factor": 0.97,
      "obs_learning_rate": 0.01,
      "prediction_horizon": 5,
      "scoring_rule": "squared_error",
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "model_library",
        "type": "multi_select",
        "options": [
          "xgboost",
          "lightgbm",
          "random_forest",
          "ridge",
          "elastic_net",
          "lstm",
          "gru",
          "har",
          "rolling_mean"
        ],
        "default": [
          "momentum",
          "reversal",
          "low_vol",
          "ridge",
          "extra_trees"
        ]
      },
      {
        "key": "ensemble_method",
        "type": "select",
        "options": [
          "dma",
          "obs",
          "static_bma",
          "equal_weight",
          "all"
        ],
        "default": "dma"
      },
      {
        "key": "forgetting_factor",
        "type": "float",
        "range": [
          0.9,
          1.0
        ],
        "default": 0.97
      },
      {
        "key": "obs_learning_rate",
        "type": "float",
        "range": [
          0.001,
          0.1
        ],
        "default": 0.01
      },
      {
        "key": "scoring_rule",
        "type": "select",
        "options": [
          "log_score",
          "brier",
          "qlike",
          "squared_error",
          "rank_ic"
        ],
        "default": "squared_error"
      }
    ],
    "outputs": [
      {
        "key": "live_model_weight_dashboard",
        "location": "charts",
        "renderer": "horizontal_bar",
        "status": "live"
      },
      {
        "key": "model_weight_evolution",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "dma_vs_obs_vs_static_bma",
        "location": "charts",
        "renderer": "line_or_table",
        "status": "live"
      },
      {
        "key": "obs_weight_evolution",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "obs_regret_curve",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "model_pruning_log",
        "location": "charts",
        "renderer": "event_log",
        "status": "live"
      },
      {
        "key": "model_performance_tracker",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "prediction_calibration_curve",
        "location": "charts",
        "renderer": "calibration",
        "status": "live"
      },
      {
        "key": "epistemic_vs_aleatoric_uncertainty",
        "location": "charts",
        "renderer": "line",
        "status": "live_proxy"
      },
      {
        "key": "distributional_uncertainty_panel",
        "location": "charts",
        "renderer": "band_line",
        "status": "live_proxy"
      },
      {
        "key": "forgetting_factor_sensitivity",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "regime_specific_lambda_path",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "current_model_weights",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "score_log",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "obs_regret_log",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "model_performance_tracker",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "regime_specific_lambda_path",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "trained distributional predictive models for full calibrated epistemic/aleatoric split",
      "LSTM/GRU live ensemble members"
    ],
    "notes": [
      "Realtime DMA updates weights sequentially from recent squared-error likelihood.",
      "OBS uses simplex-projected online convex updates on Gaussian negative log-score and emits separate weight/regret curves.",
      "Realtime uncertainty bands use current model-dispersion percentiles and residual error, not heavy bootstrapped distributional models."
    ]
  },
  {
    "id": "08",
    "slug": "feature-08",
    "title": "Multi-Factor IC-Weighted Composite Signal Optimizer",
    "category": "C",
    "shortTitle": "Multi-Factor IC-Weighted Com",
    "description": "Computes IC weights and Gram-Schmidt residualization from local cross-sectional feature panel.",
    "defaults": {
      "factor_library": "ohlcv_factor_library",
      "weighting_scheme": "ic_ir",
      "orthogonalization": "gram_schmidt",
      "walk_forward_window": 252,
      "prediction_horizon": 5,
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime",
      "higher_order_interactions": true,
      "max_interactions": 30,
      "interaction_min_ic": 0.015,
      "forward_selection_max_factors": 8
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "factor_library",
        "type": "select",
        "options": [
          "ohlcv_factor_library",
          "fama_french",
          "microstructure",
          "gbt_predictions",
          "custom"
        ],
        "default": "ohlcv_factor_library"
      },
      {
        "key": "weighting_scheme",
        "type": "select",
        "options": [
          "ic",
          "ic_ir",
          "shrinkage",
          "dml_ape"
        ],
        "default": "ic_ir"
      },
      {
        "key": "orthogonalization",
        "type": "select",
        "options": [
          "none",
          "gram_schmidt",
          "pca_neutralized"
        ],
        "default": "gram_schmidt"
      },
      {
        "key": "walk_forward_window",
        "type": "integer",
        "options": [
          126,
          252,
          504
        ],
        "default": 252
      },
      {
        "key": "output_signal_construction",
        "type": "select",
        "options": [
          "long_short_decile",
          "zscore",
          "signed_rank"
        ],
        "default": "zscore"
      },
      {
        "key": "higher_order_interactions",
        "type": "boolean",
        "default": true
      },
      {
        "key": "max_interactions",
        "type": "integer",
        "options": [
          10,
          30,
          60,
          100
        ],
        "default": 30
      },
      {
        "key": "interaction_min_ic",
        "type": "number",
        "default": 0.015
      },
      {
        "key": "forward_selection_max_factors",
        "type": "integer",
        "options": [
          4,
          8,
          12
        ],
        "default": 8
      }
    ],
    "outputs": [
      {
        "key": "ic_weighted_composite_weights",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "factor_correlation_heatmap",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "orthogonalization_impact",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "walk_forward_weight_stability",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "composite_signal_distribution",
        "location": "charts",
        "renderer": "histogram_or_table",
        "status": "live"
      },
      {
        "key": "long_short_backtest",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "factor_turnover_table",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "higher_order_interaction_table",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "interaction_table",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "forward_selection_fama_macbeth",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "elastic_lasso_factor_selection",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "alphaforge_dynamic_weights",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "ic_decay_alerts",
        "location": "charts",
        "renderer": "event_log",
        "status": "live"
      },
      {
        "key": "rolling_composite_ic",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "factor_ic_table",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "latest_composite_scores",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "orthogonalization_table",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "elastic_lasso_factor_selection",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "ic_decay_alerts",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "server-side persistence of Feature 11 DML APE weights",
      "custom factor CSV ingestion",
      "nested/full-library Fama-MacBeth model-selection research sweep"
    ],
    "notes": [
      "Computes IC weights and Gram-Schmidt residualization from local cross-sectional feature panel.",
      "Screens pairwise higher-order factor interactions with fast cross-sectional Spearman IC.",
      "Includes a realtime forward-selection Fama-MacBeth-style screen over the current local factor library.",
      "DML APE mode is available once Feature 11 outputs are persisted/routed."
    ]
  },
  {
    "id": "09",
    "slug": "feature-09",
    "title": "ML-Enhanced Pairs and Statistical Arbitrage Engine",
    "category": "D",
    "shortTitle": "ML-Enhanced Pairs / Statisti",
    "description": "Realtime candidate screen uses correlation, Engle-Granger ADF p-value, spread z-score, and OU half-life.",
    "defaults": {
      "pair_selection": "correlation_ou",
      "min_correlation": 0.45,
      "entry_z": 2.0,
      "exit_z": 0.5,
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "pair_selection",
        "type": "select",
        "options": [
          "correlation_ou",
          "engle_granger",
          "johansen_research",
          "sector_neutral"
        ],
        "default": "correlation_ou"
      },
      {
        "key": "min_correlation",
        "type": "float",
        "default": 0.45
      },
      {
        "key": "entry_z",
        "type": "float",
        "default": 2.0
      },
      {
        "key": "exit_z",
        "type": "float",
        "default": 0.5
      },
      {
        "key": "hedge_ratio_method",
        "type": "select",
        "options": [
          "static",
          "rolling_ols",
          "kalman"
        ],
        "default": "kalman"
      }
    ],
    "outputs": [
      {
        "key": "pair_candidate_leaderboard",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "spread_zscore_timeseries",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "cointegration_network",
        "location": "charts",
        "renderer": "network",
        "status": "live_proxy"
      },
      {
        "key": "kalman_hedge_ratio_path",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "entry_exit_signal_timeline",
        "location": "charts",
        "renderer": "timeline",
        "status": "live"
      },
      {
        "key": "pair_backtest_equity",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "rl_threshold_policy",
        "location": "charts",
        "renderer": "policy_table",
        "status": "research_proxy"
      },
      {
        "key": "adf_pvalue_distribution",
        "location": "charts",
        "renderer": "histogram_or_table",
        "status": "live"
      },
      {
        "key": "pair_precluster_map",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "copula_entry_thresholds",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "pair_network_components",
        "location": "charts",
        "renderer": "network_summary",
        "status": "live"
      },
      {
        "key": "ml_pair_classifier_scores",
        "location": "charts",
        "renderer": "table",
        "status": "live_fast_score"
      },
      {
        "key": "pair_candidates",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "spread_timeseries",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "kalman_hedge_ratio",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "pair_preclusters",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "Johansen full-rank tests across all candidate baskets",
      "PPO threshold optimizer"
    ],
    "notes": [
      "Realtime candidate screen uses correlation, Engle-Granger ADF p-value, spread z-score, and OU half-life.",
      "Top-pair hedge ratio is fit with a random-walk beta Kalman filter and the residual path drives z-score signals."
    ]
  },
  {
    "id": "10",
    "slug": "feature-10",
    "title": "Market Microstructure Signal Observatory",
    "category": "D",
    "shortTitle": "Market Microstructure Signal",
    "description": "Repo has OHLCV, not tick-level quotes. Realtime implementation uses accepted daily microstructure estimators.",
    "defaults": {
      "signal_families": [
        "amihud",
        "hl_amihud",
        "roll_spread",
        "corwin_schultz_spread",
        "max_factor",
        "52w_high",
        "ivol",
        "volume_surprise"
      ],
      "ic_protocol": "purged_kfold_proxy",
      "lookback_days": 756,
      "max_symbols": 250,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false,
        "source": "master_universe.parquet"
      },
      {
        "key": "signal_families",
        "type": "multi_select",
        "options": [
          "amihud",
          "hl_amihud",
          "roll_spread",
          "corwin_schultz_spread",
          "max_factor",
          "52w_high",
          "ivol",
          "volume_surprise",
          "dollar_vol_momentum",
          "turnover_rate"
        ],
        "default": [
          "amihud",
          "hl_amihud",
          "roll_spread",
          "corwin_schultz_spread",
          "max_factor",
          "52w_high",
          "ivol",
          "volume_surprise"
        ]
      },
      {
        "key": "ic_protocol",
        "type": "select",
        "options": [
          "purged_kfold_proxy",
          "cpcv_research"
        ],
        "default": "purged_kfold_proxy"
      },
      {
        "key": "amihud_window",
        "type": "integer",
        "options": [
          21,
          63
        ],
        "default": 21
      },
      {
        "key": "ivol_model",
        "type": "select",
        "options": [
          "market_residual",
          "ff3",
          "ff5_mom"
        ],
        "default": "market_residual"
      }
    ],
    "outputs": [
      {
        "key": "microstructure_ic_leaderboard",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "amihud_illiquidity_surface",
        "location": "charts",
        "renderer": "surface_or_heatmap",
        "status": "live"
      },
      {
        "key": "roll_spread_cross_section",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "max_factor_distribution",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "52_week_high_proximity_heatmap",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "ivol_cross_sectional_sort",
        "location": "charts",
        "renderer": "bar",
        "status": "live"
      },
      {
        "key": "volume_surprise_signal",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "microstructure_signal_correlation_matrix",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "liquidity_regime_monitor",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "signal_backtest",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "corwin_schultz_spread_cross_section",
        "location": "charts",
        "renderer": "histogram",
        "status": "live"
      },
      {
        "key": "hl_amihud_vs_standard_amihud",
        "location": "charts",
        "renderer": "scatter_or_table",
        "status": "live"
      },
      {
        "key": "amihud_time_surface",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live"
      },
      {
        "key": "microstructure_table",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "ic_leaderboard",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "amihud_time_surface",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "true bid-ask spread from quote data",
      "order-flow imbalance",
      "signed volume",
      "intraday Lee-Ready classification"
    ],
    "notes": [
      "Repo has OHLCV, not tick-level quotes. Realtime implementation uses accepted daily microstructure estimators.",
      "Amihud, high-low Amihud, Roll, Corwin-Schultz, MAX, 52-week high proximity, IVOL, dollar-volume momentum, turnover, and volume surprise are computed from local panels."
    ]
  },
  {
    "id": "11",
    "slug": "feature-11",
    "title": "Causal Factor Discovery Engine",
    "category": "C",
    "shortTitle": "Causal Factor Discovery",
    "description": "Realtime implementation uses K-fold cross-fitted DML residualization with Ridge, random forest, or LightGBM nuisance models when installed.",
    "defaults": {
      "factor_library": "ohlcv_factor_library",
      "dml_folds": 5,
      "nuisance_model": "ridge",
      "rolling_window": 252,
      "significance_threshold": 0.95,
      "spurious_factor_action": "flag_only",
      "lookback_days": 756,
      "max_symbols": 120,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "factor_library",
        "type": "select",
        "options": [
          "ohlcv_factor_library",
          "fama_french",
          "microstructure",
          "gbt_predictions",
          "custom"
        ],
        "default": "ohlcv_factor_library"
      },
      {
        "key": "dml_folds",
        "type": "integer",
        "options": [
          3,
          5
        ],
        "default": 5
      },
      {
        "key": "nuisance_model",
        "type": "select",
        "options": [
          "ridge",
          "elastic_net",
          "random_forest",
          "lightgbm"
        ],
        "default": "ridge"
      },
      {
        "key": "rolling_window",
        "type": "integer",
        "options": [
          126,
          252,
          504
        ],
        "default": 252
      },
      {
        "key": "significance_threshold",
        "type": "select",
        "options": [
          0.9,
          0.95,
          0.99
        ],
        "default": 0.95
      },
      {
        "key": "spurious_factor_action",
        "type": "select",
        "options": [
          "flag_only",
          "auto_prune",
          "user_decision"
        ],
        "default": "flag_only"
      }
    ],
    "outputs": [
      {
        "key": "causal_ape_leaderboard",
        "location": "charts",
        "renderer": "error_bar_table",
        "status": "live"
      },
      {
        "key": "confounding_bias_decomposition",
        "location": "charts",
        "renderer": "waterfall",
        "status": "live"
      },
      {
        "key": "ape_time_series",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "spurious_factor_detection_log",
        "location": "charts",
        "renderer": "event_log",
        "status": "live"
      },
      {
        "key": "nuisance_model_r2_table",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "robust_inference_table",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "causal_factor_network",
        "location": "charts",
        "renderer": "network",
        "status": "live"
      },
      {
        "key": "dml_vs_ols_backtest_comparison",
        "location": "charts",
        "renderer": "comparison",
        "status": "live"
      },
      {
        "key": "rolling_spurious_fraction",
        "location": "charts",
        "renderer": "line",
        "status": "live"
      },
      {
        "key": "causal_ape_table",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "causal_network_edges",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "robust_inference_table",
        "location": "tables",
        "renderer": "table",
        "status": "live"
      }
    ],
    "researchOnly": [
      "Optuna tuning for nuisance models",
      "server-side auto-prune into Feature 8"
    ],
    "notes": [
      "Realtime implementation uses K-fold cross-fitted DML residualization with Ridge, random forest, or LightGBM nuisance models when installed.",
      "Outputs distinguish Causal, Proxy, and Spurious factors using APE t-statistics and IC-vs-APE gap.",
      "Adds HC3 robust univariate inference as a fast diagnostic beside the DML APE statistic."
    ]
  },
  {
    "id": "12",
    "slug": "feature-12",
    "title": "Deep Sequence Alpha Engine",
    "category": "C",
    "shortTitle": "Deep Sequence Alpha",
    "description": "Realtime output provides deterministic architecture diagnostics and proxy model comparisons from local panels.",
    "defaults": {
      "architectures": [
        "patchtst_proxy",
        "itransformer_proxy",
        "tft_proxy",
        "gbt"
      ],
      "input_feature_set": [
        "ohlcv_factor_library",
        "fama_french",
        "macro"
      ],
      "patch_length": 21,
      "lookback_days": 756,
      "prediction_horizon": 5,
      "transformer_depth": 2,
      "attention_heads": 4,
      "dropout_rate": 0.1,
      "max_symbols": 80,
      "compute_mode": "realtime"
    },
    "fields": [
      {
        "key": "symbols",
        "type": "ticker_list",
        "required": false
      },
      {
        "key": "architectures",
        "type": "multi_select",
        "options": [
          "patchtst",
          "itransformer",
          "tft",
          "mamba",
          "lstm",
          "gbt"
        ],
        "default": [
          "patchtst_proxy",
          "itransformer_proxy",
          "tft_proxy",
          "gbt"
        ]
      },
      {
        "key": "input_feature_set",
        "type": "multi_select",
        "options": [
          "ohlcv_factor_library",
          "microstructure",
          "regime_probabilities",
          "fama_french",
          "macro"
        ],
        "default": [
          "ohlcv_factor_library",
          "fama_french",
          "macro"
        ]
      },
      {
        "key": "patch_length",
        "type": "integer",
        "options": [
          5,
          10,
          21
        ],
        "default": 21
      },
      {
        "key": "prediction_horizon",
        "type": "integer",
        "options": [
          1,
          5,
          21,
          63
        ],
        "default": 5
      },
      {
        "key": "transformer_depth",
        "type": "integer",
        "options": [
          2,
          4,
          6
        ],
        "default": 2
      },
      {
        "key": "attention_heads",
        "type": "integer",
        "options": [
          4,
          8
        ],
        "default": 4
      },
      {
        "key": "dropout_rate",
        "type": "float",
        "options": [
          0.0,
          0.1,
          0.2,
          0.3
        ],
        "default": 0.1
      }
    ],
    "outputs": [
      {
        "key": "architecture_comparison_ic_table",
        "location": "charts",
        "renderer": "table",
        "status": "live_proxy"
      },
      {
        "key": "multi_horizon_ic_decay_panel",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "patchtst_attention_heatmap",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live_diagnostic"
      },
      {
        "key": "itransformer_cross_sectional_attention_map",
        "location": "charts",
        "renderer": "heatmap",
        "status": "live_diagnostic"
      },
      {
        "key": "tft_variable_selection_weights",
        "location": "charts",
        "renderer": "bar",
        "status": "live_diagnostic"
      },
      {
        "key": "integrated_gradients_attribution",
        "location": "charts",
        "renderer": "bar",
        "status": "live_proxy"
      },
      {
        "key": "patchtst_vs_itransformer_regime_split",
        "location": "charts",
        "renderer": "line",
        "status": "live_proxy"
      },
      {
        "key": "ensemble_contribution_chart",
        "location": "charts",
        "renderer": "bar",
        "status": "live_proxy"
      },
      {
        "key": "compute_cost_vs_ic_gain_table",
        "location": "charts",
        "renderer": "table",
        "status": "live"
      },
      {
        "key": "architecture_comparison",
        "location": "tables",
        "renderer": "table",
        "status": "live_proxy"
      },
      {
        "key": "variable_selection",
        "location": "tables",
        "renderer": "table",
        "status": "live_diagnostic"
      }
    ],
    "researchOnly": [
      "full PatchTST training",
      "full iTransformer training",
      "full TFT training",
      "Mamba sequence model",
      "GPU training cache"
    ],
    "notes": [
      "Realtime output provides deterministic architecture diagnostics and proxy model comparisons from local panels.",
      "Full deep training is explicitly research-mode only because it needs GPU/job orchestration and cached artifacts."
    ]
  }
];

export function normalizeMlV2FeatureId(featureId) {
  return String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
}

export function getMlV2Feature(featureId) {
  const normalized = normalizeMlV2FeatureId(featureId);
  const feature = ML_V2_FEATURES.find((item) => item.id === normalized);
  if (!feature) throw new Error(`Unknown ML V2 feature: ${featureId}`);
  return feature;
}

export function getMlV2Sections(featureId) {
  const feature = getMlV2Feature(featureId);
  return (feature.outputs || []).map((output, index) => ({
    id: output.key.replace(/_/g, "-"),
    title: output.key.split("_").map((part) => part ? part[0].toUpperCase() + part.slice(1) : part).join(" "),
    source: output.location || "charts",
    dataKey: output.key,
    chartType: output.renderer || "table",
    rank: index === 0 ? "primary" : index < 4 ? "supporting" : "contextual",
    status: output.status || "live",
    config: {},
  }));
}
