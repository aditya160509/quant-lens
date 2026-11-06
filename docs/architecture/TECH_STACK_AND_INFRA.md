# Tech Stack and Infrastructure

Written 2026-10-05. This covers what to keep, what to add and what to skip for this application: a single-user quant research platform with a Python analytics backend and a Next.js frontend.

## Verdict

The core stack is right. Do not rewrite in Rust or Go. The gaps are infrastructure (jobs, storage, typed API, environment), not language.

## Keep

| Layer | Choice | Why |
|---|---|---|
| Backend language | Python | The quant ecosystem only exists here: numpy, pandas, statsmodels, arch, linearmodels, pyfixest, scikit-learn, cvxpy. Rust or Go would mean rewriting these, worse. |
| API | FastAPI | Async, Pydantic validation, an OpenAPI schema for free. |
| Frontend | Next.js 16 + React 19 | Already in place. |
| Server state | TanStack Query | Already installed and used (Research V2 `api.js`). |
| Client state | Zustand | Already installed. |

## Speed, in order of payoff

1. **Polars instead of pandas** for loading, filtering and pivoting parquet. It is written in Rust, so you get Rust speed without writing Rust: typically 5-20x faster. Already installed.
2. **DuckDB (Python)** for SQL-style work over parquet: universe filters, as-of joins for point-in-time fundamentals, group-bys over the whole market file.
3. **Numba** for loops that cannot be vectorized: backtest simulation, Fama-MacBeth, rolling estimators. Never use `fastmath=True` (it breaks `np.isfinite`). Use `cache=True`.
4. **Cache computed panels** to parquet, keyed by the source file's mtime, so features do not rebuild the same panel on every request.
5. **Rust only as a last resort.** Do it for one profiled hotspot, as a Python extension built with PyO3 + maturin, and only if Numba is not enough. Probably never needed.

Profile first (`py-spy`, `scalene`) before optimizing anything.

## Infrastructure gaps

| Gap | Today | Use |
|---|---|---|
| Background jobs | A JSON-file `JobStore` in each process | **Redis + arq** (or Celery). Jobs survive restarts, you can run several workers, and cancel works properly. Biggest upgrade. |
| App storage | Parquet + JSON files | Keep parquet for market data. Use **Postgres** (via existing Supabase) for saved screens, job history, holdouts and locks, alert state, run history. |
| Progress | Polling | **Server-Sent Events** from FastAPI. Simpler than WebSockets. |
| Typed API | Hand-written `fetch` calls | Generate a TypeScript client from FastAPI's OpenAPI schema with **orval** or **openapi-typescript**. This prevents the URL and request-envelope mismatches found in every V2 review. |
| Python environment | System 3.9 vs 3.11 confusion, unpinned `requirements.txt` | **uv** with a lockfile, Python 3.12 pinned in `.python-version`. |
| Errors and logs | None | **Sentry** (backend and frontend), structured JSON logs. |
| Tests in CI | Run by hand | A GitHub Actions workflow: pytest, jest, lint, build. |

## Frontend libraries

Already installed and worth using fully:

| Library | Use |
|---|---|
| TanStack Table + TanStack Virtual | Large tables (screener results, 5,000-row universes) |
| cmdk | ⌘K command palette |
| framer-motion | Motion |
| @react-three/fiber + drei | WebGL 3D views |

**Pick one main chart library.** The project currently mixes recharts, echarts, plotly and visx. For dense or many-point charts use **uPlot**, or **deck.gl** for GPU scatter and heatmaps.

The frontend rebuild and visual design are done with Claude only (see `backend/app/services/research_v2/WORK_LEFT.md`).

## Docker

**Not needed now.** While one person runs everything on one Mac:

- backend: `uv run uvicorn main:app --reload`
- frontend: `npm run dev`
- redis: `brew install redis && brew services start redis`
- postgres: Supabase

Add Docker when the app is deployed to a server (Fly, Railway, a VPS), when someone else must run it, or when you want one command for api + worker + redis + postgres. At that point a single `docker-compose.yml` with those four services is enough.

## Skip

Go, a microservices split, GraphQL, Kafka, Kubernetes. They are overkill for one user on one machine.

## Order of work

1. uv + lockfile + pinned Python
2. Polars and DuckDB in the V2 data loaders (as each module is rebuilt per `docs/reviews/V2_REBUILD_PLAYBOOK.md`)
3. Redis + arq job queue, replacing the per-module JSON `JobStore`
4. OpenAPI-generated TypeScript client
5. Sentry + CI workflow
6. Docker Compose, only when deploying
