# Factors Architecture and Migration Guide

## Current live system (what runs today)

## Backend engine
- Primary compute service: `/Users/adityabalaji/Downloads/quant  2/backend/app/services/factors_intelligence.py`
- This service computes factor outputs and returns structured payloads (JSON-ready dicts).

## Frontend factors UI
- Main page: `/Users/adityabalaji/Downloads/quant  2/frontend/src/app/labs/factors/page.js`
- Related labs pages: `frontend/src/app/labs/factors/*`
- Frontend API calls are in: `/Users/adityabalaji/Downloads/quant  2/frontend/src/lib/api.js`
  - Examples:
    - `/labs/factors`
    - `/labs/factors/intelligence/run`
    - `/labs/factors/backtest`
    - `/labs/factors/regimes`

Conclusion: Yes, current pattern is `compute in backend -> return JSON -> render in frontend`.

---

## New factors module (14-feature architecture)

Top-level module:
- `/Users/adityabalaji/Downloads/quant  2/factors`

Folders:
- `config/` settings and constants
- `core/` shared data loaders and common models
- `pipelines/` data ingestion and normalization jobs
- `data/raw/` source files (Fama-French, AQR, etc.)
- `data/processed/` normalized parquet/csv ready for features
- `features/feature_01 ... feature_14/` per-feature compute files
- `api/` route layer to expose feature outputs to frontend
- `docs/` operational docs and migration notes

### Per-feature contract (planned)
Each `feature_xx.py` should:
1. accept input payload (filters, dates, params),
2. load required processed data via `core/data_loader.py`,
3. compute feature outputs,
4. return JSON payload with explicit sections:
   - `summary_cards`
   - `charts`
   - `tables`
   - `alerts`

Frontend then renders those sections directly.

---

## Cleanup completed
- Removed all `test_feature_*.py` from `factors/features/*`.
- Removed duplicate `feature_*_placeholder.py` files from `factors/scripts/`.
- Kept only the useful script:
  - `/Users/adityabalaji/Downloads/quant  2/factors/scripts/download_factor_libraries.py`

---

## Category 7 status
Pipeline implemented and run:
- Script: `/Users/adityabalaji/Downloads/quant  2/factors/pipelines/pull_category7_macro.py`
- Output:
  - `/Users/adityabalaji/Downloads/quant  2/factors/data/processed/category7_macro_regime.parquet`
  - `/Users/adityabalaji/Downloads/quant  2/factors/data/processed/category7_macro_regime.csv`

Series included:
- VIXCLS, DGS2, DGS10, FEDFUNDS, CPIAUCSL

---

## Category 8 status (equity sector/industry mapping)
Using `market_universe.parquet` + `master_fundamentals.parquet` with ticker normalization (`.` <-> `_`):
- Equity universe: 4002 tickers
- Covered with fundamentals: 3764 (~94.05%)
- Sector populated: 3762 (~94.0%)
- Industry populated: 3762 (~94.0%)

This is strong but not 100% complete.

---

## AQR format status (important)
Current files in `factors/data/raw/aqr/*.xlsx` are not real Excel files.
They are HTML landing pages saved with `.xlsx` names.

Verified by file signature:
- `<!doctype html>` at top
- `file` command reports HTML text

Implication:
- These files cannot be used directly for factor computations.

What is needed next:
1. Update downloader to resolve direct dataset file URLs from AQR pages.
2. Download actual `.xlsx`/`.csv` data files.
3. Convert those real files into normalized `factors/data/processed/aqr_csv/` or parquet.

Until then, Fama-French is production-ready; AQR is not yet data-ready.

---

## Answer to your core design question
Yes, your understanding is correct:
- each of the 14 features should compute in backend,
- each returns structured outputs,
- frontend consumes those outputs and renders feature-specific UI.

This is exactly how your current factors system already works conceptually, and the new module should follow the same pattern with cleaner separation.
