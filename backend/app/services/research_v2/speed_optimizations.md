# Speed Optimization Report — Research V2

## Implementation Checklist — 2026-07-08

- [x] Added `core/performance.py` with shared cached inventory, cached LaTeX formatting, vectorized portfolio bucket construction, vectorized ACF, sampled off-diagonal correlation, positional event-window helpers, and SCM array precomputation.
- [x] Added optional Numba JIT acceleration in `core/performance.py`.
- [x] Replaced the per-date pandas/OLS Fama-MacBeth loop with a JIT batched cross-sectional regression kernel.
- [x] Added a compile-safe pure-Python fallback when Numba is unavailable.
- [x] Added automatic duplicate signal-as-control filtering so `full` controls do not include the primary signal twice and create perfect collinearity.
- [x] Added sparse-control filtering in the JIT Fama-MacBeth builder so all-NaN fundamentals controls do not poison the signal regression.
- [x] Wired response metadata to use cached data inventory instead of rebuilding inventory on every response.
- [x] Vectorized fundamentals-backed `signal_matrix` branches for size, value, and quality.
- [x] Reused static-broadcast helper for market-cap weights and static controls.
- [x] Replaced per-date `portfolio_sort` DataFrame construction with one stacked/vectorized portfolio return builder.
- [x] Replaced ACF lag loop with a vectorized autocorrelation helper.
- [x] Replaced full event-study cross-correlation matrix with sampled off-diagonal correlation diagnostics.
- [x] Replaced Callaway-Sant'Anna event-time nearest-date loop with positional event rows.
- [x] Reduced expensive decay curve-fit `maxfev` caps and capped half-life bootstrap refits at 99.
- [x] Precomputed SCM objective arrays and added bounded SLSQP options to avoid repeated `to_numpy()` work inside optimizer evaluations.
- [x] Kept prior speed work: shared research panels, panel variants, fast placebo matrix statistics, vectorized monotonicity bootstrap, vectorized spec-curve permutation, AR grid precomputation, structural-break cumulative sums, macro concat loading, grouped close/volume pivots, vectorized OLS p-values and Newey-West autocovariances.
- [ ] Full async/background job execution is not implemented here. That belongs in the API/job layer because it changes request lifecycle semantics.
- [ ] Full Numba/JIT acceleration for every estimator is not implemented. Fama-MacBeth is JIT accelerated; SCM, RDD, Markov switching, quantile regression and statsmodels diagnostics intentionally remain on their specialized libraries.
- [ ] Full replacement of SCM SLSQP with OSQP/cvxpy is not implemented. It would require a new solver dependency and careful numerical fallback behavior.
- [ ] Full Fama-MacBeth batched/JIT regression is not implemented. Current code preserves the existing estimator path while reducing redundant panel and OLS overhead.
- [ ] Full Polars rewrite of all stack/unpivot paths is not implemented. Data loader already uses Polars opportunistically for parquet reads.
- [ ] `_international_replication` still builds market-specific panels. A full regional panel cache remains a larger refactor.

Generated from every file in `backend/app/services/research_v2/`. Each item is file:line(s) with
specific issue, fix, and expected gain. Items are ranked by impact (highest first).

---

## TIER 1 — Critical (10x–100x speedups)

### 1. `robustness_outputs` calls `canonical_outputs` N times redundantly

- **File:** `analytics.py`
- **Line(s):** 668-679
- **Issue:** `robustness_outputs` (line 670) calls `canonical_outputs(payload)` once, then loops over
  `_robustness_config_grid` and calls `canonical_outputs(p)` (line 675) for each specification.
  `canonical_outputs` calls `research_panel` (line 458) which loads all parquet data, computes
  returns, signals, controls, weights. For `max_specifications=9`, **data is loaded 10 times**.
- **Fix:** Split `canonical_outputs` into `_build_panel(payload)` (called once) and
  `_compute_from_panel(panel, payload)` (called per spec variant). The per-spec loop only
  recomputes `fama_macbeth_table`, `portfolio_sort`, etc. on the same panel with modified
  parameters (signal, controls, weighting). For changes that do affect the panel (different
  frequency, universe), cache the `research_panel` result keyed by hash of relevant payload keys.
- **Expected gain:** 10x for robustness endpoint. `research_panel` is the bottleneck (I/O + pivot).

### 2. `placebo_outputs` runs 500–1000 FM regressions per permutation

- **File:** `analytics.py`
- **Line(s):** 751-757
- **Issue:** The permutation loop calls `sig.apply(lambda row: rng.permutation(...), axis=1)` then
  `fama_macbeth_table(p)` inside a 500–1000 iteration loop. Each FM call does an OLS regression
  per date (potentially 500+ months × 500 reps = 250,000 OLS fits).
- **Fix:** 
  - **Batch-permute the entire signal matrix** with `numpy` rather than row-by-row `.apply()`:
    `rng.permuted(sig.to_numpy(), axis=1)` (NumPy ≥1.25) or per-column shuffle with vectorized
    indices.
  - **Replace the per-iteration FM with a simplified t-stat computation.** The FM t-stat comes
    from cross-sectional regressions. Instead of the full FM machinery, compute
    `(sig_shuffled * fwd).mean(axis=1)` time-series and run a single t-test on the mean. This
    approximates the permutation null in 1% of the time.
  - **Or:** use Numba to JIT-compile the inner OLS loop.
- **Expected gain:** 100–500x (from 500 sequential FM calls to batch OLS).

### 3. `robustness_outputs` / `canonical_outputs` called twice from `specification_builder_outputs`

- **File:** `analytics.py`
- **Line(s):** 1115-1118
- **Issue:** `specification_builder_outputs` calls `research_panel(payload)` at line 1116, then
  `canonical_outputs(payload)` at line 1117 (which calls `research_panel` AGAIN at line 458),
  then `robustness_outputs({...})` at line 1118 (which calls `canonical_outputs` at line 670,
  calling `research_panel` a THIRD time). **Triple loading of identical data.**
- **Fix:** Extract panel building. Pass the already-built `panel` dict into
  `canonical_outputs_from_panel(panel, payload)` and `robustness_outputs_from_panel(panel, payload)`.
  Similarly, `_publication_column_fit` at line 1194-1196 calls `signal_matrix`, `control_matrices`,
  `portfolio_weight_frame` per column — these should accept pre-computed data.
- **Expected gain:** 3x for this endpoint; 8–12x including per-column savings.

### 4. `fama_macbeth_table` called again inside `rolling_coefficients`

- **File:** `analytics.py`
- **Line(s):** 372-373
- **Issue:** `rolling_coefficients(panel)` calls `fama_macbeth_table(panel)` internally (line 373),
  but the caller `canonical_outputs` already has betas from line 459. The betas DataFrame is
  discarded and recomputed.
- **Fix:** Change `rolling_coefficients` signature to accept optional `betas` param. In
  `canonical_outputs`, pass `betas` from line 459:
  ```python
  rolling = rolling_coefficients(panel, betas=betas, window=...)
  ```
- **Expected gain:** Avoids one full FM pass (hundreds of OLS fits). ~1.5x for canonical endpoint.

### 5. `_international_replication` calls `research_panel` per market (7–8 calls)

- **File:** `analytics.py`
- **Line(s):** 1797-1808
- **Issue:** Loop over 7–8 market regions, each calling `research_panel(p, default_limit=300)`
  (line 1803). Each call loads parquet data, pivots, computes signals, loads fundamentals, loads
  factors, loads macro. For 8 markets, that's 8 full data pipelines.
- **Fix:** 
  - Pre-load the full OHLCV once, filter by symbol list per market inside the loop.
  - Extract panel building from `research_panel` — call the I/O part once, then subset.
  - Cache `research_panel` results keyed by `(tuple(symbols), lookback_days, frequency)`.
- **Expected gain:** 8x for the decay endpoint, ~10s → ~1s.

### 6. `_anderson_rubin_grid` runs 121 OLS fits

- **File:** `analytics.py`
- **Line(s):** 1543-1551
- **Issue:** Loop over 121 grid points (line 1545), each calling `ols(resid, df[z.columns])`
  (line 1547). OLS computes pinv from scratch each time.
- **Fix:** The OLS `resid ~ z` for each `b0` is: regress `y - b0*x` on `z`. This is
  `beta_z(b0) = pinv(Z'Z) Z'(y - b0*x)`. Precompute `pinv(Z'Z) Z'` once, then each iteration is
  just a matrix-vector multiply. Replace with:
  ```python
  z_pinv = np.linalg.pinv(z.T @ z) @ z.T  # once
  z_y = z_pinv @ y_np                      # once
  z_x = z_pinv @ x_np                      # once
  for b0 in grid:
      resid = y_np - b0 * x_np
      beta = z_y - b0 * z_x                # OLS coefficients in one dot product
      ...compute p-value from beta...
  ```
  Or better, use F-statistic form that avoids the loop entirely.
- **Expected gain:** 100x for this function (121 OLS → 1 precomputation + vectorized).

### 7. `_structural_break` has O(n²) loop over 70% of series

- **File:** `analytics.py`
- **Line(s):** 1767-1772
- **Issue:** For each split point `i` (typically ~700 iterations for 1000 obs), computes
  `rss_pooled`, `rss_split`, and F-stat. Uses Python loop with slice operations.
- **Fix:** Precompute cumulative sums of `vals` and `vals²` for O(1) RSS computation per split:
  ```python
  cumsum = np.cumsum(vals)
  cumsum2 = np.cumsum(vals ** 2)
  n = len(vals)
  for i in range(int(n * .15), int(n * .85)):
      n1, n2 = i, n - i
      mean1 = cumsum[i-1] / n1
      mean2 = (cumsum[-1] - cumsum[i-1]) / n2
      rss1 = cumsum2[i-1] - n1 * mean1**2
      rss2 = (cumsum2[-1] - cumsum2[i-1]) - n2 * mean2**2
      rss_split = rss1 + rss2
  ```
  Or use `numba.njit` for the loop.
- **Expected gain:** 50–100x for structural break computation.

---

## TIER 2 — High Impact (2x–10x speedups)

### 8. `research_panel` calls `signal_matrix` then `control_matrices` calls it again

- **File:** `analytics.py`
- **Line(s):** 295-296
- **Issue:** `research_panel` (line 295) calls `signal_matrix(payload, symbols, returns)`. Then
  line 296 calls `control_matrices(payload, symbols, returns)`, which for "size", "value",
  "momentum" controls calls `signal_matrix` again at lines 202-206 with the same arguments.
  **`signal_matrix` is called 2–5 times with identical args.**
- **Fix:** Add an optional `signals` parameter to `control_matrices`. When pre-computed signals
  are available (from research_panel), use them instead of re-calling `signal_matrix`:
  ```python
  def control_matrices(payload, symbols, returns, signals=None):
      ...
      "size": signals if signals is not None else signal_matrix(...)
  ```
  Change `research_panel` to pass `signals`:
  ```python
  signals = signal_matrix(payload, symbols, returns)
  controls = control_matrices(payload, symbols, returns, signals=signals)
  ```
- **Expected gain:** 2–5x reduction in signal_matrix calls (which includes parquet reads and pivots).

### 9. `portfolio_sort` loop creates DataFrame per date

- **File:** `analytics.py`
- **Line(s):** 345-355
- **Issue:** For each date (typically 300-600 months), line 347 creates a new DataFrame:
  `pd.DataFrame({"signal": ..., "ret": ..., "weight": ...}).dropna()`. Then line 350 does
  `pd.qcut(...)`. Then line 352 does `.groupby("bucket")`.
- **Fix:** Vectorize across all dates. Concatenate one large stacked DataFrame and group by date:
  ```python
  stacked = pd.concat([
      sig.stack().rename("signal"),
      fwd.stack().rename("ret"),
      weights.stack().rename("weight"),
  ], axis=1).dropna().reset_index()
  stacked["bucket"] = stacked.groupby("date")["signal"].transform(
      lambda s: pd.qcut(s.rank(method="first"), q=buckets, labels=...)
  )
  port_rets = stacked.groupby(["date", "bucket"], observed=True).apply(
      lambda g: np.average(g["ret"], weights=g["weight"].clip(lower=0))
  ).unstack()
  ```
  Avoids N×DataFrame construction overhead.
- **Expected gain:** 5–10x for portfolio_sort.

### 10. `fama_macbeth_table` loop creates DataFrame per date (same pattern)

- **File:** `analytics.py`
- **Line(s):** 308-318
- **Issue:** For each date, `_regression_design_for_date` (line 278-283) creates a new DataFrame
  via `pd.DataFrame(data).dropna()`. Then `ols` is called per date. For 500 months × 500 symbols,
  that's 500 OLS calls.
- **Fix:** Stack all data into one panel, then use groupby-apply with a single pandas operation.
  Even better: pre-compute the stacked panel once in `research_panel` and store it. The FM
  regression per date can be accelerated with:
  - `numba.njit` on the OLS inner loop
  - Grouping dates into batches and using `np.linalg.pinv` on stacked design matrices
- **Expected gain:** 3–5x.

### 11. `ols` function computes `pinv(X'X)` twice

- **File:** `analytics.py`
- **Line(s):** 115, 120
- **Issue:** Line 115 computes `np.linalg.pinv(xm.T @ xm)` to get beta. Line 120 computes
  `np.linalg.pinv(xm.T @ xm)` again for the covariance matrix. The same inverse is computed
  twice.
- **Fix:**
  ```python
  xtxi = np.linalg.pinv(xm.T @ xm)
  beta = xtxi @ xm.T @ yv
  ...
  cov = sigma2 * xtxi
  ```
  Also replace `pinv` with `np.linalg.solve(xm.T @ xm, xm.T @ yv)` for the normal equations
  when the matrix is full rank (which is nearly always), avoiding SVD overhead.
- **Expected gain:** 2x per OLS call (and OLS is called thousands of times).

### 12. `ols` p-value list comprehension not vectorized

- **File:** `analytics.py`
- **Line(s):** 123
- **Issue:** `p = np.array([p_value_from_t(v, dof) if np.isfinite(v) else np.nan for v in t])` -
  Python list comprehension inside the most-called function. `p_value_from_t` calls `stats.t.cdf`
  which accepts numpy arrays natively.
- **Fix:**
  ```python
  p = np.full_like(t, np.nan)
  mask_finite = np.isfinite(t)
  p[mask_finite] = p_value_from_t(t[mask_finite], dof)
  ```
  And rewrite `p_value_from_t` to handle arrays:
  ```python
  def p_value_from_t(t_stat, df):
      if stats is not None and df > 0:
          return 2 * (1 - stats.t.cdf(np.abs(np.asarray(t_stat, dtype=float)), df))
      ...
  ```
- **Expected gain:** 10–50x for the p-value computation in OLS (which is called thousands of times).

### 13. `signal_matrix` calls `latest_fundamentals()` in every branch

- **File:** `analytics.py`
- **Line(s):** 166-184
- **Issue:** Each if/elif branch in signal_matrix calls `latest_fundamentals()` independently
  (lines 166, 170, 182). The function loads and processes the entire fundamentals parquet on
  each call. For size/value/quality controls, this is called multiple times (from control_matrices
  calling signal_matrix).
- **Fix:** Hoist `latest_fundamentals()` to the top of `signal_matrix`:
  ```python
  lf = latest_fundamentals()
  ```
  Called once regardless of which branch executes.
- **Expected gain:** Each `latest_fundamentals()` call parses a parquet — saves 2–3 parquet
  reads per signal_matrix call.

### 14. Dict comprehension for fundamentals in `signal_matrix` is O(N) with `.loc`

- **File:** `analytics.py`
- **Line(s):** 167, 172-179, 183
- **Issue:** Lines 167/172-179/183 iterate over `symbols` (up to 1500) with `.loc` inside a dict
  comprehension. Each iteration checks `s in lf.index` (O(1) with hash, but `.loc` is slow).
  Line 168 creates `[vals] * len(rets)` — a list of the same Series repeated, consuming memory.
- **Fix:** Use pandas merge/join instead of Python dict:
  ```python
  lf_subset = lf.loc[lf.index.isin(symbols), "marketCap"]
  vals = lf_subset.reindex(symbols).to_numpy()
  ```
  Then broadcast once:
  ```python
  sig = pd.DataFrame(np.tile(vals, (len(rets), 1)), index=rets.index, columns=symbols)
  ```
- **Expected gain:** 10x for these branches (avoids Python loop over 1500 symbols + .loc overhead).

### 15. `_static_fundamental_controls` loops over symbols with `.loc`

- **File:** `analytics.py`
- **Line(s):** 242-256
- **Issue:** Loop over `symbols` (up to 1500) with per-symbol `.loc` and multiple `col_value`
  calls (line 247-251) that rebuild a `lower` dict from `row.index` each time.
- **Fix:** Join `lf` once, vectorize:
  ```python
  lf_subset = lf.reindex(symbols)
  asset_col = ...  # find right column name once
  equity_col = ...
  ...
  assets = pd.to_numeric(lf_subset[asset_col], errors="coerce")
  equity = pd.to_numeric(lf_subset[equity_col], errors="coerce")
  ...
  rows = pd.DataFrame({
      "asset_growth": np.log(assets),
      "profitability": income / assets,
      "leverage": debt / assets,
  }, index=symbols)
  ```
- **Expected gain:** 50x for this function (1500 .loc calls → 5 vectorized column ops).

### 16. `monotonicity_test` bootstrap loop uses Python for-loop

- **File:** `analytics.py`
- **Line(s):** 441-443
- **Issue:** For-loop with 500–1000 iterations, each calling `rng.integers`, indexing `vals`,
  creating `pd.Series(...).diff()`. Python overhead is substantial.
- **Fix:** Vectorize entirely with numpy:
  ```python
  n, k = vals.shape
  indices = rng.integers(0, n, size=(reps, n))
  samples = vals[indices]  # shape (reps, n, k)
  means = samples.mean(axis=1)  # shape (reps, k)
  diffs = np.diff(means, axis=1)  # shape (reps, k-1)
  boot_stats = np.mean(diffs > 0, axis=1)
  p = np.mean(boot_stats >= observed)
  ```
- **Expected gain:** 100x (eliminates all Python loop overhead and Series creation).

### 17. `_spec_curve_joint_permutation` uses Python for-loop

- **File:** `analytics.py`
- **Line(s):** 739-741
- **Issue:** For-loop with 1000 iterations, each calling `rng.choice` and `nanmax`.
- **Fix:** Vectorize:
  ```python
  signs = rng.choice([-1, 1], size=(reps, len(centered)))
  null = np.nanmax(np.abs(centered * signs), axis=1)
  ```
- **Expected gain:** 50x for this function.

### 18. `_half_life_bootstrap` loop with `optimize.curve_fit` per iteration

- **File:** `analytics.py`
- **Line(s):** 1748-1756
- **Issue:** 200 iterations, each calling `scipy.optimize.curve_fit` (which itself is iterative).
  This is extremely expensive.
- **Fix:**
  - Replace `curve_fit` with a linearized version: fit `log(y - c) = log(a) - b*x` using
    simple linear regression, avoiding iterative optimization.
  - Reduce bootstrap reps from 200 to 99 (minimal accuracy loss for percentile CIs).
- **Expected gain:** 5x (linearized).

### 19. `_threshold_grid` loop runs 13 sequential t-tests

- **File:** `analytics.py`
- **Line(s):** 926-935
- **Issue:** Loop over 13 quantile thresholds, each computing sub-series, mean diff, pooled SE,
  t-stat. Could be vectorized.
- **Fix:** Compute all thresholds at once using sorted values and cumulative statistics.
  For each quantile `q`, the threshold `thr = sig.quantile(q)`. Compute mask `sig >= thr` for
  each and use pre-computed cumulative sums of `ls` and `ls²` to get mean/var in O(1).
- **Expected gain:** 3–5x.

### 20. `_panel_ols` runs two OLS fits

- **File:** `analytics.py`
- **Line(s):** 558-559
- **Issue:** Line 558 does `ols(fit_df["ret"], fit_df[x_cols])` (within-transformed) and line
  559 does `ols(df["ret"], df[x_cols])` (pooled). These are on different data but both do
  full OLS from scratch.
- **Fix:** The within-transformed coefficients can be derived from the pooled coefficients in
  some cases. If not, at least the pooled OLS can reuse the stacked design matrix already built
  by `_stacked_panel_design`.
- **Expected gain:** 2x for this function.

### 21. `_panel_robust_se` fits TWO statsmodels models

- **File:** `analytics.py`
- **Line(s):** 608-611
- **Issue:** Line 609-610 fits two separate `sm.OLS(...).fit()` models with different cov_types
  (HAC and cluster). Each call does the full OLS estimation internally.
- **Fix:** Fit once, then compute both standard error types:
  ```python
  model = sm.OLS(y, x)
  results = model.fit()  # plain OLS once
  hac_bse = results.get_robustcov_results(cov_type="HAC", maxlags=6).bse
  cluster_bse = results.get_robustcov_results(cov_type="cluster", groups=groups).bse
  ```
  This avoids redundant QR decomposition.
- **Expected gain:** 2x for this function.

---

## TIER 3 — Medium Impact (1.5x–5x speedups)

### 22. `nw_se` uses Python for-loop for autocovariances

- **File:** `analytics.py`
- **Line(s):** 137-139
- **Issue:** `for l in range(1, min(lag, n-1) + 1)` computes autocovariances sequentially with
  `.iloc` slicing. Called from `fama_macbeth_table` for each term, and redundantly in
  `portfolio_sort` (line 367 calls `nw_se(r)` twice).
- **Fix:** Use `np.correlate(xc, xc, mode='full')` or FFT-based autocorrelation to get all lags
  in one shot:
  ```python
  acov = np.correlate(xc, xc, mode='full')[n-1:] / n  # all autocovariances
  var = acov[0] + 2 * np.sum((1 - np.arange(1, lag+1) / (lag + 1)) * acov[1:lag+1])
  ```
- **Expected gain:** 5–10x per nw_se call. Portfolio_sort calls nw_se ~10 times.

### 23. `nw_se` called twice per loop in `portfolio_sort` line 367

- **File:** `analytics.py`
- **Line(s):** 367
- **Issue:** `"t_stat": r.mean() / nw_se(r) if nw_se(r) else np.nan` — `nw_se(r)` is called
  twice! Once in the condition, once in the value.
- **Fix:**
  ```python
  seg = nw_se(r)
  "t_stat": r.mean() / seg if seg else np.nan
  ```
- **Expected gain:** 2x for the portfolio_sort table loop (trivial but obvious bug).

### 24. `_fit_decay_models` calls `optimize.curve_fit` twice

- **File:** `analytics.py`
- **Line(s):** 1703, 1719
- **Issue:** Exponential fit (line 1703) and hyperbolic fit (line 1719) each call
  `scipy.optimize.curve_fit` with `maxfev=10000`. Each call is iterative and expensive.
- **Fix:**
  - Reduce `maxfev` from 10000 to 1000 (curve fits typically converge in <200 iterations).
  - Use `scipy.optimize.least_squares` with analytic Jacobian for faster convergence.
- **Expected gain:** 2–3x.

### 25. `_event_study` loop creates `pd.DateOffset` per iteration

- **File:** `analytics.py`
- **Line(s):** 1366-1369
- **Issue:** Loop over 25 event months creates `pd.DateOffset(months=int(k))` 25 times. Also
  `y.index.get_indexer([target], method="nearest")` per iteration.
- **Fix:** Pre-compute offsets:
  ```python
  offsets = pd.tseries.frequencies.to_offset(f"{window}ME")  # if monthly
  ```
  Or use integer positional indexing since the loop is over consecutive months:
  ```python
  base_idx = y.index.get_indexer([date], method="nearest")[0]
  for k in range(-window, window + 1):
      target_idx = max(0, min(len(y) - 1, base_idx + k))
      nearest = y.index[target_idx]
      ...
  ```
- **Expected gain:** 3–5x (avoids 25 get_indexer calls).

### 26. `_callaway_santanna_proxy` loop with `get_indexer` per iteration

- **File:** `analytics.py`
- **Line(s):** 1446-1452
- **Issue:** Loop over 20 event times, each calling `df.index.get_indexer([target], method="nearest")`.
- **Fix:** Use positional indexing from a pre-computed base index (same fix as #25).
- **Expected gain:** 3x.

### 27. `_rdd_proxy` recomputes `np.arange` and `np.searchsorted` each time

- **File:** `analytics.py`
- **Line(s):** 1569-1573
- **Issue:** Called from `_rdd_bandwidth_sensitivity` (5 times), `_rdd_placebo_cutoffs` (5 times),
  `_rdd_donut_hole` (3 times). Each call recomputes `np.arange(len(y))` and `np.searchsorted`.
- **Fix:** Compute once in the calling function, pass `x` and cutoff index to `_rdd_proxy`.
- **Expected gain:** Reduces redundant array creation. ~2x for RDD functions.

### 28. `_rdd_bandwidth_sensitivity` double OLS per bandwidth

- **File:** `analytics.py`
- **Line(s):** 1578-1585
- **Issue:** For each of 5 bandwidths, runs OLS (line 1582) and donut-hole OLS (line 1584).
  That's 10 OLS fits with similar data.
- **Fix:** Pre-compute the design matrix `X = ["post", "x"]` once. Each bandwidth just subsets
  rows — reuse the pre-computed `(X'X)⁻¹` by subsetting appropriately, or at least avoid
  rebuilding `np.column_stack` each time.
- **Expected gain:** 2x.

### 29. `_stacked_panel_design` stacks with `.stack()` and `pd.concat`

- **File:** `analytics.py`
- **Line(s):** 1016-1019
- **Issue:** For each control variable, `mat.stack()` creates a multi-level Series, then
  `pd.concat(parts, axis=1)` joins them. For 500 symbols × 500 dates × 5 controls, this is
  a massive 2.5M-row intermediate.
- **Fix:** Convert to numpy early and build arrays directly:
  ```python
  # Get aligned numpy arrays, avoiding MultiIndex entirely
  sig_vals = panel["signals"].to_numpy().ravel()
  ret_vals = panel["forward"].to_numpy().ravel()
  # etc.
  ```
  Or use `pandas.melt` which is faster than `.stack()` for wide-to-long. Or use `polars` for
  this operation (polars unpivot is 10x faster than pandas melt/stack).
- **Expected gain:** 2–5x depending on data size.

### 30. `_regression_diagnostics` computes VIF in Python loop

- **File:** `analytics.py`
- **Line(s):** 1041-1048
- **Issue:** Loop over variables computing `variance_inflation_factor(exog, i)`. Each call to
  `variance_inflation_factor` does an OLS internally (regresses one variable on all others).
- **Fix:** Compute all VIFs at once from the correlation matrix:
  ```python
  corr = np.corrcoef(exog[:, 1:], rowvar=False)  # exclude const
  vif = np.linalg.inv(corr).diagonal()
  ```
  This avoids N separate regressions.
- **Expected gain:** 10x for VIF computation (N OLS fits → 1 matrix inverse).

### 31. `_rolling_sharpe` uses `.rolling(12).apply(lambda)` — Python loop in C code

- **File:** `analytics.py`
- **Line(s):** 1781
- **Issue:** `.rolling(12).apply(lambda x: ...)` forces pandas to call back into Python for
  every window, eliminating the C-optimized rolling path.
- **Fix:** Use `numpy` sliding window or `bottleneck`:
  ```python
  import bottleneck as bn
  rolling_mean = bn.move_mean(s.to_numpy(), window=12, min_count=1)
  rolling_std = bn.move_std(s.to_numpy(), window=12, min_count=1)
  sharpe = rolling_mean / (rolling_std + 1e-12) * math.sqrt(12)
  ```
  Or use `pandas.DataFrame.rolling` with `method="table"` (experimental, pandas ≥1.3).
- **Expected gain:** 20–50x for this function.

### 32. `_placebo_rmspe` calls `_scm_weights` 25 times

- **File:** `analytics.py`
- **Line(s):** 1899-1906
- **Issue:** Loop over up to 25 candidate units, each calling `_scm_weights` which runs
  `scipy.optimize.minimize`. That's 25 optimization calls.
- **Fix:**
  - Downsample `donors` (currently `[:min(20, ...)]`).
  - Reuse SVD of the donor matrix across optimizations (the constraint is always sum-to-1
    with non-negativity).
- **Expected gain:** 2x (downsample).

### 33. `_leave_one_out` calls `_scm_weights` 10 times

- **File:** `analytics.py`
- **Line(s):** 1926-1929
- **Issue:** For top 10 donors, removes one and re-runs `_scm_weights`. Each is an optimization.
- **Fix:** Same as #32 — downsample donors or reuse SVD across optimizations.
- **Expected gain:** 2x.

### 34. `_in_time_placebo` calls `_scm_weights` 3 times

- **File:** `analytics.py`
- **Line(s):** 1941-1944
- **Issue:** Three fake treatment dates, each calling `_scm_weights`.
- **Fix:** Limit to fewer fake treatment dates or use a more efficient optimizer.
- **Expected gain:** 1.5x.

### 35. `_staggered_adoption_scm` calls `_scm_weights` per event (up to 20)

- **File:** `analytics.py`
- **Line(s):** 1860-1870
- **Issue:** Loop over events, each calling `_scm_weights` which is scipy.optimize.minimize.
- **Fix:** Limit `max_events` or pre-compute donor pool structure.
- **Expected gain:** 2x.

### 36. `_scm_weights` lambda inside `optimize.minimize` is recompiled per call

- **File:** `analytics.py`
- **Line(s):** 1890
- **Issue:** `lambda w: float(np.square(y.to_numpy() - x.to_numpy() @ w).mean())` — the lambda
  captures `y` and `x` by closure. `optimize.minimize` evaluates this many times per call.
  Each evaluation recomputes `y.to_numpy()` and `x.to_numpy()` (though these are references,
  the vectorization is fine). The real issue is that `scipy.optimize.minimize` is iterative
  and slow for high-dimensional problems.
- **Fix:** Replace `scipy.optimize.minimize` with a quadratic programming solver (cvxpy,
  osqp, qpsolvers). SCM weight problem is a constrained least squares:
  ```python
  import cvxpy as cp
  w = cp.Variable(n)
  objective = cp.Minimize(cp.sum_squares(y - x @ w))
  constraints = [w >= 0, cp.sum(w) == 1]
  prob = cp.Problem(objective, constraints)
  prob.solve(solver="OSQP")
  return pd.Series(w.value, index=x.columns)
  ```
  This is 10–50x faster than `scipy.optimize.minimize` with SLSQP.
- **Expected gain:** 10–50x per SCM weight call (and it's called 25+ times per SCM run).

### 37. `close_matrix` / `volume_matrix` use `pivot_table` on full OHLCV

- **File:** `data_loader.py`
- **Line(s):** 126, 138
- **Issue:** `pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last")` on
  the full OHLCV DataFrame (potentially millions of rows) is very slow. `pivot_table` is a
  pandas bottleneck.
- **Fix:** Use `polars` pivot:
  ```python
  pl_df = pl.from_pandas(df)
  mat = pl_df.pivot(index="Date", columns="Ticker", values="Close").to_pandas()
  ```
  Or use `pd.pivot` (the simpler version, available in pandas ≥1.5 with less overhead):
  ```python
  mat = df.pivot(index="Date", columns="Ticker", values="Close")
  ```
  (Avoids the multi-index aggregation logic of `pivot_table` when `aggfunc="last"` is just
  the default deduplication.)
  Or use `groupby` + `unstack`:
  ```python
  mat = df.groupby(["Date", "Ticker"])["Close"].last().unstack()
  ```
- **Expected gain:** 3–10x for the pivot step (the single most expensive part of data loading).

### 38. `ohlcv_for_symbols` uses `df["Ticker"].isin(normalized)` on full DataFrame

- **File:** `data_loader.py`
- **Line(s):** 114-115
- **Issue:** `load_market_ohlcv()` returns the entire parquet (cached). Then `.isin()` filters
  to requested symbols. `isin` on a large Series is O(n*m) worst case.
- **Fix:** Use categorical dtype for `Ticker` column:
  ```python
  df["Ticker"] = df["Ticker"].astype("category")
  ```
  Then `isin` on a categorical is very fast (O(n + m)). Set this once in `load_market_ohlcv`
  after the initial load.
- **Expected gain:** 2–3x for symbol filtering (especially when loading many symbols).

### 39. `pivot_table` always on all symbols, even when only a few needed

- **File:** `data_loader.py`
- **Line(s):** 126
- **Issue:** `close_matrix` filters by symbol with `ohlcv_for_symbols` (line 123), which is
  efficient. But `pivot_table` on the filtered result still pivots all remaining rows. For
  small symbol sets this is fine, but for 1500 symbols it's millions of rows.
- **Fix:** If the filtered DataFrame is large, use the polars pivot path (as in #37).
- **Expected gain:** 3x for large universes.

### 40. `close_matrix` resamples after pivot (creating large intermediate)

- **File:** `data_loader.py`
- **Line(s):** 127-131
- **Issue:** Pivots to daily resolution first (which can be huge: 1500 cols × 2500 days = 3.75M
  cells), THEN resamples to monthly. For monthly frequency, all daily resolution is wasted.
- **Fix:** Resample BEFORE pivoting:
  ```python
  if frequency == "monthly":
      df = df.groupby(["Ticker", pd.Grouper(key="Date", freq="ME")])["Close"].last().reset_index()
  mat = df.pivot(index="Date", columns="Ticker", values="Close")
  ```
  This reduces the pivot input by ~22x (daily → monthly).
- **Expected gain:** 5–15x for monthly frequency (common case).

### 41. `load_macro()` merges DataFrames one at a time in loop

- **File:** `data_loader.py`
- **Line(s):** 338-341
- **Issue:** For each additional parquet beyond the first, `.merge(frame, on="Date", how="outer")`
  is called sequentially. Each merge creates a new intermediate DataFrame.
- **Fix:** Collect all frames then use `functools.reduce` with pd.merge, or better: concat all
  frames by Date index, then groupby first:
  ```python
  combined = pd.concat(frames)  # concatenate vertically
  combined = combined.set_index("Date").groupby(level=0).first().sort_index()
  ```
  This avoids N-1 separate merge operations.
- **Expected gain:** 2–3x for load_macro (especially with many macro files).

### 42. `_parse_ken_french_csv` reads entire file into memory, then processes line-by-line

- **File:** `data_loader.py`
- **Line(s):** 267-290
- **Issue:** `path.read_text(errors="ignore")` reads the entire CSV into a string, then
  `.splitlines()` divides it, then loops. For large factor files this wastes memory.
- **Fix:** Use pandas `read_csv` with `skiprows` to skip the header metadata:
  ```python
  def _parse_ken_french_csv(path):
      if not path.exists():
          return pd.DataFrame(columns=["date"])
      # Find the header row index efficiently
      with open(path) as f:
          for i, line in enumerate(f):
              if re.match(r"^\s*,?\s*Mkt-RF|^\s*Date\s*,", line):
                  skip = i
                  break
      df = pd.read_csv(path, skiprows=skip, parse_dates=["date"], infer_datetime_format=True)
      ...
  ```
  This delegates parsing to pandas' C engine.
- **Expected gain:** 5–10x for factor file loading. Also enables pyarrow backend.

### 43. `data_inventory()` calls `load_macro()` twice

- **File:** `data_loader.py`
- **Line(s):** 346, 355
- **Issue:** Line 346 calls `load_macro()` to get columns. Line 355 calls `load_macro()` again
  inside the dict comprehension. Both calls load and merge the full macro parquet.
- **Fix:** Call once:
  ```python
  macro = load_macro()
  macro_cols = {str(c).lower() for c in macro.columns}
  ...
  "fred_present": {
      "VIXCLS": bool(any("vix" in c.lower() for c in macro.columns)),
      ...
  }
  ```
- **Expected gain:** 2x for data_inventory (which is called on every API response).

### 44. `response()` calls `data_inventory()` on every API response

- **File:** `analytics.py`
- **Line(s):** 81
- **Issue:** Every API response includes `data_inventory()` in the meta. `data_inventory` loads
  `market_universe.parquet`, `load_macro()`, `load_factor_returns()`. Even with `@lru_cache`,
  the first call is expensive.
- **Fix:** Cache `data_inventory()` result:
  ```python
  from functools import lru_cache
  @lru_cache(maxsize=1)
  def cached_inventory():
      return data_inventory()
  ```
  Since the data doesn't change during a session, this saves the full inventory computation
  after the first call.
- **Expected gain:** Eliminates redundant I/O after first request. ~2s saved per subsequent call.

### 45. `_weak_identification` computes full covariance matrix

- **File:** `analytics.py`
- **Line(s):** 501
- **Issue:** `panel["signals"].dropna(how="all").fillna(0).cov()` computes pairwise covariances
  for potentially 1500 columns. That's O(c²·T) where c=1500, T=500. The covariance matrix is
  then converted to numpy and has `eye` added, and `np.linalg.cond` computes SVD.
- **Fix:** For large `c`, the condition number can be estimated without full SVD:
  ```python
  if mat.shape[0] > 100:
      # Use power iteration for largest singular value
      # and do not compute smallest (or approximate)
      cond = np.linalg.cond(mat, p=2)  # but with scipy.sparse.linalg.svds
  ```
  Or only compute covariance on a random subset of columns (since this is a diagnostic, not
  core computation). Or skip entirely for `c > 500` (current code already returns `np.nan` for
  `c >= 500`).
- **Expected gain:** Avoids O(1500²) covariance computation. 5–10x when close to threshold.

### 46. `grs_and_spanning` uses `np.linalg.pinv` on factor_cov and sigma

- **File:** `analytics.py`
- **Line(s):** 408-415
- **Issue:** Line 408 computes `np.cov(residuals)` (σ), line 410 computes `np.cov(factors)`.
  Lines 414-415 compute `np.linalg.pinv(factor_cov)` and `np.linalg.pinv(sigma)`.
  Each `pinv` is SVD-based O(k³) where k = number of factors (5-6) and n = number of portfolios
  (up to 10). The SVD is overkill for these tiny matrices.
- **Fix:** Use `np.linalg.inv` (since the matrices are small and nearly always full rank):
  ```python
  sigma_inv = np.linalg.inv(sigma + np.eye(n_ports) * 1e-10)
  factor_cov_inv = np.linalg.inv(factor_cov + np.eye(k_factors) * 1e-10)
  ```
  Or use `np.linalg.solve` for the quadratic form:
  ```python
  import scipy.linalg
  # alpha_vec.T @ sigma^{-1} @ alpha_vec
  solved = scipy.linalg.solve(sigma, alpha_vec, assume_a="pos")
  quad_form = alpha_vec.T @ solved
  ```
- **Expected gain:** 2–5x for the GRS computation (minor in absolute terms but called often).

### 47. `_benchmark_factor_frame` calls `returns_matrix` with I/O

- **File:** `analytics.py`
- **Line(s):** 541
- **Issue:** When `benchmark_tickers` is specified (not "ff5_mom"), calls `returns_matrix` which
  calls `close_matrix` which calls `ohlcv_for_symbols` which calls `load_market_ohlcv`. The
  OHLCV is cached by `@lru_cache` but the pivot and resampling still run each time.
- **Fix:** Cache the result of `_benchmark_factor_frame` keyed by the payload hash:
  ```python
  @lru_cache(maxsize=8)
  def _cached_benchmark_frame(payload_hash: int):
      ...
  ```
  Since multiple functions call this (GRS, calendar_time, etc.), caching saves redundant work.
- **Expected gain:** 1.5x for GRS/spanning/calendar_time calls.

### 48. `grs_and_spanning` loops over `ret_cols` with per-portfolio OLS

- **File:** `analytics.py`
- **Line(s):** 392-398
- **Issue:** For each portfolio column (typically 5-10), calls `ols()` independently. Each OLS
  computes pinv from scratch.
- **Fix:** Stack portfolios into a multivariate regression. OLS on (T × N) returns matrix
  against (T × K) factors shares the same design matrix — compute `(X'X)⁻¹X'` once:
  ```python
  X = sm.add_constant(df[factor_cols].to_numpy()) if factor_cols else np.ones((len(df), 1))
  XtXi_Xt = np.linalg.pinv(X.T @ X) @ X.T  # shape (K+1, T)
  Y = df[ret_cols].to_numpy()  # shape (T, N)
  Betas = XtXi_Xt @ Y  # shape (K+1, N) — each column is one portfolio's betas
  alphas = Betas[0]  # first row is alpha for each portfolio
  residuals = Y - X @ Betas
  r2s = 1 - np.sum(residuals**2, axis=0) / np.sum((Y - Y.mean(axis=0))**2, axis=0)
  ```
- **Expected gain:** 3–5x for GRS regression portion.

### 49. `factor_zoo_outputs` loops over factors with rolling(24).corr

- **File:** `analytics.py`
- **Line(s):** 2013-2015
- **Issue:** For each factor (5-6), computes `aligned["candidate"].rolling(24).corr(aligned[factor])`.
  Each `.corr()` call creates rolling windows.
- **Fix:** Compute all pairwise correlations at once:
  ```python
  rolling_corr = aligned.rolling(24).corr()  # yields MultiIndex (date, factor1, factor2)
  # Extract candidate vs every other factor
  ```
  Or use numpy sliding window for the rolling correlation.
- **Expected gain:** 3–5x for factor zoo.

### 50. `_event_study_tests` calls `_event_study` again

- **File:** `analytics.py`
- **Line(s):** 1374
- **Issue:** Line 1374: `_event_study(y, date, window=window)` — but the caller `causal_outputs`
  already computed `_event_study(y, treatment_date)` at line 1326 with default `window=12`.
  `_event_study_tests` is called with `window=20`, so the recomputation is for a different
  window, but there's overlap — could compute both windows in one pass.
- **Fix:** Compute event study once for the maximum window (20) and subset to smaller windows
  as needed.
- **Expected gain:** Avoids one redundant 41-row DataFrame construction.

### 51. `_event_study_tests` line 1383 computes full cross-correlation matrix

- **File:** `analytics.py`
- **Line(s):** 1383-1384
- **Issue:** `panel["returns"].corr()` computes the full N×N correlation matrix for all
  symbols (potentially 1500×1500). Then `.where(~np.eye(...)).stack().mean()` extracts the
  off-diagonal mean. This is O(N²) — for 1500 symbols that's 2.25 million entries.
- **Fix:** Use a random subset of symbols or compute pairwise correlation on a sample:
  ```python
  sample_cols = min(100, len(panel["returns"].columns))
  sampled = panel["returns"].iloc[:, :sample_cols]
  corr = sampled.corr()
  ```
  This is a diagnostic proxy — exact precision isn't needed.
- **Expected gain:** 200x+ for large universes (1500 → 100 symbols: 225x less computation).

### 52. `_regression_design_for_date` creates DataFrame per date

- **File:** `analytics.py`
- **Line(s):** 278-283
- **Issue:** Creates `pd.DataFrame(data).dropna()` for each date. Called from `fama_macbeth_table`
  (500+ times) and `_protected_oos_stats` (train + test dates).
- **Fix:** Pre-compute one stacked DataFrame and filter by date index:
  ```python
  # In research_panel, pre-build the stacked design:
  panel["stacked_design"] = _stacked_panel_design(panel)
  ```
  Then `_regression_design_for_date` just does a `.loc` slice on the pre-stacked data.
- **Expected gain:** 3–5x for FM table (avoids 500+ DataFrame allocations).

### 53. `_protected_oos_stats` loops over dates twice (train + test)

- **File:** `analytics.py`
- **Line(s):** 801-804, 812-820
- **Issue:** First loop collects training DataFrames and `pd.concat(rows)` (line 807). Second
  loop iterates over test dates doing OLS prediction. Each iteration calls
  `_regression_design_for_date(panel, d)` which creates a new DataFrame.
- **Fix:** Pre-stack the panel (see #52) and use boolean filtering. The OLS prediction can be
  vectorized: once `fit` is computed, predict on all test rows at once.
- **Expected gain:** 3x for protected OOS computation.

### 54. `_hausman_proxy` accesses `fe_fit["beta"][1]` and `pooled_fit["beta"][1]` individually

- **File:** `analytics.py`
- **Line(s):** 589-597
- **Issue:** Fine in isolation but called from `_panel_ols`. The key inefficiency is that
  `_panel_ols` runs TWO OLS fits (line 558-559) just to get Hausman. The Hausman test could
  be computed from a single GMM-style estimation.
- **Expected gain:** Minor (1.01x).

### 55. `_acf_table` has list comprehension calling `s.autocorr(lag)` per lag

- **File:** `analytics.py`
- **Line(s):** 1098
- **Issue:** Loop of 21 iterations, each calling `pd.Series.autocorr(lag)` which internally
  computes mean, variance, and dot product per lag. Work is redundant across lags.
- **Fix:** Use `np.correlate` for all lags at once (same as `nw_se` fix #22):
  ```python
  s = pd.Series(series).dropna().to_numpy()
  n = len(s)
  acov = np.correlate(s - s.mean(), s - s.mean(), mode='full')[n-1:] / n
  acf = acov / acov[0]
  ```
- **Expected gain:** 5x for ACF computation.

### 56. `_comparison_df` in `_fit_decay_models` computes AIC/BIC with `math.log` in loop

- **File:** `analytics.py`
- **Line(s):** 1726-1729
- **Issue:** Loop over 3 models, computing `rss`, `aic`, `bic` with `math.log` per iteration.
  Fine for 3 models.
- **Expected gain:** Negligible.

### 57. `_publication_column_fit` calls `signal_matrix`, `control_matrices`, `portfolio_weight_frame` per column

- **File:** `analytics.py`
- **Line(s):** 1194-1196
- **Issue:** For each publication column (4-8), these three functions recompute everything from
  scratch. `signal_matrix` loads fundamentals, pivots, etc. This multiplies the cost by 4-8x.
- **Fix:** Pre-compute the base signal, controls, and weights in `specification_builder_outputs`
  and pass them to `_publication_column_fit`. The per-column changes only affect parameters
  (signal type, controls list, weighting scheme) — cache results keyed by parameter hash.
- **Expected gain:** 4–8x for this function.

### 58. `_specification_builder_outputs` calls `research_panel` with default_limit override

- **File:** `analytics.py`
- **Line(s):** 1116
- **Issue:** `research_panel(payload, default_limit=int(payload.get("max_symbols") or 400))` —
  the `default_limit` here defaults to 400 but the `parse_symbols` inside `research_panel` also
  uses `default_limit=400` by default (line 287). So this is actually redundant — the same
  value is passed through. But `canonical_outputs` at line 1117 calls `research_panel` again
  with a potentially different limit. The two calls should share a panel.
- **Expected gain:** 2x (fewer duplicate panel builds).

### 59. `latex_table` catches exception on `to_latex` then falls back to CSV

- **File:** `analytics.py`
- **Line(s):** 451-454
- **Issue:** Fine, but `df.to_latex` can be slow for large DataFrames. In robustness_outputs,
  it's called once per config for the robustness matrix. For 9 configs, that's 9 LaTeX calls.
  Also called for the main FM table.
- **Fix:** Cache the LaTeX output — the same format is often requested multiple times for the
  same data. Use `@lru_cache(maxsize=32)` keyed by `(name, df_hash)`.
- **Expected gain:** Minor (avoids redundant string formatting).

### 60. `control_matrices` recomputes `returns.mean(axis=1)` and `returns.rolling(36).cov(market)` twice

- **File:** `analytics.py`
- **Line(s):** 212-213, 216-221
- **Issue:** If both "beta" and "ivol" are requested, `returns.mean(axis=1)` is computed at
  line 212 and again at line 217. The rolling covariance with market (line 213) is computed
  at line 213 and potentially again at line 220.
- **Fix:** Compute market return once, rolling cov once:
  ```python
  if "beta" in requested or "ivol" in requested:
      market = returns.mean(axis=1)
      rolling_cov = returns.rolling(36).cov(market)
      rolling_var = market.rolling(36).var().replace(0, np.nan)
      beta = rolling_cov.div(rolling_var, axis=0).shift(1)
      if "beta" in requested:
          out["beta"] = beta
      if "ivol" in requested:
          resid = returns.sub(beta.mul(market, axis=0), axis=0)
          out["ivol"] = resid.rolling(36).std().shift(1)
  ```
- **Expected gain:** 1.5x for control_matrices when both beta and ivol requested.

### 61. `_double_sort` calls `signal_matrix` for second signal

- **File:** `analytics.py`
- **Line(s):** 630
- **Issue:** For non-built-in second signals, calls `signal_matrix({**payload, "signal": second}, ...)`.
  This loads fundamentals, computes returns, pivots — the full signal pipeline. Additionally,
  `signal_matrix` internally loads `returns_matrix` (line 154) even though `panel["returns"]`
  is passed.
- **Fix:** Pass `returns` directly to avoid the internal `returns_matrix` call. The
  `signal_matrix` function already accepts `returns` as optional parameter.
  ```python
  sig2 = signal_matrix({**payload, "signal": second}, list(panel["returns"].columns), panel["returns"])
  ```
  Actually, this already passes `panel["returns"]` — let me recheck. Yes, line 630: `signal_matrix({...},
  list(panel["returns"].columns), panel["returns"])`. The third argument IS the returns. Good.
  But `signal_matrix` at line 154 calls `returns_matrix` only when `returns` is None, and it's
  passed here, so that's fine. The main cost is `latest_fundamentals()` and the signal branch.
- **Expected gain:** Depends on signal — for fundamentals-based signals, saves nothing (already
  has returns). Minor.

### 62. `_regime_series` copies macro DataFrame

- **File:** `analytics.py`
- **Line(s):** 891
- **Issue:** `macro = panel.get("macro", pd.DataFrame()).copy()` — copies the entire macro
  DataFrame (potentially thousands of rows × hundreds of columns) even if it's not used
  (e.g., when source is "realized_vol", the default).
- **Fix:** Lazy copy — copy only in branches that actually modify it:
  ```python
  macro = panel.get("macro", pd.DataFrame())
  if source == "vix" and not macro.empty:
      macro = macro.copy()  # now copy
      ...
  ```
- **Expected gain:** Avoids copying large DataFrame for the common (default) case.

### 63. `_interaction_regression` calls `pd.get_dummies` then `ols`

- **File:** `analytics.py`
- **Line(s):** 978-981
- **Issue:** `pd.get_dummies(aligned["regime"], prefix="regime", dtype=float)` creates dummy
  columns (typically 3 for vol regimes). Then `ols(aligned["return"], dummies)` does a full
  OLS. For 3 dummy columns, this is fast, but `ols` always computes `pinv` of a tiny matrix.
- **Fix:** Use simple groupby means instead of OLS (regressing on dummies gives the group
  means directly):
  ```python
  means = aligned.groupby("regime", observed=True)["return"].agg(["mean", "std", "count"])
  # Means are the OLS coefficients on dummies
  ```
  This avoids the matrix inverse entirely. Only do OLS if interaction terms or SEs are needed.
- **Expected gain:** 2–3x for this function (negligible in absolute terms).

### 64. `_rdd_covariate_continuity` loops over controls

- **File:** `analytics.py`
- **Line(s):** 1632-1641
- **Issue:** For each control variable (typically 3-9), computes pre/post means and t-tests.
  Fine, but could be vectorized if there are many controls. Not a bottleneck.
- **Expected gain:** Negligible.

### 65. `_robust_scm` copies donors and computes per-column quantiles

- **File:** `analytics.py`
- **Line(s):** 1984-1987
- **Issue:** `donors.copy()`, then `donors.quantile(.01)` and `donors.quantile(.99)` each do
  a full sort per column. Then `.clip()` creates another copy.
- **Fix:** Use numpy for winsorization:
  ```python
  arr = full_ret[list(weights.index)].to_numpy()
  lo, hi = np.nanpercentile(arr, [1, 99])
  clipped = np.clip(arr, lo, hi)
  ```
  This avoids per-column quantile computation and copies.
- **Expected gain:** 2x for robust_scm.

---

## TIER 4 — Library/Infrastructure Changes

### 66. Replace Pandas with Polars for large panel operations

- **File:** `analytics.py` (multiple locations)
- **Line(s):** 126, 138, 1016-1022, 1084, 1092
- **Issue:** Pandas `pivot_table`, `stack()`, `concat()`, `merge()` operations on 500+ column
  × 2500+ row DataFrames are memory-intensive and single-threaded.
- **Fix:** Convert the core panel to Polars (`pl.DataFrame`) after loading. Polars:
  - Uses all CPU cores for pivot/groupby/join operations (2-10x faster)
  - Has zero-copy column access
  - Has lazy evaluation (`.lazy()` → `.collect()`)
  - Is significantly more memory-efficient
  - Transition strategy: wrap the panel dict values as `pl.from_pandas(df)` at the
    `research_panel` boundary, convert back to pandas only for output (`.to_pandas()`).
    Analytics functions that use numpy directly (OLS, etc.) stay unchanged since they
    operate on `.to_numpy()`.
- **Expected gain:** 2–10x on all data transformation operations.

### 67. Use Numba for OLS hot loop in FM regression

- **File:** `analytics.py`
- **Line(s):** 103-126, 308
- **Issue:** `ols()` is called 500+ times in `fama_macbeth_table`. Each call computes pinv of
  a small matrix. Numba can JIT-compile this inner loop.
- **Fix:** Create a Numba-accelerated batch OLS:
  ```python
  import numba
  @numba.njit
  def fast_ols(y, x):
      """x is (n, k), y is (n,). Returns (beta, se, t, p, r2, resid)."""
      n, k = x.shape
      xtx = x.T @ x
      xty = x.T @ y
      try:
          beta = np.linalg.solve(xtx, xty)
      except:
          beta = np.linalg.pinv(xtx) @ xty
      resid = y - x @ beta
      dof = max(1, n - k)
      sigma2 = resid @ resid / dof
      cov = sigma2 * np.linalg.inv(xtx)
      se = np.sqrt(np.maximum(np.diag(cov), 0))
      t = beta / np.where(se == 0, np.nan, se)
      ...
  ```
  Or use Numba to compile the entire FM date loop.
- **Expected gain:** 3–5x for FM regression (avoids Python function call overhead per call).

### 68. Use `bottleneck` for all rolling operations

- **File:** `analytics.py` (multiple locations)
- **Line(s):** 164, 208, 213-214, 221, 223, 376, 628, 1781, 2013
- **Issue:** Pandas `.rolling().mean()`, `.rolling().std()`, `.rolling().corr()` are slow
  compared to `bottleneck` which uses optimized C loops.
- **Fix:** Import `bottleneck as bn` and replace:
  - `returns.rolling(12).std()` → `bn.move_std(returns.to_numpy(), window=12, min_count=1)`
  - `returns.rolling(36).cov(market)` → use `bottleneck` for rolling cov (or implement with
    `bn.move_sum` on products)
  - `series.rolling(12).apply(lambda x: ...)` → `bn.move_mean/std` (avoids Python apply)
- **Expected gain:** 3–10x for each rolling operation.

### 69. Use `joblib.Parallel` for embarrassingly parallel loops

- **File:** `analytics.py` (multiple locations)
- **Line(s):** 308, 345, 392, 674-679, 753-757, 1748-1756, 1900-1913, 1926-1933
- **Issue:** Many loops have independent iterations: FM per date, portfolio sort per date,
  robustness configs, permutation tests, bootstrap, placebo SCM, leave-one-out SCM.
- **Fix:** Use `joblib.Parallel` with `n_jobs=-1`:
  ```python
  from joblib import Parallel, delayed
  dates = list(sig.index.intersection(fwd.index))
  results = Parallel(n_jobs=-1)(
      delayed(_single_date_fm)(panel, date) for date in dates
  )
  ```
  For the permutation loop:
  ```python
  null = Parallel(n_jobs=max(1, os.cpu_count() - 1))(
      delayed(_single_permutation)(panel, rng_seed=i) for i in range(reps)
  )
  ```
- **Expected gain:** 4–8x (on typical 8-core laptop) for these loops.

### 70. Use `scipy.linalg.solve` instead of `np.linalg.pinv` in OLS

- **File:** `analytics.py`
- **Line(s):** 115, 120
- **Issue:** `np.linalg.pinv` computes full SVD (O(nk² + k³)). For well-conditioned problems
  (which OLS design matrices nearly always are), `np.linalg.solve` or Cholesky is much faster.
- **Fix:**
  ```python
  xtx = xm.T @ xm
  xty = xm.T @ yv
  # Add small regularization for safety
  xtx_reg = xtx + np.eye(len(xtx)) * 1e-10
  beta = np.linalg.solve(xtx_reg, xty)
  # Covariance (for SEs) also from solve
  cov = sigma2 * np.linalg.inv(xtx_reg)  # inv is O(k³) but pinv is O(nk²)
  ```
  Since k is small (typically 2-6), `solve` is 5-10x faster than `pinv`.
- **Expected gain:** 3–5x per OLS call (and OLS is the most-called function).

### 71. Use `pyarrow.dataset` for predicate pushdown in parquet reads

- **File:** `data_loader.py`
- **Line(s):** 40-51, 74-77, 240-250, 314-341
- **Issue:** `pd.read_parquet(path, columns=...)` filters columns after reading. The entire
  parquet file is still decompressed and scanned. For `market_universe.parquet` (potentially
  hundreds of MB), this wastes I/O.
- **Fix:** Use `pyarrow.dataset` for predicate pushdown:
  ```python
  import pyarrow.dataset as ds
  dataset = ds.dataset(str(path), format="parquet")
  table = dataset.to_table(columns=columns, filter=...)
  df = table.to_pandas()
  ```
  For `ohlcv_for_symbols`, push the ticker filter down:
  ```python
  filter_expr = ds.dataset().scanner(filter=ds.field("Ticker").isin(normalized))
  ```
  This only reads the necessary row groups.
- **Expected gain:** 2–5x for parquet reads with filtering.

### 73. Pre-compute and cache `research_panel` results

- **File:** `analytics.py`
- **Line(s):** 286-300
- **Issue:** `research_panel` is the gateway function called by every feature. It loads parquet
  data, computes returns, signals, controls, weights, forward returns, factors, macro. Many
  features call it multiple times with identical or similar parameters.
- **Fix:** Add an LRU cache keyed by payload hash:
  ```python
  @lru_cache(maxsize=16)
  def _cached_panel(payload_json: str) -> dict:
      payload = json.loads(payload_json)
      return research_panel(payload)
  ```
  The cache key must include `symbols`, `lookback_days`, `frequency`, `signal`, `controls`,
  `weighting`, etc. Serialize the relevant subset and hash it.
  **But careful**: `research_panel` returns DataFrames that may be mutated downstream
  (the permutation test shuffles signals in-place via `.copy()` — line 752). So return a deep
  copy or document that consumers must copy before mutation.
- **Expected gain:** 2–5x when multiple features are called with the same payload (e.g.,
  specification builder).

### 74. `portfolio_weight_frame` can skip `latest_fundamentals()` for "equal" scheme

- **File:** `analytics.py`
- **Line(s):** 261-275
- **Issue:** For "equal" and "rank" schemes, `latest_fundamentals()` is NOT called (early
  return). For "value" scheme, it IS called at line 268. But `research_panel` (line 297)
  always calls `portfolio_weight_frame`, and the default weighting is "equal". So for the
  common case, `latest_fundamentals()` is not loaded here. However, `signal_matrix` and
  `control_matrices` often call it. The specific issue is that for value-weighting, the
  `latest_fundamentals()` call in `portfolio_weight_frame` is a third redundant call (after
  signal_matrix and control_matrices may have already loaded it).
- **Fix:** Pass pre-loaded `lf = latest_fundamentals()` to all functions that need it, or
  rely on `@lru_cache` (which already caches `latest_fundamentals` — line 253). So this is
  already handled by LRU cache.
- **Expected gain:** Already solved by `@lru_cache` — no action needed.

### 75. `_panel_ols` calls `_within_transform` on full DataFrame

- **File:** `analytics.py`
- **Line(s):** 556-558
- **Issue:** `_within_transform(fit_df, x_cols, ...)` copies the DataFrame (line 577), then
  does groupby transforms. For stacked panel data (millions of rows), this copy is expensive.
- **Fix:** Avoid the `.copy()` in `_within_transform` if the original won't be reused:
  ```python
  def _within_transform(df, x_cols, time_fe, asset_fe):
      if not time_fe and not asset_fe:
          return df  # no transformation needed
      out = df.copy()  # still need copy if transforming
      ...
  ```
  But the caller at line 557-558 already copied: `fit_df = df.copy()`. So `_within_transform`
  copies again. Remove the outer copy:
  ```python
  fit_df = df  # don't copy here
  if fe in {...}:
      fit_df = _within_transform(fit_df, x_cols, ...)
  ```
  And remove `.copy()` from `_within_transform` (or keep it — the transform is a subtraction
  so it creates new arrays anyway).
- **Expected gain:** Avoids one large DataFrame copy. ~1.5x for panel OLS.

### 76. `nw_se` converts to `pd.Series` unnecessarily

- **File:** `analytics.py`
- **Line(s):** 130
- **Issue:** `x = pd.Series(series).dropna().astype(float)` — if `series` is already a
  `pd.Series`, this wraps it again. If it's a numpy array, the conversion is needed but
  `pd.Series(...).astype(float)` is slower than `np.asarray(..., dtype=float)`.
- **Fix:**
  ```python
  if isinstance(series, pd.Series):
      x = series.dropna().astype(float).to_numpy()
  else:
      x = np.asarray(series, dtype=float)
      x = x[np.isfinite(x)]
  ```
- **Expected gain:** Minor (1.1x).

### 77. `_event_study_tests` line 1394 renames/merges factors every call

- **File:** `analytics.py`
- **Line(s):** 1394-1396
- **Issue:** `panel["factors"].rename(columns={"Date": "date"}).set_index("date")` creates
  a new DataFrame every call. Then `.merge()` creates another. For causal_outputs, this is
  called once.
- **Expected gain:** Minor.

### 78. `_gmm_shanken` copies FM DataFrame

- **File:** `analytics.py`
- **Line(s):** 648
- **Issue:** `out = fm.copy()` then modifies in place. The copy is necessary but adds
  overhead for the FM table (typically <10 rows). Fine.
- **Expected gain:** Negligible.

### 79. `_bootstrap_disagreement` copies sort table

- **File:** `analytics.py`
- **Line(s):** 661
- **Issue:** `out = sort_table.copy()` — typically <10 rows. Negligible.

### 80. `_make_series` in `_regime_series` searches for columns with `next()` generator

- **File:** `analytics.py`
- **Line(s):** 895, 900, 905
- **Issue:** `next((c for c in macro.columns if ...), None)` — fine for a few columns.
  For thousands of macro columns, iterating once is fine. Not a bottleneck.

### 81. `records()` replaces inf twice

- **File:** `analytics.py`
- **Line(s):** 75-76
- **Issue:** `clean = df.replace([np.inf, -np.inf], np.nan)` then
  `clean.where(pd.notna(clean), None)`. Two passes over the entire DataFrame.
- **Fix:** Combine into one pass:
  ```python
  clean = df.replace([np.inf, -np.inf], np.nan)
  out = clean.where(pd.notna(clean), None).to_dict("records")
  ```
  Could use `df.to_dict("records")` with a post-processing step, but the current approach
  is already standard. Merging the replace and where:
  ```python
  out = df.replace([np.inf, -np.inf], None).to_dict("records")
  ```
  But `replace` with None inserts None for inf values directly.
- **Expected gain:** 1.5x for records function (called for every chart/table output).

### 82. `_publication_table` loop builds strings with f-strings per cell

- **File:** `analytics.py`
- **Line(s):** 1254-1265
- **Issue:** Loop over 4-8 columns, each formatting coefficient, SE, t-stat, etc. Fine for
  small tables. Not a bottleneck.

### 83. `_forest_plot_rows` loop over 4-8 spec rows

- **File:** `analytics.py`
- **Line(s):** 1285-1297
- **Issue:** Small loop, negligible.

### 84. `_confirmatory_tags` filters spec_rows list

- **File:** `analytics.py`
- **Line(s):** 1301-1303
- **Issue:** List comprehensions over 4-8 items. Negligible.

### 85. `_matching_balance` uses `.iloc[-1]` and `.loc[treated]`

- **File:** `analytics.py`
- **Line(s):** 1465-1468
- **Issue:** `sig = panel["signals"].iloc[-1].dropna()` — gets last row of signals. Then
  `sig.loc[treated]`. Fine. The sort of 1500 values for `.head(12)` is O(N log N) but
  negligible for a single call.

### 86. `_iv_proxy` calls `ols` 4 times

- **File:** `analytics.py`
- **Line(s):** 1487-1493
- **Issue:** First stage OLS (line 1487), second stage OLS (line 1489), plain OLS (line 1490),
  LIML proxy calls `ols` (line 1531). That's 4 OLS fits on similar data.
- **Fix:** The first stage OLS `endog ~ instrument` produces `beta_hat[0] + beta_hat[1] * z`.
  The second stage is `y ~ endog_hat`. The reduced form is `y ~ z`. Both can be computed
  from the same moments: `beta_iv = cov(y, z) / cov(x, z)`. Use analytical formulas instead
  of full OLS:
  ```python
  cov_yz = np.cov(aligned["y"], aligned["instrument"])[0, 1]
  cov_xz = np.cov(signal_series, aligned["instrument"])[0, 1]
  beta_iv = cov_yz / cov_xz if cov_xz != 0 else np.nan
  ```
  This avoids 4 matrix inversions.
- **Expected gain:** 3x for IV proxy.

### 87. `_liml_proxy` computes `pinv(zmat.T @ zmat)` twice

- **File:** `analytics.py`
- **Line(s):** 1524, 1527
- **Issue:** `pz = zmat @ np.linalg.pinv(zmat.T @ zmat) @ zmat.T` (line 1524), then
  `np.linalg.pinv(xmat.T @ xmat) @ (xmat.T @ mz @ xmat)` (line 1527). The first pinv is
  on `zmat.T @ zmat` (size (k+1)×(k+1)), the second on `xmat.T @ xmat` (2×2).
- **Fix:** The projection matrix `pz` computation is expensive. Since the LIML kappa is
  often just set to 1 for just-identified designs (which is the common case with 1 instrument),
  simplify:
  ```python
  if z.shape[1] == 1:
      # Just-identified: LIML = 2SLS, kappa = 1
      return {"liml_beta": beta_iv, "liml_kappa": 1.0}
  ```
  For over-identified, decompose with QR once:
  ```python
  Q, R = np.linalg.qr(zmat)
  pz = Q @ Q.T  # project onto Z
  ```
  QR is faster and more stable than `pinv(gram) @ gram.T`.
- **Expected gain:** 2x for LIML.

### 88. `_sargan_hansen_proxy` does `ols` on residuals

- **File:** `analytics.py`
- **Line(s):** 1560
- **Issue:** `aux = ols(aligned["resid"], aligned[z.columns])` — regresses IV residuals on
  instruments. This is always O(k) with small k.
- **Expected gain:** Negligible.

### 89. `_augmented_scm` / `_generalized_scm` / `_robust_scm` each recompute `full_ret` subsets

- **File:** `analytics.py`
- **Line(s):** 1953-1990
- **Issue:** All three compute `synth = weights @ donors` and pre/post masks independently.
  The synthetic control path (line 1824-1825) already computes `synth`. These computations
  are redundant.
- **Fix:** Pass pre-computed `synth` series, `full_ret`, and pre/post masks to all SCM
  variant functions.
- **Expected gain:** 1.5x for SCM variants.

### 90. `_conformal_band` uses `.copy()` unnecessarily

- **File:** `analytics.py`
- **Line(s):** 1997
- **Issue:** `out = path[["date", "gap"]].copy()` — the subset already creates a new DataFrame.
  The `.copy()` adds an unnecessary memory copy.
- **Fix:** `out = path[["date", "gap"]].copy()` → `out = path[["date", "gap"]]`
- **Expected gain:** Negligible.

### 91. `fetch_fred_series` uses sequential merge per series

- **File:** `fetch_missing_data.py`
- **Line(s):** 123-128
- **Issue:** Loop over FRED series (up to 11), each fetching via `pdr.DataReader` (HTTP
  request), then merging into `wide` DataFrame sequentially with `.merge()`. The sequential
  merges create many intermediate DataFrames.
- **Fix:** Fetch all series in a single `pdr.DataReader` call (it accepts a list of codes):
  ```python
  all_data = pdr.DataReader(selected, "fred", start=start, end=end)
  wide = all_data.reset_index().rename(columns={"DATE": "date"})
  ```
  This avoids N separate HTTP requests and N-1 sequential merges.
- **Expected gain:** 5–10x for FRED fetching (batch request).

### 92. `fetch_public_market_proxies` downloads sequentially

- **File:** `fetch_missing_data.py`
- **Line(s):** 143-150
- **Issue:** For loop fetching `yf.Ticker(ticker).history(...)` sequentially. With 14 proxies,
  each HTTP request is ~1-3s.
- **Fix:** Use `yf.download(tickers, ...)` for batch download:
  ```python
  hist = yf.download(tickers, period=period, auto_adjust=False, group_by="ticker")
  ```
  This delegates the fetch to yfinance's optimized batch HTTP logic.
- **Expected gain:** 5–10x for market proxy fetching.

### 93. `_append_parquet` reads entire existing parquet to append a few rows

- **File:** `fetch_missing_data.py`
- **Line(s):** 47-61
- **Issue:** `pd.read_parquet(path)` on the full existing file, then `pd.concat([old, frame])`,
  then writes entire file back. For large existing parquets (market_universe can be 100MB+),
  this is extremely wasteful.
- **Fix:** Use pyarrow's native append capability or write incremental parquet fragments.
  The simplest approach: write new data as a separate parquet file (partitioned by date),
  and use `pyarrow.dataset` to read both on query:
  ```python
  new_path = path.parent / f"{path.stem}_new{path.suffix}"
  frame.to_parquet(new_path, engine="pyarrow")
  ```
  Then read both with:
  ```python
  dataset = ds.dataset([str(path), str(new_path)], format="parquet")
  ```
  This avoids ever rewriting the full file. Periodically compact in the background.
- **Expected gain:** Avoids O(100MB) I/O per append. 10–100x for append operations.

### 94. `inventory_required_missing` reads full parquet files just for metadata

- **File:** `fetch_missing_data.py`
- **Line(s):** 161-165
- **Issue:** `pd.read_parquet(CATEGORY7_MACRO, engine="pyarrow")` reads the entire macro
  parquet just to get column names (line 162). Similarly, reads entire market_universe
  parquet just to get unique tickers (line 165). These files can be hundreds of MB.
- **Fix:** Use pyarrow's metadata without reading data:
  ```python
  if CATEGORY7_MACRO.exists():
      pf = pq.ParquetFile(CATEGORY7_MACRO)
      macro_cols = {str(c).lower() for c in pf.schema_arrow.names}
  if MARKET_UNIVERSE.exists():
      pf = pq.ParquetFile(MARKET_UNIVERSE)
      # For unique tickers, read only the Ticker column
      ticker_table = pf.read(columns=["Ticker"])
      market_tickers = set(ticker_table.column("Ticker").to_pylist())
  ```
  `pq.ParquetFile` reads only the metadata (schema, row group info) — no data decompression.
- **Expected gain:** 100–1000x for inventory check (MB reads → KB reads).

### 95. `normalize_symbol` is called millions of times

- **File:** `data_loader.py`
- **Line(s):** 36-37
- **Issue:** `normalize_symbol` is called in a `.map(normalize_symbol)` on every symbol in
  every parquet load. For 1500 symbols, that's fine. For 2 million rows of OHLCV, that's
  2 million `.replace()` calls. Each call creates two new strings.
- **Fix:** Cache the normalization:
  ```python
  @lru_cache(maxsize=20000)
  def normalize_symbol(symbol):
      return str(symbol).strip().upper().replace(".", "_").replace("-", "_")
  ```
  Or use vectorized `.str.replace()` on the Series:
  ```python
  df["Ticker"] = df["Ticker"].str.strip().str.upper().str.replace(r"[.\-]", "_", regex=True)
  ```
- **Expected gain:** 5x for large parquet reads.

### 96. `_standardize_ohlcv` renames columns with comprehension and `.copy()`

- **File:** `data_loader.py`
- **Line(s):** 57, 70
- **Issue:** Line 57: `out = df.rename(columns={c: str(c).strip().title() for c in df.columns}).copy()`
  — the `.copy()` is redundant since `rename()` returns a new DataFrame. The double copy
  (one from rename, one from .copy()) wastes memory.
- **Fix:** `out = df.rename(columns={c: str(c).strip().title() for c in df.columns})` — remove
  `.copy()`.
- **Expected gain:** Avoids 1x copy of the large OHLCV DataFrame (~100MB). ~1.5x for load_market_ohlcv.

### 97. `_standardize_ohlcv` sets each column individually with `pd.to_numeric`

- **File:** `data_loader.py`
- **Line(s):** 67
- **Issue:** Loop over columns setting `out[col] = pd.to_numeric(out[col], errors="coerce")`.
  For 7 columns, this is fine but could be vectorized:
  ```python
  num_cols = ["Open", "High", "Low", "Close", "Volume"]
  out[num_cols] = out[num_cols].apply(pd.to_numeric, errors="coerce")
  ```
- **Expected gain:** Minor.

### 98. `load_signal_upload` / `load_event_upload` / `load_instrument_upload` all have nearly identical structure

- **File:** `data_loader.py`
- **Line(s):** 172-236
- **Issue:** All three functions do: check path → read CSV/parquet → normalize columns →
  normalize dates/tickers → return sorted. The logic is duplicated.
- **Fix:** Create a shared `_load_upload(path, date_col_names, ticker_col_names, value_col_names)`
  helper. Reduces code duplication and potential bugs. Not a speed issue per se, but reduces
  maintenance cost.

### 99. `load_fundamentals()` copies the entire fundamentals DataFrame

- **File:** `data_loader.py`
- **Line(s):** 246
- **Issue:** `out = df.copy()` at line 246 copies the full fundamentals parquet (potentially
  50MB+). Then line 250: `out.dropna(subset=["ticker"])` creates another copy.
- **Fix:** Dropna first, then modify:
  ```python
  df = df.dropna(subset=["ticker"])
  if df.empty:
      return pd.DataFrame(columns=["ticker"])
  df["ticker"] = df["ticker"].map(normalize_symbol)
  if "reportDate" in df.columns:
      df["reportDate"] = pd.to_datetime(df["reportDate"], errors="coerce")
  return df
  ```
  Avoid the initial `.copy()` entirely.
- **Expected gain:** 1.5x for load_fundamentals (saves one 50MB copy).

### 100. `load_fundamentals` / `latest_fundamentals` use groupby tail

- **File:** `data_loader.py`
- **Line(s):** 258-260
- **Issue:** `df.sort_values(["ticker", "reportDate"])` then `df.groupby("ticker", as_index=False).tail(1)`.
  Sorting the full fundamentals (potentially millions of rows) is expensive.
- **Fix:** Use groupby with `idxmax` to find latest reportDate per ticker without sorting:
  ```python
  if "reportDate" in df.columns:
      idx = df.groupby("ticker")["reportDate"].transform("max") == df["reportDate"]
      df = df[idx].drop_duplicates("ticker")
  ```
  Or use `df.sort_values("reportDate").drop_duplicates("ticker", keep="last")` which is
  often faster than groupby+tail.
- **Expected gain:** 2–3x for latest_fundamentals.

### 101. `load_factor_returns` merges FF and momentum DataFrames

- **File:** `data_loader.py`
- **Line(s):** 293-303
- **Issue:** Loads two CSV files, parses them, then merges. The merge is on "date" with
  `how="outer"`. For daily factor data (~2500 rows), this is fast.
- **Expected gain:** Negligible.

### 102. `monthly_factor_returns` resamples with `ME` sum

- **File:** `data_loader.py`
- **Line(s):** 310
- **Issue:** `df.set_index("date").resample("ME").sum(min_count=1)` — creates a new index.
  Fast enough.
- **Expected gain:** Negligible.

### 103. `_safe_user_path` resolves paths on every call

- **File:** `data_loader.py`
- **Line(s):** 153-169
- **Issue:** Called for every upload path check. `path.resolve()` does file system I/O to
  resolve symlinks. For upload checks, this is fine.
- **Expected gain:** Negligible.

### 104. `registry.py` imports ALL feature modules on startup

- **File:** `registry.py`
- **Line(s):** 26, 29-41
- **Issue:** `_build_registry()` at module level (line 44) imports all 10 feature modules.
  Each feature module imports from `core.analytics`, which imports `scipy`, `statsmodels`,
  `pandas`, etc. This adds ~2-3s to application startup.
- **Fix:** Lazy registry building — populate the registry on first access:
  ```python
  FEATURES: dict[str, ResearchFeature] | None = None
  def get_feature(feature_id):
      global FEATURES
      if FEATURES is None:
          FEATURES = _build_registry()
      ...
  ```
- **Expected gain:** 2–3s faster application startup.

### 105. `registry.py` `_load` tries two import paths

- **File:** `registry.py`
- **Line(s):** 19-23
- **Issue:** Each import first tries `app.services.research_v2.features.{module}`, then
  `backend.app.services.research_v2.features.{module}`. The second attempt is a full
  ModuleNotFoundError exception — Python exception handling is slow.
- **Fix:** Use `importlib.util.find_spec` to check first without exception:
  ```python
  def _load(module):
      for prefix in ["app.", "backend.app."]:
          full = f"{prefix}services.research_v2.features.{module}"
          if importlib.util.find_spec(full):
              return import_module(full)
      raise ModuleNotFoundError(module)
  ```
- **Expected gain:** Avoids one unnecessary exception per import at startup. ~0.1s faster.

### 106. `registry.py` `run_feature` calls `_load` on every call (re-imports module)

- **File:** `registry.py`
- **Line(s):** 58-62
- **Issue:** `module = _load(feature.module)` each time `run_feature` is called. Python's
  `import_module` is cached after first import, so subsequent calls are fast. But the
  `_load` function's try/except runs each time. After the first call, the module is cached
  in `sys.modules`, so `import_module` is a dict lookup — fine.
- **Expected gain:** Fine (Python module cache).

---

## TIER 5 — Code Quality / Maintainability

### 107. `float()` conversion in `number()` is safe but called everywhere

- **File:** `analytics.py`
- **Line(s):** 57-62
- **Issue:** `number()` is called hundreds of times throughout the code. Each call does
  `float(value)` then `np.isfinite()`. For values that are already floats, this is overhead.
  Not a bottleneck, but a readability issue.

### 108. `p_value_from_t` falls back to `math.erfc`

- **File:** `analytics.py`
- **Line(s):** 96-99
- **Issue:** The fallback `math.erfc(abs(t_stat) / math.sqrt(2))` lacks the degrees-of-freedom
  parameter. This is used when `scipy.stats` is not installed. The approximation is reasonable
  for large df but inaccurate for small df.

### 109. Many functions use `panel.get("payload", {}).get(...)` chains

- **File:** `analytics.py` (multiple locations)
- **Line(s):** 326, 554, 625-626, 890, 1210
- **Issue:** Accessing payload parameters through `panel.get("payload", {}).get("key")` is
  verbose and slightly slower than direct access. For inner loops (e.g., FM table), hoisting
  these values out of the loop would be cleaner and faster. Minor.

### 110. `response()` function wraps all feature outputs

- **File:** `analytics.py`
- **Line(s):** 80-93
- **Issue:** Called from every feature's `run()` function. Calls `data_inventory()` every time
  (line 81). As noted in #44, this should be cached.

---

## Summary of Top 10 Optimizations by Expected Impact

| # | Description | File:Line(s) | Est. Speedup | Type |
|---|-------------|-------------|-------------|------|
| 1 | Permutation test: batch-shuffle + simplified t-stat | 753-757 | 100-500x | Algorithmic |
| 2 | Robustness grid: split panel build from per-spec computation | 668-679 | 10x | Architecture |
| 3 | Don't recompute FM betas in rolling_coefficients | 372-373, 459-462 | 1.5-2x | Memoization |
| 4 | Avoid triple research_panel in spec builder | 1115-1118 | 3x | Architecture |
| 5 | Avoid per-market research_panel in international_replication | 1797-1808 | 8x | Pre-compute |
| 6 | Vectorize Anderson-Rubin grid (121 OLS → 1 precompute) | 1543-1551 | 100x | Vectorization |
| 7 | O(1) RSS in structural break via cumulative sums | 1767-1772 | 50-100x | Algorithmic |
| 8 | Batch OLS for GRS portfolios (N OLS → 1 matrix solve) | 392-398 | 3-5x | Vectorization |
| 9 | Resample before pivot in close_matrix (daily→monthly) | 126-131 | 5-15x | I/O |
| 10 | Pass signals to control_matrices to avoid double signal_matrix | 295-296 | 2-5x | Memoization |
