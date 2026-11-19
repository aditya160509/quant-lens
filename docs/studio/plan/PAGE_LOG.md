# Page log

One entry per page when it closes: what shipped, what was checked, what is still open. Newest first. Counts come from `CHECKLIST.md`.

## Home (`/studio`): 12 / 25, in progress

### Decisions

- **QuantConnect import moved to Build (B-163).** An AST shim turned simple QuantConnect algorithms into Studio rules (indicators, set_holdings, liquidate; unconverted lines listed). Removed from Home on 2026-11-18: it covered only simple rule strategies, exits came out as `if_else(cond, 0, 1)`, and a competitor's name on Home was not worth a half-working feature. Comes back in the Python editor once Python strategies run, keeping the user's code instead of converting it to rules. The removed version is in commit `4651300`.

## Portfolio (`/studio/portfolio`): 25 / 28, closed 2026-11-18

### Shipped

- **Methods:** equal, inverse vol, risk parity, HRP, max Sharpe, max diversification, minimum variance, shrunk minimum variance, mean-variance with shrinkage, capped Kelly, member momentum, drawdown throttle, fixed.
- **Rebalancing:** fixed, quarterly, rotation, threshold (corridor and minimum trade).
- **Constraints:** max weight, max correlation, cash reserve, minimum members, per-symbol and per-sector caps, gross and net limits, leverage cap, ban list.
- **Sleeves:** enable, start date, volatility target, capital share; a saved book can be a member (`book_ids`).
- **Regime weighting** on a benchmark rule.
- **Risk tab:** diversification and stress, efficient frontier, share of risk, crisis windows, drop-one, capacity by sleeve, sector exposure, gross/net/beta/cash/margin on the last bar.
- **Correlation tab:** matrix, overlap, clusters, marginal contribution, 6-month rolling correlation, drawdown overlap.
- **Grade tab:** combined grade from the Validate tiles.
- **Paper tab:** freeze the mix as one paper book, netted orders for today, paper return and per-member attribution (`core/book.py`, `/api/studio-v3/books`).
- **Netting in execution:** `net_execution` charges cost on netted trades (approximate; scale-outs ignored).
- **Defaults:** Study rail › Defaults › Make these my defaults.

### Checked

- Real run on Trend 100 v1, RSI(2) dip v2, SMA cross v1: +98%, grade B, about 2.5–3 s.
- Paper book from 2025-06-01: +25.0%, Sharpe 2.16; test books deleted from the store.
- Netting on: saves about $24 a year on $100k (members rarely trade against each other).
- Browser at 1440, 1024 and 375 px, dark and light; no horizontal overflow; console clean apart from an unrelated 402.
- Screenshots: `docs/studio/screens/portfolio-1440.png`, `portfolio-1024.png`.
- 100 backend tests in `tests/test_studio_v3_*.py`; ruff and tsc clean.

### UI guide and canon pass

Fixed on this page; the shared ones apply to every Studio page:

- Open tab kept in the URL (`?tab=`), restored on refresh (shared `FeatureView`).
- No entrance motion: hero figure and lines, result fade, card stagger on tab switch, panel slide on load (shared).
- Hero lines were cut short by a `pathLength` animation under `non-scaling-stroke` (shared `Hero`).
- Feature header wraps tools under the title when the centre column is narrow (shared).
- Inspect rail opens with its outputs list instead of an empty panel (shared).
- KPI strip fits four in one row (shared `.kpis`).
- Grade shown once: the verdict chip is hidden on Portfolio.
- Exposure, net and gross columns format as percent (shared `format.ts`).
- Paper view: no middle-dot meta string, spacing on the scale.
- Every menu trigger closes its menu on a second click (shared `PopMenu`); the inspector toggle no longer reopens itself mid-animation (shared `panels.ts`).
- One Run button: the header's hides on desktop while the inspector is open, and the inspector shows Run in both Study and Inspect.
- Tables stay tables down to 400px; label-value cards are for phones only.
- Symbol search is a full popup: company, type and exchange per row, exchange filters, several adds without closing, ticks on names already added.
- CAGR and volatility columns format as percent.
- Menus (View, More, dropdowns) measure themselves, stay inside the window and render at the shell root, so sticky bars never cover them (shared `PopMenu`).
- Cluster tree drawn sideways: names on the left, distance along the bottom, height from the leaf count (shared `Dendrogram`).
- Tables of 12 rows or fewer have no toolbar row; row hover covers the first column (shared `DataTable`).
- Sharpe, correlation and beta to 2 places; share columns (both active, overlap) as percent (shared `format.ts`).
- Chart drawing tools show on hover, focus or while in use (shared `TimeSeries`).
- Pair tables say Strategy and Paired with, not A and B.

### Next: table and chart pass on every card

- Line charts, bars and heatmaps against `UI_GUIDE.md` §5: axis ticks, legend placement, card spacing, chart heights; check each in the browser.
- Rolling correlation starts at 0 in 2016 because members have not traded yet; decide whether to start it at the first bar where every member has a position.

### Open

- **P-5:** page controls for sleeves (they are a JSON input today).
- **P-23:** asset class column (all data is US equity).
- **P-22:** multi-currency, blocked by data (no FX series).
- Headline Sharpe (0.60) and KPI Sharpe (0.595) round differently.
- "Combined vs each" card repeats the hero lines; kept for its axes and zoom.
- Opening an old run does not restore its strategy picks; Run then fails until they are ticked (the stale chip shows it).
- Sector exposure is rebuilt from trades and final weights, so it is approximate under quarterly, rotation and threshold rebalancing.
- Custom Python allocation function skipped.
- The netting measure without `net_execution` reads a position count, not per-symbol positions.

## Build backend (2026-11-18)

- B-58 shipped. B-53, B-59 and B-87 advanced. The Python preview captures per-bar logs and named plots, suppresses orders for the first `warmup` available bars per symbol, and returns source locations and user frames for runtime errors. The runner clamps history slices to the available prefix.
- `POST /api/studio-v3/preview` adds `logs` and `plots` on a Python success and `problem` on a Python runtime error. Existing fields are preserved.
- A 20-row compile took 0.9 ms on the local server. The real SPY Python preview took 3.07 s with 50 prefix replays, above the 300 ms target. Lint, completion and the 500-symbol backtest latency budgets remain unmeasured.
- Output is capped at 50,000 log rows plus a truncation row and 50,000 plot points. Debugger locals, automatic warm-up reporting, chart markers and tables remain open.
- B-60 shipped in the next increment. Python preview and full Backtest use the event engine, and `on_fill(ctx, fill)` receives the actual symbol, side, quantity, price, date and fee. The legacy one-argument callback also receives actual fills in these paths. B-64 advanced for simple Python strategies. Portfolio orders and the legacy signal consumers in Optimise, Validate and Live remain open.
- `POST /api/studio-v3/preview` returned actual SPY fill logs and 50 prefix comparisons in 323 ms on a warm server. Replays share the worker process. Full Backtest results carry Python logs and plots in `meta` through the existing `POST /api/studio-v3/feature/st01/jobs` route.
- Portfolio state and orders, imports, language services, project files, templates, debugger, indicator objects, remaining Build checks and QuantConnect import remain open.
- The full backend test suite stops on the missing Screener `cscv_pbo` import in `tests/test_shared_stats.py`. Repository-wide Ruff reports 1,157 findings. Ruff passes on the changed Python files.

- B-47 shipped. `on_data(ctx)` sees the run universe with current bars, immutable holdings and marked account state. B-43 advanced. The `rebalance` hook supports daily, week and month starts, every N observed sessions, and disabling the schedule. Calendar properties use observed sessions. Portfolio buy, sell, short and cover still use the sizing card. Explicit quantities, weights, limit and stop orders, and NumPy history remain open.
- The portfolio preview returned HTTP 200 on SPY in 755 ms from a cold server. The Studio suite passed all 128 tests.

- B-44 shipped. Portfolio Python supports explicit quantity and value orders, target weights, limit, stop and stop-limit orders, liquidation and cancellation. Orders share the event engine’s fill price and fee model. A new explicit order replaces the previous pending order for that symbol. Target weights use equity and close at submission. Intrabar stop-limit activation cannot take a same-bar limit fill when OHLC does not establish the order of touches.
- `POST /api/studio-v3/preview` returned actual SPY buy and sell fills for four shares in 596 ms on a cold server. The 300 ms target remains open.

- B-48 advanced and B-68 shipped. History windows expose the current observation at offset zero and past observations at negative offsets. Saved windows retain their original cutoff, and a future offset reports the offending token and user line. The runner keeps raw ndarray and DataFrame objects private.

- B-49 shipped. Python strategies can read the configured benchmark’s current close through `ctx.market.close`. Preview uses SPY, and unavailable observations return `None`. Portfolio mode provides the current OHLCV bar through `ctx.bar(symbol)`.

- B-114 shipped. `monthly(x)` uses the last available value from the preceding closed calendar month. Prefix tests verify that adding later bars leaves every earlier value unchanged. Hourly remains data-blocked.

- B-108, B-109, B-111 and B-116 backend diagnostics ship through `POST /api/studio-v3/build/condition`. It evaluates one formula or block expression over the symbol’s development data and returns true rate, most recent true date, all matching preview dates and a constant-condition flag. The visible interval is the last 730 days of development data. Frontend wiring remains open.

- B-117 backend ships in `POST /api/studio-v3/compile`. Complexity reports declared parameters, parsed formula conditions and independent referenced parameters with a variable optimisation range. Formula rules count Boolean leaves across entry, exit and market conditions. Score formulas and arbitrary Python control flow are excluded from the rule count.

- B-99 backend ships through the existing compile endpoint. It warns above 200 saved block rows or eight parameters with nonconstant optimisation ranges and rejects more than 1,000 block rows. Frontend wiring remains open.

- B-106 advanced. The formula catalogue exposes `for_bars`, `rising`, `falling`, `week_start`, `month_start` and cross-sectional `zscore`. All use the current and earlier observed bars. Earnings and fundamental filters remain open.

- B-51 shipped. Python portfolio strategies can rank a literal formula over observed symbols, filter by another formula, and choose top or bottom. `ctx.zscore` returns population z-scores by symbol, with no scores for a zero-variance or empty cross-section. The formula checker refuses future references before execution.

- B-61 advanced. Python event runs call `on_warmup_done` before the first eligible bar, `on_end_of_day` after the strategy’s bar handler and before order submission, and `on_stop` after the full run finishes. Shutdown orders cannot execute after the run. Risk-event callbacks remain open.

- B-53 advanced. Python preview and full Backtest report the configured warm-up and first order-eligible date. Per-symbol mode counts observed bars separately and returns a null date for an insufficient history. Portfolio mode counts run sessions. Automatic inference remains open.

- B-52 verified. The portfolio rebalance hook accepts daily, week, month, quarter and year starts, a positive number of observed bars, or None. Tests verify the hook and `ctx.rebalancing` agree across gaps and calendar boundaries.

- B-33 advanced via `POST /api/studio-v3/build/check`. The typed result includes sandbox and formula checks, direct nonnegative OHLCV indexes, undefined names and unused locals. Ruff supplies the last two checks when available; Studio checks remain active independently. Unreachable-order lint and editor wiring are open.

- B-32 advanced. `POST /api/studio-v3/build/complete` lists runner and Strategy members by scope and prefix. `POST /api/studio-v3/build/signature` returns an exact callable’s signature and documentation. Runner metadata comes from trusted classes, and local members come from static source inspection. Numerical library suggestions and editor integration remain open.

- B-22 advanced. `POST /api/studio-v3/build/definition` resolves local Python declarations from one-based editor coordinates. It uses Jedi if installed and a conservative top-level function and class lookup otherwise. Cross-file navigation and editor wiring remain open.

- B-31 backend ships through `POST /api/studio-v3/build/complete`. Formula suggestions include catalogue signatures, documentation and tab stops. Parameter and symbol suggestions use the editor’s supplied context, and history suggestions list supported OHLCV fields. Editor wiring remains open.

- B-62 backend ships. Literal Python `Strategy.params` tuples supply defaults and ranges to compile, `ctx.param` and the Optimise grid. Explicit saved parameter definitions take precedence. Optimise evaluates Python candidates through the event engine, with a real SPY test covering three distinct share quantities. Build frontend binding and nonliteral declarations remain open.

- B-59 backend ships. Python preview and Backtest expose plot placement, price-chart marks and structured table rows. Preview keeps its existing plot series and adds `plot_charts`, `marks` and `tables`. Marks and rows are capped at 5,000 each. Frontend rendering and sorting remain open.

- B-92 advanced. `GET /api/studio-v3/strategies/{id}/files` returns a saved project snapshot and optional per-file unified diffs. `PATCH` on the same route creates, saves, renames or deletes a file against an explicit base version. Existing code is exposed as main.py, and earlier versions retain their files. Helper imports, project execution and editor wiring remain open.

- B-92 backend now executes saved flat Python helper modules. Compile checks each source, and the worker resolves imports only against the supplied project. Formula literals in helpers participate in precomputation. Runtime diagnostics report the helper filename and line. Cross-file editor navigation and UI wiring remain open.

- B-22 advanced. Go-to-definition follows imports inside the supplied project and returns the target filename and position. The backend declares Jedi directly, and the endpoint validates project filenames before staging the analysis inputs. References, rename and editor wiring remain open.

- B-22 advanced. `POST /api/studio-v3/build/references` locates symbols across the supplied project. `POST /api/studio-v3/build/rename` previews the changed file contents without saving them. It accepts Python identifiers and restricts edits to supplied project files. Editor wiring and outline remain open.

- B-25 backend ships through `POST /api/studio-v3/build/outline`. It returns the active file’s classes, functions, nested methods and assignments from indicator or formula calls, with source spans. It uses static parsing and returns an empty outline while the file has a syntax error. Editor wiring remains open.

- B-33 advanced. The check endpoint accepts the active project document and validates imports against supplied helpers. Diagnostics carry the active filename. It flags direct context orders in literal dead branches and after unconditional control flow in the same block. Dynamic reachability and frontend debounce remain open.

- B-69 advanced. `POST /api/studio-v3/build/debug` replays Python source through the requested date and symbol, or steps one observed session forward or backward. The result includes bounded scalar state, current OHLCV, account values, accepted order intents and executed fills for the paused bar. It creates no saved run. Breakpoints, jumps to order or fill, and editor wiring remain open.

- B-69 backend now also jumps to the next order or fill for the selected symbol. The event engine stops after processing that bar and returns the same debugger snapshot as a date selection. Requests with no later activity return a 422 with a fix hint. Editor wiring and breakpoint controls remain open.

- B-70 advanced. The debugger accepts a file and line with an optional conjunction of date and symbol comparisons. It captures bounded locals before that line executes and returns the account and order snapshot after the same bar. Hit counts are computed by replay. Arbitrary expressions, equity breakpoints and editor wiring remain open.

- B-70 backend now includes an equity-loss trigger. Send `event: "equity"` and a positive `loss_fraction` to the debugger. It stops at the next eligible bar whose completed account equity meets the requested loss from the preceding session and returns the exact equity change. Editor wiring remains open.

- B-98 backend ships eight Python starters through the `python_templates` field of `GET /api/studio-v3/templates`. The existing formula catalogue stays available. The real-data acceptance test compiles and executes each starter with its suggested universe and verifies at least one trade. Gallery UI wiring remains open.

- B-50 advanced. `ctx.indicator` creates a current-bar handle from a literal formula or a supported indicator with a literal period. Handles expose readiness, value and bounded history. A portfolio handle can also feed cross-sectional ranking. Indicator calculations reuse the formula engine. LEAN golden-value verification remains open.

## Build backend (2026-11-18)

What shipped, by id:

- B-57 (partial), PYTHON_IDE A7. Python strategies may import `math`, `statistics`, `numpy`, `pandas`, `scipy.stats`, `from scipy import stats` and saved project modules. The allow-list is enforced twice: the AST screen refuses anything else with the module name and the allowed list, and the child process installs a restricted `__import__` that resolves only those names. `numpy.load`, `fromfile`, `memmap`, `ctypeslib`, `pandas.read_pickle`, `read_csv`, `to_pickle` and the other file-reaching attributes are refused by name, as are dunder attributes, `eval`, `exec`, `compile`, `open`, `globals`, `locals`, `getattr`, `setattr`, `type`, `input`, `breakpoint`, `global` and `nonlocal`. 44 known breakouts are parametrised and every one is refused; two run the child directly to prove the import gate holds past the AST screen. sklearn and scipy.optimize stay out: PYTHON_IDE A7 asks for the narrower list.
- B-50, A4. `ctx.indicator` handles and the LEAN-style `self.sma("SPY", 50)` / `self.sma(50)` form share one formula evaluation. EMA now seeds with the SMA and smooths with 2/(n+1); RSI and ATR use Wilder smoothing seeded with the mean of the first n; `std` is the population standard deviation, so `sma + k*std` is LEAN's Bollinger band. Tests pin each definition against a hand-computed sequence and check `ready` is false before the window is full.
- B-42. Server-side latency is measured in tests: lint p95 26 ms for 300 lines, completion p95 0.01 ms, compile p95 0.11 ms.
- B-65, A14. A Python portfolio strategy over 500 symbols × 2,500 bars runs in 0.55 s end to end (indicator precompute, sandboxed child, event engine). The test uses synthetic bars; real-data loading is not included.
- B-98. The eight Python starters are checked by the existing real-data test (each compiles and produces trades on SPY, QQQ and IWM).
- B-119. `POST /build/checks` returns warm-up bars and the first eligible date, the fields and windows each rule reads, the period, the universe with held and delisted names, and a survivorship row with a written note.
- B-120 (partial). Formula strategies gained `exits.opposite_signal` (a short entry closes longs and a long entry closes shorts) and `exits.end_of_week` (close on the last observed session of the week). The profit-target ladder and exit ordering are still open.
- B-163. `POST /build/import-quantconnect` rewrites a QuantConnect algorithm in place: `class …(QCAlgorithm)` becomes `class Strategy`, `Initialize`/`OnData`/`OnOrderEvent` become `init`/`on_data`/`on_fill`, and price, portfolio, order, history, log, plot and indicator calls map to `ctx`. It returns the symbols, capital, dates and warm-up it found, every rewritten line, and every line it removed or refused with a reason (QuantConnect imports, `datetime`, `Schedule.On`, `SetBrokerageModel`, unknown `On*` callbacks). Lines it cannot express are commented out, never silently dropped. The result is checked before it is returned, and the endpoint saves nothing.
- B-32 (partial). Completion covers the numpy and pandas top-level names with signatures and one-line docs, next to every `ctx`, portfolio, position, bar, fill, market, history and indicator member, and the eight LEAN-style indicator helpers in the `self` scope.

API added or extended (all under `/api/studio-v3`):

- `POST /build/checks` — warm-up, data used per rule, survivorship for the checks card. Body `{spec, settings?}`.
- `POST /build/import-quantconnect` — convert one QuantConnect algorithm; body `{source}`; returns `{ok, code, symbols, settings, warmup, converted, unconverted, problems}`.
- `POST /build/complete` — added the `numpy` and `pandas` scopes.
- `POST /build/check` — unchanged shape; import refusals now name the module and list the allow-list.
- `POST /preview`, `POST /build/debug`, `GET|PATCH /strategies/{id}/files`, `POST /compile`, `POST /build/condition` continue to serve the runner.

Budgets measured on this machine (server, warm):

- compile 20-row spec: 0.11 ms p95 (budget 100 ms).
- lint 300 lines: 26 ms p95 (budget 150 ms).
- completion: 0.01 ms p95 (budget 50 ms).
- Python backtest 500 × 2,500: 0.55 s (budget 20 s).
- `POST /build/checks` on SPY, 2015-01-02 to 2023-11-06: 0.19 s.
- `POST /build/import-quantconnect`: 67 ms.

Still open and why:

- B-57 full: sklearn and scipy.optimize are not allowed. They widen the sandbox surface (model fitting and optimisers read and write more of the interpreter) and PYTHON_IDE A7 lists the narrower set; adding them needs its own escape review.
- B-120: the profit-target ladder needs a second scale-out level in both engines; ordering rules need an explicit exit priority in the spec. Opposite-signal and end-of-week exits ship now.
- B-105/B-113: nested Any/All blocks and named formula variables are editor and parser work in the formula language; the formula AST already nests to any depth, so blocks that compile to formulas are not blocked by the backend.
- B-121: risk-parity sizing and hard per-position and gross caps need new engine parameters; equal weight, shares, cash, % equity, risk, vol target, Kelly and score exist.
- B-55 `ctx.store`, B-56 feature fitting, B-61 `on_risk_event`, B-63 engine settings from code, B-64 full Python parity, B-71 variable grid: not started.
- The frontend dialog for the QuantConnect import, the checks card rows and the numeric-library completions is wiring only; every response is complete without it.

Known limits:

- The importer handles the forms in its call table. A helper the algorithm calls that uses `self.Portfolio` in another method is converted; a `Symbol` built at runtime from a string variable is refused, because the symbol must be a literal to reach the universe.
- QuantConnect resolution other than daily is reported, not converted; Studio has daily bars only.
- `POST /build/checks` reports the warm-up of the formulas and the literal `warmup` class attribute. A Python strategy that builds an indicator from a variable period is not counted.
- `ruff format --check` does not pass on this repository baseline (43 pre-existing files, none of them changed here). `ruff check` passes on every touched file.
- `tests/test_shared_stats.py` fails to import on the baseline (`cscv_pbo` is missing from `screener_v2.core.backtest`), so the full suite is run with that module ignored.

## Build backend: risk, sizing and diagnostics (2026-11-18)

What shipped, by id:

- B-54, B-61. `spec.risk` carries `max_drawdown`, `max_daily_loss`, `max_position` and `max_gross`, each off at 0. Both engines check the drawdown against the running peak and the loss against the previous session at each close; on a breach every position is flattened at the next fill, working orders are cancelled, no new entry is taken and one risk event `{bar, kind, value, limit}` is recorded. `max_position` caps one name's notional at entry and `max_gross` caps total notional at entry. A Python strategy gets `on_risk_event(self, ctx, event)` once, with `kind`, `date`, `value` and `limit`. The vector and event engines are compared trade for trade on a breach.
- B-63. `Strategy` class attributes `fill`, `commission_bps`, `commission_share`, `commission_min`, `slippage_bps`, `slippage_range`, `borrow_bps`, `max_positions` and `leverage` override the run card. Only literals pass, ranges are checked and an unknown value is ignored. Preview and the Backtest report return `settings_overrides`, and the report's `fill_model` and `costs_off` describe the values actually used. The cost ladder still multiplies the code's cost values.
- B-120. A second profit rung: `exits.scale_at2` / `exits.scale_frac2` sells a fraction of what is left at its own level, then the final target closes the rest. Each rung fills at its own price when a bar gaps through both. Compile warns when the second level is set without a share or when it is not above the first; "What it does" names both rungs.
- B-38, B-40. Lint gained `hard-coded-symbol` (a literal ticker in a portfolio strategy that reads `ctx.symbols`), `print-in-loop`, `mutable-default`, `wall-clock` (`datetime.now`, `today`, `utcnow`), `network` (an `http://` or `https://` literal) and `unseeded-random` (`np.random` without a seeded `seed` or `default_rng`). `/build/checks` now returns `warmup_share` and `warnings`, including a warning when the warm-up needs the whole period.
- B-121 (partial). `max_position` and `max_gross` ship; an explicit inverse-vol risk-parity sizing mode is still open.

API changes (all under `/api/studio-v3`):

- `POST /preview` — adds `risk_events` and `settings_overrides`.
- `POST /build/checks` — adds `warmup_share` and `warnings`.
- `POST /build/check` — adds the six diagnostic codes above; shape unchanged.
- `POST /feature/st01/jobs` (Backtest) — `meta.risk_events` and `meta.settings_overrides`; `meta.fill_model` and `meta.costs_off` follow the code when it overrides the card.

Budgets measured on this machine (server, warm):

- lint 300 lines: 31 ms p95 (budget 150 ms), after the new diagnostics.
- compile 300-line strategy: unchanged, well under 100 ms.
- The risk checks are two comparisons per bar in both engines; the 500 × 2,500 Python run stays at 0.55 s.

Still open and why:

- B-121: inverse-vol risk parity across the candidates needs a new sizing mode in `fills.size_shares` and a volatility vector per candidate in both engines.
- B-105/B-113: nested block groups and named formula variables are formula-language and editor work; not started.
- B-55 `ctx.store`, B-56 feature fitting and sklearn, B-64 full Python parity, B-71 variables grid: not started (sklearn stays out of the sandbox on purpose).
- The frontend badge for `settings_overrides`, the risk card rows and the new problem codes is wiring only.

Known limits:

- One bar is one session: `max_daily_loss` compares consecutive bars, which is exact for the daily bars Studio holds.
- Exposure caps are applied when a position is opened, not rebalanced every bar, so marked gross can drift above the cap with price moves.
- A risk breach stops the run permanently; re-entering after a cool-down is not modelled.

## Build backend: risk parity, entry frequency and structured logs (2026-11-18)

- B-121. `sizing.mode = "risk_parity"` weights each slot's equal share by inverse 20-day volatility against the mean of that bar's entries, capped at 3x. The vector and event engines compute the same multiplier and are compared trade for trade.
- B-110 (partial). `spec.frequency` takes `daily`, `week_start` or `month_start`; entries are masked to the first observed bar of each period and exits still run every bar. "What it does" names the schedule. A drift corridor (act after X% move) is not built.
- B-80 (backend). `ctx.log(message, level, **fields)` and `ctx.log.info/warning/error(message, **fields)` store clean key values (bool, string up to 256 characters, finite numbers) on the log row as `fields`. `/preview` returns them; filtering and search are the Logs tab's job.

API changes:

- `POST /preview` — log rows may carry `fields`; `settings_overrides` and `risk_events` unchanged from the entry above.

Budgets: the risk-parity multiplier adds one pass over the day's entries in each engine; the 500 × 2,500 Python run and the 31 ms lint p95 are unchanged.

## Build backend: review fixes, version tools and formula variables (2026-11-19)

- Review fix (B-57): the AST allow-list let numpy and pandas reach files and eval through names the ban list missed (`np.loadtxt`, `np.genfromtxt`, `np.savez`, `arr.tofile`, `np.DataSource().open`, `df.to_latex/to_html/to_string(path)`, `df.query`, `pd.eval`, `np.lib`, `np.sys`, `np.os`, `pd.io`). They are refused by name now; the escape suite has 17 more cases (61 total).
- B-113 (partial). A formula may hold `name = expr` lines (newline or `;`) and `#` comments; names expand before parsing, so look-ahead checks still apply. User functions and separate entry/exit editors are open.
- B-127. `POST /strategies/{sid}/versions/{version}/restore` adds the old version as a new latest one (an unchanged spec adds nothing); `POST .../branch` starts a new strategy from it.
- B-129. `GET /strategies/{sid}/blame?file=main.py` returns `[{line, text, version}]` for the latest file.

Build API (all under `/api/studio-v3`): `POST /build/check` problems; `/build/complete` completions; `/build/signature` signature help; `/build/definition`, `/build/references`, `/build/rename`, `/build/outline` symbols; `/build/checks` warm-up, data used, survivorship; `/build/condition` true-rate, last true, always-true or false, fired bars; `/build/debug` bar stepper and breakpoints; `/build/preview` live preview; `/build/import-quantconnect` QuantConnect rewrite; `GET/PATCH /strategies/{sid}/files` project files; `PUT /strategies/{sid}` save version; `PUT /strategies/{sid}/draft` draft; plus the three version routes above.

Known limits: the sandbox ban list is by attribute name, so a new numpy or pandas file reader added in a later release must be added to `BANNED_ATTRS`.

## Build backend: workspace, editor services, runs and runner features (2026-11-19)

Shipped (by id): B-14, B-132 lease; B-21 range format and imports; B-23 find and replace; B-24 code actions; B-34 hover; B-35 look-ahead patterns; B-37 strictness; B-39 invariants; B-41 API header; B-43 universe attribute; B-45 brackets; B-46 max_entries; B-48 history numpy and pandas; B-53 inferred warm-up; B-56 feature_matrix and sklearn; B-57 scipy.optimize and sklearn; B-64 parity test; B-71 watch; B-74 order lines; B-75 inlay hints; B-76 code lens; B-77 replay; B-78 profiler; B-84 to B-88 run levels, progress, cancel, locals, delta; B-94 zip; B-95, B-141 snippets; B-104 assumptions; B-105 groups; B-106 calendar kinds (partial); B-110 corridor (Python only); B-126 labels and lock; B-128 compare and merge; B-130 history; B-131 share links.

New routes (under /api/studio-v3): POST /preview (symbols, window, bars_by_symbol, order_lines, invariants, warmup.inferred_*); POST /build/profile, /build/run, GET /build/run/{job_id}, POST /build/watch, /build/hover, /build/inlay-hints, /build/codelens, /build/code-actions, /build/organise-imports, /build/format-range, /build/migrate; /build/check takes strictness and severity; GET /strategies/{sid}/timeline, /history, /blame, /compare/{other}, /export.zip; PUT /strategies/{sid}/versions/{v}/label, /lock; POST .../versions/{v}/restore, /branch, /merge, /share, /lease, /find-replace; DELETE /strategies/{sid}/lease; GET/POST/PUT/DELETE /snippets; GET /share/{token}, POST /share/{token}/fork, DELETE /share/{token}; POST /strategies/import-zip.

Still open and why: B-55 ctx.store across runs (a store that survives runs makes the same strategy return different results, which breaks the reproduce certificate); B-93 project as pinned library (needs cross-strategy imports in the sandbox); B-115 tree blocks, B-118 find rules, B-122 if/else allocate (engine and search work, not started); B-62 binding is frontend; B-110 drift corridor for formula strategies; per-bar progress counter (the sandbox does not stream); B-67, B-123 blocked by data; B-140 owner decision.

Known limits: the runtime import layer allows submodules of the allowed roots (C code in numpy and pandas imports helpers lazily through the caller's builtins), so the AST check is the gate for user import statements; the profiler traces strategy frames only and slows the run; leases expire after 60 s without a renewal.
