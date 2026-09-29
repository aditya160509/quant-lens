# QUANT360 Studio v2 — Part 1 Code Review

**Review date:** July 26, 2026
**Files reviewed:** 12 (all compile with `py_compile`)
**Spec documents:** Studio v2 feature.md, STUDIO_V2_ARCHITECTURE.md, STUDIO_V2_FILE_SPECS.md

---

## `backend/app/studio_v2/__init__.py`

**Status:** ✅ Complete
**Issues:** None — empty package marker, correct.
**Missing:** Nothing.

---

## `backend/app/studio_v2/shared/__init__.py`

**Status:** ✅ Complete
**Issues:** None — empty package marker, correct.
**Missing:** Nothing.

---

## `backend/app/studio_v2/shared/data_loader.py`

**Status:** ✅ Complete (228 lines)
**Issues:**
- [low] `get_returns` uses `close` as a proxy for `adjusted_close` (line 129: `frame["adjusted_close"] = frame["close"]`). If the underlying parquet has an actual adjusted-close column, this silently discards dividend/split-adjustment information. If the parquet close IS already adjusted, this is correct — but the code should document this assumption.
- [low] `_load_factor_file` for CSV/AQR (line 191) reads only the first candidate file from the sorted glob list. The spec lists 36 AQR CSV files and `Developed_*.csv` multi-factor files — only the first is loaded per call. Downstream code that expects all AQR factors will get an incomplete view.
- [low] `_load_factor_file` for CSV (line 105-116) does not validate that the CSV has the expected columns — silently returns whatever is parsed.

**Missing:** Nothing from the Phase 1 spec. All 7 required functions are implemented (`get_returns`, `get_ohlcv`, `get_all_tickers`, `get_macro`, `get_factor_returns`, `get_market_cap`, `get_float`). Edge cases handled: empty tickers, missing tickers, non-finite values, date range outside coverage, empty DataFrames, file-not-found errors.

---

## `backend/app/studio_v2/shared/monte_carlo.py`

**Status:** ⚠️ Partial (277 lines)
**Issues:**
- [**critical**] `run_timing_perturbation` (lines 243-260) is **non-functional**. Line 257: `simulated = base.to_numpy() * (1.0 + 0.0 * shifts)` — the term `0.0 * shifts` is always zero (element-wise multiplication of zero by every shift value), making `(1.0 + 0.0)` = 1.0. Every "simulation" returns the identical trade-return series unperturbed. All 4,000 simulations produce the same Sharpe. The inline comment acknowledges the problem: "trade returns are re-ordered only by the perturbed execution dates in the full engine. At this shared-series layer the return distribution is preserved." — effectively admitting this mode is unimplemented.
- [medium] `run_all` (line 209) defaults `trade_log=None`, meaning timing perturbation is skipped unless the caller explicitly passes a trade log. While documented, this means the default call path (e.g., from Backtest Studio) will not run timing perturbation unless wired correctly.
- [low] `politis_romano_block_length` (line 84-107) uses an approximated MSE minimizer, not the full spectral density estimator from Politis & White (2004). The approximation (finding the first positive autocorrelation truncation) is reasonable but documented as an approximation.
- [low] Zero-variance series: returns all-NaN metrics but does not add a warning to the result's warning list.

**Missing:**
- Timing perturbation: actual date shifting requires access to the full price data and trade log with entry/exit timestamps, not just the return series. This is a fundamental architectural issue — the shared MC engine doesn't have access to the underlying price data needed to re-price shifted trades.

---

## `backend/app/studio_v2/algorithm_lab/linter.py`

**Status:** ✅ Complete (181 lines)
**Issues:**
- [low] `DuplicateVariableError` (line 37) is defined in both `linter.py` and `kernel.py` — two identical definitions. Should be extracted to a shared module to avoid divergence.
- [low] `check_lookahead_shift` (lines 130-138) flags ALL `.values` calls on subscripted expressions, which may produce false positives for legitimate patterns like `df.loc[mask].values` where alignment intent is correct.
- [low] Large file debouncing (>1000 lines, 300ms throttle) is not implemented as specified in the FILE_SPECS.md (line 128). The linter processes files of any size synchronously.
- [low] `register_completion_providers` (lines 154-165) tries monkey-patching onto a `monaco_api` parameter — this is a server-side abstraction for what should be a frontend-only Monaco API call. The function is harmless but doesn't wire up to anything real on the backend.

**Missing:** Nothing from the spec. All 6 checks implemented (`check_shift_without_ffill`, `check_hardcoded_date_ranges`, `check_future_date_reference`, `check_lookahead_shift`, `check_non_deterministic`) plus `register_completion_providers` and `build_function_registry`. Edge cases: empty source, syntax errors, multi-line expressions all handled.

---

## `backend/app/studio_v2/algorithm_lab/kernel.py`

**Status:** ⚠️ Partial (330 lines)
**Issues:**
- [medium] `detect_duplicate_definitions` (lines 143-146) returns `False` on success instead of `True`/`False` meaningfully. It also raises the same `DuplicateVariableError` that `add_variable_definition` already raises — this is dead code that is never called externally.
- [medium] `mark_stale_downstream` (lines 156-159) marks only direct dependents as stale but **does not propagate transitively**. The spec requires marking ALL transitive dependents: `mark_stale_downstream(cell_id: str) -> None` — propagates staleness markers to all transitive dependents (FILE_SPECS.md line 30). However, `get_dependents` (lines 120-130) DOES perform transitive traversal (BFS through the graph), so it's possible that `get_dependents` is correct but `mark_stale_downstream` calls it and gets the transitive set correctly. Let me re-check: `get_dependents` walks `self.cell_variables` to get the variables defined by the cell, then walks `self.variable_reads` to find which cells read those variables, then recursively walks those cells' defined variables. This IS transitive. So `mark_stale_downstream` IS transitive. But `stale_cells` is never cleared — stale markers accumulate indefinitely until `restart_kernel`. This is a correctness issue: if a stale dependent cell is re-executed, its stale flag should be removed. The code does not handle this.
- [low] `_check_definitions_and_reads` (lines 219-233) parses the AST twice — once here and again at line 249 in `execute_code_sync`. Redundant work.
- [low] Session timeout during a long computation is not handled (no keepalive pings from inside `execute_code_sync`).
- [low] Kernel crash detection and auto-restart is not implemented.
- [low] Memory exhaustion / watermark is not implemented.
- [low] Checkpoint directory path (line 197) uses `parents[2]` from the kernel.py location, which assumes a specific project layout. If the package is installed as a library, this path would be wrong.
- [low] `restore_from_checkpoint` (lines 293-301) does not update the `DependencyTracker` — the restored namespace has no staleness tracking until the next `record_execution` call.

**Missing:**
- Dependency cycle detection and reporting — the spec says "detect and report as error" but there is no cycle detection in the dependency graph.
- Configuration persistence (manual/auto/confirm modes for dependency resolution) — not implemented.
- `get_session_timeout` (line 313) implemented but no idle GC timer that actually garbage-collects expired sessions.
- `serialize_namespace` filters `np` and `pd` but NOT the internal state variables (`_*` prefixed), which is done correctly on line 308.

---

## `backend/app/studio_v2/backtest/engine.py`

**Status:** ⚠️ Partial (376 lines)
**Issues:**
- [**critical**] `_apply_corporate_actions` (lines 358-364) does **NOT** handle any corporate actions. It only updates `last_price` from the most recent close. The spec requires: splits (multiply shares, divide cost basis), dividends (add cash), delistings. None of these are implemented. This is a gap that will cause backtests to have incorrect position tracking during corporate event periods.
- [medium] `_run_date_loop` (lines 236-247) is **dead code** — it duplicates the loop logic from `run()` but is never called externally or from `run()`. It creates `_loop_trades`, `_loop_orders`, `_loop_navs` on the instance (line 240) that are never read.
- [medium] The engine loads ALL ticker OHLCV data into memory upfront (`_load_and_prepare_universe`) via individual `get_ohlcv` calls. For 500+ tickers, this means 500+ separate parquet reads. The data_loader provides `get_returns(tickers, start, end)` which loads all tickers in a single read, but the engine never uses it. The spec calls for chunking and `multiprocessing.Pool` above 500 tickers (line 263 of spec), which is not implemented.
- [low] `_combined_history` (lines 228-234) concatenates all tickers' data into one DataFrame for the strategy function. If the strategy function does look-ahead within its own logic (e.g., using `.shift(-1)` on the combined DataFrame), the engine has no guard — it relies on the linter to catch that.
- [low] The Almgren-Chriss impact calculation defaults to `λ = 4e-6` (large-cap default) for all stocks (line 343), regardless of market cap. The spec calls for per-bucket λ from `shared.liquidity`.
- [low] No margin modeling beyond the `side = "short"` label (line 313-314). The spec says "Margin modeling is available for leveraged strategies."

**Missing:**
- Corporate actions handling (splits, dividends, delistings) — **critical gap**.
- Hard-to-borrow flag checking in `_generate_orders` — not implemented.
- Parallel processing for >500 ticker universes — not implemented.
- `_is_rebalance_date` supports daily/weekly/monthly/quarterly but not "custom trigger" as specified in `SimulationConfig`.

---

## `backend/app/studio_v2/backtest/metrics.py`

**Status:** ✅ Complete (174 lines)
**Issues:**
- [low] `compute_pbo` (lines 126-138) tries column-wise Sharpe first, then row-wise if all NaN. This is a heuristic — a DataFrame where some columns have NaN and others don't will produce mixed results. The spec shows PBO computed from the CPCV path distribution where paths are columns.
- [low] `_normal_ppf` fallback (line 36) uses `statistics.NormalDist().inv_cdf()` which requires Python 3.8+. Acceptable for modern Python but not documented.
- [low] `compute_dsr` (lines 112-124) recomputes `_clean(returns)` even though the caller already passes a cleaned `returns` and a separately computed `sharpe`. The function re-cleans and gets the same result but the parameter name `sharpe` shadows the computed one — the function uses the `sharpe` parameter, not recomputing it from cleaned data. This is correct but confusing.

**Missing:** Nothing from the spec. All 7 core metrics implemented (DSR, PBO, PSR, Sharpe, Sortino, Calmar, Max Drawdown) plus win rate, profit factor, skewness, excess kurtosis. All formulas verified against spec:
- DSR formula (line 112-124): matches `Φ[(SR_CPCV - SR₀) × √(T-1) / √(1 - γ₃×SR_CPCV + (γ₄-1)/4 × SR_CPCV²)]` ✓
- PSR formula (line 104-110): matches `Z[ (SR_hat × √(T-1)) / √(1 - γ₃×SR_hat + (γ₄-1)/4 × SR_hat²) ]` ✓
- PBO formula (line 126-138): matches `fraction of CPCV paths whose OOS Sharpe < median path Sharpe` ✓
- SR₀ formula (line 120-121): matches `√(Var[SR]) × ((1-γ)Φ⁻¹(1-1/M) + γΦ⁻¹(1-1/(M·e)))` ✓
- M=1 case (line 117): SR₀ = 0, DSR reduces to PSR ✓
- Edge cases: zero variance, no downside, empty series, single day, missing CPCV paths — all handled ✓

---

## `backend/app/studio_v2/backtest/lineage.py`

**Status:** ⚠️ Partial (234 lines)
**Issues:**
- [medium] `_content_for` (lines 113-115): when the strategy file path does not exist (e.g., inline strategy where the "path" is just a name string), it returns `(str(strategy_file), str(strategy_file))` — meaning the file path string itself is used as the file content for hash computation. This produces a meaningless hash and stores a non-existent path as the strategy file. The record_run method then tries to compute metrics from the result, but uses `Path(path).name` for the strategy name (line 135), which for an inline string would just be the string itself — acceptable but fragile.
- [medium] `get_lineage_graph` (lines 147-151) does **not** acquire `self._lock` while iterating `self._runs`. Concurrent access from `record_run` (which does acquire the lock) could cause a race condition on the dict, though Python's GIL makes this unlikely to produce visible corruption.
- [low] `record_run` (line 128) imports `PerformanceMetrics` inside the method body — a circular-import workaround that makes the dependency unclear.
- [low] `search_runs` (lines 177-192) has a bug: the positional arguments passed from the router (`SearchQuery(dsr_min, pbo_max, sharpe_min, limit=limit, offset=offset)`) are correct because the dataclass ordering places `limit` and `offset` after `sortino_min` through `strategy_name_contains`, which all have defaults. This is correct by accident — `sharpe_min` correctly maps to the 3rd field. However, `sortino_min`, `max_drawdown_max`, `date_range_start`, `date_range_end`, `tags`, and `strategy_name_contains` are silently dropped from the router's query params.
- [low] `search_runs` (line 182-188): `metrics_value()` function (lines 229-234) returns `-float("inf")` for NaN/None metrics, which means any comparison like `metrics >= query.dsr_min` will be `False` for missing metrics — correct behavior but unintuitive from reading.
- [low] `get_dag_layout` (lines 216-226) does NOT acquire `self._lock`.
- [low] Uses JSON file persistence instead of the PostgreSQL/MongoDB specified in the feature spec. Acceptable for a prototype/Phase 1 implementation.

**Missing:**
- DB-based persistence (PostgreSQL/MongoDB) — uses JSON file instead.
- `record_walkforward_window` implemented (line 210) but no route or front-end consumes it yet.
- "Non-default parameter detection compares the run's parameter dict against the platform defaults" — not implemented in `record_run`. The `detect_non_default_parameters` function exists as a standalone function but is never called.

---

## `backend/app/studio_v2/algorithm_lab/__init__.py`

**Status:** ✅ Complete
**Issues:** None — empty package marker, correct.
**Missing:** Nothing.

---

## `backend/app/studio_v2/backtest/__init__.py`

**Status:** ✅ Complete
**Issues:** None — empty package marker, correct.
**Missing:** Nothing.

---

## `backend/app/studio_v2/router.py`

**Status:** ⚠️ Partial (133 lines)
**Issues:**
- [medium] All Phase 2-4 endpoints (F3 Robustness Lab, F4 Factor Sandbox, F5 Optimizer, F6 Data Studio) are **stubs** that return placeholder responses. This is expected per the build plan (Phase 1 only covers F1.1-F1.2, F2.2-F2.4, F2.6), but the stubs register routes without raising errors, silently returning `{"status": "accepted"}` or `{"status": "ready"}`.
- [low] `search_lineage` (line 90) passes only 3 of the 11 `SearchQuery` fields as query parameters. All others (`sortino_min`, `max_drawdown_max`, `date_range_start`, `date_range_end`, `tags`, `strategy_name_contains`) are not exposed via the API.
- [low] `_jsonable` (lines 24-39) uses `not np.isfinite(value)` inside the `np.floating` branch (line 36) — `np.isfinite(np.nan)` is `True` (not False), which means `NaN` values in arrays will pass the `not np.isfinite()` check incorrectly and return the value directly (NaN) instead of `None`. Actually, `np.isfinite(np.nan)` returns `False`, so `not np.isfinite(np.nan)` is `True`, so NaN values become `None`. Wait — let me re-check: for `np.floating` types, the check is `not np.isfinite(value)` which is True for NaN, so it returns `None`. For `np.ndarray`, it calls `value.tolist()` which converts NaN to `nan` (a string). For DataFrames and Series, `replace({np.nan: None})` handles NaN correctly. So there's a small inconsistency: NaN in `np.ndarray` via `tolist()` will produce `"nan"` strings, not `None`.
- [low] The `_lazy` helper (lines 107-109) is only used by `lazy_factor` (line 116). All other lazy endpoints use hardcoded imports.
- [low] `push_to_backtest` (lines 72-74) returns a static "ready" response — it does not actually push to Backtest Studio. The F1.8 spec says "serialized and sent to Backtest Studio in one click."
- [low] Paper trading endpoints (lines 95-101) instantiate a NEW `PaperTrader()` on every request — no state is shared between calls. The `get_status` call creates a fresh instance that has no memory of the `run_daily_paper_trade` call. This means status will always be empty. These classes are Phase 4 and not yet built, but the endpoints are live.

**Missing:**
- Actual Phase 2-4 implementations — all stubbed out as expected for Phase 1.
- Request body validation for some endpoints (e.g., `run_backtest` just passes `payload` through to `SimulationConfig(**payload)` without checking required fields).
- The spec shows many more query params and filters than the router exposes.

---

## Summary

| File | Status | Compiles | Lines |
|------|--------|----------|-------|
| `__init__.py` | ✅ Complete | OK | 0 |
| `shared/__init__.py` | ✅ Complete | OK | 0 |
| `shared/data_loader.py` | ✅ Complete | OK | 228 |
| `shared/monte_carlo.py` | ⚠️ **Partial** | OK | 277 |
| `algorithm_lab/linter.py` | ✅ Complete | OK | 181 |
| `algorithm_lab/kernel.py` | ⚠️ **Partial** | OK | 330 |
| `backtest/engine.py` | ⚠️ **Partial** | OK | 376 |
| `backtest/metrics.py` | ✅ Complete | OK | 174 |
| `backtest/lineage.py` | ⚠️ **Partial** | OK | 234 |
| `algorithm_lab/__init__.py` | ✅ Complete | OK | 0 |
| `backtest/__init__.py` | ✅ Complete | OK | 0 |
| `router.py` | ⚠️ **Partial** | OK | 133 |

**Correctness verdict:** All 12 files compile. Formulas in `metrics.py` (DSR, PBO, PSR, Sharpe, Sortino, Calmar) are verified correct against the spec. The `data_loader.py` correctly reads from parquet files only with no external API calls.

**Critical issues that need fixing before production:**

1. **`monte_carlo.py:257`** — `run_timing_perturbation` does nothing (`0.0 * shifts` = 0, so all 4,000 simulations produce identical results).
2. **`engine.py:358-364`** — `_apply_corporate_actions` only updates prices; splits, dividends, and delistings are not applied.
3. **`kernel.py:156-159`** — `mark_stale_downstream` never clears stale flags when downstream cells are re-executed.
