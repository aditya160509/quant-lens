# Speed Optimizations for Studio v2

## Implementation status

- [x] Optional accelerators are declared in `backend/requirements.txt`: Numba, Bottleneck, Joblib, ORJSON, and SortedContainers.
- [x] Parquet loading uses projected columns when the source schema supports them, cached full-universe fallback for title-case snapshots, LRU caches, categorical tickers, one-read batch loading, and vectorized return construction.
- [x] Monte Carlo uses Numba kernels for GARCH likelihood, stationary bootstrap, GARCH paths, and path metrics, with Bottleneck aggregate statistics and pure-Python fallbacks.
- [x] Backtest rolling ADV/volatility uses Bottleneck when available, and lambda percentiles are cached per date and reset per simulation.
- [x] Liquidity calibration uses one batch load, cached ticker metrics, and Joblib threading when available.
- [x] Metrics and CPCV Sharpe/PBO calculations use NumPy array operations with explicit finite and zero-variance handling.
- [x] Factor IC folds use batch OHLCV loading and optional threaded Joblib parallelism.
- [x] Kernel AST/compile results and dependency traversal are cached; linter AST and date-pattern parsing are cached.
- [x] Lineage uses ORJSON when available and caches repeated searches; trial best lookup uses SortedContainers when available.
- [x] Universe and Explorer use batch data and Bottleneck rolling/Garman-Klass calculations.
- [x] Router DataFrame/Series conversion uses pandas’ vectorized JSON encoder with ORJSON decoding when available.
- [x] Optimizer TPE remains the sampling authority, with configurable Optuna `n_jobs` for safe parallel trial execution; perturbation grids are NumPy-mesh based.

Optional accelerators always have a fallback. The implementation deliberately uses vectorized NumPy for CPCV purging rather than JIT-compiling datetime comparisons, because it avoids timestamp-casting risks while providing the same asymptotic behavior for the configured path sizes.

## Summary

| File | Bottleneck | Technique | Est. Speedup |
|------|-----------|-----------|-------------|
| `shared/monte_carlo.py` | GARCH MLE loop, 5000 bootstrap paths | `numba.jit(parallel=True)`, bottleneck | 10-50x |
| `backtest/engine.py` | Rolling ADV/sigma per ticker, lambda percentile | `bottleneck.move_mean/move_std`, lambda cache | 2-5x |
| `shared/data_loader.py` | Repeated parquet reads, groupby pct_change | `@lru_cache`, vectorized NumPy returns, `pd.Categorical` | 3-10x |
| `shared/liquidity.py` | 500-ticker OHLCV loop for calibration | `joblib.Parallel`, batch OHLCV | 5-10x |
| `backtest/metrics.py` | DSR/PSR/PBO across CPCV paths | Vectorized numpy, bottleneck nanmedian | 2-3x |
| `optimizer/cpcv.py` | C(N,k) combinatorics, Sharpe per path | `itertools` split generation, vectorized NumPy purging/metrics | 5-20x |
| `factors/evaluator.py` | Purged K-Fold IC loop, per-ticker OHLCV | `joblib.Parallel` across folds, batch OHLCV | 3-10x |
| `factors/diagnostics.py` | Half-life decay scan, correlation matrix | `bottleneck.move_corr`, `numba.jit` on scan | 3-5x |
| `optimizer/search.py` | Optuna trials (50-500), perturbation grid | Optuna `n_jobs`, vectorized NumPy grid | 2-4x |
| `shared/data_loader.py` | Individual `get_ohlcv` calls (O(N) parquet reads) | Batch + `@lru_cache` on parquet load | 10-50x |
| `algorithm_lab/kernel.py` | Dependency graph BFS, AST parsing | `@lru_cache` on AST results, adjacency cache | 2-3x |
| `algorithm_lab/linter.py` | AST walking on large files | Pre-compiled `re.compile`, AST node cache | 2-3x |
| `backtest/lineage.py` | JSON serialization, run search/filter | `orjson` for fast serialization, indexed search | 3-5x |
| `robustness/tests.py` | Grid search and perturbation stress loops | `joblib.Parallel` with thread-pool fallback | 4-8x |
| `optimizer/verdict.py` | Trial registry iteration | `sortedcontainers.SortedDict` | 2-3x |
| `data_studio/universe.py` | Snapshot per ticker in loop | `get_ohlcv_batch` + vectorized filter | 5-10x |
| `data_studio/explorer.py` | Garman-Klass vol per ticker | Bottleneck rolling aggregates, vectorized | 5-10x |
| `router.py` | JSON serialization of large DataFrames | `orjson` + pre-encoded dtypes | 2-5x |

## Per-File Analysis

### `shared/monte_carlo.py`

**Bottleneck:** GARCH(1,1) negative log-likelihood evaluated 3000x per MLE call. Stationary bootstrap sampling 5000 paths of length N. Sorting/traversing return arrays in pure Python loops.

**Fix:** `numba.jit(nopython=True)` on the NLL inner loop, `numba.jit(parallel=True)` on bootstrap path generation and path metric computation. `bottleneck.nanmedian`/`nanmean` for timing perturbation stats. `joblib.Parallel` for embarrassingly parallel GARCH path generation.

**Before:**
```python
def _garch_negative_log_likelihood(transformed, values):
    omega = exp(transformed[0])
    alpha = sigmoid(transformed[1])
    beta = sigmoid(transformed[2]) * (0.999 - alpha)
    variance = var(values)
    total = 0.0
    for value in values:  # pure Python loop
        diff = value - mean
        variance = omega + alpha * diff**2 + beta * variance
        total += 0.5 * (log(variance) + diff**2 / variance)
    return total
```

**After:**
```python
@numba.jit(nopython=True)
def _garch_nll_numba(transformed, values):
    ...  # same logic, JIT-compiled to LLVM
```

```python
@numba.jit(nopython=True, parallel=True)
def _bootstrap_paths_numba(values, length, n_paths, n, block):
    for p in prange(n_paths):  # parallel
        for i in range(length):
            ...
```

**Note:** All numba functions wrapped in `try/except ImportError` with `HAVE_NUMBA` flag. Pure Python fallbacks preserved.

**Speedup:** 10-50x on GARCH MLE, 5-10x on bootstrap, 10-20x on path metrics.

**Risk:** low — numba functions are pure numerical, no side effects.

---

### `backtest/engine.py`

**Bottleneck:** Rolling ADV (63-day) and sigma (21-day) computed per ticker via pandas `.rolling().mean()`. `_lambda_for_order` recomputes ADV percentiles, scanning all tickers each call.

**Fix:** `bottleneck.move_mean`/`move_std` for O(1) per-window rolling instead of O(window). Cache lambda percentiles by date so they're computed once per date, not once per order.

**Before:**
```python
frame["adv"] = frame["dollar_volume"].rolling(63, min_periods=1).mean()
frame["sigma"] = frame["close"].pct_change().rolling(21, min_periods=2).std() * sqrt(252)
```

**After:**
```python
dv_arr = frame["dollar_volume"].to_numpy(dtype=float, na_value=nan)
adv_arr = bn.move_mean(dv_arr, window=63, min_count=1)  # bottleneck
frame["adv"] = adv_arr
```

**Before (lambda per order):**
```python
def _lambda_for_order(self, ticker, current_date):
    # scans all tickers on every order
    adv_values = {...}  # N ticker lookups per order
    percentile = sum(1 for v in adv_list if v < adv) / len(adv_list)
```

**After:**
```python
def _lambda_for_order(self, ticker, current_date):
    key = (current_date,)  # cache key
    if key not in self._lambda_cache:
        # compute percentile array once per date
        ...
    # reuse cached result
```

**Speedup:** 2-5x on date loop, 5-10x on lambda computation.

**Risk:** low — bottleneck has pure Python fallback via `_HAS_BOTTLENECK` flag.

---

### `shared/data_loader.py`

**Bottleneck:** Each `get_ohlcv(ticker)` call re-reads the full 282 MB parquet. Repeated calls from engine/evaluator/universe cause N parquet reads. Groupby `pct_change` in `get_returns` is slow on large DataFrames.

**Fix:** `@lru_cache(maxsize=2)` on `_load_universe()` so the parquet is read once. `@lru_cache(maxsize=512)` on ticker-level slices. `@lru_cache(maxsize=1)` on macro and fundamentals. `bottleneck.diff`/`shift` for fast groupby returns. `pd.Categorical` on tickers for faster groupby.

**Before:**
```python
def _load_universe():
    return pd.read_parquet(UNIVERSE_PATH)

def get_ohlcv(ticker):
    frame = _load_universe()
    return frame[frame["ticker"] == ticker]  # full scan every call
```

**After:**
```python
@lru_cache(maxsize=2)
def _load_universe():
    frame = pd.read_parquet(UNIVERSE_PATH, columns=_UNIVERSE_COLUMNS)
    frame["ticker"] = pd.Categorical(frame["ticker"])  # faster groupby
    return frame

@lru_cache(maxsize=512)
def _load_ticker(symbol):
    frame = _load_universe()
    return frame.loc[frame["ticker"] == symbol].copy()  # cached result
```

**Speedup:** 3-10x on repeated `get_ohlcv` calls. 2-3x on `get_returns` via bottleneck.

**Risk:** low — `@lru_cache` is stdlib, memory-bound only (512 ticker slices at ~2MB each ~1GB).

---

### `shared/liquidity.py`

**Bottleneck:** `calibrate` loops 500 tickers calling `get_ohlcv` individually.

**Fix:** Use `get_ohlcv_batch` to load all 500 tickers in one parquet read. Use `joblib.Parallel` for independent per-ticker calibration.

**Before:**
```python
def calibrate(self, tickers):
    for ticker in tickers:
        frame = get_ohlcv(ticker)  # 500 parquet reads
        ...
```

**After:**
```python
def calibrate(self, tickers):
    batch = get_ohlcv_batch(tickers)
    for ticker, frame in batch.items():  # 1 parquet read
        ...
```

**Speedup:** 5-10x.

**Risk:** low.

---

### `backtest/metrics.py`

**Bottleneck:** `compute_pbo` applies Sharpe per column across all CPCV paths (potentially 1000+ paths). `compute_all` recomputes `_clean` multiple times.

**Fix:** Pre-compute cleaned returns once. Use vectorized numpy percentile instead of pandas apply.

**Before:**
```python
def compute_pbo(self, cpcv_paths):
    values = cpcv_paths.apply(self.compute_sharpe, axis=0)
```

**After:**
```python
def compute_pbo(self, cpcv_paths):
    if isinstance(cpcv_paths, pd.DataFrame):
        values = cpcv_paths.to_numpy(dtype=float)
        sharpes = np.nanmean(values, axis=0) / np.nanstd(values, axis=0, ddof=1) * sqrt(252)
```

**Speedup:** 2-3x.

**Risk:** low — same math, no dependencies.

---

### `optimizer/cpcv.py`

**Bottleneck:** C(N,k) split generation for N=20, k=5 yields 15,504 combinations. Each split requires purging/embargo logic. DSR computed across all paths.

**Fix:** `numba.jit` on split generation loop. Pre-allocate arrays for CPCV path storage.

**Before:**
```python
for split in self.generate_splits(n_groups, k_test):
    train_indices = np.setdiff1d(...)
    # purge in pure Python
    for i in train_indices:
        if purge_start <= dates[i] <= purge_end:
            ...
```

**After:**
```python
@numba.jit(nopython=True)
def _purge_train_numba(train_idx, test_start, test_end, horizon, embargo):
    keep = np.ones(len(train_idx), dtype=np.bool_)
    for i in range(len(train_idx)):
        date = train_idx[i]
        if (date >= test_start - horizon) and (date <= test_end + embargo):
            keep[i] = False
    return train_idx[keep]
```

**Speedup:** 5-20x.

**Risk:** medium — numba on datetime arithmetic needs careful cast to int64 timestamps.

---

### `factors/evaluator.py`

**Bottleneck:** Purged K-Fold IC loops per fold then per date within fold — O(folds * dates). `FactorExpressionEvaluator.load_data` calls `get_ohlcv` per ticker in a loop.

**Fix:** `joblib.Parallel` across folds (independent). `get_ohlcv_batch` for expression evaluation.

**Before:**
```python
def compute_purged_kfold_ic(self, scores, forward_returns, n_folds, embargo, horizon):
    for test_idx in folds:
        for current_date in test_dates:
            factor = scores.loc[current_date]
            target = forward_returns.loc[current_date]
            ic = spearman_rank_correlation(...)
```

**After:**
```python
def compute_purged_kfold_ic(self, scores, forward_returns, n_folds, embargo, horizon):
    def fold_ic(test_idx):
        # ... compute IC for one fold, return float
        pass
    with Parallel(n_jobs=-1) as pool:
        fold_ics = pool(delayed(fold_ic)(idx) for idx in folds)
```

**Speedup:** 3-10x.

**Risk:** low — folds are independent.

---

### `factors/diagnostics.py`

**Bottleneck:** Half-life decay scan tests 20+ candidate lambdas, each requiring O(T) EWMA computation. Correlation matrix on 40 factors × 500 days.

**Fix:** `bottleneck.move_corr` for fast rolling correlation. `numba.jit` on EWMA scan loop.

**Before:**
```python
def compute_half_life(self, series, max_lag=60):
    for lag in range(1, max_lag + 1):
        decay = series.ewm(halflife=lag).mean()
        correlation = series.corr(decay)
```

**After:**
```python
@numba.jit(nopython=True)
def _ewma_corr_scan(values, max_lag):
    best_lag, best_corr = 1, -inf
    for lag in range(1, max_lag + 1):
        decay = _ewma(values, lag)
        corr = np.corrcoef(values, decay)[0, 1]
        if corr > best_corr:
            best_lag, best_corr = lag, corr
    return best_lag
```

**Speedup:** 3-5x.

**Risk:** low.

---

### `optimizer/search.py`

**Bottleneck:** 50-500 Optuna trials are sequential but each trial is independent. Perturbation grid generates N^K combinations.

**Fix:** Evaluate each trial in parallel via `joblib.Parallel`. Vectorize grid generation.

**Before:**
```python
study.optimize(objective, n_trials=config.trial_budget)  # sequential
```

**After:**
```python
def _evaluate_trial(params, config):
    ...  # independent trial evaluation

with joblib.Parallel(n_jobs=-1) as pool:
    results = pool(joblib.delayed(_evaluate_trial)({...}, config) for _ in range(budget))
```

**Note:** Optuna does not natively support parallel trials from a single process. Use `joblib` with a custom sampling loop instead, or use Optuna's `Storage` for distributed trials.

**Speedup:** 2-4x on 4-core, scales with cores.

**Risk:** medium — parallel trials need careful RNG isolation. Not suitable when trials share state.

---

### `algorithm_lab/kernel.py`

**Bottleneck:** `get_dependents` BFS on variable graph recomputed on every call. AST parsing on every `execute_code_sync`.

**Fix:** Cache BFS results with `_dep_cache` dict, invalidated on variable add/remove. `@lru_cache` on AST parse for repeated code.

**Before:**
```python
def get_dependents(self, cell_id):
    dependents = set()
    # BFS every call, O(V+E)
    queue = [cell_id]
    while queue:
        current = queue.pop(0)
        ...
    return dependents
```

**After:**
```python
def get_dependents(self, cell_id):
    if cell_id in self._dep_cache:
        return self._dep_cache[cell_id].copy()
    # BFS once, cache result
    self._dep_cache[cell_id] = dependents.copy()
    return dependents
```

**Speedup:** 2-3x.

**Risk:** low.

---

### `algorithm_lab/linter.py`

**Bottleneck:** AST walking on large files (1000+ lines). Regex matching on every `.values` call.

**Fix:** `re.compile` all patterns once at module level. `@lru_cache` on AST parse results.

**Before:**
```python
def check_shift_without_ffill(self, code):
    if re.search(r"\.shift\(-?\d+\)", code):  # re-compile every call
        ...
```

**After:**
```python
_SHIFT_PATTERN = re.compile(r"\.shift\(-?\d+\)")  # compiled once

def check_shift_without_ffill(self, code):
    if _SHIFT_PATTERN.search(code):
        ...
```

**Speedup:** 2-3x on large files.

**Risk:** low.

---

### `backtest/lineage.py`

**Bottleneck:** JSON serialization of large run records on every `record_run`. `search_runs` loads all runs and filters in Python.

**Fix:** `orjson` for 2-5x faster serialization. Pre-compute index on searchable fields.

**Before:**
```python
self.storage_path.write_text(json.dumps({"runs": [...]}, default=str))
```

**After:**
```python
try:
    import orjson
    payload = orjson.dumps({"runs": [asdict(r) for r in runs]})
except ImportError:
    payload = json.dumps({"runs": [asdict(r) for r in runs]}, default=str)
```

**Speedup:** 3-5x on serialization.

**Risk:** low — orjson has pure JSON fallback.

---

### `robustness/tests.py`

**Bottleneck:** Grid search evaluates N^K param combinations sequentially. Timing perturbation runs 4000 simulations sequentially.

**Fix:** `ThreadPoolExecutor` already present. Use `ProcessPoolExecutor` for CPU-bound grid search. Vectorize timing perturbation simulation.

**Before:**
```python
def run_grid_parallel(self, param_grid, config):
    rows = [evaluate(params) for params in param_grid]  # sequential
```

**After:**
```python
def run_grid_parallel(self, param_grid, config):
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = [pool.submit(evaluate, params) for params in param_grid]
        rows = [f.result() for f in as_completed(futures)]
```

**Speedup:** 4-8x.

**Risk:** medium — ProcessPoolExecutor requires pickleable closures. ThreadPoolExecutor (current) is a safe fallback.

---

### `optimizer/verdict.py`

**Bottleneck:** Trial registry iteration to find best/worst trials. `get_search_path` returns all trials for a session.

**Fix:** `sortedcontainers.SortedDict` keyed by trial value for O(log N) best/worst lookup instead of O(N) scan.

**Before:**
```python
def get_best_trial(self, session_id):
    trials = self._trials.get(session_id, [])
    return max(trials, key=lambda t: t.value)  # O(N)
```

**After:**
```python
from sortedcontainers import SortedDict

def __init__(self):
    self._sorted: Dict[str, SortedDict] = {}

def add_trial(self, session_id, trial):
    if session_id not in self._sorted:
        self._sorted[session_id] = SortedDict()
    self._sorted[session_id][trial.value] = trial  # O(log N)

def get_best_trial(self, session_id):
    sd = self._sorted.get(session_id)
    return sd.peekitem(-1)[1] if sd else None  # O(1)
```

**Speedup:** 2-3x on large registries (1000+ trials).

**Risk:** low — requires pip install sortedcontainers, fallback to O(N) scan.

---

### `data_studio/universe.py`

**Bottleneck:** `_snapshot` calls `get_ohlcv` per ticker in loop (500 reads). Filters are applied via pandas on each call.

**Fix:** `get_ohlcv_batch` for single parquet read. Vectorize filter operations instead of looping.

**Before:**
```python
def _snapshot(self, tickers, when):
    for ticker in tickers:
        frame = get_ohlcv(ticker, when, when)  # 500 reads
        ...
```

**After:**
```python
def _snapshot(self, tickers, when):
    batch = get_ohlcv_batch(tickers, when, when)  # 1 read
    for ticker in tickers:
        frame = batch.get(ticker, DataFrame())  # zero-copy lookup
        ...
```

**Speedup:** 5-10x.

**Risk:** low.

---

### `data_studio/explorer.py`

**Bottleneck:** Garman-Klass volatility loops per ticker. Anomaly detection via rolling z-score on all 500 tickers.

**Fix:** `numba.jit` on GK formula. `bottleneck.move_mean`/`move_std` for fast rolling z-score.

**Before:**
```python
def compute_garman_klass(self, ohlc):
    return ((ohlc.high - ohlc.low)**2 / 2 - ...).rolling(21).mean()
```

**After:**
```python
@numba.jit(nopython=True)
def _garman_klass_numba(high, low, close, open_):
    n = len(high)
    factor = 0.5 * (high - low)**2 - (2 * math.log(2) - 1) * (close - open_)**2
    return np.sqrt(np.nanmean(factor) * 252)
```

**Speedup:** 5-10x.

**Risk:** low.

---

### `router.py`

**Bottleneck:** `_jsonable` recursively converts DataFrames via `to_dict(orient="records")` and replaces NaN one by one. Large results (500 tickers × 5 years) take seconds.

**Fix:** `orjson` with custom serialization for numpy/pandas types. Pre-convert DataFrames to column-oriented format.

**Before:**
```python
def _jsonable(value):
    if isinstance(value, pd.DataFrame):
        return value.replace({np.nan: None}).to_dict(orient="records")
    if isinstance(value, np.floating) and not np.isfinite(value):
        return None
```

**After:**
```python
try:
    import orjson

    def _jsonable(value):
        return orjson.dumps(value, default=_serialize_numpy).decode()
except ImportError:
    def _jsonable(value):
        # original pandas-based serialization
        ...

def _serialize_numpy(obj):
    if isinstance(obj, (np.ndarray, pd.Series)):
        return obj.tolist()
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
        return str(obj)
    raise TypeError
```

**Speedup:** 2-5x on large payloads. 1.5x on typical payloads.

**Risk:** low — orjson fallback to json.

---

## Cross-Cutting Patterns

### 1. Batch Loading Over Per-Ticker Loops

Replace all per-ticker `get_ohlcv(ticker)` loops with `get_ohlcv_batch(tickers)`.

**Files:** `engine.py`, `evaluator.py`, `liquidity.py`, `universe.py`, `explorer.py`

**Pattern:**
```python
# Before
for ticker in tickers:
    frame = get_ohlcv(ticker, start, end)

# After
batch = get_ohlcv_batch(tickers, start, end)  # 1 parquet read
for ticker, frame in batch.items():
    ...
```

### 2. LRU Cache on Pure Functions

Cache results of deterministic, expensive operations.

**Files:** `data_loader.py`, `kernel.py`, `engine.py`, `linter.py`

**Pattern:**
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_pure_function(args):
    return result
```

### 3. bottleneck for Rolling Operations

Replace `pandas.rolling().mean()/std()` with `bottleneck.move_mean/move_std` for 2-5x speedup.

**Files:** `engine.py`, `explorer.py`, `diagnostics.py`, `data_loader.py`

**Pattern:**
```python
import bottleneck as bn
arr = series.to_numpy(dtype=float, na_value=nan)
result = bn.move_mean(arr, window=63, min_count=1)
```

### 4. numba.jit on Numerical Hot Loops

JIT compile pure-numpy inner loops where pandas overhead dominates.

**Files:** `monte_carlo.py`, `cpcv.py`, `explorer.py`, `diagnostics.py`

**Pattern:**
```python
try:
    import numba
    @numba.jit(nopython=True)
    def hot_loop(values):
        for i in prange(len(values)):  # parallel
            ...
except ImportError:
    def hot_loop(values):
        for i in range(len(values)):
            ...  # pure Python fallback
```

### 5. joblib.Parallel for Independent Work

Use `joblib.Parallel(n_jobs=-1)` for embarrassingly parallel loops.

**Files:** `tests.py`, `evaluator.py`, `search.py`, `engine.py`

**Pattern:**
```python
from joblib import Parallel, delayed

results = Parallel(n_jobs=-1)(
    delayed(worker_fn)(arg) for arg in args
)
```

### 6. Pre-allocate Arrays Over List Append

Replace `rows.append(...)` with `np.empty` pre-allocation in hot paths.

**Files:** `monte_carlo.py`, `cpcv.py`, `engine.py`

**Pattern:**
```python
# Before
rows = []
for i in range(N):
    rows.append(compute(i))

# After
rows = np.empty(N, dtype=float)
for i in range(N):
    rows[i] = compute(i)
```

## Dependency Changes

Add to `requirements.txt`:

```txt
# Speed optimizations (optional — pure Python fallbacks provided)
numba>=0.58.0          # GARCH MLE, bootstrap, CPCV, Garman-Klass, EWMA scan
bottleneck>=1.3.7      # Rolling mean/std, nanmedian, diff/shift
joblib>=1.3.0          # Parallel loops for grid search, folds, calibration
orjson>=3.9.0          # Fast JSON serialization for API responses
sortedcontainers>=2.4.0 # Trial registry best/worst O(log N) lookup
```

All libraries are optional — every optimization has a `try/except ImportError` fallback to the original pure-Python/code path. The platform runs correctly without any of them, just slower.
