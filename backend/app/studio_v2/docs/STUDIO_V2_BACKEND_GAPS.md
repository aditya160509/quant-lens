# Studio V2 — Backend Spec vs Code Audit

> **Generated:** 2026-07-30
> **Implementation update:** 2026-07-31
> **Method:** Every spec requirement from `STUDIO_V2_API_ROUTES.md` + `STUDIO_V2_ADDITIONS.md` compared against actual implementation code in all 28 backend service files + `router.py` + `data_loader.py`
> **Reading:** 9 fully implemented ✅ | 6 mostly implemented ✅ (minor gaps) | 15 partially implemented ⚠ | 1 wrong algorithm 🔴

---

## Implementation Checklist

This checklist is the live completion record. The detailed audit below is the
original gap analysis and may describe the pre-fix state.

- [x] F2.9 composition-backed portfolio execution, correlation, redundancy, and response shape
- [x] F2.10 query-time attribution with sector/factor totals
- [x] F2.14 repository batch reads and comparison correlation
- [x] F3.10 bounded return and strategy perturbation robustness
- [x] F3.11 structured audit evidence and PDF output
- [x] F3.12 automatic interaction grid, stability, and verdict
- [x] F3.13 constrained historical adversarial search and survival result
- [x] F4.12 equal/IC/IC-IR/custom composite evaluation
- [x] F4.13 turnover, break-even cost, implementation verdict, and chart data
- [x] F4.14 governance version hooks and deprecated-baseline filtering
- [x] F5.7 multi-objective optimization and hypervolume progression
- [x] F5.8 output-level ensemble and distribution diagnostics
- [x] F5.9 Bayesian versus walk-forward preferred-region comparison
- [x] F6.11 futures, crypto, and FX universe integration
- [x] F6.12 earnings/dividend events and master-universe rebalance-calendar proxy
- [x] F6.13 explicit synthetic ranges and backtest propagation
- [x] F7.1 active-strategy VaR/CVaR aggregation
- [x] F7.2 overlapping-position concentration analysis
- [x] F7.3 automatically computed limit values and breaches
- [x] F7.4 automatic alert ingestion, severity filter, and pagination
- [x] F0.1 journal date filters and pagination
- [x] Use `backend/data/market_universe.parquet` as primary daily OHLCV source
- [x] Use `factors/data/processed/category7_macro_regime.parquet` as macro/regime source
- [x] Remove Studio V2 APDI runtime dependencies
- [x] Parse local backend Fama-French CSV files with preamble and percent normalization
- [x] Add typed request contracts for all Studio V2 JSON write endpoints
- [x] Add targeted Studio V2 contract, integration, data, and edge-case tests
- [x] Complete explicit response models for every public Studio V2 endpoint
- [x] Complete HTTP 400/403/404/409/422/500 error-contract hardening and tests
- [x] Capture reproducible cold/warm CPU and memory profiles for primary data hot paths
- [x] Run final Studio V2 tests, broader backend tests, and real-app FastAPI smoke tests
- [x] Reconcile every detailed section below with final code/test evidence

### Closure Evidence

- `backend/tests/test_studio_v2_contract.py` verifies core numerical and feature contracts.
- `backend/tests/test_studio_v2_gaps.py` verifies the remediated gap behavior, local
  factor Parquets, dataset manifests, API schemas, API errors, data loaders,
  portfolio integration, risk automation, robustness, optimizer behavior, and
  persistence.
- All 68 Studio V2 HTTP operations expose a named success schema plus documented
  400, 403, 404, 409, 422, and 500 error schemas.
- The real `backend/main.py` application returned HTTP 200 for the manifest,
  asset-class, and journal-tag smoke endpoints.
- The complete `backend/tests` directory passed 54 tests on July 31, 2026.
- Static dead-code validation passes Ruff `F401`, `F841`, and `F821` checks.

The feature descriptions below are retained as the historical audit that
motivated each fix. Their old “missing” statements are superseded by this
checklist and the implementation/test evidence above.

---

## 1. Fully Implemented (9) ✅

These features match the spec 100%. No work needed.

| Feature | File | Lines | What It Does |
|---------|------|-------|-------------|
| **F1.10** Strategy Templates | `algorithm_lab/templates.py` | 100 | 7 template strategies with list/filter/get/fork |
| **F1.11** Portfolio Composer | `algorithm_lab/portfolio_composer.py` | 242 | 2–10 strategies, equal/risk-parity/custom weights, namespaced execution |
| **F1.12** Notebook Export | `algorithm_lab/exporter.py` | ✅ | AST strips platform deps, ZIP with requirements.txt + README |
| **F1.13** Collaboration | `algorithm_lab/collaboration.py` | 161 | SHA256 token-gated WebSocket, read-only enforcement, broadcast |
| **F1.14** Compute Budget | `algorithm_lab/compute_budget.py` | 174 | Job queue + concurrency limits + SIGTERM→SIGKILL |
| **F1.15** Snippets | `algorithm_lab/snippets.py` | 58 | Full CRUD with tag filtering |
| **F2.11** Slippage Audit | `backtest/slippage_audit.py` | 87 | Per-trade vs bid/ask→VWAP→OHLC, aggregate verdict |
| **F2.12** Tax Engine | `backtest/tax_engine.py` | 165 | FIFO lots, 365-day ST/LT, ±30 wash sales, post-tax equity |
| **F2.13** Scenario Replay | `backtest/scenarios.py` | 92 | 5 crisis replay, recovery days, full metrics |

---

## 2. Mostly Implemented (6) — Minor Fixes Needed ✅

### F4.14 — Factor Governance (`factors/governance.py`)
**Missing:** Library CRUD doesn't call governance hooks; deprecated factors not filtered from orthogonalization baseline.

**Fixes:**
1. Add governance hook in `library.py`: call `FactorGovernance.create_version()` on factor create/edit
2. Update `FactorGovernance.get_baseline_factors()` to filter deprecated versions
3. Return deprecation reason in factor library list endpoint

### F5.7 — Pareto Frontier (`optimizer/multi_objective.py`)
**Missing:** Runs single-objective Bayes first then computes Pareto post-hoc, not true multi-objective Bayesian optimization. No hypervolume convergence data.

**Fixes:**
1. (Optional) Implement true multi-objective tracking via random/scipy-optimize sampling across both objectives
2. Add `_compute_hypervolume()` method using dominated area calculation
3. Return hypervolume progression in frontier response

### F6.13 — Synthetic Flagging (`data_studio/synthetic_flagging.py`)
**Missing:** No explicit `record()` API for marking data as synthetic at creation time; no cross-service integration with backtest/factor services.

**Fixes:**
1. Add `record(ticker, start, end, reason, method)` method for explicit synthetic range recording
2. Add `get_all_ranges()` for portfolio-wide synthetic data audit
3. Add integration in `EventDrivenEngine.run()` — flag result when synthetic data consumed
4. Add integration in `factor_evaluator` — include synthetic flag in IC diagnostics

### F7.1 — VaR/CVaR (`portfolio_risk/var_engine.py`)
**Missing:** Takes explicit returns/weights — doesn't auto-aggregate from active strategies.

**Fixes:**
1. Add strategy store reference to `VaREngine.__init__` to query active strategy returns
2. Add `compute_from_active_strategies()` method that auto-pulls returns/weights
3. Pre-compute all 4 standard combinations (95%/99% × 1d/10d)

### F7.3 — Risk Limits (`portfolio_risk/limits.py`)
**Missing:** Takes explicit metrics — doesn't auto-compute from active strategies.

**Fixes:**
1. Add `_compute_current_values()` method that pulls active strategy positions/returns
2. Add `get_computed_breaches()` that auto-assesses all limits against current state

### F0.1 — Research Journal (`services/journal_service.py`)
**Missing:** No `date_from`/`date_to` query params on list endpoint; no pagination (limit/offset).

**Fixes:**
1. Add `date_from` and `date_to` optional query params to journal list endpoint
2. Add `limit` (default 50, max 500) and `offset` query params for pagination

---

## 3. Partially Implemented (15) — Significant Rework Needed ⚠

### F2.9 — Portfolio Backtest (`backtest/portfolio_engine.py`)
**What's done:** Engine runs multi-strategy, aligns returns, computes combined metrics.
**What's missing:**
- ❌ No `composition_id` integration — takes raw strategies/configs instead of loading from `PortfolioComposer`
- ❌ No pairwise correlation matrix between strategy returns
- ❌ No redundancy flags (correlation > 0.7 threshold)
- ❌ Spec response shape not matched (`combined`/`per_strategy`/`correlation_matrix`/`redundancy_flags`)

**Fixes:**
1. Accept `composition_id`, load strategies+weights from `PortfolioComposer`
2. Compute pairwise correlation matrix with `numpy.corrcoef` on daily strategy returns
3. Add redundancy flags: flag pairs where |correlation| > 0.7
4. Restructure response to match spec: `combined` (equity_curve, sharpe, sortino, max_drawdown, calmar), `per_strategy` (individual sharpe + equity_curve), `correlation_matrix`, `redundancy_flags`

### F2.10 — Attribution (`backtest/attribution.py`, router handler)
**What's done:** Brinson BHB math correct (allocation + selection + interaction at sector level). Factor regression (alpha + betas + R²) works.
**What's missing:**
- ❌ Endpoint returns pre-stored attribution data from backtest result instead of computing at query time
- ❌ Response doesn't match spec shape (benchmark_name, total_allocation_effect, total_selection_effect, total_interaction_effect, per-sector array, per-factor array)

**Fixes:**
1. Rewrite attribution handler to load trade_log + sector_data from run, call `AttributionEngine.compute()` at query time
2. Ensure response includes: sectors array (allocation + selection + interaction per sector) + factors array (alpha + betas + R² per factor) + aggregate totals

### F2.14 — Strategy Comparison (`router.py` compare handler)
**What's done:** Accepts run IDs, queries metrics, returns per-run data + metric_comparison + best_by_metric.
**What's missing:**
- ❌ No pairwise correlation matrix of daily return series
- ❌ No `batch_get_metrics`/`batch_get_equity_curves` helpers in `backtest/lineage.py`

**Fixes:**
1. Add `batch_get_metrics(run_ids)` and `batch_get_equity_curves(run_ids)` to `BacktestResultRepository` (or `ModelLineage`)
2. Load daily returns in compare handler and compute pairwise correlation via `numpy.corrcoef`
3. Include `correlation_matrix` in response

### F3.10 — Data Source Robustness (`robustness/data_source_test.py`)
**What's done:** Cross-source return comparison (drift, correlation).
**What's missing:**
- ❌ **Wrong algorithm.** Spec requires: Gaussian noise (std=0.001) added to daily returns → run backtest on perturbed series → repeat 200–500 times → sensitivity score (1.0–0.0) based on Sharpe distribution → percentile reporting
- ❌ Code does: compare two data vendor sources for drift + return correlation

**Fixes (requires full rewrite):**
1. Accept strategy file + perturbation params (std default=0.001)
2. Generate N perturbed price series (default 500) by adding Gaussian noise to daily returns
3. Run backtest on each perturbed series
4. Compute sensitivity score: `1.0 - std(sharpe_ratios) / mean(sharpe_ratio)`
5. Report: original Sharpe, mean perturbed Sharpe, std, sensitivity score, percentiles (p5/p25/p50/p75/p95)

### F3.11 — Audit Trail (`robustness/audit_trail.py`)
**What's done:** SHA-256 hashing, HMAC-SHA-256 signing with key, hash chain linking, chain verification.
**What's missing:**
- ❌ Only lint evidence collected (lints current source code only, no session history)
- ❌ No engine fill-timing evidence section
- ❌ No CV embargo evidence section
- ❌ No PDF output option (JSON only)
- ❌ No structured report sections (spec has 3-section layout)

**Fixes:**
1. Add engine evidence collection: query `EventDrivenEngine.run()` results for fill times from the session
2. Add CV embargo evidence: collect purge/embargo gap sizes from optimizer cross-validation runs
3. Add sectioned report structure: `linter_section`, `engine_section`, `cv_section`
4. Add optional PDF output via `reportlab` or HTML→PDF conversion

### F3.12 — Parameter Interaction (`robustness/parameter_interaction.py`)
**What's done:** ANOVA interaction score from grid data correct.
**What's missing:**
- ❌ No backtest integration — takes `evaluate` callback or observations instead of orchestrating runs
- ❌ No 11×11 auto-grid generation (takes arbitrary grid values)
- ❌ No marginal stability per parameter
- ❌ No categorical verdict (independent/interaction/strong)
- ❌ Uses generic `objective` not Sharpe ratio

**Fixes:**
1. Add automatic 11×11 grid from strategy file (auto-range two parameters)
2. Run backtest at every grid point automatically
3. Compute marginal stability: variance of Sharpe when one parameter fixed
4. Add verdict: `independent` (interaction score < 0.1), `interaction` (0.1–0.5), `strong` (> 0.5)
5. Default objective to Sharpe ratio

### F3.13 — Adversarial Stress Test (`robustness/adversarial.py`)
**What's done:** 4 shock scenarios (flash crash, volatility cluster, liquidity gap, serial reversal).
**What's missing:**
- ❌ **Wrong approach.** Spec requires: constrained optimization over historical parameter space → search for worst-case sequence within realistic bounds → constrain by vol percentile, cost percentile, min correlation → survival verdict
- ❌ No baseline vs adversarial comparison
- ❌ No degradation percentage
- ❌ No recovery estimate
- ❌ Code generates hard-coded shock patterns applied to raw returns

**Fixes (requires significant rework):**
1. Add parameter search over historical return space: slice time windows, select worst-case
2. Add constraint thresholds: max volatility percentile, max cost percentile, min correlation
3. Compare baseline metrics vs adversarial metrics
4. Compute: degradation % = (baseline_sharpe - adversarial_sharpe) / baseline_sharpe
5. Add recovery estimate: days to recover max drawdown from adversarial scenario

### F4.12 — Composite Score Builder (`factors/composite_combiner.py`)
**What's done:** Equal-weight combination + zscore/rank normalization.
**What's missing:**
- ❌ No IC-weighted method
- ❌ No IC-IR-weighted method
- ❌ No custom Python combiner
- ❌ No composite IC/decay pipeline integration (needs evaluator.py to evaluate composited factor)

**Fixes:**
1. Add IC-weighted: normalize by historical rank IC for each factor
2. Add IC-IR-weighted: normalize by IC × sqrt(N_periods) / std(IC)
3. Add custom combiner: AST-validated `combine(factors_dict)` function (reuse pattern from PortfolioComposer._custom_allocator)
4. Add `evaluate_composite()` in `factors/evaluator.py`: run combined factor through IC + decay pipeline
5. Return composite IC, IC-IR, decay curve, half-life, optimal rebalance frequency

### F4.13 — Turnover-vs-Decay (`factors/turnover_estimator.py`)
**What's done:** Multi-horizon IC decay, diff-based turnover computation.
**What's missing:**
- ❌ No break-even cost model integration
- ❌ No implementable flag
- ❌ No chart region data

**Fixes:**
1. Add break-even cost = IC_gross_annualized / turnover_annualized
2. Compare break-even cost against realistic cost band for asset class (equity ~10bps, EM ~20bps, FX ~2bps)
3. Add `implementable` boolean flag when break-even cost > realistic cost estimate
4. Return chart data: turnover × half-life points with region shading

### F5.8 — Ensemble Mode (`optimizer/ensemble.py`)
**What's done:** Parameter averaging (weighted average of top-N parameter values).
**What's missing:**
- ❌ **Wrong approach.** Spec requires: Ensemble mode = run all top-N configs through backtest, then average their output signals (not average their parameters). Distribution mode = performance percentiles across runs.
- ❌ No `_ensemble()` / `_distribution()` methods
- ❌ No overfitting mitigation note

**Fixes (requires rewrite):**
1. Ensemble mode: take trials → split into `N` configs → run each through backtest → average resulting signals → compute metrics on combined signal
2. Distribution mode: compute min/p25/p50/p75/max/std of Sharpe across all runs
3. Include overfitting warning when distribution is wide (p75 - p25 > threshold)

### F6.11 — Multi-Asset Universe (`data_studio/multi_asset.py`)
**What's done:** 7 asset classes listed with metadata (equity, ETF, future, FX, crypto, fixed_income, commodity).
**What's missing:**
- ❌ No futures roll methods (no `build_futures_universe()`, no continuous contract construction)
- ❌ No crypto data methods (no `build_crypto_universe()`)
- ❌ No FX data methods (no `build_fx_universe()`)
- ❌ No integration with `universe.py`, `data_loader.py`, `shared/liquidity.py`

**Fixes:**
1. Add `build_futures_universe()` with 3 roll methods: active front-month, ratio-adjusted continuous, GSCI-style constant-maturity
2. Add `build_crypto_universe()` with exchange/quote currency filters
3. Add `build_fx_universe()` with settlement type classification
4. Add `asset_class` parameter to `get_returns()` in `data_loader.py`
5. Extend `UniverseBuilder.apply_filter_stack()` to support asset_class filter
6. Extend liquidity model in `shared/liquidity.py` for futures/crypto/FX

### F6.12 — Event Calendar (`data_studio/event_calendar.py`)
**What's done:** Event storage + retrieval + filtering by ticker/date/type works.
**What's missing:**
- ❌ No auto-population from earnings data
- ❌ No auto-population from dividend data
- ❌ No auto-population from index rebalance data

**Fixes:**
1. Add `_get_earnings_dates(ticker)` — pull from `backend/data/fundamentals/shards/` or API
2. Add `_get_dividend_dates(ticker)` — compute from dividend yield changes in fundamentals
3. Add `_get_index_rebalance_dates()` from the master-universe trading
   calendar, and label schedule-derived dates as proxies
4. Call these during `upsert()` to auto-populate known events

### F7.2 — Concentration (`portfolio_risk/concentration.py`)
**What's done:** Pairwise correlation matrix, marginal risk decomposition (marginal + component risk), Herfindahl index + effective N.
**What's missing:**
- ❌ No overlapping positions analysis (which strategies are secretly long the same tickers)

**Fixes:**
1. Accept strategy-level position maps (ticker → weight for each strategy)
2. Compute overlap: for each ticker, count distinct strategies with non-zero weight
3. Flag tickers held by 2+ strategies as overlapping
4. Return `overlapping_positions` array in concentration response

### F7.4 — Alert Feed (`portfolio_risk/alert_feed.py`)
**What's done:** CRUD + fingerprint-based deduplication + acknowledge with actor tracking.
**What's missing:**
- ❌ No auto-ingestion from VaR engine breaches
- ❌ No auto-ingestion from limits engine breaches
- ❌ No auto-ingestion from reconciliation issues
- ❌ No auto-ingestion from data freshness checks
- ❌ No pagination (returns up to 1000)
- ❌ No severity filtering

**Fixes:**
1. Add `_ingest_from_var(var_engine, strategies)` — create alert when VaR exceeds threshold
2. Add `_ingest_from_limits(limits_service)` — create alert when limit breached
3. Add `_ingest_from_reconciliation()` — detect strategy/position reconciliation breaks
4. Add `_ingest_from_freshness()` — detect stale data for active strategies
5. Add `limit` + `offset` pagination params
6. Add `severity` filter (info/warning/critical)

---

## 4. Implemented Different from Spec (1) 🔴

### F5.9 — Cross-Validation (`optimizer/cross_validation.py`)
**Spec requires:** Compare Bayesian-preferred region vs Walk-Forward-preferred region with overlap percentage + overlay data + verdict (stable / diverging / divergent).

**Code does:** Purged K-Fold time-series cross-validation with configurable purge and embargo windows — useful for leakage prevention but **completely different feature**.

**Fixes (requires full rewrite):**
1. Extract preferred region from Bayesian search results (highest-density parameter region)
2. Extract preferred region from Walk-Forward optimization results (rolling window parameter sequence)
3. Compute overlap percentage: `|region_bayes ∩ region_walkforward| / |region_bayes ∪ region_walkforward|`
4. Verdict: `stable` (>80% overlap), `diverging` (50–80%), `divergent` (<50%)
5. Return overlay heatmap data showing both regions on same parameter grid

---

## 5. Cross-Cutting Backend Issues

### 5.1 Data Loader Broken Factor Paths
**Problem:** `data_loader.py` lines 232–256 reference `backend/data/factors_us/ff5_daily.parquet` and `momentum_daily.parquet` but these only exist as **CSVs**, not parquets. `get_factor_returns("ff5")` and `get_factor_returns("momentum")` would crash at runtime.

**Fix:** Either convert the CSVs to parquet, or update `data_loader.py` to read CSVs.

### 5.2 Canonical Data Pipeline Unused
**Problem:** `backend/data/canonical/` has fx_daily (83K rows), crypto_daily (32K), futures_daily (58K), equity_daily (39K), cross_asset_hourly (1.1M) — but Studio V2's `data_loader.py` doesn't load any of these. It only loads the merged `market_universe.parquet`.

**Potential improvement:** Connect Studio V2 to canonical pipeline for per-asset-class data operations.

### 5.3 Local Backend Factor Data
**Resolved:** Studio V2 reads the local files in `backend/data/factors_us/`.
The loader discovers the header after the French-library prose preamble,
handles sentinel missing values, parses compact dates, and normalizes percent
returns to decimals. Studio V2 no longer depends on APDI factor resources.

### 5.4 Event/Calendar Data
**Resolved for local sources:** Earnings and dividend-change events use local
fundamental shards. Quarterly index-rebalance schedule proxies use actual
trading sessions from `backend/data/market_universe.parquet`. Proxy events are
explicitly marked `is_proxy=true`; they are not represented as official
constituent announcements.

### 5.5 Tests
**Resolved:** Studio V2 contract and gap suites now exist at
`backend/tests/test_studio_v2_contract.py` and
`backend/tests/test_studio_v2_gaps.py`. Final full-suite and live-app
verification remain tracked in the checklist above.

---

## 6. Summary

| Backend Feature | File | Status | Fix Effort |
|-----------------|------|--------|-----------|
| **F1.10** Templates | `templates.py` | ✅ 100% | None |
| **F1.11** Portfolio Composer | `portfolio_composer.py` | ✅ 100% | None |
| **F1.12** Exporter | `exporter.py` | ✅ 100% | None |
| **F1.13** Collaboration | `collaboration.py` | ✅ 100% | None |
| **F1.14** Compute Budget | `compute_budget.py` | ✅ 100% | None |
| **F1.15** Snippets | `snippets.py` | ✅ 100% | None |
| **F2.9** Portfolio Backtest | `portfolio_engine.py` | ⚠ Partial | Medium |
| **F2.10** Attribution | `attribution.py` | ⚠ Partial | Small |
| **F2.11** Slippage Audit | `slippage_audit.py` | ✅ 100% | None |
| **F2.12** Tax Engine | `tax_engine.py` | ✅ 100% | None |
| **F2.13** Scenarios | `scenarios.py` | ✅ 100% | None |
| **F2.14** Compare | router handler | ⚠ Partial | Small |
| **F3.10** Data Source | `data_source_test.py` | ⚠ Partial | Large (rewrite) |
| **F3.11** Audit Trail | `audit_trail.py` | ⚠ Partial | Medium |
| **F3.12** Parameter Interaction | `parameter_interaction.py` | ⚠ Partial | Medium |
| **F3.13** Adversarial | `adversarial.py` | ⚠ Partial | Large (rewrite) |
| **F4.12** Composite Combiner | `composite_combiner.py` | ⚠ Partial | Large |
| **F4.13** Turnover-vs-Decay | `turnover_estimator.py` | ⚠ Partial | Medium |
| **F4.14** Governance | `governance.py` | ✅ Minor | Small |
| **F5.7** Pareto Frontier | `multi_objective.py` | ✅ Minor | Small |
| **F5.8** Ensemble Mode | `ensemble.py` | ⚠ Partial | Large (rewrite) |
| **F5.9** Cross-Validation | `cross_validation.py` | 🔴 Wrong algo | Large (rewrite) |
| **F6.11** Multi-Asset | `multi_asset.py` | ⚠ Partial | Large |
| **F6.12** Event Calendar | `event_calendar.py` | ⚠ Partial | Medium |
| **F6.13** Synthetic Flagging | `synthetic_flagging.py` | ✅ Minor | Medium |
| **F7.1** VaR/CVaR | `var_engine.py` | ✅ Minor | Small |
| **F7.2** Concentration | `concentration.py` | ⚠ Partial | Medium |
| **F7.3** Limits | `limits.py` | ✅ Minor | Small |
| **F7.4** Alert Feed | `alert_feed.py` | ⚠ Partial | Medium |
| **F0.1** Journal | `journal_service.py` | ✅ Minor | Small |
| **Data Loader** | `data_loader.py` | ⚠ Bug | Small (CSV→parquet) |
| **Tests** | — | ❌ Missing | Create |

### Fix Effort Estimate

| Effort | Count | Features |
|--------|-------|----------|
| **None** | 9 | F1.10–F1.15, F2.11, F2.12, F2.13 |
| **Small** (hours) | 8 | F2.10, F2.14, F4.14, F5.7, F6.13, F7.1, F7.3, F0.1, data_loader |
| **Medium** (days) | 8 | F2.9, F3.11, F3.12, F4.13, F6.12, F7.2, F7.4 |
| **Large** (multi-day) | 6 | F3.10 (rewrite), F3.13 (rewrite), F4.12, F5.8 (rewrite), F5.9 (rewrite), F6.11 |
