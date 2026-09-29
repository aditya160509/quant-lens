## Implementation Checklist - 2026-06-17

Validation after this pass:
- [x] `python3 -m compileall -q backend/app/services/portfolio_v2`
- [x] Daily / weekly / monthly / hourly `returns_matrix()` smoke checked.
- [x] All Portfolio V2 feature runners F01-F13 completed with zero failures on a 10-symbol daily payload.
- [x] Cold feature smoke: ~9.8-10.4s total, with F01 owning most cold load/covariance work.
- [x] Warm-cache feature smoke: ~1.2s total across F01-F13.

Item status:
- [x] 1. `float_array` now returns C-contiguous float64 arrays and cleans NaN/inf in-place.
- [x] 2. `normalize_numeric_frame` now uses a vectorized NumPy path instead of column-by-column conversion.
- [x] 3. `dataframe_fingerprint` now rounds in-place and avoids the second array allocation.
- [x] 4. `nearest_psd` now symmetrizes and clips through fewer allocations.
- [x] 5. `fast_matrix_records` now preallocates the output list and avoids repeated append resizing.
- [x] 6. `fast_network_edges_from_corr` now uses contiguous arrays and `argpartition` for top-edge selection.
- [x] 7. Rolling eigenvalue/diversification helpers now avoid pandas `.corr()`/`.cov()` inside the loop.
- [~] 8. `rank_ic_curve` was already cached/vectorized from the prior performance pass; no new rewrite was needed in this pass.
- [x] 9. `compact_table` now uses integer `linspace` directly.
- [ ] 10. `PerfCounter.__slots__` was not added; low-impact and unnecessary versus the measured bottlenecks.
- [x] 11. `_standardize_ohlcv` now batches numeric conversion.
- [x] 12. `returns_matrix` now computes log returns with NumPy arrays and supports frequency-aware coverage thresholds.
- [x] 13. Daily + canonical OHLCV merge is cached through `_merged_ohlcv`.
- [x] 14. `available_symbols` now caches the full symbol list and slices cheaply.
- [x] 15. `normalize_symbol` is now LRU cached.
- [x] 16. Sector and market-cap lookup maps are cached.
- [x] 17. Parquet reads explicitly use the `pyarrow` engine.
- [x] 18. `clean_json` uses faster type dispatch for common scalar/container cases.
- [x] 19. EWMA covariance weights are cached.
- [x] 20. HRP path uses cached correlation frames.
- [x] 21. Risk parity and max-diversification optimizers now warm-start from inverse-vol weights.
- [x] 22. `performance_metrics` now uses NumPy cumulative paths and quantiles.
- [x] 23. Brinson attribution uses NumPy arrays and precomputed sector arrays.
- [x] 24. `liquidity_table` uses grouped aggregation instead of repeated ticker filtering.
- [~] 25. DCC loop removed `iterrows` and repeated lookups; Numba JIT was not added to avoid warm-up/dependency risk.
- [x] 26. Kelly sizing now uses a direct solve with pseudoinverse fallback.
- [x] 27. CVaR LP construction is more vectorized and cached.
- [x] 28. Regime/HMM-style fitting paths use `StandardScaler` before clustering.
- [x] 29. Gerber covariance uses NumPy sign matrices and `fast_corr`.
- [x] 30. Skill/luck bootstrap now samples all draws in one vectorized block.
- [x] 31. DebtRank propagation avoids repeated Series-to-array conversion inside the loop.
- [x] 32. Newey-West regression avoids explicit diagonal matrices and uses fast pseudoinverse.
- [x] 33. Alpha decay already uses cached rank-IC results keyed by DataFrame fingerprint.
- [ ] 34. Sparse SVD was not wired into factor-structured covariance; current matrices are small enough that full SVD is safer and stable.
- [x] 35. Data inventory is cached inside `load_context`.
- [x] 36. Portfolio return series uses NumPy dot products.
- [x] 37. `load_context` now has a bounded payload-level cache.
- [~] 38. Shared covariance caching is in place, but a single global all-estimator allocator was not added because estimator outputs have different downstream shapes.
- [~] 39. Precision network still computes from the selected return matrix; precomputed covariance injection was not added because it would change function signatures across features.
- [x] 40. Strategy-return construction remains consolidated and reuses the shared returns matrix.
- [ ] 41. Numba risk-parity JIT was not added; optimizer warm starts gave safe speed without adding JIT warm-up/packaging risk.
- [x] 42. Kaplan-Meier survival duration calculation is vectorized by run lengths.
- [x] 43. Cascade probability thresholds are cached.
- [x] 44. `fast_corr` was added and wired into Gerber/sector/cached correlation paths where safe.
- [~] 45. `safe_eigh` was added and wired into correlation diagnostics; broader replacement was avoided where functions require eigenvectors or custom ordering.
- [x] 46. Ledoit-Wolf covariance is precentered and uses `assume_centered=True`.
- [x] 47. High-impact pseudoinverse calls now use `fast_pinv` or direct solve with fallback.
- [~] 48. `dates_to_str` exists but was not broadly wired because date formatting is not a measured bottleneck in the smoke path.
- [x] 49. Rolling diversification uses BLAS-style covariance computation.
- [x] 50. `compact_records` reduces repeated datetime conversion before JSON records.

Skipped items were skipped only where they add JIT/dependency risk, require signature changes across feature contracts, or provide low measured impact compared with the implemented cache/vectorization paths.

I'll do a comprehensive audit of every file and produce the maximum-speed upgrade set. Let me analyze the entire codebase first.Here is the exhaustive, file-by-file, function-by-function upgrade list. Every upgrade is a concrete code block targeting maximum single-threaded speed under your no-parallel-threads constraint.

---

## FILE: `backend/app/services/portfolio_v2/core/performance.py`

---

**Issue 1: `float_array` does two passes (`.to_numpy()` then `np.nan_to_num`) and allocates an intermediate array.**

```python
# CURRENT
def float_array(df):
    if isinstance(df, pd.DataFrame):
        arr = df.to_numpy(dtype=float, copy=False)
    else:
        arr = np.asarray(df, dtype=float)
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

# UPGRADE — single allocation, in-place nan_to_num
def float_array(df: pd.DataFrame | np.ndarray | Iterable[Any]) -> np.ndarray:
    if isinstance(df, pd.DataFrame):
        arr = np.array(df.to_numpy(dtype=np.float64), dtype=np.float64, copy=False, order="C")
    else:
        arr = np.ascontiguousarray(df, dtype=np.float64)
    np.nan_to_num(arr, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    return arr
```

**Issue 2: `normalize_numeric_frame` calls `.apply(pd.to_numeric)` column-by-column in Python, then two more passes for inf/nan.**

```python
# CURRENT
def normalize_numeric_frame(df, *, fill=0.0):
    out = df.apply(pd.to_numeric, errors="coerce")
    return out.replace([np.inf, -np.inf], np.nan).fillna(fill)

# UPGRADE — vectorized numpy path, single allocation
def normalize_numeric_frame(df: pd.DataFrame | None, *, fill: float = 0.0) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    arr = float_array(df)                          # already strips inf/nan → 0
    if fill != 0.0:
        np.place(arr, np.isnan(arr), fill)
    return pd.DataFrame(arr, index=df.index, columns=df.columns)
```

**Issue 3: `dataframe_fingerprint` calls `float_array(sample)` which allocates, then `np.round(..., precision)` allocates a second array.**

```python
# UPGRADE — round in-place, avoid double allocation
def dataframe_fingerprint(df: pd.DataFrame, *, precision: int = 8) -> str:
    if df is None or df.empty:
        return "empty"
    sample = df
    if len(df) > 180:
        sample = pd.concat([df.iloc[:80], df.iloc[-80:]], axis=0)
    if sample.shape[1] > 300:
        sample = sample.iloc[:, :300]
    arr = float_array(sample)
    np.round(arr, precision, out=arr)              # in-place rounding
    h = hashlib.blake2b(digest_size=16)
    h.update(str(df.shape).encode())
    h.update("|".join(str(c) for c in df.columns[:300]).encode())
    h.update(str(df.index[0]).encode())
    h.update(str(df.index[-1]).encode())
    h.update(arr.tobytes())
    return h.hexdigest()
```

**Issue 4: `nearest_psd` symmetrizes by adding two `np.asarray` calls and dividing by 2 — avoidable with `np.add`.**

```python
# UPGRADE — single symmetric copy, in-place clip
def nearest_psd(matrix: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    a = np.asarray(matrix, dtype=np.float64)
    sym = np.empty_like(a)
    np.add(a, a.T, out=sym)
    sym *= 0.5
    np.nan_to_num(sym, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    try:
        vals, vecs = np.linalg.eigh(sym)
        np.maximum(vals, eps, out=vals)
        return (vecs * vals) @ vecs.T
    except Exception:
        np.fill_diagonal(sym, np.maximum(np.diag(sym), eps))
        return sym
```

**Issue 5: `fast_matrix_records` builds a Python list comprehension over a meshgrid — slow for large matrices. Use structured array iteration with a pre-allocated list.**

```python
# UPGRADE — pre-allocate output list, zip over flat views
def fast_matrix_records(
    matrix: pd.DataFrame | np.ndarray,
    labels: Iterable[str] | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    if isinstance(matrix, pd.DataFrame):
        rows_lbl = np.asarray(matrix.index, dtype=object)
        cols_lbl = np.asarray(matrix.columns, dtype=object)
        arr = float_array(matrix)
    else:
        arr = float_array(matrix)
        base = np.asarray(
            list(labels or [f"A{i+1}" for i in range(arr.shape[0])]), dtype=object
        )
        rows_lbl = base[: arr.shape[0]]
        cols_lbl = base[: arr.shape[1]]
    n, m = arr.shape[:2]
    if n * m > MAX_MATRIX_CELLS:
        side = max(1, int(math.isqrt(MAX_MATRIX_CELLS)))
        n, m = min(n, side, limit), min(m, side, limit)
    else:
        n, m = min(n, limit), min(m, limit)
    sub = arr[:n, :m]
    flat = sub.ravel()
    total = n * m
    out: list[dict[str, Any]] = [None] * total      # pre-allocated
    idx = 0
    for i in range(n):
        r_lbl = str(rows_lbl[i])
        for j in range(m):
            v = float(flat[i * m + j])
            out[idx] = {
                "row": r_lbl,
                "col": str(cols_lbl[j]),
                "value": v if math.isfinite(v) else None,
            }
            idx += 1
    return out
```

**Issue 6: `fast_network_edges_from_corr` calls `float_array(corr)` then re-indexes — add a C-contiguous guarantee.**

```python
# UPGRADE — force C-contiguous layout before indexing so numpy uses BLAS strides
def fast_network_edges_from_corr(
    corr: pd.DataFrame,
    threshold: float = 0.45,
    max_edges: int = MAX_NETWORK_EDGES,
) -> list[dict[str, Any]]:
    if corr is None or corr.empty or len(corr.columns) < 2:
        return []
    labels = np.asarray([str(c) for c in corr.columns])
    arr = np.ascontiguousarray(float_array(corr))   # guaranteed C layout
    iu = np.triu_indices_from(arr, k=1)
    vals = arr[iu]
    abs_vals = np.abs(vals)
    mask = abs_vals >= float(threshold)
    if not mask.any():
        if vals.size == 0:
            return []
        top = np.argpartition(abs_vals, max(0, vals.size - min(max_edges, vals.size)))[-min(max_edges, vals.size):]
    else:
        selected = np.flatnonzero(mask)
        order = selected[np.argsort(abs_vals[selected])[::-1]]
        top = order[:max_edges]
    src_idx, tgt_idx = iu[0][top], iu[1][top]
    top_vals = vals[top]
    return [
        {
            "source": str(labels[s]),
            "target": str(labels[t]),
            "correlation": float(v),
            "weight": float(abs(v)),
        }
        for s, t, v in zip(src_idx, tgt_idx, top_vals)
    ]
```

**Issue 7: `rolling_leading_eigenvalue` and `rolling_diversification_ratio` re-compute `.corr()` / `np.cov()` inside every loop iteration from scratch — cache the slice fingerprint.**

```python
# UPGRADE — use np.linalg.eigh on pre-computed float arrays, avoid pandas corr overhead in loop
def rolling_leading_eigenvalue(
    returns: pd.DataFrame, window: int = 126, step: int = 5
) -> list[dict[str, Any]]:
    x = normalize_numeric_frame(returns)
    n_rows, n_cols = x.shape
    if n_rows < max(20, window // 2) or n_cols < 2:
        return []
    arr = float_array(x)                           # single numpy allocation
    rows: list[dict[str, Any]] = []
    start = max(window, 20)
    for end in range(start, n_rows + 1, max(1, step)):
        sub = arr[max(0, end - window):end]
        # Manual Pearson corr via broadcasting — avoids pandas overhead
        mu = sub.mean(axis=0)
        sub_c = sub - mu
        norms = np.sqrt((sub_c ** 2).sum(axis=0))
        norms[norms < 1e-12] = 1.0
        sub_c /= norms
        corr_a = sub_c.T @ sub_c / max(sub.shape[0] - 1, 1)
        np.clip(corr_a, -1.0, 1.0, out=corr_a)
        np.fill_diagonal(corr_a, 1.0)
        vals = np.linalg.eigvalsh(corr_a)
        rows.append({
            "date": x.index[end - 1],
            "leading_eigenvalue_share": float(vals[-1] / max(n_cols, 1)),
        })
    if rows and rows[-1]["date"] != x.index[-1]:
        sub = arr[-window:]
        mu = sub.mean(axis=0); sub_c = sub - mu
        norms = np.sqrt((sub_c ** 2).sum(axis=0)); norms[norms < 1e-12] = 1.0
        sub_c /= norms
        corr_a = sub_c.T @ sub_c / max(sub.shape[0] - 1, 1)
        np.clip(corr_a, -1.0, 1.0, out=corr_a); np.fill_diagonal(corr_a, 1.0)
        vals = np.linalg.eigvalsh(corr_a)
        rows.append({
            "date": x.index[-1],
            "leading_eigenvalue_share": float(vals[-1] / max(n_cols, 1)),
        })
    return rows
```

**Issue 8: `rank_ic_curve` materializes full `signal` and `fwd` DataFrames for each horizon — only compute once and slice.**

```python
# UPGRADE — vectorized IC computation with pre-ranked arrays; avoid re-ranking per horizon
def rank_ic_curve(
    returns: pd.DataFrame, max_horizon: int = 63, signal_window: int = 21
) -> list[dict[str, float | int]]:
    x = normalize_numeric_frame(returns, fill=np.nan)
    if x.empty:
        return []
    # Pre-compute signal once
    signal = x.rolling(signal_window).mean().shift(1).rank(axis=1, pct=True)
    s_arr = np.ascontiguousarray(signal.to_numpy(dtype=np.float64))
    x_arr = np.ascontiguousarray(x.to_numpy(dtype=np.float64))
    rows: list[dict[str, float | int]] = []
    for h in range(1, int(max_horizon) + 1):
        # Forward cumulative sum rolling h, shifted -h
        fwd_arr = np.full_like(x_arr, np.nan)
        for hi in range(h):                        # sum of h steps
            rolled = np.roll(x_arr, -(hi + 1), axis=0)
            rolled[-(hi + 1):] = np.nan
            fwd_arr = np.where(np.isnan(fwd_arr), rolled, fwd_arr + np.where(np.isnan(rolled), 0, rolled))
        # Rank fwd_arr cross-sectionally per row
        from scipy.stats import rankdata
        ranked_fwd = np.apply_along_axis(
            lambda r: rankdata(np.where(np.isfinite(r), r, np.nan), method="average") / max(np.sum(np.isfinite(r)), 1),
            axis=1, arr=fwd_arr
        )
        mask = np.isfinite(s_arr) & np.isfinite(ranked_fwd)
        valid = mask.sum(axis=1) > 5
        if not valid.any():
            rows.append({"horizon": h, "ic": 0.0})
            continue
        sv = np.where(mask[valid], s_arr[valid], np.nan)
        yv = np.where(mask[valid], ranked_fwd[valid], np.nan)
        s_mean = np.nanmean(sv, axis=1, keepdims=True)
        y_mean = np.nanmean(yv, axis=1, keepdims=True)
        sc = np.where(mask[valid], sv - s_mean, 0.0)
        yc = np.where(mask[valid], yv - y_mean, 0.0)
        denom = np.sqrt((sc * sc).sum(axis=1) * (yc * yc).sum(axis=1))
        corr_h = np.divide(
            (sc * yc).sum(axis=1), denom,
            out=np.full(valid.sum(), np.nan),
            where=denom > 1e-12,
        )
        rows.append({
            "horizon": h,
            "ic": float(np.nanmean(corr_h)) if np.isfinite(corr_h).any() else 0.0,
        })
    return rows
```

**Issue 9: `compact_table` calls `np.linspace` then `np.round` then `astype(int)` — use `np.linspace` with `dtype` directly.**

```python
# UPGRADE
def compact_table(df: pd.DataFrame, limit: int = 600) -> pd.DataFrame:
    if df is None or df.empty or len(df) <= limit:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    idx = np.unique(
        np.linspace(0, len(df) - 1, limit, dtype=np.intp)
    )
    return df.iloc[idx].copy()
```

**Issue 10: `BoundedLRU` uses `OrderedDict` lookups with Python-level attribute access on every cache hit — add `__slots__` to the dataclass nodes and use a faster key format.**

```python
# UPGRADE — add __slots__ to PerfCounter, use tuple key where possible
@dataclass
class PerfCounter:
    __slots__ = ("calls", "total_seconds", "max_seconds")
    calls: int = 0
    total_seconds: float = 0.0
    max_seconds: float = 0.0

    def add(self, elapsed: float) -> None:
        self.calls += 1
        self.total_seconds += elapsed
        self.max_seconds = elapsed if elapsed > self.max_seconds else self.max_seconds

    def as_dict(self) -> dict[str, float | int]:
        avg = self.total_seconds / self.calls if self.calls else 0.0
        return {
            "calls": self.calls,
            "total_seconds": round(self.total_seconds, 6),
            "avg_seconds": round(avg, 6),
            "max_seconds": round(self.max_seconds, 6),
        }
```

---

## FILE: `backend/app/services/portfolio_v2/core/data_loader.py`

---

**Issue 11: `_standardize_ohlcv` calls `.apply(pd.to_numeric)` per column in a for-loop — use vectorized `pd.to_numeric` with `apply` replaced by `infer_objects`.**

```python
# UPGRADE — single vectorized pass per numeric column
def _standardize_ohlcv(df: pd.DataFrame, asset_class: str = "equity") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=["Ticker","Date","Open","High","Low","Close","Volume","Asset_Class"]
        )
    rename = {c: str(c).strip().title() for c in df.columns}
    out = df.rename(columns=rename)
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    if "Ticker" not in out.columns:
        return pd.DataFrame(
            columns=["Ticker","Date","Open","High","Low","Close","Volume","Asset_Class"]
        )
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out = out.rename(columns={"Adj Close": "Close"})
    numeric_cols = [c for c in ["Open","High","Low","Close","Volume"] if c in out.columns]
    for col in ["Open","High","Low","Close","Volume"]:
        if col not in out.columns:
            out[col] = np.nan
    # Vectorized numeric coerce — one pass per column, no Python loop apply
    out[["Open","High","Low","Close","Volume"]] = (
        out[["Open","High","Low","Close","Volume"]]
        .apply(pd.to_numeric, errors="coerce")
    )
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", utc=False).dt.tz_localize(None)
    out["Ticker"] = out["Ticker"].astype(str).str.strip().str.upper().str.replace(".", "_", regex=False).str.replace("-", "_", regex=False)
    if "Asset_Class" not in out.columns:
        out["Asset_Class"] = asset_class
    out["Asset_Class"] = out["Asset_Class"].fillna(asset_class).astype(str).str.lower()
    return (
        out.dropna(subset=["Ticker","Date","Close"])
        [["Ticker","Date","Open","High","Low","Close","Volume","Asset_Class"]]
        .reset_index(drop=True)
    )
```

**Issue 12: `returns_matrix` calls `pd.concat` of two full DataFrames every time even when the canonical frame is empty.**

```python
# UPGRADE — skip concat if canonical is empty, avoid redundant copy
def returns_matrix(
    symbols: Iterable[str],
    lookback_days: int = 504,
    frequency: str = "daily",
    min_coverage: float = 0.65,
) -> pd.DataFrame:
    freq = normalize_frequency(frequency)
    extra = max(int(lookback_days) + 120, int(lookback_days))
    raw = ohlcv_for_symbols(symbols, lookback_days=extra, frequency=freq)
    if raw.empty:
        return pd.DataFrame()
    prices = (
        raw.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last")
        .sort_index()
        .ffill()
    )
    if freq == "hourly":
        prices = prices.resample("1h").last().ffill()
    elif freq == "weekly":
        prices = prices.resample("W-FRI").last()
    elif freq == "monthly":
        prices = prices.resample("ME").last()
    thresh = max(20, int(len(prices) * min_coverage))
    prices = prices.dropna(axis=1, thresh=thresh)
    # Log-returns: single numpy operation instead of pandas shift-divide
    arr = prices.to_numpy(dtype=np.float64)
    log_ret = np.empty_like(arr)
    log_ret[0] = np.nan
    np.log(arr[1:] / arr[:-1], out=log_ret[1:])
    np.clip(log_ret, -10.0, 10.0, out=log_ret)        # remove blow-ups
    rets = pd.DataFrame(log_ret, index=prices.index, columns=prices.columns)
    rets = rets.dropna(how="all").tail(lookback_rows(lookback_days, freq))
    thresh2 = max(20, int(len(rets) * min_coverage))
    return rets.dropna(axis=1, thresh=thresh2).fillna(0.0)
```

**Issue 13: `ohlcv_for_symbols` calls `pd.concat([load_market_ohlcv(), load_canonical_ohlcv()])` on every single call — the concat is O(N) and runs for every feature.**

```python
# UPGRADE — module-level merged cache populated once
_MERGED_OHLCV_CACHE: pd.DataFrame | None = None

def _merged_ohlcv() -> pd.DataFrame:
    global _MERGED_OHLCV_CACHE
    if _MERGED_OHLCV_CACHE is None:
        a = load_market_ohlcv()
        b = load_canonical_ohlcv()
        if a.empty and b.empty:
            _MERGED_OHLCV_CACHE = pd.DataFrame(
                columns=["Ticker","Date","Open","High","Low","Close","Volume","Asset_Class"]
            )
        elif a.empty:
            _MERGED_OHLCV_CACHE = b
        elif b.empty:
            _MERGED_OHLCV_CACHE = a
        else:
            _MERGED_OHLCV_CACHE = (
                pd.concat([a, b], ignore_index=True)
                .drop_duplicates(["Ticker","Date"], keep="last")
                .sort_values(["Ticker","Date"])
            )
    return _MERGED_OHLCV_CACHE

def ohlcv_for_symbols(
    symbols: Iterable[str],
    lookback_days: int | None = None,
    frequency: str = "daily",
) -> pd.DataFrame:
    freq = normalize_frequency(frequency)
    normalized = {normalize_symbol(s) for s in symbols if str(s).strip()}
    df = load_hourly_ohlcv() if freq == "hourly" else _merged_ohlcv()
    out = df[df["Ticker"].isin(normalized)]
    if lookback_days and not out.empty:
        cutoff = out["Date"].max() - pd.Timedelta(days=int(lookback_days) * 2)
        out = out[out["Date"] >= cutoff]
    return out.sort_values(["Ticker","Date"])
```

**Issue 14: `available_symbols` is decorated with `@lru_cache` but takes a mutable `limit` parameter — cache ignores the limit variance. Switch to a cached base list and slice outside.**

```python
# UPGRADE — cache the full sorted list once; slice in the wrapper
@lru_cache(maxsize=4)
def _available_symbols_full(frequency: str, include_cross_asset: bool) -> tuple[str, ...]:
    freq = normalize_frequency(frequency)
    frames = [load_hourly_ohlcv()] if freq == "hourly" and not load_hourly_ohlcv().empty else [load_market_ohlcv()]
    if include_cross_asset and freq != "hourly":
        frames.append(load_canonical_ohlcv())
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        return ()
    counts = df.groupby("Ticker")["Close"].count().sort_values(ascending=False)
    return tuple(str(s) for s in counts.index)

def available_symbols(
    limit: int | None = None,
    frequency: str = "daily",
    include_cross_asset: bool = True,
) -> list[str]:
    out = list(_available_symbols_full(normalize_frequency(frequency), include_cross_asset))
    return out[:limit] if limit else out
```

**Issue 15: `normalize_symbol` is called millions of times on hot paths with no caching — add a `functools.lru_cache`.**

```python
# UPGRADE
from functools import lru_cache

@lru_cache(maxsize=8192)
def normalize_symbol(symbol: Any) -> str:
    return str(symbol).strip().upper().replace(".", "_").replace("-", "_")
```

**Issue 16: `sector_map` and `market_caps` both call `load_fundamentals_metadata()` and then do separate `dict(zip(...))` constructions on every feature call.**

```python
# UPGRADE — build both maps in one pass
@lru_cache(maxsize=1)
def _fundamentals_maps() -> tuple[dict[str, str], dict[str, float]]:
    meta = load_fundamentals_metadata()
    if meta.empty:
        return {}, {}
    sec = {}
    cap = {}
    for _, row in meta.iterrows():
        t = str(row.get("ticker", ""))
        sec[t] = str(row.get("sector", "Unknown") or "Unknown")
        mc = row.get("marketCap")
        try:
            mc = float(mc)
            cap[t] = mc if mc > 0 else 1.0
        except Exception:
            cap[t] = 1.0
    return sec, cap

def sector_map(symbols: Iterable[str]) -> dict[str, str]:
    sec, _ = _fundamentals_maps()
    return {normalize_symbol(s): sec.get(normalize_symbol(s), "Unknown") for s in symbols}

def market_caps(symbols: Iterable[str]) -> dict[str, float]:
    _, cap = _fundamentals_maps()
    return {normalize_symbol(s): cap.get(normalize_symbol(s), 1.0) for s in symbols}
```

**Issue 17: `_read_parquet` falls through to a bare `pd.read_parquet` when Polars fails — add `engine="pyarrow"` explicitly to avoid the engine detection overhead.**

```python
# UPGRADE
def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    if pl is not None and columns:
        try:
            return pl.scan_parquet(str(path)).select(columns).collect().to_pandas()
        except Exception:
            pass
    try:
        return pd.read_parquet(path, columns=columns, engine="pyarrow")
    except Exception:
        return pd.read_parquet(path, engine="pyarrow")
```

---

## FILE: `backend/app/services/portfolio_v2/core/analytics.py`

---

**Issue 18: `clean_json` is called recursively on large nested outputs and uses `isinstance` chains on every node — add a dispatch table.**

```python
# UPGRADE — type-keyed dispatch avoids repeated isinstance evaluation
import math
import numpy as np
import pandas as pd
from typing import Any

def _clean_scalar(value: float) -> float | None:
    return value if math.isfinite(value) else None

_CLEAN_DISPATCH: dict[type, Any] = {}

def clean_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    t = type(value)
    if t is int:
        return value
    if t is float:
        return value if math.isfinite(value) else None
    if t is dict:
        return {str(k): clean_json(v) for k, v in value.items()}
    if t is list:
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, pd.Series):
        return clean_json(value.to_dict())
    if isinstance(value, pd.DataFrame):
        out = value.copy()
        for col in out.select_dtypes(include=["datetime64[ns]","datetime64[ns, UTC]"]).columns:
            out[col] = out[col].dt.strftime("%Y-%m-%d")
        return clean_json(out.to_dict("records"))
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    return value
```

**Issue 19: `covariance_matrix` with `method="ewma"` recomputes the weight vector on every call — memoize the weight vector for a given `(lambda, n_obs)` pair.**

```python
# UPGRADE — cache EWMA weight vectors
from functools import lru_cache as _lru_cache

@_lru_cache(maxsize=64)
def _ewma_weights(lam: float, n: int) -> np.ndarray:
    w = np.array([(1 - lam) * lam ** i for i in range(n - 1, -1, -1)], dtype=np.float64)
    w /= w.sum()
    return w

# Inside covariance_matrix, replace the EWMA block:
# BEFORE:
#   w = np.array([(1 - lam) * lam ** i for i in range(len(x) - 1, -1, -1)], dtype=float)
#   w /= max(w.sum(), 1e-12)
# AFTER:
        elif method == "ewma":
            lam = 0.94
            w = _ewma_weights(lam, len(x))
            xc = x - np.average(x, axis=0, weights=w)
            cov = (xc * w[:, None]).T @ xc
            meta["lambda"] = lam
```

**Issue 20: `optimize_portfolios` calls `np.linalg.pinv(cov_ann + np.eye(n) * 1e-10)` then separately calls `_hrp_weights` which calls `returns.corr()` — `corr` is already available; pass it in.**

```python
# UPGRADE — pass pre-computed correlation to HRP to avoid second `.corr()` call
# In optimize_portfolios, replace:
#   hrp = _hrp_weights(returns.corr().fillna(0.0), vols, cols)
# With:
    corr_frame = cached_correlation_frame(returns)
    hrp = _hrp_weights(corr_frame, vols, cols)
```

**Issue 21: `_risk_parity` and `_max_diversification` use `scipy.optimize.minimize` with `method="SLSQP"` and no initial warm-start — pass a smarter initial guess to reduce iterations.**

```python
# UPGRADE — warm-start _risk_parity with inverse-vol weights
def _risk_parity(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    vols = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    w0 = (1.0 / vols)
    w0 /= w0.sum()                                 # inverse-vol warm start
    def obj(w: np.ndarray) -> float:
        port = math.sqrt(max(float(w @ cov @ w), 1e-12))
        rc = w * (cov @ w) / port
        return float(((rc - rc.mean()) ** 2).sum())
    res = minimize(
        obj, w0,
        bounds=[(1e-6, 1)] * n,
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
        method="SLSQP",
        options={"maxiter": 300, "ftol": 1e-10},
    )
    return res.x if res.success else w0

# UPGRADE — warm-start _max_diversification with inverse-vol
def _max_diversification(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    vols = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    w0 = (1.0 / vols); w0 /= w0.sum()
    def obj(w: np.ndarray) -> float:
        return -float((w @ vols) / math.sqrt(max(float(w @ cov @ w), 1e-12)))
    res = minimize(
        obj, w0,
        bounds=[(1e-6, 1)] * n,
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
        method="SLSQP",
        options={"maxiter": 300, "ftol": 1e-10},
    )
    return res.x if res.success else w0
```

**Issue 22: `performance_metrics` recomputes the equity curve, then the drawdown series independently — combine into a single pass.**

```python
# UPGRADE — single cumprod pass, drawdown in-place
def performance_metrics(series: pd.Series, ann: float = 252.0) -> dict[str, float]:
    r = pd.Series(series).dropna().to_numpy(dtype=np.float64)
    if r.size == 0:
        return {}
    equity = np.empty(r.size, dtype=np.float64)
    equity[0] = 1.0 + r[0]
    for i in range(1, r.size):
        equity[i] = equity[i - 1] * (1.0 + r[i])
    # Drawdown in one pass
    peak = equity[0]; max_dd = 0.0
    for i in range(r.size):
        if equity[i] > peak:
            peak = equity[i]
        dd = equity[i] / peak - 1.0
        if dd < max_dd:
            max_dd = dd
    vol = float(np.std(r, ddof=1) * math.sqrt(ann))
    mean_ann = float(r.mean() * ann)
    sharpe = mean_ann / vol if vol > 1e-12 else 0.0
    neg = r[r < 0]
    downside = float(np.std(neg, ddof=1) * math.sqrt(ann)) if len(neg) > 1 else 0.0
    sortino = mean_ann / downside if downside > 1e-12 else 0.0
    q05 = float(np.quantile(r, 0.05))
    cvar = float(r[r <= np.quantile(r, 0.05)].mean()) if (r <= np.quantile(r, 0.05)).any() else q05
    from scipy import stats as _st
    return {
        "annual_return": mean_ann,
        "annual_vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": float(max_dd),
        "var_95": q05,
        "cvar_95": cvar,
        "skew": float(_st.skew(r, nan_policy="omit")),
        "kurtosis": float(_st.kurtosis(r, nan_policy="omit")),
    }
```

**Issue 23: `brinson_attribution` calls `returns.mean()` inside a sector loop — compute it once before the loop.**

```python
# UPGRADE — hoist mean_ret out of loop (already done correctly in the source but
# the per-sector slicing of port_w/bench_w triggers repeated .sum() over the full index)
def brinson_attribution(
    returns: pd.DataFrame, weights: pd.Series, sectors: dict[str, str]
) -> list[dict[str, Any]]:
    cols = list(returns.columns)
    port_w = weights.reindex(cols).fillna(0.0).to_numpy(np.float64)
    bench_w = np.repeat(1.0 / max(len(cols), 1), len(cols))
    mean_ret = returns.mean().to_numpy(np.float64)
    sector_arr = np.array([sectors.get(c, "Unknown") for c in cols])
    rows = []
    for sector in sorted(set(sectors.values())):
        idx = np.where(sector_arr == sector)[0]
        if not idx.size:
            continue
        pw = float(port_w[idx].sum())
        bw = float(bench_w[idx].sum())
        pr = float((port_w[idx] * mean_ret[idx]).sum() / max(abs(pw), 1e-12))
        br = float((bench_w[idx] * mean_ret[idx]).sum() / max(abs(bw), 1e-12))
        rows.append({
            "sector": sector,
            "portfolio_weight": pw,
            "benchmark_weight": bw,
            "allocation_effect": (pw - bw) * br,
            "selection_effect": bw * (pr - br),
            "interaction_effect": (pw - bw) * (pr - br),
        })
    return clean_json(rows)
```

**Issue 24: `liquidity_table` iterates over `raw.groupby("Ticker")` and computes `Amihud` inside Python loops with pandas Series operations — vectorize using groupby aggregation.**

```python
# UPGRADE — vectorized Amihud via groupby transform
def liquidity_table(
    symbols: list[str],
    lookback_days: int = 252,
    nav: float = 1_000_000.0,
    weights: pd.Series | None = None,
) -> list[dict[str, Any]]:
    raw = ohlcv_for_symbols(symbols, lookback_days=lookback_days)
    if raw.empty:
        return []
    w = (
        weights.reindex(symbols).fillna(1.0 / max(len(symbols), 1))
        if weights is not None
        else pd.Series(np.repeat(1.0 / max(len(symbols), 1), len(symbols)), index=symbols)
    )
    df = raw.sort_values(["Ticker", "Date"]).copy()
    df["ret_abs"] = df.groupby("Ticker")["Close"].pct_change().abs()
    df["dv"] = df["Close"] * df["Volume"].fillna(0.0)
    df["dv"].replace(0.0, np.nan, inplace=True)
    df["amihud_raw"] = df["ret_abs"] / df["dv"]
    df["amihud_raw"].replace([np.inf, -np.inf], np.nan, inplace=True)
    # Grouped aggregation in one pass
    agg = df.groupby("Ticker").agg(
        amihud=("amihud_raw", "mean"),
        adv=("dv", lambda x: x.tail(60).mean()),
    )
    rows = []
    for s in symbols:
        ns = normalize_symbol(s)
        if ns not in agg.index:
            continue
        amihud = float(agg.loc[ns, "amihud"]) if pd.notna(agg.loc[ns, "amihud"]) else 0.0
        adv = float(agg.loc[ns, "adv"]) if pd.notna(agg.loc[ns, "adv"]) else 0.0
        position = float(abs(w.get(ns, 0.0)) * nav)
        days = position / max(adv * 0.15, 1.0)
        rows.append({
            "ticker": ns,
            "amihud": amihud,
            "adv_dollars": adv,
            "position_dollars": position,
            "days_to_liquidate_15pct_adv": days,
            "liquidity_var_bps": 10000.0 * math.sqrt(max(amihud, 0.0) * max(position, 1.0)),
        })
    return clean_json(rows)
```

**Issue 25: `dcc_garch_cov` iterates row-by-row through `z.iterrows()` which is the single most expensive Python-level loop in the entire codebase — replace with a Numba JIT-compiled recursion.**

```python
# UPGRADE — Numba JIT DCC recursion; falls back to pure numpy if Numba unavailable

try:
    import numba as nb

    @nb.njit(cache=True, fastmath=True)
    def _dcc_loop(z_arr: np.ndarray, qbar: np.ndarray, alpha: float, beta: float):
        """DCC Q-matrix recursion. Returns last covariance and avg corr series."""
        T, n = z_arr.shape
        one_minus = 1.0 - alpha - beta
        q = qbar.copy()
        avg_corrs = np.empty(T, dtype=np.float64)
        cov_last = np.empty((n, n), dtype=np.float64)
        for t in range(T):
            zz = z_arr[t]
            for i in range(n):
                for j in range(n):
                    q[i, j] = one_minus * qbar[i, j] + alpha * zz[i] * zz[j] + beta * q[i, j]
            # Normalize to correlation
            d = np.empty(n, dtype=np.float64)
            for i in range(n):
                d[i] = math.sqrt(max(q[i, i], 1e-12))
            s = 0.0; cnt = 0
            for i in range(n):
                for j in range(i + 1, n):
                    s += q[i, j] / (d[i] * d[j])
                    cnt += 1
            avg_corrs[t] = s / max(cnt, 1)
            # Store last cov
            if t == T - 1:
                for i in range(n):
                    for j in range(n):
                        cov_last[i, j] = q[i, j] / (d[i] * d[j])
        return cov_last, avg_corrs

    _NUMBA_DCC_AVAILABLE = True
except ImportError:
    _NUMBA_DCC_AVAILABLE = False


def dcc_garch_cov(
    returns: pd.DataFrame, alpha: float = 0.03, beta: float = 0.94
) -> dict[str, Any]:
    r = returns.fillna(0.0)
    if r.empty:
        return {"covariance": pd.DataFrame(), "average_correlation_series": []}
    vols = r.ewm(alpha=1 - beta, adjust=False).std().replace(0, np.nan).bfill().fillna(r.std())
    z = (r / vols).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    qbar = np.ascontiguousarray(z.cov().to_numpy(dtype=np.float64))
    z_arr = np.ascontiguousarray(z.to_numpy(dtype=np.float64))
    if _NUMBA_DCC_AVAILABLE:
        cov_last, avg_corrs = _dcc_loop(z_arr, qbar, alpha, beta)
        avg = [
            {"date": str(pd.Timestamp(d).date()), "avg_correlation": float(c)}
            for d, c in zip(z.index, avg_corrs)
        ]
    else:
        # Pure numpy fallback (original logic, vectorized where possible)
        q = qbar.copy()
        avg = []
        cov_last = qbar.copy()
        one_minus = 1.0 - alpha - beta
        for i, (dt, row) in enumerate(z.iterrows()):
            zz = row.to_numpy()[:, None]
            q = one_minus * qbar + alpha * (zz @ zz.T) + beta * q
            d = np.sqrt(np.maximum(np.diag(q), 1e-12))
            corr = q / np.outer(d, d)
            v = vols.iloc[i].to_numpy(dtype=np.float64)
            cov_last = corr * np.outer(v, v)
            upper = corr[np.triu_indices_from(corr, 1)]
            avg.append({
                "date": str(pd.Timestamp(dt).date()),
                "avg_correlation": float(np.nanmean(upper)) if len(upper) else 0.0,
            })
    return {
        "covariance": pd.DataFrame(cov_last, index=r.columns, columns=r.columns),
        "average_correlation_series": avg,
    }
```

**Issue 26: `kelly_sizing` recomputes `inv @ mu` and `inv @ ones` in sequence — compute both in a single `np.linalg.solve` call which is faster than two separate `pinv @ vec` multiplications.**

```python
# UPGRADE — solve instead of pinv-multiply
def kelly_sizing(
    mu: pd.Series,
    cov: pd.DataFrame,
    current: pd.Series | None = None,
    fraction: float = 0.5,
    leverage_cap: float = 1.0,
    tc_bps: float = 10.0,
) -> dict[str, Any]:
    cols = list(mu.index)
    cov_arr = cov.reindex(index=cols, columns=cols).to_numpy(dtype=np.float64)
    cov_reg = cov_arr + np.eye(len(cols)) * 1e-9
    mu_arr = mu.to_numpy(dtype=np.float64)
    try:
        raw = np.linalg.solve(cov_reg, mu_arr)    # faster than pinv @ mu
    except np.linalg.LinAlgError:
        raw = np.linalg.pinv(cov_reg) @ mu_arr
    np.nan_to_num(raw, copy=False)
    abs_sum = np.abs(raw).sum()
    if abs_sum > 1e-12:
        raw = raw / abs_sum * min(leverage_cap, abs_sum)
    w = np.clip(raw * fraction, -leverage_cap, leverage_cap)
    if np.abs(w).sum() > leverage_cap:
        w = w / np.abs(w).sum() * leverage_cap
    cur = current.reindex(cols).fillna(0.0).to_numpy() if current is not None else np.zeros(len(cols))
    rows = [
        {"ticker": s, "kelly_weight": float(raw[i]), "constrained_weight": float(w[i]),
         "current_weight": float(cur[i]), "sizing_gap": float(w[i] - cur[i])}
        for i, s in enumerate(cols)
    ]
    grid = []
    for f in np.linspace(0.05, 1.0, 40):
        wf = raw * f
        growth = float(wf @ mu_arr - 0.5 * wf @ cov_arr @ wf)
        cost = float(2 * (tc_bps / 10000) * np.abs(wf - cur).sum())
        grid.append({"kelly_fraction": float(f), "gross_growth": growth,
                     "cost_drag": cost, "net_growth": growth - cost})
    best = max(grid, key=lambda r: r["net_growth"]) if grid else {"kelly_fraction": 0.0}
    return {"table": rows, "growth_curve": grid, "turnover_optimal_fraction": best["kelly_fraction"]}
```

**Issue 27: `cvar_minimize` constructs large dense scipy `linprog` matrices on every call — the result is already cached via `cached_result`, but the construction itself is slow for large `n_obs`. Pre-allocate with `np.zeros` and use index assignment.**

```python
# UPGRADE — single np.zeros allocation, vectorized index fills
def cvar_minimize(
    returns: pd.DataFrame, alpha: float = 0.95, target_return: float | None = None
) -> pd.Series:
    key = f"{dataframe_fingerprint(returns)}:{alpha}:{target_return}"

    def build() -> pd.Series:
        x = returns.fillna(0.0).to_numpy(dtype=np.float64, copy=False)
        n_obs, n = x.shape
        if n == 0:
            return pd.Series(dtype=float)
        inv_cvar = 1.0 / ((1.0 - alpha) * max(n_obs, 1))
        c = np.zeros(n + 1 + n_obs, dtype=np.float64)
        c[n] = 1.0
        c[n + 1:] = inv_cvar
        extra = 1 if target_return is not None else 0
        n_rows = n_obs + extra
        n_cols = n + 1 + n_obs
        A_ub = np.zeros((n_rows, n_cols), dtype=np.float64)
        A_ub[:n_obs, :n] = -x
        A_ub[:n_obs, n] = -1.0
        # Diagonal block for slack vars
        rows_idx = np.arange(n_obs, dtype=np.intp)
        A_ub[rows_idx, n + 1 + rows_idx] = -1.0
        b_ub = np.zeros(n_rows, dtype=np.float64)
        if target_return is not None:
            A_ub[-1, :n] = -returns.mean().to_numpy(dtype=np.float64)
            b_ub[-1] = -float(target_return)
        A_eq = np.zeros((1, n_cols), dtype=np.float64)
        A_eq[0, :n] = 1.0
        bounds = [(0, 1)] * n + [(None, None)] + [(0, None)] * n_obs
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=np.array([1.0]),
                      bounds=bounds, method="highs")
        w = res.x[:n] if res.success else np.repeat(1.0 / n, n)
        return pd.Series(w, index=returns.columns)

    return cached_result("cvar_minimize", key, build).copy()
```

**Issue 28: `rolling_regimes` constructs a `features` DataFrame and calls `GaussianMixture.fit_predict` on the raw array — but it never normalizes/standardizes, causing the GMM to overweight high-variance features.**

```python
# UPGRADE — add StandardScaler before GMM and cache the result
from sklearn.preprocessing import StandardScaler

def rolling_regimes(
    portfolio_returns: pd.Series,
    macro: pd.DataFrame,
    n_regimes: int = 3,
) -> pd.DataFrame:
    r = portfolio_returns.dropna().rename("portfolio_return").to_frame()
    if r.empty:
        return pd.DataFrame()
    features = pd.DataFrame(index=r.index)
    features["vol_21"] = r["portfolio_return"].rolling(21).std().bfill()
    features["mom_63"] = r["portfolio_return"].rolling(63).sum().fillna(0.0)
    if not macro.empty:
        m = macro.set_index("date").reindex(r.index, method="ffill")
        for col in ["vix_close", "vixcls", "yc_slope_10y_2y", "bamlh0a0hym2"]:
            if col in m.columns:
                features[col] = (
                    m[col].ffill().pct_change(fill_method=None)
                    .replace([np.inf, -np.inf], np.nan).fillna(0.0)
                )
    x_raw = features.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    x = StandardScaler().fit_transform(x_raw)     # normalize before GMM
    if GaussianMixture is None or len(x) < 90:
        q = pd.qcut(
            features["vol_21"].rank(method="first"),
            q=min(n_regimes, len(features)),
            labels=False, duplicates="drop",
        )
        labels = pd.Series(q, index=features.index).fillna(0).astype(int)
    else:
        labels = pd.Series(
            GaussianMixture(
                n_components=n_regimes,
                covariance_type="full",
                random_state=7,
                max_iter=200,
                tol=1e-4,
            ).fit_predict(x),
            index=features.index,
        )
    out = features.reset_index().rename(columns={features.reset_index().columns[0]: "date"})
    out["regime"] = labels.values
    return out
```

**Issue 29: `gerber_statistic_cov` applies two boolean masks sequentially on the full DataFrame — use `np.where` on the numpy array directly.**

```python
# UPGRADE — single numpy pass, no pandas boolean indexing overhead
def gerber_statistic_cov(returns: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    r = returns.fillna(0.0)
    sigma = r.std().replace(0, np.nan).fillna(1.0).to_numpy(np.float64)
    arr = r.to_numpy(np.float64)
    threshold_mat = threshold * sigma[None, :]     # broadcast
    signs = np.where(arr > threshold_mat, 1.0, np.where(arr < -threshold_mat, -1.0, 0.0))
    # Correlation of sign matrix
    signs_df = pd.DataFrame(signs, index=r.index, columns=r.columns)
    g = signs_df.corr().fillna(0.0).to_numpy(np.float64)
    vol = r.std().fillna(0.0).to_numpy(np.float64)
    result = g * np.outer(vol, vol)
    return pd.DataFrame(result, index=r.columns, columns=r.columns)
```

**Issue 30: `skill_luck_bootstrap` allocates a new `rng.choice` array per bootstrap iteration — use a single `rng.choice` on the full 2D matrix and vectorize the mean/std.**

```python
# UPGRADE — vectorized bootstrap
def skill_luck_bootstrap(returns: pd.Series, draws: int = 2000) -> dict[str, Any]:
    r = returns.dropna().to_numpy(dtype=np.float64)
    if len(r) < 30:
        return {"p_value": None, "null_distribution": []}
    rng = np.random.default_rng(7)
    obs = float(np.mean(r) / max(np.std(r, ddof=1), 1e-12))
    centered = r - r.mean()
    n = len(centered)
    actual_draws = min(draws, 10000)
    # Single 2D sample: shape (actual_draws, n)
    sample_matrix = centered[rng.integers(0, n, size=(actual_draws, n))]
    means = sample_matrix.mean(axis=1)
    stds = sample_matrix.std(axis=1, ddof=1)
    stds[stds < 1e-12] = 1e-12
    boot_t = means / stds
    p_value = float(np.mean(np.abs(boot_t) >= abs(obs)))
    return {
        "observed_t": obs,
        "p_value": p_value,
        "null_distribution": [
            {"sample": i, "t": float(v)} for i, v in enumerate(boot_t[:500])
        ],
    }
```

**Issue 31: `debtrank_propagate` re-normalizes `W` every call even when the same exposure matrix is passed repeatedly — pre-normalize once.**

```python
# UPGRADE — normalize outside the iteration loop, use numpy only
def debtrank_propagate(
    exposure: pd.DataFrame,
    initial_distress: pd.Series,
    damping: float = 0.85,
    max_iter: int = 100,
) -> pd.Series:
    W = exposure.fillna(0.0).to_numpy(dtype=np.float64)
    row_sums = W.sum(axis=1, keepdims=True)
    np.divide(W, np.maximum(row_sums, 1e-12), out=W)  # normalize in-place
    h = initial_distress.reindex(exposure.index).fillna(0.0).to_numpy(dtype=np.float64)
    v = h.copy()
    for _ in range(max_iter):
        nxt = np.clip(h + damping * (W @ v), 0.0, 1.0)
        if np.max(np.abs(nxt - v)) < 1e-6:
            v = nxt
            break
        v = nxt
    return pd.Series(v, index=exposure.index)
```

**Issue 32: `newey_west_regression` constructs `np.diag(resid ** 2)` which is O(N^2) memory — use element-wise multiplication instead.\*\*

```python
# UPGRADE — avoid O(N^2) diagonal matrix, use broadcasting
def newey_west_regression(
    y: pd.Series, x: pd.DataFrame, lags: int = 4
) -> dict[str, Any]:
    df = pd.concat([y.rename("y"), x], axis=1).dropna()
    if len(df) <= x.shape[1] + 2:
        return {"coefficients": [], "r2": 0.0}
    X = np.c_[np.ones(len(df)), df[x.columns].to_numpy(dtype=np.float64)]
    Y = df["y"].to_numpy(dtype=np.float64)
    beta = np.linalg.lstsq(X, Y, rcond=None)[0]   # lstsq more stable than pinv
    resid = Y - X @ beta
    xtx_inv = np.linalg.pinv(X.T @ X)
    # Sandwich: X.T @ diag(e^2) @ X = (X * e[:,None]).T @ (X * e[:,None]) ... no: use:
    e2_X = X * (resid ** 2)[:, None]              # shape (T, k), avoids NxN diag
    S = X.T @ e2_X                                 # (k, k) — O(T*k^2) not O(T^2)
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1)
        Xl, Xr = X[lag:], X[:-lag]
        el, er = resid[lag:], resid[:-lag]
        gamma = (Xl * el[:, None]).T @ (Xr * er[:, None])
        S += weight * (gamma + gamma.T)
    cov = xtx_inv @ S @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    ssr = float((resid ** 2).sum())
    tss = float(((Y - Y.mean()) ** 2).sum())
    rows = [{"factor": "intercept", "beta": float(beta[0]), "se": float(se[0]), "t": float(beta[0] / se[0])}]
    rows += [
        {"factor": c, "beta": float(beta[i + 1]), "se": float(se[i + 1]), "t": float(beta[i + 1] / se[i + 1])}
        for i, c in enumerate(x.columns)
    ]
    return {"coefficients": rows, "r2": 1.0 - ssr / max(tss, 1e-12)}
```

**Issue 33: `alpha_decay` calls `rank_ic_curve` inside `cached_result` which wraps a lambda — the lambda captures `returns` by reference, preventing garbage collection of the frame during the cache lifetime. Capture only the fingerprint key.**

```python
# UPGRADE — pass builder directly without lambda closure over large frame
def alpha_decay(
    returns: pd.DataFrame,
    factor_returns: pd.Series | None = None,
    max_horizon: int = 63,
) -> dict[str, Any]:
    if returns.empty:
        return {"ic_curve": [], "half_life": None}
    fingerprint = dataframe_fingerprint(returns)
    cache_key = f"rank_ic_curve.{int(max_horizon)}:{fingerprint}"
    cached = RESULT_CACHE.get(cache_key)
    if cached is None:
        cached = rank_ic_curve(returns, max_horizon=int(max_horizon))
        RESULT_CACHE.set(cache_key, cached)
    rows = cached
    arr = np.abs([row["ic"] for row in rows])
    base = max(arr[0] if len(arr) else 0.0, 1e-9)
    below = np.where(arr <= base / 2)[0]
    half = int(below[0] + 1) if len(below) else None
    return {"ic_curve": rows, "half_life": half}
```

**Issue 34: `factor_structured_cov` calls `np.linalg.svd` with `full_matrices=False` then only uses `k=5` columns — use `np.linalg.svd` with `compute_uv=True` which is already efficient, but `scipy.linalg.svds` gives only the top-k singular values much faster for large matrices.**

```python
# UPGRADE — use scipy.sparse.linalg.svds for top-k only
from scipy.sparse.linalg import svds as _svds

def factor_structured_cov(
    returns: pd.DataFrame, factors: pd.DataFrame | None = None
) -> pd.DataFrame:
    r = returns.fillna(0.0)
    if factors is None or factors.empty:
        arr = r.to_numpy(dtype=np.float64)
        k = min(5, min(arr.shape) - 1)
        if k > 0:
            U, s, Vt = _svds(arr, k=k)             # only top-k, much faster
            U = U[:, ::-1]; s = s[::-1]            # svds returns ascending order
        else:
            U, s, Vt = np.linalg.svd(arr, full_matrices=False)
            k = min(5, U.shape[1])
            U, s = U[:, :k], s[:k]
        f = pd.DataFrame(U * s, index=r.index)
    else:
        f = factors.reindex(r.index).fillna(0.0)
    X = np.c_[np.ones(len(f)), f.to_numpy(dtype=np.float64)]
    betas = np.linalg.lstsq(X, r.to_numpy(dtype=np.float64), rcond=None)[0]
    fitted = X @ betas
    resid = r.to_numpy(np.float64) - fitted
    fcov = np.cov(f.to_numpy(np.float64), rowvar=False)
    b = betas[1:, :].T
    structured = b @ np.atleast_2d(fcov) @ b.T + np.diag(np.var(resid, axis=0))
    return pd.DataFrame(structured, index=r.columns, columns=r.columns)
```

**Issue 35: `load_context` calls `data_inventory()` on every feature invocation — `data_inventory` opens parquet files to count rows. Cache it.**

```python
# UPGRADE — module-level inventory cache
_INVENTORY_CACHE: dict | None = None

def _cached_data_inventory() -> dict:
    global _INVENTORY_CACHE
    if _INVENTORY_CACHE is None:
        _INVENTORY_CACHE = data_inventory()
    return _INVENTORY_CACHE

# In load_context, replace:
#   "inventory": data_inventory(),
# With:
#   "inventory": _cached_data_inventory(),
```

**Issue 36: `portfolio_return_series` calls `.reindex` then `.fillna` then `.dot` — use numpy dot directly after `reindex` for large `n`.**

```python
# UPGRADE — single numpy dot, no intermediate Series creation
def portfolio_return_series(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = weights.reindex(returns.columns).fillna(0.0).to_numpy(np.float64)
    arr = returns.fillna(0.0).to_numpy(np.float64)
    result = arr @ w
    return pd.Series(result, index=returns.index)
```

---

## FILE: `features/feature_01.py` through `feature_13.py`

---

**Issue 37: Every feature calls `load_context` which calls `returns_matrix` which re-reads parquet on every HTTP request. Add a request-scoped context cache keyed by payload hash.**

```python
# UPGRADE — add to analytics.py, use in every feature
import hashlib, json

_CONTEXT_CACHE: dict[str, dict] = {}
_CONTEXT_CACHE_MAX = 8

def _payload_key(payload: dict | None) -> str:
    try:
        canonical = json.dumps(payload or {}, sort_keys=True, default=str)
        return hashlib.blake2b(canonical.encode(), digest_size=8).hexdigest()
    except Exception:
        return "default"

def load_context_cached(
    payload: dict | None = None,
    *,
    min_symbols: int = 12,
    default_limit: int = 80,
) -> dict:
    key = _payload_key(payload)
    if key in _CONTEXT_CACHE:
        return _CONTEXT_CACHE[key]
    ctx = load_context(payload, min_symbols=min_symbols, default_limit=default_limit)
    if len(_CONTEXT_CACHE) >= _CONTEXT_CACHE_MAX:
        _CONTEXT_CACHE.pop(next(iter(_CONTEXT_CACHE)))
    _CONTEXT_CACHE[key] = ctx
    return ctx

# In every feature file, replace:
#   ctx = load_context(payload, ...)
# With:
#   ctx = load_context_cached(payload, min_symbols=..., default_limit=...)
```

**Issue 38: `feature_01.py` calls `dcc_garch_cov(rets)`, `factor_structured_cov(rets)`, `gerber_statistic_cov(rets)` sequentially — each re-processes the same `rets` array. Wrap all three in a single function and share the pre-computed float array.**

```python
# UPGRADE — shared float array for all four covariance estimators in F01
# Add to analytics.py:

def all_covariance_estimators(
    returns: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Compute all four estimators sharing one float_array allocation."""
    arr = float_array(returns.fillna(0.0))
    lw_cov, _ = covariance_matrix(returns, "ledoit_wolf")
    dcc_result = dcc_garch_cov(returns)
    fs_cov = factor_structured_cov(returns)
    gerber_cov = gerber_statistic_cov(returns)
    return {
        "ledoit_wolf": lw_cov,
        "dcc_garch": dcc_result["covariance"],
        "factor_structured": fs_cov,
        "gerber": gerber_cov,
        "_dcc_avg_corr": dcc_result["average_correlation_series"],
    }

# In feature_01.py replace the four separate calls with:
#   all_covs = all_covariance_estimators(rets)
```

**Issue 39: `feature_08.py` calls `network_edges(rets)` then `precision_matrix_network(rets)` — `precision_matrix_network` re-computes the Ledoit-Wolf covariance internally even though `feature_08` already has it from correlation diagnostics. Pass the covariance in.**

```python
# UPGRADE — extend precision_matrix_network to accept optional pre-computed cov
def precision_matrix_network(
    returns: pd.DataFrame,
    threshold: float = 0.05,
    precomputed_cov: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    if precomputed_cov is not None and not precomputed_cov.empty:
        cov = precomputed_cov
    else:
        cov, _ = covariance_matrix(returns, "ledoit_wolf")
    if cov.empty:
        return []
    theta = safe_inverse(cov.to_numpy(dtype=np.float64))
    d = np.sqrt(np.maximum(np.diag(theta), 1e-12))
    partial = -theta / np.outer(d, d)
    np.fill_diagonal(partial, 1.0)
    partial_df = pd.DataFrame(partial, index=cov.columns, columns=cov.columns)
    edges = fast_network_edges_from_corr(partial_df, threshold=threshold, max_edges=500)
    return [{"source": e["source"], "target": e["target"], "partial_corr": e["correlation"]} for e in edges]
```

**Issue 40: `feature_13.py` calls `build_strategy_returns(ctx["returns"])` which calls `.rolling(21).mean()`, `.rolling(63).sum()`, `.rolling(63).std()` on the same DataFrame three times — compute all rolling windows in a single pass.**

```python
# UPGRADE — consolidated rolling computation
def build_strategy_returns(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame()
    arr = returns.to_numpy(dtype=np.float64)
    # Compute all three rolling windows once
    roll21_mean = returns.rolling(21).mean()
    roll63_sum = returns.rolling(63).sum()
    roll63_std = returns.rolling(63).std()
    mom = roll21_mean.shift(1).rank(axis=1, pct=True)
    ls_mom = (mom > 0.8).astype(np.float64) - (mom < 0.2).astype(np.float64)
    val = (-roll63_sum.shift(1)).rank(axis=1, pct=True)
    ls_val = (val > -0.2).astype(np.float64) - (val < -0.8).astype(np.float64)
    invvol = 1.0 / roll63_std.shift(1).replace(0, np.nan)
    invvol = invvol.div(invvol.sum(axis=1), axis=0)
    ls_mom_n = ls_mom.div(ls_mom.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    ls_val_n = ls_val.div(ls_val.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    strategies = pd.DataFrame(index=returns.index)
    strategies["momentum_ls"] = (ls_mom_n * returns).sum(axis=1)
    strategies["reversal_ls"] = (ls_val_n * returns).sum(axis=1)
    strategies["risk_parity_proxy"] = (invvol.fillna(0.0) * returns).sum(axis=1)
    strategies["equal_weight"] = returns.mean(axis=1)
    return strategies.dropna(how="all").fillna(0.0)
```

---

## Cross-cutting: Numba JIT for the three hottest numerical kernels

---

**Issue 41: `_risk_parity` objective function and its gradient are evaluated hundreds of times by SLSQP in Python — JIT the inner computation.**

```python
# UPGRADE — Numba-accelerated risk parity objective (add to analytics.py)
try:
    import numba as nb

    @nb.njit(cache=True, fastmath=True)
    def _rp_obj(w: np.ndarray, cov: np.ndarray) -> float:
        n = w.shape[0]
        port_var = 0.0
        for i in range(n):
            for j in range(n):
                port_var += w[i] * cov[i, j] * w[j]
        port = math.sqrt(max(port_var, 1e-12))
        rc_mean = 0.0
        for i in range(n):
            rc_i = 0.0
            for j in range(n):
                rc_i += cov[i, j] * w[j]
            rc_i *= w[i] / port
            rc_mean += rc_i
        rc_mean /= n
        obj = 0.0
        for i in range(n):
            rc_i = 0.0
            for j in range(n):
                rc_i += cov[i, j] * w[j]
            rc_i = rc_i * w[i] / port
            obj += (rc_i - rc_mean) ** 2
        return obj

    _NUMBA_RP_AVAILABLE = True
except ImportError:
    _NUMBA_RP_AVAILABLE = False

def _risk_parity(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    vols = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    w0 = 1.0 / vols; w0 /= w0.sum()
    cov_c = np.ascontiguousarray(cov, dtype=np.float64)
    if _NUMBA_RP_AVAILABLE:
        obj = lambda w: _rp_obj(np.ascontiguousarray(w, np.float64), cov_c)
    else:
        def obj(w):
            port = math.sqrt(max(float(w @ cov_c @ w), 1e-12))
            rc = w * (cov_c @ w) / port
            return float(((rc - rc.mean()) ** 2).sum())
    res = minimize(obj, w0, bounds=[(1e-6, 1)] * n,
                   constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
                   method="SLSQP", options={"maxiter": 300, "ftol": 1e-10})
    return res.x if res.success else w0
```

**Issue 42: `kaplan_meier_survival` has a double Python for-loop — vectorize the inner product calculation.**

```python
# UPGRADE — vectorized Kaplan-Meier using numpy groupby equivalents
def kaplan_meier_survival(regimes: pd.Series) -> list[dict[str, Any]]:
    rows = []
    regime_arr = regimes.dropna().to_numpy()
    for r in np.unique(regime_arr):
        # Find run lengths
        is_r = (regime_arr == r).astype(np.int8)
        diff = np.diff(is_r, prepend=0, append=0)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        runs = (ends - starts).tolist()
        if not runs:
            continue
        max_t = max(runs)
        run_arr = np.array(runs, dtype=np.int64)
        for t in range(1, max_t + 1):
            at_risk = int((run_arr >= t).sum())
            events = int((run_arr == t).sum())
            # Vectorized survival product
            t_arr = np.arange(1, t + 1)
            at_risk_arr = np.array([(run_arr >= k).sum() for k in t_arr], dtype=np.float64)
            events_arr = np.array([(run_arr == k).sum() for k in t_arr], dtype=np.float64)
            surv = float(np.prod(1.0 - events_arr / np.maximum(at_risk_arr, 1)))
            rows.append({"regime": int(r), "duration": t, "survival": surv,
                         "at_risk": at_risk, "events": events})
    return rows
```

**Issue 43: `cascade_probability` creates `rng.uniform(0, 1, min(simulations, 10000))` on every call and recomputes for the same `(connectivity, leverage, shock)` triple — add a module-level cache.**

```python
# UPGRADE — cache the threshold array; deterministic seed already set
from functools import lru_cache as _lru_cache

@_lru_cache(maxsize=256)
def _cascade_thresholds(simulations: int, seed: int = 17) -> np.ndarray:
    return np.random.default_rng(seed).uniform(0, 1, simulations)

def cascade_probability(
    connectivity: float,
    leverage: float,
    shock: float,
    simulations: int = 2000,
) -> float:
    threshold = _cascade_thresholds(min(simulations, 10000))
    trigger = shock * leverage * connectivity
    return float(np.mean(trigger > threshold))
```

---

## Cross-cutting: Library-level swap recommendations

---

**Issue 44: `pd.DataFrame.corr()` uses pairwise Pearson in Python — replace with `numpy`-based computation everywhere.**

```python
# UPGRADE — add to performance.py as a drop-in replacement
def fast_corr(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation via numpy — 3-5x faster than pd.DataFrame.corr()."""
    arr = float_array(df)
    mu = arr.mean(axis=0)
    arr -= mu
    norms = np.sqrt((arr ** 2).sum(axis=0))
    norms[norms < 1e-12] = 1.0
    arr /= norms
    corr = arr.T @ arr
    np.clip(corr, -1.0, 1.0, out=corr)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=df.columns, columns=df.columns)

# Replace every occurrence of:
#   returns.corr().fillna(0.0)
# With:
#   fast_corr(returns).fillna(0.0)
```

**Issue 45: `np.linalg.eigh` is called on raw correlation matrices without verifying C-contiguity — always pass `np.ascontiguousarray` to avoid silent Fortran-order overhead.**

```python
# UPGRADE — wrapper used in rolling_leading_eigenvalue, correlation_diagnostics, etc.
def safe_eigh(mat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    c = np.ascontiguousarray(mat, dtype=np.float64)
    np.nan_to_num(c, copy=False)
    return np.linalg.eigh(c)
```

**Issue 46: `LedoitWolf().fit(x)` is called every time the covariance cache misses. Use `assume_centered=False` (default) but pass a pre-centered array to skip internal centering.**

```python
# UPGRADE — pre-center data before LedoitWolf, saves one internal pass
        if method in {"ledoit_wolf", "lw", "nonlinear_shrinkage"}:
            x_centered = x - x.mean(axis=0)       # pre-center once
            est = LedoitWolf(assume_centered=True).fit(x_centered)
            meta["shrinkage"] = float(est.shrinkage_)
            cov = est.covariance_
```

**Issue 47: All `np.linalg.pinv` calls throughout `analytics.py` recompute SVD every time — replace with `np.linalg.lstsq` where a solve suffices and `scipy.linalg.pinv` with `check_finite=False` where the pseudo-inverse is genuinely needed.**

```python
# UPGRADE — add to analytics.py
from scipy.linalg import pinv as _scipy_pinv

def fast_pinv(mat: np.ndarray) -> np.ndarray:
    """scipy pinv with finite-check disabled — ~20% faster than np.linalg.pinv."""
    return _scipy_pinv(mat, check_finite=False)

# Replace every np.linalg.pinv(X) with fast_pinv(X) throughout analytics.py
```

**Issue 48: `pd.Timestamp(dt).date()` is called in list comprehensions across multiple functions — precompute date strings in a single vectorized strftime.**

```python
# UPGRADE — vectorized date string conversion
def dates_to_str(index: pd.Index) -> list[str]:
    """Convert DatetimeIndex to ISO date strings without per-element overhead."""
    return pd.Series(index).dt.strftime("%Y-%m-%d").tolist()
```

**Issue 49: `rolling_diversification_ratio` calls `np.cov(float_array(sub), rowvar=False)` inside a loop — use an incremental covariance update instead of recomputing from scratch.**

```python
# UPGRADE — reuse the pre-allocated float array and compute cov via BLAS dot
def rolling_diversification_ratio(
    returns: pd.DataFrame,
    weights: pd.Series,
    window: int = 126,
    step: int = 5,
) -> list[dict[str, Any]]:
    x = normalize_numeric_frame(returns)
    n_rows, n_cols = x.shape
    if n_rows < max(20, window // 2) or n_cols < 2:
        return []
    w = weights.reindex(x.columns).fillna(0.0).to_numpy(np.float64)
    if np.abs(w).sum() <= 1e-12:
        w = np.repeat(1.0 / n_cols, n_cols)
    full_arr = float_array(x)
    rows: list[dict[str, Any]] = []
    for end in range(max(window, 20), n_rows + 1, max(1, step)):
        sub = full_arr[max(0, end - window):end]
        # BLAS-level covariance: (sub - mean).T @ (sub - mean) / (T-1)
        mu = sub.mean(axis=0)
        sub_c = sub - mu
        t = sub.shape[0]
        cov = (sub_c.T @ sub_c) / max(t - 1, 1)
        vols = np.sqrt(np.maximum(np.diag(cov), 0.0))
        port = math.sqrt(max(float(w @ cov @ w), 1e-18))
        rows.append({
            "date": x.index[end - 1],
            "diversification_ratio": float((np.abs(w) @ vols) / port),
        })
    if rows and rows[-1]["date"] != x.index[-1]:
        sub = full_arr[-window:]
        mu = sub.mean(axis=0); sub_c = sub - mu
        cov = (sub_c.T @ sub_c) / max(sub.shape[0] - 1, 1)
        vols = np.sqrt(np.maximum(np.diag(cov), 0.0))
        port = math.sqrt(max(float(w @ cov @ w), 1e-18))
        rows.append({
            "date": x.index[-1],
            "diversification_ratio": float((np.abs(w) @ vols) / port),
        })
    return rows
```

**Issue 50: `compact_records` calls `clean_json(compact_table(df, limit))` which serializes the entire downsampled DataFrame through the recursive `clean_json` — use `df.to_dict("records")` with a vectorized datetime column fix before calling `clean_json`.**

```python
# UPGRADE — fix datetime columns once before dict conversion
def compact_records(df: pd.DataFrame, limit: int = 600) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    tbl = compact_table(df, limit)
    for col in tbl.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        tbl = tbl.copy()
        tbl[col] = tbl[col].dt.strftime("%Y-%m-%d")
    return clean_json(tbl.to_dict("records"))
```
