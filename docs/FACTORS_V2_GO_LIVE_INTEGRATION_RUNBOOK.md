# Factors V2 Go-Live Integration Runbook

Last updated: 2026-05-10

This document is the future checklist for making the new Factors V2 module live in place of the current Labs Factors experience. It records what exists today, what must be wired, what must be replaced, how to validate it, and how to roll back safely.

## Current State

Factors V2 is implemented but intentionally dormant.

Backend compute exists under:

- `backend/app/services/factors_v2/core/`
- `backend/app/services/factors_v2/features/feature_01.py` through `feature_14.py`
- Named feature modules beside the numbered wrappers, such as `factor_valuation_spread_monitor.py`, `factor_exposure_decomposition.py`, and `allocator_transparency_report_generator.py`
- `backend/app/services/factors_v2/core/contracts.py` for feature metadata, standard output schema, module registry, and output contracts

Dormant backend API exists at:

- `backend/app/api/factors_v2.py`

Frontend API calls already exist in:

- `frontend/src/lib/api.js`

Frontend pages already exist at:

- `frontend/src/app/labs/factors-v2/page.js`
- `frontend/src/app/labs/factors-v2/layout.js`
- `frontend/src/app/labs/factors-v2/feature-01/page.js` through `feature-14/page.js`
- `frontend/src/components/factors-v2/customPagePrimitives.jsx`
- `frontend/src/components/factors-v2/registry.js`

The current legacy Factors pages remain under:

- `frontend/src/app/labs/factors/`

The current backend Labs Factors router remains mounted through:

- `backend/main.py`
- `backend/app/api/labs.py`

## Target End State

The target state is:

- `/labs/factors` becomes the public Factors Intelligence entry point, backed by the new Factors V2 UI and API.
- `/labs/factors-v2` may remain as an alias during transition or be redirected to `/labs/factors`.
- `backend/app/api/factors_v2.py` is mounted in `backend/main.py`.
- `frontend/src/lib/api.js` Factors V2 functions call live FastAPI routes through the existing `/api` proxy.
- Existing legacy Factors pages are either archived, redirected, or kept under a legacy route.
- All 14 feature routes run live against the Factors V2 backend.
- No feature returns placeholder schema or silent fake data.
- `FACTORS_V2_IMPLEMENTATION_STATUS.md` remains the audit record.

## Backend Integration

### 1. Mount The Dormant Router

In `backend/main.py`, add the import near the other API imports:

```python
from app.api import factors_v2
```

Then include the router near the Labs routers:

```python
app.include_router(factors_v2.router, prefix="/api", tags=["factors-v2"])
```

The router itself already has:

```python
router = APIRouter(prefix="/labs/factors/v2", tags=["factors-v2"])
```

With the `/api` prefix in `main.py`, the live route shape becomes:

- `GET /api/labs/factors/v2/features`
- `POST /api/labs/factors/v2/feature/{feature_id}/run`
- `POST /api/labs/factors/v2/run-all`
- `POST /api/labs/factors/v2/export/{feature_id}`
- `POST /api/labs/factors/v2/alert-subscription`

### 2. Verify Backend Router Imports

Run:

```bash
python3 -m compileall backend/app/services/factors_v2 backend/app/api/factors_v2.py backend/main.py
```

Then start backend and hit:

```bash
curl http://localhost:8000/api/labs/factors/v2/features
```

Expected:

- HTTP 200
- `status: "ok"`
- 14 feature contracts
- `schema` with the standard keys: `feature_id`, `status`, `summary_cards`, `charts`, `tables`, `alerts`, `meta`

### 3. Keep The Standard Response Contract

Every feature response must keep:

```json
{
  "feature_id": "feature_XX",
  "status": "success | warning | partial | error",
  "summary_cards": [],
  "charts": {},
  "tables": {},
  "alerts": [],
  "meta": {}
}
```

Frontend renderers depend on this shape. Do not rename these top-level keys.

### 4. Preserve Realtime Vs Research Mode

Payloads may include:

```json
{
  "compute_mode": "realtime"
}
```

or:

```json
{
  "compute_mode": "research"
}
```

Realtime constraints documented in the implementation status and feature docs must remain enforced:

- F02: realtime characteristic z-scores only for portfolio constituents; large universe uses cached/precomputed snapshots.
- F03: monthly default for long history; daily only for trailing 12 months unless Research Mode.
- F04: HMM primary in realtime; GMM covariance clustering cached/toggle/Research Mode.
- F05: full-universe decay default; sector drilldown on demand.
- F07: weekly refit default, Monte Carlo capped, trade-level costs.
- F08: Ledoit-Wolf default for factor sets above 15; DCC gated.
- F09: 20 AUM points default; 50 only in Research Mode.
- F10: no live integer cardinality; greedy post-processing; full robust mode gated.
- F11: 5-lag realtime VAR and 200 bootstrap reps; larger runs gated.
- F13: CUSUM daily; Chow diagnostic cached/weekly.
- F14: PDF capped at 20 pages realtime; longer reports async/Research Mode.

## Frontend API Integration

The required functions already exist in `frontend/src/lib/api.js`:

```js
fetchFactorsV2Features()
runFactorsV2Feature(featureId, payload)
runFactorsV2All(payload, featurePayloads)
```

They currently call:

```js
GET  ${API_BASE_URL}/labs/factors/v2/features
POST ${API_BASE_URL}/labs/factors/v2/feature/${normalized}/run
POST ${API_BASE_URL}/labs/factors/v2/run-all
```

`API_BASE_URL` is:

```js
process.env.NEXT_PUBLIC_API_URL || "/api"
```

The Next proxy in `frontend/next.config.mjs` already maps:

```js
source: "/api/:path*",
destination: "http://localhost:8000/api/:path*"
```

So no frontend API URL change is required when backend is mounted.

## Frontend Route Replacement Plan

### Option A: Keep V2 Route And Add Navigation

Use this for staged rollout.

Steps:

1. Keep `/labs/factors-v2` as-is.
2. Add a Labs navigation tile/link from the main Labs page to `/labs/factors-v2`.
3. Keep legacy `/labs/factors` untouched for one release.
4. Compare user flows and backend logs.
5. After validation, promote V2 to `/labs/factors`.

### Option B: Replace Current Factors Route

Use this when ready to make V2 the primary module.

Steps:

1. Move or copy the V2 page files from:

```text
frontend/src/app/labs/factors-v2/
```

to:

```text
frontend/src/app/labs/factors/
```

2. Preserve the old route by moving legacy files to:

```text
frontend/src/app/labs/factors-legacy/
```

or keep only a redirect page:

```js
import { redirect } from "next/navigation";

export default function LegacyFactorsRedirect() {
  redirect("/labs/factors");
}
```

3. Update all internal links that point to `/labs/factors-v2/feature-XX` so they point to `/labs/factors/feature-XX`.

Files to check:

- `frontend/src/app/labs/factors-v2/page.js`
- `frontend/src/app/labs/factors-v2/layout.js`
- `frontend/src/components/factors-v2/registry.js`
- Any Labs index page that lists feature tiles
- Any command palette or global navigation registry

4. Keep `frontend/src/components/factors-v2/` as the component namespace. There is no need to rename the component folder unless we want cosmetic consistency later.

### Recommended Path

Use Option A for the first live backend test. Use Option B only after all 14 live feature calls pass production-build and smoke checks.

## Navigation Integration

When we decide to expose the module, update the visible app navigation in the smallest number of places.

Likely files:

- `frontend/src/app/labs/page.js`
- `frontend/src/components/GlobalLayout.jsx`
- `frontend/src/components/ui/navbar.jsx`
- Any command palette registry if present

Add or update the Factors link to:

```text
/labs/factors-v2
```

for staged rollout, or:

```text
/labs/factors
```

for final replacement.

Do not add duplicate links for legacy and V2 in the final production navigation. During staged rollout, label the new one clearly as `Factors V2` or `Factor Intelligence`.

## Feature Page Live Flow

Each feature page currently follows this flow:

1. Load feature metadata from `frontend/src/components/factors-v2/registry.js`.
2. Render configuration form from the feature field contract.
3. Render output configurator from the page-level `sections` array.
4. On Run, call:

```js
runFactorsV2Feature(feature.id, payload)
```

5. Payload includes:

```js
{
  ...formValues,
  selected_outputs: selectedOutputIds
}
```

6. Backend returns standard schema.
7. `customPagePrimitives.jsx` renders selected sections in order.

Important: the frontend renderer uses each section's `source`, `dataKey`, `fallbackKeys`, `chartType`, and `config`. Backend output keys must stay aligned with those page-level section definitions.

## Data And Dependency Checklist

Before go-live, verify local data paths:

- `backend/data/market_universe.parquet`
- `backend/data/fundamentals/master_fundamentals.parquet`
- `backend/data/factors_us/ff3_daily.csv`
- `backend/data/factors_us/ff5_daily.csv`
- `backend/data/factors_us/momentum_daily.csv`
- `factors/data/processed/aqr_csv/*.csv`
- `factors/data/processed/category7_macro_regime.parquet`
- `backend/data/prices/*`

Verify Python dependencies:

- `pandas`
- `numpy`
- `scipy`
- `sklearn`
- `numba`
- `polars`
- `pyarrow`
- `cvxpy`
- `reportlab`
- `hmmlearn`
- `jax` and `jaxlib` if enabled in the current requirements

Verify frontend dependencies:

- `recharts`
- `lucide-react`
- `framer-motion` if used elsewhere
- `nextjs-toploader`

## Test Plan Before Activation

### Backend Compile

```bash
python3 -m compileall backend/app/services/factors_v2 backend/app/api/factors_v2.py backend/main.py
```

### Backend API Smoke

After mounting router and starting backend:

```bash
curl http://localhost:8000/api/labs/factors/v2/features
curl -X POST http://localhost:8000/api/labs/factors/v2/feature/01/run \
  -H "Content-Type: application/json" \
  -d '{"compute_mode":"realtime","factor":"value_pb","max_tickers":80}'
```

Expected:

- HTTP 200
- JSON serializes cleanly
- No placeholder status
- Standard schema keys exist

### All-Feature Smoke

Run all 14 feature modules directly or via `/run-all` using realtime-safe payloads.

Acceptance:

- Every feature returns valid JSON.
- Every feature has `feature_id`, `status`, `summary_cards`, `charts`, `tables`, `alerts`, `meta`.
- F10 optimizer returns bounded weights.
- F14 report returns PDF-capable metadata and respects the 20-page realtime cap.

### Frontend Build

```bash
cd frontend
npm run build
```

Expected:

- Build passes.
- `/labs/factors-v2`
- `/labs/factors-v2/feature-01` through `/feature-14`

Known non-blocking warnings from current repo:

- stale `baseline-browser-mapping`
- invalid `swcMinify` in `next.config.mjs`
- multiple lockfiles/root inference

### Browser Smoke

Start backend and frontend, then verify:

1. `/labs/factors-v2` home page loads.
2. Bottom Factors strip is visible.
3. `feature-01` through `feature-14` pages load.
4. Run button returns live backend output.
5. Output cards appear one after another.
6. Output nav active state updates while scrolling.
7. Output configurator filters outputs.
8. Annotation pins work and persist locally.
9. Copy TSV, collapse, fullscreen, and info tooltip work.
10. No text overlaps on desktop or tablet widths.

## Cutover Steps

When ready to go live:

1. Create a branch.
2. Mount `factors_v2.router` in `backend/main.py`.
3. Run backend compile.
4. Start backend and validate `/api/labs/factors/v2/features`.
5. Start frontend and run one live feature from `/labs/factors-v2/feature-01`.
6. Run smoke for all 14 features.
7. Decide staged route or final replacement:
   - staged: add navigation to `/labs/factors-v2`
   - final: move V2 route into `/labs/factors` and archive legacy route
8. Run `npm run build`.
9. Update `FACTORS_V2_IMPLEMENTATION_STATUS.md` with activation date, test results, and any partials.
10. Deploy.

## Rollback Plan

Backend rollback:

- Remove or comment the `from app.api import factors_v2` import.
- Remove or comment:

```python
app.include_router(factors_v2.router, prefix="/api", tags=["factors-v2"])
```

Frontend rollback:

- If staged, remove the visible navigation link to `/labs/factors-v2`.
- If final replacement was done, restore legacy `/labs/factors` from the archived route or git.
- Keep `frontend/src/components/factors-v2/` in place; it is isolated and does not affect legacy routes unless imported.

Data rollback:

- No database migration is required for the current local-annotation implementation.
- If future backend annotation persistence is added, keep migrations reversible and document them separately.

## Final Acceptance Checklist

- [ ] `backend/main.py` includes `factors_v2.router`.
- [ ] `GET /api/labs/factors/v2/features` returns 14 features.
- [ ] `POST /api/labs/factors/v2/feature/{01..14}/run` works for every feature.
- [ ] `frontend/src/lib/api.js` calls live routes without URL changes.
- [ ] `/labs/factors-v2` or `/labs/factors` loads the new home page.
- [ ] All 14 feature pages render input-first, run-then-output workflow.
- [ ] Output configurator sends `selected_outputs`.
- [ ] Standard schema is preserved for every backend response.
- [ ] No legacy route is accidentally broken during staged rollout.
- [ ] `npm run build` passes.
- [ ] `FACTORS_V2_IMPLEMENTATION_STATUS.md` is updated.

## Files To Touch During Actual Go-Live

Required:

- `backend/main.py`
- `FACTORS_V2_IMPLEMENTATION_STATUS.md`

Likely:

- `frontend/src/app/labs/page.js`
- `frontend/src/components/GlobalLayout.jsx`
- `frontend/src/components/ui/navbar.jsx`

Only for final route replacement:

- `frontend/src/app/labs/factors/`
- `frontend/src/app/labs/factors-v2/`

Do not touch unless needed:

- `backend/app/services/factors_v2/features/*` unless a feature smoke test reveals a real computation issue.
- `frontend/src/components/factors-v2/customPagePrimitives.jsx` unless a renderer key mismatch is found.
- `frontend/src/lib/api.js` unless the backend route shape changes.

