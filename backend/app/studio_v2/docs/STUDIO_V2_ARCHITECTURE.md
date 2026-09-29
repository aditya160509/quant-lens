# QUANT360 Studio v2 — Lean Architecture & Build Phases

**Date:** July 26, 2026
**Spec:** `Studio v2 feature.md` — 46 features, 6 pages
**Stack:** Next.js 16 + React 19 + FastAPI + Supabase + Parquet data layer
**Principle:** Lean — one file per logical service, not per feature. Shared data loaders. No duplication.
**Live data needed:** NO — everything works on historical parquet. Paper trading (F1.9) and freshness monitor (F6.10) require live/delayed feeds; skip them if live data is out of scope.

---

## Data Sources — What Exists, What to Use

### Already in Your Codebase (use these)

| Data | File | Size | Used By |
|------|------|------|---------|
| **Master universe OHLCV** | `backend/data/market_universe.parquet` | 282 MB — 4,158 tickers, 1996-2026 | **ALL features** — primary data source |
| **Category 7 macro** | `factors/data/processed/category7_macro_regime.parquet` | 258 KB — VIX, yields, CPI, Fed Funds, USD | F2.5 crisis bands, F4.9 regime IC, F6.7 explorer |
| **FF3 daily** | `backend/data/factors_us/ff3_daily.parquet` | 280 KB | F2.5 FF5 loadings |
| **FF5 daily** | `backend/data/factors_us/ff5_daily.parquet` | 691 B | F4.7 orthogonalization residualization |
| **Momentum daily** | `backend/data/factors_us/momentum_daily.parquet` | 183 KB | F4.7 baseline factor |
| **Fundamentals** | `backend/data/fundamentals/master_fundamentals.parquet` | 32 MB | F6.1 market cap + float filters only |
| **Developed 3/5 factors** | `backend/data/factors_global/Developed_*.csv` | various | F4.7 extended library |
| **AQR factors** | `factors/data/processed/aqr_csv/*.csv` | 36 files | F4.7 extended library |

**That's 8 data sources. Nothing else needed.**

### What NOT to Use

| File | Reason |
|------|--------|
| `APDI/`, `research_exports/` parquets | Copies of master universe — use the primary one |
| `backend/data/prices/*.parquet` (2,900 files) | Redundant — master universe has all tickers |
| `frontend/src/data/universes/universes.json` | Redundant — ticker list extracted from master universe parquet |
| `backend/data/canonical/cross_asset_hourly.parquet` | Not needed — all features use daily data |
| Fundamentals shards (3,833 files) | Redundant — `master_fundamentals.parquet` is the complete set |
| NBER / FOMC | Removed — VIX > 30 from Category 7 replaces crisis bands |

### How the Data Loader Should Work

```python
# services/shared/data_loader.py — the ONE loader for all services

UNIVERSE_PATH = "backend/data/market_universe.parquet"
CATEGORY7_PATH = "factors/data/processed/category7_macro_regime.parquet"
FF5_PATH = "backend/data/factors_us/ff5_daily.parquet"
MOM_PATH = "backend/data/factors_us/momentum_daily.parquet"
FUNDAMENTALS_PATH = "backend/data/fundamentals/master_fundamentals.parquet"

def get_returns(tickers, start, end) → DataFrame     # from market_universe.parquet
def get_ohlcv(ticker, start, end) → DataFrame        # from market_universe.parquet
def get_all_tickers() → list                          # extracted from market_universe.parquet
def get_macro(series_name, start, end) → Series       # from category7_macro_regime.parquet
def get_factor_returns(model="ff5") → DataFrame       # from ff5_daily.parquet or global/AQR
def get_market_cap(ticker, date) → float              # from master_fundamentals.parquet
def get_float(ticker) → float                         # from master_fundamentals.parquet
```

**Rule:** No service imports yfinance, FRED, or any external API directly. Everything comes through `data_loader.py` reading parquet files.

---

## Complete Feature-to-File Map

### Page 1 — Algorithm Lab (F1.1–F1.9)

| Feature | Backend Service | Frontend Component |
|---------|----------------|-------------------|
| F1.1 Monaco Editor + Lookahead Linter | `linter.py` | `Editor.jsx` |
| F1.2 Persistent Kernel + Dep Graph | `kernel.py` | `AlgorithmLab.jsx` (page), `StudioStore.js` |
| F1.3 Terminal Panel | none (PTY sidecar) | `EventLogPanel.jsx` |
| F1.4 Live Chart Panel | none (chart lib only) | `StudioChartPanel.jsx` |
| F1.5 Variable Inspector | `kernel.py` | `VariableInspector.jsx` |
| F1.6 File System + Version Control | none (local state) | `FileManager.jsx` |
| F1.7 Run History Panel | none (local state) | `RunHistoryPanel.jsx` |
| F1.8 One-Click Push | thin endpoint | `PushToBacktestButton.jsx` |
| F1.9 Paper Trading + Code Parity | `paper_trader.py` | `PaperTradingPanel.jsx` |

### Page 2 — Backtest Studio + Model Lineage (F2.1–F2.8)

| Feature | Backend Service | Frontend Component |
|---------|----------------|-------------------|
| F2.1 Run Configuration Panel | none (UI form) | `BacktestConfigPanel.jsx` |
| F2.2 Event-Driven Simulation | `engine.py` | `BacktestRunner.jsx` |
| F2.3 Monte Carlo (shared) | `shared/monte_carlo.py` | `MonteCarloDisplay.jsx` |
| F2.4 Honest Performance Card | `metrics.py` | `HonestPerformanceCard.jsx` |
| F2.5 Interactive Tearsheet | none (rendering) | `TearsheetView.jsx` + `RegimePnLBreakdown.jsx` |
| F2.6 Model Lineage | `lineage.py` | `ModelLineageGraph.jsx` |
| F2.7 Export | none (client-side) | `ExportDialog.jsx` |
| F2.8 Live-vs-Backtest Reconciliation | `reconciliation.py` | `LiveVsBacktestPanel.jsx` |

### Page 3 — Robustness Lab (F3.1–F3.9)

| Feature | Backend Service | Frontend Component |
|---------|----------------|-------------------|
| F3.1 Strategy Input | thin endpoint | `StrategySelector.jsx` |
| F3.2 Parameter Stability | `robustness/tests.py` | `ParameterStabilitySurface.jsx` |
| F3.3 Timing Perturbation | `robustness/tests.py` | `TimingPerturbationPanel.jsx` |
| F3.4 Universe Perturbation | `robustness/tests.py` | `UniversePerturbationPanel.jsx` |
| F3.5 Noise Injection | `robustness/tests.py` | `NoiseInjectionPanel.jsx` |
| F3.6 Cost Break-Even | `robustness/tests.py` | `CostBreakEvenChart.jsx` |
| F3.7 Capacity Stress | `robustness/tests.py` | `CapacityStressPanel.jsx` |
| F3.8 Extended Diagnostics | `robustness/tests.py` | `ExtendedDiagnostics.jsx` |
| F3.9 Composite Score + PDF | `robustness/scorer.py` | `CompositeRobustness.jsx` |

### Page 4 — Factor Sandbox (F4.1–F4.11)

| Feature | Backend Service | Frontend Component |
|---------|----------------|-------------------|
| F4.1 Expression Editor | `factors/evaluator.py` | `FactorExpressionEditor.jsx` |
| F4.2 Instant IC Diagnostics | `factors/evaluator.py` | `InstantIcPanel.jsx` |
| F4.3 IC Decay Curve | `factors/evaluator.py` | `IcDecayCurve.jsx` |
| F4.4 Cross-Sectional Distribution | `factors/evaluator.py` | `CrossSectionalDist.jsx` |
| F4.5 Crowding Monitor | `factors/diagnostics.py` | `CrowdingMonitor.jsx` |
| F4.6 Half-Life Decay Tracking | `factors/diagnostics.py` | `HalfLifeDecayChart.jsx` |
| F4.7 Orthogonalization | `factors/diagnostics.py` | `OrthogonalizationPanel.jsx` |
| F4.8 Interaction Screener | `factors/diagnostics.py` | `FactorInteractionPanel.jsx` |
| F4.9 Regime-Conditional IC | `factors/evaluator.py` | `RegimeIcPanel.jsx` |
| F4.10 Factor Comparison Table | none (client-side sort) | `FactorComparisonTable.jsx` |
| F4.11 Internal Library | `factors/library.py` | `InternalFactorLibrary.jsx` |

### Page 5 — Optimizer (F5.1–F5.6)

| Feature | Backend Service | Frontend Component |
|---------|----------------|-------------------|
| F5.1 Parameter Declaration | thin (AST parser) | `ParameterDeclaration.jsx` |
| F5.2 Bayesian Search | `optimizer/search.py` | `BayesianOptimizerPanel.jsx` |
| F5.3 Walk-Forward | `optimizer/search.py` | `WalkForwardPanel.jsx` |
| F5.4 CPCV + Deflated Sharpe | `optimizer/cpcv.py` | `CpcvPanel.jsx` |
| F5.5 Auto-Overfitting Verdict | `optimizer/verdict.py` | `OverfittingVerdict.jsx` |
| F5.6 Trial Registry | `optimizer/verdict.py` | `TrialRegistry.jsx` |

### Page 6 — Universe & Data Studio (F6.1–F6.10)

| Feature | Backend Service | Frontend Component |
|---------|----------------|-------------------|
| F6.1 Filter Stack Interface | `data_studio/universe.py` | `FilterStackInterface.jsx` |
| F6.2 Point-in-Time Data | **REMOVED from scope** | — |
| F6.3 Time-Varying Universe Viewer | `data_studio/universe.py` | `TimeVaryingUniverse.jsx` |
| F6.4 Universe Snapshot Export | none (client-side export) | `UniverseExport.jsx` |
| F6.5 Liquidity Reality Layer | `shared/liquidity.py` | `LiquidityRealityLayer.jsx` |
| F6.6 Data Catalog | `data_studio/catalog.py` | `DataCatalog.jsx` |
| F6.7 Data Explorer | `data_studio/explorer.py` | `DataExplorerPanel.jsx` |
| F6.8 Missing Data Heatmap | `data_studio/explorer.py` | `MissingDataHeatmap.jsx` |
| F6.9 Custom Data Upload | `data_studio/catalog.py` | `DataUploadDialog.jsx` |
| F6.10 Data Freshness Monitor | `data_studio/catalog.py` | `DataFreshnessMonitor.jsx` |

---

## Directory Structure

```
frontend/src/
├── app/
│   └── labs/studio/page.js              ← Page 1: Algorithm Lab (F1.1–F1.8)
│   └── studio/
│       ├── backtest/page.js              ← Page 2: Backtest Studio (F2.1–F2.8)
│       ├── robustness/page.js            ← Page 3: Robustness Lab (F3.1–F3.9)
│       ├── factors/page.js               ← Page 4: Factor Sandbox (F4.1–F4.11)
│       ├── optimizer/page.js             ← Page 5: Optimizer (F5.1–F5.6)
│       └── data-studio/page.js           ← Page 6: Data Studio (F6.1–F6.10, no F6.2)
│
├── components/studio-v2/                 ← NEW: 20 components (consolidated)
│   ├── VariableInspector.jsx
│   ├── RunHistoryPanel.jsx
│   ├── PaperTradingPanel.jsx
│   ├── HonestPerformanceCard.jsx
│   ├── RegimePnLBreakdown.jsx
│   ├── ModelLineageGraph.jsx
│   ├── LiveVsBacktestPanel.jsx
│   ├── ParameterStabilitySurface.jsx
│   ├── TimingPerturbationPanel.jsx
│   ├── CostBreakEvenChart.jsx
│   ├── CapacityStressPanel.jsx
│   ├── CompositeRobustness.jsx
│   ├── FactorExpressionEditor.jsx
│   ├── InstantIcPanel.jsx
│   ├── CrowdingMonitor.jsx
│   ├── HalfLifeDecayChart.jsx
│   ├── OrthogonalizationPanel.jsx
│   ├── FactorInteractionPanel.jsx
│   ├── FactorComparisonTable.jsx
│   ├── InternalFactorLibrary.jsx
│   ├── BayesianOptimizer.jsx
│   ├── WalkForwardPanel.jsx
│   ├── CpcvPanel.jsx
│   ├── OverfittingVerdict.jsx
│   ├── TrialRegistry.jsx
│   ├── FilterStackInterface.jsx
│   ├── TimeVaryingUniverse.jsx
│   ├── LiquidityRealityLayer.jsx
│   ├── DataExplorerPanel.jsx
│   └── DataFreshnessMonitor.jsx

backend/app/
├── routers/
│   ├── algorithm_lab.py          ← F1 endpoints
│   ├── backtest_studio.py        ← F2 endpoints
│   ├── robustness_lab.py         ← F3 endpoints
│   ├── factor_sandbox.py         ← F4 endpoints
│   ├── optimizer.py              ← F5 endpoints
│   └── data_studio.py            ← F6 endpoints
│
└── services/
    ├── shared/
    │   ├── data_loader.py        ← ONE data engine for ALL services (yfinance, FRED, FF)
    │   ├── monte_carlo.py        ← Shared MC (Block Bootstrap + GARCH)
    │   └── liquidity.py          ← Almgren-Chriss λ calibrator (F6.5 → F3.7, F5.2, F1.9)
    │
    ├── algorithm_lab/
    │   ├── kernel.py             ← F1.2 + F1.5 (kernel gateway + dependency graph)
    │   ├── linter.py             ← F1.1 (AST lookahead detector)
    │   └── paper_trader.py       ← F1.9 (cron + code parity bridge)
    │
    ├── backtest/
    │   ├── engine.py             ← F2.2 (event-driven sim, already exists, needs refactor)
    │   ├── metrics.py            ← F2.4 (DSR, PBO, PSR)
    │   ├── lineage.py            ← F2.6 (DAG storage + queries)
    │   └── reconciliation.py     ← F2.8 (divergence score)
    │
    ├── robustness/
    │   ├── tests.py              ← F3.2–F3.8 (ALL robustness tests in one file)
    │   └── scorer.py             ← F3.9 (composite score + reportlab PDF)
    │
    ├── factors/
    │   ├── evaluator.py          ← F4.1–F4.4 (expression eval, IC, decay, distribution, regime IC)
    │   ├── diagnostics.py        ← F4.5–F4.9 (crowding, half-life, ortho, interaction)
    │   └── library.py            ← F4.10–F4.11 (table data, library CRUD, validation)
    │
    ├── optimizer/
    │   ├── search.py             ← F5.2–F5.3 (Bayesian + Walk-Forward, share trial loop)
    │   ├── cpcv.py               ← F5.4 (CPCV combinatorics + DSR/PBO)
    │   └── verdict.py            ← F5.5–F5.6 (traffic light + trial registry)
    │
    └── data_studio/
        ├── universe.py           ← F6.1, F6.3 (filter stack, heatmap data)
        ├── explorer.py           ← F6.7, F6.8 (data inspection, missing data)
        └── catalog.py            ← F6.6, F6.9, F6.10 (data sources, upload, freshness)
```

**Total backend Python files: 27 (21 service + 6 routers). Phase counts: 9 + 11 + 5 + 2 = 27.** No double-counting — each shared file (data_loader, monte_carlo, liquidity) appears in exactly one phase.

### What's Missing (Frontend)

**6 page files** under `frontend/src/app/studio/`:
- `backtest/page.js` — Page 2: Backtest Studio
- `robustness/page.js` — Page 3: Robustness Lab
- `factors/page.js` — Page 4: Factor Sandbox
- `optimizer/page.js` — Page 5: Optimizer
- `data-studio/page.js` — Page 6: Data Studio
- `page.js` — Page 1: Algorithm Lab (exists at `labs/studio/page.js`, needs redirect)

**36 frontend components** under `frontend/src/components/studio-v2/`:
- 9 for Algorithm Lab: `Editor.jsx`, `AlgorithmLab.jsx`, `EventLogPanel.jsx`, `StudioChartPanel.jsx`, `VariableInspector.jsx`, `FileManager.jsx`, `RunHistoryPanel.jsx`, `PushToBacktestButton.jsx`, `PaperTradingPanel.jsx`
- 8 for Backtest Studio: `BacktestConfigPanel.jsx`, `BacktestRunner.jsx`, `MonteCarloDisplay.jsx`, `HonestPerformanceCard.jsx`, `TearsheetView.jsx`, `RegimePnLBreakdown.jsx`, `ModelLineageGraph.jsx`, `ExportDialog.jsx`, `LiveVsBacktestPanel.jsx`
- 9 for Robustness Lab: `StrategySelector.jsx`, `ParameterStabilitySurface.jsx`, `TimingPerturbationPanel.jsx`, `UniversePerturbationPanel.jsx`, `NoiseInjectionPanel.jsx`, `CostBreakEvenChart.jsx`, `CapacityStressPanel.jsx`, `ExtendedDiagnostics.jsx`, `CompositeRobustness.jsx`
- 11 for Factor Sandbox: `FactorExpressionEditor.jsx`, `InstantIcPanel.jsx`, `IcDecayCurve.jsx`, `CrossSectionalDist.jsx`, `CrowdingMonitor.jsx`, `HalfLifeDecayChart.jsx`, `OrthogonalizationPanel.jsx`, `FactorInteractionPanel.jsx`, `RegimeIcPanel.jsx`, `FactorComparisonTable.jsx`, `InternalFactorLibrary.jsx`
- 6 for Optimizer: `ParameterDeclaration.jsx`, `BayesianOptimizerPanel.jsx`, `WalkForwardPanel.jsx`, `CpcvPanel.jsx`, `OverfittingVerdict.jsx`, `TrialRegistry.jsx`
- 10 for Data Studio: `FilterStackInterface.jsx`, `TimeVaryingUniverse.jsx`, `UniverseExport.jsx`, `LiquidityRealityLayer.jsx`, `DataCatalog.jsx`, `DataExplorerPanel.jsx`, `MissingDataHeatmap.jsx`, `DataUploadDialog.jsx`, `DataFreshnessMonitor.jsx`

**API hooks** under `frontend/src/hooks/studio/`:
- `useAlgorithmLab.js` — calls to `/api/v2/algorithm-lab/*`
- `useBacktest.js` — calls to `/api/v2/backtest/*`
- `useRobustness.js` — calls to `/api/v2/robustness/*`
- `useFactors.js` — calls to `/api/v2/factors/*`
- `useOptimizer.js` — calls to `/api/v2/optimizer/*`
- `useDataStudio.js` — calls to `/api/v2/data-studio/*`

**TypeScript types** under `frontend/src/types/studio/`:
- `algorithm-lab.d.ts` — RunRecord, ExecutionResult, LintWarning, PaperTradeResult
- `backtest.d.ts` — SimulationConfig, SimulationResult, MetricCard, LineageNode
- `robustness.d.ts` — TestResult, CompositeScore, RobustnessReport
- `factors.d.ts` — FactorResult, IcResult, CrowdingResult, LibraryEntry
- `optimizer.d.ts` — OptimizerConfig, TrialRecord, VerdictResult, CPCVResult
- `data-studio.d.ts` — UniverseDefinition, DataCatalog, ExploreSeries

**Stores** under `frontend/src/stores/studio/`:
- `algorithmLabStore.js` — code, variables, session state, paper trade config
- `backtestStore.js` — runs, results, lineage graph state
- `robustnessStore.js` — test configs, scores, report state
- `factorsStore.js` — expression, IC results, library state
- `optimizerStore.js` — params, trials, verdict state
- `dataStudioStore.js` — universe builder, catalog, explorer state

---

## Build Phases

### Phase 1 — Core Foundation ($49/mo tier)
**9 files (7 service + 2 routers). Target: 6-8 weeks.**

| # | Service File | Frontend | Pages |
|---|-------------|----------|-------|
| 1 | `services/algorithm_lab/linter.py` | upgrade Editor.jsx | F1.1 |
| 2 | `services/algorithm_lab/kernel.py` | upgrade QuantKernel.js + StudioStore.js | F1.2, F1.5 |
| 3 | `services/backtest/engine.py` | (already wired) | F2.2 |
| 4 | `services/shared/monte_carlo.py` | MonteCarloCanvas.jsx (upgrade) | F2.3 |
| 5 | `services/shared/data_loader.py` | — | all pages |
| 6 | `services/backtest/metrics.py` | HonestPerformanceCard.jsx | F2.4 |
| 7 | `services/backtest/lineage.py` | ModelLineageGraph.jsx | F2.6 |
| 8 | `routers/algorithm_lab.py` | — | F1 |
| 9 | `routers/backtest_studio.py` | — | F2 |

**Deliverable:** Write in editor → see lookahead warnings → push to backtest → get DSR/PBO-adjusted Sharpe → every run saved in lineage graph. No competitor has this combo.

### Phase 2 — Pro Tier ($99/mo)
**11 files (8 service + 3 routers). Target: 8-10 weeks.**

| # | Service File | Frontend | Pages |
|---|-------------|----------|-------|
| 1 | `services/robustness/tests.py` | ParameterStabilitySurface, TimingPerturbation, CostBreakEven, CapacityStress | F3.2–F3.8 |
| 2 | `services/robustness/scorer.py` | CompositeRobustness.jsx | F3.9 |
| 3 | `services/factors/evaluator.py` | FactorExpressionEditor, InstantIcPanel, IcDecayCurve | F4.1–F4.4 |
| 4 | `services/factors/diagnostics.py` | CrowdingMonitor, HalfLifeDecay, Orthogonalization, Interaction, RegimeIC | F4.5–F4.9 |
| 5 | `services/factors/library.py` | FactorComparisonTable, InternalFactorLibrary | F4.10–F4.11 |
| 6 | `services/optimizer/search.py` | BayesianOptimizer, WalkForwardPanel | F5.2–F5.3 |
| 7 | `services/optimizer/cpcv.py` | CpcvPanel | F5.4 |
| 8 | `services/optimizer/verdict.py` | OverfittingVerdict, TrialRegistry | F5.5–F5.6 |
| 9 | `routers/robustness_lab.py` | — | F3 |
| 10 | `routers/factor_sandbox.py` | — | F4 |
| 11 | `routers/optimizer.py` | — | F5 |

### Phase 3 — Data Studio
**5 files (4 service + 1 router). Can overlap with Phase 2.**

| # | Service File | Frontend | Pages |
|---|-------------|----------|-------|
| 1 | `services/shared/liquidity.py` | LiquidityRealityLayer.jsx | F6.5 |
| 2 | `services/data_studio/universe.py` | FilterStackInterface, TimeVaryingUniverse | F6.1, F6.3 |
| 3 | `services/data_studio/explorer.py` | DataExplorerPanel + MissingDataHeatmap | F6.7–F6.8 |
| 4 | `services/data_studio/catalog.py` | DataFreshnessMonitor + Upload UI | F6.6, F6.9–F6.10 |
| 5 | `routers/data_studio.py` | — | F6 |

### Phase 4 — Paper Trading + Reconciliation
**2 files. After Phase 1 so lineage exists.**

| # | Service File | Frontend | Pages |
|---|-------------|----------|-------|
| 1 | `services/algorithm_lab/paper_trader.py` | PaperTradingPanel.jsx | F1.9 |
| 2 | `services/backtest/reconciliation.py` | LiveVsBacktestPanel.jsx | F2.8 |

---

## Key Design Rules

1. **`shared/data_loader.py`** is the ONLY data access layer. All services call it. No service imports yfinance/FRED directly. Interface: `get_returns(tickers, start, end)`, `get_ohlcv(ticker, start, end)`, `get_factor_returns(model_name)`.

2. **`shared/monte_carlo.py`** is the ONLY MC engine. Backtest Studio, Robustness Lab, and Optimizer all call the same `run_bootstrap()`, `run_garch()`, `run_timing_perturbation()` functions.

3. **`shared/liquidity.py`** is the ONLY liquidity calibrator. Called by capacity test (F3.7), optimizer (F5.2), and paper trader (F1.9). Computes λ per-cap bucket once, caches monthly.

4. **F6.2 Point-in-Time Data is REMOVED** from scope. Too expensive to build/maintain. Survivorship bias toggle still exists in F2.1, but it controls a simpler flag: use current universe vs. a stored daily snapshot.

5. **Routers are thin** — they validate requests, call one service function, return response. All logic lives in services/.

6. **Python files only.** This doc = architecture plan. Files not created yet — waiting for your go.
