# Studio V2 — Frontend Remaining Work

> **Backend audit:** see separate `STUDIO_V2_BACKEND_GAPS.md`
> **Frontend status:** 0 of 59 planned frontend files have been built

---

## 1. 33 New V2 Frontend Components

Each component maps to a feature from the spec. Backend APIs are all live at `/api/v2/`.

### Page 1 — Algorithm Lab (6 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 1 | `StrategyTemplateLibrary.jsx` | F1.10 | `GET /api/v2/algorithm-lab/templates` |
| 2 | `PortfolioComposition.jsx` | F1.11 | `POST /api/v2/algorithm-lab/compose` |
| 3 | `ExportCleanModule.jsx` | F1.12 | `POST /api/v2/algorithm-lab/export/{strategy_id}` |
| 4 | `CollaborativeSession.jsx` | F1.13 | `WS .../collaborate` |
| 5 | `ComputeGuardrail.jsx` | F1.14 | `GET .../compute-status` |
| 6 | `SnippetLibrary.jsx` | F1.15 | `GET /api/v2/algorithm-lab/snippets` |

### Page 2 — Backtest Studio (9 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 7 | `PortfolioBacktestRunner.jsx` | F2.9 | `POST /api/v2/backtest/portfolio-run` |
| 8 | `StrategyCorrelationMatrix.jsx` | F2.9 | returned in portfolio-run response |
| 9 | `SectorAttributionChart.jsx` | F2.10 | `GET .../attribution/{run_id}` |
| 10 | `FactorAttributionTable.jsx` | F2.10 | (same route) |
| 11 | `SlippagePostMortem.jsx` | F2.11 | `GET .../slippage-audit/{run_id}` |
| 12 | `TaxAwareToggle.jsx` | F2.12 | Extended `POST .../run` |
| 13 | `ScenarioReplayGrid.jsx` | F2.13 | `POST .../scenarios/{id}/replay/{sid}` |
| 14 | `ScenarioCard.jsx` | F2.13 | (used by grid) |
| 15 | `StrategyComparisonView.jsx` | F2.14 | `POST /api/v2/backtest/compare` |

### Page 3 — Robustness Lab (4 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 16 | `DataSourceRobustness.jsx` | F3.10 | `POST /api/v2/robustness/run-core-tests` |
| 17 | `LookAheadAuditExport.jsx` | F3.11 | `POST .../audit-trail/{sid}` |
| 18 | `ParameterInteractionSurface.jsx` | F3.12 | `POST .../run-core-tests` |
| 19 | `AdversarialStressTest.jsx` | F3.13 | `POST .../adversarial` |

### Page 4 — Factor Sandbox (3 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 20 | `CompositeScoreBuilder.jsx` | F4.12 | `POST /api/v2/factors/evaluate` |
| 21 | `TurnoverVsDecayChart.jsx` | F4.13 | `GET .../factors/ic-diagnostics` |
| 22 | `FactorGovernancePanel.jsx` | F4.14 | `POST .../library/{id}/approve` |

### Page 5 — Optimizer (3 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 23 | `ParetoFrontierView.jsx` | F5.7 | `POST /api/v2/optimizer/bayesian-search` |
| 24 | `EnsembleModePanel.jsx` | F5.8 | `POST /api/v2/optimizer/ensemble` |
| 25 | `CrossValidationOverlay.jsx` | F5.9 | `POST /api/v2/optimizer/cross-validate` |

### Page 6 — Universe & Data Studio (2 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 26 | `MultiAssetFilters.jsx` | F6.11 | `GET .../data-studio/asset-classes` |
| 27 | `EventCalendarOverlay.jsx` | F6.12 | `GET .../events/{ticker}` |

### Page 7 — Portfolio Risk (5 components)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 28 | `portfolio-risk/AggregateVarPanel.jsx` | F7.1 | `GET .../portfolio-risk/var` |
| 29 | `portfolio-risk/ConcentrationDashboard.jsx` | F7.2 | `GET .../portfolio-risk/concentration` |
| 30 | `portfolio-risk/CorrelationMatrix.jsx` | F7.2 | `GET .../portfolio-risk/correlation` |
| 31 | `portfolio-risk/ExposureLimitsPanel.jsx` | F7.3 | `GET/PUT .../limits` |
| 32 | `portfolio-risk/RiskAlertFeed.jsx` | F7.4 | `GET .../alerts` |

### Cross-cutting (1 component)

| # | Component | Feature | Backend API |
|---|-----------|---------|-------------|
| 33 | `ResearchJournal.jsx` | F0.1 | `GET /api/v2/journal` |

---

## 2. 4 New V2 Hooks

| Hook | Purpose |
|------|---------|
| `usePortfolioComposition.js` | Manage composition CRUD, execution, and polling state |
| `useCollaboration.js` | WebSocket lifecycle, invite generation, participant tracking |
| `useSnippets.js` | Snippet CRUD with tag management |
| `usePortfolioRisk.js` | VaR data, correlation matrix, concentration metrics, alerts |

---

## 3. 3 New V2 Stores

| Store | Purpose |
|-------|---------|
| `portfolioCompositionStore.js` | Zustand store for composition state and results |
| `portfolioRiskStore.js` | Zustand store for risk metrics and active strategies |
| `researchJournalStore.js` | Zustand store for journal entries and tags |

---

## 4. 1 New V2 Type

| File | Purpose |
|------|---------|
| `research-journal.d.ts` | TypeScript types for journal entry, tag, filtering |

---

## 5. 1 New V2 Page

| File | Route |
|------|-------|
| `portfolio-risk/page.js` | `/api/v2/portfolio-risk/*` page with all 5 risk components |

---

## 6. 17 Original Missing Components

These were flagged in `STUDIO_V2_ADDITIONS.md` as still outstanding from the original Studio spec. All 17 remain unbuilt.

| Component | Likely Backend API |
|-----------|-------------------|
| `BacktestConfigPanel.jsx` | Backtest run config form |
| `BacktestRunner.jsx` | Backtest execution + progress |
| `TearsheetView.jsx` | Performance tearsheet display |
| `DatasetSelector.jsx` | ML dataset selection |
| `StartTraining.jsx` | ML training launcher |
| `DeployModel.jsx` | ML model deployment |
| `PaperTradingPanel.jsx` | Paper trading controls |
| `ExecutionDashboard.jsx` | Execution monitoring |
| `StrategyDevelopment.jsx` | Strategy dev workspace |
| `DataImport.jsx` | External data import |
| `CleanData.jsx` | Data cleaning UI |
| `FeatureEngineering.jsx` | Feature engineering |
| `ModelConfig.jsx` | Model configuration |
| `TrainModel.jsx` | Model training |
| `EvaluateModel.jsx` | Model evaluation |
| `DeploymentStatus.jsx` | Deployment status |
| `MonitoringDashboard.jsx` | Monitoring dashboard |

---

## Total Frontend

| Category | Count |
|----------|-------|
| V2 Components | 33 |
| V2 Hooks | 4 |
| V2 Stores | 3 |
| V2 Types | 1 |
| V2 Pages | 1 |
| Original Missing | 17 |
| **Total** | **59 files** |
