# P1-W1 readiness

- Status: `READY`
- Date: 2026-09-12
- Implementation owner: Codex
- Required reviewers: quantitative reviewer, security reviewer, frontend reviewer

## Current behavior and truth authority

The mounted frontend calls `/api/studio/data`, `/api/studio/execute`, `/api/studio/monte-carlo`, and `/api/studio/walk-forward` from `StudioStore.js`. `backend/app/routers/studio.py` is the mounted authority. It currently generates synthetic OHLCV when data is absent, substitutes momentum for invalid code, assigns random MAE/MFE, coerces non-finite values to zero, and executes submitted code inside the API process. The frontend replaces failed walk-forward requests with randomized or hard-coded evidence. `QuantKernel.js` is a display-side Dynamics/Spectral calculator, not the execution endpoint, but contains proxy and zero-substitution behavior and is not approved as an analytical authority.

## Impact inventory

- Routes: `/api/studio/data`, `/api/studio/execute`, `/api/studio/monte-carlo`, `/api/studio/walk-forward`
- Backend symbols: `StrategyExecutor`, `execute_strategy`, `_sanitize_for_json`, `MonteCarloEngine`, `WalkForwardEngine`
- Frontend symbols: `StudioProvider.executeStrategy`, `runMonteCarlo`, `runWalkForward`, `ValidateView`
- Graph: `execute_strategy` directly calls `StrategyExecutor.get_price_data` and `execute_custom_code`; `runExecRequest` is the frontend caller of `/api/studio/execute`.
- Dynamic references: endpoint paths occur directly in `StudioStore.js`; no dynamic import controls these calls.

## Preserved behavior and non-goals

Preserve real parquet-backed execution, user-supplied strategy semantics, candles, signals, deterministic trades, equity, existing route paths, and current frontend layout. Do not add fake replacements when evidence is unavailable. P1-W3 execution isolation is not claimed here. Dynamics/Spectral removal belongs to P3 after route/import verification.

## Proposed files and dependencies

- Change `backend/app/routers/studio.py`.
- Add `backend/app/services/studio/schemas.py` and `metrics.py` plus package initializer.
- Extend the closest Studio backend tests.
- Change `frontend/src/components/studio/StudioStore.js` and `ValidateView.jsx` with focused tests.
- No new dependency.

## Migration, compatibility, feature flag, and rollback

No database or artifact migration. Existing response fields remain where truthful, with additive contract metadata. Fabricated values become `null` or typed errors. Rollback is file-level revert. No feature flag is appropriate for removing fabricated evidence. Compatibility window: one release for legacy field names; new metadata is additive.

## Fixtures, tolerances, performance, and evidence

Use deterministic equity/trade/benchmark fixtures. Scalar tolerance is `1e-10`. Endpoint tests cover missing data, invalid code, non-finite serialization, unavailable metrics, and deterministic output. Frontend tests prove failed validation does not create evidence. Ordinary endpoint work must remain below the existing 500 ms budget excluding parquet load and execution.

## Risks and boundary

Rejecting missing data and invalid code exposes errors previously hidden by fake success. That is intentional. In-process `exec` remains a critical P1-W3 blocker until an approved isolated provider exists; this slice must not relabel it safe.
