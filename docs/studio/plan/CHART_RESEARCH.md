# Studio v3 Chart workspace: research and engine decision

Research date 2026-11-20. Every claim carries a URL. "(unverified)" means I did not confirm it from a primary source or by running code. Repo facts (licence, stars, push date) come from the GitHub API on 2026-11-20.

## 0. Summary

- **Status on 2026-11-23 (every tagged item checked against the code):** 38 ✅ built, 37 ◐ partly built, 30 ⬜ not built, 12 ⏸ not planned now. Since this file was written, Studio moved to Vela (`@luxalgo/vela`) in the Build chart; the engine notes below are the original research.
- **Recommendation: keep and extend our own engine (`frontend/src/components/chart_engine`, Q360ChartCore).** Do not replace it. Gate that decision on one measured spike: pan and zoom 100k bars at 60 fps (section 3.3). If it fails, swap only the bar and indicator renderer, not the drawing, state or UI layers.
- **Strongest alternative if the spike fails: LuxAlgo Vela** (Apache-2.0, WebGL2, about 67 drawing tools, 70+ native indicators, panes API, plugin SDK, a pluggable `ScriptingEngine` port). It is four months old and pre-1.0, so it is a fallback and a reference, not the base.
- TakeProfit's useful ideas are almost all product design, not engine tech: the Inputs/Outputs settings split generated from code, named panes, Object Tree, drawing search and radial wheel, sync levels, link channels, a strategy tester with a full risk table, and a fork-any-built-in-indicator flow. Section 1.9 maps each to our Python `ctx` API.
- Biggest licence trap found: **PineTS is AGPL-3.0** (dual-licensed commercial). Do not bundle it in a distributed or network-served product without a commercial licence. We do not need it: our scripts are Python and run on the backend.

## 1. TakeProfit

Source index: https://takeprofit.com/docs/llms.txt (the full page list; every `.md` URL below is fetchable). Blog and changelog: the platform changelog is at https://takeprofit.com/docs/guide/changelog and the language changelog at https://takeprofit.com/docs/indie/Changelog. `takeprofit.com/blog` returned 404; the blog lives at https://takeprofit.com/@TakeProfit (listed in llms.txt, not read).

### 1.1 The Indie language

- Python subset plus decorators, runs **server-side in a sandbox**; every built-in indicator is written in Indie and open to fork. https://takeprofit.com/docs/indie/What-is-Indie.md and https://takeprofit.com/docs/indie/Why-Indie.md
- Versioned with a comment directive `# indie:lang_version = 5`. Latest release in the changelog: v5.19.0 (7 Oct 2026). https://takeprofit.com/docs/indie/Changelog.md
- Differences from Python that matter: block-level scoping, mandatory type declarations where not inferable, `int` is 32-bit, `None` only through `Optional[T]`, only `list[T]`, `dict[K,V]`, `tuple`, no nested functions, lambdas, `try/except`, `with`, `set`. https://takeprofit.com/docs/indie/Language-differences-with-Python.md
- Entry point is `Main`, either a function `def Main(self, ...)` or a class `Main(MainContext)` with `__init__` and `calc`. The script is one file: imports, helpers, classes, Main. https://takeprofit.com/docs/indie/Indicator-code-structure.md

```
@indicator('Aroon', format=format.PRICE)
@param.int('length', default=14, min=1)
@plot.line(color=color.BLUE, title='Aroon Down')
@plot.line(color=color.YELLOW, title='Aroon Up')
def Main(self, length):
    ...
    return down, up
```
(from https://takeprofit.com/docs/indie/Overview)

### 1.2 Series model

- `self.close[0]` is the current bar, `[1]` the previous. Built-in `open/high/low/close/volume` are read-only `SeriesF`. https://takeprofit.com/docs/indie/Algorithms-for-series-processing.md
- State across bars: `MutSeriesF.new(v)` writes `[0]` and keeps history; `Var[int].new(init=0)` with `.get()/.set()` for scalars (used in the strategy examples at https://takeprofit.com/docs/indie/Strategies/Orders.md).
- Stateful building blocks: `@algorithm` turns a function into a class with a sliding window; call as `Sma.new(self.close, 20)[0]`. https://takeprofit.com/docs/indie/How-Indies-syntactic-sugar-works.md
- Library: `indie.algorithms` (Sma, Ema, Rsi, Adx, Highest, Lowest, SinceHighest, CumSum, Mfv, ...), `indie.math` (cross), `indie.schedule` (trading sessions), `statistics`, `datetime`, `dataclasses`. https://takeprofit.com/docs/indie/Library-reference-overview.md
- Other instruments and timeframes: `@sec_context` plus `self.calc_on(SecMain, exchange, ticker, time_frame, source=Csv, lookahead=False)`, only callable from `__init__`. https://takeprofit.com/docs/indie/Request-additional-instruments.md
- External data: your own CSV candles or typed rows, and live WebSocket/SSE feeds via `sources.DataFeed`. https://takeprofit.com/docs/indie/External-data/External-data-overview.md and https://takeprofit.com/docs/indie/External-data/Live-data-from-a-feed.md
- Order-flow data: TPO and Volume Footprint profile requests. https://takeprofit.com/docs/indie/Profile-data/TPO-profiles.md

### 1.3 Inputs

- `@param.int|float|bool|str|source|time_frame('id', default=..., title=, min=, max=, options=)`; the function argument name must equal the id. https://takeprofit.com/docs/indie/Input-parameters.md
- The settings dialog is generated: a collapsible **Inputs** section (calculation) and **Outputs** section (colour, style, thickness slider, per-plot visibility), plus **Reset Settings**. https://takeprofit.com/docs/guide/platform/ide-widget/indicator-settings.md

### 1.4 Plotting and drawing API

Two systems, deliberately separate. https://takeprofit.com/docs/indie/Plotting-and-drawing/Plotting-and-drawing-overview.md

1. **Plots** (series, one value per bar, alertable, cannot erase history): line, marker, steps, histogram, columns (relative width 0 to 1), candles (an independent OHLC series), data grid, background, bar colour, fill between two plots (single or per-bar colour with offset), static levels and bands. Decorators declare the style at compile time, the return tuple supplies values and must match the number of `@plot.*` decorators. A bare `return float` plots a line. https://takeprofit.com/docs/indie/Plotting-and-drawing/Data-plotting-lines-columns-etc.md and https://takeprofit.com/docs/indie/Plotting-and-drawing/Fills-levels-and-bands.md
2. **Drawings** (coordinate based, can be changed or erased later, not alertable): `self.chart.draw(item)`, update by mutating the field and redrawing, `self.chart.erase(item)`. Types: line segments (arrowheads, extend to ray), rectangles, circles, triangles, channels, labels, tables. Positions: `AbsolutePosition(time, price)` or `RelativePosition` anchored to a chart corner (TOP_LEFT ... BOTTOM_RIGHT) for stats overlays. https://takeprofit.com/docs/indie/Plotting-and-drawing/Drawings-lines-labels.md

### 1.5 How indicators render and multi-pane

- `@indicator(..., overlay_main_pane=True)` draws on price; default is its own pane below. https://takeprofit.com/docs/indie/Plotting-and-drawing/Data-plotting-lines-columns-etc.md
- Pane management in the Object Tree: drag to reorder, drag the divider to resize (heights persist), minimize to a compact strip, double-click a pane to maximize and again to restore, move up/down, hide, remove. https://takeprofit.com/docs/guide/platform/chart-widget/Object-tree.md
- Scripts run server-side, so a cloud alert on a script keeps running with every tab closed. https://takeprofit.com/docs/indie/Why-Indie.md

### 1.6 Strategies and backtesting

- `@strategy(...)` replaces `@indicator`; `self` becomes `MainStrategyContext` with `self.trading` (`cash`, `position.size`, `place_order`, `amend_order`, `cancel_order`). One instrument traded at a time; `calc_on` data for analysis only. https://takeprofit.com/docs/indie/Strategies/Strategies-overview.md
- Orders use a builder: `place_order(side, size).limit(p).stop(p).take_profit(stop=, limit=).stop_loss(stop=).submit()`. Status lifecycle includes REJECTED when cash or leverage is insufficient. https://takeprofit.com/docs/indie/Strategies/Orders.md
- Strategy parameters: `initial_capital`, `commission=Commission(v, PERCENT|FIXED)`, `leverage`, `intrabar_order_filter` (NO_FILTER, ON_BAR_CLOSE, FIRST_IN_BAR, LAST_IN_BAR), `market_order_price` (MARKET_PRICE, ORDER_CREATION_PRICE, BAR_OPEN_PRICE), `risk_free_rate`. https://takeprofit.com/docs/indie/Strategies/Strategy-params.md
- Mechanics: same code backtests and trades live; orders take effect **one tick later, never instantly**; margin call and stop-out are modelled on the strategy's own books. https://takeprofit.com/docs/indie/Strategies/Strategy-mechanics.md
- Tester widget: built-in strategies (ADX Breakout, MACD, MA Cross, RSI, Price Channel, Consecutive Up/Down, Inside/Outside Bar), settings panel with instant rerun, start and end date pickers (end "Now" gives forward testing), data capped by plan (5,000 candles Freeroll, 20,000 All-In). https://takeprofit.com/docs/guide/platform/backtesting-widget/backtest-widget.md
- Stats sections: Core (total P&L, win rate, profit factor, trades, wins/losses, average trade, expectancy, risk-reward); Capital and returns (initial/final, realized/unrealized, annualized, buy and hold, average monthly, min/max equity); Risk (max/avg drawdown, number of drawdowns, max drawdown duration, Sharpe); Volatility and recovery (Sortino, Calmar, daily std, daily VaR 95/99, annualized vol, average/max recovery time); Trade quality (best/worst trade, commission-to-profit). Tabs: Trades (id, side, entry/exit time, duration, P&L, cumulative P&L, drawdown, run-up) and Orders (id, type, price, qty, exposure, fee). Visuals: equity curve, drawdown chart, position activity, trade distribution. Side-by-side compare by opening two tester widgets. Same source.
- Built-in bots (Grid, DCA, Infinity Grid, Buy the Dip, Scheduled DCA, TWAP) are the built-in strategies running live. https://takeprofit.com/docs/indie/Strategies/Built-in-trading-bots.md (title only, page not read)

### 1.7 Marketplace and community

- Indicators and strategies are published from the IDE with a Publish button; free or paid; filters Free/Paid; "Add to Chart" from the marketplace page. Seller share 80% of platform sales, 100% of referred sales. https://takeprofit.com/docs/guide/monetization-tools/Sell-your-indicators.md
- **Invite-only** scripts: private, unlisted, access granted by an API call from Stripe/Whop/Zapier; script executes server-side so source stays hidden; requires a paid plan. https://takeprofit.com/docs/guide/changelog (6 Nov 2026 entry)
- Community posts embed live charts, indicator code and screeners; paid posts; feed widget. https://takeprofit.com/docs/guide/community/Community-overview.md (title only, not read in full)
- AI: IDE assistant writes, converts (Pine, MQL5), debugs; an **MCP server** lets Claude/Codex/Cursor write code and validate it against the real Indie compiler, and since v5.19.0 also use private scripts and alerts. https://takeprofit.com/docs/indie/What-is-Indie.md and https://takeprofit.com/docs/indie/Changelog.md

### 1.8 Workspace, widgets, drawing tools

- **Workspaces**: tabs in the header, right-click for pin, rename (F2), duplicate (with widgets and drawings), delete; drag to reorder; templates or blank; themes Dark/Light/System plus user themes. https://takeprofit.com/docs/guide/getting-started/Workspaces.md
- **Widget Hub** (13 widgets): Chart, Watchlist, Account, Order Entry, Indie Code Editor, Strategy/Backtesting, Market Depth, Screener, Financials, Feed, Notes, two Lime widgets. Drag by the six-dot handle, resize by borders, **double-click a header for full screen**. https://takeprofit.com/docs/guide/getting-started/Widget-Hub.md
- **Link channels 1 to 4**, each with a colour. A channel can sync: symbol, crosshair, timeframe, date range, indicators, chart type. Same page.
- **Chart**: top bar has timeframes, chart type, `f` indicators, `VS` compare, Object Tree, undo and redo; timeline bar has time zone, ranges from 1 day to full history, go-to-date and scale modes (regular, log, percent, index 100); status line with OHLC on hover; countdown to bar close on the price label; chart templates. https://takeprofit.com/docs/guide/platform/chart-widget/Chart-widget-overview.md , https://takeprofit.com/docs/guide/platform/chart-widget/Chart-features.md , https://takeprofit.com/docs/guide/platform/chart-widget/Chart-settings.md
- Chart settings has six groups: Style (candle body, border, wick, last-price, volume colours, each with a visibility toggle), Canvas (background, grid, crosshair line style, right/top/bottom margins), Security Label, Scales, Alerts, Templates. Same Chart-settings page.
- **Drawing toolbar**: seven flyouts (volume and measurement, lines and channels, patterns and waves, shapes and curves, brush and path, Fibonacci and Gann, text) plus Measure and Search, utility group on the right (magnet, hide, sync, lock, keep drawing, remove all). Last-used tool stays on the group button. https://takeprofit.com/docs/guide/platform/chart-widget/Drawing-tools.md
  - **Search drawings** with Cmd/Ctrl+S, which also hosts the toggles (strong magnet, hide, lock, keep drawing, hotkeys, remove all) and the default sync level for new drawings.
  - **Drawing kit wheel**: Alt/Option + right-click opens a radial menu, favourites in the inner ring, categories outside.
  - **Magnet**: regular snaps to highs and lows, strong (hold Cmd/Ctrl) to every OHLC. https://takeprofit.com/docs/guide/platform/chart-widget/Utility-tools.md
  - **Sync levels**: Local (default), Channel, Workspace, Global. Drawings are anchored to time and price, so they hold across timeframes and across scale modes.
  - Hotkeys are editable; each tool shows its shortcut (e.g. Alt+T trend line, Alt+H horizontal, Alt+V vertical, Alt+F fib retracement, Alt+L long/short). https://takeprofit.com/docs/guide/platform/chart-widget/Line-tools.md and https://takeprofit.com/docs/guide/platform/chart-widget/Fibonacci-tools.md
  - Per-tool settings: Fib levels list with add/remove, per-level line style, background fill and opacity, reverse, show prices and levels, label position, font size, exact coordinates (bar and price per point). Text tool: bold, italic, underline, strike, size, alignment, text and background colour, bullets. Callout pointer position (8 directions). Long-Short tool: multi-level TP and SL with volumes, account-sized risk, fixed or flexible risk-ratio mode, floating P&L. https://takeprofit.com/docs/guide/platform/chart-widget/Measurement-tools.md and https://takeprofit.com/docs/guide/platform/chart-widget/Text-tools.md
  - Tool list by family from the index: lines (standard, arrow, ray, horizontal ray, horizontal, vertical, cross), channels (parallel, pitchfork), patterns (XABCD with Gartley/Butterfly/Crab/Bat, Cypher, head and shoulders, ABCD, triangle, three drive, Elliott impulse and correction), shapes and curves, pen, highlighter, path, polyline, Fibonacci (retracement, extension, arcs, fans, time zones), Gann (box, fan, square), measure (quick, date and price, date only, price only), volume profile, VWAP, TWAP, text, callout, price tag. https://takeprofit.com/docs/llms.txt
- **Object Tree**: groups via folder icon, per-group visibility, lock, z-order, duplicate, sync level; bulk edit; also the pane manager (1.5).
- Order flow: Volume Footprint, TPO, Renko, Liquidity Heatmap, Order Book Profile. These are crypto-microstructure features; out of scope for us.

### 1.9 What to take, mapped to our Python ctx API

Status, checked against the code on 2026-11-23: ✅ Built (works in Studio today) · ◐ Partly built · ⬜ Not built · ⏸ Not planned now. `Easy` / `Med` / `Hard` is the effort.

Our runner today: `ctx.plot(name, value, chart="main"|"own")`, `ctx.mark(symbol, label)`, `ctx.table(name, row)`, `ctx.log(...)`, `ctx.history`, `ctx.indicator`, `ctx.value("formula")`, `ctx.param`, `ctx.market_order`, `ctx.bracket` (`backend/app/services/studio_v3/core/pyrunner.py`, `docs/studio/plan/PYTHON_IDE.md`). Today `plot` takes no style or colour and a named plot must keep one chart.

| TakeProfit feature | Concrete mapping in our API | Cost |
|---|---|---|
| ◐ `Med` `@plot.line/histogram/columns/steps/marker/background/bar_color` | Add optional args: `ctx.plot(name, v, chart="own", style="line", color=None, width=1, pane=None)`. Style is a per-name constant like `chart` is today. `ctx.bgcolor(color)` and `ctx.barcolor(color)` as new per-bar calls. | small |
| ✅ `Easy` `@plot.fill('a','b')` | `ctx.fill("a", "b", color)` declared once, drawn between two named plots | small |
| ✅ `Easy` `@level`, `@band` | `ctx.hline(value, color, style)` recorded once per run | small |
| ◐ `Med` Multi-pane with several plots per pane | Today `chart="own"` gives one pane per name (inferred). Add `pane="RSI"` so named plots share a pane, plus Object Tree pane ops (reorder, resize, minimize, maximize, hide). | medium (UI) |
| ⬜ `Med` `self.chart.draw/erase` (lines, boxes, labels, tables, relative position) | `ctx.draw_line(t1,p1,t2,p2,...)`, `ctx.draw_box`, `ctx.draw_label`, with ids for update and erase; reuse `ctx.table` for screen-anchored stats. Render through our DrawingEngine as non-user layer. Cap counts like the existing 50k plot cap. | medium |
| ✅ `Med` `@param.*` and generated Inputs dialog | Declare `PARAMS = {"length": Int(14, min=1), "src": Source("close")}`; Studio renders the Inputs section and writes values into `ctx.param`. Already half-planned in A12 of PYTHON_IDE.md. | medium · Built: `inputs` on an indicator and strategy `params` show in Build's Inputs. |
| ◐ `Med` Outputs dialog (colour, width, visibility per plot, Reset) | Persist per-plot style overrides in the run state; sent back with the next render only, never to the runner. | small · Built: colour and hide per series on the chart; width and Reset open. |
| ⏸ `Easy` Series model `self.close[0]` | We already have `ctx.history(fields, n)` and `ctx.indicator(...)`. Optionally `ctx.close[0]` sugar. Keep formula strings for speed. Do not copy `MutSeriesF`; plain Python state on `self` does the job. | skip |
| ✅ `Hard` `calc_on` other symbol/timeframe | Needs portfolio-level `on_data` (A1). Defer; note only. | defer · Built: `ctx.timeframe("W"|"M"|"Q"|"Y")` without look-ahead; other symbols through portfolio `on_data`. |
| ⏸ `Med` CSV and live feeds | Skip. | skip |
| ✅ `Easy` `@strategy` params (commission, leverage, intrabar filter, market_order_price) | Map to our backtest config panel; same names. Take the "orders fill one tick later" rule as documented behaviour (we fill at next open already). | small · Built: engine settings set in code win over the card. |
| ◐ `Med` Tester widget stats and tabs | Our Dev views already have stats and tearsheet (`devStats.ts`, `DevTearsheet.tsx`). Gaps to check against the section 1.6 list: VaR 95/99, recovery times, number of drawdowns, commission-to-profit, orders tab with exposure and fee, side-by-side compare. | small each |
| ✅ `Med` Fork any built-in, version history, console, Add to Chart | Template gallery of forkable strategies (PYTHON_IDE.md B10), version list (exists), live "run on save" that redraws the chart. | medium · Built: templates, versions, Console, live preview redraw. |
| ⏸ `Hard` Marketplace, invite-only, payouts | Out of scope for a single-owner research tool. Keep only "library" (private forks). | skip |
| ◐ `Hard` Drawing sync levels, link channels | Local and Global only is enough for one workspace; link channels become "linked charts" for the Studio multi-symbol view. | medium · Built: drawings per strategy and symbol, synced to the server; no link channels. |
| ◐ `Easy` Search drawings, radial wheel, hotkey editor, favourites | All cheap on top of our `DrawingEngine/registry.ts` (`registerTool`, Map by `type`). | small |
| ◐ `Easy` Status line, countdown to close, go-to-date, scale modes, chart templates | Check which exist in `q360_chart_core.tsx`; the Dev tab already has go-to-date (recent commit). | small |
| ⏸ `Med` MCP server that validates scripts | We already have server static checks; expose them as the tool the AI assistant calls. | later |

## 2. Open source options

Verification: licence, stars, push dates and archived flag from `gh api repos/<owner>/<repo>` on 2026-11-20. Feature claims come from the linked READMEs and docs. I did not run any of these.

### 2.1 Charting engines and terminals

| Project | Licence | Stars, activity | What it gives | Gaps for us |
|---|---|---|---|---|
| **LuxAlgo Vela** https://github.com/LuxAlgo/Vela , docs https://docs.luxalgo.com/vela | Apache-2.0 plus NOTICE that requires a visible Vela attribution mark (can be moved, not removed). Pine addon is separately AGPL-3.0. https://github.com/LuxAlgo/Vela/blob/main/README.md | 1,335 stars (API; the README page showed 511, stale cache), created 2026-07-13, pushed 2026-11-19, latest tag v0.10.13, 60 open issues, 11 contributors | WebGL2 renderer with canvas2d fallback; headless core; workspace shell (topbar, status line, bottom bar, object tree, one chart or grid, sync groups, one persisted state doc); about 67 interactive drawing tools with flyouts, magnet off/weak/strong, stay-in-drawing, favourites, quick-settings popup and full settings panel; 70+ native indicators with legend row and settings dialog; panes API (list, move, merge, collapse, maximize, height weights); `ScriptingEngine` port; strategy run exposes `equity` and `trades()`; plugin SDK for chart types and layers; Binance/Coinbase/Hyperliquid providers. https://github.com/LuxAlgo/Vela/blob/main/docs/user/drawing-tools.md , https://github.com/LuxAlgo/Vela/blob/main/docs/user/api-reference.md , https://luxalgo.com/blog/introducing-vela | Pre-1.0 and four months old, so API churn. Vanilla class, not React (needs a thin wrapper). No Python engine; its documented engine is Pine. Footprint, TPO, built-in Pine editor are the paid Vela Pro. Perf on 100k bars is not published in the pages I read (unverified). |
| **KLineChart** https://github.com/klinecharts/KLineChart | Apache-2.0 | 4,319 stars, pushed 2026-11-16, v10.1.1 (2026-11-16) | Canvas, zero dependencies, ~50 KB gzip; about 30 built-in indicators (MA, EMA, BOLL, MACD, KDJ, RSI, ...), `registerIndicator` and `registerOverlay` custom APIs, magnet modes, panes by `paneId`. https://klinecharts.com/en-US/guide/indicator and https://klinecharts.com/en-US/guide/overlay | Only **16 built-in overlay types** (lines, rays, price channel, parallel line, one Fibonacci line, brush, annotation, tag). We already exceed that by a wide margin. No Fib family, pitchforks, patterns, Gann, long/short tools. |
| KLineChart Pro https://github.com/klinecharts/pro | Apache-2.0 | 352 stars, pushed 2026-07-26 | Prebuilt toolbar and period/symbol UI on KLineChart. | Mostly a thin shell; drawing set is KLineChart's. Not ahead of ours. |
| **TradingView Lightweight Charts** https://github.com/tradingview/lightweight-charts | Apache-2.0, NOTICE file asks for TradingView attribution | 17,907 stars, pushed 2026-11-18, v5.3.0 (2026-11-10) | Fast canvas charts; native **panes** (add, move series between panes, resize, remove); series primitives and pane primitives and custom series for drawing tools and overlays. https://tradingview.github.io/lightweight-charts/docs/panes and https://tradingview.github.io/lightweight-charts/docs/plugins/intro . Already in our `package.json` (`^5.1.0`); used only by `MiniChart.tsx`. | Ships no drawing tools and no indicators; you build them (or add plugins below). A report of ~60k candles performing fine is anecdotal. https://github.com/tradingview/lightweight-charts/issues/1808 |
| deepentropy lightweight-charts-drawing https://github.com/deepentropy/lightweight-charts-drawing | MIT | 157 stars, pushed 2026-11-19 | **86 TradingView-style tools** on LWC v5 (lines, channels, pitchforks, Fib, Gann, patterns, Elliott, forecasting, volume profiles, shapes, text) with TradingView factory defaults, hit tests, placement rules, magnet, JSON export and import, multi-select, z-order, per-interval visibility. Host keeps undo, storage, dialogs, toolbar. | Small and young; v0.2 broke the v0.1 API; tool list is at docs/TOOLS.md (not read). Not a drop-in for our drawings. |
| difurious lightweight-charts-line-tools https://github.com/difurious/lightweight-charts-line-tools (main), `-lines`, `-freehand` | main repo Apache-2.0; `-lines` and `-freehand` MPL-2.0 | 139 stars (main), pushed 2025-12-30; sub-packages 0 to 1 star | Interactive line-tool core and standard tool packs for LWC v5. | Low adoption, MPL file-level copyleft on the packs. |
| CandleKit https://github.com/rohanbeingsocial/candlekit-charts | MIT (per author's post; repo not checked with the API) | new; author says built with AI and early-stage https://github.com/tradingview/lightweight-charts/discussions/2091 | Drawing, indicators (SMA, EMA, RSI, MACD, BB, stochastic), replay, ruler, synced panes on LWC, React entry. | Small tool set, early. Replay idea only. |
| opencharts https://github.com/cklawkc/opencharts | MIT | 0 stars, pushed 2026-09-16 | Custom canvas engine, 20+ indicators, Pine transpiler, CCXT/Alpaca. | No traction. |
| react-financial-charts https://github.com/react-financial/react-financial-charts | MIT | 1,426 stars, last push 2024-03-09 | React/SVG financial charts. | Stale, SVG, no drawing suite. Avoid. |
| TradingView Advanced Charts (Charting Library) https://www.tradingview.com/advanced-charts | Proprietary; access by request, free only if TradingView attribution stays visible and the deployment is **public, not private or behind a paywall** https://tradingview.com/charting-library-docs/latest/introduction | n/a | The reference product: 100+ tools, indicators, saved templates, replay. | Private repo behind an access form; our app is a private research tool. Cannot count on it. |
| Apache ECharts https://github.com/apache/echarts | Apache-2.0 | 67,756 stars, pushed 2026-10-13 | General charts including candlestick, WebGL via echarts-gl. | No finance interaction model (drawings, panes of indicators). Fine for tearsheet charts, not the workspace. |
| uPlot https://github.com/leeoniya/uPlot | MIT | 10,661 stars, pushed 2026-11-17 | Very fast time-series canvas plots. | No candles or drawings; useful for equity and drawdown strips only. |
| Perspective https://github.com/perspective-dev/perspective | Apache-2.0 | 11,614 stars, pushed 2026-11-20 | WASM data grid and pivot with charts. | Trade-table and analytics, not price charting. |

### 2.2 Pine and indicator runtimes

| Project | Licence | Notes |
|---|---|---|
| **PineTS** https://github.com/LuxAlgo/PineTS (formerly QuantForgeOrg, same package `pinets`) | **AGPL-3.0, dual with commercial licence** https://github.com/LuxAlgo/PineTS#license | 963 stars, pushed 2026-11-13. Transpiles Pine v5/v6, 60+ TA functions, `request.security`, strategy namespace, streaming, execution limits. Native Pine is flagged experimental by its own README. Copyleft triggers on distribution or network service. Our scripts are Python, so Pine support is optional and should be a separate decision. |
| Vela scripting port https://github.com/LuxAlgo/Vela/blob/main/docs/user/scripting-engines.md | Port is Apache-2.0 | `prepare()` plus `execute()`, about 300-line demo engine; a backend-Python engine could implement it (this is how our `ctx.plot` output could ride Vela if we ever adopt it). |

### 2.3 Backtest and report UIs (for the tester drawer, no charting engine needed)

| Project | Licence | What to borrow |
|---|---|---|
| QuantStats https://github.com/ranaroussi/quantstats | Apache-2.0, 7,896 stars, pushed 2026-11-02 | Tearsheet content list: monthly heatmap, rolling Sharpe, drawdown periods, return distribution. Python, so reuse the formulas server-side. |
| vectorbt https://github.com/polakowo/vectorbt | Apache-2.0 **with Commons Clause** (no selling a product whose value derives from it) https://github.com/polakowo/vectorbt (LICENSE.md) | Plotly-based portfolio plots; borrow metric definitions only. Commons Clause makes it risky to embed. |
| Nautilus Trader https://github.com/nautechsystems/nautilus_trader | LGPL-3.0 | 31,697 stars, pushed 2026-11-20. Engine reference for order lifecycle and event model; no web chart UI to reuse. |
| backtesting.py https://github.com/kernc/backtesting.py | AGPL-3.0 | Bokeh report layout (equity, drawdown, trades on price). AGPL: reference only. |
| Jesse https://github.com/jesse-ai/jesse | MIT | 8,822 stars, pushed 2026-11-17. Python strategy API (`should_long`, `go_long`) and a charts dashboard; reference for strategy tester UX. |
| freqtrade / FreqUI https://github.com/freqtrade/freqtrade | GPL-3.0 | 57,085 stars. Plot configuration by indicator name into main or sub pane is the same idea as our `chart="main"|"own"`. GPL: reference only. |
| OpenBB https://github.com/openbq-org/OpenBB (the old OpenBB-finance URL redirects) | Apache-2.0 per its LICENSE (GitHub's API shows "Other") | 75,587 stars, pushed 2026-11-18. A data platform and workspace; no embeddable chart engine to adopt. Reference for widget-and-link-group UX, same idea as TakeProfit channels. |
| lightweight-charts-python https://github.com/louisnw01/lightweight-charts-python | MIT | 2,172 stars, last push 2024-09-28. Python wrapper with a drawing toolbox; stale, and our UI is React so not useful. |

## 3. Recommendation: keep and extend our engine

### 3.1 What we have (my skim of `frontend/src/components/chart_engine`, 2026-11-20)

- About 25.4k lines of TS/TSX across the engine.
- `DrawingEngine/`: 18 files (line, channel, fib and extended fib, Gann and extended Gann, pitchfork, Elliott, pattern and extended pattern, shapes, brush, measurement, projection, volume, text) feeding a `Map` registry with `registerTool`. A rough count of `type:` entries across those files is 199. That is not a de-duplicated tool count (unverified); even at half it exceeds KLineChart (16 overlays), Vela (~67) and deepentropy (86).
- `IndicatorEngine/registry.ts` (2,765 lines, about 71 `id:` entries, unverified as distinct indicators), `StrategyEngine`, `AlertEngine`, `PatternScanner`, `IndicatorPaneRenderer`, `DataAdapter` (Heikin-Ashi, Renko, range bars), `DrawingToolbar.tsx`, context-based state.
- Renderer: `ChartCanvas/index.tsx` (1,743 lines) draws on a 2D canvas plus a separate crosshair canvas, resized to device pixel ratio. No WebGL and no windowed or decimated drawing that I found in a grep for `downsample|decimat|100k` (loops over `bars.length` exist in the file). **Performance at 100k bars is unmeasured.**
- The Studio Dev chart already runs on Q360ChartCore through an overlay prop (recent commits `f08dfa5`, `9f18f4f`), so the backtest-to-chart contract exists.

### 3.2 Why not replace it

1. Our drawing and indicator coverage already exceeds every OSS candidate. Replacing the engine would mean re-porting drawing tools and state into someone else's model, then re-adding what Vela does not have (Fib family depth, our alert and pattern engines).
2. The remaining gaps are not renderer-bound. The owner's list (dense toolbar, flyouts, per-tool settings, floating toolbar, indicator panes, script dock, tester drawer, animated resizing) is chrome and data contract. Vela's workspace shell would not give us a script dock or tester drawer; we would build those either way and around a foreign shell.
3. Vela is the only candidate that matches the whole brief, but it is four months old and 0.x, adds an attribution requirement, is vanilla JS (wrapper needed), and its script story is Pine (AGPL addon) while ours is Python on the server. Its panes and `ScriptingEngine` port are good ideas to copy, not a reason to migrate.
4. Lightweight Charts plus a drawing plugin is a credible renderer but means writing the indicator pane system, replay, Renko transforms and our alert integration again, for a perf benefit we have not shown we need.

### 3.3 The one gate: a perf spike (about 30 to 60 minutes of Claude time, medium)

Load a synthetic 100k-bar series (and 250k as a stretch) into Q360ChartCore with 3 overlays and 2 indicator panes. Record frame time for pan, wheel zoom and crosshair move in Chrome DevTools; target at least 60 fps for pan and zoom with all drawings visible. Outcomes:
- **Pass**: proceed with the plan below.
- **Fail on bar rendering only**: replace just the bar and line series layer inside `ChartCanvas` with a windowed draw (only visible range, min/max per pixel column when bars are narrower than a pixel). That is a local change.
- **Fail broadly**: adopt Vela as the engine (wrap `new Vela(el, ...)` in a React component, feed it our bars, supply a custom `ScriptingEngine` that returns our `ctx.plot` series, keep our UI chrome). This is the fallback, not the plan.

### 3.4 Migration and build steps (no engine replacement)

Status, checked against the code on 2026-11-23: ✅ Built (works in Studio today) · ◐ Partly built · ⬜ Not built · ⏸ Not planned now. `Easy` / `Med` / `Hard` is the effort.

1. ◐ `Med` **Plot contract (backend, small):** extend `ctx.plot` with `style`, `color`, `width`, `pane`; add `ctx.hline`, `ctx.fill`, `ctx.bgcolor`, `ctx.barcolor`. Return them in the run result next to the existing `plots`.
2. ◐ `Med` **Overlay renderer (frontend, small to medium):** extend the `ChartOverlay` prop so plot styles render through the existing `IndicatorPaneRenderer` and ChartCanvas. Named panes share one pane. Live redraw on save/run in the script dock.
3. ⬜ `Med` **Script drawings (medium):** `ctx.draw_line/box/label` rendered through DrawingEngine as a locked, non-user layer with ids for update and erase.
4. ◐ `Med` **Inputs and Outputs panel (medium):** a declared `PARAMS` schema generates the Inputs tab; a per-plot Outputs tab edits colour, width, visibility; Reset. Reuse for built-in indicators so both share one settings pattern.
5. ◐ `Med` **Pane manager and Object Tree (medium):** reorder, drag-resize with persisted heights, minimize, maximize on double-click, hide, remove; group, lock, hide, z-order for drawings. Animate resizes with a CSS transition on grid track sizes or a spring on the pane height values (avoid layout thrash by animating a CSS variable).
6. ◐ `Easy` **Drawing UX (small each):** Cmd+S search, favourites, Alt+right-click wheel, hotkey editor, keep-drawing, weak/strong magnet, last-used tool on group button, floating toolbar, per-tool settings (Fib levels, text formatting, coordinates tab). Compare against TakeProfit and Vela lists in this doc to find missing tools rather than rebuilding all.
7. ◐ `Med` **Tester drawer (medium):** bottom drawer with Key stats, Equity and drawdown, Performance, Trades analysis (distribution, streaks, time patterns, excursions via MAE/MFE, which the Dev chart already shows), Orders tab. Add the missing metrics from 1.6.
8. ⬜ `Med` **Perf gate (3.3)** before step 2 so a renderer decision does not invalidate earlier work.

### 3.5 What to reuse from ours

All of it: DrawingEngine registry and tools, IndicatorEngine registry, DataAdapter chart types, AlertEngine, PatternScanner, StrategyEngine selectors, the ChartContext state, the Dev overlay prop and trade navigator. What to treat as a reference only: TakeProfit's UX list (1.8), Vela's drawing settings panel and panes API (2.1), deepentropy's TradingView default styles per tool, QuantStats's tearsheet contents.

### 3.6 Risks and unverified items

- Our engine's 100k-bar performance (unmeasured).
- Our drawing and indicator counts are grep counts (199 `type:` entries, 71 `id:` entries), not a verified list.
- Vela's performance claims and its drawing tool count (~67 from its own doc) are not tested; star count differed between API (1,335) and the README page (511).
- TakeProfit built-in indicator count, community page, bots page and AI/MCP pages were read only by title or snippet. The blog at takeprofit.com/@TakeProfit was not read.
- I did not run any third-party code.

---

## Supercharts parity and beyond

Added 2026-11-21. Sources: our code (`frontend/src/components/chart_engine/`, `modules/studio/chart/ChartPage.tsx`, `modules/studio/build/DevChart.tsx`), Vela docs in `node_modules/@luxalgo/vela/docs/user/` (workspace, drawing-tools, renderer-features, scripting-engines), TradingView `/features`, "Getting started with Supercharts", "How to sync the charts of my layout", multi-chart layout and layout guides, TakeProfit Indie docs (What is Indie, Indicator code structure, comparison posts), Pine Script v6 docs. Each row has one Status (legend below) and a note on what Studio has. Priority P1 to P3.

### 1. Inventory of the old `/studio/chart` and `components/chart_engine` (so nothing is lost on delete)

`/studio/chart` is `ChartPage.tsx` (153 lines). It has two parts: a light `StudioChart` view (one symbol from `/bars`, day, week, month timeframes, indicators from `getAllIndicators()`, a backtest's trades, a trade navigator, replay with 1x, 5x, 20x and key `R`) and `FullChart`, which mounts `q360_chart_core` (the same chart `/trade` uses). Counts are from grep and are not de-duplicated (unverified).

| Area | What exists | Where | Carry to Vela / DevChart? |
|---|---|---|---|
| Chart types (16) | candlestick, hollow candle, volume candles, bars, Heikin-Ashi, line, line with markers, step line, area, HLC area, baseline, Renko, Kagi, point and figure, range bars, line break | `types.ts` `ChartType`, `DataAdapter/` | ✅ Ported: Renko, Kagi, P&F, range and line break as pre-transformed bars. ⬜ Volume candles and HLC area still open |
| Scale modes | auto, manual, log, percent | `types.ts` | ✅ Linear, log, percent and indexed in Chart settings |
| Drawing tools | about 99 distinct ids in 18 files: lines, channels, Fib and extended Fib, Gann and extended Gann, pitchforks, Elliott, patterns and extended patterns, shapes, brush, measurement, projection, volume, text | `DrawingEngine/` | Vela ships about 67 tools covering the same families. Drop the old set (HAVE). Check for lost ones: extended Fib and Gann variants, Elliott sub-types |
| Drawing state | tool registry, `drawingsLocked`, drawing toolbar | `DrawingEngine/registry.ts`, `state/ChartState.ts`, `DrawingToolbar.tsx` | ◐ Vela has lock, magnet, keep drawing, eraser, undo; Studio wires favourites, tool defaults and per-strategy, per-symbol drawings synced to the server |
| Indicators (about 69 ids) | SMA, EMA, WMA, HMA, DEMA, TEMA, ZLEMA, KAMA, FRAMA, McGinley, VWMA, RSI, MACD, Stoch, CCI, ROC, MFI, TSI, KST, Coppock, Fisher, TRIX, Ultimate, Aroon, Vortex, ADX, ATR, NATR, Bollinger, Keltner, Donchian, Supertrend, SAR, Ichimoku, VWAP, OBV, CMF, A/D, Force, Pivot, Chop, Ulcer, Mass, hist vol and more | `IndicatorEngine/registry.ts`, `IndicatorMenu.tsx`, `IndicatorPaneRenderer.tsx` | Vela has 70+ native studies with settings dialog and persistence (HAVE). Diff the list once; port any missing as Python indicators (P2) |
| Candle pattern scanner | about 25 candlestick patterns (doji, hammer, shooting star, engulfing and more) with a selector | `PatternScanner/` | OLD. Port as one Python indicator that returns marks (`ctx.mark`) (P2) |
| Strategy engine | about 20 built-in strategies: MA cross, dual MA, RSI, MACD, Bollinger, Stochastic, momentum, consecutive up or down, bar up or down, inside bar, outside bar, greedy, channel breakout, Supertrend and more, with a selector | `StrategyEngine/` | OLD. Superseded by our Python `class Strategy` and starters; port the 20 as starter files so the gallery covers them (P2) |
| Alerts | price cross above or below, enter or exit range, percent change, indicator cross, indicator zone (overbought, oversold, custom), MA crossover, volume spike, candle pattern; browser and sound notification; manager UI | `AlertEngine/` | VELA has alerts and a bell in its workspace. Our condition list is richer. Port conditions as alert definitions on server (P2). Backtest chart does not need alerts; live and paper do |
| Replay | play, pause, speed 1x, 5x, 20x, scrub slider, key R (page); DevChart has its own debugger-bound replay | `ChartPage.tsx`, `DevChart.tsx` | ✅ DevChart replay bound to the debugger |
| Multi-chart | 11 layouts (1, 2H, 2V, 3H, 3V, 3L, 3R, 4, 5, 6, 8), layout menu with icons, symbol search per cell, synced crosshair timestamp | `q360_chart_core.tsx` | ◐ Grid of up to 8 symbols with synced crosshair and time; symbol, timeframe and drawing links not wired |
| Compare | `compareSymbols` overlay on the chart | `q360_chart_core.tsx` | ✅ Compare and spread in Chart settings |
| Right panels | watchlist panel, alerts panel, alpha panel (percent, z-score, ratio vs a reference) | `components/watchlist/` (WatchlistPanel, AlphaPanel, useWatchlist), `AlphaEngine/math.ts` | OLD. Alpha panel is a real quant idea; keep the maths (`AlphaEngine/math.ts`) and rebuild as an indicator or a pane (P2). Watchlist belongs to Universe page |
| Intraday | intraday wrapper and adapter for minute bars | `IntradayChartWrapper.tsx`, `DataAdapter/intraday.ts` | Studio uses daily; keep as reference for later (P3) |
| Misc | mini chart thumbnail, stable container (resize safe), oscillator and volume blocker messages | `MiniChart.tsx`, `StableChartContainer.tsx` | MiniChart: keep for cards (check users before delete). Others obsolete |

**Before deleting:** (1) `rg` for imports of `chart_engine/` from `/trade` and any other page, because `FullChart` says it is the same chart `/trade` uses; do not delete if `/trade` still mounts it. (2) Move `AlphaEngine/math.ts` and the alert condition types somewhere kept. (3) Convert the 20 strategies and the pattern scanner into starter files. (4) Screenshot the old page for reference.

### 2. TradingView Supercharts feature list, with our status

Status, checked against the code on 2026-11-23: ✅ Built (works in Studio today) · ◐ Partly built · ⬜ Not built · ⏸ Not planned now. `Easy` / `Med` / `Hard` is the effort.

Most demanded for a quant who backtests: marked **(M)**. "Studio has" names what works in the Build chart today.

**Charts and layout**

| Status | Feature | Studio has | Pri |
|---|---|---|---|
| ◐ | `Hard` Multi-chart layouts, 1 to 16 charts (M) | Grid of up to 8 symbols (Chart settings › Grid of symbols) | P1 |
| ◐ | `Hard` Sync: symbol, interval, crosshair, time, date range (M) | Grid syncs crosshair and time; no symbol or interval links | P1 |
| ⬜ | `Hard` Sync groups by colour or emoji | | P2 |
| ⬜ | `Med` Sync drawings in layout or globally | Drawings follow the strategy and symbol, not a layout | P2 |
| ◐ | `Med` Saved layouts, rename, copy, share, cloud save | Studio workspace layouts and chart templates save to the server; no chart layout sharing | P2 |
| ✅ | `Easy` Maximise one chart | Maximise and restore (⌘⇧E), pop-out window | P2 |
| ⬜ | `Med` Quick search for any action (M) | Command palette covers code, not chart actions | P2 |
| ⬜ | `Med` Symbol search by typing | Symbol select and watchlist add box | P1 |
| ⬜ | `Easy` Time zone setting, exchange time | | P3 |
| ✅ | `Easy` Range buttons and go to date | 1M, 3M, 6M, 1Y, 5Y, YTD, ALL; go to date. Daily bars, so no 1D or 5D | P1 |
| ⬜ | `Easy` Undo and redo for chart changes | | P2 |
| ◐ | `Easy` Snapshot image, copy link | PNG export; no link | P2 |
| ◐ | `Easy` Fullscreen, theme, mobile layout | Maximise and pop-out; theme follows the app; no mobile layout | P3 |

**Chart types**

| Status | Feature | Studio has | Pri |
|---|---|---|---|
| ✅ | `Easy` Candles, bars, line, area, baseline, step line, line with markers, columns, Heikin-Ashi, hollow candles | All ten in Chart settings | P1 |
| ⬜ | `Med` HLC area, high-low, volume candles | | P3 |
| ✅ | `Med` Renko, Kagi, line break, point and figure, range bars | All five, with causal ATR-14 box sizes | P2 |
| ⏸ | `Hard` Volume footprint, TPO, session volume profile | Needs intraday data | P3 |
| ⏸ | `Hard` Custom intervals incl. seconds | Data is daily only | P3 |
| ✅ | `Med` Spreads and formula symbols (A/B, A−B) | Ratio or difference against one symbol, with 60-day correlation | P2 |
| ✅ | `Med` Compare and overlay symbols | Chart settings › Compare | P1 |
| ✅ | `Easy` Log and percent scale | Linear, Log, Percent, Indexed to 100 | P1 |
| ⏸ | `Med` Extended hours and sessions | Data is daily only | P3 |

**Drawing tools**

| Status | Family | Studio has | Pri |
|---|---|---|---|
| ◐ | `Easy` Cursors, eraser, measure, zoom | Measure (date and price range); no eraser or zoom tool in the toolbar | P1 |
| ✅ | `Easy` Trend lines, rays, extended, horizontal, vertical, cross line | Lines flyout | P1 |
| ✅ | `Easy` Channels, pitchforks | Parallel and regression channels, pitchfork | P2 |
| ◐ | `Easy` Gann and Fibonacci | Fib retracement, extension, fan, time zones; Gann fan and box. No arcs, spiral or Fib channel | P2 |
| ⬜ | `Easy` Patterns: Elliott, harmonic, head and shoulders | Vela has them; not in our toolbar | P3 |
| ◐ | `Easy` Forecasting and measurement | Long/short position, date and price range, anchored VWAP, fixed-range volume profile | P2 |
| ✅ | `Easy` Shapes: rectangle, ellipse, triangle, polyline, arrow, brush, highlighter | Shapes flyout | P2 |
| ✅ | `Easy` Annotations: text, note, callout, price label, flag, arrows | Text and marks flyout | P2 |
| ⬜ | `Easy` Icons, emojis, stickers | Not in our toolbar | P3 |
| ◐ | `Easy` Magnet, keep drawing, lock all, hide all, favourites | Tool favourites and defaults saved to the server; magnet, lock and hide not in the toolbar | P1 |
| ◐ | `Med` Drawing templates (style presets per tool) | Per-tool defaults saved; no named presets | P3 |
| ⬜ | `Hard` Alerts on drawings | | P3 |
| ⬜ | `Med` Object tree: hide, lock, group, z-order, rename (M) | | P1 |
| ✅ | `Med` Data window under the crosshair (M) | Chart settings › Data window | P1 |

**Indicators and scripting**

| Status | Feature | Studio has | Pri |
|---|---|---|---|
| ✅ | `Easy` Built-in indicator library | About 70 `ta` indicators in the Indicators picker | P1 |
| ◐ | `Med` Indicator settings: inputs, style, visibility | Inputs in code and Build's Inputs; colour and hide per series | P1 |
| ◐ | `Easy` Multi-pane indicators, pane resize, move to pane | Own pane or price per plot; no move or resize controls of ours | P1 |
| ⬜ | `Med` Indicator templates (saved sets) | Chart templates save view and compare only | P2 |
| ⏸ | `Hard` Public library of community scripts | | P3 |
| ✅ | `Med` Script editor with autocomplete, versions, profiler, logs (M) | The Build IDE for Python | P1 |
| ✅ | `Hard` Custom indicators in the chart from code (M) | `class Indicator` and `self.use(...)` (section 3) | P1 |
| ✅ | `Med` Multi-timeframe data in scripts (M) | `ctx.timeframe("W"/"M"/"Q"/"Y")`, completed bars only | P1 |
| ⬜ | `Med` Candlestick pattern recognition | Old engine only | P2 |
| ⬜ | `Hard` Auto chart patterns | | P3 |
| ◐ | `Med` Seasonals | Seasonality view in Results; no chart overlay | P3 |
| ⬜ | `Med` Technical rating gauge | | P3 |

**Strategy, replay, alerts, tools**

| Status | Feature | Studio has | Pri |
|---|---|---|---|
| ✅ | `Med` Strategy Tester: overview, summary, trades, properties (M) | Results tabs, Tearsheet, Run settings | P1 |
| ◐ | `Med` Trades and orders on the chart, drag orders | Trades, stop and target lines on the chart; orders in Results › Trades › Orders; no dragging | P1 |
| ⏸ | `Hard` Deep backtesting on intraday data | Left out by the owner for now | P3 |
| ◐ | `Med` Bar replay, speeds, step, autoplay, replay trading (M) | Replay bound to the debugger, 1× to 50×, step, autoplay, blind replay; no replay trading | P1 |
| ⬜ | `Med` Alerts on conditions, drawings, scripts | | P2 |
| ◐ | `Med` Watchlists, flagged symbols, news, calendars | Watchlist in the symbols drawer | P2 |
| ⬜ | `Med` Screeners in the chart | Screener lives on its own page | P2 |
| ⬜ | `Med` Sector heatmaps | | P3 |
| ⬜ | `Hard` Paper and broker trading from the chart | | P3 |
| ✅ | `Easy` Export chart data CSV | Bars, plots and trades | P1 |
| ⏸ | `Hard` Publish ideas, social | | P3 |
| ⬜ | `Med` Fundamentals, earnings and dividend markers | No event data on the chart | P2 |
| ⏸ | `Hard` Options chain, yield curves, macro maps | | P3 |

**Open P1 items:** symbol search by typing, object tree, quick action search on the chart; partly built: multi-chart layouts and sync, drawing toolbar toggles, indicator settings, orders on the chart, replay trading.

### 3. Custom indicator language: Pine, Indie, or native Python

Status, checked against the code on 2026-11-23: ✅ Built (works in Studio today) · ◐ Partly built · ⬜ Not built · ⏸ Not planned now. `Easy` / `Med` / `Hard` is the effort.

**Facts collected**

| | Pine Script v6 | Indie (TakeProfit) | Our Python today |
|---|---|---|---|
| Syntax | Own language, indentation based, `:=` reassign | A dialect and subset of Python with decorators `@indicator`, `@algorithm`, `@sec_context`, `@param.*`, `@plot.line`, `@plot.fill`; type hints required on helper functions; entry is `Main` function or class with `calc` | Full Python 3.12 |
| Execution model | Runs bar by bar on TradingView servers; series are implicit (`close[1]`) | Server-side bar by bar; series indexed `self.close[0]`, `[1]` (note: `[0]` is current) | Strategy `on_bar` per bar and vectorised pandas |
| Strategies | `strategy()` with `strategy.entry` and order simulation | `@algorithm`-style strategies with exchange emulator, live trading | `class Strategy` with `ctx` |
| Multi-symbol and timeframe | `request.security`, dynamic requests in v6 | `Context.calc_on` with secondary contexts | `ctx` on universes (up to ~4,000) |
| Tooling | Cloud editor, profiler, logs | IDE widget, MCP server so an LLM compiles and validates code | Monaco with debugger, profiler, Output |
| Licence and portability | Closed; PineTS runtime is AGPL | Closed platform language; no Pine importer, MCP converts | Ours |
| Limits | Compute and request caps, no files, no network | Subset of Python (no arbitrary libs) | Sandboxed |

**What Indie gets right.** One decorated entry point, declarative `@param` inputs that auto-build the settings form, `@plot.*` decorators that declare how outputs look, secondary contexts for other symbols, and an MCP server so an LLM can compile-check its own code. It is Python-shaped so a Python user is at home, but it is a restricted dialect, so you cannot use pandas or numpy.

**Recommendation: native Python, one unification.** Do not adopt Pine (separate language, AGPL runtime, no gain for Python users) and do not copy Indie's restricted dialect. Keep full Python on the backend, as already decided. Add one small base class so the same file drives chart plots and backtests:

- ✅ `Hard` `class Indicator`: computes named series from bars, declares inputs and plots, runs bar by bar or vectorised (`compute`). Built: a standalone `class Indicator` only plots and is refused orders; an indicator used by a strategy declares `inputs`, `plots`, `fills`, `levels`.
- ✅ `Hard` `class Strategy` can `use` an indicator: `self.ema = self.use(ta.EMA, n=20)` gives the same numbers on the chart and in the backtest. Built (`UsedIndicator`; the Indicators picker inserts the line).
- ✅ `Med` The chart draws indicator outputs from the same pyrunner run, and the backtest reads the same values. Built.

```python
# indicators.py
from atlas import Indicator, Input, Plot, Fill

class KeltnerSqueeze(Indicator):
    overlay = False                        # own pane (True = on price)
    length  = Input.int(20, min=2, max=200, title="Length")
    mult    = Input.float(1.5, step=0.1, title="ATR mult")
    ma      = Plot.line("Basis", color="#4f8cff")
    upper   = Plot.line("Upper", color="#888", style="dashed")
    lower   = Plot.line("Lower", color="#888", style="dashed")
    squeeze = Plot.histogram("Squeeze", color=lambda v: "#e5484d" if v else "#30a46c")
    band    = Fill(upper, lower, color="#4f8cff22")

    def calc(self, bars):                  # bars: pandas DataFrame, full history, no look-ahead by contract
        basis = bars.close.ewm(span=self.length).mean()
        atr   = self.atr(bars, self.length)
        self.ma[:]      = basis
        self.upper[:]   = basis + self.mult * atr
        self.lower[:]   = basis - self.mult * atr
        bb_width        = bars.close.rolling(self.length).std() * 2
        self.squeeze[:] = (bb_width < (self.upper - self.lower) / 2).astype(float)
```

```python
# main.py
from atlas import Strategy
from indicators import KeltnerSqueeze

class Strategy(Strategy):
    def init(self):
        self.k = self.use(KeltnerSqueeze, length=20, mult=1.5)   # same code as on the chart
        self.universe("sp500")

    def on_bar(self, ctx):
        k = self.k[ctx.symbol]              # values up to ctx.date only
        if k.squeeze[-2] and not k.squeeze[-1] and ctx.close > k.ma[-1]:
            ctx.buy(size=0.02)              # 2% of equity
```

How it works: the platform runs `calc` over bars once, caches by (class source hash, inputs, symbol), and serves the numbers to both places. A look-ahead guard runs `calc` on a truncated history and compares the last values to the full-history run, and reports a Problem if they differ. Inputs become the settings form on the chart and the Inputs panel in the IDE with no extra code. Marketplace and sharing come later as importing a file.

**Optional Pine import.** Keep PineTS (AGPL) out of the product. If users ask, offer a Pine to Python converter as an AI action (like TakeProfit's MCP converter), which outputs a normal `Indicator` file the user owns.

### 4. Beyond TradingView for a quant platform

Status, checked against the code on 2026-11-23: ✅ Built (works in Studio today) · ◐ Partly built · ⬜ Not built · ⏸ Not planned now. `Easy` / `Med` / `Hard` is the effort.

| Status | Idea | Studio has | Pri |
|---|---|---|---|
| ✅ | `Med` Universe-aware chart: symbol list with per-symbol P&L, heatmap, linked chart | Symbols drawer with P&L per symbol, symbol × month heatmap, `,` and `.` to step | P1 |
| ⬜ | `Med` Chart a signal: score, rank and percentile as a pane, with the breakpoint line | | P1 |
| ✅ | `Hard` Debugger-bound replay that stops on order, fill or a 5% loss day, with locals | Built | P1 |
| ◐ | `Med` Bar-level "why": click a bar to see the decision log and which rule fired | Replay to a bar shows locals, pending orders and watches; no rule-fired log | P1 |
| ✅ | `Med` Trade ribbons with MAE, MFE and exit reason | Hovered trade draws entry, exit, MAE, MFE, stop and target | P1 |
| ⬜ | `Hard` Cross-sectional pane: the signal across the universe on one date | | P2 |
| ⬜ | `Hard` Point-in-time fundamentals and membership per bar | | P2 |
| ✅ | `Med` Regime ribbon behind price with P&L per regime | Chart settings › Regime ribbon; P&L per regime in Results | P2 |
| ✅ | `Med` Equity, drawdown and exposure panes on the price time axis | Chart settings › Equity, drawdown and exposure | P1 |
| ⬜ | `Med` Corporate actions and earnings markers | No event data | P2 |
| ◐ | `Med` Compare two runs on the chart | Baseline run entries as a marker layer; no diff list | P2 |
| ⬜ | `Med` Parameter scrubber: drag an input, the chart redraws live | | P1 |
| ✅ | `Med` Stop, target and trailing-stop lines per trade | Drawn for the hovered trade | P2 |
| ◐ | `Med` Notes stored with the run, shown on replay | Bar comments by symbol and date, stored with the strategy | P3 |
| ◐ | `Med` Shareable chart link with run, symbol, range and drawings | Read-only share link of the strategy and its run; no chart state | P3 |
| ⏸ | `Hard` AI "explain this bar" | AI is an owner decision | P3 |
| ⬜ | `Med` Screenshot to report | PNG export only | P2 |

### Top recommendations (short list)

Status, checked against the code on 2026-11-23: ✅ Built (works in Studio today) · ◐ Partly built · ⬜ Not built · ⏸ Not planned now. `Easy` / `Med` / `Hard` is the effort.

1. ◐ `Hard` Wire Vela's workspace into the chart. Built: grid with synced crosshair and time, data window, ranges, replay. Open: object tree, symbol and interval links.
2. ✅ `Med` Symbol picker and universe list linked to the chart. Built.
3. ✅ `Hard` `class Indicator` plus `self.use(...)`: one code, two outputs. Built.
4. ✅ `Med` Inputs and plots declared in Python so settings and styles are generated. Built: `inputs`, `plots`, `fills`, `levels`.
5. ✅ `Med` Multi-timeframe access in `ctx`. Built: `ctx.timeframe`.
6. ◐ `Med` Orders, stops and targets on the chart; chart CSV. Built: stops, targets, CSV. Open: orders on the chart.
7. ◐ `Med` Port the old engine's pieces before delete. Built: Renko, Kagi, P&F, range, line break. Open: volume candles, pattern scanner, alpha maths as indicators.
8. ✅ `Med` Look-ahead guard on truncated history, reported in Problems. Built.
9. ◐ `Med` Compare two runs on one chart. Built: baseline entries. Open: entry diff.
10. ⬜ `Med` Perf spike on Vela with 100k bars before dropping the old engine.
