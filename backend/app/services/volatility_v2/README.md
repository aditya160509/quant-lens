# Quant360 Volatility V2 Backend / Frontend Contract

This package is the isolated backend service layer for Volatility Intelligence
V2. It mirrors the Factors V2 service shape: individual feature modules expose
`run(payload)`, the package exports stable per-feature runners, and the frontend
has one App Router page per feature.

The service remains **not wired** into `main.py` or a live HTTP API route in this
pass. The frontend pages are structural shells that use the Volatility custom
primitives and output books; they intentionally do not call an API handler yet.

## Current Status

- [x] Created `backend/app/services/volatility_v2`.
- [x] Added feature registry for 9 Volatility V2 features.
- [x] Added individual backend feature modules `feature_01.py` through `feature_09.py`.
- [x] Added `features/__init__.py` exports for `run_feature_01` through `run_feature_09`.
- [x] Added `VOLATILITY_V2_RUNNERS` and service-layer `run_feature(feature_id, payload)`.
- [x] Added read-only data loader for local OHLCV and category7 macro parquet.
- [x] Added append-only data pooling utilities for missing OHLCV and FRED macro fields.
- [x] Added explicit contract file listing required data and planned outputs per feature.
- [x] Added frontend App Router feature pages `feature-01/page.js` through `feature-09/page.js`.
- [x] Frontend pages pass `VOLATILITY_OUTPUT_BOOKS["XX"]` directly, so output keys match the custom primitives.
- [ ] HTTP API route and `main.py` integration are not wired in this pass.

## Feature Map

| ID | Feature | Data Required | Current Implementation |
|---|---|---|---|
| 01 | Multi-Estimator Daily Volatility Engine | Daily OHLCV | Implemented service module |
| 02 | GARCH Family Suite | Daily close returns | Implemented service module |
| 03 | HAR Forecasting Suite | Daily OHLCV, cross-sectional returns | Implemented service module |
| 04 | Volatility Regime Detection Engine | Daily OHLCV, VIX, rates | Implemented service module |
| 05 | Volatility Risk Premium Monitor | Daily OHLCV, VIX | Implemented service module |
| 06 | Cross-Asset Volatility Connectedness | Daily OHLCV panel | Implemented service module |
| 07 | Multivariate Volatility and DCC Engine | Daily OHLCV panel, optional weights | Implemented service module |
| 08 | Volatility Stress Testing Engine | Daily OHLCV panel, macro history | Implemented service module |
| 09 | Volatility Budget Monitor | Daily OHLCV panel, portfolio weights | Implemented service module |

## Local Data Inventory

Already present in this repo:

- `backend/data/market_universe.parquet`: daily OHLCV master universe used by Factors V2.
- `backend/data/fundamentals/master_fundamentals.parquet`: not required for Volatility V2 core, but useful for sector/asset metadata.
- `factors/data/processed/category7_macro_regime.parquet`: macro/rates/regime parquet used by Factors V2.
- `backend/data/parquet_cache/macro_VIX.parquet`, `macro_RATES.parquet`, `macro_YC_SLOPE.parquet`, `macro_CREDIT.parquet`: existing macro cache files.

Likely missing or needs verification before full Volatility V2:

- VIXCLS column inside `category7_macro_regime.parquet`.
- DGS2 and DGS10 columns inside `category7_macro_regime.parquet`.
- BAA/credit spread fields for stress analogs.
- Cross-asset benchmark OHLCV coverage for FX, commodities, BTC/ETH, and non-US indices.
- Portfolio weight payload persistence for Feature 09.

The spec explicitly avoids intraday data, options chains, SEC filings, or
proprietary feeds. Those are not required.

## Data Pooling Utilities

`core/data_pooling.py` provides operator functions only:

- `append_ohlcv_to_master(symbols, period="10y")`
- `append_macro_to_category7(series_ids=("VIXCLS", "DGS2", "DGS10", "BAA10Y"))`
- `missing_data_report(required_symbols)`

These functions append/deduplicate by key:

- OHLCV key: `Ticker, Date`
- Macro key: `date`

They do **not** blindly overwrite parquet files. If a parquet exists, new rows
are concatenated, deduplicated, sorted, and written back.

## Implementation Sequence

1. Verify data coverage using `missing_data_report`.
2. Append missing OHLCV symbols to `backend/data/market_universe.parquet`.
3. Append missing FRED series to `factors/data/processed/category7_macro_regime.parquet`.
4. Implement Feature 01 estimators first because Features 03-05 depend on its volatility series.
5. Implement Feature 02 after Feature 01 using close returns only.
6. Implement Features 03-05 after VIX/rates data is verified.
7. Implement Features 06-09 once cross-asset universe and optional portfolio weights are settled.
8. Wire API routes after the contract is reviewed.
9. Connect frontend `onRun` only after the API route is approved.

## API/Frontend Parity Plan

When ready, mirror the Factors V2 pattern:

- Backend services:
  - `backend/app/services/volatility_v2/core/*`
  - `backend/app/services/volatility_v2/features/feature_01.py` ... `feature_09.py`
  - `backend/app/services/volatility_v2/registry.py`
- Frontend:
  - `frontend/src/app/labs/volatility-v2/feature-01/page.js` ... `feature-09/page.js`
  - `frontend/src/components/volatility-v2/customPagePrimitives.jsx`
  - `frontend/src/components/volatility-v2/registry.js`

## Frontend Key Parity

Each frontend feature page imports both:

- `VolatilityV2Workbench`
- `VOLATILITY_OUTPUT_BOOKS`

and renders:

```jsx
<VolatilityV2Workbench
  featureId="XX"
  sections={VOLATILITY_OUTPUT_BOOKS["XX"]}
/>
```

This keeps the page-level output declarations locked to the custom primitive
renderer. If a section key changes, update `VOLATILITY_OUTPUT_BOOKS` first; the
route pages inherit it automatically.

## Important Constraint

Do not wire this into `main.py` yet. The service is safe to import and run
directly, and the frontend pages are safe to render as UI shells, but the live
API should remain unchanged until the Volatility V2 HTTP route contract is
reviewed.
