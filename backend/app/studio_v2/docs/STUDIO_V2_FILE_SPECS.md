# QUANT360 Studio v2 — Complete Build Specification

**Generated:** July 26, 2026
**Source spec:** `Studio v2 feature.md` — 46 features, 6 pages
**Architecture plan:** `STUDIO_V2_ARCHITECTURE.md` — 27 backend files, 4 phases
**Total service files documented:** 22 (sorted alphabetically by path)

---

## `backend/app/studio_v2/algorithm_lab/kernel.py`

**Features covered:** F1.2 (Persistent Kernel + Reactive Dependency Graph), F1.5 (Variable Inspector)

**Imports from:** `shared.data_loader`, `backtest.lineage` (for session context)

**Phase:** Phase 1

### Classes

#### `DependencyTracker`
**Description:** Tracks which cell/file defines which variable and which cells/files read it. After every execution, updates the dependency graph. Defines edges color-coded in the editor margin. Duplicate variable names across cells is a hard error.
**Key methods:**
- `record_execution(cell_id: str, namespace: dict) -> None` — scans namespace for new/modified globals, records definitions for each variable
- `add_variable_definition(var_name: str, cell_id: str) -> None` — registers that `cell_id` defines `var_name`
- `add_variable_read(var_name: str, cell_id: str) -> None` — registers that `cell_id` reads `var_name`
- `get_dependents(cell_id: str) -> List[str]` — returns all cell IDs that depend on variables defined in `cell_id`
- `get_stale_variables() -> Dict[str, FreshnessStatus]` — returns `{var_name: GREEN|YELLOW|RED}` based on whether upstream definitions have changed
- `detect_duplicate_definitions(var_name: str) -> bool` — raises `DuplicateVariableError` if `var_name` is defined in multiple cells
- `get_dependency_graph() -> Dict` — serializes the full graph for frontend rendering
- `mark_stale_downstream(cell_id: str) -> None` — propagates staleness markers to all transitive dependents

#### `KernelGateway`
**Description:** Manages the persistent IPython kernel lifecycle. Initializes kernel on session start with the researcher's data universe. Communicates via ZMQ/Jupyter WebSocket protocol. Session timeout configurable (default 4h), garbage-collects idle kernels. Kernel-side cache uses LRU eviction keyed by `(universe_hash, computation_type, parameter_hash)`.
**Key methods:**
- `start_session(session_id: str, universe_config: dict) -> None` — spawns kernel process, initializes with data universe, registers `post_execute` hooks
- `execute_code(code: str, cell_id: str) -> ExecutionResult` — sends code to kernel via shell channel, captures stdout/stderr/error, triggers dependency tracking after execution
- `execute_code_sync(code: str, cell_id: str) -> ExecutionResult` — blocking variant
- `interrupt_kernel() -> None` — sends SIGINT to kernel process
- `restart_kernel() -> None` — terminates and re-spawns kernel, clears in-memory state
- `restore_from_checkpoint(run_id: str) -> None` — terminates current kernel, spawns new one, deserializes cloudpickle checkpoint into namespace
- `serialize_namespace() -> dict` — iterates `globals()` via `post_execute` hook, filters public names, classifies by type, sends structured JSON to frontend
- `get_session_timeout() -> int` — returns remaining idle time before GC
- `ping() -> bool` — health check
- `shutdown() -> None` — clean kernel termination

#### `SessionCache`
**Description:** LRU cache keyed by `(universe_hash, computation_type, parameter_hash)`.
**Key methods:**
- `get(key: tuple) -> Any` — returns cached value or None
- `set(key: tuple, value: Any) -> None` — stores with LRU eviction
- `invalidate(universe_hash: str) -> None` — clears all entries for a given universe
- `clear() -> None` — full cache reset

### Functions

#### `extract_variable_info(variable: Any, var_name: str) -> dict`
**Signature:** `(variable: Any, var_name: str) -> dict`
**Inputs:** Any Python object and its name
**Outputs:** `{name, type, shape, dtype, memory_bytes, preview_row (for DFs), statistics (for arrays)}`
**Logic:** Uses `type()`, `getattr(obj, 'shape', None)`, `getattr(obj, 'dtypes', None)`, `memory_usage(deep=True)` for DFs, `nbytes` for arrays.

### Data it reads/writes
- **Reads:** Session checkpoint files (pickle/cloudpickle) from `sessions/` directory keyed by `(session_id, run_sequence_number)`
- **Writes:** Session checkpoint files (pickle/cloudpickle) after each execution
- **DB tables:** `kernel_sessions` — `(session_id, created_at, last_activity, timeout_mins, status)`; `session_variables` — `(session_id, var_name, var_type, shape, memory_bytes, is_stale, last_updated_cell_id)`
- **Parquet:** None directly — calls `data_loader` for data loading into kernel

### Key formulas
None — kernel management is infrastructure. No formulas.

### Edge cases to handle
- Session timeout during a long-running computation (use keepalive pings)
- Kernel crash: auto-restart with warning to user, preserve as much state as possible
- Duplicate variable name across cells: hard error, not silent overwrite
- Memory exhaustion: implement `memory_watermark` threshold that triggers LRU eviction cascade
- Large DataFrames: truncate serialization at 1000 rows for preview; request full data via pagination
- Dependency cycles: detect and report as error
- Stale state after dependency change: support manual/auto/confirm modes
- Empty namespace on fresh kernel: all variables show as nonexistent

---

## `backend/app/studio_v2/algorithm_lab/linter.py`

**Features covered:** F1.1 (Monaco Code Editor — Lookahead Bias Linter)

**Imports from:** None (self-contained AST analysis)

**Phase:** Phase 1

### Classes

#### `LookaheadBiasLinter`
**Description:** Custom `CodeActionProvider` that scans Python AST for patterns indicating lookahead bias, hardcoded parameters, non-deterministic operations in signal logic. Runs on every keystroke server-side in the Monaco extension. Flags cannot block execution but appear as yellow warnings.
**Key methods:**
- `lint_code(source: str) -> List[LintDiagnostic]` — runs all checks, returns list of diagnostics with line numbers, severity, message
- `check_shift_without_ffill(source_ast: ast.Module) -> List[LintDiagnostic]` — detects `.shift(-1)` or `.shift(1)` on price/return data that is not followed by `.ffill()` or `.fillna()` within 3 statements
- `check_hardcoded_date_ranges(source: str) -> List[LintDiagnostic]` — flags string patterns like `"2020-01-01"`, `"2023"` in strategy config that should be parameterized
- `check_future_date_reference(source_ast: ast.Module) -> List[LintDiagnostic]` — flags variable names containing `future`, `next_week`, `tomorrow` used in signal computation
- `check_lookahead_shift(source_ast: ast.Module) -> List[LintDiagnostic]` — catches `.values` calls after slicing that break index alignment
- `check_non_deterministic(source_ast: ast.Module) -> List[LintDiagnostic]` — flags `random`, `np.random`, `datetime.now()` inside signal generation functions
- `register_completion_providers(monaco_api) -> None` — registers the platform's API surface (all factor functions, data accessors, Labs modules) as a `CompletionItemProvider`

#### `LintDiagnostic`
**Description:** Data class with `line: int, column: int, end_line: int, end_column: int, message: str, severity: Warning|Error, code: str` (machine-readable error ID).

### Functions

#### `build_function_registry() -> Dict[str, FunctionSignature]`
**Signature:** `() -> Dict[str, FunctionSignature]`
**Inputs:** None — reads from platform's registered function metadata
**Outputs:** Dict mapping function name → `{params, return_type, docstring}`
**Logic:** Scans the platform's public API surface for autocomplete registration.

### Data it reads/writes
- **Reads:** Platform function library metadata (for autocomplete registration)
- **Writes:** None — outputs lint diagnostics to frontend in real-time
- **DB tables:** None
- **Parquet:** None

### Key formulas
None — AST pattern matching rules as described above.

### Edge cases to handle
- Empty source: return empty diagnostic list
- Syntax errors: return syntax error diagnostic, skip other checks
- Multi-line expressions in AST: handle correctly with line range spans
- Large files (>1000 lines): debounce linting to every 300ms, not every keystroke
- `shift` calls in legitimate contexts (lag features): check surrounding context — if followed by `.ffill()`, no warning
- Third-last or earlier statement shift usage: narrow scope to 3-statement window
- Inline date ranges that match the backtest config: compare against session's date range — flag only if not config-driven

---

## `backend/app/studio_v2/algorithm_lab/paper_trader.py`

**Features covered:** F1.9 (Forward Paper-Trading Mode with Code Parity)

**Imports from:** `shared.data_loader`, `backtest.lineage`, `backtest.engine`

**Phase:** Phase 4

### Classes

#### `PaperTrader`
**Description:** Runs the strategy's `generate_signals()` function (identical code path to Backtest Studio) on delayed yfinance data via daily cron. Logs generated signals, records actual vs predicted returns. After N trading days (default 20), computes forward reliability score.
**Key methods:**
- `run_daily_paper_trade(strategy_name: str) -> PaperTradeResult` — (1) pulls latest 15-min-delayed OHLCV for strategy's universe, (2) calls `generate_signals()` on the data, (3) logs generated signals with timestamps, (4) records actual forward returns at next pull
- `compute_forward_reliability(strategy_name: str, min_days: int = 20) -> float` — Spearman rank correlation between predicted and actual daily returns over the paper-trading history
- `get_status(strategy_name: str) -> PaperTradingStatus` — returns burn-in days completed, current reliability score, number of signals generated
- `get_equity_curve(strategy_name: str) -> DataFrame` — returns cumulative return from live-forward signals
- `get_signal_log(strategy_name: str) -> DataFrame` — returns all generated signals with timestamps and actual outcomes

#### `CodeParityBridge`
**Description:** Ensures the same `generate_signals(data) -> signals` function is used by both Backtest Studio and Paper Trader. Validates that the strategy file's signal function signature matches the expected interface.
**Key methods:**
- `validate_strategy_signature(strategy_file: str) -> bool` — checks that the file contains `def generate_signals(data)` or similar expected signature
- `load_strategy_module(strategy_file: str) -> ModuleType` — loads the strategy file as a Python module without side effects
- `call_generate_signals(strategy_module, data: DataFrame) -> DataFrame` — calls the strategy's signal generation function with provided data

### Functions

#### `daily_cron_job() -> None`
**Signature:** `() -> None`
**Inputs:** None — reads all active paper-trading strategies from config
**Outputs:** None — side effect: runs paper trades for all active strategies
**Logic:** Scheduled via cron/APScheduler. Iterates registered paper-trading strategies and calls `run_daily_paper_trade()` for each.

### Data it reads/writes
- **Reads:** Strategy files from versioned file store; OHLCV data from yfinance (via `data_loader` or yfinance directly); paper trade state from DB
- **Writes:** `paper_trades` — `(id, strategy_name, timestamp, ticker, signal_direction, predicted_return, actual_return, entry_price, exit_price, status)`
- **DB tables:** `paper_trading_config` — `(strategy_name, universe_id, start_date, status, burn_in_days)`
- **Parquet:** None

### Key formulas

#### Forward reliability score
`ρ = Spearman_rank_correlation(predicted_daily_returns, actual_daily_returns)`
- Threshold: score < 0.3 = strategy not surviving live contact

#### Code parity guarantee
`generate_signals(data)` called identically in both backtest and paper trading — same Python module, same function pointer, same code path.

### Edge cases to handle
- Fewer than `min_days` of history: return None for reliability score, log "insufficient data"
- Missing yfinance data for a ticker: skip ticker for that day, log warning
- Universe ticker delisted: handle gracefully — no signal for delisted tickers
- Cron fails or missed day: backfill on next successful run
- Strategy file changes mid-paper-trade: log warning, continue with loaded module version
- No signals generated for multiple days: flag as "strategy not producing signals in live conditions"
- Network failure: retry with exponential backoff (3 attempts, 30s/60s/120s)

---

## `backend/app/studio_v2/backtest/engine.py`

**Features covered:** F2.2 (Event-Driven Simulation Engine)

**Imports from:** `shared.data_loader`, `backtest.metrics`, `backtest.lineage`, `shared.liquidity` (for impact cost in fills)

**Phase:** Phase 1

### Classes

#### `EventDrivenEngine`
**Description:** Sequential bar-by-bar simulation engine. Processes every bar in order — orders fire at close of signal bar, fill at next bar's open. Handles corporate actions, partial fills via ADV ratio, short-sell flags, margin modeling.
**Key methods:**
- `run(config: SimulationConfig) -> SimulationResult` — main entry point: loads universe data, iterates date range, computes signals, executes trades
- `_load_and_prepare_universe(universe_id: str, start: date, end: date) -> PriceData` — loads OHLCV from `data_loader`, adjusts for splits/dividends, computes ADV
- `_run_date_loop(dates: List[date], price_data: dict) -> None` — core simulation loop: for each date t, (1) load OHLCV, (2) compute signals, (3) generate orders, (4) fill at t+1 open, (5) apply corp actions, (6) compute NAV
- `_compute_signals(date: date, price_data: PriceData) -> SignalFrame` — calls strategy's `generate_signals()` for current date
- `_generate_orders(signals: SignalFrame, positions: PortfolioState, date: date) -> OrderList` — converts signals to orders with direction and size based on position sizing config
- `_fill_orders(orders: OrderList, price_data: PriceData, date: date) -> FillList` — fills orders at date t+1 open with partial-fill logic
- `_apply_corporate_actions(positions: PortfolioState, date: date) -> None` — adjusts for splits (multiply shares, divide cost basis), dividends (add cash), delistings
- `_compute_nav(positions: PortfolioState, cash: float, prices: PriceData, date: date) -> float` — mark-to-market NAV

#### `SimulationConfig`
**Description:** Data class holding: `strategy_source`, `universe_id`, `date_start`, `date_end`, `benchmark`, `rebalance_freq`, `position_sizing` (`equal_weight`/`vol_scaled`/`kelly`/`custom`), `cost_model` (`almgren_chriss`/`flat_bps`/`zero`), `cost_bps`, `survivorship_bias` (bool), `margin_enabled` (bool), `max_fill_pct` (default 0.20), `hard_to_borrow_threshold`.

#### `PortfolioState`
**Description:** Tracks `positions: Dict[ticker, Position]`, `cash: float`, `margin_used: float`, `nav_history: List[DateNAV]`.

#### `SimulationResult`
**Description:** Contains `trade_log: DataFrame`, `daily_returns: Series`, `daily_nav: Series`, `positions_log: DataFrame`, `orders_log: DataFrame`, `config: SimulationConfig`, `run_duration_seconds`.

### Functions

#### `compute_adv(volume_series: Series, window: int = 63) -> Series`
**Signature:** `(volume_series: Series, window: int = 63) -> Series`
**Inputs:** Daily volume series, rolling window (default 63 trading days)
**Outputs:** Rolling average daily dollar volume
**Logic:** `volume_series.rolling(window).mean() * close_price`

#### `partial_fill_ratio(order_size: float, adv: float, max_fill_pct: float = 0.20) -> float`
**Signature:** `(order_size: float, adv: float, max_fill_pct: float = 0.20) -> float`
**Inputs:** Trade size in dollars, ADV in dollars, max fill percentage
**Outputs:** Fill ratio between 0 and 1
**Logic:** `min(1.0, max_fill_pct / (trade_size / adv))` — if trade exceeds 5× ADV at 20% max, fill ratio caps at 0.04 (4% of order filled)

### Data it reads/writes
- **Reads:** `market_universe.parquet` (via data_loader) for OHLCV; `master_fundamentals.parquet` for ADV computation (volume × price)
- **Writes:** `backtest_runs` — `(run_id, strategy_hash, config, metrics, trade_log_path, equity_curve_path, created_at)`; `backtest_trades` — per-run trade table; `backtest_daily_returns` — per-run daily returns table
- **DB tables:** Via lineage.py for recording

### Key formulas

#### Order fill timing
Signal fires at `t-1` close → order fills at `t` open (zero look-ahead).

#### Partial fill ratio
`fill_ratio = min(1.0, max_fill_pct / (trade_size / ADV_t))` where `max_fill_pct` defaults to 20%.

#### Almgren-Chriss market impact (for fill prices)
`impact(bps) = λ × σ × (trade / ADV)^(3/5)` — applied as price adjustment on fills.

### Edge cases to handle
- Single ticker universe: no diversification benefit, still runs correctly
- Universe of 0 tickers after filters: return empty result with warning
- Empty date range (no trading days): return empty result
- Missing price data for a ticker at a specific date: carry forward last price, flag in log
- Split/dividend on date of position entry: handle correctly with adjusted shares
- Hard-to-borrow stock: `generate_orders` checks flag and reduces/denies short positions
- Large universe (>500 tickers): chunk and parallelize via `multiprocessing.Pool`
- First date has no signal history: skip order generation for date 1
- `max_fill_pct` exceeded for all orders in a day: partial fills across all, log warning
- Benchmark unavailable for a date: use risk-free rate for that date

---

## `backend/app/studio_v2/backtest/lineage.py`

**Features covered:** F2.6 (Model Lineage System)

**Imports from:** `backtest.engine` (for SimulationResult type), `backtest.metrics` (for metric dicts)

**Phase:** Phase 1

### Classes

#### `ModelLineage`
**Description:** DAG storage for every backtest run. Records run_id, strategy_hash (SHA-256 of file content), parent_run_id, parameters (JSONB), metrics (JSONB), timestamp, tag (Candidate/Active/Retired/Deployed). Supports diff mode, search, walk-forward mode tracking.
**Key methods:**
- `record_run(strategy_file: str, config: SimulationConfig, result: SimulationResult, parent_run_id: str = None) -> str` — computes SHA-256 of strategy file, inserts run record with all metadata
- `compute_strategy_hash(file_content: str) -> str` — SHA-256 hash of file content for change detection
- `get_run(run_id: str) -> RunRecord` — returns full record for a run ID
- `get_lineage_graph(strategy_file_hash: str) -> List[Edge]` — returns all runs for a strategy hash, grouped by parent-child edges
- `diff_runs(run_id_a: str, run_id_b: str) -> DiffResult` — returns code diff (Myers), parameter diff (set operations), performance diff (side-by-side metrics)
- `search_runs(query: SearchQuery) -> List[RunRecord]` — search by metric ranges, tag, date range, strategy name; sorted by DSR descending
- `set_run_tag(run_id: str, tag: RunTag) -> None` — sets Candidate/Active/Retired/Deployed
- `fork_run(run_id: str, new_config: dict) -> str` — creates a new run as child of `run_id` with potentially modified config
- `record_walkforward_window(parent_run_id: str, window_index: int, is_sharpe: float, oos_sharpe: float, optimal_params: dict) -> None` — records individual walk-forward window results
- `get_dag_layout(strategy_file_hash: str) -> dict` — returns nodes and edges for Dagre/Sugiyama DAG rendering

#### `RunRecord`
**Description:** Data class with `run_id, strategy_file_hash, strategy_name, parent_run_id, parameters (dict), metrics (dict), tags (List[RunTag]), created_at, duration_seconds, trade_log_path, equity_curve_path, data_freshness_snapshot (dict)`

#### `SearchQuery`
**Description:** `dsr_min, pbo_max, sharpe_min, sortino_min, max_drawdown_max, date_range_start, date_range_end, tags, strategy_name_contains, limit, offset`

### Functions

#### `detect_non_default_parameters(run_params: dict, defaults: dict) -> dict`
**Signature:** `(run_params: dict, defaults: dict) -> dict`
**Inputs:** Run parameter dict, platform default parameter dict
**Outputs:** Dict of only non-default parameters with their values
**Logic:** Set-wise comparison — returns `{k: v for k, v in run_params.items() if k not in defaults or v != defaults[k]}`

### Data it reads/writes
- **Writes:** `lineage_runs` — `(run_id UUID PK, strategy_file_hash VARCHAR(64), strategy_name TEXT, parent_run_id UUID FK, config_params JSONB, metrics JSONB, tag VARCHAR(20), created_at TIMESTAMP, duration_seconds FLOAT, data_freshness JSONB)`
- **Writes:** `lineage_edges` — `(run_id UUID FK, parent_run_id UUID FK, relationship_type VARCHAR(20))`
- **Writes:** `lineage_tags` — `(run_id UUID FK, tag VARCHAR(20), tagged_by TEXT, created_at TIMESTAMP)`
- **Writes:** `walkforward_windows` — `(parent_run_id UUID FK, window_index INT, is_start DATE, is_end DATE, oos_start DATE, oos_end DATE, is_sharpe FLOAT, oos_sharpe FLOAT, optimal_params JSONB, regime_conditional JSONB)`
- **Reads:** Strategy files from versioned file system (for diff, hash)
- **Parquet:** None directly; all data comes via engine result

### Key formulas

#### Strategy file hash
`SHA-256(file_content.encode('utf-8')).hexdigest()`

#### Walk-Forward IS/OOS ratio
`ratio = oos_sharpe / is_sharpe`

### Edge cases to handle
- First run of a strategy: `parent_run_id = None` — root node in DAG
- Empty metrics from failed run: store error state, display as failed node
- No search matches: return empty list, not error
- Circular fork references: graph construction detects and rejects cycles
- Strategy file renamed but not changed: hash remains same → lineage continuity preserved
- Strategy file unchanged but new run: child of most recent run with same hash
- Walk-forward with no OOS data: skip last window, warn
- Concurrent writes to lineage: use DB transactions with retry on conflict
- Large lineage graph (>1000 nodes): paginate and lazy-load subgraphs

---

## `backend/app/studio_v2/backtest/metrics.py`

**Features covered:** F2.4 (Honest Performance Card)

**Imports from:** `shared.data_loader` (for risk-free rate), `optimizer.cpcv` (for M trial count), `backtest.engine` (for SimulationResult)

**Phase:** Phase 1

### Classes

#### `PerformanceMetrics`
**Description:** Computes all seven numbers for the Honest Performance Card: DSR, PBO, PSR, Raw Sharpe, Sortino, Calmar, Max Drawdown. Also computes win rate, profit factor.
**Key methods:**
- `compute_all(returns: Series, cpcv_paths: DataFrame = None, m_trials: int = 1) -> MetricCard` — computes all seven metrics from the return series
- `compute_sharpe(returns: Series, rf: float = 0.0) -> float` — standard Sharpe ratio
- `compute_sortino(returns: Series, rf: float = 0.0) -> float` — downside deviation-adjusted return
- `compute_calmar(returns: Series) -> float` — CAGR / max drawdown
- `compute_max_drawdown(returns: Series) -> float` — largest peak-to-trough decline
- `compute_psr(returns: Series, sharpe: float, rf: float = 0.0) -> float` — Probabilistic Sharpe Ratio
- `compute_dsr(returns: Series, sharpe: float, m_trials: int, gamma: float = 0.5772) -> float` — Deflated Sharpe Ratio
- `compute_pbo(cpcv_paths: DataFrame) -> float` — Probability of Backtest Overfitting
- `compute_skewness(returns: Series) -> float` — third standardized moment
- `compute_excess_kurtosis(returns: Series) -> float` — fourth standardized moment minus 3
- `compute_win_rate(returns: Series) -> float` — fraction of positive days
- `compute_profit_factor(returns: Series) -> float` — sum(gains) / abs(sum(losses))

#### `MetricCard`
**Description:** Data class: `dsr, pbo, psr, sharpe, sortino, calmar, max_drawdown, win_rate, profit_factor, skewness, excess_kurtosis, m_trials, lookahead_inflation`

### Functions

#### `annualized_sharpe(daily_returns: Series, rf_annual: float = 0.0) -> float`
**Logic:** `(mean(returns) - rf_daily) / std(returns) * sqrt(252)`

#### `cagr(returns: Series) -> float`
**Logic:** `(prod(1 + returns)) ^ (252 / len(returns)) - 1`

### Data it reads/writes
- **Reads:** Daily return series from engine result; CPCV path distribution from optimizer/cpcv.py; M trial count from optimizer/verdict.py TrialRegistry
- **Writes:** None — returns `MetricCard` to caller
- **Parquet:** None

### Key formulas

#### Sharpe ratio
`Sharpe = (mean(R) - Rf) / std(R) × √252`

#### Sortino ratio
`Sortino = (mean(R) - Rf) / downside_std(R) × √252` where `downside_std = std(min(R, 0))`

#### Calmar ratio
`Calmar = CAGR / max_drawdown`

#### Maximum drawdown
`DD_t = (cummax(1+R)_t - cumprod(1+R)_t) / cummax(1+R)_t`; `MaxDD = max(DD)`

#### Probabilistic Sharpe Ratio (PSR)
`PSR = Z[ (SR_hat × √(T-1)) / √(1 - γ₃ × SR_hat + (γ₄-1)/4 × SR_hat²) ]`
- `SR_hat` = estimated Sharpe ratio, `T` = number of observations
- `γ₃` = skewness, `γ₄` = excess kurtosis, `Z` = standard normal CDF

#### Deflated Sharpe Ratio (DSR)
`DSR = Φ[ (SR_CPCV - SR₀) × √(T-1) / √(1 - γ₃ × SR_CPCV + (γ₄-1)/4 × SR_CPCV²) ]`
where `SR₀ ≈ √(Var[SR]) × ((1-γ)Φ⁻¹(1-1/M) + γΦ⁻¹(1-1/(M·e)))`
- `γ` = Euler-Mascheroni constant ≈ 0.5772
- `M` = number of trials from Optimizer session trial registry
- When `M=1`: SR₀ = 0, DSR reduces to PSR

#### Probability of Backtest Overfitting (PBO)
`PBO = fraction of CPCV paths whose OOS Sharpe < median path Sharpe`

### Edge cases to handle
- `M=1` (no optimizer trials): DSR reduces to PSR — SR₀ = 0
- All returns equal (zero variance): Sharpe = 0, Sortino = 0, DSR/PSR = Φ(0) = 0.5
- Only positive returns (no downside): Sortino denominator = 0 — return large number, label "no downside periods"
- Empty return series: all metrics return NaN with "insufficient data" label
- Single day of returns: insufficient for meaningful metrics — return None for all
- CPCV paths not provided for PBO: PBO = NaN, label "run CPCV (F5.4) to compute PBO"

---

## `backend/app/studio_v2/backtest/reconciliation.py`

**Features covered:** F2.8 (Live-vs-Backtest Reconciliation Panel)

**Imports from:** `backtest.lineage`, `backtest.metrics`, `algorithm_lab.paper_trader`

**Phase:** Phase 4

### Classes

#### `Reconciliation`
**Description:** Computes running divergence score between projected backtest returns and actual paper trading returns. Rolling 20-day window. Provides status verdict (Green/Amber/Red).
**Key methods:**
- `compute_divergence(backtest_run_id: str, paper_trading_name: str) -> ReconciliationResult` — pulls backtest projected and paper trading realized returns, computes divergence metrics
- `compute_running_divergence_score(actual: Series, predicted: Series, window: int = 20) -> Series` — `|actual - predicted| / predicted_vol`, rolling 20-day window
- `compute_reliability_decay_rate(divergence_scores: Series) -> float` — slope of divergence score over time
- `status_verdict(divergence_scores: Series) -> str` — Green (mean < 0.5), Amber (0.5-1.0), Red (> 1.0)

#### `ReconciliationResult`
**Description:** `backtest_equity_curve, paper_trading_equity_curve, divergence_scores, mean_divergence, reliability_decay_rate, verdict, num_trading_days`

### Data it reads/writes
- **Reads:** Backtest daily returns from DB (via lineage); Paper trading daily returns from `paper_trades` table
- **Writes:** None — returns ReconciliationResult for frontend rendering

### Key formulas

#### Running divergence score
`Divergence_t = |actual_return_t - predicted_return_t| / predicted_volatility_t` (rolling 20-day window)

#### Reliability decay rate
`slope = linear regression coefficient of Divergence over time` (positive = strategy getting worse)

#### Status verdict thresholds
- Green: `mean(Divergence) < 0.5`
- Amber: `0.5 ≤ mean(Divergence) ≤ 1.0`
- Red: `mean(Divergence) > 1.0`

### Edge cases to handle
- Fewer than 20 paper trading days: return "insufficient forward history"
- Paper trading curve is empty: return None, "paper trading not started"
- Mismatched date ranges: align on overlapping dates only
- Zero volatility period: use minimum volatility floor (1e-8)
- Negative divergence (forward outperforms): still valid, flag as positive

---

## `backend/app/studio_v2/data_studio/catalog.py`

**Features covered:** F6.6 (Data Catalog), F6.9 (Custom Data Upload), F6.10 (Data Freshness Monitor)

**Imports from:** `shared.data_loader`

**Phase:** Phase 3

### Classes

#### `DataCatalog`
**Description:** Searchable, filterable catalog of every data source. Each entry: source name, type, coverage universe, date range, update frequency, last successful update, quality issues.
**Key methods:**
- `register_source(name, source_type, metadata) -> None`
- `get_catalog(filters: dict = None) -> List[SourceEntry]`
- `search_catalog(query: str) -> List[SourceEntry]`
- `get_source_quality(name: str) -> QualityReport`
- `get_coverage_summary() -> CoverageSummary`
- `get_data_access_expression(source_name: str) -> str`

#### `CustomDataUploader`
**Description:** Handles CSV upload with auto-detect date format. Registers numeric columns as `custom.field_name`. Aligns to trading calendar, forward-fills gaps (1 day default, 5 max).
**Key methods:**
- `upload_csv(file_content: bytes, filename: str) -> UploadResult`
- `auto_detect_date_format(df: DataFrame) -> str`
- `align_to_trading_calendar(df, date_col) -> DataFrame`
- `forward_fill_gaps(df, max_fill_days: int = 1) -> DataFrame`
- `register_custom_field(field_name, source_name, metadata) -> None`
- `generate_validation_report(df) -> dict`

#### `DataFreshnessMonitor`
**Description:** Daily check of every automated data source at market close.
**Key methods:**
- `check_all_sources() -> Dict[str, FreshnessStatus]`
- `check_source(source_name: str) -> FreshnessStatus`
- `get_freshness_board() -> DataFrame`
- `get_run_metadata_tag() -> dict`
- `get_alerts() -> List[AlertEntry]`
- `record_backtest_freshness(run_id: str) -> None`

### Data it reads/writes
- **Reads:** All parquet data sources (via data_loader); user-uploaded CSV files; freshness metadata
- **Writes:** `data_catalog`, `data_freshness_log`, `custom_data_fields` DB tables
- **Parquet:** User uploads stored as parquet in `backend/data/custom/`

### Key formulas
None — catalog management is data infrastructure.

### Edge cases to handle
- CSV with no date column: return error with suggested detection
- CSV with all missing values: reject with "no usable data"
- Date format ambiguous (01/02/2023): default month-first with override
- Forward-fill gap exceeds max_fill_days: leave as NaN, report
- Custom field name collides: append `_2`, `_3` etc.

---

## `backend/app/studio_v2/data_studio/explorer.py`

**Features covered:** F6.7 (Data Explorer), F6.8 (Missing Data Heatmap)

**Imports from:** `shared.data_loader`

**Phase:** Phase 3

### Classes

#### `DataExplorer`
**Description:** Visual data inspection: OHLCV candlestick, volume, rolling vol (Garman-Klass), rolling Sharpe, distribution, anomaly detection.
**Key methods:**
- `get_primary_series(ticker, start, end) -> DataFrame`
- `get_derived_series(ticker, series_type, start, end) -> Series`
- `get_secondary_overlay(primary, secondary, start, end) -> DataFrame`
- `get_distribution(returns) -> DistributionStats`
- `get_anomalies(ticker, start, end) -> DataFrame`

#### `MissingDataHeatmap`
**Description:** N tickers × T dates heatmap, Canvas-rendered (500 × 5yrs = 630K cells).
**Key methods:**
- `get_heatmap_data(tickers, start, end) -> dict`
- `classify_cell_status(has_data, is_anomalous) -> str`
- `get_systematic_exclusion_dates(threshold=0.8) -> List[date]`
- `get_ticker_exclusion_dates(ticker) -> List[date]`

#### `DistributionStats`
**Description:** `mean, std, skewness, excess_kurtosis, p1, p99, jarque_bera_stat, jarque_bera_p, histogram_bins, qqplot_data`

### Functions

#### `garman_klass_vol(high, low, close, open, window=21) -> Series`
**Logic:** `√(252/N × Σ[0.5 × (ln(H/L))² - (2×ln2-1) × (ln(C/O))²])`

#### `detect_5sigma_moves(returns, window=63) -> List[AnomalyEvent]`
**Logic:** `z = (r_t - rolling_mean) / rolling_std`; flag `|z| > 5`

### Data it reads/writes
- **Reads:** `market_universe.parquet`, `category7_macro_regime.parquet`, `master_fundamentals.parquet`
- **Writes:** None — returns data for frontend rendering

### Key formulas

#### Garman-Klass realized volatility (annualized)
`σ_GK = √(252/N × Σ[0.5 × (ln(H/L))² - (2×ln2-1) × (ln(C/O))²])`

#### Jarque-Bera test
`JB = (T/6) × (S² + (K-3)²/4)`; JB ~ χ²(2) under normality

### Edge cases to handle
- Ticker not found: return "ticker not in universe"
- Missing high/low/open for Garman-Klass: fall back to close-to-close vol
- 500+ tickers for heatmap: truncate, warn
- Empty date range: return empty series

---

## `backend/app/studio_v2/data_studio/universe.py`

**Features covered:** F6.1 (Filter Stack Interface), F6.3 (Time-Varying Universe Viewer)

**Imports from:** `shared.data_loader`

**Phase:** Phase 3

### Classes

#### `UniverseBuilder`
**Description:** Filter stack pipeline. Filters: market cap bounds, ADV minimum, min share price, GICS sector, exchange, float-adjusted market cap percentile, custom expression.
**Key methods:**
- `apply_filter_stack(filters: List[FilterCard], date: date) -> DataFrame`
- `apply_market_cap_filter(tickers, min_cap, max_cap, date) -> DataFrame`
- `apply_adv_filter(tickers, min_adv, date) -> DataFrame`
- `apply_price_filter(tickers, min_price, date) -> DataFrame`
- `apply_sector_filter(tickers, include, exclude) -> DataFrame`
- `apply_exchange_filter(tickers, exchanges) -> DataFrame`
- `apply_float_filter(tickers, percentile_min, percentile_max, date) -> DataFrame`
- `apply_custom_expression(tickers, expression, date) -> DataFrame`
- `count_by_filter(filters, date) -> List[int]`
- `save_universe_definition(name, filters) -> str`

#### `TimeVaryingUniverse`
**Description:** Heatmap, entry/exit event log, Jaccard similarity between universe configs.
**Key methods:**
- `get_heatmap_data(universe_id, start, end) -> dict`
- `get_entry_exit_events(universe_id, start, end) -> DataFrame`
- `compute_jaccard_similarity(universe_a, universe_b, frequency='M') -> Series`
- `get_stock_sorted_by_market_cap(tickers, date) -> List[str]`

### Functions

#### `get_current_count(universe_id, date) -> int`
**Logic:** Loads universe definition, applies filter stack, returns `len(result)`

### Data it reads/writes
- **Reads:** `market_universe.parquet`, `master_fundamentals.parquet`
- **Writes:** `universe_definitions`, `universe_snapshots` DB tables

### Key formulas

#### Jaccard similarity
`J(U_A, U_B) = |U_A ∩ U_B| / |U_A ∪ U_B|`

### Edge cases to handle
- Empty filter stack: return full universe
- Filter removes all tickers: flag "no tickers survive"
- Market cap data unavailable: exclude from cap-based filters
- Heatmap >500 tickers: sample to 500, warn

---

## `backend/app/studio_v2/factors/diagnostics.py`

**Features covered:** F4.5 (Crowding Monitor), F4.6 (Half-Life Decay Tracking), F4.7 (Orthogonalization), F4.8 (Interaction Screener)

**Imports from:** `factors.evaluator`, `shared.data_loader`

**Phase:** Phase 2

### Classes

#### `CrowdingMonitor`
**Description:** Contemporaneous crowding via factor ETF AUM growth rate. Factor→ETF mapping: momentum→MTUM, value→VLUE, low-vol→USMV, quality→QUAL, size→IJR.
**Key methods:**
- `compute_crowding_percentile(factor_returns) -> CrowdingResult`
- `map_factor_to_etf(factor_returns) -> str`
- `get_aum_growth_percentile(etf_ticker) -> float`
- `get_traffic_light(percentile) -> str` (red > 80th, amber 50-80th, green < 50th)
- `get_historical_crowding_timeseries(etf_ticker) -> Series`

#### `HalfLifeDecayTracker`
**Description:** Recomputes IC decay half-life on rolling 2-year windows, 6-month steps.
**Key methods:**
- `compute_half_life_over_vintage(expression, start, end) -> DecayResult`
- `compute_half_life_for_window(scores, forward_returns, horizons) -> float`
- `fit_linear_regression(half_lives, vintages) -> RegressionResult`
- `get_degradation_verdict(slope, p_value) -> str`

#### `OrthogonalizationPanel`
**Description:** Gram-Schmidt sequential orthogonalization against 40 baseline factors.
**Key methods:**
- `orthogonalize(factor_scores, baseline_factors) -> OrthogonalizationResult`
- `_gram_schmidt_step(residual, basis_factor) -> Series`
- `compute_novelty_fraction(original_icir, orth_icir) -> float`

#### `InteractionScreener`
**Description:** Tests multiplicative interactions: factor_A × factor_B, cross-sectionally z-scored.
**Key methods:**
- `compute_interaction(factor_a, factor_b) -> InteractionResult`
- `cross_sectional_zscore(interaction) -> Series`

### Data it reads/writes
- **Reads:** ETF AUM data, 40 baseline factor returns (via data_loader), factor expression results from evaluator
- **Writes:** None — returns diagnostic results for frontend

### Key formulas

#### Crowding percentile
`Percentile = rank(AUM_growth_rate_13wk) / total_periods × 100`

#### Gram-Schmidt orthogonalization
For factor f and basis factors b₁...b₄₀:
1. `r₁ = f - β₁b₁` where `β₁ = cov(f,b₁)/var(b₁)`
2. Continue through all 40 factors
3. Final residual = orthogonalized factor

#### Interaction factor
`Interaction_t = zscore(FactorA_t × FactorB_t)` (cross-sectional z-score)

#### Half-life formulas
- Linear: `IC(h) = IC₀ - λh` → half-life = `IC₀/(2λ)`
- Exponential: `IC(h) = IC₀×exp(-λh)` → half-life = `ln(2)/λ`
- Hyperbolic: `IC(h) = IC₀/(1+λh)` → half-life = `1/λ`

### Edge cases to handle
- Factor style mapping all correlations < 0.3: default equal-weight, label "unclear"
- Orthogonalization with collinear factor: residual variance→0, IC→0, "fully redundant"
- Fewer than 2 years data for half-life tracking: insufficient windows
- Interaction of identical factors: flag as "trivial — factor squared"

---

## `backend/app/studio_v2/factors/evaluator.py`

**Features covered:** F4.1 (Expression Editor evaluation), F4.2 (Instant IC Diagnostics), F4.3 (IC Decay Curve), F4.4 (Cross-Sectional Distribution), F4.9 (Regime-Conditional IC)

**Imports from:** `shared.data_loader`, `factors.library`

**Phase:** Phase 2

### Classes

#### `FactorExpressionEvaluator`
**Description:** Parses and evaluates factor expressions using curated operator library.
**Key methods:**
- `evaluate(expression, universe_id, start, end) -> EvaluationResult`
- `validate_expression(expression) -> ValidationResult`
- `_parse_expression(expression) -> ast.Module`
- `_compute_time_series_operator(op_name, args, window) -> Series`
- `_compute_cross_sectional_operator(op_name, args) -> DataFrame`
- `load_data(fields, universe_id, start, end) -> PanelData`

#### `InstantIcDiagnostics`
**Description:** Naive IC, Purged K-Fold IC, Look-Ahead Inflation, IC-IR, IC t-stat, p-value.
**Key methods:**
- `compute_all(scores, forward_returns, embargo=10, n_folds=10) -> IcResult`
- `compute_naive_ic(scores, forward_returns, horizon) -> Series`
- `compute_purged_kfold_ic(scores, forward_returns, n_folds=10, embargo=10) -> float`
- `compute_icir(ic_values) -> float`
- `compute_ic_tstat(icir, n_periods) -> float`
- `compute_pvalue(t_stat) -> float`
- `color_code_pvalue(p) -> str` (green < 0.05, amber 0.05-0.10, red >= 0.10)

#### `IcDecayCurve`
**Description:** IC at horizons 1/5/10/21/42/63/126/252, three decay models, best by AIC.
**Key methods:**
- `compute_decay_curve(scores, forward_returns, horizons) -> DecayCurveResult`
- `fit_linear_decay(ic_at_h) -> DecayModelFit` — `IC(h) = IC₀ - λh`
- `fit_exponential_decay(ic_at_h) -> DecayModelFit` — `IC(h) = IC₀×exp(-λh)`
- `fit_hyperbolic_decay(ic_at_h) -> DecayModelFit` — `IC(h) = IC₀/(1+λh)`
- `select_best_model(fits) -> str` — by AIC
- `compute_half_life(fit) -> float`
- `compute_optimal_rebalance(horizons, ic_values, cost_bps) -> int`
- `bootstrap_confidence(ic_at_h, n=1000) -> dict`

#### `CrossSectionalDistribution`
**Description:** Histogram, QQ-plot, normality test, winsorized IC.
**Key methods:**
- `compute_distribution(scores, date) -> DistributionResult`
- `compute_stats(scores) -> dict`
- `compute_qqplot(scores, n_points=100) -> List[Point]`
- `jarque_bera_test(scores) -> tuple`
- `compute_winsorized_ic(scores, forward_returns, pct=0.01) -> float`

#### `RegimeConditionalIC`
**Description:** 3-state HMM on VIX + equal-weighted returns, IC per regime.
**Key methods:**
- `fit_hmm(returns, vix_levels) -> HMMResult` — Baum-Welch EM
- `assign_states(hmm) -> Series` — Viterbi algorithm
- `compute_regime_ic(scores, forward_returns, states) -> DataFrame`
- `get_regime_independence_verdict(regime_ics) -> str`

### Functions

#### `spearman_rank_correlation(x, y) -> float`
#### `compute_forward_returns(close, horizon) -> DataFrame`

### Data it reads/writes
- **Reads:** `market_universe.parquet`, `category7_macro_regime.parquet` (VIX), `ff5_daily.parquet`
- **Writes:** None — returns evaluation results for frontend

### Key formulas

#### Naive IC
`IC_naive = mean_t(Spearman_rank(factor_scores_t, returns_{t→t+H}))`

#### Purged K-Fold IC
Split into K folds. For each test fold, purge training observations with label-formation overlap with test. Apply 10-day embargo after test fold. Compute fold-wise IC, average across folds.

#### Look-Ahead Inflation
`Inflation = IC_naive - IC_purged`

#### IC-IR, t-stat, p-value
`ICIR = mean(IC_fold) / std(IC_fold)`
`t = ICIR × √(num_test_periods)`
p-value: two-tailed under standard normal

#### IC decay models
- Linear: `IC(h) = IC₀ - λh`
- Exponential: `IC(h) = IC₀ × exp(-λh)`
- Hyperbolic: `IC(h) = IC₀ / (1 + λh)`
- Model selection by AIC

#### Optimal rebalancing frequency
`h* = argmax_h[IC(h) - 2 × cost_bps / 10000]`

### Edge cases to handle
- Expression syntax error: return parse error with suggestion
- All factor scores NaN for a date: exclude date
- Single horizon available: cannot fit 3 models
- All factor scores identical (zero variance): IC = 0
- HMM fails to converge: fall back to k-means regime labels

---

## `backend/app/studio_v2/factors/library.py`

**Features covered:** F4.10 (Factor Comparison Table), F4.11 (Internal Library)

**Imports from:** `factors.evaluator`, `factors.diagnostics`

**Phase:** Phase 2

### Classes

#### `FactorLibrary`
**Description:** CRUD for internal factor library. 40 baseline factors pre-loaded. Validation gates: IC t-stat > 2.0, orthogonalized IC-IR > 0.04, half-life 3-90 days, crowding < 80th.
**Key methods:**
- `get_all_factors() -> List[FactorRecord]`
- `get_baseline_factors() -> List[FactorRecord]`
- `get_user_factors() -> List[FactorRecord]`
- `add_factor(name, expression, metrics, user_name=None) -> str` — validates gates, inserts
- `validate_factor(metrics) -> ValidationResult`
- `remove_factor(factor_id) -> None`
- `get_factor_by_id(factor_id) -> FactorRecord`
- `get_factor_by_expression_hash(hash) -> FactorRecord`
- `compute_expression_hash(expression) -> str` — SHA-256
- `get_factor_for_comparison() -> DataFrame`
- `compute_quality_rating(metrics, weights=None) -> float`

#### `FactorComparisonTable`
**Description:** Session-scoped comparison table.
**Key methods:**
- `add_session_factor(expression, metrics) -> None`
- `get_combined_table(include_baseline=True) -> DataFrame`
- `sort_by(column, ascending=False) -> None`
- `get_quality_color(rating) -> str`

### Data it reads/writes
- **Reads:** Factor return parquets (for baseline metrics); factor expression evaluation results
- **Writes:** `factor_library` DB table — `(id, name, expression, expression_hash UNIQUE, naive_ic, purged_ic, icir, ic_tstat, ic_pvalue, half_life, crowding_pctile, orthogonalized_icir, regime_universality, date_added, is_baseline, is_active)`

### Key formulas

#### Quality rating (default weights)
`Quality = 0.30×purged_ic + 0.30×icir + 0.20×min(half_life/90,1) + 0.20×regime_universality`

#### Validation gates (all must pass)
1. `|IC t-stat| > 2.0`
2. `orthogonalized IC-IR > 0.04`
3. `3 ≤ half_life ≤ 90` trading days
4. `crowding percentile < 80th`

### Edge cases to handle
- Duplicate expression (by SHA-256): reject with name reference
- All validation gates fail: show which specific gates failed
- Soft-deleted factor: excluded from table but stays in orthogonalization basis

---

## `backend/app/studio_v2/optimizer/cpcv.py`

**Features covered:** F5.4 (CPCV + Deflated Sharpe)

**Imports from:** `backtest.engine`, `backtest.metrics`, `optimizer.verdict`, `shared.monte_carlo`

**Phase:** Phase 2

### Classes

#### `CPCV`
**Description:** Combinatorial Purged Cross-Validation with N=8, k=2 (28 paths). Embargo sensitivity at 0/5/10/21 trading days.
**Key methods:**
- `run(config: CPCVConfig) -> CPCVResult`
- `generate_splits(n_groups, k_test) -> List[Tuple]` — all C(N,k) test group index combinations
- `create_group_indices(n_dates, n_groups) -> List[Tuple]` — splits dates into N groups
- `run_backtest_on_split(train_dates, test_dates, strategy, config) -> Series`
- `compute_cpcv_sharpe(oos_returns) -> CPCVSharpeResult`
- `compute_dsr(cpcv_sharpe, returns_dist, m_trials) -> float`
- `compute_pbo(oos_returns) -> float`
- `run_embargo_sensitivity(strategy, config, embargo_lengths=[0,5,10,21]) -> DataFrame`

#### `CPCVConfig`
**Description:** `n_groups: int` (4/6/8), `k_test: int` (1/2), `strategy_file`, `backtest_config`, `embargo_lengths`, `m_trials`

### Functions

#### `compute_sr0(m_trials, var_sr, gamma=0.5772) -> float`
**Logic:** `SR₀ ≈ √(Var[SR]) × ((1-γ)Φ⁻¹(1-1/M) + γΦ⁻¹(1-1/(M·e)))`

### Data it reads/writes
- **Reads:** Strategy files, OHLCV (via engine→data_loader)
- **Writes:** `cpcv_results` DB table; reads `optimizer_trials` for M count

### Key formulas

#### CPCV total paths
`C(N,k) = N! / (k! × (N-k)!)` — for N=8, k=2: 28 paths (hard cap)

#### DSR formula
`DSR = Φ[(SR_CPCV - SR₀) × √(T-1) / √(1 - γ₃×SR_CPCV + (γ₄-1)/4 × SR_CPCV²)]`
where SR₀ = expected max Sharpe under IID noise across M trials

#### PBO formula
`PBO = (1/N_splits) × Σ_i I{Sharpe_oos,i < median({Sharpe_oos})}`

### Edge cases to handle
- Data too short for N=8, k=2: reduce N automatically
- M=1 (no prior optimization): DSR approaches PSR
- All paths same Sharpe: PBO = 0 or 1, DSR=Φ(0)=0.5
- Strategy fails on some splits: exclude, warn

---

## `backend/app/studio_v2/optimizer/search.py`

**Features covered:** F5.2 (Bayesian Parameter Search), F5.3 (Walk-Forward Optimization)

**Imports from:** `backtest.engine`, `backtest.metrics`, `shared.liquidity`, `robustness.tests`, `optimizer.verdict`

**Phase:** Phase 2

### Classes

#### `BayesianOptimizer`
**Description:** Bayesian search via Optuna TPE. Trial budgets: 50/200/500. Objective: Sharpe, Sharpe-per-Capacity-Dollar, Sortino, Calmar, IR.
**Key methods:**
- `run(config: OptimizerConfig) -> OptimizerResult`
- `_objective(trial, config) -> float` — samples params, runs backtest
- `_compute_sharpe_per_capacity_dollar(params) -> float` — raw_Sharpe × capacity_ceiling_billions
- `_compute_capacity_ceiling(trade_log, params) -> float`
- `_trajectory_callback(study, trial) -> None`
- `run_perturbation_grid(optimal_params, pct=0.30, n_steps=5) -> DataFrame`
- `compute_stability_score(perturbation_results, optimal_sharpe) -> float`

#### `WalkForwardOptimizer`
**Description:** IS/OOS windows, ~500 backtests, regime-conditional IS/OOS ratio.
**Key methods:**
- `run(config: WalkForwardConfig) -> WalkForwardResult`
- `generate_windows(is_months, oos_months, mode, date_range) -> List[Window]`
- `run_is_search(is_start, is_end, config) -> ISResult`
- `evaluate_oos(oos_start, oos_end, optimal_params, config) -> OOSResult`
- `compute_stitched_oos_curve(windows) -> Series`
- `compute_mean_isoos_ratio(windows) -> tuple`
- `compute_regime_conditional_isoos(windows) -> DataFrame`

#### `OptimizerConfig`
**Description:** `strategy_file, backtest_config, parameters: List[SearchParameter], trial_budget, objective, capacity_data`

#### `SearchParameter`
**Description:** `name, type (continuous/discrete/categorical), current_value, suggested_range, values, included`

#### `WalkForwardConfig`
**Description:** `is_months, oos_months, mode, objective, trials_per_window, strategy_file, backtest_config, parameters`

### Functions

#### `infer_parameter_range(current_value) -> Tuple[float,float]`
**Logic:** `[round(val×0.5, 2sig), round(val×1.5, 2sig)]`

### Data it reads/writes
- **Reads:** Strategy files, OHLCV (via engine), ADV/liquidity data
- **Writes:** `optimizer_trials`, `optimizer_sessions`, `walkforward_results` DB tables

### Key formulas

#### Sharpe-per-Capacity-Dollar objective
`Objective = raw_Sharpe × capacity_ceiling_in_billions`
Example: Sharpe 2.0 × $50M = 0.1; Sharpe 1.2 × $5B = 6.0.

#### Walk-Forward IS/OOS ratio
`Ratio_window = OOS_Sharpe / IS_Sharpe`
Color: green > 0.65, amber 0.35-0.65, red < 0.35

#### Parameter stability score
`Stability = count(Sharpe_grid > 0.5×optimal_Sharpe) / total_grid_points`

### Edge cases to handle
- No parameters toggled on: error
- All trials same objective value: flag "insufficient parameter sensitivity"
- Walk-Forward insufficient history: shift start, warn
- Capacity ceiling = $0 (no trades): SCD objective = 0

---

## `backend/app/studio_v2/optimizer/verdict.py`

**Features covered:** F5.5 (Auto-Overfitting Verdict), F5.6 (Trial Registry)

**Imports from:** `optimizer.cpcv`, `optimizer.search`, `backtest.lineage`

**Phase:** Phase 2

### Classes

#### `OverfittingVerdict`
**Description:** Traffic-light: DSR > 0.5, PBO < 25%, IS/OOS > 0.60, stability > 65%.
**Key methods:**
- `compute_verdict(dsr, pbo, mean_isoos, stability) -> VerdictResult`
- `check_criterion(value, threshold, direction) -> CriterionResult`
- `get_recommendation(failed_criteria) -> str`

#### `VerdictResult`
**Description:** `color (green/amber/red), criteria, passed_count, failed_count, recommendations`

#### `TrialRegistry`
**Description:** Permanent log of every optimization trial.
**Key methods:**
- `record_trial(trial: TrialRecord) -> str`
- `get_trial(trial_id) -> TrialRecord`
- `get_session_trials(session_id) -> List[TrialRecord]`
- `get_best_trial(strategy_hash, objective_name) -> TrialRecord`
- `get_trial_count(strategy_hash) -> int` (returns M for DSR)
- `get_trials_for_lineage(strategy_hash) -> List[dict]`
- `get_search_path(session_id) -> DataFrame`

### Data it reads/writes
- **Reads:** CPCV results, Walk-Forward results, Bayesian results
- **Writes:** `optimizer_trials`, `optimizer_verdicts` DB tables

### Key formulas

#### Verdict thresholds
| Criterion | Threshold |
|-----------|-----------|
| DSR | > 0.5 |
| PBO | < 25% |
| IS/OOS ratio | > 0.60 |
| Parameter stability | > 65% |

All four pass → Green, three pass → Amber, ≤ two → Red.

### Edge cases to handle
- Not all modes run: partial verdict on available criteria
- All metrics NaN: return NoData
- PBO = 50% (chance): fails, recommend investigation

---

## `backend/app/studio_v2/robustness/scorer.py`

**Features covered:** F3.9 (Composite Robustness Score and PDF Report)

**Imports from:** `robustness.tests`, `backtest.metrics`

**Phase:** Phase 2

### Classes

#### `CompositeRobustnessScorer`
**Description:** Single score 0-100. Weights: Parameter Stability 30%, Timing 20%, Cost Break-Even 25%, Capacity 25%.
**Key methods:**
- `compute_composite_score(core_results) -> CompositeScore`
- `normalize_test_score(raw_value, test_type) -> float`
- `get_verdict(composite) -> str` — 75-100 Robust, 50-74 Marginal, <50 Do not advance

#### `RobustnessReport`
**Description:** Generates PDF using reportlab.
**Key methods:**
- `generate_pdf(composite, extended=None, capacity=None, charts=None) -> bytes`
- `_build_title_page(doc, run_info)`
- `_build_executive_summary(doc, composite, capacity)`
- `_build_test_page(doc, test_name, score, chart, diagnosis)`
- `_build_diagnosis_section(doc, diagnoses)`
- `_generate_diagnosis(test_name, score) -> str`

### Functions

#### `format_performance_metric(value, metric_type) -> str`
**Logic:** Sharpe/Sortino/Calmar → 3 decimals; drawdown → 2 decimals.

### Data it reads/writes
- **Reads:** Robustness test results, run metadata from lineage
- **Writes:** `robustness_reports` DB table; PDF files in `exports/`

### Key formulas

#### Composite score
`Composite = 0.30×S_param + 0.20×S_timing + 0.25×S_cost + 0.25×S_capacity`

#### Verdict thresholds
- 75-100: Robust (advance to Optimizer)
- 50-74: Marginal (return to Algorithm Lab)
- < 50: Do not advance

### Edge cases to handle
- Extended diagnostics not run: exclude from report
- Test produced NaN/error: score = 0 with "test failed" diagnosis
- All four tests scored 0: composite = 0, "Do not advance"

---

## `backend/app/studio_v2/robustness/tests.py`

**Features covered:** F3.2 (Parameter Stability Surface), F3.3 (Entry Timing Perturbation), F3.4 (Universe Perturbation), F3.5 (Noise Injection — Extended), F3.6 (Cost Break-Even), F3.7 (Capacity & Turnover Stress), F3.8 (Extended Diagnostics — Regime Decomposition, OOS Boundary Sensitivity)

**Imports from:** `backtest.engine`, `backtest.metrics`, `shared.monte_carlo`, `shared.liquidity`, `shared.data_loader`, `backtest.lineage`

**Phase:** Phase 2

### Classes

#### `ParameterStabilityTest`
**Description:** Core Test 1. 21-point grid per param (50%-150%), 2-param default (441 runs).
**Key methods:**
- `run(strategy_file, config) -> ParameterStabilityResult`
- `identify_numeric_params(strategy_file) -> List[str]`
- `build_param_grid(params, current_values, n_points=21) -> List[dict]`
- `run_grid_parallel(param_grid, config) -> DataFrame`
- `compute_heatmap_data(results, param_a, param_b) -> dict`
- `compute_stability_score(results, optimal_sharpe) -> float`

#### `TimingPerturbationTest`
**Description:** Core Test 2. k ∈ {1,3,5,10}, 1000 sims per magnitude (4000 total).
**Key methods:**
- `run(trade_log, n_simulations=1000) -> TimingPerturbationResult`
- `_single_simulation(trade_log, k) -> Series`
- `compute_timing_sensitivity_score(baseline_sharpe, k5_sharpes) -> float`

#### `UniversePerturbationTest`
**Description:** Core Test 3. 500 samples per dropout (10%, 20%, 30%), sector-matched replacement.
**Key methods:**
- `run(original_universe, config, n_samples=500) -> UniversePerturbationResult`
- `drop_and_replace(tickers, dropout_pct, sector_map) -> List[str]`
- `compute_concentration_stocks(results, tickers) -> List[str]`
- `compute_universe_stability_score(baseline_sharpe, results_at_20pct) -> float`

#### `NoiseInjectionTest` (Extended)
**Description:** Test 7. Multiplicative Gaussian noise at 4 levels, 500 sims each.
**Key methods:**
- `run(strategy_file, config, n_simulations=500) -> NoiseInjectionResult`
- `inject_noise(prices, sigma) -> DataFrame`
- `find_fragility_threshold(results_by_level) -> float`
- `compute_noise_tolerance(results_at_0_005, baseline_sharpe) -> float`

#### `CostBreakEvenTest`
**Description:** Core Test 4. 20 cost levels 0-50 bps, linear regression for break-even.
**Key methods:**
- `run(strategy_file, config, cost_levels=20, max_cost_bps=50) -> CostBreakEvenResult`
- `compute_breakeven_cost(cost_sharpes) -> float`
- `compute_cost_robustness_score(breakeven, realistic_band) -> float`

#### `CapacityStressTest`
**Description:** Core Test 5. AUM sweep $1M-$10B, 20 log-spaced points, Almgren-Chriss impact.
**Key methods:**
- `run(trade_log, adv_data, vol_data, lambda_dict) -> CapacityResult`
- `simulate_aum_level(trades, aum, adv, vol, lambda_dict, fixed_cost) -> dict`
- `compute_impact(trade_size, adv, sigma, lam) -> float`
- `find_capacity_ceiling(aum_results) -> float`
- `compute_slippage_table(aum_results) -> DataFrame`

#### `RegimeDecompositionTest` (Extended)
**Description:** Test 8. 3-state HMM on VIX + 21d realized vol.
**Key methods:**
- `run(returns, vix_series) -> RegimeDecompositionResult`
- `fit_hmm(features, n_states=3) -> HMMResult`
- `assign_states(hmm) -> Series`
- `compute_per_regime_performance(returns, states) -> DataFrame`
- `compute_regime_universality_score(per_regime_sharpes, unconditional_sharpe) -> float`

#### `OOSBoundarySensitivityTest` (Extended)
**Description:** Test 9. Five splits: baseline, ±3mo, ±6mo.
**Key methods:**
- `run(strategy, config, baseline_split, shifts=[-6,-3,0,3,6]) -> BoundarySensitivityResult`
- `compute_boundary_sensitivity_score(oos_sharpes) -> float`

### Functions

#### `get_realistic_cost_band(tickers, adv_data, mcap_data) -> Tuple[float,float]`
Large-cap 2-5 bps, mid-cap 5-15 bps, small-cap 15-30 bps.

### Data it reads/writes
- **Reads:** `market_universe.parquet`, `master_fundamentals.parquet`, `category7_macro_regime.parquet`, trade logs, strategy files
- **Writes:** `robustness_test_results` DB table

### Key formulas

#### Parameter Stability grid
21 points: `value_i = original × (0.5 + i×1.0/20)` for i=0..20

#### Stability score
`Stability = count(Sharpe > 0.5×max_Sharpe) / 441`; frag if < 20%

#### Timing sensitivity
`Sensitivity = median(Sharpe_k5) / baseline_Sharpe`; >0.80 timing-independent, <0.40 timing-critical

#### Universe stability
`Stability = count(|Sharpe - baseline| < 0.3) / 500` at 20% dropout; >70% diversified, <40% concentrated

#### Noise injection
`P_noisy(t) = P(t) × (1 + ε_t)`, `ε_t ~ N(0,σ²)`, σ ∈ {0.001,0.003,0.005,0.010}

#### Cost break-even
Linear regression: `Sharpe = α + β×cost_bps`; breakeven = `-α/β`

#### Almgren-Chriss impact
`impact(bps) = λ × σ × (trade/ADV)^(3/5)`
λ: large-cap 4×10⁻⁶, mid-cap 2.4×10⁻⁵, small-cap 1.2×10⁻⁴

#### Regime universality
`Universality = min_regime_Sharpe / unconditional_Sharpe`

#### OOS boundary sensitivity
`Sensitivity = std(OOS_Sharpe_across_5_splits)`; <0.3 low, >0.8 high

### Edge cases to handle
- 0 numeric params: "no numeric parameters to test"
- 0 trades in trade log: skip timing perturbation and capacity
- Break-even > 50 bps: "profitable at all cost levels"
- < 10 tickers in universe: reduce dropout fractions
- Regime decomposition < 252 days: fall back to tercile classification

---

## `backend/app/studio_v2/router.py`

**Features covered:** All features (F1-F6)

**Imports from:** All service modules

**Phase:** Phase 1 (skeleton), Phase 2 (F3/F4/F5), Phase 3 (F6), Phase 4 (F1.9/F2.8)

### Classes

#### `Router(APIRouter)`
**Description:** Single FastAPI/APIRouter. Thin layer — validates requests, calls service function, returns response.

**Key endpoint groups:**

**Algorithm Lab (F1):**
- `POST /api/v2/algorithm-lab/execute` — run code in kernel (F1.2)
- `GET /api/v2/algorithm-lab/variables` — variable inspector state (F1.5)
- `GET /api/v2/algorithm-lab/lint` — lookahead linter (F1.1)
- `POST /api/v2/algorithm-lab/push-to-backtest` — one-click push (F1.8)
- `POST /api/v2/algorithm-lab/paper-trade/run` — daily paper trade (F1.9)
- `GET /api/v2/algorithm-lab/paper-trade/status/{name}` — status (F1.9)
- `POST /api/v2/algorithm-lab/kernel/restore/{run_id}` — restore checkpoint (F1.7)

**Backtest Studio (F2):**
- `POST /api/v2/backtest/run` — run simulation (F2.2)
- `GET /api/v2/backtest/result/{run_id}` — full results (F2.2)
- `GET /api/v2/backtest/metrics/{run_id}` — Honest Performance Card (F2.4)
- `GET /api/v2/backtest/lineage` — lineage graph (F2.6)
- `GET /api/v2/backtest/lineage/search` — search runs (F2.6)
- `GET /api/v2/backtest/lineage/diff/{a}/{b}` — diff two runs (F2.6)
- `POST /api/v2/backtest/lineage/tag/{run_id}` — set tag (F2.6)
- `POST /api/v2/backtest/export/{run_id}` — export PDF/LaTeX/CSV/JSON (F2.7)
- `GET /api/v2/backtest/reconciliation/{bt_id}/{pt_name}` — reconciliation (F2.8)

**Robustness Lab (F3):**
- `POST /api/v2/robustness/run-core-tests` — tests 1-5 (F3.2-F3.7)
- `POST /api/v2/robustness/run-extended` — extended diag (F3.8)
- `GET /api/v2/robustness/composite-score` — composite (F3.9)
- `GET /api/v2/robustness/report/{run_id}` — PDF report (F3.9)

**Factor Sandbox (F4):**
- `POST /api/v2/factors/evaluate` — evaluate expression (F4.1)
- `GET /api/v2/factors/ic-diagnostics` — IC diagnostics (F4.2)
- `GET /api/v2/factors/decay-curve` — IC decay (F4.3)
- `GET /api/v2/factors/distribution` — cross-sectional dist (F4.4)
- `GET /api/v2/factors/crowding` — crowding (F4.5)
- `GET /api/v2/factors/half-life-tracking` — half-life vintage (F4.6)
- `POST /api/v2/factors/orthogonalize` — Gram-Schmidt (F4.7)
- `POST /api/v2/factors/interaction` — interaction screener (F4.8)
- `GET /api/v2/factors/regime-ic` — regime-conditional IC (F4.9)
- `GET /api/v2/factors/library` — full library (F4.10)
- `POST /api/v2/factors/library/add` — add to library (F4.11)

**Optimizer (F5):**
- `POST /api/v2/optimizer/parse-params` — parse params (F5.1)
- `POST /api/v2/optimizer/bayesian-search` — Bayesian (F5.2)
- `POST /api/v2/optimizer/walk-forward` — Walk-Forward (F5.3)
- `POST /api/v2/optimizer/cpcv` — CPCV (F5.4)
- `GET /api/v2/optimizer/verdict` — auto-verdict (F5.5)
- `GET /api/v2/optimizer/trials` — trial history (F5.6)

**Data Studio (F6):**
- `POST /api/v2/data-studio/universe/build` — build universe (F6.1)
- `GET /api/v2/data-studio/universe/heatmap` — heatmap (F6.3)
- `GET /api/v2/data-studio/universe/jaccard` — Jaccard overlap (F6.3)
- `GET /api/v2/data-studio/explorer/series/{ticker}` — data explorer (F6.7)
- `GET /api/v2/data-studio/explorer/anomalies` — anomaly detection (F6.7)
- `GET /api/v2/data-studio/explorer/heatmap` — missing data (F6.8)
- `GET /api/v2/data-studio/catalog` — data catalog (F6.6)
- `POST /api/v2/data-studio/catalog/upload` — CSV upload (F6.9)
- `GET /api/v2/data-studio/freshness` — freshness board (F6.10)

---

## `backend/app/studio_v2/shared/data_loader.py`

**Features covered:** ALL features — the single data engine for every service.

**Imports from:** None (self-contained parquet I/O)

**Phase:** Phase 1

### Functions

#### `get_returns(tickers: List[str], start: date, end: date) -> DataFrame`
**Logic:** Reads `market_universe.parquet`, filters by ticker + date range, computes daily returns from adjusted close.

#### `get_ohlcv(ticker: str, start: date, end: date) -> DataFrame`
**Logic:** Reads `market_universe.parquet`, returns `[date, open, high, low, close, volume, adjusted_close, dollar_volume]`.

#### `get_all_tickers() -> List[str]`
**Logic:** Reads `market_universe.parquet`, extracts unique tickers.

#### `get_macro(series_name: str, start: date, end: date) -> Series`
**Logic:** Reads `category7_macro_regime.parquet`, filters by series name and date range.

#### `get_factor_returns(model: str = "ff5") -> DataFrame`
**Logic:** Reads appropriate parquet/CSV for the requested factor model ('ff3', 'ff5', 'momentum', 'aqr', 'global_3f', 'global_5f').

#### `get_market_cap(ticker: str, date: date) -> float`
**Logic:** Reads `master_fundamentals.parquet`, returns market cap closest to date.

#### `get_float(ticker: str) -> float`
**Logic:** Reads `master_fundamentals.parquet`, returns float shares.

### Data it reads/writes
- **Reads:** `market_universe.parquet` (282 MB, 4,158 tickers, 1996-2026) — primary OHLCV source
- **Reads:** `category7_macro_regime.parquet` (258 KB, 21 macro series)
- **Reads:** `ff5_daily.parquet` (691 B), `ff3_daily.parquet` (280 KB), `momentum_daily.parquet` (183 KB)
- **Reads:** `master_fundamentals.parquet` (32 MB)
- **Reads:** `Developed_*.csv` (global factors), `aqr_csv/*.csv` (36 AQR files)
- **Writes:** None — pure read-only data access layer

### Key formulas
None — data loading infrastructure. No formulas.

### Edge cases to handle
- Ticker not found: return empty DataFrame with columns
- Date range outside coverage: return empty
- Multiple tickers, some missing: return available, log warnings
- Parquet file not found: raise FileNotFoundError with path
- Large query (>1000 tickers): chunk reads
- Market cap data not on exact date: return closest date before

---

## `backend/app/studio_v2/shared/liquidity.py`

**Features covered:** F6.5 (Liquidity Reality Layer), consumed by F3.7, F5.2, F1.9

**Imports from:** `shared.data_loader`

**Phase:** Phase 3

### Classes

#### `LiquidityCalibrator`
**Description:** Almgren-Chriss λ calibrator per liquidity bucket via cross-sectional OLS. Cached monthly.
**Key methods:**
- `calibrate(date=None) -> Dict[str, float]` — OLS per bucket
- `compute_adv(ticker, date) -> float` — 63-day rolling
- `compute_realized_vol(ticker, date) -> float` — 21-day rolling
- `estimate_bid_ask_spread(ticker, date) -> float` — from HL ratio
- `get_liquidity_bucket(ticker, date) -> str` — large/mid/small by ADV decile
- `get_lambda(ticker, date) -> float`
- `cache_coefficients(date, lambda_dict) -> None`
- `load_cached_coefficients(date) -> dict`

### Functions

#### `almgren_chriss_impact(trade_size, adv, sigma, lam) -> float`
**Logic:** `impact_bps = lam × sigma × (trade/adv)^(3/5) × 10000`

### Data it reads/writes
- **Reads:** `market_universe.parquet`, `master_fundamentals.parquet`
- **Writes:** `liquidity_coefficients` DB table (cached monthly)

### Key formulas

#### Almgren-Chriss market impact
`Impact(bps) = λ × σ × (Trade/ADV)^(3/5) × 10000`

#### Liquidity buckets (by ADV decile)
- Large-cap: top 10%
- Mid-cap: 11-50%
- Small-cap: 51-100%

#### Default λ (when calibration data insufficient)
- Large-cap: 4×10⁻⁶
- Mid-cap: 2.4×10⁻⁵
- Small-cap: 1.2×10⁻⁴

#### Bid-ask spread estimation
`Spread ≈ 2 × (High - Low) / (High + Low)` (Covar & Shumway 2001)

### Edge cases to handle
- No trade data: use default λ values
- Bucket < 30 stocks: merge with adjacent bucket
- ADV = 0: exclude from calibration
- Trade/ADV > 0.5: cap, flag "extreme"
- σ = 0: use minimum floor 1e-4
- Cache refresh fails: continue with previous month

---

## `backend/app/studio_v2/shared/monte_carlo.py`

**Features covered:** F2.3 (Monte Carlo Engine) — consumed by Backtest Studio, Robustness Lab, Optimizer

**Imports from:** `shared.data_loader`

**Phase:** Phase 1

### Classes

#### `MonteCarloEngine`
**Description:** Single shared Monte Carlo engine. Three modes: Block Bootstrap, GARCH(1,1) Synthesis, Timing Perturbation. Total 15,000 simulated paths.
**Key methods:**
- `run_all(returns, trade_log=None) -> MonteCarloResult`
- `run_block_bootstrap(returns, n_paths=5000) -> BootstrapResult`
- `run_garch_synthesis(returns, n_paths=5000, horizon=252) -> GarchResult`
- `run_timing_perturbation(trade_log, shift_magnitudes=[1,3,5,10], sims_per=1000) -> PerturbationResult`
- `compute_sharpe_histogram(path_results) -> dict`
- `compute_luck_premium(actual_curve, synthetic_curves) -> float`

### Functions

#### `politis_romano_block_length(returns) -> int`
**Logic:** `argmin(MSE of spectral density estimator)` — Politis & White (2004) corrected.

#### `stationary_bootstrap(returns, block_length, n_paths, path_length=None) -> List[Series]`
**Logic:** Draws blocks of random geometric length (mean=block_length), concatenates.

#### `garch_11_mle(returns) -> dict`
**Logic:** MLE of `σ²_t = ω + α×ε²_{t-1} + β×σ²_{t-1}` (Bollerslev 1986).

#### `garch_simulate(params, n_paths, horizon) -> List[Series]`
**Logic:** Start `σ²_1 = ω/(1-α-β)`, iterate `σ²_{t+1} = ω + α×ε²_t + β×σ²_t`.

### Data it reads/writes
- **Reads:** Return series from engine result; trade log from engine
- **Writes:** `monte_carlo_results` DB table

### Key formulas

#### GARCH(1,1) process
`r_t = μ + ε_t`, `ε_t = σ_t × z_t`, `z_t ~ N(0,1)`
`σ²_t = ω + α×ε²_{t-1} + β×σ²_{t-1}`
Constraints: `ω > 0, α ≥ 0, β ≥ 0, α + β < 1`

#### Stationary Bootstrap (Politis-Romano)
Block length L ~ Geometric(θ) where θ = 1/block_length
Expected block length = block_length

#### Luck premium
`LuckPremium = actual_final_wealth - median(synthetic_final_wealths)`

### Edge cases to handle
- Series length < 252: reduce path_length, warn
- GARCH MLE fails to converge: fall back to method-of-moments init; if still fails, bootstrap only
- α+β ≥ 1 (non-stationary): cap at 0.999, warn
- Very short series (< 63 days): skip GARCH mode
- 0 trades in trade log: skip timing perturbation
- Block length > series length: cap at series_length/4
- Zero-variance series: flag "deterministic returns"

---

**Total: 22 files documented across 4 phases.**

**Phase 1 (Core Foundation — $49/mo):** `kernel.py`, `linter.py`, `engine.py`, `metrics.py`, `lineage.py`, `monte_carlo.py`, `data_loader.py`, `router.py`

**Phase 2 (Pro — $99/mo):** `tests.py`, `scorer.py`, `evaluator.py`, `diagnostics.py`, `library.py`, `search.py`, `cpcv.py`, `verdict.py`

**Phase 3 (Data Studio):** `universe.py`, `explorer.py`, `catalog.py`, `liquidity.py`

**Phase 4 (Paper Trading + Reconciliation):** `paper_trader.py`, `reconciliation.py`

**Files processed:** 22/22
