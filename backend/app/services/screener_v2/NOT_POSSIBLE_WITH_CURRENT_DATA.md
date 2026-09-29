# Screener V2 — Not Possible With Current Data / Infrastructure

This file is limited to items that cannot be made production-correct from the current local parquet/fundamental/macro files alone. Items that are possible with current data have been implemented in `core/analytics.py` and `features/feature_01.py` through `feature_07.py`.

## Data Missing

- [ ] True point-in-time fundamentals by as-of date
  - Required for: no-lookahead formula execution, academic strategy historical screens, production-grade backtests, historical composite IC/IR weighting.
  - Current state: local fundamentals have report dates and history, but not a clean as-of availability panel.
  - Fetcher scaffold: `fetchers/fetch_missing_data.py` -> `PIT_FUNDAMENTALS`.

- [ ] Delisted securities and delisting returns
  - Required for: survivorship-bias corrected backtests.
  - Current state: master universe contains current/available traded symbols, not a complete historical delisting panel.
  - Fetcher scaffold: `fetchers/fetch_missing_data.py` -> `DELISTED_SECURITIES`.

- [ ] Prior screen run history
  - Required for: entries/exits/rank-shift change reports, percentile-rank shift alerts, alert forward-performance tracker, screen entry/exit annotations on equity curves.
  - Current state: feature calls are stateless/read-only.
  - Fetcher/storage scaffold: `fetchers/fetch_missing_data.py` -> `SCREEN_RUN_HISTORY`.

- [ ] Persistent saved screen definitions
  - Required for: saved screens, scheduled re-runs, watchlist creation from screen results.
  - Current state: runtime can emit current result rows, but cannot persist user screen definitions.
  - Fetcher/storage scaffold: `fetchers/fetch_missing_data.py` -> `SAVED_SCREENS`.

- [ ] Alert state and delivery log
  - Required for: daily/weekly alert scheduling, email delivery, alert hit-rate measurement, deduplication.
  - Current state: S6 emits alert candidates for the current run only.
  - Fetcher/storage scaffold: `fetchers/fetch_missing_data.py` -> `ALERT_STATE`.

## Infrastructure Missing

- [ ] Job runner / scheduler
  - Blocks: scheduled screen re-runs, daily/weekly email delivery, persistent watchlist monitoring.
  - Why data alone is insufficient: these require timed execution and delivery state, not just computations.

- [ ] API route registration for Screener V2
  - Blocks: static screen result API endpoint, optimizer/ML feed handoff, one-click watchlist creation.
  - Current state: backend registry exists; routes were intentionally not wired in this pass.

- [ ] File upload/API endpoint for CSV ticker-list ingestion
  - Blocks: custom ticker list upload.
  - Current state: backend accepts ticker strings/lists, but no upload route is registered.

## Computation That Needs Missing Data To Be Correct

- [ ] Purged walk-forward IC/IR weighting
  - Needs PIT score history and future returns aligned by valid as-of timestamps.

- [ ] Ridge-regularized OLS composite weight estimation
  - Needs stable historical factor matrix and forward target returns without lookahead.

- [ ] Regime-conditional IC decomposition
  - Needs PIT scores by date. Current implementation can compute macro-regime performance from realized returns, but not historical IC of signals by regime.

- [ ] True ERP5 and other 5Y academic strategy histories
  - Needs PIT fundamentals and enough clean annual statement history by ticker.

- [ ] Proper rebalancing-date randomization Monte Carlo and full PBO
  - Needs rolling rebalance simulation over historical score formation dates. Current implementation emits a bootstrap Sharpe/PBO proxy from available realized returns.

- [ ] Historical as-of formula date picker
  - Needs expression evaluation against PIT panels at selected historical dates.

## Implemented Proxies To Be Aware Of

- [x] Altman trend uses available report-date fundamentals, not audited as-of availability.
- [x] PBO is a bootstrap proxy, not full combinatorially symmetric cross-validation PBO.
- [x] Regime conditional performance is based on selected realized returns and macro regimes, not historical signal IC by regime.
- [x] Rolling formula functions currently operate on current panel order with diagnostics, not true time-series formula execution.
