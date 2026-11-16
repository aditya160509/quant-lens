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
- [ ] Blocks editor ⇄ formula both ways
- [ ] Python in Docker sandbox (no network, read-only, non-root, caps, `ast` screen); formula → Python one way
- [ ] Plain English → formula, shown for review before it runs
- [ ] Higher-timeframe rules aligned to the last closed bar (B-3)
- [ ] Allocate blocks (if/else on regime, rotate, weight)
- [ ] Preview chart < 300 ms after typing (B-5); repaint check and lint rows
- [x] Autosave draft every 2 s, undo/redo (⌘Z / ⇧⌘Z), immutable versions with picker (B-6); side-by-side diff still to do
- [x] "What it does" paragraph from the spec, no LLM (B-9)
- [x] Notes (hypothesis, regime, decisions); My limits saved with the version
- [ ] Templates (20)
- [x] Backtest tabs When (regime by benchmark trend × vol, seasonality), Names (contributors, per-name table), Paths (trade Monte Carlo fan, ruin, losing streaks); still to do: conditions (needs Library regimes), timeline, holdings treemap, prop rule check
- [ ] B-1 same rule as blocks, formula and Python gives identical trades

## Phase 3: Optimise, Validate, alerts
- [ ] Optimise: grid, random, Optuna; heatmap with plateau, 3D lazy and off by default, top sets, Pareto, importance; sweep feeds ledger (O-1..O-5)
- [ ] Validate > Walk-forward: anchored and rolling, purge and embargo, matrix, drift
- [ ] Validate > Robustness: tiles, vs random, price paths (noise, MCPT, shifted), execution, parameters, others, shocks
- [ ] Validate > Luck: luck lottery, DSR, PBO, CPCV, track record, haircut
- [ ] Validate > Hold-out: sealed, look log by actor, agent budget of 3 (V-4, V-5)
- [ ] Validate > Verdict: server-side grade, next test, what would change it (no tuning advice), power card, editable weights (V-1, V-2, V-6..V-8)
- [ ] Validate > Certificate: server re-run, hash, one-page PDF, share link (V-3)
- [ ] Alerts and daily digest engine (email, push, Telegram, webhook) with quota and failure status
- [ ] Agent API adds `optimise`, `validate`, `get_verdict`, `open_holdout`
- [ ] V-9 tile flip, V-10 quick profile < 10 s

## Phase 4: Chart
- [ ] `StudioChart` on lightweight-charts 5, `/bars` only, 1-4 pane grid with synced crosshair
- [ ] Indicator maths ported from `chart_engine` and matched to backend formulas (C-1)
- [ ] Drawings ported, saved per symbol on the server
- [ ] Strategy overlay (2 strategies), trade navigator, replay (C-4, C-5)
- [ ] Alerts created on the chart use the phase 3 engine
- [ ] `/trade` redirects to `/studio/chart` (X-7); C-2, C-3 green

## Phase 5: Portfolio and Live
- [ ] Portfolio: combine up to 8, allocation methods, correlation, marginal contribution, overlap, meta rules (P-1..P-4)
- [ ] Live > Today: signals, near triggers, map, orders sheet; blocked when data is red
- [ ] Live > Forward: freeze (`F`), daily step from parquet, Monte Carlo band, drift, decay clock (L-1..L-3, L-6)
- [ ] Live > Ledger, Health (cost leak, signal health, drawdown odds, shadow book)
- [ ] Live > Reconcile: backtest vs paper vs real, real-trade CSV import (L-5)
- [ ] Live > Alerts and digest wired (L-4, L-7)
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
- [ ] Old Studio code removed (done 2026-11-15, commit `e778120`); `chart_engine` removed after phase 4 port (graph + `rg` + route checks + smoke test)
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
