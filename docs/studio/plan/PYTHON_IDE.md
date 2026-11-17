# Build › Python: from editor box to a full IDE

Audit on 2026-11-17 of `build/CodeEditor.tsx`, `core/pycode.py` and `core/pyrunner.py`, compared with the QuantConnect cloud IDE and the LEAN `QCAlgorithm` API. Earlier "Build ~95%" was not verified; this file replaces that claim.

## What exists

- Monaco at a fixed 420px height inside the Build card, with `vs-dark` / `light`, minimap off.
- `ctx` completion and hovers (17 members), 4 snippets, formula names inside `ctx.value("`.
- ⌘S formats and saves; ⌘↵ runs.
- Server static checks give line-numbered markers (AST allow-list, banned names, formula parse). A runtime error marks its line.
- Runner: a child process with CPU, memory and file limits and safe builtins. `math` only, no numpy, no imports.
- Model: **one symbol at a time**, `on_bar(ctx)` with `buy / sell / short / cover` at the next open. Output is entry and exit arrays only.

## Gaps against QuantConnect and LEAN

### Language and API (the engine side)

| # | QuantConnect / LEAN | Studio now | Needed |
|---|---|---|---|
| A1 | `initialize()` / `on_data(slice)` across **all symbols at once** | Loops each symbol alone | Portfolio-level `on_data(ctx)` seeing every symbol in the bar; keep per-symbol `on_bar` as the simple mode |
| A2 | `set_holdings(sym, 0.25)`, `market_order(sym, qty)`, `liquidate()`, `limit_order`, `stop_market_order` | Four actions only, no size | Target weights, quantities, limit and stop orders, liquidate; sizes flow to the engine instead of the Build sizing card |
| A3 | `self.portfolio[sym].quantity`, `.invested`, `.unrealized_profit`; `portfolio.cash`, `.total_portfolio_value` | `ctx.position` = −1/0/1 | Read-only portfolio state from the engine each bar |
| A4 | Indicator objects: `self.sma(sym, 50)`, `.is_ready`, `.current.value`, warm-up | String formulas via `ctx.value("…")`, precomputed | Keep formula strings (fast); add `ctx.indicator(...)` objects with `ready` and `value` that match LEAN's definitions (`LEAN_PARITY.md` row 19) |
| A5 | `self.history(sym, 20, Resolution.DAILY)` returns a DataFrame | `ctx.close[-20:]` lists | Add `ctx.history(fields, n)` returning numpy arrays (pandas optional) |
| A6 | `schedule.on(date_rules.month_start(), …)` | None | `ctx.is_month_start` / `week_start` / `every(n)` helpers, and a `rebalance` hook |
| A7 | numpy, pandas, scipy, sklearn, statsmodels available | `math` only, imports refused | Allow-listed imports: numpy, pandas, math, statistics, scipy.stats. Still no os, io, socket, subprocess or importlib |
| A8 | `self.debug()`, `self.log()`, `print` shown in the console | `print` allowed but output dropped | Capture stdout and `ctx.log()` per bar (date, symbol) and return them, with a line cap |
| A9 | `self.plot("Chart", "Series", v)` custom charts | None | `ctx.plot(name, value)` returned as series and shown under the equity chart |
| A10 | `set_warm_up(n)` | None | `warmup = n` class attribute; no orders before bar n |
| A11 | `on_order_event`, fills with price and quantity | `on_fill(ctx)` with no detail | `on_fill(ctx, fill)` with symbol, side, quantity, price, date |
| A12 | `self.object_store` and parameters `get_parameter("x")` | `ctx.param` | Keep `ctx.param`; parameters declared in code show in the Optimise grid automatically |
| A13 | Runs on LEAN's engine with full fill, fee and slippage models | Signals → Studio engine | Orders feed the event engine directly, so LEAN parity applies to Python strategies |
| A14 | Speed: C# core | Python loop per symbol per bar | Budget: 500 symbols × 2,500 bars under 20 s. Vectorised precompute of formulas stays |

### IDE (the editor side)

| # | QuantConnect IDE / VS Code | Studio now | Needed |
|---|---|---|---|
| B1 | Full-window editor; results docked below | 420px box in a card | Full-height IDE layout: editor fills the work area, a bottom panel that resizes (30–40%), side rail collapsible (`UI_GUIDE` §7) |
| B2 | Bottom panel: Console, Logs, Problems, Results | Markers only | Tabs: Problems (static and runtime, click to jump), Output (prints and logs, filterable by symbol and date), Results (KPI strip, equity, trades), Plots |
| B3 | Project files: `main.py` plus helpers | One string | Multiple files per strategy (`main.py`, `helpers.py`), a file tree, imports between them |
| B4 | Status bar | None | Ln:Col, errors and warnings count, saved/unsaved, run state, last run time |
| B5 | Command palette and shortcuts | ⌘S, ⌘↵, app palette | Monaco palette ⌘⇧P, ⌘/ comment, ⌥↑↓ move line, ⌘D multi-cursor, F12 go to definition (local symbols), shortcuts listed in the palette |
| B6 | Autocomplete for the whole API with types | 17 `ctx` members | Every `ctx` member, portfolio fields, indicator objects, numpy and pandas top names, and the user's own class members; signature help when typing `(` |
| B7 | Lint on type | On server check | Debounced server check (300 ms) plus Pyright-style hints in the browser for undefined names |
| B8 | Debugger | None | Bar stepper: pause at a date and symbol, inspect `self` and `ctx`, step one bar (replays in the runner, read-only) |
| B9 | Version control | Versions with diff (Build) | Same, side-by-side Monaco diff with each version's result above |
| B10 | Templates and examples | One template | Gallery of 8 starters: trend, mean reversion, momentum rotation, pairs, volatility target, breakout, seasonality, ML-score |
| B11 | Live-ish preview | Build preview chart | Split view over 1280px: code left, preview right (chart with trades, plots) |
| B12 | Theme | `vs-dark` | App theme tokens defined as a Monaco theme so the editor sits in the page |
| B13 | Font | Mono 13px | JetBrains Mono, 13px, 20px line height, ligatures off, bracket colours, sticky scroll, folding |

## Order of work

1. **IDE layout** (B1, B2, B4, B12, B13): full-height editor, bottom panel with Problems and Output, status bar, themed Monaco.
2. **Runner output** (A8, A9, A10, A11): logs, plots, warm-up, fill detail. The Output and Plots tabs show them.
3. **Portfolio API** (A1, A2, A3, A5, A6, A13): `on_data` over all symbols, weights and orders sent straight to the event engine, portfolio state, history, schedule. Per-symbol `on_bar` stays as the simple mode.
4. **Imports** (A7): numpy, pandas, scipy.stats in the runner, under the same limits.
5. **Completion and checks** (B5, B6, B7): full API completion, signature help, typed hints, debounced lint.
6. **Project files** (B3) and the template gallery (B10).
7. **Debugger** (B8) and split preview (B11).
8. **Indicator objects** matching LEAN (A4); then parity tests through `LEAN_PARITY.md`.

Each step: tests for the runner, a browser check at 1440 and 390px in light and dark, the `CODE_STANDARDS.md` gates, and a commit.

## Safety stays

The runner keeps the child process, rlimits, `-I`, an empty env and no network. New imports come from an allow-list checked in the AST and at import time through a restricted `__import__`. The Docker sandbox stays deferred, as decided.
