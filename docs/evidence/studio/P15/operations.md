# P15 Studio Operations Guide

Date: 2026-09-29. Audience: operators of the canonical Studio (`/api/studio/*` + Studio shell).

## 1. Request correlation and logs

- Clients send `X-Request-ID` on every `studioRequest` (fetch). `StudioObservabilityMiddleware` accepts safe client IDs (`[A-Za-z0-9._:-]{1,128}`) or mints one, echoes it as the `X-Request-ID` response header, and writes one structured JSON line per request: `{request_id, method, route, status, duration_ms, request_bytes, response_bytes, category}`. Route **templates** are logged, never paths with IDs, bodies, query strings, or headers.
- `EventSource` cannot send headers: `waitForStudioJobEvents` appends `?request_id=` and `GET /jobs/{id}/events` echoes it as `X-Request-ID`. The middleware ID remains authoritative in logs.
- Job records persist `request_id` and `source_artifact_id`; `GET /jobs/{id}` returns the stored `request_id`, so a failed run is diagnosable from IDs alone (`request_id` -> log line -> `job_id` -> job diagnostics). Full cross-service trace correlation remains open.

## 2. Health and job diagnostics

`GET /api/studio/health` returns liveness plus diagnostics, no secrets:

```json
{
  "status": "ok", "check": "liveness",
  "request_id": "<middleware ID or null>",
  "execution": {"mode": "isolated_one_shot", "readiness": "not_checked"},
  "jobs": {"by_status": {"completed": 3}, "max_concurrent": 2},
  "storage": {"studio_portfolio_versions": 12, "...": 0},
  "quotas": {"STUDIO_MAX_PORTFOLIO_VERSIONS": 200, "...": 0},
  "feature_flags": {"STUDIO_RENDERER_WEBGL": false, "...": false}
}
```

Centralized error aggregation is still open; per-route aggregates live in the observability registry (`method + route template` -> counts, failure rate, mean/max duration, status and category histograms).

## 3. Quotas (one config)

All Studio limits resolve through `backend/app/services/studio/quotas.py` (`get_quota` / `snapshot`), env-overridable:

| Quota env | Default | Enforced in |
|---|---|---|
| `STUDIO_MAX_PORTFOLIO_VERSIONS` | 200 | `routers/studio.py` version save |
| `STUDIO_MAX_PAPER_DEPLOYMENTS` | 100 | `services/studio/paper.py` |
| `STUDIO_MAX_REPORT_RECIPES` | 200 | `services/studio/reports.py` |
| `STUDIO_MAX_RESEARCH_NOTES` | 500 | `services/studio/reports.py` |
| `STUDIO_MAX_CERTIFICATIONS` | 500 | `services/studio/certification.py` |
| `STUDIO_RATE_PER_MINUTE` / `_PER_HOUR` | 120 / 3000 | documents `middleware/security.py` `RateLimiter` |
| `STUDIO_MAX_CONCURRENT_JOBS` | 2 | documents `JobStore` executor bound |
| `STUDIO_MAX_CODE_BYTES` / `_RESPONSE_BYTES` / `_SIGNALS` / `_SIMULATIONS` | 64 KiB / 4 MiB / 100k / 10k | documents `execution.py` + conventions |
| `STUDIO_OWNER_QUOTA_BYTES` | 512 MiB | documents upload catalog owner quota |

**Open:** per-tenant quota accounting. Counts are global; usage is not yet attributed per owner. Tenancy scoping (below) is the prerequisite and is now in place.

## 4. Tenancy and ownership

- Callers identify with `X-Owner-Id`; only `sha256(id)[:32]` is stored or compared (same pattern as the upload catalog). The header value is never echoed.
- Jobs stamp `owner_hash` at create; versions stamp it into the document; paper deployments, recipes, notes, and certifications track it in the `studio_owner_index` sidecar (no service schema migration). Cross-owner reads return `403 STUDIO_FORBIDDEN`; pre-P15 records without a stamp stay readable (legacy).
- Uploads/filenames/code/params/export bodies are validated by `services/studio/security.py` (`validate_filename`, `validate_upload_meta`, `assert_no_secret_material`, `assert_no_secret_material_in_export`); violations return typed 400/422 errors without echoing secret material.

## 5. Feature flags

Backend `services/studio/feature_flags.py` and frontend `shell/studioFeatureFlags.js` mirror four env flags, all defaulting to the safe path: `STUDIO_RENDERER_WEBGL`, `STUDIO_WORKER_EXTERNAL`, `STUDIO_GPU_ENABLED`, `STUDIO_PARQUET_FAST_SCAN` (`NEXT_PUBLIC_*` on the frontend). Health exposes their live state.

## 6. Backup, restore, retention, cleanup

- Durable state: `backend/app/studio_v2/storage/studio_v2.sqlite3` (WAL mode) holds versions, deployments, recipes, notes, certifications, and the owner index; `backend/app/.studio_jobs.json` (mode 0600, atomic replace) holds jobs, idempotency keys, and promotion audits. Back up both together; a timestamped copy before upgrades is the rollback primitive (no migration framework exists yet).
- Restore: stop writers, replace both files, restart. Promotion audit hash chains and job input hashes detect tampering or skew after restore.
- Retention: object quotas bound growth (table above); upload catalog expiry (`delete_expired`) and owner byte quotas bound dataset storage. No scheduled purge job exists; operators should vacuum SQLite during maintenance windows.
- Cleanup: remove `*.tmp` job files and `-shm`/`-wal` artifacts only when no worker is running; never commit storage files (see `.gitignore`).

## 7. Incident procedure

1. Take the failing `job_id` (or `request_id`) from the client error; `GET /api/studio/jobs/{id}` shows status, progress, error (<= 500 chars), and the stored `request_id`.
2. Join `request_id` to the structured log line for method, route template, status category, and duration.
3. Check `/api/studio/health` for queue depth (`jobs.by_status`), storage counts, and flag states.
4. For paper incidents, `set_paper_kill_switch` (audited actor + reason) halts a deployment without deleting evidence; trace events via `/paper/deployments/{id}/events/{event_id}/trace`.
5. Secret-material rejections (`SECRET_MATERIAL_REJECTED`) never echo values; ask the caller to replace literals with server-side secret references.
