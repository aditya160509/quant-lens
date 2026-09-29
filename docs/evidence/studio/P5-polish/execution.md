# Execution record: P5 Develop polish (P5-W1–W3) 2026-09-29

- Date: 2026-09-29
- Scope: Phase 5 polish per docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md lines 574-633. Smallest complete change, existing patterns reused. No backend changes. `npm run build` NOT run (per task).

## Files changed (frontend/ repo root)

1. `frontend/src/stores/studio/projectStore.js`
   - Folder-aware move: `moveFile(id, folder)` relocates a file under a folder/prefix path, keeps basename, refuses clobber; `folderOf`/`normalizeFolder` helpers exported; `createFile(name, folder)` accepts destination; `rename` preserves folder prefix.
   - Conflict-safe autosave version: `lastSavedAt` + `autoSavedAt` stamps, `autosaveFile(id)` action, persist version 2 to 3 with migration, versioned storage wrapper (primary + `quant360-studio-project-backup` keys, rehydrate keeps newer timestamp).
   - Server sync documented as OPEN in code (no backend project API exists).
2. `frontend/src/components/studio/develop/ProjectTree.jsx`
   - Folder-grouped rendering, per-file Move affordance with folder picker (datalist of existing folders + free text), `M` keyboard shortcut. Keeps `role="tree"`, `aria-selected`, Enter/F2/Del, guarded delete (`confirm`).
3. `frontend/src/components/studio/Editor.jsx`
   - LSP-lite (explicitly NOT a language server): exported pure `analyzePythonSource` (empty source, missing `class Strategy`, unbalanced brackets, mixed tabs/spaces, >120 char lines, likely-denied imports as warnings), `extractSymbols` (class/def with line numbers), `STRATEGY_COMPLETIONS` + `filterCompletions` (Python keywords + Strategy snippets).
   - UI: symbol-jump dropdown in header, diagnostics strip, Monaco markers via `setModelMarkers`, palette gains Completions (click-to-insert) and Symbols (click-to-jump) sections. Cmd+P / Cmd+S bindings kept.
   - Autosave now uses `autosaveFile` (conflict-safe stamp); selection text tracked into `editorStore.selectedCode` for selection run.
4. `frontend/src/stores/studio/editorStore.js`
   - Added `selectedCode` + `setSelectedCode` (best-effort Monaco selection buffer; never authoritative file content).
5. `frontend/src/hooks/studio/useStudioExecution.js`
   - Added `executeSelection(selectedCode)`: same `execute` job type with `source: 'selection'` label; quota pre-check; empty-selection and over-budget errors; backend bounded policy still authoritative (bare snippets are truthfully rejected, never silently wrapped).
   - Added `STUDIO_QUOTAS` (mirrors `conventions.py` + `execution.py`: 64KB code, 100k signals, 4MB response, 50bps slippage, 1% commission, 30y lookback, `isolated_one_shot`) and `estimateComputeQuota(code)` display helper.
6. `frontend/src/components/studio/develop/ExecutionDock.jsx`
   - Run-selection button (disabled without selection/while executing), env picker (local `isolated_one_shot` / container display) fed by `GET /health` (`isStudioHealthResponse`; container shows truthful not-reported note), quota strip from `estimateComputeQuota`, resource telemetry (`data.metadata.resources` when present, else honest "not reported — elapsed + convention limits shown").
   - Variables explorer: per-key expand + pagination (`VARIABLES_PAGE_SIZE = 50`, exported `paginateVariable`), prev/next page controls.
7. `frontend/src/components/studio/PreExecuteModal.jsx`
   - Timezone/currency/calendar still read from backend metadata; added exported pure validators `validateCorporateActions`, `validateLookAhead`, `validateMarketConventions`, `assessPreflight` (blocking vs warnings). Inline IIFE now uses `assessPreflight`. UI adds Corporate-Action and Look-Ahead validator cards; backend currently reports `unknown`/`not_verified`, shown truthfully as warnings (never blocking).
8. `frontend/src/components/studio/develop/__tests__/p5-polish.test.ts` (new)
   - Covers folder helpers, LSP-lite diagnostics/symbols/completions, pagination bounds, preflight validators, quota constants/estimates.

## Tests run + results (exact commands)

- `cd frontend && npx eslint src/stores/studio/projectStore.js src/stores/studio/editorStore.js src/components/studio/develop/ProjectTree.jsx src/components/studio/develop/ExecutionDock.jsx src/components/studio/Editor.jsx src/components/studio/PreExecuteModal.jsx src/hooks/studio/useStudioExecution.js src/components/studio/develop/__tests__/p5-polish.test.ts` → EXIT 0, no errors, no warnings (after fixing one extra-paren parse error, one unused eslint-disable, one missing exhaustive-deps entry).
- `cd frontend && npm test -- src/components/studio/develop src/components/studio/__tests__ src/stores/studio src/lib/__tests__/studioApi.test.ts src/lib/__tests__/studioValidators.test.ts` → 19 suites passed including new `p5-polish.test.ts` (8 tests) and existing `projectStore`/`editorStore` suites; 71 tests passed, 1 failed. The 3 failing suites are PRE-EXISTING syntax errors in untouched files, verified by error location:
  - `TearsheetView.test.tsx`, `ReplayView.test.tsx` → parse error in `src/lib/studioResults.js:200` (untouched).
  - `ValidateView.audit.test.tsx` → parse error in `src/components/studio/ValidateView.jsx:164` (untouched).
- `cd backend && PYTHONPATH=. python3 -m pytest -q tests/test_studio*.py` → system `python3` is 3.9.6 and cannot parse backend `X | None` syntax (pre-existing env issue); reran with `/opt/homebrew/bin/python3.11` (pytest 9.0.2; installed missing `supabase` dep into that interpreter only, no repo change) → **260 passed, 12 failed**. All 12 failures are pre-existing/environmental in backend files (zero backend files changed by this package):
  - `test_studio_v2_frontend_traceability` (2) → extractor throws on untouched `frontend/src/hooks/studio/useDataStudio.js:73,83` (unclassified `/api/v2` paths), before any file this package touches.
  - `test_studio_metrics`, `test_studio_v2_api_inventory`, `test_studio_v2_contract`, `test_studio_v2_edge_cases` (futures roll x3), `test_studio_v2_optimizer_edges` (x3), `test_monte_carlo[moving_block_bootstrap]` → dependency drift (`fastapi` response-field validation, numpy behavior) in untouched backend code.

## Known limitations

- No full LSP server (by design): diagnostics are client-side heuristics; backend bounded policy is authoritative at run time.
- Project persistence is local-only with backup key; server sync/conflict resolution stays open until a backend project API exists.
- Env picker is display + log labeling: backend `CreateJobRequest` only accepts `execute` params, so jobs always run on `isolated_one_shot`; container option is shown as not-reported, never claimed.
- Server resource telemetry renders only if backend returns `metadata.resources`; currently shows elapsed + convention limits.
- Variables pagination previews up to 10 rows per expanded page for DOM size; pager still pages the full 50-row pages.
- `xterm.js` terminal stays intentionally deferred per P1-W3 one-shot contract.
- Pre-existing failures above (frontend syntax errors, backend dep drift) are out of scope and untouched.

## Rollback (repo root is `frontend/`; workspace changes are uncommitted)

- `git restore src/stores/studio/projectStore.js src/stores/studio/editorStore.js src/components/studio/develop/ProjectTree.jsx src/components/studio/develop/ExecutionDock.jsx src/components/studio/Editor.jsx src/components/studio/PreExecuteModal.jsx src/hooks/studio/useStudioExecution.js`
- `rm src/components/studio/develop/__tests__/p5-polish.test.ts docs/evidence/studio/P5-polish/execution.md`
- No backend files changed, so no backend rollback is needed. No migrations, no new dependencies in the repo (only `supabase` installed into the homebrew python3.11 interpreter for test verification).

## Next package

- **P6 Results** full (canonical summary, linked performance, trades/attribution) — unchanged from plan; P5 exit gate still open on server project open/create and persisted-run reproduction.
