# P0 readiness

- Status: `READY`
- Date: 2026-09-12
- Implementation owner: Codex
- Required reviewers: frontend reviewer and product approver for the P0 exit gate; no quantitative, security, or operations behavior changes in this package

## Current behavior and source of truth

`frontend/src/app/studio/page.js` and `frontend/src/app/labs/studio/page.js` both mount `frontend/src/components/studio-v2/AlgorithmLab.jsx`. The dormant original workspace is composed by `StudioProvider` in `frontend/src/components/studio/StudioStore.js` and `StudioLayout` in `frontend/src/components/studio/StudioLayout.jsx`. The store owns the current internal mode and defaults it to `develop`.

The mounted backend Studio API remains `backend/app/routers/studio.py`, registered by `backend/main.py` at `/api/studio`. P0 does not alter it or any authoritative data store.

## Affected files, symbols, routes, stores, schemas, and imports

- Routes: `/studio`, `/labs/studio`
- Existing symbols: `StudioPage`, `LegacyStudioRoute`, `StudioProvider`, `StudioLayout`
- New symbol: `OriginalStudioPage`
- Store: `StudioContext.activeTab` remains the current UI-mode authority
- Schemas and data stores: none
- Expected changes:
  - `frontend/src/app/studio/page.js`
  - `frontend/src/app/labs/studio/page.js`
  - `frontend/src/components/studio/OriginalStudioPage.jsx`
  - `frontend/src/components/studio/__tests__/OriginalStudioPage.test.tsx`
  - `frontend/src/app/studio/__tests__/routes.test.tsx`
  - `frontend/e2e/studio-routes.spec.ts`
  - `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`
  - `docs/evidence/studio/P0/readiness.md`
  - `docs/evidence/studio/P0/execution.md`

## Code-graph and dynamic-reference impact

The graph reports no inbound callers for `StudioLayout`. `AlgorithmLab` has exactly two route callers, `StudioPage` and `LegacyStudioRoute`. Repository string search found no other original-Studio route composition and no dynamic import of `StudioLayout` or `StudioProvider`. Backend registration is unaffected. Route children under `/studio/*` remain untouched.

## Preserved behavior and non-goals

The original editor, canvas, playback, comparison, layouts, costs, validation, stress, results, and replay implementations are preserved unchanged. Studio V2 components, page routes, hooks, engines, APIs, and data are not deleted. This package does not claim truth hardening, safe execution, six-mode completion, shell redesign, or Dynamics/Spectral removal.

## Proposed dependencies and implementation

No dependency is added. A client entry composes the existing provider and layout. It reads the canonical `mode` query parameter, maps currently implemented final modes to legacy internal identifiers, and defaults unsupported or invalid values to Develop. `/labs/studio` uses the framework redirect API.

## Migration, compatibility, feature flag, and rollback

There is no database migration or backfill. Existing `/studio/*` V2 routes remain compatible. No feature flag is required because P0 makes the approved canonical route switch. Rollback command: revert only the P0 route, entry, and route-test changes; no data rollback is needed. The V2 comparison shell is not retained at `/studio-v2` because no comparison need was identified.

## Fixtures, thresholds, tests, and evidence

- Baseline focused Jest route suite: 7/7 passing before edits.
- Focused Jest route and entry tests must prove original composition, Develop default, query-mode mapping, invalid-mode normalization, and the legacy redirect.
- The frontend production build must pass.
- Studio Playwright smoke must load `/studio`, direct mode URLs, and the redirect without console errors when the local runtime is available.
- Focused backend Studio tests must remain passing.
- No numerical tolerance applies. No performance regression is expected from route-only composition; build output supplies route-size evidence if available.

## Risks and unresolved decisions

The original workspace is known to contain later-phase truth and safety debt. P0 exposes it so that migration is observable but does not certify its analytical output. Portfolio and Factors do not yet have original-workspace implementations, so their query modes normalize to Develop rather than displaying fabricated placeholders. The package boundary ends after route recovery and verification; P1-W1 is the next safe package.
