# P1-W2 readiness

- Status: `READY`
- Date: 2026-09-12
- Implementation owner: Codex
- Required reviewers: quantitative reviewer and backend reviewer

## Current behavior and authority

`StrategyExecutor._compute_metrics` currently mixes calculation and presentation, hard-codes the risk-free rate and average holding period, rounds before transport, returns percentage strings, emits `Inf`, and substitutes zero for unavailable statistics. No canonical Studio metric module exists.

## Impact inventory

- Current owner: `backend/app/routers/studio.py::StrategyExecutor._compute_metrics`
- Target owner: `backend/app/services/studio/metrics.py`
- Consumers: `/api/studio/execute`, `StudioStore.processData`, `TearsheetView.jsx`
- Schemas: additive metric value, methodology, provenance, and warning contracts in `backend/app/services/studio/schemas.py`

## Preserved behavior and non-goals

Preserve the existing equity/trade inputs and legacy response aliases needed by the current UI. Calculations use decimal returns internally and do not redesign Results UI. Cross-engine reconciliation beyond the mounted route is recorded for later work rather than asserted without fixtures.

## Proposed files and dependencies

Add the canonical metric and schema modules, extend backend tests, and delegate the router calculator to them. Use NumPy and Pydantic already present. No dependency is added.

## Migration, compatibility, feature flag, and rollback

No persistent migration. The API adds canonical numeric metric records while retaining truthful legacy aliases for one compatibility release. Rollback is a file revert. No feature flag.

## Fixtures, tolerances, performance, and evidence

Fixtures cover constant gain/loss, mixed returns, benchmark-relative statistics, trades with and without excursions, and insufficient samples. Deterministic scalar tolerance is `1e-10`. Metric calculation should remain linear in observations.

## Risks and boundary

Frequency, timezone, currency, benchmark compatibility, exposure, turnover, and cost drag require explicit inputs. The calculator returns unavailable metadata when inputs are absent and must not infer them. Full reconciliation with portfolio and factor engines remains open until their conventions are inventoried.
