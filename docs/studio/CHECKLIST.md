# Studio v3 checklist (build order)

The one order of work. Page specs and acceptance ids (H-, B-, K-, O-, V-, P-, L-, C-, Y-, X-) are in [PAGES.md](PAGES.md); reasons in [REVIEW.md](REVIEW.md). Each phase ends with its acceptance tests green, screenshots at 1440 and 1024 (dark and light), a commit and a push. A phase starts only when the one before is done, except where marked "parallel".

## Phase 0: engine foundations
Built on the data we hold today; the data refresh is phase 9, after the whole build.

Engine
- [x] One canonical `services/shared/metrics.py` (the metric set); ML's Sharpe, drawdown and equity now import it. The three `performance.py` files turned out to be caches, not metric copies; Portfolio `performance_metrics` and Factors `perf_stats` keep their own output contracts (different ddof and Sortino definitions, pinned by their tests)
- [x] Vector engine (numba): SMA cross, 500 names, 10 years; measure against the 5 s budget (K-9). Measured 2026-11-16: load + signals 0.44 s (warm file cache), engine 0.009 s, 500 names × 3,319 bars
- [x] Event engine: same strategy, trade-for-trade match with the vector engine (5 parameter sets, longs and shorts, 1e-9)
- [x] Fill model shared by both: next open default, same close (optimistic label), gap through stop fills at open, worse-first same-bar rule, bar magnifier where hourly exists (K-3)

## Phase 1: backtest end to end (first usable Studio)
Status 2026-11-16: backend done and tested (34 tests). Frontend written and typechecked (lab, route, nav, run header, Home, Backtest hero and four tabs) but never opened in a browser: no screenshots, no Playwright tests, so the frontend boxes stay open.
Backend
- [x] `studio_v3` package: registry, manifest, jobs API `/api/studio-v3/...` on the shared `JobStore`
- [x] `/limits` and `/bars` endpoints (one price source for every page)
- [x] Strategy spec (pydantic) + compile from formula (shared `signal_lang` lifted to `services/shared/formula/`); look-ahead refused with line and token (B-2)
- [ ] Costs: commission, slippage, borrow, volume cap and delisting haircut done; dividends on shorts not charged (no dividend column until phase 9)
- [x] Sizing incl. risk per trade; exits incl. time stop, breakeven, scale out (B-8). Not built: vol target, Kelly, score, risk parity sizing; scale in
- [x] Trial ledger: raw and effective counts (B-7)
- [x] Zero- or too-few-trade runs refused with a reason (K-7)
- [x] Hold-out boundary (last 20%) excluded from every Backtest series (K-10)
- [x] Agent API: REST + MCP for `compile`, `backtest`, `get_ledger`, `get_data_audit`; actor log (X-3)

Frontend
- [ ] `studioLab.ts`, `/studio/[[...slug]]`, nav (Home · Build · Test · Portfolio · Live · Chart · Library), Studio back in `GlobalLayout`
- [ ] Shared pieces: run header, limits pill, freshness pill, My limits strip with closest call, trial chip, verdict chip ("not validated")
- [ ] Backtest hero (net vs benchmark, drawdown shade, hold-out line) + cost ladder 1×/2×/4×
- [ ] Tabs Overview (equity, start dates, survivorship delta, fill check), Trades (list, carried by, trade shape, unfilled), Returns (calendar, crisis strip), Risk (drawdowns, stability, costs, capacity, exposure)
- [ ] Home: strategy cards, needs attention, duplicate, import JSON spec (H-1..H-5)
- [ ] K-1..K-11 green

## Phase 2: Build
- [x] Formula editor with live compile (0.26 ms measured) and per-role findings (B-4); Screener formula-bar autocomplete not yet wired
- [x] Blocks editor ⇄ formula both ways (rows of comparisons and crosses joined by and/or; other shapes stay formula; vitest round-trip)
- [x] Python mode: Monaco with `ctx` completion, hovers, snippets, inline markers from server checks and runtime errors; `class Strategy` with `init`, `on_bar`, `on_fill`; runs in a child process (`-I`, empty env, CPU/file limits, builtins allow-list, `ast` screen, no positive indexes); formula → Python one way (tested: same trades). Not done: Docker container (daemon off), format on save
- [x] Plain English → formula by fixed phrase rules (MAs, crosses, RSI, highs and lows, ROC, weekly trend, volume, stops, targets, time stops); ignored words listed; review then "Use this rule"
- [x] Higher-timeframe rules aligned to the last closed bar: `weekly(x)` (B-3, tested)
- [x] Allocate: "Trade only when" market rule (`market` = SPY close; no entries while false, everything closed on the bar it turns false); rotate = Rank by + max positions; Portfolio switch rule (P-2). Not done: weight by score sizing, Kelly
- [x] Preview chart: any symbol, last 2 development years, entries and exits marked, refreshes 300 ms after typing (server 0.37 s); lint rows shown per rule (B-5)
- [x] Repaint check: signals recomputed on 50 history cuts of the preview name must equal full-history signals; shown under the preview
- [x] Autosave draft every 2 s, undo/redo (⌘Z / ⇧⌘Z), immutable versions with picker, field-by-field diff against any version (B-6)
- [x] "What it does" paragraph from the spec, no LLM (B-9)
- [x] Notes (hypothesis, regime, decisions); My limits saved with the version
- [x] Templates (20)
- [x] Backtest tabs When (regime by benchmark trend × vol, seasonality), Names (contributors, per-name table), Paths (trade Monte Carlo fan, ruin, losing streaks); plus Timeline (regime strip under equity), Conditions (market trend, volatility, drawdown known the night before), Holdings (P&L treemap by name, names held over time), Rule check (target, daily loss, drawdown, min days from every monthly start; ring + table, inputs in settings). Not done: unfilled limit orders (no limit orders in the engine)
- [x] B-1 same rule as blocks, formula and Python gives identical trades (blocks compile to the formula text; Python parity tested)
- [x] Checks card (compiles, no look-ahead, fires, trades on one name, exits, parameters used) with jump links; template start grid; command palette ⌘⇧P (lift number to parameter, add parameter, modes, templates, save, run; ⌘K stays the app search); parameter step and sweep size; vol-target sizing in both engines; backtest results side by side in the version diff; regime claim marked when written after a backtest; trial chip opens the ledger; drag to reorder block rows

## Phase 3: Optimise, Validate, alerts
- [x] Optimise: grid, random, Optuna (TPE); parameter map with plateau outlined, spike vs plateau call, send plateau centre to Build as a new version, top sets, all cells, Pareto, importance; every cell a trial (O-1..O-3 tested; 1,000 cells on one symbol < 10 s). plus 3D surface (Plotly, off by default), objectives profit factor / return over Ulcer / custom formula, link rule (fast < slow), constraints (min trades, max drawdown: cells excluded and counted), log-scale parameters, time budget, neighbourhood radius with stability gauge and histogram, spread of plateau equity curves, trial cost in the hero. Not done: heatmap filling in live while cells run, O-4 cancel test, O-5 screenshot baseline
- [x] Validate > Walk-forward: rolling windows over a parameter grid, stitched out-of-sample, efficiency, windows table with chosen params (drift). Not done: anchored mode, purge and embargo, re-opt × OOS matrix
- [x] Validate > Robustness: tiles, vs random entries, price noise, permutation (MCPT), delay 1 and 2 bars, cost ladder to break-even, nearby settings. Not done: shifted starts (Backtest has start dates), related symbols, shocks
- [x] Validate > Luck: luck lottery, deflated Sharpe on the effective trial count, PBO (CSCV, cash blocks score 0), minimum track record, Harvey-Liu haircut. Not done: CPCV
- [x] Validate > Hold-out: sealed by default, opened only on request, every look logged by actor, agents capped at 3 (V-4, V-5 tested)
- [x] Validate > Verdict: server-side grade with one reason, cap at C on few trades, next test, what would change it (no tuning advice), editable weights recompute in the page (V-1, V-7, V-8 tested). Not done: power card (V-6), V-2 API test
- [x] Validate > Certificate: server re-runs the stored payload and compares result hashes (V-3 tested); PDF and share link from the shared run header
- [ ] Alerts and daily digest engine (email, push, Telegram, webhook) with quota and failure status: built with Live in phase 5 (alerts fire on Live's daily signals; reuses Screener's Apprise notifier)
- [x] Agent API adds `optimise`, `validate`, `get_verdict`, `open_holdout` (MCP; agents cannot open the hold-out through validate; budget tested)
- [ ] V-9 tile flip, V-10 quick profile < 10 s

## Phase 4: Chart
- [x] `StudioChart` on lightweight-charts 5, `/bars` only: candles, volume pane, indicator panes, day/week/month/hour. Not done: 1-4 chart grid with synced crosshair, compare symbols
- [x] Indicators: all 70 from `chart_engine` registry usable (imported in place until phase 7 moves the file), editable params, kept per user. Not done: C-1 match test (registry EMA seeds with an SMA, backend EMA does not: differs in the first bars)
- [ ] Drawings ported, saved per symbol on the server
- [x] Strategy overlay (one run's trades: entries, exits with P&L), trade navigator (← →, zoom to trade ±20 bars), replay (R, 1×/5×/20×, scrub); Backtest > Trades links each traded name to Chart (C-4). Not done: two strategies at once, C-5 frame test
- [ ] Alerts created on the chart use the phase 3 engine
- [ ] `/trade` redirects to `/studio/chart` (X-7): not done on purpose; `/trade` is a multi-tab trading page, not only a chart, so redirecting would remove features. Owner decision. C-2, C-3 not yet measured

## Phase 5: Portfolio and Live
- [x] Portfolio: combine up to 8 saved strategies (picked in the strip), equal / inverse-vol / min-variance (weights in-sample, labelled), correlation, marginal contribution, overlap, meta switch rule on the benchmark acted next bar (P-1, P-2 tested). Not done: P-3 send combined to Validate
- [x] Live > Today: signals, near triggers, orders sheet; red freshness shown (runs anyway). Not done: map
- [x] Live > Forward: freeze per version (backdate labelled), bootstrap band, drift, segments (L-6 tested). Not done: `F` key, decay clock, L-1..L-3 tests
- [ ] Live > Ledger, Health: fills and drawdown odds done. Not done: cost leak, signal health, shadow book
- [x] Live > Reconcile: real-trade CSV matched ±2 days, fills vs model (L-5 tested)
- [x] Live > Alerts: Apprise channels, test send, digest on run, failures logged (L-7 tested). Not done: scheduled daily digest
- [ ] Live phone-first at 390 px (L-8)
- [ ] Agent API adds `get_signals`, `freeze_paper` (human click required)

## Phase 6: Library and imports
- [ ] Universes, costs (dated India STT if coverage allows), benchmarks, blocks and indicators, regimes and crises
- [ ] Custom metrics usable as KPI, column, objective, limit (Y-1)
- [ ] Profiles: validation, report order, sizing, layout; export and import (Y-3)
- [ ] Data section shows the phase 0 audit live
- [ ] Imports: CSV bars, Composer and QuantMage JSON mapper with untranslated parts listed
- [ ] Agents: tokens, scopes, actor log, look budget
- [ ] Optional AI reviewer as text over deterministic findings (never sets the grade)
- [ ] X-5 cost profile change marks runs stale; Y-4

## Phase 7: cross-page finish
- [ ] Old Studio code removed (done 2026-11-15, commit `e778120`); Studio Chart now embeds the full `chart_engine` chart (owner ask), so `chart_engine` stays (graph + `rg` + route checks + smoke test)
- [ ] Old Studio routes redirect to the nearest new page (X-7); `rg` finds no removed imports (X-8)
- [ ] Compare, share, export, reproduce across pages (X-4, X-6)
- [ ] Empty, loading, error, skipped states on every page (X-2)
- [ ] Budgets in PAGES §10.7 as Playwright checks under `frontend/e2e/perf/`
- [ ] Visual baselines for every route (X-1)

## Phase 8: phone
- [ ] Bottom nav, settings sheet, card rows (with Screener phone-1) for every page besides Live
- [ ] Build on phone: Formula and Plain English only

## Phase 9: data refresh (after the whole build)
Until it lands, every result's limits popover states the data as it is (mixed adjustment, most tickers end 2026-01-28 to 2026-02-01, hourly for 23 names).
- [ ] Rebuild daily parquet from Yahoo `period="max"`: one total-return adjustment for OHLC, plus RawClose, Dividends, Splits; delisted names keep their old rows; stage, validate (no ticker lost, spot checks), back up, swap
- [ ] Hourly parquet: 730 days of 1h bars for every ticker
- [ ] Daily update job (EOD append, same adjustment), logged; freshness date exposed (needed before Live is used for real)
- [ ] Data audit: symbols per year, bars per symbol, rows / 252, gaps, adjusted status, delisted share, fundamentals lag (Y-2)
- [ ] India and non-equity coverage measured; result written into PLAN §5.3

## Not in v3 (REVIEW §3)
Manual replay and journal (G2), public gallery (G4), prop-firm page (now a Paths panel), tax and wash-sale (G10), live broker trading, tick data, options.

## Decisions for the owner
- [ ] Pyodide (MPL-2.0) for in-browser Python preview: default no
- [ ] OpenBB licence conflict (Apache vs AGPL): default not used
- [ ] `arch` licence file missing on GitHub: check before relying on it beyond the existing install
- [ ] Pine import: only after the PineTS licence check (AGPL)
