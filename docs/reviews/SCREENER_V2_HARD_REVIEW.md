# Screener V2: hard review and surgical edit plan

**Scope:** the 1,901-line uploaded snapshot, not the complete repository. Source line numbers refer to the uploaded snapshot (1-based). **No edits have been applied to the repository.** No benchmark or test has been run here. Performance impacts are hypotheses until profiled. The user-supplied measured peaks are 6.52 GB before optimization, 2.97 GB at `194ca5a` for the full 3,831-name screen, and 0.95 GB for 50 names. The <1 GB full-universe goal is a target, not a demonstrated outcome.

## Executive decision

**Do not start with Rust.** First fix two correctness risks, remove duplicated historical work, introduce bounded and versioned feature storage, and profile retained allocations. Rust/PyO3 is justified only if a specific kernel remains dominant after that. A full 3,831 × 756 × 5 float64 OHLCV cube is about 116 MB of raw values, so a 2.97 GB process peak cannot be explained by one such cube alone. Python/Pandas/Polars conversions, repeated intermediate matrices, fundamentals, cached copies, allocator high-water marks, and scan buffers need attribution. `ru_maxrss` is a historical peak, **not** live resident memory.

## Severity 0: correctness and future leakage

### E01 — Fixed, bounded, as-of calendar BEFORE indicator construction (BLOCKER)
**Source:** `performance.py` 1753–1776; `data_loader.py` 768–788; `estimators.py` 187–207 (source-file positions can be located using the quoted expressions below).

**Before:** `_matrix` does `raw.pivot(...).sort('Date').tail(lookback)` across the requested union of dates; `_session_matrix` subsequently reindexes to calendar sessions. The historical branch does `pivot_last(raw_ohlcv, 'Close').tail(...)` before calendar reindexing. Different requested universes can thus choose different starting dates and different EMA/Wilder seeds. `raw_ohlcv` is also cropped to calendar sessions, so the seed depends on alignment.

**After:** resolve an explicit `as_of` cutoff and a canonical observed session index first; fetch all needed tickers up to that cutoff; pivot/reindex onto the same calendar **before** taking the last N sessions; compute indicators on that fixed N-session index. Ensure the `calendar_ticker` itself is bounded by the same `as_of`. Define what happens to off-calendar observations and document it. Do not silently forward-fill prices. Avoid a `last date of requested symbols` cutoff.

**Implementation sketch (replace the algorithm, not a drop-in patch):**
```python
cutoff = pd.Timestamp(as_of) if as_of is not None else canonical_latest_session
sessions = load_observed_calendar(calendar_ticker, end=cutoff).tail(window)
raw = fetch_ohlcv(symbols, start=sessions.min(), end=cutoff)
prices = pivot_last(raw, 'Close').reindex(index=sessions, columns=symbols)
volumes = pivot_last(raw, 'Volume').reindex(index=sessions, columns=symbols)
```
For EMA seed equivalence across universe sizes, use exactly the same calendar and warmup policy. Decide whether indicators are seeded on a fixed 756-session window or longer history. Changing seed policy requires a new reference baseline. For historical dates, `end=cutoff` is mandatory at **every** read.

**Tests:** a ticker alone vs 50 vs 3,831 yields identical per-ticker raw technical features for the same cutoff and config; historical cutoff vs a physically truncated market file; missing SPY session; holiday; listing after cutoff; missing latest quote; custom calendar; sparse ticker; as-of before latest data. Compare *universe-dependent ranks separately*: percentile/rank columns legitimately change with the screened universe and must not be required to match.

### E02 — Potential as-of leak in the calendar path (BLOCKER)
**Source:** `estimators.py` 192–207. `as_of_date` filters `raw_ohlcv`, but `calendar_quotes = ohlcv_for_symbols([...])` depends on the ambient `AS_OF` context, not the `periods['as_of_date']` argument. The same issue affects `close_matrix` and `volume_matrix` if a caller passes only `periods['as_of_date']` without entering `as_of_context`.

**Before:**
```python
as_of_date = pd.to_datetime(periods.get('as_of_date'), errors='coerce') if periods.get('as_of_date') else None
# ... later ...
calendar_quotes = ohlcv_for_symbols([config.get('calendar_ticker', 'SPY')])
```
**After:** use one effective cutoff across every loader, preferably at the API boundary via `with as_of_context(effective_cutoff): ...`, and have functions reject inconsistent explicit/ambient dates. Calendar selection and factor/FX reads must observe that same cutoff. Do not simply filter `calendar_quotes` after indicators have already been calculated.

**Tests:** invoke `latest_technical_features(..., periods={'as_of_date': old_date})` directly without ambient context and compare with explicit context; append future SPY and FX rows and verify byte-for-byte unchanged historical results.

### E03 — Potential point-in-time contamination from fundamentals metadata
**Source:** `fundamentals.py` 1000–1090. The code comments correctly recognize that vendor `.info` ratios are repeated current snapshots, then nulls some fields. But other fallback fields and metadata (`sector`, `industry`, `exchange`, `company_name`, alternate market cap/valuation columns) may still be present in historical rows without an availability timestamp.

**After:** establish a field-level provenance registry: statement-derived and dated, market-derived at cutoff, or undated vendor snapshot. For historical requests, reject/blank undated metadata and ratios unless their historical availability is established. Preserve current-mode output when legitimate. `sector`/industry labels are especially important because historical ranking and filters depend on them. This is a **verification requirement**, not proof that every listed field currently leaks.

### E04 — Source-version cache keys are not robust enough
**Source:** `performance.py` `_path_version()` 1727-ish; `data_loader.py` `_market_derived` 602–616; `load_factor_returns` 897–911.

**Before:** only `st_mtime_ns` is used for most cache versions; `load_factor_returns` has a process-lifetime `@lru_cache(maxsize=1)` with no file-version argument. Same-mtime replacement, missing-to-present transitions, or changed factor CSVs can yield stale results.

**After:** key derived artifacts on a manifest containing source path, file size, nanosecond mtime, schema/algorithm version and config; use content hash when strict integrity is needed. Factor caches must include both CSV versions. Do not delete another worker's active cache artifacts while running concurrently. Add an atomic-write plus lock/ownership strategy and startup garbage collection. A manifest is not a substitute for correctness tests.

### E05 — `_flagged_market_tickers` packs dates into an unsafe integer key
**Source:** `data_loader.py` 626–650.

**Before:**
```python
keys[position:position + len(rows)] = rows * 100_000 + days + 50_000
```
This is only collision-free if the date encoding stays in a known non-overlapping range of 100,000 integers. The assumption is neither asserted nor versioned. The code also allocates an `int64` array sized to every source row and sorts it, contributing memory and startup cost.

**After:** use a typed pair `(ticker_code, day_code)` and lexicographic sorting, or an explicit checked offset with `assert 0 <= day_code < stride` before packing. Prefer a one-time integrity artifact built at ingestion, rather than repeating a whole-market duplicate scan at runtime. Verify that alias normalization and conflict detection remain identical. Measure memory before adopting structured arrays: they may cost more per row.

### E06 — Cache correctness after a file changes
**Source:** `data_loader.py` 818–825 `latest_fundamentals` and 897–911 `load_factor_returns` are unversioned `@lru_cache(maxsize=1)`; `_fundamentals_frame(version)` calls a separately versioned loader.

**After:** make all source-dependent caches versioned and ensure invalidation cascades through fundamentals, factor returns, market metadata, FX, and derived feature parquet. Explicitly test same-process source replacement.

## Severity 1: largest likely speed/memory wins

### E07 — Remove redundant price/volume loading in historical estimators
**Source:** `estimators.py` 187–196; `pit_cache.py` 1253–1309.

**Before:**
```python
raw_ohlcv = ohlcv_for_symbols(fetch_symbols, lookback_days=max(lookback_days, 300))
prices = close_matrix(fetch_symbols, lookback_days=max(lookback_days, 260))
volumes = volume_matrix(fetch_symbols, lookback_days=max(lookback_days, 260))
# historical path immediately overwrites prices/volumes from raw_ohlcv
```
**After:** branch *before* fetching: historical path loads one bounded raw dataset and derives all necessary fields; current path selects either cached matrices or one raw frame based on profiling. Remove `pit_cache` monkey-patching of module globals after direct refactoring. This eliminates fragile global mutation and a hidden dependency on import order.

**Tests:** current/historical parity, repeated backtests, concurrent context isolation, cache on/off parity.

### E08 — Precompute raw technical features, NOT universe-relative scores
**Source:** `estimators.py` 174–408; `panel.py` 110–140.

**Before:** every full screen and each historical formation date recomputes moving averages, RSI, ATR/ADX, MACD, regression, volatility and many intermediate frames.

**After:** create a daily **per-ticker** technical feature store in Parquet, keyed by `(ticker, as_of_session, indicator_config_hash, source_version, algorithm_version, calendar_id, seed_policy)`. Precompute raw features once per new observed session. At query time, read only requested tickers and columns, then compute cross-sectional percentiles, ranks and group scores on the **actual requested universe**. Keep `bollinger_width_percentile`, `amihud_percentile`, `technical_percentile`, `short_term_reversal_flag` and other `rank_pct`-derived fields OUT of per-ticker persisted values, or recompute them after loading raw features. The user's 14-column discrepancy may include both legitimate universe-relative differences and erroneous EMA seed differences; classify each column before changing hashes.

**PIT:** an indicator computed for historical session `t` must use only data available at `t`. A newly appended file cannot silently change historical rows. The 756-session window and Wilder/EMA/OBV seed semantics must match the approved reference. Handle configurable periods by config-keyed caches or an explicit unsupported-configuration fallback. Incremental rolling/EMA state is safe only if it reproduces the chosen window-seeding semantics; a continuously seeded EMA generally does not.

**Parquet design:** partition by session bucket or ticker hash after benchmarking query patterns, not thousands of tiny files; sort within row groups; dictionary encode ticker; project only needed columns; use `scan_parquet` with predicate pushdown; atomic publish with manifest and schema version; build a small index for `(date,ticker)` lookups. Do not eagerly read every historical session to answer today's screen.

### E09 — Replace wide *intermediate* matrices with bounded per-ticker kernels
**Source:** `estimators.py` 215–399.

**Before:** repeated full-width SMA matrices for 20/50/100/200, MACD matrices, ATR/ADX intermediates, OBV, Bollinger and OHLC arrays remain alive during computation.

**After:** compute by ticker or bounded chunks (e.g. 64–256 tickers, benchmark) and emit a single latest-row result per ticker. Use NumPy/Numba or Polars expression kernels only where output parity is demonstrated. For rolling windows, calculate only the last required output and cross-age lookback, rather than full time-series output for all columns. For Wilder/EMA preserve `adjust=False`, min periods, NaN behavior, and initial seed. Polars `ewm_mean` and pandas `ewm` must be checked against the same missing-data and seed cases before substitution.

**Expected benefit:** likely reduction in intermediate peak, magnitude unmeasured. Do not convert to float32 by default: this can alter rankings and output hashes.

### E10 — Remove full-history SMA frames where only current/crossing values are needed
**Source:** `estimators.py` 252–279.

**Before:**
```python
ma_series = smas[window] = prices.rolling(window).mean()
```
**After:** compute last two SMA values for daily crosses and only `cross_lookback+1` relevant SMA observations for cross-age; use window-plus-tail inputs sufficient for exact rolling results. For 50/200 cross, calculate the last `max(20, cross_lookback)+1` SMA pairs. Keep one bounded buffer at a time. Validate missing-value behavior and all 20/50/100/200 outputs.

### E11 — Remove `scipy.stats.linregress` Python call per ticker
**Source:** `estimators.py` 330–334.

**Before:**
```python
out['obv_20d_slope'] = obv.tail(20).apply(lambda column: linregress(...).slope if ... else np.nan)
```
**After:** vectorize OLS slope over 20 observations using `sum((x-xbar)*(y-ybar))/sum((x-xbar)^2)` for complete columns; preserve the same float64 summation order where exact hashes are mandatory, or set a strict tolerance and rebaseline. Test zero/NaN volume, missing prices, and all-NaN columns. A Python loop across 3,831 columns is avoidable.

### E12 — Batch idiosyncratic-vol regressions in the normal path
**Source:** `estimators.py` 444–457; `pit_cache.py` 1274–1309.

**Before:** statsmodels OLS is called once per ticker in the default path. A batched NumPy implementation is used only under a PIT scope, and only if all factor rows are complete.

**After:** move batched regression to `estimators.py`, with a shared design matrix for complete rows, grouping missingness patterns if needed. Use a stable QR/SVD solver, not explicit matrix inverse. Verify statsmodels intercept behavior, residual normalization, rank-deficient factors, missing returns, and float tolerances. Remove import-time rebinding. This is a strong candidate for substantial CPU savings, not necessarily the main RSS gain.

### E13 — Bound PIT panel caches by actual reuse
**Source:** `validation.py` 1660–1698; `pit_cache.py` 1240–1273.

**Before:** `panels` retains full panels for every formation date and potentially academic/composite intermediates; `cache` retains every score series; shared statement snapshots are stored under a tuple of all symbols.

**After:** separate immutable source snapshots from ephemeral panels. Use a bounded LRU for panels (size selected from composite lookback requirements), retain compact score vectors for execution dates, and spill feature rows to the versioned Parquet store. **Do not evict training history required by `component_scores`**; inspect its access pattern first. Store cache metrics (bytes, hits, misses, entries) per backtest.

### E14 — Eliminate redundant cross-sectional frame copying
**Source:** `validation.py` `panel_at` returns `panels[key].copy()`; `panel.py` 79–141 creates many columns. `fundamentals.py` 1000–1100 also creates many derived columns.

**After:** return an immutable/readonly panel view or explicitly project needed columns for the requested scoring mode, with a copy only when a caller mutates it. In particular, a field-score backtest need not preserve every explanatory feature and text column at every formation date. Maintain exact behavior for formulas and composites requiring broad columns. Profile object/string columns separately from numeric arrays.

### E15 — Make the backtest's execution loop sparse, but preserve accounting
**Source:** `backtest.py` 1330–1455.

**Before:** each day performs multiple pandas Series allocations across all tickers; every rebalance creates a full zero target; per-position attribution iterates Python objects.

**After:** map tickers to integer positions once, store prices and weights in NumPy float64 arrays, and operate on active holdings for daily P&L. At rebalance, compare sparse target positions with sparse drifted holdings. Preserve the exact `gross`, drift, fixed-point transaction-cost equation, episode open/close semantics, cash handling, execution at t+1, and no stale prices. This is secondary to repeated panel construction for the reported 12-name/66–112-second case; first profile how much time is spent inside `score_at` vs `simulate`.

### E16 — Avoid repeated 5× backtests in weekday comparison
**Source:** `validation.py` 1639–1642 `score_backtest_by_weekday`.

**Before:** calls `score_backtest` five times, potentially rebuilding PIT panels independently if callers don't share a cache.

**After:** explicitly share immutable historical feature rows and score computations across weekdays, while keeping separate execution state. Confirm each weekday's exact formation dates and independent results. Benchmark weekday sweep before/after.

## Severity 2: targeted reliability and lower-risk edits

### E17 — Stop caching huge matrices with an entry-count-only policy
**Source:** `performance.py` three `@lru_cache(maxsize=6)` matrix caches.

**After:** replace or wrap with a byte-budgeted cache, or bypass wide matrices entirely for the precomputed-feature screen. An entry-count cache can retain several full-universe arrays per configuration. Track `.memory_usage(deep=True).sum()` and cache eviction. A low fixed count is not enough if keys vary by universe, lookback, source version and coverage.

### E18 — Avoid redundant `ohlcv_for_symbols` calls in `metric_panel`
**Source:** `panel.py` 99–109. `ohlcv_for_symbols(symbols + ['SPY'], 1)` is used solely to compute latest observed price date.

**After:** obtain the canonical as-of session from the already loaded technical result/calendar metadata, rather than reading the universe again. Confirm the factor observation-date rule is still correct for missing/stale ticker prices.

### E19 — Check NaN handling in group percentile ranks
**Source:** `panel.py` 71–76. `_group_rank_pct` uses `group.transform('count')`, `rank(method='average')`, and masks singleton groups to 50.

**After:** preserve this formula exactly when migrating to Polars/NumPy; don't substitute a built-in percent rank with different singleton/tie semantics. Add tests for groups of size 0/1/2, ties, all missing, and mixed missing values. The `pe_sector_percentile` formula on line 118 uses `rank(pct=True, ascending=False)` and is *not* identical to `_group_rank_pct`; preserve deliberately or document a corrected definition.

### E20 — Check `_standardize_frame` validation cost and consistency
**Source:** `data_loader.py` 555–579 and `performance.py` `_subset_frame`.

**Before:** each subset is sorted and duplicate-checked, while a whole-file integrity check may be triggered separately. This can repeat expensive work.

**After:** validate and normalize at ingestion into a canonical Parquet dataset with a versioned integrity manifest, then use fast read-only queries. Continue rejecting conflicting normalized aliases and invalid dates. Do not remove validation before there is an equivalent ingestion guarantee.

### E21 — Fix duplicate/missing fundamentals row semantics before optimizing
**Source:** `fundamentals.py` `statement_snapshots`, especially rolling 4-quarter flow assembly, `reset_index(...).reindex(quarters.index)`, and `base` selection.

**After:** construct tests for shuffled input order, nonconsecutive quarterly reports, duplicate report dates, annual/quarterly overlap, missing quarter, and null flow values. Confirm index alignment is positional and date-keyed as intended. Only then rewrite with groupwise rolling or Polars; subtle alignment bugs could silently change valuation scores.

### E22 — Fix factor data versioning and regression factor-date alignment
**Source:** `data_loader.py` 897–911; `estimators.py` 444–457.

**After:** version the FF5 and momentum inputs and assert no factor date after cutoff. Verify that `factor_returns` and stock USD returns have matching session dates and units (the loader divides source percentages by 100). Preserve the current missing-factor behavior, or explicitly document a new policy.

### E23 — Backtest accounting edge-case tests
**Source:** `backtest.py` 1330–1455.

**After:** add golden tests for missing held prices, missing execution prices, zero holdings, short exposure, leverage, costs near 1000 bps, scores with ties, weekday shifts, all-negative weighted scores, stock delisting/missing last quote, and no eligible names. Confirm P&L attribution sums to reported totals within tolerance and `t` signals never affect `t` returns.

### E24 — Clarify memory measurement
**Source:** user notes lines 7–33.

**Before:** `ru_maxrss` peak is compared with an observation of under-1-GB live data.

**After:** measure at least (a) fresh-process peak RSS, (b) resident size after warmup, (c) Python-traced allocations, (d) Arrow/Polars allocations where available, (e) cache retained bytes, and (f) runtime. On macOS, `ru_maxrss` is reported in bytes; verify conversion to GiB. Measure both cold and warm runs with identical source files. Separate loader, feature computation, fundamentals, panel ranking, serialization and backtest formation timings.

## Concrete implementation sequence and acceptance gates

| Phase | Changes | Required gate |
|---|---|---|
| 0 | Instrument per-stage wall time, RSS, retained cache bytes; capture golden fixtures | Reproduce 3,831/50/12-name baselines in clean processes |
| 1 | E01–E06 correctness and cache-version fixes | Historical no-future tests, fixed-ticker invariance, explicit accepted rebaseline |
| 2 | E07, E11, E12, E18: remove duplicated scans and Python regression loops | 50/full results unchanged except approved fixes; measured speed/RSS |
| 3 | E08: versioned point-in-time daily raw feature Parquet | Precomputed vs on-demand raw-feature parity across dates/configs |
| 4 | E09, E10, E17: bounded indicator kernels and cache | Full 3,831-name warm screen peak RSS <1 GiB if achievable; no silent accuracy loss |
| 5 | E13–E16: historical cache and sparse execution | 12-name backtest faster with identical trades, curve and PIT checks |
| 6 | Rust/Numba only for profiled remaining kernels | Net gain includes FFI overhead and memory, not just microbenchmark speed |

### Benchmark harness contract

Use a separate process for each run; three repetitions each; log median and worst-case; pin thread count, source versions, ticker set, cutoff, period config and cache state. Report `wall_s`, `peak_rss_gib`, `post_run_rss_gib`, `feature_store_bytes`, `cache_retained_bytes`, `num_panels`, `per_stage_s`, and `result_sha256`. Keep **two** hashes: (1) legacy baseline for changes expected to preserve behavior and (2) approved corrected baseline after EMA/PIT fixes. Hash canonical sorted outputs with stable NaN/date/float encoding. Comparing cross-sectional percentile values across different universes is not a valid invariant.

### Priority matrix

| Edit | Confidence | Likely value | Risk |
|---|---|---|---|
| E01–E02 | High that issue exists | Correctness prerequisite | High baseline impact |
| E07 | High | Removes redundant historical work | Low/medium |
| E08 | High architectural value | Largest likely warm-run win | High build complexity |
| E11–E12 | High | CPU speedup | Floating-point parity |
| E13 | Medium | Backtest memory | Composite history dependencies |
| E09–E10 | Medium | Peak memory | Indicator parity |
| E15 | Medium | Execution CPU | Financial accounting regression |
| Rust port | Low before profiling | Unknown | High |

## External documentation to consult during implementation

These are **reference URLs, not claims of having executed or verified an external solution**:

- Polars lazy scans, predicate/projection pushdown: https://docs.pola.rs/user-guide/lazy/optimizations/
- Polars exponential moving average semantics: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.ewm_mean.html
- Pandas EWM seed/NaN behavior: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.ewm.html
- PyArrow Parquet dataset filters/columns: https://arrow.apache.org/docs/python/dataset.html
- Python `functools.lru_cache`: https://docs.python.org/3/library/functools.html#functools.lru_cache
- Python `tracemalloc` limitations: https://docs.python.org/3/library/tracemalloc.html
- Pandas copy-on-write: https://pandas.pydata.org/docs/user_guide/copy_on_write.html
- Numba performance tips: https://numba.readthedocs.io/en/stable/user/performance-tips.html

## Instructions for an implementing agent

1. Work in a new branch; do not overwrite or modify existing benchmark fixtures.
2. Implement **one numbered edit per commit**, except tightly coupled E01/E02.
3. For each edit, provide exact changed repository file/line ranges, before/after snippets, a correctness rationale, tests run and their actual output, peak RSS and runtime deltas, and the commit SHA.
4. Keep the public API, result schema, financial execution semantics, missing-data policy and point-in-time guarantees intact unless the change is explicitly approved and rebaselined.
5. Never report an unrun test as passing. Never claim <1 GB until a clean-process 3,831-name measurement confirms it.
6. If the full source tree exposes additional callers, update them consistently; the uploaded snapshot omits `currency.py`, `stats.py`, `composite.py`, `screener.py`, and tests, so final patches require repository-wide search.

**Bottom line:** Fix calendar/PIT seeding first, precompute only raw per-ticker features, retain universe-relative ranks at query time, and bound the historical cache. These are more defensible than a blanket Rust rewrite and directly target both the observed 2.97 GB peak and 66–112-second small backtests.
