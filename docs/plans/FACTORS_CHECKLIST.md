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

---

# Section: PCA (statistical factors), merged 2026-11-17

PCA is now a section of the Factors lab, not a separate lab. Its full list moved here unchanged; the spec is still the [PCA review](../reviews/product/PCA_V2_PRODUCT_REVIEW.md). The 33 correctness fixes still land before any PCA screen.

### PCA: Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. Axioma, Barra and Bloomberg PORT set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank
- Every result prints its limits: complete-case window shrinkage, survivorship on the default universe, in-sample residuals, raw continuous futures
- Nothing was run for the review; every fix is checked against the real endpoint before it is ticked
- Nothing is capped silently

### PCA: Batch 1: Correctness, labels and quick fixes

Review Batch A, easy items. E18 M0 H0

- [ ] `E` H22: PDF analogue key `distance` becomes `mahalanobis_distance`
- [ ] `E` H13: catch the per-ticker `ou_mle` failure in F04 and record it in the result
- [ ] `E` H14: compute residual correlation once in the F04 heatmap
- [ ] `E` H23: rename `marginal_risk_contribution` to risk contribution; keep the formula
- [ ] `E` H5: rename the Bai-Perron table to mean-break segmentation
- [ ] `E` H4: rename "Statistically Robust" to "Stable (rule)"; show the two numbers
- [ ] `E` H8: rename `economically_viable` to half-life check, or compare to cost
- [ ] `E` H9: remove `breakeven_z`
- [ ] `E` H10: rename `days_since_signal_trigger`
- [ ] `E` H11: hit rate per active day and per trade
- [ ] `E` H7: use the selected K for principal angles
- [ ] `E` H28, H29: label LaVaR as heuristic; rename `current_amihud` to `current_illiquidity`
- [ ] `E` H35, H34: remove duplicate outputs and the 60-record tensor core; keep the singular values
- [ ] `E` H36, H37: remove unread Advanced inputs; keep one name for K
- [ ] `E` H39, H40: delete dead helpers (graph and import check first, per `AGENTS.md`)
- [ ] `E` H38, H41: fix docs drift in README and DONE, and the test count
- [ ] `E` H21: label the centred analog window, or make it past-only
- [ ] `E` H24: label rolling per-PC stacks as window-specific, or cut

### PCA: Batch 2: Correctness, numbers and decisions

Review Batch A, medium and hard items. E0 M12 H3

- [ ] `M` H6: CUSUM flags the global test and argmax only
- [ ] `M` H12: net exposure and beta in F04 stats; a dollar-neutral mode
- [ ] `M` H17: apply `max_weight` in long-short mode
- [ ] `M` H18: annualise consistently in the robust frontier; rename it
- [ ] `M` H15: use the cleaned covariance in the rolling backtest, or relabel it
- [ ] `M` H16: show the historical-mean caveat; add a shrunk-mean option
- [ ] `M` H19: stop mutating the model; count K candidates as trials
- [ ] `M` H20: drop the parametric claim; add a Student-t option to stress Monte Carlo
- [ ] `M` H27: average the VaR decomposition over a band around the quantile, or cut the waterfall
- [ ] `M` H33: one event ledger file used by F05, F08 and cross-asset
- [ ] `M` H31: check the statsmodels `cov_hac` contract with a known OLS case (test); unverified until run
- [ ] `M` H32: label or drop the crypto MP adjustment
- [ ] `H` H1: decide the MP reference matrix (sample or shrunk) and recompute golden fixtures; owner decision needed; size of the effect unverified
- [ ] `H` H2: keep or replace the sigma-squared fit; add uncertainty if kept
- [ ] `H` H3: recalibrate the under-specification test (MP edge at actual N and window, or a bootstrap null); owner decision needed on the null

### PCA: Batch 3: Data path

Review Batch B. E0 M4 H1

- [ ] `M` Remove the runtime dependency on `research_exports` for hourly data: copy the file to `backend/data` with its own check, or make hourly optional (`research_exports/` itself is never cleaned up)
- [ ] `M` Print the complete-case window shrinkage on the result card (limits on every result)
- [ ] `M` Mark survivorship on default-universe results
- [ ] `M` Add USDTRY and USDCNH, or print them as missing in F10 coverage
- [ ] `H` F10 roll-adjusted futures, or label raw continuous in every F10 view

### PCA: Batch 4: Workspace

Review Batch C, shell. E2 M2 H0

- [ ] `E` `/pca` from the manifest on `LabConfig`; forms from `INPUTS`, grouped (Study; Advanced hidden)
- [ ] `E` States: run, loading, error, empty, stale, with run id
- [ ] `M` Symbol search replaced by the global search, not substring (reuse the Screener search, Batch 3 there)
- [ ] `M` Reuse: `Exhibit`, `KpiStrip`, `DataTable v2` and `tableView`, `QuickLook` and `FilterChips` from `frontend/src/kit/` and Screener; universe picker and saved Screener universes. No new per-module primitives

### PCA: Batch 5: Pages

Review Batch C, exhibits. Lead with F04, F03 and F08. E0 M12 H0

- [ ] `M` Spectrum with MP density and K selector, K by clicking the spectrum, MP edge, variance threshold and Kaiser rule drawn (F01, idea 10)
- [ ] `M` Biplot with loadings and scores, colour by cos2 (F02)
- [ ] `M` Loading heatmap sorted by sector (F02)
- [ ] `M` Risk stacked bars with component and tail views (F03)
- [ ] `M` Residual z-score and half-life scatter, trade list with evidence (F04)
- [ ] `M` Spread with z bands and entry and exit markers for one selected name (F04)
- [ ] `M` Regime monitor: PC1 share with percentile bands and the CUSUM global flag (F05)
- [ ] `M` Optimiser frontier curve with max-Sharpe and min-variance markers (F06)
- [ ] `M` Bootstrap bands and cosine table with rule labels (F07)
- [ ] `M` Stress P&L heatmap and worst-day replay (F09)
- [ ] `M` Residual contagion by group and pairs on the recalibrated test (F08; depends on H3)
- [ ] `M` Residual signal or regime flag as a Screener filter, and a Screener universe into PCA (idea 7)

### PCA: Batch 6: Freedom

Review Batch C, freedom. E0 M6 H0

- [ ] `M` Views switch (table, heatmap, line, bar, scatter) and per-PC focus (ideas 1 and 2)
- [ ] `M` Explain-this-number footers: formula, window, observation count, estimator (idea 3)
- [ ] `M` Export CSV, JSON, PNG and PDF with the run id (idea 9; H22 first)
- [ ] `M` Run ledger and diff of two runs (idea 4)
- [ ] `M` Sensitivity panel over K, window and estimator; every variant logs to the trial ledger (idea 5; Research store, decision 4)
- [ ] `M` Compare two as-of dates: loadings, PC shares and residual signals side by side (idea 11)

### PCA: Batch 7: Validate and monitor

Review Batch D. E0 M3 H0

- [ ] `M` Stat-arb trade list hand-off to Validate: deflated Sharpe, PBO on the K and window grid
- [ ] `M` Contagion alerts, and alerts on PC1 share, principal angle and residual correlation, each with precision after the fact (idea 8; reuse the Screener scheduler and alerts)
- [ ] `M` Scheduled re-run through the Studio job store (already used)

### PCA: Batch 8: Ship

E1 M1 H0

- [ ] `M` Playwright test on the page with the backend up, and baseline screenshots at 375 and 1440
- [ ] `E` Tag `pca-v1`

### PCA: Later: free data

Review Batch E; tags as in the review. E0 M0 H4

- [ ] `H` F10 cross-asset page, after the data path is fixed
- [ ] `H` F11 liquidity page, after LaVaR and unwind calibration
- [ ] `H` HRP through skfolio, after a spike
- [ ] `H` Student-t stress and fat-tailed covariance

### PCA: Later: paid data

Review Batch E; both need data we do not hold. E0 M0 H2

- [ ] `H` Fundamental factor model (needs point-in-time data)
- [ ] `H` Attribution over time (needs holdings history)
