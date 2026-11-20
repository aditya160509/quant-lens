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
