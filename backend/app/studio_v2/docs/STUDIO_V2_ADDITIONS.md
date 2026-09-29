# QUANT360 Studio v2 — Feature Additions Map

28 new features across 6 pages + Page 7 + 1 cross-cutting addition.
For every feature: description, existing files to modify, new files to create, API routes needed, and data dependencies.

---

## PAGE 1 — ALGORITHM LAB ADDITIONS

### F1.10 — Strategy Template Library

**Description:** Gallery of pre-built starter strategies (cross-sectional momentum, time-series momentum, mean-reversion, stat-arb, vol carry, factor-tilt). Each is a working `.py` with inline comments. Selecting one forks into a new Algorithm Lab session pre-wired to data accessors and config schema. Templates tagged by complexity and universe type.

**Depends on:** F1.6 (File System), F1.2 (Kernel session creation)

**Existing files to modify:**
- `frontend/src/components/studio-v2/AlgorithmLab.jsx` — add template library sidebar trigger
- `backend/app/studio_v2/router.py` — add routes for template CRUD

**New frontend:**
- `frontend/src/components/studio-v2/StrategyTemplateLibrary.jsx`

**New backend:**
- `backend/app/studio_v2/algorithm_lab/templates.py`
- `backend/app/studio_v2/data/templates/` (directory with `.py` template files for each strategy family)

**API routes to add:**
```
GET  /api/v2/algorithm-lab/templates → list templates with metadata
GET  /api/v2/algorithm-lab/templates/{id} → get template source + config
POST /api/v2/algorithm-lab/templates/{id}/fork → create new session from template
```

---

### F1.11 — Multi-Strategy Portfolio Composition View

**Description:** Workspace to select 2–10 strategies from Algorithm Lab and combine into a single portfolio construct with configurable weighting (equal, risk-parity, custom Python allocator). Each sub-strategy's signals exposed as named variables in the combined kernel. Feeds the cross-strategy backtest (F2.9) and Portfolio Risk page.

**Depends on:** F1.2 (Kernel multi-namespace), F2.9 (Portfolio backtest)

**Existing files to modify:**
- `frontend/src/components/studio-v2/AlgorithmLab.jsx` — add composition view tab
- `backend/app/studio_v2/router.py` — add composition routes
- `backend/app/studio_v2/algorithm_lab/kernel.py` — multi-strategy namespace handling

**New frontend:**
- `frontend/src/components/studio-v2/PortfolioComposition.jsx`
- `frontend/src/hooks/studio/usePortfolioComposition.js`
- `frontend/src/stores/studio/portfolioCompositionStore.js`

**New backend:**
- `backend/app/studio_v2/algorithm_lab/portfolio_composer.py`

**API routes to add:**
```
POST /api/v2/algorithm-lab/compose → create portfolio from strategy IDs
GET  /api/v2/algorithm-lab/compose/{id} → get portfolio composition
POST /api/v2/algorithm-lab/compose/{id}/execute → run combined kernel
```

---

### F1.12 — Notebook-to-Production Export

**Description:** One-click export stripping all platform-specific dependencies and outputting a clean standalone Python module with `generate_signals()`, `requirements.txt`, and README.

**Depends on:** F1.6 (File System reads), F1.2 (Kernel source access)

**Existing files to modify:**
- `frontend/src/components/studio-v2/FileManager.jsx` — add export button in context menu
- `backend/app/studio_v2/router.py` — add export route

**New frontend:**
- `frontend/src/components/studio-v2/ExportCleanModule.jsx`

No new backend service needed — logic lives in a thin endpoint that parses kernel source.

**API routes to add:**
```
POST /api/v2/algorithm-lab/export/{strategy_id} → body: { format: "zip" }
```

---

### F1.13 — Collaborative Kernel Sessions

**Description:** Second user joins active kernel session as read-only or co-editing observer. Real-time editor state, variable inspector, live chart sync. Cursor position visible per participant.

**Depends on:** F1.1 (Editor), F1.2 (Kernel), F1.5 (Variable Inspector)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add WebSocket endpoint
- `frontend/src/components/studio-v2/AlgorithmLab.jsx` — add collaboration mode toggle
- `frontend/src/components/studio-v2/Editor.jsx` — multi-cursor support (Monaco editor)
- `frontend/src/components/studio-v2/VariableInspector.jsx` — real-time sync
- `frontend/src/components/studio-v2/StudioChartPanel.jsx` — real-time sync

**New frontend:**
- `frontend/src/components/studio-v2/CollaborativeSession.jsx`
- `frontend/src/hooks/studio/useCollaboration.js`

**New backend:**
- `backend/app/studio_v2/algorithm_lab/collaboration.py` (WebSocket handler)

**API routes to add:**
```
WS   /api/v2/algorithm-lab/session/{session_id}/collaborate → WebSocket for real-time sync
POST /api/v2/algorithm-lab/session/{session_id}/invite → body: { user_id, role: "read"|"edit" }
GET  /api/v2/algorithm-lab/session/{session_id}/participants → list active participants
```

---

### F1.14 — Compute Budget Guardrail Panel

**Description:** Persistent status indicator showing active compute load (running cells, queued jobs) with manual kill switch. Cell execution exceeding configurable wall-clock threshold (default 60s) surfaces "still running — kill?" prompt.

**Depends on:** F1.2 (Kernel execution lifecycle), F1.3 (Terminal)

**Existing files to modify:**
- `backend/app/studio_v2/algorithm_lab/kernel.py` — add execution timeout monitoring, kill API
- `frontend/src/components/studio-v2/AlgorithmLab.jsx` — add guardrail bar
- `backend/app/studio_v2/router.py` — add kill route

**New frontend:**
- `frontend/src/components/studio-v2/ComputeGuardrail.jsx`

**New backend:**
- `backend/app/studio_v2/algorithm_lab/compute_budget.py`

**API routes to add:**
```
GET  /api/v2/algorithm-lab/session/{session_id}/compute-status → running/queued jobs
POST /api/v2/algorithm-lab/session/{session_id}/kill/{job_id} → kill specific job
POST /api/v2/algorithm-lab/session/{session_id}/kill-all → kill all running jobs
```

---

### F1.15 — Snippet/Macro Library

**Description:** Lightweight library of reusable code fragments (rolling z-score, cost-model boilerplate, plotting calls) insertable via command palette or autocomplete trigger. Not version-controlled — snippets are copy-paste-and-modify.

**Depends on:** F1.1 (Editor autocomplete provider)

**Existing files to modify:**
- `frontend/src/components/studio-v2/Editor.jsx` — add snippet autocomplete provider
- `backend/app/studio_v2/router.py` — add snippet CRUD routes

**New frontend:**
- `frontend/src/components/studio-v2/SnippetLibrary.jsx`
- `frontend/src/hooks/studio/useSnippets.js`

**New backend:**
- `backend/app/studio_v2/algorithm_lab/snippets.py`

**API routes to add:**
```
GET  /api/v2/algorithm-lab/snippets → list snippets with tags
POST /api/v2/algorithm-lab/snippets → create snippet
PUT  /api/v2/algorithm-lab/snippets/{id} → update snippet
DELETE /api/v2/algorithm-lab/snippets/{id} → delete snippet
```

---

## PAGE 2 — BACKTEST STUDIO ADDITIONS

### F2.9 — Multi-Strategy / Portfolio-Level Backtest

**Description:** Runs the combined portfolio construct (from F1.11) through the event-driven engine as a single simulation. Produces combined equity curve, combined Sharpe/Sortino/drawdown, and pairwise correlation matrix between constituent strategies' daily returns. Flags pairs with correlation > configurable threshold (default 0.7) as redundant diversification.

**Depends on:** F1.11 (Portfolio composition), F2.2 (Event-driven engine), F2.4 (Metrics)

**Existing files to modify:**
- `backend/app/studio_v2/backtest/engine.py` — add portfolio-run mode (multiple strategy sources, combine equity curves)
- `backend/app/studio_v2/backtest/metrics.py` — add cross-strategy correlation computation
- `backend/app/studio_v2/router.py` — add portfolio backtest route

**New frontend:**
- `frontend/src/components/studio-v2/PortfolioBacktestRunner.jsx`
- `frontend/src/components/studio-v2/StrategyCorrelationMatrix.jsx`

**New backend:**
- `backend/app/studio_v2/backtest/portfolio_engine.py`

**API routes to add:**
```
POST /api/v2/backtest/portfolio-run → body: { composition_id, config }
GET  /api/v2/backtest/portfolio-result/{run_id} → combined result + correlation matrix
```

---

### F2.10 — Sector/Factor Attribution Breakdown (Brinson-style)

**Description:** Decomposes total portfolio return into allocation effect and selection effect per GICS sector and per FF5 factor tilt. Waterfall chart per sector plus summary table.

**Depends on:** F2.2 (Engine trade log output), F6.1 (GICS data)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add attribution route

**New frontend:**
- `frontend/src/components/studio-v2/SectorAttributionChart.jsx`
- `frontend/src/components/studio-v2/FactorAttributionTable.jsx`

**New backend:**
- `backend/app/studio_v2/backtest/attribution.py`

**API routes to add:**
```
GET /api/v2/backtest/attribution/{run_id} → allocation + selection effects per sector/factor
```

---

### F2.11 — Slippage/Execution Quality Post-Mortem

**Description:** Compares modeled fill prices (Almgren-Chriss) against "realistic broker" reference fills using actual historical bid-ask spread and VWAP. Per-trade slippage delta table and aggregate summary.

**Depends on:** F3.7 (Almgren-Chriss coefficients), F6.5 (Liquidity data)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add slippage audit route

**New frontend:**
- `frontend/src/components/studio-v2/SlippagePostMortem.jsx`

**New backend:**
- `backend/app/studio_v2/backtest/slippage_audit.py`

**API routes to add:**
```
GET /api/v2/backtest/slippage-audit/{run_id} → per-trade slippage + aggregate summary
```

---

### F2.12 — Tax-Aware Backtesting Mode

**Description:** Optional toggle for US tax treatment: short-term vs long-term rates, wash-sale rule detection. Post-tax equity curve alongside pre-tax. Wash-sale violation count/log.

**Depends on:** F2.2 (Engine trade log)

**Existing files to modify:**
- `backend/app/studio_v2/backtest/engine.py` — optional tax post-processing step
- `frontend/src/components/studio-v2/BacktestConfigPanel.jsx` — add tax toggle (component doesn't exist yet)
- `backend/app/studio_v2/router.py` — add tax-aware run option in backtest route

**New frontend:**
- `frontend/src/components/studio-v2/TaxAwareToggle.jsx`

**New backend:**
- `backend/app/studio_v2/backtest/tax_engine.py`

**API routes to add:**
```
Modify POST /api/v2/backtest/run → accept tax_config in payload
GET  /api/v2/backtest/tax-report/{run_id} → tax impact breakdown
```

---

### F2.13 — Scenario/Stress Replay

**Description:** Library of one-click historical scenario windows (2008 GFC, March 2020 COVID, 2022 rate-hike, 2015 China deval, dot-com crash). Re-runs strategy restricted to that window. Scenario-specific equity curve, max drawdown, recovery time in small-multiples grid.

**Depends on:** F2.2 (Engine), F6.7 (Data range selection)

**Existing files to modify:**
- `backend/app/studio_v2/backtest/engine.py` — accept date range override
- `backend/app/studio_v2/router.py` — add scenario replay routes

**New frontend:**
- `frontend/src/components/studio-v2/ScenarioReplayGrid.jsx`
- `frontend/src/components/studio-v2/ScenarioCard.jsx`

**New backend:**
- `backend/app/studio_v2/backtest/scenarios.py` (crisis period definitions + replay runner)

**API routes to add:**
```
GET  /api/v2/backtest/scenarios → list available crisis scenario definitions
POST /api/v2/backtest/scenarios/{scenario_id}/replay/{strategy_id} → run strategy in scenario window
GET  /api/v2/backtest/scenarios/result/{run_id} → scenario-specific result
```

---

### F2.14 — Strategy Comparison Mode

**Description:** Side-by-side view of 2–5 selected strategies (or lineage runs) with tearsheets in parallel columns, correlation matrix of return series, combined/overlaid equity curve. Sortable by any metric.

**Depends on:** F2.5 (Tearsheet rendering), F2.6 (Lineage queries)

**Existing files to modify:**
- `frontend/src/components/studio-v2/TearsheetView.jsx` — support multi-column mode (component doesn't exist yet)
- `backend/app/studio_v2/router.py` — add comparison route

**New frontend:**
- `frontend/src/components/studio-v2/StrategyComparisonView.jsx`

**New backend:**
no new service file — comparison logic is a thin adapter over lineage search + metrics

**API routes to add:**
```
POST /api/v2/backtest/compare → body: { run_ids: [...] } → side-by-side metrics + correlation
```

---

## PAGE 3 — ROBUSTNESS LAB ADDITIONS

### F3.10 — Data-Source Robustness Test

**Description:** Re-runs full backtest using perturbed price data — small random adjustments within known precision tolerances of the data source — across 200–500 simulations. Reports data-sensitivity score.

**Depends on:** F2.2 (Engine), F3.7 (Capacity simulation framework)

**Existing files to modify:**
- `backend/app/studio_v2/robustness/tests.py` — add data-source test class
- `backend/app/studio_v2/router.py` — extend lazy_robustness dispatch
- `backend/app/studio_v2/shared/data_loader.py` — add data perturbation utilities

**New frontend:**
- `frontend/src/components/studio-v2/DataSourceRobustness.jsx`

**New backend:**
- `backend/app/studio_v2/robustness/data_source_test.py`

**No new API routes needed** — reuse `POST /api/v2/robustness/run-core-tests` with `test: "data_source"`

---

### F3.11 — Look-Ahead Audit Trail Export

**Description:** Signed, timestamped PDF/JSON report documenting every check confirming no future information leaked: lookahead-linter results, fill-timing guarantee, Purged K-Fold embargo settings. Due-diligence artifact for allocators/reviewers.

**Depends on:** F1.1 (Linter), F4.2 (Purged K-Fold), F2.2 (Fill timing)

**Existing files to modify:**
- `backend/app/studio_v2/algorithm_lab/linter.py` — add audit log export method
- `backend/app/studio_v2/router.py` — add audit route

**New frontend:**
- `frontend/src/components/studio-v2/LookAheadAuditExport.jsx`

**New backend:**
- `backend/app/studio_v2/robustness/audit_trail.py`

**API routes to add:**
```
POST /api/v2/robustness/audit-trail/{strategy_id} → generate signed audit report
```

---

### F3.12 — Combinatorial Parameter Interaction Test

**Description:** Detects whether one parameter's sensitivity changes depending on a second parameter's value. 3D sensitivity surface (or sliced 2D surfaces) with interaction-effect score separate from each parameter's standalone stability score.

**Depends on:** F3.2 (Parameter Stability Surface)

**Existing files to modify:**
- `backend/app/studio_v2/robustness/tests.py` — add interaction test class
- `backend/app/studio_v2/router.py` — extend lazy_robustness dispatch

**New frontend:**
- `frontend/src/components/studio-v2/ParameterInteractionSurface.jsx`

**New backend:**
- `backend/app/studio_v2/robustness/parameter_interaction.py`

**No new API routes needed** — reuse `POST /api/v2/robustness/run-core-tests` with `test: "parameter_interaction"`

---

### F3.13 — Adversarial Stress Test

**Description:** Constructs worst plausible sequence of returns and costs within realistic historical bounds using constrained optimization search over the historical parameter space. Not random resampling — deliberately searches for near-worst-case combination.

**Depends on:** F3.6 (Cost break-even metrics), F3.7 (Capacity framework)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add adversarial route

**New frontend:**
- `frontend/src/components/studio-v2/AdversarialStressTest.jsx`

**New backend:**
- `backend/app/studio_v2/robustness/adversarial.py`

**API routes to add:**
```
POST /api/v2/robustness/adversarial → body: { strategy_file, constraints }
GET  /api/v2/robustness/adversarial/result/{run_id}
```

---

## PAGE 4 — FACTOR SANDBOX ADDITIONS

### F4.12 — Factor Combination / Composite Score Builder

**Description:** Select 2–10 factors, combine into composite score via configurable weighting (equal, IC-weighted, IC-IR-weighted, custom Python combiner). Composite runs through same IC Diagnostics and Decay Curve pipeline as individual factors.

**Depends on:** F4.2 (IC diagnostics), F4.3 (Decay curve)

**Existing files to modify:**
- `backend/app/studio_v2/factors/evaluator.py` — add composite evaluation method
- `backend/app/studio_v2/router.py` — add composite routes
- `frontend/src/components/studio-v2/FactorExpressionEditor.jsx` — add composite builder mode

**New frontend:**
- `frontend/src/components/studio-v2/CompositeScoreBuilder.jsx`

**New backend:**
- `backend/app/studio_v2/factors/composite_combiner.py`

**API routes to add:**
```
POST /api/v2/factors/composite → body: { factor_ids, weights } → composite IC/IR/decay
```

---

### F4.13 — Turnover-vs-Decay Tradeoff View

**Description:** Chart plotting each factor's IC half-life against position turnover rate. Shaded "uninvestable after costs" region computed from platform's cost-break-even logic. Immediate visibility into whether a factor is implementable net of costs.

**Depends on:** F4.3 (Half-life), F4.6 (Decay tracking), F3.6 (Cost break-even)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add tradeoff route

**New frontend:**
- `frontend/src/components/studio-v2/TurnoverVsDecayChart.jsx`

**New backend:**
- `backend/app/studio_v2/factors/turnover_estimator.py`

**API routes to add:**
```
GET /api/v2/factors/turnover-decay/{factor_id} → half-life vs turnover chart data
```

---

### F4.14 — Factor Library Governance Panel

**Description:** Version history for every factor in the internal 40-factor baseline library: who/when modified, changelog, approval status (proposed/approved/deprecated). Deprecating removes from orthogonalization baselines while preserving historical runs.

**Depends on:** F4.11 (Library)

**Existing files to modify:**
- `backend/app/studio_v2/factors/library.py` — add version tracking, approval workflow, deprecation
- `backend/app/studio_v2/router.py` — extend library routes

**New frontend:**
- `frontend/src/components/studio-v2/FactorGovernancePanel.jsx`

**New backend:**
- `backend/app/studio_v2/factors/governance.py`

**API routes to add:**
```
GET    /api/v2/factors/library/{id}/versions → version history
POST   /api/v2/factors/library/{id}/approve → set approved
POST   /api/v2/factors/library/{id}/deprecate → set deprecated
GET    /api/v2/factors/library/{id}/changelog → full edit history
```

---

## PAGE 5 — OPTIMIZER ADDITIONS

### F5.7 — Multi-Objective Pareto Frontier View

**Description:** Bayesian search tracking multiple objectives (Sharpe, capacity ceiling, max drawdown) simultaneously. Interactive scatter (2 objectives) or parallel-coordinates plot (3+). Researcher picks from frontier matching their risk/capacity preference.

**Depends on:** F5.2 (Bayesian search), F3.7 (Capacity estimation)

**Existing files to modify:**
- `backend/app/studio_v2/optimizer/search.py` — extend optimizer to track multiple objectives
- `backend/app/studio_v2/router.py` — add multi-objective route

**New frontend:**
- `frontend/src/components/studio-v2/ParetoFrontierView.jsx`

**New backend:**
- `backend/app/studio_v2/optimizer/multi_objective.py`

**API routes to add:**
```
POST /api/v2/optimizer/pareto-search → body: { param_ranges, objectives: ["sharpe","capacity","drawdown"] }
```

---

### F5.8 — Ensemble/Parameter Averaging Mode

**Description:** Takes top N (default 10) parameter configurations by objective score and either runs all N as an ensemble averaging signals, or reports distribution of expected performance as uncertainty band. Framed as overfitting mitigation.

**Depends on:** F5.2 (Search results), F5.6 (Trial registry)

**Existing files to modify:**
- `backend/app/studio_v2/optimizer/search.py` — add ensemble evaluation mode
- `backend/app/studio_v2/router.py` — add ensemble route

**New frontend:**
- `frontend/src/components/studio-v2/EnsembleModePanel.jsx`

**New backend:**
- `backend/app/studio_v2/optimizer/ensemble.py`

**API routes to add:**
```
POST /api/v2/optimizer/ensemble → body: { session_id, top_n }
```

---

### F5.9 — Optimizer Cross-Validation View

**Description:** Compares parameter region favored by Bayesian search vs Walk-Forward for same strategy, rendered as overlay on parameter stability heatmap. High overlap = positive robustness signal. Low overlap = warning flag.

**Depends on:** F5.2, F5.3 (Both optimization modes), F3.2 (Stability surface)

**Existing files to modify:**
- `backend/app/studio_v2/optimizer/search.py` — method to extract preferred region
- `backend/app/studio_v2/optimizer/cpcv.py` — method to extract WFA preferred region
- `backend/app/studio_v2/router.py` — add cross-validation route

**New frontend:**
- `frontend/src/components/studio-v2/CrossValidationOverlay.jsx`

**New backend:**
- `backend/app/studio_v2/optimizer/cross_validation.py`

**API routes to add:**
```
POST /api/v2/optimizer/cross-validate → body: { strategy_file } → region overlap data
```

---

## PAGE 6 — UNIVERSE & DATA STUDIO ADDITIONS

### F6.11 — Multi-Asset-Class Universe Support

**Description:** Extends Filter Stack Interface to support futures (continuous contract construction with roll methodology: front-month, volume-weighted, fixed-day roll), major crypto pairs, and FX spot/forward. Each asset class gets its own filter primitives.

**Depends on:** F6.1 (Filter stack), F6.5 (Liquidity calibration)

**Existing files to modify:**
- `backend/app/studio_v2/data_studio/universe.py` — add asset-class filter primitives
- `backend/app/studio_v2/shared/liquidity.py` — multi-asset ADV/vol computation
- `backend/app/studio_v2/shared/data_loader.py` — futures/crypto/FX data sources
- `frontend/src/components/studio-v2/FilterStackInterface.jsx` — add asset class selector

**New frontend:**
- `frontend/src/components/studio-v2/MultiAssetFilters.jsx`

**New backend:**
- `backend/app/studio_v2/data_studio/multi_asset.py`

**API routes to add:**
```
GET /api/v2/data-studio/asset-classes → list supported asset classes + their filter primitives
```

---

### F6.12 — Corporate Event Calendar Overlay

**Description:** Overlay toggle in Data Explorer and Backtest tearsheet marking earnings dates, index-rebalance dates, dividend ex-dates on price/equity-curve timeline as vertical markers.

**Depends on:** F6.7 (Data Explorer), F2.5 (Tearsheet)

**Existing files to modify:**
- `frontend/src/components/studio-v2/DataExplorerPanel.jsx` — add event overlay toggle
- `frontend/src/components/studio-v2/StudioChartPanel.jsx` — add vertical marker rendering
- `frontend/src/components/studio-v2/TearsheetView.jsx` — add event markers (component doesn't exist yet)
- `backend/app/studio_v2/router.py` — add event data route

**New frontend:**
- `frontend/src/components/studio-v2/EventCalendarOverlay.jsx` (toggle control + marker data)

**New backend:**
- `backend/app/studio_v2/data_studio/event_calendar.py`

**API routes to add:**
```
GET /api/v2/data-studio/events/{ticker} → query: start_date, end_date → event list with dates/types
```

---

### F6.13 — Synthetic/Backfilled Data Flagging

**Description:** Any date range with gap-filled, forward-filled, or synthetically constructed data is visually distinguished in every chart — dashed line segments or distinct marker color — not rendered identically to real observed data.

**Depends on:** F6.7 (Data Explorer), F6.8 (Missing data detection)

**Existing files to modify:**
- `frontend/src/components/studio-v2/StudioChartPanel.jsx` — accept `is_synthetic` segments in series data
- `frontend/src/components/studio-v2/DataExplorerPanel.jsx` — pass synthetic flags to chart
- `frontend/src/components/studio-v2/TimeVaryingUniverse.jsx` — mark backfilled regions

**New backend:**
- `backend/app/studio_v2/data_studio/synthetic_flagging.py` (annotates data series with synthetic ranges)

No new components needed — extend existing chart infrastructure.

**API routes to add:**
```
GET /api/v2/data-studio/synthetic-ranges/{ticker} → list of date ranges with synthetic status
```

---

## NEW PAGE 7 — PORTFOLIO RISK MANAGEMENT

### F7.1 — Aggregate VaR/CVaR Panel

**Description:** Portfolio-level Value at Risk and Conditional VaR across all "Active"/"Deployed" tagged strategies. Parametric (variance-covariance) and historical simulation methods at 95%/99% confidence over 1-day/10-day horizons.

**Depends on:** F2.6 (Lineage tags to identify active strategies), F1.11 (Portfolio composition for weights)

**Existing files to modify:**
- `backend/app/studio_v2/backtest/lineage.py` — add method to query active strategies with their equity curves
- `backend/app/studio_v2/router.py` — add Page 7 routes

**New frontend:**
- `frontend/src/components/studio-v2/portfolio-risk/AggregateVarPanel.jsx`
- `frontend/src/stores/studio/portfolioRiskStore.js`
- `frontend/src/hooks/studio/usePortfolioRisk.js`
- `frontend/src/app/studio/portfolio-risk/page.js`

**New backend:**
- `backend/app/studio_v2/portfolio_risk/__init__.py`
- `backend/app/studio_v2/portfolio_risk/var_engine.py`

**API routes to add:**
```
GET  /api/v2/portfolio-risk/var → query: confidence=[95,99], horizon=[1,10] → VaR/CVaR both methods
GET  /api/v2/portfolio-risk/active-strategies → list active + deployed strategies with equity curves
```

---

### F7.2 — Cross-Strategy Correlation & Concentration Dashboard

**Description:** Live-updating correlation matrix across all active strategies' daily returns. Exposure overlap panel — surfaces when multiple strategies are long the same 20 names.

**Depends on:** F7.1 (Active strategy list), F3.4 (Universe perturbation concentration detection logic)

**Existing files to modify:**
- `backend/app/studio_v2/robustness/tests.py` — export concentration detection for cross-strategy use
- `backend/app/studio_v2/router.py` — add correlation/concentration routes

**New frontend:**
- `frontend/src/components/studio-v2/portfolio-risk/ConcentrationDashboard.jsx`
- `frontend/src/components/studio-v2/portfolio-risk/CorrelationMatrix.jsx`

**New backend:**
- `backend/app/studio_v2/portfolio_risk/concentration.py`

**API routes to add:**
```
GET /api/v2/portfolio-risk/correlation → correlation matrix across active strategies
GET /api/v2/portfolio-risk/concentration → overlapping positions across strategies
```

---

### F7.3 — Position & Exposure Limits Panel

**Description:** Configurable limits (max single-name weight, max sector weight, max gross/net leverage, max strategy-level VaR contribution) with real-time breach indicators.

**Depends on:** F7.1 (VaR calculations), F7.2 (Position overlap data)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add limits CRUD routes

**New frontend:**
- `frontend/src/components/studio-v2/portfolio-risk/ExposureLimitsPanel.jsx`

**New backend:**
- `backend/app/studio_v2/portfolio_risk/limits.py`

**API routes to add:**
```
GET  /api/v2/portfolio-risk/limits → current limits configuration
PUT  /api/v2/portfolio-risk/limits → update limits
GET  /api/v2/portfolio-risk/limits/breaches → current breaches
```

---

### F7.4 — Real-Time Risk Alert Feed

**Description:** Unified chronological feed surfacing any monitored condition crossing threshold: paper-trading divergence score breach, VaR breach, concentration limit breach, data freshness failure.

**Depends on:** F1.9 (Paper trading divergence), F7.1 (VaR), F7.3 (Limits), F6.10 (Freshness)

**Existing files to modify:**
- `backend/app/studio_v2/router.py` — add alert feed route

**New frontend:**
- `frontend/src/components/studio-v2/portfolio-risk/RiskAlertFeed.jsx`

**New backend:**
- `backend/app/studio_v2/portfolio_risk/alert_feed.py`

**API routes to add:**
```
GET /api/v2/portfolio-risk/alerts → chronological alert feed, paginated
POST /api/v2/portfolio-risk/alerts/{alert_id}/ack → acknowledge alert
```

---

## CROSS-CUTTING

### F0.1 — Research Notebook / Journal Layer

**Description:** Persistent freeform prose journal attached to researcher's account (not to single strategy file). Entries optionally tagged to specific Model Lineage run IDs. Records *why* — closes the gap between "a log of backtests" and "an actual research record."

**Depends on:** F2.6 (Lineage run IDs for tagging)

**Existing files to modify:**
- `frontend/src/components/studio-v2/ModelLineageGraph.jsx` — add journal entry link icon per run node
- `backend/app/studio_v2/router.py` — add journal CRUD routes

**New frontend:**
- `frontend/src/components/studio-v2/ResearchJournal.jsx`
- `frontend/src/stores/studio/researchJournalStore.js`
- `frontend/src/types/studio/research-journal.d.ts`

**New backend:**
- `backend/app/studio_v2/services/journal_service.py`

**API routes to add:**
```
GET    /api/v2/journal → list entries, filterable by run_id, date range, tags
POST   /api/v2/journal → create entry
PUT    /api/v2/journal/{entry_id} → update entry
DELETE /api/v2/journal/{entry_id} → delete entry
GET    /api/v2/journal/tags → list all tags across entries
```

---

## SUMMARY OF EXISTING FILES TO MODIFY

| File | Feature(s) | Change |
|------|-----------|--------|
| `router.py` | All | Add ~35 new routes + imports |
| `engine.py` | F2.9, F2.12, F2.13 | Portfolio mode, tax post-processing, date range override |
| `kernel.py` | F1.11, F1.14 | Multi-strategy namespace, execution timeout monitoring |
| `linter.py` | F3.11 | Audit log export method |
| `lineage.py` | F7.1 | Active strategy query with equity curves |
| `tests.py` (robustness) | F3.10, F3.12 | Data-source test class, interaction test class; export concentration detection for F7.2 |
| `evaluator.py` (factors) | F4.12 | Composite evaluation method |
| `library.py` | F4.14 | Version tracking, approval workflow, deprecation |
| `search.py` | F5.7, F5.8 | Multi-objective tracking, ensemble mode |
| `data_loader.py` | F6.11 | Futures/crypto/FX data sources; data perturbation utilities for F3.10 |
| `universe.py` | F6.11 | Multi-asset-class filter primitives |
| `liquidity.py` | F6.11 | Multi-asset ADV/vol computation |
| `AlgorithmLab.jsx` | F1.10, F1.11, F1.13, F1.14 | Template sidebar trigger, composition view tab, collab toggle, guardrail bar |
| `Editor.jsx` | F1.13, F1.15 | Multi-cursor for collab, snippet autocomplete provider |
| `VariableInspector.jsx` | F1.13 | Real-time sync for collab |
| `StudioChartPanel.jsx` | F1.13, F6.12, F6.13 | Real-time sync, event markers, synthetic data dashed lines |
| `FilterStackInterface.jsx` | F6.11 | Asset class selector |
| `DataExplorerPanel.jsx` | F6.12, F6.13 | Event overlay toggle, synthetic flag passthrough |
| `ModelLineageGraph.jsx` | F0.1 | Journal entry link icon per run node |
| `FactorExpressionEditor.jsx` | F4.12 | Composite builder mode |

---

## SUMMARY OF NEW FILES

### Frontend Components (33 new)
```
components/studio-v2/StrategyTemplateLibrary.jsx                  (P1)
components/studio-v2/PortfolioComposition.jsx                      (P1)
components/studio-v2/ExportCleanModule.jsx                         (P1)
components/studio-v2/CollaborativeSession.jsx                      (P1)
components/studio-v2/ComputeGuardrail.jsx                          (P1)
components/studio-v2/SnippetLibrary.jsx                            (P1)
components/studio-v2/PortfolioBacktestRunner.jsx                   (P2)
components/studio-v2/StrategyCorrelationMatrix.jsx                 (P2)
components/studio-v2/SectorAttributionChart.jsx                    (P2)
components/studio-v2/FactorAttributionTable.jsx                    (P2)
components/studio-v2/SlippagePostMortem.jsx                        (P2)
components/studio-v2/TaxAwareToggle.jsx                            (P2)
components/studio-v2/ScenarioReplayGrid.jsx                        (P2)
components/studio-v2/ScenarioCard.jsx                              (P2)
components/studio-v2/StrategyComparisonView.jsx                    (P2)
components/studio-v2/DataSourceRobustness.jsx                      (P3)
components/studio-v2/LookAheadAuditExport.jsx                      (P3)
components/studio-v2/ParameterInteractionSurface.jsx               (P3)
components/studio-v2/AdversarialStressTest.jsx                     (P3)
components/studio-v2/CompositeScoreBuilder.jsx                     (P4)
components/studio-v2/TurnoverVsDecayChart.jsx                      (P4)
components/studio-v2/FactorGovernancePanel.jsx                     (P4)
components/studio-v2/ParetoFrontierView.jsx                        (P5)
components/studio-v2/EnsembleModePanel.jsx                         (P5)
components/studio-v2/CrossValidationOverlay.jsx                    (P5)
components/studio-v2/MultiAssetFilters.jsx                         (P6)
components/studio-v2/EventCalendarOverlay.jsx                      (P6)
components/studio-v2/portfolio-risk/AggregateVarPanel.jsx          (P7)
components/studio-v2/portfolio-risk/ConcentrationDashboard.jsx     (P7)
components/studio-v2/portfolio-risk/CorrelationMatrix.jsx          (P7)
components/studio-v2/portfolio-risk/ExposureLimitsPanel.jsx        (P7)
components/studio-v2/portfolio-risk/RiskAlertFeed.jsx              (P7)
components/studio-v2/ResearchJournal.jsx                           (CC)
```

### Frontend Hooks (4 new)
```
hooks/studio/usePortfolioComposition.js
hooks/studio/useCollaboration.js
hooks/studio/useSnippets.js
hooks/studio/usePortfolioRisk.js
```

### Frontend Stores (4 new)
```
stores/studio/portfolioCompositionStore.js
stores/studio/portfolioRiskStore.js
stores/studio/researchJournalStore.js
```

### Frontend Types (1 new)
```
types/studio/research-journal.d.ts
```

### Frontend Pages (1 new)
```
app/studio/portfolio-risk/page.js
```

### Backend Service Files (28 new)
```
algorithm_lab/templates.py
algorithm_lab/portfolio_composer.py
algorithm_lab/collaboration.py
algorithm_lab/compute_budget.py
algorithm_lab/snippets.py
backtest/portfolio_engine.py
backtest/attribution.py
backtest/slippage_audit.py
backtest/tax_engine.py
backtest/scenarios.py
robustness/data_source_test.py
robustness/audit_trail.py
robustness/parameter_interaction.py
robustness/adversarial.py
factors/composite_combiner.py
factors/turnover_estimator.py
factors/governance.py
optimizer/multi_objective.py
optimizer/ensemble.py
optimizer/cross_validation.py
data_studio/multi_asset.py
data_studio/event_calendar.py
data_studio/synthetic_flagging.py
portfolio_risk/__init__.py
portfolio_risk/var_engine.py
portfolio_risk/concentration.py
portfolio_risk/limits.py
portfolio_risk/alert_feed.py
services/journal_service.py
```

### Plus 15 original-spec components still missing (unchanged from original):
```
components/studio-v2/BacktestConfigPanel.jsx
components/studio-v2/BacktestRunner.jsx
components/studio-v2/MonteCarloDisplay.jsx
components/studio-v2/TearsheetView.jsx
components/studio-v2/ExportDialog.jsx
components/studio-v2/StrategySelector.jsx
components/studio-v2/UniversePerturbationPanel.jsx
components/studio-v2/NoiseInjectionPanel.jsx
components/studio-v2/ExtendedDiagnostics.jsx
components/studio-v2/IcDecayCurve.jsx
components/studio-v2/CrossSectionalDist.jsx
components/studio-v2/RegimeIcPanel.jsx
components/studio-v2/ParameterDeclaration.jsx
components/studio-v2/DataCatalog.jsx
components/studio-v2/MissingDataHeatmap.jsx
components/studio-v2/UniverseExport.jsx
components/studio-v2/DataUploadDialog.jsx
```

### Grand Total
- **33 new components** (additions)
- **17 missing original components** (to catch up on)
- **4 new hooks**
- **4 new stores**
- **1 new type**
- **1 new page**
- **28 new backend files**
- **20 existing files to modify**
- **~35 new API routes**
