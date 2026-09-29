# QUANT360 — COMPLETE PLATFORM SPECIFICATION
## Six Core Pages. Nothing Better Exists.

---

## PAGE 1 — ALGORITHM LAB

**What institutions pay for this:** Bloomberg BQuant Enterprise charges Terminal subscription rates ($32,000/year/seat) for a Python analytics sandbox with Bloomberg data access. Their sandbox has no persistent kernel, no co-located chart panel, no variable inspector, no version-controlled file system, and no direct connection to any downstream testing environment. It is a glorified Jupyter notebook with Bloomberg API bindings. BQuant won Best AI Solution for Historical Data Analysis at the 2025 A-Team Group Awards — which means even the best institutional version of this currently available is still fundamentally a notebook environment. Yours is a full quant IDE. The gap is enormous.

**The core proposition:** A VS Code-grade integrated development environment built entirely around the quant workflow. The chart is not a separate page. The kernel is not re-initialized on every run. The file system is not a flat list of scripts. Every design decision is oriented toward one thing: maximum iteration speed from idea to tested signal.

---

### FEATURE 1.1 — Monaco Code Editor

**What it is:** A full VS Code-grade code editor (Monaco engine) embedded in the browser, purpose-built for quant research workflows. Supports Python with real-time autocomplete that indexes the platform's own function library — every utility, every data accessor, every Labs module output becomes autocomplete-aware. Includes a lookahead-bias linter that fires automatically without being asked — named as Backtrader's specific weakness (runs biased strategies silently) and QuantConnect's strength (guardrails built in). Flags common quant-specific errors before execution: lookahead bias (using future data, crossing time-series with date-shifted data without forward-fill), hardcoded parameters that should be configurable, and non-deterministic operations in signal logic. The linter runs on every keystroke, not on demand. Debugger intentionally omitted — real telemetry across 68 developers and 11,805 tracked sessions found breakpoint debugger usage at 0.2-1.4% of active coding time, with developers overwhelmingly relying on live state inspection instead.

**How it works:** Monaco runs entirely in the browser via JavaScript. The platform registers its full API surface (all factor functions, data accessors, Labs modules) as an autocomplete provider via the Monaco `CompletionItemProvider` API. On every keystroke, the provider filters the registered symbol list against the current token and returns ranked suggestions. The lookahead-bias linter runs as a custom Monaco `CodeActionProvider` — it scans the AST for patterns like `shift(-1)` on price data without forward-fill handling, inline date ranges that don't match the backtest config, and variables named with future date references. Syntax highlighting and linting run through Monaco's built-in Pyright/ruff integration.

**INPUTS**

| Parameter | Options |
|---|---|
| Language mode | Python |
| Autocomplete source | Platform function library, all Labs module outputs, data accessors |
| Linting | Pyright / ruff (real-time) + lookahead-bias linter |
| Debugging | Intentionally omitted — replaced by Variable Inspector state inspection |

**OUTPUTS**

| Output | Description |
|---|---|
| Real-time syntax highlighting | Full Python highlighting with error detection before execution |
| Autocomplete suggestions | Context-aware suggestions including platform-specific functions |
| Lint diagnostics | Error and warning markers inline + lookahead-bias warnings |
| Debugger state | Not provided — use Variable Inspector for live state inspection |

### FEATURE 1.2 — Persistent Python Kernel with Reactive Dependency Tracking

**What it is:** A long-running Python kernel that maintains state between code executions within a session, layered with a reactive dependency graph that prevents the classic hidden-state bug — where stale variables silently produce wrong backtest numbers. The "persistent kernel, state survives between runs" model is a trade (speed vs. correctness), and this design solves both sides: you keep iteration speed, but stale state is always visible as stale.

**How it works — Kernel:** The kernel runs as a persistent process (IPython kernel protocol or custom Jupyter kernel gateway). On session start, the kernel is initialized with the researcher's data universe. Variable state, loaded modules, and computed artifacts remain in the process memory across all `execute` calls. The kernel communicates with the frontend via ZMQ/Jupyter WebSocket protocol. Session lifecycle is independent of page navigation. Session timeout (configurable, default 4h) garbage-collects idle kernels. The kernel-side cache uses an LRU eviction policy keyed by (asset_universe_hash, computation_type, parameter_hash).

**How it works — Reactive Dependency Graph:** A dataflow tracker records which cell/file defines which variable and which cells/files read it. After every execution, the tracker updates the dependency graph. When a researcher edits or re-runs an upstream cell, all downstream cells that depend on the modified variables are automatically marked stale in the Variable Inspector panel. The researcher can configure the behavior: (a) manual — stale cells are grayed out with a "stale" badge, the researcher decides when to re-run, (b) automatic — downstream cells re-execute in topological order on edit, or (c) confirm — prompt before re-execution. Dependency edges are color-coded in the editor margin. Defining the same variable name in two cells is a hard error — not a silent race condition. This directly implements the Marimo/ipyflow proven pattern: cell dependencies inferred and visible before any execution, so a fresh kernel session reproduces the exact intended output.

**INPUTS**

| Parameter | Options |
|---|---|
| Session lifetime | Full session duration (persistent across runs) |
| Data loaded | OHLCV, covariance matrices, fitted models — loaded once, cached in memory |
| Cache scope | Per-session, persists across code executions |
| Session timeout | Configurable (default 4h) |
| Cache eviction | LRU keyed by (universe_hash, computation_type, param_hash) |
| Dependency resolution | Manual / Automatic / Confirm |
| Duplicate variable detection | Hard error |

**OUTPUTS**

| Output | Description |
|---|---|
| In-memory state | Previously computed variables, loaded data, fitted models accessible instantly |
| Iteration speed | Near-zero reload time between runs within a session |
| Dependency graph | Edges color-coded in editor margin |
| Stale markers | Grayed-out cells with "stale" badge when upstream dependencies change |

### FEATURE 1.3 — Terminal Panel

**What it is:** A full bash terminal co-located with the code editor in a split-pane layout. The terminal and Python kernel share the same process — a variable defined in the terminal (`x = pd.DataFrame(...)`) is immediately visible in the editor and vice versa. Supports pip install, file operations, data downloads, and real-time log streaming from long-running computations.

**How it works:** The terminal runs via xterm.js in the browser, connected to the kernel's process via a PTY (pseudoterminal) multiplexer. The kernel's stdin/stdout/stderr are shared between the terminal and editor execution contexts. The PTY multiplexer runs as a sidecar process (or Docker sidecar) that creates a new bash process on session start, attaches it to the kernel's Python process so they share the same memory space and Python interpreter. Shell commands run as subprocesses of this bash. Kernel variable sharing works because both the terminal's Python REPL and the editor's execution context use the same `__main__` module namespace.

**INPUTS**

| Parameter | Options |
|---|---|
| Shell type | Full bash terminal |
| Kernel sharing | Shared kernel state with editor |
| Commands | Any system command, pip install, file operations |

**OUTPUTS**

| Output | Description |
|---|---|
| Terminal output | Real-time stdout/stderr from commands and long-running computations |
| Shared variables | Variables defined in terminal immediately accessible in editor |

### FEATURE 1.4 — Live Chart Panel

**What it is:** A co-located chart panel that renders immediately when strategy code executes — no navigation to a separate page, no new tab. Displays OHLCV candlesticks with buy/sell signal overlays as colored markers directly on the price series. Supports secondary panels for custom indicator series, rolling metrics, and factor scores. Ghost overlay mode dims prior runs so the researcher can visually compare two parameter configurations side by side.

**How it works:** The chart panel uses a JavaScript charting library (Lightweight Charts or ECharts) rendered in an iframe or Shadow DOM within the editor split-pane. The kernel sends structured chart data (OHLCV arrays, signal arrays, custom series) via the Jupyter comm protocol or a dedicated WebSocket channel. Each render call creates a new layer. Ghost overlays are implemented by rendering prior runs with reduced opacity (`opacity: 0.3`) on the same time axis. Crosshair synchronization across subpanels is handled by a shared mousemove event handler that maps the cursor position to the same time index across all chart instances. Multi-ticker synchronized time axes share a single x-axis range controller — zoom/drag on any chart broadcasts the new range to all sibling charts.

**INPUTS**

| Parameter | Options |
|---|---|
| Chart type | OHLCV candlestick, custom series |
| Overlay signals | Buy/sell markers from strategy output |
| Multiple tickers | Basket strategies with synchronized time axes |
| Ghost overlay | Prior runs displayed as dimmed overlays for visual comparison |

**OUTPUTS**

| Output | Description |
|---|---|
| Main price chart | Interactive candlestick with signal overlays |
| Secondary panels | Custom indicator series, rolling metrics, factor scores |
| Crosshair | Synchronized across all subpanels |
| Zoom/pan | Scroll to zoom, drag to pan |

### FEATURE 1.5 — Variable Inspector Panel with Dependency Staleness Indicators

**What it is:** A persistent sidebar that displays all live variables in the kernel — name, type, shape (for arrays and DataFrames), memory footprint, and a one-row data preview. Each variable is annotated with a staleness indicator from the reactive dependency graph: green (fresh, all upstream definitions are current), yellow (depends on an edited cell — data may be stale), red (stale — upstream definition has changed since this variable was computed). Click any DataFrame to open it in a full interactive table viewer. Click any array to plot its histogram. Eliminates the `print()` debugging loop by showing the entire computation state with its freshness at a glance.

**How it works:** After every kernel execution, a kernel-side middleware (registered via `post_execute` hook) serializes the namespace: it iterates `globals()`, filters for public names, classifies each variable by type, and sends a structured JSON payload to the frontend via the comm channel. The dependency graph (Feature 1.2) provides the staleness status for each variable. For DataFrames, it sends `.dtypes`, `.shape`, `.memory_usage(deep=True)`, and `head(1)`. For arrays, it sends `.shape`, `.dtype`, `.nbytes`, and computed statistics. The frontend renders this as a tree/list in a sidebar panel with colored staleness badges. Clicking a DataFrame triggers a separate request that streams the full data in paginated chunks (1,000 rows at a time).

**INPUTS**

| Parameter | Options |
|---|---|
| Kernel variables | All live variables in the Python kernel |
| Data type detection | DataFrames, arrays, scalars, custom objects |
| Staleness source | Reactive dependency graph (Feature 1.2) |

**OUTPUTS**

| Output | Description |
|---|---|
| Variable sidebar | Name, type, shape, memory footprint, preview row, staleness badge |
| Interactive table viewer | Sortable, filterable, searchable DataFrame view |
| Array histogram | Distribution plot with descriptive statistics |

### FEATURE 1.6 — File System and Version Control

**What it is:** A project file tree in the left sidebar organized by convention: `strategies/` (`.py` files), `data/` (config files), `factors/` (factor libraries), `results/` (backtest output archives), `exports/` (generated reports). Every file save creates a versioned snapshot — the platform stores the complete history. View any prior version, diff two versions side by side (code diff and performance diff simultaneously if both were backtested), and roll back to any point.

**How it works:** The file system is a server-side directory structure. The frontend uses a virtual filesystem abstraction (similar to VS Code's FileSystemProvider) that communicates with the backend via REST/WebSocket. On save, the backend stores a copy of the file content in a content-addressable store keyed by `(file_path, content_hash)`, appends a record to a version manifest (JSON lines file), and updates the user's working copy. The diff view uses a LCS-based diff algorithm (Myers) on the server side for code diff. For performance diff, the backend queries the Model Lineage database for the two runs' metric snapshots and returns a side-by-side JSON comparison. Rollback copies the versioned content back to the working file path and broadcasts a file-change event to the editor.

**INPUTS**

| Parameter | Options |
|---|---|
| File organization | Strategies, data config, factor libraries, results, exports — each in subdirectories |
| Version trigger | Every file save creates a versioned snapshot |

**OUTPUTS**

| Output | Description |
|---|---|
| Project file tree | Full directory browser in left sidebar |
| Version history | Snapshot of every file at every save |
| Side-by-side diff | Code diff and performance diff simultaneously |
| Rollback | Restore any prior version |

### FEATURE 1.7 — Run History Panel

**What it is:** A collapsible panel that automatically logs every code execution in the session. Each entry records: timestamp, duration, printed metrics (Sharpe, IC), pass/fail status, and a link to the chart state at that run. Click any prior run to restore the kernel to that exact state — variables, charts, and all. Functions as an undo system for quant research.

**How it works:** On every execution, a kernel-side hook captures: wall-clock start/end time (via `time.monotonic()`), stdout/stderr text, and any exception traceback. The frontend captures a chart state snapshot (the current series data and viewport). Both are sent to a session history service that stores them in a SQLite DB keyed by `(session_id, run_sequence_number)`. For kernel state restoration, the backend maintains checkpoint files — after each run, it serializes the kernel namespace to a pickle/cloudpickle file keyed to the run ID. Clicking a prior run: the current kernel is terminated, a new kernel is spawned, and the checkpoint file is loaded into it. The chart state is restored from the saved snapshot without re-rendering from data.

**INPUTS**

| Parameter | Options |
|---|---|
| Execution events | Every code run is automatically logged |
| Restoration trigger | Click any prior run to restore kernel state |

**OUTPUTS**

| Output | Description |
|---|---|
| Run history log | Timestamp, duration, metrics, pass/fail, chart state link |
| Kernel state restoration | Full variable and chart state restored from any prior run |

### FEATURE 1.8 — One-Click Push to Backtest Studio (and Future Factor Sandbox)

**What it is:** A single-button transfer from the Algorithm Lab editor to Backtest Studio. The strategy file and all currently active parameters (universe, cost model, benchmark, parameter values) are serialized and sent to Backtest Studio in one click. The strategy arrives pre-configured — no re-entry of anything. *(Future)* Push a factor expression directly from the editor to Factor Sandbox for IC, decay, crowding, and orthogonalization analysis.

**How it works:** The push button triggers the frontend to collect: (1) the current file path and content hash, (2) the kernel's active parameter values (extracted from the namespace or a config dict), (3) the current universe identifier, cost model settings, and benchmark ticker from session state. These are packaged as a JSON payload and sent to the Backtest Studio API via POST. Backtest Studio creates a new run configuration record, stores the strategy file path reference, and pre-fills its configuration panel with the transferred parameters. The user lands in Backtest Studio with everything ready — one click to start the backtest. The Factor Sandbox push (future) will use the same mechanism but route to the Sandbox's expression evaluation endpoint.

**INPUTS**

| Parameter | Options |
|---|---|
| Target environment | Backtest Studio (live) / Factor Sandbox (future) |
| Parameters transferred | Universe, cost model, benchmark, parameter values |

**OUTPUTS**

| Output | Description |
|---|---|
| Pre-configured strategy | Strategy arrives in target environment with all parameters intact |
| Pipeline | Single click from code to tearsheet |

### FEATURE 1.9 — Forward Paper-Trading Mode with Backtest-to-Live Code Parity

**What it is:** The single highest-demand feature in algorithmic trading infrastructure — strategy code written in Algorithm Lab runs **unmodified** against a live/delayed data feed the same way it runs in Backtest Studio. No rewrite, no translation layer, no "live version" of the strategy. The code path for signal generation is identical between backtest and live execution. This solves the #1 documented gap across every real tool comparison: "your backtesting strategy works perfectly, but going live means starting over, because VectorBT, backtesting.py, backtrader, and Zipline aren't designed for real-time execution, so you end up rewriting everything from scratch." QuantConnect's actual named advantage over every rival is exactly this — backtests use the same code paths as live trading.

After backtesting and before real capital deployment, the platform runs the identical strategy code on live delayed-feed data (yfinance 15-min-delayed quotes). Generates real signals daily, logs them against what actually happened, with zero capital at risk. This directly targets the documented failure mode where strategies that look strong in backtest collapse in live conditions (Grid Trading: +20.68% backtest → −28.22% live; LSTM: best backtest returns on two markets, negative live returns on both).

**How it works:** The strategy file pushed from Algorithm Lab contains only pure signal logic — no data-loading code, no execution code, no calendar logic. The same `generate_signals(data) → signals` function is called by both the Backtest Studio event-driven engine and the Paper Trading daily cron. The cron job: (1) pulls the latest 15-min-delayed OHLCV for the strategy's universe, (2) calls `generate_signals()` on it, (3) logs generated signals with timestamps, (4) at the next pull, records actual vs predicted. Results accumulate in a paper-trading equity curve in the Model Lineage system. After N trading days (default 20), the platform computes a "forward reliability score": rank correlation between predicted and actual daily returns. Score < 0.3 means the strategy is not surviving live contact.

**INPUTS**

| Parameter | Options |
|---|---|
| Strategy source | Algorithm Lab — code runs unmodified |
| Data feed | yfinance 15-min-delayed OHLCV |
| Schedule | Daily cron (market close) |
| Burn-in days | Default 20, user-configurable |
| Universe | Inherited from strategy config |

**OUTPUTS**

| Output | Description |
|---|---|
| Paper-trading equity curve | Cumulative return from live-forward signals |
| Signal log | Generated signals with timestamps and actual outcomes |
| Forward reliability score | Rank correlation between predicted and actual daily returns |
| Predicted-vs-actual chart | Side-by-side comparison of backtest projection vs forward reality |
| Code parity guarantee | Same `generate_signals()` function used in both backtest and live |
---

## PAGE 2 — BACKTEST STUDIO + MODEL LINEAGE

**What institutions pay for this:** Bloomberg PORT costs $6,000 per seat per year for performance attribution and backtesting. FactSet's backtesting module is included in their $12,000–$20,000/year subscription and produces static PDF tearsheets with no drill-down capability. StatPro and Advent Geneva charge $50,000–$200,000/year for GIPS-compliant attribution workflows. None of them have model lineage. None of them show DSR. None of them show PBO. None of them run Monte Carlo as an integrated layer. None of them store a version-controlled history of every backtest run ever executed with full parameter traceability. Axioma Portfolio Analytics charges separately from the optimizer for attribution and produces reports that cannot be drilled into interactively. The combined institutional alternative to what this page does costs well over $250,000/year per institutional seat across multiple vendors.

**The core proposition:** The honest backtesting environment plus the complete research system of record. Every backtest run that has ever executed on this platform is stored, tagged, searchable, and connected to every other run through a visual lineage graph. The tearsheet is not a PDF. Every chart is interactive, every period is drillable, every trade is inspectable. And the honest performance card — DSR, PBO, PSR — sits at the top of every result, not buried in an appendix.

---

### FEATURE 2.1 — Run Configuration Panel

**What it is:** A left sidebar panel that loads any strategy from Algorithm Lab or the Model Lineage archive and exposes all backtest configuration parameters. Universe is pulled from Universe and Data Studio with point-in-time correctness auto-applied. Date range uses calendar pickers. Benchmark options: SPY, URTH, equal-weight universe, or custom upload. Rebalancing: daily/weekly/monthly/quarterly/custom trigger. Position sizing: equal-weight, volatility-scaled, Kelly fraction, or custom Python function. Transaction cost model: Almgren-Chriss square-root market impact (DEFAULT — honest, estimated from ADV and volatility; backtests using default models typically underestimate real costs by 50-100%), flat bps (0-50 in 0.5 increments), or zero cost (comparison only, labeled "unrealistic — underestimates real costs by 50-100%"). Survivorship bias is on by default — toggling it off shows the inflation bias.

**How it works:** The panel is a form component that loads the strategy's default parameters from the strategy file's config section (a Python dict or YAML frontmatter). Each parameter field is bound to a validation function. Universe selection queries the Universe & Data Studio API for available universe definitions and returns a universe ID that carries the point-in-time data configuration. The Almgren-Chriss model requires per-stock ADV and volatility estimates: the platform computes these from the 63-day rolling average of daily dollar volume and 21-day rolling realized volatility. The survivorship bias toggle controls a boolean flag in the simulation engine that determines whether the data loader uses today's constituent list (bias-on) or the point-in-time constituent list (bias-off).

**INPUTS**

| Parameter | Options |
|---|---|
| Strategy source | Algorithm Lab / Model Lineage archive |
| Universe | From Universe and Data Studio, point-in-time correct |
| Date range | Calendar pickers for start and end |
| Benchmark | SPY / URTH / equal-weight universe / custom upload |
| Rebalancing frequency | Daily / weekly / monthly / quarterly / custom trigger |
| Position sizing | Equal-weight / volatility-scaled / Kelly fraction / custom Python function |
| Transaction cost model | **Almgren-Chriss square-root market impact (DEFAULT)** / flat bps (0-50, 0.5 increments) / zero cost (comparison only, labeled unrealistic) |
| Survivorship bias | On by default (toggle to quantify bias inflation) |

**OUTPUTS**

| Output | Description |
|---|---|
| Strategy loaded | Full parameter set, universe, execution configuration intact |
| Survivorship bias inflation | Numeric display of bias impact when toggle is off |

### FEATURE 2.2 — Event-Driven Simulation Engine

**What it is:** A sequential bar-by-bar simulation engine — not vectorized. Every bar is processed in order exactly as a live system would process it. Orders fire at the close of the signal bar and fill at the open of the next bar (zero look-ahead). Corporate actions (splits, dividends, delistings, spin-offs) are fully handled via the adjusted price series. Short-selling is constrained: hard-to-borrow stocks are flagged using historical volume and float as a proxy. Margin modeling is available for leveraged strategies. Realistic partial fills apply when position size exceeds a meaningful fraction of ADV.

**How it works:** The core loop: for each date `t` in the date range, the engine (1) loads the day's OHLCV data for the universe, (2) computes signal values from the strategy function, (3) if signals trigger on date `t-1` close, generates orders with direction and size, (4) fills orders at date `t` open price with partial-fill logic (`fill_ratio = min(1.0, max_fill_pct / (trade_size / ADV_t))` where `max_fill_pct` defaults to 20%), (5) applies corporate action adjustments to position records (splits multiply shares and divide cost basis, dividends add cash), (6) computes portfolio NAV, records positions and trades to the event log. The engine runs in a single Python process using NumPy arrays for price data. For universes above 500 tickers, the universe is chunked and processed in parallel using multiprocessing `Pool`.

**INPUTS**

| Parameter | Options |
|---|---|
| Simulation type | Event-driven (sequential bar processing) |
| Order timing | Signal fires at close, filled at next open |
| Corporate actions | Splits, dividends, delistings, spin-offs applied via adjusted prices |
| Short-selling | Hard-to-borrow flagged via historical volume/float |
| Margin modeling | Available for leveraged strategies |
| Fill model | Partial fills for positions sized as fraction of ADV |

**OUTPUTS**

| Output | Description |
|---|---|
| Trade log | Every executed order with fill prices and timestamps |
| Portfolio state | Positions, cash, margin at each bar |

### FEATURE 2.3 — Monte Carlo Engine (Shared)

**What it is:** Backtest Studio consumes a single, shared Monte Carlo engine — not a third independent implementation. The engine is callable from Backtest Studio, Robustness Lab, and Optimizer with the same three modes: (1) Block Bootstrap of Returns, (2) Random Trade Timing Perturbation, (3) Synthetic Path Generation via GARCH. Total: **15,000 simulated paths** per full run. Monte Carlo paths are the lightest per-unit computation — resampling and evaluating a return series is far cheaper than re-running an event-driven simulation.

**How it works — Mode 1 (Block Bootstrap):** The realized daily return series is resampled using the Politis-Romano Stationary Bootstrap. Block length is auto-selected as `argmin` of the MSE of the spectral density estimator (Politis-White corrected). 5,000 paths are generated by drawing blocks of random length (geometric distribution with mean = block_length) from the original series. Each path produces a full equity curve, Sharpe, max drawdown, and Sortino. Output: a histogram of Sharpe ratios with the actual backtest Sharpe as a vertical dashed line.

**How it works — Mode 2 (Timing Perturbation):** Every entry and exit date in the realized trade log is shifted by a random integer drawn uniformly from {−k, ..., +k} for k ∈ {1, 3, 5} trading days. Exit shifted by the same amount to preserve holding period. 1,000 simulations per shift magnitude.

**How it works — Mode 3 (GARCH Synthesis):** A GARCH(1,1) model is fit to the realized return series via MLE (Bollerslev 1986). 5,000 synthetic return paths are generated from the fitted process. Output: median, 10th, and 90th percentile equity curves overlaid on the actual equity curve. The gap between actual and median is the luck premium.

**INPUTS**

| Parameter | Mode | Options |
|---|---|---|
| Bootstrap replications | Block Bootstrap | 5,000 paths |
| Block length | Block Bootstrap | Auto-selected via Politis-Romano |
| Timing shift range | Timing Perturbation | ±1 / ±3 / ±5 trading days |
| Perturbation simulations | Timing Perturbation | 1,000 per shift magnitude (3,000 total) |
| GARCH model | GARCH Synthesis | GARCH(1,1) fit via MLE |
| Synthetic paths | GARCH Synthesis | 5,000 |
| **Total paths** | **All modes** | **15,000** |

**OUTPUTS**

| Output | Description |
|---|---|
| Sharpe distribution histogram | Actual backtest Sharpe marked as vertical dashed line |
| Timing sensitivity chart | Overlaid histograms per shift magnitude |
| Synthetic equity curves | Median, 10th, 90th percentile overlaid on actual equity curve |
| Luck premium | Gap between actual equity curve and Monte Carlo median |

### FEATURE 2.4 — Honest Performance Card

**What it is:** Seven numbers displayed at the top of every result in large typeface, above the equity curve. Row 1 (overfitting verdicts): Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO), Probabilistic Sharpe Ratio (PSR). Row 2 (performance metrics): Raw Sharpe, Sortino, Calmar, Maximum Drawdown. Color-coded: all three overfitting metrics green = credible, any red = scrutiny required. Performance metrics sit below overfitting diagnostics because a Sharpe of 2.1 with DSR of 0.1 is worthless.

**How it works — DSR:** DSR = Φ[(SR_CPCV - SR₀) × √(T-1) / √(1 - γ₃ × SR_CPCV + (γ₄-1)/4 × SR_CPCV²)] where SR₀ is the expected maximum Sharpe under IID noise across M trials: SR₀ ≈ √(Var[SR]) × ((1-γ)Φ⁻¹(1-1/M) + γΦ⁻¹(1-1/(Me))). The trial count M is pulled from the Optimizer's session trial registry. When no optimizer trial registry exists (standalone backtest run with no prior search), M defaults to 1 — no multiple testing correction is applied because no search was performed, and DSR reduces to PSR. As M grows, SR₀ grows, and DSR shrinks — a researcher who tried 500 parameter combinations needs a much higher raw Sharpe to achieve the same DSR as one who tried 10.

**How it works — PBO:** PBO = fraction of CPCV backtest paths whose OOS Sharpe falls below the median path Sharpe. PBO = 50% means chance-level performance. PBO = 5% means strong evidence of genuine alpha.

**How it works — PSR:** PSR = Z[ (SR_hat × √(T-1)) / √(1 - γ₃ × SR_hat + (γ₄-1)/4 × SR_hat²) ] where γ₃ is skewness and γ₄ is excess kurtosis of the return distribution. Accounts for non-normal return distributions that inflate standard Sharpe confidence intervals.

**INPUTS**

| Parameter | Options |
|---|---|
| Trial count M | Pulled automatically from Optimizer session trial registry |
| Return series | From backtest execution |
| CPCV path distribution | From Monte Carlo / CPCV engine |
| Skewness γ₃ | Computed from return series |
| Excess kurtosis γ₄ | Computed from return series |

**OUTPUTS**

| Output | Description |
|---|---|
| DSR (Deflated Sharpe Ratio) | Corrected for multiple testing across M trials |
| PBO (Probability of Backtest Overfitting) | Fraction of CPCV paths below median |
| PSR (Probabilistic Sharpe Ratio) | Accounts for fat tails and skewness |
| Raw Sharpe | Standard Sharpe ratio |
| Sortino | Downside deviation-adjusted return |
| Calmar | CAGR / max drawdown |
| Maximum Drawdown | Largest peak-to-trough decline |

### FEATURE 2.5 — Interactive Tearsheet

**What it is:** A multi-panel live tearsheet where every panel is interactive and every period is drillable. No static PDFs. Eight coordinated panels: (1) equity curve with benchmark and crisis annotations, (2) rolling 12-month Sharpe aligned on the same axis, (3) monthly return heatmap, (4) drawdown analysis table, (5) trade-level scatter plot, (6) rolling 252-day FF5 factor loadings, (7) up-capture and down-capture ratios, (8) regime-conditional P&L breakdown.

**How it works — Equity curve panel:** Cumulative portfolio return vs benchmark plotted as two line series. High-volatility crisis periods (trailing 63-day VIX > 30, computed from Category 7 macro data) rendered as shaded vertical bands. The user can toggle bands on/off.

**How it works — Monthly return heatmap:** A 12-column (months) × N-row (years) grid. Each cell computes the net return for that month from the daily portfolio return series. Color scale: red (negative) → white (zero) → green (positive), scaled to ±2× the standard deviation of monthly returns.

**How it works — Drawdown panel:** The engine scans the cumulative return series for local maxima, then for each subsequent trough, computes depth = (peak - trough) / peak, duration = trading days from peak to recovery (or current date if unrecovered). Results stored in a sorted table. Clicking a row sends a zoom command to the equity curve chart to focus on that period and filters the trade log to trades executed during that window.

**How it works — FF5 stacked area:** At each date, regress the trailing 252-day portfolio excess returns on the FF5 factor returns via OLS. The coefficients (β_MKT, β_SMB, β_HML, β_RMW, β_CMA) are the rolling factor loadings. These are plotted as a stacked area chart where the area height at each date sums to the total systematic risk contribution. The rolling window is 252 trading days, stepped daily.

**How it works — Regime breakdown panel:** The engine classifies every trading day in the backtest period into regimes using two independent dimensions: (1) **volatility regime** — trailing 63-day realized volatility terciles (low/medium/high), (2) **trend regime** — 252-day market slope (±15% = bull/bear, between = flat). Each day gets a compound regime label (e.g. "high-vol bear"). For each regime with ≥20 trading days, the panel computes: total P&L contribution (as % of total strategy P&L), annualized Sharpe within that regime, hit rate (fraction of positive days), average trade return, and number of trades. Results render as a sortable table with a horizontal bar chart showing "P&L % of total" per regime. A strategy that generated 85% of its P&L in a single regime type is flagged with a warning: "Portfolio is a leveraged bet on [regime] — verify strategy works across all conditions." The table is collapsible to one dimension at a time (volatility only or trend only).

**INPUTS**

| Parameter | Options |
|---|---|
| Portfolio return series | From backtest execution |
| Benchmark | SPY / URTH / custom |
| FF5 factor loadings | Market beta, SMB, HML, RMW, CMA (rolling 252-day OLS) |
| Daily market return | SPY or benchmark total return for trend regime classification |

**OUTPUTS**

| Output | Description |
|---|---|
| Equity curve with benchmark | Annotated with high-volatility crisis bands (VIX > 30) |
| Rolling 12-month Sharpe | Aligned on same time axis as equity curve |
| Monthly return heatmap | Year × month grid, color-coded |
| Drawdown table | Start, trough, recovery, depth, duration — sorted by depth |
| Trade scatter plot | Entry date vs return, colored by holding period |
| FF5 stacked area chart | Rolling factor loadings over time |
| Up/down capture panel | Rolling 12-month capture ratios |
| **Regime P&L breakdown table** | P&L %, Sharpe, hit rate, avg trade, trade count per regime — with concentration warning for single-regime dependency |

### FEATURE 2.6 — Model Lineage System

**What it is:** A permanent, searchable record of every backtest run executed on the platform. Each run automatically captures: strategy file hash (detects changes even if filename is unchanged), universe definition ID, date range, benchmark, cost model, all non-default parameters, DSR, PBO, raw Sharpe, Sortino, max drawdown, and timestamp. The lineage graph is a directed acyclic graph where nodes are runs and edges connect runs sharing a parent strategy file.

**How it works — Logging:** After each backtest completes, a post-run hook collects all run metadata into a structured JSON object. The strategy file hash is computed as SHA-256 of the file content. Non-default parameter detection compares the run's parameter dict against the platform defaults for each parameter type. The record is inserted into a PostgreSQL/MongoDB collection with a composite index on `(strategy_file_hash, universe_id, date_range_start, date_range_end)`.

**How it works — Lineage graph:** The graph is computed by grouping runs by strategy file hash and ordering by timestamp within each group. Edges connect consecutive runs within the same group (lineage: Run N+1 is a child of Run N). Branches occur when a run loads a strategy from a specific prior run (the "fork" action in the UI). The graph is rendered using a DAG layout algorithm (Sugiyama or Dagre). Nodes are color-coded by tag status (Candidate/Active/Retired/Deployed).

**How it works — Diff mode:** Selecting two runs triggers: (1) code diff — the backend reads both strategy files from the version control store and computes a Myers diff, (2) parameter diff — the two parameter dicts are compared via set operations on keys, (3) performance diff — the two run records' metrics are returned side by side. All three are rendered in a three-panel layout.

**How it works — Walk-Forward Mode:** The researcher sets IS window length (12/24/36/60 months) and OOS window length (1/3/6/12 months). The engine anchors the first IS-OOS split at the earliest date in the data, runs a Bayesian search (50 trials default) on the IS period, records optimal parameters and IS Sharpe, applies frozen params to the OOS period, records OOS Sharpe, and rolls forward by one OOS window. Results grid: one row per window with IS/OOS ratio. The stitched OOS equity curve concatenates all OOS period returns.

**INPUTS**

| Parameter | Options |
|---|---|
| Runs logged | Every backtest run automatically |
| Diff selection | Any two runs |
| Search query | Any metric combination (DSR, PBO, Sharpe, etc.) |
| Walk-forward windows | IS window and OOS window (user-set) |

**OUTPUTS**

| Output | Description |
|---|---|
| Lineage graph | DAG of all runs with parent-child edges |
| Three-panel diff | Code diff, parameter diff, performance diff side by side |
| Search results | Runs matching query, sorted by DSR descending |
| Walk-forward grid | IS/OOS Sharpe per window with ratio column |
| Tags | Candidate / Active / Retired / Deployed per run |

### FEATURE 2.7 — Export

**What it is:** One-click export in four formats: PDF tearsheet, LaTeX table (performance metrics formatted for journal insertion), CSV trade log, CSV equity curve, and JSON run metadata.

**How it works — PDF:** The frontend captures the current tearsheet state (all chart panels as Canvas elements via `toDataURL()`, all tables as HTML), sends them to a server-side PDF renderer (WeasyPrint or Playwright). The renderer composes the elements into a multi-page PDF with consistent typography, page numbers, and a title page containing the run's name, date, and strategy file reference.

**How it works — LaTeX:** Seven performance metrics are formatted as a LaTeX `tabular` environment: first row is metric names, second row is numeric values, formatted to 3 decimal places for Sharpe/Sortino/Calmar and 2 decimal places for drawdown percentage. The table is wrapped in a `table` float with a `\caption` containing the run identifier. Output is a `.tex` file ready for `\input{}` into any document.

**How it works — CSV/JSON:** The backend queries the run's stored data (trade log table, daily equity curve table, run metadata record) and writes them as CSV and JSON files respectively. All files are zipped into a single download archive.

**OUTPUTS**

| Output | Description |
|---|---|
| PDF tearsheet | Complete interactive tearsheet as printable document |
| LaTeX table | Seven performance metrics formatted for journal insertion |
| Trade log CSV | All executed trades with fill data |
| Equity curve CSV | Daily portfolio and benchmark values |
| Run metadata JSON | Full parameter set for exact reproducibility |

### FEATURE 2.8 — Live-vs-Backtest Reconciliation Panel

**What it is:** A side-by-side comparison panel that shows the predicted equity curve (from the original backtest) vs. the actual forward paper-trading curve (from Paper-Trading Mode, Feature 1.9) with a running divergence score. This operationalizes the entire "backtest overfitting" concern — instead of only predicting overfitting statistically (DSR/PBO), the platform measures it empirically as it happens. No commercial platform at any price does this well.

**How it works:** The panel pulls the original backtest's projected daily returns and the paper-trading mode's realized daily returns (both stored in the Model Lineage system). It renders two overlaid equity curves in the same chart: one solid (backtest projection) and one dashed (forward reality). Below: a running divergence score computed as |actual_return − predicted_return| / predicted_volatility, rolling 20-day window. A divergence score that consistently exceeds 1.0 means the strategy is underperforming its backtest by more than one standard deviation of its predicted volatility — a quantitative flag that the strategy is not surviving live contact. The panel also computes a "reliability decay rate": the slope of the divergence score over time. A positive slope means the strategy is getting worse relative to its backtest the longer it runs forward. The panel is available for any strategy that has at least 20 paper-trading days of history.

**INPUTS**

| Parameter | Options |
|---|---|
| Backtest run ID | From Model Lineage |
| Paper-trading run ID | From Paper-Trading Mode (Feature 1.9) |
| Divergence window | Rolling 20-day default, configurable |

**OUTPUTS**

| Output | Description |
|---|---|
| Overlaid equity curves | Backtest (solid) vs forward (dashed) on same axis |
| Running divergence score | |actual − predicted| / predicted_vol, 20-day rolling |
| Reliability decay rate | Slope of divergence score over time |
| Status verdict | Green (divergence < 0.5) / Amber (0.5-1.0) / Red (> 1.0) |

---

## PAGE 3 — ROBUSTNESS LAB

**What institutions pay for this:** Nothing directly comparable exists at any price. StrategyQuant has a primitive Monte Carlo suite for retail forex traders. The AlgoXpert IS-WFA-OOS paper (March 2026) explicitly documented that parameter stability surface analysis, the most critical robustness test, is absent from every commercial quant platform. Axioma Risk charges $150,000+ per year for risk analytics that answer a different question — not "is this strategy curve-fitted" but "what is the current portfolio's risk exposure." The robustness question — is the strategy's historical performance genuine or a data-mining artifact — has no institutional vendor answer. Every serious quant fund answers it with internal tools built by their research teams. This page builds those internal tools and makes them available for the first time.

**The core proposition:** A standalone environment dedicated to the single most important question in quantitative research — is this strategy's performance real or did it get lucky? Four core tests (Parameter Stability, Entry Timing Perturbation, Transaction Cost Break-Even, and Capacity & Turnover Stress) each targeting a different failure mode of backtested strategies, plus three Extended Diagnostics (Noise Injection, Regime Decomposition, OOS Boundary Sensitivity) available on-demand. Culminates in a composite robustness score and a PDF report a researcher can hand to any risk committee or journal reviewer.

---

### FEATURE 3.1 — Strategy Input

**What it is:** Loads any strategy from Algorithm Lab or any specific run from Backtest Studio's Model Lineage archive. The full parameter set, universe definition, and execution configuration arrive intact. All robustness tests run against exactly what will be deployed — not a simplified proxy.

**How it works:** The strategy loader pulls the strategy file from the versioned file store and parses its configuration section (a Python dict or YAML block at the top of the file). For runs loaded from Model Lineage, the exact parameter set used in that run is loaded, not the current default in the strategy file. The configuration is validated against the expected schema and any missing parameters are filled from platform defaults. The universe definition is resolved via the Universe & Data Studio API to get the point-in-time constituent list for the run's date range.

**INPUTS**

| Parameter | Options |
|---|---|
| Strategy source | Algorithm Lab / Backtest Studio Model Lineage |
| Configuration | Full parameter set, universe, execution config — loaded intact |

### FEATURE 3.2 — Test 1: Parameter Stability Surface

**What it is:** The most critical robustness test. Identifies whether strategy performance is hypersensitive to exact parameter values or genuinely robust across a wide region of parameter space. The finding that kills the most strategies and is invisible on every other platform.

**How it works:** Identify all numeric parameters in the strategy (lookback windows, threshold values, holding periods, any numeric constant). For each parameter, create a grid from 50% to 150% of the optimized value in equal steps (21-point grid per parameter). Run the full backtest at every combination. Compute Sharpe at every grid point. **Default: 2-parameter max** (441 runs). 3+ parameter grids are opt-in only (9,261 runs for 3 params) — a 21× reduction in compute for the cases that matter most. Output a 2D heatmap surface per parameter pair. Stability score per parameter: fraction of grid points where Sharpe exceeds half of the maximum Sharpe.

**INPUTS**

| Parameter | Options |
|---|---|
| Parameter grid | 50% to 150% of optimized value, 21 points per parameter |
| Max parameters by default | 2 (3+ requires explicit opt-in) |
| Grid dimensions | 2-param: 441 runs. 3-param: 9,261 runs (opt-in). |
| Objective | Sharpe at each grid point |

**OUTPUTS**

| Output | Description |
|---|---|
| 2D heatmap surface | Parameter A vs B, Sharpe as color gradient (red to green) |
| Stability score per parameter | Fraction of grid with Sharpe > 50% of max |
| Fragility flag | Stable region < 20% |

### FEATURE 3.3 — Test 2: Entry Timing Perturbation

**What it is:** Tests whether the strategy's edge depends on entering at the precise moment the signal fires. Total: **4,000 simulations** (4 magnitudes × 1,000 each).

**How it works:** Take the complete realized trade log from the backtest. For each trade, shift the entry date by a random integer drawn uniformly from {−k, ..., +k} for k ∈ {1, 3, 5, 10} trading days. Shift the exit date by the same amount to preserve holding period. Recalculate costs at shifted prices. Run 1,000 simulations per shift magnitude. Compute Sharpe, Sortino, and max drawdown for each simulation. Timing sensitivity score = median Sharpe at k=5 divided by baseline Sharpe at k=0. Score above 0.80 means timing-independent. Below 0.40 means timing-critical.

**INPUTS**

| Parameter | Options |
|---|---|
| Shift magnitudes k | 1, 3, 5, 10 trading days |
| Simulations per magnitude | 1,000 (4,000 total) |
| Trade log source | Realized backtest trade log |

**OUTPUTS**

| Output | Description |
|---|---|
| Sharpe histograms | Four overlaid histograms (one per k) with baseline marked |
| Timing sensitivity score | Median Sharpe(k=5) / baseline Sharpe |

### FEATURE 3.4 — Test 3: Universe Perturbation

**What it is:** Tests whether a strategy that appears diversified is actually concentrated in a small subset of stocks driving all returns. Total: **1,500 simulations** (3 dropout levels × 500 each).

**How it works:** Draw 500 bootstrap samples per dropout fraction (10%, 20%, 30%). Each sample drops a randomly selected fraction of stocks and replaces them with sector-matched substitutes from the broader available universe. Sector matching ensures the universe's sector composition stays constant — the test isolates stock-specific concentration, not sector concentration. Run the full backtest on each perturbed universe (event-driven engine). Compute Sharpe and max drawdown per simulation. Track which stocks' removal causes the largest average Sharpe decline — the top 20 stocks are the hidden concentration points. Universe stability score = fraction of 500 simulations at 20% dropout that produce Sharpe within 0.3 of baseline. Above 70% means genuinely diversified. Below 40% means concentrated.

**INPUTS**

| Parameter | Options |
|---|---|
| Dropout fractions | 10%, 20%, 30% |
| Bootstrap samples | 500 per fraction (1,500 total) |
| Replacement | Sector-matched substitutes from broader universe |

**OUTPUTS**

| Output | Description |
|---|---|
| Sharpe distribution histograms | Three histograms (one per dropout fraction) with baseline |
| Top 20 concentration stocks | Ranked by Sharpe degradation contribution |
| Universe stability score | Fraction of simulations within 0.3 of baseline at 20% dropout |

### FEATURE 3.5 — Test 4: Price Noise Injection *(Extended Diagnostics — on-demand only)*

**What it is:** Tests whether strategies are exploiting precise price relationships that will not survive real-world data imprecision. Moved to on-demand "Extended Diagnostics" — not run automatically with Tests 1/2/3/5.

**How it works:** Inject multiplicative Gaussian noise: P_noisy(t) = P(t) × (1 + ε_t), ε_t ~ N(0, σ_noise²). Four levels: σ_noise ∈ {0.001, 0.003, 0.005, 0.010} corresponding to 0.1%, 0.3%, 0.5%, and 1.0% daily price noise. 500 simulations per level. The noise level at which the median simulated Sharpe crosses zero is the fragility threshold. Noise tolerance score: Sharpe retention at σ_noise = 0.005.

**INPUTS**

| Parameter | Options |
|---|---|
| Noise levels | 0.001, 0.003, 0.005, 0.010 (0.1% to 1.0% daily) |
| Simulations per level | 500 (2,000 total) |
| Noise distribution | Gaussian multiplicative: N(0, σ_noise²) |

**OUTPUTS**

| Output | Description |
|---|---|
| Sharpe histograms | Four overlaid with baseline marked |
| Fragility threshold | Noise level where median Sharpe crosses zero |
| Noise tolerance score | Sharpe retention at σ=0.005 |

### FEATURE 3.6 — Test 5: Transaction Cost Break-Even Analysis

**What it is:** Tests whether strategies that appear profitable at assumed costs are viable at realistic costs. A strategy with break-even below the realistic cost band for its universe cannot be deployed profitably regardless of its zero-cost Sharpe. This is the most destructive test for over-optimized strategies.

**How it works:** Run the full backtest at 20 equally spaced transaction cost levels from 0 bps to 50 bps round-trip. Plot Sharpe as a function of cost. Break-even cost: the cost level where Sharpe crosses zero, estimated precisely via linear regression. Cost robustness score: break-even cost divided by midpoint of the realistic cost band for the strategy's universe. Reference bands: 2-5 bps for large-cap liquid equities, 5-15 bps for mid-cap, 15-30 bps for small-cap.

**INPUTS**

| Parameter | Options |
|---|---|
| Cost levels | 20 equally spaced from 0 to 50 bps round-trip |
| Realistic cost bands | Large-cap: 2-5 bps, Mid-cap: 5-15 bps, Small-cap: 15-30 bps |

**OUTPUTS**

| Output | Description |
|---|---|
| Sharpe vs cost chart | Break-even point annotated with realistic cost bands |
| Cost robustness score | Break-even / midpoint of realistic cost band |

### FEATURE 3.7 — Test 6: Capacity & Turnover Stress Test (Core)

**What it is:** Answers the question your entire platform currently cannot answer: **is this strategy a toy that only works at $2M, or something that scales to $500M?** Institutional evaluators explicitly require a capacity map showing expected slippage by AUM, turnover, and liquidity bucket. This test computes the AUM level at which the average trade's market impact erodes the strategy's edge to zero — the same logic as the QuantPedia capacity methodology, which defines capacity as the breakeven AUM where turnover transaction costs exactly negate the strategy's premium.

**How it works:** The engine pulls the strategy's position sizes and the universe's ADV data (from the data layer, Feature 6.8). For each stock in the strategy's portfolio, it calibrates the Almgren-Chriss market impact coefficient λ per liquidity bucket (large-cap: λ ≈ 4×10⁻⁶, mid-cap: λ ≈ 2.4×10⁻⁵ — empirical estimates from market impact literature). For each rebalancing event in the backtest, it simulates the trade at increasing AUM levels (log-spaced from $1M to $10B, 20 points) and computes the market impact cost in bps: impact = λ × σ × (trade_size / ADV)^(3/5). The net return at each AUM level = gross return − impact cost − fixed transaction costs. The capacity ceiling is the AUM level where net return crosses zero. Output: a single "Capacity: $X million" number alongside Sharpe on every tearsheet, plus a capacity curve chart showing net alpha erosion as AUM grows.

**INPUTS**

| Parameter | Options |
|---|---|
| AUM sweep range | $1M to $10B, 20 log-spaced points |
| Impact model | Almgren-Chriss square-root: λ × σ × (trade_size / ADV)^(3/5) |
| Lambda per liquidity bucket | Large-cap: 4×10⁻⁶, Mid-cap: 2.4×10⁻⁵, Small-cap: 1.2×10⁻⁴ |
| ADV source | 63-day rolling average daily dollar volume |
| Fixed transaction costs | From strategy config (bps per trade) |

**OUTPUTS**

| Output | Description |
|---|---|
| Capacity ceiling | AUM in $ where net return crosses zero |
| Capacity curve chart | Net alpha vs AUM, log scale |
| Slippage table | Estimated slippage, net alpha, net Sharpe at $10M, $100M, $1B, $10B |
| Liquidity-bucket breakdown | Contribution to impact per market cap bucket |

### FEATURE 3.8 — Extended Diagnostics (On-Demand)

Three additional tests are available on-demand but not run in the default certification pass:

**Test 7 — Price Noise Injection:** Tests whether strategies are exploiting precise price relationships that will not survive real-world data imprecision. Inject multiplicative Gaussian noise at four levels (0.1% to 1.0% daily). Reports fragility threshold and noise tolerance score. (2,000 simulations)

**Test 8 — Regime-Conditional Performance Decomposition:** Identifies strategies that derive most of their Sharpe from a single market regime. Three-state HMM on VIX and realized vol. Reports per-regime Sharpe and regime universality score.

**Test 9 — Out-of-Sample Boundary Sensitivity:** Tests whether the apparent robustness score is an artifact of the chosen IS/OOS split boundary. Uses five split configurations: baseline, baseline ±3 months, baseline ±6 months. The baseline split is defined as the same IS/OOS boundary used in the Walk-Forward optimization (Feature 5.3) or, if no Optimizer run exists, the split that leaves the last 24 months as OOS. Each alternative split shifts the boundary date forward/backward while holding the total backtest window fixed — moving the boundary means the first N months of the original OOS period become IS, and the last N months of the original IS period become OOS. The strategy is evaluated at each boundary without re-optimizing parameters (frozen from the original run). Reports boundary sensitivity score = standard deviation of OOS Sharpe across the five splits. Low sensitivity (score < 0.3) means robustness is not an artifact of the split date; high sensitivity (score > 0.8) means apparent robustness is specific to the chosen boundary.

These are set on-demand because they add ~7,500 simulations to the certification pass and address failure modes that are typically visible from the four core tests.

**What it is:** Identifies strategies that derive all of their Sharpe from a single market regime and will fail when that regime ends. Moved to on-demand "Extended Diagnostics."

**How it works:** Classify every trading day into a regime using a 3-state Hidden Markov Model fit on VIX level and rolling 21-day realized volatility. Regime states: low-vol bull, high-vol bear, transition. Compute Sharpe, Sortino, hit rate, and average trade return separately within each regime. Compute the fraction of total backtest P&L generated in each regime. Regime universality score: Sharpe of the worst-performing regime divided by unconditional Sharpe. A strategy that generated 85% of its total P&L in the low-vol bull regime is a leveraged bet on low volatility.

**INPUTS**

| Parameter | Options |
|---|---|
| Regime model | 3-state Hidden Markov Model |
| Features | VIX level, rolling 21-day realized volatility |
| Regime states | Low-vol bull, high-vol bear, transition |

**OUTPUTS**

| Output | Description |
|---|---|
| Per-regime Sharpe bar chart | Compared to unconditional Sharpe |
| Performance heat table | Sharpe, Sortino, hit rate, avg trade return per regime |
| P&L attribution pie chart | Fraction of total profit per regime |
| Regime universality score | Worst-regime Sharpe / unconditional Sharpe |

### FEATURE 3.9 — Composite Robustness Score and Robustness Report

**What it is:** A single score from 0 to 100, computed as a weighted average of the four core test scores. Weights: Parameter Stability 30%, Timing Perturbation 20%, Cost Break-Even 25%, Capacity & Turnover 25%. Extended Diagnostics scores are reported separately and do not feed into the composite. Score 75-100: Robust (advance to Optimizer). 50-74: Marginal (return to Algorithm Lab). Below 50: Do not advance (fundamental robustness failures).

**How it works:** Each core test produces a normalized score (0.0 to 1.0). The composite = Σ(w_i × score_i). The one-click PDF report renders all core test results, Extended Diagnostics results (if run), all charts, all component scores, the composite score, the capacity ceiling, and a plain-English diagnosis for every component scoring below 60. The PDF is formatted for direct submission to a risk committee or journal reviewer.

**OUTPUTS**

| Output | Description |
|---|---|
| Composite score | 0-100 weighted average of four core tests |
| Capacity ceiling | $X million alongside score on every tearsheet |
| One-click PDF report | All test results, charts, scores, capacity, plain-English diagnosis |

---

## PAGE 4 — FACTOR SANDBOX

**What institutions pay for this:** WorldQuant's WebSim platform — the closest existing equivalent — is free to use but provides only: type an expression, get IC and a basic fitness score. No IC decay curve. No half-life computation. No crowding monitor. No orthogonalization against an existing library. No regime-conditional IC breakdown. No honest Purged K-Fold validated IC versus naive IC comparison. No interactive visualization of any kind. Axioma Risk Model Machine ($150,000+/year) allows institutions to customize their factor risk model definitions — but this is a risk model configuration tool, not a factor research sandbox. Bloomberg's BQuant allows factor construction via Python with Bloomberg data — but provides no IC infrastructure, no decay analysis, no crowding signals. The complete, honest, institutionally rigorous factor research environment described here does not exist at any price from any vendor.

**The core proposition:** A fully self-contained factor research environment. You construct a factor expression, and the platform immediately tells you: is it statistically real, how fast does the signal decay, is it independently informative versus redundant with existing factors, is it crowded, and does it work across market regimes. No module connections, no imports from elsewhere in the platform. Everything is standalone.

---

### FEATURE 4.1 — Expression Editor

**What it is:** A center-panel code editor for writing factor formulas in Python using a curated operator library. Every operator is documented with its mathematical definition, typical use case, and known data requirements in a searchable sidebar panel. The editor supports autocomplete for all operators and data fields.

**INPUTS**

| Parameter | Options |
|---|---|
| Expression language | Python with curated operator library |
| Time-series operators | ts_mean, ts_std, ts_rank, ts_delta, ts_corr, ts_zscore, ts_max, ts_min, ts_decay_linear, ts_autocorr, ts_skew, ts_kurt |
| Cross-sectional operators | cs_rank, cs_zscore, cs_winsorize, cs_demean, cs_neutralize_sector, cs_neutralize_beta, cs_quantile |
| Price-volume data | open, high, low, close, volume, dollar_volume, returns, log_returns, vwap, adjusted_close |
| Derived data | ATR, RSI, SMA, EMA, MACD, BB_upper, BB_lower, realized_vol (4 estimators) |
| Reference data | GICS sector, market cap, days since IPO |
| Ken French data | RF, MKT_RF, SMB, HML, RMW, CMA, MOM |

**OUTPUTS**

| Output | Description |
|---|---|
| Operator sidebar | Searchable documentation with math definition, use case, data requirements |

### FEATURE 4.2 — Instant IC Diagnostics Panel

**What it is:** Six numbers that populate immediately (sub-2-second latency) below the expression editor when a factor expression is run. Provides the complete statistical verdict on whether the factor has predictive power.

**How it works:** Naive IC = Spearman rank correlation between cross-sectional factor scores at date t and cross-sectional stock returns from t to t+H, averaged across all dates. Purged K-Fold IC applies Purged K-Fold CV: training observations whose label-formation window overlaps with any test observation are removed, and a 10-trading-day embargo is applied after each test fold. The gap between Naive IC and Purged IC is labeled "Look-Ahead Inflation = X IC units." IC-IR = Purged K-Fold IC / std(IC across test folds). IC t-stat = IC-IR × √(num_test_periods). p-value is two-tailed under standard normal, color-coded: green (p < 0.05), amber (0.05 ≤ p < 0.10), red (p ≥ 0.10). Half-life is pulled from the IC Decay Curve (Feature 4.3).

**INPUTS**

| Parameter | Options |
|---|---|
| Factor expression | From Expression Editor |
| Evaluation window | Full data range |
| CV method | Purged K-Fold with 10-day embargo |
| Forward horizons | Auto-computed from IC decay curve |

**OUTPUTS**

| Output | Description |
|---|---|
| Naive IC | Raw Spearman rank correlation (inflated) |
| Purged K-Fold IC | Honest IC with look-ahead correction |
| Look-Ahead Inflation | Naive IC - Purged IC, labeled in IC units |
| IC-IR | Risk-adjusted IC |
| IC t-statistic | Statistical significance test |
| p-value | Two-tailed, color-coded (green/amber/red) |
| Annualized half-life | IC decay half-life in trading days |

### FEATURE 4.3 — IC Decay Curve

**What it is:** A chart plotting IC at forward horizons 1, 5, 10, 21, 42, 63, 126, 252 trading days with 90% bootstrap confidence intervals at each horizon. Three fitted decay models overlaid: linear (IC(h) = IC₀ − λh), exponential (IC(h) = IC₀ × exp(−λh)), and hyperbolic (IC(h) = IC₀ / (1 + λh)). The best-fit model is selected by AIC and highlighted. Half-life is computed from the best-fit model and displayed as a vertical dashed line. Optimal rebalancing frequency = argmax_h[IC(h) − 2 × cost_bps / 10000] marked as a separate vertical line.

**INPUTS**

| Parameter | Options |
|---|---|
| Forward horizons | 1, 5, 10, 21, 42, 63, 126, 252 trading days |
| Decay models | Linear / Exponential / Hyperbolic |
| Model selection | AIC (best fit highlighted) |
| Cost per trade | User-set bps for optimal frequency computation |

**OUTPUTS**

| Output | Description |
|---|---|
| IC decay curve | IC vs horizon with 90% bootstrap CI |
| Best-fit model | Highlighted with AIC selection |
| Half-life | Vertical dashed line from best-fit model |
| Optimal rebalancing frequency | argmax_h[IC(h) - 2 × cost_bps / 10000] |

### FEATURE 4.4 — Cross-Sectional Distribution Panel

**What it is:** A histogram of factor scores across the full universe at the most recent evaluation date, with five descriptive statistics displayed numerically: mean, standard deviation, skewness, excess kurtosis, 1st and 99th percentile values. A QQ-plot overlay tests for normality (Jarque-Bera test with p-value). Heavy right tail or extreme kurtosis triggers an automatic winsorized IC computation alongside raw IC for comparison. The distribution from one year ago is shown as a ghost overlay — significant divergence means the factor's historical IC estimate may not reflect current behavior.

**INPUTS**

| Parameter | Options |
|---|---|
| Factor scores | Current evaluation date, full universe |
| Comparison distribution | One year ago (ghost overlay) |

**OUTPUTS**

| Output | Description |
|---|---|
| Score histogram | With QQ-plot normality test |
| Descriptive statistics | Mean, std, skewness, excess kurtosis, 1st/99th pct |
| Winsorized IC | Auto-computed alongside raw IC |
| Distribution divergence | Ghost overlay of prior-year distribution |

### FEATURE 4.5 — IC Crowding Monitor (Contemporaneous Only)

**What it is:** A dedicated panel that tracks whether the current factor is crowded, measured using factor ETF AUM growth rate. The evidence for ETF-AUM growth as a *forward-looking* predictor of factor returns is weak (ρ = −0.63 with over-prediction of Sharpe, not with future returns; some studies find no crowding effect at all in ETFs/mutual funds). This monitor is explicitly contemporaneous only — it shows what current crowding *is*, not what it predicts about future returns.

**How it works:** Factor-style mapping: momentum → MTUM AUM, value → VLUE AUM, low-vol → USMV AUM, quality → QUAL AUM, size → IJR/IWM AUM vs SPY. For custom factors, the platform correlates the factor's return series against each style ETF's return series and assigns the closest match. The crowding metric is the 13-week rolling AUM growth rate of the matched ETF, expressed as a percentile rank over its own 5-year history. Traffic-light display: red > 80th percentile, amber 50th-80th, green < 50th. Labeled: "Crowding percentile — contemporaneous snapshot. Not validated as a forward return predictor." Historical crowding level plotted as a time series alongside the IC decay curve.

**INPUTS**

| Parameter | Options |
|---|---|
| Factor expression | Any factor or custom expression |
| Factor-style mapping | Auto-correlation to MTUM/VLUE/USMV/QUAL/IJR |
| Crowding window | 13-week rolling AUM growth rate |
| Historical baseline | 5-year percentile rank |

**OUTPUTS**

| Output | Description |
|---|---|
| Crowding percentile gauge | Traffic-light display (red/amber/green) |
| Historical crowding time series | Plotted alongside IC decay curve |
| Crash probability context | Lee (2024): top decile has 1.7-1.8x crash probability |

### FEATURE 4.6 — Factor Half-Life Decay Tracking Over Vintage

**What it is:** A panel that recomputes the factor's IC decay half-life on a rolling basis (every 2 years of trailing data) and plots half-life-over-time as its own chart. This turns the Sandbox from "how good is this factor right now" into "is this factor's edge actively dying, and how fast" — a materially more valuable, forward-looking answer that costs little to build since the decay-curve machinery (Feature 4.3) already exists.

**How it works:** The panel takes the factor expression and splits the available history into overlapping 2-year windows, stepped at 6-month intervals. For each window, the IC Decay Curve (Feature 4.3) is recomputed and the half-life is extracted from the best-fit decay model. The half-life values are plotted as a time series with fit uncertainty bands. A linear regression is overlaid: a negative slope means the factor's edge is systematically degrading. The panel also shows the half-life at the earliest window vs. the latest window as two labeled points. The finding this enables: factor half-lives are empirically shrinking across the industry — roughly 60 months for 2005-2010 vintage factors vs. roughly 18 months for 2020-2024 vintage. This panel lets a researcher see whether their factor is following that trend or bucking it.

**INPUTS**

| Parameter | Options |
|---|---|
| Factor expression | Any factor from Sandbox session |
| Rolling window | 2 years of trailing data |
| Step interval | 6 months |
| Decay model | Best-fit from Feature 4.3 (AIC selection) |

**OUTPUTS**

| Output | Description |
|---|---|
| Half-life-over-time chart | Half-life (y) vs vintage year (x) with fit uncertainty bands |
| Regression overlay | Linear trend line with slope coefficient |
| Earliest vs latest half-life | Labeled points at both ends |
| Degradation verdict | Green (stable or improving) / Amber (moderate decline) / Red (rapid degradation) |

### FEATURE 4.7 — Orthogonalization Panel

**What it is:** Automatically tests how much of a new factor's IC survives after removing all known factor exposures from the Sandbox's internal baseline library — 40 factors spanning momentum (12 variants), reversal (8), low volatility (6), volume/liquidity (8), and higher moments (6), all computed internally from OHLCV data with Ken French data for residualization.

**How it works:** Gram-Schmidt sequential orthogonalization: (1) sort the 40 baseline factors by IC-IR descending, (2) regress the new factor on the first baseline factor and take the residual, (3) regress that residual on the second baseline factor and take the new residual, (4) repeat through all 40 factors. The final residual is the orthogonalized factor. Compute its Purged K-Fold IC and IC-IR. Display raw IC-IR vs orthogonalized IC-IR side by side. The orthogonalization impact bar shows the fraction of raw IC-IR that survives (green = novel component) vs the fraction that disappears (gray = redundant component). A factor with 85% green is genuinely new. A factor with 15% green is almost entirely redundant.

**INPUTS**

| Parameter | Options |
|---|---|
| New factor expression | From Expression Editor |
| Baseline library | 40 factors (momentum, reversal, low-vol, volume, higher moments) |
| Orthogonalization method | Gram-Schmidt sequential |

**OUTPUTS**

| Output | Description |
|---|---|
| Raw IC-IR vs orthogonalized IC-IR | Side-by-side comparison |
| Orthogonalization impact bar | Green (novel) vs gray (redundant) fraction |
| Baseline library browser | Full documentation in collapsible sidebar |

### FEATURE 4.8 — Interaction Screener

**What it is:** Tests multiplicative interactions between any two factors from the Sandbox's internal baseline library. Based on Borri, Chetverikov, Liu, and Tsyvinski (NBER WP 33663, 2025): pairwise interactions of six common factors improve cross-sectional R² from 31% to 59%.

**How it works:** Interaction factor = factor_A(t) × factor_B(t), cross-sectionally z-scored at each date. The interaction term is evaluated for IC and IC-IR under the same Purged K-Fold protocol as any individual factor. The interaction's IC and IC-IR are displayed alongside both parent factors' standalone metrics, making the incremental contribution immediately visible. A significant interaction IC that exceeds either parent's standalone IC identifies a non-linear pricing relationship that no linear factor combination would capture.

**INPUTS**

| Parameter | Options |
|---|---|
| Factor A | Any factor from baseline library |
| Factor B | Any factor from baseline library |
| Interaction formula | factor_A × factor_B, cross-sectionally z-scored |
| Evaluation | Purged K-Fold IC and IC-IR |

**OUTPUTS**

| Output | Description |
|---|---|
| Interaction IC/IC-IR | Alongside both parent factors' standalone metrics |
| Incremental contribution | Visible comparison of interaction vs parents |

### FEATURE 4.9 — Regime-Conditional IC Breakdown

**What it is:** Computes IC separately for three market regimes — low-vol bull, high-vol bear, transition — using a 3-state HMM fit entirely within the Sandbox on the universe's equal-weighted return series and VIX level. No external module connections required.

**How it works:** The HMM is fit using the Baum-Welch EM algorithm on two features: the equal-weighted universe daily return and the VIX level. The HMM estimates three states' emission distributions (Gaussian with diagonal covariance) and the transition matrix. Each trading day is assigned to the most probable state via the Viterbi algorithm. IC is computed separately within each regime's dates. Output: a bar chart showing IC per regime alongside unconditional IC. A factor whose IC is stable across all three regimes is genuinely regime-independent. A factor with IC = 0.08 in low-vol bull and −0.02 in high-vol bear requires a regime filter to be deployable.

**INPUTS**

| Parameter | Options |
|---|---|
| Regime model | 3-state HMM (internal to Sandbox) |
| Features | Equal-weighted universe return, VIX level |
| Regime states | Low-vol bull, high-vol bear, transition |

**OUTPUTS**

| Output | Description |
|---|---|
| IC per regime bar chart | Alongside unconditional IC |
| Regime independence verdict | Whether factor requires regime filter |

### FEATURE 4.10 — Factor Comparison Table

**What it is:** A running table of every factor expression tested in the current session alongside all 40 baseline library factors. Columns: name or expression (truncated with hover tooltip), naive IC, purged IC, IC-IR, half-life, crowding percentile, orthogonalized IC-IR, regime universality score (worst-regime IC / unconditional IC), overall quality rating. Sortable by any column, color-coded by quality rating.

**How it works:** Each time a factor expression is evaluated, the results are appended to a session-scoped results list stored in the frontend state. The baseline library factors are pre-loaded from the Sandbox's internal library database. The table component renders the combined list. Columns are reactive — sorting by any column triggers a client-side sort of the data array. Quality rating is computed as a weighted composite of purged IC, IC-IR, half-life, and regime universality (weights configurable in Sandbox settings).

**INPUTS**

| Parameter | Options |
|---|---|
| Session factors | All expressions tested in current session |
| Baseline factors | All 40 library factors |

**OUTPUTS**

| Output | Description |
|---|---|
| Comparison table | Columns: name, naive IC, purged IC, IC-IR, half-life, crowding percentile, orthogonalized IC-IR, regime universality, quality rating |
| Sorting | Sortable by any column |
| Color-coding | By quality rating |

### FEATURE 4.11 — Add to Internal Library

**What it is:** One-button addition of a validated factor to the Sandbox's internal baseline library. Validation gates: Purged K-Fold IC t-stat > 2.0, orthogonalized IC-IR > 0.04, half-life between 3 and 90 trading days, crowding percentile below 80th. Once added, all future orthogonalization computations strip this factor's contribution as well, ensuring the library's cumulative informational content is always reflected.

**How it works:** When the user clicks "Add to Library," the frontend sends a POST request to the Sandbox's library API with the factor expression, all computed metrics, and a human-readable name (auto-generated from the expression or user-supplied). The backend inserts a record into the baseline library database (SQLite/PostgreSQL) with columns: `name, expression, naive_ic, purged_ic, icir, half_life, crowding_pctile, orthogonalized_icir, regime_universality, date_added, expression_hash`. The expression hash (SHA-256) is the unique key — identical expressions cannot be added twice. The Sandbox's internal orthogonalization pipeline is updated to include this factor in its Gram-Schmidt basis for all future evaluations.

**INPUTS**

| Parameter | Options |
|---|---|
| Validation criteria | IC t-stat > 2.0, orthogonalized IC-IR > 0.04, half-life 3-90 days, crowding < 80th pctile |

**OUTPUTS**

| Output | Description |
|---|---|
| Factor added to library | With full metadata |
| Updated orthogonalization | All future factors tested against expanded library |

---

## PAGE 5 — OPTIMIZER

**What institutions pay for this:** Axioma Portfolio Optimizer is $30,000–$50,000/year for a constrained QP optimizer with a fixed factor risk model. It does not compute DSR. It does not compute PBO. It does not show a parameter stability surface. It does not run CPCV. It does not show IS/OOS Sharpe ratios per window. What Axioma provides is a tool for constructing risk-efficient portfolios given a fixed alpha signal — which is an entirely different problem from what this page solves. The quant-specific parameter optimization with proper overfitting detection does not exist as a commercial product at any price. Every fund builds their own version internally.

**The core proposition:** The complete, honest parameter optimization environment. Three distinct modes — Bayesian sweep, Walk-Forward, and CPCV — all producing outputs designed to detect overfitting rather than reward it. The auto-overfitting verdict at the end answers definitively whether the optimized strategy is credible.

---

### FEATURE 5.1 — Strategy Input and Parameter Declaration

**What it is:** Loads any strategy from Algorithm Lab and automatically parses the code to identify all numeric parameters — values declared as variables in the strategy's configuration section. Each parameter is displayed with its current value, suggested optimization range (inferred from the order of magnitude of the current value), and a toggle to include it in optimization. Parameters can be continuous (real-valued range), discrete (integer list), or categorical (string labels like `'equal_weight'`, `'vol_scaled'`, `'kelly'`).

**How it works:** A static code analyzer (using Python's `ast` module) parses the strategy file's abstract syntax tree, looking for top-level variable assignments with numeric values or tuples of values. It classifies each as continuous (single float/int), discrete (list/tuple of ints), or categorical (list/tuple of strings). The suggested range for continuous params is inferred as [current_value × 0.5, current_value × 1.5], rounded to 2 significant digits. The researcher can override any range or type classification. Only toggled-on parameters are included in the optimization — the rest are held at their current values.

**INPUTS**

| Parameter | Options |
|---|---|
| Strategy source | Algorithm Lab |
| Parameter types | Continuous (real range) / Discrete (integer list) / Categorical (string labels) |
| Optimization range | Inferred from magnitude, user-overridable |

**OUTPUTS**

| Output | Description |
|---|---|
| Identified parameter list | Current value, suggested range, toggle for inclusion |

### FEATURE 5.2 — Mode 1: Bayesian Parameter Search

**What it is:** Bayesian parameter optimization using Optuna TPE (Tree-structured Parzen Estimator) sampler. Grid search is intentionally excluded — exhaustive grid evaluation (1,000 runs for a 3-param strategy) produces the same information as Bayesian search with 500 trials but at double the compute cost, and the "comparison" output never changes how a researcher acts. Bayesian search alone is strictly superior in high-dimensional spaces because it focuses compute on promising regions.

**How it works:** At each trial, the TPE sampler builds a probabilistic model of the objective function's landscape using all prior trial results and proposes the next parameter set most likely to improve the objective. Trial budgets: 50 trials for rapid exploration, 200 for thorough search, 500 for exhaustive optimization. The search trajectory is recorded so the researcher can visually confirm the search converged. After search completes, the platform automatically runs a ±30% perturbation grid around the optimal values to produce the parameter stability score.

**Sharpe-per-Capacity-Dollar objective:** When selected, each trial's objective = raw Sharpe × capacity_ceiling_in_billions. This penalizes parameter configurations that only work at tiny position sizes. A Sharpe of 2.0 with a $50M capacity ceiling scores 0.1. A Sharpe of 1.2 with a $5B capacity ceiling scores 6.0. The optimizer naturally prefers the second configuration — directly encoding the real institutional selection logic where a fund managing tens of billions prefers a lower-Sharpe, higher-capacity signal because only the latter is deployable at meaningful scale. The capacity ceiling for each trial's parameter set is computed by running the Capacity & Turnover Stress Test (Feature 3.7) on the trial's trade log in a reduced-fidelity mode (1/10 the simulation count).

**INPUTS**

| Parameter | Options |
|---|---|
| Search method | Bayesian (Optuna TPE) only — grid search removed |
| Trial budget | 50 (rapid) / 200 (thorough) / 500 (exhaustive) |
| Objective | Sharpe (default) / Sharpe-per-Capacity-Dollar / Sortino / Calmar / Information Ratio |
| Capacity cap | Required when using Sharpe-per-Capacity-Dollar; sourced from Capacity Test (Feature 3.7) |
| Parameter ranges | Auto-inferred from code, user-overridable |
| Parameter types | Continuous (real range) / Discrete (integer list) / Categorical (string labels) |

**OUTPUTS**

| Output | Description |
|---|---|
| 2D heatmap grid | Sharpe across all evaluated parameter combinations (all pairs) |
| Bayesian trajectory overlay | Search path overlaid on heatmap showing convergence |
| Parameter stability score | ±30% perturbation grid around optimal values |

### FEATURE 5.3 — Mode 2: Walk-Forward Optimization

**What it is:** The institutional validation standard for parameter optimization. Runs ~500 backtests (10 windows × 50 Bayesian trials per window) to evaluate whether optimized parameters generalize to unseen data.

**How it works:** Configure IS window (12/24/36/60 months), OOS window (1/3/6/12 months), mode (rolling = IS window shifts forward; anchored = IS always starts from inception), and objective (Sharpe/Sortino/Calmar/IR). For each IS period: run Bayesian search (50 trials default), record optimal parameters and IS Sharpe. Apply frozen optimal parameters to the OOS period and record OOS Sharpe without further optimization. The output grid has one row per window with IS/OOS dates, optimal parameter values, IS Sharpe, OOS Sharpe, and IS/OOS ratio. Color-coded: green > 0.65 (robust), amber 0.35-0.65 (marginal), red < 0.35 (overfit). The stitched OOS equity curve concatenates all OOS period returns into a single continuous curve — this is the only honest equity curve a walk-forward strategy has. The IS equity curve is shown as a ghost overlay. Mean IS/OOS ratio is reported with a 90% bootstrap confidence interval. Regime-conditional IS/OOS ratio is also computed per market regime.

**INPUTS**

| Parameter | Options |
|---|---|
| IS window | 12 / 24 / 36 / 60 months |
| OOS window | 1 / 3 / 6 / 12 months |
| Mode | Rolling / Anchored |
| Objective | Sharpe / Sortino / Calmar / Information Ratio |
| Bayesian trials per window | 50 (default) |

**OUTPUTS**

| Output | Description |
|---|---|
| IS/OOS grid | Per-window: dates, optimal params, IS Sharpe, OOS Sharpe, IS/OOS ratio |
| Stitched OOS equity curve | Concatenated OOS returns, IS curve as ghost overlay |
| Mean IS/OOS ratio | With 90% bootstrap confidence interval |
| Regime-conditional IS/OOS | Per-regime breakdown |

### FEATURE 5.4 — Mode 3: CPCV + Deflated Sharpe

**What it is:** The definitive overfitting test — **28 full backtest paths** (N=8, k=2, the hard cap from the spec) run across combinatorially symmetric IS/OOS splits. No other commercial platform produces this output.

**How it works — CPCV:** N groups (4/6/8, hard cap at 8 for compute feasibility since C(8,2) = 28 paths provides sufficient distribution estimation), k test groups (1 or 2, k=2 maximizes paths). Total paths generated: C(N,k). For each of the C(N,k) IS/OOS group combinations: fit the model on the training complement, evaluate on the k test groups, concatenate OOS predictions across all group combinations into complete backtest paths. Each path is a complete equity curve spanning the full evaluation period with no look-ahead.

**How it works — DSR:** DSR = Φ[(CPCV_Sharpe − SR₀) × √(T−1) / √(1 − γ₃ × CPCV_Sharpe + (γ₄−1)/4 × CPCV_Sharpe²)] where SR₀ is the expected maximum Sharpe under IID noise across M trials: SR₀ ≈ √(Var[SR]) × ((1−γ)Φ⁻¹(1−1/M) + γΦ⁻¹(1−1/(Me))). The trial count M is pulled from the session's trial registry (Feature 5.6).

**How it works — PBO:** PBO = fraction of CPCV paths whose OOS Sharpe falls below the median path Sharpe. PBO = 50% = chance level. PBO = 5% = strong evidence of genuine alpha.

**How it works — Embargo sensitivity:** CPCV Sharpe and PBO are recomputed at embargo lengths of 0, 5, 10, 21 trading days and displayed as a table. A strategy whose Sharpe collapses as embargo increases has its apparent edge in autocorrelation leakage — the most common hidden failure mode in quant research.

**INPUTS**

| Parameter | Options |
|---|---|
| N groups | 4 / 6 / 8 (hard cap at 8) |
| k test groups | 1 / 2 |
| Total paths | C(N,k) — 28 for N=8, k=2 |
| Embargo lengths | 0, 5, 10, 21 trading days |

**OUTPUTS**

| Output | Description |
|---|---|
| CPCV Sharpe histogram | Mean, median, 5th, 95th percentiles marked |
| DSR | Corrected for trial count (formula annotated) |
| PBO | Fraction of CPCV paths below median |
| DSR+PBO verdict | 2×2 quadrant panel |
| Embargo sensitivity table | Sharpe and PBO at each embargo length |

### FEATURE 5.5 — Auto-Overfitting Verdict

**What it is:** After all three optimization modes complete, a single traffic-light verdict based on four criteria: Green = DSR > 0.5, PBO < 25%, mean IS/OOS ratio > 0.60, parameter stability score > 65% (all four met). Amber = 3 of 4 met (note which failed). Red = fewer than 3 met (return to Algorithm Lab).

**How it works:** The verdict engine collects the outputs of all three modes: DSR and PBO from CPCV (Mode 3), mean IS/OOS ratio from Walk-Forward (Mode 2), and parameter stability score from the Bayesian search (Mode 1). Each criterion is compared against its threshold. The verdict is computed as: all four pass → Green, three pass → Amber, two or fewer pass → Red. The specific failing criteria are displayed alongside the verdict so the researcher knows exactly what to address.

**INPUTS**

| Parameter | Options |
|---|---|
| DSR threshold | > 0.5 |
| PBO threshold | < 25% |
| IS/OOS ratio threshold | > 0.60 |
| Stability score threshold | > 65% |

**OUTPUTS**

| Output | Description |
|---|---|
| Traffic-light verdict | Green / Amber / Red with criteria breakdown |

### FEATURE 5.6 — Trial Registry

**What it is:** A permanent log of every optimization trial — full parameter set, objective score, and timestamp — synchronized with Backtest Studio's Model Lineage system. The Optimizer's trial history forms branches in the lineage graph, showing the complete search path from initial strategy to optimized final configuration.

**How it works:** Each time a trial completes (any mode), a post-trial hook collects `(trial_id, session_id, strategy_file_hash, parameter_dict, objective_value, objective_name, timestamp, mode)` and inserts it into the trial registry table. The Model Lineage system keys on `session_id + strategy_file_hash` to link trial branches to parent runs. The trial registry DB is indexed on `(strategy_file_hash, objective_value DESC)` for fast "best ever" queries.

**OUTPUTS**

| Output | Description |
|---|---|
| Trial history | Full parameter set, objective score, timestamp per trial |
| Lineage integration | Branches in Model Lineage graph from search path |

---

## PAGE 6 — UNIVERSE AND DATA STUDIO

**What institutions pay for this:** Point-in-time constituent data with survivorship bias correction is the foundational data infrastructure that separates legitimate institutional backtesting from retail backtesting. FactSet charges $12,000–$20,000/year for their Point-in-Time database. Compustat's Point-in-Time service costs $20,000+ annually. Index constituent history is sold by S&P Dow Jones Indices as a separate enterprise data product. The Data Explorer equivalent does not exist at any price on any quant platform — every existing platform forces researchers to write code just to look at their data. Bloomberg's DAPI allows programmatic data access but has no visual exploration layer. This page delivers point-in-time correctness, the visual data explorer, and the missing data diagnostic in one unified environment.

**The core proposition:** The data foundation that every other page on this platform depends on. Universe Builder constructs the investment universe with full point-in-time correctness. Data Studio provides visual, interactive data inspection with no code required. Everything else on this platform is only as good as the data inputs managed here.

---

### UNIVERSE BUILDER

#### FEATURE 6.1 — Filter Stack Interface

**What it is:** A visual pipeline where the universe is constructed by stacking filter conditions as vertically ordered cards. Each filter's output passes to the next card, with the current count of surviving stocks displayed at every stage. Filter cards are draggable (reorderable) and can be toggled on/off without deletion for quick comparison of universe definitions.

**INPUTS**

| Parameter | Options |
|---|---|
| Market cap bounds | Min/max in dollars, recomputed daily |
| Avg daily dollar volume | Minimum threshold (liquidity screen) |
| Min share price | $1 / $2 / $5 thresholds |
| GICS sector | Include/exclude sectors |
| Exchange filter | NYSE / NYSE+Nasdaq / NYSE+Nasdaq+AMEX / All |
| Float-adjusted market cap percentile | e.g., top 50% |
| Custom expression filter | Any Boolean expression over OHLCV fields |
| Filter order | Draggable, reorderable |

**OUTPUTS**

| Output | Description |
|---|---|
| Survivor count | Current count at each filter card |
| Toggle on/off | Filters persist without deletion for quick comparison |

#### FEATURE 6.2 — Point-in-Time Constituent Data

**What it is:** Point-in-time data with survivorship correction — named across every source as the single differentiator that separates a serious institutional platform from a toy. Every universe definition is applied using only information available at each historical date. Market cap uses the price and shares outstanding as of that date. Delisted stocks remain in the pre-delisting universe. IPO stocks are excluded from pre-IPO universes. Survivorship bias correction fires automatically by default — no opt-in required. Toggling it off shows an inflated comparison with a red warning banner quantifying the bias.

**How it works:** The data layer maintains a point-in-time snapshot table: for each date, it stores the complete list of stocks that existed on that date with their characteristics as of that date. This is built by applying a backward-looking filter to the forward-filling data pipeline. When the event-driven simulation engine requests universe constituents for date t, it queries the snapshot for date t — not the live/current universe. The survivorship bias toggle changes the query source: on = snapshot table by date, off = current universe for all dates.

**INPUTS**

| Parameter | Options |
|---|---|
| Survivorship bias | On (default, point-in-time correct) / Off (today's constituents for all dates) |

**OUTPUTS**

| Output | Description |
|---|---|
| Bias inflation estimate | Annualized return gap in bps (momentum strategy comparison) |
| Red warning banner | Active when survivorship bias is off |

#### FEATURE 6.3 — Time-Varying Universe Viewer

**What it is:** An interactive heatmap visualization where the x-axis is calendar time, the y-axis is stocks sorted by market cap at each date, and cells are colored green (included) or gray (excluded). Includes an entry/exit event log table and a universe overlap analysis using the Jaccard similarity coefficient between two parallel universe configurations.

**How it works:** The backend generates the heatmap data by querying the point-in-time snapshot table for each date in the selected range, grouping by ticker, and computing the inclusion status per date. The frontend renders this as a Canvas-based heatmap with WebGL acceleration for performance at 500 tickers × 1,260 days. The Jaccard similarity between two universe configs is computed as |A ∩ B| / |A ∪ B| at each monthly frequency and plotted as a line chart. Divergence over time means the two universes have structurally diverged — a regime change in market composition.

**INPUTS**

| Parameter | Options |
|---|---|
| Date range | Selectable via zoom |
| Stock sorting | Market cap at each date |
| Universe configs | Two parallel stacks for overlap analysis |

**OUTPUTS**

| Output | Description |
|---|---|
| Universe heatmap | Green (included) / gray (excluded) over time |
| Entry/exit event log | Searchable table with dates, reasons, characteristics |
| Jaccard similarity chart | Overlap between two universe configurations over time |

#### FEATURE 6.4 — Universe Snapshot Export

**What it is and why it is a money-bagger:** Export the exact constituent list on any specific date as CSV — ticker, market cap, sector, and metadata.

**OUTPUTS**

| Output | Description |
|---|---|
| CSV snapshot | Exact constituent list with ticker, market cap, sector, metadata |

#### FEATURE 6.5 — Turnover & ADV-Based Liquidity Reality Layer

**What it is:** A universe-level impact coefficient calibration system that wires all three new features (Paper Trading, Capacity Test, Capacity-Aware Optimization) into a shared, non-duplicated data foundation. Instead of each feature guessing at market impact independently, this layer provides calibrated Almgren-Chriss impact coefficients per liquidity bucket derived from the platform's own data.

**How it works:** For each stock in the universe, the layer computes: (1) 63-day rolling average daily dollar volume (ADV), (2) 21-day rolling realized volatility, (3) average bid-ask spread (estimated from daily high-low ratio if spread data is unavailable). Stocks are grouped into liquidity buckets by ADV decile: large-cap (top 10% by ADV), mid-cap (11-50%), small-cap (51-100%). Within each bucket, the Almgren-Chriss impact coefficient λ is calibrated via cross-sectional regression: for each stock, estimate λ from the relationship between observed trade size / ADV ratio and realized impact (measured as the absolute price move following a large trade, adjusted for contemporaneous market return). The resulting λ per bucket feeds the Capacity Test (Feature 3.7), the Sharpe-per-Capacity-Dollar objective (Feature 5.2), and the Paper-Trading Mode's cost model (Feature 1.9). The calibrated coefficients are stored in the data catalog and are automatically refreshed monthly.

**INPUTS**

| Parameter | Options |
|---|---|
| Data source | ADV, volatility, bid-ask (from OHLCV data) |
| Liquidity buckets | Large-cap (top 10% ADV) / Mid-cap (11-50%) / Small-cap (51-100%) |
| Calibration method | Cross-sectional OLS: impact = λ × σ × (trade_size/ADV)^(3/5) |
| Refresh frequency | Monthly |

**OUTPUTS**

| Output | Description |
|---|---|
| λ per liquidity bucket | Calibrated impact coefficient for large/mid/small cap |
| Calibration diagnostic | R-squared and standard error of each bucket's regression |
| Data catalog entry | Coefficients stored and versioned in data catalog |
| Downstream consumers | Capacity Test (F3.7), Optimizer (F5.2), Paper Trading (F1.9) |

---

### DATA STUDIO

#### FEATURE 6.6 — Data Catalog

**What it is:** A searchable, filterable catalog of every data source on the platform. Each entry shows: source name, URL, data type (OHLCV/factor/macro/reference), coverage universe, date range, update frequency, last successful update timestamp, and known data quality issues. Includes yfinance OHLCV (1990-present, daily), FRED series (VIX, yields, OAS, USD index), Ken French Data Library (FF3/FF5 + Momentum, daily), and user-uploaded custom data.

**INPUTS**

| Parameter | Options |
|---|---|
| Data sources | yfinance OHLCV, FRED series, Ken French Data Library, user-uploaded CSVs |

**OUTPUTS**

| Output | Description |
|---|---|
| Searchable catalog | Source name, type, coverage, date range, frequency, last update, quality issues |
| Data access expression | Naming convention for expression editor access |

#### FEATURE 6.7 — Data Explorer

**What it is and why it is a money-bagger:** Visual, interactive, no code required. The complete data inspection environment that does not exist on any quant platform.

**What it contains:** Select any ticker or FRED/French series. Primary chart: OHLCV candlestick (equity) or line chart (series). Below: volume bars, rolling 21-day realized vol (Garman-Klass), rolling 252-day Sharpe. All panels synchronized. Secondary series overlay with dual y-axes. Distribution panel with histogram, QQ-plot, stats, normality test. Anomaly detection: 5-sigma moves, zero-volume days, missing data gaps, price reversals.

**INPUTS**

| Parameter | Options |
|---|---|
| Primary series | Any ticker, FRED series, or French series |
| Secondary series | Any second series for comparison overlay |

**OUTPUTS**

| Output | Description |
|---|---|
| Primary chart | OHLCV candlestick or line chart |
| Sub-panels | Volume, rolling vol (GK), rolling Sharpe |
| Overlay chart | Dual y-axis comparison |
| Distribution panel | Histogram, QQ-plot, mean, std, skew, kurtosis, Jarque-Bera p-value |
| Anomaly table | Date, severity, suggested action |

#### FEATURE 6.8 — Missing Data Heatmap

**What it is:** An N tickers × T dates heatmap where cells are colored green (data present and valid), yellow (data flagged anomalous by the anomaly detector), or red (data absent). Renders up to 500 tickers × 5 years (630,000 cells) without performance degradation using Canvas-based rendering. Systematic red bands across all tickers on specific dates indicate market closures or data provider outages — these dates are automatically excluded from all factor computations and backtest runs. Idiosyncratic red cells on specific ticker-date combinations indicate stock-level data issues that may contaminate IC calculations.

**INPUTS**

| Parameter | Options |
|---|---|
| Ticker subset | Up to 500 tickers |
| Date range | Any range |
| Coverage | Green (valid), yellow (anomalous), red (absent) |

**OUTPUTS**

| Output | Description |
|---|---|
| Missing data heatmap | 500 × 1,260 cell grid without degradation |
| Auto-exclusion list | Dates with systematic red bands excluded from all computations |

#### FEATURE 6.9 — Custom Data Upload

**What it is and why it is a money-bagger:** Upload any CSV with at minimum date and ticker columns. Auto-detects date format. Registers numeric columns as `custom.field_name`. Aligns to trading calendar, forward-fills gaps (default 1, max 5 days).

**INPUTS**

| Parameter | Options |
|---|---|
| File format | CSV with date column + ticker column |
| Forward-fill max | 1 day (default), 5 days (maximum) |

**OUTPUTS**

| Output | Description |
|---|---|
| Validation report | Date coverage, ticker coverage, missing fraction, value distribution, return correlation |

#### FEATURE 6.10 — Data Freshness Monitor

**What it is:** A daily check of every automated data source at market close. Status board shows: source name, last successful update timestamp, data lag in trading days, and status (current/stale/failed). Amber alert for stale sources, red alert for failed updates with the error message. Every backtest run is tagged in the Model Lineage system with a snapshot of the data freshness status at execution time — if a backtest ran on stale FRED data, that fact is permanently recorded in the run's metadata.

**INPUTS**

| Parameter | Options |
|---|---|
| Data sources | All automated sources (yfinance, FRED, Ken French) |
| Check frequency | Daily at market close |

**OUTPUTS**

| Output | Description |
|---|---|
| Freshness status board | Current/stale/failed per source with lag |
| Amber/red alerts | Stale sources trigger amber, failed sources trigger red |
| Run metadata tag | Data freshness snapshot attached to each backtest run |

---

## COMPUTATION COST SUMMARY

The following table shows the exact run-count math for every compute-intensive feature on the platform. All counts are arithmetic from the spec's own parameters — no benchmarking assumptions.

### Run-Count Math (exact, from spec parameters)

| Feature | Runs Required | How Derived |
|---|---|---|
| **Parameter Stability Surface** (3-param, opt-in) | 9,261 backtests | 21³ grid points |
| **Parameter Stability Surface** (2-param, default) | 441 backtests | 21² grid points |
| **CPCV** (N=8, k=2) | 28 full backtest paths | C(8,2) hard cap |
| **Bayesian search** (Sharpe objective, default) | 500 backtests | Direct trial count |
| **Bayesian search** (Sharpe-per-Capacity-Dollar objective) | 500 backtests + 500 reduced-fidelity capacity runs | Each trial runs a reduced-fidelity Capacity Stress sub-simulation (1/10 simulation count, Feature 3.7) to compute the capacity ceiling for that trial's parameter set |
| **Walk-Forward** (10 windows × 50 trials) | 500 backtests | 10 × 50 |
| **Timing Perturbation** (4 magnitudes × 1,000) | 4,000 simulations | Direct from spec |
| **Monte Carlo** (3 modes, shared engine) | 15,000 simulated paths | From spec parameters |
| **Capacity & Turnover Stress** (20 AUM points) | 20 impact simulations per strategy | 20 log-spaced points × λ-bucket calibration |
| **Noise Injection** (4 levels × 500, on-demand) | 2,000 simulations | Direct from spec |
| **OOS Boundary Sensitivity** (5 splits, on-demand) | 5 × walk-forward cost | Reduced from 9 to 5 |
| **Paper Trading** (daily forward run) | 1 signal generation pass/day | Cron-triggered |

**One full "certify this strategy" pass** (Parameter Stability 2-param + CPCV + Walk-Forward + Timing Perturbation + Cost Break-Even + Capacity Stress + Monte Carlo) = **~20,000 backtest-or-simulation-equivalent runs** for one strategy.

### Relative Cost Notes

- **CPCV at 28 paths looks small** but each path is a full backtest over the *entire* dataset, not a subset — per-path cost is higher than a grid-search run.
- **Monte Carlo's 15,000 paths** are the lightest individual unit — resampling and evaluating a return series is far cheaper than re-running an event-driven simulation.
- **Parameter Stability Surface** is the heaviest compute by a wide margin. The 2-param default reduces this by 21× compared to 3-param.
- **Paper Trading** is trivial compute — one signal generation pass per day with no backtest re-run.

### Optimizations Applied

| Optimization | Impact |
|---|---|
| Grid search removed from Optimizer Mode 1 | Eliminates 1,000-run redundancy (Bayesian covers same ground with 500 trials) |
| Parameter Stability Surface capped at 2 params by default | 441 runs vs 9,261 (21× reduction); 3+ params opt-in |
| Core robustness reduced to 4 tests (1/2/5/Capacity) | Cuts ~7,500 simulations from automatic certification pass by moving 3 tests to on-demand |
| OOS Boundary Sensitivity reduced from 9 to 5 splits | Halves this test's cost with disclosed granularity loss |
| Monte Carlo shared across pages | Single engine consumed by Backtest Studio, Robustness Lab, and Optimizer |
| Universe Perturbation moved out of core | Eliminates 1,500 simulations from default certification pass |
| Debugger removed from Monaco editor | Eliminates debug protocol engineering; saves ~2-3 dev-months |
| Crowding Monitor degreed to contemporaneous only | Gutted predictive claims; saved engineering from false ML confidence layer |

---

*Six pages. Nothing better exists at any price from any vendor. Every feature specified above is buildable from free public data: yfinance OHLCV, FRED API, Ken French Data Library, computed from first principles. Total external data cost: $0/month.*
