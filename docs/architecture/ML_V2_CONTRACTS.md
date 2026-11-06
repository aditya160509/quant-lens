# ML V2 contracts

Contract version `ml_v2.2026-10-05`. Generated from the backend manifest; regenerate with `tests/ml_v2_contract_snapshot.py`.

## Endpoints (prefix `/api/ml/v2`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/features` | `{contract_version, deprecated_inputs, features:[{id,title,status,inputs,outputs,known_limitations}]}` |
| GET | `/features/{id}` | One manifest row |
| POST | `/features/{id}/validate` | `{valid:true,payload}` with defaults applied, or 422 `{detail:string}` |
| POST | `/features/{id}/jobs` | Body is the flat payload; returns `{job_id,status}`; 422 on invalid inputs or unknown tickers |
| GET | `/jobs/{job_id}?include_result=true` | `{job_id,status,progress:{percent,message},error,feature_id,created_at,updated_at,result?}`; status is queued, running, completed, failed or cancelled |
| GET | `/jobs/{job_id}/result` | Result only (409 until completed) |
| POST | `/jobs/{job_id}/cancel` | Cancels at the next stage checkpoint |
| POST | `/features/{id}/run` | Synchronous run (small universes) |
| GET | `/symbols?q=&limit=` | Ticker search |
| POST | `/uploads?kind=universe` | CSV universe, returns `{upload_id,symbols}` |

## Input row
`{key,label,type,default,required,level,group,unit,help,depends_on,options?,min?,max?,integer?}`. `type` is one of select, multiselect, number, boolean, date, ticker_list, ticker, text_list, json. `level` is quick, standard or expert. `depends_on` is `{field,values}` (show when the field holds one of the values) or `{field,present:true}`; it is a display hint, not a validation rule. Unknown keys are rejected; `compute_mode` and `research_mode` are dropped.

## Result envelope
`{feature_id,status,summary_cards:[{label,value,unit,detail?}],charts:{id:records},tables:{id:records},alerts:[{level,message}],meta}`. Every list holds flat records; no NaN or inf (null instead); dates are `YYYY-MM-DD` strings. An output row's `path` (`charts.x` or `tables.x`) locates it; `type` is timeseries, bar, scatter, heatmap, kpi, table, network or dendrogram; `encoding` names the columns for x, y, series, value; `bin:true` means the client histograms raw values; `schema.columns` lists columns with type number, string, date or boolean. Heatmaps are long (`row,col,value`) except the wide `amihud_time_surface` (`dynamic_columns`: one numeric column per ticker). Outputs with `depends_on` are empty lists unless that input is set.


## Feature 01: Combinatorial Purged Cross-Validation Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `model_type` | select | `"ridge"` | quick |  | ['ridge', 'lasso', 'elastic_net', 'linear_svm', 'mlp', 'random_forest', 'extra_trees', 'xgboost', 'lightgbm', 'catboost'] |  |
| `label_type` | select | `"regression_return"` | expert |  | ['regression_return'] |  |
| `prediction_horizon` | select | `5` | quick | sessions | [1, 5, 21, 63] |  |
| `embargo_period` | select | `5` | standard | sessions | [0, 1, 5, 10, 21, 63] |  |
| `cpcv_n_groups` | select | `6` | standard | groups | [4, 6, 8] |  |
| `cpcv_k_test_groups` | select | `2` | standard | groups | [1, 2] |  |
| `calculate_embargo_sensitivity` | boolean | `false` | expert |  |  |  |
| `strategy_returns` | json | `null` | expert |  |  |  |
| `pbo_partitions` | select | `8` | expert | blocks | [4, 6, 8, 10, 12] | {"field": "strategy_returns", "present": true} |
| `selected_strategy` | number | `0` | expert | column | 0.. | {"field": "strategy_returns", "present": true} |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `80` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `cpcv_sharpe_distribution` | bar | `charts.cpcv_sharpe_distribution` | `{"x": "sharpe", "bin": true}` | sharpe:number |
| `purged_vs_naive_cv_comparison` | bar | `charts.purged_vs_naive_cv_comparison` | `{"x": "method", "y": "sharpe"}` | method:string, sharpe:number |
| `backtest_paths_chart` | timeseries | `charts.backtest_paths_chart` | `{"x": "date", "y": "equity", "series": "path"}` | path:number, date:date, equity:number |
| `probability_of_backtest_overfitting` | kpi | `charts.probability_of_backtest_overfitting` | `{"value": ["pbo", "dsr"], "status": "status"}` | pbo:number, dsr:number, status:string, reason:string |
| `deflated_sharpe_ratio` | kpi | `charts.deflated_sharpe_ratio` | `{"value": ["pbo", "dsr"], "status": "status"}` | pbo:number, dsr:number, status:string, reason:string |
| `embargo_sensitivity` | table | `charts.embargo_sensitivity` | `{}` |  |
| `per_fold_performance` | table | `tables.per_fold_performance` | `{}` | split:number, test_groups:object, training_observations:number, test_observations:number, purged_observations:number, embargo_sessions:number, test_start:date, test_end:date, purged_sharpe:number, naive_sharpe:number, ic:number |
| `cpcv_path_metrics` | table | `tables.cpcv_path_metrics` | `{}` | path:number, sharpe:number, observations:number |

Not supported: scikit-learn compatible user model upload; non-uniform event timestamp CSV ingestion; full triple-barrier uniqueness from externally supplied event end-times.

## Feature 02: Gradient-Boosted Tree Alpha Engine with Full Attribution

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `model_family` | select | `"all"` | quick |  | ['all', 'xgboost', 'lightgbm', 'catboost', 'random_forest', 'extra_trees', 'ridge'] |  |
| `feature_set` | select | `"ohlcv_factor_library"` | expert |  | ['ohlcv_factor_library'] |  |
| `prediction_target` | select | `"next_period_return"` | expert |  | ['next_period_return'] |  |
| `prediction_horizon` | select | `5` | quick | sessions | [1, 5, 21, 63, 126, 252] |  |
| `tuning_mode` | select | `"platform_defaults"` | standard |  | ['platform_defaults', 'manual', 'optuna_research'] |  |
| `sample_weighting` | select | `"equal"` | expert |  | ['equal', 'time_decay'] |  |
| `sector_filter` | text_list | `null` | expert |  |  |  |
| `minimum_formation_notional` | number | `0` | expert | quote currency | 0.. |  |
| `hyperparameters` | json | `null` | expert |  |  | {"field": "tuning_mode", "values": ["manual"]} |
| `optuna_trials` | number | `10` | standard | trials | 1..50 | {"field": "tuning_mode", "values": ["optuna_research"]} |
| `exact_shap_cap` | number | `64` | expert | rows | 1..256 |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |
| `embargo_period` | number | `5` | standard | sessions | .. |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `prediction_rank_table` | table | `charts.prediction_rank_table` | `{}` | date:date, ticker:string, sector:string, prediction:number, rank:number |
| `shap_feature_importance` | bar | `charts.shap_feature_importance` | `{"x": "feature", "y": "mean_abs_shap"}` | feature:string, mean_abs_shap:number |
| `shap_beeswarm` | scatter | `charts.shap_beeswarm` | `{"x": "shap_value", "y": "feature", "color": "feature_value"}` | ticker:string, feature:string, feature_value:number, shap_value:number |
| `shap_waterfall_top_signal` | bar | `charts.shap_waterfall_top_signal` | `{"x": "feature", "y": "shap_value"}` | feature:string, shap_value:number |
| `model_ic_leaderboard` | bar | `charts.model_ic_leaderboard` | `{"x": "model", "y": ["validation_ic", "test_ic"]}` | model:string, validation_mae:number, validation_ic:number, ensemble_weight:number, test_ic:number, test_mae:number |
| `rolling_monthly_ic_series` | timeseries | `charts.rolling_monthly_ic_series` | `{"x": "month", "y": "rolling_ic"}` | month:string, rolling_ic:number, observations:number |
| `current_predictions` | table | `tables.current_predictions` | `{}` | date:date, ticker:string, sector:string, prediction:number, rank:number |
| `model_performance` | table | `tables.model_performance` | `{}` | model:string, validation_mae:number, validation_ic:number, ensemble_weight:number, test_ic:number, test_mae:number |
| `heldout_predictions` | table | `tables.heldout_predictions` | `{}` | date:date, ticker:string, prediction:number, actual_forward_return:number |
| `tuning_trials` | table | `tables.tuning_trials` | `{}` |  |
| `training_audit` | table | `tables.training_audit` | `{}` | train_rows:number, test_rows:number, validation_rows:number, selected_model:string |

## Feature 03: Multi-Horizon Volatility Forecasting Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `asset` | ticker | `null` | quick |  |  |  |
| `forecast_horizons` | multiselect | `[1, 5, 21, 63]` | quick | sessions | [1, 5, 21, 63] |  |
| `model_suite` | select | `"har_ml"` | standard |  | ['har_ml', 'har_ridge', 'har_gbm', 'har_x', 'arch_family'] |  |
| `garch_fit_cap` | select | `1000` | expert | sessions | [500, 1000, 1500] | {"field": "model_suite", "values": ["arch_family", "har_ml"]} |
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `80` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `vol_forecast_panel` | timeseries | `charts.vol_forecast_panel` | `{"x": "date", "y": ["forecast_vol", "realized_vol"], "series": "model", "facet": "horizon"}` | date:date, model:string, horizon:number, forecast_vol:number, realized_vol:number |
| `forecast_error_distribution` | bar | `charts.forecast_error_distribution` | `{"x": "model", "y": "mae", "facet": "horizon"}` | model:string, horizon:number, mae:number, qlike:number, interval_coverage:number |
| `vol_term_structure` | timeseries | `charts.vol_term_structure` | `{"x": "horizon", "y": "forecast_vol", "series": "model"}` | model:string, horizon:number, forecast_vol:number, formation_date:date |
| `realized_vs_predicted` | scatter | `charts.realized_vs_predicted` | `{"x": "forecast_vol", "y": "realized_vol", "series": "model", "facet": "horizon"}` | date:date, model:string, horizon:number, forecast_vol:number, realized_vol:number |
| `model_confidence_intervals` | timeseries | `charts.model_confidence_intervals` | `{"x": "date", "y": ["lower", "upper"], "series": "model", "facet": "horizon"}` | date:date, model:string, horizon:number, lower:number, upper:number |
| `realized_vol_estimator_comparison` | bar | `charts.realized_vol_estimator_comparison` | `{"x": "estimator", "y": "current_vol"}` | estimator:string, current_vol:number |
| `garch_model_selection` | table | `charts.garch_model_selection` | `{}` |  |
| `garch_leverage_news_impact_curve` | timeseries | `charts.garch_leverage_news_impact_curve` | `{"x": "shock_sigma", "y": "next_variance"}` |  |
| `ensemble_vol_forecast_weights` | bar | `charts.ensemble_vol_forecast_weights` | `{"x": "model", "y": "ensemble_weight"}` |  |
| `forecast_tournament` | table | `tables.forecast_tournament` | `{}` | model:string, horizon:number, mae:number, qlike:number, interval_coverage:number |
| `forecast_rows` | table | `tables.forecast_rows` | `{}` | date:date, model:string, horizon:number, forecast_vol:number, realized_vol:number |
| `garch_model_selection` | table | `tables.garch_model_selection` | `{}` |  |

## Feature 04: Meta-Labeling and Triple-Barrier Label Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `profit_taking_barrier` | number | `0.05` | quick | return or sigma | .. |  |
| `stop_loss_barrier` | number | `0.03` | quick | return or sigma | .. |  |
| `max_holding_period` | select | `21` | quick | sessions | [5, 10, 21, 63] |  |
| `barrier_mode` | select | `"fixed"` | standard |  | ['fixed', 'vol_scaled'] |  |
| `barrier_side` | select | `"bilateral"` | expert |  | ['bilateral'] |  |
| `position_sizing` | select | `"probability"` | standard |  | ['probability', 'binary'] |  |
| `primary_side_model` | select | `"momentum_sign"` | expert |  | ['momentum_sign'] |  |
| `confidence_level` | select | `0.9` | standard | probability | [0.8, 0.9, 0.95] |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |
| `embargo_period` | number | `5` | standard | sessions | .. |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `triple_barrier_label_distribution` | bar | `charts.triple_barrier_label_distribution` | `{"x": "label", "y": "count"}` | label:number, count:number |
| `event_outcome_timeline` | scatter | `charts.event_outcome_timeline` | `{"x": "date", "y": "forward_return", "color": "label"}` | date:date, ticker:string, forward_return:number, label:number, vol_21:number, touch_date:date, touch_type:string, upper_barrier:number, lower_barrier:number, barrier_method:string, primary_side:number, meta_probability:number, position_size:number, cqr_lower:number, cqr_upper:number, cqr_interval_width:number |
| `meta_label_probability_distribution` | bar | `charts.meta_label_probability_distribution` | `{"x": "meta_probability", "bin": true}` | meta_probability:number |
| `cqr_interval_width_distribution` | bar | `charts.cqr_interval_width_distribution` | `{"x": "interval_width", "bin": true}` | interval_width:number |
| `cqr_coverage_audit` | timeseries | `charts.cqr_coverage_audit` | `{"x": "date", "y": ["empirical_coverage", "target_coverage"]}` | date:date, target_coverage:number, empirical_coverage:number |
| `barrier_hit_path_examples` | table | `charts.barrier_hit_path_examples` | `{}` | date:date, ticker:string, forward_return:number, label:number, vol_21:number, touch_date:date, touch_type:string, upper_barrier:number, lower_barrier:number, barrier_method:string, primary_side:number, meta_probability:number, position_size:number, cqr_lower:number, cqr_upper:number, cqr_interval_width:number |
| `label_method_comparison` | bar | `charts.label_method_comparison` | `{"x": "method", "y": ["positive_rate", "negative_rate", "neutral_rate"]}` | method:string, events:number, ambiguous:number, positive_rate:number, negative_rate:number, neutral_rate:number |
| `barrier_sensitivity_surface` | heatmap | `charts.barrier_sensitivity_surface` | `{"x": "profit_taking", "y": "stop_loss", "value": "positive_rate"}` | profit_taking:number, stop_loss:number, events:number, ambiguous_events:number, positive_rate:number, negative_rate:number, neutral_rate:number |
| `label_audit` | table | `tables.label_audit` | `{}` | date:date, ticker:string, forward_return:number, label:number, vol_21:number, touch_date:date, touch_type:string, upper_barrier:number, lower_barrier:number, barrier_method:string, primary_side:number, meta_probability:number, position_size:number, cqr_lower:number, cqr_upper:number, cqr_interval_width:number |
| `label_method_comparison` | bar | `tables.label_method_comparison` | `{"x": "method", "y": ["positive_rate", "negative_rate", "neutral_rate"]}` | method:string, events:number, ambiguous:number, positive_rate:number, negative_rate:number, neutral_rate:number |
| `barrier_parameters` | table | `tables.barrier_parameters` | `{}` | profit_taking:number, stop_loss:number, max_holding_period:number, barrier_mode:string, barrier_side:string |
| `barrier_sensitivity` | table | `tables.barrier_sensitivity` | `{}` | profit_taking:number, stop_loss:number, events:number, ambiguous_events:number, positive_rate:number, negative_rate:number, neutral_rate:number |

Not supported: external primary model upload; feature-store event timestamp ingestion.

## Feature 05: Constrained HRP, NCO and Minimum-Variance Allocation

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `covariance_estimator` | select | `"ledoit_wolf"` | standard |  | ['sample', 'ledoit_wolf', 'oas', 'ewma', 'rmt_cleaned'] |  |
| `clustering_linkage` | select | `"ward"` | expert |  | ['ward', 'single', 'complete', 'average'] | {"field": "optimization_variant", "values": ["standard_hrp", "nco"]} |
| `optimization_variant` | select | `"standard_hrp"` | quick |  | ['standard_hrp', 'nco', 'min_variance'] |  |
| `max_weight` | number | `0.25` | standard | weight | 0.0..1.0 |  |
| `min_weight` | number | `0.0` | standard | weight | 0.0..1.0 |  |
| `max_sector_weight` | number | `0.4` | standard | weight | 0.0..1.0 |  |
| `black_litterman_tau` | number | `0.05` | expert |  | 0.0001..1.0 |  |
| `views` | json | `null` | expert |  |  |  |
| `allocation_window` | select | `126` | standard | sessions | [63, 126, 252] |  |
| `cost_bps` | number | `5` | standard | bps | 0..1000 |  |
| `risk_aversion` | number | `2.5` | expert |  | 0.01..100 |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `80` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `hrp_weight_vector` | bar | `charts.hrp_weight_vector` | `{"x": "asset", "y": "weight"}` | asset:string, weight:number, sector:string |
| `cluster_dendrograms` | dendrogram | `charts.cluster_dendrograms` | `{"left": "left", "right": "right", "height": "distance", "size": "count"}` | left:number, right:number, distance:number, count:number |
| `quasi_diagonalized_covariance_heatmap` | heatmap | `charts.quasi_diagonalized_covariance_heatmap` | `{"x": "col", "y": "row", "value": "value"}` | row:string, col:string, value:number |
| `risk_contribution_decomposition` | bar | `charts.risk_contribution_decomposition` | `{"x": "asset", "y": "risk_contribution"}` | asset:string, risk_contribution:number |
| `walk_forward_allocation` | timeseries | `charts.walk_forward_allocation` | `{"x": "date", "y": "equity"}` | date:date, gross_return:number, net_return:number, turnover:number, cost_fraction:number, equity:number |
| `black_litterman_posterior_return_vector` | table | `charts.black_litterman_posterior_return_vector` | `{}` | asset:string, reference_prior_return:number, posterior_return:number, posterior_weight:number |
| `bl_vs_pure_hrp_weight_comparison` | bar | `charts.bl_vs_pure_hrp_weight_comparison` | `{"x": "asset", "y": ["allocation_weight", "black_litterman"]}` | asset:string, allocation_weight:number, black_litterman:number |
| `hrp_weights` | table | `tables.hrp_weights` | `{}` | asset:string, weight:number, sector:string |
| `allocation_training_audit` | table | `tables.allocation_training_audit` | `{}` | formation_date:date, training_end:date, assets:number |
| `black_litterman` | table | `tables.black_litterman` | `{}` | asset:string, reference_prior_return:number, posterior_return:number, posterior_weight:number |

Not supported: PPO rebalancing, HERC and asymptotic tail-dependence estimators are not implemented; no proxy output is produced.

## Feature 06: Market Regime Detection and Adaptive Strategy Routing Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `input_features` | multiselect | `["returns", "realized_vol"]` | standard |  | ['returns', 'realized_vol', 'rolling_sharpe', 'skew', 'kurtosis'] |  |
| `hmm_state_count` | select | `3` | quick | states | [2, 3, 4] |  |
| `gmm_component_count` | select | `3` | standard | components | [2, 3, 4] |  |
| `pc1_window` | select | `63` | standard | sessions | [21, 63, 126] |  |
| `random_graph_threshold` | number | `0.45` | expert | |rho| | 0.0..1.0 |  |
| `regime_alert_threshold` | number | `0.65` | standard | probability | 0.0..1.0 |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `regime_probability_time_series` | timeseries | `charts.regime_probability_time_series` | `{"x": "date", "y": ["state_1", "state_2", "state_3", "state_4"]}` | date:date, dominant_state:number, state_1:number, state_2:number, state_3:number |
| `regime_transition_heatmap` | heatmap | `charts.regime_transition_heatmap` | `{"x": "col", "y": "row", "value": "value"}` | row:string, col:string, value:number |
| `ensemble_vs_hmm_comparison` | kpi | `charts.ensemble_vs_hmm_comparison` | `{"value": ["oos_agreement"]}` | oos_agreement:number, observations:number |
| `pc1_variance_monitor` | timeseries | `charts.pc1_variance_monitor` | `{"x": "date", "y": "pc1_explained_variance"}` | date:date, pc1_explained_variance:number |
| `regime_conditional_asset_returns` | bar | `charts.regime_conditional_asset_returns` | `{"x": "asset", "y": "mean_log_return", "series": "regime"}` | asset:string, regime:number, mean_log_return:number, observations:number |
| `correlation_network_density` | kpi | `charts.correlation_network_density` | `{"value": ["density"]}` | density:number, absolute_correlation_threshold:number |
| `parallel_gmm_regime_probabilities` | timeseries | `charts.parallel_gmm_regime_probabilities` | `{"x": "date", "y": ["component_1", "component_2", "component_3", "component_4"]}` | date:date, component_1:number, component_2:number, component_3:number |
| `transition_matrix` | table | `tables.transition_matrix` | `{}` | row:string, col:string, value:number |
| `current_regime_probabilities` | table | `tables.current_regime_probabilities` | `{}` | date:date, dominant_state:number, state_1:number, state_2:number, state_3:number |
| `training_audit` | table | `tables.training_audit` | `{}` | train_dates:number, test_dates:number, training_end:date, hmm_converged:boolean |

## Feature 07: Bayesian Online Learning and Dynamic Model Averaging Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `model_library` | multiselect | `["momentum", "reversal", "low_vol", "ridge", "extra_trees"]` | standard |  | ['momentum', 'reversal', 'low_vol', 'ridge', 'extra_trees'] |  |
| `ensemble_method` | select | `"dma"` | quick |  | ['dma', 'obs', 'static_bma', 'equal_weight', 'all'] |  |
| `forgetting_factor` | number | `0.97` | standard |  | 0.9..1.0 | {"field": "ensemble_method", "values": ["dma", "all"]} |
| `obs_learning_rate` | number | `0.01` | standard |  | 0.001..0.1 | {"field": "ensemble_method", "values": ["obs", "all"]} |
| `scoring_rule` | select | `"squared_error"` | expert |  | ['squared_error'] |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |
| `embargo_period` | number | `5` | standard | sessions | .. |  |
| `prediction_horizon` | number | `5` | quick | sessions | .. |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `live_model_weight_dashboard` | bar | `charts.live_model_weight_dashboard` | `{"x": "model", "y": ["dma_weight", "obs_weight"]}` | model:string, dma_weight:number, obs_weight:number |
| `model_weight_evolution` | timeseries | `charts.model_weight_evolution` | `{"x": "date", "y": "weight", "series": "model"}` | date:date, model:string, weight:number |
| `dma_vs_obs_vs_static_bma` | table | `charts.dma_vs_obs_vs_static_bma` | `{}` | date:date, ticker:string, dma_prediction:number, obs_prediction:number, static_bma_prediction:number, ensemble_prediction:number, realized:number, model_dispersion_std:number |
| `obs_weight_evolution` | timeseries | `charts.obs_weight_evolution` | `{"x": "date", "y": "weight", "series": "model"}` | date:date, model:string, weight:number |
| `obs_regret_curve` | timeseries | `charts.obs_regret_curve` | `{"x": "date", "y": "obs_regret"}` | date:date, obs_cumulative_loss:number, best_fixed_model_loss:number, obs_regret:number |
| `model_performance_tracker` | bar | `charts.model_performance_tracker` | `{"x": "model", "y": "rmse"}` | model:string, mae:number, rmse:number, directional_accuracy:number |
| `prediction_calibration_curve` | scatter | `charts.prediction_calibration_curve` | `{"x": "mean_prediction", "y": "mean_realized"}` | bucket:number, mean_prediction:number, mean_realized:number, observations:number |
| `current_model_weights` | table | `tables.current_model_weights` | `{}` | model:string, dma_weight:number, obs_weight:number |
| `score_log` | table | `tables.score_log` | `{}` | date:date, ticker:string, dma_prediction:number, obs_prediction:number, static_bma_prediction:number, ensemble_prediction:number, realized:number, model_dispersion_std:number |
| `obs_regret_log` | table | `tables.obs_regret_log` | `{}` | date:date, obs_cumulative_loss:number, best_fixed_model_loss:number, obs_regret:number |
| `model_performance_tracker` | bar | `tables.model_performance_tracker` | `{"x": "model", "y": "rmse"}` | model:string, mae:number, rmse:number, directional_accuracy:number |
| `training_audit` | table | `tables.training_audit` | `{}` | train_rows:number, test_rows:number, label_horizon_sessions:number |

## Feature 08: Multi-Factor IC-Weighted Composite Signal Optimizer

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `factor_library` | select | `"ohlcv_factor_library"` | expert |  | ['ohlcv_factor_library'] |  |
| `weighting_scheme` | select | `"ic_ir"` | quick |  | ['ic', 'ic_ir', 'shrinkage'] |  |
| `orthogonalization` | select | `"gram_schmidt"` | standard |  | ['none', 'gram_schmidt'] |  |
| `walk_forward_window` | select | `252` | standard | sessions | [126, 252, 504] |  |
| `output_signal_construction` | select | `"zscore"` | standard |  | ['long_short_decile', 'zscore', 'signed_rank'] |  |
| `cost_bps` | number | `5` | standard | bps | 0..1000 |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |
| `embargo_period` | number | `5` | standard | sessions | .. |  |
| `prediction_horizon` | number | `5` | quick | sessions | .. |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `ic_weighted_composite_weights` | bar | `charts.ic_weighted_composite_weights` | `{"x": "factor", "y": "weight"}` | date:date, factor:string, weight:number, training_mean_ic:number, training_ic_ir:number |
| `walk_forward_weight_stability` | timeseries | `charts.walk_forward_weight_stability` | `{"x": "date", "y": "weight", "series": "factor"}` | date:date, factor:string, weight:number, training_mean_ic:number, training_ic_ir:number |
| `composite_signal_distribution` | bar | `charts.composite_signal_distribution` | `{"x": "ticker", "y": "score"}` | date:date, ticker:string, score:number |
| `long_short_backtest` | timeseries | `charts.long_short_backtest` | `{"x": "date", "y": "equity"}` | date:date, gross_return:number, net_return:number, turnover:number, cost_fraction:number, equity:number |
| `factor_correlation_heatmap` | heatmap | `charts.factor_correlation_heatmap` | `{"x": "col", "y": "row", "value": "value"}` | row:string, col:string, value:number |
| `factor_weights` | table | `tables.factor_weights` | `{}` | date:date, factor:string, weight:number, training_mean_ic:number, training_ic_ir:number |
| `latest_composite_scores` | table | `tables.latest_composite_scores` | `{}` | date:date, ticker:string, score:number |
| `training_audit` | table | `tables.training_audit` | `{}` | date:date, training_start:date, training_end:date, training_dates:number |

Not supported: server-side persistence of Feature 11 DML APE weights; custom factor CSV ingestion; nested/full-library Fama-MacBeth model-selection research sweep.

## Feature 09: Cointegrated Pairs and Statistical Arbitrage Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `pair_selection` | select | `"engle_granger"` | standard |  | ['engle_granger', 'sector_neutral'] |  |
| `min_correlation` | number | `0.45` | standard | rho | 0.0..1.0 |  |
| `entry_z` | number | `2.0` | quick | z | 0.1..6.0 |  |
| `exit_z` | number | `0.5` | quick | z | 0.0..4.0 |  |
| `hedge_ratio_method` | select | `"kalman"` | standard |  | ['static', 'rolling_ols', 'kalman'] |  |
| `cost_bps` | number | `10` | standard | bps | 0..1000 |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `pair_candidate_leaderboard` | table | `charts.pair_candidate_leaderboard` | `{}` | asset_a:string, asset_b:string, formation_correlation:number, engle_granger_statistic:number, engle_granger_pvalue:number, cointegrated:boolean, formation_observations:number |
| `spread_zscore_timeseries` | timeseries | `charts.spread_zscore_timeseries` | `{"x": "date", "y": "zscore"}` | hedge_ratio:number, intercept:number, spread:number, zscore:number, date:date |
| `cointegration_network` | network | `charts.cointegration_network` | `{"source": "source", "target": "target", "weight": "pvalue"}` | source:string, target:string, pvalue:number |
| `hedge_ratio_path` | timeseries | `charts.hedge_ratio_path` | `{"x": "date", "y": "hedge_ratio"}` | hedge_ratio:number, intercept:number, spread:number, zscore:number, date:date |
| `entry_exit_signal_timeline` | timeseries | `charts.entry_exit_signal_timeline` | `{"x": "date", "y": "zscore", "marker": "direction"}` | date:date, direction:number, zscore:number |
| `pair_backtest_equity` | timeseries | `charts.pair_backtest_equity` | `{"x": "date", "y": "equity"}` | date:date, gross_return:number, net_return:number, turnover:number, cost_fraction:number, equity:number |
| `pair_candidates` | table | `tables.pair_candidates` | `{}` | asset_a:string, asset_b:string, formation_correlation:number, engle_granger_statistic:number, engle_granger_pvalue:number, cointegrated:boolean, formation_observations:number |
| `spread_timeseries` | table | `tables.spread_timeseries` | `{}` | hedge_ratio:number, intercept:number, spread:number, zscore:number, date:date |
| `hedge_ratio` | table | `tables.hedge_ratio` | `{}` | hedge_ratio:number, intercept:number, spread:number, zscore:number, date:date |
| `training_audit` | table | `tables.training_audit` | `{}` | formation_end:date, formation_sessions:number, selected_pair:object |

## Feature 10: Market Microstructure Signal Observatory

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `signal_families` | multiselect | `["amihud", "hl_amihud", "roll_spread", "corwin_schultz_spread", "max_factor", "52w_high", "ivol", "volume_surprise"]` | quick |  | ['amihud', 'hl_amihud', 'roll_spread', 'corwin_schultz_spread', 'max_factor', '52w_high', 'ivol', 'volume_surprise', 'dollar_vol_momentum', 'turnover_rate'] |  |
| `ic_protocol` | select | `"daily_forward_ic"` | expert |  | ['daily_forward_ic'] |  |
| `amihud_window` | select | `21` | standard | sessions | [21, 63] |  |
| `ivol_model` | select | `"market_residual"` | expert |  | ['market_residual'] |  |
| `cost_bps` | number | `10` | standard | bps | 0..1000 |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `250` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `microstructure_ic_leaderboard` | bar | `charts.microstructure_ic_leaderboard` | `{"x": "signal", "y": "mean_daily_ic"}` | signal:string, mean_daily_ic:number, ic_ir:number, observations_dates:number |
| `amihud_illiquidity_surface` | table | `charts.amihud_illiquidity_surface` | `{}` | amihud:number, roll_spread:number, max_factor:number, high_52w_proximity:number, ivol:number, volume_surprise:number, dollar_vol_momentum:number, turnover_rate:number, hl_amihud:number, corwin_schultz_spread:number, ticker:string, sector:string |
| `roll_spread_cross_section` | bar | `charts.roll_spread_cross_section` | `{"x": "ticker", "y": "roll_spread"}` | ticker:string, roll_spread:number |
| `max_factor_distribution` | bar | `charts.max_factor_distribution` | `{"x": "ticker", "y": "max_factor"}` | ticker:string, max_factor:number |
| `52_week_high_proximity_heatmap` | bar | `charts.52_week_high_proximity_heatmap` | `{"x": "ticker", "y": "high_52w_proximity"}` | ticker:string, high_52w_proximity:number |
| `ivol_cross_sectional_sort` | bar | `charts.ivol_cross_sectional_sort` | `{"x": "ticker", "y": "ivol"}` | ticker:string, ivol:number |
| `volume_surprise_signal` | bar | `charts.volume_surprise_signal` | `{"x": "ticker", "y": "volume_surprise"}` | ticker:string, volume_surprise:number |
| `microstructure_signal_correlation_matrix` | heatmap | `charts.microstructure_signal_correlation_matrix` | `{"x": "col", "y": "row", "value": "value"}` | row:string, col:string, value:number |
| `liquidity_regime_monitor` | timeseries | `charts.liquidity_regime_monitor` | `{"x": "date", "y": "mean_amihud"}` | date:date, mean_amihud:number |
| `signal_backtest` | timeseries | `charts.signal_backtest` | `{"x": "date", "y": "equity", "series": "signal"}` | signal:string, date:date, gross_return:number, net_return:number, turnover:number, cost_fraction:number, equity:number |
| `corwin_schultz_spread_cross_section` | bar | `charts.corwin_schultz_spread_cross_section` | `{"x": "ticker", "y": "corwin_schultz_spread"}` | ticker:string, corwin_schultz_spread:number |
| `hl_amihud_vs_standard_amihud` | scatter | `charts.hl_amihud_vs_standard_amihud` | `{"x": "amihud", "y": "hl_amihud", "label": "ticker"}` | ticker:string, amihud:number, hl_amihud:number |
| `amihud_time_surface` | heatmap | `charts.amihud_time_surface` | `{"x": "ticker", "y": "date", "value": "wide: one numeric column per ticker"}` | date:date, AAPL:number, AMZN:number, BA:number, BAC:number, CAT:number, CSCO:number, CVX:number, DIS:number, GE:number, GOOGL:number, HD:number, IBM:number, INTC:number, JNJ:number, JPM:number, KO:number, MCD:number, META:number, MRK:number, MSFT:number, NKE:number, NVDA:number, ORCL:number, PEP:number, PFE:number, PG:number, T:number, VZ:number, WMT:number, XOM:number |
| `microstructure_table` | table | `tables.microstructure_table` | `{}` | amihud:number, roll_spread:number, max_factor:number, high_52w_proximity:number, ivol:number, volume_surprise:number, dollar_vol_momentum:number, turnover_rate:number, hl_amihud:number, corwin_schultz_spread:number, ticker:string, sector:string |
| `ic_leaderboard` | table | `tables.ic_leaderboard` | `{}` | signal:string, mean_daily_ic:number, ic_ir:number, observations_dates:number |
| `amihud_time_surface` | heatmap | `tables.amihud_time_surface` | `{"x": "ticker", "y": "date", "value": "wide: one numeric column per ticker"}` | date:date, AAPL:number, AMZN:number, BA:number, BAC:number, CAT:number, CSCO:number, CVX:number, DIS:number, GE:number, GOOGL:number, HD:number, IBM:number, INTC:number, JNJ:number, JPM:number, KO:number, MCD:number, META:number, MRK:number, MSFT:number, NKE:number, NVDA:number, ORCL:number, PEP:number, PFE:number, PG:number, T:number, VZ:number, WMT:number, XOM:number |

Not supported: true bid-ask spread from quote data; order-flow imbalance; signed volume; intraday Lee-Ready classification.

## Feature 11: Conditional Factor Association Engine

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `factor_library` | select | `"ohlcv_factor_library"` | expert |  | ['ohlcv_factor_library'] |  |
| `dml_folds` | select | `5` | standard | folds | [3, 5] |  |
| `nuisance_model` | select | `"ridge"` | standard |  | ['ridge', 'elastic_net', 'random_forest', 'lightgbm'] |  |
| `rolling_window` | select | `252` | standard | sessions | [126, 252, 504] |  |
| `significance_threshold` | select | `0.95` | standard | probability | [0.9, 0.95, 0.99] |  |
| `spurious_factor_action` | select | `"flag_only"` | expert |  | ['flag_only'] |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `120` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |
| `embargo_period` | number | `5` | standard | sessions | .. |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `conditional_ape_leaderboard` | bar | `charts.conditional_ape_leaderboard` | `{"x": "factor", "y": "dml_ape", "lower": "lower", "upper": "upper"}` | factor:string, dml_ape:number, dml_se:number, ape_t_stat:number, lower:number, upper:number, univariate_slope:number, hc3_se:number, hc3_t_stat:number, adjustment_vs_univariate_slope:number, classification:string, signed_weight:number |
| `ape_time_series` | timeseries | `charts.ape_time_series` | `{"x": "date", "y": "ape", "series": "factor"}` | date:date, factor:string, ape:number, se:number |
| `adjustment_vs_univariate_slope` | bar | `charts.adjustment_vs_univariate_slope` | `{"x": "factor", "y": "adjustment_vs_univariate_slope"}` | factor:string, dml_ape:number, dml_se:number, ape_t_stat:number, lower:number, upper:number, univariate_slope:number, hc3_se:number, hc3_t_stat:number, adjustment_vs_univariate_slope:number, classification:string, signed_weight:number |
| `robust_inference_table` | table | `charts.robust_inference_table` | `{}` | factor:string, dml_ape:number, dml_se:number, univariate_slope:number, hc3_se:number |
| `conditional_ape_table` | table | `tables.conditional_ape_table` | `{}` | factor:string, dml_ape:number, dml_se:number, ape_t_stat:number, lower:number, upper:number, univariate_slope:number, hc3_se:number, hc3_t_stat:number, adjustment_vs_univariate_slope:number, classification:string, signed_weight:number |
| `unidentified_factors` | table | `tables.unidentified_factors` | `{}` |  |
| `robust_inference_table` | table | `tables.robust_inference_table` | `{}` | factor:string, dml_ape:number, dml_se:number, univariate_slope:number, hc3_se:number |

Not supported: Optuna tuning for nuisance models; server-side auto-prune into Feature 8.

## Feature 12: Sequence Alpha: Patch and Inverted Transformers, LSTM and MLP

### Inputs

| key | type | default | level | unit | range/options | depends_on |
|---|---|---|---|---|---|---|
| `symbols` | ticker_list | `null` | quick |  |  |  |
| `architectures` | multiselect | `["patchtst"]` | quick |  | ['patchtst', 'itransformer', 'lstm', 'mlp'] |  |
| `sequence_length` | number | `63` | standard | sessions | 5..252 |  |
| `patch_length` | select | `21` | expert | sessions | [5, 10, 21] | {"field": "architectures", "values": ["patchtst"]} |
| `transformer_depth` | number | `2` | expert | layers | 1..4 | {"field": "architectures", "values": ["patchtst", "itransformer"]} |
| `attention_heads` | select | `4` | expert | heads | [2, 4, 8] | {"field": "architectures", "values": ["patchtst", "itransformer"]} |
| `dropout_rate` | number | `0.1` | expert | probability | 0.0..0.5 |  |
| `epochs` | number | `15` | standard | epochs | 1..100 |  |
| `prediction_horizon` | select | `5` | quick | sessions | [1, 5, 21, 63] |  |
| `universe` | select | `"default"` | expert |  | ['default', 'all'] |  |
| `frequency` | select | `"daily"` | expert |  | ['daily'] |  |
| `lookback_days` | number | `756` | quick | sessions | 90..10000 |  |
| `max_symbols` | number | `20` | standard | symbols | 1..5000 |  |
| `as_of_date` | date | `null` | standard | date |  |  |
| `embargo_period` | number | `5` | standard | sessions | .. |  |
| `random_seed` | number | `7` | expert |  | 0..2147483647 |  |

### Outputs

| id | type | path | encoding | columns |
|---|---|---|---|---|
| `architecture_comparison` | bar | `charts.architecture_comparison` | `{"x": "architecture", "y": "spearman_ic"}` | architecture:string, spearman_ic:number, monthly_ic_ir:number, mae:number, training_time_seconds:number, train_samples:number, test_samples:number |
| `monthly_oos_ic` | timeseries | `charts.monthly_oos_ic` | `{"x": "month", "y": "ic", "series": "architecture"}` | architecture:string, month:string, ic:number |
| `training_loss` | timeseries | `charts.training_loss` | `{"x": "epoch", "y": "training_mse", "series": "architecture"}` | architecture:string, epoch:number, training_mse:number |
| `architecture_comparison` | bar | `tables.architecture_comparison` | `{"x": "architecture", "y": "spearman_ic"}` | architecture:string, spearman_ic:number, monthly_ic_ir:number, mae:number, training_time_seconds:number, train_samples:number, test_samples:number |

Not supported: TFT, Mamba, integrated gradients and trained attention visualizations are not implemented and are not selectable.
