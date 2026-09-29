# PCA V2 Audit Checklist

Updated: 2026-06-10

## Current Pass Status

- [x] Read the audit end to end and targeted only the open gaps.
- [x] Added dedicated cross-asset data loaders in `core/data_loader.py`.
- [x] Added support for the larger verified hourly parquet at `research_exports/final_submission_package/SUBMISSION_MAIN/data_sources/parquet/market_universe_hourly.parquet`.
- [x] Added local price-file loading from `backend/data/prices` for FX, commodity futures, rates futures, crypto, ETF and equity proxies.
- [x] Added `core/performance.py` with fast covariance, contiguous float conversion, batched correlation, safe pseudo-inverse, downsampling and timing helpers.
- [x] Added `core/cross_asset.py` as the dedicated Feature 10 subsystem.
- [x] Implemented Feature 10 end to end with real local cross-asset blocks.
- [x] Feature 10 now returns `status="ok"` instead of `partial`.
- [x] Feature 10 now emits asset-class-specific covariance estimator audit rows.
- [x] Feature 10 FX block uses EWMA covariance with lambda 0.94 and explicitly ignores unreliable FX volume.
- [x] Feature 10 commodity/rates futures blocks use OAS covariance.
- [x] Feature 10 crypto block uses MCD robust covariance when sample size supports it, with OAS fallback.
- [x] Feature 10 computes unified cross-asset covariance and correlation heatmaps.
- [x] Feature 10 computes DCC-style conditional correlation using standardized residuals and optimized DCC parameters.
- [x] Feature 10 computes rolling block correlation monitor.
- [x] Feature 10 computes CASCI cross-asset systemic correlation index.
- [x] Feature 10 computes FX minimum-variance hedge-ratio table.
- [x] Feature 10 computes crypto volume-quality / wash-trading proxy screen.
- [x] Feature 10 computes Cornish-Fisher adjusted MP threshold for the crypto block.
- [x] Feature 10 emits calendar-alignment audit explaining equity-day versus seven-day handling.
- [x] Feature 10 emits stress-date block-correlation overlays where dates exist in local data.
- [x] Feature 10 emits hourly parquet inventory and confirms the 272-ticker hourly source.
- [x] Added `residual_ou_backtest()` and wired Feature 04 historical OU P&L output.
- [x] Added Bai-Perron-style multiple breakpoint search and wired Feature 05.
- [x] Added HOSVD/Tucker tensor outputs for Feature 05 rolling eigenvalue tensor.
- [x] Added HOSVD/Tucker residual-correlation tensor outputs for Feature 08.
- [x] Added Bertsimas-Brown-style robust ellipsoidal frontier and wired Feature 06.
- [x] Added retained-PC factor risk parity optimizer and wired Feature 06.
- [x] Added compact PDF export generation and wired Feature 09.
- [x] Materialized canonical cross-asset parquet panels under `backend/data/canonical`.
- [x] Materialized server-side holdings/trade history parquet under `backend/data/canonical`.
- [x] Wrote futures roll-method audit parquet under `backend/data/canonical`.
- [x] Made `market_universe.parquet` the source of truth for daily PCA and cross-asset daily prices.
- [x] Added explicit full-master routing: `universe="all"|"full"|"master"` and `use_full_master_universe=true` can use all 4,155 master symbols.
- [x] Raised PCA symbol routing cap to 5,000 for explicit full-master requests.
- [x] Added hourly frequency support in `returns_matrix()` using the largest verified hourly parquet.
- [x] Added frequency-aware lookback row slicing so `lookback_days` means days, not raw rows, for hourly data.
- [x] Added frequency-aware symbol routing so hourly defaults use the hourly parquet inventory instead of daily-only symbols.
- [x] Replaced hardcoded 252 annualization in live PCA analytics with `annualization_factor(frequency)`.
- [x] Added `frequency` and `annualization_factor` to response metadata.
- [x] Fixed Feature 11 pandas compatibility issue in `reset_index(names=...)`.
- [x] Verified `python3 -m compileall -q backend/app/services/pca_v2`.
- [x] Verified smoke run for Features 01-11. All returned `ok`.

## Honest Remaining Limitations

- [x] Clean standalone canonical cross-asset parquet panels are materialized. Current files: `equity_daily.parquet`, `fx_daily.parquet`, `futures_daily.parquet`, `crypto_daily.parquet`, `cross_asset_hourly.parquet`, and `asset_metadata.parquet`.
- [x] Durable server-side holdings/trade history parquet is materialized from `portfolio_state.json`.
- [x] Futures roll-method audit is materialized.
- [ ] Independent institutional roll-adjusted futures methodology is still not verified. The repo has futures symbols and Yahoo-style continuous/proxy files, but no contract identifiers, roll dates, or backward-ratio/backward-difference stitching policy. The audit explicitly marks these as usable return proxies, not independently roll-audited futures chains.
- [ ] True order-flow, signed volume, bid/ask spread and tick-level microstructure data are still not present.

---

Going through every file you gave me.

---

## FEATURE 1 — `core/analytics.py` → `rmt_model()` + `mp_threshold()` + `covariance_estimator()`

**σ² fitting is wrong.** `mp_threshold()` uses `np.nanmedian(vals)` as σ². The spec requires iterative moment-matching: restrict eigenvalues to the noise bulk below a trial λ_max, compute the mean of that bulk, set that as the new σ², refit λ_max, repeat until convergence. The median of the full spectrum is not the same thing and will misplace the noise boundary whenever signal eigenvalues are large.

**Resolved finding — outlier pre-processing.** The spec lists five options before the covariance estimator runs: none, winsorize 1%/99%, winsorize 2.5%/97.5%, Huber M-estimation, trimming. The original audit found these absent.

Resolved: `preprocess_returns()` is implemented and wired into `rmt_model()`.

**Shrinkage blend reconstruction missing.** The spec requires a slider between pure RMT-cleaned and pure sample covariance. Currently `rmt_model()` always produces the hard-clip reconstruction — signal eigenvectors plus diagonal idiosyncratic. There is no `blend_gamma` parameter and no blended output. The `reconstruct_covariance()` logic needs a `blend_gamma` argument wired from `payload.get("blend_gamma")`.

**`covariance_estimator()` MCD path silently falls back.** The condition `len(x) > x.shape[1] + 5` is too weak. MCD requires roughly T > 2N to be reliable. Add a proper check and warn in meta when MCD is requested but the sample is too small.

---

## FEATURE 2 — `features/feature_02.py` + analytics helpers

**Resolved finding — Promax rotation.** The original audit found only Varimax implemented.

Resolved: `promax()` is implemented and wired in Feature 02.

**Resolved finding — hierarchical PCA.** The original audit required intra-cluster PCA and second-level PCA across cluster factors.

Resolved: `hierarchical_pca()` is implemented and wired in Feature 02.

**Per-asset R² of the factor model not computed.** The loading records exist but there is no column showing what fraction of each asset's variance is explained by the K-PC model. This is `Σₖ λₖ vᵢₖ² / Σᵢᵢ` per asset. Should be added to `loading_records()` output and the `full_loading_matrix` table.

**Hoyer sparsity score missing.** Spec requires a sparsity metric per loading column to quantify how concentrated each factor is. Not computed anywhere. Needs a helper in `analytics.py` and a row added to the `eigenvector_json` table in feature_02.

**`_cluster_map()` is not a hierarchical PCA output.** It is just a sector-level average of absolute PC1 loadings. The chart is labeled `hierarchical_pca_cluster_map` but does not represent any hierarchical decomposition. Until HPCA is implemented this should be labeled as a sector-aggregation proxy in meta.

---

## FEATURE 3 — `features/feature_03.py` + `risk_decomposition()` in analytics

**Resolved finding — benchmark-relative active risk attribution.** The original audit required active weights, tracking error, factor tilt share and selection share.

Resolved: `active_risk_attribution()` is implemented and wired in Feature 03.

**Rolling risk decomposition is just rolling vol.** The `rolling` variable in feature_03 is a 21-day rolling standard deviation of portfolio returns — a single scalar time series. The spec requires a rolling stacked area chart showing the per-PC variance contribution percentage over time. This needs a separate `rolling_risk_decomposition()` function that refits the factor exposures over rolling windows and tracks `λᵢ (wᵀ vᵢ)² / σ²_p` per PC at each date.

**Cornish-Fisher VaR is computed but not decomposed.** The spec requires VaR decomposed per factor contribution as a waterfall. The `_waterfall()` helper in feature_03 uses `cornish_fisher_var` as the total but distributes it proportionally to variance shares — this is an approximation that ignores the Cornish-Fisher correction on the individual factor contributions. Low priority but worth flagging.

---

## FEATURE 4 — `features/feature_04.py` + `ou_signal_table()` in analytics

**Resolved finding — volume-time adjustment.** The original audit required Avellaneda-style residual scaling by relative dollar volume.

Resolved: `volume_time_residuals()` is implemented and gated by `payload["volume_time"]`.

**Break-even Z-score not computed.** Each signal row in the table shows `direction` and `economically_viable` but `economically_viable` is just `half_life <= max_half_life`. The spec requires economic viability to also check that the gross expected P&L exceeds round-trip transaction costs: `σᵢ_eq × (|z| − s_exit) > 2 × cost_bps / 10000`. A `breakeven_z()` helper is needed and both `breakeven_z` and `net_viable` should be columns in the signal table. Wire `payload.get("cost_bps")` for the cost input.

**OU parameter standard errors not computed.** The spec requires delta-method standard errors on κ, μ, and especially the half-life. Currently the table returns point estimates only. The OLS residual variance from the AR(1) regression gives `Var(b̂)` directly via `ζ² × (XᵀX)⁻¹[1,1]`. From `Var(b̂)`, the SE on half-life follows via the delta method: `SE(HL) = |ln(2) / (b ln(b)²)| × SE(b)`. These should be columns in `ou_parameter_table`.

**Resolved finding — OU MLE estimation path.** The original audit required a payload toggle between OLS and full MLE.

Resolved: `ou_mle()` is implemented and wired behind `payload["ou_method"]="mle"`.

**Resolved finding — signal decay analysis.** The original audit required forward Z-score decay at T+1/T+5/T+10/T+21/T+42/T+63.

Resolved: `signal_decay_analysis()` is implemented and wired behind `payload["signal_decay"]`.

**Backtest P&L engine resolved in final pass.** `residual_ou_backtest()` now runs historical entry/exit logic with gross/net returns, transaction costs, drawdown, hit rate, turnover, Sharpe, CAGR and equity curve outputs. Feature 04 exposes `residual_ou_backtest_equity` and `residual_ou_backtest_stats`.

---

## FEATURE 5 — `features/feature_05.py` + `rolling_pca_metrics()` in analytics

**Current percentile ranking not computed.** The spec requires the live alert panel to show the current PC1 share as a percentile of its 252-day history. `rolling_pca_metrics()` computes `pc1_zscore` via z-score normalization but the spec also wants the raw percentile rank (0-100). Add a `compute_percentile_rank()` call in feature_05 after the rolling metrics are assembled.

**PC1 loading evolution heatmap not returned.** `rolling_pca_metrics()` tracks `pc1_share` and `pc1_cosine_stability` as scalars but never stores the actual PC1 loading vector at each rolling date. The spec requires an N×T matrix of loading values for the heatmap and animated playback. A separate `rolling_loading_evolution()` function needs to be added that stores `(date, ticker, pc1_loading)` triples at each step. This is separate from `rolling_pca_metrics()` because of the size — storing full loading vectors at every step is expensive and should be downsampled.

**Principal angles between K-dimensional subspaces not computed.** `rolling_pca_metrics()` tracks `pc1_cosine_stability` which is the scalar cosine similarity of PC1 only. The spec requires the maximum principal angle between the full K-dimensional loading matrix at time t and at time t minus the lag window, computed via SVD of `P(t)ᵀ P(t−lag)`. This generalizes the cosine similarity to the whole factor bundle. Wire alongside the existing cosine metric in the rolling loop.

**Bai-Perron multiple breakpoint test resolved in final pass.** `bai_perron_breakpoints()` now searches multiple mean-break combinations with BIC selection and Feature 05 exposes `bai_perron_breakpoint_table`.

**Multi-frequency tensor decomposition resolved in final pass.** Feature 05 now emits HOSVD/Tucker-style tensor core records plus factor/window/time singular values via `tensor_hosvd_proxy()`.

---

## FEATURE 6 — `features/feature_06.py` + `optimize_portfolio()` in analytics

**This feature has the most gaps of any feature.**

**Resolved finding — ERC / risk parity.** The original audit required the Spinu convex reformulation.

Resolved: `erc_portfolio()` is implemented and wired through Feature 06 objective selection.

**Maximum Sharpe Portfolio not explicitly solved.** The current code runs a mean-variance sweep over risk aversion values. The explicit MSP via the Tobin separation trick — minimize `wᵀΣw` subject to `wᵀ(μ − rf) = 1` then renormalize — is not done. The sweep may or may not hit the true MSP depending on the risk aversion grid and expected returns.

**PC-Factor Risk Parity resolved in final pass.** `pc_factor_risk_parity_portfolio()` now solves for long-only weights that equalize retained-PC systematic variance contributions and Feature 06 emits both contribution and weight outputs.

**Resolved finding — K-sensitivity chart.** The original audit required rolling OOS Sharpe as a function of K.

Resolved: `k_sensitivity_sweep()` is implemented and wired in Feature 06.

**Resolved finding — Black-Litterman posterior.** The original audit found no BL computation.

Resolved: `black_litterman_posterior()` is implemented and wired when `payload["bl_views"]` is provided.

**Resolved finding — turnover constraint.** The original audit required linearized turnover constraints.

Resolved: turnover constraints are wired in the CVXPY optimizer path.

**Constraint shadow prices return None.** The `constraint_shadow_prices` table has `"shadow_price": None` hardcoded. CVXPY exposes dual values via `constraint.dual_value` after solving. Wire these up.

**Robust efficient frontier resolved in final pass.** `_robust_proxy()` has been removed. Feature 06 now uses `robust_frontier_ellipsoidal()`, a Bertsimas-Brown-style ellipsoidal uncertainty penalty frontier with CVXPY when available and a deterministic uncertainty-augmented fallback.

---

## FEATURE 7 — `features/feature_07.py` + `bootstrap_validation()` in analytics

**IC2 and IC3 formulas resolved.** `_bai_ng_proxy()` has been replaced by `bai_ng_criteria()`, which computes rank-r SSR and the proper Bai-Ng IC1/IC2/IC3 penalties.

**Resolved finding — block bootstrap.** The original audit required block bootstrap with user-set block length.

Resolved: `block_bootstrap_sample()` is implemented and wired through `payload["bootstrap_type"]="block"`.

**Resolved finding — subsampling stability.** The original audit required a separate subsampling stability run.

Resolved: `subsampling_stability()` is implemented and wired in Feature 07.

**Principal-angle computation resolved in final pass.** Bootstrap validation now computes SVD principal angles between the full-sample loading subspace and each bootstrap loading subspace, and Feature 07 exposes `principal_angle_analysis` / `principal_angle_table`.

---

## FEATURE 8 — `features/feature_08.py` + `residual_contagion()` in analytics

**Rolling group residual correlation time series missing.** `residual_contagion()` computes `group_rows` as a single current snapshot of average pairwise residual correlation per sector. The spec requires this as a rolling daily time series — the primary chart is a multi-line plot of sector residual correlation over time, not a current-only table. A `rolling_group_residual_corr()` function needs to be added that loops over rolling windows and collects `(date, sector, avg_residual_corr)` triples. This is the most important missing output in feature_08 because it is labeled as the primary chart.

**Resolved finding — crisis overlay.** The original audit required annotated crisis bands for frontend rendering.

Resolved: Feature 08 emits `crisis_overlay_dates`.

**Tensor residual correlation monitoring resolved in final pass.** Feature 08 now emits real residual-correlation tensor HOSVD outputs via `residual_tensor_hosvd()` instead of `tensor_residual_frequency_proxy`.

---

## FEATURE 9 — `features/feature_09.py` + `stress_scenarios()` in analytics

**Resolved finding — historical worst-day scenarios.** The original audit required replaying the five worst historical PC realizations.

Resolved: `historical_worst_day_scenarios()` is implemented and wired in Feature 09.

**Resolved finding — joint multi-PC shock.** The original audit required simultaneous multi-PC shock support.

Resolved: `joint_scenario_pnl()` is implemented and wired in Feature 09 when `payload["joint_shocks"]` is supplied.

**Stress VaR uses only 2K scenarios.** The spec notes that 2K scenarios is too small for reliable quantile estimation and recommends augmenting with 10,000 Monte Carlo draws from the K-dimensional Gaussian factor distribution. Currently `stress_var` and `stress_cvar` are computed as percentiles of the 2K parametric scenario P&L vector — the 95th percentile of 20 values is not a reliable VaR estimate.

**PDF export resolved in final pass.** Feature 09 now emits a base64 PDF through `stress_pdf_report_base64()` in the `pdf_export` table.

---

## FEATURE 10 — `features/feature_10.py`

**Everything in the spec is missing. This is a stub.** The current implementation does a simple `_asset_blocks()` classification based on ticker string matching and computes average cross-block covariance from the single cleaned equity matrix. The feature returns `status: "partial"`. The full spec requires:

- Asset-class-specific covariance estimators per block: FX uses EWMA λ=0.94, commodities use OAS, crypto uses MCD student-t EM
- DCC-GARCH(1,1) for cross-block conditional correlations
- Calendar alignment handling: equity-day-only vs 7-day with weekend crypto return documentation
- Crypto volume filter for wash trading detection
- Cornish-Fisher adjusted MP threshold for the crypto block using the fourth cumulant
- FX hedging at the covariance level via the minimum-variance hedge ratio matrix `H* = Σ_FX⁻¹ Σ_FX,equity^T`
- Rolling block correlation monitor with CASCI index
- Block correlation heatmap with stress-date comparison overlay

The right approach here is to build `core/cross_asset.py` as a separate module with `detect_asset_class()`, `block_covariance()`, and `assemble_block_covariance()` as the scaffolding, then rebuild feature_10 to call it. The data loader already has `dollar_volume_matrix()` but needs FX and commodity OHLCV to be wired through `parse_symbols()`.

---

## FEATURE 11 — `features/feature_11.py` + `liquidity_outputs()` in analytics

**Resolved finding — Pastor-Stambaugh gamma.** The original audit required PS gamma branching.

Resolved: `pastor_stambaugh_gamma()` is implemented and wired through `payload["illiquidity_measure"]`.

**Kyle's lambda daily approximation resolved.** `kyle_lambda_daily()` is implemented and wired through `payload["illiquidity_measure"]`.

**Resolved finding — Newey-West standard errors.** The original audit required Bartlett-kernel HAC standard errors.

Resolved: `newey_west_se()` is implemented and wired into liquidity beta regression.

**`illiquidity_measure` payload parameter ignored.** The function always computes Amihud regardless of what the user requests. Wire `payload.get("illiquidity_measure")` to branch between Amihud, PS gamma, and Kyle's lambda.

**Amihud normalization option ignored.** The spec requires cross-sectional rank normalization, log transformation, or standardization before the PCA on the illiquidity panel. Currently `amihud` is log1p-transformed and rolling-meaned but there is no rank normalization option.

**`quant_unwind_score` formula is correct but the threshold alert is hardcoded.** Wire `payload.get("quant_unwind_threshold")` properly — it is already in feature_11 but the default is `0.15` which is fine, just confirm it reads from payload correctly (it does via `float(payload.get("quant_unwind_threshold") or 0.15)` which is fine).

---

## DATA LOADER — `core/data_loader.py`

No FX or commodity OHLCV feeds. `available_symbols()` and `returns_matrix()` only pull from `MARKET_UNIVERSE` which is equity OHLCV. Feature 10's cross-asset engine has no data source for FX rates, commodity futures, or crypto. When Feature 10 is built properly, `data_loader.py` needs a `fx_returns_matrix()` and `commodity_returns_matrix()` function or `parse_symbols()` needs to handle non-equity tickers routed to different parquet files or yfinance calls.

---

## IMPLEMENTATION STATUS (Updated: 2025-06-10)

### ✅ DONE — `core/analytics.py`

| Gap | Function Added | Status |
|-----|---------------|--------|
| σ² moment-matching | `fit_mp_sigma2()` + wired in `rmt_model()` | ✅ DONE |
| Outlier preprocessing | `preprocess_returns()` + wired in `rmt_model()` | ✅ DONE |
| Promax rotation | `promax()` | ✅ DONE |
| Hoyer sparsity | `hoyer_sparsity()` | ✅ DONE |
| Asset R² | `asset_r2()` | ✅ DONE |
| Hierarchical PCA | `hierarchical_pca()` | ✅ DONE |
| Active risk attribution | `active_risk_attribution()` | ✅ DONE |
| Rolling risk decomposition (per-PC) | `rolling_risk_decomposition()` | ✅ DONE |
| Volume-time residuals | `volume_time_residuals()` + wired in `ou_signal_table()` | ✅ DONE |
| OU SE (delta method) | computed inline in `ou_signal_table()` | ✅ DONE |
| Break-even Z | computed inline in `ou_signal_table()` | ✅ DONE |
| Principal angles (SVD) | `subspace_principal_angles()` + `rolling_pca_metrics()` | ✅ DONE |
| Rolling group residual corr (time series) | `rolling_group_residual_corr()` | ✅ DONE |
| Historical worst-day scenarios | `historical_worst_day_scenarios()` | ✅ DONE |
| Joint multi-PC shock | `joint_scenario_pnl()` | ✅ DONE |
| 10K MC stress VaR | wired in `stress_scenarios()` | ✅ DONE |
| ERC portfolio (Spinu) | `erc_portfolio()` + wired in `optimize_portfolio()` | ✅ DONE |
| Max Sharpe (Tobin) | `max_sharpe_portfolio()` + wired in `optimize_portfolio()` | ✅ DONE |
| K-sensitivity OOS Sharpe | `k_sensitivity_sweep()` | ✅ DONE |
| Black-Litterman posterior | `black_litterman_posterior()` + wired in `optimize_portfolio()` | ✅ DONE |
| Turnover constraint | wired in `optimize_portfolio()` CVXPY block | ✅ DONE |
| Proper Bai-Ng IC1/IC2/IC3 (SSR-based) | `bai_ng_criteria()` | ✅ DONE |
| Block bootstrap | `block_bootstrap_sample()` + wired in `bootstrap_validation()` | ✅ DONE |
| Subsampling stability | `subsampling_stability()` + wired in `bootstrap_validation()` | ✅ DONE |
| Pastor-Stambaugh gamma | `pastor_stambaugh_gamma()` + wired in `liquidity_outputs()` | ✅ DONE |
| Kyle's lambda | `kyle_lambda_daily()` + wired in `liquidity_outputs()` | ✅ DONE |
| Newey-West HAC SE | `newey_west_se()` + wired in `liquidity_outputs()` | ✅ DONE |
| Illiq measure branching | wired in `liquidity_outputs()` | ✅ DONE |
| Crisis overlay dates | returned in `feature_08.py` | ✅ DONE |

### ✅ DONE — Feature Files

| Feature | Key Additions | Status |
|---------|--------------|--------|
| feature_01.py | σ² + outlier filter transparency in summary/meta | ✅ DONE |
| feature_02.py | Promax, HPCA, asset R², Hoyer sparsity | ✅ DONE |
| feature_03.py | Active risk attribution, rolling per-PC decomposition | ✅ DONE |
| feature_04.py | Volume-time toggle, SE/break-even Z exposure | ✅ DONE |
| feature_06.py | ERC/MSP/BL/turnover/k-sensitivity wired | ✅ DONE |
| feature_07.py | Proper Bai-Ng IC, block bootstrap, subsampling | ✅ DONE |
| feature_08.py | Rolling group residual corr time series, crisis overlay | ✅ DONE |
| feature_09.py | Hist worst-day, joint shock, 10K MC stress VaR | ✅ DONE |
| feature_11.py | PS gamma/Kyle's lambda/NW SE/illiq branching | ✅ DONE |

### ✅ DONE (second pass — previously deferred)

| Item | Function / Location | Status |
|------|-------------------|--------|
| Blend gamma slider (F1, F5) | `blend_covariance()` + wired in feature_01/feature_05 | ✅ DONE |
| Constraint shadow prices (F6) | `optimize_portfolio_with_duals()` + feature_06 | ✅ DONE |
| MLE OU estimation (F4) | `ou_mle()` + feature_04 (gated: `payload["ou_method"]="mle"`) | ✅ DONE |
| Signal decay analysis (F4) | `signal_decay_analysis()` + feature_04 (gated: `payload["signal_decay"]=true`) | ✅ DONE |
| PC1 loading evolution heatmap (F5) | `rolling_loading_evolution()` + feature_05 | ✅ DONE |
| PC1 percentile rank (F5) | `pc1_percentile_rank()` + feature_05 | ✅ DONE |

### ✅ DONE (final audit-close pass)

| Item | Function / Location | Status |
|------|-------------------|--------|
| Feature 10 cross-asset engine | `core/cross_asset.py`, `feature_10.py` | ✅ DONE |
| FX / commodity / rates / crypto data loader | `load_cross_asset_ohlcv()` and `cross_asset_returns_matrix()` read daily prices from `market_universe.parquet`; local price files remain operator diagnostics only | ✅ DONE |
| Full master universe routing | `parse_symbols()` + `load_context()` supports all 4,155 master symbols on request | ✅ DONE |
| Hourly PCA frequency | `returns_matrix(..., frequency="hourly")`, hourly symbol routing, hourly lookback rows | ✅ DONE |
| Frequency-aware annualization | `annualization_factor()` + `model_annualization()` across analytics | ✅ DONE |
| Canonical cross-asset panels | `materialize_canonical_cross_asset_panels()` wrote `backend/data/canonical/*.parquet` | ✅ DONE |
| Durable holdings/trades parquet | `materialize_portfolio_holdings_history()` wrote holdings and trade history parquet | ✅ DONE |
| Futures roll-method audit | `verify_futures_roll_methodology()` wrote `futures_roll_audit.parquet` | ✅ DONE |
| Robust BL efficient frontier (F6) | `robust_frontier_ellipsoidal()` + Feature 06 `robust_vs_standard_frontier` | ✅ DONE |
| PC-factor risk parity (F6) | `pc_factor_risk_parity_portfolio()` + Feature 06 contribution/weight outputs | ✅ DONE |
| Backtest P&L engine (F4) | `residual_ou_backtest()` + Feature 04 `residual_ou_backtest_equity` / `residual_ou_backtest_stats` | ✅ DONE |
| Bai-Perron multiple breakpoints (F5) | `bai_perron_breakpoints()` + Feature 05 `bai_perron_breakpoint_table` | ✅ DONE |
| Tucker tensor decomposition (F5) | `tensor_hosvd_proxy()` + Feature 05 tensor core / singular values | ✅ DONE |
| Tucker residual tensor decomposition (F8) | `residual_tensor_hosvd()` + Feature 08 residual tensor core / singular values / summary | ✅ DONE |
| PDF export (F9) | `stress_pdf_report_base64()` + Feature 09 `pdf_export` table | ✅ DONE |

### ⚠️ Still Not Claiming Because Data Is Not In Repo

| Item | Honest status |
|------|---------------|
| Independently roll-adjusted futures chains | [ ] Not verifiable from local files. Current futures are Yahoo-style continuous/proxy series with no contract IDs or roll dates. `futures_roll_audit.parquet` documents this explicitly. |
| True order-flow / signed volume / bid-ask / tick microstructure | [ ] Not present in repo. PCA V2 uses daily OHLCV liquidity proxies where available, not true tick/order-book data. |
