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
