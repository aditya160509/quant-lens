# Studio V2 Backend — Spec vs. Code Audit

**Date:** 2026-07-30  
**Scope:** F3.10–F3.13, F4.12–F4.14, F5.7–F5.9, F6.11–F6.13, Page 7 (F7.1–F7.4), F0.1  
**Spec source:** `docs/STUDIO_V2_API_ROUTES.md`  
**Code source:** `backend/app/studio_v2/`  
**Method:** Read every source file + router to compare actual logic against spec requirements.

---

## F3.10 — Data-Source Robustness Test (`data_source_test.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `DataSourceRobustnessTest` class | ✅ | Present |
| Route wired via `robustness_core` handler | ✅ | Checks `payload.get("sources")` |
| Accept strategy file + perturbation params | ❌ | Takes multiple `sources`, not a strategy file |
| Gaussian noise (std=0.001) added to daily returns | ❌ | No noise perturbation at all |
| Runs backtest on perturbed series | ❌ | Compares cross-source returns directly |
| 200–500 simulations | ❌ | Single pass, no Monte Carlo |
| Sensitivity score (1.0–0.0) | ❌ | Returns cross-source drift + correlation |
| Sharpe distribution percentiles | ❌ | Not computed |

**Verdict:** The file and route exist, but the implementation is **cross-source comparison** (diffing two data vendor feeds), which is useful but **fundamentally different** from the spec's requirement: Gaussian-noise perturbation of a single source's prices with 500-simulation Monte Carlo and sensitivity score. The spec's core feature (perturbation-based robustness testing) doesn't exist.

---

## F3.11 — Look-Ahead Audit Trail Export (`audit_trail.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `AuditTrail` class | ✅ | Present |
| Route: `POST /api/v2/robustness/audit-trail/{strategy_id}` | ✅ | Registered in router |
| SHA-256 hashing of source | ✅ | `hashlib.sha256(source.encode())` |
| HMAC-SHA-256 signing with key | ✅ | `hmac.new(key, canonical, sha256)` |
| Hash chain to previous record | ✅ | `previous_hash` from last record |
| Chain verification method | ✅ | `verify()` method |
| Collect lint evidence from session history | ⚠ | Lints current source code only, no session history |
| Engine fill-timing evidence section | ❌ | Not collected |
| Purged K-Fold embargo evidence section | ❌ | Not collected |
| PDF output option | ❌ | JSON only |
| Structured report sections | ❌ | Flat findings list, no section structure |

**Verdict:** Core cryptographic signing and hash-chaining are properly implemented. But evidence collection is limited to linting the current source code — the three-section structure (Linter + Engine + CV Embargo) specified in the design is not implemented. No PDF output.

---

## F3.12 — Combinatorial Parameter Interaction Test (`parameter_interaction.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `ParameterInteractionTest` class | ✅ | Present |
| Route wired via `robustness_core` handler | ✅ | Checks `payload.get("parameter_grid")` |
| Accept strategy file + two parameter names | ⚠ | Takes `parameter_grid` dict, not auto-ranging from strategy |
| 11×11 grid (121 combos) | ⚠ | Takes arbitrary grid values, no auto-sizing |
| Run backtest at every grid point | ❌ | Accepts `evaluate` callback or observations |
| 3D surface computation | ✅ | `pivot_table` with ANOVA residual |
| Interaction score | ✅ | Residual variance / total variance |
| Marginal stability per parameter | ❌ | Not explicitly computed |
| Verdict (independent/interaction/strong) | ❌ | Returns raw `strength` only |
| Sharpe map | ❌ | Uses generic `objective`, not Sharpe |

**Verdict:** The ANOVA-style interaction analysis works correctly, but the spec's full backtest integration, auto-grid generation (11×11), marginal stability scores, and categorical verdict are missing. The feature accepts an `evaluate` callback/observations rather than orchestrating the backtest runs itself.

---

## F3.13 — Adversarial Stress Test (`adversarial.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `AdversarialStressTest` class | ✅ | Present |
| Route: `POST /api/v2/robustness/adversarial` | ✅ | Registered |
| Route: `GET /api/v2/robustness/adversarial/result/{run_id}` | ✅ | Registered |
| Constrained optimization over historical params | ❌ | 4 hard-coded shock scenarios instead |
| Constraint thresholds (vol_pctile, cost_pctile, corr) | ❌ | Uses `shock_sigma` instead |
| Worst-case sequence construction | ❌ | Applies shocks to raw returns |
| Survival verdict | ❌ | Not computed |
| Max drawdown comparison | ❌ | Returns basic max_drawdown from evaluate callback |
| Baseline vs adversarial comparison | ❌ | No baseline is computed |
| Degradation percentage | ❌ | Not computed |
| Recovery estimate | ❌ | Not computed |
| Persistence | ✅ | Stored via SQLiteStore |

**Verdict:** The implementation generates 4 useful stress scenarios (flash crash, vol cluster, liquidity gap, serial reversal) but these are **not the constrained optimization over the historical parameter space** that the spec calls for. The spec describes searching for the worst-case sequence within realistic historical bounds; the code applies simple shock patterns to returns. No survival analysis or degradation metrics.

---

## F4.12 — Factor Combination / Composite Score Builder (`composite_combiner.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `CompositeFactorCombiner` class | ✅ | Present |
| Route: `POST /api/v2/factors/evaluate` | ✅ | Registered; checks `payload.get("factors")` |
| Equal-weight method | ✅ | Default uniform weights |
| IC-weighted method | ❌ | Not implemented |
| IC-IR-weighted method | ❌ | Not implemented |
| Custom Python combiner | ❌ | Not implemented |
| Run composite through IC/decay pipeline | ❌ | evaluator.py has no `evaluate_composite()` |
| Return composite IC, IC-IR | ❌ | Not computed |
| Return decay curve, half-life | ❌ | Not computed |
| Return optimal rebalance frequency | ❌ | Not computed |

**Verdict:** Basic factor combination (zscore/rank normalization + explicit weights) works. But the three advanced weighting schemes (IC-weighted, IC-IR-weighted, custom combiner) and the all-important IC/decay pipeline integration are missing. The composite score is computed but NOT evaluated through the factor diagnostics.

---

## F4.13 — Turnover-vs-Decay Tradeoff View (`turnover_estimator.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `TurnoverDecayEstimator` class | ✅ | Present |
| Route: `GET /api/v2/factors/ic-diagnostics` | ✅ | Registered |
| Compute IC half-life | ✅ | Multi-horizon IC decay |
| Compute rank turnover rate | ⚠ | Computes diff-based turnover, not rank autocorrelation |
| Estimate break-even cost | ❌ | Uses input `cost_bps`, no platform cost model |
| Implementable flag (net of costs) | ❌ | Not computed |
| Chart region data | ❌ | Not returned |
| `compute_tradeoff()` method | ❌ | Method is `estimate()` |
| `_check_implementable()` | ❌ | Not present |

**Verdict:** The turnover computation and multi-horizon IC decay work well. But the break-even cost analysis, implementability check, and chart visualization data described in the spec are missing. The feature computes turnover×cost but doesn't compare against a realistic cost band or produce a boolean implementable verdict.

---

## F4.14 — Factor Library Governance Panel (`governance.py`)
**Status: ✅ MOSTLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `FactorGovernance` class | ✅ | Present |
| Route: `GET /versions` | ✅ | Registered |
| Route: `POST /approve` | ✅ | Registered |
| Route: `POST /deprecate` | ✅ | Registered |
| Route: `GET /changelog` | ✅ | Registered |
| Create version with expression | ✅ | With SHA-256 hash |
| List version history | ✅ | Sorted by version number |
| Approve factor (reviewer) | ✅ | With actor + reason |
| Deprecate factor (reason required) | ✅ | Validates reason is not empty |
| Full changelog | ✅ | History of events per version |
| Persistent via SQLiteStore | ✅ | Durable storage |
| Governance hooks in library.py | ❌ | `library.py` doesn't call governance on CRUD |
| Deprecation filters baseline | ❌ | `get_baseline_factors()` ignores deprecation status |

**Verdict:** The governance module itself is well-implemented with all four routes working, proper version tracking, state transitions, and persistence. What's missing is the **integration with the factor library** — `library.py` doesn't call governance on factor creation/edits, and deprecated factors are not filtered from the orthogonalization baseline.

---

## F5.7 — Multi-Objective Pareto Frontier View (`multi_objective.py`)
**Status: ✅ MOSTLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `ParetoOptimizer` class | ✅ | Present (named `ParetoOptimizer` not `MultiObjectiveOptimizer`) |
| Route: `POST /api/v2/optimizer/bayesian-search` | ✅ | Registered; checks for `"objectives"` in payload |
| Accept parameter ranges + objectives | ✅ | Via payload |
| Pareto dominance computation | ✅ | Correct non-dominated sorting |
| Return frontier points | ✅ | Dataframe of non-dominated points |
| Return dominated points | ✅ | Included in `trials` |
| True multi-objective Bayesian search | ❌ | Runs single-objective Bayes first, then Pareto filter |
| Convergence data (hypervolume) | ❌ | Not returned |
| `_pareto_dominance()` / `_compute_frontier()` methods | ⚠ | Logic inline |

**Verdict:** The Pareto frontier computation is correct and properly wired. However, the spec says the Bayesian search should **track multiple objectives simultaneously**; the code runs a single-objective Bayesian optimizer first, then computes the Pareto frontier from all trials. This is functionally useful but not true multi-objective Bayesian optimization.

---

## F5.8 — Ensemble/Parameter Averaging Mode (`ensemble.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `ParameterEnsemble` class | ✅ | Present |
| Route: `POST /api/v2/optimizer/ensemble` | ✅ | Registered |
| Query trial registry for top-N | ✅ | Takes `trials` directly |
| Ensemble mode (run + average signals) | ❌ | Averages parameters, not signals |
| Distribution mode (percentile stats) | ❌ | Not implemented |
| `_ensemble()` method | ❌ | Not present |
| `_distribution()` method | ❌ | Not present |
| Performance distribution stats (min/p25/p50/p75/max/std) | ❌ | Not computed |
| Overfitting mitigation note | ❌ | Not included |

**Verdict:** Parameter averaging (combining top-N parameter sets into a weighted average) works. But the two modes described in the spec — ensemble mode (running configs and averaging signals) and distribution mode (computing performance distributions) — are not implemented. This is a simpler parameter-averaging tool, not the ensemble signal generator described in the spec.

---

## F5.9 — Optimizer Cross-Validation View (`cross_validation.py`)
**Status: ⚠ MINIMALLY IMPLEMENTED** (does something different)

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `OptimizerCrossValidation` class | ✅ | Present |
| Route: `POST /api/v2/optimizer/cross-validate` | ✅ | Registered |
| Run Bayesian search | ❌ | Not implemented |
| Run Walk-Forward optimization | ❌ | Not implemented |
| Extract preferred region from each method | ❌ | Not implemented |
| Compute overlap percentage | ❌ | Not implemented |
| Return overlay data + verdict | ❌ | Not implemented |
| `_extract_region()` / `_compute_overlap()` methods | ❌ | Not present |

**What it actually does:** Implements **Purged K-Fold time-series cross-validation** with configurable purge and embargo windows. This is a useful feature (train/test separation with leakage prevention) but is **completely different** from the spec's requirement: comparing Bayesian-preferred region vs Walk-Forward-preferred region.

**Verdict:** The file contains a working Purged K-Fold implementation, but the entire spec feature (cross-method region comparison with overlap percentage) is absent.

---

## F6.11 — Multi-Asset-Class Universe Support (`multi_asset.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `MultiAssetCatalog` class | ✅ | Present (named `MultiAssetCatalog`, not `MultiAssetUniverse`) |
| Route: `GET /api/v2/data-studio/asset-classes` | ✅ | Registered |
| List supported asset classes | ✅ | equity, etf, future, fx, crypto, fixed_income, commodity |
| Asset-class-specific filter primitives | ✅ | Per-class metadata |
| Futures roll methods | ❌ | No `build_futures_universe()` or roll methods |
| Crypto exchange/quote filters | ❌ | No `build_crypto_universe()` |
| FX settlement types | ❌ | No `build_fx_universe()` |
| Continuous contract construction | ❌ | Not implemented |
| Universe dispatch in `universe.py` | ❌ | No asset_class parameter |
| Data loader methods (futures/crypto/FX) | ❌ | `data_loader.py` has no multi-asset sources |
| Liquidity multi-asset extension | ❌ | Not implemented |

**Verdict:** The asset class catalog and validation work correctly — listing 7 asset classes with metadata. But **none of the data building methods** (continuous futures, crypto pair data, FX data) are implemented. The spec's three build methods, three roll methodologies, and the integrations into `universe.py`, `data_loader.py`, and `liquidity.py` are all missing.

---

## F6.12 — Corporate Event Calendar Overlay (`event_calendar.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `EventCalendar` class | ✅ | Present |
| Route: `GET /api/v2/data-studio/events/{ticker}` | ✅ | Registered |
| Filter by ticker, date range, event type | ✅ | Supported |
| Persistent via SQLiteStore | ✅ | Durable CRUD |
| Auto-populate earnings dates | ❌ | Events must be manually upserted |
| Auto-populate dividend dates | ❌ | Not implemented |
| Auto-populate index rebalance dates | ❌ | Not implemented |
| `_get_earnings_dates()` / `_get_dividend_dates()` / `_get_index_rebalance_dates()` | ❌ | Not present |

**Verdict:** The event storage, retrieval, and filtering work correctly. But this is a **passive storage layer** — events must be manually inserted via `upsert()`. The automated calendar population from fundamentals data, as described in the spec, is not implemented.

---

## F6.13 — Synthetic/Backfilled Data Flagging (`synthetic_flagging.py`)
**Status: ✅ MOSTLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `SyntheticRangeDetector` class | ✅ | Present (named `SyntheticRangeDetector`, not `SyntheticDataTracker`) |
| Route: `GET /api/v2/data-studio/synthetic-ranges/{ticker}` | ✅ | Registered |
| Detect synthetic ranges | ✅ | Multiple heuristics: explicit flag, flat close+zero vol, source label |
| Return start/end/reason/method/filled_count | ✅ | Ranges with start, end, observations |
| `record()` method (explicit recording) | ❌ | Detects retrospectively, no recording |
| `get_all_ranges()` | ❌ | Only per-ticker |
| Integration with backtest/factor services | ❌ | Not implemented |

**Verdict:** The synthetic range detection is well-implemented with multiple detection heuristics (explicit flag, flat close+zero volume, source label inspection). What's missing is the explicit recording API (to mark data as synthetic at creation time) and the cross-service integration to flag when backtests/factor evaluations consumed synthetic data.

---

## F7.1 — Aggregate VaR/CVaR Panel (`var_engine.py`)
**Status: ✅ MOSTLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `VaREngine` class | ✅ | Present |
| Route: `GET /api/v2/portfolio-risk/var` | ✅ | Registered |
| Route: `GET /api/v2/portfolio-risk/active-strategies` | ✅ | Registered |
| Parametric (variance-covariance) VaR | ✅ | Computed via NormalDist CDF |
| Historical simulation VaR | ✅ | Quantile-based |
| Conditional VaR (CVaR/ES) | ✅ | Tail mean |
| 95% and 99% confidence | ✅ | Configurable, accepts any value |
| 1-day and 10-day horizons | ✅ | Scaled by sqrt(horizon) |
| Auto-aggregate from active strategies | ❌ | Takes explicit returns/weights |
| `_parametric_var()` / `_historical_var()` named methods | ⚠ | Logic inline |

**Verdict:** Core VaR/CVaR computation is correct for both parametric and historical methods, with proper horizon scaling. The active strategies route works. Missing: auto-aggregation of returns/weights from active strategies (currently takes explicit inputs) and pre-computation of all four standard confidence/horizon combinations.

---

## F7.2 — Cross-Strategy Correlation & Concentration (`concentration.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `ConcentrationEngine` class | ✅ | Present |
| Route: `GET /api/v2/portfolio-risk/correlation` | ✅ | Registered |
| Route: `GET /api/v2/portfolio-risk/concentration` | ✅ | Registered |
| Correlation matrix | ✅ | Full pairwise correlation |
| Marginal risk decomposition | ✅ | Marginal + component risk |
| Weight HHI / effective N | ✅ | Herfindahl index + effective positions |
| Overlapping positions analysis | ❌ | Not implemented — no ticker-level overlap |
| Integration with active strategies | ❌ | Takes explicit returns/weights |
| Utility export from robustness/tests.py | ❌ | Not done |

**Verdict:** Correlation matrix and risk decomposition (marginal risk, component risk, concentration metrics) work well. But the spec's key feature — **overlapping positions** analysis that surfaces when different strategies are secretly long the same names — is not implemented.

---

## F7.3 — Position & Exposure Limits Panel (`limits.py`)
**Status: ✅ MOSTLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `RiskLimitService` class | ✅ | Present |
| Route: `GET /api/v2/portfolio-risk/limits` | ✅ | Registered |
| Route: `PUT /api/v2/portfolio-risk/limits` | ✅ | Registered |
| Route: `GET /api/v2/portfolio-risk/limits/breaches` | ✅ | Registered |
| CRUD for limits | ✅ | `list()` + `replace()` |
| Breach detection | ✅ | Operator-based comparison |
| Persistent via SQLiteStore | ✅ | Durable storage |
| Auto-compute current values from strategies | ❌ | Takes explicit metrics |
| `_compute_current_values()` | ❌ | Not present |
| Fixed schema (max_single_name_pct, etc.) | ⚠ | Uses flexible metric/operator/threshold (arguably better) |

**Verdict:** Full CRUD + breach detection with flexible schema works correctly. The only missing piece is auto-computation of current exposure values from active strategies — currently the breaches endpoint takes explicit metrics input.

---

## F7.4 — Real-Time Risk Alert Feed (`alert_feed.py`)
**Status: ⚠ PARTIALLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `AlertFeed` class | ✅ | Present |
| Route: `GET /api/v2/portfolio-risk/alerts` | ✅ | Registered |
| Route: `POST /api/v2/portfolio-risk/alerts/{id}/ack` | ✅ | Registered |
| Create alerts with deduplication | ✅ | Fingerprint-based dedup |
| List with filtering | ⚠ | Only `acknowledged` filter; no severity/since |
| Acknowledge alerts | ✅ | With actor tracking |
| Pagination (limit/offset) | ❌ | Returns up to 1000, no pagination |
| Auto-ingestion from VaR engine | ❌ | `_ingest_from_var()` not present |
| Auto-ingestion from limits | ❌ | `_ingest_from_limits()` not present |
| Auto-ingestion from reconciliation | ❌ | `_ingest_from_reconciliation()` not present |
| Auto-ingestion from freshness | ❌ | `_ingest_from_freshness()` not present |

**Verdict:** Alert CRUD and acknowledgement work with good deduplication. But the auto-ingestion from risk engines (VaR, limits, reconciliation, freshness) specified in the design is not implemented. Alerts must be created manually. Pagination and severity filtering are also missing.

---

## F0.1 — Research Notebook / Journal Layer (`journal_service.py`)
**Status: ✅ MOSTLY IMPLEMENTED**

| Spec Requirement | Status | Details |
|---|---|---|
| File exists with `JournalService` class | ✅ | Present |
| Route: `GET /api/v2/journal` | ✅ | Registered |
| Route: `POST /api/v2/journal` | ✅ | Registered |
| Route: `PUT /api/v2/journal/{id}` | ✅ | Registered |
| Route: `DELETE /api/v2/journal/{id}` | ✅ | Registered |
| Route: `GET /api/v2/journal/tags` | ✅ | Registered |
| CRUD operations | ✅ | All working |
| Tag filtering | ✅ | Supports tag filter |
| Search by title/body | ✅ | Text search |
| Tag listing with counts | ✅ | Returns tag + count |
| Linked run IDs | ⚠ | Stored in payload but no linked_run_ids query param |
| Date range filtering (date_from/date_to) | ❌ | Not implemented |
| Pagination (limit/offset) | ❌ | No limit/offset support in API |
| 1000-row cap | ⚠ | Store limit caps at 1000 |

**Verdict:** Full CRUD with tag filtering, text search, and tag aggregation works correctly. The only gaps are date range filtering and pagination (limit/offset) on the list endpoint.

---

## Summary Table

| Feature | File | Status | Key Gaps |
|---|---|---|---|
| **F3.10** | `data_source_test.py` | ⚠ Partial | Wrong algorithm (cross-source comparison vs perturbation Monte Carlo) |
| **F3.11** | `audit_trail.py` | ⚠ Partial | Only lint evidence; no engine/CV sections; no PDF |
| **F3.12** | `parameter_interaction.py` | ⚠ Partial | No backtest integration; no verdict; no auto-grid |
| **F3.13** | `adversarial.py` | ⚠ Partial | Hard-coded shocks instead of constrained optimization |
| **F4.12** | `composite_combiner.py` | ⚠ Partial | No IC/ICIR-weighted methods; no IC/decay pipeline |
| **F4.13** | `turnover_estimator.py` | ⚠ Partial | No break-even cost; no implementable flag |
| **F4.14** | `governance.py` | ✅ Mostly | Missing library.py integration hooks |
| **F5.7** | `multi_objective.py` | ✅ Mostly | Not true multi-objective Bayes (post-hoc Pareto) |
| **F5.8** | `ensemble.py` | ⚠ Partial | Averages params not signals; no distribution mode |
| **F5.9** | `cross_validation.py` | ⚠ Minimal | Implements Purged K-Fold, NOT Bayesian-vs-WalkForward |
| **F6.11** | `multi_asset.py` | ⚠ Partial | Only catalog; no data building or roll methods |
| **F6.12** | `event_calendar.py` | ⚠ Partial | Passive storage only; no auto-population |
| **F6.13** | `synthetic_flagging.py` | ✅ Mostly | Missing recording API and cross-service integration |
| **F7.1** | `var_engine.py` | ✅ Mostly | Missing auto-aggregation from active strategies |
| **F7.2** | `concentration.py` | ⚠ Partial | Missing overlapping positions analysis |
| **F7.3** | `limits.py` | ✅ Mostly | Missing auto-compute from active strategies |
| **F7.4** | `alert_feed.py` | ⚠ Partial | Missing auto-ingestion from risk engines; no pagination |
| **F0.1** | `journal_service.py` | ✅ Mostly | Missing date filtering and pagination |

### Route Registration
All 40+ routes referenced in the spec for these features are registered in `router.py` — route registration is 100% complete. The gaps are in the service logic.

### Files Created
All 18 code files listed in the spec exist at their expected paths. File creation is 100% complete.

### What's Fully Implemented
No feature is 100% spec-complete. The closest are F4.14 (governance), F5.7 (Pareto), F6.13 (synthetic), F7.1 (VaR), F7.3 (limits), and F0.1 (journal), each missing 1–3 minor sub-features.

### What's Most Different From Spec
- **F3.10** — Completely different algorithm
- **F5.9** — Implements something entirely different
- **F3.13** — Wrong approach to adversarial construction
- **F4.12** — Missing all advanced weighting methods
- **F6.11** — Only a catalog, none of the data building
