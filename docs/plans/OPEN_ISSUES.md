# Open issues

Known gaps to check. Tick when fixed and verified. Screener items still live in [SCREENER_CHECKLIST.md](SCREENER_CHECKLIST.md).

## Memory and speed

Measured with `ru_maxrss` on a full Screen run (3,831 names).

| Commit | Peak | Time | Results |
|---|---|---|---|
| Before `1281f1e` | 6.52 GB | 43.8 s | baseline |
| `1281f1e` | 4.13 GB | 34.2 s | identical hash |
| `8379929` (Polars) | 4.17 GB | 31.3 s | identical hash |

- [ ] Full Screen run under 2 GB
- [ ] Run reads only requested stocks, columns and dates; a 50-name screen costs a few hundred MB
- [ ] Indicators off wide pandas frames in `latest_technical_features`
- [ ] Find what holds RSS at about 2.6 GB when live data is under 1 GB (allocator retention suspected, unproven)
- [ ] Decide on precomputed daily indicators in parquet, with point-in-time window rules
- [ ] Backtest speed: 172 s to 135 s on 20 names, before `pit_cache`; over 6 minutes on 100. Re-measure
- [ ] Bottlenecks named, unmeasured: `instrument_specs` scan per date, `_fundamental_growth_metrics` per symbol
- [ ] Hot-loop pass with numba or Polars; numba is only in `screener_v2/core/stats.py`
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
- [ ] Old S5 PBO duplicate still in `core/backtest.py`; S4 and S2 removed

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
