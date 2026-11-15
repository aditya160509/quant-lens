# Studio v3: the plan

Date: 2026-11-15. Status: proposed, not started. Owner decision taken: **rewrite from scratch**. Nothing in the current Studio code is kept as code; ideas that worked are carried over by name (section 4). The chart engine is also taken apart and rebuilt (section 6); it is the only part with progress worth mining.

Companion files: [FEATURES_AND_OUTPUTS.md](FEATURES_AND_OUTPUTS.md) (every page, input and output), [FRONTEND.md](FRONTEND.md) (screens and interaction), [REUSE.md](REUSE.md) (what to copy from Screener, Research, ML), [COMPETITORS.md](COMPETITORS.md) and [OPEN_SOURCE.md](OPEN_SOURCE.md) (research), [CHECKLIST.md](CHECKLIST.md) (progress).

---

## 1. What Studio is

**Build a trading strategy three ways, test it until it is either trusted or rejected, then watch it forward.** Every result says how far it can be trusted, with the test named, the data limits printed and the code visible.

One sentence per mode:

| Mode | The user's question | Leads with |
|---|---|---|
| Build | "How do I write this idea down?" | Blocks, formula or Python, same strategy object |
| Backtest | "What would it have done?" | Equity vs benchmark, after costs |
| Optimise | "Which settings, and is the best one a fluke?" | Plateau map, not the single best cell |
| Validate | "Is the edge real?" | One verdict, from walk-forward, robustness, Monte Carlo and overfitting tests |
| Regimes | "When does it work?" | Return by regime and by year |
| Combine | "What if I run several?" | Correlation and combined equity |
| Signals today | "What does it say now?" | Names that trigger today |
| Paper | "Is it still working since I stopped tuning?" | Forward equity since the freeze date |
| Certify | "Can I show someone?" | One-page report with a hash that reproduces |
| Chart | "Show me on the price." | Price, indicators, trade markers, replay |

## 2. Why rewrite (and not repair)

Read in `docs/reviews/product/STUDIO_V2_PRODUCT_REVIEW.md` (2026-11-09) and confirmed by size: 15k lines in `app/studio_v2`, 2.2k in `routers/studio.py`, 11k in `components/studio`, 25k in `chart_engine`, two data stacks, two routers.

- The validation tests the wrong thing: the sensitivity grid runs a built-in momentum rule, not the user's strategy.
- Controls look wired but are not: `universe` ignored on execute; `end_date` breaks for past dates.
- Fills on the signal bar's close, and the strategy sees future rows.
- Certification trusts test results sent by the browser.
- Paper is a journal with no prices.
- Chart reads live yfinance; Studio reads parquet. Same ticker, different prices.
- Most of `app/studio_v2` is reached only from a retired router.

Every one of these is a design fault, not a bug. Fixing them in place touches every file. The other labs (Screener, Research, ML) already share a workspace, a job API, an output registry and a design system that Studio does not use. Building Studio as the fourth lab on that base is less code than repairing the old one.

## 3. Principles (each one is a test, not a wish)

1. **One strategy object.** Blocks, formula and Python all compile to the same `Strategy` spec. A test asserts the three forms of the same rule give identical trades.
2. **No look-ahead by construction.** The engine hands the strategy data up to bar *t* only; orders fill at bar *t+1* open (default) or *t* close (explicit switch, labelled). A test plants a future-peeking strategy and expects a refusal.
3. **Costs always on.** Commission, slippage and borrow have non-zero defaults; zero costs show a "costs off" pill on every output.
4. **Validation runs the user's strategy.** Every robustness test re-runs the same compiled strategy. No built-in stand-ins.
5. **The server computes every verdict.** The browser never sends a result to be certified.
6. **One data source.** Parquet daily and hourly bars, the same loader as Screener. Chart, backtest and paper read the same numbers.
7. **Every output has a lead figure or it is cut** (Outputs v2 rule).
8. **Limits printed.** Data range, coverage, survivorship, fundamentals lag and fill model sit in the "N limits" pill on every run.
9. **Reproducible.** A run is (strategy hash, data version, settings). Same three in, same numbers out; certify re-runs it.

## 4. Ideas kept from the old Studio (as ideas, rewritten)

| Idea | Old place | New place |
|---|---|---|
| Python strategies in a locked container (no network, read-only, non-root, CPU and memory caps, `ast` screen) | `services/studio/execution.py` | `studio_v3/core/sandbox.py` |
| Cost on traded notional, gross and net equity both kept | `routers/studio.py` | `core/engine.py` |
| MAE and MFE per trade | `_trade_excursion` | `core/trades.py` |
| Monte Carlo: Gaussian, i.i.d. and block bootstrap, seeded | `MonteCarloEngine` | `core/montecarlo.py` |
| Walk-forward with purge and embargo, deterministic PASS/FAIL thresholds | `WalkForwardEngine` | `core/walkforward.py` |
| Skipped tests say "skipped, because…", never faked | `run_scenarios` | every test |
| Certification bundle hashed over inputs and results | `certification.py` | `core/certify.py`, server re-runs |
| Paper gates and kill switch | `paper.py` | `core/paper.py`, now with daily prices |

## 5. Backend architecture

New package `backend/app/services/studio_v3/`, same shape as `screener_v2` and `research_v2`, so the existing job API, manifest, state DB and share code apply unchanged.

```
studio_v3/
  registry.py          feature ids st01..st12 → runner, inputs, outputs (manifest)
  core/
    spec.py            Strategy spec (pydantic): universe, signals, entries, exits, sizing, costs, schedule
    compile.py         blocks → spec; formula → spec (reuses research_v2 signal_lang); Python → sandboxed callable
    data.py            thin wrapper over screener_v2 data_loader: daily + hourly bars, PIT fundamentals, benchmark
    engine.py          two engines over one fill model (section 5.1)
    orders.py          market, limit, stop, stop-limit, trailing, take-profit, OCA, pyramiding
    trades.py          trade list, MAE/MFE, holding time, exit reason
    metrics.py         the metric set (FEATURES_AND_OUTPUTS §4); one canonical function
    sweep.py           grid, random and Optuna search; numba-parallel over parameter sets
    walkforward.py     anchored and rolling WF, WF matrix, WFE
    robustness.py      vs random, MCPT, noise, vs shifted, vs others, delay, cost shock, param permutation
    montecarlo.py      reshuffle, resample, block bootstrap, randomized exits, equity bands
    overfit.py         PSR, DSR, PBO via CSCV, CPCV (reuse ml_v2/core/cpcv.py), minimum track record, haircut Sharpe
    regimes.py         trend, volatility, drawdown and HMM regimes (reuse research_v2/core/regime.py, ml_v2/core/regimes.py)
    verdict.py         combine every test into one graded verdict with reasons
    paper.py           frozen strategy, daily EOD step from parquet, forward equity, drift alerts
    certify.py         re-run, hash, one-page PDF (reuse screener exports)
    sandbox.py         Docker runner for Python strategies
  features/
    feature_01.py … feature_12.py   one thin runner per page
  tests/  (under backend/tests/test_studio_v3_*.py)
```

### 5.1 The engine (the part that must be best-in-class)

Two engines, one fill model, cross-checked by a test on every CI run:

| Engine | Use | How | Target speed |
|---|---|---|---|
| **Vector** | Signal strategies (enter/exit booleans, target weights), sweeps, robustness repeats | numpy + numba over a (bars × symbols) array; positions from shifted signals; costs on weight change | 10k bars × 500 names × 1 param set < 50 ms; 1,000-cell sweep < 10 s |
| **Event** | Order strategies (stops, limits, trailing, OCA, pyramiding, per-trade sizing), Python strategies | bar loop in numba (`@njit`) for blocks and formulas; pure Python loop only for sandboxed code | 10k bars × 1 symbol < 20 ms (numba), < 2 s (Python) |

Fill model (shared, explicit, printed on every run):
- Default: signal at close *t*, market fill at open *t+1*. Option: fill at close *t* ("same bar", labelled optimistic).
- Stops and limits trigger inside bar *t+1* using its high/low; when both sides hit in one bar, the worse one fills first (conservative), with a "bar magnifier" option that resolves the order from hourly bars when we hold them.
- Gaps: a stop gapped through fills at the open, not the stop price.
- Costs: commission (bps or per share, with minimum), slippage (bps or fraction of bar range), borrow on shorts (bps a year), optional volume cap (max % of bar volume, rest unfilled).
- Delisted holdings settle at last close into cash (same rule as `screener_v2/core/backtest.py`).
- Corporate actions: adjusted prices for signals, raw for share counts when both exist; otherwise adjusted, said in limits.

Why our own engine: vectorbt OSS carries the Commons Clause (not shippable), nautilus_trader is LGPL and an execution platform we do not need, backtesting.py is AGPL, backtrader GPL, zipline is portfolio-only and slow. Our arrays plus numba match their speed for the cases we sell. Licences: see [OPEN_SOURCE.md](OPEN_SOURCE.md).

### 5.2 API

No new router. Studio registers as a lab on the same pattern as Screener:

- `GET  /api/studio-v3/manifest`: features, inputs, outputs (the frontend lab reads it).
- `POST /api/studio-v3/feature/{id}/jobs` → `{job_id}`; `GET /jobs/{id}` (status, stages, result); `DELETE /jobs/{id}` cancels. SSE progress for long sweeps.
- `GET|POST|PUT /api/studio-v3/strategies[/{id}]`: saved strategies, immutable versions, diff between versions.
- `POST /api/studio-v3/compile`: blocks or formula or code → spec + lint findings, in < 100 ms, for live feedback while typing.
- `GET /api/studio-v3/bars?symbols=&from=&to=&tf=1d|1h`: the one price source, also for the chart.
- `POST /shares`, `GET /shared/{token}`: same as Screener's share code.

### 5.3 Data (what we hold, said plainly)

- Daily OHLCV: `market_universe.parquet`, about 4,157 instruments, 1999 to 2026-01-28 (Screener's range strip).
- Hourly: `market_universe_hourly.parquet` and `intraday_hourly_v5`; range and coverage to be measured in phase 0.
- Fundamentals: from 2021, 90-day filing lag (Screener rule).
- No tick data, no order book, no options chains history: no tick-level fills, no options strategies in v3.
- Survivorship: listed and delisted names as the parquet holds them; measure the delisted share in phase 0 and print it.

## 6. The chart, rebuilt

`components/chart_engine` holds the most finished work (71 indicators, ~40 drawing tools, candlestick patterns, alerts) but reads live yfinance and is one 2k-line core plus a 1.7k-line canvas. Plan: dissect, keep the maths, rebuild the shell.

- Keep and port to `frontend/src/charts/studio/`: indicator maths (`IndicatorEngine/registry.ts`), drawing tool geometry (`DrawingEngine/*`), pattern detectors (`PatternScanner`).
- Rebuild: one chart component on `lightweight-charts` 5 (already installed; panes and plugins), fed only by `/api/studio-v3/bars`.
- New: strategy overlay (entries, exits, stops as price lines, position shading), trade markers that open the trade in the ledger, replay with a scrub bar (C3 pattern), multi-symbol sync.
- Alerts move to the server (Screener's alerts and notify), not `localStorage`.
- Detail in [FRONTEND.md](FRONTEND.md) §5.

## 7. Phases (importance order; phone last)

Each phase ends with tests green, a screenshot pass at 1440 and 1024, and a commit.

| Phase | Ships | Done means |
|---|---|---|
| 0 | Data audit and engine spike | Hourly coverage and delisted share measured; vector engine runs SMA cross on 500 names under target speed; event engine matches it trade for trade |
| 1 | Spec, compile, engine, metrics, Backtest page (st01) | Formula and block strategies backtest end to end in the lab; hero, equity, trades, metrics, limits |
| 2 | Build page: blocks, formula, Python sandbox, versions, live lint | Same rule written three ways gives identical trades (test) |
| 3 | Optimise (st02) and Validate: walk-forward (st03), robustness (st04), Monte Carlo (st05), overfitting (st06), one verdict | Planted overfit strategy is flagged; a known-robust one passes |
| 4 | Chart workspace (st12) | Trades on price, replay, indicators ported, one data source |
| 5 | Regimes (st07), Combine (st08), Signals today (st09) | |
| 6 | Paper (st10) and Certify (st11) | Paper steps daily from parquet; certify re-runs and the hash matches |
| 7 | Remove old Studio | Graph + `rg` + route checks + smoke test, per AGENTS.md; `/studio` points at the new lab |
| 8 | Phone layout | Bottom nav, settings sheet, card rows (shared with Screener phone-1) |

## 8. Removed (when phase 7 lands)

Removal follows AGENTS.md: graph check, `rg`, route registration check, smoke test, then delete in one commit.

- `backend/app/studio_v2/` (all of it, after `persistence` and `observability` callers move)
- `backend/app/routers/studio.py`, `backend/app/services/studio/`
- `frontend/src/components/studio/`, `src/app/studio/` (replaced), `src/stores/studio/`, `src/hooks/studio/`, `src/lib/studio*.js`
- `frontend/src/components/chart_engine/` after its maths is ported
- Old Studio tests (`backend/tests/test_studio_*.py`) replaced by `test_studio_v3_*.py`
- `/trade` redirects to the Studio chart

## 9. Not doing in v3

- Live broker trading (paper only; a broker adapter is a later decision with legal weight)
- Tick data, order book, options strategies (data we do not hold)
- Crypto and forex unless Screener's non-equity loader covers them (check in phase 0)
- Multi-user collaboration (single-owner strategies; share by link)
- An AI that writes strategies with no human review (plain English → formula is in, shown before it runs)
