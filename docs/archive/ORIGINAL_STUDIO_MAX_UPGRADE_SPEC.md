# Original Studio Maximum Upgrade Specification

## Decision

The original single-workspace Studio becomes the only Studio product. Studio V2 is not retained as a separate interface. Its best validated capabilities may be transplanted into the original workflow, but its seven-route navigation, duplicated shells, and laboratory presentation are not carried forward.

The product remains one coherent workspace centered on a research session:

`Develop → Portfolio → Results → Validate → Factors → Replay`

Advanced analysis appears when relevant. It does not become a collection of disconnected dashboards.

## Product principles

1. One strategy, portfolio, dataset snapshot, and run context follows the user everywhere.
2. The editor and chart remain the dominant surface.
3. Every displayed number must come from real data or be explicitly unavailable.
4. Missing data never becomes a synthetic backtest or a false zero.
5. Common actions complete in one or two clicks.
6. Expensive diagnostics are bounded and opt-in.
7. No GPU is required for the core product.
8. The architecture stays small until measured scale requires another service.

## Current original Studio baseline

### Develop

Already present:

- Monaco strategy editor.
- Strategy execution.
- Candlestick chart with signals and trades.
- Indicators, custom overlays, drawings, patterns, and volume profile.
- Crosshair inspection and benchmark overlay.
- Strategy A/B comparison.
- Multi-chart layouts.
- Playback controls and event log.
- Slippage and commission controls.

### Tearsheet

Already present:

- Equity and drawdown.
- Performance and trade metrics.
- Monthly returns.
- Basic attribution and export presentation.

This becomes **Results**.

### Stress

Already present:

- Monte Carlo paths and distribution.
- Loss and ruin estimates.

This is merged into **Validate**. A separate Stress page is unnecessary.

### Validate

Already present:

- Walk-forward testing.
- In-sample and out-of-sample comparison.
- Fold results and performance degradation.

### Dynamics

Already present:

- Spectral, wavelet, entropy, fractal, volatility, regime, tail-risk, topology, and related visualizations.

The current implementation is too large and contains unverified or approximate outputs. Dynamics is removed as a primary page. Only a small set of validated models survives as an optional Analysis drawer.

### Replay

Already present:

- Historical step/play controls.
- Trade and signal context.
- Adjustable playback speed.

## Final workspace pages and features

## 1. Develop

### Keep and harden

- Monaco editor, chart, signals, drawings, overlays, A/B mode, benchmark comparison, layouts, and event log.
- Replace silent strategy fallbacks with visible errors.
- Replace synthetic fallback market data with an unavailable-data state.
- Calculate MAE, MFE, holding period, and trade statistics from actual fills.
- Limit layouts to useful presets: single, vertical split, horizontal split, and 2×2.

### Add

- Saved projects and strategies.
- Real file history and code diff.
- Run history with code, parameters, data snapshot, duration, output, and failure state.
- Compare two runs without rerunning either one.
- Parameter detection from strategy configuration.
- DataFrame and variable inspector.
- Problems/output/trades bottom panel.
- One-click backtest using the current session configuration.
- Reproducibility fingerprint for every run.
- Research hypothesis, notes, and tags attached to the project.
- Backtest-count and parameter-count overfitting warnings.

### Best Studio V2 transplants

- Typed error normalization.
- Request cancellation, timeout, and stale-response protection.
- Saved strategy repository.
- Run restoration using stored artifacts, without restoring an unsafe pickled process.
- Snippet library.
- Research journal attached to the active project.

## 2. Portfolio

This is the largest new user-facing capability.

### Portfolio construction

- Select multiple saved strategies.
- Select multiple assets or universes.
- Assign weights by strategy and asset.
- Equal weight.
- Inverse volatility.
- Risk parity.
- Minimum variance.
- Maximum diversification.
- User-defined weights and constraints.
- Long-only, long-short, gross exposure, and leverage controls.
- Rebalancing frequency and drift bands.

### Portfolio testing

- Configurable history, with five years as a convenient preset rather than a hard-coded period.
- Portfolio and benchmark equity.
- Strategy and asset contribution.
- Correlation and diversification.
- Sector, country, asset-class, currency, and factor exposure.
- Turnover, fees, slippage, borrow cost, and estimated impact.
- Drawdown contribution.
- Rolling risk and return.
- Rebalance event ledger.
- Capacity warning by strategy and security.
- Save, clone, compare, and version portfolios.

### Portfolio monitoring

- Current versus target allocation.
- Drift alerts.
- Concentration limits.
- VaR and CVaR with honest unavailable states.
- Correlation changes.
- Exposure-limit breaches.
- Paper portfolio tracking.

Koyfin validates the value of reusable portfolio views, model portfolios, exposure analysis, linked widgets, and relative performance. See <https://www.koyfin.com/help/topic/functionality/>.

## 3. Results

### Core results

- Equity and underwater drawdown.
- Net and gross returns.
- Sharpe, Sortino, Calmar, volatility, maximum drawdown, CAGR, win rate, payoff ratio, and profit factor.
- Number of trades and statistical sample warnings.
- Rolling metrics.
- Complete trade ledger.
- Monthly and annual return tables.
- Benchmark-relative alpha, beta, tracking error, and information ratio.

### Diagnosis

- Sector, asset, strategy, factor, and regime attribution.
- Slippage and fee post-mortem.
- Entry and exit quality.
- Holding-period distribution.
- Best and worst trade inspection.
- Live or paper versus backtest reconciliation.
- Data freshness and provenance at execution time.

### History and export

- Compare any two saved runs.
- Code, parameter, metric, trade, and data-snapshot diff.
- Model lineage from research to portfolio and validation.
- CSV, JSON, and PDF export.
- Portable reproducibility bundle containing config, hashes, metrics, and data manifest references.

QuantConnect exposes backtest, optimization, and live results inside one research environment, which supports keeping result comparison connected to the project rather than creating another standalone product. See <https://www.quantconnect.com/docs/v2/research-environment/meta-analysis/key-concepts>.

## 4. Validate

Validation is progressive. The default test set is fast; expensive tests are explicitly requested.

### Default validation

- Train/test or anchored out-of-sample split.
- Rolling or anchored walk-forward validation.
- Stitched out-of-sample equity curve.
- In-sample versus out-of-sample degradation.
- Parameter stability for one or two parameters.
- 2D heatmap and optional 3D surface using the same bounded result grid.
- Transaction-cost and slippage break-even.
- Entry timing perturbation with a small bounded sample.
- Regime performance.
- Benchmark and universe sensitivity.
- Deflated Sharpe using the project trial count.
- Clear pass, caution, or fail explanation with the underlying values.

### On-demand validation

- Lightweight CPCV with a bounded number of groups and paths.
- Price-noise sensitivity.
- Alternative universe perturbation.
- Capacity stress.
- Monte Carlo with 500–2,000 paths, not 100,000.
- Bootstrap confidence intervals.

### Explicitly excluded from defaults

- 9,261-run three-parameter stability grids.
- Automatic 15,000-path Monte Carlo batches.
- Full certification suites that execute approximately 20,000 simulations for every run.
- Unvalidated topology, manifold, or decorative mathematical surfaces.

Walk-forward optimization is retained because market conditions and useful parameters change over time, but optimization frequency must remain conservative to control overfitting. See <https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization>.

## 5. Factors

### Core factor research

- Factor expression editor.
- Cross-sectional Pearson and rank IC.
- Purged IC where overlapping labels require it.
- IC mean, dispersion, t-statistic, p-value, IC/IR, and positive-period fraction.
- IC decay by forward-return horizon.
- Cross-sectional factor distribution.
- Turnover versus decay.
- Coverage, missingness, winsorization, and normalization inspection.
- Sector and market-cap neutralization.
- Orthogonalization against known factors.
- Factor interaction analysis.
- Regime-conditional IC.
- Crowding and correlation with the internal factor library.
- Compare factors and build a composite.
- Save, version, approve, deprecate, and restore factors.

### Research safeguards

- Point-in-time data only.
- Survivorship and delisting awareness.
- Explicit forward-return construction.
- Embargo/purge controls where required.
- Multiple-testing correction and permanent trial count.
- Synthetic-data provenance warning.
- Cost and capacity analysis before promotion.

## 6. Replay

### Keep and improve

- Start at any historical point.
- Play, pause, step, speed, and jump to live/end.
- Synchronized replay across selected charts.
- Signals, fills, stops, targets, and position state on the chart.
- Drawings and indicators preserved during replay.
- Inspect the code version and run that generated any trade.
- Portfolio replay with allocation and exposure changes.
- Replay results and trade list export.

TradingView demonstrates that replay is most useful when it stays directly attached to the chart, supports synchronized layouts, and preserves drawings and indicators. See <https://www.tradingview.com/support/solutions/43000474024-how-do-i-turn-bar-replay-on/>.

## Additional high-value features found through product research

These additions are useful and do not require GPU-heavy infrastructure.

### Research lifecycle

- Project stage: idea, research, backtest, paper, approved, archived.
- Hypothesis and acceptance criteria recorded before the first backtest.
- Backtest and parameter attempt counter.
- Promotion gates based on user-defined validation thresholds.
- Paper-to-backtest reconciliation.
- Strategy health and drift after paper deployment.

QuantConnect now presents research, backtesting, paper trading, and live trading as a connected pipeline. The useful lesson is the continuous project lifecycle, not copying its separate product screens. See <https://www.quantconnect.com/docs/v2/cloud-platform/research-pipeline>.

### Linked analysis context

- Link ticker, date range, benchmark, portfolio, and run selection across panels.
- Reusable view presets.
- Saved result layouts.
- Shareable read-only project snapshots.

Koyfin's linked dashboard groups and reusable views validate this interaction model. See <https://www.koyfin.com/help/topic/functionality/>.

### Transparent compute

- Estimated run count before starting work.
- Estimated duration and memory class.
- Cancel control.
- Partial progress and completed-fold results.
- Result reuse when code, data, and parameters are unchanged.
- Segmented long backtests to cap memory.
- User-selectable fast, normal, and thorough budgets.

QuantRocket documents segmented backtests, bounded worker concurrency, and 1D/2D parameter scans as practical ways to control memory while retaining useful optimization. See <https://www.quantrocket.com/docs/>.

### Extensibility without UI sprawl

- A small internal widget specification for table, time series, distribution, heatmap, and metric-ledger outputs.
- New analysis endpoints declare their parameters and output schema.
- The Studio renderer supplies sorting, inspection, export, loading, and error behavior.

OpenBB uses API-backed widget specifications to connect custom data to reusable interactive components. The relevant lesson is schema-driven rendering, not introducing a user-facing widget marketplace. See <https://docs.openbb.co/workspace/developers/json-specs/widgets-json-reference>.

## Lean production architecture

## Required services

The initial production system requires only:

1. **Next.js frontend**
2. **FastAPI application**
3. **PostgreSQL**
4. **One isolated Python worker process**

Large artifacts remain Parquet/JSON files on durable storage. Use local durable storage for a single-host deployment or S3-compatible object storage when deploying across multiple hosts.

## No Redis by default

PostgreSQL is sufficient for:

- Projects and strategies.
- Runs and parameters.
- Job records and progress.
- Worker claiming through `FOR UPDATE SKIP LOCKED`.
- Cancellation flags.
- Trial registry and lineage.
- Alerts and limits.

Redis should be introduced only after measured queue throughput or event latency proves PostgreSQL inadequate. It is not a default dependency.

## No permanent kernel per user by default

The original Studio does not require a continuously running Jupyter kernel to deliver its best workflow.

Default execution model:

1. Save source and configuration.
2. Submit an execution job.
3. Run it in an isolated worker process.
4. Persist structured outputs and artifacts.
5. Return the variable summary, logs, tables, charts, and result ID.

This model is reproducible, inexpensive, and avoids stale hidden state. A short-lived warm worker may be added later for active users, with a strict idle timeout and memory cap. It should remain an optimization, not the correctness model.

## No WebSocket by default

- Use normal REST for configuration, reads, and quick commands.
- Use Server-Sent Events for one-way job progress and logs.
- Use polling as a fallback.
- Add WebSocket only for a genuine interactive terminal or multi-user collaboration.

## Job execution

- API writes a job row to PostgreSQL.
- Worker claims the next eligible row with `SKIP LOCKED`.
- Worker executes in a constrained subprocess or container.
- Progress and cancellation state are written to the job row.
- SSE streams new progress to the browser.
- Completed results are stored once and addressed by run ID.

This avoids Redis, Celery, Kafka, and a separate scheduler for the initial product.

## Execution isolation

User Python must not run through unrestricted in-process `exec()`.

Required controls:

- Separate process or container.
- Read-only base filesystem.
- Explicit writable workspace.
- CPU, memory, process, file-size, and wall-time limits.
- Network disabled by default.
- Approved package environment.
- Structured stdout, stderr, and exception capture.
- Worker termination on timeout or cancellation.

## State ownership

### Browser

- Active tab and pane sizes.
- Selected chart tools.
- Unsaved editor text.
- Temporary filters and selections.

### Server

- Projects, strategies, portfolios, factors, runs, jobs, trials, notes, and permissions.
- Never rely on localStorage as the authoritative research record.

### Large artifacts

- Equity curves, trades, returns, path samples, parameter grids, and reports.
- Store as Parquet or compressed JSON and reference them by immutable artifact ID.

## Frontend state

- Replace the single oversized Studio Context with small domain slices.
- Use Zustand only for workspace UI and unsaved session state.
- Use a typed server-request layer for authoritative data.
- Do not duplicate server results into multiple global stores.
- Load advanced panels only when opened.

## Performance rules

- Polars/NumPy for computation.
- Parquet projection and predicate pushdown.
- Hash `(code + parameters + data snapshot + engine version)` and reuse identical results.
- Segment long date ranges to cap memory.
- Default worker concurrency based on available RAM, not CPU count alone.
- Bound every simulation and optimization request.
- Stream or paginate large trades and matrices.
- Canvas/WebGL only for genuinely large heatmaps or dense charts.
- No GPU dependency for backtesting, factor research, optimization, or portfolio risk.

## What is intentionally not added

- Redis, Celery, Kafka, Kubernetes, or microservices without measured need.
- Permanent Jupyter kernels for every user.
- A full unrestricted bash terminal.
- GPU-per-session infrastructure.
- Automatic exhaustive optimization.
- Decorative 3D charts without a real two-parameter result grid.
- Synthetic fallback data presented as market evidence.
- Random or hard-coded analytical results.

## Delivery order

### Phase 1: Truthful core

- Remove fabricated and synthetic fallback results.
- Isolate Python execution.
- Split the oversized Studio store.
- Introduce projects, runs, artifacts, and typed errors.
- Preserve Develop, Results, Validate, and Replay behavior.

### Phase 2: Portfolio and Factors

- Multi-strategy portfolio construction and backtest.
- Complete factor research page.
- Shared project/run/data context.

### Phase 3: Validation and comparison

- Bounded optimization surfaces.
- Walk-forward, cost break-even, regime tests, and lightweight CPCV.
- Run, portfolio, and factor comparison.

### Phase 4: Paper monitoring

- Paper execution using the same strategy logic.
- Backtest-to-paper reconciliation.
- Portfolio drift, limits, and alerts.

## Definition of success

A user can create or select a strategy, test it on a real point-in-time dataset, combine it with other strategies into a portfolio, inspect honest results, validate robustness, research its factors, replay its decisions, and reproduce every displayed result from one saved project without navigating into a second product.

## Factors implementation audit

The Factors product is not starting from zero. The F01–F14 backend modules exist under `backend/app/services/factors_v2/features`, their API is mounted at `/api/labs/factors/v2`, and a generic schema-driven frontend exists. The visible Studio Factors page currently exposes only an expression and information-coefficient workflow plus a few diagnostics. It is not the complete F01–F14 product.

### Already available in the backend

- F01 valuation spread.
- F02 exposure decomposition.
- F03 attribution.
- F04 regime analysis.
- F05 decay.
- F06 crowding.
- F07 factor backtest.
- F08 covariance.
- F09 capacity.
- F10 portfolio optimization.
- F11 stress testing.
- F12 factor DNA.
- F13 monitoring.
- F14 report generation.

### Required frontend completion

- Retain the existing expression builder, information coefficient analysis, decay, crowding, interactions, and factor library.
- Add purpose-built views for exposure decomposition, attribution, backtesting, covariance, capacity, constrained optimization, stress, factor DNA, monitoring, and report export.
- Replace the generic schema renderer with feature-specific financial visualizations only where they improve interpretation: attribution waterfall, regime timeline, fitted decay, covariance view, capacity curve, constraint diagnostics, stress table, DNA summary, and monitoring health history.
- Keep all fourteen capabilities within the single Factors page using a compact mode switch or analysis navigator. Do not recreate fourteen application routes.

### Truthfulness fixes required before release

- Remove the hard-coded F01 fallback values `regression_beta=-0.002` and `r_squared=0.18`. Return an explicit unavailable result with a reason.
- Label F03 carryover calculations and F08 stress calculations whenever a proxy or fallback estimator is used.
- Keep seeded Monte Carlo or bootstrap generators only where simulation is mathematically intended, and expose the seed, sample count, cap, and method.
- Do not present dormant alert registration as active monitoring. Show monitoring as local/in-product until a real delivery worker exists.
- Surface estimator names, approximation status, cardinality limits, fallback metadata, and Research Mode caps in the response and UI.

### Lean completion order

1. Connect the existing F01–F14 API to the single Studio Factors page.
2. Remove unsupported hard-coded results and add typed provenance and fallback metadata.
3. Build the eight missing high-value output views: exposure, attribution, backtest, covariance, capacity, optimization, stress, and monitoring.
4. Add Factor DNA and report export after the analytical views are truthful.
5. Add alert delivery only when monitoring demand justifies a small scheduled worker; Redis is not required.
