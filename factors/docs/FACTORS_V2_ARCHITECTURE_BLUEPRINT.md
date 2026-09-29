# FACTORS V2 Architecture Blueprint

## 1) Final decision (applied)

You chose Option A with changes:
- Keep `factors/` as standalone data + pipeline + documentation workspace.
- Remove `factors/features` from that workspace.
- Move runtime feature code into backend under:
  - `backend/app/services/factors_v2/`

This is now applied.

---

## 2) Current folder ownership model

## Runtime (used by app/API)
- `backend/app/services/factors_v2/`
- Contains feature compute logic and shared loaders/contracts.

## Data engineering + pipeline workspace
- `factors/`
- Contains:
  - raw data pulls (Fama/French/AQR)
  - processed datasets (Category 7 etc.)
  - pipeline scripts
  - architecture docs

This split keeps backend clean while preserving data reproducibility.

---

## 3) Factors V2 runtime structure

```text
backend/app/services/factors_v2/
  __init__.py
  core/
    data_loader.py
    contracts.py
  features/
    feature_01.py
    feature_02.py
    ...
    feature_14.py
  schemas/          # optional later if strict pydantic/jsonschema is added
  utils/            # optional shared helpers
```

### Per-feature file strategy
For now: **one file per feature** (`feature_xx.py`) with:
1. input parsing/validation,
2. compute logic,
3. output shaping.

This keeps it simple while feature logic is being built.

Later (optional), split each feature into `inputs.py`, `compute.py`, `outputs.py` if complexity grows.

---

## 4) Output schema standard (all features)

Every feature returns JSON-ready dict with exactly these keys:

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

### Why this schema
- Frontend can render any feature consistently.
- Easy to build generic UI blocks for cards/charts/tables.
- Supports partial availability (`status=warning`) when data is missing.

---

## 5) Where charts are created

Charts are **not** created in backend as images.

Backend returns chart **data payload** in `charts`.
Frontend page renders that payload using chart components.

So:
- Backend = numbers/series/labels.
- Frontend = visual rendering.

---

## 6) API strategy (when you are ready)

You said you do not want wiring until full features are built. Correct approach.

Recommended final API style:
- `POST /api/labs/factors/v2/feature/01/run`
- `POST /api/labs/factors/v2/feature/02/run`
- ...
- `POST /api/labs/factors/v2/feature/14/run`

All endpoints return the standard schema.

You can keep existing `frontend/src/lib/api.js` pattern and add v2 functions later.

---

## 7) Frontend strategy (later)

Recommended pages:
- `frontend/src/app/labs/factors-v2/page.js` (hub)
- `frontend/src/app/labs/factors-v2/feature-01/page.js`
- ...
- `feature-14/page.js`

These pages will call v2 endpoints and render standardized payload.

---

## 8) Data categories and locations

## Category 1: Daily OHLCV prices
- Source store: `backend/data/prices/*.parquet`
- Universe panel: `backend/data/market_universe.parquet`

## Category 2: Benchmark returns
- Required set (spec): `SPY`, `URTH`, `EEM`, `VEA`
- Current: all present except `URTH` (to be pulled)

## Category 3: Fundamentals (non-point-in-time)
- `backend/data/fundamentals/master_fundamentals.parquet`
- Coverage is high but not perfect; use `status=warning` and note missing tickers.

## Category 4: Fama/French prebuilt factors
- `factors/data/raw/fama_french/` (downloaded and extracted)

## Category 5: AQR factors
- Real Excel files downloaded:
  - `Betting-Against-Beta-Equity-Factors-Daily.xlsx`
  - `The-Devil-in-HMLs-Details-Factors-Daily.xlsx`
  - `Quality-Minus-Junk-Factors-Monthly.xlsx`
- Converted CSV tabs:
  - `factors/data/processed/aqr_csv/`

Note: old files named `aqr_*.xlsx` are HTML landing pages and should be ignored.

## Category 6: RF
- Available in Fama/French files (`RF` column)

## Category 7: Macro/regime (FRED)
- Pipeline: `factors/pipelines/pull_category7_macro.py`
- Output:
  - `factors/data/processed/category7_macro_regime.parquet`
  - `factors/data/processed/category7_macro_regime.csv`

## Category 8: Sector/industry
- From fundamentals parquet (`sector`, `industry`)
- Coverage is strong but not 100%; apply fallback and warnings.

## Category 10: FX
- Stored in `backend/data/prices` as `XXXUSD=X` style series.

## Category 11: Roll spread approximation
- Derived metric from Category 1 daily returns.

---

## 9) Feature-by-feature data dependency map

## Feature 01 Valuation Spread Monitor
Needs: C1, C3, C8
Returns: spread cards, percentile timeseries, sector contribution table

## Feature 02 Exposure Decomposition
Needs: C1, C2, C3, C4/C5, C8, C10
Returns: exposure bars, active exposures, holdings contribution

## Feature 03 Attribution
Needs: C1, C2, C4/C5, C8
Returns: waterfall, contribution table, rolling attribution panels

## Feature 04 Regime Analysis
Needs: C1, C4/C5, C7
Returns: regime probabilities, conditional return heatmaps, transition matrix

## Feature 05 Alpha Decay / Half-life
Needs: C1, C3, C4/C5
Returns: IC decay curves, half-life tables, model comparison

## Feature 06 Crowding
Needs: C1, C3, C11
Returns: composite score, metric radar, crash probability table

## Feature 07 Backtesting Engine
Needs: C1, C2, C3, C11, C10 (global)
Returns: equity curves, stats, turnover/cost decomposition

## Feature 08 Covariance / Risk
Needs: C1, C4/C5
Returns: covariance/correlation heatmaps, eigen diagnostics

## Feature 09 Capacity
Needs: C1, C11
Returns: AUM-capacity curve, slippage diagnostics

## Feature 10 Optimizer
Needs: C1, C4/C5, Feature08 outputs
Returns: frontier, weights, risk budget, binding constraints

## Feature 11 Stress Testing
Needs: C1, C4/C5, C7
Returns: scenario PnL, reverse stress vector, contagion response

## Feature 12 Factor DNA
Needs: C1, C3, C4, C5, C6, C8
Returns: DNA radar, regime DNA, correlation fingerprint, classifier output

## Feature 13 Live Signal Monitor
Needs: C1, C3, C6
Returns: health dashboard, drift/break alerts, recovery tracker

## Feature 14 Allocator Report
Needs: Features 02/03/06/07/09/11/13 outputs
Returns: report sections payload + export-ready structured blocks

---

## 10) Migration checklist (safe path)

1. Keep old factors routes/UI untouched.
2. Build each v2 feature file in backend service first.
3. Validate outputs locally against schema.
4. Add v2 router only when multiple features are ready.
5. Add frontend `factors-v2` pages after backend responses are stable.
6. Migrate one feature at a time from old to v2.
7. Decommission old code only after parity checks pass.

---

## 11) What to do with current files now

Keep:
- `factors/pipelines/*`
- `factors/data/raw/*`
- `factors/data/processed/*`
- `factors/docs/*`
- `backend/app/services/factors_v2/*`

Ignore/deprecate for compute:
- HTML masquerading AQR files:
  - `aqr_betting_against_beta.xlsx`
  - `aqr_data_library_global_style_premia.xlsx`
  - `aqr_devil_in_hml_details.xlsx`
  - `aqr_quality_minus_junk.xlsx`

Use instead:
- Real downloaded AQR files and converted CSV tabs.

---

## 12) Final implementation convention

- One feature = one `feature_xx.py` file for now.
- Each feature exposes:
  - `run(payload: dict) -> dict`
- Output must follow common schema.
- Any missing data should not crash the endpoint:
  - set `status="warning"`
  - add clear `alerts` entries.

This gives stable frontend behavior while data coverage is still being completed.
