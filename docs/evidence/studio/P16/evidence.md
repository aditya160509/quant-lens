# P16-W1 Parity / Deletion Evidence + P16-W2 SAFE Cleanup

Date (UTC): 2026-09-29
Rollback tag (local only, not pushed): `p16-pre-cleanup-20260929`
Scope: evidence + SAFE cleanup only. No routes broken. No V2 pages/components/engines deleted.

## 1. frontend/src/components/studio-v2/ inventory

- Total files under `frontend/src/components/studio-v2/`: **115** (all types, via `find ... | wc -l`).
- Code files (`.jsx`/`.js`/`.tsx`/`.ts`, incl. `portfolio-risk/` and `__tests__/`): **107**.
- Method: `ls -R`, `find -type f | wc -l`. `rg` is not installed in this environment, so `grep -rn` was used as the substitute throughout (commands recorded below).

## 2. Importer evidence (grep substitute for rg)

Commands run (from repo root):

```
grep -rn "studio-v2" frontend/src | wc -l            # => 118 lines
grep -rln "studio-v2" frontend/src | sort            # => 15 files (see below)
grep -ho "studio-v2/[^\"']*" frontend/src/app/studio/*/page.js | sort -u   # => 72 distinct modules
```

Files matching `studio-v2` across `frontend/src` (15 files):

Prod route importers (all under `frontend/src/app/studio/`):

- `frontend/src/app/studio/backtest/page.js`
- `frontend/src/app/studio/data/page.js`
- `frontend/src/app/studio/factors/page.js`
- `frontend/src/app/studio/optimizer/page.js`
- `frontend/src/app/studio/portfolio-risk/page.js`
- `frontend/src/app/studio/robustness/page.js`
- `frontend/src/app/studio/error.js` (route error boundary, CSS class only, no component import)

Self-references inside `frontend/src/components/studio-v2/` (relative `./X` imports + CSS class strings, not external importers):

- `labPrimitives.jsx`, `AlgorithmLab.jsx`, `studio.css`, `algorithm-backtest.css`, `generational-studio.css`, `remaining.css`
- `__tests__/professionalCopy.test.ts` (path join to studio-v2 dir for copy audit)

No prod route outside `frontend/src/app/studio/*` imports `studio-v2`. Verified via `grep -rln "studio-v2" frontend/src` full list above.

### 2a. Per-page direct imports (static + dynamic)

72 distinct `studio-v2/*` modules are directly imported by the six live sub-routes:

- backtest/page.js: `remainingPrimitives`, `labPrimitives`, `BacktestConfigPanel`, `BacktestRunner`, `TearsheetView`, `StrategyCorrelationMatrix`, `ResearchJournal`, `BacktestForensicsConsole`, `algorithm-backtest.css` + dynamic `PortfolioBacktestRunner`, `SectorAttributionChart`, `FactorAttributionTable`, `SlippagePostMortem`, `ScenarioReplayGrid`, `StrategyComparisonView`, `MonteCarloDisplay`, `ExportDialog`, `HonestPerformanceCard`, `ModelLineageGraph`, `LiveVsBacktestPanel`
- data/page.js: `labPrimitives`, `FilterStackInterface`, `TimeVaryingUniverse`, `LiquidityRealityLayer`, `DataExplorerPanel`, `DataFreshnessMonitor`, `DataCatalog`, `MissingDataHeatmap`, `domain-instruments.css` + dynamic `MultiAssetFilters`, `EventCalendarOverlay`, `UniverseExport`, `DataUploadDialog`
- factors/page.js: `labPrimitives`, `ScientificLabInstruments`, `FactorExpressionEditor`, `InstantIcPanel`, `CrowdingMonitor`, `HalfLifeDecayChart`, `OrthogonalizationPanel`, `FactorInteractionPanel`, `FactorComparisonTable`, `InternalFactorLibrary`, `ExtendedDiagnostics`, `IcDecayCurve`, `CrossSectionalDist`, `RegimeIcPanel` + dynamic `CompositeScoreBuilder`, `TurnoverVsDecayChart`, `FactorGovernancePanel`
- optimizer/page.js: `labPrimitives`, `BayesianOptimizer`, `WalkForwardPanel`, `CpcvPanel`, `OverfittingVerdict`, `TrialRegistry`, `ParameterDeclaration`, `domain-instruments.css` + dynamic `ParetoFrontierView`, `EnsembleModePanel`, `CrossValidationOverlay`
- portfolio-risk/page.js: `labPrimitives`, `remainingPrimitives`, `portfolio-risk/AggregateVarPanel`, `portfolio-risk/ConcentrationDashboard`, `portfolio-risk/CorrelationMatrix`, `portfolio-risk/ExposureLimitsPanel`, `portfolio-risk/RiskAlertFeed`, `ResearchJournal`, `domain-instruments.css`
- robustness/page.js: `labPrimitives`, `ScientificLabInstruments`, `ParameterStabilitySurface`, `TimingPerturbationPanel`, `CostBreakEvenChart`, `CapacityStressPanel`, `CompositeRobustness`, `UniversePerturbationPanel`, `NoiseInjectionPanel` + dynamic `DataSourceRobustness`, `LookAheadAuditExport`, `ParameterInteractionSurface`, `AdversarialStressTest`

Shared indirect (relative-import) modules, all live because `labPrimitives.jsx` / `remainingPrimitives.jsx` are imported by every sub-route above:

- `StudioErrorBoundary` (imported by `labPrimitives.jsx:7`, `remainingPrimitives.jsx:4`), `StudioControlDeck` (`labPrimitives.jsx:8,143`), `studioNavigation` (`labPrimitives.jsx:9`, `StudioControlDeck.jsx:5`), `studioError` (`labPrimitives.jsx:10`, `remainingPrimitives.jsx:5`, `DataExplorerPanel`, `RunHistoryPanel`, `FileManager`, `VariableInspector`, `EventLogPanel`, `Editor`), `quantOutputUtils` (`TimeVaryingUniverse.jsx:5`, `ParameterStabilitySurface.jsx:12`, `DataExplorerPanel.jsx:6`), `MarketTape` + `TelemetryFooter` (`labPrimitives.jsx:5-6`), `StudioIcon` (used by `FileManager`, `RunHistoryPanel`, `EventLogPanel`, `PushToBacktestButton`, `AlgorithmFlightDeck`, `PaperTradingPanel`, `VariableInspector`, `CommandPalette`), `TaxAwareToggle` (`BacktestConfigPanel.jsx:4`), `ScenarioCard` (`ScenarioReplayGrid.jsx:5`)

### 2b. Backend Data-inspector surface still serving (backend/app/studio_v2/router.py)

`useDataStudio` (`frontend/src/hooks/studio/useDataStudio.js`) calls these live endpoints, all implemented in `backend/app/studio_v2/router.py`:

- `GET /api/v2/data-studio/catalog` -> `data_catalog` (router.py:1145, via `data_studio/catalog.py:DataCatalog`)
- `GET /api/v2/data-studio/freshness` -> `data_freshness` (router.py:1153, via `DataFreshnessMonitor`)
- `GET /api/v2/data-studio/explorer/series/{ticker}` -> `explorer_series` (router.py:1159)
- `POST /api/v2/data-studio/universe/build` -> `build_universe` (router.py:1189, via `data_studio/universe.py:UniverseBuilder`)
- `POST /api/v2/data-studio/upload` -> `upload_custom_data` (router.py:1222, via `CustomDataUploader`, bounded size + quota + owner-auth)
- `GET /api/v2/data-studio/uploads` -> `list_custom_uploads` (router.py:1313, owner-scoped)
- `DELETE /api/v2/data-studio/uploads/{upload_id}` -> `delete_custom_upload` (router.py:1323)
- `GET /api/v2/data-studio/manifests` + `POST /api/v2/data-studio/manifests/refresh` -> `data_manifests` / `refresh_data_manifest` (router.py:1340-1344)
- Explorer anomalies/heatmap + `ticker_events` + `synthetic_ranges` also live (router.py:1176-1393).

Conclusion: catalog/freshness/uploads engines in `backend/app/studio_v2/data_studio/` + `shared/data_manifest.py` are prod-serving and must NOT be deleted.

## 3. Route registration

| Route | File | Shell | Status |
|---|---|---|---|
| `/studio` | `frontend/src/app/studio/page.js` | Canonical original shell (`@/components/studio/OriginalStudioPage`) | Canonical |
| `/studio/backtest` | `frontend/src/app/studio/backtest/page.js` | V2 (`studio-v2` panels) | V2-owned |
| `/studio/data` | `frontend/src/app/studio/data/page.js` | V2 (Data inspector) | V2-owned |
| `/studio/factors` | `frontend/src/app/studio/factors/page.js` | V2 | V2-owned |
| `/studio/optimizer` | `frontend/src/app/studio/optimizer/page.js` | V2 (page.js at `app/studio/optimizer/`, note: no fs `optimizer` dir listing anomaly, route file confirmed) | V2-owned |
| `/studio/portfolio-risk` | `frontend/src/app/studio/portfolio-risk/page.js` | V2 | V2-owned |
| `/studio/robustness` | `frontend/src/app/studio/robustness/page.js` | V2 | V2-owned |
| `/labs/studio` | `frontend/src/app/labs/studio/page.js` | `redirect("/studio")` | Redirect, no shell |

Verified: `/studio` mounts `OriginalStudioPage`; `/labs/studio` redirects to `/studio`. No route broken by this task (zero route files touched).

## 4. Quality audit (canonical Studio path)

- No direct backend-internals import in components: PASS. `grep -rn "from backend|from app.studio|import backend|exec(|eval("` over `components/studio/`, `components/studio-v2/`, `app/studio/` returned only: `Studio/PreExecuteModal.jsx` comments about reading backend metadata (not imports), `studio-v2/Editor.jsx:21` `LIKELY_DENIED_IMPORTS` lint list, and `backend/.../execution_worker.py` `exec(compile(...))` (backend-side sandbox, see below). No frontend file imports backend internals.
- No synthetic data: PASS on sampled Data-inspector components. `grep -rni "synthetic|Math.random"` over `DataCatalog.jsx`, `DataFreshnessMonitor.jsx`, `DataExplorerPanel.jsx` returned zero fabrication hits; backend has `data_studio/synthetic_flagging.py:SyntheticRangeDetector` which flags (not fabricates) synthetic ranges.
- No unrestricted exec: CONDITIONAL PASS. `execute_code` (router.py:471) runs user code in a forked `multiprocessing` worker (`execution_worker.execute_in_worker`) with restricted globals (`pd`, `np`, `__builtins__` + session namespace), cancellable via `ComputeBudget`/kill, result filtered to picklable non-underscore locals. Frontend `Editor.jsx` keeps a denied-import hint list. No raw `eval`/`new Function`/`child_process` in frontend studio paths.
- Secret rejection: GAP. No secret-scan/reject logic found in `backend/app/studio_v2/router.py`, `shared/*.py`, `data_studio/catalog.py`, `algorithm_lab/kernel.py|linter.py|execution_worker.py`, or `hooks/studio/` + `DataUploadDialog.jsx` (`grep -rn "secret|BEGIN.*PRIVATE|api_key|API_KEY|password"` returned zero hits in those files). Upload path validates size/quota/owner-identity but does not scan content for secrets. Recorded as remaining P16 gap, not fixed in this task (out of SAFE scope).
- Error envelopes: PASS. Backend `_error_detail(code, message, details, request_id)` + `_guarded` wrapper map to 400/401/403/404/409/422/500 with `ErrorResponse` models (router.py:246-300). Frontend uses `InlineError`/`toStudioError`/`formatStudioValue` pervasively (all six sub-route pages + panels).

## 5. SAFE cleanup: what was deleted vs left

### Deleted by this task: NONE (zero new file deletions)

Rationale: every `studio-v2` component is either directly imported by a live `/studio/*` route, indirectly imported via `labPrimitives`/`remainingPrimitives`/`AlgorithmLab` relative imports, or referenced by `__tests__`/hooks contract tests. Every `backend/app/studio_v2` engine backing catalog/freshness/uploads/factors-library/optimizer is prod-serving (Section 2b). Under the strict rule (zero graph + zero grep + zero route + zero test references required), nothing qualified.

Pre-existing working-tree deletions (NOT made by this task, left untouched):

- `backend/app/services/.regime_cache/*.json` (already `D` in working tree; matches task description of regime_cache JSONs already deleted).
- Top-level report bundles (`API_OPTIMIZATION_REPORT.md`, `FEATURE_MASTER_PLAN.md`, `FINAL_IMPLEMENTATION_REPORT.md`, `IMPLEMENTATION_STATUS_REPORT.md`, `MACRO_AUDIT_REPORT.md`, `MASTER_PLAN.md`, `ML.MD`, `SECURITY_AUDIT.md`, `SPEC_ANALYSIS_REPORT.md`, `STATS_AUDIT_REPORT.md`, `TASK_TRACKER.md`, all `D` unstaged) plus `backend/app/api/earnings.py|liquidity.py|monitor.py`, `backend/app/macro.py`, `backend/app/models/*.py`, `.playwright-mcp/*.png`, `.orchids/orchids.json`, `data/prices/*`, `data/factors_us/*` deletions. These predate this task; P16-W2 does not claim, stage, or revert them.

Checked and correctly left alone:

- `frontend/output/playwright`: does not exist, nothing to clean.
- `*.backup`/`*.bak`/`*.orig`: only `frontend/node_modules/form-data/README.md.bak` (inside node_modules, not tracked source). Left alone.
- `__pycache__`/`__pycache__/*.pyc`: present under `backend/app/studio_v2/*` and `backend/tests`, but gitignored build artifacts, not tracked deletions. Left alone per minimal-change rule.

### Left alone with reasons (open / V2-owned)

- All six `frontend/src/app/studio/*/page.js` V2 routes: live prod routes (Section 3).
- All 72 directly-imported + all relatively-imported `studio-v2` shared modules: live importers (Section 2a).
- `AlgorithmLab.jsx` subtree (`AlgorithmLab`, `AlgorithmFlightDeck`, `Editor`, `EventLogPanel`, `StudioChartPanel`, `VariableInspector`, `FileManager`, `RunHistoryPanel`, `PushToBacktestButton`, `PaperTradingPanel`, `CommandPalette`, `StrategyTemplateLibrary`, `PortfolioComposition`, `ExportCleanModule`, `CollaborativeSession`, `ComputeGuardrail`, `SnippetLibrary`): OPEN. `AlgorithmLab.jsx` itself has no `@/components/studio-v2/AlgorithmLab` route importer, but it aggregates the subtree via relative imports and its hook (`useAlgorithmLab`) is covered by contract tests. Evidence of deadness is plausible but not conclusive, so per instructions it is LEFT and marked open, not deleted.
- `StrategySelector.jsx`, `RegimePnLBreakdown.jsx` (studio-v2): OPEN. Zero importers found (the `StrategySelector` hits in `chart_engine/` are a different component), but single-file deletion evidence (graph tool unavailable, only grep) is below the strict bar, so LEFT and marked open.
- `backend/app/studio_v2/*` (catalog, freshness, uploads, factors library/governance, optimizer search/cpcv/ensemble/verdict, robustness jobs, backtest engines, portfolio-risk engines, journal, manifests): all serving live `/api/v2/*` endpoints consumed by hooks/tests. LEFT.

## 6. Verification runs

- `npx eslint` (from `frontend/`, on all seven route files to prove routes intact; this task changed no source files, only added docs): exit 0, zero warnings/errors on `src/app/studio/page.js`, `backtest/page.js`, `data/page.js`, `factors/page.js`, `optimizer/page.js`, `portfolio-risk/page.js`, `robustness/page.js`.
- `npx jest src/app/studio/__tests__/routes.test.tsx src/components/studio/__tests__/StudioShellControls.test.tsx src/components/studio/__tests__/StudioModeStage.test.tsx` (from `frontend/`): 3 suites passed, 13 tests passed, 0 snapshots.
- `PYTHONPATH=backend python3.11 -m pytest -q backend/tests/test_studio_jobs.py backend/tests/test_studio_security.py backend/tests/test_studio_reports.py`: 27 passed, 1 FAILED. The single failure is `test_studio_reports.py::test_arrow_export_is_deterministic_and_reconciled` with `ModuleNotFoundError: No module named 'pyarrow'` (missing optional dependency in this environment, unrelated to P16 which changed zero backend code).
