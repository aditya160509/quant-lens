# P13 Composer Polish Execution — 2026-09-29

**Scope:** Phase 13 composer polish per `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md` §19
(lines ~979-1018). Resizable layouts verified plus saved views, linked selections,
report templates, image/PDF/Arrow exports, formula registry with required-field
policy. Main plan file NOT updated.

**Files changed:**
- `backend/app/services/studio/reports.py` — `FORMULAS` registry (15 metric paths),
  `TEMPLATE_REQUIRED_PATHS` + `TEMPLATE_DEFAULTS` for the 4 template identities,
  `template_block_list()`, `views` persisted on recipes, `save_view()`,
  render now carries `formulas`, `policy`, `warnings`, `export_version` (1.1),
  `engine_version`; CSV gained `formula`/`report_hash`/`export_version` columns;
  HTML gained print stylesheet, Warnings/Formula sections, version footer;
  new `export_arrow()` via existing `pyarrow` IPC stream (no new dependency).
- `backend/app/routers/studio.py` — `OutputRecipeRequest.views`,
  `RecipeViewRequest`, `GET /reports/templates`,
  `GET /reports/templates/{template_name}`, `POST /reports/recipes/{id}/views`,
  export route extended with `arrow` (`application/vnd.apache.arrow.stream`).
  Incidental repair (pre-existing breakage, not P13): restored missing
  `def _safe_numeric` line and restored deleted `PortfolioOptimizeRequest`
  class (verbatim body; two in-file references depended on it). Both were
  damaged by a concurrent edit of this untracked working-tree file; no API
  semantics changed.
- `frontend/src/stores/studio/composerSelectionStore.js` (new) — zustand
  pub/sub for linked selections (`selectedArtifact`, `selectedMetric`).
- `frontend/src/components/studio/ComposerView.jsx` — Link buttons per block
  with cross-block highlight (`data-linked`), clickable metric paths with
  cross-block highlight, saved views (name/save/apply, persisted via recipe
  views endpoint), Apply-template-layout from server defaults, per-block
  canvas sparkline with PNG download via `canvas.toDataURL`, Print/Save-as-PDF
  button with print stylesheet, formula/warning/version display, `arrow`
  export link. Existing labels, save payload shape, and html/csv/json links
  preserved.
- `backend/tests/test_studio_reports.py` — 5 new tests (templates, policy/
  formulas/warnings/versions, saved views, Arrow determinism, HTML print/CSS).
- `frontend/src/components/studio/__tests__/ComposerView.test.tsx` — 2 new
  tests (linked artifact selection, template apply without invented metrics).

**Tests (all passing):**
- `PYTHONPATH=. /opt/homebrew/bin/python3.11 -m pytest -q
  tests/test_studio_reports.py tests/test_studio_paper.py
  tests/test_studio_portfolio.py tests/test_studio_jobs.py
  tests/test_studio_certification.py tests/test_studio_advanced_validation.py`
  — **41 passed** (reports suite alone: 10 passed).
- `npx eslint` on the 3 changed/new frontend files — clean (exit 0).
- `npx jest src/components/studio/__tests__/ComposerView.test.tsx` —
  **4 passed** (2 pre-existing + 2 new).
- Router smoke via TestClient: `GET /studio/reports/templates` 200 with all
  4 identities; `GET /studio/reports/templates/validation` 200 (2 blocks,
  required paths); unknown template 404 `REPORT_TEMPLATE_NOT_FOUND`.
- `npm run build` NOT executed per instructions. Full backend suite and full
  frontend suite NOT executed (scoped verification only).

**Limitations / truth boundary:**
- PDF is the browser Print dialog with Save-as-PDF over a print stylesheet;
  no server-side PDF renderer was added (no heavy deps, per scope).
- Image export covers per-block metric sparklines via `canvas.toDataURL`;
  there is no chart-library image pipeline (none exists in the composer).
- Arrow export is a minimal IPC stream of the same rows as CSV, using the
  already-declared `pyarrow>=14.0.0` dependency; no new package added.
- Template required paths are enforced as warnings (`policy.missing_required_paths`
  + report `warnings`), never inferred or backfilled; `custom` has no required paths.
- Formulas are documentation strings for the canonical calculators, not recomputation.

**Rollback:**
- `git checkout` does not apply (files untracked). To revert P13 polish only:
  restore `backend/app/services/studio/reports.py`,
  `backend/app/routers/studio.py`,
  `frontend/src/components/studio/ComposerView.jsx`,
  `backend/tests/test_studio_reports.py`,
  `frontend/src/components/studio/__tests__/ComposerView.test.tsx` from backup,
  and delete `frontend/src/stores/studio/composerSelectionStore.js` plus
  `docs/evidence/studio/P13-polish/`. Re-apply the two incidental `studio.py`
  repairs only if the concurrent editor has not already fixed them.

**Next:**
- Consider a `views` schema test at the router level once the concurrent
  `studio.py` refactor settles.
- If a server-side PDF or full-chart PNG pipeline is later required, add it
  as its own phase with an explicit dependency decision.
