This is a large, well-structured codebase. Let me go through it systematically and list every meaningful speed lever, organized by where the gain lives.

---

## `performance.py` kernels

**`batch_covariance_upper`**

- The `np.moveaxis` + `np.einsum` path allocates a large intermediate `(n_windows, window, n_factors, n_factors)` tensor. Replace with a direct stride-trick view and a single batched `np.einsum("bki,bkj->bij", centered, centered)` using `optimize="optimal"` — avoids the moveaxis copy entirely.
- Cast to `float32` before einsum, not after — saves one traversal.
- For large `step` values the sliding window is sparse; skip the view entirely and use a raw loop with `np.cov` only when `n_windows < 50`, avoiding einsum setup overhead on tiny batches.

**`rolling_autocorr_1` (Numba)**

- Currently O(N·W) with inner Python-equivalent arithmetic. Add `parallel=True` — the outer loop over `i` is embarrassingly parallel and has no data dependency across iterations.
- Pre-allocate `a`, `b` as scratch arrays outside the loop and slice in-place — avoids two allocations per iteration.

**`implementation_shortfall_kernel` (Numba parallel)**

- `np.ceil` inside `prange` forces a float→int round-trip. Pre-cast `participation_cap` to float64 scalar before the kernel, move `ceil` to integer via `(int(participation) + int(participation_cap > 0) - 1) // 1` pattern or just `int(math.ceil(...))` — Numba compiles this to a single CPU instruction.
- The `6`-column output matrix is written column-by-column inside the loop; reordering to row-major writes improves cache locality since Numba defaults to C-contiguous arrays.

**`batched_forward_sums` (Numba parallel)**

- The prefix sum is computed sequentially before the parallel horizon loop — this is correct but the serial prefix pass dominates for long series. Switch to a Numba `parallel=True` prefix scan (Blelloch scan) or simply split: compute prefix once outside, then `prange` over both horizons AND time simultaneously with a 2D `prange`.
- Current `int(horizons[hidx])` cast inside `prange` creates a scalar load per thread — pre-cast `horizons` to `int64` before calling the kernel (already done in callers, but enforce with `astype(np.int64, copy=False)` at the call site).

**`vectorized_rolling_ic_matrix` (Numba parallel)**

- Inner loop recomputes `mx = np.mean(sx)` by summing `window` elements each time — O(W) per step. Convert to an incremental Welford mean update — O(1) per step — cutting total work from O(H·N·W) to O(H·N).
- The `if not np.isfinite(y).all()` check iterates the full window to check for NaN. Maintain a running NaN count instead, incrementing/decrementing as the window slides.

**`rolling_std_percentile_kernel` (Numba)**

- The inner `np.sort(valid)` re-sorts the entire history up to position `i` — this is O(i log i) per step, making the full kernel O(N² log N). Replace with an insertion-sort maintained sorted buffer of size `window` (O(W) per step) — same approach already used in `rolling_percentile_numba`, just apply it here too.
- The `np.searchsorted` on the sorted window array is O(log W) — already fine, keep it.

**`vectorized_mc_equity` (Numba parallel)**

- `seed_offsets` produces shifted-index block bootstrap — valid, but the `if j < 0 / j >= n` guards inside the hot loop are branch-misprediction hazards. Pre-clamp offsets at the call site with `np.clip(offsets, -(n-1), n-1)` so the guards are always false and the compiler can elide them.
- Each simulation writes a full equity path serially — fine, but if `n` is large, strip-mining the inner loop into cache-line-sized chunks (64 doubles = 512 bytes) improves prefetch behavior.

**`elastic_net_coordinate_descent` (Numba)**

- The outer `max_iter` loop is serial by design (coordinate descent has sequential dependencies per column), but the inner `np.dot(X[:, j], residual)` traverses a column of a C-contiguous array — this is stride-`n` access, cache-hostile. Transpose `X` to Fortran order (`np.asfortranarray`) before calling the kernel so column `j` is contiguous. This alone can be 3-5x faster for wide `X`.

**`tiled_dot_kernel` (Numba parallel)**

- This reimplements BLAS dgemm. Unless Numba's OpenMP backend is unavailable, just call `np.dot` (which dispatches to MKL/OpenBLAS) — it will be faster than any Python-level tiling for any matrix size above ~50×50. Remove this function and replace callers with `np.dot`.

**`welford_rolling` (Numba)**

- The inner `for j in range(start, i+1)` recomputes the running mean from scratch each step — O(W) per step. The Welford update is incremental by definition; implement a proper sliding-window Welford that adds the new element and removes the outgoing element. This drops complexity from O(N·W) to O(N).

**`rolling_corr_kernel` (Numba)**

- Same incremental mean issue as `vectorized_rolling_ic_matrix` — recomputes `mx`, `my` by summing the window each step. Sliding mean update cuts this from O(N·W) to O(N).

**`cusum_statistic` (Numba)**

- `np.nanmean` and `np.nanstd` over the full array are called once at the top — not a hot path, but these allocate. Pre-compute mean and std with a single pass using Welford before entering the loop.

**`rolling_percentile_numba` (Numba)**

- Insertion sort is O(W²) per step. For `W > 64`, a heap-based sliding quantile (e.g. two-heap median trick generalized to arbitrary percentile) is O(log W) per step. The crossover point is roughly `W = 50`; add a branch: insertion sort for `W ≤ 50`, heap for larger windows.

---

## `analytics.py` core functions

**`characteristic_panel`**

- The 5-minute TTL cache is good, but `load_fundamentals()` is called every cache miss and does a full read. Add a module-level `_FUND_CACHE` with its own TTL — fundamentals change at most daily.
- `returns.tail(252).std()` and `returns.tail(252).std() * sqrt(252)` are computed twice for `low_vol` and `realized_vol`. Compute once, store, reuse.
- The three vectorized momentum series (`mom_252`, `mom_21`, `mom_126`) each do array subtraction and division — already fast, but the `.map(dict)` call on `rows["Ticker"]` is a Python dict lookup per row. Use `pd.Series.reindex(rows["Ticker"])` instead — vectorized and avoids the dict-construction overhead.
- The `load_fundamentals()` call to get revenue growth is a full reload of the fundamentals parquet inside an already-loaded context. Cache this separately or compute growth at load time.

**`factor_returns`**

- The `_FR_CACHE` uses a string key but calls `load_factor_returns` and `load_aqr_factor_returns` on every miss, each of which reads from disk. Add a file-mtime check so stale cache entries are invalidated only when the underlying parquet changes — avoids unnecessary re-reads across requests.
- The `df.join(aqr, how="outer")` creates a new DataFrame. If `aqr` is empty (common path), the join is wasted — the `if not aqr.empty` guard is already there, good.

**`valuation_spread`**

- `_precomputed` deduplicates rolling sums per FF column (Fix #5) — correct. But `pd.qcut` + `rank(method="first")` inside the factor loop is O(N log N) per factor. For multiple factors sharing similar universe, precompute all ranks in a single vectorized pass: `chars[factors].rank(method="first", pct=True)`.
- The `sector` DataFrame construction with `pd.concat([top.groupby...])` creates two intermediate DataFrames per factor. Merge on sector index directly: `chars.groupby("sector")[f].agg(["mean"]).pipe(...)` in one call.
- `empirical_percentile(s.tail(lookback), s.iloc[-1])` calls `.tail()` which copies — use `s.iloc[-lookback:]` with a view where possible, or pre-slice `s` once.

**`sector_brinson_fachler`**

- `returns[names].mul(bench_w.reindex(names) / max(wb, 1e-12), axis=1).sum(axis=1)` is computed in a loop over sectors. This is O(sectors × N × T). Vectorize: pre-multiply the full return matrix by weights once, then sum per sector using `groupby` on the column axis — reduces to a single matrix multiply.
- `sort_values(["Ticker", "Date"])` is called on `prices` every invocation despite `price_sample` already being sorted. Remove the redundant sort.

**`covariance_payload`**

- The vectorized correlation path (Fix #7) uses `np.linalg.norm` which computes a full L2 norm. For the correlation formula, `(X.T @ X)` is already computed implicitly — reuse the diagonal of the covariance matrix via `np.sqrt(np.diag(cov_arr))` to avoid recomputing norms from scratch.
- `LedoitWolf().fit(x.values.astype(np.float32))` casts to float32 then sklearn internally upcasts to float64 — pointless copy. Pass `float64` directly.

**`ols_beta`**

- `np.linalg.lstsq` is called then the residuals are recomputed manually. `lstsq` already returns residuals as its third return value — use them directly instead of `Y - X @ coef`.

**`backtest_series`**

- Calls `implementation_shortfall` which calls `characteristic_panel` which has a 5-min TTL cache. If `backtest_series` is called in a tight loop across factors (e.g. Feature 6's `_crowding_league`), the panel is shared — already efficient. But `implementation_shortfall` calls `factor_returns` internally through `payload` — ensure the `_FR_CACHE` is warm before the loop to avoid repeated disk reads.

**`perf_stats`**

- The drawdown duration loop in pure Python (`for flag in in_dd.to_numpy`) is O(N) with Python overhead. Vectorize with `np.diff` on the boolean array to find run-length segments: `starts = np.where(np.diff(np.concatenate([[0], mask, [0]])) == 1)` — avoids the Python loop entirely.

**`compact_series`**

- `np.linspace(...).astype(int)` for downsampling computes float then truncates — use `np.round(...).astype(int)` to avoid systematic bias toward early points, and cast with `copy=False`.

**`matrix_records`**

- `float(v)` inside the list comprehension calls Python's `float()` on each numpy scalar — 3-5x slower than `v.item()`. Replace `float(v)` with `v.item()` and `np.isfinite(float(v))` with `np.isfinite(v)`.

---

## Feature module hot paths

**Feature 01 (`valuation_spread` monitor)**

- `_crisis_anchor_percentiles` iterates over `series.columns × CRISIS_ANCHORS` with `pd.to_numeric` + `.dropna()` + slice inside a double loop. Pre-convert the entire series to numeric once before the loops.
- The `s.loc[:used_date]` slice on a DatetimeIndex uses label-based lookup — faster with `s.truncate(after=used_date)` which uses binary search directly.

**Feature 02 (exposure decomposition)**

- `_rolling_exposure_snapshots` uses a deterministic drift proxy and deep-copies each `heatmap` row per month (12 × N dicts). This is for display only — generate it lazily or cap at 6 months in realtime mode. The `np.sin` call per ticker per month is negligible but the dict copy is O(N × 12).
- `_tracking_error_budget` calls `covariance_payload` which is already cached if called in the same request cycle — check if `_FR_CACHE` sharing covers this.

**Feature 04 (regime)**

- `GaussianHMM.fit(obs.values)` where `obs` is a 21-day rolling mean — hmmlearn does not use BLAS for small `n_components`. Cache the fitted HMM for 1 hour keyed on the data hash; the model parameters change slowly.
- `_factor_timing_regression` calls `np.linalg.lstsq` in a `factors × signals` double loop — this is O(F·S·N) OLS. Batch all signals into a single multi-output regression: `np.linalg.lstsq(X, Y_matrix)` where `Y_matrix` stacks all forward-return targets column-wise.
- `_factor_seasonality` calls `rets.groupby(rets.index.month)` which creates 12 groups each traversed per factor. Pivot to a `(month, factor)` groupby once and vectorize the mean.

**Feature 05 (alpha decay)**

- `_cross_sector_decay` calls `characteristic_panel` again with a higher `max_tickers` inside a function that is already downstream of a panel call. The TTL cache may return the lower-universe result. Add explicit `max_tickers` keying to `_CHAR_PANEL_CACHE`.
- `_multi_factor_power_radar` calls `backtest_series` per factor in a serial loop — these are independent. If `compute_mode == "research"` and the threading layer is safe, this is a `ThreadPoolExecutor` candidate (same caveat as Feature 14 about Numba's workqueue backend).

**Feature 06 (crowding)**

- `_crowding_league` calls `valuation_spread` + `backtest_series` per factor in a serial loop over 12 factors — each call hits `characteristic_panel` (cached) and `factor_returns` (cached) but still does per-factor `rolling_std_percentile_kernel` calls. Batch: compute the crowding path for all factors simultaneously by stacking their return series and running the kernel once over the matrix.
- `_bid_ask_spread_proxy` calls `_roll_spread` and `_amihud_illiquidity` per ticker in a dict comprehension — these are serial per-column pandas operations. Vectorize: compute `pct_change` for the entire close matrix at once, then compute the Roll covariance matrix via `np.einsum` across the long/short book simultaneously.
- `_bayesian_crash_table` iterates over 3 horizons with `.quantile` and boolean masking per horizon — negligible, but the `aligned["crowd"] >= lower` mask is recomputed 3 times on the same DataFrame. Pre-filter once.

**Feature 07 (backtesting)**

- `_real_quintile_monotonicity` calls `price_sample` (cached) and then does `close.pct_change(rebalance_days).shift(-rebalance_days)` on the full tail — this is O(N_tickers × window_days). The result should be cached per `(factor, rebalance_days, window_days)` key since it's purely data-driven.
- `vectorized_mc_equity` with 250 sims × `len(net)` steps — already fast with Numba parallel, but the `seed_offsets` array allocation inside `run()` uses `rng.integers(-5, 6)` which creates a Python RNG. Pre-generate offsets at module load time for the default seed.

**Feature 08 (covariance)**

- `_crisis_preset_comparison` calls `.corr()` on up to 4 time windows of `rets` — each `.corr()` is O(N²·T). The vectorized correlation path in `covariance_payload` is already faster; call it instead of raw `.corr()`. Or pre-slice all preset windows before the loop and compute correlations in a single batched operation.
- `_rolling_pair_correlation` uses pandas `.rolling().corr()` which is Python-slow for long series. Replace with the Numba `rolling_corr_kernel` already in `performance.py`.

**Feature 09 (capacity)**

- `_capacity_curve_piecewise` loops over `aums` in Python — this is O(N_aum) with numpy-heavy operations per iteration. Vectorize entirely: split `aum_arr` into two boolean-masked subarrays (Kyle vs Almgren) and compute both in one numpy broadcast each.

**Feature 10 (optimizer)**

- CVXPY problem construction (`cp.Variable`, `cp.quad_form`, constraint building) has ~10-50ms of Python overhead per solve regardless of problem size. Cache the compiled CVXPY problem object (not just the weights) keyed on `(factor_names_tuple, long_short, robust)` — warm start then only updates parameters. This requires CVXPY's parameter interface (`cp.Parameter`), which allows changing `mu` and `cov_values` without rebuilding the problem.
- `_efficient_frontier` solves 25 separate CVXPY problems serially — each independent. If CVXPY's solver (OSQP) supports batched warm starts, use them. Otherwise this is another `ThreadPoolExecutor` candidate if the threading layer is safe.
- `_black_litterman_factor` calls `np.linalg.pinv` twice — these are O(N³). For small factor count (N ≤ 15), `np.linalg.solve` on the structured system is 10x faster and numerically equivalent.

**Feature 11 (stress testing)**

- `_historical_analog_search` computes `np.linalg.pinv(cov)` once (good), then iterates over `(len(rets) - 21)` windows computing Mahalanobis distance in a Python loop. Vectorize: stack all 21-day windows into a matrix with `sliding_window_view`, compute all sums at once, then batch the Mahalanobis computation as `(W - target) @ inv @ (W - target).T` diagonalized — reduces from O(N·K²) Python-loop to one matrix multiply.
- `_bootstrap_irf_ci` fits one base VAR then uses a fixed-design residual bootstrap with covariance scaling — already avoiding per-sample VAR refits. The remaining bottleneck is the `rng.integers(0, len(resid), size=(samples, len(resid)))` bootstrap index matrix, which allocates O(samples × T) integers. Pre-allocate this once and reuse across calls with a deterministic seed.
- VAR `select_order` calls `VAR(var_data).select_order(maxlags=...)` which fits multiple models — expensive. Cache the selected lag per data-hash with a 1-hour TTL.

**Feature 12 (DNA)**

- `_get_classifier` is module-level cached — good. But `run_feature_module(5, 6, 8, 4, ...)` calls 4 upstream features sequentially. These are independent — prime `ThreadPoolExecutor` candidate (same Numba-thread caveat).
- `_sector_dna_snapshot` calls `characteristic_panel` again — already cached, but the `groupby("sector").sum()` + normalization is recomputed on every Feature 12 call. Cache the sector weight breakdown alongside the panel.

**Feature 13 (monitoring)**

- `_run_multi_factor` loops over up to 25 factors calling `run(sub_payload)` serially — each `run()` call re-executes `backtest_series` → `rolling_corr_kernel` → CUSUM. With a warm `_FR_CACHE` and `_CHAR_PANEL_CACHE`, the bottleneck is the Numba kernels. This loop is the single largest throughput opportunity in the whole codebase — parallelize with `ThreadPoolExecutor` bounded at 4 workers (conservative for Numba workqueue safety) or pre-batch all factor return arrays and run a single vectorized CUSUM across all factors simultaneously.
- `_weekly_chow_proxy` recomputes `s.var(ddof=2)` and `left.mean()`, `right.mean()` — these share the same data. Compute all moments in one pass.

**Feature 14 (report)**

- The `parallel_report_sections` path is already there but disabled by default due to Numba workqueue. A safe alternative: pre-warm all upstream `_FR_CACHE` and `_CHAR_PANEL_CACHE` entries in a single serial pass before forking threads — the parallel threads then only touch cached data and never trigger Numba compilation, making threading safe.
- `_SECTION_FRAGMENT_CACHE` is unbounded — cap it at 128 entries with an `OrderedDict`-based LRU to prevent memory growth in long-running servers.
- `_render_pdf` uses ReportLab's `SimpleDocTemplate.build()` which is synchronous and CPU-bound. For the async/deferred path, offload to a `ProcessPoolExecutor` (not thread — PDF rendering is pure CPU with no shared Numba state).

---

## Cross-cutting

- **Numba compilation stall**: `_prewarm_kernels()` covers most kernels but misses `vectorized_mc_equity`, `tiled_dot_kernel`, `implementation_shortfall_kernel`, and `dcc_recursion_kernel`. Add dummy calls for all of them at module import time.
- **`clean_json`**: Called on the entire response dict recursively. The `pd.isna(value)` try/except is a slow path for any non-scalar. Add an explicit `isinstance(value, (np.ndarray, pd.Series, pd.DataFrame))` fast-reject before the try/except.
- **`stable_cache_key`**: `json.dumps` with `default=str` serializes the full payload on every call. For hot paths (called per-feature per-request), memoize on the payload's `id()` if the dict is not mutated, or compute a faster hash using `xxhash` or `hashlib.blake2b` instead of SHA-256.
- **`governance_metadata`**: Calls `datetime.utcnow().isoformat()` on every response — trivial individually but called once per feature. Cache the timestamp at request-start time and pass it through, or round to the nearest second to share across features in the same request.
- **Numba `cache=True`**: All kernels have it — good. Ensure the cache directory is on a fast local filesystem (not NFS) and that the Numba cache is pre-populated in the Docker image build step, not at first request.
- **`_ARRAY_CACHE` and `_SCRATCH_CACHE`**: Both use simple Python dicts. For multi-process deployments (gunicorn with workers), these caches are not shared — each worker warms independently. Consider a Redis-backed shared cache for `_FR_CACHE` and `_CHAR_PANEL_CACHE` (the two most expensive) using pickle serialization.

Yes, a lot more. Going deep:

---

## Memory layout and allocation

**Avoid DataFrame entirely in hot paths**
`characteristic_panel` builds and returns a full pandas DataFrame that every feature immediately converts back to numpy arrays. The DataFrame is just a named numpy array with overhead. For the z-score block, characteristic exposures, and return arrays that feed Numba kernels, maintain a parallel `np.ndarray` representation alongside the DataFrame — features that only need numerical computation skip the DataFrame entirely.

**Contiguous memory for all factor return matrices**
`factor_returns` returns a DataFrame whose underlying numpy blocks may be non-contiguous if columns were joined from different sources (`df.join(aqr)`). After joining, call `df = pd.DataFrame(np.ascontiguousarray(df.values), index=df.index, columns=df.columns)` once and cache that. Every downstream `.values` call then gets a zero-copy contiguous view instead of triggering a copy.

**Pre-allocate output buffers at module load**
For fixed-shape outputs like the MC equity matrix (250 × N), the covariance upper triangle, and the rolling IC matrix, pre-allocate the output arrays at module load time using `scratch_array`. Numba kernels that write into pre-allocated buffers skip the `np.empty` call inside the kernel — the allocator overhead is real at high request rates.

**`np.empty` vs `np.zeros`**
Several kernels initialize with `out[:] = np.nan` immediately after `np.empty` — this is correct but writes the array twice. Use `np.full(shape, np.nan)` instead which writes once.

**Memory pools with `memoryview`**
For the rolling window operations that repeatedly slice subarrays (rolling IC, rolling correlation, rolling OLS), wrap the source array in a `memoryview` before the Numba call. Numba accepts memoryviews as typed arrays with zero-copy semantics and avoids the Python buffer protocol overhead per slice.

---

## NumPy-specific

**`np.einsum` path selection**
`batch_covariance_upper` uses `optimize=True` which lets numpy choose the contraction path at runtime. For a fixed array shape (which you have — factor count is known at startup), pre-compute the optimal path once with `np.einsum_path` and pass the explicit path string on subsequent calls. This eliminates the path-optimization overhead on every call.

**Structured arrays for row-oriented data**
The `heatmap`, `rows`, and other list-of-dict outputs that flow through `matrix_records`, `compact_series`, and `clean_json` are Python lists of Python dicts — slow to construct and iterate. For internal computation, keep these as numpy structured arrays (`np.dtype([('row', 'U32'), ('column', 'U32'), ('value', 'f4')])`). Convert to list-of-dicts only at the final `response()` boundary.

**`np.searchsorted` for percentile queries**
`empirical_percentile` uses `(hist < value).mean()` — a full O(N) comparison. If `hist` is pre-sorted (which it can be, since it's a rolling historical series), `np.searchsorted(sorted_hist, value) / len(sorted_hist)` is O(log N). Sort once, cache the sorted array alongside the series.

**Avoid `np.where` with large boolean masks**
`_stock_level_divergence` uses `np.where(surprise > 0.5, ...)` on a large array. For sparse outputs (most values are "neutral"), use `np.nonzero` to find only the interesting indices and operate only on those — avoids materializing the full output array.

**`np.lib.stride_tricks.as_strided` for rolling windows**
Beyond `sliding_window_view`, for the specific case of rolling 21-day sums in `batched_forward_sums`, use `as_strided` with a precomputed prefix sum array — the strided view gives O(1) per window sum versus O(W) even with prefix sums in Numba, because the strided view avoids copying window data.

---

## Numba-specific

**AOT compilation with `numba.pycc`**
The eight core kernels (`rolling_autocorr_1`, `batched_forward_sums`, `vectorized_rolling_ic_matrix`, `rolling_std_percentile_kernel`, `vectorized_mc_equity`, `cusum_statistic`, `elastic_net_coordinate_descent`, `rolling_corr_kernel`) are stable. Compile them ahead-of-time with `numba.pycc` into a shared library and import as a regular C extension. This eliminates the JIT compilation path entirely and removes the Numba dependency from the hot path — the compiled `.so` loads like any other Python module.

**`fastmath=True` implications**
All kernels have `fastmath=True` which enables reassociation and FMA. Be explicit about what this enables: for the correlation kernels, `fastmath` allows FMA on the inner dot products which is a genuine speedup. For the percentile kernel's sort, `fastmath` has no effect — remove it from `rolling_percentile_numba` to reduce the compiled code footprint.

**`numba.typed.List` and `numba.typed.Dict`**
Any Numba-JIT function that receives Python lists or dicts incurs boxing/unboxing overhead. The `_sector_dna_snapshot` and `_crowding_league` functions pass lists of factor names into Numba-adjacent code. Pre-convert factor name lookups to integer indices and use `numba.typed.Dict` for the mapping — integer key lookups in Numba are O(1) with zero boxing.

**`@numba.njit` with explicit type signatures**
Numba compiles a new specialization for each type signature it sees. Several kernels are called with both `float32` and `float64` inputs depending on upstream casts. Pin the signature explicitly: `@njit("float64[:](float64[:], int64)")` for the most common path — eliminates the dispatch overhead and reduces cache size.

**Numba threading layer**
The default `workqueue` threading backend is the source of the multi-thread unsafety mentioned for Feature 14. Switch to the TBB backend (`NUMBA_THREADING_LAYER=tbb` environment variable, with `tbb` installed) — TBB is fork-safe and reentrant, which both enables safe `ThreadPoolExecutor` parallelism and improves `prange` performance by 20-40% on NUMA systems.

**`@numba.extending.overload` for numpy functions inside kernels**
`np.nanmean` and `np.nanstd` inside Numba kernels fall back to the object mode implementation when the array contains NaNs. Implement custom Numba-native nan-aware mean/std using `overload` — these are 3-5x faster than the object-mode fallback for the rolling windows used here.

---

## SciPy and sklearn

**`LedoitWolf` with pre-whitened data**
`LedoitWolf().fit(x.values)` runs sklearn's shrinkage estimator on raw returns. Pre-whiten (demean) the data with `x -= x.mean()` before fitting — sklearn does this internally but allocates a copy. Pass pre-demeaned data and set `assume_centered=True` to skip sklearn's internal centering copy.

**`scipy.optimize.curve_fit` in Feature 05**
`_fit_decay` calls `curve_fit` three times per factor. `curve_fit` uses Levenberg-Marquardt by default — for these simple 2-parameter exponential and hyperbolic fits, Newton's method with analytical Jacobians converges in 3-5 iterations and is 10-50x faster than LM with numerical Jacobians. Provide the analytical `jac` argument: for `a·exp(-b·h)`, `jac = [exp(-b·h), -a·h·exp(-b·h)]`.

**`VAR.select_order` in Feature 11**
`statsmodels.tsa.api.VAR.select_order` fits up to `maxlags` separate VAR models — O(maxlags × N³ × T). Replace with a single VAR fit at `maxlags` and compute AIC/BIC from the log-likelihood analytically — one fit instead of N fits.

**`GaussianHMM` from hmmlearn**
hmmlearn's `fit` uses the Baum-Welch EM algorithm in pure Python/Cython. For 3-state diagonal-covariance HMM on a factor return stream (typically 1260 × 5), `pomegranate` (GPU-optional, PyTorch-backed) or `dynamax` (JAX-backed) are 10-100x faster. If neither is available, pre-warm the HMM with `init_params=""` and set `params="mc"` (only update means and covariances, not transition matrix) after the first fit — reduces EM iterations significantly for stable regimes.

---

## Polars

Replacing pandas in the high-frequency call paths gives the largest single-library speedup available without rewriting to C. The specific targets:

**`characteristic_panel`** — the entire function is one large pandas pipeline. Rewrite as a Polars LazyFrame: `pl.scan_parquet("market_universe")`, join with fundamentals, compute z-scores with `pl.col(...).rank().sub(mean).div(std)` in a single `with_columns` pass. Polars executes the full pipeline in parallel across columns using its query optimizer and Rayon thread pool. Expected speedup: 5-15x for the panel construction.

**`sector_brinson_fachler`** — the `groupby` + `mul` + `sum` pattern repeated per sector is exactly what Polars' group-by aggregation is optimized for. The entire sector loop becomes a single `group_by("sector").agg(...)` expression.

**`_crowding_league` and `_running_multi_factor` loops** — any function that iterates over factors and applies the same pandas operations can be vectorized in Polars by stacking factor columns and using horizontal expressions.

**Polars-Numba bridge** — Polars Series expose a zero-copy `to_numpy(allow_copy=False)` that returns a numpy array sharing the underlying Arrow buffer. This means Polars for data wrangling → zero-copy handoff to Numba kernels → Polars for output formatting, with no intermediate copies.

---

## CuPy / GPU paths

**Covariance matrix computation**
`LedoitWolf` and `fast_covariance_matrix` are O(N²·T) matrix operations — ideal for GPU. For the `characteristic_panel` path with 5000 tickers and 252 days, `cupy.cov` on a V100 is ~50x faster than numpy on CPU. The Ledoit-Wolf shrinkage formula can be implemented in CuPy directly: `shrinkage * identity + (1 - shrinkage) * sample_cov`, both trivially GPU-vectorized.

**Monte Carlo equity paths**
`vectorized_mc_equity` with 500 simulations × 2520 steps is a matrix operation — each simulation is an independent cumulative product. Replace the Numba kernel with `cupy.cumprod(1 + returns[offsets], axis=1)` on a `(sims, T)` GPU matrix. The GPU parallelism across 500 independent paths is perfect.

**Rolling IC matrix**
`vectorized_rolling_ic_matrix` with `H` horizons × `N` time steps × `W` window elements is a 3D reduction — maps directly to a GPU kernel. `cupy.lib.stride_tricks.sliding_window_view` + `cupy.corrcoef` over the window axis computes all horizons simultaneously.

**When GPU is not available**
Use `cupy` with a CPU fallback via `import cupy as cp` wrapped in a try/except that falls back to numpy — the API is identical for the operations above.

---

## JAX

**`jax_covariance_batch` is already there but underused**
The function exists but is only called in one place. Expand its use to `_crisis_preset_comparison` (4 covariance computations), `_cross_sector_decay` (per-sector covariance adjustments), and Feature 08's normal/crisis split covariances.

**`jax.vmap` for per-horizon IC**
`vectorized_rolling_ic_matrix` computes the same rolling correlation operation independently for each horizon. In JAX: define the single-horizon rolling IC as a function, then `jax.vmap` over the horizon axis — JAX compiles a single XLA kernel that runs all horizons in parallel on CPU or GPU.

**`jax.jit` + `jax.lax.scan` for rolling operations**
The rolling Welford, rolling autocorrelation, and rolling OLS kernels are all sequential scans — exactly what `jax.lax.scan` is designed for. `lax.scan` compiles the loop body to XLA, enabling fusion with the upstream computation and eliminating Python-loop overhead entirely. The carry state is the running mean/variance, the scanned element is the new observation.

**`jax.grad` for analytical Jacobians**
The `curve_fit` calls in Feature 05 need analytical Jacobians for speed. Instead of deriving them manually, define the decay models as JAX functions and use `jax.grad` or `jax.jacobian` — JAX auto-differentiates through `a * jnp.exp(-b * h)` exactly, generating the analytical Jacobian without manual derivation.

---

## Caching infrastructure

**`functools.cached_property` for per-request computed values**
For values computed once per request from the same payload (factor name normalization, universe selection, characteristic ranks), wrap them in `cached_property` on a request-scoped object rather than recomputing in each feature module function call.

**`diskcache` for medium-TTL results**
`_CHAR_PANEL_CACHE`, `_FR_CACHE`, and the HMM model cache are in-process. For multi-worker deployments, `diskcache` provides a thread-safe, process-safe disk cache with automatic TTL expiration, compression, and eviction — replacing the hand-rolled dict caches with a single unified store. It uses memory-mapped files so repeated reads within a process are zero-copy.

**`joblib.Memory` for expensive function memoization**
`VAR.select_order`, `GaussianHMM.fit`, `LedoitWolf.fit`, and `_academic_archetype_library` are all pure functions of their inputs. Wrapping them with `joblib.Memory` provides automatic persistent disk caching with input hashing — no manual cache key construction needed.

**Request-scoped cache context**
Every feature module independently calls `characteristic_panel`, `factor_returns`, `backtest_series` etc. In a single request that triggers Feature 14 (which calls 7 upstream features), these functions are called up to 7 times — the module-level caches handle most of this, but there's still 7× the function call overhead. Introduce a request-scoped context object that pre-computes all shared inputs once and passes them as arguments, eliminating even the cache lookup overhead.

---

## Concurrency architecture

**`asyncio` with `loop.run_in_executor`**
The API endpoint is presumably async (FastAPI or similar). All the CPU-bound work currently blocks the event loop. Move each feature module `run()` call into `loop.run_in_executor(process_pool, run, payload)` — this parallelizes across CPU cores without Numba threading issues since each process has its own Numba state.

**`ProcessPoolExecutor` with pre-warmed workers**
Use `initializer=_prewarm_kernels` in the `ProcessPoolExecutor` constructor — each worker process runs `_prewarm_kernels()` at startup, pre-loading the Numba cache. First-request latency drops from ~2s (JIT compilation) to ~50ms (cache load).

**`concurrent.futures.as_completed` with timeout**
Feature 14's sequential upstream calls have no timeout. A single slow upstream feature (e.g. VAR fitting) blocks the entire report. Add per-feature timeout via `executor.submit(...).result(timeout=5.0)` — degrade gracefully to the cached or fallback result rather than blocking.

**Batch request coalescing**
If multiple concurrent requests ask for the same factor/payload combination (common in dashboard polling), coalesce them at the API layer using a `asyncio.Lock` per cache key — the first request computes, subsequent identical requests wait and receive the same result. This is the "thundering herd" problem for the expensive `characteristic_panel` and `GaussianHMM.fit` paths.

---

## Algorithmic

**Incremental updates instead of full recomputation**
`characteristic_panel` recomputes the full universe from scratch every 5 minutes. For most tickers, nothing changes between calls — only prices update. Maintain an incremental update buffer: store the previous panel, then only recompute the rows for tickers whose price has changed since the last call. For a 5000-ticker universe with ~500 intraday price updates, this reduces the computation by 90%.

**Approximate nearest neighbor for `_historical_analog_search`**
Feature 11 computes exact Mahalanobis distance to every 21-day window in history — O(T·K²) where K is the factor count. For large `T`, use `faiss` (Facebook AI Similarity Search) with a flat L2 index after applying the Cholesky factor of the inverse covariance as a whitening transform — exact nearest neighbor in the whitened space equals exact Mahalanobis neighbor, but `faiss` uses SIMD-optimized inner product search and is 10-100x faster for `T > 1000`.

**Low-rank covariance approximation**
The factor covariance matrix has at most 10-15 factors, but `ledoit_wolf` operates on the full sample covariance. For the stress testing and portfolio optimization paths, represent the covariance as `L @ L.T + D` (Cholesky + diagonal) — quadratic forms `w @ Σ @ w` then compute as `||L.T @ w||² + w.T @ D @ w`, which is O(K²) instead of O(K²) but with a 3-5x smaller constant due to cache-friendly triangular access.

**Randomized SVD for PCA in regime detection**
Feature 04's GMM operates on covariance upper-triangle vectors — high-dimensional for large factor sets. Pre-project with `sklearn.utils.extmath.randomized_svd` (or `torch.linalg.svd` with `full_matrices=False`) to reduce dimension from `K*(K+1)/2` to 3-5 principal components before GMM fitting — reduces GMM fitting time from O(N·K²) to O(N·d²) where d=5.

**Sparse factor exposure matrix**
In Feature 02, most tickers have zero exposure to most factors after the mandate filter. Represent `merged[z_cols]` as a `scipy.sparse.csr_matrix` — the portfolio exposure dot products `(merged["weight"] * merged[zcol].fillna(0)).sum()` become sparse matrix-vector products, which are faster when sparsity > 50%.

**FFTW-based autocorrelation**
`rolling_autocorr_1` computes lag-1 autocorrelation in a sliding window via direct O(W) correlation per step. For large windows, compute autocorrelation via FFT: `np.fft.rfft` on the full series, multiply by its conjugate, `np.fft.irfft` — O(N log N) for all lags simultaneously. Extract lag-1 from the output, then use a sliding window on the autocorrelation result. The crossover point is roughly W > 200.

---

## Serialization and I/O

**Parquet with column pruning**
`load_market_universe()`, `load_fundamentals()`, `load_aqr_factor_returns()` presumably read full parquet files. Pass `columns=[...]` to `pd.read_parquet` or `pl.scan_parquet(...).select(...)` — parquet's columnar format means unneeded columns are never read from disk.

**Arrow IPC for inter-process cache sharing**
Instead of pickling DataFrames across processes (which copies memory), serialize to Apache Arrow IPC format in shared memory using `pyarrow.plasma` or `multiprocessing.shared_memory`. Workers read the Arrow buffer zero-copy using `pyarrow.ipc.read_message` — a 5000-row characteristic panel that takes 50ms to pickle takes 0.5ms to share via Arrow IPC.

**`orjson` for response serialization**
`clean_json` + Python's `json.dumps` is the final step before sending the API response. `orjson` serializes numpy arrays, pandas Timestamps, and Python dicts 10-50x faster than the standard library and handles `np.float32` natively without the `float(v)` conversion overhead.

**Memory-mapped parquet with `mmap_mode`**
For the market universe parquet that is read on every cold start, open it with `np.load(..., mmap_mode='r')` (for numpy format) or `pa.memory_map(...)` (for Arrow format) — the OS page cache handles physical I/O and multiple processes share the same physical memory pages.

---

## Profiling to prioritize

Before implementing any of the above, instrument with:

- **`py-spy`** (sampling profiler, zero overhead, works on running processes) — identifies which functions consume wall time in production
- **`memray`** — identifies allocation hot spots; the biggest wins above come from eliminating allocations in hot loops
- **`perf stat -e cache-misses,cache-references`** on the Numba kernels — confirms whether the cache-locality changes to `elastic_net` and `implementation_shortfall_kernel` are actually hitting the predicted bottleneck
- **`numba --annotate-html`** on each kernel — shows which lines are in object mode vs nopython mode; any object-mode line is a 100x slowdown opportunity

The highest-leverage items in order, based on the code as written: Polars for `characteristic_panel`, incremental panel updates, `orjson` for serialization, pre-allocated output buffers in Numba kernels, and batching the `_crowding_league` / `_run_multi_factor` factor loops.
