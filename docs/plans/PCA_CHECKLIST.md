# PCA checklist

Open-source picks for every batch: [Open source stack](../references/2026-11-open-source.md). PCA review section 9 adds skfolio (adopt after a spike), Riskfolio-Lib (test oracle only) and Typst.

Tick PCA items here only. Spec: [product review](../reviews/product/PCA_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 5](PLAN.md). Merge decisions: [merge map section 8](../architecture/CROSS_MODULE_MERGE_MAP.md). H numbers are the review's code findings (section 6.2); "idea" numbers are its section 8. Items marked "reuse" use a Screener or kit piece that already exists.

This is the one list of everything to build. The review stays the spec and has no ticks. Batches 1 and 2 are the review's Batch A: 33 correctness fixes that land before any PCA page, because the page would otherwise show wrong numbers.

Tags: `E` easy, under half a day. `M` medium, one to three days. `H` hard, more than three days or needs a decision. Work batches in order; within a batch, top to bottom.

## Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. Axioma, Barra and Bloomberg PORT set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank
- Every result prints its limits: complete-case window shrinkage, survivorship on the default universe, in-sample residuals, raw continuous futures
- Nothing was run for the review; every fix is checked against the real endpoint before it is ticked
- Nothing is capped silently

## Batch 1: Correctness, labels and quick fixes

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

## Batch 2: Correctness, numbers and decisions

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

## Batch 3: Data path

Review Batch B. E0 M4 H1

- [ ] `M` Remove the runtime dependency on `research_exports` for hourly data: copy the file to `backend/data` with its own check, or make hourly optional (`research_exports/` itself is never cleaned up)
- [ ] `M` Print the complete-case window shrinkage on the result card (limits on every result)
- [ ] `M` Mark survivorship on default-universe results
- [ ] `M` Add USDTRY and USDCNH, or print them as missing in F10 coverage
- [ ] `H` F10 roll-adjusted futures, or label raw continuous in every F10 view

## Batch 4: Workspace

Review Batch C, shell. E2 M2 H0

- [ ] `E` `/pca` from the manifest on `LabConfig`; forms from `INPUTS`, grouped (Study; Advanced hidden)
- [ ] `E` States: run, loading, error, empty, stale, with run id
- [ ] `M` Symbol search replaced by the global search, not substring (reuse the Screener search, Batch 3 there)
- [ ] `M` Reuse: `Exhibit`, `KpiStrip`, `DataTable v2` and `tableView`, `QuickLook` and `FilterChips` from `frontend/src/kit/` and Screener; universe picker and saved Screener universes. No new per-module primitives

## Batch 5: Pages

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

## Batch 6: Freedom

Review Batch C, freedom. E0 M6 H0

- [ ] `M` Views switch (table, heatmap, line, bar, scatter) and per-PC focus (ideas 1 and 2)
- [ ] `M` Explain-this-number footers: formula, window, observation count, estimator (idea 3)
- [ ] `M` Export CSV, JSON, PNG and PDF with the run id (idea 9; H22 first)
- [ ] `M` Run ledger and diff of two runs (idea 4)
- [ ] `M` Sensitivity panel over K, window and estimator; every variant logs to the trial ledger (idea 5; Research store, decision 4)
- [ ] `M` Compare two as-of dates: loadings, PC shares and residual signals side by side (idea 11)

## Batch 7: Validate and monitor

Review Batch D. E0 M3 H0

- [ ] `M` Stat-arb trade list hand-off to Validate: deflated Sharpe, PBO on the K and window grid
- [ ] `M` Contagion alerts, and alerts on PC1 share, principal angle and residual correlation, each with precision after the fact (idea 8; reuse the Screener scheduler and alerts)
- [ ] `M` Scheduled re-run through the Studio job store (already used)

## Batch 8: Ship

E1 M1 H0

- [ ] `M` Playwright test on the page with the backend up, and baseline screenshots at 375 and 1440
- [ ] `E` Tag `pca-v1`

## Later: free data

Review Batch E; tags as in the review. E0 M0 H4

- [ ] `H` F10 cross-asset page, after the data path is fixed
- [ ] `H` F11 liquidity page, after LaVaR and unwind calibration
- [ ] `H` HRP through skfolio, after a spike
- [ ] `H` Student-t stress and fat-tailed covariance

## Later: paid data

Review Batch E; both need data we do not hold. E0 M0 H2

- [ ] `H` Fundamental factor model (needs point-in-time data)
- [ ] `H` Attribution over time (needs holdings history)
