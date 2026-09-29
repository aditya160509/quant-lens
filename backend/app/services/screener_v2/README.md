# Screener V2 Backend

This package implements the Screener V2 backend feature layer from `screener features.md`.
It is not wired to routes yet.

## Data Inventory

- [x] Daily adjusted OHLCV: `backend/data/market_universe.parquet`
- [x] Hourly OHLCV available for future intraday screens: `backend/data/market_universe_hourly.parquet`
- [x] Master fundamentals: `backend/data/fundamentals/master_fundamentals.parquet`
- [x] Macro/regime panel: `factors/data/processed/category7_macro_regime.parquet`
- [x] Fama/French FF5 and momentum CSVs: `backend/data/factors_us/`
- [ ] Clean point-in-time fundamentals by as-of date: fetcher scaffold created, dataset not present
- [ ] Delisted securities panel for survivorship-bias correction: fetcher scaffold created, dataset not present
- [ ] Persistent saved screens / alert state / screen run history: fetcher scaffold created, server storage not wired

## Feature Checklist

- [x] S1 Core Multi-Factor Screener Engine
  - [x] Ranked screener table
  - [x] Filter funnel waterfall
  - [x] Cross-sectional percentile context
  - [x] Sector heatmap view
  - [x] Quick-look card
  - [ ] Saved screens persistence: output key exists, server persistence not wired

- [x] S2 Formula Builder and Custom Expression Screener
  - [x] Formula parser/evaluator for arithmetic, comparisons, `rank`, `zscore`, `sector_rank`, `sector_zscore`, `where`
  - [x] Formula result table
  - [x] Formula validation panel
  - [x] Historical formula backtest proxy from local price panel
  - [x] Factor zoo comparison

- [x] S3 Composite Quant Score Engine
  - [x] Composite score ranking
  - [x] Component decomposition
  - [x] Component IC/IR proxy leaderboard
  - [x] Factor correlation heatmap
  - [x] Composite vs factor backtest
  - [x] Regime conditional breakdown proxy by sector

- [x] S4 Academic Strategy Screener Library
  - [x] Strategy leaderboard
  - [x] Per-strategy stock list
  - [x] Piotroski F-score proxy
  - [x] Altman Z-score status
  - [x] Strategy correlation matrix
  - [x] Historical strategy performance proxy
  - [ ] True historical academic screens with no lookahead: requires point-in-time fundamentals

- [x] S5 Screener Backtester with Point-in-Time Validation
  - [x] Equity curve
  - [x] Full performance statistics
  - [x] Rolling performance
  - [x] Holding-period sensitivity
  - [x] Rebalancing-date sensitivity
  - [x] Turnover report
  - [x] Sector attribution
  - [x] Regime conditional performance proxy
  - [x] Monte Carlo Sharpe distribution
  - [x] Stock-level attribution
  - [ ] Production-grade point-in-time validation and delisting correction: requires appended PIT and delisted datasets

- [x] S6 Alert Engine and Watchlist Monitor
  - [x] Alert feed from current watchlist metrics
  - [x] Alert performance tracker structure
  - [x] Screen entry/exit log
  - [ ] Persistent alert scheduler and notification delivery: needs server job runner/storage

- [x] S7 Comparative Relative Valuation Screener
  - [x] Four-dimension valuation card
  - [x] Sector valuation landscape heatmap
  - [x] Own-history percentile time series from available fundamentals history
  - [x] Peer comparison table

- [x] S8 Screener Result Export and Integration Layer
  - [x] Instant TSV/JSON export payload
  - [x] API endpoint metadata placeholder
  - [x] Change report for current run
  - [ ] Route/API registration: intentionally not wired in this pass
  - [ ] Historical change report across runs: requires screen run history storage

## Files

- `core/data_loader.py`: local parquet and CSV readers.
- `core/analytics.py`: reusable screener analytics.
- `features/feature_01.py` through `features/feature_08.py`: feature runners.
- `registry.py`: feature manifest and `run_feature(feature_id, payload)`.
- `fetchers/fetch_missing_data.py`: append-only scaffolds for datasets that are not currently local.

## Smoke Usage

```python
from backend.app.services.screener_v2.registry import run_feature

payload = {"universe": "AAPL MSFT NVDA AMZN GOOGL META JPM XOM", "max_symbols": 8}
result = run_feature("01", payload)
print(result["summary_cards"])
```

## Validation

- [x] `python3 -m compileall -q backend/app/services/screener_v2`
- [x] Smoke-ran S1-S8 with a 10-symbol local universe.
- [x] Every feature returned `status: ok`.
- [x] Every feature returned the spec-facing output keys listed above.
- [x] No API route was wired in this pass.
