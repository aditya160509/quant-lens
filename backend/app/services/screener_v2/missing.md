> Historical audit, superseded by [DONE.md](DONE.md) and the central Screener V2 review. Checked boxes here are not current verification evidence. Removed strategies and estimators must not be restored from this checklist.

## Attachment Upgrade Checklist — 2026-07-06

Scope: applied the Screener V2 backend upgrades from `/Users/adityabalaji/.codex/attachments/cd5147f4-cb3b-484b-892a-a3bd69facdd3/pasted-text.txt`.

- [x] FormulaEngine now evaluates `lag()` and `rolling_*()` for PIT fundamental fields from `fundamental_history`: `roa`, `roe`, `current_ratio`, `debt_equity`, `gross_margin`, `operating_margin`, and `mcap`.
- [x] Formula diagnostics now explicitly state PIT fundamental lags use reported filing periods, not trading-day periods.
- [x] S3 composite engine now supports `weighting_mode: "ic_ir"` using bootstrap cross-sectional IC-IR proxy weights.
- [x] S3 composite engine now supports `weighting_mode: "ridge"` using ridge-regularized current cross-section weights.
- [x] S3 Feature 03 now surfaces weighting diagnostics in response metadata.
- [x] S4 academic strategy scores now include a four-block QMJ implementation: profitability, growth, safety, payout, and final `quality_minus_junk`.
- [x] S4 quantitative momentum now uses true monthly momentum smoothness from local prices instead of an inverse-volatility proxy.
- [x] S4 dual momentum now gates relative momentum by trailing risk-free return rather than zero return.
- [x] S5 `score_backtest(...)` now emits an explicit survivorship-bias warning in statistics.
- [x] S5 added weekday-specific rebalancing sensitivity table: Monday through Friday.
- [x] S6 added same-session historical alert precision replay for golden-cross and RSI-extreme alerts.
- [x] `component_ic_leaderboard(...)` now reuses shared bootstrap index draws instead of generating samples per field.
- [x] `latest_technical_features(...)` now uses a shared OHLC pivot helper for high/low/open matrices.
- [x] `apply_filters(...)` now skips untouched range filters before constructing numeric masks.
- [x] S1 market-cap bucket chart is now optional via `include_market_cap_buckets`.
- [x] Compile check passed: `python3 -m compileall -q backend/app/services/screener_v2`.
- [x] Smoke check passed for S1-S8 through `run_feature(...)`.
- [x] Targeted formula smoke passed for PIT fundamentals: `lag(roa, 1)` and `rolling_mean(current_ratio, 2)`.
- [x] Targeted S3 smoke passed for manual, IC-IR, and ridge weighting modes.
- [ ] True cross-session alert precision remains not done; it requires persistent alert history and a job runner.
- [ ] True walk-forward IC-IR/ridge weights remain not done; they require stored historical score snapshots.
- [ ] True delisted-security survivorship correction remains not done; it requires delisted-security price/return history.

## Revision Audit Checklist — 2026-07-06

Scope: applied the remaining Screener V2 performance/correctness fixes from `/Users/adityabalaji/.codex/attachments/596f3a7d-667f-4e43-aeeb-da1a6356d1b6/pasted-text.txt`.

- [x] Cache staleness fixed: market matrix caches and fundamental-history caches now include source parquet `mtime` version stamps.
- [x] Market OHLCV cache now pre-indexes the parquet by ticker, avoiding full dataframe `isin` scans on every subset miss.
- [x] Ticker cache keys are order-independent and de-duplicated through sorted normalized symbols.
- [x] Fundamental history cache is no longer capped at `8192` ticker entries and is backed by a one-per-version fundamentals frame cache.
- [x] Formula time-series functions now support true local histories for `return_1w`, `return_1m`, `return_3m`, `return_6m`, `return_12m`, `r_5d`, `r_21d`, `r_63d`, `r_126d`, `r_252d`, `r_jt`, and `momentum_jt`.
- [x] Formula fallback diagnostics now list the full supported exact-return horizon set.
- [x] Relative valuation now loads each ticker's history once per card and derives percentile, slope, and chart rows from that shared frame.
- [x] Default own-history valuation now uses a blended percentile across available valuation metrics instead of silently using the first fallback metric.
- [x] Full strategy performance metadata and table now share one `_select_strategies_for_backtest(...)` helper.
- [x] `metric_panel(...)` now raises on duplicate ticker rows after the technical/fundamental merge.
- [x] S6 alert dashboard removed the duplicate `vratio` display column while preserving `volume_spike_ratio` and formula compatibility.
- [x] Compile check passed: `python3 -m compileall -q backend/app/services/screener_v2`.
- [x] Smoke check passed for S1-S8 through `run_feature(...)`.
- [x] Targeted formula smoke passed for `lag(r_21d, 2) + rolling_mean(momentum_jt, 3)` with exact local time-series diagnostics.
- [ ] Superset-aware custom matrix cache is not implemented; the versioned/pre-indexed LRU removes the current hot scan and staleness bugs without adding a fragile manual eviction policy.

## Performance Pass Checklist — 2026-07-05

Scope: added a dedicated Screener V2 performance layer and wired the highest-impact repeated data transformations through it. This pass avoids response-shape changes and keeps runtime feature calls read-only.

- [x] Added `core/performance.py` with bounded process-local LRU caches.
- [x] Cached close-price matrix construction by stable ticker set and lookback.
- [x] Cached volume matrix construction by stable ticker set and lookback.
- [x] Cached return matrix construction by stable ticker set, lookback, and coverage threshold.
- [x] Cached per-symbol fundamental history lookups.
- [x] Updated `data_loader.close_matrix`, `volume_matrix`, `returns_matrix`, and `fundamental_history` to use the performance layer.
- [x] Returned defensive DataFrame copies from cached loader wrappers so feature code cannot mutate cached objects.
- [x] Optimized full strategy performance loop to avoid rebuilding the same ticker index for every strategy.
- [x] Added cache introspection via `performance_cache_info()`.
- [x] Compile check passed: `python3 -m compileall -q backend/app/services/screener_v2`.
- [x] Smoke check passed for S1-S8 twice in one process.
- [x] Observed all-feature smoke speed improved from about `9.332s` cold to about `2.364s` warm in the same Python process.
- [ ] Cross-process shared cache is not implemented; this would require Redis/diskcache or an API worker cache policy.
- [ ] Parallel feature execution is not implemented; current safest speedup is deterministic single-process memoization.

## Revision Audit Checklist — 2026-07-01

Scope: applied the implementable fixes from `/Users/adityabalaji/.codex/attachments/3b4356f7-3145-4411-9712-080b2538fe42/pasted-text.txt`. This pass focused on correctness gaps in technical indicators, beta fallback visibility, formula time-series handling, academic strategy hygiene, and explicit metadata.

- [x] S1 SMA windows now compute one rolling frame per window and derive both current SMA values and same-day cross flags from that frame.
- [x] S1 `sma_cross_event` now aligns both input frames before computing event flags.
- [x] S1 Wilder smoothing now uses a strict seed window and no longer resets to raw values after missing observations.
- [x] S1 ADX/DMI now reuses the ATR Wilder-smoothed true-range denominator instead of recomputing it independently.
- [x] S1 beta output now emits `beta_effective`, `beta_effective_source`, and `beta_252_unavailable_reason`.
- [x] S1 top table now exposes the effective beta fields so the UI can show the actual beta used.
- [x] S1 dropped requested symbols are captured in `latest_technical_features.attrs`, propagated through `metric_panel.attrs`, and surfaced in Feature 01 metadata.
- [x] S2 formula engine now reconstructs true historical `return_1d` for `lag()` and rolling operators from local close history.
- [x] S2 formula diagnostics now distinguish exact local time-series support from snapshot-order fallback behavior.
- [x] S3 component IC bootstrap now preserves duplicate bootstrap samples instead of accidentally de-duplicating through index selection.
- [x] S4 Piotroski F5 now prefers long-term debt, falls back to total debt, and emits `f5_leverage_field_used`.
- [x] S4 academic strategy merge now validates one-to-one ticker rows and raises on duplicate ticker inputs or duplicate Piotroski outputs.
- [x] S4 strategy leaderboard and full strategy performance now exclude helper/intermediate criteria, proxy/spec internals, Altman raw fields, and `best_strategy_score`.
- [x] S4 full strategy performance now emits `historical_strategy_performance_metadata` with evaluated and excluded strategy lists.
- [ ] Server-side saved-screen persistence remains not done; requires storage/API state outside current local computation layer.
- [ ] True PIT non-price formula histories remain not done; requires append-only historical metric panels, not just current fundamentals snapshots.
- [ ] Batch quick-look endpoint remains intentionally not added; audit marked it optional unless a real UI bottleneck appears.

## Exact Formula Audit Checklist — 2026-07-01

Scope: applied the implementable formula corrections from `/Users/adityabalaji/.codex/attachments/c6389038-65d0-4b91-b17c-dc009a2a14c4/pasted-text.txt`. Items requiring persistent point-in-time panels, delisted-security history, prior alert snapshots, or scheduled jobs remain open and are marked clearly.

- [x] S1 GICS-like industry-group tier added through static `industry -> industry_group` mapping.
- [x] S1 industry-group relative score and per-factor industry-group relative percentiles added.
- [x] S1 `PROX52 = P_t / H52_t` added as `prox52`.
- [x] S1 `VRATIO = volume_today / volume_20d` added as `vratio`.
- [x] S1 technical loader now fetches `SPY` alongside the requested universe for true market beta.
- [x] S1 true SPY beta emitted as `beta_252`; universe fallback is separately named `beta_universe_proxy`.
- [x] S1 `beta_spy` compatibility alias now maps only to true SPY beta.
- [x] S1 ATR switched from simple rolling average to Wilder smoothing.
- [x] S1 ADX switched from simple DX rolling mean to Wilder smoothing.
- [x] S1 RSI gain/loss averages switched to Wilder smoothing.
- [x] S1 same-day SMA cross fields added for SMA 20/50/100/200.
- [x] S1 golden/death cross event and recent-20-day flags added.
- [x] S1 filters added for `prox52`, `vratio`, recent golden cross, and recent death cross.
- [x] S2 existing price/OHLC `lag` and rolling operators verified against true local price history.
- [x] S2 non-price lag/rolling operators remain allowed but emit warning diagnostics because PIT field histories do not exist.
- [x] S3 component score path now sign-corrects raw values before winsorization/ranking.
- [x] S3 winsorization changed from mean ± 3σ to 1st/99th percentile clipping.
- [x] S3 beta neutralization changed from correlation-as-slope to true OLS slope neutralization.
- [x] S3 effective number of independent factors added as `effective_number_of_factors`.
- [x] S4 Greenblatt ROIC added from EBIT over working-capital-plus-fixed-assets when local statement history has the required fields.
- [x] S4 share-count-based net payout yield added as `net_payout_yield_spec` when local statement history has share counts.
- [x] S4 spec-labelled Piotroski criteria and `piotroski_f_score_spec` added when two periods of local fundamentals exist.
- [x] S4 old level-based Piotroski remains as `piotroski_f_score_proxy` fallback.
- [x] S5 eligibility gating added so selected names must have sufficient local price history at the backtest start.
- [x] S5 Sharpe now subtracts annualized local risk-free rate when available.
- [x] S5 Sortino now uses full-sample downside semi-deviation versus risk-free rate.
- [x] S5 full rebalancing-date Monte Carlo PBO added behind `run_full_pbo`.
- [x] S6 `VOLUME_SPIKE` alert now uses canonical `vratio`.
- [x] S6 same-day price cross above/below SMA 20/50/100/200 alerts added.
- [x] S7 own-history percentile now excludes the current observation from the reference set.
- [x] S7 OLS re-rating/de-rating slope added to the valuation card.
- [x] Compile check passed: `python3 -m compileall -q backend/app/services/screener_v2`.
- [x] Smoke check passed for S1-S8, including `run_full_pbo` with a small trial count.
- [ ] Full point-in-time formula `lag` and rolling support for fundamentals/derived non-price fields remains not done; requires historical PIT metric panels.
- [ ] True walk-forward ICIR with purged overlapping return windows remains not done; requires stored historical score panels.
- [ ] Delisted-security survivorship correction remains not done; requires delisted ticker history.
- [ ] Percentile-rank shift alerts remain not done; requires prior alert snapshots or persistent daily state.
- [ ] Scheduled screens, delivery, and realized alert precision remain not done; require a job runner and persistence.

## Upgrade Checklist — Attachment Pass 2026-07-01

Scope: applied every upgrade from `/Users/adityabalaji/.codex/attachments/3521d202-b3b8-491a-8f56-ebdb2185bab5/pasted-text.txt` that can be implemented with current local Screener V2 data and without adding server persistence or a job runner.

- [x] S1 quick-look now emits full price chart data in `chart_full`.
- [x] S1 quick-look now emits fixed-window chart data in `chart_windows` for 1M, 3M, 1Y, 3Y, and 10Y.
- [x] S2 `lag(close,N)` and price/OHLC rolling operators now evaluate against true local price history through `close_matrix`.
- [x] S2 non-price `lag` and rolling operators still run, but return an explicit diagnostic warning because point-in-time field history is not available yet.
- [x] S3 per-stock score decomposition added as `per_stock_score_decomposition`.
- [x] S3 component IC-IR proxy now uses bootstrap-resampled cross-sectional IC mean/std instead of dividing IC by raw component value volatility.
- [x] S4 all-strategy performance table added as `historical_strategy_performance_all`.
- [x] S5 turnover report now uses a dated rank-drift rebalance series from local price history, replacing the static top-N ratio.
- [x] S6 `volume_spike_ratio` added to the metric panel.
- [x] S6 volume spike alert added as `VOLUME_SPIKE` with configurable `volume_spike_multiple`.
- [x] S6 watchlist live dashboard now includes `volume_spike_ratio` when available.
- [x] S7 universe valuation percentile added to the four-dimension valuation card.
- [x] S7 per-metric universe percentile table added as `universe_percentile_table`.
- [x] Compile check passed: `python3 -m compileall -q backend/app/services/screener_v2`.
- [x] Smoke check passed for S1-S8 through `run_feature(...)`.
- [ ] Saved screen persistence remains not done; requires server-side storage/API state.
- [ ] Scheduled screen reruns, email delivery, and realized alert precision remain not done; require job runner and notification plumbing.
- [ ] True point-in-time fundamental history remains not done; requires append-only PIT fundamentals and delisted-security datasets.

## Implementation Checklist — 2026-06-28

Scope: implemented all possible non-S8 items from this file. S8 was intentionally skipped per instruction.

### S1 — Core Multi-Factor Screener Engine

- [x] Exchange filter support added when exchange metadata exists.
- [x] Float percentage filter support added when float metadata exists.
- [x] Shares outstanding filter added.
- [x] SMA crossover event detection added through `sma20_50_cross_days` and `sma50_200_cross_days`.
- [x] EMA 20/50/100/200 filters and distance fields added.
- [x] MACD signal, histogram, bullish flag, and recent crossover age added.
- [x] Bollinger band position and width percentile added.
- [x] ATR and ATR-percent-of-price added.
- [x] ADX and DMI direction fields added.
- [x] Stochastic oscillator added.
- [x] Williams %R added.
- [x] OBV 20-day slope added.
- [x] Consecutive up/down day fields added.
- [x] Short-term reversal flag added.
- [x] Relative performance vs SPY/universe proxy added.
- [x] Forward P/E filter added.
- [x] P/CF filter added.
- [x] EV/EBIT filter added.
- [x] Interest coverage filter added.
- [x] Revenue growth YoY filter added from available fundamentals history.
- [x] EPS growth YoY filter added from available fundamentals history.
- [x] Revenue growth 3Y CAGR filter added from available fundamentals history.
- [x] Debt/EBITDA filter added.
- [x] Payout ratio filter added.
- [x] Dividend-paying-only toggle added.
- [x] FF3 residual IVOL field/filter added.
- [x] MAX factor field/filter added.
- [x] 52-week high proximity field/filter added.
- [x] 21-day volatility forecast field/filter added.
- [x] Amihud illiquidity percentile added as filterable field.
- [x] Sector-relative and industry-relative percentile fields added for primary metrics.
- [x] Company name column added when local fundamentals include name metadata.
- [x] Heatmap includes market-cap size metadata.
- [x] Sub-$1 penny stock exclusion toggle added.
- [x] Market cap bucket distribution preview added.
- [x] Dollar volume preset liquidity floors added backend-side through `dollar_volume_preset`.
- [ ] Saved screen persistence remains not wired; requires server storage.
- [ ] Scheduled screen re-run/change notifications remain not wired; requires job runner and notification channel.
- [ ] Custom ticker list CSV upload remains frontend/API work, not backend runtime logic.
- [ ] Dollar volume preset liquidity floors remain frontend preset work; backend accepts explicit dollar volume floors.

### S2 — Formula Builder

- [x] `lag(field,N)` parser support added with explicit snapshot-order diagnostic.
- [x] `rolling_mean`, `rolling_std`, `rolling_max`, `rolling_min` parser support added with explicit snapshot-order diagnostic.
- [x] `sector_rank()` and `sector_zscore()` exercised in smoke test.
- [x] OHLCV fields exposed in formula namespace: `open`, `high`, `low`, `close`, `adj_close`, `volume_20d`.
- [x] FF factor fields exposed in formula namespace when local factor files parse: `mkt_rf`, `smb`, `hml`, `rmw`, `cma`, `mom`, `rf`.
- [x] Factor zoo comparison now includes IC vs 1M return.
- [x] Long-short backtest support added through shared `score_backtest`.
- [x] Backend formula template library added.
- [ ] Historical date picker/as-of formula execution remains not done; requires PIT/as-of panel and API/UI state.
- [ ] Template library UI remains not done; backend accepts formula strings.
- [ ] True time-series formula operators remain marked as snapshot-order diagnostics until PIT formula execution exists.

### S3 — Composite Quant Score Engine

- [x] Preset composite strategies added: AQR quality-value, momentum-quality, low-vol-quality, VMQ, FF5 screen, conservative formula, trending value.
- [x] Sector neutralization option added.
- [x] Beta neutralization option added.
- [x] Winsorize option added.
- [x] Signed rank output option added.
- [x] Factor sign auto-correction added for negative-weight fields.
- [x] Factor correlation redundancy alerts added for pairs above 0.6 absolute correlation.
- [x] Composite vs factor backtest supports long-short and score-weighted construction.
- [ ] Full IC-IR weighting from purged walk-forward history remains not done; requires historical PIT score formation.
- [ ] Ridge-regularized OLS weight estimation remains not done; requires stable PIT target matrix.
- [ ] IC-IR estimation window toggle remains not done for same PIT reason.
- [ ] Regime-conditional IC decomposition remains not done; current output still uses current cross-section/sector proxy.

### S4 — Academic Strategy Screener Library

- [x] Graham Net-Net proxy added.
- [x] O'Shaughnessy Value Composite Two added.
- [x] ERP5 proxy added using available multi-period fundamentals where present.
- [x] Deep Value Yield added.
- [x] Mohanram G-Score proxy added.
- [x] Sloan Accruals signal added.
- [x] Dual Momentum added.
- [x] Twin Momentum added.
- [x] Quantitative Momentum smoothness proxy added.
- [x] O'Shaughnessy Trending Value added.
- [x] Conservative Formula updated to low-vol + net payout yield + momentum.
- [x] Altman Z + Piotroski overlay added.
- [x] Meb Faber shareholder yield proxy added.
- [x] Dogs of the Dow proxy added.
- [x] High Dividend Low Payout screen added.
- [x] Altman Z'' score added.
- [x] Interest Coverage Distress screen added.
- [x] Acquirer's Multiple now uses EV/EBIT when available.
- [x] Piotroski individual criterion scorecard added.
- [x] Historical strategy statistics table added for selected strategy.
- [x] Strategy correlation matrix is denser because more strategies are implemented.
- [x] Altman Z 8-quarter trend added where local fundamentals history exists.
- [ ] True ERP5 5Y PIT history and no-lookahead academic backtests require PIT fundamentals.
- [ ] Altman Z 8-quarter trend per ticker remains limited by available history frequency/coverage.
- [ ] Regime-conditional annualized strategy performance remains not done; requires PIT strategy return series.

### S5 — Screener Backtester

- [x] Score-weighted portfolio construction added.
- [x] Long-short portfolio construction added.
- [x] Rebalancing frequency parameter now flows into cost/stat calculations.
- [x] Sortino ratio added.
- [x] Calmar ratio added.
- [x] Average drawdown added.
- [x] Hit rate added.
- [x] Average gain/loss added.
- [x] Best/worst calendar year added.
- [x] Holding-period sensitivity now passes different rebalance-day assumptions.
- [x] Stock-level attribution now includes entry/exit dates.
- [x] Turnover report replaced hardcoded static snapshot with rebalance proxy.
- [x] Sector-neutral portfolio construction added for current-score backtests.
- [x] Rebalancing-date sensitivity now runs separate offset assumptions.
- [x] PBO proxy added from bootstrap Sharpe distribution.
- [x] Macro-regime conditional performance added from local macro/regime parquet.
- [ ] True point-in-time fundamentals remain not enforceable until PIT dataset is appended.
- [ ] Survivorship-bias correction remains not enforceable until delisted-security dataset is appended.
- [ ] Sector-neutralized rebalancing remains not fully implemented as a dynamic portfolio rebalance engine.
- [ ] Proper rebalancing-date randomization Monte Carlo and PBO remain not done; require full rolling rebalance simulations.

### S6 — Alert Engine

- [x] Metric threshold alerts added.
- [x] Formula/core score threshold alerts added.
- [x] Volume/price confirmation alert added.
- [x] Price vs SMA/MACD/Bollinger technical alerts added.
- [x] Consecutive day trigger alerts added.
- [x] Watchlist monitoring dashboard output added.
- [x] Alert performance tracker includes forward-window note.
- [x] Fundamental change alerts added from available report history.
- [ ] Percentile-rank shift alerts remain not done; require previous intraday/daily alert state.
- [ ] Fundamental change alerts remain not done; require scheduled quarterly comparison state.
- [ ] Alert scheduling, email delivery, and realized hit-rate tracking remain not wired; require job runner and persistence.
- [ ] Screen entry/exit annotations on equity curve require persistent screen run history.

### S7 — Comparative Relative Valuation

- [x] Industry peer comparison added through `peer_scope=industry`.
- [x] Custom peer list support added.
- [x] Market-cap bucket peer comparison added.
- [x] Historical context window toggle added.
- [x] Universe-wide four-dimension cards added.
- [x] Sector valuation landscape heatmap expanded to sectors x metrics.
- [x] Own-history percentile time series made metric-selectable.
- [x] Peer comparison table includes better/worse delta vs selected ticker.
- [x] Re-rating/de-rating trend annotation added to history series.

### S8 — Export and Integration

- [ ] Skipped entirely per user instruction: "except s8".

Looking at the spec vs the implementation across all 8 features:

**S1 — Core Multi-Factor Screener Engine**

```
- Exchange filter (NYSE/NASDAQ/AMEX/OTC)
- Float percentage filter
- Shares outstanding filter
- SMA crossover event detection (crossed above/below within last N days)
- EMA filters (20/50/200-day)
- MACD signal (bullish/bearish crossover within last N days, histogram)
- Bollinger Bands filter (price vs bands, band width percentile)
- ATR filter (absolute and % of price)
- ADX filter (trend strength + DMI+/DMI- direction)
- Stochastic oscillator filter
- Williams %R filter
- OBV trend filter (slope positive/negative over N days)
- Consecutive up/down days filter
- Short-term reversal flag (bottom decile 1W/1M)
- Relative performance vs SPY filter (alpha proxy)
- Forward P/E filter
- P/CF filter
- EV/EBIT filter
- Interest coverage ratio filter
- Revenue growth YoY filter
- EPS growth YoY filter
- Revenue growth 3Y CAGR filter
- Debt/EBITDA filter
- Payout ratio filter
- Dividend-paying-only toggle
- IVOL filter (idiosyncratic vol from FF3 residual)
- MAX factor filter (max single-day return past 21 days)
- 52-week high proximity score as screener filter
- Volatility forecast 21-day filter
- Amihud illiquidity percentile filter (cross-sectional rank only; raw computed but not percentile-ranked as a filter)
- Sector-relative and industry-relative percentile view on all metrics (currently universe-only)
- Company name column in output
- Heatmap sized by market cap (size encoding not present — flat grid)
- Saved screen persistence (acknowledged in meta)
- Scheduled screen re-run with change notifications
- Custom ticker list upload (CSV)
- Sub-$1 penny stock exclusion toggle
- Dollar volume preset liquidity floors UI
- Market cap bucket distribution preview before run
```

**S2 — Formula Builder**

```
- lag(field, N) time operator
- rolling_mean(field, N), rolling_std(field, N), rolling_max(field, N), rolling_min(field, N)
- sector_rank() and sector_zscore() — NOT implemented (FormulaEngine._call has stubs but sector_rank uses panel["sector"] groupby which requires panel to have sector loaded at call time; sector_zscore groupby transform is there but untested)
- All OHLCV field names as formula variables (open/high/low/volume/adj_close not exposed, only derived metrics in panel)
- All FF factor fields in formula namespace (mkt_rf, smb, hml, rmw, cma, mom not in panel)
- Historical date picker (run formula as-of a past date)
- Template library pre-built formulas (no library UI or loader)
- Factor zoo comparison ranks formula IC against every other platform signal (currently only computes mean/cutoff/coverage, not IC)
- Long-short backtest (top decile minus bottom decile) — current score_backtest only does long-only top-N
- Formula field: lag, rolling operators not parsed by FormulaEngine (AST only handles arithmetic/compare/call; no time-series node)
```

**S3 — Composite Quant Score Engine**

```
- IC-IR weighting (weight ∝ Spearman IC / IC std from walk-forward history) — currently only equal/manual weight
- Ridge-regularized OLS weight estimation
- IC-IR estimation window toggle (63/126/252/expanding)
- Sector neutralization (subtract sector median before combining)
- Beta neutralization
- Winsorize ±3σ normalization option
- Signed rank [−1,+1] output scale
- All preset composite strategies (AQR Quality Value, Momentum-Quality, Low-Vol Quality, VMQ, FF5 Screen, Conservative Formula, Trending Value) — no preset loader
- Rolling Purged walk-forward IC-IR in component leaderboard (current component_ic_leaderboard uses simple Spearman on snapshot, no walk-forward, no Purged)
- Composite vs individual factor backtest comparing weighted vs naïve equal-weight
- Regime-conditional IC decomposition (current regime_breakdown is sector grouping proxy, not VIX/yield-curve regime)
- Factor sign auto-correction for valuation factors before combination
- Factor correlation redundancy alert (>0.6 pair flagged before run)
```

**S4 — Academic Strategy Screener Library**

```
- Graham Net-Net screen (current assets − total liabilities > market cap)
- O'Shaughnessy Value Composite Two (multi-metric combined rank: EV/EBITDA + P/E + P/S + P/CF; P/CF not in panel)
- ERP5 screen (EV/EBIT + ROC + 5Y avg EBIT/EV + 5Y avg ROC — requires multi-year fundamental history)
- Deep Value Yield (EV/EBIT + dividend yield combined rank)
- Mohanram G-Score (8 growth/quality signals for high P/B stocks)
- Sloan Accruals signal (total accruals / total assets)
- Dual Momentum (absolute momentum filter vs T-bills + relative rank)
- Twin Momentum (fundamental momentum + price momentum)
- Quantitative Momentum / QM (momentum smoothness filter)
- O'Shaughnessy Trending Value (Value Composite Two × 6M momentum)
- Conservative Formula (low beta + net payout yield + momentum — pim van vliet)
- Altman Z-Score + Piotroski overlay as combined screen
- Meb Faber Shareholder Yield (dividend + net buyback yield approx)
- Dogs of the Dow screen
- High Dividend Low Payout screen
- Altman Z''-Score for non-manufacturers
- Interest Coverage Distress Screen (short-side flag)
- Acquirer's Multiple (EV/EBIT) — ev_ebitda proxy used, not EV/EBIT specifically
- Piotroski individual criterion scorecard per ticker (9-criterion pass/fail display)
- Altman Z-Score 8-quarter trend per ticker
- Historical strategy performance table (annualized return/Sharpe/MDD by strategy, regime-conditional) — only leaderboard avg_score computed
- Strategy correlation matrix uses numeric cols from strategies df but most strategies not implemented so matrix is sparse
```

**S5 — Screener Backtester**

```
- True point-in-time fundamental enforcement (meta warns; not enforced)
- Survivorship bias correction / delisted ticker inclusion
- Sector-neutralized rebalancing (equal sector weights)
- Score-weighted portfolio construction (weight ∝ composite score)
- Long-short backtest (top decile long + bottom decile short)
- Rebalancing frequency toggle (weekly/monthly/quarterly — currently static snapshot)
- Sortino ratio, Calmar ratio in performance stats
- Average drawdown and recovery time stats
- Hit rate (fraction of positions profitable)
- Average gain vs average loss
- Best/worst calendar year
- Holding period sensitivity — currently calls score_backtest 4× with same args (holding_days parameter not actually varied in score_backtest; the loop is a stub)
- Rebalancing date sensitivity (entry day offset distribution)
- Monte Carlo using proper rebalancing-date randomization (current MC samples daily returns with replacement, not rebalancing offset)
- PBO (Probability of Backtest Overfitting) statistic
- Stock-level attribution with entry/exit dates (current stock_attr has no entry/exit dates, only total_return over full window)
- Turnover computation (current turnover hardcoded to 1.0)
```

**S6 — Alert Engine**

```
- Metric threshold alerts (single metric crosses threshold)
- Formula value threshold alerts
- Percentile rank shift alerts (sector-relative percentile moves >N pts intraday)
- Volume spike alerts
- Price vs SMA/EMA/Bollinger Band alerts
- Consecutive day trigger alerts
- Fundamental change alerts (quarterly metric changes >X%)
- Alert frequency scheduling (daily after close / weekly) — no job runner
- Email notification delivery
- Alert history log with forward performance tracking
- Alert performance tracker hit rate (currently a count stub with precision_proxy=None)
- Watchlist live monitoring dashboard with per-ticker metric color-coding vs target ranges
- Screen entry/exit log annotated on equity curve
```

**S7 — Comparative Relative Valuation**

```
- Industry-group peer comparison (only sector-level currently)
- Custom peer list (user-uploaded tickers)
- Market cap bucket peer comparison
- Historical context window toggle (1Y/3Y/5Y/10Y) — own_history_percentile uses full history, no window control
- Universe-wide four-dimension card for all tickers simultaneously (currently single-ticker only)
- Sector valuation landscape heatmap (sectors × metrics matrix, colored by percentile vs 10Y sector history) — current sector_heat only covers one metric
- Own-history percentile time series per metric (current own_history_series uses first available of PE/PB/PS, not user-selectable)
- Peer comparison table with color-coded better/worse vs selected ticker
- Re-rating / de-rating trend annotation on history series
```

**S8 — Export and Integration**

```
- JSON export format
- Plain ticker list export (one per line)
- Scheduled daily/weekly email delivery of re-run screen results
- Portfolio optimizer module feed (send result as candidate universe)
- Research notebook / ML environment feed
- Watchlist creation from screen result (one-click to Feature S6)
- Screen result static API endpoint (meta says not wired; endpoint not registered)
- Change report diff (entries/exits/rank shifts vs prior run) — currently hardcoded current_run status only, no prior-run state stored
- Column selection UI (all / active filters only / user-selected)
```
