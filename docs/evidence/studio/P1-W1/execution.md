# P1-W1 truth audit execution

Date: 2026-09-12

## Outcome

The mounted Studio execution and validation path no longer substitutes synthetic OHLCV data, a default momentum strategy, random walk-forward folds, hard-coded fallback validation summaries, random trade excursions, or plausible-looking tearsheet defaults. Missing data and invalid strategies now fail explicitly. Results from data and strategy execution include observed data-quality and provenance metadata.

`QuantKernel.js` was audited but not rewritten in this package. It remains a client-side analytical boundary with many zero and proxy substitutions. The migration plan already assigns replacement-by-authority to the later workspace rewrite, so those features are not certified by the Phase 1 gate.

## Verification

- `PYTHONPATH=backend /opt/homebrew/bin/pytest backend/tests/test_studio_metrics.py -q`: 7 passed.
- `npx eslint src/components/studio/StudioStore.js src/components/studio/ValidateView.jsx src/components/studio/TearsheetView.jsx --quiet`: passed.
- `npm test -- --runInBand src/components/studio/__tests__/OriginalStudioPage.test.tsx src/app/studio/__tests__/routes.test.tsx`: 12 passed.
- `npm run build`: passed; `/studio` and its child routes were generated.

The repository-wide frontend lint command currently scans generated Playwright report assets under `frontend/output` and reports third-party minified hook errors. No lint configuration was changed in this package.

## Remaining gates

- Safe strategy execution is not complete. User code still reaches in-process `exec`, and the existing V2 worker also lacks the required container or microVM boundary.
- QuantKernel analytical authority remains to be replaced, not preserved.
- Cross-engine metric reconciliation and contract-frequency, timezone, currency, and benchmark compatibility checks remain open.
