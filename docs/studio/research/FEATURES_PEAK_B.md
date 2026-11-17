# Studio: every feature at its peak (pass B)

Second, independent pass. Pass A (`FEATURES_PEAK_A.md`, a research agent) and this one merge into `plan/FEATURES_PEAK.md`. Part I is the Python IDE (Build). Part II covers every other page.

Pages read on 2026-11-17:
- QuantConnect: `cloud-platform/projects/ide`, `cloud-platform/backtesting/debugging`, `cloud-platform/projects/shared-libraries`
- TradingView: Pine `primer/first-steps`, `writing/debugging` (Pine Logs), `concepts/strategies` (strategy report, broker emulator, orders, pyramiding, OCA, costs)
- Earlier this session: the LEAN source (`Statistics.cs`, fills, slippage, fees) and Vercel, Emil and Krehel UI rules

Each section has the same three parts: **What the best do**, **Peak for Studio** (what we build), and **Customise** (settings the user owns). Defaults are given for every setting.

---

## 1. Workspace layout

**What the best do**
- **QuantConnect** is the VS Code workbench in a browser. It has a right navigation rail (Explorer, Run and Debug, Resources, Ask Mia), a bottom console with a Cloud Terminal tab and a Problems tab, and an editor that splits horizontally and vertically by dragging files. It warns that two browser tabs on one project fall out of sync.
- **TradingView** docks the Pine Editor under the chart, with the Strategy Tester as another bottom tab, so code, chart and results are all on one screen.
- **MetaEditor** has a navigator on the left, a toolbox at the bottom (Errors, Search, Debug, Profiler), and the strategy tester in its own window.

**Peak for Studio**
- **Three zones.** Left rail: Files, Outline, Search, Templates, Versions. Centre: editor groups. Bottom panel: Problems, Output, Logs, Results, Plots, Debug, Terminal (read-only REPL). Right rail: Preview chart, Inspector (variables), AI. Each zone collapses, resizes, and remembers its size per user.
- **Editor groups.** Split right or down, up to 4 groups, by dragging a tab to an edge. Each group has its own tabs, which can be pinned, kept in preview, or marked dirty.
- **Preset layouts**, switched with one key:
  - **Write**: editor full width, panel collapsed.
  - **Test**: editor 60%, preview 40%, panel at 35%.
  - **Debug**: editor, variables on the right, Debug tab open.
  - **Review**: diff on top, results below.
- **Zen mode** (⌘K Z): only the editor, centred at 100 columns.
- **One session per strategy.** A second browser tab opens read-only with a "take over" button, so the out-of-sync bug QuantConnect warns about can't happen.
- **Phone (390px):** one zone at a time with a bottom switcher (Code / Run / Results). Editing is allowed, but blocks and formula are the recommended modes there.

**Customise:** zone positions (panel bottom or right), sizes, default layout per mode, the activity rail on the left or right, compact density on or off. Default: the Test layout on screens wider than 1280px, otherwise Write.

---

## 2. Editor core (Monaco)

**What the best do**
- **QuantConnect** ships the full VS Code editor: folding, outline, keybinding editor (F1), light and dark themes.
- **Pine** has autocomplete, hover docs, and ⌘-click to open the reference manual.
- **VS Code** adds multi-cursor, column select, sticky scroll, bracket-pair colours, inlay hints, CodeLens, peek and minimap.

**Peak for Studio**
- **Text editing**
  - Multi-cursor: ⌥-click, ⌘D for next match, ⌘⇧L for all matches.
  - Column select with ⇧⌥-drag.
  - Move lines ⌥↑↓, copy lines ⇧⌥↑↓, delete line ⌘⇧K, toggle comment ⌘/, block comment ⇧⌥A.
  - Expand or shrink the selection with ⌃⇧→/←.
- **Display and navigation**
  - Folding by indent and by `# region` markers. Sticky scroll shows the current class and method.
  - Bracket-pair colours and guides. Rulers at 88 and 120 columns, both optional.
- **Inlay hints:**
  - the parameter value next to `ctx.param("fast")`, e.g. `= 50`;
  - the last value next to `ctx.value("rsi(close,14)")` from the preview run, e.g. `→ 61.2 on 2026-01-30`;
  - the computed type next to a variable.
- **CodeLens above `on_bar`:** "Run on SPY · Run on universe · Debug from 2020-03-01". Above each `ctx.rule(...)`: "true on 34% of bars".
- **Gutter**
  - Breakpoints and logpoints.
  - Run markers on lines that placed orders in the last preview, with a hover showing the count and the first 5 dates.
  - Change markers since the last saved version.
- **Code Actions** (⌘.)
  - Extract a formula string to a parameter.
  - Convert `ctx.rule(...)` to an indicator object.
  - Wrap the selection in `if ctx.position == 0`.
  - Add a missing `on_fill`.
- **Format on save** with ruff format (already wired) and organise imports. Format a selection with ⌘K ⌘F.
- **Find and replace in this file and across all project files**, with regex, case and whole-word options and a preview before replacing.
- **Go to:** a symbol (⌘⇧O), a line (⌃G), a definition (F12), the references (⇧F12), a peek of the definition (⌥F12). Rename symbol (F2) across files.
- **Undo history** survives reloads per file.

**Customise:** font family, size, line height and ligatures; tab size; word wrap; rulers; minimap; whitespace rendering; cursor style and blinking; format on save; auto-closing brackets; suggestion delay; inlay hints on or off by kind; vim and emacs keybindings (monaco-vim, monaco-emacs). Defaults: JetBrains Mono 13/20px, ligatures off, tab 4, wrap off, rulers off, minimap off, format on save on, all inlay hints on.

---

## 3. Language intelligence

**What the best do**
- **QuantConnect** IntelliSense covers LEAN members with type, description and parameters. Its docs state it does not cover user-defined objects.
- **Pine** has a full typed language with errors as you type and a reference manual for every function.

**Peak for Studio**
- **A Python language server in the browser**, Pyright compiled to WASM in a web worker, with stub files for `ctx`, the portfolio and order objects, the indicator classes, numpy, pandas and math. That covers types, errors, completion and hover for the user's own classes too, beating QuantConnect's stated gap.
- **Completion**
  - Every API member, with signature help on `(`, the active parameter in bold, and docs with an example.
  - Formula names and operators inside `ctx.value("…")`, with the argument template.
  - Parameter names inside `ctx.param("…")`, symbols inside `ctx.symbol == "…"`, fields inside `ctx.history("…")`.
  - Snippets with tab stops.
- **Diagnostics as you type (300ms), in three layers:**
  1. Pyright errors: undefined names, wrong types, wrong argument counts.
  2. Studio rules from the server: banned names, look-ahead patterns such as a positive index into history, imports outside the allow-list.
  3. Formula parse errors inside strings, underlined at the exact token.
- **Hover:** docs, signature, and for formulas their meaning, lookback and warm-up bars. When a preview has run, it also shows the latest value.
- **Look-ahead detector**, specific to quant work and a P0 under `CODE_STANDARDS.md`. Static analysis flags `close[0]`, `close[1:]`, any history access without a negative index, use of `ctx.date` in a comparison with a future date literal, and reading `next_*`. The runtime History object already refuses these, so the editor marks them before the run.
- **Docs panel:** ⌘-click or F1 on any API name opens its reference page beside the editor, offline and versioned with the API.

**Customise:** strictness (basic or strict type checking), which diagnostic layers are shown, and a severity per rule (error, warning, off). Defaults: basic, all layers, look-ahead as an error.

---

## 4. The strategy API (what the code can say)

**What the best do**
- **LEAN** offers:
  - `initialize` and `on_data(slice)` over the whole universe;
  - orders: `set_holdings`, `market_order`, `limit_order`, `stop_market_order`, `liquidate`;
  - `portfolio[sym]` state;
  - indicator objects with `is_ready`, warm-up and consolidators;
  - `schedule.on(date_rules, time_rules)`, `history()` as DataFrames;
  - `plot`, `log` and `debug`; `object_store`; `get_parameter`.
- **Pine** offers:
  - `strategy.entry` with pyramiding;
  - `strategy.exit` with take-profit, stop-loss, trailing stops and partial exits;
  - OCA groups (`cancel` and `reduce`) and `strategy.close` / `close_all`;
  - `calc_on_order_fills` and `process_orders_on_close`;
  - commission and slippage settings, and risk rules such as `strategy.risk.max_drawdown`.

**Peak for Studio**, with two modes sharing one engine:

**Simple mode** (exists today): `on_bar(ctx)` per symbol, `buy / sell / short / cover`. Keep it. It is the bridge from formulas.

**Portfolio mode** (new):

```python
class Strategy:
    universe = "sp500"             # or a list, or a screen id
    warmup = 200                   # bars before any order
    rebalance = "month_start"      # or week_start, every(5), daily, None

    def init(self, ctx):
        self.mom = ctx.indicator("roc(close, 126)")      # per symbol, LEAN-identical
        self.trend = ctx.indicator("sma(market, 200)")

    def on_data(self, ctx):
        if not ctx.rebalancing or not self.trend.ready:
            return
        if ctx.market.close < self.trend.value:
            ctx.liquidate(); return
        ranked = ctx.rank(self.mom, top=10)              # [(symbol, value)]
        ctx.target_weights({s: 1 / len(ranked) for s, _ in ranked})

    def on_fill(self, ctx, fill):                        # fill.symbol, side, qty, price, date, fee
        ctx.log(f"{fill.side} {fill.qty} {fill.symbol} @ {fill.price:.2f}")
```

| Area | API | Notes |
|---|---|---|
| Orders | `target_weights(dict)`, `set_weight(sym, w)`, `order(sym, qty)`, `order_value(sym, $)`, `limit(sym, qty, price, ttl=1)`, `stop(sym, qty, price)`, `stop_limit`, `liquidate(sym=None)`, `cancel(order_id)`, `cancel_all()` | All fill through `fills.py` and are LEAN-parity tested |
| Brackets | `bracket(sym, qty, stop=, target=, trail=)` with OCA cancel; partial exits by `qty=` per level (Pine's `strategy.exit` levels) | Stop first when both hit one bar (stated) |
| Pyramiding | `max_entries = 3` class attribute, per-symbol | Pine's pyramiding |
| Portfolio | `ctx.portfolio.cash`, `.value`, `.leverage`, `.exposure`; `ctx.pos(sym).qty`, `.avg_price`, `.unrealized`, `.bars_held`, `.entry_date` | Read-only |
| Data | `ctx.history(field, n, sym=None)` → numpy (`pandas=True` for DataFrame); `ctx.bar(sym)`; `ctx.symbols` alive today; `ctx.market` (benchmark) | Negative-only access |
| Indicators | `ctx.indicator(formula)` → `.value`, `.ready`, `.history(n)`, `.window`; same names as formulas | LEAN definitions, parity-tested |
| Ranking | `ctx.rank(ind, top=, bottom=, where=)`, `ctx.zscore(ind)` cross-section | Vectorised |
| Schedule | `rebalance` attribute; `ctx.rebalancing`; `ctx.is_month_start/week_start/quarter_start/year_start`; `ctx.every(n)` | |
| Risk rules | `max_drawdown = 0.2` (flatten and stop), `max_daily_loss`, `max_position = 0.1`, `max_gross = 1.0` class attributes | Pine `strategy.risk.*` |
| Output | `print`, `ctx.log(msg, level="info")`, `ctx.plot(name, value, chart="main" or "own")`, `ctx.mark(sym, label)` on the price chart, `ctx.table(name, row)` | Pine Logs + labels + tables |
| Parameters | `ctx.param(name)`, or declared `params = {"fast": (10, 5, 50, 5)}` → appear in Build params and the Optimise grid | QC `get_parameter` |
| State | instance attributes; `ctx.store` (persists across runs, small JSON) | QC ObjectStore |
| ML | `ctx.feature_matrix(formulas, lookback)`, `ctx.fit_every(n)` hook, sklearn allowed (walk-forward safe: fit only on past bars) | Ours |

**Imports allowed:** math, statistics, numpy, pandas, scipy.stats, scipy.optimize, sklearn (linear models, trees, preprocessing), and the user's own project files. Everything else is refused with the line marked.

**Customise:** the default mode for new strategies (simple or portfolio), and per-strategy engine settings (fill timing, costs, sizing) from the Build card or as class attributes. The code wins over the card when both are set, and a badge says so.

---

## 5. Running and feedback loop

**What the best do**
- **TradingView** recompiles on save, and the chart and Strategy Tester update at once.
- **QuantConnect** builds the project, then runs a backtest in the cloud and streams logs.

**Peak for Studio**
- **Three run levels:**
  1. *Live preview* while typing (debounced 600ms): one symbol, 2 years, shows trades on the chart, inlay values and order markers. It is killed and restarted as the user types.
  2. *Quick run* (⌘↵): the full universe, 5 years, results in the panel.
  3. *Full run* (⌘⇧↵): the Backtest page settings, recorded in the ledger.
- **Progress** in the status bar ("bar 1,240 / 2,516 · 18 symbols · 3.2 s"), with partial equity streamed to the Results tab.
- **Cancel** with Esc in the panel. Every run has its time budget shown.
- **Runtime error:** jump to the line, show the stack trace with only the user's frames, plus the values of locals at the failing bar (symbol, date, `self` attributes) — a crash dump.
- **Compare with the last run:** a delta row (return, Sharpe, trades) shown after each quick run.

**Customise:** preview symbol and window; auto-preview on or off; quick-run universe and years. Defaults: SPY, 2 years, on, top 50 by volume over 5 years.

---

## 6. Logs, plots and output (Pine Logs is the bar)

**What the best do**
- **Pine Logs:** `log.info`, `log.warning` and `log.error`, each tied to a bar, with filters by level, start date, text, match case, whole word, regex and custom code filters. Clicking a log jumps the chart to its bar.
- Debugging via labels and tables drawn on the chart.
- **QuantConnect:** a Cloud Terminal with logs and errors, a clear button, and a daily log quota.

**Peak for Studio**
- **Logs tab** is a virtual list with these columns: level, date, symbol, message, and the code line.
  - Filter by level, symbol, date range, text, regex, match case and whole word.
  - Clicking a row moves the preview chart to that bar and the editor to that line.
  - Export as CSV.
  - Cap: 50,000 lines per run, with a visible "truncated at …" row.
- **Logpoints:** a gutter right-click adds "log `{expr}` here" without editing the code, the same as a VS Code logpoint.
- **Plots tab:** each `ctx.plot` name becomes a series.
  - It can overlay the price chart or sit in its own pane, with a shared time axis.
  - Toggle each series, and compare plots across two runs.
- **Marks:** `ctx.mark` draws labels on the price chart (Pine labels).
- **Tables:** `ctx.table` builds a sortable table in the panel (Pine tables).

**Customise:** default log level, timestamp format, wrap long lines, colour by level. Default: info, date only.

---

## 7. Debugger (QuantConnect's is the bar)

**What the best do**
- **QuantConnect:**
  - Breakpoints with expression conditions and hit counts.
  - Enable, disable and remove one or all.
  - Continue, step over, step into, restart and disconnect.
  - A Variables panel where you can set values, and a Watch panel for custom expressions.
  - DataFrames render readably.
- **MetaEditor** debugs on history data and has a profiler.

**Peak for Studio**
- Breakpoints, conditional breakpoints (`ctx.symbol == "AAPL" and ctx.date >= "2020-03-01"`), hit-count breakpoints, logpoints, and **data breakpoints**: "pause when `ctx.portfolio.value` falls 5% in a day" or "pause on the first order".
- **Bar stepping** that only a backtest debugger can do: step one bar, step to the next order, step to the next fill, run to a date, step back one bar. Studio re-runs deterministically to bar t−1, so time travel works.
- **Variables:** `self`, `ctx` (portfolio, positions, the current bar of every symbol), locals. Numpy arrays and DataFrames open in a grid viewer with a sparkline.
- **Watch** expressions, evaluated every pause, with their history as a small chart across pauses.
- A **debug console** (REPL) at the paused frame, read-only to the engine; it can't place orders.
- The **preview chart follows** the paused bar, with the position and pending orders drawn.
- Built on the runner: the child process runs under `sys.settrace` / `bdb` with a JSON protocol over pipes, so there is no network listener and the sandbox limits still apply.

**Customise:** pause on exceptions (all or uncaught), skip warm-up bars, step granularity (line or bar). Defaults: uncaught, skip warm-up, bar.

---

## 8. Results inside the IDE (TradingView Strategy Tester is the bar)

**What the best do**
- TradingView's Strategy Tester has three tabs.
  - **Metrics** has five sections: key stats with an equity chart, return details against buy-and-hold, trades analysis with distributions, run-ups and drawdowns, and capital efficiency with margin.
  - **List of trades** and **Properties** (every setting used) are the other two tabs.
- Each metric has All / Long / Short columns and a description link.

**Peak for Studio**
- The **Results tab** is a compact Backtest report:
  - a KPI strip (return, CAGR, Sharpe, PSR, max drawdown, trades, win rate, expectancy, fees, exposure) with All / Long / Short toggles;
  - equity against benchmark with drawdown shading;
  - a trade list (click a row to jump the chart to the trade and the code to the line that placed it);
  - a trade-return histogram;
  - a **Properties** list with every setting and the data version, for reproduction.
- Every metric links to its definition (formula, LEAN reference) in a hover card.
- "Open in Backtest" carries the run to the full page with nothing recomputed.

**Customise:** which KPIs appear and in what order (saved per user, shared with Backtest), and the currency and percent format.

---

## 9. Files, projects and libraries

**What the best do**
- **QuantConnect:** projects with many files, a file outline, shared libraries you can create, add, rename, remove and delete (projects reference library projects), and best-practice notes.
- **Pine:** published libraries imported by `import user/lib/1`.

**Peak for Studio**
- A strategy is a **project**: `main.py` plus any `.py` modules, plus `README.md` and `params.json`. The file tree supports create, rename, move, delete, duplicate and drag to reorder.
- **Libraries:** any project can be marked a library, then imported by others with a pinned version (`from lib.momentum import rank`). Updating a library never silently changes a saved strategy; a badge offers "v3 available, review diff".
- **Outline** of classes, methods and indicators for the open file.
- **Import and export:** a zip of the project; paste a QuantConnect algorithm and a shim maps `QCAlgorithm` calls onto `ctx` (initialize→init, on_data, set_holdings, SMA, history), listing the calls it can't map.
- Size limits: 50 files, 200 KB per file.

---

## 10. Versions, diff and collaboration

**What the best do**
- **Pine** has a version history per save, with a diff and revert.
- **QuantConnect** has project collaboration with live co-editing, and backtests stored per project.

**Peak for Studio**
- Every save is an **immutable version** (exists).
  - Monaco side-by-side diff between any two, with each version's run result above it.
  - Restore or branch from any version.
  - Name and tag versions ("validated", "live"); a live version is locked.
- **Local history:** autosave snapshots every 2 seconds of typing, kept 7 days, separate from versions.
- **Blame:** each line shows the version that last changed it.
- **Share:** a read-only link or a fork link. A comment can be pinned on a line (thread in the gutter).
- Collaboration: one editor at a time with take-over, as in §1. Live co-editing is not planned for v3.

---

## 11. Templates, snippets and examples

**Peak for Studio**
- A **gallery of 12 starters**, each with a one-line description, its last backtest on the default universe, and "use as start":
  - trend 50/200, RSI(2) mean reversion, momentum rotation top 10, dual momentum, pairs z-score;
  - volatility target, breakout with ATR stop, turn of month, gap fade, sector rotation;
  - ML ranking (sklearn), risk parity.
- **User snippets:** save a selection as a snippet with tab stops, triggered by a prefix; snippets can be shared through the Library page.
- **Examples in hover docs** can be inserted with one click.

---

## 12. AI assistance

**What the best do**
- **QuantConnect's Mia** has agentic chat with project context: it edits files, runs backtests and deploys live.
- **Cursor** offers inline edit (⌘K), chat with the codebase, and tab completion.

**Peak for Studio** (optional, never sets a grade)
- Inline ⌘K on a selection ("make the exit a trailing ATR stop"), shown as a diff to accept or reject.
- Explain an error or a line.
- Write a test strategy from plain English, then show the diff.
- The agent API already exposes compile and backtest; the AI uses the same tools and every action goes to the actor log. Deploying live always needs a human click.

**Customise:** off by default; model choice; the context it sees (open file, project, last run).

---

## 13. Keyboard and commands

- **Command palette** (⌘⇧P) holds every command with its shortcut. Studio's app palette (⌘K) and Monaco's palette are merged into one list, grouped as Editor, Run, View and Studio.
- **Keybinding editor:** search, rebind, reset; detects conflicts; exports as JSON.
- **Defaults:**

| Key | Action |
|---|---|
| ⌘S | Format and save |
| ⌘↵ | Quick run |
| ⌘⇧↵ | Full run |
| F5 | Debug |
| F9 | Toggle breakpoint |
| F10 / F11 | Step bar / step line |
| ⌘J | Toggle the panel |
| ⌘B | Toggle the left rail |
| ⌘\ | Split |
| ⌘P | Go to file |
| ⌘⇧O | Go to symbol |
| ⌘⇧F | Search the project |
| ⌘K Z | Zen mode |

---

## 14. Settings model

- Settings have three levels: **user** (all strategies), **strategy** (`studio.json` in the project), and **workspace defaults**. Each setting shows where its value comes from.
- They are edited in a settings page with search, or as JSON in the editor with a schema (completion and validation).
- Settings sync to the server per user.

---

## 15. Performance budgets

| Action | Budget |
|---|---|
| Editor ready after the page loads | < 1.0 s (Monaco and Pyright load lazily, with a skeleton at the final size) |
| Keystroke to diagnostics | < 300 ms |
| Live preview (1 symbol, 2 years) | < 1.5 s |
| Quick run (50 symbols, 5 years) | < 8 s |
| Full run (500 symbols, 10 years, portfolio mode) | < 30 s |
| Debugger step | < 100 ms |
| Logs list | 50k rows at 60 fps (virtualised) |

---

## 16. Things others do badly (avoid)

- QuantConnect's IntelliSense skips user-defined classes. Ours uses Pyright, so it covers them.
- QuantConnect's two-tab desync. Ours uses a single editing session with take-over.
- Pine's intrabar guesswork (it assumes open→high→low→close order from the open's position). Ours uses a stated worst case: the stop fills first.
- Pine results change when chart settings change. Ours: every run records its Properties and data version.
- MetaEditor needs a separate tester window. Ours keeps results in the same frame.
- Log quotas that silently drop lines. Ours shows a truncation row.
- IDEs that need a cloud node queue. Ours: preview and quick run are local and instant.

## 17. Studio-only features (no competitor has these)

- **Look-ahead detector in the editor**, plus the 50-cut repaint check (exists in Build) shown inline in the code.
- **Inline formula values** next to every `ctx.value` call, and the true-rate next to every `ctx.rule` call.
- **Trial ledger awareness:** the status bar shows "trial 14 on this idea", because every run counts toward the deflated Sharpe ratio.
- **Bar-level time travel** in the debugger.
- **The same code drives every page:** Optimise picks up the declared `params`, Validate stress-tests the code, and Live freezes a version.

---

# Part II: every page at its peak

The same pattern for each page: **Best today** (who leads and how), **Peak for Studio** (what we build), and **Customise**. Competitor facts come from `COMPETITORS.md` (23 products, read 2026-11-15) and the pages read this session.

## 18. Home (strategy list)

**Best today**
- QuantConnect's project list is a plain list of folders.
- Composer shows symphony cards with returns.
- StrategyQuant X has a databank, which is a sortable grid of thousands of generated strategies with every metric as a column.

**Peak for Studio**
- Two views over one list:
  - **Cards**: name, sparkline of the last run, verdict chip, trial count, last edited.
  - **Databank grid**, as in SQX: any metric as a column, sort, filter, saved column sets, and a multi-select bar for compare, archive, tag and export.
- **Needs attention** strip, ranked:
  - live drift beyond the band;
  - data newer than the last run;
  - a validation that expired after its code changed;
  - a failed run;
  - an alert that fired.
- **Folders and tags.** Search by name, rule text, ticker or tag. Typing in the search finds strategies that use `rsi(` inside their code.
- **Compare 2–6 strategies:** overlaid equity, a metric table, correlation, and a code diff.
- **Import:** JSON spec, a QuantConnect algorithm (through the shim), a Composer symphony JSON, a CSV of signals, or a Pine strategy, the last only after the licence check.
- **Bulk actions:** re-run on new data, validate the selection, export a zip.

**Customise:** default view, card fields, grid columns and sort, and pinned strategies.

## 19. Build (beyond the Python IDE in Part I)

**Best today**
- Composer has a visual block tree with if/else, filters and weights.
- Build Alpha and SQX have point-and-click rule builders and genetic generation.
- TradingView has Pine, and QuantConnect has full code.

**Peak for Studio**
- **Four modes, one spec:** blocks ⇄ formula ⇄ Python (one way) ⇄ plain English. The mode switch never loses work: an untranslatable part stays and is marked.
- **Blocks**
  - Condition rows exist today.
  - Add Composer-style **tree blocks**: if/else branches, filter by rank, weight by method, group, nested to any depth, each block showing its live true-rate.
- **Formula**
  - Live compile with a token-level error (exists).
  - Add an inline value preview under each rule ("true on 31% of bars, last true 2026-01-28"), a function reference panel, and multi-timeframe calls (`weekly(close)`), causal only.
- **Generation**, as in SQX and Build Alpha. "Find rules" searches a grammar of entries and exits, with an out-of-sample split built in.
  - Every candidate counts in the trial ledger, so the deflated Sharpe stays honest.
  - The output goes to the databank grid.
- **Checks card** (exists): look-ahead, signals fire, enough trades. Add: warm-up bars needed, data each rule uses, and survivorship exposure.
- **Exits library:** fixed and ATR stop, trailing (percent, ATR, chandelier), time stop, breakeven, scale-out levels, a profit-target ladder, an exit on an opposite signal, an end-of-week exit. Each can be combined and ordered.
- **Sizing library:** shares, cash, % equity, risk per trade, vol target, Kelly with a cap, score-weighted, equal, risk parity, and max position and gross limits.

**Customise:** default mode, default exits and sizing profile (from Library), and the blocks palette order.

## 20. Backtest

**Best today**
- TradingView Strategy Tester has metrics with All / Long / Short columns, return details, trade analysis, run-ups and drawdowns, capital efficiency, a list of trades, and properties.
- QuantConnect has a stat strip, equity, custom charts, orders, trades, logs, insights, and a report PDF.
- Portfolio123 has rolling and period tables.
- AmiBroker has a detailed per-trade report.

**Peak for Studio** (most exists; the gaps are listed)
- **Hero:** net return vs benchmark with drawdown shading and the hold-out line (exists). Add **All / Long / Short** toggles to every metric, as in TradingView.
- **Stat strip** with a fixed order chosen by the user. Add **PSR, expectancy, fees total, volume traded, capacity** (QuantConnect and LEAN).
- **Run-ups**, the mirror of drawdowns, with the same table (TradingView).
- **Capital efficiency:** cash idle %, gross and net exposure over time, margin used, and buying-power headroom.
- **Per-trade drill:** a chart of the trade with entry and exit bars, the rule values at entry, MAE/MFE, and the code line that fired.
- **Report export:** a PDF or HTML tear sheet in a fixed order chosen in Library, including the Properties block (every setting and the data version).
- **Benchmarks:** any symbol, a blend (60/40), or another strategy, with alpha, beta, IR and tracking error against each.

**Customise:** KPI set and order, tab order, default benchmark, report template.

## 21. Optimise

**Best today**
- QuantConnect has cloud grid and Euler search with strategy-level constraints and a parameter heatmap.
- TradingView has nothing native beyond manually changing inputs.
- SQX has genetic optimisation, walk-forward optimisation, and a walk-forward matrix.
- AmiBroker has exhaustive search, CMA-ES and a 3D chart.
- MetaTrader 5 has a genetic optimiser, forward periods and custom criteria.

**Peak for Studio** (exists: grid, random, Optuna, map, 3D surface, objectives, constraints, live fill)
- **Methods:** add genetic and CMA-ES (Optuna has both), and **walk-forward optimisation**, where each window re-optimises and the out-of-sample periods are stitched together (SQX, MT5).
- **Custom objective** written as a formula over metrics, e.g. `sharpe - 0.5 * max_dd`, available on every page.
- **Plateau finder:** pick the centre of the widest stable region, not the peak (exists as plateau vs spike; add a "select plateau centre" button).
- **Budget awareness:** every cell counts in the ledger. Show the deflated-Sharpe hurdle rising as the grid grows, before running.
- **Parallel coordinates** view for more than 3 parameters.
- **Distributed runs:** use all local cores, with an estimated time before starting.

**Customise:** default method, trial budget, objective, constraint presets.

## 22. Validate

**Best today**
- SQX has a robustness battery: Monte Carlo trade reordering, skipping trades, randomised history, parameter perturbation, and higher-precision checks.
- Build Alpha has noise tests, vs random, and Monte Carlo.
- QuantConnect has out-of-sample periods only.
- Most products have no PBO or deflated Sharpe.

**Peak for Studio** (exists: walk-forward, matrix, CPCV, vs random, noise, MCPT, delay, costs, nearby settings, deflated Sharpe, PBO, shocks, power, certificate)
- **Profiles:** quick (< 10 s), standard, full. Each is a saved list of tests and their pass bars in Library.
- **Add from SQX:** skip X% of trades, randomise slippage per trade, change the start bar by ±N, and a higher-precision check (re-run on a different fill model, LEAN parity).
- **Out-of-sample on unseen symbols:** train on half the universe and test on the other half.
- **Regime split:** pass bars must hold in each regime, not just on average.
- **One verdict** with the reason chain, plus the certificate (hash-matched reproduction, exists).

**Customise:** test list per profile, pass thresholds, and which tests block the verdict.

## 23. Portfolio

**Best today**
- Portfolio123 has books, which combine ranking systems with weights.
- Composer nests symphonies.
- QuantConnect runs multi-alpha in one algorithm.
- Portfolio Visualizer has allocation optimisers and efficient frontiers.

**Peak for Studio** (exists: up to 12 members, equal, inverse vol, risk parity, HRP, max Sharpe, fixed, rolling quarterly, rotate top, tree, weights over time)
- **Combined grade:** run Validate on the combined equity. Send it to Validate with one click (P-3).
- **Efficient frontier** of members with the chosen mix marked.
- **Rebalance costs** counted when weights shift; **netting** of trades between members on the same symbol.
- **Constraints:** max weight per member, max correlation, a sector cap across members.
- **Stress:** the combined portfolio in each crisis window (2015+).

**Customise:** default method, rebalance frequency, estimation window, constraints.

## 24. Live

**Best today**
- QuantConnect has live trading on 20+ brokers, live charts, orders, logs, and an insights stream.
- Composer has one-click automated execution.
- TradingView alerts go to webhooks.
- Option Alpha has bots with decision recipes and a paper mode.
- Collective2 tracks verified track records.

**Peak for Studio** (exists: signals, orders, freeze to paper with backtest band and drift, reconcile, Apprise alerts)
- **Shadow book:** the frozen version keeps running on fresh data next to paper. Live vs backtest-expected per trade explains slippage, cost leak and missed signals.
- **Signal health:** the rate of signals vs backtest, the distribution of rule values vs history, and a stale-data guard (blocked while data ends 2026-02-01, per `DECISIONS.md`).
- **Order CSV and broker bridges:** a CSV for manual brokers first, then Alpaca and IBKR paper through their APIs. Real money needs a human click every time.
- **Alerts:** fire on signal, fill, drift beyond band, drawdown beyond limit, or data stale. Channels: email, push, Telegram, webhook, with a quota and a visible failure status.
- **Phone first:** today's actions on one screen.

**Customise:** alert rules and channels, quiet hours, drift band width, and the broker per strategy.

## 25. Chart

**Best today**
- TradingView: 100+ indicators, 110+ drawing tools, multi-chart layouts, bar replay, alerts on drawings, and synced crosshairs.
- TrendSpider: automated trendlines, multi-timeframe analysis, raindrop charts.
- Koyfin: comparisons, fundamentals on the chart.

**Peak for Studio** (exists: candles, volume, 70 indicators, trades on price, trade navigator, replay)
- **Strategy overlay:** rule values, entry and exit markers, and stop and target lines for each open trade, from any saved strategy.
- **Drawings saved on the server per symbol:** trendlines, horizontals, fib, rectangles, text. Alerts can be set on a drawing.
- **Layouts:** 1, 2 or 4 charts with synced symbol, crosshair and time.
- **Compare:** add symbols as % lines.
- **Replay with the strategy:** step bars and watch orders appear; manual trading in replay is recorded to a journal.
- **Indicator from formula:** any formula string becomes an indicator pane, so Build and Chart share one language.

**Customise:** chart style, colours, saved templates (indicator sets), default timeframe (daily only, decided).

## 26. Library

**Best today**
- QuantConnect has shared libraries and datasets.
- Portfolio123 has universes, ranking systems and custom formulas.
- SQX has building-block sets and custom indicators.
- TradingView has community scripts and published libraries.

**Peak for Studio**
- **Universes:** static lists, rule-based screens (re-evaluated each rebalance, point-in-time), index members, and sectors.
- **Cost profiles:** IB fixed, IB tiered, zero-commission with spread, custom. Each is dated, and changing one marks old runs stale (X-5).
- **Benchmarks** and blends.
- **Indicators and blocks:** user formulas saved by name with a description and tests, usable everywhere.
- **Custom metrics:** a formula over the equity and trades series, usable as a KPI, a column, an objective or a limit (Y-1).
- **Regimes and crises:** dated windows (2015+), editable.
- **Profiles:** validation, report order, sizing, layout. Export and import as JSON.
- **Data:** the live audit (symbols per year, gaps, adjustment status, freshness).
- **Agents:** tokens with scopes, an actor log, and a look budget (how many hold-out looks are allowed).

**Customise:** everything here is user-owned. Library is the customisation layer for the rest of Studio.

## 27. Cross-page

- **Command palette everywhere** (⌘K): every page, strategy, action and setting.
- **Compare** anything with anything: two runs, two versions, two strategies.
- **Share and export:** a link (read-only), a PDF, a JSON spec, a zip.
- **Reproduce:** every result shows its hash; "reproduce" re-runs it and matches the hash.
- **Every state designed** (empty, loading, error, skipped) on every card.
- **One customisation model:** user, strategy and workspace levels, as in Part I §14.
