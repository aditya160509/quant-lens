# Backend RAM: floor, causes and plan

Date: 2026-10-05. Measured: ML V2 peak RSS was 3.2 GB and is 1.4 GB after the symbol-only load (30 tickers, 756 sessions). Every other number here is an estimate; profile before claiming it.

## 1. What the data needs (arithmetic)

| What | Size |
|---|---|
| All daily data: 10.8M rows × OHLCV, float32 | about 220 MB |
| Close only, 4,157 tickers | about 45 MB |
| Typical run: 30 tickers × 756 days × 20 features | about 2 MB |
| Big run: 4,000 tickers × 20 years, close only | about 20 MB |

The data is small. Most of the RAM goes to libraries, copies and processes.

## 2. Floor today: Python plus libraries (rough)

| Piece | RAM |
|---|---|
| Python + numpy + pandas + FastAPI | 80–120 MB |
| polars | +30–50 MB |
| sklearn / scipy / statsmodels | +60–100 MB |
| LightGBM / XGBoost / CatBoost | +50–150 MB |
| shap | +50–100 MB |
| torch (F12 only) | +300–600 MB |
| arch, hmmlearn, optuna | +30–60 MB |

| Module | Idle floor | Typical-run floor |
|---|---|---|
| Screener / Factors | about 120 MB | 150–200 MB |
| Research V2 | about 150 MB | 200–300 MB |
| Portfolio / Vol | about 150 MB | 200–250 MB |
| PCA V2 | about 150 MB | 200–250 MB |
| ML V2 F01–F11 | about 250 MB | 300–450 MB |
| ML V2 F12 | about 600 MB | 0.7–1 GB |

## 3. Why it is high now

1. Heavy libraries imported eagerly at startup (torch, shap, the boosting libraries): 0.6–1 GB before any request.
2. Spawned worker processes each re-import the libraries (150–600 MB each), and joblib/loky keeps idle pools.
3. Data loaded too wide: whole parquet files or all tickers, then filtered. Fixed for ML V2.
4. pandas float64 plus a copy per step (pivot, rank, merge), so a peak holds 3–10 copies.
5. Python rarely returns memory to the OS, so the process stays at its high-water mark.
6. Caches, job stores and large result payloads (F07 and F10 results are about 3 MB each, with duplicated data).
7. Several processes at once: the Next.js dev server (0.5–1.5 GB), the backend and the workers.

## 4. Going below the Python floor

| Technique | Effect |
|---|---|
| Scale-to-zero workers: they start per job and exit | Idle compute about 0 MB |
| Thin API (minimal Python about 40 MB, or Rust/Go 10–30 MB) that does no math | Small always-on footprint |
| Precompute and cache common results | Most requests become a file read |
| Memory-mapped Arrow/parquet via polars or DuckDB | Data pages are shared and freeable |
| Streaming or chunked panels (polars/DuckDB) | Peak bounded by chunk size |
| ONNX Runtime for F12 inference (train offline with torch) | 30–60 MB instead of 300–600 MB |
| LightGBM only; `pred_contrib` instead of the shap package | Saves 200–400 MB |
| float32, numpy in hot loops, in-place operations | Peak 2–5× lower |
| jemalloc/mimalloc, recycle workers after N jobs | Removes the high-water-mark effect |

Hard limits: about 40 MB of interpreter and numpy while a job runs; the calculation's working set (for example, a 4,000 × 4,000 covariance matrix is 64 MB in float32); training memory for boosting, HMM and torch.

| Setup | Idle | Typical run |
|---|---|---|
| Now (ML V2) | about 1.4 GB measured peak | — |
| Lazy imports + one recycled worker | about 150 MB | 300–450 MB |
| + LightGBM only, no shap, ONNX F12, float32, streaming | about 100 MB | 150–250 MB |
| Thin API + short-lived workers + cache | 10–40 MB | 150–250 MB, only during a job |

## 5. Plan (in order; measure idle and peak RSS before and after each step)

| # | Step | Size | Expected gain |
|---|---|---|---|
| 1 | Profile idle and peak RSS per module (a script that runs one feature per module and records RSS) | S | Real numbers to replace the estimates |
| 2 | Lazy imports: torch, shap, the boosting libraries, statsmodels and arch inside the functions that use them, not at module top | S | 0.5–1 GB idle |
| 3 | One job worker, `max_tasks_per_child` recycling; shut down joblib/loky pools after each job | S | Frees the high-water mark and idle pools |
| 4 | LightGBM-only path (make XGBoost/CatBoost optional); SHAP via LightGBM `pred_contrib` | M | 200–400 MB in ML V2 |
| 5 | float32 panels, polars lazy scans with column and ticker pushdown in every module | M | Peak 2–5× lower |
| 6 | Stop duplicating chart and table data in results (F07, F10) | S | Smaller results and job store |
| 7 | Frontend production build (`next build && next start`) for daily use | S | Saves 0.5–1 GB versus the dev server |
| 8 | Optional, only for paid hosting: thin API, scale-to-zero workers, result cache, ONNX for F12 | L | Idle 10–40 MB |

Steps 2, 3 and 7 give most of the gain for little code. Do them first.

Related: the memory notes in `backend/app/services/research_v2/WORK_LEFT.md`.
