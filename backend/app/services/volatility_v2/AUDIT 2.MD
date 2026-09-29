# Volatility V2 Audit 2 - Implementation Checklist

Last updated: 2026-05-16

Scope: runtime backend files under `backend/app/services/volatility_v2`. Consolidated scratch files are intentionally out of scope for verification.

## Verification

- [x] Runtime compile passed:
  - `backend/app/services/volatility_v2/core/analytics.py`
  - `backend/app/services/volatility_v2/core/performance.py`
  - `backend/app/services/volatility_v2/core/data_loader.py`
  - `backend/app/services/volatility_v2/core/data_pooling.py`
  - `backend/app/services/volatility_v2/registry.py`
  - `backend/app/services/volatility_v2/features/feature_01.py` through `feature_09.py`
- [x] Feature sweep passed with payload `assets=["SPY","QQQ","IWM"]`, `asset="SPY"`, `lookback_days=420`, `states=4`.
- [x] F01 returned `ok`: 9 chart outputs, 7 table outputs.
- [x] F02 returned `ok`: 9 chart outputs, 6 table outputs.
- [x] F03 returned `ok`: 7 chart outputs, 5 table outputs.
- [x] F04 returned `ok`: 7 chart outputs, 5 table outputs.
- [x] F05 returned `ok`: 4 chart outputs, 5 table outputs.
- [x] F06 returned `ok`: 7 chart outputs, 3 table outputs.
- [x] F07 returned `ok`: 8 chart outputs, 7 table outputs.
- [x] F08 returned `ok`: 5 chart outputs, 8 table outputs.
- [x] Research-mode smoke check passed for F02, F03, F04, and F08.
- [x] F04 research mode returned 60 HMM restart/BIC rows.
- [x] F08 research mode returned 100,000 Monte Carlo paths.
- [x] F09 returned `ok`: 7 chart outputs, 8 table outputs.
- [!] Runtime warnings remain from scipy/sklearn/pandas during some optimization paths. They do not stop feature execution.

## Speed Upgrade 2 Pass

- [x] `speed upgrade 2 .md` read end-to-end and converted into a checklist without deleting the original content.
- [x] BLAS/OpenMP thread guards added before volatility registry imports.
- [x] Polars predicate pushdown added for symbol-filtered OHLCV parquet reads.
- [x] Cached close-price and return-panel primitives added for repeated feature computations.
- [x] Numpy sliding-window rolling mean/variance helpers added.
- [x] `volatility_estimators()` moved from repeated pandas rolling Series calls to numpy rolling helpers.
- [x] `volatility_estimators_multi()` added and F01 multi-window output wired to it.
- [x] Diebold-Mariano tournament now computes upper-triangle tests and mirrors the matrix.
- [x] Model Confidence Set bootstrap statistic vectorized across bootstrap reps.
- [x] DCC-GARCH and Realized-GARCH MLE warm-start cache added.
- [x] Barunik-Krehlik connectedness vectorized with `einsum`.
- [x] Synthetic volatility surface generation vectorized.
- [x] Realtime F01-F09 smoke sweep passed after this pass.
- [!] Analytical DCC gradient remains intentionally not applied because the supplied gradient was approximate and could bias optimizer convergence. The JIT likelihood plus warm-start path is the safer verified speed improvement.
- [!] `arch` family warm-start reuse remains not applied because parameter vectors differ across GARCH/EGARCH/GJR/APARCH/FIGARCH and distribution specs.

## Feature 01 - Multi-Estimator Vol Engine

- [x] Bandi-Russell daily feasible proxy added as `bandi_russell_estimator` and `bandi_russell_liquidity_proxy`.
- [x] Liquidity-threshold/noise penalty included in Bandi-Russell proxy.
- [x] Opening Gap Fragility detector added as `opening_gap_fragility` and `opening_gap_fragility_detector`.
- [x] Range-based realized correlation matrix added as `range_correlation_matrix`.
- [x] Volatility-adjusted momentum panel added as `vol_adjusted_momentum_panel` and `vol_adjusted_momentum`.
- [x] Cross-asset ranked panel remains live.
- [!] True Bandi-Russell intraday estimator is not possible from daily OHLCV alone; the implemented output is explicitly a daily-data proxy.

## Feature 02 - GARCH Family Suite

- [x] Full `arch` GARCH-family scoreboard remains live for GARCH, EGARCH, GJR-GARCH, APARCH, FIGARCH and Gaussian/t/GED/skew-t distributions.
- [x] Realized GARCH MLE added as `Realized-GARCH-Gaussian`.
- [x] Realized GARCH variance series added as `realized_garch_variance_series`.
- [x] Regime-conditional NIC ribbon added as `regime_conditional_nic_ribbon`.
- [x] Nyblom-style parameter stability table added as `nyblom_parameter_stability`.
- [x] APARCH delta benchmark table added as `aparch_delta_benchmark`.
- [x] VaR duration proxy added to `var_backtests`.
- [x] Term-structure simulation confidence bands added to `garch_term_structure` with p05/p25/p50/p75/p95 bands.
- [x] Research mode raises term-structure simulation to 2,500 paths; realtime uses 750 paths and marks this constraint in metadata.
- [!] Multi-start `arch` MLE was not added because the current feature sweep is already expensive and stable; this remains a future convergence-hardening item.

## Feature 03 - HAR Forecasting Suite

- [x] Bipower variation jump estimator added via `bipower_variation`.
- [x] HAR-J now uses BPV jump input.
- [x] Jump estimator disagreement table added as `jump_estimator_disagreement`.
- [x] Directional hit rate added to forecast accuracy rows.
- [x] Directional DM test and p-value added to forecast accuracy rows.
- [x] MCS equal/weighted combination forecasts added to the forecast frame when MCS has multiple members.
- [x] HAR-X macro regressors added: VRP, yield slope, HY credit.
- [x] HAR-X macro contribution chart added as `har_x_macro_contribution`.
- [x] Walk-forward HAR forecast check added as `walk_forward_forecast_chart` and `walk_forward_accuracy`.
- [x] Bootstrap forecast confidence bands added as `forecast_confidence_bands`.
- [x] Research mode uses 500 bootstrap draws; realtime uses 150 draws and marks this constraint in metadata.

## Feature 04 - Regime Detection Engine

- [x] Macro-augmented SJM feature vector added: credit change, yield-slope change, VIX z-score.
- [x] Adaptive EW-HMM added as `adaptive_hmm_timeline`.
- [x] Filtered vs smoothed posterior comparison added as `smoothed_vs_filtered_comparison`.
- [x] Weibull regime duration survival model added as `regime_duration_survival`.
- [x] Global vol regime synchronization index added as `global_vol_regime_sync_index`.
- [x] HMM 20 random restarts plus BIC K-selection added behind research mode.
- [x] `hmm_bic_k_selection` table added, and selected K is surfaced in summary/meta.
- [!] Filtered/smoothed Brier score gap is not separately surfaced; the paired timelines are live.

## Feature 05 - VRP Monitor

- [x] Hodrick standard errors added to `return_predictability_regression`.
- [x] User-selectable VRP z-score lookback added and surfaced in `vrp_zscore_lookback_comparison`.
- [x] Regime-conditional BTZ decomposition added as `regime_conditional_btz`.
- [x] VRP term structure added as `vrp_term_structure` for 30d, 90d, 180d.
- [x] VRP mean-reversion speed remains live.
- [x] Append-only public implied-vol index pooling added in `core/data_pooling.py` for `^VIX3M`, `^VIX6M`, `^VIX9D`, and `^VIX1Y`.
- [x] `macro_frame` now reads `vix3m`/`vix6m` columns when present.
- [x] `vrp_term_structure` uses true Yahoo VIX3M/VIX6M fields when present and explicitly marks `interpolated_proxy` otherwise.
- [x] Append run succeeded for category7 macro parquet: added 4 rows, total rows 12,237.

## Feature 06 - Connectedness and Spillover

- [x] Exponentially weighted VAR path added via `fit_var_ew`.
- [x] Barunik-Krehlik frequency-domain connectedness added as `frequency_decomposed_connectedness`.
- [x] Connectedness-at-Risk added as chart/table output when enough macro data exists.
- [x] VAR/FEVD connectedness index remains live.
- [x] Pairwise FEVD heatmap remains live.
- [x] Dynamic network graph remains live.

## Feature 07 - Multivariate Vol and DCC

- [x] DCC-MIDAS long-run correlation matrix added as `dcc_midas_long_run_correlation`.
- [x] DCC-MIDAS long-run pair component is added to `dcc_time_series` when a pair is selected.
- [x] Probability-weighted crisis correlation added as `probability_weighted_crisis_correlation`.
- [x] Minimum torsion risk attribution added as `minimum_torsion_risk_attribution`.
- [x] Fisher Z-test crisis amplification table added as `fisher_z_crisis_amplification`.
- [x] Rolling condition number history added as `condition_number_history`.
- [x] Existing DCC MLE covariance/correlation and portfolio attribution remain live.
- [!] DCC-MIDAS is implemented as a monthly realized-correlation MIDAS component, not a full joint DCC-MIDAS likelihood.

## Feature 08 - Stress Testing and Scenario Engine

- [x] Clayton copula tail model added as `reverse_stress_copula`.
- [x] Reverse stress rows now include Clayton theta and lower-tail dependence.
- [x] Graphical LASSO analog matching added as `historical_analog_glasso`.
- [x] Defensive fallback to pseudo-inverse precision added when GLASSO is ill-conditioned.
- [x] Adversarial historically-plausible scenario added as `adversarial_scenario`.
- [x] Stress VaR and CVaR now include 95% and 99% levels.
- [x] Existing historical analogs, reverse stress, multi-scenario comparison, and contagion IRF remain live.
- [x] Bootstrap IRF confidence bands added as `contagion_impulse_response_bands` and `contagion_irf_bootstrap_bands`.
- [x] Research mode uses 500 IRF bootstraps; realtime uses 120 bootstraps and marks this constraint in metadata.
- [x] Research mode stress Monte Carlo now uses 100,000 paths; realtime remains 20,000 paths and marks this constraint in metadata.

## Feature 09 - Portfolio Vol Budget and Risk Targeting

- [x] Two-step KKT rebalance added via `two_step_rebalance`.
- [x] Two-step detail table added as `two_step_rebalancing_detail`.
- [x] Almgren-Chriss market-impact cost model added as `almgren_chriss_transaction_costs`.
- [x] Kelly-criterion vol target added as `kelly_vol_target`.
- [x] Kelly target added to the portfolio dashboard and summary cards.
- [x] Historical vol-targeting backtest now includes gross, net-of-cost, and cumulative cost series.
- [x] Historical performance now includes baseline, gross vol-targeted, net-of-cost vol-targeted, and annualized cost drag.
- [!] Full day-by-day nonlinear Almgren-Chriss execution path is not implemented; transaction costs are applied as a practical rebalance/cost-drag model.

## Cross-Module Additions

- [x] Global volatility regime synchronization index implemented in F04 as `global_vol_regime_sync_index`.
- [x] Synthetic volatility surface helper implemented in `core/analytics.py`.
- [x] Synthetic volatility surface exposed in F02 as `synthetic_vol_surface`.
- [x] Vol-adjusted momentum signal implemented in F01.
- [x] Runtime `compute_mode` / `research_mode` helpers added and surfaced through feature metadata where heavy paths differ.

## Speed Upgrades

- [x] Speed upgrades checklist added to `speed upgrades.md` without deleting original content.
- [x] Verified `bottleneck`, `numexpr`, `joblib`, and `threadpoolctl`; `icc_rt` unavailable on this environment.
- [x] Joblib disk cache added for repeat OHLCV symbol loads.
- [x] LRU macro cache added for repeat macro frame reads.
- [x] JIT kernels added/wired for autocorrelation, rolling rank percentile, GARCH loop, Realized-GARCH NLL, and DCC likelihood.
- [x] DCC optimizer switched to L-BFGS-B plus JIT likelihood.
- [x] HMM/SJM speedups applied: diag HMM, lower iterations/tolerance, quantile KMeans initialization, MiniBatch fallback, optimized filtered emissions.
- [x] F02 hot paths vectorized: NIC, VaR transition counts, inline KS.
- [x] Selected pivot/corr/percentile/date-format/serialization hot paths optimized.
- [x] GARCH scoreboard cache added with bounded in-memory size.
- [x] Research mode remains active: F04 uses 20 HMM restarts/BIC; F08 uses 100,000 MC paths; F02/F03 use higher simulation/bootstrap counts.
- [x] Added `core/performance.py`.
- [x] Newey-West LRV now uses JIT-capable `newey_west_lrv_jit`.
- [x] Stationary bootstrap now uses JIT-capable `stationary_bootstrap_jit`.
- [x] Statistical Jump Model Viterbi path now uses JIT-capable `sjm_viterbi`.
- [x] DCC correlation path now uses JIT-capable `dcc_correlation_path`.
- [x] VAR design matrix construction now uses `build_var_design_matrix`.
- [x] VAR MA matrices now use `var_ma_matrices_fast`.
- [x] Generalized FEVD now uses vectorized `generalized_fevd_fast`.
- [x] OLS HAC now uses vectorized `ols_hac_fast`.
- [x] Polars parquet scan path is present in `core/data_loader.py` for market OHLCV when Polars is importable.
- [!] orjson API serialization was not added. `clean_json` remains the compatibility serializer.
- [!] GARCH/DCC global caching was not added to avoid stale memory growth in long-running backend sessions.
- [!] Parallel per-asset feature execution was not added; current deterministic serial execution avoids thread contention in `arch`/BLAS.

## Known Remaining Work

- [x] Expose `synthetic_vol_surface` in a runtime feature response.
- [x] Add F02 term-structure simulation confidence bands.
- [x] Add F03 bootstrap forecast confidence bands.
- [x] Add F04 HMM restart/BIC selection behind research mode.
- [x] Add F08 bootstrap IRF bands behind research mode.
- [x] Add F08 100,000-path Monte Carlo behind research mode.
- [x] Confirm Polars read path exists in `core/data_loader.py`.
- [ ] Full multi-start `arch` MLE remains future convergence hardening. Current `arch` sweep is complete and stable but not multi-start per model/dist.
- [ ] Full joint DCC-MIDAS likelihood remains future research scope. Current DCC-MIDAS output is a monthly realized-correlation MIDAS component, explicitly marked.
- [ ] Full day-by-day nonlinear Almgren-Chriss execution path remains future scope. Current costs are practical rebalance/cost-drag outputs.
