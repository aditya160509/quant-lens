# Quant Lens

Quant research platform: Next.js frontend, FastAPI backend, local parquet data.

```bash
scripts/dev.sh
```

Frontend: http://127.0.0.1:3000. Backend: http://127.0.0.1:8000/api/docs.

| Path | Holds |
|---|---|
| `frontend/src/modules` | Current lab apps (ML, Research) |
| `frontend/src/charts` | Chart kit |
| `frontend/src/workspace` | Lab workspace engine |
| `backend/app/services/*_v2` | Module engines |
| `backend/data`, `factors/data`, `data` | Local datasets, not in git |
| `docs` | Start at `docs/PLAN.md` |

Backend setup: `cd backend && uv sync`. Tests: `uv run pytest`.
