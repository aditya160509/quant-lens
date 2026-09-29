# P2-W1 and API boundary partial execution

Date: 2026-09-12

This package establishes contract version `1.0`, shared metric, warning, data-quality, provenance, result-metadata, and error-envelope models. Current original-Studio POST requests declare the contract version and incompatible values are rejected during request validation.

The mounted original workspace now routes all active Studio data, execution, Monte Carlo, and walk-forward requests through `frontend/src/lib/studioApi.js`. The client adds request IDs, a 30-second timeout, caller cancellation, versioned bodies, normalized typed errors, one safe GET retry for retryable failures, and opt-in response validation. Contract declarations under `frontend/src/types/studio/contracts.d.ts` mirror the shared metadata, metric, artifact, run, result, and error shapes.

This is intentionally not marked as complete P2-W1 or P2-W2. Full project, dataset, run, validation, factors, portfolio, replay, export, paper-run, and artifact-manifest schemas remain, as does consolidation of the separate V2 hooks.
