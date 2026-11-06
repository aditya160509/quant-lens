# Delete map

Date: 2026-11-06. Nothing here has been deleted. Frontend counts come from a static import trace from the kept routes; dynamic backend imports are not covered, so each batch needs the checks below.

## Keep

- Pages: `/` home, `/trade` chart, `/ml`, `/research`, `/studio`, auth, pricing, profile, payment, documentation, security, workspace.
- Frontend: `modules/`, `charts/`, `workspace/`, and everything those pages import (`chart_engine`, `studio`, `trading`, `sovereign`, `landing`, `watchlist`, `ui`).
- Backend: all `*_v2` services (Research, ML, Screener, PCA, Factors, Volatility, Portfolio). The rebuilds use them.
- Data: `backend/data/prices`, `fundamentals`, `canonical`, `market_universe.parquet`, `ml_v2`, `research_v2`, factors data.
- `research_exports/`: the paper package. Not product code, gitignored, never delete as cleanup.

## Batch A: old v1 pages (delete now)

| Delete | Replaced by |
|---|---|
| `/labs/factors/*` (11 pages) | `factors-v2` |
| `/labs/volatility/*` (13 pages) | `volatility-v2` |
| `/labs/ml/*` (14 pages) | `/ml` |
| `/labs/regimes/*` (7 pages) | ML Market state; check nothing unique is lost |
| `/labs/macro`, `/labs/mission-control`, `/macro`, `/markets`, `/market-labs` | none: owner decision |
| `/portfolio/*` (old pages) | `portfolio-v2` |
| `components/labs`, `components/portfolio`, `components/ml_v2` | as above |

Then remove the backend routes only these pages called (`labs`, `cluster_b`, `ml_api`, `pca_eigenphysics`, `screener_api`, `market_labs`, `macro`, and their services), one router at a time. `/api/labs` and `/api/portfolio` are still referenced by kept code, so those need a caller check first.

## Batch B: `docs/CLEANUP_PLAN.md` batches 1 to 3

Stale test artifacts, logs and unimported files. Recheck each, because the plan is a month old.

## Batch C: v2 feature pages (delete only when each rebuild ships)

`/labs/screener-v2`, `factors-v2`, `pca-v2`, `volatility-v2`, `portfolio-v2` and their `components/*-v2`. These are the only UI for those modules today.

## Full trace result

With Batch A and C both gone: 196 of 482 frontend files, about 51,500 lines, 2.5 MB.

## Checks per batch

`rg` and graph check, `backend/venv/bin/python -c "import main"`, `pytest`, `npm run build`, open the kept pages, then one commit per batch.
