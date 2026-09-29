# P3-W1 rewrite-boundary audit

Date: 2026-09-12

## Outcome

The audited original Studio surface contains 10,673 lines across the nineteen named shell, state, chart, and support modules. This is a rewrite boundary, not a cleanup package.

## Decisions

- Retain `constants.js` only as starter-strategy fixtures. Persisted strategy identity must move to project/version contracts.
- Retain Monaco integration in `Editor.jsx`; move editor state and execution commands out of the monolithic store.
- Retain drawing interactions and indicator definitions, but move them behind owned chart contracts.
- Rewrite `CustomOverlayBuilder.jsx` persistence because it currently writes directly to local storage.
- Retain `GridChartCell.jsx` as a temporary composition seam.
- Rewrite `EventLogPanel.jsx`, `ValidateView.jsx`, and `ReplayView.jsx` against artifact and job contracts.
- Retain the visual structure of `StrategyLibrary.jsx`, but replace fixture ownership with project/version data.
- Split `DevelopView.jsx` (713 lines), `Q360Canvas.jsx` (1,069 lines), `QuantKernel.js` (1,340 lines), `StudioStore.js` (626 lines), and `StudioLayout.jsx` (275 lines).
- Replace `QuantKernel.js` analytical authority with tested backend or bounded-worker results. Do not preserve its zero/proxy substitutions.
- `DynamicsView.jsx` (3,326 lines), `SpectralAnalysis.jsx` (445 lines), and `QuantKernel.js` (1,340 lines) were removed after confirming that the canonical mode contract could not reach Dynamics, Spectral had no consumer, and QuantKernel was used only by Dynamics. Their store state, fetch action, tab constant, layout import, and render branch were removed in the same change.
- Keep `TechReferenceHub.jsx` temporarily because it is reachable from the activity rail; its static material should later become contextual help.
- Introduce `DataPreflightGate.jsx` as the canonical import while retaining the legacy preflight implementation during the split.

## Direct-call audit

The benchmark Studio data request in `DevelopView.jsx` was moved to the shared Studio client. The remaining direct request in that component loads the sovereign ticker catalog, which is outside the current Studio endpoint adapter and remains explicitly recorded for migration.
