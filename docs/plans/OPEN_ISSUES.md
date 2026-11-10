# Open issues

Known gaps to check. Tick when fixed and verified. Screener items still live in [SCREENER_CHECKLIST.md](SCREENER_CHECKLIST.md).

## Memory and speed

Measured with `ru_maxrss` on a full Screen run (3,831 names).

| Commit | Peak | Time | Results |
|---|---|---|---|
| Before `1281f1e` | 6.52 GB | 43.8 s | baseline |
| `1281f1e` | 4.13 GB | 34.2 s | identical hash |
| `8379929` (Polars) | 4.17 GB | 31.3 s | identical hash |

Memory plan run (`SCREENER_V2_MAXIMUM_MEMORY_REDUCTION_V2.md`). Each case in a fresh child, `POLARS_MAX_THREADS=2`, peak by `ru_maxrss`, hash is sha256 of the panel CSV or response JSON. Cases: full = `metric_panel` on 3,831 names; 50 = first 50; PIT 50 = as of 2025-06-02; Composite = feature 03 on 50 US names (IC-IR); Backtest = feature 05 on 12 US names.

| Step | Full | 50 | PIT 50 | Composite 50 | Backtest 12 |
|---|---|---|---|---|---|
| Baseline `567f204` | 2,331 MB, 14.7 s, `9194d4c2` | 694 MB, 2.5 s, `62364695` | 658 MB, 1.7 s, `cd927b91` | 860 MB, 43.4 s, `3b390b85` | 790 MB, 55.5 s, `da4f7ef0` |
| 2. Panel cache bounded by bytes (256 MB) | same code path | same | same | same | same hash; one run never fills the cache |
| 3. D05 batched FF3 OLS, `pit_cache.py` removed | 2,259–2,600 MB (3 runs; baseline 2,331–2,382), 12.3–12.9 s, `eaaff879` (ivol only, max rel diff 4.6e-16 on 1,404 names; all other columns identical) | 688 MB, 1.6 s, same | 622 MB, 1.4 s, same | 819 MB, 41.6 s, same | 750 MB, 56.0 s, same |
| 4. D06 growth in one grouped pass, no per-ticker history cache (columns were already projected in `c6d3a97`) | 2,280–2,583 MB, 10.2–10.4 s, `eaaff879` same | 671 MB, 1.5 s, same | 591 MB, 1.4 s, same | 832 MB, 37.0 s, same | 744 MB, 52.6 s, same |
| 5. D03 dated raw-feature snapshots (`core/snapshots.py`, `ALGORITHM_VERSION=bounded-window-v1`); cold = first run writes, warm = reads one date | cold 2,111 MB, 15.4 s; **warm 492–502 MB, 0.8–0.9 s**, `eaaff879` same | cold 838 MB, 1.8 s; **warm 409 MB, 0.6 s**; read from full-run rows 423 MB, 0.6 s; all same hash | warm 419 MB, 0.6 s, same | cold 927 MB, 58.3 s; **warm 730 MB, 8.8 s**, same | cold 766 MB, 56.9 s; **warm 650 MB, 19.5 s**, same |
| 6. D07: backtests score from snapshots and keep one score vector per date (run-local panel copies dropped); NumPy daily simulator (golden parity test); NumPy average rank; Feature 05 reuses the base run when holding = rebalance period | warm 489 MB, 0.8 s, same | warm 414 MB, 0.6 s, same | warm 414 MB, 0.6 s, same | warm 711 MB, 7.7 s, same | **warm 687 MB, 13.4 s**, same (cold ~57 s: 405 dates still built once) |

7. Compiled kernels not built: after steps 1–6 no warm path runs indicator code (profile: snapshot reads, ranks and the simulator). Indicators only run on a cold store (full screen ~11 s, 2.1 GB peak; 12-name backtest ~57 s). Revisit Numba/Cython for the cold backfill only if that matters. Also not done: shared USD price/FX context across sensitivity runs (about 4% of the warm backtest profile), canonical ingest (D01, M02), content-hash versions (keys use file mtimes).

- [x] Full Screen run under 2 GB (warm, from snapshots: 0.5 GB)
- [ ] Run reads only requested stocks, columns and dates; a 50-name screen costs a few hundred MB
- [ ] Indicators off wide pandas frames in `latest_technical_features`
- [ ] Find what holds RSS at about 2.6 GB when live data is under 1 GB (allocator retention suspected, unproven)
- [x] Decide on precomputed daily indicators in parquet, with point-in-time window rules: bounded-window policy kept (`ALGORITHM_VERSION`), raw per-ticker rows per date, ranks per request
- [x] Backtest speed: 12 US names 55.5 s to 13.4 s warm (snapshots), about 57 s on a cold store. 100 names not re-measured
- [ ] Bottlenecks named, unmeasured: `instrument_specs` scan per date, `_fundamental_growth_metrics` per symbol
- [x] Hot-loop pass: daily simulator and ranks moved to NumPy; numba not needed once warm paths stopped computing indicators
- [ ] DuckDB against Polars, not measured

## Screener engine plan

Python keeps the API, jobs and orchestration. Heavy work moves to precomputed data, then one Rust module called through PyO3. Prove it on the Screener, then replicate for the other labs. No lab is rewritten whole.

Rule for every stage: the same inputs give the same output hash on a clean worktree, on 50 names and the full universe, before and after. If a hash differs, stop and fix it. Latest measured peak: 0.95 GB on 50 names, 2.97 GB on the full universe (`194ca5a`).

1. [x] Cheap wins measured. Kept `POLARS_MAX_THREADS=2` and the cached integrity pass. Rejected as no gain: Polars streaming, DuckDB scans, jemalloc (mimalloc has no dylib here)
1a. [x] Fixed: price windows no longer come from the requested set's union calendar (weekend and foreign dates cut about a year of SPY sessions from the full-universe window). Windows are now the last N calendar sessions, or the last N observations per ticker when no calendar applies. Same names alone against the full universe: 93 of 100 technical columns identical; 4 are cross-sectional ranks (`bollinger_width_percentile`, `amihud_percentile`, `technical_percentile`, `short_term_reversal_flag`), 3 differ only as None or NaN (`golden_cross_age_days`, `beta_252_unavailable_reason`, `price_observation_date`). Hash baseline for `latest_technical_features(lookback 756)`: 50 names `e8c19c0912c2003d`, full universe `da7ee2e5054b57f3` (3,831 names)
2. [ ] Precompute daily indicators to parquet, with point-in-time window seeding; a screen reads finished numbers. Target: full run under 1 GB
3. [ ] Measure what is still slow or heavy. Build stage 4 only for what stage 3 proves, which is expected to be backtests and custom formulas
4. [ ] One Rust crate with PyO3 and maturin, using Polars or Arrow, replacing exactly these Python files:

| File in `screener_v2/core/` | Lines | What moves |
|---|---|---|
| `estimators.py` | 313 | All indicators: warmup, Wilder seeding and null handling must match |
| `panel.py` | 84 | Panel assembly and ranks |
| `stats.py` | 100 | Rank, z-score, winsorise, smoothing |
| `backtest.py` | 174 | Simulation loop and CSCV |
| `validation.py` | part of 201 | Point-in-time scoring loop only |

About 900 Python lines, likely 2,000 to 3,000 lines of Rust. `pit_cache.py` (78) is deleted once this lands.

5. [ ] Only if profiling still demands it: `data_loader.py` (494), `performance.py` (200) and the numeric parts of `fundamentals.py` (278)
6. [ ] Not rewritten: API routes, features, `screener.py`, `formula.py`, `composite.py`, `valuation.py`, currency, jobs and persistence
7. [ ] Once the Screener passes stages 1 to 4, replicate the same pattern lab by lab, starting from each lab's own profile

Lines per lab for reference: Screener 5,834; Factors 5,199; ML 5,176; PCA 5,736; Portfolio 6,891; Research 8,175; Volatility 10,100.

## Ready for many users

Do this before most of the Rust list; the job store is the first thing that will break. Reasoned from how the code is built, not load-tested. Rewriting in Rust would not fix any of these.

| Now | Why it breaks | Fix |
|---|---|---|
| [ ] Jobs in a JSON file, rewritten on every update (`services/studio/jobs.py`) | Slows and locks as jobs grow; cannot span servers | Postgres and a real queue |
| [ ] Jobs run in a 2-thread pool inside the API process | A few backtests make everyone wait; a restart kills running jobs | Separate worker processes |
| [ ] Each process loads its own data | Memory multiplies with workers | Precomputed store, shared data service |
| [ ] Results and caches on local disk | Does not work on more than one server | Object storage and Redis |
| [ ] Every screen recalculates indicators | Cost grows with each user | Precompute daily; users read the same numbers |
| [ ] Limits, auth and share links unreviewed | Abuse; one user can hog the machine | Per-user quotas and a security review |

Memory per job is the server bill: 3 GB to under 1 GB is about three times the jobs per server.

Order: finish the Python fixes and precompute; Postgres, queue and workers before launch; load test; then Rust on what the test shows. Rust earns its place where work cannot be shared: user formulas, backtests, scheduled alerts across saved screens, one shared in-memory data service.

Rust decision for the Screener: paused. Both reviews say profile and fix Python first. If the backtest reaches about 10 s and memory is near target, Rust waits for scale. Otherwise port only what is still heavy, as Polars plugins, likely a few hundred lines.

Reviews: [hard review](../reviews/SCREENER_V2_HARD_REVIEW.md), [second review](../reviews/SCREENER_V2_REVIEW_2.md).

Findings that change results, to confirm and approve (second review numbers): SPY inside percentile ranks (E10), rank and sort disagree on ties (E11), stale growth metrics (E15), rebalance stats on fixed blocks (E16), risk-free rate missing near the latest date (E17).

## Rust at scale

For when the product hosts many users. Ranked by expected gain for the work; estimates, each to be proven by a profile under real traffic. Same hash rule as the engine plan. Python stays for statistics and models.

| Rank | Area | Why it pays at scale | Where now |
|---|---|---|---|
| 1 | Indicator and panel engine | Every screen, backtest and alert uses it | `screener_v2/core/estimators.py`, `panel.py`, `stats.py` |
| 2 | Backtest and simulation kernel | Longest CPU jobs; each lab has its own cost loop | `screener_v2/core/backtest.py`, and the cost loops in the merge map |
| 3 | Shared market data service | One in-memory Arrow store instead of a copy per process; seven lab loaders become one | `*/core/data_loader.py`, `services/shared/` |
| 4 | Formula engine | User-written, so it cannot be precomputed; needs a sandboxed, fast evaluator | `screener_v2/core/formula.py`, `signal_lang` |
| 5 | Screen and alert evaluator | Scheduled re-runs for every saved screen and user | `screener_v2/core/screener.py`, `alerts.py`, `scheduler.py` |
| 6 | Validation statistics | PBO, bootstrap and Monte Carlo are parallel and repeated | `services/shared/stats.py`, `ml_v2/core/validate_engine.py` |
| 7 | Covariance and risk kernels | Matrix work repeated across Portfolio, PCA, Factors and Volatility | merge map items |
| 8 | API edge: job queue, cache, rate limits, streaming | Cuts idle memory per user; a Rust gateway in front of Python workers | `backend/app/api/` |
| 9 | Live price and websocket fan-out | Many connections, low memory per connection | `backend/app/api` websocket routes |

Keep in Python: model fitting and libraries with no equal Rust version (`arch`, `statsmodels`, `hmmlearn`, scikit-learn), reports, feature definitions and product logic.

Order: finish the engine plan on the Screener first, then 3, then 4 and 5. Reconsider 8 and 9 when real traffic exists.

## Code to clean up

- [ ] `core/pit_cache.py` rebinds names in `estimators` and `fundamentals` at import; move into those modules
- [ ] Batched FF3 regression matches the old one to floating-point tolerance, not bit for bit
- [ ] Two formula engines: `core/formula.py` and `signal_lang`
- [ ] PBO copies left in Screener `core/backtest.py` and Portfolio `core/stats.py`; Portfolio deflated Sharpe also separate
- [ ] `noqa` added over old lint errors in `research_v2/reports.py` and the six lab loaders
- [ ] Five style-only uncommitted edits in `screener_v2/core`: `backtest.py`, `composite.py`, `gics.py`, `scheduler.py`, `valuation.py`
- [ ] `screener/base.ts` was overwritten and recreated by another worker; confirm it matches its users
- [x] Old S5 PBO duplicate removed from `core/backtest.py`; feature 05 uses `services/shared/stats.cscv_pbo` (same pbo on test matrices); S4 and S2 removed

## Not proven

- [ ] 55 Screener items marked `(untested)`: need a batch test and a look on the page
- [ ] Rank, Test and Monitor never seen with results on the page
- [ ] Excel download, PDF download, column resize, universe picker, "Screens" actions not tried on the page
- [ ] Batch 8 and 11 code was written before the spec-reading instruction; check against the product review

## Security, before going online

- [ ] Share links are public with no login
- [ ] API keys and limits are new and unreviewed

## Data

- [ ] Company names about 90% or less: SEC, NSE and a partial Yahoo fetch; the rest show Unknown
- [ ] US names have no NYSE or Nasdaq exchange label
- [ ] Market cap assumes statement currency equals quote currency, US and India only; ADRs such as ASML are approximate
- [ ] Indian composite score was blank when last checked
- [ ] Piotroski has at most 8 of 9 checks: the debt check has no data
- [ ] Altman Z covers 32% of names
- [ ] RSI and beta cover about 1,400 of 3,831 names because of the US session grid
- [ ] Enterprise value counts unreported preferred and minority claims as zero
- [ ] Backtests test USD-quoted names only on mixed universes; the dropped count is in stats, not shown on the page

## Design

- [ ] UI issue 7: header takes about 40% of the screen before the table
- [ ] UI issue 15: universe selector
- [ ] UI issues 16 and 20 partly fixed; ML pages not rechecked
- [ ] Search dialog logs a Radix DialogTitle console error
- [ ] Phone: tab strip scrolls with no visible cue

## Reviews

- [ ] ML, Research and Volatility reviews to redo
- [ ] Factors review is a first pass: mostly headers and docstrings
- [ ] PCA, Portfolio and Studio reviews not checked against the code by a second reader

- [x] Market cap blank for 375 of the top 500: the latest close was read from the last shared row, so ragged final dates blanked names; now each name's own last close and date. Coverage 125 to 499 of 500.
- [x] sector_composite_breakdown: count now counts scored names, with `unscored` beside it; a null average means every name in the sector lacks a factor.
- [ ] US exchange labels "Unknown": no local exchange source exists (company_names.parquet has ticker, name, source only). Needs the SEC company_tickers_exchange file, not fetched.
- [x] /jobs/{id} already returns only status and progress until completed.

## Screener backend work left (2026-11-10)

Beyond bug fixes. Order: 1, then approve or reject 2, then 3; 5 before launch.

1. Speed and memory (background agent working from `~/Downloads/SCREENER_V2_MAXIMUM_MEMORY_REDUCTION_V2.md`; notes in `MEMORY_HOTSPOTS_V2.txt`)
   - [x] Backtest under 15 s on 12 names (now 13.4 s warm, 57 s cold; was 61 s; 405 dated panels across 14 sensitivity runs)
   - [x] Full screen under 1 GB (now 489 MB, 0.8 s warm; cold 2.1 GB; was 2.97 GB, about 32 s; prices read three times)
   - [ ] Composite first run under 2 s on 50 names (now 7.7 s; was about 10 s; repeat 1 s)
   - [x] Byte-bounded panel caches (`validation._PANEL_CACHE` holds 400 by count; `explain._PREVIEW` 4)
   - [x] Batched idiosyncratic-vol OLS in the normal path; delete `pit_cache.py`
   - [x] Fundamental growth in one grouped pass, used columns only
   - [x] Dated raw-feature snapshot store; ranks stay universe-relative; seeding policy kept as bounded window
   - [ ] Sensitivity runs (offsets, weekdays, holding periods) as an optional second job
2. Result-changing fixes, need approval: E10 SPY in percentiles, E11 rank and sort ties, E15 stale growth, E16 rebalance stats on fixed blocks, E17 risk-free near the latest date
3. Backend for frontend plan items
   - [ ] Compare a field to another or to its sector median (P/E below sector median, price above SMA 200)
   - [ ] Historical conditions: 5-year average, change over N periods
   - [ ] Rank basis by market cap or coverage; country, exchange, sector, currency and cap-band presets
   - [ ] Natural-language filters into editable filters (build on `/nl-formula`)
   - [ ] Time machine and live funnel with passing names
   - [ ] Alert builder rules and channels
4. Data gaps: US exchange labels (no local source), company names about 90%, Piotroski debt check, Altman Z 32%, Indian composite blank, RSI and beta about 1,400 names, the 12 later-data items in SCREENER_CHECKLIST
5. Ready for many users: see the section above (Postgres and queue, workers, shared data, object storage, quotas, security review)

## Screener: precompute past data (planned, 2026-11-10)

Fill the dated snapshot store (`core/snapshots.py`) ahead of time instead of on first request, so screens and backtests on past dates never run cold (today: 11 s / 2.1 GB first full screen, 57 s first backtest).

- **Store:** raw per-stock features per date (indicators, returns, vol, fundamentals, FF3 residuals) as Parquet, one file per date, keyed by source version. Already the format `snapshots.py` writes.
- **Never stored:** percentiles, ranks, scores (depend on the chosen universe; milliseconds at query time). Non-default lookbacks or periods and custom formulas compute once, then cache.
- **Backfill tiers (estimates):** month-ends 3y = 36 dates, ~50 MB, ~7 min (covers monthly backtests); weekly 3y ~200 MB, ~30 min; daily 3y ~750 dates, ~1–2 GB, ~2–3 h overnight.
- **Order:** month-ends first, then daily for the latest year; add cleanup of files from old versions (store has no cleanup today, 61 MB after the memory-plan runs).
- **Paid source later:** no lock-in. Files are keyed by source version; on switch, wipe and rerun the same backfill. Daily feeds then only need a nightly one-date job. Treat files as derived data: never hand-edit.
