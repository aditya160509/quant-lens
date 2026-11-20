# Studio v3 Chart workspace: research and engine decision

Research date 2026-11-20. Every claim carries a URL. "(unverified)" means I did not confirm it from a primary source or by running code. Repo facts (licence, stars, push date) come from the GitHub API on 2026-11-20.

## 0. Summary

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

Our runner today: `ctx.plot(name, value, chart="main"|"own")`, `ctx.mark(symbol, label)`, `ctx.table(name, row)`, `ctx.log(...)`, `ctx.history`, `ctx.indicator`, `ctx.value("formula")`, `ctx.param`, `ctx.market_order`, `ctx.bracket` (`backend/app/services/studio_v3/core/pyrunner.py`, `docs/studio/plan/PYTHON_IDE.md`). Today `plot` takes no style or colour and a named plot must keep one chart.

| TakeProfit feature | Concrete mapping in our API | Cost |
|---|---|---|
| `@plot.line/histogram/columns/steps/marker/background/bar_color` | Add optional args: `ctx.plot(name, v, chart="own", style="line", color=None, width=1, pane=None)`. Style is a per-name constant like `chart` is today. `ctx.bgcolor(color)` and `ctx.barcolor(color)` as new per-bar calls. | small |
| `@plot.fill('a','b')` | `ctx.fill("a", "b", color)` declared once, drawn between two named plots | small |
| `@level`, `@band` | `ctx.hline(value, color, style)` recorded once per run | small |
| Multi-pane with several plots per pane | Today `chart="own"` gives one pane per name (inferred). Add `pane="RSI"` so named plots share a pane, plus Object Tree pane ops (reorder, resize, minimize, maximize, hide). | medium (UI) |
| `self.chart.draw/erase` (lines, boxes, labels, tables, relative position) | `ctx.draw_line(t1,p1,t2,p2,...)`, `ctx.draw_box`, `ctx.draw_label`, with ids for update and erase; reuse `ctx.table` for screen-anchored stats. Render through our DrawingEngine as non-user layer. Cap counts like the existing 50k plot cap. | medium |
| `@param.*` and generated Inputs dialog | Declare `PARAMS = {"length": Int(14, min=1), "src": Source("close")}`; Studio renders the Inputs section and writes values into `ctx.param`. Already half-planned in A12 of PYTHON_IDE.md. | medium |
| Outputs dialog (colour, width, visibility per plot, Reset) | Persist per-plot style overrides in the run state; sent back with the next render only, never to the runner. | small |
| Series model `self.close[0]` | We already have `ctx.history(fields, n)` and `ctx.indicator(...)`. Optionally `ctx.close[0]` sugar. Keep formula strings for speed. Do not copy `MutSeriesF`; plain Python state on `self` does the job. | skip |
| `calc_on` other symbol/timeframe | Needs portfolio-level `on_data` (A1). Defer; note only. | defer |
| CSV and live feeds | Skip. | skip |
| `@strategy` params (commission, leverage, intrabar filter, market_order_price) | Map to our backtest config panel; same names. Take the "orders fill one tick later" rule as documented behaviour (we fill at next open already). | small |
| Tester widget stats and tabs | Our Dev views already have stats and tearsheet (`devStats.ts`, `DevTearsheet.tsx`). Gaps to check against the section 1.6 list: VaR 95/99, recovery times, number of drawdowns, commission-to-profit, orders tab with exposure and fee, side-by-side compare. | small each |
| Fork any built-in, version history, console, Add to Chart | Template gallery of forkable strategies (PYTHON_IDE.md B10), version list (exists), live "run on save" that redraws the chart. | medium |
| Marketplace, invite-only, payouts | Out of scope for a single-owner research tool. Keep only "library" (private forks). | skip |
| Drawing sync levels, link channels | Local and Global only is enough for one workspace; link channels become "linked charts" for the Studio multi-symbol view. | medium |
| Search drawings, radial wheel, hotkey editor, favourites | All cheap on top of our `DrawingEngine/registry.ts` (`registerTool`, Map by `type`). | small |
| Status line, countdown to close, go-to-date, scale modes, chart templates | Check which exist in `q360_chart_core.tsx`; the Dev tab already has go-to-date (recent commit). | small |
| MCP server that validates scripts | We already have server static checks; expose them as the tool the AI assistant calls. | later |

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

1. **Plot contract (backend, small):** extend `ctx.plot` with `style`, `color`, `width`, `pane`; add `ctx.hline`, `ctx.fill`, `ctx.bgcolor`, `ctx.barcolor`. Return them in the run result next to the existing `plots`.
2. **Overlay renderer (frontend, small to medium):** extend the `ChartOverlay` prop so plot styles render through the existing `IndicatorPaneRenderer` and ChartCanvas. Named panes share one pane. Live redraw on save/run in the script dock.
3. **Script drawings (medium):** `ctx.draw_line/box/label` rendered through DrawingEngine as a locked, non-user layer with ids for update and erase.
4. **Inputs and Outputs panel (medium):** a declared `PARAMS` schema generates the Inputs tab; a per-plot Outputs tab edits colour, width, visibility; Reset. Reuse for built-in indicators so both share one settings pattern.
5. **Pane manager and Object Tree (medium):** reorder, drag-resize with persisted heights, minimize, maximize on double-click, hide, remove; group, lock, hide, z-order for drawings. Animate resizes with a CSS transition on grid track sizes or a spring on the pane height values (avoid layout thrash by animating a CSS variable).
6. **Drawing UX (small each):** Cmd+S search, favourites, Alt+right-click wheel, hotkey editor, keep-drawing, weak/strong magnet, last-used tool on group button, floating toolbar, per-tool settings (Fib levels, text formatting, coordinates tab). Compare against TakeProfit and Vela lists in this doc to find missing tools rather than rebuilding all.
7. **Tester drawer (medium):** bottom drawer with Key stats, Equity and drawdown, Performance, Trades analysis (distribution, streaks, time patterns, excursions via MAE/MFE, which the Dev chart already shows), Orders tab. Add the missing metrics from 1.6.
8. **Perf gate (3.3)** before step 2 so a renderer decision does not invalidate earlier work.

### 3.5 What to reuse from ours

All of it: DrawingEngine registry and tools, IndicatorEngine registry, DataAdapter chart types, AlertEngine, PatternScanner, StrategyEngine selectors, the ChartContext state, the Dev overlay prop and trade navigator. What to treat as a reference only: TakeProfit's UX list (1.8), Vela's drawing settings panel and panes API (2.1), deepentropy's TradingView default styles per tool, QuantStats's tearsheet contents.

### 3.6 Risks and unverified items

- Our engine's 100k-bar performance (unmeasured).
- Our drawing and indicator counts are grep counts (199 `type:` entries, 71 `id:` entries), not a verified list.
- Vela's performance claims and its drawing tool count (~67 from its own doc) are not tested; star count differed between API (1,335) and the README page (511).
- TakeProfit built-in indicator count, community page, bots page and AI/MCP pages were read only by title or snippet. The blog at takeprofit.com/@TakeProfit was not read.
- I did not run any third-party code.
