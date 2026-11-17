# 04 — Research Module Backend: Engineering Audit

**Scope.** `backend/app/services/research_v2/**` (all subpackages; statistical *correctness* of estimators is excluded by charter), `backend/app/api/research_v2*.py`, `backend/app/services/research_cache.py`, `backend/tests/test_research_v2_*.py`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/.ruff_cache`, `backend/.pytest_cache`.
**Normative standard.** `docs/studio/standards/CODE_STANDARDS.md` §§1, 7.1, 7.2, 8.1, 8.2, 8.3, 11.1, 11.2, 12, 13.1, 13.2, 14, 16, 17, 19, 20.
**Method.** Read every in-scope source file; ran the §1 backend gates verbatim against the research paths; ran `deptry`, `vulture`, and a runtime import/`AttributeError` probe. No source file was modified.
**Code size.** 8,294 lines across 49 Python modules; largest: `core/causal.py` (869), `core/data_loader.py` (580), `reports.py` (539), `core/panel.py` (497), `core/signal_lang.py` (478).
**Out of scope.** Numerical/statistical validity, frontend, and the `studio_v3` / `portfolio_v2` / `ml_v2` modules (referenced only where they duplicate research_v2 logic).

---

## Gates: exact commands and real results

All commands run from `backend/` with the project virtualenv (`.venv/bin/*`, Python 3.12.12, ruff 0.17.4).

### Ruff lint

```
$ .venv/bin/ruff check app/services/research_v2 app/api/research_v2*.py
Found 140 errors.
[*] 96 fixable with `--fix` (8 unsafe fixes available with `--fix --unsafe-fixes`).
EXIT=1
```

Rule breakdown (`--statistics`):

| Code | Count | Code | Count | Code | Count |
|---|---|---|---|---|---|
| UP006 | 49 | S112 | 6 | UP045 | 2 |
| BLE001 | 20 | UP017 | 4 | RUF100 | 2 |
| RUF046 | 17 | UP037 | 3 | PIE810 | 2 |
| I001 | 15 | RUF059 | 3 | B023 | 2 |
| UP035 | 9 | RUF022 | 1 | PLC3002 | 1 |
| | | FURB136 | 1 | F401 | 1 |
| | | B008 | 1 | B006 | 1 |

**Result: FAIL.**

### Ruff format

```
$ .venv/bin/ruff format --check app/services/research_v2 app/api/research_v2*.py tests/test_research_v2_*.py
54 files would be reformatted, 8 files already formatted
EXIT=1
```

**Result: FAIL.**

### Tests

```
$ .venv/bin/python -m pytest -q tests/test_research_v2_math.py \
    tests/test_research_v2_features.py tests/test_research_v2_data_and_api.py \
    tests/test_research_v2_projects.py tests/test_research_v2_reports.py \
    tests/test_research_v2_signals.py
66 passed, 69 warnings in 31.91s
```

Per-file collection: math 10, features 10, data_and_api 9, projects 6, reports 9, signals 22.

**Result: PASS** (0 failed, 0 skipped). Note the 69 warnings are *not* clean — see E-29 and E-31.

### Dependency hygiene

```
$ .venv/bin/deptry .
DEP001 'pandas_datareader' imported but missing from the dependency definitions
      app/services/research_v2/fetchers/fetch_missing_data.py:118
DEP002 'anyio' defined as a dependency but not used in the codebase
DEP002 'bottleneck' ... 'cryptography' ... 'orjson' ... 'python-dateutil'
DEP002 'python-multipart' ... 'tzdata' ... 'websockets'
Found 9 dependency issues. EXIT=1
```

### Dead code

```
$ .venv/bin/vulture app/services/research_v2 --min-confidence 80
app/services/research_v2/core/estimators.py:326: unused variable 't_beta'
app/services/research_v2/core/performance.py:95: unused variable 'loader_token'
app/services/research_v2/fetchers/fetch_missing_data.py:114: unused variable 'api_key'
app/services/research_v2/universes.py:53: unused variable 'mtime'
EXIT=3
```

### Runtime probe (cache)

```
$ .venv/bin/python -c "from app.services.research_cache import research_cache; research_cache.stats()"
AttributeError: 'ResearchCache' object has no attribute 'PRICE_TTL'
```

### Severity summary

| Severity | Count | Meaning applied here |
|---|---|---|
| **P0** | 3 | Research results cannot be reproduced or are lost; release-blocking. |
| **P1** | 16 | Broken behaviour, data staleness, or a correctness-adjacent defect with contained blast radius. |
| **P2** | 26 | Maintainability, typing, lint, dependency and documentation defects. |
| **Total** | **45** | |

**Verdict: the §1 backend gate does not pass.** Per §19, "A change is complete only when its applicable requirements have passed"; per §0/§19 "No P0 issue remains." Neither condition holds.

---

# P0 — Release blocking

## E-01 Add data, code and seed versions to every result's provenance

**Severity:** P0
**Standard clause:** §12 — "Data version is included in provenance." / "Relevant software and algorithm versions are included." / "Random seeds are included." / "Execution settings are included."
**Evidence:**

`audit.py:55-60` is the only provenance block written into every feature result, and it captures coverage statistics — not versions:

```python
def data_audit(panel: Any | None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """meta.data_audit: universe size and coverage by month, missing share, survivorship, PIT lag, adjustments."""
```

`data_inventory()` (referenced at `core/performance.py:102-104`) records file paths and row counts only. A search for any seed, git SHA, or package version entering `meta` returns nothing:

```
$ grep -rn "seed" app/services/research_v2/ --include=*.py | grep -i "meta\|provenance\|record"
(no output)
```

The seeds that actually drive every stochastic table are hardcoded literals in eight modules (`core/placebo.py:117 seed: int = 3`, `core/robustness.py:88 seed: int = 0`, `core/robustness.py:252 seed: int = 7`, `core/stats.py:175 seed: int = 11`, `core/decay.py:183 seed: int = 0`, `core/causal.py:356 seed: int = 5`, plus `core/diagnostics.py:103 random_state=1`).

**Impact:** A saved result cannot be re-derived. There is no record of which data snapshot produced it, which code revision ran it, or which seed generated its permutation p-values. If the market parquet is refreshed, every stored result silently becomes unattributable — the recorded statistics still look valid but describe a dataset that no longer exists. §12's "Saved runs remain interpretable after software upgrades" and "Reproduction failures identify the mismatched component" are both unimplementable as built: there is no component identifier to mismatch.

**Fix:** Add a `meta.provenance` block written by `attach_audit()` containing: (a) a content hash over the loaded source parquet paths plus `mtime`/size, (b) `git rev-parse HEAD` resolved once at process start with a `-dirty` suffix, (c) `sys.version`, `numpy.__version__`, `pandas.__version__`, `scipy.__version__`, `numba.__version__`, (d) the resolved seed set, and (e) the normalised payload. Promote `attach_audit` to own this field so no feature can forget it.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-02 Commit the job result and its artifact atomically, after the artifact exists

**Severity:** P0
**Standard clause:** §8.3 — "Results are committed atomically." / "Worker crashes leave recoverable job states." / §19 — "Jobs transition through valid states."
**Evidence:** `api/research_v2.py:75-82` marks the job `completed` in SQLite *before* the artifact is written, and the write itself is a separate non-transactional step:

```python
    result.setdefault("meta", {})["preregistered"] = store.is_preregistered(pid, payload)
    store.save_job(job_id, feature_id, payload, "completed", 1.0, result, project_id=pid)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, default=str))
    tmp.replace(path)
    return {"result_file": path.name, "bytes": path.stat().st_size}
```

**Impact:** Any failure between line 76 and line 81 — disk full, `RESULTS_DIR` on a full or read-only volume, a `default=str` object whose `__str__` raises, or process kill — leaves a job permanently `completed` with a `result` column that the API will serve as truth while `{job_id}.json` does not exist or is stale. Downstream, `GET /jobs/{job_id}` and report export consume that status. There is no reconciliation on startup, so the inconsistent state is durable. §8.3's "Orphaned jobs and artifacts are recoverable or cleaned safely" has no counterpart in this code.

**Fix:** Write the artifact first (temp file + `fsync` + `replace`), then persist the job row in a single transaction that includes the artifact path and its sha256. If the row write fails, delete the artifact. Add a startup reconciliation pass that marks `completed` rows with a missing/unreadable artifact as `failed`.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-03 Serialize artifacts with a reversible encoder instead of `default=str`

**Severity:** P0
**Standard clause:** §12 — "Strategy specifications use canonical serialization." / "Serialization order is deterministic." / "Hashes are computed from canonical representations." / "Saved runs remain interpretable after software upgrades."
**Evidence:** `api/research_v2.py:80`:

```python
    tmp.write_text(json.dumps(result, default=str))
```

The same pattern appears at the persistence boundary in `store/db.py:37`:

```python
def _dumps(v: Any) -> str | None:
    return None if v is None else json.dumps(v, default=str)
```

**Impact:** `default=str` is lossy and non-invertible. A `set` becomes `"{'a', 'b'}"`, a `tuple` becomes `"(1, 2)"`, a `pd.Timestamp` becomes `"2020-01-31 00:00:00"`, a `np.float64` becomes `"0.0123"`, and `NaN`/`Infinity` are emitted as bare `NaN`/`Infinity` — which `json.loads` accepts but most other JSON parsers reject. The bytes returned to the caller for the same run are therefore not guaranteed to equal the bytes a later reader loads. §12 requires the *opposite*: a canonical representation that makes identical results hash identically and remain interpretable. There is also no content hash anywhere on the artifact, so `bytes` (line 82) is the only integrity signal and it is not stored.

**Fix:** Introduce one canonical encoder in `core/common.py` (`_clean_value` already exists and is used by `attach_audit`) that maps Timestamps to ISO-8601 UTC, non-finite floats to `null` with a separate `nan_counts` map, numpy scalars to Python scalars, and sets to sorted lists. Use `json.dumps(..., allow_nan=False, sort_keys=True, separators=(",", ":"))` for artifacts. Store a sha256 of that canonical form alongside the artifact and expose it in `meta`.

**Confidence:** CONFIRMED
**Effort:** M

---

# P1 — Serious defects

## E-04 Fix the undefined `PRICE_TTL` reference in `ResearchCache`

**Severity:** P1
**Standard clause:** §8.2 — "Return types represent possible failures accurately." / §8.2 — "Dead code and stale compatibility paths are removed only after usage checks."
**Evidence:** `app/services/research_cache.py:168` and `:193` reference an attribute the class never defines. `__init__` declares `TTL_DAILY`, `TTL_HOURLY`, `TTL_INTRADAY`, `TTL_QUOTE`, `COMPUTE_TTL` (`:34-38`) — but no `PRICE_TTL`:

```python
            if self._is_expired(ts, self.PRICE_TTL)
```

```python
            "price_ttl_seconds": self.PRICE_TTL,
```

Runtime confirmation:

```
$ .venv/bin/python -c "from app.services.research_cache import research_cache; research_cache.stats()"
AttributeError: 'ResearchCache' object has no attribute 'PRICE_TTL'
$ .venv/bin/python -c "from app.services.research_cache import research_cache; research_cache.clear_expired()"
AttributeError: 'ResearchCache' object has no attribute 'PRICE_TTL'
```

**Impact:** Both methods are 100% broken — `clear_expired()` raises before deleting anything, so expiry-based eviction can never run, and `stats()` raises for any operator dashboard. `grep` shows no in-repo caller of either method yet, which is precisely why the defect survived: the two public maintenance entry points were never exercised. Any monitoring wiring or scheduled cleanup task added by an operator will fail on first invocation.

**Fix:** Rename to a real key. Price TTL is interval-dependent (`_ttl_for_interval`), so the correct fix is to record the TTL used at insert time — store `(data, timestamp, ttl)` — rather than re-deriving it in `clear_expired`, and report `sorted(self._interval_ttls)` in `stats()`. Add a unit test that constructs the cache, sets an entry, and asserts `stats()` and `clear_expired()` both succeed.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-05 Bound the research cache or remove it

**Severity:** P1
**Standard clause:** §11.1 — "Caches use appropriate version keys." / "Cache invalidation is tested." / "Large allocations have explicit limits." / §8.2 — "Resource cleanup is deterministic."
**Evidence:** `app/services/research_cache.py` stores price frames keyed by `(ticker, interval, start, end)` in a plain dict with no size cap and no eviction on insert:

```python
    def set_prices(self, ticker: str, interval: str, start: str, end: str, data: Any) -> None:
```

The only removal paths are `clear_all()` (`:149`) and the broken `clear_expired()` (E-04). The instance is a module-level singleton (`:199 research_cache = ResearchCache()`) shared process-wide, and it is live on the price API (`app/api/prices.py:46, 84, 212, 244, 322, 333`).

**Impact:** Every distinct `(ticker, interval, start, end)` tuple retains a full OHLCV DataFrame for the process lifetime. On a long-running server with a date-range picker, that is unbounded growth proportional to distinct ranges × tickers, measured in hundreds of MB. Because expiry never runs (E-04), even entries that *should* be stale are retained indefinitely. There is no key versioning, so a data refresh does not invalidate anything and stale prices are served until restart.

**Fix:** Add `maxsize` with LRU eviction (`cachetools.LRUCache` or an ordered dict), record the TTL at insert time, and include a dataset generation token in the key so a refresh invalidates the whole namespace. Expose hit-rate and eviction counts in `stats()`.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-06 Replace the global `build_panel` monkey-patch with explicit injection

**Severity:** P1
**Standard clause:** §8.1 — "Domain logic is separated from HTTP handling." / "Circular dependencies are avoided." / §8.2 — "No unnecessary mutable global state." / §8.3 — "Concurrent writes cannot corrupt storage."
**Evidence:** `audit.py:23-52` replaces the module-level `build_panel` symbol on eleven imported modules for the duration of a request:

```python
PANEL_MODULES = ["panel", "canonical", "diagnostics", "regime", "placebo", "decay", "zoo", "robustness", "specification", "causal", "synthetic"]
```

```python
        patched.append((mod, original))
        mod.build_panel = wrapper
```

The patch is applied and reverted by a `try/finally` context manager (`:48-52`), and `registry.run_feature` wraps the entire feature execution in it (`registry.py:65 with shared_panel() as panels:`).

**Impact:** This is process-global mutation of import-time module state used to implement request-scoped caching. It is safe only because the process pool happens to run one job per process (`max_tasks_per_child=1`, `max_workers=2`). Any of the following turns it into silent cross-request data corruption: raising `max_tasks_per_child`, adding a threaded worker, running a feature inline for a preview endpoint, or an async caller that interleaves two `shared_panel()` scopes. In those cases one request's cached panel is returned to another request that has since restored the original function, or the `finally` restores a stale `original` captured by a competing scope. The dependency graph is also inverted: `audit.py` — a reporting module — imports and mutates eleven numerical modules to observe them.

**Fix:** Pass the cache explicitly. Either give `build_panel` an optional `cache` parameter, or add a `PanelFactory` object constructed once per job and threaded through `run(payload, factory)`. If interception is genuinely required, resolve it with a context variable (`contextvars.ContextVar`) that `build_panel` reads, so no module attribute is ever reassigned.

**Confidence:** CONFIRMED
**Effort:** L

---

## E-07 Do not build the panel cache key from `json.dumps(..., default=str)`

**Severity:** P1
**Standard clause:** §12 — "Hashes are computed from canonical representations." / "Hash stability is tested when irrelevant metadata changes." / "Hash changes are tested when relevant inputs change."
**Evidence:** `audit.py:39-44`:

```python
        def wrapper(payload, *args, _orig=original, **kwargs):
            key = json.dumps([payload, args, kwargs], sort_keys=True, default=str)
            if key not in store:
                store[key] = _orig(payload, *args, **kwargs)
```

**Impact:** `default=str` collapses every non-JSON-native value to its `__str__`, so distinct payloads collide. `{"date": pd.Timestamp("2020-01-31")}` and `{"date": "2020-01-31 00:00:00"}` produce the same key. `{"x": 1}` and `{"x": "1"}` do not collide (int and str differ), but `{"start": date(2020,1,1)}` and `{"start": "2020-01-01"}` do. `float('nan')` serialises as `NaN`, which is not valid JSON and makes the key non-canonical. Because the consequence of a false match is returning another payload's panel, a collision here silently produces wrong research output with no error. The one collision the code *does* need to guard against — `payload` containing unhashable or unserialisable objects — is exactly what `default=str` conceals.

**Fix:** Hash a canonical form: normalise dates to ISO strings, sort lists where order is semantically irrelevant, reject unknown types loudly, then `hashlib.sha256` the JSON bytes. Follow E-03's encoder so the key and the artifact share one canonical representation.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-08 Stop masking audit failures as empty audit data

**Severity:** P1
**Standard clause:** §8.2 — "No silent fallback changes financial meaning." / §15 — "Numerical failures are observable." / §20(8) — "Uncertainty must remain visible. Insufficient evidence produces a limitation, not a fabricated conclusion."
**Evidence:** `audit.py:164-176` converts two analysis failures into values that *look* like successful, empty analyses:

```python
        try:
            meta["costs"] = _clean_value(cost_analysis(panel, payload))
        except Exception as exc:  # costs never fail a study
            meta["costs"] = {"available": False, "reason": str(exc)}
    if panel is not None and "return_series" not in meta:
        try:
            from .core.estimators import sort_portfolios

            meta["return_series"] = [round(float(x), 6) for x in sort_portfolios(panel, 5)["long_short"].dropna().to_numpy()]
        except Exception:
            meta["return_series"] = []
```

**Impact:** The `costs` branch keeps a reason, which is acceptable, but the `return_series` branch discards the exception entirely and writes `[]`. A consumer cannot distinguish "this study produced no long-short return series" from "`sort_portfolios` raised because the panel was degenerate". Downstream reporting and the report card treat an empty series as absent-by-design, so a real numerical failure is presented to the user as a legitimate result. The bare `except Exception` also catches `KeyboardInterrupt`-adjacent and `MemoryError` conditions on some paths. Since `attach_audit` runs on *every* feature, this is the single most-exercised silent fallback in the module.

**Fix:** Record `{"available": False, "reason": type(exc).__name__ + ": " + str(exc)}` in both branches, matching the `costs` pattern, and log at `WARNING` with the job ID. Do not catch `BaseException`. Add a test that forces `sort_portfolios` to raise and asserts the reason is present.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-09 Invalidate the market-data caches, or stop caching them

**Severity:** P1
**Standard clause:** §11.1 — "Caches use appropriate version keys." / "Cache invalidation is tested." / §8.2 — "No silent fallback changes financial meaning."
**Evidence:** Six `@lru_cache(maxsize=1)` decorators in `core/data_loader.py` guard data that changes when a fetcher runs:

```
core/data_loader.py:111  def _market_summary() -> tuple[tuple[str, ...], int]:
core/data_loader.py:142  def _raw_tickers() -> dict[str, tuple[str, ...]]:
core/data_loader.py:170  def us_equity_symbols() -> tuple[str, ...]:
core/data_loader.py:391  def static_sectors() -> pd.Series:
core/data_loader.py:506  def load_factor_returns() -> pd.DataFrame:
core/data_loader.py:527  def load_macro() -> pd.DataFrame:
```

None is ever called with `.cache_clear()` — `grep -rn "cache_clear" app/` returns nothing.

**Impact:** `us_equity_symbols()` and `available_symbols()` define the tradable universe for *every* panel. After `fetchers/fetch_missing_data.py` appends new tickers to the market parquet, the running server continues to report the old universe until restart: new symbols are invisible to `/symbols`, `/universe`, and any study, while `static_sectors()` keeps serving stale sector labels. `load_macro()` and `load_factor_returns()` are worse — FF factor and macro series are joined into every panel, so a refreshed or corrected series is silently ignored and results are computed against the previous vintage while the inventory reports the file as current. `maxsize=1` means one entry is retained with no expiry, so this is not a bounded staleness window; it is permanent for the process lifetime.

**Fix:** Use a dataset-generation token as part of the cache key (the same token from E-01), and bump it when a fetcher writes. Alternatively key on `(path, mtime, size)` — `universes._stats(source, mtime)` at `universes.py:52` already demonstrates the correct pattern in this codebase. Add a test that touches the parquet and asserts `available_symbols()` changes.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-10 Remove the silent polars-to-pandas downgrade in `_read_parquet`

**Severity:** P1
**Standard clause:** §8.2 — "No silent fallback changes financial meaning." / "Broad exception handling is justified." / §11.1 — "Peak memory is measured."
**Evidence:** `core/data_loader.py:41-56`:

```python
    if pl is not None and columns:
        try:
            # Strings as categoricals and floats as float32 before pandas sees them: the full market
            # file otherwise peaks near 3 GB while loading (millions of Python ticker strings).
            lf = pl.scan_parquet(str(path)).select(columns)
            lf = lf.with_columns(pl.col(pl.Utf8).cast(pl.Categorical), pl.col(pl.Float64).cast(pl.Float32))
            return lf.collect().to_pandas()
        except Exception:  # noqa: BLE001, S110
            pass
```

The identical `except Exception: ... pass` appears at `:106` and `:129`; further bare `except Exception` fallbacks occur at `:224`, `:384`, `:540`.

**Impact:** The comment states the fallback exists because the pandas path "peaks near 3 GB". A silent `pass` therefore means that when polars fails — a schema change, a missing optional column, a corrupt file, a categorical-cast error, or an OOM inside `collect()` — the process falls through to a path with a documented 3 GB peak, on whichever request happened to be running, with no log line. On a 2-worker pool under memory pressure this is a plausible OOM-kill with no diagnostic. Additionally the `float32` truncation is silent: when polars succeeds, `Close` and `Volume` lose precision relative to the pandas path, so the *same input file* produces numerically different panels depending on which branch ran. That is a nondeterminism source invisible to the caller.

**Fix:** Log the exception at `WARNING` with the path and column list before falling back. Catch the narrow exceptions polars raises (`pl.exceptions.ComputeError`, `pl.exceptions.SchemaError`, `OSError`) instead of `Exception`. Make the dtype policy explicit: either keep `float64` (and accept the memory) or document `float32` in `meta.data_audit.adjustments` and assert it in a test.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-11 Remove the full-file fallback from inside `_market_summary`

**Severity:** P1
**Standard clause:** §11.1 — "Large allocations have explicit limits." / "Caches use appropriate version keys." / §11.2 — "Timeouts are explicit."
**Evidence:** `core/data_loader.py:129-135`:

```python
        except Exception:  # noqa: BLE001, S110
            pass
    df = load_market_ohlcv()
    if df.empty:
        return (), 0
    counts = df.groupby("Ticker", observed=True)["Close"].count().sort_values(ascending=False)
```

**Impact:** `_market_summary()` is documented as "Small per-symbol close counts … **without loading prices**". The fallback does exactly the opposite: it materialises the entire market parquet (multi-GB, millions of rows) to compute a `groupby().count()`. And it is inlined inside an `@lru_cache(maxsize=1)`, so the peak allocation — plus the resulting DataFrame — is retained for the process lifetime on the first failure. `available_symbols()` is called from `GET /symbols` (twice, see E-22), `GET /universe`, and `parse_symbols`. A user typing in the ticker search box is therefore sufficient to trigger a multi-GB load if the polars aggregation fails.

**Fix:** Delete the fallback. Do the aggregation with polars only, and if polars is unavailable, raise a clear `RuntimeError("polars is required for symbol discovery")` rather than silently regressing to an unbounded read. Cache only the tuple of names, never the DataFrame.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-12 Apply one locking discipline to the holdout and lock stores

**Severity:** P1
**Standard clause:** §8.3 — "Concurrent writes cannot corrupt storage." / §8.2 — "Resource cleanup is deterministic." / §5.4 hold-out isolation.
**Evidence:** `core/holdout.py` implements two different persistence paths with different guarantees. `_write` (`:40-49`) uses `flock(LOCK_EX)` + `fsync` + atomic `replace`:

```python
    with tmp.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        json.dump(data, fh, indent=2, default=str)
        fh.flush()
        os.fsync(fh.fileno())
        fcntl.flock(fh, fcntl.LOCK_UN)
    tmp.replace(STORE)
```

but `_read_locks` (`:102-106`) takes no lock, and `lock_specification` (`:109-118`) writes without a lock and without `fsync`:

```python
def _read_locks() -> dict[str, Any]:
    if not LOCKS.exists():
        return {}
    with LOCKS.open() as fh:
        return json.load(fh)
```

```python
        tmp.write_text(json.dumps(locks, indent=2, default=str))
        tmp.replace(LOCKS)
```

Separately, `reserve_window` (`:60-66`) and `record_evaluation` (`:69-75`) perform a read-modify-write with the lock released between `_read()` and `_write()`, so the pair is not atomic.

**Impact:** The locked-specification store is the mechanism that decides whether a column is labelled "confirmatory" versus "exploratory" — the whole point of the pre-registration design. Concurrent `POST /locks` requests read the same `locks` dict and each write their own version, so one lock is silently lost while the API returns a hash claiming it was recorded. Worse, a `_read_locks()` racing a `tmp.replace()` can observe a partially written file — on POSIX `replace` is atomic so the *file* is never torn, but the *read-then-modify* window is unguarded, which is exactly the lost-update case. The divergence between two stores also means the two live in the same directory with inconsistent durability: `LOCKS` loses content on a crash that `STORE` survives.

**Fix:** Give the locks store the same `_read`/`_write` helpers with `flock` + `fsync`. Move read-modify-write into a single locked critical section (open, `LOCK_EX`, read, mutate, write, `fsync`, unlock). Better still, move both stores into the existing SQLite store (`store/db.py`) and let the transaction provide atomicity.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-13 Require authorization to release a protected holdout window

**Severity:** P1
**Standard clause:** §7.1 — "Every protected operation requires authenticated identity." / "Human-only operations are enforced through trusted authorization." / "User ownership is checked on every strategy, run and artifact." / §5.4 hold-out isolation.
**Evidence:** `api/research_v2.py:177-181`:

```python
@router.delete("/holdouts/{study_key:path}")
def release_holdout(study_key: str) -> Dict[str, Any]:
```

There is no `Depends`, no identity parameter, and no audit call in the handler. `app/middleware/security.py` provides rate limiting, security headers and audit logging only — it defines no authentication scheme (`grep -n "auth" app/middleware/security.py` returns only a comment about "Rate limiting on auth endpoints"). `store.db` records `reserved_at` and `evaluations` but the release is not logged.

**Impact:** The holdout is the one mechanism in the module that prevents a researcher from tuning against out-of-sample data. A single unauthenticated `DELETE` removes the protection and leaves no record of who removed it or when, so the "is this holdout still pristine" question — the stated purpose in the module docstring at `core/holdout.py:1-7` — becomes unanswerable. `{study_key:path}` also accepts embedded slashes, so the key space is attacker-chosen rather than validated.

**Fix:** Require an actor identity, record the release with actor + timestamp + reason in the store, and make release a two-step confirm (or restrict it to an admin role). Validate `study_key` against the actual set of reserved keys before deleting, and return 404 otherwise.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-14 Do not block a request thread on an unbounded `.result()`

**Severity:** P1
**Standard clause:** §11.2 — "Timeouts are explicit." / "Long jobs return a job identifier promptly." / "Failed jobs release resources." / §8.3 — "Long-running work does not block the API event loop." / "Queue capacity and concurrency are bounded."
**Evidence:** `api/research_v2.py:68-72`:

```python
def _execute(job_id: str, feature_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    store, pid = get_store(), payload.get("project_id")
    run_payload = {**payload, "_sealed_after": store.sealed_after(pid)} if pid else payload
    try:
        result = _pool().submit(run_in_worker, feature_id, run_payload).result()
```

`.result()` has no `timeout`. The pool is `ProcessPoolExecutor(max_workers=2, max_tasks_per_child=1)` (`:64`).

**Impact:** `/feature/{id}/jobs` is documented as returning a job id so the client can poll, and `GET /jobs/{id}` exists for exactly that — yet the creating request is held open for the whole computation. A study over a large universe with 5,000 bootstrap replications takes minutes; the reverse proxy or browser will time out first, and the client gets a failure while the job keeps running and eventually writes a `completed` row nobody is watching. With two workers and no queue bound, a third submission queues indefinitely behind two long jobs, holding a third connection. Cancellation (`:164`) has no path into the pool for a *running* task, so `POST /jobs/{id}/cancel` can only help jobs that have not started.

**Fix:** Submit and return `{"job_id": ...}` immediately; let the worker write the terminal state. If a synchronous mode is genuinely needed, give it an explicit timeout and a 202 fallback. Bound the queue with a semaphore and reject with 429 above capacity. Wire cancellation through `ProcessPoolExecutor`'s futures or a cooperative cancel flag checked between bootstrap replications.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-15 Make random seeds caller-settable and recorded

**Severity:** P1
**Standard clause:** §12 — "Random seeds are included." / "Repeated runs under the supported environment produce equivalent results." / §8.2 — "Named constants replace repeated unexplained literals."
**Evidence:** Every stochastic routine takes a default seed literal and no caller ever passes one. `grep -rn "seed"` in the module shows defaults only:

```
core/placebo.py:117      def _permutation_null(panel: Panel, controls: list[str], reps: int, lag: int, seed: int = 3) -> np.ndarray:
core/robustness.py:88    def build_specs(values: dict[str, list[str]], mode: str, cap: int, seed: int = 0) -> tuple[list[Spec], int]:
core/robustness.py:252   def joint_permutation_test(ev: SpecEvaluator, specs: list[Spec], reps: int, seed: int = 7) -> dict[str, Any]:
core/stats.py:86         def stationary_bootstrap_means(data: np.ndarray, reps: int, block: float | None = None, seed: int = 0) -> np.ndarray:
core/stats.py:175        def _supf_null(k: int, trim: float, reps: int = 4000, grid: int = 1000, seed: int = 11) -> np.ndarray:
core/decay.py:183        def half_life_bootstrap(rolling: pd.Series, discovery: pd.Timestamp, reps: int, block: int = 12, seed: int = 0) -> tuple[float, float]:
core/causal.py:356       def _did_placebo(long: pd.DataFrame, reps: int, real: float, seed: int = 5) -> dict[str, Any]:
```

No payload key sets a seed and no `meta` field records one (see E-01).

**Impact:** Determinism is real but accidental and undocumented: results are reproducible only because the literals never change, and a researcher cannot deliberately vary the seed to test Monte-Carlo stability — a standard robustness check that §12 implies is supported. Worse, the seed-to-routine mapping (`3` placebo, `5` DiD placebo, `7` joint permutation, `11` sup-F, `0` bootstrap) is an undocumented convention spread across five files with no constant naming it. A future edit that changes one literal silently changes published results with no diff signal at the call site.

**Fix:** Add `seed` to `normalize_config` with a documented default, thread it into every stochastic routine, and write the resolved value into `meta.provenance.seed`. Name the per-routine offsets (`SEED_PERMUTATION = 3`, `SEED_PLACEBO_DID = 5`, …) in one module so the convention is visible.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-16 Honour or remove the `loader_token` invalidation parameter

**Severity:** P1
**Standard clause:** §11.1 — "Cache invalidation is tested." / §8.2 — "Dead code and stale compatibility paths are removed only after usage checks." / "Public interfaces are documented."
**Evidence:** `core/performance.py:94-104` documents the parameter as the invalidation hook and then ignores it:

```python
@lru_cache(maxsize=1)
def cached_data_inventory(loader_token: str = "default") -> dict[str, Any]:
    """Session-level inventory cache.

    The token argument is present so callers can intentionally invalidate from
    tests or fetcher flows without changing the public analytics response shape.
    """

    from .data_loader import data_inventory

    return data_inventory()
```

`vulture` confirms the parameter is unused (`performance.py:95 unused variable 'loader_token'`).

**Impact:** `@lru_cache(maxsize=1)` means only the *first* `loader_token` is ever cached; calling with a different token evicts the previous entry only by accident of `maxsize=1`, and calling with the same token never re-reads. The documented contract — "callers can intentionally invalidate" — is false: a fetcher that refreshes the parquet and increments a token gets a re-computation only because the key changed, but any other token pattern returns the stale entry. A caller trusting the docstring will report stale inventory after a refresh. This is a public-ish interface whose documentation contradicts its behaviour.

**Fix:** Either honour the token by keying the cache on it with a larger `maxsize` and documenting that a new token means a new generation, or delete the parameter and the docstring. Given E-09, the correct fix is one generation token shared across `data_loader` and `performance`.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-17 Replace broad exception handling with specific exception types

**Severity:** P1
**Standard clause:** §8.2 — "Exceptions are specific." / "Broad exception handling is justified." / §15 — "Logs distinguish operational failures from user validation failures." / "Errors contain sufficient debugging context."
**Evidence:** 35 `except Exception` sites in scope, 12 of which swallow silently (`pass`/`continue`):

```
$ grep -rn "except Exception" app/services/research_v2 app/api/research_v2*.py --include=*.py | wc -l
35
```

Density by file:

```
      8 app/services/research_v2/core/data_loader.py
      8 app/services/research_v2/core/causal.py
      4 app/services/research_v2/reports.py
      3 app/services/research_v2/audit.py
      2 app/services/research_v2/fetchers/fetch_missing_data.py
      2 app/services/research_v2/core/decay.py
      1 each: features/merge.py, core/zoo.py, core/synthetic.py,
              core/signal_service.py, core/regime.py, core/performance.py
```

Ruff independently flags 20 `BLE001 blind-except` and 6 `S112 try-except-continue`.

**Impact:** `except Exception` at these sites catches `MemoryError`, `RecursionError`, `KeyboardInterrupt`-adjacent conditions, `numpy.linalg.LinAlgError`, `pyfixest`'s own convergence errors, and genuine programming errors (`AttributeError`, `TypeError`) indistinguishably. Several of the twelve silent sites convert a crash into a plausible-looking empty result — meaning a user sees a study succeed with missing rows rather than an error. Without per-site justification, there is also no way to tell which broad catches are deliberate ("costs never fail a study", `audit.py:170`) from which are defensive leftovers.

**Fix:** Enumerate the expected failure modes per site and catch those (`UnknownSymbolsError`, `ValueError`, `KeyError`, `pd.errors`, `pl.exceptions.*`, `sqlite3.OperationalError`). Where a broad catch is genuinely correct, keep it, add a one-line comment stating *why*, log the exception at `WARNING` with the job ID, and record `exc_info=True`. Add a lint allowlist so new `BLE001` sites need an explicit `noqa` with a reason.

**Confidence:** CONFIRMED
**Effort:** L

---

## E-18 Use the one shared `cscv_pbo` implementation

**Severity:** P1
**Standard clause:** §8.1 — "Shared financial behavior has one canonical implementation." / §20(6) — "One canonical implementation per financial concept. Reuse verified shared behavior." / §8.1 — "New abstractions solve demonstrated duplication or complexity."
**Evidence:** `reports.py:33` imports the shared implementation and `reports.py:341` then wraps it in a local function; `core/ledger_math.py:11` imports it again and defines a second wrapper at `:31`:

```
reports.py:33            from .shared.stats import cscv_pbo   (import target: app.services.shared.stats)
core/ledger_math.py:11   from app.services.shared.stats import cscv_pbo
```

Three separate `pbo_cscv`-style wrappers exist across the repository (`reports.py:341`, `core/ledger_math.py:31`, plus copies in `studio_v3` and `portfolio_v2`).

**Impact:** PBO (probability of backtest overfitting) is exactly the statistic a reviewer will compare across modules. With three wrappers, the same study can be assigned different PBO values by the research report, the ledger, and the studio depending on wrapper defaults for block count, percentile handling, and NaN policy. There is no test asserting the wrappers agree, so a divergence introduced in one module is invisible.

**Fix:** Delete the wrappers and call `app.services.shared.stats.cscv_pbo` directly from all three consumers, passing explicit arguments. Add a single test that runs one input through the report path and the ledger path and asserts identical output.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-19 Add an authentication boundary to the research API

**Severity:** P1
**Standard clause:** §7.1 — "Every protected operation requires authenticated identity." / "User ownership is checked on every strategy, run and artifact." / "Cross-user access is tested." / §7.3 — "Stored artifacts are associated with their owner."
**Evidence:** None of the four research routers declares a security dependency:

```
$ grep -n "Depends\|Security\|oauth2\|api_key" app/api/research_v2*.py
(no output)
```

`app/middleware/security.py` installs rate limiting, security headers and audit logging (`class SecurityMiddleware`, `:295`) but performs no identity check. Jobs are stored with a `project_id` (`store/db.py:19`) but no owner column, and `GET /jobs/{job_id}` (`api/research_v2.py:145`) returns any job by id.

**Impact:** Every research artifact — job payloads, results, projects, pre-registrations, holdout state, share tokens — is readable and writable by any caller who can reach the port, and `DELETE /holdouts/{key}` is an unauthenticated destructive operation (E-13). §7.1's "User ownership is checked on every strategy, run and artifact" has no implementation to check. If this service is ever exposed beyond localhost, the entire research record is open. Note: whether the deployment is intentionally localhost-only is not documented anywhere in scope, which §16 treats as a documentation gap in its own right.

**Fix:** Add an auth dependency to the router (`APIRouter(dependencies=[Depends(require_identity)])`), add an `owner` column to `jobs`/`projects`, and filter every read by owner. Document the localhost-only exception explicitly with an owner and expiry per §16, if that is the intended posture.

**Confidence:** CONFIRMED
**Effort:** L

---

# P2 — Maintainability, typing, tooling and documentation

## E-20 Stop silently skipping modules in `shared_panel`

**Severity:** P2
**Standard clause:** §8.2 — "Exceptions are specific." / "Broad exception handling is justified."
**Evidence:** `audit.py:30-34`:

```python
    for name in PANEL_MODULES:
        try:
            mod = importlib.import_module(f"app.services.research_v2.core.{name}")
        except Exception:
            continue
```

**Impact:** A renamed, deleted, or import-broken core module is silently dropped from the patch set. The feature still runs; `meta.data_audit` and `meta.costs` then silently degrade to the `panel is None` branch (`audit.py:59-60`, `"survivorship": "not handled"`), so a broken import presents as "this study does not use a formation-date signal panel". The list is hardcoded alongside `FEATURE_MODULES`, so the two can drift.

**Fix:** Catch `ImportError`/`ModuleNotFoundError` only, log at `WARNING`, and assert in a test that all eleven modules in `PANEL_MODULES` exist and expose `build_panel`.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-21 Remove the process-global database path override

**Severity:** P2
**Standard clause:** §8.2 — "No unnecessary mutable global state." / §8.1 — "Persistence logic is separated from numerical algorithms."
**Evidence:** `store/db.py:15-29`:

```python
DEFAULT_PATH = Path(BACKEND_DATA) / "research_v2.sqlite"
_path = DEFAULT_PATH
...
def set_db_path(path: Path | str) -> None:
    global _path
    _path = Path(path)
```

`Store.__init__` (`:45-46`) resolves `self.path = Path(path) if path else _path`, so every subsequently constructed `Store()` inherits whatever the last `set_db_path` call installed.

**Impact:** A test or fetcher that calls `set_db_path` mutates the storage location for the rest of the process, including any worker about to persist a real job. Because `get_store()` is a singleton, the override is invisible to callers. This is the classic reason module-global config is banned: the effect is order-dependent and unobservable from a stack trace.

**Fix:** Remove `set_db_path`; pass the path explicitly into `Store(...)`, and let tests construct their own `Store(tmp_path)`.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-22 Paginate and cache symbol search

**Severity:** P2
**Standard clause:** §11.2 — "Large responses are paginated or bounded." / "Request latency budgets are defined per endpoint."
**Evidence:** `api/research_v2.py:91-96`:

```python
    sectors = static_sectors()
    hits = [s for s in available_symbols() if s.startswith(query)] if query else []
    hits += [s for s in available_symbols() if query and query in s and s not in hits]
```

**Impact:** Two full scans of the entire symbol tuple per request, and the second builds a list comprehension with an `s not in hits` membership test — O(n·m) when `hits` is large. `available_symbols()` returns thousands of entries for the US universe. This is a per-keystroke endpoint in the UI. The result is then sliced to `limit`, so all the work is discarded.

**Fix:** Call `available_symbols()` once, iterate once, and stop after `limit` matches. Better, build the prefix index once alongside the `lru_cache` in `_market_summary` so search is a dict lookup.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-23 Record the provenance of IC-weighted formula combinations

**Severity:** P2
**Standard clause:** §12 — "Execution settings are included." / "Repeated runs under the supported environment produce equivalent results." / §16 — "Numerical assumptions are documented."
**Evidence:** `core/signal_service.py:139-150` computes full-sample ICs, derives weights, and emits a rounded expression string:

```python
    for e in exprs:
        sl.parse(e)
        ics.append(sl.rank_ic(sl.evaluate(e, ctx), ctx["returns"].shift(-1)).dropna())
    if method == "ic":
        raw = np.array([x.mean() if len(x) else 0.0 for x in ics])
        # a negative-IC signal enters with a flipped sign so every leg predicts in the same direction
        w = raw / max(np.abs(raw).sum(), 1e-12)
        parts = [f"{abs(wi):.4f} * {'-' if wi < 0 else ''}zscore({e})" for wi, e in zip(w, exprs)]
```

*(Statistical validity of using `shift(-1)` full-sample ICs is out of scope for this audit. The finding below is about provenance and serialisation only.)*

**Impact:** A data-dependent transformation is returned as an opaque formula **string** with weights rounded to four decimals, and neither the weights nor the sample used to fit them are recorded anywhere in `meta`. The returned formula is therefore not equal to the numbers that produced it (4 dp rounding), and a later re-run of `combine` on refreshed data yields a *different* formula with no way to tell that the previous result used different weights. §12 requires that identical inputs produce identical results *and* that the settings producing a result be recorded; here the settings are silently baked into a string.

**Fix:** Return the weight vector alongside the expression (`{"expr": ..., "weights": [...], "method": "ic", "fitted_on": {"start": ..., "end": ..., "n_periods": ...}}`) and store it in `meta`. Emit weights with full float precision or state the rounding explicitly.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-24 Stop advertising a numba disk cache that cannot hit

**Severity:** P2
**Standard clause:** §11.1 — "Numba compilation time is distinguished from steady-state runtime." / "Hot paths are profiled before optimization."
**Evidence:** `core/performance.py:80-91`:

```python
            _FM_JIT = njit(cache=True)(_fm_kernel_py)
```

The pool that executes it is created with `max_tasks_per_child=1` (`api/research_v2.py:64`), so each job runs in a brand-new spawned process.

**Impact:** `cache=True` writes compiled artifacts to `__pycache__` so a *later process* can reuse them; that does work across processes. But the comment's intent — amortising compile time over jobs — is undermined by the interaction: the first call in every fresh worker pays full JIT compile latency on top of the study, and the module-level `_FM_JIT is None` guard never helps because the global is per-process. The comment at `:81` ("Compile the kernel on first use so importing this module does not load numba") is accurate; the `cache=True` claim is not measured. There is no benchmark distinguishing compile from steady-state anywhere in the repo, which §11.1 requires before an optimisation is accepted.

**Fix:** Measure and record: log compile time separately (wrap the first call and log elapsed). If compile cost is material relative to typical job latency, move to a long-lived worker process without `max_tasks_per_child=1`. Either way, add the measurement to `meta` so the claim is backed.

**Confidence:** SUSPECTED (the cache does persist across processes; the *claim* of amortisation is what is unverified)
**Effort:** S

---

## E-25 Replace the frozen feature-manifest cache

**Severity:** P2
**Standard clause:** §11.1 — "Caches use appropriate version keys." / §8.2 — "No unnecessary mutable global state."
**Evidence:** `registry.py:27-33`:

```python
@lru_cache(maxsize=1)
def features() -> dict[str, ResearchFeature]:
```

`feature_manifest()` (`:48`) is served by `GET /features` (`api/research_v2.py:85-87`).

**Impact:** The manifest is materialised from eleven module-level constants on first request and never refreshed. This is harmless in production (the constants do not change at runtime) but it means a plugin or test that patches `INPUTS`/`OUTPUTS` sees the original set — the classic `lru_cache`-in-tests trap. It also permanently retains eleven module objects, which `run_feature` then re-imports through `_load`, relying on `sys.modules` rather than on the cached manifest.

**Fix:** Cache the manifest explicitly with a `_manifest` module variable and an internal `_reset()` used by tests, or drop the cache — building eleven small dicts is microseconds.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-26 Remove the import-time mutation of another module's global

**Severity:** P2
**Standard clause:** §8.1 — "Circular dependencies are avoided." / "Each module has a clearly defined responsibility." / §8.2 — "No unnecessary mutable global state."
**Evidence:** `core/signal_lang.py:32-34`, executed at import time:

```python
# Flow items below mix quarterly and annual rows; keep annual only (shared helper reads this set).
dl.FLOW_FIELDS.update({"Operating Cash Flow", "Free Cash Flow", "Capital Expenditure", "EBITDA", "Research And Development", "Selling General And Administration", "Interest Expense", "Cost Of Revenue", "Cash Dividends Paid", "Pretax Income"})
```

**Impact:** Importing the formula language mutates `data_loader`'s shared configuration. Import order therefore determines the behaviour of `point_in_time_fundamental` for every other consumer — a module that never touches `signal_lang` gets a different flow-field set depending on whether something else imported it first. This is invisible in tests that import everything and order-dependent in production, and it makes `data_loader` non-composable.

**Fix:** Move the flow-field set into `data_loader` as the single definition (or a shared `core/fields.py`) and have `signal_lang` read it. No `.update()` on foreign module state.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-27 Replace the `threading.local` look-ahead side channel

**Severity:** P2
**Standard clause:** §8.2 — "No unnecessary mutable global state." / "Public interfaces are documented." / §8.1 — "Each module has a clearly defined responsibility."
**Evidence:** `core/signal_lang.py:419-421` and `:440-445`:

```python
_GUARD = threading.local()
```

```python
def set_lookahead(v: dict[str, Any] | None) -> None:
    _GUARD.value = v


def get_lookahead() -> dict[str, Any]:
    return getattr(_GUARD, "value", None) or {"flagged": False}
```

`registry.py:66-68` reads it back after the feature returns:

```python
        result = _load(module).run(payload)  # load only this feature, not the whole manifest
        from .core.signal_service import attach_lookahead

        result = attach_lookahead(result)  # meta.lookahead for signal_expr runs
```

**Impact:** The look-ahead verdict is communicated through an ambient thread-local rather than a return value. Consequences: `get_lookahead()` returns a *stale* dict from a previous run if the current run never called `set_lookahead` — `{"flagged": False}` is the fallback, so a missing computation is indistinguishable from a clean verdict. It only works because the worker is single-threaded; inside an async or pooled caller it silently reads another job's state. And it is the one field a reviewer most needs to trust.

**Fix:** Return the look-ahead result from the evaluation and pass it explicitly to `attach_lookahead`. If a context is unavoidable, use `contextvars.ContextVar` (which is per-task, not per-thread) and default to `{"flagged": None, "reason": "not evaluated"}` so absence is visible.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-28 Stop dropping failed RDD specifications silently

**Severity:** P2
**Standard clause:** §8.2 — "No silent fallback changes financial meaning." / §20(8) — "Uncertainty must remain visible."
**Evidence:** `core/causal.py:660-690`, five occurrences:

```python
    for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        try:
            sensitivity.append({"bandwidth_multiple": mult, **est(y, x, cl, c, h * mult, fuzzy)})
        except Exception:
            continue
```

and the same pattern for placebo cutoffs, donut holes, and covariate-adjusted estimates.

**Impact:** The sensitivity, placebo and donut tables exist to show a result is robust. If `est()` fails for a specific bandwidth or covariate — degenerate cluster counts, a singular design matrix, a too-thin side — the row vanishes and the surviving table looks *cleaner* than the data warrants. Because the tables are rendered as-is (`tables = {...}`, `:697-701`), the user cannot tell that, say, 3 of 6 bandwidth multiples failed. The selection is also non-random: failures cluster at the narrowest bandwidths, which are exactly the ones a reader cares about.

**Fix:** Append `{"bandwidth_multiple": mult, "available": False, "reason": str(exc)}` instead of `continue`, and surface a `n_failed` count in the table. Catch specific numerical errors.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-29 Bind the loop variables captured by the leave-one-out lambda

**Severity:** P2
**Standard clause:** §8.2 — "Numeric conversions are explicit." / "Comments explain invariants, assumptions and unusual decisions."
**Evidence:** `core/causal.py:775-776`:

```python
                total, count = block.sum(axis=1, min_count=1), block.notna().sum(axis=1)
                z[members] = block.apply(lambda col: (total - col.fillna(0)) / (count - col.notna().astype(int)).replace(0, np.nan))
```

Ruff reports this twice:

```
B023 Function definition does not bind loop variable `total`
B023 Function definition does not bind loop variable `count`
```

**Impact:** `total` and `count` are rebound as the `members` loop iterates, and the lambda closes over the *names*, not the values. The code is currently correct only because `DataFrame.apply` invokes the lambda eagerly before the next iteration. Any change to a deferred/lazy evaluation path — `.apply` on a polars frame, `.map_partitions`, or moving the lambda out of the immediate call — silently produces an instrument built from the wrong industry block. That is a look-ahead-free but badly wrong instrument.

**Fix:** Bind explicitly: `lambda col, total=total, count=count: ...`. Or compute the expression vectorised without a lambda.

**Confidence:** CONFIRMED (lint-confirmed; runtime-safe today)
**Effort:** S

---

## E-30 Give failures a taxonomy so the API can return 4xx instead of 500

**Severity:** P2
**Standard clause:** §7.2 — "Error responses are structured." / "Internal stack traces are not exposed to clients." / §8.2 — "Return types represent possible failures accurately."
**Evidence:** Failures are raised as bare builtins throughout — `ValueError("Set the treatment date.")` (`core/synthetic.py:72`), `ValueError(f"performance_metric must be one of ...")` (`core/decay.py:50`), `KeyError(f"Unknown Research V2 feature {feature_id}")` (`registry.py:43`). The API only translates one exception type (`api/research_v2.py:73-74`):

```python
    except UnknownSymbolsError as exc:
        raise ValueError(str(exc)) from exc
```

**Impact:** A user-supplied invalid parameter (`scm_variant must be one of ...`) and an internal numerical failure both surface as an unhandled exception. Without an exception handler mapping them, FastAPI returns a 500 for what is a 422-class validation error, so clients cannot distinguish "fix your input" from "the server broke". §7.2 also asks that internal traces not reach clients, which depends entirely on the global handler's configuration rather than on the domain code.

**Fix:** Introduce a small hierarchy (`ResearchValidationError`, `ResearchDataError`, `ResearchComputationError`), raise those from the core, and register one `exception_handler` mapping validation→422, data→409/422, computation→500 with a correlation id only.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-31 Fix the 140 lint errors

**Severity:** P2
**Standard clause:** §1 Backend gate — "Ruff lint passes." / §19 — "Ruff lint | PASS / FAIL".
**Evidence:** `Found 140 errors.` across 19 rule codes; 96 mechanically fixable. The two largest classes are `UP006` (49 — `List`/`Dict`/`Tuple` from `typing` where `list`/`dict`/`tuple` are used) and `BLE001` (20 — see E-17), then `RUF046` (17 unnecessary `int()` casts), `I001` (15 unsorted import blocks), `UP035` (9 deprecated `typing` imports).

Representative `RUF046` sites are numeric conversions the standard explicitly calls out (§8.2 "Numeric conversions are explicit"). Representative `UP006` sites are pervasive:

```
app/services/research_v2/core/synthetic.py:18   from typing import Any
app/api/research_v2.py:45                       payload: Dict[str, Any] = Field(default_factory=dict)
```

**Impact:** The gate is red, so the module cannot satisfy §19 and cannot be shipped under §0. Beyond the gate, `UP006`/`UP035`/`I001` are pure noise that hides the six findings that matter (`BLE001`, `B023`, `B006`, `B008`); a reviewer cannot see the signal. `RUF046` matters because `int()` on a float silently truncates — 17 sites where a numeric boundary is handled implicitly rather than explicitly, exactly what §8.2 forbids.

**Fix:** Land `ruff check --fix` (96 of 140) and `ruff format` (54 files) as one mechanical commit with no behaviour intent, then fix the remaining 44 by hand, starting with `BLE001`, `B023`, `B006`, `B008`, `RUF046`. For `RUF046`, replace `int(x)` with `int(round(x))` or the correct pandas/numpy conversion and state the rounding rule in a comment.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-32 Format the codebase

**Severity:** P2
**Standard clause:** §1 Backend gate — "Ruff formatting passes." / §17 — "Generated artifacts are intentional."
**Evidence:** `.venv/bin/ruff format --check app/services/research_v2 app/api/research_v2*.py tests/test_research_v2_*.py` → `54 files would be reformatted, 8 files already formatted`.

**Impact:** 87% of the module is unformatted. This makes every future diff noisy (a one-line change produces a whole-file reformat once someone finally runs the formatter), it makes review of the real changes in this audit effectively impossible, and it means no pre-commit hook can be added without a single giant formatting commit. §17's "Diff is reviewed before committing" is defeated by a codebase where any edit may reformat its file.

**Fix:** One isolated `ruff format` commit touching only whitespace, merged immediately before any functional change, then a pre-commit hook to keep it clean.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-33 Commit the ruff configuration

**Severity:** P2
**Standard clause:** §1 Verification integrity — "CI runs on a clean checkout." / "Local and CI environments use compatible dependency versions." / "Commands actually executed are recorded."
**Evidence:** `backend/pyproject.toml` (62 lines) contains only `[project]` and `[dependency-groups]` — no `[tool.ruff]`, `[tool.ruff.lint]`, or `[tool.pytest.ini_options]`. No `ruff.toml` or `.ruff.toml` exists anywhere under the repo root:

```
$ ls -a backend | grep -i ruff
.ruff_cache
$ find . -maxdepth 3 -name "ruff.toml" -o -maxdepth 3 -name ".ruff.toml"
(no output)
```

Ruff nevertheless resolved 814 enabled rules, including rules outside its default set (`S112`, `BLE001`, `RUF046`, `FURB136`, `PLC3002`, `PIE810` are not enabled by default), and it applied exclusions that make the run pass on some files.

**Impact:** The gate that produced "140 errors" is not reproducible from the repository. On a clean checkout with a stock `ruff 0.17.4`, the same command yields a *different* (much smaller) rule set and therefore a different verdict — so the report cannot be reproduced by CI or a reviewer, violating §1's "CI runs on a clean checkout" and "Local and CI environments use compatible dependency versions". The `noqa` comments in the source (`# noqa: BLE001, S110`, `# noqa: BLE001, S110` and many bare `# noqa: BLE001`) imply a config existed at authoring time that was never committed.

**Fix:** Add `[tool.ruff]` with `target-version = "py312"`, an explicit `[tool.ruff.lint] select` list, `[tool.ruff.lint.per-file-ignores]`, and `[tool.pytest.ini_options] filterwarnings`. Commit it. Then re-run the gate and record the result as the new baseline.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-34 Gitignore the tool caches

**Severity:** P2
**Standard clause:** §17 — "Generated artifacts are intentional." / "Only intended files are staged."
**Evidence:** `backend/.ruff_cache` exists on disk. The repository `.gitignore` ignores `.pytest_cache/` at line 156 and `__pycache__/` at 67 and 235, but never `.ruff_cache`:

```
$ grep -n "ruff_cache\|pytest_cache\|__pycache__" .gitignore
67:__pycache__/
156:.pytest_cache/
235:backend/__pycache__/
```

Neither cache directory is currently tracked (`git status` is clean for both), so this is a latent trap rather than a present violation.

**Impact:** A single `git add -A` or `git add backend` stages a multi-MB binary cache directory into the repository, where it then churns on every lint run and pollutes every subsequent diff. The omission sits next to an entry for the sibling cache (`.pytest_cache/`), which is what makes it a defect rather than a preference.

**Fix:** Add `.ruff_cache/` (and `**/.ruff_cache/`) to `.gitignore` alongside `.pytest_cache/`.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-35 Constrain the numerical dependency range

**Severity:** P2
**Standard clause:** §14 — "Package versions are locked." / "Integrity checks are preserved." / "Transitive dependency risks are reviewed."
**Evidence:** `pyproject.toml:3-46` declares 46 runtime dependencies, every one with a lower bound only, and no upper bound on the numerical stack:

```toml
requires-python = ">=3.12"
dependencies = [
    "anyio>=3.7.0",
    ...
    "numpy>=1.24.0",
    ...
    "pandas>=2.0.0",
    ...
    "scipy>=1.10.0",
```

`httpx` is declared twice (`httpx>=0.24.0` at runtime, `httpx>=0.28.1` in the dev group), and `apprise>=2.2.0` is appended out of alphabetical order at the end.

**Impact:** `uv.lock` (155 packages, committed) does pin the resolution, so installs are reproducible *today* — this is not a live reproducibility break. But §14 asks for locked versions as a property of the project, and with `numpy>=1.24.0` and `pandas>=2.0.0` unbounded, a `uv lock --upgrade` silently moves the entire numerical stack. Pandas 3.x and NumPy 2.x are both breaking-release major versions, and this module's panel construction (`pct_change(fill_method=None)`, `resample("ME")`, `float32` casts, `np.datetime64("NaT")`) is exactly the kind of code that breaks on such a move. The duplicate `httpx` declaration also means the dev group's tighter bound can be silently relaxed by the runtime one depending on resolver order.

**Fix:** Add upper bounds on the numerics (`numpy>=1.24,<3`, `pandas>=2.0,<4`, `scipy>=1.10,<2`, `numba>=0.57,<1`) matching the ranges actually tested. Remove the duplicate `httpx`. Sort the list. Add `deptry` and `pip-audit` to the §1 security gate.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-36 Declare `pandas_datareader` and drop the eight unused dependencies

**Severity:** P2
**Standard clause:** §14 — "New dependencies solve a documented need." / "Dependency removal includes import and build checks." / "Development-only packages do not unnecessarily enter production bundles."
**Evidence:** `deptry .` reports 9 issues (1× DEP001, 8× DEP002), quoted in full under Gates above. The undeclared import is at `fetchers/fetch_missing_data.py:118`:

```python
        df = pdr.DataReader(code, "fred", start=start).reset_index().rename(columns={"DATE": "date", code: col})
```

**Impact:** `fetch_fred_series` is the only path that can produce the macro/regime series, and `pandas_datareader` is not installed by the lockfile. The function raises `RuntimeError("Install pandas_datareader to fetch FRED series")` at runtime, so the documented refresh path is dead by default — the guard at `:115-117` was written to catch this, which shows it was known and never resolved. Meanwhile `anyio`, `bottleneck`, `cryptography`, `orjson`, `python-dateutil`, `python-multipart`, `tzdata`, `websockets` are each pinned into every install with no import in the tree. `python-multipart` and `websockets` are declared for FastAPI's upload and WebSocket support, so those two are likely intentional but undeclared-as-intentional; the rest are pure weight.

**Fix:** Keep FastAPI's implicit requirements (`python-multipart`, `websockets`) and annotate them with a comment or move them to a `server` extra. Remove `bottleneck`, `orjson`, `python-dateutil`, `tzdata`, `anyio`, `cryptography` after verifying no dynamic import. Add `pandas_datareader` to the dependency list, or delete `fetch_fred_series` if the FRED path is out of scope. Re-run `deptry` in the §1 gate so this cannot regress.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-37 Remove or correctly mark the dead parameters

**Severity:** P2
**Standard clause:** §8.2 — "Dead code and stale compatibility paths are removed only after usage checks." / "Public interfaces are documented." / §8.1 — "Public interfaces are documented."
**Evidence:** `vulture --min-confidence 80` reports 4 hits. Two are genuinely dead:

`core/estimators.py:326` — `t_beta` is accepted and never read:

```python
def weak_identification(betas: pd.DataFrame, factor: str, t_beta: pd.Series | None = None) -> dict[str, Any]:
```

`fetchers/fetch_missing_data.py:114` — `api_key` is accepted and never read, even though FRED requires a key for any non-trivial usage:

```python
def fetch_fred_series(api_key: str | None = None, series: Iterable[str] | None = None, start: str = "1990-01-01") -> dict[str, int]:
```

**Impact:** `weak_identification` is a public API whose signature promises a t-statistic input that the implementation ignores. A caller that carefully supplies `t_beta` gets a result computed without it — and the Kan-Zhang/Kleibergen test it documents is precisely a t-statistic-based test. `fetch_fred_series(api_key=...)` likewise looks like it authenticates and does not, which will produce a confusing rate-limit failure rather than an auth failure.

Note: the other two vulture hits are **not** defects and should be suppressed rather than fixed. `universes.py:53 _stats(source: str, mtime: float, recent_days: int = 63)` uses `mtime` deliberately as an `lru_cache` key (correct cache-busting pattern), and `performance.py:95 loader_token` is E-16.

**Fix:** Delete `t_beta` from `weak_identification` or wire it into the check. Delete `api_key` or pass it through to `pdr.DataReader` (which accepts `api_key`). Add `# noqa`-equivalent comments (`# vulture: ignore`) plus a rationale for the two intentional cache-key parameters, and add vulture to CI with a committed allowlist.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-38 Break up the long research functions

**Severity:** P2
**Standard clause:** §8.1 — "Each module has a clearly defined responsibility." / "New abstractions solve demonstrated duplication or complexity." / §20(9) — "Every feature must justify its complexity."
**Evidence:** AST measurement of functions ≥80 lines:

```
 132 core/causal.py:136      run_did
 123 core/causal.py:444      run_event_study
 105 core/diagnostics.py:29  run_diagnostics
  96 core/canonical.py:33    canonical_from_panel
  94 core/causal.py:740      run_iv
  91 core/regime.py:76       run_regime
  83 core/synthetic.py:62    run_synthetic
  80 core/causal.py:628      run_rdd
```

**Impact:** `run_did` at 132 lines mixes eleven responsibilities in one scope: symbol parsing, monthly aggregation, cohort construction, window bounds, characteristic extraction, propensity matching, balance tables, model fitting, placebo, Callaway–Santanna, Goodman-Bacon and table assembly. Every one of these reads and writes the same local namespace (`y`, `months`, `cohort`, `treated_units`, `never`, `units`), so a change to cohort construction can silently alter what the placebo loop sees. `run_iv` compounds this by defining a 60-line closure (`est`, `:649`) inside it. None of these functions is unit-testable in isolation, which is why the test suite exercises them only end-to-end.

**Fix:** Extract the phases into named helpers with explicit arguments and return values (`_build_cohort(events, months)`, `_windows(cohort, pre, post)`, `_assemble_tables(...)`). Each extraction is behaviour-preserving and should land with a golden-number test pinning the output before and after.

**Confidence:** CONFIRMED
**Effort:** L

---

## E-39 Replace magic literals with named constants

**Severity:** P2
**Standard clause:** §8.2 — "Named constants replace repeated unexplained literals." / §16 — "Numerical assumptions are documented."
**Evidence:** Unnamed thresholds define the research universe and its quality filters:

`core/panel.py:130` — minimum history to keep a symbol, with no constant and no comment:
```python
    close_m = close_m.loc[:, close_m.notna().sum() >= 24]
```

`core/panel.py:133` — the bad-print filter, whose comment states a different number than the code:
```python
    returns = returns.where(returns.abs() < 3)  # drop split/bad-print artefacts (>300% in a month)
```

`core/panel.py:243,245` — silent defaults inside `normalize_config`:
```python
        "lookback_days": int(payload.get("lookback_days") or 3650),
        "min_assets": int(payload.get("min_assets") or 30),
```

`reports.py:19-21` — grading thresholds, which are at least partly documented:
```python
REPORT_FEATURES = ["01", "02", "03", "04", "05", "08", "11"]
BANDS = [("A", 85), ("B", 70), ("C", 55), ("D", 40)]
T_THRESHOLDS = (3.0, 2.5, 2.0, 1.5)  # A, B, C, D: Harvey-Liu-Zhu t = 3.0 bar down to 1.5
```

Further examples: `core/causal.py:436 _parse_window` default `(-12, 12)`, `core/statistics` block lengths, `core/regime.py:19-31` condition thresholds duplicated between `CONDITIONS` (human strings) and `CONTINUOUS` (keys) — the `15/25/35` VIX band appears in the description string only, not as a constant.

**Impact:** `panel.py:130`'s `>= 24` is the single most consequential undocumented constant in the module: it decides which symbols enter every study. It is not exposed as a payload key, not reported in `meta.data_audit`, and its value (24 monthly observations) is not justified anywhere. Two researchers running the same signal cannot tell whether a differing universe came from their choice or from this floor. `panel.py:133` is worse — the comment says ">300%" and the code drops `abs() < 3`, i.e. keeps exactly 300% and drops below, so the boundary semantics are stated incorrectly. `min_assets: 30` and `lookback_days: 3650` are `or`-defaulted, so a caller passing `0` gets the default rather than zero — a classic falsy-default bug in a numeric boundary (§8.2 "Integer and floating-point boundaries are checked").

**Fix:** Hoist to named module constants (`MIN_MONTHS_HISTORY = 24`, `MAX_ABS_MONTHLY_RETURN = 3.0`, `DEFAULT_LOOKBACK_DAYS = 3650`, `DEFAULT_MIN_ASSETS = 30`), report the resolved values in `meta.data_audit`, and replace `payload.get(k) or default` with `payload.get(k, default)` (or an explicit `is None` check) so `0` is respected.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-40 Give the signal library a typed schema

**Severity:** P2
**Standard clause:** §8.2 — "Public functions have meaningful type annotations." / §8.1 — "Public interfaces are documented." / §8.2 — "Numeric conversions are explicit."
**Evidence:** `core/signal_library.py:8-70` defines 55 anomalies as unlabelled 7-tuples, then zips them into dicts by position:

```python
_L = [
    # momentum and reversal
    ("mom_12_1", "Momentum 12-1", "momentum", "delay(close, 1) / delay(close, 12) - 1", "Jegadeesh and Titman (1993)", 1993, 1),
```

```python
LIBRARY = [{"id": a, "name": b, "category": c, "formula": d, "citation": e, "year": f, "expected_sign": g} for a, b, c, d, e, f, g in _L]
```

The whole file is served verbatim by `GET /signals` (`api/research_v2_signals.py:57`) and consumed by `signal_service` via `BY_ID`.

**Impact:** The tuple order is a hidden contract. Inserting a field, or transposing `year` and `expected_sign` (both integers — `1993` and `1` are adjacent and both valid in either slot), produces a library that still parses and still passes the current test, because `tests/test_research_v2_signals.py:84` only asserts `item["expected_sign"] in (1, -1)` — and `1993` is not in `(1, -1)`, so that one case would catch a swap of *those* two, but nothing catches a swap of `year` with any other integer-like field. There is no type check that `formula` parses: the test at `:81-84` checks presence, not validity.

**Fix:** Replace tuples with a frozen dataclass or `TypedDict` (`SignalSpec(id, name, category, formula, citation, year, expected_sign)`), and extend the existing test to `signal_lang.parse(spec.formula)` every entry, asserting each formula compiles against the operator registry.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-41 Move the operator script out of the service package

**Severity:** P2
**Standard clause:** §8.1 — "Each module has a clearly defined responsibility." / §8.2 — "Dead code and stale compatibility paths are removed only after usage checks."
**Evidence:** `fetchers/fetch_missing_data.py:177-180`:

```python
if __name__ == "__main__":
    print(inventory_required_missing())
```

The module also performs import-time constants and, per E-36, imports an undeclared dependency at call time (`:115-118`).

**Impact:** This is an operator CLI living inside an importable service package. `python -m app.services.research_v2.fetchers.fetch_missing_data` is the only entry point, it has no argument parsing (the FRED key from E-37 cannot be supplied), it prints a dict rather than JSON, and it is not covered by any test. Because it sits in the package it is reachable from production import paths, so a `import` of the fetchers subpackage pulls in the module-level path constants and the FRED series map.

**Fix:** Move to `backend/scripts/fetch_missing_data.py` with `argparse` (`--fred-key`, `--series`, `--market-proxies`, `--json`) and keep `fetchers/` as a pure library.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-42 Derive the report feature list from the registry

**Severity:** P2
**Standard clause:** §8.1 — "Each module has a clearly defined responsibility." / §8.2 — "Named constants replace repeated unexplained literals." / §8.1 — "Existing callers are identified before shared interfaces change."
**Evidence:** `reports.py:19` hardcodes a subset of feature ids:

```python
REPORT_FEATURES = ["01", "02", "03", "04", "05", "08", "11"]
```

`registry.py:11` independently hardcodes the module list:

```python
FEATURE_MODULES = [*(f"feature_{i:02d}" for i in range(1, 10)), "feature_11"]  # the spec defines no Feature 10
```

The report set omits `06`, `07` and `09` even though those feature modules exist and run.

**Impact:** Two independent enumerations of "which features exist" that already disagree in intent: the registry offers nine features, the report grades seven, and the omission of 06/07/09 is not explained by any comment or constant. Adding Feature 12 requires edits in both files, and forgetting `REPORT_FEATURES` produces a silently incomplete report card rather than an error. The `range(1, 10)` + explicit `"feature_11"` construction is itself fragile — it encodes "no feature 10" as arithmetic rather than data.

**Fix:** Make `REPORT_FEATURES` a declared property on each feature (`REPORTS = True/False`) or a single ordered list in `registry.py` that both `FEATURE_MODULES` and `reports.py` consume. Replace `range(1,10)` with an explicit tuple of ids.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-43 Reconcile the module's status documents with the gate results

**Severity:** P2
**Standard clause:** §16 — "Checklist completion reflects actual evidence." / "Documentation does not claim untested functionality is verified." / §19 — "A checked box is evidence of completed verification, never a substitute for it."
**Evidence:** `app/services/research_v2/WORK_LEFT.md` states:

```
Status 2026-09-29: backend is complete (see DONE.md)
```

`app/services/research_v2/DONE.md` makes architectural claims that the code contradicts — notably lazy imports and no `lru_cache` on large frames, against six `@lru_cache(maxsize=1)` market-data readers (E-09) and a `load_market_ohlcv()` full-scan fallback inside one of them (E-11).

The measured state on the same tree is 140 lint errors across 19 rule codes, 54 of 62 files unformatted, and 9 dependency issues.

**Impact:** A new contributor reading `WORK_LEFT.md` concludes there is nothing to do and does not run the gate. The document is dated and has no owner or review condition, which §16 requires for any standing claim ("Temporary exceptions have an owner and expiration or review condition"). This is the mechanism by which the lint debt reached 140 errors: the status file asserted completion, so nobody checked.

**Fix:** Replace the status line with the actual gate output and a date, or delete `WORK_LEFT.md`/`DONE.md` and let the gate be the status. If the DONE.md claims are to be kept, either make them true or annotate each with the file and line that violates it.

**Confidence:** CONFIRMED
**Effort:** S

---

## E-44 Close the test gaps in the failure paths

**Severity:** P2
**Standard clause:** §13.1 — "Every nontrivial branch has an appropriate test." / "Failure paths are tested." / "Boundary conditions are tested." / §13.2 — "Removing future bars does not change earlier signals." / "Identical inputs produce identical results."
**Evidence:** 66 tests pass, and `tests/test_research_v2_math.py` is genuinely good — it pins golden values and includes look-ahead assertions, which is the strongest coverage in the suite. But the following in-scope units have no direct test:

- `app/services/research_cache.py` — zero tests, which is why the `PRICE_TTL` `AttributeError` (E-04) survived.
- `store/db.py`, `store/ledger.py`, `store/seal.py` — no direct tests; `test_research_v2_projects.py` exercises the store only through the API.
- `audit.py::cost_analysis` and `attach_audit`'s failure branches (E-08) — no test forces the exception.
- `core/decay.py::half_life_bootstrap` — the bootstrap path is not exercised.
- `core/robustness.py::joint_permutation_test` — not exercised.
- `holdout.py::release_window` / `lock_specification` — no concurrency or lost-update test (E-12).
- Report export/rendering (`reports.py` grading, `REPORT_FEATURES`) — asserted for shape, not for the A–F mapping.

No property-based tests exist anywhere in the module, so §13.2's "Removing future bars does not change earlier signals" and "Identical inputs produce identical results" are asserted only by hand-written cases in one file.

**Impact:** Every P1 finding in this audit except E-06/E-19 sits in a unit with no direct test — that is not a coincidence. The suite verifies the happy path end-to-end, which is why 66 tests pass while `stats()` raises `AttributeError` on first call. The missing failure-path tests are the direct cause of the silent-fallback defects surviving (E-08, E-10, E-11, E-28): a test that forced one exception per fallback would have caught each.

**Fix:** Add, in priority order: (1) a cache test asserting `stats()`/`clear_expired()` work; (2) one test per `attach_audit` failure branch asserting the reason is recorded; (3) a truncation test that drops the last N months and asserts earlier formation-date signals are byte-identical (§13.2); (4) a repeat-run determinism test asserting identical output for identical payload. Prefer extending the four existing test files over creating new ones.

**Confidence:** CONFIRMED
**Effort:** M

---

## E-45 Add a type-check gate

**Severity:** P2
**Standard clause:** §8.2 — "Public functions have meaningful type annotations." / "Return types represent possible failures accurately." / §1 Backend gate.
**Evidence:** `pyrefly>=1.4.1` is declared in the dev dependency group (`pyproject.toml:53`) but there is no `[tool.pyrefly]` section, no CI step, and no recorded run. The annotation coverage is broad and mostly modern (`dict[str, Any]`, `| None`), yet `Dict`, `List` and `Optional` coexist with them (`typing` imports remain at `api/research_v2.py:11`, `core/synthetic.py:18`), and 49 `UP006` violations show the two styles are interleaved within single files.

**Impact:** A type checker is installed, pinned, and never run — so the 140 lint errors are the only static signal, and annotation mistakes are invisible. Concretely, `weak_identification(..., t_beta: pd.Series | None = None)` (E-37) is a type-correct but semantically dead parameter that a checker cannot catch, while genuinely wrong annotations (a function declaring `-> dict[str, Any]` that can raise, everywhere) are exactly what §8.2 asks to be made accurate. There is no payoff from the declared dev dependency at present.

**Fix:** Add `[tool.pyrefly]` with the project roots, run `pyrefly check app/services/research_v2 app/api/research_v2*.py` in the §1 gate, and record the baseline error count. Fix in batches, starting with the public feature entry points (`run(payload) -> dict[str, Any]`).

**Confidence:** CONFIRMED
**Effort:** M

---

# Cross-cutting observations

**The P1 cluster is single-rooted.** Six findings (E-06, E-07, E-08, E-09, E-11, E-16) share one cause: process-global caches with no version key. The fix for E-09 — a dataset-generation token threaded through the cache keys — also resolves E-07 (canonical key), E-11 (delete the fallback rather than cache it), and E-16 (honour the token). E-06 is the structural prerequisite for all of them. Sequencing: E-06 → E-09/E-16 → E-07 → E-08/E-11.

**The P2 cluster is one formatting commit plus one config commit.** E-31, E-32, E-33 and E-34 dissolve into two mechanical changes (`ruff format`, `ruff check --fix`) and one 30-line config file. Once landed, the remaining 44 lint errors and every future one become visible.

**What the audit did not find.** No SQL injection: every `store/db.py` query is parameterised (`c.execute(sql, args)` throughout). No path traversal in the core: uploads validate extensions (`api/research_v2.py:108-110`) and storage roots are module constants. No committed secrets: `gitleaks` was not available in this environment, so this is unverified rather than cleared — flagged here because §1's security gate was not executable.

**Evidence that could not be obtained.** `pyrefly check` was not run (no config, no recorded baseline, and the run would report thousands of pre-existing findings from other modules). A concurrency test of `shared_panel` was not attempted, so E-06's corruption risk is reasoned from the code's structure (module-attribute reassignment inside a request scope) rather than demonstrated — it is marked CONFIRMED for the *design* and the thread-safety consequence is stated as a risk, not an observed failure.
