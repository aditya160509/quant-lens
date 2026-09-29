# Studio V2 Implementation Handoff

Last updated: 2026-07-30

## Status checklist

- [x] Read the Studio V2 remaining-work specification.
- [x] Audited the existing Studio V2 pages, components, hooks, stores, and shared primitives.
- [x] Added all 33 named V2 feature components from Sections 1 and 6 of `STUDIO_V2_REMAINING.md`.
- [x] Added the four named Studio V2 hooks.
- [x] Added the three named Zustand stores.
- [x] Added the research-journal type declarations.
- [x] Added the Portfolio Risk page and its five feature panels.
- [x] Integrated the new feature panels into the Algorithm Lab, Backtest, Robustness, Factors, Optimizer, and Data pages.
- [x] Added a shared, responsive visual system for the new institutional research panels.
- [x] Added request cancellation, response caching, binary-download handling, and PUT/DELETE support to the shared Studio API hook.
- [x] Added lazy loading for expensive page sections and heavy visualizations.
- [ ] Resolve the current Studio-specific ESLint findings listed below.
- [ ] Run a clean production build after the lint fixes.
- [ ] Run browser-level functional and responsive validation with the backend available.
- [ ] Validate every new API flow against live backend responses, including error and empty states.
- [ ] Resolve the conflict in the “17 Original Missing Components” specification before calling the 59-file plan complete.
- [ ] Add focused component, hook, store, and API contract regression tests.

## Scope and source of truth

This handoff covers the Studio V2 frontend work requested in:

- `STUDIO_V2_REMAINING.md`
- `frontend/src/app/studio/`
- `frontend/src/components/studio-v2/`
- `frontend/src/hooks/studio/`
- `frontend/src/stores/studio/`
- `frontend/src/types/studio/`

The repository already had a large dirty worktree before this pass. This document does not attribute unrelated backend, frontend, data, cache, deletion, or configuration changes to the Studio V2 implementation. No unrelated files were reverted or deleted.

## Work completed

### Shared API and state infrastructure

The shared Studio API client now supports:

- GET, POST, PUT, and DELETE requests.
- JSON and binary responses.
- ZIP and octet-stream downloads as `Blob` values.
- Request-key cancellation so stale requests do not overwrite newer results.
- Time-to-live response caching for repeatable read requests.
- Shared loading and error state.

The following hooks were added:

- `usePortfolioComposition.js`
- `useCollaboration.js`
- `useSnippets.js`
- `usePortfolioRisk.js`

The following stores were added:

- `portfolioCompositionStore.js`
- `portfolioRiskStore.js`
- `researchJournalStore.js`

The following type declaration was added:

- `research-journal.d.ts`

### Shared frontend primitives and design system

`remainingPrimitives.jsx` and `remaining.css` provide a consistent system for the new panels:

- Research panels, stat rails, compact ledgers, matrices, drawers, and progress strips.
- Error, empty, loading, and disabled states.
- Compact number, percentage, currency, and date formatting.
- Lightweight SVG micro-lines instead of a charting dependency for small series.
- Responsive grids and narrow-screen layout behavior.
- Reduced-motion support.
- `content-visibility` containment for below-the-fold rendering performance.
- Reusable download handling for backend-generated artifacts.

The Studio navigation now exposes Portfolio Risk. The live clock has hydration protection.

### Algorithm Lab

Added:

- `StrategyTemplateLibrary.jsx`
- `PortfolioComposition.jsx`
- `ExportCleanModule.jsx`
- `CollaborativeSession.jsx`
- `ComputeGuardrail.jsx`
- `SnippetLibrary.jsx`
- `ResearchJournal.jsx`

The Algorithm Lab now includes a Research Assets drawer for templates, composition, snippets, collaboration, compute controls, clean export, and the research journal. Forking a template can populate the active editor.

### Backtest Studio

Added:

- `PortfolioBacktestRunner.jsx`
- `StrategyCorrelationMatrix.jsx`
- `SectorAttributionChart.jsx`
- `FactorAttributionTable.jsx`
- `SlippagePostMortem.jsx`
- `TaxAwareToggle.jsx`
- `ScenarioReplayGrid.jsx`
- `ScenarioCard.jsx`
- `StrategyComparisonView.jsx`

Also added the supporting baseline panels:

- `BacktestConfigPanel.jsx`
- `BacktestRunner.jsx`
- `MonteCarloDisplay.jsx`
- `TearsheetView.jsx`
- `ExportDialog.jsx`
- `StrategySelector.jsx`

The Backtest page now combines run configuration, execution, honest performance, Monte Carlo output, attribution, slippage analysis, tax-aware controls, scenario replay, comparison, and export.

### Robustness Lab

Added:

- `DataSourceRobustness.jsx`
- `LookAheadAuditExport.jsx`
- `ParameterInteractionSurface.jsx`
- `AdversarialStressTest.jsx`
- `UniversePerturbationPanel.jsx`
- `NoiseInjectionPanel.jsx`

These panels were integrated with the existing CPCV, walk-forward, timing perturbation, capacity, overfitting, and stability views.

### Factor Sandbox

Added:

- `CompositeScoreBuilder.jsx`
- `TurnoverVsDecayChart.jsx`
- `FactorGovernancePanel.jsx`
- `ExtendedDiagnostics.jsx`
- `IcDecayCurve.jsx`
- `CrossSectionalDist.jsx`
- `RegimeIcPanel.jsx`

The page now exposes composite construction, decay and turnover evidence, approval history, diagnostics, cross-sectional distribution, and regime-conditioned Information Coefficient analysis.

### Optimizer

Added:

- `ParetoFrontierView.jsx`
- `EnsembleModePanel.jsx`
- `CrossValidationOverlay.jsx`
- `ParameterDeclaration.jsx`

The optimizer page now combines Bayesian search with Pareto inspection, ensemble construction, cross-validation evidence, and explicit parameter declarations.

### Universe and Data Studio

Added:

- `MultiAssetFilters.jsx`
- `EventCalendarOverlay.jsx`
- `DataCatalog.jsx`
- `MissingDataHeatmap.jsx`
- `UniverseExport.jsx`
- `DataUploadDialog.jsx`

The page now brings catalog, point-in-time universe, liquidity, freshness, missingness, event, multi-asset, upload, and export workflows into one surface.

### Portfolio Risk

Added the `/studio/portfolio-risk` page and:

- `portfolio-risk/AggregateVarPanel.jsx`
- `portfolio-risk/ConcentrationDashboard.jsx`
- `portfolio-risk/CorrelationMatrix.jsx`
- `portfolio-risk/ExposureLimitsPanel.jsx`
- `portfolio-risk/RiskAlertFeed.jsx`

The page supports active-strategy selection, aggregate Value at Risk, concentration diagnostics, correlation inspection, exposure-limit editing, and alerts.

## Backend review work already recorded in the repository

The following review documents contain their own dated remediation checklists and remain the authoritative record for those backend passes:

- `backend/app/services/ml_v2/review.md`
- `backend/app/services/screener_v2/review.md`
- `backend/app/services/factors_v2/review.md`
- `backend/app/services/pca_v2/review.md`
- `backend/app/services/portfolio_v2/review.md`
- `backend/app/services/volatility_v2/review.md`

Their top-level checklists record completed mathematical, API, correctness, and performance work, plus deliberate exclusions. In particular:

- ML V2 records corrected Deflated Sharpe Ratio, Probability of Backtest Overfitting, embargo validation, ensemble weighting, Information Coefficient Information Ratio, Roll spread, deterministic hashing, leakage removal, feature routing, and realtime model enhancements.
- Screener V2 records corrected gap math, rebalance costs, point-in-time formula handling, formula guards, technical indicators, factor templates, export formats, scoring, holding-period analysis, valuation directions, and focused regression tests.
- Factors V2 records corrected predictive inference, holding-return attribution, leakage, bootstrap logic, factor decay, covariance selection, impact modeling, optimizer constraints, impulse responses, and F01 through F14 smoke validation.
- PCA V2 records completed remediation for F01 through F11, API routing, mathematical regression checks, and local-data smoke execution.
- Portfolio V2 records substantial F01 through F13 remediation, with several external-data and advanced-model gaps still explicitly open.
- Volatility V2 records lookahead removal, estimator corrections, dynamic News Impact Curves, Value at Risk coverage, API routing, and local smoke checks.

These statements summarize the checklists already present in those files. A new repository-wide backend test run was not performed as part of this frontend handoff.

## Remaining work and exact next steps

### 1. Fix Studio lint errors

Current known defects:

- `TurnoverVsDecayChart.jsx` has a malformed `useMemo` expression.
- `useCollaboration.js` reconnect logic references its callback during callback initialization.
- `ComputeGuardrail.jsx` needs stable API method dependencies and deferred initial refresh.
- `FactorGovernancePanel.jsx` needs a stable load callback and deferred initial refresh.
- `ResearchJournal.jsx` needs narrower store/API subscriptions and stable dependencies.
- `useSnippets.js` needs its initial state-producing load deferred outside the effect body.
- Several pages and data-loading panels need destructured API/store callbacks in dependency arrays.

Required verification:

```bash
cd frontend
npx eslint \
  src/app/studio \
  src/components/studio-v2 \
  src/hooks/studio \
  src/stores/studio
```

Acceptance condition: zero Studio-specific ESLint errors. Warnings should also be removed unless a warning is demonstrated to be a false positive and documented inline.

### 2. Resolve the 17-component specification conflict

`STUDIO_V2_REMAINING.md` currently names these original missing components:

- `BacktestConfigPanel.jsx`
- `BacktestRunner.jsx`
- `TearsheetView.jsx`
- `DatasetSelector.jsx`
- `StartTraining.jsx`
- `DeployModel.jsx`
- `PaperTradingPanel.jsx`
- `ExecutionDashboard.jsx`
- `StrategyDevelopment.jsx`
- `DataImport.jsx`
- `CleanData.jsx`
- `FeatureEngineering.jsx`
- `ModelConfig.jsx`
- `TrainModel.jsx`
- `EvaluateModel.jsx`
- `DeploymentStatus.jsx`
- `MonitoringDashboard.jsx`

The current implementation pass instead added a Studio-focused set that includes Monte Carlo, export, strategy selection, robustness, factor-diagnostic, optimizer, and data components. Some named files in the source specification still do not exist under `studio-v2`, especially the ML training and deployment group.

Next action:

1. Decide whether the source list is stale and should point to the already-developed ML V2 and execution pages elsewhere in the frontend.
2. If the list is current, build and integrate the missing named components into explicit Studio routes.
3. Update `STUDIO_V2_REMAINING.md` so its checklist and count match the actual required product surface.

Until this is resolved, the statement “59 of 59 files complete” would be inaccurate.

### 3. Close end-to-end composition and portfolio-run gaps

The portfolio backtest workflow needs a verified strategy-source handoff:

1. Persist every forked/saved strategy in the Algorithm Lab asset state, not only the current strategy.
2. Let Portfolio Composition select at least two real saved strategies.
3. Make `portfolio-run` accept a composition identifier or resolve every stored strategy to executable source.
4. Preserve shared configuration, per-strategy overrides, weights, and provenance.
5. Return and render correlation, attribution, slippage, and individual-versus-combined results.
6. Test cancellation, failure, partial result, and rerun behavior.

### 4. Finish synthetic-range visualization

The Data Studio specification includes synthetic-range display. The frontend still needs to:

1. Request synthetic ranges for the selected ticker.
2. Overlay those ranges on the data chart using an unambiguous dashed or shaded treatment.
3. Add a legend and tooltip text that explains why the data is synthetic.
4. Ensure exports preserve synthetic-range metadata.

### 5. Validate API contracts

For every new component:

1. Compare the frontend payload against its backend request model.
2. Compare response parsing against real success responses.
3. Exercise empty, partial, unauthorized, validation-error, timeout, and server-error responses.
4. Confirm downloadable ZIP, CSV, JSON, and audit artifacts retain filenames and MIME types.
5. Confirm WebSocket authentication, participant lifecycle, reconnection backoff, and intentional disconnect behavior.

### 6. Add automated tests

Minimum useful test set:

- API hook cache, cancellation, binary response, and error normalization.
- Portfolio composition add/remove/reweight invariants.
- Portfolio risk loading and limit-update state.
- Research journal filtering and CRUD.
- Collaboration connection, reconnect, send, and disconnect behavior with a mocked WebSocket.
- Component empty/loading/error states.
- Matrix and chart behavior with missing, constant, and non-finite values.
- Page smoke tests for all seven Studio routes.
- Backend contract tests for every endpoint consumed by a new component.

### 7. Run production and browser verification

After lint and automated tests:

```bash
cd frontend
npm run build
```

Then run the frontend and backend and verify:

- `/studio`
- `/studio/backtest`
- `/studio/robustness`
- `/studio/factors`
- `/studio/optimizer`
- `/studio/data`
- `/studio/portfolio-risk`

Browser acceptance:

- No console errors, hydration errors, failed dynamic imports, or unhandled rejections.
- All primary controls are keyboard reachable and visibly focused.
- Drawers and dialogs trap or manage focus correctly and close with Escape.
- Labels, buttons, matrices, and status states remain legible at 360, 768, 1024, and 1440 pixel widths.
- No horizontal page overflow.
- Reduced-motion preference is respected.
- Expensive panels load only when required.
- Large datasets do not cause long main-thread stalls.

### 8. Performance profiling

After correctness:

1. Record production bundle sizes for every Studio route.
2. Confirm heavy charting libraries are isolated to route-level or panel-level chunks.
3. Profile initial render, drawer opening, large matrix rendering, and data refresh.
4. Virtualize only tables or lists proven large enough to need it.
5. Move genuinely expensive backend work to cached/offline jobs and keep the interactive path bounded.
6. Do not add GPU paths, exhaustive bootstrap defaults, nested full-universe optimization, or other disproportionate compute unless a real user workflow requires them.

## Deliberately deferred compute-heavy work

The backend review files already mark several items as intentionally deferred because they are expensive and unnecessary for normal interactive use. Examples include:

- Broad or nested hyperparameter searches on every request.
- Deep sequence-model training and reinforcement-learning training in the realtime path.
- Hundreds or thousands of default bootstrap refits.
- Mixed-integer cardinality optimization.
- Exhaustive daily rolling refits.
- Full-universe nested purged cross-validation.
- Per-request dynamic conditional correlation or vector autoregression bootstraps.
- GPU-specific execution paths without a demonstrated user requirement.

These should remain offline, cached, explicitly opt-in, or omitted. “Maximum performance” here means minimizing latency and resource use for meaningful user workflows, not running every theoretically possible model.

## Definition of done

Studio V2 is complete only when all of the following are true:

- [ ] The source specification has one unambiguous list of required artifacts.
- [ ] Every required artifact exists and is integrated into a reachable page.
- [ ] Every visible workflow reaches a real backend endpoint or is clearly marked unavailable.
- [ ] Studio lint passes.
- [ ] Focused frontend and backend tests pass.
- [ ] The frontend production build passes.
- [ ] All seven routes pass desktop and mobile browser validation.
- [ ] Accessibility and keyboard behavior are verified.
- [ ] Performance profiling shows no unbounded interactive work.
- [ ] The final completion report contains command output, test counts, and any deliberate exclusions.

