# P0 execution evidence

## Outcome

The canonical `/studio` route now mounts the original single-workspace Studio through `StudioProvider` and `StudioLayout`. Develop is the default. Direct links for currently implemented final modes map into the existing internal views, and unsupported or invalid modes normalize explicitly to `?mode=develop`. `/labs/studio` performs one framework redirect to `/studio`.

## Safety baseline

The root and nested frontend worktrees contained extensive pre-existing edits and untracked files before this package. The Studio route and test files were already untracked in the nested frontend and were inspected directly before editing. No unrelated change was reset, deleted, or reformatted. The original backend remains mounted from `backend/main.py` through `backend/app/routers/studio.py` at `/api/studio`; no backend file changed.

The pre-edit graph contained 15,257 nodes and 57,763 edges. It showed no inbound callers for `StudioLayout` and exactly two route callers for `AlgorithmLab`: `/studio` and `/labs/studio`. After the route change, a fast graph refresh completed with 15,281 nodes and 57,818 edges.

## Changed files

- `frontend/src/app/studio/page.js`
- `frontend/src/app/labs/studio/page.js`
- `frontend/src/app/studio/__tests__/routes.test.tsx`
- `frontend/src/components/studio/OriginalStudioPage.jsx`
- `frontend/src/components/studio/__tests__/OriginalStudioPage.test.tsx`
- `frontend/e2e/studio-routes.spec.ts`
- `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`
- `docs/evidence/studio/P0/readiness.md`
- `docs/evidence/studio/P0/execution.md`

## Tests and results

Baseline before editing:

```text
cd frontend && npm test -- --runInBand src/app/studio/__tests__/routes.test.tsx
PASS: 1 suite, 7 tests
```

Verification after editing:

```text
cd frontend && npm test -- --runInBand src/app/studio/__tests__/routes.test.tsx src/components/studio/__tests__/OriginalStudioPage.test.tsx
PASS: 2 suites, 12 tests

cd frontend && npx eslint src/app/studio/page.js src/app/labs/studio/page.js src/app/studio/__tests__/routes.test.tsx src/components/studio/OriginalStudioPage.jsx src/components/studio/__tests__/OriginalStudioPage.test.tsx e2e/studio-routes.spec.ts
PASS: exit 0

cd frontend && npm run build
PASS: Next.js 16.0.5 production build; 185 static pages generated, including /studio and /labs/studio

PYTHONPATH=backend python3 -m pytest backend/tests/test_studio_v2_health.py backend/tests/test_studio_v2_contract.py -q
PASS: 25 tests; 12 dependency deprecation warnings
```

The configured Playwright smoke command did not execute because the repository's managed Chromium binary is absent. No browser download or dependency mutation was performed. The same runtime acceptance was exercised in installed Chrome with the existing frontend and backend processes:

- `/studio` visibly rendered the original Develop workspace and enabled `EXECUTE STRATEGY`.
- `/studio?mode=results` retained its URL and rendered the Results surface.
- `/labs/studio` landed at `/studio` once and rendered Develop.
- Chrome reported no console warnings or errors across those checks when the backend was running.

## Performance and migrations

No data, schema, or artifact migration exists. The route remains statically generated. The `/studio` client-reference manifest names 13 JavaScript chunks totaling 935,224 uncompressed bytes, including shared framework/application chunks. The complete `.next/static/chunks` directory is 24 MB and is not a route-specific measure.

Five local requests against `next start` returned a 38,889-byte `/studio` document. Time-to-first-byte was 12.315 ms on the first request and 1.362 to 1.999 ms on four warm requests. These local transport numbers exclude browser hydration, data loading, and interaction readiness, so P15 must replace them with the representative-hardware budgets defined by the plan.

## P0 reuse, rewrite, and remove matrix

| Surface | Decision | Product value and correctness | Maintainability, accessibility, and performance evidence |
|---|---|---|---|
| `StudioProvider` and `StudioLayout` | Reuse for route recovery, then rewrite/split in P3 | They restore the required shared workspace and Develop flow. Their current state and legacy mode names are not final authorities. | The store is 670 lines and the layout is 275 lines; broad context subscriptions and limited semantic mode navigation require later replacement and interaction tests. |
| `DevelopView`, Monaco editor, and chart workflow | Reuse capability, audit implementation in P1/P3/P5 | The editor, execute action, controls, and linked chart are the highest-value original workflow. Current execution and fallback truth are explicitly uncertified. | `DevelopView` is 701 lines. Monaco is retained; surrounding tools and state boundaries require focused rewrites. Live Chrome exposed an accessible Execute button but does not establish full keyboard coverage. |
| `Q360Canvas` and `QuantKernel` | Rewrite behind owned contracts | The financial canvas interactions are valuable; frontend analytical authority and any synthetic fallback are not acceptable final boundaries. | The files total 2,409 lines and lack the owned kernel contract and measured large-data path required by P4. |
| `TearsheetView`, `ValidateView`, `StressView`, and `ReplayView` | Reuse as observable migration surfaces, then rewrite/merge by owning phase | They preserve Results, validation, stress, and replay workflows while later packages replace unsupported or fabricated evidence. | Current files total 894 lines. Their accessibility, numerical truth, and large-result behavior remain phase-specific gates. |
| Studio V2 `AlgorithmLab` shell | Remove from canonical route now; retain code and child routes until P16 | A second shell contradicts the product decision. Its engines and domain features may still be valuable. | Graph tracing found only the two shell route callers changed in P0. No V2 component or backend engine was deleted. |
| `DynamicsView` and `SpectralAnalysis` | Preserve in P0, remove after P3 dependency and parity checks | Their product surfaces are explicitly rejected, but P0 is not authorized to delete them. | They total 3,771 lines. Removal requires graph, import, endpoint, and runtime evidence under P3/P16. |

This matrix is a P0 boundary decision, not a later-phase parity or deletion approval.

## Limitations

This route switch makes later truth and safety work observable. It does not resolve the known synthetic fallback, unrestricted execution, legacy mode naming, or oversized-store debt. Only Develop, Results, Validate, and Replay have current original-workspace mappings. Portfolio, Factors, and unknown mode values normalize to Develop rather than presenting a nonfunctional placeholder.

## Rollback

Revert the two route modules, `OriginalStudioPage.jsx`, the focused test changes, and these P0 evidence/checklist edits. No database, backend, or artifact rollback is needed.

## Next safe package

Complete the P0-W1 bundle/performance baseline and reuse/rewrite/remove matrix, then begin P1-W1 with its own current `READY` discovery artifact.
