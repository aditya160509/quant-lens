# Studio checklist (single tracker)

One tracker for every acceptance id and every point in [FEATURES_PEAK.md](FEATURES_PEAK.md). Page specs: [PAGES.md](PAGES.md). Reasons: [REVIEW.md](REVIEW.md). Data limits and decisions: [DECISIONS.md](DECISIONS.md). Python editor gaps: [PYTHON_IDE.md](PYTHON_IDE.md). LEAN steps: [LEAN_PARITY.md](../research/LEAN_PARITY.md). Item-to-id map: bottom of FEATURES_PEAK.md.

## Rules

- One page at a time, in this order: Portfolio (finish), Home, Build (Python IDE per PYTHON_IDE.md), Backtest, Optimise, Validate, Live, Chart, Library, Cross-page.
- A page is finished when every item is built or deferred with a reason, it passes standards/CODE_STANDARDS.md, standards/UI_GUIDE.md and standards/UI_CANON.md, and it is checked in a browser at 1440 and 390 px in light and dark. Then commit and push (AGENTS.md).
- Build order (PYTHON_IDE.md): 1 IDE layout, 2 runner output, 3 portfolio API, 4 imports, 5 completion and checks, 6 project files and template gallery, 7 debugger and split preview, 8 indicator objects.
- `[x]` means built and in the DONE list (2026-11-17), in the old checklist's `[x]` lines, or in git history. Anything not listed is `[ ]`.
- Tags: `(partial: …)` some of it is built. `(blocked by data: …)` DECISIONS.md applies. `(owner decision: …)` see Owner decisions. `(not in v3: …)` out of scope per PAGES "Not in v3" or REVIEW §3.
- Phase 1 frontend boxes were unchecked in the old list because nothing had been viewed in a browser. Home and Backtest are ticked where the DONE list says they are built. Browser checks (screenshots, Playwright) stay open on the acceptance ids.

## Counts (done / total)

| Page | Done | Total |
|---|---|---|
| Portfolio | 5 | 28 |
| Home | 1 | 26 |
| Build | 29 | 162 |
| Backtest | 18 | 57 |
| Optimise | 18 | 40 |
| Validate | 18 | 50 |
| Live | 11 | 46 |
| Chart | 6 | 35 |
| Library | 0 | 36 |
| Cross-page | 2 | 58 |
| **All pages** | **108** | **538** |

## Portfolio (`/studio/portfolio`, spec §6): 5 / 28 done

### Acceptance (PAGES)

- [x] P-1 Equal-weight combination of two fixtures equals the hand-computed series
- [x] P-2 Meta rule "SPY above 200d" switches on the next open with no look-ahead
- [ ] P-3 Combined strategy sent to Validate returns a verdict
- [ ] P-4 Screenshots at 1440 and 1024

### Target additions (FEATURES_PEAK)

- [ ] P-5 Sleeves carry weight, capital, start date, enable toggle and scaling (vol target, leverage cap); a sleeve can be a portfolio (partial: weights and up to 12 members built; capital, start, toggle, scaling and nesting open)
- [ ] P-6 More allocation methods: minimum variance, max diversification, mean-variance with shrinkage, capped Kelly, momentum of members, drawdown throttle, custom Python function (partial: equal, inverse vol, risk parity, HRP, max Sharpe, fixed built; these open) [FP 36]
- [ ] P-7 Rebalance on a calendar or a threshold corridor, with a minimum trade size to cut churn (partial: quarterly re-estimation built; threshold and minimum trade size open) [FP 36]
- [ ] P-8 Stacked-area weights over time with the effective number of bets (partial: weights over time built; effective number of bets open)
- [ ] P-9 Diversification ratio, drawdown overlap, capacity by sleeve, turnover, cost drag, net exposure by symbol across sleeves (partial: correlation, marginal contribution, trade and name overlap built; the rest open) [FP 37]
- [ ] P-10 Correlation over the full period and over a rolling window (partial: full-period correlation built; rolling window open)
- [ ] P-11 Constraints: max weight per member, per symbol and per sector; gross and net limits; leverage; cash reserve; minimum member count; ban list; max correlation between members (partial: cap per member built; others open) [FP 36]
- [ ] P-12 Sleeve drop-out test: remove each member and show the effect [FP 37]
- [ ] P-13 Correlation shock: all members at correlation 0.8
- [ ] P-14 Crisis stress: the combined portfolio in each crisis window from 2015 [FP 74]
- [ ] P-15 Overlap guard: warns when two members hold the same symbol in opposite directions or share more than 70% of signals
- [ ] P-16 Walk-forward allocation test: out-of-sample weights shown against full-sample weights (partial: quarterly out-of-sample weights built; comparison to full-sample weights open) [FP 38]
- [ ] P-17 Netting: opposite trades on one symbol across members cancel before execution [FP 74]
- [ ] P-18 Efficient frontier of the members with the chosen mix marked [FP 74]
- [ ] P-19 Rebalance costs counted when weights shift
- [ ] P-20 Deploy as one book, paper first, with netted orders and per-member P&L attribution
- [ ] P-21 Alpha, beta, tracking error and information ratio against the chosen benchmark
- [ ] P-22 Multi-currency account with a base currency and FX on cash (blocked by data: no FX data in the data set)
- [ ] P-23 Portfolio view during a run: exposure by symbol, sector and asset class, cash, margin, beta to benchmark (partial: holdings treemap and names held built; sector exposure, beta and margin open)
- [ ] P-24 Meta rule: weight by regime; rotate to the strongest by trailing N months (partial: rotation to top N by 3-month return built; regime weighting open)
- [ ] P-25 Customise: default method, rebalance frequency, estimation window, constraints
- [x] P-26 Cluster tree of members
- [x] P-27 Rotation to the top N by trailing 3-month return
- [x] P-28 Weights re-estimated quarterly on the trailing year (no look-ahead, tested)

## Home (`/studio`, spec §1): 1 / 26 done

### Acceptance (PAGES)

- [ ] H-1 Paints 50 saved strategies in under 400 ms (Playwright)
- [ ] H-2 Needs attention lists a strategy whose paper step is older than 3 trading days (partial: needs-attention strip built; paper-age rule not checked)
- [ ] H-3 Duplicate makes version 1 with an empty trial ledger (partial: duplicate built; empty-ledger rule not tested)
- [ ] H-4 Studio JSON import recompiles and shows compile findings before saving (partial: JSON import built, first version only, never fully passed)
- [ ] H-5 Screenshots at 1440 and 1024, dark and light

### Target additions (FEATURES_PEAK)

- [ ] H-6 Table view with sortable, toggleable columns (name, status, Sharpe, max DD, last run, equity sparkline) and a stale-run badge; card view stays the default (partial: card view only) [FP 53]
- [ ] H-7 Status chips Draft, Backtested, Validated, Paper, Live; a click filters; Validated only when a scorecard exists for the current version [FP 53]
- [ ] H-8 Search by name, tag, hypothesis, symbol, indicator and code text (typing rsi( finds strategies that use it)
- [ ] H-9 Saved filters, folders, tags and pins
- [ ] H-10 Archive; hard delete needs a typed confirmation and a 30-day trash
- [ ] H-11 Bulk actions on a selection: tag, move, archive, run same range, compare, combine into a portfolio [FP 53]
- [ ] H-12 Hover actions on a row: Run, Duplicate, Open in Chart, Open Live, Share
- [ ] H-13 Create menu: blank, template, plain-English prompt, Studio bundle, trade CSV, QuantConnect Python (via shim), library strategy (partial: blank, template, duplicate and JSON import exist)
- [ ] H-14 Live strip at the top: live and paper strategies with today P&L, alert count, heartbeat and kill-all
- [ ] H-15 Saved views, column sets, default sort, density, group by status, tag or folder
- [ ] H-16 Empty state: three one-click starters (blank, template, from a Screener screen)
- [ ] H-17 Compare 2 to 6 strategies from Home: overlaid equity, metric table, correlation, code diff; opens Portfolio
- [ ] H-18 Needs attention ranked: drift beyond band, data newer than last run, validation expired by a code change, failed run, alert fired (partial: strip exists; trigger list not verified)
- [ ] H-19 Import a QuantConnect algorithm through the shim; unmapped calls listed before saving [FP 67]
- [ ] H-20 Import a CSV of signals
- [ ] H-21 Card fields: sparkline of last run, verdict chip, trial count, last edited (partial: grade, trial count and paper status shown; sparkline not verified)
- [ ] H-22 Recent runs table with a settings-changed-since marker
- [ ] H-23 Data freshness pill ("Daily data to 2026-02-01"), amber after 3 days, red after 10
- [ ] H-24 Customise: default view, card fields, grid columns and sort, pinned strategies
- [ ] H-25 Bulk re-run on new data and export a selection as a zip
- [x] H-26 Strategy cards with grade, trial count, paper status and last run; duplicate; JSON import (first version)

## Build (`/studio/build/:id?`, spec §2): 29 / 162 done

The Python IDE items (tag PY) follow PYTHON_IDE.md. Build order is in the Rules above.

### Acceptance (PAGES)

- [x] B-1 Same rule as blocks, formula and Python gives identical trades
- [x] B-2 Look-ahead (close[+1], centred window) refused with the line and token named
- [x] B-3 Weekly SMA on a Wednesday uses the last closed week
- [x] B-4 Compile under 100 ms server side for a 20-row strategy
- [ ] B-5 Preview refreshes within 300 ms after typing stops (in-page timing) (partial: server 0.37 s measured; in-page timing not tested)
- [ ] B-6 Reload restores the unsaved draft exactly (partial: autosave every 2 s built; reload test not recorded)
- [ ] B-7 Ten near-identical sweep cells add ten raw and fewer than four effective trials (partial: raw and effective counts shown; cell test not recorded)
- [x] B-8 Time stop, breakeven and scale-out each have a fixture with exact expected trades
- [x] B-9 "What it does" paragraph for the SMA cross fixture equals a stored string
- [ ] B-10 Screenshots at 1440 and 1024

### Target additions (FEATURES_PEAK)

- [ ] B-11 Full-height IDE: editor fills the work area; bottom panel resizes 30 to 40%; side rail collapses (partial: editor is a 420 px box) [PY B1]
- [ ] B-12 Three zones: left rail (Files, Outline, Search, Templates, Versions), centre editor, bottom panel (Problems, Output, Logs, Results, Plots, Debug, Terminal); right rail (preview, Inspector, AI); each zone remembers its size
- [ ] B-13 Editor groups: split right or down, up to 4 groups; tabs can be pinned, kept in preview, or marked dirty
- [ ] B-14 One editing session per strategy: a second tab opens read-only with a take-over button
- [ ] B-15 Phone (390 px): one zone at a time with a Code, Run, Results switcher; Build on phone is Formula and Plain English only
- [ ] B-16 IDE keys: F5 debug, F9 breakpoint, F10 step bar, F11 step line, ⌘J panel, ⌘B rail, ⌘\ split, ⌘P file, ⌘⇧F search project
- [ ] B-17 JetBrains Mono 13 px, 20 px line height, ligatures off, bracket colours, sticky scroll, folding (partial: Mono 13 px only) [PY B13]
- [ ] B-18 App theme tokens defined as a Monaco theme so the editor sits in the page (partial: vs-dark and light only) [PY B12]
- [ ] B-19 Editing keys: ⌘/ comment, ⌥↑↓ move line, ⌘D next match, ⌘⇧K delete line, ⇧⌥-drag column select, go to line ⌃G (partial: ⌘S format and save and ⌘↵ run exist) [PY B5]
- [x] B-20 Format Python on save with ruff
- [ ] B-21 Format selection (⌘K ⌘F) and organise imports
- [ ] B-22 Go to symbol ⌘⇧O, go to line ⌃G, definition F12, references ⇧F12, peek ⌥F12, rename F2 across files
- [ ] B-23 Find and replace across all project files: regex, case, whole word, preview before replacing
- [ ] B-24 Code actions ⌘.: extract formula string to parameter, convert ctx.rule to indicator object, wrap selection in if ctx.position == 0, add missing on_fill
- [ ] B-25 Outline of classes, methods and indicators for the open file
- [ ] B-26 Undo history survives reload, per file (partial: undo and redo built; survives reload not built)
- [ ] B-27 Save state indicator (Saved, Saving, Conflict) and local draft recovery from IndexedDB (partial: autosave exists; indicator and conflict state open)
- [ ] B-28 Read-only banner when the editor code differs from the code that produced the visible result
- [ ] B-29 Side-by-side Monaco diff of two versions, with each version run result above it (partial: field-by-field diff with run results built; Monaco side-by-side open) [PY B9]
- [ ] B-30 In-browser Pyright in a web worker with Studio stubs (ctx, portfolio, orders, indicators, numpy, pandas, math, typed Bar, Fill, Order, Position); covers the user own classes [FP 26, 62]
- [ ] B-31 Completion inside ctx.value("…") for formula names, ctx.param("…") for parameter names, ctx.symbol == "…" for symbols, ctx.history("…") for fields; snippets with tab stops (partial: formula names inside ctx.value exist)
- [ ] B-32 Completion for the whole API with signature help on "(" (active parameter bold) and a docs example (partial: 17 ctx members with hovers; no signature help) [PY B6]
- [ ] B-33 Three diagnostic layers as you type (300 ms): Pyright errors; Studio rules (banned names, look-ahead patterns, imports outside the allow-list); formula parse errors at the exact token (partial: server static markers and formula token errors exist; debounce and Pyright layer open)
- [ ] B-34 Hover: docs, signature, formula meaning, lookback and warm-up bars, latest value after a preview; hover on a parameter shows its range and last best value (partial: ctx hovers exist)
- [ ] B-35 Look-ahead detector in the editor: close[0], close[1:], history without a negative index, ctx.date against future literals, next_* reads; marked before the run (partial: AST screen refuses positive indexes; inline editor markers open) [FP 8]
- [ ] B-36 Docs panel: ⌘-click or F1 opens the reference beside the editor; searchable (API, indicators, recipes); offline and versioned
- [ ] B-37 Strictness setting (basic or strict) and severity per rule (error, warning, off); defaults: basic, all layers, look-ahead as error
- [ ] B-38 Domain diagnostics: unused parameter, warm-up longer than data, order with no stop in live, hard-coded symbol in a parameterised strategy, print in hot loop, mutable default in params [FP 26]
- [ ] B-39 ctx.assert_invariant(cond, msg) puts red markers on the chart and fails the Validate step
- [ ] B-40 Lint flags wall-clock time, network calls and unseeded random, so one code runs in backtest, paper and live
- [ ] B-41 API version header (# studio-api: 1) with an automatic migrator and a quick fix
- [ ] B-42 Latency budget: completions under 100 ms, diagnostics under 500 ms after typing stops
- [ ] B-43 Portfolio mode: on_data(ctx) sees every symbol in the bar; universe set by a class attribute (list, index, or screen id); per-symbol on_bar kept as the simple mode [FP 61] [PY A1]
- [ ] B-44 Orders: target_weights, set_weight, order (qty), order_value, limit, stop, stop_limit, liquidate, cancel, cancel_all; all fill through fills.py (partial: buy, sell, short and cover at the next open only) [FP 61] [PY A2]
- [ ] B-45 Brackets: bracket(sym, qty, stop, target, trail) with OCA cancel; partial exits by qty per level; stop fills first when both hit one bar [FP 61]
- [ ] B-46 Pyramiding: max_entries class attribute per symbol; scale in added to the Build exits card [FP 61]
- [ ] B-47 Read-only portfolio state: ctx.portfolio cash, value, leverage, exposure; ctx.pos(sym) qty, avg price, unrealised, bars held, entry date (partial: ctx.position is -1, 0 or 1 only) [FP 61] [PY A3]
- [ ] B-48 ctx.history(field, n, sym=None) returns numpy (pandas=True for a DataFrame); negative indexes only (partial: ctx.close[-20:] lists exist; history() open) [PY A5]
- [ ] B-49 ctx.bar(sym) for the current bar and ctx.market for the benchmark
- [ ] B-50 ctx.indicator(formula) with .value, .ready, .history(n), .window; LEAN-identical definitions (LEAN_PARITY row 19) (partial: ctx.value formula strings exist; objects open) [FP 43] [PY A4]
- [ ] B-51 ctx.rank(ind, top, bottom, where) and ctx.zscore(ind) across the universe, vectorised [FP 61]
- [ ] B-52 rebalance attribute (month_start, week_start, every(n), daily, None); ctx.rebalancing; is_month_start, is_week_start, is_quarter_start, is_year_start [FP 61] [PY A6]
- [ ] B-53 warmup class attribute: no orders before bar n; auto warm-up reported ("starts trading on …") [FP 61] [PY A10]
- [ ] B-54 Risk attributes: max_drawdown (flatten and stop), max_daily_loss, max_position, max_gross; each breach logged as a risk event [FP 61]
- [ ] B-55 ctx.store keeps small JSON across runs; instance attributes keep state
- [ ] B-56 ctx.feature_matrix(formulas, lookback) and ctx.fit_every(n); sklearn allowed; fits use past bars only
- [ ] B-57 Import allow-list: math, statistics, numpy, pandas, scipy.stats, scipy.optimize, sklearn, and the project files; others refused with the line and a request link (partial: math only; imports refused) [PY A7]
- [ ] B-58 print and ctx.log(msg, level) captured per bar (date, symbol), 50,000-line cap with a truncation row (partial: print allowed, output dropped) [PY A8]
- [ ] B-59 ctx.plot(name, value, chart="main" or "own"), ctx.mark(sym, label) on the price chart, ctx.table(name, row) as a sortable table [FP 29] [PY A9]
- [ ] B-60 on_fill(ctx, fill) gets symbol, side, quantity, price, date and fee (partial: on_fill(ctx) without detail) [PY A11]
- [ ] B-61 Lifecycle hooks: on_end_of_day, on_warmup_done, on_risk_event, on_stop
- [ ] B-62 params = {"fast": (10, 5, 50, 5)} declared in code appear in Build params and the Optimise grid; ctx.param kept (partial: ctx.param exists; declared params not wired to Optimise) [FP 9] [PY A12]
- [ ] B-63 Per-strategy engine settings as class attributes (fill timing, costs, sizing); code wins over the card and a badge says so
- [ ] B-64 Python orders feed the event engine directly, so LEAN parity applies to Python strategies [PY A13]
- [ ] B-65 Budget: 500 symbols × 2,500 bars in under 20 s [PY A14]
- [ ] B-66 Default mode for new strategies (simple or portfolio) in Customise
- [ ] B-67 Refuse formulas or Python that read fundamentals for dates before 2021 (blocked by data: fundamentals held from 2021 only)
- [ ] B-68 Runtime guard: positive history index raises in backtest, same rule as the editor lint (partial: AST screen; runtime guard not verified)
- [ ] B-69 Bar stepper: pause at a date and symbol, inspect self and ctx, step one bar, step to the next order or fill, run to a date, step back one bar (deterministic re-run) [FP 27] [PY B8]
- [ ] B-70 Breakpoints with conditions (ctx.symbol == "AAPL" and ctx.date >= …) and hit counts; data breakpoints (first order; equity down 5% in a day) [FP 27, 65]
- [ ] B-71 Variables (self, ctx, locals); arrays and DataFrames in a grid viewer; watch expressions with history; read-only debug console
- [ ] B-72 Preview chart follows the paused bar, with position and pending orders drawn
- [ ] B-73 Logpoints from the gutter ("log {expr} here") without editing the code
- [ ] B-74 Gutter: run markers on lines that placed orders in the last preview (hover shows count and first 5 dates); change markers since last version
- [ ] B-75 Inlay hints: parameter value next to ctx.param, last value next to ctx.value from the preview, computed type [FP 63]
- [ ] B-76 CodeLens above on_bar ("Run on SPY · Run on universe · Debug from 2020-03-01"); above ctx.rule ("true on 34% of bars") [FP 64]
- [ ] B-77 Time travel on a finished backtest: pick any bar, see a variable snapshot, arrow keys step back and forward; snapshots only for chosen date ranges [FP 27]
- [ ] B-78 Profiler: time per function and per line, slowest 10 lines, flame graph, memory chart
- [ ] B-79 Logs tab: virtual list (level, date, symbol, message, code line); filters for level, symbol, date, text, regex, case, whole word; click row jumps chart and editor; CSV export [FP 28]
- [ ] B-80 Structured logs: ctx.log.info("entry", symbol=s, rsi=r) stored as key values, searchable [FP 28]
- [ ] B-81 Plots tab: each ctx.plot series overlays the price or sits in its own pane on a shared time axis; toggle each; compare across two runs [FP 29] [PY B2]
- [ ] B-82 Problems tab: static and runtime errors, click to jump to the line (partial: markers only, no Problems list) [PY B2]
- [ ] B-83 Results tab: compact Backtest report (KPI strip with All, Long, Short; equity vs benchmark; trade list; trade histogram; Properties block); Open in Backtest without recompute [PY B2]
- [ ] B-84 Three run levels: live preview (600 ms debounce, one symbol, 2 years), quick run ⌘↵ (universe, 5 years), full run ⌘⇧↵ (recorded in the ledger) (partial: preview built (300 ms, 2 years); quick and full levels not split)
- [ ] B-85 Progress in the status bar ("bar 1,240 / 2,516 · 18 symbols · 3.2 s") with partial equity streamed to Results
- [ ] B-86 Cancel with Esc; time budget shown on every run
- [ ] B-87 Runtime error: jump to the line, stack trace with user frames only, locals at the failing bar (symbol, date, self attributes) (partial: runtime error marks its line only)
- [ ] B-88 Delta row after each quick run against the last run (return, Sharpe, trades)
- [ ] B-89 Preview settings: symbol and window (default SPY, 2 years), auto-preview on or off; quick-run universe (top 50 by volume, 5 years) (partial: preview symbol and window exist)
- [ ] B-90 Status bar: Ln:Col, error and warning counts, saved state, run state, last run time, "trial 14 on this idea" (partial: trial chip in Build; status bar not built) [FP 68]
- [ ] B-91 Yellow banner on a result when the editor code differs from the run
- [ ] B-92 Strategy is a project: main.py plus modules, README.md and params.json; file tree with create, rename, move, delete, duplicate and drag; limits 50 files and 200 KB per file [PY B3]
- [ ] B-93 Any project can be marked a library and imported by others with a pinned version; "v3 available, review diff" badge; updates never change saved strategies silently [FP 58]
- [ ] B-94 Zip import and export of a project
- [ ] B-95 User snippets: save a selection with tab stops and a prefix trigger; shareable through Library
- [ ] B-96 Examples in hover docs insert with one click
- [ ] B-97 Gallery of 12 starters with a one-line description, last backtest on the default universe and "use as start" (trend 50/200, RSI(2), momentum top 10, dual momentum, pairs z-score, vol target, ATR breakout, turn of month, gap fade, sector rotation, ML ranking, risk parity) (partial: 20 formula templates exist; gallery stats open)
- [ ] B-98 Python starters: trend, mean reversion, momentum rotation, pairs, vol target, breakout, seasonality, ML score [PY B10]
- [ ] B-99 Warn above 200 blocks, hard stop at 1,000; warn above 8 optimisable parameters
- [ ] B-100 Customise: personal templates, parameter ranges per strategy, default sizing and costs per user, editor font and keymap
- [ ] B-101 Monaco palette and the app palette merged into one list, grouped Editor, Run, View, Studio
- [ ] B-102 Four authoring modes on one spec: blocks, formula, Python, plain English; the mode switch never loses work (partial: all four exist; code-only badge and switch marking open) [FP 22]
- [ ] B-103 Blocks and formula show generated Python side by side (read only); formula to Python is one way, original kept; hand edits that cannot be represented set a code-only badge (partial: formula to Python one way exists; side panel and badge open) [FP 22]
- [ ] B-104 Plain English shows the interpreted rules as blocks before any run; ambiguous words highlighted ("oversold" = RSI(14) < 30); restated "what it does" paragraph; original prompt kept in version history (partial: phrase rules, ignored words listed, review then use; highlights and history open) [FP 23]
- [ ] B-105 Any and All groups, nested to any depth (partial: rows joined by and or; nesting open) [FP 24]
- [ ] B-106 Condition kinds: cross above and below, for N bars, rising, falling, earnings filter, fundamentals, calendar, cross-sectional (partial: crosses and higher-timeframe rules exist; others open)
- [ ] B-107 Inline parameter editor with an optimisation range per parameter; plain-language summary line; colour by role; collapse, disable, comment, duplicate, copy as code; undo 50 steps [FP 9]
- [ ] B-108 Red marker on incomplete blocks; detector for conditions that are always true or always false on your data
- [ ] B-109 Click a condition block: the preview shows the bars where it fired (no full backtest) [FP 24]
- [ ] B-110 Trading frequency: calendar (daily, weekly, monthly, on bar close) or threshold corridor (X% drift)
- [ ] B-111 Formula inline value under each rule: true-rate and last true date
- [ ] B-112 Function reference panel for formula mode
- [ ] B-113 Named variables (fast = ema(close, 12)), user functions, comments; separate entry and exit formulas
- [ ] B-114 Multi-timeframe calls causal only: weekly(x) built and tested; monthly open; hourly blocked by data (partial: weekly built (B-3); monthly open) [FP 42]
- [ ] B-115 Composer-style tree blocks: if/else branches, filter by rank, weight by method, group; nest to any depth [FP 69]
- [ ] B-116 Live true-rate on every condition block ("true on 31% of bars, last true 2026-01-28") [FP 69]
- [ ] B-117 Complexity meter: counts parameters and rules and shows degrees of freedom while building [FP 25]
- [ ] B-118 Find rules: grammar search of entries and exits with an out-of-sample split; every candidate counts in the trial ledger; results go to the Home databank grid [FP 70]
- [ ] B-119 Checks card adds warm-up bars needed, data each rule uses, survivorship exposure (partial: checks card exists; three rows open)
- [ ] B-120 Exits library additions: profit-target ladder, exit on opposite signal, end-of-week exit; exits combinable and ordered (partial: stop, target, trailing, time, breakeven, scale out exist; these open)
- [ ] B-121 Sizing additions: equal weight, risk parity, max position and gross limits (partial: shares, cash, % equity, risk, vol target, Kelly, score exist)
- [ ] B-122 Allocate: if/else on a condition (regime, trend); hold bonds or cash when off (partial: market rule (trade only when) exists; if/else branch and bonds open)
- [ ] B-123 Entry filters: fundamentals, calendar, cross-sectional, earnings-date filter (blocked by data: fundamentals from 2021 only; earnings dates where held)
- [ ] B-124 Indicator exit and scale in as exit-card rows
- [x] B-125 Stated regime claim marked "written after" when added after a drawdown
- [ ] B-126 Version timeline: each version with its metrics (equity sparkline, Sharpe); name and tag versions ("validated", "live"); a live version is locked (partial: version list, picker and field diff with run results exist; timeline metrics, tags and lock open) [FP 35]
- [ ] B-127 Restore or branch from any version; restore creates a new version and deletes nothing [FP 35]
- [ ] B-128 Experiments as branches: fork a strategy, change a rule, compare two branches on one chart, merge back [FP 35]
- [ ] B-129 Blame: each line shows the version that last changed it
- [ ] B-130 Local history: autosave snapshots kept 7 days, separate from versions (partial: autosave draft every 2 s; 7-day history open)
- [ ] B-131 Share a read-only link or a fork link; pinned comment threads on a line
- [ ] B-132 Single editing session per strategy with take-over; the second tab is read-only (no QuantConnect-style desync) [FP 66]
- [ ] B-133 Notes (hypothesis, what was tried, decisions) exported with the certificate
- [ ] B-134 Saved rule groups reusable as blocks; custom indicators by formula shared with Chart and Screener
- [ ] B-135 Customise: default mode, default exits and sizing profile from Library, blocks palette order, block colours and compact or expanded view
- [ ] B-136 Keyboard-first block insertion (type "/") and snap grid
- [ ] B-137 Shared undo across views; Explain on any selection; convert to library block; one parameter table across all views
- [ ] B-138 Python keys: F5 debug and Run, ⌘⇧↵ full run (quick run ⌘↵)
- [ ] B-139 Python engine settings (fill timing, costs, sizing) shown as a badge when code overrides the card
- [ ] B-140 Inline ⌘K edit on a selection, shown as a diff to accept or reject (AI is an owner decision) (owner decision: AI features, see OD-11)
- [ ] B-141 Snippets palette (⌘⇧S) with user and team snippets
- [x] B-142 Formula editor with live compile (0.26 ms measured) and per-role findings
- [x] B-143 Blocks and formula convert both ways: rows of comparisons and crosses joined by and/or; other shapes stay formula (round-trip test)
- [x] B-144 Python mode: Monaco with ctx completion, hovers, snippets, inline markers from server checks and runtime errors; class Strategy with init, on_bar, on_fill
- [x] B-145 Python runs in a locked child process (-I, empty env, CPU and file limits, builtins allow-list, AST screen, no positive indexes)
- [x] B-146 Formula to Python one way: same trades as the formula (tested)
- [x] B-147 Plain English to rule by fixed phrase rules (MAs, crosses, RSI, highs and lows, ROC, weekly trend, volume, stops, targets, time stops); ignored words listed; review, then Use this rule
- [x] B-148 Allocate: "Trade only when" market rule (market = SPY close; everything closed on the bar it turns false); rotate = Rank by + max positions; Portfolio switch rule
- [x] B-149 Sizing: shares, cash, % equity, risk per trade, vol target (both engines), Kelly (capped), score weighting (both engines, parity tested)
- [x] B-150 Repaint check: signals on 50 history cuts of the preview name must equal full-history signals; shown under the preview
- [x] B-151 Preview chart: any symbol, last 2 development years, entries and exits marked, refreshes 300 ms after typing (server 0.37 s)
- [x] B-152 Undo and redo (⌘Z, ⇧⌘Z)
- [x] B-153 Immutable versions with a picker; field-by-field diff against any version
- [x] B-154 Checks card: compiles, no look-ahead, fires, trades on one name, exits, parameters used; jump links
- [x] B-155 My limits (walk-away conditions) and notes saved with the version
- [x] B-156 Command palette ⌘⇧P: lift a number to a parameter, add parameter, modes, templates, save, run (⌘K stays app search)
- [x] B-157 Parameter step and sweep size; step count shown against the sweep size
- [x] B-158 Drag to reorder block rows
- [x] B-159 Template start grid (20 templates)
- [x] B-160 Stated regime claim marked "written after" when added after a backtest
- [x] B-161 Trial chip opens the ledger drawer
- [x] B-162 Backtest results side by side in the version diff

## Backtest (`/studio/backtest`, spec §3): 18 / 57 done

### Acceptance (PAGES)

- [ ] K-1 Hero numbers equal metrics.py outputs within 1e-9 on the SMA-cross fixture (partial: canonical metrics.py merged; hero equality test not recorded)
- [ ] K-2 Same run twice gives identical trades and equity (hash equal)
- [x] K-3 Fills at next open by default; a gap through a stop fills at the open
- [ ] K-4 With zero costs every output shows a "costs off" pill
- [ ] K-5 Start-date card reproduces a hand-computed result for 3 start dates (partial: start-date card built; test not recorded)
- [ ] K-6 Survivorship delta changes the equity line on a fixture with one delisted name (partial: survivorship delta built; fixture test not recorded)
- [x] K-7 Zero-entry run refused with a reason, not an empty report
- [ ] K-8 Trade list of 10,000 rows scrolls with median frame ≤ 16.7 ms
- [ ] K-9 500 names, 10 years, under 5 s cold (partial: 0.44 s load and signals and 0.009 s engine measured on a warm cache; cold not measured)
- [x] K-10 Hold-out dates do not appear in any Backtest series
- [ ] K-11 Screenshots at 1440 and 1024, dark and light, each tab

### Target additions (FEATURES_PEAK)

- [ ] K-12 Run header: strategy, version, range, capital, data version, execution preset, seed, duration, engine version; Reproduce and Duplicate and edit buttons
- [ ] K-13 Immutable run record: code hash, params, data version, execution model, engine version, seed, timing; a re-run gives the same numbers (partial: certificate hash in Validate; per-run record not built) [FP 1]
- [ ] K-14 Stat tiles: pick any 8 of 60+ stats; each has a definition on hover (formula and LEAN reference) (partial: KPI strip picks 4 to 6; 60+ stats and definitions open) [FP 30]
- [ ] K-15 Add PSR, expectancy, fees total, volume traded and capacity to the stat strip [FP 30]
- [ ] K-16 All, Long and Short toggles on every metric
- [ ] K-17 Date range brush recomputes every stat for the selected range [FP 30]
- [ ] K-18 Benchmark overlay: log or linear, % or $; regime shading; trade markers toggle (partial: hero shows benchmark; toggles open)
- [ ] K-19 Rolling 6, 12 and 36-month windows for return, Sharpe, volatility and beta (partial: rolling Sharpe, volatility and beta built; 36-month and return windows open)
- [ ] K-20 Return distribution with a normal overlay; best and worst day lists
- [ ] K-21 VaR and CVaR at 95 and 99, tail ratio, Ulcer index, beta and correlation to benchmark, leverage, concentration
- [ ] K-22 Stress scenarios inside the data (2018 Q4, 2020, 2022) (partial: 2015+ crisis strip built; 2008 and 2011 blocked by data (no stock bars before 2015))
- [ ] K-23 Trades: 100,000+ rows; column toggles; filters (winners, losers, symbol, tag, date, size); export CSV and Parquet (partial: virtualised list and sets exist; filters, toggles and export open) [FP 31]
- [ ] K-24 Per-trade drill: chart with entry and exit bars, rule values at entry, MAE and MFE, the code line that fired (jump to code) (partial: trade navigator on Chart; rule values and code line open) [FP 31]
- [ ] K-25 Trade analytics: P&L by hour, weekday, month, regime and symbol; streaks; expectancy by tag (partial: P&L by regime and month exist; others open)
- [ ] K-26 What-if exit overlay (stop or target change), flagged as approximate
- [ ] K-27 Costs tab: gross vs net, commission, slippage, borrow and financing bars; break-even cost level (partial: cost ladder 1×, 2×, 4×; gross vs net in Risk; break-even in Validate; financing open)
- [ ] K-28 Cost sensitivity slider 0× to 3×, recomputed from stored fills [FP 32]
- [ ] K-29 Execution model panel with presets (US retail, crypto, futures) and a custom Python cost hook: fill, slippage (fixed bps, volume share, spread), commission, borrow, financing, margin, settlement, lot size, tick rounding, session calendar (partial: commission, slippage, borrow, volume cap, delisting haircut exist; presets and hook open) [FP 13]
- [ ] K-30 Intrabar fill fidelity levels (fast, standard, detailed, tick) with the ambiguous-bar count shown (blocked by data: hourly bars removed 2026-11-16; worst-case stop-first rule applied and labelled) [FP 14]
- [ ] K-31 Trade Monte Carlo methods: shuffle, resample, block bootstrap, trade skip; 250, 1,000 or 2,500 runs; caveat "bands are not limits" (partial: trade Monte Carlo, ruin and streaks built; method list not verified) [FP 5]
- [ ] K-32 Confidence-level table at 80, 90, 95 and 99 percent for the trade Monte Carlo [FP 5]
- [ ] K-33 Warnings card: look-ahead suspicion, fewer than 30 trades, top trade above 20% of profit, parameter at range edge, costs above 50% of gross, survivorship note, data gaps (partial: few-trades label and K-7 refusal exist) [FP 34]
- [ ] K-34 Run-ups table, mirror of the drawdown table (top 10: start, trough, recovery, length) [FP 71]
- [ ] K-35 Capital efficiency: cash idle %, gross and net exposure over time, margin used, buying-power headroom (partial: exposure over time exists; cash idle, margin and headroom open) [FP 71]
- [ ] K-36 Benchmarks: any symbol, a 60/40 blend, another strategy; alpha, beta, information ratio and tracking error against each (partial: SPY default; blends and extra metrics open)
- [ ] K-37 Report export: PDF or HTML tear sheet in a fixed order set in Library, with the Properties block
- [ ] K-38 Properties list: every setting used and the data version
- [ ] K-39 Tabs Orders, Positions and Exposure, Logs and Plots, Warnings, Code and Settings
- [ ] K-40 Customise: KPI set and order (shared with Backtest), tab order, default benchmark, report template, number formats, colour-blind palette
- [ ] K-41 Options-specific output: fill at mid with slippage per contract, Greeks, assignment events (not in v3: options are out of v3 (PAGES "Not in v3"))
- [ ] K-42 Unfilled limit orders card (needs limit orders from Build B-12)
- [x] K-43 Hero: net return vs benchmark, drawdown shading, hold-out boundary line
- [x] K-44 Cost ladder 1×, 2×, 4× beside the hero
- [x] K-45 Tabs Overview, Trades, Returns, Risk, When, Names, Paths
- [x] K-46 Timeline: regime strip under the equity curve
- [x] K-47 Conditions table: market trend, volatility, drawdown known the night before
- [x] K-48 Holdings: P&L treemap by name and names held over time
- [x] K-49 Rule check: target, daily loss, max drawdown and min days from every monthly start (ring and table)
- [x] K-50 Start-date card: CAGR by start date with the My limits pass marked
- [x] K-51 Survivorship delta: delisted names kept vs survivors only
- [x] K-52 Capacity card: one number, impact curve in Table view
- [x] K-53 Seasonality: month-of-year hit rate
- [x] K-54 Names: per-name results and top contributors
- [x] K-55 Ruin table: P(drawdown above each threshold)
- [x] K-56 Losing streaks: 95th percentile
- [x] K-57 When tab: return and Sharpe per regime, trades per regime beside each bar

## Optimise (`/studio/optimise`, spec §4): 18 / 40 done

### Acceptance (PAGES)

- [x] O-1 Planted spike strategy reports "spike only"; planted plateau reports a plateau
- [x] O-2 1,000-cell sweep on one symbol under 10 s
- [x] O-3 Sweep adds trials equal to cells run; effective count smaller for neighbours
- [ ] O-4 Cancel stops compute within 2 s and keeps finished cells
- [ ] O-5 Screenshots of Map, Surface and Top sets

### Target additions (FEATURES_PEAK)

- [ ] O-6 Setup sheet: parameter checkbox, min, max, step, scale (linear or log), type, "link to" (slow > fast + 5), live count of combinations with runtime and cost estimate (partial: step count, log scale and link rule exist; checkbox sheet and estimates open)
- [ ] O-7 Objective builder: several objectives from any stat or expression (sharpe - 0.5 × max_dd), direction, weights; penalty rules (fewer than 100 trades is invalid); Pareto for 2 or 3 (partial: objectives, link and constraints, Pareto built; weights and penalties open) [FP 10]
- [ ] O-8 Search methods: grid, random, Sobol, Bayesian (default above 3 parameters), genetic (NSGA-II), CMA-ES, successive halving; plain advice in the picker (partial: grid, random and Optuna TPE built; Sobol, NSGA-II, CMA-ES and halving open) [FP 10]
- [ ] O-9 No cap on the number of optimised parameters (checked above 3) [FP 10]
- [ ] O-10 Budget: max runs, max minutes, early stop after N runs with no improvement; cost and time estimate before launch (partial: time budget exists; max runs, early stop and estimate open)
- [ ] O-11 Data split in Optimise: in-sample, hold-out or walk-forward; out-of-sample shown beside each row; hold-out hidden from the objective (partial: walk-forward and sealed hold-out in Validate; no split in Optimise)
- [ ] O-12 Results table: every stat, in-sample and out-of-sample columns, rank, stability score, robust flag; sort, filter, column picker, CSV (partial: top sets table exists; columns, filter and CSV open)
- [ ] O-13 Heat map for any two parameters with a chosen stat; click a cell to open its run; contour smoothing toggle; overlay flags peaks without plateaus (partial: heat map and plateau outline built; click-to-run and contour toggle open)
- [ ] O-14 Pick-plateau tool: drag-select a region; returns the median parameter set and spread; runs that set (partial: plateau centre sent to Build; region select open) [FP 11]
- [ ] O-15 Parallel coordinates view for more than 3 parameters [FP 72]
- [ ] O-16 Scatter of stat A vs stat B coloured by parameter; histogram of outcomes across all trials (what a random pick gives)
- [ ] O-17 Controls: pause, resume, cancel, clone with changed ranges, zoom in on a selection, save sweep as template, pin best (partial: cancel built (test O-4 open); others open)
- [ ] O-18 Top sets: click a row to backtest that set (partial: top sets built; click-through not verified)
- [ ] O-19 Budget awareness: deflated-Sharpe hurdle shown before running, rising as the grid grows
- [ ] O-20 Warning when the best parameters sit at a range edge; plateau recommended over peak
- [ ] O-21 Cache: identical code, parameters and data are never rerun
- [ ] O-22 Custom objective in Python: def objective(result) -> float
- [ ] O-23 Use all local cores, with an estimated time before the run starts
- [ ] O-24 Walk-forward optimisation entry point in Optimise: each window re-optimises; out-of-sample periods stitched (partial: built in Validate; Optimise entry point open) [FP 72]
- [x] O-25 Custom objective written as a formula over metrics (sharpe - 0.5 × max_dd), available on every page [FP 72]
- [x] O-26 Constraints: min trades, max drawdown; excluded cells counted [FP 10]
- [x] O-27 Stability score from the neighbourhood (gauge and histogram); plateau vs spike call [FP 11]
- [x] O-28 Send the plateau centre to Build as a new version (adds to the ledger)
- [ ] O-29 Customise: default method, objective, split, max workers, auto-run Validate on the top 5
- [x] O-30 Trial counter feeding deflated Sharpe in Validate, shown on the page
- [x] O-31 3D surface (Plotly), off by default
- [x] O-32 Log-scale parameters
- [x] O-33 Time budget on a sweep
- [x] O-34 Spread of plateau equity curves, best one bold
- [x] O-35 Parameter map fills in as cells finish (every 5th cell)
- [x] O-36 Pareto front view
- [x] O-37 Parameter importance bars
- [x] O-38 Top 20 sets table
- [x] O-39 Trial cost under the hero: "this sweep added N raw, M effective trials"
- [x] O-40 Link rule between two parameters (fast < slow)

## Validate (`/studio/validate`, spec §5): 18 / 50 done

### Acceptance (PAGES)

- [x] V-1 Planted overfit strategy gets D or F with luck named; robust trend fixture gets A, B or C
- [ ] V-2 Verdict computed on the server; a posted modified result changes nothing (API test) (partial: server-side grade built; API test not done)
- [x] V-3 Re-running Certificate on the same version reproduces the hash
- [x] V-4 Opening the hold-out writes a look with actor, time and version; UI count equals the log
- [x] V-5 Agent token cannot open the hold-out a fourth time without human approval (API test)
- [ ] V-6 Power card: planted Sharpe 0.5 detection rate within 5 points of a direct simulation (partial: power card built; simulation check not recorded)
- [x] V-7 Editing weights recomputes the grade without a job
- [x] V-8 Strategy with 12 trades is skipped on walk-forward and the grade cap is shown
- [ ] V-9 Tiles flip one by one during a run (screenshot sequence at 3 timestamps)
- [ ] V-10 Quick profile finishes under 10 s on a single-symbol 10-year daily strategy

### Target additions (FEATURES_PEAK)

- [ ] V-11 Scorecard: each test Pass, Warn or Fail with threshold, actual number, one-line reason and link; weakest test highlighted; thresholds editable per user or team as a validation policy (partial: one server grade with reasons and editable weights; per-test rows open) [FP 3]
- [ ] V-12 Profiles Quick (under 10 s), Standard and Full, each a saved list of tests and pass bars in Library; one-click run and a custom checklist
- [x] V-13 Walk-forward anchored or rolling, with purge and re-optimise on or off [FP 4]
- [x] V-14 Stitched out-of-sample periods from walk-forward; efficiency; windows table [FP 72]
- [ ] V-15 Randomised out-of-sample blocks
- [ ] V-16 k-fold by time blocks with purge and embargo (partial: CPCV paths built; k-fold by time blocks not separate)
- [ ] V-17 Walk-forward matrix: 3D surface and the "k of n cells pass" rule (partial: matrix heatmap built; 3D surface and k-of-n rule open) [FP 4]
- [ ] V-18 White's reality check or SPA test
- [x] V-19 Price-path robustness: noise, vs random, vs shifted starts, vs other names, permutation (MCPT) [FP 6]
- [ ] V-20 Noise test shows band width, not only pass or fail (partial: noise test built; band display not verified) [FP 6]
- [ ] V-21 Synthetic price paths: block bootstrap and GARCH
- [ ] V-22 Trade-list Monte Carlo in Validate: reshuffle, resample, random trade skip, randomised exits, variance test; confidence table 80, 90, 95, 99 [FP 5]
- [ ] V-23 Delayed entry at 1, 2 and 5 bars (partial: delay 1 and 2 built; 5 bars open)
- [ ] V-24 Cost stress 1× to 3× with the break-even marked (partial: 2× and 3× and break-even built; full 1× to 3× sweep open)
- [x] V-25 Liquidity cap as a share of volume
- [ ] V-26 Partial fills, spread widening and missed fills
- [ ] V-27 Parameter permutation grid around the chosen values; % change randomisation with probability and max change; sensitivity plot; Taguchi; plateau width (partial: share of nearby settings profitable built; permutation, Taguchi and sensitivity plot open)
- [ ] V-28 Regime tests: performance by regime, worst regime, rolling consistency, year-by-year table [FP 73]
- [ ] V-29 Pass bars must hold in each regime, not only on average [FP 73]
- [ ] V-30 Sanity: look-ahead re-run on truncated data and compare signals; single-trade dependence; data-leak scan [FP 8]
- [ ] V-31 Workflow chaining: run a chain on every strategy in a folder; auto-dismiss on fail; table of survivors
- [ ] V-32 Each test shows a chart, a table, a two-line "how to read this", simulation count, seed and runtime; re-run with more simulations; export
- [ ] V-33 Verdict is bound to the strategy version; a code change marks it stale and says so
- [ ] V-34 Same suite on a portfolio, including correlation stability
- [ ] V-35 Live gate: a deployment can require a minimum grade; override needs a typed reason in the audit log
- [ ] V-36 Simulations default 1,000, up to 100,000; fixed or random seed; compute budget
- [ ] V-37 Skip X% of trades test; per-trade slippage randomisation (from SQX)
- [ ] V-38 Higher-precision check: re-run on a different fill model
- [ ] V-39 Out-of-sample on unseen symbols: train on half the universe, test on the other half [FP 73]
- [ ] V-40 Customise: test list per profile, pass thresholds, which tests block the verdict
- [ ] V-41 Hold-out enforced at project or team level, not only per strategy (partial: sealed per strategy; project and team level open) [FP 12]
- [x] V-42 Deflated Sharpe on the effective trial count, carried from Optimise [FP 7]
- [x] V-43 Luck tests: luck lottery, deflated Sharpe, PBO with logit histogram, Harvey-Liu haircut, minimum track record, power card, CPCV violin [FP 7]
- [x] V-44 One verdict with a reason chain
- [ ] V-45 One-page PDF and /share/<token> link from the run header (partial: certificate with reproduce built; PDF and share link not in the DONE list; verify)
- [x] V-46 Robustness tiles: pass, fail, skipped, each with reason and threshold
- [x] V-47 Vs random: histogram of random strategies with the same trade count, holding time, stop and target; ours marked
- [x] V-48 Shocks: gap down 10%, volatility ×3, everything moves with the market (labelled synthetic)
- [x] V-49 Walk-forward efficiency, windows table with chosen parameters, drift line
- [x] V-50 Verdict: reason, cap at C on few trades, next test, what would change it (no tuning advice)

## Live (`/studio/live`, spec §7): 11 / 46 done

### Acceptance (PAGES)

- [ ] L-1 With data stale beyond 10 days the daily step refuses and writes nothing (partial: built to run anyway when data is red; spec says refuse (see OD-8))
- [ ] L-2 After a simulated new bar, fills at next open with the same costs as the backtest (vector engine test)
- [ ] L-3 Freezing stores spec, data version and seed; no Forward curve drawn before the freeze date (partial: freeze per version built (backdate labelled); test not recorded)
- [ ] L-4 Drift alert fires on a planted series and appears in the feed and in the digest (partial: drift and alerts built; digest not built)
- [x] L-5 Reconcile on an imported CSV matches hand-built counts on a 10-trade fixture
- [x] L-6 A newer version starts a new segment; the old record stays under the old version
- [ ] L-7 Alert quota and channel verification visible; failed webhook shows status and retry (partial: failures logged and test send built (L-7 tested); quota and retry open)
- [ ] L-8 Screenshots at 390 px (Today and Forward) and 1440

### Target additions (FEATURES_PEAK)

- [x] L-9 Forward equity with the backtest Monte Carlo band (expectation ± band) and drift [FP 15]
- [ ] L-10 Divergence monitor: live vs backtest on the same period; missing and extra signals; fill slippage; threshold alerts (partial: reconcile vs model built; monitor and threshold alerts open) [FP 15]
- [ ] L-11 Shadow book: the frozen version keeps running on fresh data next to paper; per-trade explanation of drift (slippage, cost leak, missed signals) [FP 75]
- [ ] L-12 Cost leak: paper costs vs backtest, daily line
- [ ] L-13 Signal health: signal rate vs backtest, rule value distribution vs history, rank IC vs backtest mean
- [ ] L-14 Decay clock: time to catch a dead edge and time to 80% power; F key freezes
- [ ] L-15 Deployment wizard: version, mode (signals, paper, live), account, capital and size scale, risk limits, schedule, alert rules, diff vs backtest assumptions, typed confirmation; saved as a deployment record
- [ ] L-16 Signals-only mode: each signal (symbol, action, size, reason) to the feed, email, push or webhook; "signal valid until"; "I took it" or "skipped" tracking [FP 20]
- [ ] L-17 Paper records slippage observed vs the model and latency (partial: paper on the same fill model; slippage vs model report built; latency open)
- [ ] L-18 Layout: deployments list left, today dashboard centre, orders and alerts right
- [ ] L-19 Dashboard: positions (qty, avg, mark, P&L, % of book), open orders, fills, P&L today, week and total with the backtest band, exposure, margin, heartbeat, last data tick, next scheduled event, log tail, strategy variables (partial: today, forward band and fills exist; positions with mark, heartbeat, log tail and variables open)
- [ ] L-20 Kill switches: pause entries, flatten all, halt strategy, halt account (one confirm); automatic triggers for max daily loss, max drawdown, stale data, broker mismatch, with confirmation levels [FP 17]
- [ ] L-21 Crash recovery: persisted strategy state; restart reconciles positions; a mismatch pauses and asks [FP 18]
- [ ] L-22 Reconcile: four-question table (same trades %, fill difference, residue, volatility) and real trades on the chart (skipped and taken signals) (partial: CSV match and fills vs model built; four-question table and chart overlay open)
- [ ] L-23 Promotion gates: Backtest, Validate, Paper, small live, Live; editable checklist (min trades, min paper days, max divergence); Forward needs a version graded at or above the gate [FP 16]
- [x] L-24 Order CSV for manual brokers (orders sheet)
- [ ] L-25 Manual order ticket with pre-trade checks; full order lifecycle with reject reasons (owner decision: live order entry, see OD-6)
- [ ] L-26 Broker adapters (IB, Alpaca, Tradier, Schwab, Tastytrade, crypto): connection status, permissions, balances, reconnect and disconnect events (owner decision: live broker trading is not in v3, see OD-6) [FP 19]
- [ ] L-27 Alert rule builder: drawdown beyond limit, order rejected, data lag, no signal for 3 days, heartbeat lost, drift beyond band, signal, fill (partial: Apprise channels and test send built; rule builder open) [FP 21]
- [ ] L-28 Webhook templating ({{symbol}} {{action}} {{qty}}), channel routing per severity, quiet hours, escalation (unacknowledged for 10 min goes to SMS), acknowledgement history [FP 21]
- [ ] L-29 Channels: email, push, Telegram, webhook JSON; quota per alert shown (partial: Apprise channels; push and Telegram not verified)
- [ ] L-30 Strategy-defined alerts: ctx.alert(text, level, channels)
- [ ] L-31 Daily digest after the data load (email or push): signals, positions, equity, drift
- [ ] L-32 Runs after the daily data load (blocked by data: daily update job not built (phase 9))
- [ ] L-33 Phone first: today actions on one screen; swipe between tabs; tap a signal for QuickLook
- [ ] L-34 Live run history: each live day as a result page comparable to the backtest
- [ ] L-35 Change control: deploy a new version with code and parameter diff; apply at the next bar; one-click rollback; audit log
- [ ] L-36 Customise: default risk limits per account, alert rule template, channel routing, dashboard widgets, timezone, sound, drift band width, broker per strategy, digest contents and time, units
- [ ] L-37 Stale-data guard: Today and Forward do not compute when data ends before today; no zero-return days written (blocked by data: data ends 2026-02-01; see OD-8)
- [ ] L-38 Agent API: get_signals; freeze_paper needs a human click
- [ ] L-39 Map: universe as dots, names that fire lit, sortable
- [x] L-40 Today: signals table (symbol, action, value, distance to trigger, size)
- [x] L-41 Near triggers table
- [x] L-42 Orders sheet: copyable text and CSV
- [x] L-43 Ledger fills with the same fill model and costs as the backtest
- [x] L-44 Health: drawdown odds at the backtest Sharpe and at half
- [x] L-45 Freeze per version (backdate labelled); a new version starts a segment
- [x] L-46 Alerts: Apprise channels, test send, digest on run, failures logged

## Chart (`/studio/chart/:symbol?`, spec §8): 6 / 35 done

### Acceptance (PAGES)

- [ ] C-1 Every chart indicator matches the backend formula within 1e-6 on a fixture (partial: EMA seeds differ in the first bars (registry seeds with an SMA))
- [ ] C-2 Chart, Backtest and Live read the same close for the same symbol and date
- [ ] C-3 10 years daily plus 3 indicators first paint under 400 ms
- [ ] C-4 Clicking a trade in Backtest opens Chart zoomed to that trade with its stop and target (partial: name link and trade navigator (±20 bars) built; stop and target on this view not verified)
- [ ] C-5 Replay at 20× holds 60 fps on 5,000 bars (Playwright frame sample) (partial: replay 1×, 5×, 20× and scrub built; frame test not done)

### Target additions (FEATURES_PEAK)

- [ ] C-6 Layouts of 1, 2, 4 (and 6, 9) charts with synced symbol, crosshair and time; each sync toggled [FP 45]
- [ ] C-7 Compare symbols as rebased % lines or indexed to 100
- [ ] C-8 Price scales: linear, log, percent, indexed to 100
- [ ] C-9 Chart types: hollow, OHLC bars, Heikin-Ashi, line, area, baseline, Renko, range, Kagi, Point and Figure, volume footprint, step (partial: candles only)
- [ ] C-10 One chart engine on every page (Backtest, Live, Library, Build preview); WebGL; 1M bars smooth; decimation above 50k points (partial: one engine on the Chart page; WebGL and 1M bars not built) [FP 45]
- [ ] C-11 Indicator popup with Inputs, Style and Visibility tabs; apply to the selected pane; indicators on indicators; templates; favourites (partial: indicators editable and kept per user; tabs, templates and favourites open)
- [ ] C-12 Indicator lab: pick an indicator, symbol and range; tune with sliders; the chart updates live with no backtest [FP 44]
- [ ] C-13 Formula-to-indicator pane: any formula string becomes a pane, so Build and Chart share one language [FP 76]
- [ ] C-14 Strategy overlay: entries and exits, stop and target lines, position shading, signal pane; two strategies at once (partial: one run: entries and exits; stop and target lines, shading and two-strategy overlay open) [FP 48]
- [ ] C-15 Click a trade marker for a card: why it fired, with the rule values at that bar [FP 48]
- [ ] C-16 Drawing tools (trend line, ray, horizontal, channel, Fibonacci, pitchfork, rectangle, text, arrow, measure, position tool, anchored VWAP); magnet to OHLC; lock, hide, group, clone; saved per symbol on the server [FP 46]
- [ ] C-17 Drawings convert into alerts and block conditions ("price crosses the line") [FP 46]
- [ ] C-18 Alerts created on the chart use the alert engine; right-click price to alert when it crosses; indicator and drawing-touch alerts
- [ ] C-19 Replay: speeds to 50×, step forward and back, jump to date, blind replay (hides future bars and ticker), simulated orders and P&L (partial: 1×, 5×, 20× and scrub built; 50×, blind replay and simulated orders open) [FP 47]
- [ ] C-20 Strategy-stepped replay: orders appear bar by bar with the debugger [FP 47]
- [ ] C-21 Manual trading in replay, recorded to a journal (owner decision: manual replay and journal are not in v3, see OD-7)
- [ ] C-22 Data window: crosshair readout of every series; legend values [FP 29]
- [ ] C-23 Screenshot as PNG (watermark off) and export of the data in view
- [ ] C-24 Spread charts: ratio A/B and a correlation panel
- [ ] C-25 Events layer: earnings, splits, economic releases, news; regime shading and strategy trades layers (blocked by data: no dividend, economic or news feed held)
- [ ] C-26 Automated analysis (trendlines, support and resistance, patterns) labelled as heuristics; reproducible code; can become a block
- [ ] C-27 Customise: colours per theme, font size, crosshair style, price scale side, saved layouts and templates per symbol or global, a key per tool
- [ ] C-28 Pan and zoom at 60 fps with 5 indicators on 100k bars; first paint under 1 s
- [x] C-29 Timeframes: daily, weekly and monthly (hourly removed by decision)
- [ ] C-30 Keys and buttons: R replay, ← → trades, G from Backtest, drawing toolbar with the 12 most used, ⌘K add indicator (partial: R, ← →, trade navigator and G built; toolbar and ⌘K open)
- [x] C-31 Candles, volume pane and indicator panes on lightweight-charts 5
- [x] C-32 All 70 chart_engine indicators usable; editable parameters kept per user
- [x] C-33 Trade navigator: ← → steps, zoom to trade ±20 bars
- [x] C-34 Replay: R key, 1×, 5×, 20×, scrub
- [x] C-35 Studio Chart embeds the full chart_engine chart

## Library (`/studio/library/:section?`, spec §9): 0 / 36 done

### Acceptance (PAGES)

- [ ] Y-1 Custom metric cagr / ulcer works as a KPI, a table column, an Optimise objective and a My limit
- [ ] Y-2 Data audit counts equal a direct parquet query on the fixture
- [ ] Y-3 Exported profile imports on another account and reproduces the same Backtest
- [ ] Y-4 Screenshots at 1440 and 1024

### Target additions (FEATURES_PEAK)

- [ ] Y-5 Universe types: static list, index members (point in time), screen rules, ETF holdings, top N by dollar volume, crypto pairs, option chains, custom Python [FP 39]
- [ ] Y-6 Universe detail: preview table, count over time, turnover, survivorship status, data coverage, rebalance frequency, min price and ADV filters, ban list; point-in-time badge [FP 39]
- [ ] Y-7 Universe versions frozen; a run pins the universe version it used [FP 39]
- [ ] Y-8 Cost presets: US retail, IBKR fixed and tiered, zero commission with spread, futures CME, crypto spot and perpetual, FX retail, options per contract, custom [FP 40]
- [ ] Y-9 Every profile dated with an effective-from date; India STT only after coverage is measured (blocked by data: India coverage not measured)
- [ ] Y-10 Compare a cost profile's impact on a strategy in one click [FP 40]
- [ ] Y-11 Custom Python cost model; assigned per strategy or asset class; stored in the run record [FP 40]
- [ ] Y-12 Benchmarks: symbols, blends (60/40), own CSV
- [ ] Y-13 Blocks and indicators: reusable rule groups and formula indicators shared with Chart and Screener
- [ ] Y-14 Indicator registry browser: formula, plot, reference, default parameters, optimisation range, warm-up, speed tag; "try on chart"; deprecation notes; 150+ indicators (partial: 70 chart indicators in the registry; browser and 150+ open) [FP 43]
- [ ] Y-15 Custom indicator as a Python function with @indicator(inputs, outputs, warmup) and optional jit=True; appears in blocks and formulas
- [ ] Y-16 Regimes and crises: custom regimes by formula; extra dated crisis windows from 2015
- [ ] Y-17 Per-run data quality report: missing bars, stale prices, zero-volume bars, outliers, survivorship note; failing quality shows as a warning on the result [FP 41]
- [ ] Y-18 Data catalog: symbols, first and last date, gaps, adjustment status, source, last update; click to preview [FP 41]
- [ ] Y-19 Custom data: upload CSV or Parquet (500 MB per dataset), column mapping wizard, versioned, used as ctx.data("name")
- [ ] Y-20 Fundamentals with ctx.field(symbol, field), point in time (blocked by data: fundamentals from 2021 with a 90-day lag)
- [ ] Y-21 Corporate-action switch: adjusted, raw, total return; a badge on each result (blocked by data: mixed adjustment; no dividend column until phase 9)
- [ ] Y-22 CSV bars and trades: column mapping, timezone, adjustments, per-row errors, saved import profiles
- [ ] Y-23 Composer and QuantMage JSON mapper; untranslated parts listed
- [ ] Y-24 TradingView trade export CSV
- [ ] Y-25 Trade list import run through Validate (external strategy)
- [ ] Y-26 Broker statements to compare live with expected
- [ ] Y-27 Agent definitions: name, instructions, tools allowed, budget, model, schedule, run history with cost; no live-order tool; tokens and scopes (partial: actor log and 3-look hold-out budget built; definitions, tokens and scopes open) [FP 57]
- [ ] Y-28 AI experiment agent: variants run as branches under a budget (owner decision: AI features, see OD-11) [FP 56]
- [ ] Y-29 Sharing: private, team, link; fork and merge upstream updates [FP 58]
- [ ] Y-30 Projects marked as library: imports pinned by version; auto docs from docstrings; examples tested on each publish [FP 58]
- [ ] Y-31 Template gallery: at least 30 vetted templates, each with expected stats on a fixed period and known weaknesses (partial: 20 templates exist; expected stats and weaknesses open) [FP 58]
- [ ] Y-32 Search across the Library with tags, owner, version and usage count ("used by 7 strategies")
- [ ] Y-33 Custom blocks from a Python function, shown in the palette with an icon and parameter form
- [ ] Y-34 Customise: default universe, cost profile, data source per asset class, pinned items, import defaults
- [ ] Y-35 Profiles: validation, report order, default sizing, workspace layout; export and import JSON
- [ ] Y-36 Data section shows the phase 0 audit live (symbols per year, bars per symbol, gaps, adjustment, freshness)

## Cross-page (`all`, spec §10): 2 / 58 done

### Acceptance (PAGES)

- [ ] X-1 Every page has a Playwright screenshot at 1440 and 1024, dark and light; Live also at 390
- [ ] X-2 Every page has empty, loading, error and skipped state tests
- [ ] X-3 The same strategy through the UI and the agent API gives the same hash
- [ ] X-4 A shared link opens read-only, shows the hash, and Reproduce matches
- [ ] X-5 Changing a Library cost profile marks dependent runs stale
- [ ] X-6 No page sends a computed result to the server for certification (API test)
- [ ] X-7 Old route /trade redirects to Chart; old Studio routes redirect to the nearest new page (owner decision: /trade is a multi-tab trading page; redirect is an owner decision, see OD-5)
- [ ] X-8 rg finds no import of removed Studio modules (partial: old Studio code removed (commit e778120); rg check not recorded)

### Target additions (FEATURES_PEAK)

- [ ] X-9 Reproduce button on every result: re-runs on the server and matches the stored hash [FP 1]
- [ ] X-10 One engine and execution model for backtest, paper and live; paper vs backtest divergence report (partial: vector and event engines share one fill model; paper and live divergence report open) [FP 2]
- [ ] X-11 Compare any two runs, versions or strategies (up to 8 in Portfolio): settings changed, winner per row, overlaid curves, code diff, execution model diff (partial: RunCompare reused; version diff shows results side by side; general compare open) [FP 33]
- [ ] X-12 Command palette ⌘K over every page, strategy, template, setting and action; rebindable; pin favourites (partial: ⌘K app search and Build palette (⌘⇧P) exist; spans all pages open) [FP 49]
- [ ] X-13 Keys: ⌘↵ run, ⌘S save, [ ] tabs, C compare, R replay, T trades, G chart, F freeze, / search, Esc closes drawers (partial: some keys built; the rest open)
- [ ] X-14 Remappable keybindings: search, record chord, conflict warnings; presets VS Code, Vim, Emacs, JetBrains, Sublime; export and import JSON [FP 50]
- [ ] X-15 Cheat-sheet overlay (?) with context shortcuts; every toolbar tooltip shows its shortcut
- [ ] X-16 Settings in three levels (user, strategy or project, run or workspace); search; sync per user; admin locks; each setting shows its source, default and reset [FP 51]
- [ ] X-17 Themes: light, dark, high contrast; import a VS Code theme JSON; separate chart theme; colour-blind safe preset
- [ ] X-18 Dockable layouts with presets Write, Test, Debug, Review; zones collapse and resize; zen mode ⌘K Z; default by width (Test above 1280 px, else Write) [FP 52]
- [ ] X-19 Phone layout for every page except Live: bottom nav, settings sheet, card rows
- [ ] X-20 Mobile read view: Home, Live dashboard, alerts and kill switch; no editing
- [ ] X-21 Share link: read-only; expiry and revoke; hides code if chosen; never private preferences
- [ ] X-22 Export: CSV of every table, trades CSV, equity CSV, PNG and SVG of charts, one-page PDF, full report PDF, spec as JSON and as Python
- [ ] X-23 Embed: hero and verdict chip
- [ ] X-24 Audit log of who changed, ran and deployed what, filterable and exportable; roles viewer, commenter, editor, owner (partial: actor log for agent calls built; audit page and roles open) [FP 59]
- [ ] X-25 Comments anchored to lines and to chart bars; resolvable threads; mentions [FP 59]
- [ ] X-26 Notification centre: run complete, validation done, optimisation finished, live alerts, comments; channel per type
- [ ] X-27 Compute manager: queue of running and waiting jobs with cancel, priority, time and cost estimate, quotas (partial: shared JobStore jobs API; queue view and quotas open) [FP 60]
- [ ] X-28 Streaming results with cancel that keeps partial results, marked partial; runs continue when the tab closes; notification when done (partial: Optimise map fills live; partial-result save and notification open) [FP 60]
- [ ] X-29 Why a run was stopped (timeout, memory, handler too long) with a fix tip
- [ ] X-30 Budgets as Playwright checks under frontend/e2e/perf: compile under 100 ms, preview under 300 ms, one symbol 10 years under 1 s, 500 names under 5 s, 1,000 cells under 10 s, 10k-row trade list median ≤ 16.7 ms, chart first paint under 400 ms, click to paint under 70 ms, Validate quick under 10 s (partial: compile (0.26 ms) and 1,000-cell sweep measured; the rest open)
- [ ] X-31 Editor ready under 1.0 s; keystroke to diagnostics under 300 ms; quick run (50 symbols, 5 years) under 8 s; full run (500 symbols, 10 years, portfolio) under 30 s; debugger step under 100 ms; 50k log rows at 60 fps
- [ ] X-32 Keyboard-only flows; screen-reader labels; a table alternative to every chart; colour-blind palettes; reduced motion (replay shows a still frame)
- [ ] X-33 Onboarding: a sample strategy per mode and a 5-minute guided path Build, Backtest, Validate, Paper; tips shown once
- [ ] X-34 Left nav: dot on fresh unseen runs; collapses to icons
- [ ] X-35 Strategy picker in every run header; switching keeps the page
- [ ] X-36 Shared pieces: limits pill, freshness pill, My limits strip, trial chip, verdict chip, stale marker (partial: trial chip built; other pieces open)
- [ ] X-37 Hero kinds fan, heatmap, tiles, gauge and grade in modules/research/Hero.tsx
- [ ] X-38 Reset to default on every control; "Customised" marker on changed inputs
- [ ] X-39 Agent API: list_templates, compile, backtest, optimise, validate, get_verdict, get_ledger, get_signals, get_data_audit, open_holdout, freeze_paper; typed spec and verdict in every response (partial: compile, backtest, optimise, validate, get_verdict, get_ledger, get_data_audit, open_holdout built; list_templates, get_signals and freeze_paper open)
- [ ] X-40 Guard rails: the effective trial count applies to agents; no endpoint sorts strategies by backtest return; freeze and certify need a human click (partial: look budget and actor log built; sort guard and freeze click open)
- [ ] X-41 One alert engine for Chart, Live and Library: email, push, Telegram, webhook JSON; quota per alert; webhook failure shows status and retry time; quiet hours per strategy (partial: Apprise engine built for Live; quota, retry time and quiet hours open) [FP 21]
- [ ] X-42 AI assistant: inline edit, explain an error, write a test strategy, critic citing lines and numbers; diff approval; logged to the actor log (owner decision: AI is optional and never sets a grade, see OD-11) [FP 55]
- [ ] X-43 Notebook tab sharing the data layer and engine: load_run, optimise helpers, ipynb import and export (owner decision: not in the 9-page spec, see OD-10) [FP 54]
- [ ] X-44 Engine targets: 10 years of daily data on one symbol under 1 s; parallel optimisation over all cores; cache keyed by data version and indicator parameters (partial: vector engine measured; cache and parallel optimisation partial) [FP 60]
- [ ] X-45 Avoid: results that cannot be reproduced, silent truncation, hidden fill and cost assumptions (partial: certificate hash in Validate; truncation rows and fill and cost labels open)
- [ ] X-46 Avoid: quotas that stop a run; decimate and show a truncation row instead (charts, logs, trades)
- [ ] X-47 Avoid: no verdict; one locked policy and one scorecard (partial: one server grade built; per-test scorecard open)
- [x] X-48 Avoid: intrabar guesswork; the stated worst case applies (stop fills first)
- [ ] X-49 Avoid: optimisers capped at 3 parameters, and runs that cannot be compared (partial: no cap in the code; comparability of runs not checked)
- [ ] X-50 Avoid: debuggers that need a breakpoint to start
- [ ] X-51 Avoid: two browser tabs editing one strategy
- [ ] X-52 Avoid: AI edits applied without lint, validation and diff approval (owner decision: applies once AI is built, see OD-11)
- [ ] X-53 Avoid: desktop-locked settings and results; results must be portable (export bundles open) (partial: web app; export bundles open)
- [ ] X-54 Avoid: block builders that hide lookback and rebalance assumptions (partial: What it does text and limits; lookback and rebalance per block open)
- [ ] X-55 Avoid: dated, dialog-heavy settings; one searchable settings model instead
- [ ] X-56 Avoid: live vs backtest divergence hidden by default; show it on Live (partial: reconcile shows divergence on request)
- [ ] X-57 Studio route /studio/[[...slug]] and nav (Home · Build · Test · Portfolio · Live · Chart · Library) (partial: route and nav built per DONE list; not verified in a browser)
- [x] X-58 Old Studio code removed (commit e778120); chart_engine kept

### Engine and backend foundations (built, phases 0 and 1)

- [x] ENG-1 One canonical services/shared/metrics.py; ML Sharpe, drawdown and equity import it
- [ ] ENG-2 Vector engine (numba): 500 names, 10 years under the 5 s budget (measured warm: load and signals 0.44 s, engine 0.009 s, 500 names × 3,319 bars) (partial: cold run not measured)
- [x] ENG-3 Event engine: trade-for-trade match with the vector engine (5 parameter sets, longs and shorts, 1e-9)
- [x] ENG-4 Shared fill model: next open default, same close (optimistic label), gap through stop fills at open, worse-first same-bar rule
- [x] FND-1 studio_v3 package: registry, manifest, jobs API /api/studio-v3/... on the shared JobStore
- [x] FND-2 /limits and /bars endpoints (one price source for every page)
- [x] FND-3 Strategy spec (pydantic) and compile from formula (shared signal_lang lifted to services/shared/formula/); look-ahead refused with line and token
- [ ] FND-4 Costs: commission, slippage, borrow, volume cap, delisting haircut (partial: dividends on shorts not charged (no dividend column until phase 9))
- [ ] FND-5 Sizing incl. risk per trade; exits incl. time stop, breakeven and scale out (partial: scale in and risk parity sizing open)
- [x] FND-6 Trial ledger with raw and effective counts
- [x] FND-7 Zero- or too-few-trade runs refused with a reason
- [x] FND-8 Hold-out boundary (last 20%) excluded from every Backtest series
- [x] FND-9 Agent API (REST and MCP) for compile, backtest, get_ledger, get_data_audit; actor log

## Data refresh (phase 9, after the whole build)

Until it lands, every result's limits popover states the data as it is (mixed adjustment, most tickers end 2026-01-28 to 2026-02-01, daily only).

- [ ] DR-1 Rebuild daily parquet from Yahoo period max: one total-return adjustment for OHLC, plus RawClose, Dividends, Splits; delisted names keep old rows; stage, validate, back up, swap
- [x] DR-2 Hourly parquet dropped 2026-11-16 (Studio is daily only; Yahoo keeps 730 days of hourly bars)
- [ ] DR-3 Daily update job (end-of-day append, same adjustment), logged; freshness date exposed (needed before Live is used for real)
- [ ] DR-4 Data audit: symbols per year, bars per symbol, rows / 252, gaps, adjusted status, delisted share, fundamentals lag (Y-2)
- [ ] DR-5 India and non-equity coverage measured; result written into PLAN §5.3

## LEAN parity (research/LEAN_PARITY.md §7, in order)

LEAN is the test oracle for engines, fills, costs and statistics. Each step: tests first (they fail), then the fix, then the CODE_STANDARDS gates, then commit. A step is done only when both engines pass its goldens. No golden is in the DONE list, so all steps are open.

- [ ] LP-1 Step 1 Harness: fixtures, to_lean.py, one buy-and-hold algorithm, lean backtest in Docker, golden JSON, parity.py; done when SPY buy-and-hold matches to the cent
- [ ] LP-2 Step 2 Fills and timing (LEAN rows 1-6, 12-14): signal, stop, target, gap and delisting templates on both engines
- [ ] LP-3 Step 3 Costs (rows 7-9): constant, volume-share and market-impact slippage; IB fees; integer shares and cash buffer
- [ ] LP-4 Step 4 Buying power and shorting (rows 10-11)
- [ ] LP-5 Step 5 Statistics (row 15) and benchmark: the full LEAN statistics block
- [ ] LP-6 Step 6 Indicators (row 19) checked against LEAN test data
- [ ] LP-7 Step 7 Portfolio, validate, optimise, live and Python runner (LEAN_PARITY §6)
- [ ] LP-8 Step 8 Data refresh link (§5) when phase 9 lands
- [ ] LP-9 After every module: review pass (CODE_STANDARDS audit, line-by-line correctness, edge-case tests, simplify, speed, record in CHECKLIST and DECISIONS)

## Owner decisions

Each needs an answer before the page it blocks. Defaults are in the text.

- [ ] OD-1 Pyodide (MPL-2.0) for an in-browser Python preview: default no
- [ ] OD-2 OpenBB licence conflict (Apache vs AGPL): default not used
- [ ] OD-3 arch licence file missing on GitHub: check before relying on it beyond the existing install
- [ ] OD-4 Pine import: only after the PineTS licence check (AGPL)
- [ ] OD-5 /trade: keep as its own multi-tab page, or redirect to Chart (X-7)
- [ ] OD-6 Live broker trading: adapters (IB, Alpaca, Tradier, Schwab, Tastytrade, crypto), live order entry and a real-money click. REVIEW §3 says not in v3; FEATURES_PEAK 19, Live pass A §G and pass B §24 want it
- [ ] OD-7 Manual replay and trade journal (REVIEW G2). FEATURES_PEAK pass B §5 and §25 want manual trades in replay recorded to a journal
- [ ] OD-8 Live when data is stale. CHECKLIST builds Live to run when red; DECISIONS says disable Today and Forward until the daily update job exists; L-1 says refuse. Pick one rule
- [ ] OD-9 Public sharing and a public gallery (REVIEW G4 not in v3); pass A §13 wants publish: private, team, link, public
- [ ] OD-10 Notebook tab (FEATURES_PEAK 54; pass A §11). Not in the 9-page spec
- [ ] OD-11 AI assistant, AI critic and AI experiment agent (FEATURES_PEAK 55, 56). The spec has only an optional AI reviewer (phase 6)
- [ ] OD-12 Options (pass A §C). REVIEW §3 says not in v3
- [ ] OD-13 Docker sandbox for Python: deferred (owner: keep for later); the locked child process stays
- [ ] OD-14 Intrabar fidelity: hourly removed, so the worst-case stop-first rule is the only fill rule until data exists. Confirm
- [ ] OD-15 Validate PDF and share link: CHECKLIST says built; the DONE list does not mention them. Confirm they exist before ticking
- [ ] OD-16 Multi-currency portfolio needs FX data; decide whether to measure FX coverage
- [ ] OD-17 Dividends on shorts stay off until phase 9 (DECISIONS)
- [ ] OD-18 Tax and wash-sale (REVIEW G10) is not in v3. Confirm it stays out
- [ ] OD-19 Tick data is not in v3 (REVIEW §3). Confirm it stays out
