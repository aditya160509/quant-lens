# Studio IDE feature research (A)

Goal: for each IDE feature area, record what the best products do, then spec the strongest, most customisable form for Studio (Monaco, web app, blocks/formula/Python, backtest, optimise, validate, paper/live).

## Sourcing note

Pages actually fetched and read for this file (marked [R]):

- [R] QuantConnect Debugging: https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/debugging
- [R] QuantConnect Backtest Results: https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results
- [R] QuantConnect Optimization Getting Started: https://www.quantconnect.com/docs/v2/cloud-platform/optimization/getting-started
- [R] QuantConnect Projects: https://www.quantconnect.com/docs/v2/cloud-platform/projects
- [R] QuantConnect Research Environment: https://www.quantconnect.com/docs/v2/research-environment/key-concepts/getting-started
- [R] QuantConnect Scheduled Events: https://www.quantconnect.com/docs/v2/writing-algorithms/scheduled-events
- [R] QuantConnect Reality Modeling: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts
- [R] Pine Strategies: https://www.tradingview.com/pine-script-docs/concepts/strategies/
- [R] Pine Debugging: https://www.tradingview.com/pine-script-docs/writing/debugging/
- [R] Pine Alerts: https://www.tradingview.com/pine-script-docs/concepts/alerts/
- [R] Pine Inputs: https://www.tradingview.com/pine-script-docs/concepts/inputs/
- [R] Pine Libraries: https://www.tradingview.com/pine-script-docs/concepts/libraries/
- [R] VS Code IntelliSense: https://code.visualstudio.com/docs/editing/intellisense
- [R] MQL5 Strategy Tester: https://www.mql5.com/en/docs/runtime/testing
- [R] NinjaTrader 8 NinjaScript Editor: https://ninjatrader.com/support/helpGuides/nt8/NT%20HelpGuide%20English.html?ninjascript_editor.htm (fetched; only page title and size confirmed, claims below about it are from product knowledge)

Several guessed URLs returned 404 (QC optimization overview, universes overview, object-store, parameters, historical-data overview, code-editor; Pine language/strategies and writing/libraries; Monaco typedoc; mql5 article 1587). Claims for those topics, and for Composer, StrategyQuant X, Build Alpha, AmiBroker, WealthLab, Cursor, Jupyter/Colab, and Monaco options, come from product knowledge and are marked [K] (not re-verified this session). Treat [K] as "likely true, verify before copying a spec".

Facts confirmed from pages read:

- QC debugger: breakpoints by gutter click; conditions are Expression or Hit Count; Variables panel with Set Value; Watch expressions; Step Over Alt+F10, Step Into Alt+F11, Restart Shift+F11, Disconnect Shift+F5; needs at least one breakpoint to start.
- QC chart quotas: Free 10 series x 4,000 points, Researcher 10 x 8,000, Team 25 x 16,000, Trading Firm 25 x 32,000, Institution 100 x 96,000. Exceeding the series quota stops the algorithm.
- QC results tabs: runtime statistics, built-in charts (performance, asset plots, order fill prices), custom charts, key statistics, reports, orders, trades, insights, logs, project files, share, download, clone, rename, delete. Org managers can enforce an out-of-sample period (backtests must end N months before today).
- QC optimization: needs a parameter via GetParameter/Parameter attribute, a prior successful backtest, and credits. Max 3 parameters in cloud (more via local CLI). Min, max, step per parameter. Constraints (target, operator, value). Node count and cost estimate shown before launch. Strategy and target selectable. Table can be downloaded, filtered, column-toggled, sorted. Warns about overfitting.
- QC scheduled events: DateRules (on, every_day, every(days), month/week/quarter/year start/end with offsets and per-symbol trading-day awareness, today, tomorrow, custom FuncDateRule), TimeRules (before/after_market_open/close, every(timedelta), at(h,m,s,tz), noon, midnight, now, custom FuncTimeRule). Execution order: scheduled events, then consolidators, then on_data. Backtest vs live timing differences are documented. Event handler timeout is 10 minutes.
- QC reality models: security-level (fee, fill, slippage, buying power, etc.) set via `security.set_*_model` or a security initializer; portfolio-level (margin call model, risk-free rate model).
- Pine strategy report tabs: Metrics (key stats, return details, trades analysis, run-ups/drawdowns, capital efficiency), Trades, Properties. Broker emulator; "bar magnifier" (`use_bar_magnifier=true`, "High" bar detalization, Premium and above) for intrabar fills; order types market/limit/stop/stop-limit; OCA groups; `strategy.risk.*` commands; `calc_on_every_tick`, `calc_on_order_fills`, `process_orders_on_close`; commission and slippage; margin and leverage; 9,000-trade retention cap; docs warn about lookahead, selection bias, overfitting.
- Pine debugging: `log.*()` into a Pine Logs pane from any scope, labels with tooltips, `plot()` into up to four places (chart, status line, price scale, Data Window), bgcolor/barcolor.
- Pine alerts: run 24x7 on servers; `alert()`, `alertcondition()`, order-fill alert messages in strategies, script alerts.
- Pine libraries: exported functions, methods, UDTs, enums, constants; documented with annotations; publishable; imported via `import user/lib/version`.
- Pine inputs: Settings > Inputs tab, `input.*()` types, inline grouping, tooltips.
- MQL5 tester: Print/Comment/Alert are disabled during optimisation (except OnInit); three tick modes (every tick, 1-minute OHLC, open prices only); cloud network agents limited to 4GB disk/RAM; "frames" send per-pass data back without disk writes.
- Jupyter in QC: QuantBook, notebooks per project, run cells, stop nodes.

---

## 1. Editor core

Competitors:

- QuantConnect: Monaco-style web IDE with project file tree, multiple files, debugger gutter, Run and Debug panel. [R projects, debugging]
- TradingView Pine Editor: single-script editor docked under the chart; syntax highlighting, quick "Add to chart", save, version history. [K]
- VS Code: gold standard; multi-cursor, column select, folding, minimap, sticky scroll, bracket pair colourisation, breadcrumbs, split editors, zen mode. [R IntelliSense page; rest K]
- MetaEditor (MT5): MQL5 editor with compile (F7), error list, navigator, code styler. [K]
- NinjaScript Editor: C# editor, F5 compile, errors list, built-in wizard that builds code from a UI. [K]
- AmiBroker AFL editor: syntax colouring, parameter window, "Verify syntax", formula tree. [K]
- WealthLab: C# editor, strategy wizard, block-style "Strategy Builder". [K]
- Cursor: VS Code fork with inline AI edit and chat. [K]

Peak version for Studio:

- Monaco with full VS Code feel: multi-cursor (Alt+click, Ctrl+Alt+Up/Down), column select, bracket pair colours, indent guides, sticky scroll, breadcrumbs, minimap (on by default, toggle), code folding with fold-by-level (Ctrl+K Ctrl+1..7), word wrap toggle (Alt+Z), smooth scrolling, rulers at 88 and 100 columns.
- Tabs with preview tabs, pinned tabs, split view (horizontal/vertical, up to 4 groups), drag to reorder, dirty dot, close-others, reopen-closed (Ctrl+Shift+T).
- Project file tree: strategy.py, indicators/, utils/, params.json, notebooks/, tests/, README. Create/rename/move/delete, drag and drop, file icons, search-in-tree filter. Limit: 200 files per project, 1 MB per file (soft warning at 500 KB).
- Three authoring modes on one strategy, one source of truth: Blocks, Formula, Python. A mode switch shows a live "generated Python" side-by-side (read-only from blocks, editable after "eject"). Eject is one-way and warns.
- Auto-save every 1 s after idle, with an explicit "Saved / Saving / Conflict" indicator. Never lose text on a refresh (local draft recovery from IndexedDB).
- Formatting on save with ruff format (default on), organise imports on save (default on), both toggleable per project. Trim trailing whitespace, final newline.
- Diff editor for any two versions, any two files, or file vs last backtest snapshot.
- Read-only banner when the code differs from the code that produced the visible backtest ("Results are from version 14, editor is at 17").

## 2. Language and API

Competitors:

- QuantConnect LEAN QCAlgorithm: Python/C#, `initialize`, `on_data`, `on_order_event`, `on_securities_changed`, `on_end_of_day`, `on_warmup_finished`, `on_margin_call_warning`. Framework mode splits into Alpha, Portfolio Construction, Risk, Execution, Universe selection modules. [R scheduled/reality pages; framework K]
- TradingView Pine v6: series-based language, no loops over bars needed, `strategy()` declaration with many properties, user-defined types, methods, enums, maps, `request.*`, libraries. [R strategies, libraries]
- NinjaScript (C#): `OnStateChange`, `OnBarUpdate`, `OnOrderUpdate`, `OnExecutionUpdate`. [K]
- MQL5: `OnInit`, `OnTick`, `OnTester`, `OnTesterPass`, `OnTradeTransaction`. [R tester page]
- AmiBroker AFL: array-based vector formulas, `Buy/Sell/Short/Cover` arrays, `ApplyStop`. [K]
- Composer: symphonies as a tree of blocks (weight, if, filter, asset). [K]
- StrategyQuant X / Build Alpha: no code needed; generates code in MQL/EasyLanguage/Python from building blocks. [K]

Peak version for Studio:

- One small, typed Python API: `class Strategy` with `init(ctx)`, `on_bar(ctx, bar)`, `on_fill(ctx, fill)`, `on_universe(ctx, added, removed)`, `on_end_of_day(ctx)`, `on_warmup_done(ctx)`, `on_risk_event(ctx, event)`, `on_stop(ctx)`. Plus a vector API: `def signals(df) -> DataFrame` for vectorised research.
- Same code runs in backtest, paper and live. A lint rule flags anything that differs between modes (wall-clock `datetime.now()`, network calls, `random` without seed).
- Typed everything: dataclasses for `Bar`, `Fill`, `Order`, `Position`; `py.typed` stubs shipped so Monaco shows real types.
- Look-ahead guard: indexing `bars[+1]` or using `shift(-n)` raises in backtest and is a lint warning in the editor.
- Formula mode: Excel-like and Pine-like expressions (`sma(close, 20) > sma(close, 50) and rsi(14) < 30`), compiled to the same Python. Show compiled Python on hover.
- Block mode: every block has a "View as code" action; every code snippet in a block has typed inputs.
- Framework mode optional (separate files for universe, alpha, sizing, risk, execution) with a "Combine" view; templates for each.
- Version the API: `# studio-api: 1` header, with an automatic migrator when the API changes.
- Sandboxed Python: allowlist of imports (numpy, pandas, scipy, sklearn, statsmodels, numba, ta libs); blocked: os, subprocess, sockets. Show a clear message and a "request import" link rather than a stack trace.

## 3. Data access

Competitors:

- QuantConnect: `history()` returning pandas, `add_equity/forex/crypto/future/option`, custom data classes, `Object Store`, `request history with flatten`, fundamentals via universes, Alternative datasets marketplace. [R reality/schedule; rest K; QC history page 404]
- TradingView: `request.security()`, `request.security_lower_tf()`, `request.financial()`, `request.economic()`, `request.dividends/earnings/splits`, `request.seed()` for GitHub-hosted data. [K]
- NinjaTrader: `AddDataSeries`, multi-series via `BarsInProgress`. [K]
- MT5: `CopyRates`, `CopyTicks`, `iMA` handles. [K]
- Composer: curated ETF/stock data only. [K]
- StrategyQuant: custom data import wizard (CSV), data cleaning, symbol manager. [K]
- Jupyter/Colab: any Python data library. [K]

Peak version for Studio:

- A data panel ("Data" tab) listing every dataset available: symbol, asset class, bar sizes, first/last timestamp, gaps, adjusted/unadjusted, source, last update. Click to preview in a grid and a chart.
- `ctx.history(symbols, n, "1d"|"1h"|"5m"|..., fields=[...], adjusted=True)` returns a typed DataFrame. Hard rule: only data available at that bar close. Cached.
- Multi-timeframe in one line: `ctx.bars("SPY", "1d")` inside an intraday strategy, with correct "last completed bar" semantics (the thing Pine `request.security` gets wrong without `lookahead_off`). Studio never allows the lookahead variant.
- Custom data: upload CSV/Parquet, map columns in a wizard, name it, get autocompletion `ctx.data("my_series")`. Up to 500 MB per dataset, versioned.
- Corporate actions switch (split/dividend adjusted, raw, total return) with a visible badge on each result.
- Data quality report per run: missing bars, stale prices, zero-volume bars, outliers, survivorship note. Failing quality is a warning on the result page, not a hidden detail.
- Cross-asset and fundamentals fields available via a single `ctx.field("AAPL", "pe_ratio")` with point-in-time dates.
- Object store: key-value + file store per project (`ctx.store.put/get`), size shown in UI, 100 MB per project default.

## 4. Indicators

Competitors:

- QuantConnect: 100+ built-in indicators registered with `self.sma(symbol, 20)`, auto-updating with data, `WarmUpPeriod`, `IndicatorBase` for custom, automatic indicator on consolidators, `plot indicator`. [K]
- Pine: `ta.*` namespace (sma, ema, rsi, macd, atr, supertrend, etc.), custom via functions and libraries; every value is a series. [K]
- NinjaTrader: ~100 built-ins, user-written indicators plotted on chart. [K]
- MT5: `iMA`, `iRSI` handles, custom indicators (`.ex5`). [K]
- AmiBroker: ~hundreds of AFL functions, vectorised. [K]
- StrategyQuant X: ~40 indicators plus "custom indicator" via code. [K]

Peak version for Studio:

- Built-in library of at least 150 indicators grouped (trend, momentum, volatility, volume, statistics, regime, cross-sectional), each with: formula, reference, default params, param ranges for optimisation, warm-up length, output names. One registry drives autocomplete, blocks, formula mode, and the optimiser.
- Indicator "lab" panel: pick indicator, symbol and range, tweak params with sliders, see the chart update live (no backtest).
- Auto warm-up: Studio computes the max warm-up from all indicators and pre-loads that history; reports "Strategy starts trading on 2020-03-12 (200 bars warm-up)".
- Streaming and vector parity test: every indicator is verified so streaming result equals vector result (hidden check; surfaced as a green "parity" badge).
- Custom indicator = a Python function with decorator `@indicator(inputs=..., outputs=..., warmup=...)`; shows up in blocks and formula mode automatically.
- Numba acceleration option for custom indicators (`@indicator(jit=True)`).
- Chained indicators (`rsi_of(sma(close,5),14)`) supported and drawn.
- Indicators on any series: price, volume, another indicator, equity curve (for equity-curve trading rules).

## 5. Orders and execution model

Competitors:

- QuantConnect: market, limit, stop market, stop limit, limit-if-touched, trailing stop, market-on-open/close, combo orders, `set_holdings`, `liquidate`, `order_target_percent`; order events; fee, fill, slippage, settlement, margin models per security; brokerage models (IB, Alpaca, Binance, ...). [R reality; order list K]
- Pine: `strategy.entry/order/exit/close/close_all/cancel`, OCA groups, pyramiding, `calc_on_order_fills`, `process_orders_on_close`, bar magnifier, commission types, slippage in ticks, `strategy.risk.*`. [R]
- NinjaTrader: `EnterLong`, `ExitLongStopLimit`, `SetStopLoss`, managed vs unmanaged approach, `Calculate.OnEachTick`. [K]
- MT5: market execution modes, pending orders, stop level, freeze level, deviation; tick modes every tick/1m OHLC/open prices; real-tick mode. [R tester]
- AmiBroker: `SetTradeDelays`, `ApplyStop`, `PositionSize`. [K]

Peak version for Studio:

- Orders: `ctx.buy/sell(symbol, qty|pct|notional, type="market"|"limit"|"stop"|"stop_limit"|"trailing", price=..., tif="day"|"gtc"|"ioc"|"fok"|"moo"|"moc", tag="...")`, `ctx.target_percent(...)`, `ctx.rebalance({...})`, `ctx.close(symbol)`, `ctx.flatten()`. Bracket and OCO as first-class: `ctx.bracket(entry, stop, target)`.
- Order tags and groups show up in the trades table, chart markers, and logs.
- Execution model panel on every strategy (also saved with each run): fill assumption (next open, close, VWAP of next N bars, intrabar sim), slippage (fixed bps, volume share, spread-based), commissions (per share, per trade, % notional, exchange fees), borrow cost, financing, margin rules, settlement, partial fill rules, min lot, price tick rounding, session calendars. Each has a sensible preset (Retail US equities, Futures CME, Crypto spot, FX) and a "custom model" Python hook.
- Intrabar fills like Pine bar magnifier and MT5 "every tick": use lower-timeframe bars when available to decide whether stop or target hit first in the same bar; surface "ambiguous bar" count in results; default pessimistic (stop first).
- Order lifecycle visible: submitted, accepted, partial, filled, cancelled, rejected, with reason codes (insufficient buying power, halted, min size).
- Stale-fill and illiquidity guard (QC calls these out in Scheduled Events docs): warn when a strategy trades daily data at intraday times, or the first minutes of an illiquid symbol.
- Dry-run "what would this order do now" button in paper/live (shows size, est. cost, margin impact).

## 6. Portfolio

Competitors:

- QuantConnect: `portfolio` object (cash, total value, holdings, unrealized profit, margin used), portfolio-level margin call model, risk-free rate model, `set_cash`, multi-currency cash book, portfolio construction models. [R reality; rest K]
- Pine: single-symbol strategy account (equity, open trades, `strategy.initial_capital`, margin) with `strategy.risk.*` limits (max drawdown, max intraday loss, max position size). [R]
- Composer: weighting methods (equal, inverse volatility, specified). [K]
- StrategyQuant X: portfolio master combining multiple strategies, correlation matrix, Monte Carlo. [K]
- Build Alpha: portfolio builder across strategies. [K]

Peak version for Studio:

- Multi-asset, multi-currency account model from day one; base currency selectable; FX conversion on cash.
- Built-in sizing helpers: fixed fractional, volatility target, risk parity, Kelly (capped), ATR risk per trade, equal weight, inverse vol, custom function. Picker in blocks; function in code.
- Risk guards as declarative config (like `strategy.risk.*` but richer): max drawdown stop (flatten and halt), daily loss limit, max gross/net exposure, max leverage, max position per symbol, max sector weight, max orders per day, cool-down after N losses. Each guard logs a "risk event" row.
- Portfolio view during a run: positions table, exposure bars by symbol/sector/asset class, cash, margin used, Greeks for options, beta to benchmark.
- Combine strategies: portfolio of strategies with capital split, correlation matrix, diversified equity curve, risk-contribution chart.
- Benchmark selection (SPY default) with relative stats (alpha, beta, tracking error, information ratio).

## 7. Scheduling

Competitors:

- QuantConnect: ScheduledEvents with rich DateRules/TimeRules (see sourcing note), per-symbol trading calendars, custom rules, removal, documented event order (scheduled, consolidation, on_data), backtest vs live timing caveats, 10-minute handler timeout. [R]
- Pine: runs on bar close/every tick; timeframe-based via `timeframe.change()`, `time()` sessions; no true scheduler. [K]
- NinjaTrader: `OnBarUpdate` with `Calculate` mode; `Times[0][0]`; session templates. [K]
- MT5: `OnTimer`, `EventSetTimer`. [K]
- Composer: daily rebalance rule per symphony. [K]

Peak version for Studio:

- `ctx.schedule(every="day"|"week"|"month"|"quarter", at="open+10m"|"close-30m"|"10:30", on="last_trading_day"|"first_trading_day"|"mon,fri", symbol="SPY", tz="America/New_York")`. Equivalent builder in blocks and a human sentence in formula mode ("every month on the last trading day, 30 minutes before close").
- Calendar-aware by default (holidays, half days, per-exchange sessions, 24/7 crypto) and uses the same engine in backtest and live.
- Preview: "Next 10 firings" list and a calendar heat-map of firing dates so mistakes are obvious before running.
- Documented and visible event order per bar; a "timeline" debug view shows scheduled -> consolidator -> on_bar for one bar.
- Backtest-vs-live drift warning (QC documents that backtest scheduled events run on next bar, live fires on a real clock): Studio makes both fire at the same logical time and states the data latency assumption in the run settings.
- Handler timeout default 60 s with a visible profiler bar; configurable up to 10 minutes, with a recommendation to move heavy work to a `train` job.
- Cancel, pause, resume events at runtime via handle.

## 8. Logging, plots, debugging

Competitors:

- QuantConnect: `log/debug/error`, log files per backtest with download, custom charts with series types and markers, chart quotas by tier, Python debugger with breakpoints (expression and hit-count conditions), Variables, Watch, Set Value, step over/into. [R debugging, results]
- TradingView: Pine Logs pane (`log.info/warning/error`) from any scope, labels/boxes/lines/tables as debug drawings, plot into Data Window/status line/price scale, `bgcolor`, `barcolor`; Pine Profiler (script performance). [R debugging; profiler K]
- VS Code: logpoints, conditional breakpoints, data breakpoints, call stack, debug console, inline values. [K]
- MetaEditor: debugger on history data or real-time, breakpoints, watch, profiler by function and by line. [K]
- NinjaTrader: `Print()` to Output window, `Draw.*` objects, Visual Studio attach. [K]
- MT5 tester: Print/Comment disabled during optimisation for speed (except in OnInit). [R]

Peak version for Studio:

- Logs panel: levels (debug, info, warn, error), timestamp in sim time and wall time, bar index, symbol, strategy tag; filter by level, text, regex, symbol, date range; click a row to jump to that bar on the chart and to the line of code; "pin" and "copy as JSON".
- Structured logging: `ctx.log.info("entry", symbol=s, rsi=r)` stored as key/values, searchable and exportable; auto-capture `print()`.
- Logpoints: right-click gutter, "Add logpoint: `rsi={rsi}`" with no code edit (VS Code style). They are removed from the optimiser path automatically.
- Time-travel debugger on a finished backtest: pick any bar, see variable snapshots, indicator values, open orders, positions, with arrow keys to step forward/back. Snapshots recorded only for chosen date ranges (to bound size). This beats QC (live stepping only) and Pine (logs only).
- Live debugger like QC/VS Code: breakpoints (line, conditional expression, hit count, logpoint, "break on exception", "break when order rejected"), step over/into/out, continue, variables tree, watch, set value, call stack, debug console to evaluate expressions. Shortcuts follow VS Code (F5, F9, F10, F11, Shift+F11) with QC's Alt+F10/F11 optional.
- Plot API: `ctx.plot("rsi", value, pane="rsi", color=..., style="line"|"histogram"|"step"|"dots")`, `ctx.mark(bar, "text", shape="arrow", color)`, `ctx.hline`, `ctx.region(start,end,color)`, tables on chart. Panes resizable, draggable; per-series toggle; chart quota default 25 series x 50,000 points with a visible meter and automatic decimation (never silently stop the run like QC).
- Data window: crosshair readout of every series at the cursor (Pine's Data Window pattern).
- Profiler: per-function and per-line time in the run; "slowest 10 lines" and a flame graph; memory chart.
- Assertions: `ctx.assert_invariant(cond, msg)` become red markers on the chart and failing tests in the Validate step.
- In optimisation, logs/plots auto-disabled with a banner (MT5 style) but keep an "only log errors" option.

## 9. Testing and results

Competitors:

- QuantConnect: runtime stats, performance chart, asset plots, key statistics, report PDF, orders/trades/insights tables, CSV/JSON downloads, clone/rename/delete, share results, out-of-sample period enforcement. [R results]
- Pine Strategy Tester: Metrics (key stats, returns, trade analysis, run-ups/drawdowns, capital efficiency), Trades list, Properties tab, Overview; trade markers on chart; 9,000-trade cap; deep backtesting; bar magnifier. [R]
- MT5 Strategy Tester: Results, Graph, Report, Journal tabs; visual mode with speed slider; tick modes. [R tester; tabs K]
- NinjaTrader Strategy Analyzer: Summary, Charts, Trades, Executions, Monte Carlo, Walk Forward. [K]
- StrategyQuant X: robustness tests (Monte Carlo, walk forward matrix, system parameter permutation, noise tests, "retest with another data"). [K]
- Build Alpha: robustness (Monte Carlo, vs random, Noise, Walk forward, Delayed test). [K]
- AmiBroker: Analysis window with Report, Equity, Trades, Optimization results. [K]
- WealthLab: Performance, Trades, Monte Carlo, Equity curve compare. [K]

Peak version for Studio:

- Every run is an immutable record: code hash, params, data version, execution model, engine version, seed, timing. Rerun reproduces numbers exactly; "Reproduce" button.
- Result page tabs: Overview, Equity and drawdown, Trades, Orders, Positions, Exposure, Returns (monthly heat map, yearly, rolling), Risk (VaR, tail, rolling Sharpe/vol/beta), Benchmark compare, Logs, Plots, Code snapshot, Settings, Warnings.
- 60+ stats with plain definitions on hover (CAGR, Sharpe, Sortino, Calmar, max DD, DD duration, win rate, profit factor, expectancy, payoff, exposure %, turnover, capacity estimate, PSR/DSR, SQN, tail ratio, ulcer index, skew/kurt, alpha/beta).
- Trade analysis: MAE/MFE scatter, hold time histogram, P&L by hour/weekday/month/regime/symbol, streaks, best/worst trades with chart jump.
- Compare view: select 2-6 runs, overlay equity curves, diff stats, diff parameters, diff code.
- Warnings engine on the result page: look-ahead suspicion, too few trades (<30), too good Sharpe, parameter at edge of range, high sensitivity, low capacity, ambiguous intrabar fills, stale data, survivorship.
- Validation suite ("Validate" step, one click): walk-forward, out-of-sample holdout (project-level locked holdout like QC out-of-sample period), Monte Carlo trade reshuffle and resample, noise injection, parameter perturbation, delayed entry, cost stress (2x/3x), random-entry baseline, deflated Sharpe with trials count. Single scorecard with pass/warn/fail and reasons.
- Export: CSV, JSON, Parquet, PDF tear sheet, shareable read-only link, and "open in notebook" with the result loaded.
- Cap trade retention at 100,000 trades (Pine caps at 9,000) with streaming storage; never silently trim.
- Visual replay mode: play the backtest bar by bar with speed control (MT5 visual mode), showing orders and equity.

## 10. Optimisation

Competitors:

- QuantConnect: up to 3 parameters in cloud, min/max/step, constraints, node count and cost estimate, choice of strategy (grid, Euler search, etc. [K]) and target metric, sortable/filterable result table, download. Local CLI for more params. [R]
- MT5: slow complete, fast genetic, forward optimisation, all symbols selected, custom criterion via `OnTester`, frames and cloud network agents (4GB limits). [R tester]
- NinjaTrader: Default and Genetic optimisers, custom optimisation fitness, walk-forward. [K]
- TradingView: no built-in optimiser (users hand-run inputs; third-party tools). [K]
- StrategyQuant X: genetic builder, genetic evolution, walk-forward matrix, cross-checks. [K]
- AmiBroker: exhaustive, smart (CMA-ES, PSO, tribes), walk-forward, `Optimize()` calls. [K]
- WealthLab: exhaustive, Particle Swarm, Genetic, Monte Carlo, Walk Forward. [K]

Peak version for Studio:

- Parameters are declared once: `p = ctx.param("fast", 10, min=2, max=100, step=1, kind="int"|"float"|"choice"|"bool", log=False)`. Blocks and formulas auto-expose the same params. UI shows a table of params with checkbox "optimise", range, step, distribution.
- No hard cap on number of params (QC caps at 3 in cloud). Search methods: grid, random, Latin hypercube, Sobol, Bayesian (Optuna TPE), genetic (NSGA-II), CMA-ES, successive halving. Defaults to Bayesian above 3 params.
- Multi-objective: choose several targets (Sharpe up, drawdown down, trades up), see Pareto front, pick a point.
- Constraints: any stat with operator and value (max DD < 20%, trades > 100); invalid runs are greyed not discarded.
- Cost and time estimate before launch (number of runs x seconds each, parallel workers), with a stop button and early-stopping rule.
- Result views: sortable table (every stat column, toggle, filter, download), 2D heat map for any pair, parallel coordinates plot, 3D surface, parameter importance bar, "stability" score (neighbour average vs peak), cluster of robust plateaus. Click any row opens the full backtest.
- Overfit guards on by default: split (in-sample/out-of-sample), walk-forward optimisation (anchored and rolling), trials counter feeding deflated Sharpe, warning when best params sit at a range edge, "choose plateau not peak" recommended.
- Resume, pause, clone optimisation, rename, delete, pin best.
- Custom objective in Python (`def objective(result) -> float`), like MT5 `OnTester`.
- Cache: identical (code, params, data) never rerun.
- One-click "promote best params to strategy defaults" which writes a new version.

## 11. Research notebooks

Competitors:

- QuantConnect Research: QuantBook, `add_equity`, `history`, plotting, per-project notebooks, run cells, stop nodes, add/rename/delete; supports Python and C# (Jupyter). [R]
- Jupyter/Colab: cells, kernels, inline plots, widgets, runtime GPU (Colab), share via link, Drive mounting. [K]
- Composer/TradingView/NinjaTrader/MT5: no notebooks. [K]
- Cursor/VS Code: notebook editor with AI. [K]

Peak version for Studio:

- Notebook tab in each project, sharing the same data layer and strategy code: `from studio import research as r` -> `r.history(...)`, `r.backtest("strategy.py", params=...)`, `r.load_run(id)`, `r.optimise(...)`.
- Cells run on a kernel that has the same package set and sandbox as the strategy runtime; kernel status, memory use, restart, interrupt, "run all above", variable explorer, DataFrame viewer with sort/filter.
- Studio-native widgets: `r.chart(df)`, `r.indicator_lab()`, `r.param_explorer()` returning interactive Plotly/lightweight-charts in cell output.
- Notebook to strategy: select cells, "Extract to strategy function". Strategy to notebook: "Open run in notebook" preloads the equity and trades frames.
- Format: .ipynb compatible import and export; stored as plain JSON diff-friendly with outputs stripped on save by default.
- Limits shown: kernel idle timeout 60 min default, 4 GB RAM default, one kernel per project, resource meter visible.
- Real-time collaboration optional (see section 12).

## 12. Versioning and collaboration

Competitors:

- QuantConnect: project sharing with teammates, clone backtests/projects, organisation roles, backtest history per project, "live coding" collaboration [K], git sync with local CLI (`lean cloud pull/push`). [K; Projects page R]
- TradingView: Pine script version history with diff, restore; "Publish" with release notes; private/invite-only/open; script comments. [K]
- VS Code: Git integration, timeline, diff, GitHub PRs, Live Share. [K]
- Cursor: same as VS Code plus shadow workspaces. [K]
- StrategyQuant X: project database with versions of strategies; no collaboration. [K]
- Google Colab: comments, share, revision history. [K]

Peak version for Studio:

- Every save of a strategy creates a lightweight snapshot; "Commit" makes a named version with message. Timeline panel shows versions with the backtest metrics attached to each (equity sparkline, Sharpe), so you see which edit made it better or worse.
- Side-by-side diff between any versions; restore creates a new version, never destroys history.
- Branches ("experiments"): fork a strategy, change a rule, compare the two branches' results on one chart. Merge a branch back.
- Git sync: connect a GitHub repo; push/pull; the project is a normal folder (strategy.py, params.json, studio.toml). `studio` CLI mirrors it.
- Share: read-only link to code and results; invite by email with roles Viewer, Commenter, Editor, Owner; per-run share links that hide code if wanted.
- Comments anchored to lines and to chart bars; resolvable threads; mentions.
- Presence and live co-editing (cursor colours) via Yjs, off by default, per-project toggle.
- Audit log: who changed what, who ran what, who deployed what to live (required for live trading).
- Locked holdout period at project/org level (QC out-of-sample period): backtests cannot end after cutoff date until "unlock" with a recorded reason.

## 13. Templates, libraries, sharing

Competitors:

- QuantConnect: strategy library with community posts, "Clone" project, algorithm framework templates, libraries as projects you can add to other projects, third-party libraries. [R projects; rest K]
- TradingView: script library (public, invite-only, protected), `import user/lib/1` libraries exporting functions/types/enums with annotated docs; House Rules for publication; ideas. [R libraries]
- NinjaTrader: NinjaScript add-ons, App Share, import/export `.zip`. [K]
- MetaTrader: Market (paid EAs), Code Base (free), VPS. [K]
- Composer: public symphonies marketplace, clone and edit. [K]
- StrategyQuant: templates for builder; "genetic options" presets. [K]
- AmiBroker: formula library on user forum. [K]

Peak version for Studio:

- New-strategy gallery with filters (asset class, style, timeframe, complexity, mode: blocks/formula/Python): at least 30 vetted templates (trend following, mean reversion, momentum rotation, pairs, vol targeting, risk parity, breakout, opening range, options income, crypto funding). Each opens with a plain-language explainer, expected stats on a fixed period, and known weaknesses.
- Libraries: a project can be marked "library"; others import by `from lib.risk import atr_stop` with version pinning (`@1.2`). Library docs auto-generated from docstrings and type hints (Pine library style), with examples tested on every publish.
- Snippets palette (Ctrl+Shift+S): user snippets, team snippets, tab-stop placeholders; "save selection as snippet".
- Publish: private, team, link, public. A published strategy shows code license, a locked verification run (code hash + result), and clone count.
- Import/export: strategy bundle (.studio zip: code, params, notebooks, settings, run summary) round trips between workspaces. Import from Pine/AFL is out of scope; import from QuantConnect (Python) via adapter is in scope.
- Block library: custom blocks made from a Python function, appear in block palette with icon and param form.

## 14. AI assistance

Competitors:

- QuantConnect: "Ask AI" in docs, "Mia" AI assistant in IDE for code help and explanation. [K; "Ask AI" visible in fetched pages]
- TradingView: Pine Script AI helper features and community "Pine Coder" tools are limited; Pine Editor has no first-party agent. [K]
- Cursor: inline edit (Ctrl+K), chat with codebase context, agent mode with tool use, tab completion predicting next edit, rules files, @-mentions of files/docs. [K]
- GitHub Copilot in VS Code: inline completion, chat, edits, agent mode. [K]
- Composer: AI "Symphony from prompt" helper. [K]
- StrategyQuant/Build Alpha: no LLM; machine search is the "AI". [K]
- Colab: Gemini code gen in cells and "explain error". [K]

Peak version for Studio:

- Context aware assistant docked to the editor with access to: current file, params, last run result, logs, error, selected chart region, data catalog, engine API docs.
- Actions (each shows a diff to accept/reject; never auto-applies unless the user enables it): write strategy from description, convert blocks to Python and back, explain code line by line, fix error from traceback, add risk guard, add param and expose for optimisation, convert to vectorised form, write unit test, refactor, add logging, comment trades.
- Inline: Ctrl+K "edit selection", ghost-text completions with next-edit prediction (Cursor-like), "explain this stat" on any result number, "why did this trade happen" on a chart marker (uses the time-travel snapshot).
- Critic mode: after each backtest, AI reviews the result and the code for overfitting, look-ahead, unrealistic costs, thin sample; outputs a short list with line references. Must cite data (trade count, stat, line) rather than opinion.
- Agentic research loop: "Try 5 variants of the exit rule and report which survives walk-forward" runs experiments in a sandbox with a budget (runs, minutes, cost) and returns a table; each variant is a branch.
- Rules file (`studio.rules.md`) for house style, forbidden patterns, preferred risk limits; the assistant obeys it.
- Model picker, usage meter, per-project data-sharing switch, offline mode with a local model. Prompts and edits logged in the audit trail.
- Hard guardrails: AI can never place live orders or change live deployments; it can propose, a human clicks.

## 15. Alerts and live

Competitors:

- QuantConnect: live deployment to brokerages (IB, Alpaca, Tradier, Kraken, etc.), live results with logs, notifications (email, SMS, webhook, Telegram) from code, `set_live_mode`, state persistence via object store, "Live Trading" nodes with cost. [K; section links R only via nav]
- TradingView: alerts run 24x7 on servers; alert types: price/indicator, drawing, script `alert()`, `alertcondition()`, strategy order-fill alerts with placeholders (`{{strategy.order.action}}`), webhook URL, frequency options (once, once per bar, once per bar close), expiry. [R alerts]
- MT5: Expert Advisors on VPS, push notifications, `SendMail`, `Alert` (disabled in tester). [R tester; VPS K]
- NinjaTrader: SIM account, ATM strategies, connect to brokers, Alerts window with sounds, email. [K]
- Composer: auto-trade on Alpaca/ DriveWealth with rebalance schedule and email. [K]
- AmiBroker: auto-trading via IB controller, alerts with `AlertIf`. [K]

Peak version for Studio:

- Promotion path with gates: Backtest -> Validate -> Paper -> Live small -> Live. Each step has a checklist (min trades, min days of paper, max divergence from backtest) the user can edit; live cannot be enabled without a typed confirmation and a risk limits sheet.
- Paper mode uses the same engine and execution model; records slippage and latency, and shows a daily "paper vs backtest" divergence report (signals matched, fills differ).
- Live dashboard: positions, open orders, P&L today/total, heartbeat, data lag, last bar time, broker connection, kill switch (flatten all and halt), pause new entries, per-strategy and global.
- Alerts: rule builder ("drawdown > 5%", "order rejected", "data lag > 2 min", "no signal for 3 days", "position size > X", "heartbeat lost") with channels (email, push, Slack/Discord/Telegram, webhook with templated JSON `{{symbol}} {{action}} {{qty}}`); frequency controls (once, per bar, per day); quiet hours; test button.
- Strategy-defined alerts: `ctx.alert("text", level, channels=[...])`.
- State persistence and crash recovery: strategy state auto-saved, restart resumes with same positions after reconciliation with the broker; mismatch halts and asks.
- Deploy diff: shows exactly what changed vs the currently running version (code diff and params diff); hot-swap only between bars, never mid-order.
- Run history for live: each live day as a result page comparable to backtest.
- Signals-only mode (publish signals/webhook, no execution) for users who trade elsewhere.

## 16. Keyboard and commands

Competitors:

- VS Code: command palette (Ctrl+Shift+P), quick open (Ctrl+P), go to symbol (Ctrl+Shift+O), go to line (Ctrl+G), rename F2, peek F12/Alt+F12, find references Shift+F12, multi-cursor, keybinding editor with JSON, chords. [K; IntelliSense triggers Ctrl+Space R]
- QuantConnect: debugger shortcuts Alt+F10/F11, Shift+F11, Shift+F5; Monaco defaults. [R]
- TradingView: Pine Editor shortcuts (Ctrl+Enter add to chart, Ctrl+S save, Ctrl+Space autocomplete), chart hotkeys (Alt+T trend line etc.), command search "/". [K]
- MetaEditor: F7 compile, F5 debug, F4 profile. [K]
- NinjaScript: F5 compile. [K]
- Cursor: Ctrl+K inline edit, Ctrl+L chat, Tab accept. [K]

Peak version for Studio:

- Command palette (Ctrl/Cmd+Shift+P) lists every action in the app, not just the editor: run backtest, run on range, optimise, validate, open run, switch mode, deploy paper, toggle panels, new branch, go to bar/date, add indicator. Recent and fuzzy match; shows the shortcut.
- Quick open (Ctrl+P) for files, runs (`#run`), params (`@param`), symbols (`$AAPL`), commands (`>`), lines (`:120`).
- Default keymap is VS Code's; presets: VS Code, Sublime, JetBrains, Vim (monaco-vim), Emacs; full keybinding editor (search by action, record chord, conflict warnings), import/export JSON.
- Core run shortcuts: Ctrl+Enter run backtest, Ctrl+Shift+Enter run with last params on last range, F5 debug, Ctrl+B toggle sidebar, Ctrl+J toggle bottom panel, Ctrl+\ split editor, Ctrl+K Z zen mode.
- Cheat sheet overlay (`?`) showing context-sensitive shortcuts. Every toolbar button's tooltip shows its shortcut.
- Chart keys: arrows step bar, Space play/pause replay, +/- zoom, G go to date, T jump to next trade.
- Accessible: all actions reachable without a mouse; screen reader mode toggle in Monaco.

## 17. Customisation and settings

Competitors:

- VS Code: settings UI and JSON, user/workspace/folder scopes, themes, icon themes, snippets, extensions, profiles, settings sync, `editor.*` options. [K]
- Monaco editor API: `IStandaloneEditorConstructionOptions` includes fontSize, fontFamily, fontLigatures, lineHeight, minimap, wordWrap, tabSize, renderWhitespace, rulers, bracketPairColorization, guides, stickyScroll, folding, lineNumbers, cursorStyle/Blinking, smoothScrolling, quickSuggestions, suggest options, inlayHints, parameterHints, formatOnType/Paste, accessibilitySupport, readOnly, theme via `defineTheme`. [K; typedoc 404]
- TradingView: chart themes, Pine editor font size/theme, indicator Settings (Inputs, Style, Visibility tabs), templates for indicator settings. [R inputs]
- MetaEditor: toolbar, colour scheme, code style options. [K]
- NinjaTrader: workspaces, templates for charts/strategies/indicators, hotkeys. [K]
- AmiBroker: layouts, templates, preferences dialogs with 100s of options. [K]

Peak version for Studio:

- Settings UI with search, three scopes (User, Project, Run), and settings.json editable. Every setting has a description, default, and "reset" icon. Changes apply live.
- Editor options (all exposed): font family (with a good mono default, ligatures toggle), size 10-24, line height, tab size, spaces/tabs, rulers, minimap (show, side, scale, slider), word wrap, whitespace rendering, bracket colours, indent guides, sticky scroll, cursor style/blink/smooth caret, line numbers (on, relative, off), scroll beyond last line, mouse wheel zoom, format on save/paste/type, auto closing brackets/quotes, suggestion behaviour (accept on Tab or Enter, snippets priority, quick suggestions on/off/delay), parameter hints, inlay hints (types, param names), code lens (run test, run on this function), hover delay.
- Theme system: light, dark, high contrast, 6+ built-in editor themes (Dark+, Light+, Solarized, One Dark, GitHub, Monokai), import VS Code theme JSON, separate chart theme (candles up/down colours, grid, background), colour-blind safe preset.
- Layout: dockable panels (editor, chart, results, logs, data, notebook, AI), drag to rearrange, save named layouts ("Coding", "Review results", "Live monitor"), per-monitor popout windows.
- Result column sets, default stats list, number formats (%, bps, currency), timezone, date format, default benchmark, default capital, default execution preset; all per-user with per-project override.
- Run templates: named bundles of range, capital, data, execution model, params; chosen from a dropdown next to the Run button.
- Settings sync across devices; export/import settings file; admin policy layer for teams (lock a setting).
- Extension points (later): custom blocks, indicators, execution models, result widgets via a small plugin API.

## 18. Performance

Competitors:

- QuantConnect: backtest nodes by tier (B-series CPU/RAM), 10-minute handler timeout, chart quotas, data memory limits, "Lean Cloud" parallel optimisation nodes. [R schedule, results, optimisation]
- Pine: runs in the browser/server, 9,000-trade cap, execution time limit (~20-40 s typical, [K]) with profiler. [R trade cap; profiler K]
- MT5: multi-core local optimisation, MQL5 Cloud Network, frames, limits of 4GB disk/RAM per agent. [R]
- NinjaTrader: multi-threaded optimiser, 64-bit. [K]
- AmiBroker: C++-speed AFL, multi-threading, "turbo" mode. [K]
- StrategyQuant X: multi-core genetic, databanks. [K]
- Monaco/VS Code: virtualised rendering, web workers for language services, large file mode. [K]

Peak version for Studio:

- Engine speed targets (state them in the UI): 10 years of daily data on one symbol under 1 s; 1 year of minute bars on 10 symbols under 10 s; vectorised mode (`signals(df)`) 20x faster than event mode, auto-selected when the strategy is vectorisable.
- Numba/Rust core for event loop; parallel optimisation over all cores with worker pool; progress bar with ETA, runs/second, and CPU meter.
- Incremental backtest: change only the last N bars of code? Not possible, but cache indicators and data between runs so the second run of the same data is fast. Cache keyed by (data version, indicator params).
- Editor stays responsive: language server in a web worker, large file mode above 2 MB, results tables virtualised (100k rows smooth), charts use WebGL/canvas with decimation (LTTB) for >50k points.
- Run quotas visible (concurrent runs, CPU minutes, memory), with a clear "why was this killed" reason (timeout, memory, handler too long) and tip to fix.
- Streaming results: equity curve and trades appear during the run; cancel at any time with partial results saved and marked.
- Background runs continue when the tab closes; notification when done.
- Cold start budget: IDE interactive under 2 s on a typical laptop.

## 19. Language intelligence (editor core extras)

Competitors:

- VS Code IntelliSense: completion lists, parameter info, quick info, member lists, CamelCase filtering, Ctrl+Space, trigger characters, snippets, auto imports via language server. [R IntelliSense page]
- Pine Editor: autocomplete of namespaces, function signature help, built-in docs hover with "go to reference", error squiggles, version converter v5 -> v6. [K]
- QuantConnect: Python IntelliSense via Pylance-like service in web IDE, hover docs for LEAN API, error list, autocomplete of `self.` members. [K]
- MetaEditor: IntelliSense with MQL5 doc, F1 jumps to docs, code navigation panel. [K]
- NinjaScript: full C# IntelliSense via Roslyn, wizard-generated code. [K]

Peak version for Studio:

- Language server (Pyright or Jedi in a web worker; pyright-wasm preferred) with Studio stubs: completion, signature help, hover with docs and examples, go to definition, peek definition, find all references, rename symbol (F2), outline (Ctrl+Shift+O), workspace symbols, call hierarchy, code actions ("Add missing import", "Extract function", "Convert to f-string"), inlay hints, semantic highlighting, diagnostics as you type.
- Domain diagnostics (the thing no competitor does well): look-ahead, unused param, indicator warm-up longer than data range, order with no stop in live mode, hard-coded symbol in a param strategy, using `print` in hot loop, mutable default in param.
- Hover on any param shows its optimisation range and last best value; hover on an indicator shows its last value in the selected debug bar.
- Docs panel with search (API, indicator reference, recipes), opens beside the editor; F1 on a symbol jumps to it.
- Quick fix to migrate API versions.
- Minimum latency budget: completions under 100 ms, diagnostics under 500 ms after typing stops.

---

# Ranked list: 40 highest-value features for Studio

1. Immutable, reproducible run records (code hash, params, data version, execution model, seed) with "Reproduce".
2. Same code and execution model for backtest, paper and live, with a paper-vs-backtest divergence report.
3. Validation suite in one click (walk-forward, holdout, Monte Carlo, noise, cost stress, deflated Sharpe) producing a scorecard.
4. Look-ahead protection by construction (API design plus editor lint plus runtime guard).
5. Declarative params exposed once and reused by blocks, formula, code, optimiser.
6. Optimiser with grid/random/Bayesian/genetic, multi-objective Pareto, constraints, heat maps, stability score, no 3-param cap.
7. Execution model panel with presets and custom hooks (fees, slippage, fills, borrow, margin).
8. Intrabar fill simulation with conservative default and "ambiguous bar" count.
9. Full Monaco language server with Studio stubs: completion, signature help, hover, go to definition, rename, diagnostics.
10. Domain-specific diagnostics (look-ahead, warm-up, risk guards missing, overfit hints).
11. Result page with 60+ stats, plain-language definitions, compare 2-6 runs.
12. Warnings engine on results (too few trades, too-good Sharpe, edge-of-range params).
13. Version timeline with metrics attached to each version, diff, restore, branches.
14. Time-travel debugger on finished backtests (any bar, variable snapshot).
15. Live-step debugger with conditional, hit-count, and logpoints, VS Code-compatible keys.
16. Structured logs panel with filter, click-to-bar, click-to-line.
17. Plot API with panes, markers, regions, data window, decimation, no silent chart-quota failure.
18. Three authoring modes (blocks, formula, Python) with live generated-code view and eject.
19. Command palette that covers every app action, plus quick open for files, runs, params, symbols.
20. Fully remappable keybindings with VS Code, Vim, JetBrains presets.
21. Settings with search and user/project/run scopes; full Monaco option exposure.
22. Dockable, saveable layouts and theme import (VS Code theme JSON).
23. Calendar-aware scheduler API with rule previews (next 10 firings) and same behaviour in backtest and live.
24. Data catalog panel with gaps, adjustments, last update, quality report per run.
25. Multi-timeframe access with correct "last completed bar" semantics only.
26. Indicator registry (150+) driving autocomplete, blocks, formulas, optimiser ranges, with auto warm-up.
27. Indicator lab (interactive tuning with no backtest).
28. Risk guards as declarative config (drawdown stop, daily loss, exposure caps) with logged risk events.
29. AI assistant with diffs, inline edit, error fix, explain stat, "why did this trade happen".
30. AI critic that reviews each backtest and cites lines and numbers.
31. AI experiment agent that runs variants as branches under a budget.
32. Live dashboard with kill switch, heartbeat, data lag, reconciliation and halt on mismatch.
33. Alert rule builder with webhook templating, frequency, quiet hours, test button.
34. Promotion gates (backtest -> validate -> paper -> small live -> live) with editable checklists.
35. Notebook tab sharing data and engine, with `load_run` and `optimise` helpers, ipynb import/export.
36. Libraries with version pinning, auto-docs and tested examples; block-from-function.
37. Template gallery with 30+ vetted strategies, expected stats, known weaknesses.
38. Locked out-of-sample holdout at project/org level.
39. Performance targets, parallel workers, run caching, streaming results, cancel with partial results.
40. Comments anchored to code lines and chart bars, roles, audit log, optional live co-editing.

---

# What competitors do badly (avoid)

- QuantConnect: chart quota stops the run when exceeded; cloud optimisation capped at 3 parameters; backtest vs live scheduled-event timing differs and is a documented trap; debugger needs a breakpoint just to start; cost and credits visible only at launch; heavy framework concepts hard for beginners.
- TradingView: trade list capped at 9,000 and silently trimmed; no built-in optimiser; no real debugger (logs only); single-symbol strategy account; broker emulator uses OHLC assumptions unless bar magnifier (paid); `request.security` look-ahead footguns; no version-aware result history.
- MetaTrader 5: Print/Comment disabled in optimisation, making debugging hard; cloud agents have hard 4GB limits yet still bill; outdated editor UX; result tabs not comparable across runs.
- NinjaTrader: C# only, compile-wait loop, Windows only, optimiser results hard to compare, unmanaged vs managed order confusion.
- AmiBroker AFL: array thinking is powerful but cryptic; poor error messages; dated UI.
- Composer: easy but opaque; little control over execution; no real debugging or validation.
- StrategyQuant X / Build Alpha: strong robustness tests but a data-mining culture that encourages overfitting; desktop UI heavy; code export quality varies.
- Jupyter/Colab: no reproducibility (hidden state, out-of-order cells), ephemeral runtimes, weak collaboration on code vs outputs.
- Cursor/Copilot: confident edits without domain checks; AI writes look-ahead bugs without noticing; Studio's AI must be wrapped by the same lint, validation and diff-approval rules.
- All of them: results that cannot be reproduced later; silent truncation; hidden assumptions (fill price, slippage, costs) not shown beside the equity curve; no visible warning that a good-looking result is likely overfit.

---
---

# PART 2: Every Studio page (scope extension)

The Python IDE above was one example. This part covers each Studio page the same way: what competitors do, then the peak version with customisation.

## Part 2 sources

Read this session [R]:

- [R] StrategyQuant Monte Carlo Tests: https://strategyquant.com/doc-new/monte-carlo-tests (trade manipulation: randomize order by resampling or exact, randomly skip trades with a probability; retest methods: randomize strategy parameters with probability and max % change, randomize history data; results as equity curves plus a table at confidence levels such as 80/90/95%)
- [R] StrategyQuant Walk-Forward Matrix: https://strategyquant.com/doc-new/walk-forward-matrix (grid of walk-forward runs over number of runs, e.g. 5 to 15, and OOS %, e.g. 20/30/40; finds best re-optimisation period; 3D chart; pass rule such as "7 of 9 cells succeed")
- [R] StrategyQuant search results on cross checks: https://strategyquant.com/doc-new/cross-checks-robust-testing-overview (cross-checks chained after generation: other markets, other timeframes, Monte Carlo, walk-forward, with auto-dismiss filters)
- [R] Build Alpha Robustness Guide (16+ tests): https://buildalpha.com/robustness-testing-guide (in/out-of-sample, randomized OOS, walk-forward, Vs Random, Monte Carlo permutation, noise test, Vs Shifted, Vs Others, synthetic data, MC reshuffle and resample, randomized MC for exits, variance test, delayed test, liquidity test, parameter permutation/sensitivity, Taguchi, automated sequence workflows, portfolio-level robustness)
- [R] Composer threshold trading: https://help.composer.trade/article/76-threshold-trading (rebalance when a weight leaves a corridor instead of on a calendar); search snippets on weight types (equal, specified, inverse volatility, market cap), "Any/All" condition groups, create with AI, backtest outputs (alpha, beta, R2, Sharpe, max drawdown, trailing returns, historical allocations table). Composer backtest help page was blocked (bot_blocked), so its detail is from search snippets only.
- [R] Option Alpha automations: https://docs.optionalpha.com/tools/bots/automations (steps are Actions and Loops; loops repeat per symbol or per open position; scheduled as Continuous scanners/monitors (every 15 min default), on a schedule, or by button; actions: decide, open/close, notify, tag) and best practices https://docs.optionalpha.com/tools/backtesting/best-practices (backtest evaluates at the top of the minute, uses mid-price at entry, slippage is added per contract, live fills differ; generate a bot straight from a backtest)
- [R] AmiBroker walk-forward: https://amibroker.com/guide/h_walkforward.html (automatic walk-forward mode, IS and OOS composite equity tickers, OOS summary report chained so each step starts from the previous ending equity, custom optimisation target from custom backtester metrics)
- [R] QuantConnect live trading search results: https://www.quantconnect.com/docs/v2/cloud-platform/live-trading (brokerage list includes Interactive Brokers, Alpaca, Tastytrade, Schwab, Kraken, Bybit, TradeStation, Webull, Public and more; paper trading selectable on Deploy Live; `on_brokerage_disconnect`; auto-restart and error emails; live results page)
- [R] Search snippets only (pages not opened): TrendSpider (https://trendspider.com: automated trendlines, multi-timeframe overlay, 200+ indicators, Raindrop charts, no-code Strategy Tester with 50+ years of data, cloud alerts and no-code bots), Portfolio123 (https://www.portfolio123.com: ranking systems, screener, rolling screen backtest, simulations with buy/sell rules, DataMiner API, rank performance buckets), WealthLab (https://wealth-lab.com: Building Blocks, optimisers with visualizers, WFO with efficiency %, Monte Carlo Lab extension), Pine Strategy Tester (page read in Part 1).

Not read, from product knowledge [K]: TradingView chart/screener/replay help, QuantConnect Alpha Streams, Koyfin, MetaTrader 5 detail beyond the tester page, NinjaTrader beyond the editor page, TrendSpider and Portfolio123 internals. Verify before copying exact limits.

---

## A. Home (strategy list)

Competitors:

- QuantConnect: project list with folders, search, last backtest metrics, clone, share, rename, delete, org-level views. [K; projects page R, thin]
- TradingView: "Open script" list, favourites, sort by recent; no per-script performance. [K]
- Composer: symphony list with live status, YTD return, drawdown, invested amount, tags; "Discover" marketplace. [K; help snippets R]
- Option Alpha: bots list with state (running, paused), P&L, open positions, health. [K]
- NinjaTrader: Strategies tab with enabled state and account. [K]
- Portfolio123: strategy/ports list with simulation, live book, and ranking system folders. [K]

Peak version for Studio:

- Table and card views, user choice. Columns (all toggleable and sortable): name, mode (blocks/formula/Python/English), status (draft, validated, paper, live), last run date, CAGR, Sharpe, max DD, trades, tags, owner, version, health, last edited. Default columns: name, status, Sharpe, max DD, last run, sparkline of equity.
- Per-row equity sparkline from the latest verified run, with a badge when the run is stale (code changed since).
- Status pipeline chips: Draft -> Backtested -> Validated -> Paper -> Live. Click a chip to filter. A strategy cannot show "Validated" unless the validation scorecard exists for the current version.
- Search (name, tag, code text, symbol used, indicator used), saved filters, folders and tags, pins, archive (never hard delete without a typed confirmation and a 30-day trash).
- Bulk actions: tag, move, archive, run same range on selected, compare selected (opens compare view), combine selected into a portfolio.
- Quick actions on hover: Run, Duplicate, Open in Chart, Open Live, Share.
- Create menu: blank, from template, from English prompt, import (.studio bundle, CSV of trades, QuantConnect Python), from a library strategy.
- Live strip at top: all live and paper strategies with today's P&L, alert count, heartbeat status, kill-all button.
- Customisation: saved views, column sets, default sort, density (compact/comfortable), group by (status, tag, folder).
- Empty state: three one-click starters, never a blank page.

## B. Build (blocks, formula, Python, plain English)

Competitors:

- Composer: tree of blocks (weight, if/else with Any/All conditions, filter, asset, group), weights equal/specified/inverse vol/market cap, trading frequency (calendar or threshold corridor), "Create with AI". [R snippets, threshold page R]
- Option Alpha: automation editor of ordered Actions and Loops, run as scanner/monitor/scheduled/button, decisions, notifications, tags. [R]
- WealthLab 8: Building Blocks visual strategy builder, C# code, strategy parameters panel. [K; blog snippet R]
- StrategyQuant X: Builder with block sets (indicators, entry/exit rule structure, money management), genetic generation, code export to MQL/NinjaScript/TradeStation/Python. [K]
- Build Alpha: pattern-based strategy generation, user-defined entry/exit rules, one-click code export to 8+ platforms. [R search snippet]
- TrendSpider: no-code visual scripting strategy builder. [R search snippet]
- TradingView Pine: code only; Pine Editor; "Strategy Tester" overlays. [R]
- QuantConnect: code only (Python/C#); framework modules. [R/K]

Peak version for Studio:

- One document model, four views: Blocks, Formula, Python, English. Edit in any view that is lossless; Python edits that cannot be represented in blocks mark the strategy "code-only" (visible badge) rather than silently destroying structure.
- Blocks:
  - Palette: Universe, Signal (indicator, price, fundamentals, custom), Condition (Any/All groups, nested, cross above/below, for N bars, rising/falling), Filter/Rank (top N by metric), Weight (equal, specified, inverse vol, vol target, risk parity, market-cap, signal-proportional), Entry, Exit (stop, target, trailing, time stop, signal flip, break-even), Risk guard, Schedule, Branch (if/else), Loop (per symbol, per position), Notify, Tag.
  - Each block: inline param editor with range for optimisation, plain-language summary line, colour by role, collapse, disable (grey), comment, duplicate, copy as code, drag to reorder, undo/redo (50 steps).
  - Live validation: red marker on incomplete blocks; "this condition is always true/false on your data" detector.
  - Mini-preview: click any condition block to see the bars where it fired on the chart (no full backtest).
  - Trading frequency setting from Composer: calendar (daily, weekly, monthly, on bar close) or threshold (corridor, X% drift).
- Formula:
  - Spreadsheet-like expression editor with autocomplete, units, and inline value preview at the cursor bar; named variables (`fast = ema(close, 12)`), user functions, comments.
  - Entry and exit as separate formulas; position size formula; error underline with plain message.
  - Compiles to the same Python shown in a side panel.
- Python: see Part 1 sections 1 to 9 and 19.
- English:
  - Describe the strategy in a sentence; Studio shows the interpreted rules as blocks BEFORE running, with ambiguous bits highlighted ("When you say 'oversold', I used RSI(14) < 30. Change?"). The user must confirm. Never runs from a prompt silently.
  - Every English strategy keeps the original prompt in version history and a restated "what this strategy does" paragraph generated from the blocks (so drift is visible).
- Cross-view features: undo history shared; "Explain" button on any selection; "Convert to library block"; params panel shows all params from all views in one table.
- Customisation: block colour themes, compact/expanded blocks, show/hide plain-language lines, snap grid, canvas vs tree layout, keyboard-first block insertion (type `/` to add).
- Limits: warn at more than 200 blocks, hard stop at 1,000; warn at more than 8 optimisable params.
- Complexity meter: counts params and rules; "degrees of freedom" shown next to it so users see the overfit risk as they build (no competitor does this).

## C. Backtest (report, trades, returns, risk)

Competitors:

- TradingView Strategy Tester: Metrics (key stats, return details, trades analysis, run-ups and drawdowns, capital efficiency), Trades list, Properties; bar magnifier; 9,000 trade cap. [R]
- QuantConnect: runtime stats, charts, key statistics, report, orders, trades, insights, logs, download, share, clone, out-of-sample enforcement. [R]
- Composer: alpha, beta, R2, Sharpe, max drawdown, cumulative/annualised/trailing returns, historical allocations table. [R snippets]
- Option Alpha: backtest with entry time in 5-minute increments, slippage per contract, mid-price entry, bot generation from backtest. [R]
- AmiBroker: report with many metrics, ISEQUITY/OSEQUITY composites, custom backtester metrics. [R]
- Portfolio123: rolling screen backtests and simulations with rank-bucket performance. [R snippets]
- StrategyQuant X / Build Alpha / WealthLab: databank of results with many columns, equity compare, stats filters. [K]
- MetaTrader 5: tick modes (every tick, 1-minute OHLC, open prices only), visual mode, report and graph tabs. [R]

Peak version for Studio:

- Run header: strategy, version, range, capital, data version, execution preset, seed, duration, engine version. "Reproduce" and "Duplicate and edit" buttons. A yellow banner when the editor code differs from the run.
- Tabs: Summary, Equity and Drawdown, Returns, Risk, Trades, Orders, Positions and Exposure, Benchmark, Costs, Logs and Plots, Warnings, Code and Settings.
- Summary: equity curve with drawdown below, benchmark overlay (toggle log/linear, % or $), regime shading (bull/bear/high-vol), trade markers toggle, date range brush that recomputes every stat for the selection. Stat tiles user-configurable (pick any 8 of 60+), with definitions on hover.
- Returns: monthly heat map, yearly bars, rolling windows (6/12/36 months) for return, Sharpe, vol, beta; return distribution with normal overlay; best/worst day lists; calendar view.
- Risk: drawdown table (top 10 with start, trough, recovery, length), underwater plot, VaR/CVaR at 95/99, tail ratio, ulcer index, beta/correlation to benchmark, exposure over time, leverage, concentration, stress scenarios (2008, 2020, rates 2022) if data covers them.
- Trades: virtualised table, 100,000+ rows, columns toggleable (entry/exit time, symbol, side, size, entry/exit price, P&L $/%, MAE, MFE, bars held, tag, reason, costs); filters (winners, losers, symbol, tag, date, size); click row to jump on the chart and to the source line; export CSV/Parquet.
- Trade analytics: MAE/MFE scatter, P&L by hour/weekday/month/regime, holding time histogram, streaks, expectancy by tag, "what if" exit overlay (change stop/target and see approximate effect, flagged as approximate).
- Costs tab: gross vs net, commission, slippage, borrow, financing; break-even cost level; cost sensitivity slider (0x to 3x) that recomputes instantly using stored fills.
- Intrabar assumptions visible: tick/bar mode, ambiguous-bar count (stop and target both hit), fill rule. Choose fidelity: Fast (bar close), Standard (bar OHLC with pessimistic ordering), Detailed (lower timeframe magnifier), Tick (when data available).
- Options-specific (when strategy trades options): fill at mid with slippage per contract (Option Alpha pattern) plus bid/ask option; Greeks over time; assignment events; days to expiry stats.
- Compare: 2 to 6 runs, overlay, diff stats, diff params, diff code, diff execution model.
- Warnings tab: look-ahead suspicion, too few trades, huge single-trade contribution (top trade > 20% of profit), parameter at range edge, costs eat >50% of gross, survivorship note, data gaps.
- Export: PDF tear sheet (customisable sections and logo), CSV, JSON, shareable link with optional hide-code.
- Customisation: saved report layouts, stat sets, default benchmark, number formats, colour-blind palette, dark/light chart themes.

## D. Optimise (sweeps, maps, objectives)

Competitors (see also Part 1 section 10):

- QuantConnect: min/max/step, up to 3 params in cloud, constraints, node and cost estimate, strategy and target selection, sortable table. [R]
- AmiBroker: exhaustive, smart optimisers, walk-forward with custom metric targets from the custom backtester. [R walk-forward page; rest K]
- WealthLab: exhaustive and Monte Carlo optimisers, optimisation visualizers (2D/3D) via extension API, WFO with efficiency %. [R snippets]
- StrategyQuant X: genetic evolution, optimiser module with walk-forward and matrix, filters on results. [R/K]
- MetaTrader 5: genetic and complete, forward mode, custom criterion, frames. [R tester page]
- Build Alpha: parameter permutation/sensitivity and Taguchi robust design in robustness suite. [R headings]
- Portfolio123: rank performance by bucket as a way to test factor strength. [R snippet]

Peak version for Studio:

- Setup sheet: table of parameters with checkbox, min, max, step, scale (linear/log), type, "link to" (tie one param to another, e.g. slow > fast + 5), and a live count of combinations and estimated runtime and cost.
- Objective builder: one or several objectives from any stat, expression (`sharpe - 0.5*max_dd`), direction, weights; penalty rules (trades < 100 -> invalid); Pareto mode for 2 or 3 objectives.
- Search method picker with plain advice: Grid (small spaces), Random, Sobol, Bayesian (default above 3 params), Genetic/NSGA-II, CMA-ES, Successive halving. Budget: max runs, max minutes, early stop on no improvement for N runs.
- Data split built in: in-sample vs hold-out vs walk-forward optimisation (anchored or rolling), with the OOS shown alongside every row. The hold-out is hidden from the objective by construction.
- Results:
  - Table with every stat, in-sample and OOS columns, rank, stability score (average of neighbours), robust flag; filter, sort, column picker, CSV.
  - 2D heat map for any two params with a chosen stat, cell click opens the run; contour smoothing toggle; shows neighbourhood stability overlay (flag peaks without plateaus).
  - 3D surface, parallel coordinates, parameter importance, scatter of stat A vs stat B coloured by param, histogram of outcome across all trials (what a random pick would give).
  - "Pick plateau" tool: select a region of the map; Studio returns the median param set and its spread, with a run of that set.
- Trials counter feeds deflated Sharpe in Validate; shown on the page ("1,240 trials, expected best Sharpe from luck alone: 1.1").
- Controls: pause/resume/cancel, clone with changed ranges, narrow ranges around selection ("zoom in" with one click), save sweep as a template, pin best.
- Apply: "Use these params" creates a new version; never overwrites silently.
- Customisation: default search method, default objective, default split, max parallel workers, auto-run validation on the top 5.

## E. Validate (walk-forward, Monte Carlo, robustness, overfitting)

Competitors:

- StrategyQuant X: Monte Carlo trade manipulation (randomise order via resample or exact, randomly skip trades) with confidence-level tables; MC retests (randomise parameters with probability and max % change, randomise history data); Walk-Forward Matrix over runs x OOS %; cross-checks automated after generation with filters. [R]
- Build Alpha: 16+ tests in groups: data split (IS/OOS, randomised OOS, walk-forward), edge vs luck (Vs Random, Monte Carlo permutation), alternate price paths (Noise, Vs Shifted, Vs Others, synthetic), trade-list MC (reshuffle, resample, randomised MC for exits, variance test), execution (delayed, liquidity), parameter (permutation/sensitivity, Taguchi); automated sequence workflows; reading noise-test width not just pass/fail. [R]
- AmiBroker: automatic walk-forward with IS and OOS composite equity, OOS summary report, custom metric target. [R]
- WealthLab: WFO, Monte Carlo Lab, sensitivity. [R snippets]
- QuantConnect: out-of-sample period enforced at org level; warns about overfitting in optimisation docs. [R]
- TradingView: docs warn about lookahead, selection bias, overfitting; no tooling. [R]
- Portfolio123: stress tests by rolling screens, bucket monotonicity. [R snippet]

Peak version for Studio:

- Validate page = scorecard plus drill-down. One button "Run full validation" with a preset (Quick 2 min, Standard 15 min, Thorough 1 h) and a custom checklist.
- Scorecard: each test gives Pass / Warn / Fail with the threshold and the actual number, a one-line reason, and a link to details. Overall grade shown with the weakest test highlighted. Thresholds editable per user/team and saved as a "validation policy".
- Test groups (include all of the competitors' tests, named plainly):
  1. Data split: fixed hold-out, randomised OOS blocks, k-fold by time blocks (purged and embargoed), walk-forward (anchored/rolling), Walk-Forward Matrix (runs x OOS%) with 3D surface and "k of n cells pass" rule (SQX).
  2. Edge vs luck: Vs Random (best random-entry strategy with same trade frequency), Monte Carlo permutation (shuffle returns to make synthetic paths), White's reality check / SPA, deflated Sharpe and probability of backtest overfitting using the optimisation trials count.
  3. Alternate price paths: noise test (perturb OHLC by x ATR, N runs; show distribution and width), Vs Shifted (shift entry bars), Vs Others (related symbols, other timeframes, other time periods), synthetic data (block bootstrap, GARCH).
  4. Trade-list Monte Carlo: reshuffle (drawdown distribution), resample with replacement, randomly skip trades (p%), randomised exits, variance test (what if future is worse than past), confidence table at 80/90/95/99%.
  5. Execution: delayed entry (1, 2, 5 bars), slippage and commission stress (1x to 3x), partial fills, liquidity cap (% of volume), spread widening, missed fills.
  6. Parameter robustness: permutation grid around chosen params, % change randomisation (SQX) with probability and max change, sensitivity plot, Taguchi, plateau width.
  7. Regime tests: performance by regime (trend/range, high/low vol, rates up/down, bull/bear), worst regime stats, rolling window consistency, subperiod table (year by year).
  8. Sanity: look-ahead detector (re-run with shifted data truncated and compare signals), minimum trades, single-trade dependence, data-leak scan of features.
- Workflow chaining (SQX cross-checks and Build Alpha sequence workflows): run a chain on every strategy in a folder; auto-dismiss on fail; table of survivors.
- Detail views: every test has chart + table + "how to read this" in two sentences, number of simulations, seed, runtime; re-run with more sims; export.
- Result of Validate is bound to a strategy version; changing code invalidates it and says so.
- Portfolio-level validation: same suite on a portfolio of strategies (Build Alpha) including correlation stability.
- Gate: live deployment (page G) can require a minimum validation grade; override needs a typed reason that goes in the audit log.
- Customisation: choose tests, thresholds, number of sims (default 1,000, up to 100,000), seeds, fixed vs random seed, compute budget, save policy per team.

## F. Portfolio (combining strategies, allocation)

Competitors:

- Composer: weights equal/specified/inverse vol/market cap in a tree, nested symphonies, threshold rebalancing, historical allocations table. [R snippets and threshold page]
- StrategyQuant X: Portfolio Master (combine strategies, correlation, money management at portfolio level, Monte Carlo). [K]
- Build Alpha: portfolio simulation, robustness of portfolios. [R]
- Portfolio123: simulations with multiple sleeves, position limits, turnover, ranking-based rebalancing. [R snippets]
- QuantConnect: portfolio construction models (equal weight, mean-variance, Black-Litterman, risk parity), risk models, Alpha Streams marketplace for selling alphas. [K]
- WealthLab: portfolio-level backtests with multi-strategy and "Combine strategies" extension. [K]
- AmiBroker: portfolio backtester, position sizing, rotation, "custom backtester" for portfolio logic. [K, AmiBroker custom backtester snippet R]
- NinjaTrader: multi-strategy under one account. [K]

Peak version for Studio:

- Portfolio object = list of sleeves (strategies or other portfolios), each with weight, capital, start date, enable toggle, scaling (vol target, leverage cap).
- Allocation methods: fixed weights, equal, inverse vol, risk parity (ERC), minimum variance, max diversification, mean-variance with shrinkage, HRP, Kelly-fraction (capped), momentum-of-strategies, drawdown-based throttle, custom Python function. Rebalance rule: calendar or threshold corridor (Composer), plus min trade size to cut churn.
- Live preview of weights over time (stacked area) and effective number of bets.
- Analytics: combined equity versus individual sleeves, correlation matrix (full-period and rolling), diversification ratio, marginal contribution to risk and return, drawdown overlap (do sleeves lose together?), capacity by sleeve, turnover, cost drag, net exposure by symbol across sleeves, netting benefit (opposite trades cancel before execution).
- Constraints: max weight per sleeve, per symbol, per sector, gross/net limits, leverage, cash reserve, min sleeve count, ban list.
- Stress: reuse the Validate suite on the combined equity; sleeve drop-out test (remove each sleeve, see the effect); correlation shock (all sleeves correlation to 0.8).
- Overlap guard: warns when two sleeves hold the same symbol in opposite directions or share >70% of signals.
- Walk-forward allocation test: estimate weights on trailing window, evaluate OOS, to avoid fitting weights on the full sample (show the difference vs full-sample weights).
- One-click "deploy portfolio" to paper/live as a single book with netted orders and per-sleeve P&L attribution.
- Customisation: default allocation method, rebalance schedule, constraint presets, which analytics are on the page.

## G. Live (paper trading, signals, orders, alerts, broker)

Competitors:

- QuantConnect: deploy wizard, brokerage list (IB, Alpaca, Tastytrade, Schwab, Kraken, Bybit, TradeStation, Webull, Public and others), Paper Trading brokerage option, live results page, auto-restart, error emails, `on_brokerage_disconnect` hook. [R]
- Option Alpha: bots with scanners/monitors on 15-minute defaults, notifications, bot generated from a backtest, differences vs backtest explained. [R]
- Composer: auto-trade symphonies at a broker, invest/withdraw, threshold or calendar. [K, snippets R]
- TrendSpider: cloud alerts and no-code bots. [R snippet]
- TradingView: server-side alerts with webhook, alert frequency options, strategy order-fill alerts with placeholders; paper trading account; broker integrations. [R alerts; rest K]
- MetaTrader 5: EAs on VPS, push/email notifications, Alert disabled in tester. [R/K]
- NinjaTrader: SIM mode, ATM strategies, order and position windows, alerts window. [K]
- AmiBroker: auto-trading via broker plugins, alerts. [K]

Peak version for Studio:

- Page layout: left list of live/paper deployments; centre: today dashboard; right: orders and alerts.
- Deployment wizard: pick strategy version -> pick mode (Signals only, Paper, Live) -> broker/account -> capital and size scale -> risk limits -> schedule/session -> alert rules -> review diff vs backtest assumptions -> typed confirmation to go live. All saved as a deployment record.
- Modes:
  - Signals only: publishes each signal (symbol, action, size, reason) to the feed, email, push, webhook; user trades manually. Shows "signal valid until" and a one-click "I took it / skipped it" for tracking real vs signal P&L.
  - Paper: same engine, simulated fills using live quotes and the same execution model; records slippage observed vs model.
  - Live: broker execution with order-by-order confirmation toggle (manual approve for first N trades), then auto.
- Broker layer: adapters for IB, Alpaca, Tradier, Schwab, Tastytrade, Kraken/crypto exchanges first; connection status, permissions, account balances, buying power; read-only "dry connection" test; reconnect and disconnect events surfaced and logged (QC hook parity).
- Dashboard: positions (qty, avg, mark, P&L, % of book), open orders (cancel/modify), fills, P&L today/week/total with backtest expected band overlay ("live is inside/outside the 90% MC band"), exposure, margin, heartbeat, last data tick, next scheduled event, logs live-tail, strategy variables view (the state).
- Divergence monitor: live vs backtest on same period, shows missing/extra signals and fill slippage; threshold alerts.
- Orders tab: full lifecycle, reject reasons, manual order ticket with pre-trade checks (size limit, price band, duplicate guard).
- Kill switches: pause entries, flatten all, halt strategy, halt account; also automatic triggers (max daily loss, max DD, data stale, broker mismatch) with confirmation levels.
- Alerts: rule builder, channels (email, push, SMS, Slack, Discord, Telegram, webhook with JSON template placeholders), severities, quiet hours, escalation (if unacked in 10 min -> SMS), test button, alert history with ack. Events: signal fired, order placed/filled/rejected, risk limit hit, drawdown level, data lag, broker disconnect, heartbeat lost, strategy error, divergence beyond threshold.
- State and recovery: persisted strategy state, restart with position reconciliation, mismatch pauses and asks.
- Change control: deploy a new version with diff view; apply at next safe point; keep previous version one-click rollback; audit log for every action.
- Customisation: default risk limits per account, default alert rules template, channel routing per severity, dashboard widget layout, timezone, sound.

## H. Chart (charting, indicators, drawings, replay)

Competitors:

- TradingView: market-leading charts: 100+ built-in indicators, Pine scripts, drawing tools (trend lines, Fibonacci, patterns, measure), multi-chart layouts, replay mode, templates, alerts from drawings, compare symbols, multiple timeframes, extended hours, Renko/Heikin-Ashi/Point & Figure etc. [K; Pine pages R for overlays/labels/tables/Data Window]
- TrendSpider: automated trendlines, multi-timeframe overlay, 200+ indicators, Raindrop charts, automated pattern recognition, backtest on chart. [R snippets]
- Koyfin: charts with fundamentals overlays, comparison, templates, dashboards, screener. [K]
- NinjaTrader: charts with SuperDOM, drawing tools, templates, market replay. [K]
- MetaTrader 5: chart with objects, templates, tester visual mode. [K, R tester]
- AmiBroker: very fast charts, multiple panes, AFL-drawn charts. [K]
- QuantConnect: result charts and custom series, not a trading chart. [R]
- Option Alpha / Composer: minimal charts. [K]

Peak version for Studio:

- One chart engine used everywhere (Backtest, Live, Library, Build previews). Canvas/WebGL, 1M bars smooth, decimation for zoomed-out views.
- Chart types: candles, hollow, OHLC bars, Heikin-Ashi, line, area, baseline, Renko, range, Kagi, Point & Figure, volume footprint (when data), step. Scales: linear, log, percent, indexed to 100.
- Multi-pane layout with drag-resize; multi-chart grids (1, 2, 4, 6, 9) with synced crosshair, symbol, timeframe, or none (user toggles each sync).
- Indicators: from the Library registry, add via search (`/`), overlays and panes, params popup with Inputs, Style, Visibility tabs (the Pine pattern), templates, favourites, "apply to selected pane", indicators on indicators, save templates.
- Strategy overlay: run a strategy on the chart and show entries/exits, stop/target lines, position size ribbon, equity in a pane; click a marker for trade card (why it fired, with variable values).
- Drawings: trend line, ray, horizontal/vertical, channel, Fibonacci (retracement, extension, fan), pitchfork, rectangle, ellipse, text/note, arrow, measure tool, price range, date range, long/short position tool (risk/reward), anchored VWAP; style per tool; magnet to OHLC; lock, hide, group, clone, per-timeframe visibility; sync drawings across charts of the same symbol. Drawings can be converted into alerts and into block conditions ("price crosses line").
- Replay: bar-by-bar play with speed 1x to 50x, step forward/back, jump to date, random start date ("blind replay" hides future and ticker name for discretionary practice), simulated orders and P&L, multi-timeframe consistent replay, replay a strategy live-stepped with the debugger.
- Data window and crosshair readout for all series; hover tooltips; legend with values; screenshot and share (PNG with watermark off); export data in view.
- Compare and spread: add symbols as overlay with percent scale; ratio charts (A/B); correlation panel.
- Events layer: earnings, dividends, splits, economic releases, news markers (when data available); strategy trades layer; regime shading layer.
- Alerts from chart: right-click price -> "Alert when crosses"; alert on indicator conditions; alert on drawing touch (TradingView pattern).
- Automated analysis (TrendSpider pattern, optional and labelled clearly as heuristics): auto trendlines, support/resistance zones, pattern detection with confidence; toggle layers; each is reproducible code and can be turned into a block.
- Customisation: colours for candles/background/grid per theme, font size, crosshair style, timezone and session (RTH/ETH), price scale position, saved layouts and templates (per symbol or global), keyboard shortcuts for every tool, hotkey "Alt+T" style quick-draw.
- Performance targets: pan/zoom 60 fps with 5 indicators on 100k bars; first paint under 1 s.

## I. Library (universes, cost profiles, indicators, imports, agents)

Competitors:

- QuantConnect: universe selection (coarse/fine, ETF constituents, scheduled, option chains, futures), datasets marketplace, object store, libraries as projects, Alpha Streams. [K; reality models R]
- Portfolio123: universes and "rules" libraries, ranking systems library, factor and formula library, fundamentals database with point-in-time. [R snippets]
- TradingView: indicator/script library, community scripts, watchlists, screener with saved screens. [K]
- StrategyQuant X: databanks, symbol/data manager, building-block sets, templates for money management and exits. [K]
- WealthLab: data sets, building block library, extensions marketplace. [R snippets]
- AmiBroker: watchlists, formula library, databases. [K]
- Koyfin: screens, custom dashboards, saved templates. [K]
- Composer: public symphonies as reusable components. [K]
- Option Alpha: bot templates, scanners library. [R snippets]
- Cursor: rules and agent definitions in files. [K]

Peak version for Studio:

- Library tabs: Universes, Cost profiles, Indicators, Blocks, Data and imports, Templates, Agents, Snippets. Search across all, tags, owner, version, usage count ("used by 7 strategies").
- Universes:
  - Types: static list, index constituents (point-in-time), screen-based (rules on liquidity, price, market cap, sector, fundamentals), ETF holdings, top-N by dollar volume, crypto pairs by volume, option chains rules, custom Python.
  - Each universe: preview table, count over time chart, turnover, survivorship status (delisted included yes/no), data coverage, rebalance frequency, min price and min ADV filters, ban list. Always point-in-time; badge when it is not.
  - Version and freeze: a strategy pins the universe version used in a run.
- Cost profiles: named bundles (commission schedule, slippage model, spread model, borrow rates, financing, margin, fees, taxes optional) with presets (Retail US equities, IBKR Pro, Futures CME, Crypto spot/perp, FX retail, Options per-contract). Compare profile impact on a strategy in one click. Custom Python cost model. Assigned per strategy or per asset class; stored in run record.
- Indicators: registry browser with formula, plot, reference, default params, optimisation range, warm-up, speed tag; user indicators with tests; "try on chart" button; deprecation notes.
- Imports: CSV/Parquet price data, fundamentals, trade lists (for validating an external strategy's trades via Validate), broker statements (to compare live vs expected), TradingView trade export CSV, QuantConnect Python. Import wizard with column mapping, timezone, adjustments, preview, validation errors listed per row; saved import profiles.
- Agents: reusable AI agent definitions (Cursor-like rules): name, instructions, tools allowed (read results, run backtest, propose edits), budget limits, model, schedule (e.g. "every Sunday re-validate live strategies and summarise drift"); run history with cost; never allowed live order tools.
- Templates and snippets as in Part 1 section 13.
- Sharing: library items private, team, or public; fork and track upstream changes with a "merge update" button.
- Customisation: default universe, default cost profile, default data source per asset class, pinned items, import profile defaults.

## J. Cross-page systems

- Global search and command palette (Part 1 section 16) spans all pages.
- Notification centre: run complete, validation done, optimisation finished, live alerts, shared comments; per-type channel settings.
- Activity and audit: one timeline of every run, deploy, edit, share with filters; export for compliance.
- Settings: account, data sources and keys (stored encrypted, never shown again), brokers, team roles, billing/compute quota, themes, keymaps, defaults for all pages; admin policy locks.
- Compute manager: queue view of running and waiting jobs (backtest, sweep, validation, notebook kernel), cancel, priority, cost and time estimates, quotas.
- Onboarding: sample strategy per mode, 5-minute guided path Build -> Backtest -> Validate -> Paper; tips shown once.
- Accessibility: keyboard-only flows, screen-reader labels on charts (table alternative), colour-blind palettes, reduced motion.
- Mobile read view: Home, Live dashboard, alerts, kill switch (no editing).

---

# Part 2: more things competitors do badly (add to avoid list)

- Composer: blocks look simple but hide heavy lookback and rebalance assumptions; no real validation tooling; weak control over fills and costs.
- Option Alpha: backtest entry on the minute with mid-price; docs themselves list reasons live bots differ; Studio should show live-vs-backtest divergence by default.
- StrategyQuant X and Build Alpha: huge test menus with no single verdict; the user can pick tests that pass. Studio gives one scorecard and a locked policy.
- TrendSpider and TradingView: signal patterns shown without sample-size or luck context; automated trendlines are heuristics not edges.
- Portfolio123 / WealthLab: powerful but dated, many modal dialogs and hidden settings; Studio should keep a single settings model with search.
- QuantConnect: allocation, universe, and alpha concepts spread across many framework classes; Studio should show them as simple page sections with code view on demand.
- AmiBroker / NinjaTrader / MT5: results and settings locked in desktop files; difficult to share or reproduce. Studio runs are portable bundles.

---

# Top 60 features, ranked (whole Studio)

1. Immutable, reproducible run records with one-click Reproduce.
2. Same engine and execution model across backtest, paper, live.
3. One-click Validate scorecard with editable policy (pass/warn/fail with reasons).
4. Walk-forward (anchored/rolling) plus Walk-Forward Matrix with 3D surface.
5. Trade-list Monte Carlo (reshuffle, resample, skip trades) with confidence-level table.
6. Price-path robustness: noise test, Vs Random, Vs Shifted, Vs Others, permutation.
7. Deflated Sharpe and trials counter carried from Optimise into Validate.
8. Look-ahead protection by API design, lint, and runtime guard.
9. Declarative params shared by blocks, formula, code, optimiser.
10. Optimiser with grid/random/Bayesian/genetic, constraints, multi-objective, no 3-param cap.
11. Parameter heat maps with stability (plateau) scoring and "pick plateau" tool.
12. Hidden hold-out period enforced at project or team level.
13. Execution model panel with presets and custom hooks (fees, slippage, fills, borrow, margin).
14. Intrabar fill fidelity levels with ambiguous-bar count shown.
15. Live vs backtest divergence monitor with expected-band overlay.
16. Promotion gates: backtest -> validate -> paper -> small live -> live, with editable checklists.
17. Kill switches and automatic risk triggers (daily loss, DD, stale data, broker mismatch).
18. Position reconciliation and crash recovery in live.
19. Broker adapters (IB, Alpaca, Tradier, Schwab, Tastytrade, crypto) with connection status and disconnect handling.
20. Signals-only mode with took/skipped tracking.
21. Alert rule builder with webhook templating, escalation, quiet hours, test button.
22. Four authoring modes (blocks, formula, Python, English) on one document model.
23. English-to-blocks with explicit interpretation confirmation before any run.
24. Block editor with Any/All nested conditions, live "where did this fire" chart preview.
25. Degrees-of-freedom / complexity meter while building.
26. Full Monaco language server with Studio stubs and domain diagnostics.
27. Time-travel debugger on finished backtests plus live-step debugger with logpoints.
28. Structured logs panel with click-to-bar and click-to-line.
29. Plot API with panes, markers, regions, data window, decimation (no silent quota failure).
30. Backtest report with 60+ stats, customisable tiles, range-brush recompute.
31. Trades table of 100k+ rows with MAE/MFE, tags, jump-to-chart and jump-to-code.
32. Costs tab with sensitivity slider (0x to 3x).
33. Compare 2 to 6 runs: equity, stats, params, code, execution model.
34. Warnings engine on every report (few trades, edge params, top-trade dependence, cost drag).
35. Version timeline with metrics per version, diff, branches, restore.
36. Portfolio builder with risk parity/HRP/min-variance/threshold rebalancing and constraints.
37. Portfolio analytics: marginal risk contribution, drawdown overlap, sleeve drop-out test.
38. Walk-forward allocation test (weights estimated out-of-sample).
39. Universe library, point-in-time, with survivorship badge and pinned versions.
40. Cost profile library with presets and impact comparison.
41. Data catalog with gaps, adjustments, and a per-run data quality report.
42. Multi-timeframe access with only "last completed bar" semantics.
43. Indicator registry (150+) driving autocomplete, blocks, formulas, optimiser ranges, warm-up.
44. Indicator lab with live tuning on chart, no backtest needed.
45. One chart engine for every page (WebGL, 1M bars) with multi-chart sync options.
46. Drawings that convert to alerts and block conditions.
47. Replay mode including blind replay and strategy-stepped replay.
48. Strategy overlay on chart with per-trade "why it fired" card.
49. Command palette and quick open spanning all pages and objects.
50. Fully remappable keybindings with VS Code/Vim/JetBrains presets.
51. Settings with scopes (user/project/run), search, sync, and admin locks.
52. Dockable saved layouts per task (Coding, Review, Live monitor).
53. Home table with status pipeline chips, sparkline, stale-run badge, bulk actions.
54. Notebook tab sharing data and engine, `load_run` and `optimise` helpers.
55. AI assistant with diff-approval, critic mode citing lines and numbers.
56. AI experiment agent running variants as branches under a budget.
57. Agents library with budgets, schedules, and no live-order permission.
58. Libraries with version pinning, auto docs, tested examples, and forkable templates.
59. Audit log and roles (viewer/commenter/editor/owner), comments anchored to code and bars.
60. Performance and compute manager: queue, ETA, quotas, streaming results, cancel with partial results.
