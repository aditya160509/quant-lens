# P16 V2 Capability Migration Map (W1 evidence, no migration performed)

Date (UTC): 2026-09-29. Status: mapping only. This task performed zero migrations and zero deletions (see `evidence.md`). Owners below are proposed future homes, not completed moves.

## Capability -> proposed owner

| V2 capability (current home) | Live endpoint / hook | Proposed new owner | Notes |
|---|---|---|---|
| Data catalog (`backend/app/studio_v2/data_studio/catalog.py:DataCatalog`, router `data_catalog`) | `GET /api/v2/data-studio/catalog`, `useDataStudio.loadCatalog` | Canonical Data Studio owner (TBD, likely `backend/app/data/*` + `components/studio/Data*`) | Stays V2-owned for now; Data inspector depends on it |
| Freshness (`DataFreshnessMonitor`, router `data_freshness`) | `GET /api/v2/data-studio/freshness`, `useDataStudio.loadFreshness` | Same canonical Data owner | Stays V2-owned for now |
| Uploads (`CustomDataUploader`, router `upload/list/delete_custom_upload`) | `POST/GET/DELETE /api/v2/data-studio/uploads`, `useDataStudio.upload/deleteUpload` | Same canonical Data owner, with auth/quota preserved | Owner-scoped (`user.id`), size-bounded; stays V2-owned for now |
| Manifests (`shared/data_manifest.py`, router `data_manifests/refresh_data_manifest`) | `GET/POST /api/v2/data-studio/manifests*` | Same canonical Data owner | Stays V2-owned for now |
| Factors library + governance (`factors/library.py`, `factors/governance.py`, router `list/create/get/update/delete_factor_library`, `factor_approve/deprecate/restore/changelog/versions`) | `/api/v2/factors/library*`, `/api/v2/factors/evaluate`, `/api/v2/factors/ic-diagnostics`, `useFactors` | Canonical Factors owner (TBD) | Stays V2-owned for now |
| Optimizer (`optimizer/search.py|cpcv.py|cross_validation.py|ensemble.py|verdict.py`, router `optimizer_*`) | `/api/v2/optimizer/*` (bayesian-search, cpcv, walk-forward, trials, verdict, ensemble), `useOptimizer` | Canonical Optimizer owner (TBD) | Stays V2-owned for now |

## What stays V2-owned for now (explicit)

- All six `/studio/*` sub-routes and their panels (backtest, data, factors, optimizer, portfolio-risk, robustness).
- Backtest engines (`backtest/engine.py`, `portfolio_engine.py`, `attribution.py`, `slippage_audit.py`, `scenarios.py`, `lineage.py`), robustness jobs (`robustness/jobs.py`), portfolio-risk engines (`var_engine.py`, `concentration.py`, `limits.py`, `alert_feed.py`), journal (`services/journal_service.py`), algorithm-lab kernel/linter/worker.
- `AlgorithmLab.jsx` subtree + `StrategySelector.jsx` + `RegimePnLBreakdown.jsx`: marked OPEN in `evidence.md`; any future deletion needs graph + test + route triple-evidence plus a migration target for `useAlgorithmLab` contract tests.
- Secret-rejection gap (no secret scan on execute/upload paths): must be designed (detection + rejection UX + tests) before any migration that widens code/upload surface, not silently patched here.
