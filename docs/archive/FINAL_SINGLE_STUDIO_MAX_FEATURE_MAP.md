# Final Single-Studio Maximum Feature Map

## Final product decision

There is one Studio and one persistent project context. Studio V2 is not a second product. The original Studio supplies the preferred single-workspace workflow, not a code-preservation mandate. Existing original and V2 code may be reused, massively upgraded, fully rewritten, merged, or removed. The target is the best production implementation, not loyalty to either legacy tree.

“Lean” or “minimal” architecture means the fewest independently operated systems and abstractions that can deliver the complete maximum product safely. It does not mean fewer user capabilities, generic components, incomplete infrastructure, or temporary-quality code.

### Current routing reality

The intended single-workspace Studio is not currently mounted. `frontend/src/app/studio/page.js` and `frontend/src/app/labs/studio/page.js` both render Studio V2 `AlgorithmLab`. The original `StudioLayout`, `StudioStore`, `DevelopView`, `TearsheetView`, `StressView`, `ValidateView`, `DynamicsView`, `ReplayView`, and `Q360Canvas` are dormant. Phase 0 restores the chosen one-workspace product at `/studio`, but the implementation may rewrite those files completely or replace them with better modules. The six product pages remain internal Studio modes. Useful V2 engines and ideas migrate behind the final contracts; both weak legacy implementations are retired when their replacements pass truth, capability, performance, and migration gates.

The final primary navigation is:

`Develop → Portfolio → Results → Validate → Factors → Replay`

Project, Data, Jobs, Versions, Paper status, and Command Palette are global workspace controls, not additional pages.

## Status legend

- **Current:** already present in the original Studio.
- **Harden:** present, but correctness, integration, or UX must be repaired.
- **Add:** new product capability.
- **V2 transplant:** useful capability already specified or implemented in Studio V2.
- **Remove:** delete or retire.
- **Merge:** capability survives inside another page.
- **Core:** inexpensive enough for normal interactive use.
- **Job:** durable background execution.
- **Research:** expensive, explicitly requested analysis with a visible compute estimate.

## Universal workspace

These capabilities follow the user across all six pages.

### Current

- Selected ticker and benchmark.
- Selected strategy and code.
- Strategy A/B state.
- Chart drawings, indicators, overlays, layouts, and playback state.
- Slippage and commission settings.

### Final additions

- Project selector with one active research project.
- Active strategy, portfolio, universe, dataset snapshot, benchmark, and run shown in a compact context bar.
- Save state, unsaved-change marker, undo/redo, and explicit version history.
- Command palette for navigation, execution, search, and panel actions.
- Global quick search for projects, strategies, factors, symbols, runs, and datasets.
- Jobs drawer with queued/running/completed/failed/cancelled states, progress, elapsed time, estimate, cancel, retry, and open-result actions.
- Typed error drawer with summary, cause, affected input, remediation, request ID, and expandable technical details.
- Data provenance drawer with source, point-in-time date, universe version, adjustment policy, missingness, fallback status, and engine version.
- Compare tray that accepts strategies, runs, factors, and portfolios from any relevant page.
- Notes and tags attached to projects, runs, and models.
- Keyboard-first navigation and resizable/dockable panels.
- Shareable internal project snapshot and reproducible export manifest.

### Cross-page ownership rules

- Develop owns paper execution, orders, fills, logs, and runtime control.
- Portfolio owns portfolio-level paper exposure, allocation drift, limits, and reconciliation views; it links to Develop for execution control.
- Results owns realized backtest/paper performance explanation. Factor attribution in Factors is the factor-model analytical service; Results consumes its versioned output when explaining a run or portfolio.
- Each domain launches its own relevant stress job: Validate owns strategy robustness stress, Portfolio owns holdings/allocation stress, and Factors owns factor-model stress. All use the shared job and scenario contracts; results remain attached to the originating domain object.
- Factors **Test** mode validates a factor. The primary Validate page validates a complete strategy or portfolio workflow.

### Global removals

- Separate Studio V2 shell and duplicated navigation.
- Giant marketing headings and page-opening hero blocks inside the product.
- Generic rectangle-card layouts where a table, chart, editor, or split pane communicates more.
- Silent conversion of missing or invalid values to zero.
- Synthetic market data or random analytics presented as observed evidence.
- Duplicate copies of authoritative server results in unrelated frontend stores.

---

## Page 1: Develop

### Purpose

Write, inspect, execute, and debug one strategy without leaving the research workspace.

### Internal modes

1. **Code:** editor-dominant strategy development.
2. **Chart:** market and signal inspection.
3. **Notebook:** cell-based exploratory research using the same project files and data snapshot.
4. **Paper:** authoritative forward-simulation execution and runtime control using the same strategy interface.

### Current features

- Monaco strategy editor.
- Strategy execution.
- Candlestick chart.
- Signal, trade, and indicator rendering.
- Custom overlays.
- Drawing tools and patterns.
- Volume profile.
- Crosshair inspection.
- Benchmark comparison.
- Strategy A/B comparison.
- Multi-chart layouts from 1x1 through 4x4.
- Playback controls.
- Event log.
- Technical-analysis hub.
- Slippage and commission controls.

### Harden

- Replace unrestricted in-process `exec()` with isolated execution.
- Reject invalid strategy code instead of silently substituting momentum logic.
- Remove synthetic OHLCV fallback from analytical runs.
- Make every editor run produce a structured run record.
- Virtualize logs, files, variables, and large tables.
- Split the oversized Studio store and canvas implementation into focused modules.
- Make code, chart, drawings, and run selection persist per project.

### Add

- Warm Python kernel per active project with 30–60 minute idle shutdown.
- Real terminal attached to the isolated project environment, with a constrained command policy.
- Variable inspector with type, shape, preview, memory size, producer cell/run, and stale-dependency marker.
- File tree with create, rename, move, delete, search, and unsaved markers.
- Dependency and environment panel with locked versions and reproducible environment manifest.
- Breakpoints, structured logs, tracebacks linked to source lines, and execution timing.
- Run selected cell, run file, run strategy, interrupt, restart kernel, and clear state.
- Parameter declaration directly from code.
- Data preview from the active point-in-time snapshot.
- One-click backtest and one-click send to Factors.
- Code diff between two versions or runs.
- Saved strategy templates without silently replacing user code.
- Paper account state, orders, fills, positions, P&L, logs, disconnects, and reset.
- Explicit paper-versus-live limitations, including market impact, queue position, latency, and fill assumptions.

### V2 transplants

- Persistent Python context.
- Reactive dependency tracking.
- Variable staleness indicators.
- File system and version control.
- Run history.
- Push to backtest.
- Backtest-to-paper code parity.

### Compute tier

- Editing, charting, previews, and ordinary cells: **Core**.
- Backtests, large notebook cells, dependency installation, and paper reconciliation: **Job**.
- No GPU by default.

### UX layout

- Left rail: project files and saved strategies.
- Center: editor or notebook.
- Right dock: chart, variables, data preview, or documentation.
- Bottom dock: output, terminal, problems, jobs, and dependencies.
- The user controls panels; opening the page does not trigger expensive computation.

---

## Page 2: Portfolio

### Purpose

Combine strategies or assets, allocate capital, understand exposures, and test portfolio decisions.

### Internal modes

1. **Build:** holdings, strategies, sleeves, constraints, and target weights.
2. **Optimize:** risk-return and constraint-aware construction.
3. **What-if:** prospective trade and allocation impact.
4. **Monitor:** drift, limits, capacity, and portfolio-level paper analytics; execution control remains in Develop > Paper.

### Current features

- No complete original-Studio portfolio construction page.
- Some portfolio metrics and attribution exist in the Tearsheet.
- Selected benchmark and strategy comparison state already exist.

### Add: Build

- Add assets, saved strategies, factor portfolios, and custom return series.
- Support equal weight, manual weight, inverse volatility, risk parity, volatility target, minimum variance, maximum diversification, benchmark-relative, and custom allocation.
- Multi-sleeve portfolios with sleeve-level budgets and constraints.
- Cash allocation, rebalance frequency, contribution/withdrawal assumptions, leverage, and shorting controls.
- Import holdings or weights from CSV and export the complete model.
- Saved portfolios, saved benchmarks, and saved capital-market assumptions.
- Exposure breakdown by asset, strategy, sleeve, sector, country, currency, factor, and custom tag.
- Correlation, covariance, marginal risk, component risk, and diversification contribution.

### Add: Optimize

- Efficient frontier.
- Mean-variance, CVaR, tracking-error, risk-parity, drawdown-aware, Black-Litterman, and factor-target optimization.
- Hard and soft constraints for weights, groups, turnover, tracking error, beta, factor exposure, liquidity, position size, and transaction cost.
- Multiple covariance estimators with the selected estimator visible.
- Robust/resampled inputs to reduce estimation sensitivity.
- Cardinality approximation status and infeasibility diagnostics.
- Compare current, target, optimized, and benchmark portfolios.
- Capacity-aware optimization and market-impact estimates.

### Add: What-if

- Stage proposed buys, sells, hedges, or allocation changes without changing the saved portfolio.
- Show changes in expected risk, factor exposures, tracking error, drawdown sensitivity, cost, liquidity, and capacity.
- Factor hedge builder with residual exposures and constraint diagnostics.
- Factor exposure matching using cheaper or more liquid instruments.
- Historical, factor, macro, and user-defined scenarios.
- Pre-trade compliance and limit checks.

### Add: Monitor

- Target-versus-current drift.
- Rebalance suggestions with estimated transaction cost.
- Strategy/sleeve contribution and concentration.
- Risk-budget breaches.
- Capacity erosion and liquidity warnings.
- Paper portfolio reconciliation.
- Optional tax-lot-aware rebalancing as a later jurisdiction-specific module, never a default promise.

### V2 transplants

- Covariance estimators.
- Capacity analysis.
- Constrained optimizer.
- Stress scenarios.
- Model lineage and dataset snapshot linkage.

### Compute tier

- Holdings edits and exposure summaries: **Core**.
- Optimization, portfolio backtests, capacity, and stress: **Job**.
- Large resampling or broad scenario grids: **Research**.

### UX layout

- Left: portfolio tree with assets, strategies, and sleeves.
- Center: holdings/exposure table or frontier/scenario visualization.
- Right: constraints, assumptions, and decision impact.
- Bottom: rebalance orders, violations, comparisons, and job history.

---

## Page 3: Results

### Purpose

Explain what happened, why it happened, and whether the result can be trusted.

### Internal modes

1. **Overview:** honest performance summary.
2. **Risk:** drawdowns, tails, exposures, and concentration.
3. **Attribution:** sources of return and risk.
4. **Trades:** trade and execution diagnosis.
5. **Compare:** run, strategy, and portfolio comparison.
6. **Report:** reproducible export.

### Current features

- Equity curve.
- Drawdown curve.
- Performance and trade metrics.
- Monthly return heatmap.
- Basic attribution.
- Trade list.
- Export presentation.

### Harden

- Remove hard-coded average holding period.
- Remove random MAE/MFE values.
- Stop displaying unavailable metrics as zero.
- Add sample size, units, methodology, benchmark, and annualization basis to metrics.
- Link every output to code version, parameters, data snapshot, engine version, and cost model.

### Add: Overview

- Honest performance card with return, volatility, Sharpe, Sortino, Calmar, drawdown, recovery, hit rate, payoff, turnover, exposure, and costs.
- Benchmark-relative alpha, beta, tracking error, information ratio, and active return.
- Gross-versus-net performance and cumulative cost drag.
- Rolling return, volatility, Sharpe, beta, correlation, and drawdown views.
- Calendar, monthly, yearly, and underwater views.

### Add: Risk

- Historical VaR/CVaR with method and confidence level.
- Drawdown episodes with depth, duration, recovery, and contributing positions.
- Tail dependence, concentration, liquidity, capacity, and exposure history.
- Factor-versus-idiosyncratic risk split.
- Marginal and component risk contribution.

### Add: Attribution

- Asset, strategy, sleeve, sector, factor, signal, regime, and long/short attribution.
- Brinson-style allocation/selection where portfolio inputs support it.
- Factor return contribution and residual unexplained return.
- Contribution waterfall with drill-through to positions and trades.
- Decision attribution: entry, sizing, exit, hedge, cost, and timing.

### Add: Trades

- Real MAE/MFE derived from market paths.
- Holding period, excursion, slippage, commission, turnover, fill quality, and latency where available.
- Best/worst trades, clustered loss patterns, and repeated failure signatures.
- Order-to-fill timeline and rejected/cancelled order diagnosis.

### Add: Compare and Report

- Compare up to four total objects: one primary run or portfolio plus as many as three comparison runs or portfolios, with synchronized charts and aligned date ranges.
- Metric deltas with definitions and statistical uncertainty.
- Saved comparison views.
- PDF, HTML, CSV, Parquet, JSON, and reproducibility manifest.
- Scheduled report generation only when the shared Celery Beat scheduler is enabled.
- Generated commentary may summarize verified attribution data, but cannot invent causes.

### V2 transplants

- Honest performance card.
- Interactive tearsheet.
- Model lineage.
- Export manifest.
- Live-versus-backtest reconciliation.

### Compute tier

- Stored result inspection: **Core**.
- Attribution recomputation, large exports, and comparison alignment: **Job**.

### UX layout

- Compact metric strip, not oversized cards.
- One dominant chart with linked secondary diagnostics.
- Dense sortable tables with drill-down.
- All methodology and provenance accessible without covering the analysis.

---

## Page 4: Validate

### Purpose

Determine whether a strategy is stable, realistic, and worthy of paper testing.

### Internal modes

1. **Quick Check:** bounded default validation.
2. **Stability:** parameter and timing robustness.
3. **Out-of-Sample:** walk-forward and holdout evidence.
4. **Costs & Capacity:** economic viability.
5. **Scenarios:** historical, simulated, and regime stress.
6. **Certification:** expensive overfitting diagnostics.

### Current features

- Walk-forward testing.
- In-sample/out-of-sample comparison.
- Fold results.
- Performance degradation.
- Separate Monte Carlo Stress page.

### Harden

- Remove random fallback values from walk-forward results.
- Bound Monte Carlo memory instead of creating unrestricted full matrices.
- Require real observations and explicit insufficient-data errors.
- Preserve seeds, methods, sample counts, folds, embargoes, and caps.

### Add: Quick Check

- Data leakage and lookahead checks.
- Minimum history and trade-count checks.
- Cost sensitivity.
- Small parameter-neighborhood stability check.
- Entry-timing perturbation.
- Subperiod and regime breakdown.
- Clear pass, caution, fail, or unavailable result for each test.

### Add: Stability

- One- and two-parameter response surfaces.
- Parameter plateau width and local sensitivity.
- Entry/exit timing jitter.
- Universe perturbation.
- Benchmark and rebalance-frequency sensitivity.
- Execution-model sensitivity.
- Seed stability for stochastic methods.

### Add: Out-of-Sample

- Anchored and rolling walk-forward.
- Holdout selection and leakage-safe preprocessing.
- Fold-level results and degradation distribution.
- Rolling model/parameter selections.
- Train/test/paper separation.
- Research pipeline gate from idea to backtest to paper.

### Add: Costs, Capacity, and Scenarios

- Transaction-cost break-even.
- Slippage and commission grids.
- Turnover decomposition.
- ADV participation and capacity curve.
- Historical crisis replay.
- Factor, macro, and user-defined shocks.
- Block bootstrap and Monte Carlo with bounded samples.
- Ruin probability and sequence-risk analysis where mathematically applicable.

### Add: Certification

- Combinatorial purged cross-validation.
- Deflated Sharpe ratio.
- Probability of backtest overfitting.
- Multiple-testing and selection-bias accounting.
- Noise injection and extended bootstrap diagnostics.
- Composite robustness report with test-by-test evidence, not a magical opaque score.

### Merge and remove

- Merge the current Stress page into Validate > Scenarios.
- Remove a separate Optimizer page; parameter optimization belongs inside Validate > Stability/Out-of-Sample.
- Remove automatic 9,261-grid or 20,000-run defaults.
- Remove decorative 3D surfaces unless real two-parameter results justify them.

### Compute tier

- Quick Check: **Core** or short **Job**.
- Walk-forward, parameter surfaces, and bounded scenarios: **Job**.
- CPCV, DSR, PBO, large bootstrap, or broad grids: **Research** with cost estimate and explicit confirmation.

### UX layout

- Left: validation test navigator and saved presets.
- Center: selected test evidence.
- Right: parameters, compute estimate, assumptions, and methodology.
- Bottom: trial registry, job progress, failures, and comparisons.

---

## Page 5: Factors

### Purpose

Discover, validate, explain, construct, stress, and monitor factors in one institutional workflow.

### Internal modes

1. **Discover:** define and inspect a factor.
2. **Test:** validate factor efficacy and stability without confusing it with the primary Validate page.
3. **Understand:** explain exposures, interactions, and attribution.
4. **Construct:** turn factors into portfolios and hedges.
5. **Stress:** examine factor and macro shocks.
6. **Monitor:** detect decay, drift, crowding, and model failure.

### Current Studio features

- Expression editor.
- Information coefficient evaluation.
- Factor library CRUD.
- IC decay.
- Crowding analysis.
- Interaction diagnostics.
- Basic regime diagnostics.

### Current F01–F14 backend capabilities

- Valuation spread.
- Exposure decomposition.
- Attribution.
- Regime analysis.
- Decay.
- Crowding.
- Factor backtest.
- Covariance.
- Capacity.
- Constrained optimizer.
- Stress testing.
- Factor DNA.
- Monitoring.
- Report generation.

### Add: Discover

- Formula and visual expression builder.
- Data-field browser with units, frequency, availability, and point-in-time status.
- Universe, sector, country, size, liquidity, and date filters.
- Cross-sectional distribution, missingness, outliers, coverage, and data freshness.
- Winsorization, standardization, ranking, lagging, neutralization, and transformations.
- Saved custom factors, tags, descriptions, owners, versions, and assumptions.
- Fundamental, statistical, macro, and custom factor model selection.

### Add: Test

- IC and rank IC with confidence intervals.
- Quantile returns, monotonicity, spread, hit rate, and t-statistics.
- Decay curve and fitted half-life.
- Turnover, transaction costs, capacity, and net factor return.
- Long-short and factor-mimicking portfolio backtests.
- Rolling, regime, sector, country, size, and universe stability.
- Vintage analysis and publication-lag sensitivity.
- Walk-forward and holdout testing.
- Multiple-testing and false-discovery warnings.

### Add: Understand

- Portfolio and security exposure decomposition.
- Factor return and risk attribution.
- Fundamental-versus-statistical model comparison.
- Rolling exposures and factor contribution history.
- Orthogonalization against existing factors.
- Correlation, redundancy, clustering, and interaction screening.
- Factor DNA with behavior, regime preference, decay, turnover, crowding, capacity, and failure conditions.
- Model coverage and residual/unexplained risk.

### Add: Construct

- Pure factor portfolios.
- Composite multi-factor scoring.
- Factor-mimicking portfolios.
- Factor exposure matching with alternative instruments.
- Factor-neutral and target-exposure portfolio optimization.
- Risk budgets, exposure bounds, sector neutrality, turnover, liquidity, and cost constraints.
- Hedge candidates with residual exposure and constraint diagnostics.
- Send selected factor portfolio directly to Portfolio or Validate.

### Add: Stress

- Historical factor crashes.
- User-defined factor shocks.
- Macro-to-factor scenarios.
- Crowding and liquidity unwind.
- Regime-conditioned exposure and loss.
- Proposed-trade factor impact.

### Add: Monitor

- Rolling IC, rank IC, spread, turnover, capacity, and coverage.
- Exposure and factor-contribution drift.
- CUSUM/change-point warnings.
- Crowding deterioration.
- Model-input freshness and missing-data alerts.
- Threshold definitions, alert provenance, and acknowledgement history.
- Scheduled factor report once real delivery infrastructure exists.

### Truthfulness repairs

- Remove hard-coded F01 `regression_beta=-0.002` and `r_squared=0.18` fallbacks.
- Label every F03/F08 proxy or fallback estimator.
- Distinguish seeded simulation from observed market evidence.
- Do not claim dormant alert registration is active delivery.
- Surface estimator, seed, cap, approximation, model coverage, and Research Mode metadata.

### Merge and remove

- Do not create fourteen F01–F14 routes in the user experience.
- Replace the generic schema renderer with feature-specific financial views.
- Remove a standalone Factor Optimizer; construction belongs in Factors > Construct or Portfolio > Optimize.

### Compute tier

- Expression inspection, distribution, library, and stored results: **Core**.
- IC, decay, backtest, covariance, capacity, and construction: **Job**.
- Broad universes, CPCV, extensive interaction search, or large stress suites: **Research**.

### UX layout

- Left: factor definition and library.
- Center: one dominant analysis view.
- Right: universe, transformations, methodology, and compare tray.
- Bottom: ranked tables, diagnostics, jobs, and output provenance.

---

## Page 6: Replay

### Purpose

Reconstruct market state and strategy decisions step by step.

### Internal modes

1. **Market:** synchronized price and indicator playback.
2. **Decision:** signal, variable, and rule-state reconstruction.
3. **Execution:** order, fill, cost, and latency timeline.
4. **Compare:** two-run or backtest-versus-paper replay.

### Current features

- Historical step and play controls.
- Trade-focused replay.
- Basic attribution context.
- Existing chart, drawings, indicators, and events can be reused.

### Add

- Synchronized multi-chart replay.
- Speed control, step forward/back, event jump, trade jump, and drawdown jump.
- Preserve drawings, indicators, layouts, benchmark, and crosshair state.
- Point-in-time positions, cash, exposure, orders, signals, variables, and risk state.
- Decision trace showing which strategy condition fired and which inputs it used.
- Order lifecycle from submission through fill, cancellation, rejection, or expiry.
- Cost, spread, slippage, latency, and fill-assumption overlays.
- Side-by-side replay for two strategy versions.
- Backtest-versus-paper divergence replay.
- Annotated bookmarks and exportable incident clips/snapshots.

### V2 transplants

- Run lineage.
- Backtest-to-paper reconciliation.
- Structured event stream.
- Variable and dependency snapshots where available.

### Compute tier

- Replay of stored events: **Core**.
- Reconstruction of missing decision state: **Job** and only when reproducible inputs exist.

### UX layout

- Chart remains dominant.
- Timeline spans the bottom edge.
- Decision/execution inspector occupies a collapsible right dock.
- No dashboard grid of unrelated cards.

---

## Global Data drawer

Data is not a seventh primary page. It is a global drawer that can expand over the current workspace. Expansion does not change the primary Studio route, create a seventh navigation item, or discard the active project/page context.

### V2 transplants and additions

- Data catalog.
- Point-in-time universe builder.
- Time-varying universe viewer.
- Universe snapshot export.
- ADV and liquidity layer.
- Data explorer.
- Missing-data heatmap.
- Custom CSV/Parquet upload.
- Freshness monitor.
- Corporate-action and adjustment policy.
- Coverage, survivorship, lookahead, delisting, and publication-lag checks.
- Dataset version, checksum, schema, lineage, and usage history.
- Preview before loading large data.

### UX rule

The active dataset and universe are always visible in the context bar. Detailed data management opens only when requested.

---

## Final removals and mergers

| Current or proposed element | Final action | Destination or reason |
|---|---|---|
| Studio V2 product shell | Remove | One original Studio remains |
| Stress page | Merge | Validate > Scenarios |
| Dynamics page, drawer, model wall, and name | Remove completely | Independently useful diagnostics move into Results, Validate, Factors, or Portfolio under accurate domain names |
| Optimizer page | Merge | Validate for strategy parameters; Portfolio/Factors for weights |
| Universe/Data page | Merge into global workspace | Data drawer/full-screen mode |
| Separate factor routes | Remove from UX | Six Factors modes in one page |
| Generic factor JSON renderer | Replace | Purpose-built financial outputs |
| Synthetic OHLCV fallback | Remove | Explicit unavailable/error state |
| Invalid-code momentum fallback | Remove | Typed execution failure |
| Random MAE/MFE and walk-forward output | Remove | Compute from evidence or unavailable |
| Hard-coded factor regression values | Remove | Explicit insufficient-data result |
| Giant default simulations | Remove | Bounded jobs and explicit Research Mode |
| Decorative 3D surfaces | Remove by default | Use only for real two-parameter topology |
| Full unrestricted user terminal | Constrain | Isolated project terminal |
| Immortal kernel | Replace | Warm idle-expiring project kernel |
| Redis as application database | Reject | PostgreSQL stays authoritative |
| WebSockets everywhere | Reject | Only kernel/terminal/live bidirectional streams |

## Mandatory current-feature upgrade program

No current feature or file is accepted merely because it already exists. Preserve user value and proven interaction behavior, not legacy component boundaries. Every retained or rewritten capability must pass correctness, integration, performance, accessibility, responsive-layout, provenance, empty/error-state, and automated-test checks.

### Phase 0: reconnect the product

1. Mount the upgraded original Studio shell at `/studio`.
2. Keep `/labs/studio` as a temporary redirect to `/studio`, not a second implementation.
3. Inventory original and `AlgorithmLab` capabilities, then classify each as reuse, rewrite, replace, merge, or remove.
4. Add route-level smoke tests proving all six final pages render.
5. Remove the old V2 shell only after feature and API parity are verified.

### Critical truth and safety repairs

- Move arbitrary Python `exec()` out of the FastAPI process into an isolated worker/container with CPU, RAM, wall-time, output, filesystem, subprocess, and network limits.
- Remove automatic synthetic OHLCV fallback. Synthetic data exists only in an explicit Demo mode and is marked in every response and view.
- Remove random MAE/MFE, hard-coded holding period, random walk-forward fallback, hard-coded factor regression, and every invented zero.
- Compute MAE/MFE from actual price paths and holding periods from actual entry/exit timestamps.
- Define one explicit event order: bar close, signal, order submission, next eligible fill, costs, then mark-to-market.
- Persist fill, spread, slippage, participation, partial-fill, shorting, corporate-action, adjustment, and benchmark assumptions.
- Return typed unavailable, partial, stale, cancelled, failed, and insufficient-data states.

### State and request upgrades

- Replace the 670-line global `StudioStore` with workspace, chart, execution, validation, research, and persistence domains.
- Give every request an ID and cancellation signal so stale ticker, strategy, or date-range responses cannot overwrite current state.
- Batch grid data requests and bound concurrency; do not download and execute the same 4x4 grid symbols twice.
- Store authoritative results on the server and keep only UI/session state in the browser.
- Version persisted browser state and recover safely from incompatible layouts.
- Preserve pane-indicator configuration in grid mode; temporarily hide unsupported panes instead of deleting user choices.

### Current chart feature upgrade

- Precompute indicator series when data or configuration changes, never during every hover event.
- Move playback drawing to `requestAnimationFrame`; keep the frame index in a ref and throttle React HUD updates.
- Split static grid, price data, indicators, annotations, and interaction into independent rendering layers.
- Redraw only dirty layers and the changed viewport.
- Centralize time/price/pixel coordinate transforms and remove inconsistent offset state.
- Handle empty data, a single candle, flat prices, zero volume, missing bars, gaps, logarithmic scale constraints, resizing, and high-DPI displays.
- Cap device-pixel ratio in dense multi-chart layouts.
- Suspend offscreen charts and lazy-load non-visible analysis.
- Synchronize crosshair, viewport, replay time, and benchmark state through explicit contracts.
- Add keyboard inspection and a tabular equivalent for every chart.
- Test pointer interaction, zoom, pan, drawings, resizing, flat series, gaps, replay, export, and synchronized layouts.

### Chart-engine ownership strategy

The product should be custom at the financial-semantic and interaction layers, not custom for vanity.

#### Allowed low-level dependencies

- Monaco for code editing.
- Browser Canvas2D, OffscreenCanvas, WebGL, Web Workers, typed arrays, and platform accessibility APIs.
- D3 utilities only for scale, tick, interpolation, or formatting functions that are directly used.
- A low-level WebGL/device library only when it reduces driver boilerplate without owning finance semantics, layouts, interactions, output composition, or visual design.
- Monaco remains appropriate for editing unless a measured product requirement justifies replacement.

#### Wrap behind one owned adapter

No page imports a third-party chart engine directly. Build an owned `Q360Scene` and `FinancialChart` contract covering:

- Series and typed financial data.
- Viewport and synchronized time scale.
- Price scale and formatter.
- Crosshair and inspection HUD.
- Indicators and panes.
- Drawings and annotations.
- Signals, orders, fills, and positions.
- Benchmark and relative-performance overlays.
- Playback and event navigation.
- Loading, empty, partial, stale, and error states.
- Accessibility and tabular fallback.
- Image/data export.

#### Build and own custom financial primitives

- OHLCV and volume presentation.
- Trade entry/exit/fill markers.
- Signal and order lifecycle timeline.
- Benchmark-relative overlay.
- Drawdown and recovery bands.
- Exposure and factor strips.
- Cost, capacity, liquidity, and data-gap annotations.
- Crosshair/HUD formatting.
- Synchronized multi-chart controller.
- Provenance, methodology, and data-quality badges.
- Scales, axes, ticks, grid layout, scene graph, layer scheduling, hit testing, picking, gestures, dirty-region rendering, level of detail, worker transforms, export, and accessible data descriptions.

#### Remove after graph verification and smoke testing

- Unused or duplicate D3, ECharts, lightweight-charts, Plotly, Recharts, and React Plotly packages.
- Page-specific chart abstractions that bypass `FinancialChart`.
- Duplicate indicator/pattern implementations.
- Generic chart cards that cannot express financial states or methodology.

### Current Develop upgrades

- Reconnect the route to the upgraded implementation.
- Add real project/file persistence, diagnostics before execution, cancellation, progress, execution timeline, data snapshot, and fill model.
- Stabilize chart viewport, precompute indicators, bound grid loading, and add keyboard chart inspection.
- Remove silent fallback strategies, fake outputs, and destructive grid-mode indicator behavior.

### Current Results upgrades

- Keep metrics numeric through the API and format only at the presentation edge.
- Add metric definitions, units, methodology, benchmark basis, sample size, confidence, provenance, and data-quality status.
- Add real benchmark-relative metrics, exposure, turnover, MAE/MFE, holding-period distribution, and reproducible export.
- Remove unavailable-as-zero behavior and unsupported attribution.

### Current Stress upgrades before merging into Validate

- Batch/stream Monte Carlo rather than allocate unrestricted `(simulations × horizon)` matrices.
- Retain aggregates and a small deterministic path sample.
- Show method, seed, sample size, assumptions, confidence interval, memory estimate, progress, cancel, and retry.
- Add historical replay and block-bootstrap modes; avoid certainty claims from a normal-only model.

### Current Validate upgrades

- Rerun real strategies in every fold and fit parameters only inside training windows.
- Add leakage-safe preprocessing, proper out-of-sample metrics, purging/embargo where labels overlap, costs, capacity, sensitivity, multiple-testing correction, and deflated Sharpe.
- Replace the decorative verdict with evidence-backed pass/caution/fail/unavailable results.
- Remove every randomized frontend fallback.

### Dynamics and Spectral removal

- Remove `DynamicsView`, `SpectralAnalysis`, the model wall, navigation, routes, Dynamics-specific endpoints, caches, labels, and unsupported physics-flavored claims.
- Do not preserve a Dynamics drawer or compatibility page.
- A genuinely useful volatility, regime, tail-risk, liquidity, dependency, or persistence diagnostic may survive only after an independent mathematical audit. It must be renamed accurately, owned by the page where the user takes action, use typed contracts, and have no dependency on the retired Dynamics UI.
- Move canonical estimators out of frontend `QuantKernel` code into tested backend services or bounded jobs.

### Current Replay upgrades

- Replace simple `playIndex` playback with deterministic decision, signal, order, fill, cost, position, cash, exposure, and risk reconstruction.
- Add event navigation, missing-bar/corporate-action visibility, backtest-versus-paper comparison, and deterministic replay tests.

### Required quality gates for every retained feature

- No fabricated evidence or silent fallback.
- Typed response and error contract.
- Data snapshot and model provenance.
- Deterministic test fixture where applicable.
- Unit tests for financial math and edge cases.
- API contract test.
- Frontend loading, empty, partial, error, cancel, and stale states.
- Keyboard accessibility and responsive behavior.
- Performance budget and representative benchmark.
- Route-level smoke test.
- Documentation of assumptions and limitations.

## Q360 owned visual-computing and output system

The final frontend does not assemble pages from generic imported chart cards. It owns a coherent visual language, financial rendering model, interaction model, output contracts, and accessibility layer. Dependencies provide low-level engines only.

### Architecture decision

Build `Q360 Visual Kernel`, a renderer-independent TypeScript package used by every Studio page.

```text
Domain result contracts
  ↓
Columnar data model and transforms
  ↓
Visual specifications and financial primitives
  ↓
Scene graph, layout, scales, interaction, annotation
  ↓
Canvas2D worker backend | WebGL backend | DOM/SVG accessibility overlay
```

React owns composition, controls, panels, and semantic DOM. The visual kernel owns data-to-pixel rendering and interaction state. A chart frame must never require a React component rerender.

### Selected foundation libraries

| Foundation | Final role | Why selected | What remains custom |
|---|---|---|---|
| TypeScript | All visual contracts and primitives | Compile-time domain safety | Every financial result and visual specification |
| Canvas2D | Default financial rendering backend | Predictable, crisp, low overhead | Entire render pipeline and financial marks |
| OffscreenCanvas | Worker-side rendering and export | Removes heavy canvas work from the UI thread | Frame protocol, dirty layers, synchronization |
| Comlink | Typed worker RPC | Small wrapper over worker messaging | Domain worker API and cancellation protocol |
| PixiJS v8 WebGL renderer | Dense GPU backend only | Stable WebGL renderer, batching, resources, texture lifecycle | Financial scene graph, shaders, picking, marks, semantics |
| Apache Arrow JS | Columnar client data transport | Typed, cache-friendly, interoperable, avoids object-per-row overhead | Financial schemas, validation, derived columns |
| TypedArray | Hot render buffers | Minimal allocation and direct GPU/Canvas consumption | Buffer ownership, pooling, indexing |
| TanStack Table | Headless table state | Full rendering and styling ownership | All Q360 table markup, cells, finance behavior |
| TanStack Virtual | Row/column/panel virtualization | Keeps DOM bounded | Virtual finance grid and keyboard model |
| TanStack Query | Server-state lifecycle | Cache, cancellation, invalidation, request dedupe | Domain query keys and result normalization |
| Zustand with selectors | Local workspace interaction state | Small subscription islands | Domain slices and persistence policy |
| D3 modular utilities | Scales, ticks, arrays and formatting only | Battle-tested numerical utilities | Axes, marks, layouts and interaction rendering |
| Floating UI | Collision-aware popovers/tooltips | Reliable positioning | Tooltip content, behavior and visual design |
| Radix primitives | Invisible accessibility mechanics only | Focus, keyboard and ARIA behavior | Every visible component and style |
| dnd-kit | Docking/reordering interaction foundation | Headless drag-and-drop control | Panel docking model and Studio visuals |
| Monaco | Code editing | Production editor foundation | Quant actions, diagnostics, run integration |
| Plotly | Exceptional on-demand 3D research output only | Mature camera and surface rendering | Q360 shell, provenance, controls and data contracts |

### Libraries not used as the visible product

- TradingView Lightweight Charts is a performance and financial-behavior reference, not the product renderer.
- uPlot is a benchmark/reference for dense aligned time-series performance, not the product visual language.
- Apache ECharts and Recharts are not page-level renderers.
- deck.gl is not appropriate for the primary financial workspace.
- WebGPU is an experimental backend flag only. PixiJS and deck.gl both document continuing WebGPU limitations; production defaults to WebGL/Canvas2D.
- AG Grid is unnecessary unless future enterprise spreadsheet requirements exceed the owned TanStack-based grid. Do not ship both.
- No Three.js for ordinary analytical output.
- No chart library is imported from a page or feature component.

### Renderer selection policy

Use measured complexity, not user-facing switches:

- DOM/SVG: labels, axes, small legends, accessible controls and editable annotations.
- Canvas2D: candlesticks, lines, areas, bands, histograms, compact heatmaps and ordinary interactions.
- Offscreen Canvas2D: playback, multi-chart layouts, image export and expensive static layers.
- PixiJS/WebGL: extremely dense scatterplots, large correlation/covariance matrices, millions of points, high-frequency replay and large heatmaps.
- Plotly lazy chunk: real two-parameter 3D surfaces only.

Every backend implements the same typed `RenderBackend` contract. Visual output cannot change its meaning when the backend changes.

### Core visual-kernel packages

```text
visual-kernel/
  contracts/       typed domain and visual specifications
  data/            Arrow schemas, typed buffers, indexes, downsampling
  scales/          time, price, percent, log, ordinal and color scales
  layout/          panes, axes, legends, grids and small multiples
  scene/           retained nodes, z-order, dirty regions and clipping
  marks/           lines, areas, bars, candles, points, cells and bands
  finance/         trades, fills, drawdowns, exposure, attribution, regimes
  interaction/     crosshair, hover, selection, zoom, pan and keyboard
  annotations/     drawings, labels, events, orders and data-quality marks
  backends/        canvas2d, offscreen, webgl and svg/dom overlay
  workers/         transform, indicator, layout, render and export workers
  a11y/            summaries, keyboard navigation and table equivalents
  export/          PNG, SVG overlay, CSV, Arrow, Parquet manifest and print
  testing/         targeted golden contracts, fixtures, interaction and benchmarks
```

### Data and frame pipeline

1. API returns a typed manifest plus Arrow/JSON payload depending on size.
2. A worker validates schema, sorts/indexes time, detects gaps and builds typed buffers.
3. Derived series and indicators execute once per `(data, parameters)` hash.
4. Level-of-detail pyramids are built for long time series.
5. The viewport selects the smallest sufficient resolution without changing statistics.
6. Layout and axes calculate independently from marks.
7. Static, data, annotation and interaction layers retain separate dirty flags.
8. The render worker emits a frame or directly controls an OffscreenCanvas.
9. React updates only semantic labels, controls and low-frequency summaries.

### Required rendering algorithms

- Min/max or OHLC-aware downsampling that preserves extrema, gaps and first/last observations.
- Pixel-column candle aggregation for histories denser than screen resolution.
- Stable autoscale with padding, optional lock, comparison normalization and outlier policy.
- Binary search from pointer time to nearest observation.
- Spatial index for freeform annotations and dense scatter picking.
- Dirty-rectangle or retained-layer invalidation.
- Buffer pooling to prevent garbage-collection spikes.
- Deterministic tick selection and financial number formatting.
- Viewport-linked computation; never calculate invisible points for hover.
- Gap-aware lines that never imply observations across missing periods.
- Color-contrast-safe palettes with positive/negative meaning that also works without color.

### Owned base marks

- `LineMark`
- `StepLineMark`
- `AreaMark`
- `BandMark`
- `BarMark`
- `HistogramMark`
- `CandlestickMark`
- `OHLCMark`
- `PointMark`
- `BubbleMark`
- `CellMark`
- `HeatmapMark`
- `WaterfallMark`
- `BoxWhiskerMark`
- `ViolinMark`
- `RangeMark`
- `ReferenceLineMark`
- `ReferenceBandMark`
- `TextLabelMark`

### Owned financial primitives

- `PriceSeries`
- `VolumeSeries`
- `IndicatorPane`
- `BenchmarkOverlay`
- `RelativePerformanceSeries`
- `TradeMarkerLayer`
- `OrderLifecycleLayer`
- `SignalLayer`
- `PositionExposureLayer`
- `DrawdownSeries`
- `RecoveryBand`
- `RegimeBand`
- `CorporateActionLayer`
- `DataGapLayer`
- `CostDragLayer`
- `CapacityCurve`
- `EfficientFrontier`
- `RiskContributionBars`
- `AttributionWaterfall`
- `RollingMetricSeries`
- `ReturnHeatmap`
- `CorrelationMatrix`
- `CovarianceMatrix`
- `ParameterSurface`
- `FoldTimeline`
- `MonteCarloFan`
- `DistributionDiagnostic`
- `FactorDecayCurve`
- `QuantileReturnPlot`
- `FactorExposureStrip`
- `FactorDNAProfile`
- `StressImpactTable`
- `DecisionTimeline`
- `BacktestPaperDivergence`

### Owned interaction primitives

- Crosshair with pinned and comparison modes.
- Pan, wheel/pinch zoom, box zoom and reset.
- Range selection and time brush.
- Synchronized viewport/crosshair groups.
- Multi-cursor run comparison.
- Replay scrubber and event snapping.
- Drawing select, move, resize, duplicate, lock and delete.
- Keyboard point navigation and tooltip inspection.
- Context menu and command-palette actions.
- Drill-through from any mark into positions, trades, factors or source data.
- Shareable visual state containing viewport, selections, layers and annotations.

### Owned output shell primitives

Every analytical output composes these, rather than inventing a new card:

- `AnalysisFrame`: title, question answered, state, provenance and actions.
- `MetricStrip`: dense comparable metrics with units and definitions.
- `ChartFrame`: visual kernel surface plus semantic fallback.
- `FinanceGrid`: custom TanStack table with virtualization and financial cells.
- `InspectorDock`: selection details and methodology.
- `LegendRail`: persistent interactive layer controls.
- `MethodBadge`: observed, estimated, proxy, simulated or unavailable.
- `QualityBadge`: coverage, freshness, missingness and fallback state.
- `ComputeBadge`: core, job or research plus runtime/memory estimate.
- `ComparisonRail`: selected runs, strategies, factors and portfolios.
- `EmptyState`, `PartialState`, `StaleState`, `ErrorState`, `CancelledState` and `InsufficientDataState`.
- `ExportMenu`: image, underlying data and reproducibility manifest.

### Custom FinanceGrid cells

- Numeric value with precision and unit.
- Price and percentage change.
- Contribution bar embedded behind the value.
- Sparkline using the visual kernel, not an imported chart component.
- Exposure and limit cell.
- Confidence interval cell.
- Method/proxy status cell.
- Data-quality cell.
- Constraint violation cell.
- Order/fill status cell.
- Expandable lineage and methodology cell.

### Page-to-output mapping

#### Develop

- `PriceSeries`, `VolumeSeries`, `IndicatorPane`, `SignalLayer`, `TradeMarkerLayer`, `OrderLifecycleLayer`, `BenchmarkOverlay`, `DataGapLayer`, `DecisionTimeline`, synchronized multi-chart controller and editor diagnostics.

#### Portfolio

- `FinanceGrid`, `EfficientFrontier`, `RiskContributionBars`, `CorrelationMatrix`, `CovarianceMatrix`, `FactorExposureStrip`, `CapacityCurve`, constraint inspector, rebalance order grid and what-if delta view.

#### Results

- `MetricStrip`, `RelativePerformanceSeries`, `DrawdownSeries`, `RecoveryBand`, `RollingMetricSeries`, `ReturnHeatmap`, `AttributionWaterfall`, trade excursion plot, cost-drag layer and comparison rail.

#### Validate

- `ParameterSurface`, plateau contour, `FoldTimeline`, degradation distribution, `MonteCarloFan`, cost break-even curve, `CapacityCurve`, scenario impact view and evidence matrix.

#### Factors

- Distribution diagnostic, quantile return plot, IC series, `FactorDecayCurve`, interaction/correlation matrix, `FactorExposureStrip`, attribution waterfall, pure-factor performance, capacity curve, factor DNA profile and monitoring history.

#### Replay

- `PriceSeries`, `DecisionTimeline`, `OrderLifecycleLayer`, position/exposure strip, cost annotations, event navigator, synchronized comparison cursor and `BacktestPaperDivergence`.

### Visual quality standards

- Information density comparable to a professional terminal, without indiscriminate borders and cards.
- One dominant analytical surface per mode.
- Typography and spacing optimized for long sessions.
- Crisp half-pixel alignment and device-pixel-ratio-aware strokes.
- Stable layout while data loads or updates.
- No animation that delays analytical reading; motion only communicates state change.
- Every color has a non-color cue.
- Every chart has a keyboard-accessible data summary and downloadable source.
- Every visual exposes units, frequency, timezone, sample, methodology and data status.
- Tooltips never cover the selected evidence and can be pinned.
- Comparisons use shared scales when valid and explicitly warn when normalization differs.

### Performance budgets

- Initial Studio shell interaction-ready on a representative laptop within 2 seconds after cached assets.
- Pointer-to-crosshair response below one animation frame at the 95th percentile.
- Pan/zoom/playback target 60 frames per second; never below 30 frames per second under supported loads.
- No ordinary chart interaction triggers a full React page render.
- Main-thread long tasks above 50 ms are treated as defects.
- Grid DOM remains bounded through row and column virtualization.
- Multi-chart mode suspends offscreen panes and caps total backing-store pixels.
- Visual chunks load per page/mode; Plotly and WebGL research backends never enter the initial bundle.
- Memory and frame benchmarks cover 10K, 100K, 1M and 5M observation scenarios.

### Testing and observability

- Vitest for scales, transforms, aggregators, formatters and scene invalidation.
- Property-based tests for coordinate round trips, scale bounds and downsampling invariants.
- Deterministic geometry/value tests for every primitive, plus a small golden-image contract set for renderer conformance, themes, and failure-prone financial marks.
- Playwright interaction tests for pan, zoom, hover, keyboard, replay, drawings and synchronization.
- axe accessibility checks plus manual screen-reader/keyboard acceptance tests.
- Performance harness recording frame time, long tasks, memory, buffer allocations and redraw causes.
- Development overlay showing FPS, frame cost, dirty layers, visible points, selected level of detail and worker queue.
- Cross-backend conformance tests proving Canvas2D and WebGL express the same values and selections.

### Migration from current Q360Canvas

1. Freeze only financially correct behavior with deterministic fixtures and a small interaction test set; do not preserve visual defects through a large screenshot suite.
2. Extract coordinate transforms, viewport and scales into pure tested modules.
3. Convert current candles, volume, lines, trades and crosshair into typed primitives.
4. Add retained layers and dirty-region tracking.
5. Move transforms and indicators to workers.
6. Add OffscreenCanvas backend and main-thread fallback.
7. Add the owned WebGL backend only after Canvas2D benchmarks identify a real limit; PixiJS may supply low-level device, batching, and resource lifecycle if it wins the benchmark.
8. Move every page output onto `AnalysisFrame`, `ChartFrame` and `FinanceGrid`.
9. Remove direct `chart_engine` imports from pages.
10. Remove unused chart dependencies after graph, bundle, visual and smoke-test verification.

### Research basis for this stack

- PixiJS recommends stable WebGL for production while its WebGPU renderer continues to mature: <https://pixijs.com/8.x/guides/components/renderers>.
- TradingView's plugin model confirms the value of custom series and primitives layered around a stable time-series core: <https://tradingview.github.io/lightweight-charts/docs/plugins/intro>.
- OffscreenCanvas is broadly available and supports worker-side Canvas/WebGL rendering: <https://developer.mozilla.org/en-US/docs/Web/API/OffscreenCanvas>.
- TanStack Table and Virtual provide headless state and bounded rendering while leaving all markup and visual design under product control: <https://tanstack.com/table/docs/> and <https://tanstack.com/table/latest/docs/framework/react/guide/virtualization>.
- Apache Arrow JS supplies columnar typed memory and efficient interchange suitable for analytical clients: <https://arrow.apache.org/js/>.
- Comlink provides a small RPC layer for worker boundaries: <https://github.com/googlechromelabs/comlink>.
- uPlot's columnar format, scale pipeline and Canvas focus provide useful performance patterns and benchmark targets: <https://leeoniya.github.io/uPlot/docs/>.
- deck.gl documents that its WebGPU support is not yet production ready, reinforcing the Canvas2D/WebGL-first decision: <https://deck.gl/docs/developer-guide/webgpu>.

## Implementation architecture and target files

## Canonical migration decision: continue the workflow, rebuild as needed

The original Studio's single-workspace workflow is the product base. Its code is not sacred. Reconnect the workflow first so migration remains observable, then reuse only code that supports the target. A file may keep its name while being completely rewritten, or it may be replaced by a better module when compatibility exports and dependency checks make that safer. Do not build another competing shell, but do rebuild the chosen shell, tools, charts, grids, outputs, and state model as deeply as required for maximum production quality.

The target architecture below is a complete production boundary map. Create a boundary when it has clear authority, lifecycle, tests, or performance needs. Avoid ceremonial directories, but never collapse security, jobs, artifacts, mathematical truth, rendering, or domain ownership merely to make the tree look small.

### Evidence from the code graph

- The current `/studio` and `/labs/studio` routes render Studio V2 `AlgorithmLab`.
- The original `StudioLayout`, `DevelopView` and `Q360Canvas` have no live inbound route callers and are dormant.
- Before migration, the original backend router remains mounted through `backend/main.py` and still exposes data, execution, Monte Carlo, walk-forward, legacy Dynamics, health and ticker endpoints. The legacy Dynamics endpoints are current-state inventory only and are removed or reassigned under accurate domain contracts during migration.
- `backend/app/routers/studio.py` is an active compatibility surface but combines routing, market data, execution, metrics and simulations in one file.

### Product behavior that becomes the foundation

- Monaco strategy editor and strategy templates.
- Ticker, benchmark, capital, slippage and commission controls.
- Custom OHLCV canvas, volume, indicators, signals, trades and fills.
- 1x1 through 4x4 multi-chart grid.
- Synchronized cursor, zoom and playback.
- Drawing tools and custom overlays.
- Strategy A/B comparison.
- Event log.
- Layout presets and keyboard interaction.
- Equity, drawdown, tearsheet and monthly heatmap.
- Walk-forward fold presentation.
- Monte Carlo fan presentation.
- Deterministic Replay behavior.

This list preserves capabilities, not implementations. Each capability receives a reuse, rewrite, replace, merge, or remove decision after code, UX, mathematical, and performance review.

### Complete frontend architecture

```text
frontend/src/app/studio/
  page.js                           mounts OriginalStudioPage
  error.js

frontend/src/app/labs/studio/
  page.js                           redirects to /studio

frontend/src/components/studio/
  OriginalStudioPage.jsx            provider + shell composition
  StudioLayout.jsx                  final shell entry; may be fully rewritten
  StudioStore.js                    temporary compatibility facade only
  studioTypes.js                    shared input/output/event contracts
  studioApi.js                      typed API client and cancellation

  DevelopView.jsx                   final Develop composition; rewrite allowed
  TearsheetView.jsx                 temporary Results compatibility export
  ValidateView.jsx                  final Validate composition; rewrite allowed
  StressView.jsx                    temporary; later merged into Validate
  ReplayView.jsx                    final Replay composition; rewrite allowed

  shell/
    ActivityRail.jsx
    ProjectSidebar.jsx
    EditorGroup.jsx
    BottomPanel.jsx
    Inspector.jsx
    CommandLayer.jsx
    StatusBar.jsx

  develop/
  portfolio/
  results/
  validate/
  factors/
  replay/
  outputs/

  primitives/
    index.js                        one obvious public import
    FinancialCanvas.jsx             owned visual-kernel surface
    FinanceGrid.jsx
    OutputState.jsx
    Metric.jsx
    Panel.jsx
    Legend.jsx
    Tooltip.jsx

  visual-kernel/
    scene/
    scales/
    axes/
    layout/
    layers/
    picking/
    gestures/
    annotations/
    workers/
    accessibility/
    export/
    renderers/canvas2d/
    renderers/webgl/

  adapters/
    chartEngineAdapter.js
    studioApiAdapter.js
    studioV2Adapter.js
```

This structure is intentionally lean in operational dependencies but complete in ownership. The product may use the existing filenames as compatibility entry points while their internals are rewritten. Page code never owns rendering-engine details, backend transport, or financial mathematics.

### Complete backend architecture

```text
backend/app/routers/studio.py        thin compatibility routes retained

backend/app/studio/
  router.py                          final versioned API composition
  contracts/
    requests.py
    responses.py
    errors.py
    events.py
    provenance.py
  application/
    projects.py
    runs.py
    results.py
    validation.py
    factors.py
    portfolios.py
    replay.py
    paper.py
  execution/
    provider.py
    kernels.py
    jobs.py
    quotas.py
    sandbox.py
  artifacts/
    repository.py
    manifests.py
    lineage.py
    exports.py
    retention.py
  data/
    catalog.py
    universes.py
    snapshots.py
    quality.py
  engines/
    metrics.py
    backtest.py
    validation.py
    factors.py
    portfolio.py
    replay.py
  infrastructure/
    database.py
    object_store.py
    queue.py
    streams.py
    observability.py
  security/
    authorization.py
    execution_policy.py
    uploads.py
```

Existing validated Studio V2, Factors V2 and Portfolio V2 services may be called through adapters initially. Reuse is conditional, not mandatory. Incorrect, duplicated, poorly bounded, or structurally limiting code is rewritten behind the stable Studio contracts. Mathematical engines, execution isolation, artifacts, jobs, permissions, and provenance retain independent ownership even when deployed together.

### Original file decisions

| Current file | Decision | Migration action |
|---|---|---|
| `constants.js` | Rewrite or split | Keep verified strategy definitions; move limits, contracts, commands, and tokens to owned modules |
| `Editor.jsx` | Reuse Monaco, rewrite tools | Build diagnostics, persistence, commands, runtime metadata, diff, and navigation to target quality |
| `StudioStore.js` | Replace | Temporary facade while project, server, selection, layout, editor, execution, and preference state move to proper owners |
| `StudioLayout.jsx` | Rewrite allowed | Keep the single-workspace concept; rebuild rails, docks, panes, command layer, focus, and resizing as needed |
| `DevelopView.jsx` | Rewrite allowed | Preserve valuable workflows, not current component structure |
| `Q360Canvas.jsx` | Replace behind compatibility export | Build the owned visual kernel; port only correct interactions and finance semantics |
| `DrawingTools.jsx` | Rewrite allowed | Typed geometry, snapping, editing, persistence, undo, keyboard, and worker-safe hit testing |
| `CustomOverlayBuilder.jsx` | Rewrite | Typed allowlisted expression compiler, validation, previews, provenance, and bounded execution |
| `IndicatorsPanel.jsx` | Rewrite allowed | Registry-driven indicators, parameters, panes, methodology, preview, and state persistence |
| `GridChartCell.jsx` | Rewrite allowed | Virtualized/suspended cells, shared data, viewport groups, bounded rendering, and accessible focus |
| `EquityComparisonCanvas.jsx` | Merge | Move into the owned FinancialCanvas comparison layer |
| `EventLogPanel.jsx` | Rewrite allowed | Typed events, virtualization, filters, causal navigation, and bounded retention |
| `LayoutManager.jsx` | Rewrite allowed | Versioned layouts, validation, migrations, commands, and no unrelated data fetching |
| `LayoutInitModal.jsx` | Merge | Workspace initialization flow |
| `LayoutPickerModal.jsx` | Merge | Layout manager and command palette |
| `MonteCarloCanvas.jsx` | Merge | Validate/Stress output primitive |
| `PreExecuteModal.jsx` | Replace and rename | Real DataPreflightGate |
| `StressView.jsx` | Keep temporarily | Honest job-backed outputs, then merge into Validate |
| `ValidateView.jsx` | Rewrite allowed | Evidence-first fold, scenario, sensitivity, job, and verdict workflows |
| `DynamicsView.jsx` | Remove | No Dynamics page or drawer remains |
| `SpectralAnalysis.jsx` | Remove | Reintroduce a specific audited diagnostic only in its owning domain if later justified |
| `QuantKernel.js` | Replace by authority | Worker-safe display transforms only; backend owns analytical truth |
| `ReplayView.jsx` | Rewrite allowed | Canonical events, fills, state, P&L, seeking, comparison, and causal inspection |
| `StrategyLibrary.jsx` | Rewrite allowed | Server-backed versions, provenance, search, templates, permissions, and promotion status |
| `Tearsheet.jsx` | Merge | Reusable Results output primitives |
| `TearsheetView.jsx` | Replace behind compatibility export | Becomes the purpose-built Results workspace |
| `TechReferenceHub.jsx` | Remove or contextualize | Verified help belongs beside the relevant control, not in a generic runtime hub |

### Lean and complete persistence and compute decision

- PostgreSQL stores projects, versions, jobs, provenance and artifact references.
- Parquet or compressed artifacts store large arrays.
- Begin with a PostgreSQL `FOR UPDATE SKIP LOCKED` worker when deployment is single-host and job volume is modest.
- Add Celery and Redis when durable parallel workers, retries or scheduled monitoring become an observed requirement.
- Use one warm idle-expiring kernel for interactive Develop work.
- Run backtests, Monte Carlo, validation, optimization, factor research, and portfolio research as isolated jobs.
- REST handles ordinary operations, SSE handles one-way job progress, and WebSocket is reserved for the terminal/kernel.

### Continuous migration sequence

Every step must leave `/studio` usable.

1. Add a temporary route flag and make the V2 shell accessible at `/studio-v2` for comparison.
2. Create `OriginalStudioPage.jsx` and mount the original provider/layout at `/studio`.
3. Redirect `/labs/studio` to `/studio`.
4. Preserve current `/api/studio/*` URLs and add typed frontend/backend adapters around them.
5. Remove unsafe, synthetic, random and hard-coded backend behavior before adding features.
6. Add request cancellation, typed states and provenance without redesigning the visible workspace.
7. Keep `StudioStore` only as a temporary facade while replacing one state authority at a time behind compatible hooks/selectors.
8. Remove direct `chart_engine` imports. Port required behavior to the owned Q360 scene contract; use a short-lived adapter only where it reduces migration risk.
9. Replace `Q360Canvas` behind its compatibility export with the owned visual kernel. Incremental extraction is optional; a full rewrite is preferred when it produces cleaner authority, performance, or correctness.
10. Rename Tearsheet to Results and merge Stress into Validate after behavior parity.
11. Transplant one verified V2 capability at a time through `studioV2Adapter`.
12. Remove Dynamics and Spectral routes, UI, stores, endpoints, caches, and claims after moving any independently approved diagnostics to their true owners.
13. Delete duplicate shells, components, routes and packages only after graph, import, route, contract, and focused interaction verification.

### V2 transplant policy

Transplant capability, not presentation duplication.

- Reuse Studio V2 isolated jobs, lineage, honest metrics, reconciliation, data catalog, robustness, optimizer, factor and portfolio services when tests prove correctness.
- Reuse the best interaction ideas from V2 custom primitives: output configuration, annotations, pinned summaries, drill-down, workspace export/import, comparison, progress and typed output states.
- Render those capabilities using the final rewritten single-workspace shell and owned primitives.
- Do not carry across V2's separate shell, route sprawl, giant headings, generic JSON outputs or duplicated navigation.

### Concrete V2 retirement scope after parity

The following frontend routes are redirected to the corresponding internal `/studio` mode, then removed after bookmarks, tests and navigation are migrated:

- `frontend/src/app/studio/backtest/page.js`
- `frontend/src/app/studio/data/page.js`
- `frontend/src/app/studio/factors/page.js`
- `frontend/src/app/studio/optimizer/page.js`
- `frontend/src/app/studio/portfolio-risk/page.js`
- `frontend/src/app/studio/robustness/page.js`
- `frontend/src/app/labs/studio/page.js` after its redirect deprecation window

Within `frontend/src/components/studio-v2`, retire `AlgorithmLab.jsx`, its alternate shell/navigation and shell-only styling after the original Studio reaches parity. Domain components are not bulk-deleted. Each is either transplanted behind an original-Studio mode, converted into an owned primitive, or proven unused through the graph and smoke tests. Stores, hooks and types under `frontend/src/stores/studio`, `frontend/src/hooks/studio` and `frontend/src/types/studio` are merged into the original compatibility layer one domain at a time before duplicates are removed.

No backend Studio V2 engine is deleted merely because its frontend shell is retired. Backend services remain available through adapters until the target service has parity tests and all inbound routes are migrated.

### First vertical production release

The first release is deliberately smaller than the final feature map:

1. Reconnected single-workspace Studio with the rewritten production shell foundation.
2. Honest data and execution paths.
3. Stable Develop canvas/editor/grid/playback.
4. Truthful Results.
5. Real quick Validate and Monte Carlo job.
6. Deterministic Replay.
7. Typed errors, provenance, cancellation and smoke tests.

Portfolio construction, full Factors, certification, monitoring and extension APIs follow as vertical slices after this base is stable.

### Lessons from existing V2 custom primitives

The code graph identifies 437 functions across the existing V2 `customPagePrimitives` files. Strong patterns worth retaining include:

- Factors V2: chart synchronization, output configuration, custom holdings/ticker inputs, annotations, drill-down, pinned summaries, workspace import/export, factor decay, attribution, capacity, crisis comparison and monitoring.
- Portfolio V2: construction, backtest, attribution, stress, macro, regime, liquidity, contagion, decay, Kelly, execution, systemic-risk and strategy primitives.
- Volatility V2: output dock/minimap, comparison runs, forecast bands, volatility cone, regime dashboard, estimator comparison, QQ plot, ridge plot, network graph, drawing canvas and export.
- ML V2: output dock, custom metric panels, scatter/quadrant/network views, run progress, sticky summaries, input curtain and output export.
- Research/Screener V2: decision ledger, specification curves, event studies, regression tables, alert tape, change reports and configurable output rails.

The existing pattern must not be copied literally. `factors-v2/customPagePrimitives.jsx` is approximately 219 KB, while several sibling primitive files are 80–120 KB. A single giant implementation file makes testing, lazy loading, tree shaking and ownership worse.

The final compromise is:

- One global public primitives import: `@/studio/primitives`.
- One page/domain output registry such as `portfolio.outputs.ts` or `factors.outputs.ts`, re-exported through the global barrel only when cross-page reuse is intentional.
- One page-specific output registry per page.
- Small typed implementations underneath.
- No page imports individual third-party rendering libraries.

### Target frontend tree

```text
frontend/src/
  app/studio/
    layout.tsx
    page.tsx                         mounts OriginalStudioPage; Develop is the default internal mode
    loading.tsx
    error.tsx
    __tests__/routes.test.tsx

  studio/
    shell/
      StudioShell.tsx
      ActivityRail.tsx
      ContextBar.tsx
      CommandPalette.tsx
      DockManager.tsx
      JobsDrawer.tsx
      ProblemsDrawer.tsx
      ProvenanceDrawer.tsx
      CompareTray.tsx
      DataWorkspaceOverlay.tsx
      StatusBar.tsx
      WorkspaceRestore.tsx

    pages/
      develop/
        DevelopWorkspace.tsx
        develop.inputs.ts
        develop.outputs.ts
        develop.commands.ts
        develop.layout.ts
      portfolio/
        PortfolioWorkspace.tsx
        portfolio.inputs.ts
        portfolio.outputs.ts
        portfolio.commands.ts
        portfolio.layout.ts
      results/
        ResultsWorkspace.tsx
        results.inputs.ts
        results.outputs.ts
        results.commands.ts
        results.layout.ts
      validate/
        ValidateWorkspace.tsx
        validate.inputs.ts
        validate.outputs.ts
        validate.commands.ts
        validate.layout.ts
      factors/
        FactorsWorkspace.tsx
        factors.inputs.ts
        factors.outputs.ts
        factors.commands.ts
        factors.layout.ts
      replay/
        ReplayWorkspace.tsx
        replay.inputs.ts
        replay.outputs.ts
        replay.commands.ts
        replay.layout.ts

    primitives/
      index.ts                        single public primitives entrypoint
      contracts.ts
      registry.ts
      states/
        EmptyOutput.tsx
        LoadingOutput.tsx
        PartialOutput.tsx
        StaleOutput.tsx
        FailedOutput.tsx
        CancelledOutput.tsx
        InsufficientDataOutput.tsx
      shell/
        AnalysisFrame.tsx
        ChartFrame.tsx
        MetricStrip.tsx
        InspectorDock.tsx
        LegendRail.tsx
        MethodBadge.tsx
        QualityBadge.tsx
        ComputeBadge.tsx
        OutputToolbar.tsx
      inputs/
        SymbolInput.tsx
        UniverseInput.tsx
        HoldingsInput.tsx
        StrategyInput.tsx
        FactorInput.tsx
        DateRangeInput.tsx
        ParameterEditor.tsx
        ConstraintEditor.tsx
        ScenarioBuilder.tsx
        CostModelEditor.tsx
      grids/
        FinanceGrid.tsx
        VirtualGrid.tsx
        cells/
          NumericCell.tsx
          ChangeCell.tsx
          ContributionCell.tsx
          SparkCell.tsx
          ConfidenceCell.tsx
          ExposureCell.tsx
          ConstraintCell.tsx
          ProvenanceCell.tsx
      charts/
        FinancialChart.tsx
        FinancialChartA11y.tsx
        ChartInspector.tsx
        ChartLegend.tsx
        ChartToolbar.tsx
      finance/
        PriceOutput.tsx
        DrawdownOutput.tsx
        AttributionOutput.tsx
        CapacityOutput.tsx
        FrontierOutput.tsx
        MatrixOutput.tsx
        MonteCarloOutput.tsx
        ParameterSurfaceOutput.tsx
        FactorOutput.tsx
        ReplayOutput.tsx
      collaboration/
        AnnotationLayer.tsx
        CommentThread.tsx
        PinnedSummary.tsx
      export/
        ExportMenu.tsx
        ReproducibilityManifest.tsx
        ReportComposer.tsx

    visual-kernel/
      contracts/
      data/
      scales/
      layout/
      scene/
      marks/
      finance/
      interaction/
      annotations/
      backends/canvas2d/
      backends/offscreen/
      backends/webgl/
      workers/
      accessibility/
      export/
      testing/
      index.ts

    editor/
      MonacoWorkspace.tsx
      FileExplorer.tsx
      NotebookSurface.tsx
      TerminalSurface.tsx
      VariableInspector.tsx
      DependencyInspector.tsx
      ProblemsPanel.tsx
      ExecutionTimeline.tsx

    stores/
      workspace.store.ts
      layout.store.ts
      chart.store.ts
      editor.store.ts
      execution.store.ts
      comparison.store.ts
      selection.store.ts
    queries/
      queryKeys.ts
      studio.client.ts
      jobs.client.ts
      kernel.client.ts
      artifacts.client.ts
    contracts/
      common.ts
      project.ts
      strategy.ts
      run.ts
      portfolio.ts
      validation.ts
      factor.ts
      replay.ts
      artifact.ts
      errors.ts
    workers/
      data.worker.ts
      indicator.worker.ts
      render.worker.ts
      export.worker.ts
    styles/
      tokens.css
      shell.css
      editor.css
      outputs.css
      print.css
```

### Target backend tree

```text
backend/app/studio/
  router.py                          thin route composition only
  dependencies.py
  contracts/
    common.py
    projects.py
    strategies.py
    runs.py
    portfolios.py
    validation.py
    factors.py
    replay.py
    jobs.py
    artifacts.py
    errors.py
  api/
    projects.py
    strategies.py
    kernel.py
    backtests.py
    portfolios.py
    validation.py
    factors.py
    replay.py
    data.py
    jobs.py
    artifacts.py
    exports.py
  application/
    project_service.py
    strategy_service.py
    run_service.py
    portfolio_service.py
    validation_service.py
    factor_service.py
    replay_service.py
    promotion_service.py
  domain/
    project.py
    strategy.py
    orders.py
    fills.py
    portfolio.py
    factors.py
    validation.py
    lineage.py
    provenance.py
  engines/
    backtest/
      engine.py
      event_loop.py
      execution_model.py
      cost_model.py
      corporate_actions.py
      metrics.py
      attribution.py
    portfolio/
      construction.py
      covariance.py
      optimizer.py
      capacity.py
      scenarios.py
    validation/
      walk_forward.py
      perturbation.py
      bootstrap.py
      monte_carlo.py
      cpcv.py
      overfitting.py
      scorer.py
    factors/
      evaluator.py
      transforms.py
      diagnostics.py
      backtest.py
      attribution.py
      covariance.py
      optimizer.py
      capacity.py
      stress.py
      monitoring.py
    replay/
      event_log.py
      reconstruction.py
      reconciliation.py
  data/
    loader.py
    catalog.py
    universe.py
    snapshots.py
    quality.py
    manifests.py
  execution/
    sandbox.py
    kernel_manager.py
    kernel_protocol.py
    terminal_policy.py
    limits.py
  jobs/
    celery_app.py
    tasks.py
    scheduler.py
    progress.py
    cancellation.py
    deduplication.py
  persistence/
    models.py
    repositories.py
    migrations/
  artifacts/
    store.py
    retention.py
    serializers.py
    export.py
  observability/
    logging.py
    metrics.py
    tracing.py
    audit.py
  tests/
    unit/
    contract/
    integration/
    performance/
    fixtures/
```

### Backend migration rule

Existing validated Studio V2, Factors V2 and Portfolio V2 engines are migrated, not blindly rewritten. Routes become thin adapters. Shared loading, data manifests, liquidity, persistence, Monte Carlo and error utilities move into `studio/data`, `studio/artifacts`, `studio/persistence`, `studio/engines/validation` and `studio/contracts/errors.py` according to ownership. Raw JSON/SQLite storage under `studio_v2/storage` is replaced by repositories and artifact storage after migration tests prove parity.

`backend/app/routers/studio.py` is the only mounted Studio router during the initial migration. It delegates into the target `backend/app/studio` contracts, application services, execution, artifacts, data, engines, infrastructure, and security owners as they become ready. `backend/app/studio/router.py` becomes the final router once at least three independently owned API groups exist or the compatibility router remains above roughly 400 meaningful lines after extraction. At that point, `backend/app/routers/studio.py` becomes a one-release import shim preserving existing mounts and paths; it is removed after route-contract and client migration tests pass. Both routers never contain parallel business logic.

Factors F01–F14 map as follows:

- F01 valuation, F04 regimes, F05 decay, F06 crowding and F12 DNA move to `studio/engines/factors/diagnostics.py` and focused helpers when needed.
- F02 exposure decomposition and F03 return attribution move to `studio/engines/factors/attribution.py`.
- F07 backtesting moves to `studio/engines/factors/backtest.py`.
- F08 covariance moves to `studio/engines/factors/covariance.py`.
- F09 capacity moves to `studio/engines/factors/capacity.py`.
- F10 optimization moves to `studio/engines/factors/optimizer.py`.
- F11 stress moves to `studio/engines/factors/stress.py`.
- F13 monitoring moves to `studio/engines/factors/monitoring.py`.
- F14 report generation moves to `studio/artifacts/export.py` with factor-specific composition supplied by `factor_service.py`.

## Per-page product contracts

### Develop contract

**Description:** A complete quantitative IDE for writing, inspecting and forward-testing strategies.

**Required inputs**

- Project, code version and environment.
- Strategy entrypoint.
- Symbols or universe.
- Dataset snapshot and date range.
- Frequency, timezone and adjustment policy.
- Starting capital and benchmark.
- Execution, slippage, commission, borrow and participation assumptions.
- Parameters, secrets references and dependency lock.

**Optional inputs and user freedom**

- Code, notebook cells or visual parameter declarations.
- Custom files, packages, data uploads, factors and derived fields.
- Layout profile, editor keymap, theme density and keyboard shortcuts.
- Saved snippets, templates, run configurations and environment profiles.
- Custom chart layers and internal output specifications through approved typed extension points.

**Primary features**

- Monaco IDE, project files, notebook, terminal, warm kernel, variables, dependencies, problems and version diff.
- Strategy execution, event log, debugger diagnostics, parameter declarations and run history.
- Price/indicator workspace, drawings, multi-chart, playback and paper execution.

**Outputs**

- Compile/lint diagnostics.
- Cell/file execution output.
- Structured signals, orders, fills, positions and state snapshots.
- Backtest/paper run record.
- Equity, exposure and event streams.
- Logs, exceptions, timing, memory and dependency lineage.
- Promotion-ready strategy artifact.

**Custom outputs**

- Financial price workspace with indicators, signals, fills and decision trace.
- Variable/dataframe explorer.
- Execution flame/timing lane.
- Order lifecycle and state-transition timeline.
- Dependency graph and stale-cell map.
- Run-diff view and backtest-paper divergence preview.

### Portfolio contract

**Description:** A construction and decision workspace for combining assets, strategies, factors and sleeves under real constraints.

**Required inputs**

- Portfolio or holdings.
- Assets, saved strategies, factor portfolios or return series.
- Weights or allocation method.
- Benchmark, capital, currency and rebalance policy.
- Dataset snapshot and cost/liquidity assumptions.

**Optional inputs and user freedom**

- Custom expected returns, covariance, factor targets and capital-market assumptions.
- Hard/soft constraints, nested groups, custom tags and risk budgets.
- Custom objective built from an approved objective-function library.
- Proposed trades, hedges, cash flows and scenario presets.
- Saved model portfolios, sleeves, comparison sets and layout profiles.

**Primary features**

- Build, Optimize, What-if and Monitor modes.
- Multi-sleeve construction, constrained optimization, risk budgeting, capacity and rebalance planning.
- Portfolio backtest, exposure analysis, scenario testing and paper drift monitoring.

**Outputs**

- Current, target, optimized and benchmark weights.
- Expected and realized portfolio statistics.
- Risk, factor, sector, country, currency and strategy exposures.
- Marginal/component risk and diversification contribution.
- Rebalance orders, costs, capacity, violations and residual risk.
- Scenario impacts, hedge candidates and optimization diagnostics.

**Custom outputs**

- Portfolio tree and editable holdings grid.
- Efficient frontier with selectable candidates.
- Risk-budget and contribution waterfall.
- Correlation/covariance matrix with clustering.
- Constraint feasibility map.
- Rebalance trade tape and cost decomposition.
- What-if delta canvas and factor hedge residual view.
- Capacity/liquidity curve and portfolio drift map.

### Results contract

**Description:** The authoritative explanation of performance, risk, trades and differences between runs.

**Required inputs**

- One completed or partial run.
- Its strategy/portfolio version, data snapshot, benchmark and methodology.

**Optional inputs and user freedom**

- Up to three comparison runs.
- Custom metric selection, ordering and saved report layout.
- User-defined benchmark or derived comparison series.
- Filters for date, regime, asset, strategy, sleeve, factor, side and trade cohort.
- Annotations, pinned findings and report narrative.

**Primary features**

- Overview, Risk, Attribution, Trades, Compare and Report modes.
- Honest metrics, rolling analysis, drawdowns, factor/asset attribution and execution diagnosis.

**Outputs**

- Performance, benchmark-relative, risk, exposure and trade metrics.
- Equity, return, drawdown, rolling and calendar series.
- Asset/strategy/factor/decision attribution.
- Orders, fills, trades, MAE/MFE, costs and holding periods.
- Data-quality, sample, method and provenance metadata.

**Custom outputs**

- Dense metric strip and definition inspector.
- Equity/drawdown linked canvas.
- Drawdown episode explorer.
- Attribution waterfall with drill-through.
- Trade-excursion and holding-period distributions.
- Cost-drag and slippage post-mortem.
- Multi-run difference view with normalized/shared-scale controls.
- Custom report composer and reproducibility package.

### Validate contract

**Description:** A bounded evidence system that tests whether a strategy or portfolio is stable, realistic and promotion-ready.

**Required inputs**

- Strategy or portfolio run definition.
- Parameters and permissible ranges.
- Dataset/universe snapshots.
- Costs, execution assumptions and validation preset.

**Optional inputs and user freedom**

- Custom folds, embargo, purging, perturbations, scenarios and acceptance thresholds.
- User-selected objective and guardrail metrics.
- Compute budget, concurrency, seed and early-stopping policy.
- Saved validation recipes and comparison baselines.

**Primary features**

- Quick Check, Stability, Out-of-Sample, Costs & Capacity, Scenarios and Certification.
- Walk-forward, parameter surfaces, perturbation, transaction-cost break-even, capacity, Monte Carlo, bootstrap, CPCV, DSR and PBO.

**Outputs**

- Test-by-test result, assumptions, evidence and status.
- Fold/trial registry.
- Parameter selections and stability regions.
- OOS degradation, costs, capacity, scenario loss and overfitting evidence.
- Promotion verdict with explicit failed/unavailable tests.

**Custom outputs**

- Validation evidence matrix.
- Parameter plateau/response canvas.
- Fold timeline and degradation distribution.
- Monte Carlo fan and ruin threshold.
- Cost break-even and capacity curves.
- Scenario replay grid.
- Overfitting evidence panel and transparent composite report.

### Factors contract

**Description:** One institutional workflow for discovering, testing, understanding, constructing, stressing and monitoring factors.

**Required inputs**

- Factor expression or saved factor.
- Universe and date range.
- Forward return horizon.
- Data snapshot and point-in-time policy.
- Transform, neutralization and missing-data rules.

**Optional inputs and user freedom**

- Custom fields, formulas, transforms, risk models and factor combinations.
- Portfolio holdings for exposure/attribution.
- Quantiles, lags, regimes, costs, constraints, scenarios and monitoring thresholds.
- Saved factor workspaces, annotations, output ordering and comparison sets.

**Primary features**

- Discover, Test, Understand, Construct, Stress and Monitor.
- Existing F01–F14 backend capabilities plus expression, IC, interactions, orthogonalization and factor library.

**Outputs**

- Factor values, coverage, distribution and missingness.
- IC/rank IC, confidence, decay, turnover, quantile returns and factor backtests.
- Exposures, attribution, covariance, capacity, stress, DNA and monitoring events.
- Pure-factor or optimized portfolio candidates.
- Model coverage, residual risk, proxy/fallback and methodology metadata.

**Custom outputs**

- Expression/data lineage graph.
- Cross-sectional distribution and quantile ladder.
- IC/decay synchronized view.
- Rolling exposure and regime ribbon.
- Orthogonalization and redundancy network.
- Factor attribution waterfall.
- Capacity/crowding dashboard.
- Factor DNA profile.
- Monitoring health timeline and report composer.

### Replay contract

**Description:** A deterministic reconstruction of market state, strategy reasoning, orders and fills.

**Required inputs**

- Run and data snapshot.
- Event log and execution assumptions.
- Replay start/end and speed.

**Optional inputs and user freedom**

- Second run or paper session.
- Selected event classes, charts, indicators and state variables.
- User bookmarks, annotations and saved replay layouts.

**Primary features**

- Market, Decision, Execution and Compare modes.
- Synchronized playback, event navigation, state reconstruction and backtest-paper comparison.

**Outputs**

- Point-in-time market, portfolio, signal, order, fill, position, cash, exposure and variable state.
- Decision trace and condition evaluation.
- Execution/cost timeline and divergence explanation.
- Replay bookmarks, snapshots and incident package.

**Custom outputs**

- Synchronized financial chart workspace.
- Decision tree/state inspector.
- Signal-order-fill lifecycle lane.
- Portfolio state strip.
- Event minimap and bookmark rail.
- Dual-run comparison cursor.
- Backtest-paper divergence canvas.

## Maximum user freedom without product chaos

### Users may customize

- Workspace layout, pane placement, size, visibility and saved profiles.
- Editor keymap, shortcuts, density and accessible theme variants.
- Inputs, formulas, parameters, universes, factors, constraints, objectives and scenarios.
- Chart layers, indicators, drawings, annotations, scales and synchronization groups.
- Output order, pinned outputs, comparison sets, filters, tables, columns and precision.
- Reports, exports, notebooks, code, dependencies and approved data uploads.
- Compute budget within platform limits.

### Users may extend through typed contracts

- `StrategyPlugin`
- `IndicatorPlugin`
- `FactorTransformPlugin`
- `PortfolioObjectivePlugin`
- `ScenarioPlugin`
- `OutputPrimitivePlugin`
- `DataAdapterPlugin`

Each plugin declares input/output schema, deterministic behavior, compute class, permissions, provenance and renderer compatibility. User extensions never receive unrestricted browser/server authority.

### The product still controls

- Truthfulness and data labels.
- Security sandbox and resource limits.
- Financial units and method disclosure.
- Error contracts and output states.
- Accessibility and export requirements.
- Reproducibility and lineage.
- Which code may execute synchronously.

## Final feature-list verdict

The six-page feature list is sufficiently broad. Adding more primary pages would reduce quality. Eight high-value capabilities should be added across the existing pages and global shell:

1. **Hypothesis and decision ledger:** attach thesis, expected mechanism, falsification rule and outcome to each experiment.
2. **Experiment graph:** show ancestry across code, data, parameter, factor, validation and portfolio changes.
3. **Data preflight gate:** block analytical runs when point-in-time, coverage, freshness or adjustment requirements fail.
4. **Promotion gates:** explicit Research → Backtest → Validated → Paper states with evidence requirements.
5. **Output composer:** pin any verified output into a reusable report or monitoring workspace.
6. **Saved recipes:** reusable run, validation, factor, portfolio, scenario and report configurations.
7. **Decision trace:** explain the exact conditions and inputs behind every signal/order.
8. **Reproduction bundle:** code, environment, data manifest, parameters, engine version, outputs and checksums in one artifact.

Lower-value additions are rejected unless later demand proves them: social feeds, an open public plugin marketplace, decorative 3D, unrestricted AI-generated trading logic, GPU sessions, and duplicated dashboards.

## Work estimate: normal output versus maximum custom system

These estimates assume experienced engineers, existing backend mathematics are reused where correct, and workstreams overlap. They are engineering ranges, not calendar promises.

| Scope | Normal library-heavy output | Maximum owned system |
|---|---:|---:|
| Product shell and navigation | 2–3 engineer-weeks | 5–8 engineer-weeks |
| IDE, files, kernel, terminal, variables | 6–10 | 16–26 |
| Visual kernel and chart primitives | 5–8 | 24–40 |
| Custom grids and output shells | 3–5 | 10–16 |
| Develop page completion | 4–7 | 12–20 |
| Portfolio page completion | 5–8 | 14–22 |
| Results page completion | 3–5 | 8–14 |
| Validate page completion | 5–9 | 14–24 |
| Factors page completion | 6–10 | 16–28 |
| Replay page completion | 4–7 | 12–20 |
| Backend consolidation/jobs/artifacts | 8–12 | 18–30 |
| Accessibility, testing and performance | 5–8 | 16–24 |
| Total engineering effort | **56–92 engineer-weeks** | **165–272 engineer-weeks** |

### Interpretation

- The maximum system is roughly **2.5–3 times** the work of a normal library-heavy implementation.
- One strong full-time engineer working sequentially would need roughly **3.5–6 years** for the complete maximum scope at production quality.
- A coordinated team of six experienced engineers can target roughly **8–14 calendar months**, depending on backend correctness and how much existing V2 code passes verification.
- A focused first production release covering the shell, Develop, Results, quick Validate, core Factors, jobs and trustworthy outputs is approximately **70–110 engineer-weeks**, or about **4–7 months** for six engineers with parallel work.

### Why the extra work exists

- Owned rendering engines require scale, layout, picking, accessibility, export and cross-browser work normally supplied by chart libraries.
- IDE kernels and terminals require isolation, lifecycle, persistence and failure recovery.
- Financial correctness requires deterministic engines, provenance and edge-case tests.
- Custom outputs require domain-specific interaction and drill-through rather than generic cards.
- Maximum freedom requires typed extension contracts, migration policy and resource governance.

### Recommended delivery boundary

Do not attempt all 165–272 engineer-weeks before showing users value. Build the owned contracts and shell first, then deliver vertical slices:

1. Develop + trustworthy backtest + Results.
2. Quick Validate + Replay.
3. Factors Discover/Test/Understand.
4. Portfolio Build/What-if.
5. Advanced optimization, certification, monitoring and extension APIs.

Every slice uses the final architecture, so no throwaway generic frontend is required.

## Final compute and infrastructure model

### Interactive path

- Next.js frontend.
- FastAPI API.
- Warm isolated Python kernel per active project.
- WebSocket only for the kernel, terminal, and truly bidirectional live sessions.
- REST for reads, writes, run creation, and stored results.
- SSE for one-way job progress and logs where appropriate.

### Durable job path

- Celery for backtests, validation, optimization, factor jobs, reports, and scheduled monitoring.
- Celery Beat is the single authoritative scheduler for enabled reports and monitoring checks; ordinary interactive jobs do not pass through Beat.
- Redis only as Celery broker and ephemeral progress transport.
- PostgreSQL for projects, versions, jobs, results, permissions, provenance, and authoritative state.
- Isolated worker subprocess/container with CPU, RAM, runtime, network, and filesystem controls.
- Parquet for large columnar artifacts; object storage only when deployment becomes multi-host.
- PostgreSQL stores artifact metadata, checksums, owners, lineage, retention policy, expiry, job status, and bounded partial-diagnostic manifests. Parquet or object storage holds the large payload itself.
- A scheduled cleanup job removes expired payloads only after checking retention, references, and pinned status; metadata tombstones remain for auditability.

### Resource policy

- Warm kernel: one per active project, 30–60 minute idle expiry, restartable.
- Heavy jobs never depend on the browser or kernel remaining open.
- Every heavy action displays estimate, bounds, progress, cancellation, and retained partial diagnostics where valid.
- Default concurrency is based on available RAM and workload size, not CPU count alone.
- Identical jobs are deduplicated using code, parameters, dataset snapshot, engine version, and cost-model hashes.
- GPU is optional for a future model that proves it needs one, never a default Studio dependency.

## Final user journey

1. Open or create a project.
2. Select a point-in-time dataset and universe.
3. Develop and debug a strategy in Code, Chart, or Notebook mode.
4. Run an honest backtest.
5. Inspect Results and Replay failures.
6. Research or attach factors when the strategy thesis requires them; test factors inside Factors.
7. Validate strategy stability, costs, capacity, and out-of-sample behavior; validation may send the user back to Develop or Factors.
8. Combine approved strategies and factors into a Portfolio.
9. Run portfolio what-if, stress, and optimization; iterate through Factors or Validate when evidence changes.
10. Promote the strategy to Develop > Paper.
11. Monitor allocation and exposure drift in Portfolio, inspect performance in Results, and reconcile paper behavior against backtest assumptions.

## Sources and product lessons

- QuantConnect's connected idea-to-research-to-backtest-to-paper pipeline supports a continuous project lifecycle: <https://www.quantconnect.com/docs/v2/cloud-platform/research-pipeline>.
- QuantConnect treats optimization as a durable, costed concurrent job rather than an ordinary synchronous request: <https://www.quantconnect.com/docs/v2/cloud-platform/optimization/deployment>.
- MSCI BarraOne joins factor risk, attribution, stress, what-if analysis, and reporting around holdings: <https://www.msci.com/data-and-analytics/portfolio-management/barra-one>.
- Bloomberg PORT emphasizes unified positions, attribution, optimization, scenario analysis, data validation, and automated reporting: <https://professional.bloomberg.com/products/bloomberg-terminal/portfolio-analytics/>.
- Axioma supports multiple factor-model types and horizons, pure factor portfolios, custom models, hedging, and risk budgeting: <https://www.simcorp.com/solutions/axioma-solutions/axioma-factor-risk-models/axioma-equity-factor-risk-models>.
- Portfolio Visualizer validates saved models, custom data series, factor regression, factor matching, forward assumptions, rolling optimization, and approachable portfolio workflows: <https://www.portfoliovisualizer.com/faq> and <https://www.portfoliovisualizer.com/analysis>.
- Alpaca documents why paper trading needs identical interfaces but explicit simulation limitations: <https://docs.alpaca.markets/docs/paper-trading>.
- OpenBB demonstrates configurable API-backed analytical views while reserving WebSockets for genuinely live grids: <https://docs.openbb.co/workspace/developers/json-specs/widgets-json-reference>.

## Definition of the final product

The final Studio is a single research operating system. It lets a user write and inspect strategies, build portfolios, understand results, validate robustness, research factors, replay decisions, and progress into paper monitoring without losing project context or receiving fabricated evidence. Advanced institutional capabilities exist, but remain organized into clear modes and execute only when the user asks for them.
