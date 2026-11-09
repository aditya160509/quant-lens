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

## Code to clean up

- [ ] `core/pit_cache.py` rebinds names in `estimators` and `fundamentals` at import; move into those modules
- [ ] Batched FF3 regression matches the old one to floating-point tolerance, not bit for bit
- [ ] Two formula engines: `core/formula.py` and `signal_lang`
- [ ] PBO copies left in Screener `core/backtest.py` and Portfolio `core/stats.py`; Portfolio deflated Sharpe also separate
- [ ] `noqa` added over old lint errors in `research_v2/reports.py` and the six lab loaders
- [ ] Five style-only uncommitted edits in `screener_v2/core`: `backtest.py`, `composite.py`, `gics.py`, `scheduler.py`, `valuation.py`
- [ ] `screener/base.ts` was overwritten and recreated by another worker; confirm it matches its users
- [ ] Old S4, S2 and S5 code still there

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
