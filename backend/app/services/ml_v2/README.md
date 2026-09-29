# ML V2 Backend Implementation Report

Last updated: 2026-06-11

## Current Pass Update — Fast Non-Research Additions From Optional Gap List

- [x] Added F02 `exact_shap_sample_importance`: exact TreeSHAP when supported, capped to a small latest-book sample so it remains realtime-safe.
- [x] Added F07 `distributional_uncertainty_panel`: live prediction band from model dispersion plus realized residual error.
- [x] Added F08 `forward_selection_fama_macbeth`: lightweight date-wise cross-sectional forward-selection screen.
- [x] Added F11 `robust_inference_table`: HC3 robust slope/standard-error/t-stat diagnostic beside DML APE.
- [ ] Optuna Bayesian tuning was not added to realtime because trial loops multiply runtime.
- [ ] PPO rebalancing / PPO pair thresholds were not added to realtime because they require training episodes.
- [ ] GINN/PatchTST/iTransformer/TFT/Mamba training was not added to realtime because it requires model training/checkpointing.
- [ ] Full-universe exact TreeSHAP remains research-only; only the capped sample is live.
- [ ] True tick/order-book microstructure remains blocked by missing tick/quote data.

## Current Pass Update — Audit Gap Closure and Speed

- [x] Added `core/performance.py` with disk-cache helpers, cached Ledoit-Wolf covariance, vectorized IC computation, and shared thread-pool imports.
- [x] Added cross-sectional feature-panel disk caching keyed by universe/date/frequency/horizon.
- [x] Parallelized per-ticker feature-panel construction with `ThreadPoolExecutor`.
- [x] Added Corwin-Schultz spread, high-low Amihud, dollar-volume momentum, turnover rate, max factor, 52-week-high proximity, and safe volume z-score to the shared ML feature panel.
- [x] Expanded `numeric_xy()` so F01/F02/F07/F08/F11 can consume the new microstructure and price-action features.
- [x] Added F02 long-side attribution output: `shap_long_side_importance`.
- [x] Added F02 short-side attribution output: `shap_short_side_importance`.
- [x] Enriched F04 LightGBM CQR with volatility percentile rank, high-vol regime flag, signal strength, realized-tail rank, and signed label strength features.
- [x] Added F08 pairwise higher-order interaction screening.
- [x] Added F08 output keys: `higher_order_interaction_table` and `interaction_table`.
- [x] Hardened F10 microstructure backtests against NaN-only or invalid signal universes.
- [x] Vectorized F10 IC leaderboard calculation over stacked forward returns.
- [x] Guarded F11 rolling APE time-series against short growing panels.
- [x] Cached the F05 Ledoit-Wolf covariance path for repeated optimizer runs.
- [ ] Exact TreeSHAP values remain research-only; current F02 side attribution is a deterministic model-importance proxy split by the current long/short prediction book.
- [ ] True tick/order-book microstructure remains unavailable in repo data; F10 continues to use daily OHLCV estimators.

## Current Pass Update — CatBoost, CQR, HMM, OBS, Kalman

- [x] Installed CatBoost in the active Python user environment.
- [x] Added CatBoost to F02 model family with `CatBoostRegressor(loss_function="RMSE", verbose=False, allow_writing_files=False)`.
- [x] Replaced F04 volatility-only interval proxy with LightGBM lower/upper quantile CQR and chronological conformal calibration.
- [x] Added F04 CQR coverage audit from realized interval coverage over time.
- [x] Replaced F06 GMM-default regime engine with Gaussian HMM Baum-Welch fitting through `hmmlearn`.
- [x] Added deterministic F06 HMM state ordering by descending realized mean return.
- [x] Kept F06 Gaussian Mixture as an explicit fallback if HMM fitting fails.
- [x] Replaced F07 OBS metadata proxy with simplex-projected online convex updates on Gaussian negative log-score.
- [x] Added F07 OBS weight evolution and regret curve outputs.
- [x] Replaced F09 flat neutral hedge-ratio placeholder with a random-walk beta Kalman filter.
- [x] F09 spread/z-score path now uses Kalman residuals for the top pair when available.
- [ ] Student-t / skew-t HMM emissions remain research-only because they require custom emission likelihood EM/MLE beyond `hmmlearn`.
- [ ] F09 Johansen basket testing and PPO threshold training remain research-only because they are expensive candidate-basket/state-policy jobs.

## Current Pass Update — Missing Implementations Pack

- [x] Added Garman-Klass realized volatility estimator.
- [x] Added Yang-Zhang realized volatility estimator.
- [x] Added bipower variation jump decomposition.
- [x] Added Corwin-Schultz spread estimator.
- [x] Added high-low Amihud liquidity estimator.
- [x] Added EWMA covariance estimator.
- [x] Added RMT-cleaned covariance estimator.
- [x] Added NCO weights path for F05.
- [x] Added Engle-Granger ADF p-values to F09 pair selection.
- [x] Added cross-fitted DML helper for F11.
- [x] Added IC decay ratio and walk-forward IC weights for F08.
- [x] Added RF-vs-HMM ensemble agreement diagnostics for F06.
- [x] Replaced F03/F05/F08/F09/F10/F11 engine paths with the upgraded implementations.
- [x] Smoke-tested F03/F05/F06/F08/F09/F10/F11 successfully.
- [ ] True tick/order-book microstructure remains impossible without quote/trade data.
- [ ] PPO rebalancing and PPO stat-arb threshold policies remain research-mode jobs.

## Current Pass Update — Feature Files Expanded

- [x] Replaced 10-line feature stubs with full per-feature modules.
- [x] Every `feature_01.py` through `feature_12.py` now declares:
  - [x] `FEATURE_ID`
  - [x] `FEATURE_TITLE`
  - [x] `DEFAULTS`
  - [x] `ALIASES`
  - [x] `INPUT_CONTRACT`
  - [x] `OUTPUT_CONTRACT`
  - [x] `RESEARCH_ONLY`
  - [x] `IMPLEMENTATION_NOTES`
  - [x] `normalize_feature_payload()`
  - [x] `run()`
- [x] Added `merge_feature_contract()` to `core/analytics.py` so every response carries frontend/API-ready metadata.
- [x] Added `normalize_payload()` to `core/analytics.py` so each feature handles aliases/defaults/research-mode promotion consistently.
- [x] Kept reusable math in `core/analytics.py` to avoid duplicated statistical bugs.
- [x] Did not run the smoke-test suite in this pass because the explicit instruction was "dont test this time just code".

Feature file sizes after expansion:

- [x] F01: 98 lines
- [x] F02: 65 lines
- [x] F03: 57 lines
- [x] F04: 61 lines
- [x] F05: 65 lines
- [x] F06: 64 lines
- [x] F07: 62 lines
- [x] F08: 63 lines
- [x] F09: 61 lines
- [x] F10: 61 lines
- [x] F11: 65 lines
- [x] F12: 68 lines
- [x] Shared analytics: 1,122 lines

## Scope

ML V2 was built as a backend-only service package following the V2 module shape used by Factors, Volatility, and PCA:

- `registry.py` exposes feature metadata and `run_feature(feature_id, payload)`.
- `core/data_loader.py` reads local repo data only.
- `core/analytics.py` owns shared computations and output key generation.
- `core/data_fetcher.py` documents append-only fetch plans for optional missing data. It does not fetch automatically.
- `features/feature_01.py` through `features/feature_12.py` are individual runners.

No API route or frontend wiring was added.

## Data Inventory Used

- [x] Daily master universe parquet: `backend/data/market_universe.parquet`
- [x] Hourly parquet, preferring larger research export when present
- [x] Fundamentals metadata parquet: `backend/data/fundamentals/master_fundamentals.parquet`
- [x] Macro/FRED-style regime parquet: `factors/data/processed/category7_macro_regime.parquet`
- [x] Ken French FF3/FF5/Momentum daily CSVs in `factors/data/raw/fama_french`
- [ ] True tick-level bid/ask/order-book data is not present. Feature 10 uses accepted daily OHLCV estimators: Amihud, Roll, 52-week high proximity, IVOL, volume surprise.
- [ ] True earnings/event calendar data is not present. Feature 12 leaves earnings-cycle future inputs as future data-fetch scope.
- [x] CatBoost, XGBoost, LightGBM, sklearn tree models, shap, hmmlearn, arch, and torch are installed or supported when present.

Observed local inventory at implementation time:

- Daily rows: 10,760,520
- Daily tickers: 4,154
- Hourly rows: 1,148,817
- Hourly tickers: 272
- Macro rows: 12,237
- Fama/French rows: 26,190

## Feature Checklist

### F01 — Purged K-Fold and CPCV Engine

- [x] Purged K-Fold with embargo
- [x] CPCV combinatorial path generation
- [x] Naive vs purged leakage-bias comparison
- [x] Deflated Sharpe Ratio output
- [x] Backtest path envelope output
- [x] Embargo sensitivity table/chart
- [x] Per-fold performance table
- [x] Fractional uniqueness proxy for overlapping labels
- [x] PBO output
- [x] DSR + PBO joint decision panel

Output keys:

- `cpcv_sharpe_distribution`
- `purged_vs_naive_cv_comparison`
- `deflated_sharpe_ratio`
- `backtest_paths_chart`
- `embargo_sensitivity`
- `model_performance_vs_embargo`
- `probability_of_backtest_overfitting`
- `dsr_pbo_joint_decision`
- `per_fold_performance`
- `label_fractional_uniqueness_audit`
- `cpcv_path_metrics`

### F02 — Gradient-Boosted Alpha Engine with Attribution

- [x] Ridge, Random Forest, Extra Trees, Gradient Boosting
- [x] XGBoost when installed
- [x] LightGBM when installed
- [x] CatBoost when installed
- [x] IC-weighted ensemble weights
- [x] Current prediction rank table
- [x] Feature attribution table using exact model importances / coefficient magnitude
- [x] Long-side and short-side attribution proxy tables
- [x] Capped exact TreeSHAP sample importance when supported by the fitted model
- [x] IC decay profile across horizons
- [x] Prediction distribution and top-bottom spread

Output keys:

- `prediction_rank_table`
- `shap_feature_importance`
- `shap_long_side_importance`
- `shap_short_side_importance`
- `exact_shap_sample_importance`
- `model_ic_leaderboard`
- `ic_weighted_ensemble_weights`
- `ic_decay_profile`
- `prediction_distribution`
- `top_bottom_signal_spread`
- `current_predictions`
- `model_performance`
- `feature_importance`
- `training_audit`

### F03 — Multi-Horizon Volatility Forecasting Engine

- [x] HAR-Ridge forecast
- [x] HAR-GBM forecast
- [x] Close-to-close realized volatility
- [x] Garman-Klass realized volatility
- [x] Yang-Zhang realized volatility
- [x] Bipower jump component decomposition
- [x] Forecast error distribution
- [x] Volatility term structure
- [x] Realized vs predicted panel
- [x] Confidence interval proxy from empirical forecast error
- [x] Macro overlay from local category7 macro parquet
- [ ] GINN neural architecture is not trained here; this pass provides live HAR/ML forecasts from local data

Output keys:

- `vol_forecast_panel`
- `forecast_error_distribution`
- `vol_term_structure`
- `realized_vs_predicted`
- `model_confidence_intervals`
- `vix_yield_macro_overlay`
- `jump_component_decomposition`
- `realized_vol_estimator_comparison`
- `forecast_tournament`
- `forecast_rows`

### F04 — Meta-Labeling and Triple-Barrier Label Engine

- [x] Profit-taking / stop-loss / max-holding-period labels
- [x] Label distribution
- [x] Event outcome timeline
- [x] Meta-label probability proxy
- [x] LightGBM quantile CQR lower/upper bands
- [x] Chronological conformal calibration residual adjustment
- [x] Coverage audit
- [x] Barrier parameter table

Output keys:

- `triple_barrier_label_distribution`
- `event_outcome_timeline`
- `meta_label_probability_distribution`
- `cqr_interval_width_distribution`
- `cqr_coverage_audit`
- `barrier_hit_path_examples`
- `label_audit`
- `barrier_parameters`

### F05 — HRP Portfolio Optimizer

- [x] Ledoit-Wolf covariance estimate
- [x] OAS covariance estimate
- [x] EWMA covariance estimate
- [x] RMT-cleaned covariance estimate
- [x] Hierarchical clustering linkage and dendrogram records
- [x] HRP recursive bisection weights
- [x] NCO weights path
- [x] HRP vs equal-weight rolling Sharpe
- [x] Quasi-diagonalized covariance heatmap
- [x] Risk contribution decomposition
- [x] Tail-dependence proxy matrix
- [x] Rolling cluster stability proxy
- [x] Black-Litterman posterior return vector proxy
- [x] BL vs pure HRP weight comparison
- [ ] PPO RL rebalancing is not trained in this pass; output is a research-mode placeholder metric clearly marked in metadata

Output keys:

- `cluster_dendrograms`
- `hrp_weight_vector`
- `hrp_vs_nco_vs_markowitz_equal_weight`
- `rl_rebalancing_vs_fixed_schedule`
- `quasi_diagonalized_covariance_heatmap`
- `risk_contribution_decomposition`
- `tail_dependence_matrix`
- `rolling_cluster_stability`
- `black_litterman_posterior_return_vector`
- `bl_vs_pure_hrp_weight_comparison`
- `view_attribution_backtest`
- `covariance_estimator_comparison`
- `hrp_weights`
- `risk_contribution`

### F06 — Market Regime Detection and Strategy Routing

- [x] Gaussian HMM regime probability engine using Baum-Welch
- [x] Deterministic regime labels ordered by descending mean return
- [x] Gaussian Mixture fallback if HMM fitting fails
- [x] Transition heatmap
- [x] Ensemble-vs-HMM compatible comparison output
- [x] RF-vs-HMM Viterbi state agreement diagnostic
- [x] PC1 structural break monitor
- [x] Regime-conditional factor performance
- [x] Strategy performance attribution by regime
- [x] Regime-conditional volatility term structure
- [x] Random graph systemic risk indicator
- [ ] Student-t/skew-t emission HMMs remain research-only; Gaussian HMM is live

Output keys:

- `regime_probability_time_series`
- `regime_transition_heatmap`
- `ensemble_vs_hmm_comparison`
- `pc1_structural_break_monitor`
- `regime_conditional_factor_performance`
- `strategy_performance_attribution_by_regime`
- `regime_conditional_vol_term_structure`
- `random_graph_systemic_risk_indicator`
- `transition_matrix`
- `current_regime_probabilities`

### F07 — Bayesian Online Learning and DMA Engine

- [x] Candidate model library from momentum, reversal, low-vol, Ridge, Extra Trees
- [x] Sequential Bayesian/DMA-style model weight updates
- [x] Live model weight dashboard
- [x] Weight evolution
- [x] DMA/static score log
- [x] Pruning log
- [x] Epistemic/aleatoric diagnostic proxy
- [x] Forgetting-factor half-life sensitivity
- [x] OBS simplex-projected online convex optimizer
- [x] OBS weight evolution
- [x] OBS regret curve
- [x] Realtime distributional uncertainty panel from model dispersion

Output keys:

- `live_model_weight_dashboard`
- `model_weight_evolution`
- `dma_vs_obs_vs_static_bma`
- `model_pruning_log`
- `obs_weight_evolution`
- `obs_regret_curve`
- `distributional_uncertainty_panel`
- `epistemic_vs_aleatoric_uncertainty`
- `forgetting_factor_sensitivity`
- `current_model_weights`
- `score_log`

### F08 — IC-Weighted Composite Signal Optimizer

- [x] Factor IC table
- [x] IC-weighted composite weights
- [x] Sector-neutralized factor inputs
- [x] IC decay ratio by factor
- [x] Factor correlation heatmap
- [x] Gram-Schmidt-style orthogonalization impact table
- [x] Walk-forward weight stability
- [x] Latest composite scores
- [x] Long-short backtest
- [x] Factor turnover proxy
- [x] Higher-order pairwise interaction screen
- [x] Realtime forward-selection Fama-MacBeth-style screen
- [ ] DML APE replacement is not server-persisted yet; Feature 11 emits APE weights that can be routed later

Output keys:

- `ic_weighted_composite_weights`
- `factor_correlation_heatmap`
- `orthogonalization_impact`
- `walk_forward_weight_stability`
- `composite_signal_distribution`
- `long_short_backtest`
- `factor_turnover_table`
- `higher_order_interaction_table`
- `interaction_table`
- `forward_selection_fama_macbeth`
- `factor_ic_table`
- `latest_composite_scores`
- `orthogonalization_table`

### F09 — ML-Enhanced Pairs and Stat Arb Engine

- [x] Pair candidate leaderboard
- [x] Correlation/OU half-life screen
- [x] Engle-Granger ADF p-value scoring
- [x] Spread z-score time series
- [x] Cointegration-style network records
- [x] Random-walk beta Kalman hedge-ratio path for the top pair
- [x] Kalman residual spread and residual z-score path
- [x] Entry/exit signal timeline
- [x] Pair backtest equity
- [x] RL threshold policy metadata
- [ ] Full Johansen basket testing and RL threshold training are not run in realtime pass

Output keys:

- `pair_candidate_leaderboard`
- `spread_zscore_timeseries`
- `cointegration_network`
- `kalman_hedge_ratio_path`
- `entry_exit_signal_timeline`
- `pair_backtest_equity`
- `rl_threshold_policy`
- `adf_pvalue_distribution`
- `pair_candidates`
- `spread_timeseries`

### F10 — Market Microstructure Signal Observatory

- [x] Microstructure IC leaderboard
- [x] Amihud illiquidity surface
- [x] High-low Amihud liquidity surface
- [x] Roll spread cross-section
- [x] Corwin-Schultz spread cross-section
- [x] Dollar-volume momentum
- [x] Turnover rate
- [x] MAX factor distribution
- [x] 52-week high proximity heatmap
- [x] IVOL cross-sectional sort
- [x] Volume surprise signal
- [x] Signal correlation matrix
- [x] Liquidity regime monitor
- [x] Signal backtest
- [ ] Tick/order-book/bid-ask data is not in repo; daily OHLCV microstructure estimators are used honestly

Output keys:

- `microstructure_ic_leaderboard`
- `amihud_illiquidity_surface`
- `roll_spread_cross_section`
- `max_factor_distribution`
- `52_week_high_proximity_heatmap`
- `ivol_cross_sectional_sort`
- `volume_surprise_signal`
- `microstructure_signal_correlation_matrix`
- `liquidity_regime_monitor`
- `signal_backtest`
- `corwin_schultz_spread_cross_section`
- `hl_amihud_vs_standard_amihud`
- `microstructure_table`
- `ic_leaderboard`

### F11 — Causal Factor Discovery Engine

- [x] K-fold cross-fitted double/debiased residualization with cross-sectional factors
- [x] APE leaderboard
- [x] Confounding bias decomposition
- [x] APE time series
- [x] Spurious factor detection log
- [x] Nuisance model R² table
- [x] HC3 robust inference diagnostic table
- [x] Causal factor network
- [x] DML vs OLS backtest comparison
- [x] Rolling spurious fraction
- [ ] LightGBM nuisance models are not defaulted in realtime; Ridge nuisance is used for speed and stability

Output keys:

- `causal_ape_leaderboard`
- `confounding_bias_decomposition`
- `ape_time_series`
- `spurious_factor_detection_log`
- `nuisance_model_r2_table`
- `robust_inference_table`
- `causal_factor_network`
- `dml_vs_ols_backtest_comparison`
- `rolling_spurious_fraction`
- `causal_ape_table`
- `causal_network_edges`
- `robust_inference_table`

### F12 — Deep Sequence Alpha Engine

- [x] Architecture comparison table
- [x] Multi-horizon IC decay panel
- [x] PatchTST-style attention heatmap diagnostic
- [x] iTransformer-style cross-sectional attention map
- [x] TFT-style variable selection weights
- [x] Integrated-gradients-style attribution table
- [x] PatchTST vs iTransformer regime split
- [x] Ensemble contribution chart
- [x] Compute cost vs IC gain table
- [ ] Full Transformer/PatchTST/iTransformer/TFT training is not run in this backend pass; outputs are deterministic sequence diagnostics over local data and clearly marked in metadata

Output keys:

- `architecture_comparison_ic_table`
- `multi_horizon_ic_decay_panel`
- `patchtst_attention_heatmap`
- `itransformer_cross_sectional_attention_map`
- `tft_variable_selection_weights`
- `integrated_gradients_attribution`
- `patchtst_vs_itransformer_regime_split`
- `ensemble_contribution_chart`
- `compute_cost_vs_ic_gain_table`
- `architecture_comparison`
- `variable_selection`

## Verification

- [x] `python3 -m compileall -q backend/app/services/ml_v2`
- [x] Feature smoke run for F01-F12 with local daily parquet and compact 14-symbol universe
- [x] Every feature returned `status: ok`
- [x] Every feature returned non-empty `summary_cards`
- [x] Every feature returned chart/table dictionaries with stable frontend-ready keys

## Honest Remaining Work — What Is Not Done, Why, And How To Finish

This section is intentionally blunt. The backend is usable as a local-data ML module, but several items from the full institutional spec require either missing data, missing dependencies, GPU/research jobs, or API persistence between modules.

### Platform Wiring

- [ ] **API route not wired**
  - **Reason:** User explicitly asked for backend module construction only, not API wiring.
  - **Possible:** Yes, straightforward.
  - **What to do:** Add an API endpoint mirroring Factors/PCA shape: route receives `feature_id` and payload, calls `app.services.ml_v2.registry.run_feature(feature_id, payload)`, returns the JSON response.

- [ ] **Frontend pages not created**
  - **Reason:** User asked for backend first.
  - **Possible:** Yes.
  - **What to do:** Create `frontend/src/components/ml-v2/customPagePrimitives.jsx`, `registry.js`, `/labs/ml-v2/page.js`, `/layout.js`, and individual `/feature-01/page.js` through `/feature-12/page.js`, using the output contracts now embedded in each response.

- [ ] **Cross-feature server-side persistence not implemented**
  - **Reason:** ML F08 wants DML APE weights from F11, F07 wants model libraries from F02/F03/F12, F06 wants strategy routing into other modules. That needs a server-side workspace/cache layer.
  - **Possible:** Yes.
  - **What to do:** Add an `ml_v2/workspace_store.py` backed by SQLite/parquet/Redis later. Persist `latest-summary`, `latest-output`, and typed feature artifacts by `{workspace_id, feature_id, run_id}`.

### Missing Data Constraints

- [ ] **True tick-level bid/ask/order-book microstructure**
  - **Affected feature:** F10
  - **Reason:** Repo has daily and hourly OHLCV, but not quote-level bid/ask, signed trades, order book depth, or exchange message data.
  - **Possible:** Only if new data is added.
  - **Current implementation:** Uses honest daily OHLCV estimators: Amihud, Roll spread proxy, MAX, 52-week high proximity, IVOL, volume surprise.
  - **What to do:** Add a `tick_quotes.parquet` or `quotes_l1.parquet` append-only loader with columns: `ticker`, `timestamp`, `bid`, `ask`, `bid_size`, `ask_size`, `trade_price`, `trade_size`, `exchange`. Then implement quoted/effective spread, order imbalance, VPIN, signed volume, Lee-Ready classification.

- [ ] **True earnings/event calendar**
  - **Affected feature:** F12
  - **Reason:** TFT known-future inputs include days to earnings; repo does not have clean earnings calendar data.
  - **Possible:** Yes with free/public or yfinance calendar fetch, but not currently materialized.
  - **Current implementation:** Uses date-cycle-compatible diagnostics only; no fake earnings calendar.
  - **What to do:** Add append-only `events_calendar.parquet` with `ticker`, `event_date`, `event_type`, `source`, then wire days-to-event as TFT/static known-future input.

- [ ] **External user model upload / custom CSV upload**
  - **Affected features:** F01, F02, F08, F11
  - **Reason:** No API/file-upload layer exists yet.
  - **Possible:** Yes after API wiring.
  - **What to do:** Add an upload endpoint that validates schema and stores artifacts under a workspace/run id. Never execute arbitrary pickle models directly; require a safe sklearn-compatible spec or ONNX-style model boundary.

### Missing Or Optional Dependencies

- [ ] **Optuna Bayesian tuning**
  - **Affected features:** F02, F11, F12
  - **Reason:** Tuning is intentionally not run in realtime because it can multiply runtime by trial count.
  - **Possible:** Yes, research mode.
  - **What to do:** Add `optuna` dependency, create a research-mode job path with `trial_count`, timeout, cached results, and audit trail.

### Feature-Specific Gaps

- [ ] **F01 — user-supplied event end-times and exact fractional uniqueness**
  - **Reason:** Exact uniqueness requires label start/end timestamps, especially for non-uniform event bars. The backend currently infers overlap from prediction horizon.
  - **Possible:** Yes after file/API ingestion.
  - **What to do:** Accept `event_times` table with `event_id`, `start_time`, `end_time`, `ticker`; compute concurrency and fractional uniqueness exactly per Lopez de Prado.

- [ ] **F02 — exact TreeSHAP for every prediction at full universe scale**
  - **Reason:** SHAP is installed, but exact per-row TreeSHAP across thousands of tickers can be expensive and should be a research-mode toggle.
  - **Possible:** Yes.
  - **What to do:** Add `exact_shap=true` path for tree models; cap realtime rows, cache SHAP arrays by model hash and data window.

- [ ] **F03 — GINN neural volatility model**
  - **Reason:** Current implementation uses live HAR-Ridge/HAR-GBM forecasts. GINN requires a neural training loop and model artifact persistence.
  - **Possible:** Yes, research mode.
  - **What to do:** Add PyTorch GINN model class, train/validation split, early stopping, cached model artifact, and forecast outputs beside HAR models.

- [x] **F04 — full CQR with quantile LightGBM**
  - **Status:** Implemented with lower/upper LightGBM quantile models, chronological calibration residuals, interval width, and empirical coverage audit.
  - **Remaining refinement:** Add purged K-fold calibration when event timestamps are persisted.

- [ ] **F05 — PPO reinforcement-learning rebalancing**
  - **Reason:** PPO needs a simulated portfolio environment, training episodes, reward accounting, and cached policy artifacts.
  - **Possible:** Yes, research mode, but not a realtime calculation.
  - **What to do:** Add HRP environment with state = correlation/eigenvalue features, action = rebalance/no rebalance or allocation adjustment, reward = net Sharpe/turnover penalty, then train PPO via stable-baselines3 or a lightweight PyTorch implementation.

- [x] **F05 — NCO variant**
  - **Status:** Implemented nested clustered weights with HRP within clusters and HRP across clusters.
  - **Remaining refinement:** HERC and full nested CV model selection can be added as research-mode variants.

- [x] **F06 — Gaussian Baum-Welch HMM**
  - **Status:** Implemented with `hmmlearn.GaussianHMM`, state probabilities, transition matrix, and state diagnostics.
  - **Remaining refinement:** Student-t/skew-t emissions require custom EM/MLE and remain research-only.

- [x] **F06 — ensemble-HMM tree voting diagnostic**
  - **Status:** Implemented RF-vs-HMM Viterbi state agreement and lead-time proxy.
  - **Remaining refinement:** User-labeled external regime ranges can turn this diagnostic into supervised regime classification.

- [x] **F07 — true OBS optimizer**
  - **Status:** Implemented projected gradient on the simplex using Gaussian negative log-score, with OBS-vs-DMA-vs-static predictions and regret curve.
  - **Remaining refinement:** Add richer predictive distributions per model for calibrated uncertainty decomposition.

- [ ] **F07 — distributional epistemic/aleatoric uncertainty**
  - **Reason:** Requires each model to output predictive distributions or bootstrapped prediction intervals, not just point forecasts.
  - **Possible:** Yes.
  - **What to do:** Add quantile LightGBM, bootstrap Ridge, and ensemble variance decomposition.

- [ ] **F08 — DML APE replacement weights from F11**
  - **Reason:** F11 emits APE weights, but F08 does not yet read persisted F11 artifacts.
  - **Possible:** Yes after workspace persistence.
  - **What to do:** Store F11 `causal_ape_table`; in F08, if `weighting_scheme=dml_ape`, load latest compatible F11 run and replace IC weights with positive significant APE weights.

- [ ] **F08 — Forward Selection Fama-MacBeth**
  - **Reason:** Not yet implemented in realtime path.
  - **Possible:** Yes.
  - **What to do:** Implement date-by-date cross-sectional regressions, forward factor inclusion by OOS IC/t-stat, and compare selected library vs full composite.

- [x] **F09 — Engle-Granger ADF pair scoring**
  - **Status:** Implemented ADF p-value scoring on candidate pair spreads, cointegrated flag, and ADF distribution output.
  - **Remaining refinement:** Johansen basket tests remain research-mode because they are expensive across large candidate universes.

- [x] **F09 — Kalman dynamic hedge ratio**
  - **Status:** Implemented state-space model `y_t = beta_t x_t + eps_t` with random-walk beta, Kalman filter update, hedge-ratio path, residual, and residual z-score.
  - **Remaining refinement:** Estimate Q/R by MLE per pair and cache parameters by pair/window.

- [ ] **F09 — PPO threshold optimizer**
  - **Reason:** Requires training episodes across historical pair signals.
  - **Possible:** Yes, research mode.
  - **What to do:** Create pair-trading environment with state = z-score, volatility, half-life, drawdown; action = enter/exit/hold; reward = net P&L with turnover costs.

- [ ] **F10 — true intraday microstructure**
  - **Reason:** Hourly data exists, but not true quote/trade-level data. Hourly OHLCV is not enough for signed volume/order-flow imbalance.
  - **Possible:** Only with more granular data.
  - **What to do:** Materialize tick/quote parquet and implement true spread/imbalance metrics.

- [ ] **F11 — LightGBM nuisance models by default**
  - **Reason:** Current default uses Ridge nuisance models for speed and deterministic behavior. LightGBM nuisance is more powerful but heavier.
  - **Possible:** Yes.
  - **What to do:** Add `nuisance_model=lightgbm_research`, cross-fit K folds, cache nuisance predictions, compute robust standard errors.

- [x] **F11 — fast heteroskedasticity-robust inference**
  - **Done:** Added HC3 robust univariate slope/SE/t-stat output as `robust_inference_table`.
  - **Still research-only:** Newey-West and clustered standard errors by date/sector because they need a more explicit panel regression design and clustering policy.

- [ ] **F12 — full PatchTST / iTransformer / TFT training**
  - **Reason:** Requires deep training loops, GPU-aware batching, checkpointing, early stopping, and cached model artifacts.
  - **Possible:** Yes, research mode.
  - **What to do:** Add PyTorch datasets over `{ticker, date, sequence}`, implement architecture classes or use a vetted time-series library, train with purged validation, persist model and attention tensors.

- [ ] **F12 — Mamba sequence model**
  - **Reason:** Not implemented; may require extra dependency and careful sequence batching.
  - **Possible:** Yes if dependency is installed and GPU/runtime is acceptable.
  - **What to do:** Add optional Mamba model path behind `compute_mode=research`, compare IC against PatchTST/iTransformer/TFT.

## What Is Truly Not Possible With Current Repo Data

- [ ] **True order-book analytics** are not possible without bid/ask/order-book/tick data.
- [ ] **True event/earnings-aware TFT known-future inputs** are not possible without an events calendar.
- [x] **CatBoost outputs** are possible and wired when `catboost` is installed.
- [ ] **Production deep model claims** are not honest until trained model artifacts are generated and cached.

Everything else is possible with current repo data and engineering time. The main next engineering step is not more math; it is adding research-mode job orchestration, artifact persistence, and API/frontend routing.
