# Dev IDE

## Research

Searched with TinyFish; licences marked (v) were confirmed on the page, the rest are from the project's repo and worth one more look before copying code. Ideas, not code, unless the licence is permissive.

| Project | Link | Licence | What to take |
|---|---|---|---|
| VS Code Activity Bar guidelines | https://code.visualstudio.com/api/ux-guidelines/activity-bar | docs | One icon style per item, clear names, no duplicate icons; 48px bar, 24px glyph, active state by colour or background, not a coloured edge line. Done in the Dev bar. |
| TradingView Pine Editor | https://www.tradingview.com/support/solutions/43000763320 | closed (ideas only) | Editor lives at the bottom of the chart; Pine Logs pane with info grey, warning orange, error red; profiler mode; strategy tester as a tab next to the code. Matches our Output tab and Results tab. |
| TradingView Lightweight Charts | https://tradingview.github.io/lightweight-charts/docs/plugins/intro | Apache-2.0 (v) | Series primitives for order lines, paused-bar vertical line and shaded held spans without a new chart. Already the engine under StudioChart. |
| KLineChart Pro (SiMahfud fork) | https://github.com/SiMahfud/klinechartpro | Apache-2.0 | Bar replay: play, pause, speed 1x/5x/20x, scrub slider, keyboard step. Copied the control set; wired it to the debugger instead of a local cursor. |
| @datacurve/react-code-panes | https://github.com/datacurve-ai/react-code-panes | check repo | Split panes, editor tabs, sidebars, bottom panel as small React parts. Pattern reference; our shell already has these. |
| dockview | https://github.com/mathuo/dockview | MIT | Drag-to-dock tabs and floating groups if the editor area ever needs free layout. Not adopted: too heavy for one extra tab type. |
| kbar | https://github.com/timc1/kbar | MIT | Command palette with sections and fuzzy search. Our Monaco command palette (F1) already covers actions; View dropdown covers the rest. |
| nteract monaco-editor | https://github.com/nteract/nteract | BSD-3 | One Monaco model per notebook cell, cell ids, shared kernel. Reference for percent-format cells (idea 5). |
| NautilusTrader visualization | https://nautilustrader.io/docs/latest/concepts/visualization | LGPL-3.0 (ideas only) | Tearsheet as extensible tabs: equity, drawdown, monthly returns, trades. Our Results tab follows this. |
| QuantStats | https://github.com/ranaroussi/quantstats | Apache-2.0 (v) | Tearsheet metric set and plot list (returns, drawdown, rolling Sharpe, monthly heatmap, return distribution). |
| FreqUI plot configurator | https://github.com/freqtrade/frequi | check repo (Freqtrade is GPL-3.0) | Per-series chart toggles and which pane a series lands in, loaded from the strategy (`plot_config`). Ours: ctx.plot already names the chart; toggle chips in the Chart tab. |
| Jesse | https://github.com/jesse-ai/jesse | MIT | Candle chart with orders and fills drawn from the backtest, per-trade jump. Same as the trade navigator on the Chart page. |
| QuantConnect Lab | https://www.quantconnect.com/docs | closed (ideas only) | Research notebook beside the backtest, results as tabs beside code, Explorer collapse. Basis for Results tab and auto-collapse. |

Decisions: no new dependency. Reuse StudioChart (lightweight-charts) for the Chart tab, add replay cursor and paused-bar marker to it, and drive both from POST /build/debug.

## Ranked ideas

1. Bar replay tied to the debugger: scrub or play bars, editor line and locals follow; makes strategy bugs visible; 1 day.
2. Run any cell or function on a date range and show its returned frame in a Results tab; fastest feedback loop; 1 day.
3. Results as tabs (equity, trades, tearsheet, each run pinned and diffable beside the code); no context switch after a backtest; 1 day.
4. TradingView-grade chart in the preview (lightweight-charts: drawing tools, order and fill markers, indicator panes from ctx.plot, crosshair-synced with debugger); trust in what the code did; 2 to 3 days.
5. Notebook cells (percent-format cells in a .py, inline frames and plots, shared kernel with the backtest data); research and strategy in one file; 2 days.
6. Library and examples browser (tagged starters, one-click insert, versioned shared libraries imported into main.py); removes blank-page time; 1 day.
7. AI help (explain a Problem, fix selection, write a condition from a sentence, explain a trade at the paused bar); lowers the skill bar; 1 to 2 days.
8. Code that can create: custom indicators, data transforms, universe filters, parameter sweeps and plots saved as named artefacts reusable across strategies; 2 days.
9. Split chart and code with synced cursor date; 0.5 day.
10. Command palette for every IDE action with rebindable keys; 0.5 day.

## Feature catalogue (detailed)

30 features, ranked by impact for a quant writing strategies in Studio Build. Each one lives in a view, a dropdown, a palette command or an existing panel, so no new always-visible button is needed. Licences are stated only where the page or the existing table confirmed them; "not checked" means verify before copying any code. Effort is in working days for one person: S under 1 day, M 1 to 3 days, L over 3 days.

### 1. Bar replay tied to the debugger

**What it is:** The user opens the Chart view from the View dropdown and presses Replay. The chart starts at the bar they pick (click any bar, or type a date in the palette). Play, pause, step one bar, and scrub are available from the same strip under the chart, with speed 1x, 5x and 20x. At each bar the editor highlights the line that ran for that bar, and the Locals panel shows values at that bar. Stepping with the arrow keys moves both the chart cursor and the debugger, so a bug can be found by watching the bar where a position was opened or where a stop was skipped. Holding Shift while stepping jumps to the next trade, and the replay stops at each order fill. The paused bar gets a vertical line on the chart and the shaded span of any open position stays visible while paused.

**Why it matters:** Most strategy bugs are timing bugs (a signal read one bar too late, an exit that fires on the entry bar). Watching the bar with the code that produced it is the fastest way to see that. TradingView's Bar Replay is the reference UX for playback and speed control.

**Where it lives in the UI:** Chart view (View dropdown, or the palette command "Replay from date"). Controls sit on the chart's bottom edge and are hidden when the chart is closed. Keyboard: Space plays and pauses, Left and Right step a bar, Shift plus arrows jump to trades.

**How to build it here:** The Chart tab already exists. `frontend/src/modules/studio/build/DevChart.tsx` renders `StudioChart` (from `frontend/src/charts/studio/StudioChart`) with an `upto` cursor and calls the debugger; `DevIDE.tsx` already posts to `POST /build/debug`, and the paused date is passed to `onPause`. Add a play timer that advances the same `at` index that the debugger uses, so the editor and chart share one cursor. Replay controls go in `DevChart.tsx`. The paused-bar line and the held-span shading use lightweight-charts series primitives, as the existing research table decided. Backend: reuse `backend/app/services/studio_v3/core/pyrunner.py` (the debugger's per-bar run); do not run the full backtest again.

**Reuse:** KLineChart Pro (SiMahfud fork, licence stated as Apache-2.0 in the table above) has the play, pause, speed and scrub control set (https://github.com/SiMahfud/klinechartpro). Replay controls are our own code; no dependency needed.

**Effort:** M

**Sources:** https://tradingview.com/support/solutions/43000712747-how-does-bar-replay-work ; https://tradingview.com/blog/en/bar-replay-5913 ; https://github.com/SiMahfud/klinechartpro ; https://tradingview.com/blog/en/synchronized-bar-replay-45933

### 2. Results tabs with pinned, diffable runs

**What it is:** Every backtest run opens as a tab next to the code tab, labelled with the run time and a short parameter string. The user can pin a run so it stays while later runs replace the default tab. Choosing "Compare" next to two pinned runs opens a diff: a table of metrics where the difference and the percentage change are shown, and both equity curves are overlaid on one chart. The user can rename a run, tag it, and close it. Results tabs keep their filters, so opening a tearsheet from one run does not reset a trade filter set on another.

**Why it matters:** A quant rarely wants one run. The real question is "did this change help, and by how much", which needs two results on screen at once. QuantConnect and NautilusTrader both keep results separate from the code, which lets the user keep reading the code while looking at results.

**Where it lives in the UI:** A Results group in the editor tab bar (not a new panel), plus a "Compare runs" palette command. Pinned runs show a pin icon. The Results tab is created by the existing Output or Results path in `DevIDE.tsx`.

**How to build it here:** Frontend: keep runs in a list in `DevIDE.tsx` state keyed by run id, render each run through the existing results renderer, and add a compare view that takes two run ids. Backend: each run already returns a result object from `backend/app/services/studio_v3/core/backtest.py`; store results per run id in memory for the session (no new table). Diffs are computed in the frontend from the two metric objects.

**Reuse:** Ideas only from QuantConnect (closed) and NautilusTrader (LGPL-3.0, ideas only). No code reuse.

**Effort:** M

**Sources:** https://quantconnect.com/docs/v2/cloud-platform/projects/ide ; https://nautilustrader.io/docs/latest/concepts/visualization ; https://tradingview.com/support/solutions/43000763320-how-to-work-with-pine-editor

### 3. Tearsheet view

**What it is:** A Tearsheet view opens from the Results tab and shows one scrollable page with fixed sections in this order: key statistics (CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor, exposure, average hold), returns (cumulative and monthly heatmap), drawdown (underwater curve with the top five drawdowns listed by depth and length), rolling statistics (rolling Sharpe and volatility), return distribution, and crisis or regime periods the user has chosen. Each section has a small gear icon that opens a dropdown to turn sections on or off, and the choice is saved per user. The page can be exported as a self-contained HTML file or printed.

**Why it matters:** The first question after a backtest is "how bad was the worst drawdown and how long did it last". A tearsheet answers that without reading a trade list. The section set below is the standard that QuantStats and NautilusTrader cover, so users coming from those tools will expect it.

**Where it lives in the UI:** Results tab, a "Tearsheet" button in the tab's dropdown. Section toggles are in the gear dropdown, so the page itself has no extra buttons.

**How to build it here:** Frontend: one component with one renderer per section, reusing `StudioChart` for the equity and drawdown charts. Backend: compute the stats from the equity series and trade list in `backend/app/services/studio_v3/core/backtest.py` (or a small helper beside it). Do not add a dependency for the stats if they are short; the formulas are simple.

**Reuse:** QuantStats (Python, licence stated as Apache-2.0 in the table above) for the metric set and plot list: https://github.com/ranaroussi/quantstats . NautilusTrader's tearsheet layout is also a reference (LGPL-3.0, ideas only).

**Effort:** M

**Sources:** https://github.com/ranaroussi/quantstats ; https://quantconnect.com/docs/v2/cloud-platform/backtesting/report ; https://nautilustrader.io/docs/latest/concepts/reports ; https://nautilustrader.io/docs/latest/concepts/visualization

### 4. Walk-forward runner with efficiency score

**What it is:** A Walk-forward option sits in the Optimise dropdown. The user sets the in-sample length, out-of-sample length and step (for example 2 years optimise, 6 months test, step 6 months), and chooses an optimisation target such as Sharpe or CAR/MDD. The runner optimises on each in-sample window, runs the chosen parameters on the next out-of-sample window, and stitches the out-of-sample pieces into one equity curve. The view shows a band chart with blue for in-sample and green for out-of-sample windows, a table with each window's chosen parameters, and a walk-forward efficiency (WFE) figure: the out-of-sample annualised return divided by the in-sample annualised return. A parameter that changes on every window is flagged, because that means the optimiser is fitting noise.

**Why it matters:** A single optimised backtest always looks better than live trading. Walk-forward shows whether the edge survives on data the optimiser never saw. NinjaTrader, Amibroker and Build Alpha all treat it as the standard validation, so quants expect it.

**Where it lives in the UI:** Optimise view, as a mode in the mode dropdown next to "Grid". Results go to a Results tab (feature 2).

**How to build it here:** Backend: `backend/app/services/studio_v3/core/optimise.py` already runs parameter searches. Wrap it: split the bar range into windows, call the existing optimise on each in-sample window, then call `backtest.py` on the next window with the best parameters. Keep the stitching in one function. Frontend: a band chart on `StudioChart`, plus the window table.

**Reuse:** Ideas from NinjaTrader (closed, anchored and standard modes), Amibroker (closed) and Build Alpha (closed). The WFE definition is from Tradelyze's glossary (closed site, read only). No open-source code to copy.

**Effort:** L

**Sources:** https://static.ninjatrader.com/support/helpGuides/nt8/walk_forward_optimize_a_strate.htm ; https://amibroker.com/guide/h_walkforward.html ; https://buildalpha.com/walk-forward-optimization ; https://tradelyze.io/learn/walk-forward-efficiency ; https://www.mql5.com/en/articles/23250

### 5. Monte Carlo robustness panel

**What it is:** A Robustness view runs a Monte Carlo test on a finished backtest. It has two methods. Trade-order shuffling reorders the same set of trades and recomputes the equity curve, which tests whether the timing of the trades matters. Candle resampling changes the price data slightly and reruns the strategy, which tests whether the result depends on exact prices. The user picks the number of runs (default 1000). The view shows the original result as a vertical line on a histogram of the resampled results for each metric (final return, max drawdown, Sharpe), plus a percentile for the original. A verdict card states it in plain words: below the median means the result is weaker than typical, and above the 95th percentile means the backtest may sit in the luckiest tail.

**Why it matters:** One equity curve is one draw from many possible histories. The percentile tells a quant how lucky the backtest was. Jesse explains exactly this split (trade-order shuffling and candle-based testing), and StrategyQuant runs the same family of tests.

**Where it lives in the UI:** Robustness view (View dropdown), and a "Run robustness" command in the palette. It is never on the main toolbar.

**How to build it here:** Backend: add a `robustness` helper next to `backend/app/services/studio_v3/core/backtest.py`. Shuffling needs only the trade list, so it is cheap. Candle resampling needs the data path in `data.py`; run it in a background job, because the runs are slow. Use a fixed seed and return it so results can be reproduced. Frontend: a histogram component with the original marker, drawn from the summary arrays.

**Reuse:** Jesse (MIT, from the existing table) has both methods and a verdict table, documented at https://docs.jesse.trade/docs/monte-carlo . The MC verdict thresholds in its docs are worth copying as text.

**Effort:** L

**Sources:** https://docs.jesse.trade/docs/monte-carlo ; https://strategyquant.com/doc-new/monte-carlo-tests ; https://github.com/jesse-ai/jesse/blob/master/jesse/mcp/resources/monte_carlo.md

### 6. Optimisation explorer with heatmap and parameter importance

**What it is:** The Optimise view shows the results of a grid sweep as a table sorted by the chosen target, with a selector to switch the target without rerunning. Below the table, two parameters can be picked for a heatmap, where each cell is coloured by the target value and the chart is labelled with both parameter values. A parameter importance bar shows which inputs moved the target most. Clicking a cell applies those parameters to the code as a new run. A history line shows the best value found so far against trial number, so the user can see when the search stopped improving.

**Why it matters:** A sweep of 500 combinations is useless unless the user can see the shape of the surface. A heatmap shows whether the best result sits on a broad hill or an isolated spike. Optuna's visualisations (history, importance, parallel coordinates) are the reference set.

**Where it lives in the UI:** Optimise view, with the heatmap in a dropdown ("Plot: heatmap, importance, history"). Clicking a result applies it to the code through the existing parameter editor.

**How to build it here:** Backend: `backend/app/services/studio_v3/core/optimise.py` already produces the sweep rows. Return them as a flat array with one column per parameter plus the metric columns. Frontend: the table is a plain list; the heatmap is a small grid renderer. Importance can be a simple variance-by-parameter calculation, which is enough for a first version.

**Reuse:** Optuna (licence not checked on the page) for the chart definitions: https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/005_visualization.html . Optuna dashboard is a reference for the live history view: https://github.com/optuna/optuna-dashboard .

**Effort:** M

**Sources:** https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/005_visualization.html ; https://github.com/optuna/optuna-dashboard ; https://github.com/Roboquant-AI/tradingview-optimizer ; https://www.metatrader5.com/en/terminal/help/algotrading/visualization

### 7. Parameter plateau and stability view

**What it is:** For a chosen parameter set, the view tests each parameter one step either side of its current value, using the same data, and shows the target for each neighbour. The result is a small table and a line for each parameter: a flat line means the strategy is stable around the chosen value, and a sharp spike means it is fragile. The verdict says "plateau" when most neighbours score within a set tolerance of the chosen value, and "spike" when only the chosen value scores well. The user can apply the best neighbour (the one with the most stable surrounding score) instead of the single best value.

**Why it matters:** Picking the single best parameter is the most common way to overfit. A plateau means small changes in the market should not break the strategy. Build Alpha and StrategyQuant both report parameter stability and parameter jitter for this reason.

**Where it lives in the UI:** A "Stability" tab inside Optimise, reached from the best row's dropdown menu. No extra button on the main bar.

**How to build it here:** Backend: reuse the optimise runner with a fixed grid of neighbours (plus or minus one step), so no new engine is needed. Frontend: a per-parameter line strip and a verdict line. Keep the tolerance as one number in the view, not a setting.

**Reuse:** Build Alpha (closed) is the reference for parameter stability; StrategyQuant's parameter jitter is a related method. Ideas only.

**Effort:** M

**Sources:** https://buildalpha.com/walk-forward-optimization ; https://strategyquant.com/doc-new/monte-carlo-tests ; https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization

### 8. Chart tab drawing layer on the custom chart engine

**What it is:** The Chart tab gets a drawing layer. The user picks a tool from a Draw dropdown (horizontal line, trend line, rectangle, Fibonacci retracement, text note). Drawings snap to bars and to the replay cursor, so a level drawn at the entry bar stays where it was. Drawings are saved with the strategy file as a comment block (or a small sidecar JSON file in the same folder), so they survive reloads and can be shared with the code. Each drawing has an Object tree entry: toggle visibility, select, lock, delete. The tools come from the existing chart engine, so no second drawing system is built.

**Why it matters:** Traders annotate the price action to explain a setup. A strategy that trades a level should be able to show the level on the chart next to the code. The engine already has many drawing tools; the Dev IDE should use them instead of growing a new set.

**Where it lives in the UI:** Chart view, a Draw dropdown on the chart's top edge, and an Objects tab in the right-hand panel. The Draw dropdown contains only tools that are useful for strategy work (about six), with the full set under "More tools".

**How to build it here:** Reuse `frontend/src/components/chart_engine/DrawingEngine/registry.ts` (line, channel, Fibonacci, Gann, pattern, text tools are all registered there) and `frontend/src/components/chart_engine/state/ChartState.ts`. Do not reuse the whole chart container if it is heavy; mount only the drawing layer on top of `StudioChart`. Persist drawings through the existing workspace store in `backend/app/services/studio_v3/core/workspace.py`.

**Reuse:** The repo's own chart engine (no new code). KLineChart Pro (SiMahfud fork) has the object tree and chart templates pattern: https://github.com/SiMahfud/klinechartpro . KLineChart is a lightweight base library: https://github.com/klinecharts/KLineChart (licence not checked on the page).

**Effort:** L

**Sources:** https://github.com/SiMahfud/klinechartpro ; https://klinecharts.com/en-US/guide/introduction ; https://github.com/klinecharts/extension

### 9. Indicator panes from ctx.plot with a plot configurator

**What it is:** Every `ctx.plot(name, value, chart=...)` call in the strategy becomes a series. The Chart tab shows them as chips in a Plots dropdown: a checkbox per series, a choice of pane (overlay on price or its own pane below), a colour, and a line or histogram style. The user can save several plot layouts with names and switch between them, for example "entries" and "volatility". The chips show the value at the paused bar so the user can read an indicator without hovering. The strategy can ship a default layout, which loads when the file is opened.

**Why it matters:** Strategy logic is mostly indicators. Being able to see the indicator the code used, on the same bar, is what turns the chart into a debugging tool. FreqUI has the same concept: a plot configuration loaded from the strategy and switchable.

**Where it lives in the UI:** Chart view, Plots dropdown. No new panel. The default layout is saved in a comment block at the top of the strategy, as FreqUI does with `plot_config`.

**How to build it here:** Backend: `ctx.plot` is implemented in `backend/app/services/studio_v3/core/pyrunner.py` (around line 324), with `chart="own"` as the default. Return series grouped by chart name in the debug payload. Frontend: `DevChart.tsx` already passes `indicators={[]}` to `StudioChart`; fill it from the debug payload, one entry per visible plot, and render the chips.

**Reuse:** FreqUI's plot configurator (Freqtrade is GPL-3.0; idea only, copy no code). Indicator registry in `frontend/src/components/chart_engine/IndicatorEngine/registry.ts` for colours and styles.

**Effort:** M

**Sources:** https://github.com/freqtrade/freqtrade/blob/develop/docs/freq-ui.md ; https://www.freqtrade.io/en/stable/plotting/ ; https://docs.freqtrade.io/en/2026.5/plotting

### 10. Trade navigator with MAE and MFE

**What it is:** A trade list sits under the chart. Each row shows the entry time, side, entry price, exit price, P and L, hold time, and two extra columns: MAE (the worst excursion against the position while it was open) and MFE (the best excursion in the position's favour). Clicking a row moves the chart and the replay cursor to that trade, with the entry and exit marked and the trade's price range shaded. Next and previous buttons (or the keys [ and ]) step through trades. A filter bar can show only losers, only the trades that were stopped out, or trades from one month.

**Why it matters:** The MAE and MFE columns show whether a stop is too tight (large MAE on winners) or an exit leaves money on the table (large MFE on losers). This is the first analysis most discretionary and systematic traders run. Jesse's trade-by-trade view and TradingView's strategy report cover the same ground.

**Where it lives in the UI:** A Trades tab in the Results view, plus the navigator on the Chart view. Filters are a dropdown on the table header.

**How to build it here:** Backend: compute MAE and MFE in `backend/app/services/studio_v3/core/backtest.py` from the bar high and low during each trade's hold. Frontend: a table component and a call into `DevChart.tsx` to set the cursor date.

**Reuse:** Jesse (MIT per the existing table) for the per-trade chart jump pattern. Ideas from TradingView's strategy report (closed).

**Effort:** M

**Sources:** https://www.tradingview.com/pine-script-docs/concepts/strategies ; https://github.com/jesse-ai/jesse ; https://www.metatrader5.com/en/terminal/help/algotrading/visualization

### 11. Percent-format research cells in the .py file

**What it is:** The strategy file may contain research cells, marked with a `# %%` line. A cell can be a title (`# %% [markdown]`) or a code cell. Each code cell has a Run button in its top-left corner, and Shift+Enter runs it and moves to the next cell. The cell's result (a frame, a plot, a printed value) appears under the cell as an inline output, so the research sits in the same file as the strategy. Outputs are not written into the file, which keeps git diffs clean. Cells share one kernel with the backtest data, so a variable defined in a research cell can be used by the strategy's preview run.

**Why it matters:** Quants prototype a signal, check its statistics, then copy it into the strategy. With cells, the prototype and the strategy live in one reviewable file. Jupytext's percent format is widely supported by editors (Spyder, VS Code, PyCharm), so the file stays portable.

**Where it lives in the UI:** A "Cells" toggle in the editor's top bar (from the View dropdown). Cell Run buttons appear only when the toggle is on, so the code view stays clean when it is off.

**How to build it here:** Frontend: `frontend/src/modules/studio/build/CodeEditor.tsx` already wraps Monaco; add code lenses for `# %%` markers and inline output widgets. Backend: `backend/app/services/studio_v3/core/pyrunner.py` runs a snippet against the data already loaded for the preview; add a "run cell" entry point that uses the same runner. Parse cells with a small splitter (no dependency needed; the format is one marker line).

**Reuse:** Jupytext (licence not checked on the page) defines the percent format and its parser behaviour: https://jupytext.org/formats/scripts/ . nteract's Monaco notebook pattern (one model per cell) is a reference: https://github.com/nteract/nteract (BSD-3 per the existing table).

**Effort:** L

**Sources:** https://jupytext.org/formats/scripts/ ; https://jupytext.readthedocs.io/en/latest/formats.html ; https://github.com/mwouts/nbpercent ; https://docs.marimo.io/guides/coming_from/jupytext/

### 12. Run any selection on a date range into a Results tab

**What it is:** The user selects an expression, a function name, or a block of code, presses Run selection, and picks a date range (default: the loaded window; a range picker in the popup). The result opens in a Results tab as a table or chart. Typical uses are "the signal on 2024 only" or "the feature frame for this ticker". The run does not change the strategy state, so the user can repeat it with another range without a full backtest.

**Why it matters:** Feedback time is the main cost of research. Running a small piece of code on a date range in a second, instead of a full backtest in a minute, changes how often a quant tests an idea.

**Where it lives in the UI:** A context-menu item in the editor ("Run selection") and a palette command. The result tab is a Results tab (feature 2).

**How to build it here:** Frontend: the editor's selection is already available in `CodeEditor.tsx`. Backend: call the same single-function runner used by the debugger in `pyrunner.py` with a date filter on `data.py`. Keep it to one function call; do not add a second execution engine.

**Reuse:** Hex SQL cells show the same pattern for queries (licence closed; ideas only): https://learn.hex.tech/docs/explore-data/cells/sql-cells/sql-cells-introduction

**Effort:** S

**Sources:** https://learn.hex.tech/docs/explore-data/cells/sql-cells/sql-cells-introduction ; https://marimo.io/use-cases ; https://docs.marimo.io/getting_started/key_concepts

### 13. Reactive cells that re-run only what depends on a change

**What it is:** In a research cell file, changing one cell re-runs only the cells that read a variable it defines, and marks the rest as stale without running them. The stale cells show a grey dot. A toggle in the cell toolbar switches between "run on change" and "manual", so a slow cell does not block typing. The user sees which cells are stale and can run them in order from one button.

**Why it matters:** The usual notebook problem is hidden state: a cell run out of order gives a result that the file does not reproduce. Reactive execution makes the file reproducible. marimo's docs stress this as its main difference from Jupyter.

**Where it lives in the UI:** A cell toolbar toggle and a "Run stale cells" palette command. No new panel.

**How to build it here:** Parse each cell for names it assigns and names it reads (Python `ast` on the cell, no dependency). Build a dependency map in `CodeEditor.tsx` and mark the downstream cells. Run order uses the same runner as feature 11.

**Reuse:** marimo (licence not checked on the page; its docs say it is an open-source Python notebook): https://github.com/marimo-team/marimo . Use its key concepts as the spec.

**Effort:** L

**Sources:** https://docs.marimo.io/getting_started/key_concepts ; https://github.com/marimo-team/marimo ; https://marimo.io

### 14. SQL cells over the local data store

**What it is:** A research cell can be SQL instead of Python. The user writes a query against the market data tables (for example `SELECT symbol, date, close FROM bars WHERE ...`), and the result becomes a variable that Python cells can read. Autocomplete offers table and column names from the data browser. A parameter box in the cell (a symbol, a start date) is read from the query with a placeholder, so one query serves several tickers.

**Why it matters:** Many research questions are a grouping or a join over the universe ("average gap by weekday for all symbols"). SQL is faster to write for that than pandas, and the result can be piped into Python for the strategy.

**Where it lives in the UI:** A cell type choice ("Python / SQL") on the cell toolbar. The table list lives in the Data view (feature 15).

**How to build it here:** Backend: `backend/app/services/studio_v3/core/data.py` holds the data access. Run SQL through DuckDB over the same files; DuckDB is a new dependency, so check the owner's approval first (AGENTS.md requires approval for new dependencies). A fallback without a dependency: restrict SQL to a fixed set of group-by templates. Frontend: a SQL cell editor in `CodeEditor.tsx`.

**Reuse:** Hex SQL cells (closed; ideas only). DuckDB (licence not checked on this page).

**Effort:** L

**Sources:** https://learn.hex.tech/docs/explore-data/cells/sql-cells/sql-cells-introduction ; https://hex.tech/blog/sql-notebooks ; https://hex.tech/product/notebooks

### 15. Data browser with a coverage map and quality checks

**What it is:** A Data view lists the symbols and timeframes in the workspace. For each symbol it shows a coverage bar (a timeline with gaps in a warning colour), the first and last bar, and counts of quality problems: missing bars, zero-volume bars, a price jump bigger than a set threshold (likely a split), and duplicate timestamps. Clicking a symbol opens its chart and a small table of the first and last bars. A "Use in strategy" button adds the symbol to the file's universe or a `ctx.data` call, and the choice is shown in the palette.

**Why it matters:** Bad data produces bad backtests that look good. A coverage view shows that a strategy that trades 2019 to 2024 is missing a year for one symbol, and a quality check catches an unadjusted split before it looks like a 90 percent loss.

**Where it lives in the UI:** A Data view in the activity bar (one icon), with a Data dropdown in the editor for quick insert. No new always-visible button elsewhere.

**How to build it here:** Backend: `backend/app/services/studio_v3/core/data.py` and `store.py` already hold the bars; add a `coverage` function that returns gap ranges and quality counts for one symbol. Keep it read-only. Frontend: a coverage strip component and the existing chart for a selected symbol.

**Reuse:** Idea only; no library needed. No data-view page was read, so treat the layout as our own design.

**Effort:** M

**Sources:** https://quantconnect.com/docs/v2/cloud-platform/research/getting-started ; https://quantconnect.com/docs/v2/research-environment/key-concepts/research-engine ; https://www.zipline.io (Zipline Pipeline factor reference) ; https://www.quantrocket.com/code/

### 16. Debugger locals quick-look

**What it is:** In the Locals panel of the debugger, every variable is clickable. A pandas frame or a Series opens a small popup table with the first and last rows, the shape, the dtypes and the column summary. A numeric series opens a mini sparkline across the replay window. A value that is a list of trades opens the trade navigator (feature 10). The popup closes on Escape and stays put while the replay moves, so the user can compare the value on two bars by stepping.

**Why it matters:** The usual way to see a variable is a print statement, which adds noise and needs a re-run. A click shows the value at the paused bar with no code change, which keeps the debugger honest.

**Where it lives in the UI:** Locals panel (already in the debugger) and a Shift+click shortcut in the editor. No extra panel.

**How to build it here:** Backend: `pyrunner.py` already returns locals at a bar; add a serialisation step for frames and series (head, tail, dtypes) with a size cap. Frontend: a popup component in `DevIDE.tsx`'s debugger area.

**Reuse:** VS Code's variables panel and data viewer are the UX reference (Microsoft, MIT; not checked on the page): https://code.visualstudio.com/docs/editing/getting-started/userinterface

**Effort:** S

**Sources:** https://code.visualstudio.com/docs/editing/getting-started/userinterface ; https://vscode-docs.readthedocs.io/en/stable/editor/debugging ; https://stackoverflow.com/questions/60097076/view-dataframe-while-debugging-in-vs-code

### 17. Snippet and indicator library with tags

**What it is:** A Library dropdown lists snippets: named blocks of code (a trailing stop, a volatility filter, a session time check) with tags, a one-line description, and an "Insert" action that places the snippet at the cursor and adds any imports it needs. Users can save a selection as a snippet, tag it, and share it inside the workspace. Each snippet can be tested from its entry: a small run on one symbol, with the result shown in a Results tab, so the user knows it works before inserting it.

**Why it matters:** Strategies reuse the same building blocks. A library turns those into one click, and the test-on-insert step stops a broken snippet from entering a strategy.

**Where it lives in the UI:** Library dropdown in the editor top bar, plus a palette command "Insert snippet". The library view is a list inside the dropdown, not a new panel.

**How to build it here:** Backend: `backend/app/services/studio_v3/core/library.py` already exists; extend it with tags and the test run. Frontend: the Library dropdown uses the same list pattern as `Palette.tsx`.

**Reuse:** Monaco snippet controller (licence not checked on this page) for insert and tab stops: https://microsoft.github.io/monaco-editor/ . Jesse's strategy examples are a reference for what to ship: https://jesse.trade/

**Effort:** S

**Sources:** https://microsoft.github.io/monaco-editor/ ; https://stackoverflow.com/questions/48212023/how-to-insert-snippet-in-monaco-editor ; https://docs.jesse.trade/

### 18. Starter gallery with cached results

**What it is:** The New strategy dropdown lists starters by type (trend, mean reversion, breakout, options-style rules), each with a short description and a thumbnail of the equity curve from a cached run on a fixed universe. Opening a starter copies it into a new file with the code and the parameters set to tested defaults. The thumbnail is a stored image from the last run, so the gallery opens instantly. Each starter links to the library snippets it uses.

**Why it matters:** The blank file is the biggest barrier for a new user. A gallery with visible results shows what a good starting point looks like and lets the user compare before writing a line.

**Where it lives in the UI:** The New dropdown in the Build home (`frontend/src/modules/studio/build/home` area), with no extra button.

**How to build it here:** `frontend/src/modules/studio/build/recipes.ts` already holds starter recipes; add a cached result per recipe. Backend: `backend/app/services/studio_v3/core/templates.py` holds the starter code, so add a run step that stores one summary per template.

**Reuse:** Composer's marketplace shows historical backtests for each strategy (closed; idea only): https://www.composer.trade/ai

**Effort:** S

**Sources:** https://www.composer.trade/ai ; https://apps.apple.com/us/app/composer-by-sofi/id6471564746 ; https://composer.trade/pricing

### 19. Shareable read-only strategy link with pinned results

**What it is:** The Share dropdown creates a link to a snapshot of the strategy file and one pinned result. The viewer sees the code, the results tab, the tearsheet, and a Clone button that copies the file into the viewer's own workspace. The snapshot does not change when the author edits later. The viewer cannot run the strategy with new data unless they clone it. Access can be set to "anyone with the link" or to named workspace members.

**Why it matters:** Quants want to show a result to a colleague or a client without a screenshot, and the colleague must be able to inspect the code behind it. QuantConnect shares a backtest link with the cloned project for this.

**Where it lives in the UI:** Share dropdown in the editor top bar.

**How to build it here:** Backend: `backend/app/services/studio_v3/core/store.py` for the snapshot, with a read-only route and a clone route. Frontend: a read-only mode of the Build page that disables editing. Auth: reuse the existing workspace permissions; do not invent a new access model.

**Reuse:** QuantConnect's backtest sharing (closed; idea only): https://quantconnect.com/docs/v2/cloud-platform/research/deployment

**Effort:** M

**Sources:** https://quantconnect.com/docs/v2/cloud-platform/research/deployment

### 20. Review comments on code lines and chart bars

**What it is:** A user can add a comment to a code line or to a bar on the chart. A comment on a bar keeps the bar's date, so it appears at the same point when someone replays. Comments show as small markers in the gutter and on the chart, and open in a thread with replies and a resolve tick. The author can filter to open comments. Comments are stored with the strategy snapshot and do not change the code.

**Why it matters:** Strategy review is usually done by message, which loses the context. A comment on a bar ties the discussion to the exact bar the reviewer means.

**Where it lives in the UI:** A comment icon in the gutter and a Comments tab in the right-hand panel. No always-visible button.

**How to build it here:** Store comments on the workspace record in `backend/app/services/studio_v3/core/workspace.py`, keyed by file, line or bar date. Frontend: gutter decorations in `CodeEditor.tsx` and markers in `DevChart.tsx`.

**Reuse:** Monaco's decoration API (not checked on the page) and the drawing object tree pattern from feature 8.

**Effort:** M

**Sources:** https://microsoft.github.io/monaco-editor/ ; https://github.com/SiMahfud/klinechartpro

### 21. AI explains the paused bar and fixes a selection

**What it is:** When the debugger is paused, an "Explain this bar" item in the Debug menu sends the paused bar's values, the executed lines and the open position to the AI model. The reply is a short explanation in the Output tab: why the strategy entered or did not enter, and which condition decided it. A second action, Cmd+K on a selected block, asks for a change ("make the stop volatility-based"). The AI returns a diff that the user accepts or rejects in the editor. Nothing is applied without a click, and the AI cannot run a backtest by itself.

**Why it matters:** A quant often knows the strategy's intent but not why one bar behaved differently. A plain explanation at the bar is quicker than rereading the code, and the diff step keeps the user in control of the code.

**Where it lives in the UI:** The Debug menu (explain) and the editor's Cmd+K inline edit. No new panel.

**How to build it here:** Backend: a route that builds the prompt from the debug payload (`POST /build/debug` output) and returns text or a diff. Frontend: inline diff in `CodeEditor.tsx`. Keep the model call server-side. Check the AI route's existing auth and rate limits in `backend/app/services/studio_v3/core/` before adding one.

**Reuse:** Cursor's inline edit (closed; idea only): https://cursor.com/help/ai-features/inline-edit . Cursor's Agent is the reference for keeping edits behind an accept step.

**Effort:** M

**Sources:** https://cursor.com/help/ai-features/inline-edit ; https://cursor.com/docs/agent/overview ; https://dev.to/_d7eb1c1703182e3ce1782/cursor-ai-editor-a-developers-complete-review-2026-noc

### 22. AI robustness critic

**What it is:** After a robustness run (features 4 to 7), a "Critique" button in the Robustness view sends the summary numbers to the AI model. The reply lists what the tests show in plain words, names the weakest test, and suggests the next test to run (for example "the result is a spike in the ATR multiplier; run the stability view on that parameter"). It never changes parameters. Each suggestion has a Run button that starts the named test, so the AI proposes and the user decides.

**Why it matters:** Most traders do not know which robustness test to run next or how to read a histogram. The critic points at the right test and explains the verdict, which teaches the user as well as helping them.

**Where it lives in the UI:** A Critique action in the Robustness view. No new panel.

**How to build it here:** Backend: the same route as feature 21, fed with the robustness summary arrays instead of the debugger payload. Frontend: a text card in the Robustness view with suggestion buttons that call the existing run functions.

**Reuse:** Build Alpha's robustness suite (closed; the list of tests is a reference): https://buildalpha.com/features

**Effort:** S

**Sources:** https://buildalpha.com/features ; https://www.buildalpha.com/noise-test-parameter-optimization/ ; https://buildalpha.com/walk-forward-optimization

### 23. Paper trading hook with live-versus-backtest divergence

**What it is:** A Live dropdown lets the user send the strategy to paper trading with one of the connected brokers. The Live view shows the paper equity against the backtest equity for the same period, with a divergence line and a count of trades that were expected but not filled, and filled at a worse price. A threshold sets an alert when the divergence passes a limit, so the user sees a broken assumption (slippage, fill timing) before real money is involved. Orders in paper mode are simulated by the broker, not by Studio, so the test is the broker's behaviour.

**Why it matters:** Backtests assume fills that live markets do not give. A divergence view shows the gap in one chart. Alpaca's paper environment runs the same order flow as live except that orders are not routed to an exchange, which makes it a safe test bed.

**Where it lives in the UI:** Live dropdown in the editor top bar, and a Live view for the running strategy. The send action asks for confirmation.

**How to build it here:** Backend: `backend/app/services/studio_v3/core/live.py` and `fills.py` already exist; reuse them for the paper hook and record the fills. Divergence is computed from the recorded fills and the backtest trade list. Frontend: a chart with two lines and a table.

**Reuse:** Alpaca paper trading (API; the Python SDK's licence not checked on the page): https://docs.alpaca.markets/us/docs/paper-trading . Freqtrade's dry-run mode is the reference for a paper run (GPL-3.0; idea only).

**Effort:** L

**Sources:** https://docs.alpaca.markets/us/docs/paper-trading ; https://www.freqtrade.io/en/stable/ ; https://www.freqtrade.io/en/stable/hyperopt/

### 24. Live status and kill switch panel

**What it is:** A Live status view lists the strategies that are running live or in paper, with their open positions, today's P and L, the time of the last bar, and the last error. Each strategy has Start, Stop and Flatten buttons, and Flatten asks for a confirmation that names the number of open positions. Errors are shown with the bar and the line where they happened, which links back to the editor. A global Stop-all sits in the palette, not on the toolbar.

**Why it matters:** When a live strategy misbehaves, the trader needs one place to see the state and to stop it. The kill switch must be easy to find and hard to press by accident.

**Where it lives in the UI:** A Live view (from the View dropdown), and a palette command "Stop all live strategies".

**How to build it here:** Backend: `backend/app/services/studio_v3/core/live.py` already tracks run state; expose start, stop and flatten through the existing route pattern. Frontend: a list view in the Live view, and a confirmation dialog.

**Reuse:** FreqUI's trade view (GPL-3.0; idea only): https://github.com/freqtrade/freqtrade/raw/refs/heads/develop/docs/freq-ui.md

**Effort:** M

**Sources:** https://github.com/freqtrade/freqtrade/raw/refs/heads/develop/docs/freq-ui.md ; https://www.freqtrade.io/en/stable/ ; https://jesse.trade/blog/news/jesse-300-a-new-charting-and-live-trading-experience

### 25. Command palette for every action and go-to-date

**What it is:** The palette (Cmd+Shift+P, already in the app) lists every IDE action, including the ones now in the View, Optimise and Live dropdowns. Typing filters by name, and each command shows its key binding. Two special commands are added: "Go to date" (type 2021-03-04 and the chart, the editor's date variable and the replay cursor move there) and "Go to symbol" (jump to a function or a parameter in the file). Recently used commands sit at the top. The palette is the way to reach a feature that has no button.

**Why it matters:** A power user should never need the mouse for a feature they know by name. Go-to-date is the single most useful jump in a strategy IDE, because the question is almost always about one bar.

**Where it lives in the UI:** Palette, opened from the existing Commands button (⌘⇧P). No new button.

**How to build it here:** `frontend/src/modules/studio/build/Palette.tsx` already takes a `commands` array, and `BuildPage.tsx` already builds the list and handles ⌘⇧P. Add the new commands to that array and a date and symbol matcher. Monaco's symbol list (outline) feeds Go to symbol.

**Reuse:** JupyterLab's command palette (licence not checked on the page) is the reference for command ids and the recent list: https://jupyterlab.readthedocs.io/en/stable/user/commands.html . kbar (MIT per the existing table) is the fuzzy-search reference, not a dependency.

**Effort:** S

**Sources:** https://jupyterlab.readthedocs.io/en/stable/user/commands.html ; https://jupyterlab.readthedocs.io/en/3.3.x/user/commands.html ; https://microsoft.github.io/monaco-editor/api/enums/monaco.keycode.html

### 26. Rebindable keymap with chords

**What it is:** A Keyboard shortcuts section in the palette lets the user see every shortcut in a list and rebind any of them. Chords (two-key sequences such as Ctrl+K then Ctrl+R) are allowed for less-used commands. Conflicts are shown at the time of binding. The keymap is saved per user, and a preset (Default, Vim-like movement for the editor) can be chosen from a dropdown. Shortcuts are shown in every menu and in the palette list.

**Why it matters:** The IDE will have many commands, and a fixed keymap limits how fast a power user can work. A rebindable keymap is a standard expectation in VS Code and Cursor.

**Where it lives in the UI:** Palette command "Keyboard shortcuts", opened as a list. No button.

**How to build it here:** Monaco's `addAction` takes keybindings (the Monaco API lists them as KeyMod and KeyCode values), so the commands from feature 25 can carry a user binding. Store the map in a per-user setting through the existing settings store. Do not add a keybinding library; the Monaco and window handlers are enough.

**Reuse:** Monaco keybinding API (licence not checked on this page): https://microsoft.github.io/monaco-editor/api/enums/monaco.keycode.html . The issue thread on rebinding is a useful warning about conflicts: https://github.com/microsoft/monaco-editor/issues/102

**Effort:** M

**Sources:** https://github.com/microsoft/monaco-editor/issues/102 ; https://rikki.dev/posts/monaco-command-palette ; https://raw.githubusercontent.com/CodinGame/monaco-vscode-api/main/demo/src/main.views.ts

### 27. Saved layouts and workspace presets

**What it is:** The View dropdown has a Layout section with named presets: "Research" (code and cells, with the Chart docked to the right), "Debug" (code and debugger, Chart and Locals below), "Review" (Results and Tearsheet full width), and "Live" (Live status and code). The user can save the current arrangement under a name, reset to a preset, and rename or delete their own. The Explorer auto-collapses at narrow widths, which is already in place, and the presets respect that rule.

**Why it matters:** A quant switches between writing, debugging and reviewing many times a day. One click to the right arrangement saves time and keeps each task uncluttered.

**Where it lives in the UI:** View dropdown, Layout section. No button on the main bar.

**How to build it here:** The IDE shell already has panel state in `DevIDE.tsx` (the Explorer auto-collapse at narrow widths and the Dev activity bar). Store the panel sizes and positions per preset. Persist in the per-user settings. Do not adopt a docking library unless a free-floating layout is wanted.

**Reuse:** dockview (MIT per the existing table) is the reference if free layout is ever needed: https://github.com/mathuo/dockview . VS Code's layout docs are the spec: https://code.visualstudio.com/docs/editing/getting-started/userinterface

**Effort:** M

**Sources:** https://code.visualstudio.com/docs/editing/getting-started/userinterface ; https://stackoverflow.com/questions/57333905/vs-code-move-debug-tab-left-panel-to-bottom ; https://github.com/microsoft/vscode/issues/118975

### 28. Pop-out windows for chart and results

**What it is:** A small button-free action in the View menu, "Pop out chart", opens the Chart or a Results tab in a separate browser window that stays synced with the main window: the replay cursor, the selected run and the date are shared. On a second monitor the user can keep the code and the chart side by side. Closing the pop-out returns the panel to the main window.

**Why it matters:** Replay plus code plus results need more space than one laptop screen. A synced pop-out gives the space without a second copy of the data.

**Where it lives in the UI:** View dropdown, "Pop out" submenu. No always-visible button.

**How to build it here:** Frontend: a second route that renders the Chart and Results components, with the shared state in a small store or the `BroadcastChannel` API. Backend: none beyond the existing data calls.

**Reuse:** Ideas only from VS Code's detachable views. No library needed.

**Effort:** M

**Sources:** https://code.visualstudio.com/docs/editing/getting-started/userinterface ; https://github.com/microsoft/vscode/issues/118975

### 29. Parameter jitter and execution-degradation stress test

**What it is:** A Stress tab in the Robustness view runs the strategy again with each parameter moved by a random percentage (for example plus or minus 10 percent), with commission and slippage raised by a set factor, and with the price history perturbed a little. The result is a fan chart of equity curves and a table of how often the strategy still beats a set target. The test says whether the result depends on exact inputs or on cheap fills. Each stress setting has a plain-language label, and the defaults are the ones the owner chooses.

**Why it matters:** A strategy that works only with exact parameters and perfect fills will fail live. The stress test shows how much room the edge has before the costs and noise erase it.

**Where it lives in the UI:** Robustness view, Stress tab. No button on the main bar.

**How to build it here:** Backend: reuse `backend/app/services/studio_v3/core/backtest.py` and `fills.py` with a perturbation argument. The perturbations are simple multiplications on inputs and fill prices. Frontend: the fan chart uses `StudioChart` with several series.

**Reuse:** StrategyQuant's parameter jitter and execution degradation (closed; ideas only): https://strategyquant.com/doc-new/monte-carlo-tests

**Effort:** M

**Sources:** https://strategyquant.com/doc-new/monte-carlo-tests ; https://strategyquant.com/blog/new-robustness-tests-on-the-strategyquant-codebase-5-monte-carlo-methods-to-bulletproof-your-trading-strategies ; https://github.com/Roboquant-AI/tradingview-optimizer

### 30. Chart templates and chart types

**What it is:** The Chart view's Style dropdown offers chart types (candles, hollow candles, Heikin Ashi, bars, line, area) and saved templates. A template stores the chart type, the colours, the visible plot chips (feature 9), and the drawings (feature 8) that are not tied to one file. Templates can be applied to any strategy, which is useful for a standard look across the team. The template list is in the dropdown, with a Save as template action at the bottom.

**Why it matters:** Chart style is a small thing, but a consistent look across strategies speeds up reading them. Templates also let a team agree a standard view for review.

**Where it lives in the UI:** Style dropdown on the Chart view. No new button.

**How to build it here:** `StudioChart` already sets the series type (lightweight-charts supports candles, bars, line and area series). Map the dropdown to the series type and store templates per user. The chart engine's style presets in `frontend/src/components/chart_engine/` can be reused for colours.

**Reuse:** KLineChart Pro (licence stated as Apache-2.0 in the existing table) has six chart types and a template store: https://github.com/SiMahfud/klinechartpro . KLineChart: https://klinecharts.com/en-US/guide/introduction

**Effort:** S

**Sources:** https://github.com/SiMahfud/klinechartpro ; https://klinecharts.com/en-US/guide/introduction ; https://github.com/klinecharts/KLineChart

## Build order

1. Command palette additions and go-to-date (25), so every later feature is reachable from one place. S.
2. Debugger locals quick-look (16) and run-selection on a date range (12). Both reuse the debugger path. S.
3. Bar replay tied to the debugger (1), the most-used feature in the ranked list above. M.
4. Results tabs with pinned runs (2) and the trade navigator with MAE and MFE (10). M.
5. Tearsheet view (3) and chart drawing layer (8). M and L.
6. Indicator panes and chart templates (9, 30). M and S.
7. Optimisation explorer (6) and parameter plateau view (7). M.
8. Monte Carlo panel (5) and the stress test (29). L and M.
9. Walk-forward runner (4). L; it depends on the optimiser in step 7.
10. Percent-format research cells (11), then reactive cells (13) and SQL cells (14, only after dependency approval). L.
11. Data browser with coverage and quality checks (15). M.
12. Library, starter gallery and shared read-only links (17, 18, 19). S to M.
13. AI explain and critique (21, 22), kept behind an accept step. M and S.
14. Paper trading hook and divergence view (23), then live status and kill switch (24). L and M. Do these only after the owner approves live-trading scope.
15. Review comments (20), keymap (26), layouts (27), pop-out windows (28). M each.
