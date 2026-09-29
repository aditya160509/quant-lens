# P3-W1 boundary execution

Date: 2026-09-19

## Removed authority

The obsolete Dynamics frontend, standalone Spectral component, and client-side QuantKernel were removed together. This eliminated 5,111 source lines plus their store state, direct dynamics request, layout branch, and tab definition. No compatibility export was retained because no canonical route or remaining component imports the files.

The unused 390-line `LayoutManager.jsx` implementation was also removed after graph and literal-import checks confirmed that the live shell uses `LayoutPickerModal.jsx` and `LayoutInitModal.jsx` instead.

All active workspace panes now render inside `StudioPaneBoundary`. A failed pane preserves the surrounding workspace, exposes a visible alert and retry action, and resets automatically when the user changes modes.

`DataPreflightGate` now receives observed data-quality metadata from both data-load and execution responses. It shows the selected symbol, observed row count, and quality status, and prevents execution when observed data is unavailable.

The equity comparison canvas no longer owns an alternate Sharpe formula. It consumes the canonical backend Sharpe, return, and drawdown values. Its benchmark comparison is now labeled total excess return instead of alpha. Monte Carlo uses compounded simple returns consistently with the canonical return convention and the UI describes the parametric method accurately.

The backend `/studio/dynamics` compatibility endpoint remains temporarily available but has no mounted Studio client. Removing that API is deferred until external-consumer compatibility is checked.

## Verification

- Literal import/reference scan after deletion: no remaining DynamicsView, SpectralAnalysis, QuantKernel, fetchDynamics, dynamicsData, or showSpectralAnalysis references.
- Focused ESLint: passed.
- Focused frontend tests: 19 passed, including pane failure isolation and retry.
- Production Next.js build: passed and generated `/studio` plus existing Studio child routes.

## Recovery

Restore the three deleted components and the associated `StudioLayout`, `StudioStore`, and `constants.js` references from the pre-P3 workspace state. No data or schema migration is involved.
