> Historical document. Superseded on 2026-10-07 by [DONE.md](DONE.md) and the backend `/features` manifest. Earlier completion/default/estimator claims below are not the current runtime contract.

# Factors V2 Runtime README

This README explains exactly how to build, test, and migrate Factors V2.

## 1) Current run-time ports and hosts

From `keepalive_run.sh`:
- Backend: `127.0.0.1:8000` (uvicorn)
- Frontend: `127.0.0.1:3000` (Next.js dev)

So all API tests are against backend on:
- `http://127.0.0.1:8000`

And frontend pages run on:
- `http://127.0.0.1:3000`

---

## 2) What runs today (legacy factors)

Legacy factors APIs are currently served in:
- `backend/app/api/labs.py`

Current factors endpoints include:
- `POST /labs/factors`
- `GET /labs/factors/universe`
- `POST /labs/factors/intelligence/run`
- plus many feature-specific routes under `/labs/factors/...`

Frontend currently calls those in:
- `frontend/src/lib/api.js`

---

## 3) Where Factors V2 APIs will be created

When you are ready to wire V2, create a new router file:
- `backend/app/api/factors_v2.py`

And register it in backend app startup (`main.py` include_router).

Recommended prefix:
- `/labs/factors/v2`

Recommended endpoint pattern:
- `POST /labs/factors/v2/feature/01/run`
- `POST /labs/factors/v2/feature/02/run`
- ...
- `POST /labs/factors/v2/feature/14/run`

This keeps old and new systems running in parallel with zero breakage.

---

## 4) Feature development workflow (your exact question)

Yes, your understanding is correct.

If you finish Feature 1 first, do this:
1. Implement compute in `backend/app/services/factors_v2/features/feature_01.py`.
2. Add a single API endpoint for Feature 1 in `backend/app/api/factors_v2.py`.
3. Test API response directly (curl/Postman/local script).
4. Only then create frontend UI page for that output.

So the order is:
- backend feature compute -> backend endpoint -> API test -> frontend render.

You do **not** need to wire all 14 at once.

---

## 5) Runtime folder responsibilities

## This folder (`backend/app/services/factors_v2`)
- production compute logic
- feature functions that return JSON-ready output payloads

## Standalone folder (`/factors`)
- data pulls and conversion pipelines
- raw and processed factor datasets
- architecture and migration docs

Do not move raw data files into backend services.

---

## 6) What each feature file should contain

Current pattern (simple): one Python file per feature:
- `feature_01.py` ... `feature_14.py`

Each file should contain:
1. input parsing/validation
2. data loading calls (via `core/data_loader.py`)
3. compute logic
4. output shaping to standard JSON schema

That is enough for now.

---

## 7) Standard output schema (all features)

Every feature must return:

```json
{
  "feature_id": "feature_01",
  "status": "ok|warning|error|placeholder",
  "summary_cards": [],
  "charts": {},
  "tables": {},
  "alerts": [],
  "meta": {}
}
```

Important:
- backend returns **chart data**, not chart images.
- frontend builds visuals from `charts` payload.

---

## 8) Where frontend V2 pages should live (later)

When you start UI migration:
- `frontend/src/app/labs/factors-v2/page.js` (hub)
- `frontend/src/app/labs/factors-v2/feature-01/page.js`
- ...
- `feature-14/page.js`

You can keep legacy pages under `/labs/factors` untouched until all V2 features are stable.

---

## 9) API migration strategy (safe)

1. Keep legacy APIs active.
2. Build V2 compute for one feature.
3. Add one V2 endpoint for that feature.
4. Test endpoint thoroughly.
5. Add frontend V2 page for that feature.
6. Repeat feature by feature.
7. Retire legacy only after parity checks pass.

This is low risk and easy rollback.

---

## 10) Data readiness note (AQR/Fama/FRED)

- Fama/French datasets are downloaded and usable.
- AQR real Excel files are downloaded and converted to CSV tabs under:
  - `factors/data/processed/aqr_csv/`
- Category 7 macro pipeline is implemented and generated:
  - `factors/data/processed/category7_macro_regime.parquet`

So V2 feature compute can start immediately.

---

## 11) Minimal test recipe for one feature

Example for Feature 1 after endpoint is added:

```bash
curl -X POST 'http://127.0.0.1:8000/labs/factors/v2/feature/01/run' \
  -H 'Content-Type: application/json' \
  -d '{"as_of":"2026-05-04","universe":"global","factor":"value_pb"}'
```

Check:
- status is `ok` or `warning`
- schema keys exist
- no stack traces
- charts/tables payload not empty (if data exists)

---

## 12) Final answer to your question

Yes:
- build feature compute first,
- then add that feature's API,
- test backend output,
- then build frontend page that renders those outputs.

That is exactly the right method.


## 13) Mathematical specification source-of-truth

Feature math, formulas, and design rules are documented in:
- `/Users/adityabalaji/Downloads/quant  2/factors/docs/FACTORS_COMPUTATION_DOCUMENT.md`

When implementing each `feature_xx.py`, treat this document as the primary computation spec.
Implementation order should be:
1. parse inputs,
2. apply formulas from the computation document,
3. generate standardized output schema payload.

If there is any mismatch between this README and the computation document, the computation document takes precedence for mathematical logic.

