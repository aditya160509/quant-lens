# QUANT360 Studio v2 — Phase 2-4 Code Review

**Generated:** July 26, 2026
**Scope:** 14 service files + 4 `__init__.py` files
**Compilation:** All 14 compilable files pass `python3 -m py_compile`

---

## robustness/tests.py (F3.2–F3.8)

**Status:** ⚠️ Partial

**Issues:**
- [HIGH] `UniversePerturbationTest.drop_and_replace` (line 161) does NOT implement sector-matched replacement. It simply shuffles the original ticker list and re-inserts dropped tickers back — no sector mapping lookup occurs. Spec requires "sector-matched substitutes from the broader available universe."
- [HIGH] `RegimeDecompositionTest.fit_hmm` (line 274) is a stub — returns feature dict without fitting any HMM. Spec requires 3-state Baum-Welch EM. Falls back to VIX percentile classification with no actual HMM inference.
- [MEDIUM] `ParameterStabilityTest.run_grid_parallel` (line 103) evaluates sequentially, not in parallel. Name suggests multiprocessing but runs a simple for-loop.
- [MEDIUM] `NoiseInjectionTest.run` (line 207) ignores `strategy_file` parameter — reads prices and evaluate callback from config dict instead. Spec says strategy_file drives the test.
- [LOW] `TimingPerturbationTest._single_simulation` (line 134) does not shift exit by the same amount as entry (spec: "Shift the exit date by the same amount to preserve holding period"). It just shuffles returns randomly within a ±k window rather than shifting trade entries and exits.
- [LOW] Missing `from ..shared.data_loader import ...` import for loading VIX/macro data (spec requires this). Test passes VIX series directly as parameter.
- [LOW] `get_realistic_cost_band` (line 304) accepts but never uses `adv_data` parameter.

**Missing:**
- No sector data integration for universe perturbation sector matching
- No actual HMM EM fitting for regime decomposition
- No parallel/multiprocessing execution for grid search

---

## robustness/scorer.py (F3.9)

**Status:** ✅ Complete

**Issues:**
- [LOW] `RobustnessReport` `_build_title_page`, `_build_executive_summary`, `_build_test_page`, `_build_diagnosis_section` methods (lines 71-81) are stubs that append plain strings to a doc object rather than proper reportlab elements. The core `generate_pdf` method works correctly with real reportlab paragraphs/tables.

**Missing:**
- Nothing — composite score weights (30/20/25/25), verdict thresholds, normalize logic all match spec.

---

## factors/evaluator.py (F4.1–F4.4, F4.9)

**Status:** ⚠️ Partial

**Issues:**
- [HIGH] `InstantIcDiagnostics.compute_purged_kfold_ic` (line 172) does NOT implement proper purging or embargo logic. The `embargo` parameter is accepted but never used. The method naively splits data with `np.array_split` and computes naive IC per fold without purging training observations that overlap with test label-formation periods. Spec: "For each test fold, purge training observations with label-formation overlap with test. Apply 10-day embargo after test fold."
- [HIGH] `RegimeConditionalIC.fit_hmm` (line 254) is a stub — no HMM fitting. Falls back to VIX percentile tercile classification with hardcoded regime names. Spec requires Baum-Welch EM on VIX + equal-weighted returns.
- [MEDIUM] `FactorExpressionEvaluator.load_data` (line 118) loops per ticker calling `get_ohlcv()` individually — this is O(N) parquet reads. For 500 tickers this will be extremely slow. Should batch-load.
- [LOW] `FactorExpressionEvaluator.evaluate` (line 154) builds lambda closures for each operator at call time, re-creating them on every evaluation. Should be class-level.

**Missing:**
- K-fold purging with embargo window before test fold
- Proper HMM Baum-Welch implementation (or use `hmmlearn`)
- Batch OHLCV loading for universes

---

## factors/diagnostics.py (F4.5–F4.8)

**Status:** ⚠️ Partial

**Issues:**
- [HIGH] `CrowdingMonitor.get_aum_growth_percentile` (line 69) returns hardcoded `50.0`. The comment acknowledges "ETF AUM is not one of the allowed parquet sources." The spec requires factor→ETF mapping (MTUM, VLUE, USMV, QUAL, IJR) with AUM growth rate percentile from real data. Without actual AUM data, the crowding monitor is non-functional.
- [MEDIUM] `InteractionScreener.compute_interaction` (line 138) uses `a.shift(-1)` as forward returns for parent IC computation, which introduces lookahead (shift(-1) uses future data). Spec is ambiguous on what forward returns to use here.
- [LOW] `HalfLifeDecayTracker.compute_half_life_over_vintage` (line 102) passes expression dict that should come from evaluator results — fine for usage but fragile API.

**Missing:**
- Real ETF AUM data source or integration with data_loader for crowding computation
- Proper lookahead-safe forward returns for interaction IC

---

## factors/library.py (F4.10–F4.11)

**Status:** ✅ Complete

**Issues:**
- [MEDIUM] `FactorLibrary._factors` is a class-level dict shared across instances (line 50). If multiple `FactorLibrary` instances are created, they share state. Should be instance-level.
- [MEDIUM] `FactorLibrary.add_factor` (line 71) uses `uuid.uuid4()` for user factors vs. `uuid.uuid5()` for baseline factors. Inconsistent — both should be stable or both unique.
- [LOW] No DB persistence as spec describes (`factor_library` DB table). Uses in-memory dict only.

**Missing:**
- Nothing functionally — all 40 baseline factors, all validation gates, quality rating, comparison table implemented correctly.

---

## optimizer/search.py (F5.2–F5.3)

**Status:** ⚠️ Partial

**Issues:**
- [HIGH] `BayesianOptimizer.run` (line 144) does NOT use Optuna TPE as specified. Implements naive random uniform sampling with `np.random.default_rng(42)`. Spec: "Bayesian search via Optuna TPE. Trial budgets: 50/200/500."
- [MEDIUM] `_trajectory_callback` (line 132) is a no-op stub. Should record trial history for the trajectory visualization.
- [MEDIUM] `BayesianOptimizer._objective` (line 114) peeks into `config.backtest_config.get("evaluate")` which is fragile — tightly coupled to dict-like config. Would break with typed dataclass config.
- [LOW] `WalkForwardOptimizer.compute_regime_conditional_isoos` (line 186) just returns the raw window DataFrame without computing regime-conditional breakdowns as spec describes.

**Missing:**
- Optuna TPE implementation (`optuna.samplers.TPESampler`)
- Trajectory tracking (current `_trajectory_callback` is a no-op)
- Walk-forward regime-conditional IS/OOS breakdown per regime

---

## optimizer/cpcv.py (F5.4)

**Status:** ⚠️ Partial

**Issues:**
- [HIGH] `CPCV.run` (line 100) does NOT implement CPCV purging/embargo logic. The `config.embargo_lengths` parameter is only used for `run_embargo_sensitivity`, not for actual split generation. Spec: "For each test fold, purge training observations with label-formation overlap with test."
- [MEDIUM] `CPCV.run` — the test split selection via `generate_splits(n_groups, k_test)` generates all C(N,k) combinations, but the training set for each split is simply `np.setdiff1d` (all dates not in test), without purging dates adjacent to test folds.
- [MEDIUM] DSR computation (line 81) uses `1.0 / (t - 1.0)` as `Var[SR]` approximation — this is the asymptotic variance of Sharpe under IID normal. More accurate would be using `(1 + 0.5×SR²)/(T-1)` or computing from the actual return distribution.

**Missing:**
- Purging of training observations that overlap with test fold label-formation dates
- Embargo window applied before each test fold

---

## optimizer/verdict.py (F5.5–F5.6)

**Status:** ✅ Complete

**Issues:**
- [MEDIUM] `TrialRegistry` uses class-level `_trials: Dict[str, TrialRecord] = {}` on line 73, shared across all instances. The same pattern as FactorLibrary. Would cause cross-session trial pollution.
- [LOW] No DB persistence as spec describes (`optimizer_trials`, `optimizer_verdicts` DB tables). Uses in-memory dict only.
- [LOW] `check_criterion` (line 61) returns `CriterionResult` with `name` set to `direction` parameter instead of the criterion name — the `name` field is wrong.

**Missing:**
- Nothing functionally — all verdict thresholds (DSR>0.5, PBO<25%, IS/OOS>0.60, stability>65%), traffic light logic, and trial registry CRUD are present.

---

## shared/liquidity.py (F6.5)

**Status:** ✅ Complete

**Issues:**
- [MEDIUM] `LiquidityCalibrator.calibrate` (line 54) computes OLS pseudo-calibration by dividing spread by `sigma * 0.1^(3/5)` — this is a simplification of the spec's cross-sectional OLS but produces plausible λ values.
- [MEDIUM] `calibrate` iterates all 500 tickers sequentially calling `get_ohlcv` individually — very slow for the full ticker list. Could batch-load.
- [LOW] Default λ values (line 20): large 4×10⁻⁶, mid 2.4×10⁻⁵, small 1.2×10⁻⁴ — matches spec.

**Missing:**
- Nothing — Almgren-Chriss impact formula, liquidity bucket assignment, annual cache, spread estimation all match spec.

---

## data_studio/universe.py (F6.1, F6.3)

**Status:** ⚠️ Partial

**Issues:**
- [MEDIUM] `apply_sector_filter` (line 54) creates a DataFrame with all-None sector column, making sector include/exclude filters non-functional. Every ticker gets `None` sector. The spec requires GICS sector filtering from universe data, but sector data isn't loaded from the parquet.
- [MEDIUM] `apply_exchange_filter` (line 60) ignores the `exchanges` parameter entirely — returns all tickers regardless. Exchange data is not available in the loaded data.
- [MEDIUM] `_snapshot` (line 32) calls `get_ohlcv` per ticker in a loop — O(N) parquet reads.
- [LOW] `definitions` is a class-level dict shared across instances (line 30).

**Missing:**
- Sector data loading/integration (GICS sector info from master_fundamentals or another source)
- Exchange data for exchange filtering
- Batch data loading

---

## data_studio/explorer.py (F6.7–F6.8)

**Status:** ✅ Complete

**Issues:**
- [MEDIUM] `DataExplorer.get_primary_series` (line 53) adds `returns`, `realized_vol_gk`, and `rolling_sharpe` as columns alongside OHLCV columns — this returns a wide DataFrame that includes the original OHLC timestamp columns and may have NaN on the first rows due to pct_change(). Functionally correct.
- [LOW] `MissingDataHeatmap.get_heatmap_data` (line 108) calls `get_ohlcv` per ticker in a loop — same pattern. For 500 tickers this will be slow.

**Missing:**
- Nothing — Garman-Klass vol formula matches spec exactly, Jarque-Bera test correct, 5-sigma anomaly detection correct.

---

## data_studio/catalog.py (F6.6, F6.9–F6.10)

**Status:** ✅ Complete

**Issues:**
- [LOW] `DataCatalog._seed` (line 64) hardcodes registration of 5 data sources. The `get_catalog` and `search_catalog` methods are functional.
- [LOW] No actual DB persistence — all state in-memory.

**Missing:**
- Nothing — CSV upload with auto-detect date, trading calendar alignment, forward-fill gaps (max 5 days), freshness monitor with file mtime checks — all match spec.

---

## algorithm_lab/paper_trader.py (F1.9)

**Status:** ⚠️ Partial

**Issues:**
- [HIGH] `PaperTrader.run_daily_paper_trade` (line 78) uses `get_ohlcv` from data_loader (parquet/historical data) to simulate paper trading. Spec explicitly says "yfinance 15-min-delayed quotes" for live paper trading. The implementation is just a historical backtest replay, not an actual paper trading system with delayed live data. This invalidates the "code parity" guarantee since both operate on the same historical parquet.
- [MEDIUM] `run_daily_paper_trade` loads the strategy module fresh on each call (line 81) — no caching of compiled module. This adds overhead and risks the strategy file changing mid-session.
- [MEDIUM] Predicted return is set to the signal value (line 85): `"predicted_return": value`. The spec says forward reliability compares "predicted daily returns" vs "actual daily returns" — the predicted return should be estimated from the signal magnitude, not just set equal to the signal direction.
- [LOW] `daily_cron_job` (line 106) creates a new `PaperTrader` instance but then accesses `PaperTrader._configs` at the class level, which is empty — the existing instance has no configs registered. The cron job wouldn't find any strategies.

**Missing:**
- yfinance or live feed integration for delayed data
- Module caching for strategy reload
- Proper predicted return estimation from signal values
- Edge case handling: network retry with exponential backoff (spec: "3 attempts, 30s/60s/120s")

---

## backtest/reconciliation.py (F2.8)

**Status:** ⚠️ Partial

**Issues:**
- [MEDIUM] `Reconciliation.__init__` (line 31) takes `backtest_returns` and `paper_trader` as constructor arguments rather than querying from Lineage and PaperTrader as spec describes. Spec: "pulls backtest projected and paper trading realized returns (both stored in the Model Lineage system)."
- [MEDIUM] `compute_divergence` (line 49) uses `self.backtest_returns.get(backtest_run_id, [])` — expects a dict keyed by run_id rather than querying the lineage DB.
- [LOW] Status verdict `"insufficient forward history"` (line 47, 55) is returned as a verdict string but also appears in the `ReconciliationResult` verdict field. Mixing verdicts and system status messages is muddled.

**Missing:**
- Integration with ModelLineage for pulling backtest return series
- Integration with PaperTrader for pulling paper trading return series
- Proper date range overlap alignment (handled partially via concat+dropna)

---

## `__init__.py` files (4 files)

**Status:** ✅ Complete

**Issues:** None — all four (`robustness/__init__.py`, `factors/__init__.py`, `optimizer/__init__.py`, `data_studio/__init__.py`) are empty package markers, which is correct for namespace packages.

---

## Cross-Cutting Observations

### Compilation
All 14 non-`__init__` files pass `python3 -m py_compile` without errors.

### Data Loading
Most files correctly import from `shared.data_loader`. However, `robustness/tests.py` omits the import (receives VIX/returns as parameters, violating the rule that data_loader is the sole data access layer). Multiple files do per-ticker loops calling `get_ohlcv` in sequence — this is the most expensive pattern for parquet data and should use batch-loading.

### HMM Dependency
Three files stub HMM fitting (`evaluator.py:254`, `tests.py:274`, and the spec references `monte_carlo.py` elsewhere). Without a real HMM library (like `hmmlearn`), regime classification falls back to VIX percentile terciles.

### In-Memory State
`TrialRegistry`, `FactorLibrary`, and `UniverseBuilder` store state in class-level dicts. No DB persistence is implemented as the specs describe. This means data is lost on process restart and is shared across sessions/instances inadvertently.

### Formula Accuracy
Where implemented, the financial formulas are correct:
- Almgren-Chriss impact: `λ × σ × (trade/ADV)^(3/5) × 10000` ✓
- DSR/SR₀: Euler-Mascheroni corrected ✓
- Garman-Klass volatility ✓
- Jarque-Bera ✓
- IC decay models (linear/exponential/hyperbolic) with AIC selection ✓
- Gram-Schmidt orthogonalization ✓
- Sharpe/Sortino/Calmar/MaxDD ✓
- Composite score weights (30/20/25/25) ✓
- Verdict thresholds ✓
