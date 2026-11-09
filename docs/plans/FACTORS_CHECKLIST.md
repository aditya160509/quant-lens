# Factors checklist

Open-source picks for every batch: [Open source stack](../references/2026-11-open-source.md).

Tick Factors items here only. Spec: [product review](../reviews/product/FACTORS_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 3](PLAN.md). Merge decisions: [merge map section 8](../architecture/CROSS_MODULE_MERGE_MAP.md). F numbers are the review's feature ids; "idea" numbers are its section 5.

This is the one list of everything to build. The review stays the spec and has no ticks. Items marked "reuse" use a Screener or kit piece that already exists; they add no new component.

Tags: `E` easy, up to a few hours. `M` medium, about a session. `H` hard, several sessions or real risk. Work batches in order; within a batch, top to bottom.

## Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. Portfolio123, Barra and Axioma set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank
- Every result prints its limits: 90-day statement lag, survivorship, 2021+ statements
- Factors is a factor lab that shows its limits; it is not sold as a Barra replacement
- Output correctness of every feature is unverified in the review; each page batch ends with a run against the real endpoint
- Nothing is capped silently

## Batch 1: Clean

Correctness and honest labels before any page. E4 M1 H0

- [ ] `E` F05 half-life formulas: exponential `ln2/b`, hyperbolic `1/b` (code adds 1 and 2); add one assert-based check on a known curve
- [ ] `E` Rename the F06 registry title (`core/contracts.py:60`, "Factor Crowding Monitor") and labels to "concentration and liquidity"; rename F14 "Crowding Disclosure" and drop "crowding controls"
- [ ] `E` F01 alert text: say "70th percentile", not "upper historical tail"
- [ ] `E` Remove dead `_ALMGREN_ETA`, `_SQRT_MODEL_THRESHOLD_USD`, `_empty_quintile_rows`, `_rolling_premium_spread` (grep: defined, never called); smoke-test before deleting, per AGENTS
- [ ] `E` F11: remove the `locals().get(...)` pattern; name the default exposures (1/N) and shocks (-2 sigma) in `meta`
- [ ] `E` Remove the sine sparkline (`customPagePrimitives.jsx`; carried from the prior review, not re-read, and the file may be gone after the frontend removal)
- [ ] `E` Per-field help written in `features/inputs.py`, replacing the shared sentence (idea 3)
- [ ] `E` F06 output labels renamed "concentration and liquidity"; F11 `hedging_recommendation` label renamed to what the code does
- [ ] `E` Look-ahead audit (PLAN 3.1; not in the review's checklist); include F04 conditional returns, where the regime label uses the same-day return (verify with a one-day lag first)
- [ ] `E` F08: label the EWMA DCC as not the Volatility DCC (`core/dcc.py`)
- [ ] `M` Data banner on every result and in the PDF: survivorship, 90-day lag, 2021+ statements (idea 6)

## Batch 2: Workspace

`/factors` on the shared kit, forms from the manifest. E2 M2 H0

- [ ] `M` `/factors` workspace from `GET /features`, five pages, on `LabConfig`
- [ ] `E` Reuse: `Exhibit`, `KpiStrip`, `DataTable v2` and `tableView` from `frontend/src/kit/`; no new per-module primitives
- [ ] `E` Reuse: `QuickLook` for any ticker; `FilterChips` for universe and factor filters; the Screener universe picker
- [ ] `M` Shared loader for Factors; Fama-French date-range check; AQR verification (merge map decision 16)

## Batch 3: Value and exposure

F01 and F02, with F03 and F12 as tabs. E0 M1 H0

- [ ] `M` Value and exposure page (F01, F02; tabs F03, F12): holdings beside benchmark, DNA with units, bottleneck exposure named

## Batch 4: Regime and timing

F04 and F05, with F06 as a tab. E0 M1 H0

- [ ] `M` Regime and timing page (F04, F05; tab F06): regime pill, decay curves, half-life with interval and the published decay warning. Regime kernel comes from Volatility (merge map decision 7)

## Batch 5: Test and capacity

F07 and F09. E0 M2 H0

- [ ] `M` Test and capacity page (F07, F09) on the shared execution kernel (merge map step 5); NAV matches the old run within tolerance
- [ ] `M` F09 capacity: calibrated impact constants (now fixed at `_ALMGREN_ETA = 0.1`), capacity sweep and break-even cost

## Batch 6: Risk and construction

F08, F10 and F11 as lenses on shared engines. E0 M0 H1

- [ ] `M` F10: expected returns explicit or shrunk by default (today the in-sample factor mean, `feature_10.py`); print the default used; one out-of-sample check on weights
- [ ] `H` Risk and construction page (F08, F10, F11) on the shared covariance and construction engines (Portfolio owns covariance, decision 3; DCC is Volatility's, decision 14; merge map steps 6 and 8). One engine serves Factors and Portfolio. Drop the empty `hedging_recommendation` table until an instrument map exists

## Batch 7: Monitor

F13 and F14. E0 M0 H1

- [ ] `H` Monitor page: scheduler, delivery and matured hit rate for F13. Reuse the Screener scheduler and alerts (Batch 9) and the alert precision scoreboard

## Batch 8: Validate

E0 M1 H0

- [ ] `M` Validate hand-off from F07 with the trial count; every changed input counts as a trial and feeds the deflated Sharpe, shown beside the result (idea 4; Research store owns the ledger, decision 4)

## Batch 9: Freedom

E1 M2 H1

- [ ] `H` Custom factor upload: any column becomes a factor through F01, F05 and F07; it joins the trial count. Includes any subset of factors and a custom benchmark (ideas 1 and 2)
- [ ] `M` Saved recipes and run compare: a full payload saved as a named, shareable file; any two runs side by side, differences highlighted (ideas 5 and 7)
- [ ] `M` Stored ranking systems and a benchmark-relative tear sheet (parity gaps in review section 3; reuse the Screener Rank weights)
- [ ] `E` CSV export beside the PDF, and JSON with the payload and `source_versions` attached (idea 8)

## Batch 10: Ship

E1 M1 H0

- [ ] `M` Verified pages, phone layout, accessibility pass and visual baselines (PLAN recipe stage 6)
- [ ] `E` Ship, tag `factors-v1`

## Later: free data

Tags set here; the review does not split free from paid. E0 M0 H1

- [ ] `H` Non-US factor sets

## Later: paid data

Tags set here; the review gives none. E0 M0 H5

- [ ] `H` Ownership-based crowding (F06 has no ownership, short-interest, 13F or flow data)
- [ ] `H` Stock-level specific risk
- [ ] `H` Full revaluation, macro and climate stress; real hedges for F11 need an instrument map
- [ ] `H` Real-time monitoring
- [ ] `H` Long point-in-time fundamentals (Portfolio123 parity gap)
