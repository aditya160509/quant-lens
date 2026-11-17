# Research V2 backend — runtime verification

Read-only audit of `backend/app/api/research_v2*.py` and `backend/app/services/research_v2/`.
Source files were not modified. The only writes were runtime side effects of the API itself
(projects, saved signals, jobs, one share token, two holdout seals/unseals) plus this report.

## Count table

| Severity | Count |
|---|---|
| P0 | 2 |
| P1 | 10 |
| P2 | 8 |
| **Total** | **20** |

Contracts tested: `docs/architecture/RESEARCH_V3_CONTRACTS.md`, `services/research_v2/DONE.md`,
`docs/evidence/frontend-review/research-v2/review.md`, `docs/studio/standards/CODE_STANDARDS.md`
§1, §5.4, §5.5, §7.1, §11.2, §13.3–13.4, §19.

---

## 1. Environment

| Item | Value |
|---|---|
| Python | 3.12.12 (`.venv`) |
| FastAPI | 0.162.0 (uses deferred `_IncludedRouter`, so `app.routes` is not enumerable before `openapi()`) |
| Test method | `fastapi.testclient.TestClient(main:app)`, in-process, no uvicorn, no network |
| Working dir | `/Users/adityabalaji/Downloads/quant  2/backend` |
| Data stores | `data/research_v2/jobs.json`, `data/research_v2.sqlite`, `data/research_v2/results/*.json` |

```
$ cd backend && time .venv/bin/python -c "import app.api.research_v2"
.venv/bin/python -c "import app.api.research_v2"  0.64s user 0.14s system 57% cpu 1.344 total
```

```
$ PYTHONPATH=. .venv/bin/python probe_routes.py
MAIN import seconds: 1.79
N_ROUTES (app.routes): 29  (21 are unexpanded _IncludedRouter objects)
```

Import is cheap and clean — no heavy feature imports at router import (matches `DONE.md` §"Memory").
Route enumeration required `app.openapi()` (0.09 s).

---

## 2. Route inventory (34 implemented)

Source: `app.openapi()["paths"]` filtered to `/api/labs/research/v2`.
Contract route list = §1–§3 of `RESEARCH_V3_CONTRACTS.md` (27 endpoints, incl. `feature/{id}/jobs`,
`jobs/{id}` from the jobs paragraph).

| # | Method | Path | In contract | Router |
|---|---|---|---|---|
| 1 | GET | `/features` | yes | research_v2.py |
| 2 | GET | `/symbols` | **no** | research_v2.py |
| 3 | GET | `/universe` | **no** | research_v2.py |
| 4 | POST | `/uploads` | **no** | research_v2.py |
| 5 | POST | `/feature/{feature_id}/jobs` | yes | research_v2.py |
| 6 | GET | `/jobs/{job_id}` | yes | research_v2.py |
| 7 | POST | `/jobs/{job_id}/cancel` | **no** | research_v2.py |
| 8 | GET | `/holdouts` | **no** (project holdout is documented; this legacy window list is not) | research_v2.py |
| 9 | DELETE | `/holdouts/{study_key}` | **no** | research_v2.py |
| 10 | GET | `/locks` | **no** | research_v2.py |
| 11 | POST | `/locks` | **no** | research_v2.py |
| 12 | POST | `/report-card/jobs` | yes | research_v2_reports.py |
| 13 | POST | `/batch/jobs` | yes | research_v2_reports.py |
| 14 | POST | `/validation/jobs` | yes | research_v2_reports.py |
| 15 | GET | `/universes` | yes | research_v2_reports.py |
| 16 | GET | `/literature/match` | yes | research_v2_reports.py |
| 17 | GET | `/report/{name}` | yes (`.tex`, `.pdf`; also `.md`) | research_v2_reports.py |
| 18 | GET | `/signals/operators` | yes | research_v2_signals.py |
| 19 | GET | `/signals/fields` | yes | research_v2_signals.py |
| 20 | POST | `/signals/validate` | yes | research_v2_signals.py |
| 21 | GET | `/signals/library` | yes | research_v2_signals.py |
| 22 | POST | `/signals/saved` | yes | research_v2_signals.py |
| 23 | GET | `/signals/saved` | yes | research_v2_signals.py |
| 24 | GET | `/signals/saved/{signal_id}` | yes | research_v2_signals.py |
| 25 | POST | `/signals/combine` | yes | research_v2_signals.py |
| 26 | GET | `/projects` | yes | research_v2_projects.py |
| 27 | POST | `/projects` | yes | research_v2_projects.py |
| 28 | GET | `/projects/{pid}` | yes | research_v2_projects.py |
| 29 | GET | `/projects/{pid}/ledger` | yes | research_v2_projects.py |
| 30 | GET | `/projects/{pid}/holdout` | yes | research_v2_projects.py |
| 31 | POST | `/projects/{pid}/holdout` | yes | research_v2_projects.py |
| 32 | POST | `/preregistrations` | yes | research_v2_projects.py |
| 33 | POST | `/share` | yes | research_v2_projects.py |
| 34 | GET | `/share/{token}` | yes | research_v2_projects.py |

**Missing: none.** All 27 documented endpoints exist. **Extra/undocumented: 9** (#2,3,4,7,8,9,10,11
and the `.md` extension of #17). They are harmless in themselves; the risk is that they are unversioned
public surface (R-12) and that `DELETE /holdouts/{study_key}` mutates protection state with no audit (R-02).

---

## 3. Endpoint smoke table

Measured in-process with TestClient, cold (first call) then warm.

| Method | Path | Status | Cold ms | Body | Contract shape |
|---|---|---|---|---|---|
| GET | `/features` | 200 | 49 | 96,093 B | ✅ 10 features; every input carries `required/depends_on/conflicts_with/unit/level/citation` |
| GET | `/symbols?q=AAPL` | 200 | 208 | 53 B | ⚠️ wrapped `{results:[…]}`, contract does not document this endpoint |
| GET | `/universe` | 200 | 8 | 75,500 B | ⚠️ undocumented; 1,402 US names with `rank` |
| GET | `/universes` | 200 | 990 / 8 warm | 4,183 B | ✅ 40 universes `{id,label,region,asset_type,count}`; `global`=4,157 |
| GET | `/holdouts` | 200 | 2 | 15 B | ⚠️ wrapped `{holdouts:[]}`, undocumented |
| GET | `/locks` | 200 | 1 | 12 B | ⚠️ wrapped `{locks:{}}`, keyed object not a list |
| GET | `/signals/saved` | 200 | 6 | `[]` | ✅ list |
| GET | `/signals/library` | 200 | 1 | 9,716 B | ✅ 54 entries (≥40 required) with all 7 fields |
| GET | `/signals/operators` | 200 | 1 | 3,350 B | ✅ 25 operators |
| GET | `/signals/fields` | 200 | 27 | 4,862 B | ✅ 42 fields, sources `price|derived|fundamental`, coverage |
| GET | `/literature/match?expr=…` | 200 | 762 | — | ❌ returns `{matches:[…]}`, contract says a bare array |
| GET | `/projects` | 200 | 7 | — | ✅ |
| GET | `/projects/{id}` | 200 | 2 | — | ✅ plus undocumented `sealed_after` |
| GET | `/projects/{id}/ledger` | 200 | 2 | — | ❌ nulls / mislabeled metric (R-05) |
| GET | `/projects/{id}/holdout` | 200 | 2 | 37 B | ✅ `{sealed_after,unsealed}` |
| GET | `/projects/nope` | 404 | 2 | — | ✅ `{"detail":"Unknown project"}` |
| GET | `/jobs/nope` | 404 | 2 | — | ✅ |
| GET | `/share/nope` | 404 | 2 | — | ✅ |
| GET | `/report/nope.tex` | 404 | 1 | — | ✅ |
| GET | `/signals/saved/999999` | 404 | 1 | — | ✅ |

Contract shapes verified in detail:

```
signals/library first: {'id': 'mom_12_1', 'name': 'Momentum 12-1', 'category': 'momentum',
 'formula': 'delay(close, 1) / delay(close, 12) - 1', 'citation': 'Jegadeesh and Titman (1993)',
 'year': 1993, 'expected_sign': 1}

signals/fields sample: {'name': 'close', 'source': 'price', 'doc': 'Month-end close', 'coverage': 1.0}

features inputs: keys union = ['citation','conflicts_with','default','depends_on','group','help',
 'key','label','level','max','min','options','required','required_unless','type','unit']
```

---

## 4. Job lifecycle evidence

### 4.1 Happy path (F11, 40 tickers, 730-day lookback)

```
JOB11_CREATE 200 {"job_id":"826287…","status":"queued","feature_id":"11"}   (17 ms)
  poll status=running  elapsed=0.1s
  poll status=completed elapsed=2.2s
JOB11_RESULT keys: ['feature_id','status','summary_cards','charts','tables','meta']
JOB11_META keys: ['data_inventory','research_caveats','config','lookahead','data_audit','costs',
                  'return_series','preregistered']
JOB11_DATA_AUDIT keys: ['universe_size_by_month','coverage_by_month','missing_share',
                        'survivorship','pit_lag_days','adjustments']  n_months=23
JOB11_SURVIVORSHIP: not handled  pit_lag= None  missing= 0.0
JOB11_COSTS keys: ['available','cost_model','long_only','aum_usd','gross_sharpe','net_sharpe',
 'breakeven_bps','breakeven_basis','turnover','turnover_basis','annual_turnover','capacity_usd',
 'capacity_basis','borrow_cost_per_period','mean_gross_return','mean_net_return']
JOB11_LOOKAHEAD: {'flagged': False}
```

All three documented `meta` blocks exist and are correctly shaped (§1 line 21, §3 lines 39–40).
`cost_model` input is honoured (spread 5 bps, `impact:"none"`, `long_only:true` → `net_sharpe 0.745`,
`breakeven_bps 323.75`, `capacity_usd: null`). `universe_id/regions/asset_types/min_price/
min_dollar_volume/min_listing_months` are honoured; unknown `universe_id` surfaces
`Unknown universe_id 'nope'. See GET /universes.`

### 4.2 Signal job with `signal_expr`

```
JOB11X_LOOKAHEAD: {'flagged': False, 'mean_corr_future_month': 0.0333, 'mean_corr_same_month': 0.0165}
```

Look-ahead guard runs and reports the extra diagnostics when a formula is supplied.

### 4.3 Projects, saved signals, share

```
PROJECT_CREATE 200 {"id":"e7a6b3f143bb", …}
PROJECT_CREATE_DUP 200 {"id":"35c2e08e685a", …} distinct_id=True      # duplicate names allowed
SIGNAL_SAVE    200 {"id":1,"version":1}
SIGNAL_SAVE_V2 200 {"id":1,"version":2}                              # same name → new version ✅
SIGNAL_GET     200 {"id":1,"name":"audit-mom-…","versions":[{…},{…}]} ✅
SHARE          200 {"token":"1oEcVBUW…"}
SHARE_READ     200 ['feature_id','result','created_at'] full_result=True  bytes=7312
```

### 4.4 Holdout

```
SEAL2_SET       200 {"sealed_after":"2023-01-01","unsealed":false}
SEAL2_MONTHS    first/last/n: ['2016-02'] ['2022-11'] 82
SEAL2_CAVEATS   ['Project holdout sealed: data after 2023-01-01 is excluded.']
OPEN_MONTHS     first/last/n: ['2016-02'] ['2025-12'] 119   post-2023 count= 35
```

The seal is applied correctly **when the payload carries the sealed `project_id`** — and completely
bypassed when it does not (R-01).

### 4.5 Failure / cancel / persistence

```
BAD_FEATURE        404 {"detail":"'Unknown Research V2 feature 99'"}
CANCEL_UNKNOWN     404
CANCEL_KNOWN       200 {"status":"cancelled", …}
CANCEL_AFTER       200 status=cancelled, no "result" key
CANCEL_TWICE       200
BATCH_EMPTY        422 (pydantic min_length)
BATCH_501          422 (max_length 500)
VALIDATION_BAD_METHOD 422
VALIDATION_FOLDS_99   422
```

Persistence in a **fresh Python process** (new TestClient, new store instances) — jobs.json-only,
both-stores, and SQLite-only jobs all resolve; this is the closest available substitute for a server restart:

```
OLD_ONLY_COMPLETED 50
PERSIST_OLD          ed54c1b2 200 completed has_result=True bytes=9453
PERSIST_NEW          8b79f2cf 200 completed has_result=True bytes=1230
SQLITE_ONLY 2
PERSIST_SQLITE_ONLY  101c9b21 200 {"job_id":"…","type":"research_v2_sc05","status":"completed",…}
```

---

## 5. Findings

## R-01 Hold-out seal is bypassed by omitting `project_id`
- **Severity:** P0
- **Standard:** §5.4 "Hold-out observations are excluded from development summaries that would leak
  performance information"; contract §2 line 28: "While a holdout is sealed, jobs exclude data after the seal date."
- **Evidence:**
  ```
  SEAL2_SET       200 {"sealed_after":"2023-01-01","unsealed":false}
  # payload includes project_id
  SEAL2_JOB       completed   months 2016-02 … 2022-11  (82)
  # identical payload, project_id removed
  OPEN_JOB        completed   months 2016-02 … 2025-12  (119)  post-2023 count= 35
  ```
  Command: `PYTHONPATH=. .venv/bin/python probe_e2e3.py`. `_execute` reads the seal only from
  `payload.get("project_id")` (`app/api/research_v2.py:70`), so the seal is a property of a *client-supplied
  field*, not of the data session.
- **Impact:** any caller — including the browser's own job form if `project_id` is absent — can evaluate the
  reserved hold-out at will and report the result as an in-sample finding. This is the exact failure mode
  §5.4 and the P0 class ("Hold-out leakage") exist to prevent. Unsealing is not even required.
- **Fix:** resolve the holdout server-side (session/project context or a single active seal per user), require
  `project_id` for every feature job once any seal exists, and hard-fail jobs whose payload could reach data
  after an active seal instead of silently running unsealed.
- **Confidence:** CONFIRMED

## R-02 Hold-out control is unauthenticated and has no audit trail
- **Severity:** P0
- **Standard:** §5.4 "Access controls are enforced server-side", "Hold-out access is authenticated",
  "Every exposure is recorded in an append-only audit trail", "Repeated exposure changes the reported
  independence status".
- **Evidence:** `POST /projects/{pid}/holdout` has no auth dependency (all 34 routes: `security` absent —
  §8 of this report), and `set_holdout` is a single `UPDATE projects SET sealed_after=?`
  (`store/db.py:115-116`). No table, event or hash records seals/unseals:
  ```
  SEAL_UNSEAL       200 {"sealed_after":null,"unsealed":true}
  SEAL_UNSEAL_AGAIN 200 {"sealed_after":null,"unsealed":true}     # no record, no count, no actor
  ```
  `sqlite3 data/research_v2.sqlite ".tables"` → `jobs projects preregistrations shares` only.
- **Impact:** a seal can be removed (or re-cut) silently by any client, and the resulting results are
  indistinguishable from a genuinely pre-registered out-of-sample test. §5.4's "every exposure recorded"
  and "repeated exposure changes independence status" cannot be satisfied with the current schema.
- **Fix:** append-only `holdout_events(id, project_id, action, actor, sealed_after, prior, created_at,
  prev_hash, hash)` written inside the same transaction as the holdout change; require auth + explicit
  confirmation for unseal; surface `evaluation_count` and `independence` on `GET /projects/{id}/holdout`.
- **Confidence:** CONFIRMED

## R-03 `meta.preregistered` is decided at completion, so post-hoc hypotheses count as preregistered
- **Severity:** P1
- **Standard:** §5.5 "Verdict inputs are server-computed", §2.2 execution chronology; contract §2 line 29.
- **Evidence:**
  ```
  JOB submitted at T, prereg created 0.2 s later while the job is still running
  PREREG_CREATED_AFTER_SUBMIT 200 {"id":"549cd18bd410", …}
  JOB_PREREG_FLAG completed True
  ```
  `research_v2.py:75` sets `result["meta"]["preregistered"] = store.is_preregistered(pid, payload)` *after*
  the worker returns, and `store.db:130` matches against whatever preregistrations exist at that moment.
- **Impact:** a researcher can see the result, then register the hypothesis, and the result is stamped
  "preregistered" — defeating the confirmatory/exploratory distinction the field exists to make.
- **Fix:** snapshot the matching preregistration id(s) when the job is created (store them on the job row) and
  copy that snapshot into `meta` at completion.
- **Confidence:** CONFIRMED

## R-04 Formula signals can never be preregistered
- **Severity:** P1
- **Standard:** contract §1: "Every feature payload accepts `signal_expr` … A formula overrides `signal`";
  §2: "Results carry `meta.preregistered: bool`". §5.5.
- **Evidence:** preregistration with `signal = "delay(close, 1) / delay(close, 12) - 1"` accepted (200), then
  ```
  JOB_FORMULA_PREREG completed False   payload_signal= custom
  ```
  `store.db:131` compares `payload.get("signal")`, which is absent (or "custom") for formula runs. The ledger
  also records `"signal": null` for every formula run.
- **Impact:** the confirmatory workflow silently cannot be used for the formula language, which is the
  headline feature of §1. Formula runs are permanently non-preregistrable, and the ledger cannot count them.
- **Fix:** canonicalise the signal key at the boundary (`signal_expr` > `signal_ref` > `signal`) and match
  preregistrations and ledger entries on that key.
- **Confidence:** CONFIRMED

## R-05 Ledger reports a t-stat as `haircut_sharpe.observed` and leaves the DSR hurdle null
- **Severity:** P1
- **Standard:** §2.4 multiple testing, §5.5 "Verdict inputs are server-computed"; contract §2 line 27
  `{… deflated_sharpe_hurdle, haircut_sharpe:{observed, haircut}, pbo? …}`.
- **Evidence:**
  ```
  JOB01 summary cards: [('Signal λ', 0.01406), ('FM t-stat', 1.9693289250604094), …]
  LEDGER: {"trials":1,"distinct_signals":1,"deflated_sharpe_hurdle":null,
           "haircut_sharpe":{"observed":1.9693289250604094,"haircut":-4.44e-16}}
  LEDGER_ENTRIES: [{… "t_stat":1.9693289250604094, "sharpe":null …}]
  ```
  `store/ledger.py:33` falls back to `best["t_stat"]` when no card matches "sharpe", so a **t-statistic is
  returned under a key named `observed` Sharpe**, and `haircut_t` is applied to that t-stat. `deflated_sharpe_hurdle`
  needs ≥2 numeric Sharpe values (`ledger.py:27`), which never exist because `_card()` only scans
  `summary_cards` and no run emits a "Sharpe" card — even though `meta.costs.gross_sharpe` is present.
- **Impact:** a Sharpe haircut is displayed that was computed from a t-stat (dimensionally wrong, ~2.0 vs a
  real Sharpe of ~0.3), and the multiple-testing hurdle is always null on real projects. Both feed the
  research narrative the ledger is supposed to police.
- **Fix:** read Sharpe from `meta.costs.gross_sharpe` (or the L/S card) and keep `t_stat` in its own field;
  when no Sharpe exists return `observed: null` rather than substituting a t-stat; compute the DSR when
  ≥2 trials exist.
- **Confidence:** CONFIRMED

## R-06 Invalid `sealed_after` is accepted, persisted, and wedges the project
- **Severity:** P1
- **Standard:** §13.3 "Jobs transition through valid states", §7.2 API boundaries.
- **Evidence:**
  ```
  SET   200 {"sealed_after":"not-a-date","unsealed":false}
  JOB   failed  ERROR: Unknown datetime string format, unable to parse: not-a-date
  PROJECT_STILL_SEALED {"sealed_after":"not-a-date","unsealed":false}
  ```
  `HoldoutIn.sealed_after` is `Optional[str]` (`research_v2_projects.py:20`) and `set_holdout` writes it
  verbatim; the failure only appears later inside `apply_seal` → `pd.Timestamp`. `"31/01/2023"` is also
  accepted and silently interpreted day-first.
- **Impact:** one typo makes every subsequent job on the project fail with a raw pandas message and no way to
  see why from the holdout endpoint. The project stays broken until manually unsealed.
- **Fix:** parse with `date.fromisoformat` in the request model (422 on failure), store an ISO date only, and
  reject dates in the future or before the data start.
- **Confidence:** CONFIRMED

## R-07 Sealing a project whose remaining window is empty fails with a misleading data error
- **Severity:** P1
- **Standard:** §5.4, §13.3 "Failures are surfaced correctly".
- **Evidence:** seal `2023-01-01` with `lookback_days: 730` (data only 2024-02 onward):
  ```
  SEALED_JOB status=failed
  SEALED_ERROR: Only 0 formation dates have >= 30 assets with the 'momentum' signal.
                Widen the universe or lookback, or choose a price-based signal.
  ```
  The real cause is the holdout, not the universe or the signal.
- **Impact:** users widen the universe / switch signal (which cannot help) instead of extending the lookback or
  moving the seal. Wasted runs and mistrust of the seal.
- **Fix:** in `build_panel`, if the seal removed all formation dates, raise a dedicated
  `HoldoutCoverageError` naming the seal date and the last usable month.
- **Confidence:** CONFIRMED

## R-08 The global 20-req/s burst limiter breaks the documented job-polling contract
- **Severity:** P1
- **Standard:** §11.2 "Polling does not create excessive server load", "Long jobs return a job identifier
  promptly"; §13.3 "API requests reach the correct numerical engine".
- **Evidence:**
  ```
  BURST25 [200×15, 429×10] elapsed=0.04s
  body: {"error":"Too Many Requests","detail":{"limit":20,"window":"burst","retry_after":1}}
  AFTER_COOLDOWN 200
  ```
  `app/middleware/security.py:167-171` allows 20 requests/second per IP and 120/minute, with a 60 s block on
  the minute bucket. Our very first smoke run hit 429 after ~20 calls and every later call in that batch failed.
- **Impact:** a research page that mounts the manifest, a project, two job polls and a ledger request
  (the documented flow) sits at the edge of 20/s; with `refetchIntervalInBackground` on two jobs plus
  navigation the client starts receiving 429s and React Query (`retry: 1`) surfaces an error instead of a
  result. The 429 envelope is also unlike every other error in the API (`{detail: string}`), so no client
  handles it.
- **Fix:** exempt `GET /jobs/{id}` (or raise the research-lab bucket), always send `Retry-After`, return the
  same `{detail}` shape, and move progress to SSE as `WORK_LEFT.md` already plans.
- **Confidence:** CONFIRMED

## R-09 The job payload has no type or range validation; bad input fails late with raw Python errors
- **Severity:** P1
- **Standard:** §11.2 API performance/validation, §13.3 "Failures are surfaced correctly", §7.2 API boundaries.
  The manifest itself declares `lookback_days` min 730 / max 11000 and `max_symbols` min 30 / max 2000.
- **Evidence** (all accepted `200` at submit, then fail inside the worker):
  ```
  BADPAYLOAD negative_lookback job=failed error=Unknown tickers (not in local market data): AA, AAMI, …
  BADPAYLOAD string_lookback   job=failed error=invalid literal for int() with base 10: 'abc'
  NAN_RAW_POST 200            job=failed error=cannot convert float NaN to integer
  MAXSYM_STR_JOB               error=invalid literal for int() with base 10: 'many'
  ```
  `RunRequest.payload` is `Dict[str, Any]`; `normalize_config` does `int(payload.get("lookback_days"))`
  without a range check (`core/panel.py:243-244`).
- **Impact:** a typo produces a job record that fails seconds later with an internal message; the negative
  lookback case is actively misleading (it blames tickers). Every bad payload also consumes a worker process
  and leaves a failed job in the ledger history.
- **Fix:** generate a pydantic request model per feature from the manifest's `key/type/min/max/options`
  (the manifest already has all of it) and return 422 at the boundary.
- **Confidence:** CONFIRMED

## R-10 A job can reference a non-existent project and runs orphaned
- **Severity:** P1
- **Standard:** §13.3 "Saved strategy versions reload correctly", contract §2 line 26 "every run in a
  project is a trial".
- **Evidence:**
  ```
  BOGUS_PROJECT_POST 200 {"job_id":"9b24e71e…","status":"queued"}
  BOGUS_PROJECT_JOB  completed
  BOGUS_PROJECT_GET  404
  ```
  `_execute` calls `store.sealed_after(pid)`; `get_project` returns `None` and the run proceeds.
- **Impact:** a mistyped/forged `project_id` silently produces a completed study that appears in **no**
  project, no ledger and no trial count — the exact accounting the ledger exists to provide. It is also the
  mechanism behind R-01.
- **Fix:** 404 on unknown `project_id` in `create_job`, `_submit` and `preregistrations`.
- **Confidence:** CONFIRMED

## R-11 Persistence is split across two stores; the contract names only SQLite
- **Severity:** P1
- **Standard:** contract §2 line 24: "Jobs and results persist in SQLite at `backend/data/research_v2.sqlite`,
  so `GET /jobs/{id}` works after a restart"; §13.3 "Results persist correctly".
- **Evidence:**
  ```
  jobs.json 126  sqlite 62
  in json not sqlite: 66        (52% of history)
  in sqlite not json: 2
  completed: 105 → 105 result files present, 0 missing
  ```
  `research_v2.py:33` still creates a `JobStore(path=…/jobs.json)`, and `JOBS.get()` is consulted first
  (`:147`); `store.save_job` is a secondary write. `GET /jobs/{id}` therefore depends on `jobs.json` for
  most history.
- **Impact:** deleting/rotating/corrupting `jobs.json` (which `JobStore._load` treats as fatal:
  `RuntimeError("Studio job store is unreadable")`) loses the status and payload of half the run history,
  although the contract says SQLite is the store. Two divergent indexes also caused 2 SQLite-only jobs
  (`sc05`) that only resolve through the fallback.
- **Fix:** make SQLite the sole index; import `jobs.json` once with a migration test; keep the file read-only
  or delete it after migration.
- **Confidence:** CONFIRMED

## R-12 No authentication on any research endpoint (34/34)
- **Severity:** P1 (P0 if the service is reachable beyond localhost)
- **Standard:** §7.1 authentication/authorization, §5.4 "Hold-out access is authenticated".
- **Evidence:**
  ```
  SECURITY_SCHEMES []            (app.openapi()["components"])
  TOTAL_PATHS 202  NO_AUTH_PATHS 202
  RV2_ENDPOINTS 34 / 34 with no `security`
  ```
  The app has no security scheme at all; `get_client_key` only reads `request.state.user_id`, which nothing
  sets. Same for the share endpoint — but the contract deliberately makes `GET /share/{token}` public, so the
  delta is that everything else is public too.
- **Impact:** anyone who can reach the port can create studies, read every project's results, create/remove
  holdout seals and preregistrations, and download reports. The contract's project/holdout model implies an
  owner; there is none, and `project_id` is the only "credential".
- **Fix:** router-level `Depends(require_user)`, per-user project ownership on every `/projects/*` and job
  route, and a signed, expiring token for `/share`. Keep only `/share/{token}` public.
- **Confidence:** CONFIRMED

## R-13 Documented response shapes drift (literature, holdouts, symbols, locks)
- **Severity:** P2
- **Standard:** contract §3 line 42: "`GET /literature/match?expr=` → `[{library_id, name, corr}]`";
  §19 "Documentation matches implementation".
- **Evidence:**
  ```
  LITERATURE 200 {"matches":[{"library_id":"momentum","name":"Momentum","corr":1.0000000000000002},…]}
  ```
  Contract says a bare array. Similarly `/holdouts` → `{holdouts:[…]}`, `/locks` → `{locks:{hash:…}}`,
  `/symbols` → `{results:[…]}`, `/universe` → `{symbols:[…]}`, and `GET /report/{name}` also accepts `.md`
  (undocumented). `/features`, `/universes`, `/signals/*` are exact.
- **Impact:** a contract-driven client (`matches.map(...)`) breaks on the literature endpoint; the other
  wrappers are undocumented surface that the frontend must guess.
- **Fix:** return the bare array for `/literature/match` (and document the remaining envelopes), or amend the
  contract with the exact wrappers. Pick one.
- **Confidence:** CONFIRMED

## R-14 Batch rows drift from the documented schema
- **Severity:** P2
- **Standard:** contract §3 line 36: rows are `{signal, t_stat, p, p_adj_bhy, sharpe, ic, grade, survives}`.
- **Evidence:**
  ```
  ROW {"signal":"momentum","t_stat":0.2878,"p":0.7744,"sharpe":-0.0165,"ic":-0.0048,"months":65,
       "ls_t_stat":-0.0430,"p_adj_bhy":1.0,"grade":"F","survives":false}
  ROW {"signal":"doesnotexist","error":"Signal formula error: Unknown name 'doesnotexist' (characters 0-12)"}
  ROW_FIELDS_UNION ['grade','ic','ls_t_stat','months','p','p_adj_bhy','sharpe','signal','survives','t_stat']
  ```
  Failed signals produce a row with **only** `signal` and `error`.
- **Impact:** typed clients must treat every row as optional; a UI that colours by `grade` renders the error
  row as a blank success. Extra fields (`months`, `ls_t_stat`) are useful but undocumented.
- **Fix:** define a row model with `grade/survives/p_adj_bhy: null` on error and document the extra fields.
- **Confidence:** CONFIRMED

## R-15 `folds` is a group count, not a fold count, and is silently clamped
- **Severity:** P2
- **Standard:** contract §3 line 41: `{payload, method, folds, embargo_days} → {folds:[{…}]}`.
- **Evidence:**
  ```
  POST /validation/jobs {"folds": 5, "method": "cpcv"} → result folds=10, summary.folds=10
  POST /validation/jobs {"folds": 99} → 422 (ge=3, le=12)
  ```
  `reports.py:384` iterates `itertools.combinations(range(folds), 2)`, so `folds=5` yields 10 evaluation
  folds. `run_validation` also clamps with `max(3, min(int(folds), 12))` (`:359`) after pydantic already
  enforced the same bounds.
- **Impact:** the audit trail says "10 folds" for a request that asked for 5, and the summary's `folds` field
  changes meaning between walk_forward (`folds+1` chunks → `folds` evaluations) and CPCV (`C(folds,2)`).
- **Fix:** rename the request field to `groups` for CPCV or document the expansion; report
  `requested_groups` and `evaluation_folds` separately.
- **Confidence:** CONFIRMED

## R-16 Duplicate project names are allowed
- **Severity:** P2
- **Standard:** §19 "Documentation matches implementation"; usability of the project switcher.
- **Evidence:**
  ```
  PROJECT_CREATE_DUP 200 {"id":"35c2e08e685a","name":"audit-proj-1794907733", …} distinct_id=True
  PROJECT_DUPES {'audit-proj-1794907780': 2, 'audit-proj-1794907733': 2} total 8
  ```
  `projects` has no `UNIQUE(name)` and `create_project` does not check.
- **Impact:** two indistinguishable entries in any name-based picker; runs split across them and the ledger
  under-counts trials.
- **Fix:** unique `(owner_id, name)` or return a suffix; at minimum warn on exact duplicates.
- **Confidence:** CONFIRMED

## R-17 Literature correlation exceeds 1
- **Severity:** P2
- **Standard:** §2.5 statistical inference (a correlation is bounded by ±1).
- **Evidence:** `"corr": 1.0000000000000002`
- **Impact:** a strict client (`corr > 1` invariant, or a 0–100 CI bar) breaks; tiny but it ships in the
  headline "nearest published anomaly" answer.
- **Fix:** `float(np.clip(corr, -1.0, 1.0))` where the match is emitted.
- **Confidence:** CONFIRMED

## R-18 The central payload is an untyped `Dict` and no endpoint declares a response model
- **Severity:** P2
- **Standard:** §8.2 Python quality, §7.2 API boundaries.
- **Evidence:**
  ```
  RV2_ENDPOINTS 34
  RV2_NO_RESPONSE_SCHEMA 0   (0 of 34 operations declare a 200 schema)
  POST /feature/{feature_id}/jobs body: {"$ref":"RunRequest"} → payload: object, additionalProperties: true
  ```
- **Impact:** the API contract exists only in prose; nothing prevents R-09-style drift, and generated clients
  cannot type any result. `GET /jobs/{id}` returns a shape that changes with status.
- **Fix:** a `FeaturePayload` model (generated from the manifest) and a discriminated `JobStatus` response
  model (`queued|running|completed|failed|cancelled`).
- **Confidence:** CONFIRMED

## R-19 Cancelling a job still computes it and writes an orphan result file
- **Severity:** P2
- **Standard:** §11.2 "Failed jobs release resources"; `DONE.md` "Cancelling a job stops publication of its
  result; a computation already running finishes in the background".
- **Evidence:** F02 cancelled 1.5 s after submit; later:
  ```
  data/research_v2/results/3c151324c03642e494bb995561b475b9.json  EXISTS 81,891 bytes
  result files 106, referenced by jobs.json 105, orphans 1
  ```
  `_execute` writes `RESULTS_DIR/<job_id>.json` unconditionally after the pool returns; only
  `JobStore.run_sync` checks the cancel flag.
- **Impact:** cancellation is documented as "stop publishing" but it still burns a multi-second worker
  process and leaves a full result (including `meta`, charts, tables) on disk forever, unreachable and
  uncounted.
- **Fix:** check cancellation in `_execute` before writing, delete any partial file, and record the cancel in
  the job audit.
- **Confidence:** CONFIRMED

## R-20 The spawned worker pool requires an import-safe `__main__`, and the failure is opaque
- **Severity:** P2
- **Standard:** §11.2, §13.3 "Failures are surfaced correctly".
- **Evidence:** starting the app from a non-file entrypoint (`python - <<'PY'`) makes every job fail:
  ```
  JOB failed ERROR: A process in the process pool was terminated abruptly while the future was running or pending.
  ```
  The child traceback (`FileNotFoundError: …/backend/<stdin>`) is never surfaced. (Under `uvicorn main:app`
  the entrypoint is file-backed and this did not occur in our runs; see limitations.)
- **Impact:** deployment through `-c`/stdin, some notebook kernels, or a frozen entrypoint produces jobs that
  always fail with a message that names neither the cause nor the fix.
- **Fix:** use an explicit top-level worker entry (`app.services.research_v2.worker`) and forward the child's
  exception text; document that the API must be started from a module.
- **Confidence:** CONFIRMED (failure mode) / UNVERIFIED (impact under the documented uvicorn launch)

---

## 6. What I could not verify, and why

1. **Real process restart.** Persistence was checked from a fresh Python process with a new `TestClient` and
   new store instances (all three job sources resolve). I did not start/stop uvicorn (explicitly out of
   scope), so an actual server restart is UNVERIFIED.
2. **Report-card cost and response size on a valid payload.** A report card runs F01–F05 + F11 + F08 in one
   worker; at the documented 3–30 s per feature that exceeds the 120 s job budget. I ran one invalid-payload
   card (completed in ~5 s, 5,788 B, all dimensions F, `component_errors` populated, correct fail verdict)
   and verified `.tex` (3,683 B), `.md` (3,099 B) and `.pdf` (4,380 B) render. **No bound on a valid card's
   size or runtime is verified.** `BatchRequest` is bounded at 500 signals (422 at 501).
3. **Concurrency.** The pool is 2 workers with `max_tasks_per_child=1`; I exercised cancellation and queueing
   but not sustained parallel load, so throughput and the §11.2 "concurrent request behavior is tested"
   clause remain UNVERIFIED.
4. **Holdouts/locks window flow (`GET /holdouts`, `DELETE /holdouts/{study_key}`).** No protected window
   exists in the store (`{"holdouts":[]}`); creating one and releasing it would mutate research state that is
   not mine to delete, so I only verified the empty list and the 404 path. Marked UNVERIFIED.
5. **Upload limits.** I verified the sandbox (random `upload_id`, traversal filename rejected, bad extension
   422, missing columns 422) but not the 20 MB cap (I did not send a 20 MB body).
6. **Auth/permissions behavior.** Verified absence (0 security schemes), not enforcement under a reverse proxy.
7. **`capacity_usd`.** Returned `null` with `impact:"none"`; I did not run the `sqrt` path to confirm the
   capacity number's units, so the contract's `capacity_usd` semantics are only partially verified.
   (`impact:"sqrt"` is the default and the code path exists.)
8. **Progress.** Every job reports the same `{percent: 50, message: "running"}` until terminal — consistent
   with `WORK_LEFT.md` §5 ("job progress messages"), which lists step-level progress as not done. Not filed
   as a defect because it is a documented open item.
9. **`GET /features` and `/universes` cold latency** was measured on a warm OS page cache after earlier runs;
   the 990 ms first-call for `/universes` is not a clean cold-start number.

## Notes on the data written

Runtime side effects of this audit, deliberately left in place: 8 projects (`audit-*`, 2 pairs sharing a
name), 1 saved signal (2 versions), 1 share token, 1 lock, 1 preregistration, ~30 jobs (features 01, 02, 11,
report-card, batch, validation), 3 uploads, several holdout seal/unseal cycles, and one orphan result file.
Nothing was deleted or modified in source.
