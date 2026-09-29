# QUANT360 Volatility V2 Implementation Audit

Last updated: 2026-05-15

This file is now the implementation checklist for `backend/app/services/volatility_v2`. It reflects the current code after the full audit pass, not the old scaffold state.

## Verification

- [x] `python3 -m compileall backend/app/services/volatility_v2`
- [x] Feature sweep executed for F01-F09 with `assets=["SPY","QQQ","IWM"]`, `asset="SPY"`, `lookback_days=420`
- [x] F01 returned `ok`
- [x] F02 returned `ok`
- [x] F03 returned `ok`
- [x] F04 returned `ok`
- [x] F05 returned `ok`
- [x] F06 returned `ok`
- [x] F07 returned `ok`
- [x] F08 returned `ok`
- [x] F09 returned `ok`
- [x] Missing FRED macro fields appended to `factors/data/processed/category7_macro_regime.parquet`
- [x] Core OHLCV seed universe exists in `backend/data/market_universe.parquet`

## Data Layer

- [x] `core/data_loader.py` reads local daily OHLCV from `backend/data/market_universe.parquet`
- [x] `core/data_loader.py` reads category7 macro from `factors/data/processed/category7_macro_regime.parquet`
- [x] `core/data_pooling.py` is append-only and deduplicates by key
- [x] FRED fetcher supports `VIXCLS`, `DGS2`, `DGS10`, `BAMLC0A0CM`, `BAMLH0A0HYM2`
- [x] Existing category7 macro parquet now has the required FRED series after append
- [x] Yahoo OHLCV fetcher handles flattened MultiIndex responses
- [x] Runtime feature code does not mutate parquet

## Core Analytics

- [x] `clean_json` sanitizes NumPy, pandas, NaN, and Inf payloads
- [x] `volatility_estimators` computes close-to-close, Parkinson, Garman-Klass, Rogers-Satchell, and Yang-Zhang
- [x] Parkinson estimator includes the daily discrete-sampling correction
- [x] Yang-Zhang supports 24h-style assets by excluding overnight gap variance for `_USD` / FX-like symbols
- [x] Estimator efficiency uses variance of variance-estimator series, not raw vol variance
- [x] Estimator table returns 252d, 5y, and full-history percentile fields
- [x] QLIKE Diebold-Mariano estimator tournament implemented
- [x] DM p-values and Bonferroni significance flags returned
- [x] Newey-West long-run variance helper implemented
- [x] Newey-West HAC standard errors implemented in `ols_table`
- [x] Stationary bootstrap index generator implemented
- [x] Bootstrap Model Confidence Set helper implemented
- [x] `arch` library MLE implemented for GARCH, EGARCH, GJR-GARCH, APARCH, and FIGARCH
- [x] Gaussian, Student-t, GED, and skew-t distributions wired through `arch`
- [x] `hmmlearn` GaussianHMM Baum-Welch EM implemented for regimes
- [x] Statistical Jump Model implemented with k-means++ initialization and jump-penalty dynamic programming
- [x] OAS-style Ledoit-Wolf shrinkage implemented
- [x] Two-stage DCC-GARCH MLE implemented
- [x] VAR(p) with BIC lag selection implemented
- [x] Pesaran-Shin generalized FEVD implemented

## Feature 01 - Multi-Estimator Daily Volatility Engine

- [x] Close-to-close rolling estimator
- [x] Parkinson rolling estimator
- [x] Garman-Klass rolling estimator
- [x] Rogers-Satchell rolling estimator
- [x] Yang-Zhang rolling estimator
- [x] Multi-window estimator panel for 10, 21, 42, 63, 126, and 252 days
- [x] Five-estimator comparison chart
- [x] Estimator disagreement band
- [x] Estimator efficiency table
- [x] QLIKE DM tournament table
- [x] Estimator agreement index
- [x] Weakest disagreement pair surfaced in alert
- [x] Annualized vol panel data for five dials
- [x] Cross-asset ranked panel
- [x] Custom annualization supported

## Feature 02 - GARCH Family Suite

- [x] 5 model families fit through `arch`
- [x] 4 conditional distributions fit through `arch`
- [x] 20 model/distribution combinations scored
- [x] Log-likelihood, AIC, BIC, RMSE, and QLIKE returned
- [x] Bootstrap Model Confidence Set membership returned
- [x] Winning model parameters surfaced
- [x] News impact curve uses model-specific formulas
- [x] Term structure returned for 1, 5, 10, 21, 42, 63, 126, and 252 days
- [x] Long-memory FIGARCH diagnostic series returned
- [x] PIT histogram returned
- [x] KS test for PIT uniformity returned
- [x] Conditional 99% VaR series returned
- [x] Kupiec unconditional coverage test returned
- [x] Christoffersen independence test returned
- [x] Volatility state gauge returned
- [ ] Multiple optimizer starting points are not explicitly controlled because `arch` owns the optimizer internals
- [ ] Term-structure simulation confidence bands are not returned yet

## Feature 03 - HAR Forecasting Suite

- [x] HAR model implemented
- [x] LHAR model implemented with Jensen correction
- [x] HAR-J model implemented
- [x] Signed jump regressors implemented
- [x] HAR-Leverage implemented
- [x] Signed leverage regressors implemented
- [x] ACSV-HAR implemented
- [x] A-ACSV-HAR implemented with positive/negative dispersion
- [x] HAC Newey-West standard errors used
- [x] Multi-horizon forecast diagnostics for 1, 5, 10, 21, 42, and 63 days
- [x] Forecast accuracy includes RMSE, QLIKE, MAE, and R2 field
- [x] Bootstrap MCS membership returned
- [x] Jump proxy series returned
- [x] Leverage effect chart returned
- [x] ACSV contribution chart returned
- [ ] Full walk-forward expanding-window re-estimation is not implemented; current run uses full-sample fit plus multi-horizon diagnostics
- [ ] Bootstrap forecast confidence bands are not returned yet

## Feature 04 - Volatility Regime Detection

- [x] SJM feature vector includes vol 5/21/63, 21d return, RS/YZ jump ratio, and squared-return autocorrelation
- [x] SJM k-means++ initialization implemented
- [x] SJM jump-penalty dynamic programming implemented
- [x] HMM Baum-Welch EM implemented through `hmmlearn`
- [x] HMM smoothed probabilities returned
- [x] Macro rules include VIX threshold, curve inversion, and vol trend
- [x] Rolling Brier precision weights used for ensemble combination
- [x] Probabilistic regime timeline returned
- [x] Current regime dashboard returned
- [x] Regime-conditional stats returned
- [x] Transition heatmaps returned for 1w, 1m, and 3m horizons
- [x] KL-style method divergence returned
- [x] Transition alert log returned
- [ ] HMM random restarts and automatic BIC K selection are not implemented; K remains user-selected

## Feature 05 - Volatility Risk Premium Monitor

- [x] VIX/FRED implied-vol proxy loaded from category7 macro
- [x] GARCH physical expectation method implemented
- [x] HAR physical expectation method implemented
- [x] Rolling physical expectation method implemented
- [x] VRP raw spread returned
- [x] VRP squared variance form returned
- [x] VRP z-score returned
- [x] Cross-asset comparison table returned
- [x] BTZ return predictability regression returned with HAC standard errors
- [x] Current predicted forward return surfaced
- [x] OU mean-reversion half-life returned
- [x] Rolling 252d half-life series returned
- [x] VRP component attribution returned
- [ ] Z-score lookback is still fixed to 1260 days unless changed in code

## Feature 06 - Cross-Asset Connectedness and Spillover

- [x] Vol panel built from Feature 1 Yang-Zhang estimator
- [x] VAR(p) estimated on log-vol panel
- [x] BIC lag selection over p=1..5 implemented
- [x] Generalized FEVD implemented
- [x] Total connectedness index returned
- [x] Net spillover ranking table returned
- [x] Dynamic connectedness network nodes/edges returned
- [x] Pairwise FEVD heatmap returned
- [x] Rolling to/from decomposition returned
- [x] Connectedness regime alert returns top drivers
- [x] VAR impulse-response payload returned

## Feature 07 - Multivariate Volatility and DCC

- [x] Sample covariance returned
- [x] EWMA covariance returned
- [x] OAS-style Ledoit-Wolf shrinkage returned
- [x] Two-stage DCC-GARCH MLE returned
- [x] Current DCC correlation heatmap returned
- [x] DCC pair time series returned
- [x] Normal/crisis/delta comparison returned
- [x] Eigenvalue decomposition returned
- [x] Cumulative variance explained returned
- [x] Portfolio risk attribution returned
- [x] Pairwise covariance contribution heatmap returned
- [x] Minimum variance portfolio returned
- [x] Diversification ratio returned
- [x] Current vs equal-weight vs minimum-variance projected-vol comparison returned
- [ ] Fisher Z-test for crisis correlation amplification is not implemented yet

## Feature 08 - Volatility Stress Testing

- [x] Historical preset scenarios use local historical windows when present
- [x] Parametric stress scenario supported
- [x] Historical analog search uses macro/market variables and Mahalanobis distance
- [x] Reverse stress vector implemented from vol-change covariance and leverage direction
- [x] Vol shock bar chart returned
- [x] Portfolio P&L waterfall returned
- [x] Historical analog comparison returned
- [x] Reverse stress scenario output returned
- [x] Contagion IRF uses VAR MA coefficients when VAR fit succeeds
- [x] Multi-scenario comparison returned
- [x] Stress VaR/CVaR returned
- [x] DCC average correlation and recovery-time estimates returned in scenario table
- [ ] Monte Carlo uses 20,000 paths, not 100,000, to keep local runs tractable
- [ ] Bootstrap confidence bands for IRF are not returned yet

## Feature 09 - Portfolio Volatility Budget Monitor

- [x] Portfolio variance `w'Ωw` returned from DCC covariance
- [x] Regime probabilities pulled from Feature 04
- [x] Regime-weighted volatility target computed
- [x] Gross exposure cap applied to scaling factor
- [x] Euler marginal risk contributions returned
- [x] Equal vol budget comparison returned
- [x] Iterative budget-alignment reweighting implemented
- [x] Vol-to-target gap gauge returned
- [x] Scaling factor history returned
- [x] Regime-conditional target evolution returned
- [x] Rebalancing recommendation returned
- [x] Vol budget breach log returned
- [x] Historical vol-targeting backtest returned
- [x] Backtest statistics table returned: annualized return, vol, Sharpe, max drawdown, Calmar
- [ ] Transaction costs are not yet fully netted through the backtest path; turnover is returned for UI costing

## Honest Remaining Work

These are the remaining items that are not fully implemented in the exact institutional research-paper form:

- [ ] F02 explicit multiple optimizer starting points inside `arch` MLE are not controlled by our code
- [ ] F02 term-structure simulation confidence bands
- [ ] F03 full walk-forward expanding-window re-estimation
- [ ] F03 bootstrap forecast confidence bands
- [ ] F04 HMM 20 random restarts and BIC K-selection
- [ ] F05 user-selectable VRP z-score lookback
- [ ] F07 Fisher Z-test for crisis correlation amplification
- [ ] F08 bootstrap IRF confidence bands
- [ ] F08 100,000-path stress Monte Carlo, if we accept slower local runtime
- [ ] F09 explicit transaction-cost netting in historical backtest

Everything else in the previous audit that was marked missing or proxy has been implemented or replaced with a live statistical engine.
