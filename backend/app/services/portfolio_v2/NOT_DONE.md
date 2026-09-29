# Portfolio V2 - Skipped / Not Fully Done Items

Last updated: 2026-06-28

This file is the honest gap register for Portfolio V2. The feature runners F01-F13 exist and run against the current local parquet data, but a few outputs are proxies or are intentionally not fully institutional because the required licensed / user-supplied datasets are not present yet.

## Current Validation Baseline

- [x] Backend feature files exist for F01-F13.
- [x] Shared `core/data_loader.py`, `core/analytics.py`, and `core/performance.py` exist.
- [x] Append-only missing-data helper exists at `fetchers/fetch_missing_data.py`.
- [x] Previous smoke test ran all F01-F13 with zero failures on a 10-symbol daily payload.
- [x] Daily / weekly / monthly / hourly return matrix paths were smoke checked.

## Missing External Datasets

These are the main blockers for turning remaining proxy outputs into true live institutional outputs.

- [ ] Point-in-time index constituents
  - Needed for: F02 survivorship-bias corrected backtests and historical membership audit.
  - Current state: not present in local parquet.
  - Reason not done: requires CRSP/Compustat, Norgate, Bloomberg, index provider history, or another licensed constituent archive.
  - Next step: append to `backend/data/portfolio_v2/point_in_time_constituents.parquet`.

- [ ] Factor ETF AUM history
  - Needed for: F09 true ETF-flow/AUM crowding regime indicator.
  - Current state: not present in local parquet.
  - Reason not done: requires ETF issuer files, Bloomberg, ETF.com, or fund sponsor data.
  - Next step: append to `backend/data/portfolio_v2/factor_etf_aum_history.parquet`.

- [ ] Peer fund holdings / 13F normalized books
  - Needed for: F12 true peer-overlap network and actual fund-to-fund DebtRank.
  - Current state: not present as cleaned peer books.
  - Reason not done: requires parsed 13F filings or user-uploaded peer portfolios.
  - Next step: append to `backend/data/portfolio_v2/peer_fund_holdings.parquet`.

- [ ] Strategy-level position books
  - Needed for: F13 true inter-strategy netting, turnover, capacity constraints, and redeployment.
  - Current state: only deterministic strategy proxies are derived from asset returns.
  - Reason not done: requires internal strategy holdings / signal books.
  - Next step: append to `backend/data/portfolio_v2/strategy_position_books.parquet`.

## Feature-Level Gaps

### F01 Portfolio Construction Engine

- [~] Rolling rebalance stability history
  - Current output: `stability_table` reports dispersion across optimized objectives.
  - Reason not fully done: true stability needs a historical rebalance loop with point-in-time inputs and stored prior optimizer states.
  - Next step: add rolling rebalance simulation and persist weight snapshots.

- [~] DCC-GARCH covariance
  - Current output: live DCC-style covariance and average-correlation series exist.
  - Reason marked partial: optimized for realtime; not a full heavy research-mode institutional DCC calibration across very large universes.
  - Next step: add separate research-mode DCC path for large universes if needed.

### F02 Honest Backtesting Engine

- [ ] Survivorship-bias corrected backtest
  - Current output: live equity curve, drawdown, performance table, PSR/DSR, walk-forward, and bias audit exist.
  - Reason not done: missing point-in-time index constituents and delisted-security history.
  - Next step: wire `point_in_time_constituents.parquet` and delisting-adjusted returns.

- [~] Transaction-cost model
  - Current output: simple turnover proxy cost drag.
  - Reason partial: no broker-specific execution fills, spread history, or market-impact calibration per order.
  - Next step: connect F11 execution model and per-symbol spread / ADV cost curves.

### F03 Performance Attribution Engine

- [~] True factor attribution
  - Current output: active return, Brinson/Fachler tables, drawdown attribution, risk attribution, skill/luck bootstrap.
  - Reason partial: factor attribution uses available returns/weights and sector metadata; no uploaded proprietary factor exposure model.
  - Next step: allow explicit factor exposure matrices and benchmark factor returns.

- [~] Skill/luck test
  - Current output: bootstrap null distribution exists.
  - Reason partial: no manager-level decision log or trade-intent data to separate realized skill from ex-post portfolio exposure.
  - Next step: add trade/blotter metadata if available.

### F04 Portfolio Stress Testing and Scenario Engine

- [~] Scenario library
  - Current output: quantile scenarios, historical crisis replay where data exists, reverse stress, Monte Carlo, and correlation stress.
  - Reason partial: no official curated scenario catalog with exact shock vectors by asset class.
  - Next step: add scenario definition parquet with named shocks and crisis windows.

- [~] Monte Carlo
  - Current output: fast Gaussian simulation over portfolio return.
  - Reason partial: does not yet use copula/jump/stochastic-vol research path.
  - Next step: add research-mode heavy simulation path only if runtime budget allows.

### F05 Market-Implied Macro Factor Model

- [~] Macro data coverage
  - Current output: uses available Category 7 / macro parquet fields such as VIX, yield curve, credit spreads when present.
  - Reason partial: missing fields are skipped; full Bloomberg-style macro factor library is not guaranteed locally.
  - Next step: expand macro parquet with complete FRED / cross-asset macro series.

- [~] Asset-level macro exposure model
  - Current output: Ridge exposures per asset and portfolio with Newey-West diagnostics.
  - Reason partial: no true market-implied factor model from options/rates curves.
  - Next step: add rates/vol surface and implied inflation/credit factor sources.

### F06 Regime Detection and Regime-Aware Allocation

- [~] Regime model
  - Current output: rolling regime detection, transition matrix, regime performance, survival curves, conditional covariance/performance.
  - Reason partial: uses available returns and macro drivers; no full HMM state-space research calibration with all macro/liquidity features.
  - Next step: add research-mode HMM/Markov-switching estimator with richer macro panel.

- [~] Regime-aware weights
  - Current output: recommended weight scale by regime.
  - Reason partial: not a full constrained optimizer per regime.
  - Next step: run F01 optimizer inside each regime subset and emit regime-specific target weights.

### F07 Liquidity Analytics Engine

- [~] Liquidity model
  - Current output: Amihud, ADV, days-to-liquidate, liquidity VaR proxy, half-life, liquidation schedule, frontier.
  - Reason partial: no order book depth, intraday spread, quote, or venue-level liquidity data.
  - Next step: append spread/order-book/intraday liquidity panels if available.

- [~] Crisis liquidation cost
  - Current output: proxy based on available ADV/Amihud.
  - Reason partial: no historical stressed bid-ask/liquidity regimes per ticker.
  - Next step: add crisis liquidity calibration table.

### F08 Correlation, Diversification and Contagion Network Engine

- [~] Crisis correlation
  - Current output: crisis delta uses worst-return tail windows.
  - Reason partial: no user-selectable curated crisis scenario matrix.
  - Next step: add crisis preset selector and scenario correlation library.

- [~] Rolling pair correlations
  - Current output: top pairs get rolling correlation break checks.
  - Reason partial: all-pair rolling correlations are intentionally capped for speed.
  - Next step: add research-mode all-pair matrix if needed.

### F09 Alpha Decay and Factor Half-Life Engine

- [~] Crowding output
  - Current output: `crowding_proxy` uses cross-sectional dispersion.
  - Reason partial: ETF AUM/flow history is missing.
  - Next step: append factor ETF AUM history and replace proxy with true flow/AUM crowding.

- [ ] Publication decay
  - Current output: `publication_decay` returns `not_available`.
  - Reason not done: no documented factor publication-date database is available locally.
  - Next step: add factor publication metadata with dates, taxonomy, and post-publication return windows.

### F10 Growth-Optimal Position Sizing and Capital Allocation

- [~] Kelly sizing
  - Current output: live Kelly/constrained weights, growth curve, ruin probability surface, drawdown leverage, turnover-optimal curve.
  - Reason partial: estimates depend on return/covariance inputs only; no Bayesian posterior uncertainty or strategy-specific capacity model.
  - Next step: add posterior alpha uncertainty and F13 strategy capacity data.

- [~] Ruin probability
  - Current output: analytical fast approximation.
  - Reason partial: no heavy path-dependent ruin simulator.
  - Next step: add research-mode path simulator if desired.

### F11 Optimal Execution and Transaction Cost Engine

- [~] Execution model
  - Current output: Almgren-Chriss-style trajectory, implementation shortfall, frontier, joint schedule, cross-impact cost.
  - Reason partial: no broker fills, quote history, venue data, or intraday spread/depth by symbol.
  - Next step: append intraday spread/depth/fill datasets and calibrate per-symbol impact.

- [~] Target weights
  - Current output: supports `target_weights` payload, otherwise target equals current.
  - Reason partial: no UI/API persistence of separate target portfolio book yet.
  - Next step: persist target portfolios server-side.

### F12 Systemic Risk and Fire-Sale Contagion Engine

- [~] Peer portfolios
  - Current output: peer books are deterministic proxies generated from current holdings/cap-weight style shuffles.
  - Reason partial: true peer fund holdings are missing.
  - Next step: append `peer_fund_holdings.parquet`.

- [~] DebtRank
  - Current output: normalized overlap matrix is used as exposure proxy.
  - Reason partial: no directional counterparty/fund exposure matrix.
  - Next step: build real fund-to-fund/asset liquidation exposure matrix from peer holdings.

### F13 Multi-Strategy Portfolio Allocation and Risk Budgeting Engine

- [~] Strategy returns
  - Current output: deterministic proxies from asset returns: momentum, reversal, risk-parity proxy, equal weight.
  - Reason partial: no uploaded live strategy return streams or strategy books.
  - Next step: append `strategy_position_books.parquet` or strategy returns panel.

- [~] Netting / reallocation
  - Current output: proxy trade matrix between equal, Sharpe-momentum, and Kelly allocations.
  - Reason partial: true strategy-level trade intentions and capacity limits are missing.
  - Next step: persist strategy orders/positions and capacity limits.

## Speed-Up Items Intentionally Not Done

These are not feature gaps, but they were consciously skipped from `speed upgrades.md`.

- [ ] `PerfCounter.__slots__`
  - Reason: low measured impact compared with cache/vectorization paths.

- [ ] Sparse SVD in factor-structured covariance
  - Reason: current matrices are small enough that full SVD is safer and more stable.

- [ ] Numba/JIT risk-parity optimizer
  - Reason: adds warm-up and packaging risk; inverse-vol warm starts already improved runtime safely.

- [~] Single global all-estimator covariance allocator
  - Reason: estimator outputs have different shapes and downstream needs; shared covariance caching is already in place.

- [~] Precomputed precision-network covariance injection
  - Reason: would require changing function signatures across feature contracts.

- [~] Broad `safe_eigh` replacement
  - Reason: only wired where eigenvalues are needed; other functions require vectors or custom ordering.

- [~] Broad `dates_to_str` replacement
  - Reason: date formatting is not a measured bottleneck in the smoke path.

## Data Fetch Plan

The append-only fetch helper is:

`backend/app/services/portfolio_v2/fetchers/fetch_missing_data.py`

It currently documents targets for:

- `point_in_time_constituents.parquet`
- `factor_etf_aum_history.parquet`
- `peer_fund_holdings.parquet`
- `strategy_position_books.parquet`

No runtime feature imports this fetcher. It is intentionally manual / append-only so normal analytics runs do not overwrite existing data.

