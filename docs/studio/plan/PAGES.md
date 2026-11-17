# Studio v3: page spec

Date: 2026-11-15. Replaces the page plan in FRONTEND.md §1-2 and the page list in FEATURES_AND_OUTPUTS.md §0. Engine, principles, metric set and customisation layers in PLAN.md and FEATURES_AND_OUTPUTS.md §4, §10 stay. Reasons for every change: [REVIEW.md](REVIEW.md).

Style rule (Outputs v2): one lead figure or one-line finding per card; no taglines; no helper text a good layout would not need. Everything cut from a card stays in its Table view or Export.

Reuse paths are from [REUSE.md](../research/REUSE.md) (checked 2026-11-15). "Shared" = already in `modules/research` or `kit`.

---

## 0. Pages, routes, nav

| Page | Route | Job | Nav group |
|---|---|---|---|
| Home | `/studio` | none | top |
| Build | `/studio/build/:id?` | compile only | top |
| Backtest | `/studio/backtest` | `st01` | Test |
| Optimise | `/studio/optimise` | `st02` | Test |
| Validate | `/studio/validate` | `st03` (validate, composed of tests) | Test |
| Portfolio | `/studio/portfolio` | `st04` | top |
| Live | `/studio/live` | `st05` (daily step, signals) | top |
| Chart | `/studio/chart/:symbol?` | bars only | top |
| Library | `/studio/library/:section?` | none | bottom |

Nav: `Home · Build · Test (Backtest, Optimise, Validate) · Portfolio · Live · Chart · Library`. Dot on a page = fresh unseen run. Old ids st03-st12 retire; the manifest keeps one id per job.

Every run page reads `?strategy=<id>@<version>&run=<job>`. The strategy picker is in the run header on every page.

## 0.1 Shared pieces (used by every page)

| Piece | What it shows | Rule |
|---|---|---|
| Run header | Title, strategy chip (name, version), status, Save, Share, Export, Run | Reuse `FeatureView` |
| Hero | The lead figure of the page | Kinds: `figure`, `versus`, `lines`, `bars`, `fan`, `heatmap`, `tiles`, `gauge`, `grade`. New: `fan`, `heatmap`, `tiles`, `gauge`, `grade` in `modules/research/Hero.tsx` |
| KPI strip | 4-6 numbers, user-pickable | `kit/KpiStrip.tsx` |
| Limits pill | "N limits"; popover: data range, coverage, delisted share and rule, fill model, costs, fundamentals lag, hourly held for K names, data freshness date | One source: `/api/studio-v3/limits` |
| Freshness pill | "Data to 2026-07-06 (132 days old)" amber after 3 days, red after 10 | Blocks Live when red |
| My limits strip | Pass or fail against the user's walk-away conditions with the closest call: "Drawdown 22% of 25% limit: 12% room" | Opens every result before the hero |
| Trial chip | "1,840 raw / 212 effective trials" | Opens ledger (section 3.9) |
| Verdict chip | Grade letter if validated, else "not validated" | Links to Validate |
| Stale marker | Settings changed after the run | `FeatureView` |

Shared inputs on every run page (one `Inspector`, grouped; defaults from the user's saved profile):

| Group | Inputs |
|---|---|
| Strategy | Saved strategy and version, or the open draft |
| Universe | One symbol, list, saved Screener screen (re-run point in time each rebalance), Screener preset, top N by liquidity or cap, uploaded CSV set, saved Library universe; shows count and delisted count |
| Period | Presets 1Y to Max, custom start and end, as-of date. **Development period only** until Validate opens the hold-out (last 20% by default, editable once before the first run, then locked) |
| Timeframe | 1d; weekly and monthly resampled (1h superseded by C-29) |
| Fill | Next open (default); same close (labelled optimistic); bar magnifier where hourly exists, else worst-case same-bar rule (superseded by K-30) |
| Costs | Library cost profile (US retail, India retail with dated STT and charges, crypto maker and taker, custom); commission bps or per share with minimum; slippage bps or % of range; borrow bps a year; dividends on shorts; volume cap |
| Delisting | Delisting return: last close (default, labelled) / haircut % / custom per exchange |
| Sizing | Fixed shares, fixed $, % equity, **risk per trade (% equity to the stop)**, vol target (ATR, stdev), Kelly (capped), equal, score, risk parity |
| Portfolio | Max positions, max weight, rebalance (daily, weekly day, monthly, on signal), long, long-short, short, cash yield |
| Benchmark | SPY default, any symbol, 60/40, buy-and-hold of universe, own CSV |
| Capital | Starting capital, currency, leverage cap, margin rate |

---

## 1. Home

| Item | Spec |
|---|---|
| Purpose | Find a strategy, see what needs attention, start a new one. |
| Who, when | Everyone, on arrival. Daily users glance at "needs attention" then go to Live. |

**Inputs**

| Group | Inputs |
|---|---|
| Find | Search (name, tag, hypothesis text), filters (grade, paper status, folder, tag), sort (last run, grade, name) |
| Create | New blank, from template, from a Screener screen, duplicate, import (Studio JSON, trade CSV, Composer or QuantMage JSON via mapper) |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Needs attention | "2 strategies: data stale, 1 drift alert" | List with one action each | TradingView alert emails scattered across inboxes |
| Strategy cards | Mini equity, grade, trial count, paper status, last run date | Card grid, folders | Composer and Tactfolio lists (name and return only) |
| Recent runs | Run, strategy, settings changed since previous | Table | |
| Templates | 20 starters with a one-line rule | Card grid | |
| Data freshness | "Daily data to 2026-07-06" | Pill | Nobody shows it |

**Interactions**: click card to open the last run; `N` new; `/` search; drag to folder; multi-select then Compare or Archive; press `D` duplicate. Compare up to 8 strategies opens Portfolio.

**Customisation**: card fields, sort, density, folder colours, which templates show.

**States**

| State | Shows |
|---|---|
| Empty | Three actions: blank, template, from a Screener screen |
| Loading | Card skeletons, 150 ms delay before showing |
| Error | Strategy list failed: retry; cached list kept |
| Skipped | Card without a run shows "not run" and a Run button |

**Reuses**: `screener/saved/SavedPage.tsx` (cards, mini result, folders, schedule pill), `kit/Compare.tsx`.

**Acceptance**

- H-1 With 50 saved strategies the page paints cards in under 400 ms (Playwright).
- H-2 "Needs attention" lists a strategy whose Paper last step is older than 3 trading days.
- H-3 Duplicate creates a new strategy with version 1 and an empty trial ledger; the source ledger is not copied.
- H-4 Importing a Studio JSON spec recompiles it and shows compile findings before saving.
- H-5 Screenshot at 1440 and 1024, dark and light.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **H-6** Table view with sortable, toggleable columns (name, status, Sharpe, max DD, last run, equity sparkline) and a stale-run badge; card view stays the default [FP 53]
- **H-7** Status chips Draft, Backtested, Validated, Paper, Live; a click filters; Validated only when a scorecard exists for the current version [FP 53]
- **H-8** Search by name, tag, hypothesis, symbol, indicator and code text (typing rsi( finds strategies that use it)
- **H-9** Saved filters, folders, tags and pins
- **H-10** Archive; hard delete needs a typed confirmation and a 30-day trash
- **H-11** Bulk actions on a selection: tag, move, archive, run same range, compare, combine into a portfolio [FP 53]
- **H-12** Hover actions on a row: Run, Duplicate, Open in Chart, Open Live, Share
- **H-13** Create menu: blank, template, plain-English prompt, Studio bundle, trade CSV, QuantConnect Python (via shim), library strategy
- **H-14** Live strip at the top: live and paper strategies with today P&L, alert count, heartbeat and kill-all
- **H-15** Saved views, column sets, default sort, density, group by status, tag or folder
- **H-16** Empty state: three one-click starters (blank, template, from a Screener screen)
- **H-17** Compare 2 to 6 strategies from Home: overlaid equity, metric table, correlation, code diff; opens Portfolio
- **H-18** Needs attention ranked: drift beyond band, data newer than last run, validation expired by a code change, failed run, alert fired
- **H-19** Import a QuantConnect algorithm through the shim; unmapped calls listed before saving [FP 67]
- **H-20** Import a CSV of signals
- **H-21** Card fields: sparkline of last run, verdict chip, trial count, last edited
- **H-22** Recent runs table with a settings-changed-since marker
- **H-23** Data freshness pill ("Daily data to 2026-02-01"), amber after 3 days, red after 10
- **H-24** Customise: default view, card fields, grid columns and sort, pinned strategies
- **H-25** Bulk re-run on new data and export a selection as a zip
- **H-26** Strategy cards with grade, trial count, paper status and last run; duplicate; JSON import (first version)

---

## 2. Build

| Item | Spec |
|---|---|
| Purpose | Write the strategy once, in blocks, formula, Python or plain English, and see signals on price as you type. |
| Who, when | Anyone creating or editing; most time spent here before the first Backtest. |

**Inputs**

| Group | Inputs |
|---|---|
| Entry | Long and short conditions: indicator, price, fundamental, calendar, cross-sectional, higher-timeframe (aligned to the last closed higher bar; lookahead-safe by construction), earnings-date filter where dates are held |
| Exit | Stop % or ATR, trailing, take profit, **time stop (N bars)**, indicator exit, **breakeven move**, **scale out in parts**, **scale in** (pyramiding rules) |
| Allocate | Rotate among a basket, weight by score, **if/else on a condition (regime, trend)**, hold bonds or cash when off. Same object as the rest |
| Sizing | As shared inputs, including risk per trade |
| Parameters | Any number lifted to a named parameter with range and step; step count shown against the sweep size |
| Rules in words | Plain English box; result shown as blocks and formula; nothing runs until accepted |
| Code | Python `class Strategy` with `init`, `on_bar(ctx)`, `on_fill`, sandboxed |
| My limits | Walk-away conditions: max drawdown, max drawdown duration, min trades, min years, beta ceiling, max cost share, min pass share across start dates |
| Stated regime | Optional "works when..." claim, saved with the version; marked "written after" if added after a drawdown |
| Notes | Hypothesis, what was tried, decisions; saved with versions; exported with the certificate |
| Preview symbol and window | First universe symbol, last 2 years by default |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Editor (four modes) | One spec | Blocks rows / Formula bar / Monaco / Plain English | NinjaTrader AI: script is the only check [S4]; ours shows blocks and a paragraph |
| What it does | A deterministic 3-line description of the spec, no LLM | Text under the editor | |
| Signals preview | "14 trades, +31%, last 2 years" | Mini chart, throttled 300 ms | TradingView inputs need a full run |
| Checks | "No look-ahead (50 cuts)"; lint; too few trades; missing exit; signals never fire | Rows with fix links | Pine ports reintroduce look-ahead silently |
| Trial ledger | "1,840 raw / 212 effective; humans 40, AI helper 12, agents 1,788" | Chip, drawer with list | Nobody found counts by actor |
| Versions | v7, diff against v5 (rules or code side by side, results side by side) | Drawer | `@pierre/diffs` |
| Compile findings | Errors mapped to Monaco markers and token underlines | Inline | |

**Interactions**: `⌘↵` run backtest; `⌘S` save version; autosave every 2 s to a draft (survives reload); undo and redo history of edits; Tab through block slots, Enter adds a row; drag rows; switch Blocks ⇄ Formula both ways, Formula → Python one way (original kept); `⌘K` palette: "new strategy from template", "lift number to parameter"; snippets in Monaco; paste Pine as a stretch import (only after the licence check).

**Customisation**: saved rule groups as reusable blocks; custom indicators by formula (shared with Chart and Screener); personal templates; parameter ranges per strategy; default sizing and costs per user; editor font and keymap.

**States**

| State | Shows |
|---|---|
| Empty | Template picker and Plain English box |
| Loading | Editor shows immediately; checks show "checking" rows |
| Error | Compile error inline at the token; Run stays disabled with the reason |
| Skipped | Repaint check "skipped: fewer than 60 bars of data" with reason; never blank |

**Reuses**: `screener/formula/*` (formula bar), `@monaco-editor/react`, `screener_v2/core/formula.py` and `nl_formula.py`, `research_v2/core/signal_lang.py` lifted to `services/shared/formula/`, `charts/PriceChart.tsx` for the preview until Chart lands, `kit/` DataTable not needed.

**Acceptance**

- B-1 The same rule written as blocks, formula and Python produces identical trades (backend test, three fixtures).
- B-2 A strategy that reads `close[+1]` or a centred window is refused with the line and token named (planted test).
- B-3 A higher-timeframe "weekly SMA" rule evaluated on a Wednesday uses the last closed week; test compares to a hand-built frame.
- B-4 Compile responds in under 100 ms server side for a 20-row strategy.
- B-5 Preview refreshes within 300 ms after typing stops (Playwright in-page timing).
- B-6 Reload restores the unsaved draft exactly.
- B-7 Trial ledger shows raw and effective counts; ten near-identical sweep cells add ten raw and fewer than four effective (test).
- B-8 Time stop, breakeven and scale-out each have a fixture strategy with exact expected trades.
- B-9 "What it does" paragraph for the SMA cross fixture equals a stored string.
- B-10 Screenshot at 1440 and 1024.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **B-11** Full-height IDE: editor fills the work area; bottom panel resizes 30 to 40%; side rail collapses [PY B1]
- **B-12** Three zones: left rail (Files, Outline, Search, Templates, Versions), centre editor, bottom panel (Problems, Output, Logs, Results, Plots, Debug, Terminal); right rail (preview, Inspector, AI); each zone remembers its size
- **B-13** Editor groups: split right or down, up to 4 groups; tabs can be pinned, kept in preview, or marked dirty
- **B-14** One editing session per strategy: a second tab opens read-only with a take-over button
- **B-15** Phone (390 px): one zone at a time with a Code, Run, Results switcher; Build on phone is Formula and Plain English only
- **B-16** IDE keys: F5 debug, F9 breakpoint, F10 step bar, F11 step line, ⌘J panel, ⌘B rail, ⌘\ split, ⌘P file, ⌘⇧F search project
- **B-17** JetBrains Mono 13 px, 20 px line height, ligatures off, bracket colours, sticky scroll, folding [PY B13]
- **B-18** App theme tokens defined as a Monaco theme so the editor sits in the page [PY B12]
- **B-19** Editing keys: ⌘/ comment, ⌥↑↓ move line, ⌘D next match, ⌘⇧K delete line, ⇧⌥-drag column select, go to line ⌃G [PY B5]
- **B-20** Format Python on save with ruff
- **B-21** Format selection (⌘K ⌘F) and organise imports
- **B-22** Go to symbol ⌘⇧O, go to line ⌃G, definition F12, references ⇧F12, peek ⌥F12, rename F2 across files
- **B-23** Find and replace across all project files: regex, case, whole word, preview before replacing
- **B-24** Code actions ⌘.: extract formula string to parameter, convert ctx.rule to indicator object, wrap selection in if ctx.position == 0, add missing on_fill
- **B-25** Outline of classes, methods and indicators for the open file
- **B-26** Undo history survives reload, per file
- **B-27** Save state indicator (Saved, Saving, Conflict) and local draft recovery from IndexedDB
- **B-28** Read-only banner when the editor code differs from the code that produced the visible result
- **B-29** Side-by-side Monaco diff of two versions, with each version run result above it [PY B9]
- **B-30** In-browser Pyright in a web worker with Studio stubs (ctx, portfolio, orders, indicators, numpy, pandas, math, typed Bar, Fill, Order, Position); covers the user own classes [FP 26, 62]
- **B-31** Completion inside ctx.value("…") for formula names, ctx.param("…") for parameter names, ctx.symbol == "…" for symbols, ctx.history("…") for fields; snippets with tab stops
- **B-32** Completion for the whole API with signature help on "(" (active parameter bold) and a docs example [PY B6]
- **B-33** Three diagnostic layers as you type (300 ms): Pyright errors; Studio rules (banned names, look-ahead patterns, imports outside the allow-list); formula parse errors at the exact token
- **B-34** Hover: docs, signature, formula meaning, lookback and warm-up bars, latest value after a preview; hover on a parameter shows its range and last best value
- **B-35** Look-ahead detector in the editor: close[0], close[1:], history without a negative index, ctx.date against future literals, next_* reads; marked before the run [FP 8]
- **B-36** Docs panel: ⌘-click or F1 opens the reference beside the editor; searchable (API, indicators, recipes); offline and versioned
- **B-37** Strictness setting (basic or strict) and severity per rule (error, warning, off); defaults: basic, all layers, look-ahead as error
- **B-38** Domain diagnostics: unused parameter, warm-up longer than data, order with no stop in live, hard-coded symbol in a parameterised strategy, print in hot loop, mutable default in params [FP 26]
- **B-39** ctx.assert_invariant(cond, msg) puts red markers on the chart and fails the Validate step
- **B-40** Lint flags wall-clock time, network calls and unseeded random, so one code runs in backtest, paper and live
- **B-41** API version header (# studio-api: 1) with an automatic migrator and a quick fix
- **B-42** Latency budget: completions under 100 ms, diagnostics under 500 ms after typing stops
- **B-43** Portfolio mode: on_data(ctx) sees every symbol in the bar; universe set by a class attribute (list, index, or screen id); per-symbol on_bar kept as the simple mode [FP 61] [PY A1]
- **B-44** Orders: target_weights, set_weight, order (qty), order_value, limit, stop, stop_limit, liquidate, cancel, cancel_all; all fill through fills.py [FP 61] [PY A2]
- **B-45** Brackets: bracket(sym, qty, stop, target, trail) with OCA cancel; partial exits by qty per level; stop fills first when both hit one bar [FP 61]
- **B-46** Pyramiding: max_entries class attribute per symbol; scale in added to the Build exits card [FP 61]
- **B-47** Read-only portfolio state: ctx.portfolio cash, value, leverage, exposure; ctx.pos(sym) qty, avg price, unrealised, bars held, entry date [FP 61] [PY A3]
- **B-48** ctx.history(field, n, sym=None) returns numpy (pandas=True for a DataFrame); negative indexes only [PY A5]
- **B-49** ctx.bar(sym) for the current bar and ctx.market for the benchmark
- **B-50** ctx.indicator(formula) with .value, .ready, .history(n), .window; LEAN-identical definitions (LEAN_PARITY row 19) [FP 43] [PY A4]
- **B-51** ctx.rank(ind, top, bottom, where) and ctx.zscore(ind) across the universe, vectorised [FP 61]
- **B-52** rebalance attribute (month_start, week_start, every(n), daily, None); ctx.rebalancing; is_month_start, is_week_start, is_quarter_start, is_year_start [FP 61] [PY A6]
- **B-53** warmup class attribute: no orders before bar n; auto warm-up reported ("starts trading on …") [FP 61] [PY A10]
- **B-54** Risk attributes: max_drawdown (flatten and stop), max_daily_loss, max_position, max_gross; each breach logged as a risk event [FP 61]
- **B-55** ctx.store keeps small JSON across runs; instance attributes keep state
- **B-56** ctx.feature_matrix(formulas, lookback) and ctx.fit_every(n); sklearn allowed; fits use past bars only
- **B-57** Import allow-list: math, statistics, numpy, pandas, scipy.stats, scipy.optimize, sklearn, and the project files; others refused with the line and a request link [PY A7]
- **B-58** print and ctx.log(msg, level) captured per bar (date, symbol), 50,000-line cap with a truncation row [PY A8]
- **B-59** ctx.plot(name, value, chart="main" or "own"), ctx.mark(sym, label) on the price chart, ctx.table(name, row) as a sortable table [FP 29] [PY A9]
- **B-60** on_fill(ctx, fill) gets symbol, side, quantity, price, date and fee [PY A11]
- **B-61** Lifecycle hooks: on_end_of_day, on_warmup_done, on_risk_event, on_stop
- **B-62** params = {"fast": (10, 5, 50, 5)} declared in code appear in Build params and the Optimise grid; ctx.param kept [FP 9] [PY A12]
- **B-63** Per-strategy engine settings as class attributes (fill timing, costs, sizing); code wins over the card and a badge says so
- **B-64** Python orders feed the event engine directly, so LEAN parity applies to Python strategies [PY A13]
- **B-65** Budget: 500 symbols × 2,500 bars in under 20 s [PY A14]
- **B-66** Default mode for new strategies (simple or portfolio) in Customise
- **B-67** Refuse formulas or Python that read fundamentals for dates before 2021
- **B-68** Runtime guard: positive history index raises in backtest, same rule as the editor lint
- **B-69** Bar stepper: pause at a date and symbol, inspect self and ctx, step one bar, step to the next order or fill, run to a date, step back one bar (deterministic re-run) [FP 27] [PY B8]
- **B-70** Breakpoints with conditions (ctx.symbol == "AAPL" and ctx.date >= …) and hit counts; data breakpoints (first order; equity down 5% in a day) [FP 27, 65]
- **B-71** Variables (self, ctx, locals); arrays and DataFrames in a grid viewer; watch expressions with history; read-only debug console
- **B-72** Preview chart follows the paused bar, with position and pending orders drawn
- **B-73** Logpoints from the gutter ("log {expr} here") without editing the code
- **B-74** Gutter: run markers on lines that placed orders in the last preview (hover shows count and first 5 dates); change markers since last version
- **B-75** Inlay hints: parameter value next to ctx.param, last value next to ctx.value from the preview, computed type [FP 63]
- **B-76** CodeLens above on_bar ("Run on SPY · Run on universe · Debug from 2020-03-01"); above ctx.rule ("true on 34% of bars") [FP 64]
- **B-77** Time travel on a finished backtest: pick any bar, see a variable snapshot, arrow keys step back and forward; snapshots only for chosen date ranges [FP 27]
- **B-78** Profiler: time per function and per line, slowest 10 lines, flame graph, memory chart
- **B-79** Logs tab: virtual list (level, date, symbol, message, code line); filters for level, symbol, date, text, regex, case, whole word; click row jumps chart and editor; CSV export [FP 28]
- **B-80** Structured logs: ctx.log.info("entry", symbol=s, rsi=r) stored as key values, searchable [FP 28]
- **B-81** Plots tab: each ctx.plot series overlays the price or sits in its own pane on a shared time axis; toggle each; compare across two runs [FP 29] [PY B2]
- **B-82** Problems tab: static and runtime errors, click to jump to the line [PY B2]
- **B-83** Results tab: compact Backtest report (KPI strip with All, Long, Short; equity vs benchmark; trade list; trade histogram; Properties block); Open in Backtest without recompute [PY B2]
- **B-84** Three run levels: live preview (600 ms debounce, one symbol, 2 years), quick run ⌘↵ (universe, 5 years), full run ⌘⇧↵ (recorded in the ledger)
- **B-85** Progress in the status bar ("bar 1,240 / 2,516 · 18 symbols · 3.2 s") with partial equity streamed to Results
- **B-86** Cancel with Esc; time budget shown on every run
- **B-87** Runtime error: jump to the line, stack trace with user frames only, locals at the failing bar (symbol, date, self attributes)
- **B-88** Delta row after each quick run against the last run (return, Sharpe, trades)
- **B-89** Preview settings: symbol and window (default SPY, 2 years), auto-preview on or off; quick-run universe (top 50 by volume, 5 years)
- **B-90** Status bar: Ln:Col, error and warning counts, saved state, run state, last run time, "trial 14 on this idea" [FP 68]
- **B-91** Yellow banner on a result when the editor code differs from the run
- **B-92** Strategy is a project: main.py plus modules, README.md and params.json; file tree with create, rename, move, delete, duplicate and drag; limits 50 files and 200 KB per file [PY B3]
- **B-93** Any project can be marked a library and imported by others with a pinned version; "v3 available, review diff" badge; updates never change saved strategies silently [FP 58]
- **B-94** Zip import and export of a project
- **B-95** User snippets: save a selection with tab stops and a prefix trigger; shareable through Library
- **B-96** Examples in hover docs insert with one click
- **B-97** Gallery of 12 starters with a one-line description, last backtest on the default universe and "use as start" (trend 50/200, RSI(2), momentum top 10, dual momentum, pairs z-score, vol target, ATR breakout, turn of month, gap fade, sector rotation, ML ranking, risk parity)
- **B-98** Python starters: trend, mean reversion, momentum rotation, pairs, vol target, breakout, seasonality, ML score [PY B10]
- **B-99** Warn above 200 blocks, hard stop at 1,000; warn above 8 optimisable parameters
- **B-100** Customise: personal templates, parameter ranges per strategy, default sizing and costs per user, editor font and keymap
- **B-101** Monaco palette and the app palette merged into one list, grouped Editor, Run, View, Studio
- **B-102** Four authoring modes on one spec: blocks, formula, Python, plain English; the mode switch never loses work [FP 22]
- **B-103** Blocks and formula show generated Python side by side (read only); formula to Python is one way, original kept; hand edits that cannot be represented set a code-only badge [FP 22]
- **B-104** Plain English shows the interpreted rules as blocks before any run; ambiguous words highlighted ("oversold" = RSI(14) < 30); restated "what it does" paragraph; original prompt kept in version history [FP 23]
- **B-105** Any and All groups, nested to any depth [FP 24]
- **B-106** Condition kinds: cross above and below, for N bars, rising, falling, earnings filter, fundamentals, calendar, cross-sectional
- **B-107** Inline parameter editor with an optimisation range per parameter; plain-language summary line; colour by role; collapse, disable, comment, duplicate, copy as code; undo 50 steps [FP 9]
- **B-108** Red marker on incomplete blocks; detector for conditions that are always true or always false on your data
- **B-109** Click a condition block: the preview shows the bars where it fired (no full backtest) [FP 24]
- **B-110** Trading frequency: calendar (daily, weekly, monthly, on bar close) or threshold corridor (X% drift)
- **B-111** Formula inline value under each rule: true-rate and last true date
- **B-112** Function reference panel for formula mode
- **B-113** Named variables (fast = ema(close, 12)), user functions, comments; separate entry and exit formulas
- **B-114** Multi-timeframe calls causal only: weekly(x) built and tested; monthly open; hourly blocked by data [FP 42]
- **B-115** Composer-style tree blocks: if/else branches, filter by rank, weight by method, group; nest to any depth [FP 69]
- **B-116** Live true-rate on every condition block ("true on 31% of bars, last true 2026-01-28") [FP 69]
- **B-117** Complexity meter: counts parameters and rules and shows degrees of freedom while building [FP 25]
- **B-118** Find rules: grammar search of entries and exits with an out-of-sample split; every candidate counts in the trial ledger; results go to the Home databank grid [FP 70]
- **B-119** Checks card adds warm-up bars needed, data each rule uses, survivorship exposure
- **B-120** Exits library additions: profit-target ladder, exit on opposite signal, end-of-week exit; exits combinable and ordered
- **B-121** Sizing additions: equal weight, risk parity, max position and gross limits
- **B-122** Allocate: if/else on a condition (regime, trend); hold bonds or cash when off
- **B-123** Entry filters: fundamentals, calendar, cross-sectional, earnings-date filter
- **B-124** Indicator exit and scale in as exit-card rows
- **B-125** Stated regime claim marked "written after" when added after a drawdown
- **B-126** Version timeline: each version with its metrics (equity sparkline, Sharpe); name and tag versions ("validated", "live"); a live version is locked [FP 35]
- **B-127** Restore or branch from any version; restore creates a new version and deletes nothing [FP 35]
- **B-128** Experiments as branches: fork a strategy, change a rule, compare two branches on one chart, merge back [FP 35]
- **B-129** Blame: each line shows the version that last changed it
- **B-130** Local history: autosave snapshots kept 7 days, separate from versions
- **B-131** Share a read-only link or a fork link; pinned comment threads on a line
- **B-132** Single editing session per strategy with take-over; the second tab is read-only (no QuantConnect-style desync) [FP 66]
- **B-133** Notes (hypothesis, what was tried, decisions) exported with the certificate
- **B-134** Saved rule groups reusable as blocks; custom indicators by formula shared with Chart and Screener
- **B-135** Customise: default mode, default exits and sizing profile from Library, blocks palette order, block colours and compact or expanded view
- **B-136** Keyboard-first block insertion (type "/") and snap grid
- **B-137** Shared undo across views; Explain on any selection; convert to library block; one parameter table across all views
- **B-138** Python keys: F5 debug and Run, ⌘⇧↵ full run (quick run ⌘↵)
- **B-139** Python engine settings (fill timing, costs, sizing) shown as a badge when code overrides the card
- **B-140** Inline ⌘K edit on a selection, shown as a diff to accept or reject (AI is an owner decision)
- **B-141** Snippets palette (⌘⇧S) with user and team snippets
- **B-142** Formula editor with live compile (0.26 ms measured) and per-role findings
- **B-143** Blocks and formula convert both ways: rows of comparisons and crosses joined by and/or; other shapes stay formula (round-trip test)
- **B-144** Python mode: Monaco with ctx completion, hovers, snippets, inline markers from server checks and runtime errors; class Strategy with init, on_bar, on_fill
- **B-145** Python runs in a locked child process (-I, empty env, CPU and file limits, builtins allow-list, AST screen, no positive indexes)
- **B-146** Formula to Python one way: same trades as the formula (tested)
- **B-147** Plain English to rule by fixed phrase rules (MAs, crosses, RSI, highs and lows, ROC, weekly trend, volume, stops, targets, time stops); ignored words listed; review, then Use this rule
- **B-148** Allocate: "Trade only when" market rule (market = SPY close; everything closed on the bar it turns false); rotate = Rank by + max positions; Portfolio switch rule
- **B-149** Sizing: shares, cash, % equity, risk per trade, vol target (both engines), Kelly (capped), score weighting (both engines, parity tested)
- **B-150** Repaint check: signals on 50 history cuts of the preview name must equal full-history signals; shown under the preview
- **B-151** Preview chart: any symbol, last 2 development years, entries and exits marked, refreshes 300 ms after typing (server 0.37 s)
- **B-152** Undo and redo (⌘Z, ⇧⌘Z)
- **B-153** Immutable versions with a picker; field-by-field diff against any version
- **B-154** Checks card: compiles, no look-ahead, fires, trades on one name, exits, parameters used; jump links
- **B-155** My limits (walk-away conditions) and notes saved with the version
- **B-156** Command palette ⌘⇧P: lift a number to a parameter, add parameter, modes, templates, save, run (⌘K stays app search)
- **B-157** Parameter step and sweep size; step count shown against the sweep size
- **B-158** Drag to reorder block rows
- **B-159** Template start grid (20 templates)
- **B-160** Stated regime claim marked "written after" when added after a backtest
- **B-161** Trial chip opens the ledger drawer
- **B-162** Backtest results side by side in the version diff

---

## 3. Backtest

| Item | Spec |
|---|---|
| Purpose | Show what the strategy would have done, after costs, and how fragile that result is. |
| Who, when | Everyone, right after Build, and again after every change. |

Runs on the development period. The hold-out is not drawn. Default layout: **honest order** (fine print, drawdown, monthly table, distribution, rolling, equity last); the user can switch to equity first.

### 3.1 Hero and strip

| Output | Lead | View | Beats |
|---|---|---|---|
| Hero | "+142% vs SPY +81%, 6.0 years, Sharpe 1.12, worst drawdown −18%, 214 trades" | `lines`: net equity vs benchmark, drawdown shade, split line at the hold-out boundary | |
| Cost ladder | "Net CAGR 9.1% at 1×, 6.4% at 2×, 2.2% at 4× costs" | Three numbers beside the hero | Tactfolio shows three cost checks on its page only |
| My limits strip | "Passes 5 of 6; drawdown 22% of 25%: 12% room; passes from 9 of 12 start dates" | Checklist above the hero | LuxAlgo shows closest call for prop rules only |
| KPI strip | Sharpe, CAGR, max DD, trades, win rate, profit factor (user picks) | `KpiStrip` | |

### 3.2 Tabs and cards

| Tab | Card | Lead | View | Notes |
|---|---|---|---|---|
| Overview | Equity and drawdown | Net vs gross vs benchmark | Line + underwater; log toggle; gross and net overlay | |
| Overview | Start dates | "Positive from 41 of 50 start dates; CAGR 3% to 14%" | Dot strip: CAGR by start date, My limits pass marked | Missing from the old plan; LuxAlgo has the idea on prop cards |
| Overview | Survivorship delta | "Dead companies cost 2.6 points a year (18.1% vs 15.5%)" | Two lines: delisted kept vs survivors only | We hold the dead names; most tools do not |
| Overview | Fill check (superseded by K-30) | "Hourly fills cut return 11% (23 names with hourly data)" | Bar vs magnifier lines | Shown only where hourly exists; else "worst-case same-bar rule applied" |
| Trades | Trade list | Win rate, average win and loss, profit factor | Virtualised DataTable; all trades | Columns: entry, exit, side, size, P&L, %, bars, MAE, MFE, exit reason, costs, regime at entry, signal value; sets as tabs |
| Trades | Carried by | "Best 5 trades made 62% of profit; without them CAGR 3.1%" | Bars of P&L share; toggle "hide top 5" recomputes KPIs | |
| Trades | Trade shape | "Losers reached +1R in 31% of cases" | MAE/MFE scatter + P&L histogram + hold-time box plots in one card (three views) | Merges five old cards |
| Trades | Unfilled orders | "Unfilled limit entries returned +1.9% on average" | Two bars: filled, unfilled | Only when limit orders are used |
| Returns | Calendar | "Without the best 3 months: CAGR 4.2%" | Monthly heatmap + yearly bars vs benchmark; hide-best-months toggle | |
| Returns | Crisis strip | "−9% vs SPY −21% in 2022" | One strip with only the periods inside the data; table for the rest | |
| Risk | Drawdowns | "Longest drawdown 19 months (limit 12)" | Underwater + top 5 table (depth, length, recovery) | |
| Risk | Stability | "Sharpe 1.4 first third, 0.3 last third: decaying" | Rolling 6M and 12M Sharpe, vol, beta, correlation; thirds marked | Merges rolling and benchmark cards |
| Risk | Costs | "Costs ate 23% of gross return" | Gross vs net bars, turnover | |
| Risk | Capacity | "About $4M before impact; Sharpe halves at $18M" | One number, curve in Table view | Merges capacity and impact curve |
| Risk | Exposure | Time in market, gross and net | Area | Table view of Trade shape if no leverage |
| When | By regime | "84% of P&L in trend up, low vol" | Bars of return and Sharpe per regime; trades per regime beside each bar ("9 trades: too few") | Regimes: trend (200d), volatility terciles, drawdown state, HMM, custom |
| When | Conditions | "When VIX > 25, Sharpe −0.4" | Table of conditions | Library regimes |
| When | Seasonality | Month-of-year hit rate | Bars | |
| When | Timeline | Regime bands over price with equity under | Chart | |
| Names | Per-name results | "12 of 500 names made 55% of profit" | Virtualised table: trades, P&L, win rate, share, best and worst; click opens Chart | TrendSpider group table; Build Alpha top and worst tickers |
| Names | Holdings | Top contributors | Treemap; weights over time | |
| Paths | Trade Monte Carlo | "95% of reshuffled paths stay above −27% drawdown" | `fan`: median, 25-75, 5-95; Resample, Shuffle, block bootstrap, trade skip; 250/1,000/2,500 runs; caveat "bands are not limits" | LuxAlgo has two methods |
| Paths | Ruin | "P(drawdown > 30%) = 4%" | Table of thresholds | |
| Paths | Rule check | Pass share for user rules (target, daily loss, max drawdown, min days) across start dates | Ring + table | Replaces the prop page |
| Paths | Streaks | 95th percentile losing streak | Bars | |

Replay is a hero action (`R`): equity draws, trades appear on price, holdings fly in and out; still frame under Reduce motion.

**Interactions**: click a trade opens Chart at entry−20 to exit+20 with stops; tick trades and press `C` for aligned price paths; click a name row opens Chart; `[` `]` change tab; `T` Trades; `R` Replay; toggle gross and net; compare to previous run (`RunCompare`).

**Customisation**: hero kind, KPIs, tab order, card show, hide, duplicate, resize, view switch; range, log, one colour, mark a level; report order (honest, equity first, custom); custom metric by formula; custom crisis periods; custom regimes (Library).

**States**

| State | Shows |
|---|---|
| Empty | "Pick a strategy" and the last three strategies |
| Loading | Stage list with counts ("Loading 500 names 312 / 500"), cancel |
| Error | Job failed with the stage and reason; settings preserved |
| Skipped | A run with 0 entries is refused: "0 entries: rule never true on this universe", with the three most likely causes; fewer than 30 trades marks every statistic "few trades" |
| Stale | "Settings changed since this run" and a Run button |
| Data stale | Freshness pill amber or red; backtest still runs on the history it has and says so |

**Reuses**: `screener/test/TearSheet.tsx` (monthly heatmap, return histogram, underwater, drawdown story), `charts/Backtest.tsx`, `screener/Story.tsx` (replay, sorting field), `kit/DataTable.tsx`, `kit/KpiStrip.tsx`, `modules/research/outputs/*`, `RunCompare.tsx`, `services/screener_v2/core/backtest.py` (cross-check), `core/metrics.py` (one canonical, merged first).

**Acceptance**

- K-1 Hero numbers equal `metrics.py` outputs within 1e-9 on the SMA-cross fixture.
- K-2 Same run twice: identical trades and equity (hash equal).
- K-3 Fills at next open by default; a test with a gap through a stop fills at the open, not the stop.
- K-4 With zero costs every output shows a "costs off" pill.
- K-5 Start-date card reproduces a hand-computed result for 3 start dates.
- K-6 Survivorship delta changes the equity line on a fixture with one delisted name and shows the same delisting rule in the limits popover.
- K-7 Zero-entry run returns a refusal with a reason, not an empty report (API test and screenshot).
- K-8 Trade list with 10,000 rows scrolls with median frame ≤ 16.7 ms (`tablebench.mjs` pattern).
- K-9 500 names, 10 years: under 5 s cold (measured, not promised until the phase 0 spike).
- K-10 Hold-out dates do not appear in any Backtest series (test inspects the payload).
- K-11 Screenshot at 1440 and 1024, dark and light, each tab.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **K-12** Run header: strategy, version, range, capital, data version, execution preset, seed, duration, engine version; Reproduce and Duplicate and edit buttons
- **K-13** Immutable run record: code hash, params, data version, execution model, engine version, seed, timing; a re-run gives the same numbers [FP 1]
- **K-14** Stat tiles: pick any 8 of 60+ stats; each has a definition on hover (formula and LEAN reference) [FP 30]
- **K-15** Add PSR, expectancy, fees total, volume traded and capacity to the stat strip [FP 30]
- **K-16** All, Long and Short toggles on every metric
- **K-17** Date range brush recomputes every stat for the selected range [FP 30]
- **K-18** Benchmark overlay: log or linear, % or $; regime shading; trade markers toggle
- **K-19** Rolling 6, 12 and 36-month windows for return, Sharpe, volatility and beta
- **K-20** Return distribution with a normal overlay; best and worst day lists
- **K-21** VaR and CVaR at 95 and 99, tail ratio, Ulcer index, beta and correlation to benchmark, leverage, concentration
- **K-22** Stress scenarios inside the data (2018 Q4, 2020, 2022)
- **K-23** Trades: 100,000+ rows; column toggles; filters (winners, losers, symbol, tag, date, size); export CSV and Parquet [FP 31]
- **K-24** Per-trade drill: chart with entry and exit bars, rule values at entry, MAE and MFE, the code line that fired (jump to code) [FP 31]
- **K-25** Trade analytics: P&L by hour, weekday, month, regime and symbol; streaks; expectancy by tag
- **K-26** What-if exit overlay (stop or target change), flagged as approximate
- **K-27** Costs tab: gross vs net, commission, slippage, borrow and financing bars; break-even cost level
- **K-28** Cost sensitivity slider 0× to 3×, recomputed from stored fills [FP 32]
- **K-29** Execution model panel with presets (US retail, crypto, futures) and a custom Python cost hook: fill, slippage (fixed bps, volume share, spread), commission, borrow, financing, margin, settlement, lot size, tick rounding, session calendar [FP 13]
- **K-30** Intrabar fill fidelity levels (fast, standard, detailed, tick) with the ambiguous-bar count shown [FP 14]
- **K-31** Trade Monte Carlo methods: shuffle, resample, block bootstrap, trade skip; 250, 1,000 or 2,500 runs; caveat "bands are not limits" [FP 5]
- **K-32** Confidence-level table at 80, 90, 95 and 99 percent for the trade Monte Carlo [FP 5]
- **K-33** Warnings card: look-ahead suspicion, fewer than 30 trades, top trade above 20% of profit, parameter at range edge, costs above 50% of gross, survivorship note, data gaps [FP 34]
- **K-34** Run-ups table, mirror of the drawdown table (top 10: start, trough, recovery, length) [FP 71]
- **K-35** Capital efficiency: cash idle %, gross and net exposure over time, margin used, buying-power headroom [FP 71]
- **K-36** Benchmarks: any symbol, a 60/40 blend, another strategy; alpha, beta, information ratio and tracking error against each
- **K-37** Report export: PDF or HTML tear sheet in a fixed order set in Library, with the Properties block
- **K-38** Properties list: every setting used and the data version
- **K-39** Tabs Orders, Positions and Exposure, Logs and Plots, Warnings, Code and Settings
- **K-40** Customise: KPI set and order (shared with Backtest), tab order, default benchmark, report template, number formats, colour-blind palette
- **K-41** Options-specific output: fill at mid with slippage per contract, Greeks, assignment events
- **K-42** Unfilled limit orders card (needs limit orders from Build B-12)
- **K-43** Hero: net return vs benchmark, drawdown shading, hold-out boundary line
- **K-44** Cost ladder 1×, 2×, 4× beside the hero
- **K-45** Tabs Overview, Trades, Returns, Risk, When, Names, Paths
- **K-46** Timeline: regime strip under the equity curve
- **K-47** Conditions table: market trend, volatility, drawdown known the night before
- **K-48** Holdings: P&L treemap by name and names held over time
- **K-49** Rule check: target, daily loss, max drawdown and min days from every monthly start (ring and table)
- **K-50** Start-date card: CAGR by start date with the My limits pass marked
- **K-51** Survivorship delta: delisted names kept vs survivors only
- **K-52** Capacity card: one number, impact curve in Table view
- **K-53** Seasonality: month-of-year hit rate
- **K-54** Names: per-name results and top contributors
- **K-55** Ruin table: P(drawdown above each threshold)
- **K-56** Losing streaks: 95th percentile
- **K-57** When tab: return and Sharpe per regime, trades per regime beside each bar

---

## 4. Optimise

| Item | Spec |
|---|---|
| Purpose | Find a stable range of settings, not the single best cell. |
| Who, when | After Backtest, when parameters matter. |

**Inputs**

| Group | Inputs |
|---|---|
| Search | Grid, random, Bayesian (Optuna TPE); budget (cells, seconds); seed |
| Parameters | Any lifted parameter, range, step, log scale, link two parameters (e.g. fast < slow) |
| Objective | Sharpe, CAGR / drawdown, profit factor, Ulcer, custom formula; multi-objective weights |
| Constraints | Min trades, max drawdown, min pass share across start dates |
| Neighbourhood | Radius for the stability score (default 1 step) |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Hero | "Plateau at fast 40-60, slow 180-220: Sharpe 0.9-1.1" | `heatmap` of two chosen parameters, plateau outlined, others fixed at plateau centre | Single best cell views (backtesting.py heatmap) |
| Stability | "71% of neighbours within 20% of best" | `gauge` + neighbourhood histogram | |
| Surface | Shape | Contour (default), 3D rotate (lazy-loaded, off by default) | |
| Top sets | Best 20 by objective | Table: params, Sharpe, CAGR, DD, trades, stability; click backtests that set | |
| Trade-off | Pareto front | Scatter return vs drawdown, front highlighted | |
| Importance | "slow matters 3× more than fast" | Bars (fANOVA) | |
| Spread | Outcomes across the plateau | Overlaid equity lines, best bold | |
| Trial cost | "This sweep added 400 raw, 38 effective trials" | Line under the hero | Nobody found shows this |

**Interactions**: click a heatmap cell to backtest it; drag-select a region to set the plateau; pick any two parameters on the axes; `C` compare two sets; "Send plateau centre to Build" creates a new version (adds to the ledger).

**Customisation**: colour scale, objective formula, which parameter pair is default, table columns; saved search profiles.

**States**

| State | Shows |
|---|---|
| Empty | "No parameters yet: lift a number in Build" |
| Loading | Live cell counter ("612 / 1,000"), partial heatmap fills as cells finish (SSE), cancel |
| Error | Per-cell failures counted; run completes with the failures listed |
| Skipped | Cells with fewer trades than the minimum are greyed, counted, and named "too few trades" |

**Reuses**: `charts/Heatmap.tsx`, `charts/XYPlot.tsx`, `modules/research/outputs/plots.tsx` (specification curve), `kit/DataTable.tsx`, `services/screener_v2/core/validation.py` (signal cache pattern), Optuna (MIT).

**Acceptance**

- O-1 A planted spike strategy (one lucky cell) reports "spike only", not a plateau; a planted plateau strategy reports a plateau (backend tests).
- O-2 1,000-cell sweep on a single symbol under 10 s (vector engine).
- O-3 The sweep adds trials to the ledger equal to cells run; effective count is smaller when cells are neighbours.
- O-4 Cancel stops compute within 2 s and keeps finished cells.
- O-5 Screenshot of Map, Surface (still), Top sets.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **O-6** Setup sheet: parameter checkbox, min, max, step, scale (linear or log), type, "link to" (slow > fast + 5), live count of combinations with runtime and cost estimate
- **O-7** Objective builder: several objectives from any stat or expression (sharpe - 0.5 × max_dd), direction, weights; penalty rules (fewer than 100 trades is invalid); Pareto for 2 or 3 [FP 10]
- **O-8** Search methods: grid, random, Sobol, Bayesian (default above 3 parameters), genetic (NSGA-II), CMA-ES, successive halving; plain advice in the picker [FP 10]
- **O-9** No cap on the number of optimised parameters (checked above 3) [FP 10]
- **O-10** Budget: max runs, max minutes, early stop after N runs with no improvement; cost and time estimate before launch
- **O-11** Data split in Optimise: in-sample, hold-out or walk-forward; out-of-sample shown beside each row; hold-out hidden from the objective
- **O-12** Results table: every stat, in-sample and out-of-sample columns, rank, stability score, robust flag; sort, filter, column picker, CSV
- **O-13** Heat map for any two parameters with a chosen stat; click a cell to open its run; contour smoothing toggle; overlay flags peaks without plateaus
- **O-14** Pick-plateau tool: drag-select a region; returns the median parameter set and spread; runs that set [FP 11]
- **O-15** Parallel coordinates view for more than 3 parameters [FP 72]
- **O-16** Scatter of stat A vs stat B coloured by parameter; histogram of outcomes across all trials (what a random pick gives)
- **O-17** Controls: pause, resume, cancel, clone with changed ranges, zoom in on a selection, save sweep as template, pin best
- **O-18** Top sets: click a row to backtest that set
- **O-19** Budget awareness: deflated-Sharpe hurdle shown before running, rising as the grid grows
- **O-20** Warning when the best parameters sit at a range edge; plateau recommended over peak
- **O-21** Cache: identical code, parameters and data are never rerun
- **O-22** Custom objective in Python: def objective(result) -> float
- **O-23** Use all local cores, with an estimated time before the run starts
- **O-24** Walk-forward optimisation entry point in Optimise: each window re-optimises; out-of-sample periods stitched [FP 72]
- **O-25** Custom objective written as a formula over metrics (sharpe - 0.5 × max_dd), available on every page [FP 72]
- **O-26** Constraints: min trades, max drawdown; excluded cells counted [FP 10]
- **O-27** Stability score from the neighbourhood (gauge and histogram); plateau vs spike call [FP 11]
- **O-28** Send the plateau centre to Build as a new version (adds to the ledger)
- **O-29** Customise: default method, objective, split, max workers, auto-run Validate on the top 5
- **O-30** Trial counter feeding deflated Sharpe in Validate, shown on the page
- **O-31** 3D surface (Plotly), off by default
- **O-32** Log-scale parameters
- **O-33** Time budget on a sweep
- **O-34** Spread of plateau equity curves, best one bold
- **O-35** Parameter map fills in as cells finish (every 5th cell)
- **O-36** Pareto front view
- **O-37** Parameter importance bars
- **O-38** Top 20 sets table
- **O-39** Trial cost under the hero: "this sweep added N raw, M effective trials"
- **O-40** Link rule between two parameters (fast < slow)

---

## 5. Validate

| Item | Spec |
|---|---|
| Purpose | Decide whether the edge is real, with one graded verdict and the tests behind it. |
| Who, when | After Backtest and Optimise, before Paper. Also when an agent finishes a search. |

One page, one run. The run executes all selected tests on the user's compiled strategy, shows tiles flipping as each finishes (SSE), and ends with the verdict. Each test can be re-run alone.

**Inputs**

| Group | Inputs |
|---|---|
| Profile | Validation profile from Library (default, strict, quick); tests on or off; weights; pass thresholds |
| Walk-forward | Anchored or rolling; window and step; purge, embargo; re-optimise on or off |
| Robustness | Paths per test (100 / 500 / 2,000); noise level; shift range; delay bars (1, 2); cost multiples (2×, 3×); volume cap; related symbols; skip share |
| Luck | Trials: the ledger (raw, effective) with an override; CPCV groups and test groups |
| Shocks | Gap down %, volatility multiple and duration, correlation to 1 |
| Seed | Fixed per run, shown |

**Outputs (tabs)**

| Tab | Output | Lead | View | Beats |
|---|---|---|---|---|
| Verdict | Grade | "B: real edge, fragile to costs; break-even at 2.1× costs" | `grade` with reason; score table: test, weight, result, link | QuantProof Edge Score has no reasons shown in the text read |
| Verdict | Next test | "Run: delay 2 bars (not run)" | One line | Canli `fix_next` |
| Verdict | What would change it | "Needs 40 more trades"; "costs break it at 2.1×" | List; no parameter tuning suggestions; any suggestion that edits parameters opens a new version and adds to the ledger | |
| Verdict | Power | "Detects a Sharpe 0.5 edge 80% of the time at 212 trades; flags 4% of shuffled strategies" | Table and one line | No product found shows it |
| Verdict | My limits and start dates | Same strip as Backtest | | |
| Walk-forward | Stitched OOS | "Walk-forward efficiency 68%" | `lines` with window bands labelled by chosen params | |
| Walk-forward | Windows | "11 of 14 windows profitable" | Table: IS, OOS dates, params, Sharpe, return, WFE | |
| Walk-forward | Matrix | "9 of 25 (re-opt × OOS) cells pass" | Heatmap | SQX walk-forward matrix |
| Walk-forward | Drift | "fast moved 20 → 65: unstable" | Line of params per window | |
| Robustness | Tiles | "Passes 7 of 9" | `tiles`: pass, fail, skipped with reason and threshold | |
| Robustness | Vs random | "Beats 96% of 1,000 random strategies with the same trade count, holding time, stop and target" | Histogram, ours marked | Random entries with the same stop and target remove win-rate artefacts |
| Robustness | Price paths | Noise, permutation (MCPT), shifted starts | Fan + width; histogram; bars per shift | Build Alpha set, on the user's strategy |
| Robustness | Execution | Delay 1 and 2 bars, cost 2× and 3× (break-even marked), volume cap | Lines and bars | |
| Robustness | Parameters | Share of nearby settings profitable | Heatmap from Optimise neighbourhood | |
| Robustness | Others | Same rule on related symbols and sector peers | Small multiples | |
| Robustness | Shocks | "Gap down 10%: drawdown −31%" | Table | Merges stress scenarios |
| Luck | Luck lottery | "After 1,840 tries (212 effective), noise alone reaches Sharpe 1.9; yours is 1.4" | Histogram of best-of-N noise Sharpe, ours marked | Nobody found leads with it |
| Luck | Deflated Sharpe | "DSR 0.62 after 212 effective trials" | `gauge` | Stochastly, Canli numbers |
| Luck | PBO | "Probability of overfitting 71%" | Logit histogram; IS-rank vs OOS-rank scatter | |
| Luck | CPCV | OOS Sharpe across paths | Violin + path equities | |
| Luck | Track record | "Needs 3.4 years live at 95%" | One number | |
| Luck | Haircut Sharpe | Before and after | Bars | |
| Hold-out | Sealed hold-out | "Hold-out Sharpe 0.7 vs 1.1 in-sample; looked at 2 times (human 1, agent 1)" | Paired bars + look log | Look log by actor |
| Certificate | Certificate | Grade, hash, "reproduced 2026-11-15 ✓" | Report view; server re-runs backtest and every test from spec, data version, seed and compares hashes | Canli signs a statistic; this re-runs everything |
| Certificate | One-page PDF and share link | Hero, equity, verdict table, limits, rules, hash | PDF + `/share/<token>` | |

**Interactions**: click a tile to jump to its card; "Run again with more paths" on any test; edit weights live and see the grade recompute from stored results (no re-run); open hold-out requires a click and logs a look (humans: unlimited but logged; agents: budget of 3 per strategy, more needs a human click); Certify button greyed until all required tests have run on the current version.

**Customisation**: validation profiles (tests, weights, thresholds, default seed); tile order; report order for PDF; custom tests as formulas over the equity or trades (later).

**States**

| State | Shows |
|---|---|
| Empty | "No run on this version" and Run (all) or Run quick |
| Loading | Tiles flip live with counts ("Noise 312 / 500"), cancel one or all |
| Error | A failed test shows "failed: reason", others continue; verdict says "incomplete" |
| Skipped | Each skipped test: "skipped: only 18 trades" or "no related symbols held"; verdict lists skips and caps the grade at the letter allowed without them |
| Stale | New version or changed settings: verdict marked stale, never shown as current |

**Reuses**: `modules/research/outputs/robustness.tsx` (tile pattern), `research_v2/core/holdout.py`, `placebo.py`, `robustness.py`, `specification.py`, `ml_v2/core/cpcv.py` and `validation.py`, `skfolio` CPCV as test oracle, `screener_v2/core/exports.py` and `shares.py` (PDF and share), `charts/Distribution.tsx`, `charts/Forest.tsx`, `kit/DataTable.tsx`.

**Acceptance**

- V-1 A planted overfit strategy (best of 2,000 random rules) receives D or F with "luck" named as the reason; a known robust strategy (long-run trend on a broad index fixture) receives A, B or C.
- V-2 Verdict is computed on the server from stored test results; posting a modified result from the browser changes nothing (API test).
- V-3 Re-running Certificate on the same version reproduces the hash.
- V-4 Opening the hold-out writes a look with actor, time and the version; the count in the UI equals the log.
- V-5 An agent token cannot open the hold-out a fourth time without a human approval event (API test).
- V-6 Power card: on a fixture with a planted Sharpe 0.5 signal the detection rate printed is within 5 points of a direct simulation.
- V-7 Editing weights recomputes the grade without a job.
- V-8 A strategy with 12 trades gets "skipped" on walk-forward and the grade cap is shown.
- V-9 Tiles flip one by one during a run (screenshot sequence at 3 timestamps).
- V-10 Quick profile finishes in under 10 s on a single-symbol 10-year daily strategy.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **V-11** Scorecard: each test Pass, Warn or Fail with threshold, actual number, one-line reason and link; weakest test highlighted; thresholds editable per user or team as a validation policy [FP 3]
- **V-12** Profiles Quick (under 10 s), Standard and Full, each a saved list of tests and pass bars in Library; one-click run and a custom checklist
- **V-13** Walk-forward anchored or rolling, with purge and re-optimise on or off [FP 4]
- **V-14** Stitched out-of-sample periods from walk-forward; efficiency; windows table [FP 72]
- **V-15** Randomised out-of-sample blocks
- **V-16** k-fold by time blocks with purge and embargo
- **V-17** Walk-forward matrix: 3D surface and the "k of n cells pass" rule [FP 4]
- **V-18** White's reality check or SPA test
- **V-19** Price-path robustness: noise, vs random, vs shifted starts, vs other names, permutation (MCPT) [FP 6]
- **V-20** Noise test shows band width, not only pass or fail [FP 6]
- **V-21** Synthetic price paths: block bootstrap and GARCH
- **V-22** Trade-list Monte Carlo in Validate: reshuffle, resample, random trade skip, randomised exits, variance test; confidence table 80, 90, 95, 99 [FP 5]
- **V-23** Delayed entry at 1, 2 and 5 bars
- **V-24** Cost stress 1× to 3× with the break-even marked
- **V-25** Liquidity cap as a share of volume
- **V-26** Partial fills, spread widening and missed fills
- **V-27** Parameter permutation grid around the chosen values; % change randomisation with probability and max change; sensitivity plot; Taguchi; plateau width
- **V-28** Regime tests: performance by regime, worst regime, rolling consistency, year-by-year table [FP 73]
- **V-29** Pass bars must hold in each regime, not only on average [FP 73]
- **V-30** Sanity: look-ahead re-run on truncated data and compare signals; single-trade dependence; data-leak scan [FP 8]
- **V-31** Workflow chaining: run a chain on every strategy in a folder; auto-dismiss on fail; table of survivors
- **V-32** Each test shows a chart, a table, a two-line "how to read this", simulation count, seed and runtime; re-run with more simulations; export
- **V-33** Verdict is bound to the strategy version; a code change marks it stale and says so
- **V-34** Same suite on a portfolio, including correlation stability
- **V-35** Live gate: a deployment can require a minimum grade; override needs a typed reason in the audit log
- **V-36** Simulations default 1,000, up to 100,000; fixed or random seed; compute budget
- **V-37** Skip X% of trades test; per-trade slippage randomisation (from SQX)
- **V-38** Higher-precision check: re-run on a different fill model
- **V-39** Out-of-sample on unseen symbols: train on half the universe, test on the other half [FP 73]
- **V-40** Customise: test list per profile, pass thresholds, which tests block the verdict
- **V-41** Hold-out enforced at project or team level, not only per strategy [FP 12]
- **V-42** Deflated Sharpe on the effective trial count, carried from Optimise [FP 7]
- **V-43** Luck tests: luck lottery, deflated Sharpe, PBO with logit histogram, Harvey-Liu haircut, minimum track record, power card, CPCV violin [FP 7]
- **V-44** One verdict with a reason chain
- **V-45** One-page PDF and /share/<token> link from the run header
- **V-46** Robustness tiles: pass, fail, skipped, each with reason and threshold
- **V-47** Vs random: histogram of random strategies with the same trade count, holding time, stop and target; ours marked
- **V-48** Shocks: gap down 10%, volatility ×3, everything moves with the market (labelled synthetic)
- **V-49** Walk-forward efficiency, windows table with chosen parameters, drift line
- **V-50** Verdict: reason, cap at C on few trades, next test, what would change it (no tuning advice)

---

## 6. Portfolio

| Item | Spec |
|---|---|
| Purpose | Combine several strategies and see whether the mix is better than the best one. |
| Who, when | After two or more strategies pass Validate; also for meta strategies. |

**Inputs**

| Group | Inputs |
|---|---|
| Members | Up to 12 strategies (versions), or "all in this folder" |
| Allocation | Equal, inverse vol, risk parity, max Sharpe, HRP, fixed weights; rebalance; cap per strategy |
| Meta rule | If condition then strategy A else B; rotate to the strongest by trailing N months; weight by regime |
| Period | Shared inputs; overlap only |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Hero | "Three together: Sharpe 1.4 vs best single 1.1, drawdown −12% vs −18%" | `lines`: combined vs each | StrategyQuant Portfolio Master (Pro caps strategies) |
| Correlation | "Lowest pair: 0.12" | Heatmap + dendrogram | |
| Allocation | Weights by method | Stacked bars over time | |
| Marginal | "B adds the most" | Bars | |
| Overlap | Shared trades and names | Matrix | |
| Meta result | "Regime switch beat both parts in 2 of 3 crises" | Equity + switch markers | Composer symphony logic, with validation |
| Combined verdict | Grade of the combination | `grade` chip linking to Validate with the combined strategy as a member list | |

**Interactions**: drag to reorder; tick strategies in Home then "Combine"; `C` compare; export weights as CSV.

**Customisation**: allocation method defaults, correlation window, hero kind.

**States**: Empty "Add two strategies"; Loading stages per member; Error names the failing member and keeps the rest; Skipped "no common period".

**Reuses**: `ml_v2/core/allocation.py`, `portfolio_v2/`, `charts/Heatmap.tsx`, `charts/Dendrogram.tsx`, `kit/Compare.tsx`.

**Acceptance**

- P-1 Equal-weight combination of two fixtures equals a hand-computed series.
- P-2 A meta rule "SPY above 200d: stocks, else bonds" backtests with the switch on the next open; no look-ahead (planted test).
- P-3 Combined strategy can be sent to Validate and returns a verdict.
- P-4 Screenshot at 1440 and 1024.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **P-5** Sleeves carry weight, capital, start date, enable toggle and scaling (vol target, leverage cap); a sleeve can be a portfolio
- **P-6** More allocation methods: minimum variance, max diversification, mean-variance with shrinkage, capped Kelly, momentum of members, drawdown throttle, custom Python function [FP 36]
- **P-7** Rebalance on a calendar or a threshold corridor, with a minimum trade size to cut churn [FP 36]
- **P-8** Stacked-area weights over time with the effective number of bets
- **P-9** Diversification ratio, drawdown overlap, capacity by sleeve, turnover, cost drag, net exposure by symbol across sleeves [FP 37]
- **P-10** Correlation over the full period and over a rolling window
- **P-11** Constraints: max weight per member, per symbol and per sector; gross and net limits; leverage; cash reserve; minimum member count; ban list; max correlation between members [FP 36]
- **P-12** Sleeve drop-out test: remove each member and show the effect [FP 37]
- **P-13** Correlation shock: all members at correlation 0.8
- **P-14** Crisis stress: the combined portfolio in each crisis window from 2015 [FP 74]
- **P-15** Overlap guard: warns when two members hold the same symbol in opposite directions or share more than 70% of signals
- **P-16** Walk-forward allocation test: out-of-sample weights shown against full-sample weights [FP 38]
- **P-17** Netting: opposite trades on one symbol across members cancel before execution [FP 74]
- **P-18** Efficient frontier of the members with the chosen mix marked [FP 74]
- **P-19** Rebalance costs counted when weights shift
- **P-20** Deploy as one book, paper first, with netted orders and per-member P&L attribution
- **P-21** Alpha, beta, tracking error and information ratio against the chosen benchmark
- **P-22** Multi-currency account with a base currency and FX on cash
- **P-23** Portfolio view during a run: exposure by symbol, sector and asset class, cash, margin, beta to benchmark
- **P-24** Meta rule: weight by regime; rotate to the strongest by trailing N months
- **P-25** Customise: default method, rebalance frequency, estimation window, constraints
- **P-26** Cluster tree of members
- **P-27** Rotation to the top N by trailing 3-month return
- **P-28** Weights re-estimated quarterly on the trailing year (no look-ahead, tested)

---

## 7. Live

| Item | Spec |
|---|---|
| Purpose | Say what to do today, keep a frozen strategy on paper, and tell when it stops working. |
| Who, when | Daily users, mornings and after the close. **Phone-first layout** (this page is the one people open on a phone). |

**Inputs**

| Group | Inputs |
|---|---|
| Source | A strategy version (draft allowed for Today; Forward needs a frozen version from Validate with grade ≥ the user's gate) |
| Freeze | Start date, capital, limits (position, exposure, daily loss), kill switch |
| Alerts | Channel (email, push, Telegram, webhook JSON), events (entry, exit, near trigger, drift, data stale), quiet hours, quota shown |
| Import | CSV of real trades or a broker export column map |
| Schedule | Runs after the daily data load |

**Outputs (tabs)**

| Tab | Output | Lead | View | Beats |
|---|---|---|---|---|
| Today | Signals | "7 entries, 3 exits as of 2026-07-06" | Table: symbol, action, value, distance to trigger, size; tick to Compare or add to Paper | |
| Today | Near triggers | Names within x% of firing | Table | |
| Today | Map | Universe as dots, firing ones lit | Sorting field | |
| Today | Orders sheet | "Buy 41 AAPL at next open; stop 8%" | Copyable text and CSV | |
| Forward | Forward equity | "+4.1% since freeze vs expectation +3.2% ± 5.0%" | `lines` with the backtest Monte Carlo band | |
| Forward | Drift | "Live Sharpe left the 95% band on 2026-10-02" | Marker + alert | |
| Forward | Decay clock | "At 3 months a dead edge is caught 18% of the time; 80% power at 2.6 years" | Table and one line | halleytech idea in FEATURES st10 |
| Ledger | Fills | Daily fills, same fill model and costs | Table | Tradetron "Live Offline" |
| Health | Cost leak | "Paper costs 3 bp above backtest" | Daily line | |
| Health | Signal health | Rank IC vs backtest mean | Line (ranking strategies) | |
| Health | Drawdown odds | "A drawdown this deep: 1 in 14 at the backtest Sharpe, 1 in 3 at half" | Two numbers | |
| Health | Shadow book | Stopped strategy keeps running for 12 months | Equity | |
| Reconcile | Backtest vs paper vs real | "Same trades 91%; average fill 4 bp worse; residue small, grows with volatility" | Four-question table + trade diff list | Tradetron describes it as a manual how-to |
| Reconcile | Real trades on chart | "You skipped 6 signals and took 4 it never gave" | Chart overlay | TradeZella, Tradervue import trades, but do not compare to a strategy |
| Alerts | Rules and feed | Last 30 alerts, hit rate | List | `screener/monitor/*` |
| Digest | Daily email or push | One message: signals, positions, equity, drift | Message preview | Tactfolio daily email |

**Interactions**: `F` freeze; kill switch is one confirm; swipe between tabs on phone; tap a signal for QuickLook; test alert sends a sample; a new version cannot inherit a Paper record (starts a new segment).

**Customisation**: digest contents and time, alert channels per strategy, which Health cards show, units.

**States**

| State | Shows |
|---|---|
| Empty | "Freeze a validated strategy to start paper" and Today available for any draft |
| Loading | Step progress after the daily load |
| Error | Step failed: last good state kept, reason, retry |
| Skipped | Data stale (red): Today and Forward say "not updated: data to 2026-07-06" and do not compute; no zero-return days written |

**Reuses**: `screener_v2/core/scheduler.py`, `alerts.py`, `notify.py`, `snapshots.py`, `screener/monitor/*`, `screener/Story.tsx` (sorting field), `kit/QuickLook.tsx`, `kit/DataTable.tsx`, old Studio paper gates (idea only).

**Acceptance**

- L-1 With data stale beyond 10 days the daily step refuses and writes nothing (test).
- L-2 After a simulated new bar, the step produces fills at next open with the same costs as the backtest (test against vector engine).
- L-3 Freezing a version stores spec, data version and seed; the Forward curve before the freeze date is never drawn.
- L-4 A drift alert fires when live equity leaves the 95% band in a planted series and appears in the feed and in the digest.
- L-5 Reconcile on an imported CSV matches hand-built counts on a 10-trade fixture.
- L-6 A strategy with a newer version starts a new segment; the old record stays under the old version.
- L-7 Alert quota and channel verification states visible; a failed webhook shows status and retry.
- L-8 Screenshot at 390 px (phone, Today and Forward) and 1440.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **L-9** Forward equity with the backtest Monte Carlo band (expectation ± band) and drift [FP 15]
- **L-10** Divergence monitor: live vs backtest on the same period; missing and extra signals; fill slippage; threshold alerts [FP 15]
- **L-11** Shadow book: the frozen version keeps running on fresh data next to paper; per-trade explanation of drift (slippage, cost leak, missed signals) [FP 75]
- **L-12** Cost leak: paper costs vs backtest, daily line
- **L-13** Signal health: signal rate vs backtest, rule value distribution vs history, rank IC vs backtest mean
- **L-14** Decay clock: time to catch a dead edge and time to 80% power; F key freezes
- **L-15** Deployment wizard: version, mode (signals, paper, live), account, capital and size scale, risk limits, schedule, alert rules, diff vs backtest assumptions, typed confirmation; saved as a deployment record
- **L-16** Signals-only mode: each signal (symbol, action, size, reason) to the feed, email, push or webhook; "signal valid until"; "I took it" or "skipped" tracking [FP 20]
- **L-17** Paper records slippage observed vs the model and latency
- **L-18** Layout: deployments list left, today dashboard centre, orders and alerts right
- **L-19** Dashboard: positions (qty, avg, mark, P&L, % of book), open orders, fills, P&L today, week and total with the backtest band, exposure, margin, heartbeat, last data tick, next scheduled event, log tail, strategy variables
- **L-20** Kill switches: pause entries, flatten all, halt strategy, halt account (one confirm); automatic triggers for max daily loss, max drawdown, stale data, broker mismatch, with confirmation levels [FP 17]
- **L-21** Crash recovery: persisted strategy state; restart reconciles positions; a mismatch pauses and asks [FP 18]
- **L-22** Reconcile: four-question table (same trades %, fill difference, residue, volatility) and real trades on the chart (skipped and taken signals)
- **L-23** Promotion gates: Backtest, Validate, Paper, small live, Live; editable checklist (min trades, min paper days, max divergence); Forward needs a version graded at or above the gate [FP 16]
- **L-24** Order CSV for manual brokers (orders sheet)
- **L-25** Manual order ticket with pre-trade checks; full order lifecycle with reject reasons
- **L-26** Broker adapters (IB, Alpaca, Tradier, Schwab, Tastytrade, crypto): connection status, permissions, balances, reconnect and disconnect events [FP 19]
- **L-27** Alert rule builder: drawdown beyond limit, order rejected, data lag, no signal for 3 days, heartbeat lost, drift beyond band, signal, fill [FP 21]
- **L-28** Webhook templating ({{symbol}} {{action}} {{qty}}), channel routing per severity, quiet hours, escalation (unacknowledged for 10 min goes to SMS), acknowledgement history [FP 21]
- **L-29** Channels: email, push, Telegram, webhook JSON; quota per alert shown
- **L-30** Strategy-defined alerts: ctx.alert(text, level, channels)
- **L-31** Daily digest after the data load (email or push): signals, positions, equity, drift
- **L-32** Runs after the daily data load
- **L-33** Phone first: today actions on one screen; swipe between tabs; tap a signal for QuickLook
- **L-34** Live run history: each live day as a result page comparable to the backtest
- **L-35** Change control: deploy a new version with code and parameter diff; apply at the next bar; one-click rollback; audit log
- **L-36** Customise: default risk limits per account, alert rule template, channel routing, dashboard widgets, timezone, sound, drift band width, broker per strategy, digest contents and time, units
- **L-37** Stale-data guard: Today and Forward do not compute when data ends before today; no zero-return days written
- **L-38** Agent API: get_signals; freeze_paper needs a human click
- **L-39** Map: universe as dots, names that fire lit, sortable
- **L-40** Today: signals table (symbol, action, value, distance to trigger, size)
- **L-41** Near triggers table
- **L-42** Orders sheet: copyable text and CSV
- **L-43** Ledger fills with the same fill model and costs as the backtest
- **L-44** Health: drawdown odds at the backtest Sharpe and at half
- **L-45** Freeze per version (backdate labelled); a new version starts a segment
- **L-46** Alerts: Apprise channels, test send, digest on run, failures logged

---

## 8. Chart

| Item | Spec |
|---|---|
| Purpose | Show price, indicators and the strategy's trades on one data source. |
| Who, when | After Backtest (click a trade), and for chart reading. |

**Inputs**: symbol (or list for a grid), timeframe (1d, 1h where held (superseded by C-29), weekly, monthly), indicators (search, favourites, presets), drawings, strategy overlay (up to 2), compare symbols (rebased %), layout (1-4 panes with synced crosshair), alerts.

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Price + volume + indicator panes | The strategy's trades on price | lightweight-charts 5 panes | Pine tables and overlays limited by plan |
| Strategy overlay | Entry and exit arrows, stop and target lines, position shading, signal pane | Overlay toggle per strategy | |
| Trade navigator | "Trade 41 of 214: +6.2%, MAE −2.1%, exit: target" | Floating card; ← → steps | |
| Replay | Bar-by-bar with equity and position under | Play, pause, 1× to 20×, scrub | Automated trades only; hand-trading is out of v3 |
| Compare | Rebased lines | % scale overlay | |
| Alerts | Created on the chart, evaluated on the server | Marker + feed link | |

**Interactions**: `R` replay; ← → trades; `G` from Backtest jumps here; drawing toolbar with the 12 most used and the rest in a menu; drawings saved per symbol on the server; `⌘K` "add indicator".

**Customisation**: indicator presets, drawing templates, colours per series, layouts, key per tool.

**States**: Empty "Pick a symbol"; Loading skeleton pane, first paint under 400 ms; Error "bars unavailable for X" with the data range held; Skipped "hourly held for 23 names" when 1h is chosen elsewhere (superseded by C-29).

**Reuses**: `chart_engine/IndicatorEngine/registry.ts` maths (71 indicators), `DrawingEngine/*` geometry, `/api/studio-v3/bars`. Patterns are not ported until a page names a use.

**Acceptance**

- C-1 Every chart indicator matches the backend formula within 1e-6 on a fixture (shared test).
- C-2 Chart, Backtest and Live read the same bars: same close for the same symbol and date (test).
- C-3 10 years daily + 3 indicators first paint under 400 ms.
- C-4 Clicking a trade in Backtest opens Chart zoomed to that trade with its stop and target.
- C-5 Replay at 20× stays at 60 fps on 5,000 bars (Playwright frame sample).


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **C-6** Layouts of 1, 2, 4 (and 6, 9) charts with synced symbol, crosshair and time; each sync toggled [FP 45]
- **C-7** Compare symbols as rebased % lines or indexed to 100
- **C-8** Price scales: linear, log, percent, indexed to 100
- **C-9** Chart types: hollow, OHLC bars, Heikin-Ashi, line, area, baseline, Renko, range, Kagi, Point and Figure, volume footprint, step
- **C-10** One chart engine on every page (Backtest, Live, Library, Build preview); WebGL; 1M bars smooth; decimation above 50k points [FP 45]
- **C-11** Indicator popup with Inputs, Style and Visibility tabs; apply to the selected pane; indicators on indicators; templates; favourites
- **C-12** Indicator lab: pick an indicator, symbol and range; tune with sliders; the chart updates live with no backtest [FP 44]
- **C-13** Formula-to-indicator pane: any formula string becomes a pane, so Build and Chart share one language [FP 76]
- **C-14** Strategy overlay: entries and exits, stop and target lines, position shading, signal pane; two strategies at once [FP 48]
- **C-15** Click a trade marker for a card: why it fired, with the rule values at that bar [FP 48]
- **C-16** Drawing tools (trend line, ray, horizontal, channel, Fibonacci, pitchfork, rectangle, text, arrow, measure, position tool, anchored VWAP); magnet to OHLC; lock, hide, group, clone; saved per symbol on the server [FP 46]
- **C-17** Drawings convert into alerts and block conditions ("price crosses the line") [FP 46]
- **C-18** Alerts created on the chart use the alert engine; right-click price to alert when it crosses; indicator and drawing-touch alerts
- **C-19** Replay: speeds to 50×, step forward and back, jump to date, blind replay (hides future bars and ticker), simulated orders and P&L [FP 47]
- **C-20** Strategy-stepped replay: orders appear bar by bar with the debugger [FP 47]
- **C-21** Manual trading in replay, recorded to a journal
- **C-22** Data window: crosshair readout of every series; legend values [FP 29]
- **C-23** Screenshot as PNG (watermark off) and export of the data in view
- **C-24** Spread charts: ratio A/B and a correlation panel
- **C-25** Events layer: earnings, splits, economic releases, news; regime shading and strategy trades layers
- **C-26** Automated analysis (trendlines, support and resistance, patterns) labelled as heuristics; reproducible code; can become a block
- **C-27** Customise: colours per theme, font size, crosshair style, price scale side, saved layouts and templates per symbol or global, a key per tool
- **C-28** Pan and zoom at 60 fps with 5 indicators on 100k bars; first paint under 1 s
- **C-29** Timeframes: daily, weekly and monthly (hourly removed by decision)
- **C-30** Keys and buttons: R replay, ← → trades, G from Backtest, drawing toolbar with the 12 most used, ⌘K add indicator
- **C-31** Candles, volume pane and indicator panes on lightweight-charts 5
- **C-32** All 70 chart_engine indicators usable; editable parameters kept per user
- **C-33** Trade navigator: ← → steps, zoom to trade ±20 bars
- **C-34** Replay: R key, 1×, 5×, 20×, scrub
- **C-35** Studio Chart embeds the full chart_engine chart

---

## 9. Library

| Item | Spec |
|---|---|
| Purpose | One place for the things every other page reuses and the user customises. |
| Who, when | Occasionally; first use when setting defaults. |

| Section | Holds | Lead | Notes |
|---|---|---|---|
| Universes | Saved universes (Screener screens, lists, uploads), counts, delisted count | "Nifty 500 point in time: 12 delisted" if coverage exists | Phase 0 decides India |
| Costs | Profiles (US retail, India retail with **dated** STT and charges, crypto, custom) with effective-from dates | "STT schedule from 2026-04-01" only after verification | India rates change; every profile is dated |
| Benchmarks | Symbols, blends (60/40), own CSV | | |
| Blocks and indicators | Reusable rule groups, formula indicators | | Shared with Chart and Screener |
| Regimes and crises | Custom regimes by formula; extra crisis periods | | |
| Metrics | Custom metric formulas usable as KPI, column, objective, limit | | |
| Profiles | Validation profiles, report orders, default sizing, workspace layout | | Replaces "workspace presets" |
| Data | Data audit: symbols per year, bars per symbol, rows / 252 check, fundamentals filing lag, adjusted status, delisted share and rule, hourly coverage (K names), freshness and last update job result | "Daily data to 2026-07-06; 4,158 tickers; hourly 23" (measured 2026-11-15) | The audit is also in the limits popover |
| Imports | Uploaded CSV bars and trades, Composer and QuantMage JSON mapper | Mapping shows what could not be translated | |
| Agents | Tokens, scopes, actor log, look budget | | Section 11 |

**Interactions**: every item can be saved as default, reset, exported as JSON, shared by link (settings only, never private prefs); sync server-side (`prefsSync`).

**States**: Empty sections show one action; Loading list skeleton; Error "could not save, kept locally"; Skipped section "India costs: coverage not measured".

**Reuses**: `kit/DataTable.tsx`, `prefsSync`, Screener saved-universe and preset code.

**Acceptance**

- Y-1 A custom metric formula `cagr / ulcer` works as a KPI, a table column, an Optimise objective and a My limit (four tests).
- Y-2 Data audit counts equal a direct parquet query on the fixture.
- Y-3 Exported profile imports on another account and reproduces the same Backtest.
- Y-4 Screenshot at 1440 and 1024.


### Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **Y-5** Universe types: static list, index members (point in time), screen rules, ETF holdings, top N by dollar volume, crypto pairs, option chains, custom Python [FP 39]
- **Y-6** Universe detail: preview table, count over time, turnover, survivorship status, data coverage, rebalance frequency, min price and ADV filters, ban list; point-in-time badge [FP 39]
- **Y-7** Universe versions frozen; a run pins the universe version it used [FP 39]
- **Y-8** Cost presets: US retail, IBKR fixed and tiered, zero commission with spread, futures CME, crypto spot and perpetual, FX retail, options per contract, custom [FP 40]
- **Y-9** Every profile dated with an effective-from date; India STT only after coverage is measured
- **Y-10** Compare a cost profile's impact on a strategy in one click [FP 40]
- **Y-11** Custom Python cost model; assigned per strategy or asset class; stored in the run record [FP 40]
- **Y-12** Benchmarks: symbols, blends (60/40), own CSV
- **Y-13** Blocks and indicators: reusable rule groups and formula indicators shared with Chart and Screener
- **Y-14** Indicator registry browser: formula, plot, reference, default parameters, optimisation range, warm-up, speed tag; "try on chart"; deprecation notes; 150+ indicators [FP 43]
- **Y-15** Custom indicator as a Python function with @indicator(inputs, outputs, warmup) and optional jit=True; appears in blocks and formulas
- **Y-16** Regimes and crises: custom regimes by formula; extra dated crisis windows from 2015
- **Y-17** Per-run data quality report: missing bars, stale prices, zero-volume bars, outliers, survivorship note; failing quality shows as a warning on the result [FP 41]
- **Y-18** Data catalog: symbols, first and last date, gaps, adjustment status, source, last update; click to preview [FP 41]
- **Y-19** Custom data: upload CSV or Parquet (500 MB per dataset), column mapping wizard, versioned, used as ctx.data("name")
- **Y-20** Fundamentals with ctx.field(symbol, field), point in time
- **Y-21** Corporate-action switch: adjusted, raw, total return; a badge on each result
- **Y-22** CSV bars and trades: column mapping, timezone, adjustments, per-row errors, saved import profiles
- **Y-23** Composer and QuantMage JSON mapper; untranslated parts listed
- **Y-24** TradingView trade export CSV
- **Y-25** Trade list import run through Validate (external strategy)
- **Y-26** Broker statements to compare live with expected
- **Y-27** Agent definitions: name, instructions, tools allowed, budget, model, schedule, run history with cost; no live-order tool; tokens and scopes [FP 57]
- **Y-28** AI experiment agent: variants run as branches under a budget [FP 56]
- **Y-29** Sharing: private, team, link; fork and merge upstream updates [FP 58]
- **Y-30** Projects marked as library: imports pinned by version; auto docs from docstrings; examples tested on each publish [FP 58]
- **Y-31** Template gallery: at least 30 vetted templates, each with expected stats on a fixed period and known weaknesses [FP 58]
- **Y-32** Search across the Library with tags, owner, version and usage count ("used by 7 strategies")
- **Y-33** Custom blocks from a Python function, shown in the palette with an icon and parameter form
- **Y-34** Customise: default universe, cost profile, data source per asset class, pinned items, import defaults
- **Y-35** Profiles: validation, report order, default sizing, workspace layout; export and import JSON
- **Y-36** Data section shows the phase 0 audit live (symbols per year, bars per symbol, gaps, adjustment, freshness)

---

## 10. Cross-page behaviour

### 10.1 Navigation and palette

| Item | Spec |
|---|---|
| Left nav | Section 0; dot on fresh runs; collapses to icons |
| Strategy picker | In every run header; switching keeps the page |
| Palette `⌘K` | Pages, strategies, templates, "run validate on this strategy", "compare with previous run", "copy link with settings", "export one-page PDF", "freeze to paper", "open Library > Costs"; rebindable keys; pin favourites |
| Keys | `⌘↵` run, `⌘S` save, `[` `]` tabs, `C` compare, `R` replay, `T` trades, `G` chart, `F` freeze, `/` search, Esc closes drawers |
| Breadcrumb | None; the run header carries strategy and version |

### 10.2 Compare

Any two runs, versions or strategies; up to 8 strategies (Portfolio); two Validate runs side by side; Backtest vs Paper vs Real in Live > Reconcile. Output: settings changed, numbers with winner per row, curves overlaid. Reuse `RunCompare.tsx`, `kit/Compare.tsx`.

### 10.3 Share and export

| Item | Spec |
|---|---|
| Share link | Strategy, settings, layout, results; read-only; expiry and revoke; never private prefs |
| Embed | Hero and verdict chip |
| Export | CSV of every table, trades CSV, equity CSV, PNG and SVG of any chart, one-page PDF, full report PDF, spec as JSON and as Python |
| Reproduce | A shared run shows its hash and a "Reproduce" button that re-runs on the server |

### 10.4 Alerts and digest

One alert engine for Chart, Live and Library. Channels: email, push, Telegram, webhook JSON. Each alert shows quota used. A webhook failure shows status code and retry time. Quiet hours per strategy.

### 10.5 Agent API (AX)

| Item | Spec |
|---|---|
| Surface | REST plus an MCP server over the same jobs: `list_templates`, `compile`, `backtest`, `optimise`, `validate`, `get_verdict`, `get_ledger`, `get_signals`, `get_data_audit`, `open_holdout`, `freeze_paper` |
| Output | Typed spec, plain-text verdict, limits and trial ledger in every response |
| Guard rails | Every call is logged by actor; the effective trial count applies to agents the same as to humans; hold-out looks budgeted (3 per strategy) and logged; `freeze_paper` and `certify` need a human click; no endpoint sorts strategies by backtest return |
| Why | QuantConnect, StrategyQuant, Build Alpha, Tactfolio and Canli ship MCP already; agents overclaim and inflate search (REVIEW §2) |

### 10.6 Customisation

As FEATURES_AND_OUTPUTS §10, with two changes: presets live in Library > Profiles; every customisation is in the typed spec so agents read and set it. Reset-to-default on every control; a "Customised" marker (shared) on changed inputs.

### 10.7 Budgets (tested)

| Action | Budget |
|---|---|
| Compile | < 100 ms server |
| Preview refresh | < 300 ms after typing stops |
| Backtest 1 symbol, 10 years | < 1 s |
| Backtest 500 names, 10 years | < 5 s cold (confirm in phase 0) |
| 1,000-cell sweep, 1 symbol | < 10 s |
| Trade list 10,000 rows | median frame ≤ 16.7 ms |
| Chart first paint, 10 years + 3 indicators | < 400 ms |
| Tab, menu, palette | < 70 ms click to paint |
| Validate quick profile, 1 symbol | < 10 s |

### 10.8 Phases (replaces PLAN §7 ordering)

| Phase | Ships |
|---|---|
| 0 | Data audit, daily update job, hourly coverage (23 names measured), delisted share, India coverage; engine spike; merge `metrics.py` |
| 1 | Spec, compile, engine, Backtest (Overview, Trades, Returns, Risk), Home, agent API with ledger |
| 2 | Build (four modes, sizing by risk, new exits, higher-timeframe rules, allocate blocks, autosave), Names, When, Paths tabs |
| 3 | Optimise; Validate (verdict, walk-forward, robustness, luck, hold-out, certificate); alerts and digest |
| 4 | Chart (trades on price, replay) |
| 5 | Portfolio; Live (Today, Forward, Reconcile) |
| 6 | Library completion, imports, India profile if coverage allows |
| 7 | Remove old Studio (graph + `rg` + route checks + smoke test per AGENTS.md) |
| 8 | Phone layout for the rest (Live is phone-first from phase 5) |

### 10.9 Cross-page acceptance

- X-1 Every page has a Playwright screenshot at 1440 and 1024, dark and light; Live also at 390.
- X-2 Every page has an empty, loading, error and skipped state test.
- X-3 The same strategy through UI and through the agent API gives the same hash.
- X-4 A shared link opens read-only, shows the hash, and Reproduce matches.
- X-5 Changing a Library cost profile marks dependent runs stale.
- X-6 No page sends a computed result to the server for certification (API test).
- X-7 Old route `/trade` redirects to Chart; old Studio routes redirect to the nearest new page.
- X-8 `rg` finds no import of removed Studio modules after phase 7 (AGENTS.md rule).


### 10.10 Target additions (FEATURES_PEAK)

New points from plan/FEATURES_PEAK.md (FP n) and the research specs; PY n is a row in PYTHON_IDE.md. Ids continue the page prefix. Build status is in CHECKLIST.md.

- **X-9** Reproduce button on every result: re-runs on the server and matches the stored hash [FP 1]
- **X-10** One engine and execution model for backtest, paper and live; paper vs backtest divergence report [FP 2]
- **X-11** Compare any two runs, versions or strategies (up to 8 in Portfolio): settings changed, winner per row, overlaid curves, code diff, execution model diff [FP 33]
- **X-12** Command palette ⌘K over every page, strategy, template, setting and action; rebindable; pin favourites [FP 49]
- **X-13** Keys: ⌘↵ run, ⌘S save, [ ] tabs, C compare, R replay, T trades, G chart, F freeze, / search, Esc closes drawers
- **X-14** Remappable keybindings: search, record chord, conflict warnings; presets VS Code, Vim, Emacs, JetBrains, Sublime; export and import JSON [FP 50]
- **X-15** Cheat-sheet overlay (?) with context shortcuts; every toolbar tooltip shows its shortcut
- **X-16** Settings in three levels (user, strategy or project, run or workspace); search; sync per user; admin locks; each setting shows its source, default and reset [FP 51]
- **X-17** Themes: light, dark, high contrast; import a VS Code theme JSON; separate chart theme; colour-blind safe preset
- **X-18** Dockable layouts with presets Write, Test, Debug, Review; zones collapse and resize; zen mode ⌘K Z; default by width (Test above 1280 px, else Write) [FP 52]
- **X-19** Phone layout for every page except Live: bottom nav, settings sheet, card rows
- **X-20** Mobile read view: Home, Live dashboard, alerts and kill switch; no editing
- **X-21** Share link: read-only; expiry and revoke; hides code if chosen; never private preferences
- **X-22** Export: CSV of every table, trades CSV, equity CSV, PNG and SVG of charts, one-page PDF, full report PDF, spec as JSON and as Python
- **X-23** Embed: hero and verdict chip
- **X-24** Audit log of who changed, ran and deployed what, filterable and exportable; roles viewer, commenter, editor, owner [FP 59]
- **X-25** Comments anchored to lines and to chart bars; resolvable threads; mentions [FP 59]
- **X-26** Notification centre: run complete, validation done, optimisation finished, live alerts, comments; channel per type
- **X-27** Compute manager: queue of running and waiting jobs with cancel, priority, time and cost estimate, quotas [FP 60]
- **X-28** Streaming results with cancel that keeps partial results, marked partial; runs continue when the tab closes; notification when done [FP 60]
- **X-29** Why a run was stopped (timeout, memory, handler too long) with a fix tip
- **X-30** Budgets as Playwright checks under frontend/e2e/perf: compile under 100 ms, preview under 300 ms, one symbol 10 years under 1 s, 500 names under 5 s, 1,000 cells under 10 s, 10k-row trade list median ≤ 16.7 ms, chart first paint under 400 ms, click to paint under 70 ms, Validate quick under 10 s
- **X-31** Editor ready under 1.0 s; keystroke to diagnostics under 300 ms; quick run (50 symbols, 5 years) under 8 s; full run (500 symbols, 10 years, portfolio) under 30 s; debugger step under 100 ms; 50k log rows at 60 fps
- **X-32** Keyboard-only flows; screen-reader labels; a table alternative to every chart; colour-blind palettes; reduced motion (replay shows a still frame)
- **X-33** Onboarding: a sample strategy per mode and a 5-minute guided path Build, Backtest, Validate, Paper; tips shown once
- **X-34** Left nav: dot on fresh unseen runs; collapses to icons
- **X-35** Strategy picker in every run header; switching keeps the page
- **X-36** Shared pieces: limits pill, freshness pill, My limits strip, trial chip, verdict chip, stale marker
- **X-37** Hero kinds fan, heatmap, tiles, gauge and grade in modules/research/Hero.tsx
- **X-38** Reset to default on every control; "Customised" marker on changed inputs
- **X-39** Agent API: list_templates, compile, backtest, optimise, validate, get_verdict, get_ledger, get_signals, get_data_audit, open_holdout, freeze_paper; typed spec and verdict in every response
- **X-40** Guard rails: the effective trial count applies to agents; no endpoint sorts strategies by backtest return; freeze and certify need a human click
- **X-41** One alert engine for Chart, Live and Library: email, push, Telegram, webhook JSON; quota per alert; webhook failure shows status and retry time; quiet hours per strategy [FP 21]
- **X-42** AI assistant: inline edit, explain an error, write a test strategy, critic citing lines and numbers; diff approval; logged to the actor log [FP 55]
- **X-43** Notebook tab sharing the data layer and engine: load_run, optimise helpers, ipynb import and export [FP 54]
- **X-44** Engine targets: 10 years of daily data on one symbol under 1 s; parallel optimisation over all cores; cache keyed by data version and indicator parameters [FP 60]
- **X-45** Avoid: results that cannot be reproduced, silent truncation, hidden fill and cost assumptions
- **X-46** Avoid: quotas that stop a run; decimate and show a truncation row instead (charts, logs, trades)
- **X-47** Avoid: no verdict; one locked policy and one scorecard
- **X-48** Avoid: intrabar guesswork; the stated worst case applies (stop fills first)
- **X-49** Avoid: optimisers capped at 3 parameters, and runs that cannot be compared
- **X-50** Avoid: debuggers that need a breakpoint to start
- **X-51** Avoid: two browser tabs editing one strategy
- **X-52** Avoid: AI edits applied without lint, validation and diff approval
- **X-53** Avoid: desktop-locked settings and results; results must be portable (export bundles open)
- **X-54** Avoid: block builders that hide lookback and rebalance assumptions
- **X-55** Avoid: dated, dialog-heavy settings; one searchable settings model instead
- **X-56** Avoid: live vs backtest divergence hidden by default; show it on Live
- **X-57** Studio route /studio/[[...slug]] and nav (Home · Build · Test · Portfolio · Live · Chart · Library)
- **X-58** Old Studio code removed (commit e778120); chart_engine kept
