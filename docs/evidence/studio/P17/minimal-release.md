# P17 Minimal Release Evidence (private, 2026-09-29)

## 1. Pinned deps (recorded, not pinned upstream)

- `backend/requirements.txt` exists, uses unpinned `>=` ranges only. No lock file. Honest floor versions:
  `fastapi>=0.100.0`, `pyarrow>=14.0.0`. No `requirements*.lock`, no `frontend` python pin.
- Installed and actually exercised: system `python3` (3.9): `fastapi 0.124.4`, `pyarrow 24.0.0`;
  `python3.11` test env: `fastapi 0.141.1`, `pydantic 2.13.5` (pip-installed ad hoc for this drill, `--break-system-packages`).
- `frontend/package-lock.json` exists. `next 16.0.5` in both `package.json` and lock (`node_modules/next 16.0.5`).
  `react`/`react-dom 19.2.0`.
- Gap: backend deps are floor ranges, not pinned. Reproducible installs are not guaranteed.

## 2. Production build

- Command: `npm run build` in `frontend/`. Result: PASS, exit 0.
  `Compiled successfully`, `Generating static pages (185/185)`.
- `/studio` routes built (7): `/studio`, `/studio/backtest`, `/studio/data`, `/studio/factors`,
  `/studio/optimizer`, `/studio/portfolio-risk`, `/studio/robustness`.

## 3. Five-mode smoke (no live services, tests as proxy)

- `curl` health check: `localhost:8000` and `localhost:3000` both `000` (nothing listening).
  No backend/frontend started, no live browser run. Stated clearly.
- Artifact identity flow verified in code:
  Develop (`DevelopView.jsx`) produces runs; Results (`TearsheetView.jsx:415` renders
  `portfolioArtifact.artifact_id`); Validate (`ValidateView.jsx:235,303` consumes
  `portfolioArtifact.artifact_id`, backend `routers/studio.py:148,158,1343,1374`
  threads `source_artifact_id`); Portfolio (`PortfolioView.jsx`, `services/studio/portfolio.py`);
  Replay (`ReplayView.jsx:272,281` replays by `artifact.artifact_id` + `engine_version`);
  Compose (`ComposerView.jsx`); Paper (`PaperView.jsx:32,101,103` gates deploy on
  `version_id + artifact_id + completed wfJob + promotion`, lists `source_artifact_id`;
  backend `services/studio/paper.py:73` rejects `source_artifact_id` mismatch,
  `services/studio/certification.py:38-49` binds bundle to artifact hash).
- Tests: `PYTHONPATH=backend python3.11 -m pytest -q
  backend/tests/test_studio_jobs.py backend/tests/test_studio_portfolio.py backend/tests/test_studio_paper.py`
  = 24 passed. `npx jest` on `TearsheetView`, `ValidateView.audit`, `ReplayView`,
  `ComposerView`, `PaperView`, `StudioModeStage` = 6 suites, 12 tests, all pass.
- Caveat: system `python3` is 3.9 and cannot collect the suite
  (`dict | None` syntax in `routers/studio.py:112`); 3.11 is required.

## 4. Backup/recovery drill

- Durable stores (verified on disk): `backend/app/.studio_jobs.json` (absent until first job;
  NOTE task text said `backend/.studio_jobs.json`, actual resolved path is `backend/app/.studio_jobs.json`
  per `services/studio/jobs.py:27`), `backend/app/studio_v2/storage/studio_v2.sqlite3`
  (+ `lineage.json`, `strategies/`), `backend/data/yf_cache.db`. Portfolio versions and paper
  deployments live in the sqlite store (`SQLiteStore`, `studio_paper_deployments` in `paper.py:21`);
  jobs/idempotency/audits in the jobs JSON. No `uploads/` dir exists in backend.
- Persistence logic (`jobs.py:79-85`): write tmp file, `chmod 0600`, atomic `replace`; load on every
  read-modify-write under `fcntl` process lock + thread lock; corrupt store raises instead of silently resetting.
- Drill commands and results:
  `mkdir -p /tmp/p17-backup && cp backend/app/studio_v2/storage/studio_v2.sqlite3
  backend/app/studio_v2/storage/lineage.json backend/data/yf_cache.db /tmp/p17-backup/` = ok (3 files).
  Restore dry-run: `cmp /tmp/p17-backup/studio_v2.sqlite3 backend/app/studio_v2/storage/studio_v2.sqlite3`
  = IDENTICAL (copy-back would be a no-op; no restore performed against live files).
  Restart recovery: `JobStore` create on temp path, re-instantiate on same path, `get` returns
  identical `job_id` and `source_artifact_id`, no `*.tmp` leftovers = PASS.
- `P15/operations.md` reviewed: store paths, quotas, restore procedure already accurate; no edit needed.

## 5. Rollback

- P16 tag exists: `p16-pre-cleanup-20260929`. Created local-only `p17-pre-release` (both resolve to `64dc9caa`).
- Rollback (local only, never pushed): `git reset --hard p17-pre-release`

## 6. Gaps

1. Backend requirements unpinned (`>=` only); no lock file.
2. No live e2e: services were not running, no browser automation performed.
3. Runtime requires Python 3.11+; default `python3` here is 3.9 and fails at import.
4. No migration framework; restore is file copy with writers stopped (per P15 ops note).
5. No scheduled purge/vacuum job; retention is quota-bound only.
