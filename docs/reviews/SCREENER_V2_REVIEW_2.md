# Screener V2 Review: Memory, Determinism, Speed

Scope: panel.py, estimators.py, data_loader.py, fundamentals.py, pit_cache.py, backtest.py, validation.py, performance.py.
Not visible to me: stats.py (`_wilder_smooth`, `_pick`, `rank_pct`), currency.py, composite.py, academic.py, formula.py. Every edit that depends on them says so.
No Polars/pandas API was executed here. Re-check signatures against your pinned versions (for example `ewm_mean(min_samples=...)` was `min_periods` before Polars 1.21).

---

## 0. Executive summary

1. **The EMA bug and the memory problem share one root cause.** The window is cut from the *requested set's union calendar* and anchored on the *requested set's max date* (`performance._matrix` and `_subset_frame`), and only afterwards reindexed to SPY sessions. The fix is to define the session window from the calendar instrument first, then load each ticker into that fixed grid (E1, E2). This removes universe dependence, removes all pandas pivots, and removes three full-file scans per call.
2. **The 12-name backtest at 66 to 112 s is not compute, it is fixed overhead.** About 36 formation dates means roughly 2 to 3 s per panel for 12 names. A 12-name panel is microseconds of arithmetic. What costs seconds is a dozen or more `_subset_frame` calls per panel, each doing two passes over a ~10M-row file with a *computed* ticker predicate that defeats row-group pruning (E3, E4). Load once per backtest, slice per date.
3. **Your 50-name peak of 0.95 GB is almost certainly a static floor, not a compute peak.** Fifty names of market data is under 5 MB. The floor is interpreter plus imports (pandas, polars, scipy, statsmodels, pyarrow, roughly 250 to 350 MB) plus `master_fundamentals.parquet` loaded with all 364 columns and cached forever. Fundamentals is ranked #4 in your list. I would rank it #1 or #2 and it needs a one-line measurement to confirm (section 1). Column pruning is hash-safe.
4. **The full-universe overhead of about 2.0 GB above the floor equals roughly 65 to 85 live 756 x 3831 float64 frames** (23.2 MB each). That is exactly the number of simultaneous frames `latest_technical_features` creates. Most features only need the last 20 to 253 rows, so most frames should be 3x to 12x shorter, and the recursive ones (EMA, MACD, Wilder, ADX, RSI) should be precomputed (E5 to E9, section 4).
5. **Real correctness findings** beyond your list: PIT-cache key collisions across payloads (E12), SPY contaminating cross-sectional percentiles (E10), rebalance-period statistics grouped by fixed blocks instead of actual rebalances (E16), risk-free rate NaN for any backtest ending within Ken French's publication lag (E17), stale growth metrics with no recency bound (E15), `rank` inconsistent with sort order under ties (E11), and column names that lie when periods are overridden (E21).
6. **Precompute is the right plan, but only for time-series-only features.** Four features in `latest_technical_features` are cross-sectional (`bollinger_width_percentile`, `technical_percentile`, `amihud_percentile`, `short_term_reversal_flag`) and must stay at query time or the "same inputs, same hash" invariant is meaningless (section 4).
7. **Rust is premature.** After E1 to E9 the remaining heavy work is Wilder/ADX/RSI recursions, which Numba or a Polars expression covers. Reserve PyO3 for the scoring loop in validation.py if and only if profiling still shows it after the precompute lands.

---

## 1. What your own measurements imply (arithmetic, not opinion)

| Quantity | Value | Consequence |
|---|---|---|
| One T x N float64 frame, T=756, N=3831 | 23.2 MB | 1016-row windows: 31.1 MB |
| Full run minus 50-name run (2.97 GB vs 0.95 GB) | ~2.0 GB | 2.0 GB / 23.2 MB is about 86 frame-equivalents; per name about 0.52 MB |
| Per-name scaling | ~0.52 MB per name | Consistent with ~65 to 85 simultaneous frames, not with the 3 lru caches alone (max 18 x 31 MB = 560 MB) |
| 50-name peak | 0.95 GB | Market data for 50 names is under 5 MB, so the floor is imports plus fundamentals |
| Backtest, 12 names | 66 to 112 s | About 36 formations (1008 sessions / 21), so 1.8 to 3.1 s per panel for 12 names, which is scan overhead |

**Measure these three numbers before touching anything else** (5 minutes):

```python
import pandas as pd, sys
from app.services.screener_v2.core import data_loader as dl
f = dl.load_fundamentals()
print("rows", len(f), "cols", f.shape[1], "MB", f.memory_usage(deep=True).sum() / 1e6)
print(f.memory_usage(deep=True).sort_values(ascending=False).head(15) / 1e6)   # which columns dominate (object columns first)
```
```bash
python -X importtime -c "import app.services.screener_v2.core.estimators" 2> imports.txt   # then sort by cumulative column
python - <<'PY'
import resource, psutil, os
print("rss MB", psutil.Process(os.getpid()).memory_info().rss/1e6)
PY
```
On macOS, `ru_maxrss` is in **bytes** (Linux reports KB), and RSS does not include compressed pages. For the real pressure number use `footprint -p <pid>` (phys_footprint). A fanless Air under memory compression can show an RSS that understates what the OS is actually holding.

Pushdown check (decides whether DuckDB, streaming, and every other engine "failed" for a single shared reason):

```python
lf = dl.load_market_frame().filter(dl.NORMALIZED_TICKER.is_in(["AAPL", "MSFT"]))
print(lf.explain())   # if the filter appears as a FILTER node above the scan, not as scan SELECTION/predicate, nothing is pruned
```
A predicate on `str.strip_chars().str.to_uppercase().str.replace_all(...)` cannot use parquet row-group statistics. Every engine then reads the full Ticker column and normalizes about 10M strings per call. That is a plausible common cause for "streaming, DuckDB, jemalloc: no gain".

---

## 2. Edit index (ordered by return on effort)

| ID | File | Kind | Gain | Changes today's hashes? |
|---|---|---|---|---|
| E1 | performance.py | Fix EMA bug, calendar-first window, `market_window` | Determinism, -3 scans/call, -pandas pivots | Yes, only where old output was universe-contaminated |
| E2 | estimators.py | Use E1, delete pivots, tail-slice | Memory, time | Same as E1 |
| E3 | performance.py / pit_cache.py | Load once per backtest, slice per date | 66 to 112 s to likely under 10 s | No |
| E4 | data_loader.py | Pre-normalized, sorted, pruneable market store | Scan time, memory | No |
| E5 | data_loader.py | Prune fundamentals columns | Likely 0.5 to 0.8 GB | No |
| E6 | fundamentals.py | Avoid full-frame copies in `statement_snapshots` | ~2 transient copies | No |
| E7 | estimators.py | Vectorize beta, OBV slope, run lengths, cross ages | Seconds, small memory | Float noise ~1e-12 |
| E8 | estimators.py | Tail slicing for rolling features, Yang-Zhang | 3x to 12x smaller frames | No |
| E9 | estimators.py | Wilder family: one kernel, no `.apply`, dedupe ATR/ATR_DM | Seconds | Depends on `_wilder_smooth` |
| E10 | estimators.py | Percentiles after reindex (SPY contamination) | Correctness | Yes for 4 columns |
| E11 | panel.py | `rank` consistent with sort, drop scan for date | Correctness, 2 scans | `rank` on ties |
| E12 | validation.py | PIT cache key collisions, copies | Correctness | No |
| E13 | pit_cache.py | Remove monkeypatching, bound panel memory | Maintainability, memory | No |
| E14 | performance.py | Byte-budget caches instead of `maxsize=6` x3 | Memory ceiling | No |
| E15 | fundamentals.py | Vectorize growth, add recency bound | Time, correctness | Yes (stale rows drop out) |
| E16 | validation.py | Rebalance-period stats from real rebalance flags | Correctness | Yes, 3 stats |
| E17 | validation.py | Risk-free lag handling | Correctness | Yes, fills NaNs |
| E18 | backtest.py | Missing-price policy, small perf items | Robustness | No by default |
| E19 | data_loader.py | One normalizer | Drift risk | No |
| E20 | estimators.py | `statsmodels` and `scipy` removal | -60 to -100 MB import floor (measure) | Float noise |
| E21 | estimators.py | Column names that lie | Correctness | Rename only |

---

## 3. Line-by-line edits

### E1. performance.py: calendar-first window (the EMA fix) and `market_window`

**Issue (high).** `_matrix` does: `_subset_frame(symbols, lookback+260, ...)`, where the anchor is `query.select(Date.max())` over the *requested symbols*, then `pivot(...).tail(lookback)` over the *requested symbols' union calendar*. `_session_matrix` then reindexes to the last N SPY sessions. If the union calendar has more rows per year than SPY (any Sunday to Thursday exchange such as Tadawul or TASE, plus every foreign holiday mismatch), `tail(756)` of the union covers fewer than 756 SPY sessions. The head of the SPY grid is NaN for that run and not for a 50 US-name run. `ewm(adjust=False)` seeds at the first non-NaN, so the seed date moves with the universe. A second coupling is the anchor: one ticker with a stray late date moves the window for everyone that shares a call with it.

**Magnitude check, so you know what you are looking for.** EMA weight on the seed after n observations is (1 - 2/(span+1))^(n-1). For span 200: n=756 gives 5.3e-4; n=606 gives 2.3e-3; n=486 gives 7.8e-3. A 2.2% error on `ema_200` therefore needs a head offset of several hundred rows, or a large price move between seed date and now. Union-calendar inflation from Sunday-Thursday markets explains a head offset of roughly 100 to 200 rows, so it is probably necessary but may not be sufficient. Run this to confirm before you rely on my hypothesis:

```python
a = dl.close_matrix(sub50 + ["SPY"], 756); b = dl.close_matrix(full_universe, 756)
cols = [c for c in a.columns if c in b.columns]
fa = a[cols].apply(pd.Series.first_valid_index); fb = b[cols].apply(pd.Series.first_valid_index)
print((fa != fb).sum(), "tickers with a different first valid date")
print(a.index[0], b.index[0], len(a), len(b))
common = a.index.intersection(b.index)
print((a.loc[common, cols].fillna(-1) != b.loc[common, cols].fillna(-1)).any(axis=1).sum(), "dates with price mismatches")
```
If the last line is nonzero, the price data itself differs (alias or standardization path), which is a second bug.

**Solution.** Define the session grid from the calendar instrument only; load each ticker into that fixed grid; build wide float64 arrays directly with `searchsorted` (no pandas pivot, no long pandas frame, no intermediate copies).

```diff
--- a/performance.py
+++ b/performance.py
-def _subset_frame(symbols: tuple[str, ...], lookback_days: int | None, columns: tuple[str, ...] | None, as_of) -> pl.DataFrame:
+def _subset_frame(symbols: tuple[str, ...], lookback_days: int | None, columns: tuple[str, ...] | None, as_of, start=None) -> pl.DataFrame:
     ...
     if as_of is not None:
         query = query.filter(pl.col("Date") <= pd.Timestamp(as_of))
+    if start is not None:
+        query = query.filter(pl.col("Date") >= pd.Timestamp(start))
     if lookback_days:
```

Add (new, same file):

```python
@lru_cache(maxsize=16)
def _calendar_versioned(calendar: str, version: int) -> np.ndarray:
    frame = _subset_frame((calendar,), None, ("Ticker", "Date", "Close"), None)
    return np.sort(frame["Date"].unique().to_numpy()).astype("datetime64[ns]")


def session_dates(calendar: str, n: int, as_of=None) -> np.ndarray:
    """The last n observed sessions of the calendar instrument at or before as_of. Independent of the screened universe."""
    from . import data_loader
    cal = _calendar_versioned(data_loader.normalize_symbol(calendar), _market_version())
    if as_of is not None:
        cal = cal[: np.searchsorted(cal, pd.Timestamp(as_of).to_datetime64().astype("datetime64[ns]"), side="right")]
    return cal[-int(n):]


_FIELDS = ("Open", "High", "Low", "Close", "Volume")


def market_window(symbols, dates: np.ndarray, fields: tuple[str, ...] = _FIELDS):
    """(tickers, {field: T x N float64}) on exactly `dates`. Rows of a ticker on non-calendar days are dropped,
    which is what reindexing to the calendar did before. Columns are sorted like the old matrices."""
    from . import data_loader
    names = tuple(sorted({data_loader.normalize_symbol(s) for s in symbols if str(s).strip()}))
    if not names or not len(dates):
        return [], {f: np.empty((len(dates), 0)) for f in fields}
    frame = _subset_frame(names, None, ("Ticker", "Date", *fields), as_of=dates[-1], start=dates[0])
    if not frame.height:
        return [], {f: np.empty((len(dates), 0)) for f in fields}
    runs = frame["Ticker"].cast(pl.String).rle().struct.unnest()      # frame is sorted by Ticker, Date
    tickers = runs["value"].to_list()
    codes = np.repeat(np.arange(runs.height), runs["len"].to_numpy())
    stamp = frame["Date"].to_numpy().astype("datetime64[ns]")
    pos = np.searchsorted(dates, stamp)
    hit = pos < len(dates)
    hit[hit] = dates[pos[hit]] == stamp[hit]
    out = {}
    for f in fields:
        m = np.full((len(dates), len(tickers)), np.nan)
        m[pos[hit], codes[hit]] = frame[f].to_numpy()[hit]
        out[f] = m
    return tickers, out
```

Then `data_loader.close_matrix`/`volume_matrix` become thin wrappers (the `as_of` branch and the cached branch collapse into one, because the grid is already as-of aware):

```diff
--- a/data_loader.py
+++ b/data_loader.py
-def _session_matrix(frame, lookback_days): ...
-def close_matrix(...): ...
-def volume_matrix(...): ...
+def _field_matrix(symbols, lookback_days, field):
+    from .currency import CONFIG
+    from .performance import market_window, session_dates
+    calendar = CONFIG.get().get("calendar_ticker")
+    if not calendar:
+        raise ValueError("calendar_ticker is required: a union-calendar window depends on the screened universe")
+    dates = session_dates(calendar, int(lookback_days), AS_OF.get())
+    tickers, wide = market_window(symbols, dates, (field,))
+    frame = pd.DataFrame(wide[field], index=pd.DatetimeIndex(dates, name="Date"), columns=pd.Index(tickers, dtype=object, name="Ticker"))
+    return frame.dropna(axis=1, how="all")
+
+def close_matrix(symbols, lookback_days=756): return _field_matrix(symbols, lookback_days, "Close")
+def volume_matrix(symbols, lookback_days=756): return _field_matrix(symbols, lookback_days, "Volume")
```
`returns_matrix` keeps working because it calls `close_matrix` in the as-of branch; the non-as-of branch still uses `cached_returns_matrix`, which calls `_cached_close_matrix_versioned`. Point that at `_field_matrix` as well (or delete the cache, see E14) so the two branches cannot diverge.

**Decision to document.** With no calendar instrument the window is universe dependent by construction. I made it an error. If you need a calendar-less mode, make it explicit and exclude it from the determinism guarantee.

---

### E2. estimators.py: head of `latest_technical_features`

**Issue (high).** Lines from `raw_ohlcv = ohlcv_for_symbols(...)` through `del raw_ohlcv` do: one long pandas frame (about 4M rows x 7 columns, object Ticker column), two matrix builds (E1's bug), three more `pivot_last` calls (each an unstack with transient copies of several times the output), a second as-of branch that overrides the first, and a separate full-file read of SPY. The as-of branch also uses `periods["as_of_date"]` only, while `close_matrix` reads the `AS_OF` ContextVar: if only the ContextVar is set, under `pit_scope` the patched `_skip_close_matrix` returns an empty frame and `prices.empty` returns `["ticker"]` silently.

**Solution.** One call, five arrays, no pandas long frame.

```diff
--- a/estimators.py
+++ b/estimators.py
-    raw_ohlcv = ohlcv_for_symbols(fetch_symbols, lookback_days=max(lookback_days, 300))
-    prices = close_matrix(fetch_symbols, lookback_days=max(lookback_days, 260))
-    volumes = volume_matrix(fetch_symbols, lookback_days=max(lookback_days, 260))
-    as_of_date = pd.to_datetime(periods.get("as_of_date"), errors="coerce") if periods.get("as_of_date") else None
-    ... (entire block through) ...
-    del raw_ohlcv
+    from .currency import CONFIG
+    from .data_loader import AS_OF
+    from .performance import market_window, session_dates
+    calendar_symbol = CONFIG.get().get("calendar_ticker", "SPY")
+    if not calendar_symbol:
+        raise ValueError("calendar_ticker is required for deterministic technicals")
+    as_of = periods.get("as_of_date") or AS_OF.get()
+    if as_of is not None and pd.isna(pd.Timestamp(as_of)):
+        raise ValueError("Invalid as_of_date")
+    dates = session_dates(calendar_symbol, max(lookback_days, 260), as_of)
+    if not len(dates):
+        raise ValueError("calendar_ticker has no observed sessions")
+    tickers, wide = market_window(fetch_symbols, dates)
+    live = ~np.isnan(wide["Close"]).all(axis=0)                 # old pivot_last dropped all-NaN columns
+    index = pd.DatetimeIndex(dates, name="Date")
+    columns = pd.Index([t for t, k in zip(tickers, live) if k], dtype=object, name="Ticker")
+    def _frame(field):
+        return pd.DataFrame(wide[field][:, live], index=index, columns=columns)
+    prices, volumes, highs, lows, opens = (_frame(f) for f in ("Close", "Volume", "High", "Low", "Open"))
+    del wide
```
`prices.empty` check stays. All five frames now share columns and index, so the `tr_columns = ranges[0].columns.union(...)` dance and `_pivot_ohlc_field` are dead: delete both. The calendar reindex block (`calendar_quotes`, `session_dates`, `prices.reindex`, `volumes.reindex`, `raw_ohlcv[raw_ohlcv.Date.isin(...)]`) is deleted too.

Because `estimators.close_matrix` and `volume_matrix` are no longer called, `pit_cache._skip_close_matrix`/`_skip_volume_matrix` and their two rebinds become dead (see E13). Keep the two imports in estimators until pit_cache is edited, otherwise `pit_cache` fails with `AttributeError` at import (`_close_matrix = estimators.close_matrix`).

---

### E3. Load once per backtest, slice per formation date

**Issue (high, time).** Count `_subset_frame` invocations for one `metric_panel` call: `latest_technical_features` 2 + 2 (matrices) + 2 (SPY sessions inside `_session_matrix` x2) + 1 (calendar), `latest_fundamental_features` 1 + 1, `metric_panel` 1. Each `_subset_frame` does `max(Date)` pass, then the data pass. That is on the order of 20 full-file scans per formation date, per backtest, multiplied by the weekday variants. This matches 2 to 3 s per 12-name panel.

**Solution.** The window for every formation date is a slice of one superset window. Prefetch once in `score_backtest` and store in the existing PIT memo.

Move the ContextVar to performance.py so there is no import cycle:

```python
# performance.py
from contextvars import ContextVar
_MEMO = ContextVar("screener_pit_memo", default=None)   # pit_cache imports this instead of owning it
```
```python
def prefetch_window(symbols, dates: np.ndarray):
    memo = _MEMO.get()
    if memo is None:
        return
    tickers, wide = market_window(symbols, dates)
    memo[("window", tuple(sorted(set(tickers))))] = (dates, tickers, wide)
```
and at the top of `market_window`:

```python
    memo = _MEMO.get()
    if memo is not None:
        for key, (full_dates, full_tickers, full) in memo.items():
            if isinstance(key, tuple) and key and key[0] == "window":
                lo = np.searchsorted(full_dates, dates[0]); hi = np.searchsorted(full_dates, dates[-1], side="right")
                if hi - lo == len(dates) and full_dates[lo] == dates[0] and set(names) <= set(full_tickers):
                    sel = [full_tickers.index(t) for t in names if t in set(full_tickers)]
                    return [full_tickers[i] for i in sel], {f: full[f][lo:hi][:, sel] for f in fields if f in full}
```
In `score_backtest`, after `calendar` is built, call `prefetch_window(symbols + [calendar_symbol, "SPY"], calendar_with_warmup)` inside `pit_scope`. Warmup is `max(lookback, 260)` sessions before the first formation date. Point-in-time safety is preserved because each per-date slice ends at `dates[-1] <= as_of`; the memo never exposes a row after the slice end. Add a unit test for exactly that (section 6, test 2).

Also stop re-scanning for scalar dates: in `metric_panel`, `observed = ohlcv_for_symbols(symbols + ["SPY"], 1); latest_price_date = observed.Date.max()` becomes `latest_price_date = pd.Timestamp(session_dates(cal, 1, as_of)[-1])`. This follows the semantics your own `default_as_of` docstring already argues for ("not another asset's newer quote"). The same replacement applies to `latest_fundamental_features` (`market = ohlcv_for_symbols(symbols, 1)` just to get a cutoff date).

---

### E4. data_loader.py / market file: make the predicate pushable

**Issue (high).** `NORMALIZED_TICKER.is_in(list(symbols))` is a computed expression. Row-group pruning and dictionary pushdown cannot apply. The `_market_derived` pattern you already built is the right idea, applied only to two summaries.

**Solution.** Materialize once per market-file version a *clean store* next to it and read that for all hot paths.

Write-time (reuse `_market_derived`'s atomic-rename and version key):

```python
CLEAN = MARKET_CACHE_DIR / f"market_clean_{version}.parquet"
lf = (pl.scan_parquet(MARKET_UNIVERSE).select(OHLCV_COLUMNS)
        .with_columns(NORMALIZED_TICKER, pl.col("Date").cast(pl.Date)))
frame, integrity = _standardize_frame(lf.collect())          # still one-time, still validates aliases and bad closes
frame.write_parquet(tmp, compression="zstd", compression_level=3,
                    row_group_size=131_072, statistics=True)  # sorted by Ticker, Date already
```
Read-time: `pl.scan_parquet(CLEAN).filter(pl.col("Ticker").is_in(names) & (pl.col("Date") >= start) & (pl.col("Date") <= end))`. With the file sorted by Ticker and row groups of 131k rows, each ticker occupies one to a few row groups and the `Ticker` min/max stats prune the rest. Dates are pruned within them.

Keep the original `_subset_frame` as the fallback when no clean store exists, and keep `market_source_integrity()` semantics by persisting `integrity` as JSON beside the store. Keep float64 for OHLCV: float32 would break hash identity.

Check with `lf.explain()` that the predicate is now at the scan. If it is, expect a per-call cost in milliseconds.

---

### E5. data_loader.py: prune fundamentals columns (probably the biggest single memory edit)

**Issue (high).** `pd.read_parquet(MASTER_FUNDAMENTALS)` loads all columns (your own comment in `statement_snapshots` says 364), keeps them forever in an `lru_cache`, then `statement_snapshots` copies the frame at least twice (`source[source.ticker.isin(symbols)]`, then `frame.sort_values(...).drop_duplicates(...)` for `base`). `_fundamentals_frame` in performance.py shares the same object, and `cached_fundamental_history` slices 364 columns per ticker, 512 of them cached. If the file holds R rows, the resident cost is about 8 x 364 x R bytes per copy. Measure it with the snippet in section 1.

**Solution.** Read only the columns this module family uses.

```python
FUNDAMENTAL_COLUMNS = (
    "ticker", "reportDate", "periodType", "exchange", "fullExchangeName", "sector", "industry",
    # flows
    "Total Revenue", "Gross Profit", "EBIT", "Operating Income", "EBITDA", "Net Income", "Operating Cash Flow",
    "Free Cash Flow", "Interest Expense", "Interest Expense Non Operating", "Cash Dividends Paid",
    "Common Stock Dividend Paid", "Dividend Paid Cfo", "Repurchase Of Capital Stock", "Issuance Of Capital Stock",
    "Tax Provision", "Pretax Income",
    # balance sheet
    "Total Assets", "Total Liabilities Net Minority Interest", "Current Assets", "Current Liabilities",
    "Cash And Cash Equivalents", "Total Debt", "Retained Earnings", "Inventory", "Net PPE",
    "Diluted Average Shares", "Basic Average Shares", "Ordinary Shares Number",
    "Stockholders Equity", "Common Stock Equity", "Preferred Stock Equity", "Preferred Stock",
    "Minority Interest", "Total Equity Gross Minority Interest",
    # growth
    "Diluted EPS", "Basic EPS",
)
```
```diff
-    df = pd.read_parquet(MASTER_FUNDAMENTALS, engine="pyarrow")
+    available = set(pq.read_schema(MASTER_FUNDAMENTALS).names)
+    df = pd.read_parquet(MASTER_FUNDAMENTALS, columns=[c for c in FUNDAMENTAL_COLUMNS if c in available], engine="pyarrow")
```
This list is derived from fundamentals.py only. The vendor snapshot columns (`marketCap`, `trailingPE`, ...) are deliberately NaN'd and then overwritten with computed values, so they are not needed. Before merging, `grep -rn "load_fundamentals\|latest_fundamentals\|fundamental_history\|_pick(" backend/app/services/screener_v2` and add any column that composite.py, academic.py or formula.py read directly. Also run both a 50-name and a full-universe screen and assert the output hash is unchanged. If `_pick` falls back to alias spellings you have not listed (`totalRevenue`, `revenue`, `operatingIncome`), add those that exist in the schema.

Second-order wins in the same function: cast low-cardinality strings to category (`sector`, `industry`, `exchange`, `periodType`), and normalize `ticker` through a dict over `unique()` rather than `Series.map(normalize_symbol)` per row.

---

### E6. fundamentals.py: `statement_snapshots`

**Issue (medium).**
- `frame = source[source.ticker.isin(symbols)]`: with a full universe this is a full copy.
- Loop `for field in fields: base[field] = rolling[field].reindex(...).fillna(annual[field].reindex(...))` is fine, but `quarters.groupby("ticker")[fields].rolling(4, min_periods=4).sum()` allocates a MultiIndex frame the size of the quarterly slice.
- Called per `symbols` tuple, memoized by `_shared_statements` under a 3831-string tuple key (hashing 3831 strings every call).

**Solution.** Take rows by position from the existing `groupby.indices` dict, and key the memo by a digest.

```diff
-    source = load_fundamentals()
-    frame = source[source.ticker.isin(symbols)]
+    from .performance import _fundamentals_positions, _fundamentals_version
+    source = load_fundamentals()
+    positions = _fundamentals_positions(_fundamentals_version())
+    take = np.concatenate([positions[s] for s in symbols if s in positions] or [np.empty(0, dtype=np.intp)])
+    frame = source.take(np.sort(take))
```
and in pit_cache: `key = ("statements", hashlib.blake2b("\0".join(symbols).encode(), digest_size=16).hexdigest())`.

Note a point-in-time soundness caveat for your methodology section: `reportDate + 90 days` is a proxy for availability, not a filing date. It is conservative for US 10-K/10-Q filers and for Indian quarterlies (45 days), but a late filer or a restatement can still leak. If you can source `acceptedDate` or `filingDate`, switch `eligible_reports` to it and keep 90 days only as the fallback.

---

### E7. estimators.py: vectorize the per-column Python loops

Each of the following is a `DataFrame.apply(lambda col: ...)` over 3,831 columns, which means 3,831 Series constructions and interpreter round trips per call.

**(a) Beta.** Current: `usd_returns.tail(252).apply(lambda col: col.cov(market))` then masks to complete columns. Equivalent closed form on the complete columns only:

```python
window = usd_returns.tail(252)
market = window["SPY"]
var = market.var()
if market.notna().all() and var and var > 0:
    complete = window.notna().all()
    r = window.loc[:, complete].to_numpy()
    m = market.to_numpy()
    beta = ((r - r.mean(axis=0)) * (m - m.mean())[:, None]).sum(axis=0) / (len(m) - 1) / var
    out["beta_252"] = pd.Series(beta, index=window.columns[complete.to_numpy()]).reindex(out.index)
else:
    out["beta_252"] = np.nan
```

**(b) OBV slope.** Current: full-history `cumsum`, then `linregress` per column on the last 20 rows requiring `notna().all()`. The slope is invariant to the additive offset of the cumulative sum, and an OBV value is NaN exactly when that day's signed volume is NaN, so only 21 rows are needed:

```python
sv = (np.sign(prices.tail(21).diff()) * volumes.tail(21)).tail(20).to_numpy()
ok = ~np.isnan(sv).any(axis=0)
x = np.arange(20) - 9.5                         # sum(x) == 0, so no centring of y is needed
slope = (x[:, None] * np.cumsum(sv, axis=0)).sum(axis=0) / (x ** 2).sum()
out["obv_20d_slope"] = pd.Series(np.where(ok, slope, np.nan), index=prices.columns).reindex(out.index)
```
Delete `from scipy.stats import linregress` and the full-size `signed_volume` and `obv` frames. Expect relative differences of about 1e-12 (the new cumsum starts at zero, so it is numerically better conditioned).

**(c) Trailing run lengths** (`consecutive_up_days`, `consecutive_down_days`; today a Python loop over 756 elements per column per side):

```python
def _trailing_run(mask: pd.DataFrame) -> pd.Series:
    a = mask.to_numpy(dtype=bool)
    last_false = np.where(~a, np.arange(a.shape[0], dtype=np.int32)[:, None], -1).max(axis=0)
    return pd.Series(a.shape[0] - 1 - last_false, index=mask.columns)
out["consecutive_up_days"] = _trailing_run(rets.gt(0))
out["consecutive_down_days"] = _trailing_run(rets.lt(0))
```
`rets.gt(0)` is already False at NaN, which matches `fillna(False)`.

**(d) Cross ages** (`_last_sign_cross_age`, called on three frames). For columns with no NaN in the window, the age is simply the number of steps since the last sign change. With `s = np.sign(a)`, `change = s[1:] != s[:-1]` and the age equals `np.argmax(change[::-1], axis=0)` where `change.any(axis=0)`, else NaN. Use it for complete columns and fall back to the existing function for the (rare) columns with NaN, because the current function drops NaN before differencing and that compaction semantics must be preserved:

```python
def _cross_ages(frame: pd.DataFrame) -> pd.Series:
    a = frame.to_numpy(dtype=float)
    out = pd.Series(np.nan, index=frame.columns)
    complete = ~np.isnan(a).any(axis=0)
    if complete.any():
        s = np.sign(a[:, complete]); change = s[1:] != s[:-1]
        age = np.argmax(change[::-1], axis=0).astype(float)
        out.loc[complete] = np.where(change.any(axis=0), age, np.nan)
    for col in frame.columns[~complete]:
        out[col] = _last_sign_cross_age(frame[col])
    return out
```
Test it against the old function on random data with injected NaNs (section 6, test 5). `_last_event_age` for golden/death age can be done the same way on `cross_50_200.tail(cross_lookback)`.

---

### E8. estimators.py: only compute what is needed, on only the rows it needs

**Issue (high, memory).** Every rolling feature is built over the full 756 rows, then `.iloc[-1]` or `.tail(k)` is taken. Examples: `smas[window]` for all four windows over 756 rows; `bb_*` four frames; `rets` (756 rows) used only through `.tail(252)`; `usd_prices` and `traded_usd` full size though used through `.tail(20)`, `.tail(63)`, `.tail(253)`; Yang-Zhang logs over 756 rows then `.tail(63)`; `low14`, `high14`, `stoch_k` full size then `iloc[-1]`.

**Solution.** Slice first. The row requirement per feature:

| Feature family | Rows needed |
|---|---|
| returns, momentum_jt, return_12m, beta, relative return | 253 |
| SMA 20/50/100/200 value and today-cross | window + 1 |
| SMA cross ages (lookback L, default 20) | window + L |
| Bollinger, stochastic, Williams %R | 20 + 14 + 3 |
| Yang-Zhang 63 | 64 |
| amihud, dollar volume, volume | 21 |
| EMA, MACD, ATR, ADX, RSI | full history (recursive): precompute, E5 of section 4 |

Pattern (changes memory only, numerics unchanged because rolling windows on a suffix equal rolling windows on the whole when the suffix is long enough):

```python
px253 = prices.tail(253)
usd_prices = usd_price_matrix(prices.tail(253))          # was the full 756 x N matrix
rets = px253.pct_change(fill_method=None)
...
smas[window] = prices.tail(window + cross_lookback).rolling(window).mean()
```
Yang-Zhang on 64 rows (identical rows used because `tail(63)` of a 64-row slice equals `tail(63)` of the full frame, and the first row only supplies `shift(1)`):

```python
o, h, l, c = (x.tail(64) for x in (opens, highs, lows, prices))
valid = o.gt(0) & h.gt(0) & l.gt(0) & c.gt(0)
o, h, l = o.where(valid), h.where(valid), l.where(valid)
prev = c.shift(1)
log_overnight = np.log(o / prev.where(prev.gt(0))).replace([np.inf, -np.inf], np.nan)
log_open_close = np.log(c / o).replace([np.inf, -np.inf], np.nan)
rs = (np.log(h / o) * np.log(h / c) + np.log(l / o) * np.log(l / c)).replace([np.inf, -np.inf], np.nan)
# then .tail(63) exactly as before
```
Also: the `len(prices) > 252` style guards must keep using the *full* length, not the slice length.

Expected effect: about 3x fewer live rows for the frames that are not recursive, and one frame (`usd_prices`) goes from 23 MB to 7.7 MB. Together with E2 and the precompute this is the path from about 85 frame-equivalents to single digits.

---

### E9. estimators.py: Wilder family (ATR, ADX/DMI, RSI)

**Issue (high, time).** `_wilder_smooth` is applied through `DataFrame.apply` seven times (`atr`, `atr_dm`, `plus_dm`, `minus_dm`, `dx`, `gain`, `loss`), i.e. about 27,000 Python calls per run. With the default periods `atr_period == adx_period == 14`, `atr` and `atr_dm` are the same computation done twice.

**Solution.**
1. `atr_dm = atr if adx_period == atr_period else tr.apply(...)`, then `.replace(0, np.nan)` on a copy. Zero risk.
2. One 2-D kernel for all columns at once. I cannot see `_wilder_smooth`, so mirror its NaN and seed semantics exactly. The textbook version is below; Numba on arm64 is fine.

```python
from numba import njit

@njit(cache=True)
def wilder_2d(x: np.ndarray, n: int) -> np.ndarray:
    T, N = x.shape
    out = np.full((T, N), np.nan)
    for j in range(N):
        count = 0; acc = 0.0; state = np.nan
        for i in range(T):
            v = x[i, j]
            if np.isnan(v):
                continue                      # replace by whatever _wilder_smooth does at gaps (reset or carry)
            if count < n:
                count += 1; acc += v
                if count == n:
                    state = acc / n; out[i, j] = state
            else:
                state = state + (v - state) / n; out[i, j] = state
    return out
```
Alternative with no new dependency: `pl.DataFrame(arr).select(pl.all().ewm_mean(alpha=1/n, adjust=False, min_samples=n))` is only correct if `_wilder_smooth` seeds with the first observation instead of an n-period mean. These differ for the first ~5n observations, which matters for young tickers. Decide this once and write it into the precompute spec. Convert NaN to null first (`fill_nan(None)`); Polars treats NaN as a value and will poison the recursion.

Pytest the kernel against the old function on gappy data before swapping (section 6, test 5).

---

### E10. estimators.py: SPY inside cross-sectional percentiles

**Issue (medium).** `fetch_symbols` includes `"SPY"`, and `bollinger_width_percentile`, `amihud_percentile`, `short_term_reversal_flag` and `technical_percentile` are ranked over `out`, which still contains SPY and every name that is later dropped by `dropped_symbols`. `out.reindex(requested)` happens after. The percentile of a stock therefore depends on whether SPY is in `fetch_symbols` (always true today, so no visible nondeterminism, but the result differs from what the user screened).

**Solution.** Move the five percentile assignments below `out = out.reindex([s for s in requested_symbols if s in out.index])`. Hash impact: those four columns.

Also, these four columns plus everything computed from them in panel.py are **cross-sectional**. They are explicitly excluded from the precompute (section 4).

---

### E11. panel.py

**Issue 1 (medium).** `panel["rank"]` uses `rank(method="first")` on `core_quant_score` in input order, then the frame is sorted by `["core_quant_score", "dollar_volume_20d"]`. Ties in the score are broken by dollar volume in the row order and by input order in `rank`. They disagree.

```diff
-    panel["rank"] = panel["core_quant_score"].rank(ascending=False, method="first").astype("Int64")
-    return panel.sort_values(["core_quant_score", "dollar_volume_20d"], ascending=False).reset_index(drop=True)
+    panel = panel.sort_values(["core_quant_score", "dollar_volume_20d", "ticker"], ascending=[False, False, True], kind="stable").reset_index(drop=True)
+    panel["rank"] = pd.array(np.where(panel["core_quant_score"].notna(), np.arange(1, len(panel) + 1), pd.NA), dtype="Int64")
+    return panel
```
Adding `ticker` as the final key makes the order fully deterministic when both numeric keys tie (a latent hash instability). Add `import numpy as np`.

**Issue 2.** `valuation_percentile` and `quality_percentile` are accessed with `panel[...]`: when `tech.empty` and `fund` lacks a column this raises `KeyError` instead of a clear message. Cheap guard: `missing = [c for c in needed if c not in panel]; if missing: raise ValueError(...)`.

**Issue 3.** `pe_sector_percentile`: `positive_pe.groupby(panel["sector"]).rank(pct=True, ascending=False) * 100.0` is not the same scale as `_group_rank_pct` (which maps to 0..100 via (rank-1)/(n-1)). If both feed a score, the mismatch is silent. Use `_group_rank_pct` with a sign flip for consistency.

**Issue 4.** The `observed` scan (E3).

---

### E12. validation.py: PIT cache correctness and copies

**Issue 1 (high, silent wrong answers).** `panels[("panel", date)]` and `panels[("academic", date)]` are keyed by date only, but `shared_cache` can be passed by the caller and reused across calls (it is a parameter). A second call with a different `symbols`, filter payload, `lookback_days`, period overrides, or `kind` returns a stale panel. `("statements", tuple(symbols))` is the only key that includes the symbol set.

```diff
+    import hashlib, json
+    fingerprint = hashlib.blake2b(json.dumps({"s": list(symbols), "p": payload}, sort_keys=True, default=str).encode(), digest_size=12).hexdigest()
     def panel_at(date):
-        key = ("panel", pd.Timestamp(date))
+        key = ("panel", fingerprint, pd.Timestamp(date))
...
-                    academic_key = ("academic", key)
+                    academic_key = ("academic", fingerprint, key)
```
`component_scores(panel, ..., history_cache=panels)` reads from the same dict; verify that it uses compatible keys (I cannot see composite.py).

**Issue 2 (medium, memory).** `panels` holds the full panel for every formation date. At full universe: 3831 names x ~250 columns x 8 B = 7.7 MB per date, 36 dates is about 280 MB, times five for `score_backtest_by_weekday` if the dict is shared. `panel_at` also returns `.copy()` on every call and `score_at` calls it once per date.

```diff
-    def panel_at(date):
+    def panel_at(date, copy=True):
...
-        return panels[key].copy()
+        return panels[key].copy() if copy else panels[key]
...
-                panel = panel_at(key)
+                panel = panel_at(key, copy=(kind == "formula"))        # only the formula branch mutates the frame
```
If the composite scorer needs history, keep only the columns it reads in the long-lived cache, and spill the rest: `panels[key] = frame[needed_cols]`, or `frame.to_parquet(tmp)` plus a lazy reader. Cap the dict (E14's budget cache).

**Issue 3 (minor).** `with as_of_context(key), pit_scope(panels):` appears in both `score_at` and `panel_at`; the nesting is harmless but the second `pit_scope` token and `as_of_context` do redundant ContextVar sets per date. Keep it only in `panel_at`.

---

### E13. pit_cache.py: monkeypatching

**Issue (medium).** The module rebinds `estimators.close_matrix`, `estimators.volume_matrix`, `estimators._idiosyncratic_vol`, `fundamentals.statement_snapshots` at import time. Consequences: behavior depends on import order; any module that did `from .estimators import _idiosyncratic_vol` earlier keeps the unpatched one; a test that imports estimators alone behaves differently from production; and `_skip_close_matrix` returns an *empty frame* rather than skipping, which silently produces `["ticker"]`-only output when a caller forgets `as_of_date` (see E2).

**Solution.**
- After E2, delete `_skip_close_matrix`, `_skip_volume_matrix`, `_close_matrix`, `_volume_matrix` and their two rebinds.
- `_idiosyncratic_vol`: make `batched_idiosyncratic_vol` the *only* implementation, in estimators.py, used in both the memo and non-memo paths (E20). Then the dispatcher and the rebind vanish.
- `statement_snapshots`: add the memo lookup inside fundamentals.py (three lines, using the shared ContextVar from performance.py). Then pit_cache.py contains only `pit_scope`, which is the structure its docstring already promises.

---

### E14. performance.py: caches without a byte budget

**Issue (medium).** Three `lru_cache(maxsize=6)` on matrices (up to 18 x 31 MB = 560 MB, keyed by 3831-string tuples) plus `maxsize=512` on per-ticker fundamentals slices of all 364 columns (about 90 MB at 175 KB each, and evicting constantly in `_fundamental_growth_metrics`, which sweeps 3831 symbols through a 512-slot cache, a 0% hit rate by construction).

**Solution.** Bound by bytes, not entries.

```python
class ByteLRU:
    def __init__(self, budget): self.budget, self.size, self.items = budget, 0, {}
    def get(self, key, make):
        if key in self.items:
            self.items[key] = self.items.pop(key); return self.items[key][0]
        value = make(); nbytes = int(value.memory_usage(deep=False).sum())
        self.items[key] = (value, nbytes); self.size += nbytes
        while self.size > self.budget and len(self.items) > 1:
            _, (_, b) = next(iter(self.items.items())); self.items.pop(next(iter(self.items))); self.size -= b
        return value
MATRICES = ByteLRU(256 * 2**20)
```
Remove the fundamentals-history cache entirely once E15 vectorizes growth. With pandas 3 copy-on-write the `.copy(deep=False)` at call sites is redundant.

---

### E15. fundamentals.py: `_fundamental_growth_metrics`

**Issue (medium).** (a) Python loop over all symbols, each calling `fundamental_history` (slice of 364 columns), then `_pick`, `pd.to_numeric`, and `to_datetime` per symbol. (b) Correctness: growth is taken from the last two annual reports with no check that the last report is recent, so a company whose last annual report is three years old still reports `revenue_growth_yoy`. `eligible_reports` enforces a 640-day upper bound for the main snapshot; growth does not.

**Solution.** One groupby over the already-pruned frame, with the same eligibility window.

```python
def _fundamental_growth_metrics(symbols, as_of_date=None):
    cutoff = pd.Timestamp(as_of_date) if as_of_date else AS_OF.get()
    src = load_fundamentals()
    src = src[src.ticker.isin(symbols) & src.periodType.eq("annual")]
    if cutoff is not None:
        report = pd.to_datetime(src.reportDate)
        src = src[(report + pd.Timedelta(days=90) <= cutoff) & (report + pd.Timedelta(days=640) >= cutoff)]
    src = src.sort_values(["ticker", "reportDate"])
    g = src.groupby("ticker", sort=False)
    gap = g.reportDate.diff().dt.days
    rev = pd.to_numeric(_pick(src, ["Total Revenue", "totalRevenue", "revenue"]), errors="coerce")
    eps = pd.to_numeric(_pick(src, ["Diluted EPS", "Basic EPS"]), errors="coerce")
    last = src.groupby("ticker").tail(1).index
    prev_rev, prev_eps = rev.groupby(src.ticker).shift(1), eps.groupby(src.ticker).shift(1)
    ok = gap.loc[last].between(320, 410) & (prev_rev.loc[last] > 0)
    out = pd.DataFrame(index=pd.Index(last.map(src.ticker), name="ticker"))
    out["revenue_growth_yoy"] = (rev.loc[last] / prev_rev.loc[last] - 1).where(ok.to_numpy()).to_numpy()
    ...
```
Complete `eps_growth_yoy` and the 3-year CAGR (shift(3) with `gap` window checks) the same way. This is a sketch, so keep the per-symbol implementation as the oracle in a test and compare outputs on the full universe. Hash impact: stale rows now get NaN.

---

### E16. validation.py: rebalance-period statistics

**Issue (medium, mislabeled statistics).** `position_returns = strategy.groupby(np.arange(len(strategy)) // max(1, rebalance_days))` groups by fixed blocks from the first curve row. Actual rebalances execute at `start + 1 + k*rebalance_days` (and with a weekday filter they are not evenly spaced). Block boundaries therefore drift from rebalance boundaries, and `rebalance_period_hit_rate`, `rebalance_period_average_gain` and `rebalance_period_average_loss` describe the wrong windows.

```diff
-    position_returns = strategy.groupby(np.arange(len(strategy)) // max(1, rebalance_days)).apply(lambda r: (1 + r).prod() - 1)
+    period = frame["rebalance"].cumsum()
+    position_returns = strategy[period.gt(0)].groupby(period[period.gt(0)]).apply(lambda r: (1 + r).prod() - 1)
```
The `rebalance` flag is already in `frame` (backtest.py writes it). The first period is the one beginning at the first execution day; any rows before it (weekday variants) are in cash and excluded.

---

### E17. validation.py: risk-free lag

**Issue (medium).** `rf_annual` is NaN unless `rf_daily` is non-null on every strategy date. Ken French daily files publish with a lag of weeks to a couple of months, so any backtest that ends at the latest market date gets `rf_annual = NaN`, `sharpe = NaN`, `sortino = None`. Silent NaN is correct behavior under your no-fill policy, but it is almost certainly not what the user wants to see on the headline backtest.

**Solutions, pick one and state it in `stats`:**
1. Report Sharpe and Sortino over the overlap window with `risk_free_coverage` and `risk_free_end_date` fields; set the full-window values only when coverage is 100%.
2. Add a daily T-bill series (FRED DTB3, converted to a daily rate) as an *observed* secondary source with its own provenance flag; use Ken French where present, the T-bill series for the tail, and report `rf_source: "ff+dtb3"`.
3. Truncate the backtest end to the last FF date for the risk-adjusted metrics only.

Option 1 costs six lines and preserves the no-substitution policy.

Minor: `rolling[...].apply(np.prod, raw=True)` could use `np.exp(np.log1p(strategy).rolling(w).sum()) - 1`, but that moves values at 1e-16, which affects hashes unless you round. Not worth it for three 1000-element calls.

---

### E18. backtest.py

1. **Missing held price raises and kills the whole run** (`Missing observed price for held position`). That is the correct default under a no-stale-price policy, but a single trading halt in one of 50 names invalidates the run. Add `missing_price_policy: "raise" | "liquidate_at_last_observed"`; default stays `"raise"`, and the alternative is recorded in stats as a flagged policy, with the liquidation trade costed. This is a research decision; the code change is small.
2. `counts = prices.notna().cumsum()` creates a full int64 frame; use `prices.notna().to_numpy().cumsum(axis=0, dtype=np.int32)`.
3. The per-day loop uses `prices.iloc[i]` on a wide frame and boolean masks on Series of width N. For full-universe long-short it is the second hotspot after scoring. Convert `prices` to a float64 ndarray and index by integer positions; keep tickers in a parallel array. Expected 5x to 20x on the loop, no change in results if arithmetic order is preserved.
4. `attribute()` is called per held ticker per day and does dict lookups; accumulate in ndarrays (`pnl[j] += ...`) and build the dict once at the end.
5. Fixed-point cost solve is correct and converges (contraction since k < 0.1), but the 50-iteration loop runs per rebalance. A closed form exists when the sign pattern of `(1-c)T - D` is constant, so you could try Newton once and fall back. Low priority.
6. `cscv_pbo`: the logit treats `rank = 1/(N+1)` to `N/(N+1)`, so it never hits 0 or 1, which is right. `np.array_split` gives unequal block sizes when `len % partitions != 0`; Bailey et al. use equal blocks. Trim the head to a multiple of `partitions` and say so in the output.

---

### E19. One normalizer

Four implementations of ticker normalization exist: `data_loader.normalize_symbol`, `performance.symbol_key`, an inline copy in `cached_fundamental_history` and `_cached_fundamental_history_versioned`, and the Polars regex `[.\-]`. They agree today. They will not forever. Put one function and one Polars expression in a leaf module (`core/symbols.py`) and import both everywhere. Add a property test that the Python and Polars versions agree on a fuzz set (spaces, lowercase, `.`, `-`, `_`, Unicode dashes).

---

### E20. Drop `statsmodels` and `scipy.stats` from the hot path

`_idiosyncratic_vol` fits one `sm.OLS` per ticker (3,831 fits, each with Python-level object construction), and `linregress` is imported for OBV. `batched_idiosyncratic_vol` in pit_cache.py is already the right algorithm and is only used under `pit_scope`.

```python
def idiosyncratic_vol(returns, factors):
    required = ["mkt_rf", "smb", "hml", "rf"]
    out = pd.Series(np.nan, index=returns.columns, dtype=float)
    if len(returns) != 63 or not set(required).issubset(factors.columns):
        return out
    aligned = factors.set_index("date")[required].reindex(returns.index).to_numpy(dtype=float)
    complete = returns.notna().all().to_numpy() & ~np.isinf(returns.to_numpy(dtype=float)).any(axis=0)
    if np.isnan(aligned).any() or not complete.any():
        return out
    y = returns.to_numpy(dtype=float)[:, complete] - aligned[:, 3:]
    x = np.column_stack([np.ones(63), aligned[:, :3]])
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ coef
    out.iloc[np.flatnonzero(complete)] = np.sqrt((resid ** 2).mean(axis=0) * TRADING_DAYS)
    return out
```
This also drops the `len != 63` fallback to statsmodels (for any other window length it is just NaN today as well, since the original returns NaN below 63 rows but accepts >63 rows; keep the `>=63` semantics if callers pass longer windows). Importing `statsmodels.api` and `scipy.stats` costs memory at first use; measure with `python -X importtime` and RSS before and after, and expect tens of MB. `np.linalg.pinv` vs `lstsq` agree to about 1e-12.

---

### E21. Names that lie

`atr_14`, `adx_14`, `rsi_14` keep those names when `atr_period`, `adx_period`, `rsi_period` are overridden. A consumer reading `rsi_14` under `rsi_period=7` is silently wrong. Either suffix with the real period (`rsi_{rsi_period}`) or add `rsi_period` as a column. Similarly `volume_20d`, `dollar_volume_20d` are fixed-20 by design (fine). `sma20_50_cross_days` uses `cross_lookback` while `golden_cross_within_20d` hardcodes 20: name or parametrize consistently. `stochastic_k` uses `stochastic_period` but the local variables are named `low14` and `high14`.

---

## 4. The precompute design (what to build, what not to)

### 4.1 Partition features by dependency

| Class | Examples | Precompute? |
|---|---|---|
| Causal, per-ticker, recursive | EMA 20/50/100/200, MACD, signal, histogram, ATR, ADX, DMI, RSI | Yes, full-history, long format |
| Causal, per-ticker, windowed | SMA, Bollinger, stochastic, Williams %R, returns, vol, Yang-Zhang, OBV slope, 52w high/low, run lengths, cross ages | Yes, or cheap from the last 253 rows |
| Per-ticker plus a fixed benchmark | beta_252, relative_return_3m_spy, ivol_ff3_63d | Yes (SPY and FF are not "the universe") |
| Cross-sectional | bollinger_width_percentile, technical_percentile, amihud_percentile, short_term_reversal_flag, everything `rank_pct` in panel.py | **No.** Compute at query time from the latest precomputed row |

### 4.2 Store layout

```
market_cache/indicators_{market_version}_{code_version}.parquet
  Ticker (categorical or dictionary), Date (Date32), ema_20, ema_50, ..., macd, macd_signal,
  atr, plus_di, minus_di, adx, rsi, sma_*, bb_*, ...   (float64)
sorted by (Ticker, Date); row_group_size 131072; zstd(3); statistics on
```
Size: 3831 tickers x about 7000 sessions x 60 float64 columns is about 12.9 GB uncompressed if you keep 28 years. Restrict to the window you serve (for example 6 years: 1500 sessions, about 2.8 GB uncompressed, 0.5 to 1 GB on disk with zstd). Query pattern `Ticker in S and Date == t` reads one row per ticker through row-group pruning.

### 4.3 Seeding policy (decide once, write it down)

Choose per-ticker, on the ticker's own history, causal only:
- **EMA**: first observation seeded (pandas `adjust=False`) or SMA-seeded (TA-Lib convention). Both are universe independent. SMA-seeding removes dependence on the very first print and is the conventional choice.
- **Wilder**: SMA-seeded over n valid observations (matches E9 kernel).
- **Gaps**: your grid is the SPY calendar, so a Tadawul ticker has NaNs on SPY sessions it did not trade. Today EMA across NaNs decays per *grid* step (pandas `ignore_na=False`). Keep that behavior if you want a smooth transition; Polars `ewm_mean(ignore_nulls=False)` is the equivalent. Build the grid via a left join of `(Ticker x calendar)` onto the clean store, not via per-ticker native calendars.

### 4.4 Why this meets your constraints

- **Point-in-time.** Every column is a causal recursion or a trailing window, so row t depends only on rows <= t. The as-of query is `Date == t`. Test with append-invariance (section 6, test 2).
- **Same inputs, same hash, 50 vs full.** Row (ticker, t) is a function of that ticker's history only. Subset-invariance is then a theorem, and test 1 enforces it.
- **Incremental updates.** Persist the last state (`ema_*`, Wilder states) per ticker. A daily append becomes O(new rows), not O(history).
- **Backtests become lookups.** Formation-date features come from the store; only the cross-sectional percentiles and fundamentals are recomputed per date, and those are vectorized over the latest row.
- **Memory.** The latest-row panel for the full universe is 3831 x about 150 columns x 8 B = 4.6 MB. With E5 the resident floor is the pruned fundamentals plus imports.

### 4.5 Polars sketch for the non-Wilder part

```python
grid = calendar_dates_df.join(tickers_df, how="cross")                   # Ticker x Date
lf = (grid.lazy().join(clean_lf, on=["Ticker", "Date"], how="left")
        .sort(["Ticker", "Date"])
        .with_columns(pl.col("Close").fill_nan(None))
        .with_columns(
            *[pl.col("Close").ewm_mean(span=w, adjust=False, min_samples=w, ignore_nulls=False).over("Ticker").alias(f"ema_{w}")
              for w in (20, 50, 100, 200)],
            *[pl.col("Close").rolling_mean(w).over("Ticker").alias(f"sma_{w}") for w in (20, 50, 100, 200)],
        ))
```
`min_samples` equals the pandas `min_periods`. Verify that pandas `min_periods=min(window, len(prices))` (used today) reduces to `window` for the lengths you serve; for lengths shorter than `window` the current code relaxes the minimum, which the store should not replicate (a 5-row history has no meaningful `ema_200`). That is a deliberate semantic change; flag it.

### 4.6 One-time hash break and how to bound it

The EMA fix and the seeding policy change values. Do it once, in one commit, and prove the change is small and explained:
- Assert `max |new - old| / |old| < 1e-3` for `ema_200` when the old window was universe clean (50-name run on both sides) and review every exceedance.
- Hash rounded values (for example 10 significant digits via `np.format_float_positional`), not raw bytes, because Polars/Numba/pandas can differ in the last ulp for the same recursion.

---

## 5. Profiling protocol (turn the ranking into measurements)

1. **Stage RSS.** Wrap the stages in `metric_panel`: market load, technical features, fundamentals, merge, ranks. Record `psutil.Process().memory_info().rss` and `ru_maxrss` before/after each.
2. **Allocation sites.** `memray run -o run.bin screen_full.py` then `memray flamegraph run.bin` (memray supports macOS). Use `--native` to see Arrow/Polars allocations that `tracemalloc` cannot see.
3. **Time.** `py-spy record --native -o prof.svg -- python backtest12.py` (needs `sudo` on macOS), or `cProfile` with `snakeviz`. For the backtest, expect `collect`, `_subset_frame` and `_standardize_frame` at the top.
4. **Frame census.** Insert a one-off hook at the end of `latest_technical_features`: `sum(x.memory_usage(deep=True).sum() for x in gc.get_objects() if isinstance(x, pd.DataFrame))`. It tells you directly whether the "85 frame-equivalents" estimate holds.
5. **Thermals.** A fanless M4 Air throttles under sustained all-core load. Keep `POLARS_MAX_THREADS=2` for scans, but if you add Numba or Rayon, cap at the performance-core count (4) and run benchmarks three times back to back; report the median of the second and third.

---

## 6. Test suite to freeze the contracts

```python
# 1. Subset invariance (the bug you found, as a permanent test)
@pytest.mark.parametrize("seed", range(5))
def test_subset_invariance(seed, universe, loaded):
    rng = np.random.default_rng(seed)
    sub = list(rng.choice(universe, size=50, replace=False))
    a = latest_technical_features(sub, 756).set_index("ticker")
    b = latest_technical_features(universe, 756).set_index("ticker").loc[a.index]
    time_series_cols = [c for c in a.columns if c not in CROSS_SECTIONAL_COLUMNS]
    pd.testing.assert_frame_equal(a[time_series_cols], b[time_series_cols], check_exact=True)

# 2. Append invariance (point-in-time)
def test_no_lookahead(universe, t):
    with as_of_context(t):
        a = latest_technical_features(universe[:20], 756, {"as_of_date": str(t.date())})
    with as_of_context(t), truncated_market_after(t + pd.Timedelta(days=30)):    # fixture removes later rows from the source
        b = latest_technical_features(universe[:20], 756, {"as_of_date": str(t.date())})
    pd.testing.assert_frame_equal(a, b, check_exact=True)

# 3. Permutation invariance
def test_order_invariance(universe):
    a = latest_technical_features(universe[:30], 756).set_index("ticker")
    b = latest_technical_features(universe[:30][::-1], 756).set_index("ticker")
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index(), check_exact=True)

# 4. market_window equals the legacy pivot path on a clean subset, element for element
def test_market_window_matches_legacy(...): ...

# 5. Kernel parity against the old implementations on random data with injected NaN gaps
@given(st.integers(30, 300), st.floats(0.0, 0.2))
def test_cross_age_and_wilder_parity(n, nan_rate): ...     # np.testing.assert_allclose(rtol=1e-9, equal_nan=True)

# 6. Hash stability across 50 and full, on rounded values
```
Test 1 is exactly your stated constraint. It should fail on the current code, which makes it a good first commit.

---

## 7. Rust scope, restated

Do not start PyO3 until after E1 to E9 and the precompute. After those, the candidate hotspots are:
1. The scoring loop in validation.py if `component_scores` and `apply_filters` dominate per-date cost.
2. `simulate()` if the loop remains pandas (see E18.3; a NumPy port usually removes the need).
3. `cscv_pbo` only if you raise partitions above 12 (C(12,6) = 924 is trivial).

If you do go to Rust: use `pyo3-polars` expression plugins for per-column recursions (zero-copy with Arrow, no GIL, parallel over groups), not NumPy-array PyO3 kernels, because the data already lives in Polars. Keep the Numba or pure-NumPy implementation as the test oracle.

---

## 8. Things I could not verify (and what would change)

| Unknown | Why it matters |
|---|---|
| `stats._wilder_smooth` seeding and NaN semantics | E9, precompute spec |
| `stats._pick` and `rank_pct` behavior with NaN and ties | E5 column list, E10 |
| `currency.usd_price_matrix`, `instrument_specs` | E8 slicing (does it need the full index for FX alignment or only the dates it is given?) |
| composite.py, academic.py column access | E5 (extra raw fundamentals columns), E12 (`history_cache` key scheme) |
| Whether Date in the market parquet is `Date`, `Datetime[us]` or `Datetime[ns]` | `market_window` casts defensively; confirm with `pl.scan_parquet(...).schema` |
| Row count and column width of `master_fundamentals.parquet` | My "probably the biggest edit" claim for E5 rests on this |
| Real distribution of calendars in the universe | Whether union inflation alone explains the 2.2% (E1 experiment) |

---

## 9. Suggested order of work

1. Write tests 1 to 3 (section 6). Commit the failing subset-invariance test.
2. Run the section 1 measurements and the E1 experiment. Update the ranking with numbers.
3. E5 (fundamentals pruning), E3 (prefetch and slice), E1/E2 (calendar-first window). Expect the 50-name peak to drop below 0.5 GB, the 12-name backtest to fall by an order of magnitude, and test 1 to pass.
4. E7, E8, E9 (vectorize and tail-slice). Re-measure the full-run peak.
5. Build the indicator store (section 4), starting with the non-Wilder features, then Wilder via the kernel.
6. E10 to E21 correctness and hygiene edits, each with its own hash-impact note in the commit message.
7. Only then decide on Rust.
