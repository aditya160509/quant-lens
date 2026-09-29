# Research V2 Implementation Checklist

## Completed In This Pass

- [x] Created `backend/app/services/research_v2/` with `core`, `features`, `fetchers`, `schemas`, and `utils` folders.
- [x] Added package exports in `__init__.py`.
- [x] Added `registry.py` with manifest and `run_feature()` dispatch for features 01-09 and 11.
- [x] Added read-only `core/data_loader.py`.
- [x] Uses `backend/data/market_universe.parquet` as the primary daily OHLCV source.
- [x] Falls back to the research export market universe parquet when needed.
- [x] Reads `backend/data/fundamentals/master_fundamentals.parquet`.
- [x] Reads Ken French FF5 and momentum CSVs when present.
- [x] Reads category7 macro/regime parquet and `backend/data/parquet_cache/macro_*.parquet`.
- [x] Added append-only FRED and public-market proxy fetch helpers under `fetchers/fetch_missing_data.py`.
- [x] Fetcher appends public macro data into the existing category7 macro/regime parquet, not a duplicate research-only parquet.
- [x] Fetcher appends public market proxies into the existing `backend/data/market_universe.parquet`, not a duplicate research-only parquet.
- [x] Added server-side CSV/parquet upload readers for signal ranks, event/treatment files, and external instruments.
- [x] Exposed `signal_csv_path` input across signal-driven research features.
- [x] Exposed `event_csv_path` and `instrument_csv_path` on Feature 07.
- [x] Added Pydantic request/response schemas under `schemas/`.
- [x] Added a compact direct Research V2 smoke runner at `smoke_test.py`.

## Feature Files

- [x] Feature 01, Canonical Test Engine.
- [x] Feature 02, Robustness Engine.
- [x] Feature 03, Placebo and Falsification Suite.
- [x] Feature 04, Regime Conditional Analyzer.
- [x] Feature 05, Diagnostic Center.
- [x] Feature 06, Specification Builder and Publication Output.
- [x] Feature 07, Causal Identification Engine.
- [x] Feature 08, Signal Decay and Arbitrage Clock.
- [x] Feature 09, Synthetic Control Engine.
- [x] Feature 11, Cross-Sectional Dependence and Factor Zoo Positioning Engine.
- [x] Feature 10 intentionally not created because the supplied specification does not define a Feature 10.
- [x] Audited every feature file against runtime analytics output. All declared `OUTPUTS` keys now resolve from `charts` or `tables` at runtime.
- [x] Feature files are wired as real runners into `core.analytics`; no feature file is a placeholder-only stub.

## Implemented Output Coverage

- [x] Fama-MacBeth regression table.
- [x] Panel OLS table.
- [x] Panel OLS now supports none, time, asset, and two-way fixed-effect demeaning with a Hausman-style comparison p-value.
- [x] Panel OLS now reports a genuine `linearmodels` kernel Driscoll-Kraay covariance estimate and two-way clustered covariance when estimable, with a labelled statsmodels HAC fallback only for malformed/sparse panels.
- [x] Single portfolio sort table.
- [x] Double sort matrix.
- [x] Fama-MacBeth now supports configured controls through the shared panel engine.
- [x] Full control menu expanded to size, value, momentum, reversal, beta, idiosyncratic volatility, asset growth, profitability, and leverage.
- [x] Portfolio sorts now support equal-weight, value-weight, and rank-weight schemes.
- [x] Rebalancing frequency options added for daily, weekly, monthly, and quarterly panel construction.
- [x] User-defined benchmark tickers are supported for calendar-time alpha, GRS and spanning style tests.
- [x] Double sort now supports a user-selectable second signal and fixes the low-volatility lookahead bug by shifting rolling volatility.
- [x] GRS output upgraded to finite-sample GRS-style F statistic with factor mean/covariance adjustment and p-value.
- [x] Factor spanning table.
- [x] Patton-Timmermann-style monotonicity bootstrap proxy.
- [x] Rolling coefficient chart.
- [x] Calendar-time portfolio alpha and cumulative long-short series added to Feature 01.
- [x] FM validity flag.
- [x] Weak identification card.
- [x] GMM vs Shanken comparison panel now uses identity-weighted one-step time-series moment estimation for Fama-MacBeth lambdas and a factor-covariance-derived Shanken multiplier.
- [x] Bootstrap vs t-test disagreement flag.
- [x] LaTeX and CSV export payloads.
- [x] Robustness matrix, specification curve, degrees-of-freedom counter and summary line.
- [x] Robustness engine now builds a broader spec-curve grid across signals, windows, controls, SE lags, weighting, bucket counts and rebalancing frequency.
- [x] Robustness engine now includes a lightweight sign-flip max-statistic joint p-value over the implemented spec curve.
- [x] Permutation placebo, time displacement placebo, wrong-direction placebo and OOS comparison.
- [x] Placebo/OOS output now includes protected holdout start, protected months and out-of-sample R2.
- [x] Adjacent asset-class placebo, Fisher/Stouffer combined significance, and falsification verdict card.
- [x] Regime timeline, conditional returns, interaction regression and macro state summary.
- [x] Regime source routing for realized volatility, VIX, recession, and credit spread states.
- [x] Chow-style regime difference test, threshold grid, quantile regression, Markov-switching fit, and regime amplification output.
- [x] Residual diagnostic tests, QQ output, influence diagnostics and missing-data audit.
- [x] VIF, Durbin-Watson, Ljung-Box, White, Breusch-Pagan, RESET, correlogram, heteroskedasticity plot, and Andrews structural break diagnostics.
- [x] Publication table bundle, appendix LaTeX output, and in-memory ReportLab PDF rendering.
- [x] Feature 06 now builds a real multi-column publication table with per-column signal, controls, SE type, FE tag, weighting scheme, and confirmatory/exploratory tags.
- [x] Feature 06 now emits a coefficient forest plot payload with 95% confidence intervals.
- [x] Feature 06 now emits an auto-built specification-curve table from the robustness engine.
- [x] Feature 06 now emits journal-style LaTeX for the main table plus appendix bundle.
- [x] Event-study, DiD, matching balance, IV and RDD panels.
- [x] Event-study Patell/BMP/Kolari-Pynnönen-style tests, calendar-time alpha, pre-event drift, and post-event reversal outputs.
- [x] IV table now includes first-stage F, Staiger-Stock threshold flag, Lee 2022 threshold flag, 2SLS beta, OLS beta, AR proxy p-value, and Hausman proxy.
- [x] IV table now includes LIML beta/kappa, Anderson-Rubin grid interval, and Sargan-Hansen p-value when overidentified.
- [x] RDD table now includes bandwidth sensitivity and placebo cutoff diagnostics.
- [x] RDD table now includes IK-style bandwidth, McCrary-style density test, covariate-continuity checks and donut-hole sensitivity.
- [x] Signal vitality, McLean-Pontiff comparison, decay curve, half-life, Andrews break path, Sharpe decay and anomaly lifecycle summary.
- [x] Decay model comparison now fits exponential, linear, and hyperbolic curves with AIC/BIC/R2.
- [x] Half-life confidence interval now uses bootstrap resampling rather than a fixed multiplier.
- [x] Synthetic control treated/synthetic path, gap plot, donor weights, RMSPE ratio, leave-one-out sensitivity and conformal band.
- [x] Synthetic control placebo distribution now refits donor-placebo SCM paths.
- [x] Synthetic control leave-one-out now refits post-treatment effects without each top donor.
- [x] Synthetic control in-time placebo diagnostics added.
- [x] Synthetic control in-time placebo now refits SCM weights at each fake treatment date.
- [x] Augmented synthetic control output added with pre-period bias correction.
- [x] Generalized synthetic control output added using SVD interactive fixed-effect factors.
- [x] Robust matrix-completion synthetic control output added using winsorized donor matrix proxy.
- [x] Staggered-adoption SCM output added for researcher-provided event/treatment files.
- [x] Factor zoo positioning, Harvey-Liu-Zhu threshold card, correlation map and extended spanning proxy.
- [x] Factor zoo positioning chart now reports IC information ratio as mean rolling IC divided by standard deviation of rolling IC, not correlation divided by cross-factor correlation standard deviation.
- [x] International replication now uses regional stock baskets from the master universe suffixes rather than single ETF tickers when enough stocks are available.
- [x] User-provided raw signal ranks can be loaded from a server-side CSV/parquet path and used by the shared signal engine.
- [x] User-provided event/treatment files can be loaded from a server-side CSV/parquet path in Feature 07.
- [x] User-provided external instrument files can be loaded from a server-side CSV/parquet path in Feature 07.

## Performance Speed-Up Checklist

- [x] Reused one `research_panel()` build across canonical, robustness and specification-builder paths instead of repeatedly reloading/recomputing the same panel.
- [x] Added `canonical_outputs_from_panel()` so callers with an existing panel avoid another full data load.
- [x] Added `robustness_outputs_from_panel()` so Feature 02 and Feature 06 can reuse the same base panel.
- [x] Added `panel_variant()` to recompute only changed signal/control/weight/forward-return matrices for specification variants.
- [x] `specification_builder_outputs()` now shares the base panel across canonical, robustness, publication columns and spec curve outputs.
- [x] `rolling_coefficients()` now accepts precomputed Fama-MacBeth betas and no longer reruns the same regression unnecessarily.
- [x] `control_matrices()` now reuses the already computed signal matrix when controls overlap with signal names.
- [x] Static fundamentals control construction is vectorized with reindexing and tiled arrays rather than per-symbol Python loops.
- [x] OLS now reuses `X'X`, `X'y` and one inverse/pseudoinverse for betas, covariance, t-stats and p-values.
- [x] P-value calculation now vectorizes array inputs instead of list-comprehending over coefficients.
- [x] Newey-West standard errors now use vectorized autocovariance via `np.correlate`.
- [x] Portfolio-sort Newey-West calls now compute each spread standard error once instead of twice.
- [x] Monotonicity bootstrap now samples a 3D NumPy array and computes bootstrapped spreads vectorized.
- [x] Placebo permutation test now uses a fast matrix score path rather than running full Fama-MacBeth regressions for every permutation.
- [x] Specification-curve joint permutation now uses vectorized sign-flip max statistics.
- [x] Panel robust standard errors now fit the base statsmodels model once and derive robust covariance results from that fit.
- [x] Anderson-Rubin grid now precomputes projection matrices and reuses them across the grid.
- [x] Andrews structural-break scan now uses cumulative sums/squares instead of recomputing split RSS from scratch.
- [x] Rolling Sharpe now uses rolling mean/std directly instead of a Python lambda over every window.
- [x] VIF diagnostics now use an inverse correlation-matrix path instead of one regression per column.
- [x] Event-study window extraction now uses positional indexing around the nearest date rather than repeated date-offset index lookups.
- [x] Daily/weekly/monthly close and volume matrices now pre-aggregate before pivoting and use grouped unstacking.
- [x] Macro loading now concatenates indexed frames and resolves duplicate dates once instead of sequential merge loops.
- [x] `data_inventory()` now reuses the loaded macro frame instead of loading macro data twice.
- [x] Categorical ticker groupby warning fixed with `observed=True`.
- [x] Fast permutation empty-slice warning fixed with explicit valid-count division.
- [x] Numba JIT acceleration added for the Fama-MacBeth cross-sectional regression hot path.
- [x] Fama-MacBeth now runs through a batched matrix kernel and preserves the same output keys.
- [x] Duplicate primary signal controls are filtered out to prevent perfect-collinearity blowups under `controls=full`.
- [x] Sparse/all-NaN controls are skipped in the JIT FM design so usable signal estimates are still returned.
- [ ] Full Numba/JIT acceleration for every estimator was not added. Specialized statsmodels/scipy estimators remain on their native libraries.
- [ ] Async/background execution for long permutations, SCM placebos and publication bundles is not added. This still belongs in an API/job layer.
- [ ] Full portfolio-sort vectorization across all buckets and weighting modes is not complete.
- [ ] Full `_international_replication()` panel cache across markets is not complete; it still builds market-specific panels where needed.
- [ ] Threshold-grid, RDD and half-life bootstrap routines still have some Python loops because those paths need estimator-specific branching.
- [ ] Dedicated econometrics-package replacements for DK/GMM/SCM variants remain out of scope for this speed pass.

## Honest Limitations

- [ ] Browser/API upload storage is not wired here. The backend now accepts server-side file paths, but route-level upload handling still belongs in the API layer.
- [x] Feature 06 PDF rendering is implemented in the service layer using ReportLab. It returns `meta.pdf_base64`, a filename, MIME type, byte count, and a lightweight `tables.pdf_report` descriptor without writing artifacts to disk.
- [ ] Publication-grade IV requires an external instrument file. The backend now accepts one; without it, IV falls back to a price-derived diagnostic proxy and is explicitly marked as such.
- [ ] Formal multi-cohort DiD treatment files require external event/treatment files. The backend now accepts one; without it, event-study and DiD use a single treated unit and treatment date from payload.
- [x] International replication proxies are now present in the main market universe for EFA, EWJ, EWU, EEM, VGK, FEZ, and DXJ.
- [ ] Patton-Timmermann monotonicity remains a bootstrap practical implementation, not a verbatim journal package clone.
- [x] Driscoll-Kraay uses `linearmodels.PanelOLS(...).fit(cov_type="kernel")` with Bartlett kernel and explicit bandwidth when the panel is estimable. A statsmodels HAC fallback is clearly labelled in the output metadata.
- [x] One-step GMM is implemented for the Fama-MacBeth time-series moment condition `E[lambda_t - theta] = 0` with identity weighting and Newey-West moment covariance.
- [x] Shanken adjustment now derives its multiplier from the observed benchmark-factor covariance matrix and factor means.
- [ ] This is not a full joint asset-pricing GMM that estimates cross-sectional betas and risk premia in one nonlinear system. That requires a separate, explicitly specified estimator and model selection policy.
- [ ] Goodman-Bacon, Callaway-Sant'Anna and Sun-Abraham outputs are practical event/treatment-data tables, not drop-in replacements for dedicated econometrics packages.
- [ ] Augmented/generalized/robust SCM variants are implemented as data-backed practical estimators; they are not full specialized package clones.
- [x] Goodman-Bacon, Callaway-Sant'Anna-style ATT, and Sun-Abraham-style event-time tables are implemented as backend outputs for available treatment data.
- [x] LIML, Anderson-Rubin grid interval, and Sargan-Hansen fields are implemented in the IV output where the design supports them.
- [x] Augmented/generalized/robust synthetic control variants are implemented as backend outputs.

## Data Status

- [x] Master daily OHLCV parquet present.
- [x] Fundamentals master parquet present.
- [x] FF5 daily CSV present.
- [x] Momentum daily CSV present.
- [x] Macro/regime parquet present.
- [x] Macro parquet cache present for VIX/rates/credit-style series.
- [x] Category7 macro/regime parquet now contains VIXCLS, DGS3MO, DGS2, DGS10, BAMLC0A0CM, BAMLH0A0HYM2, FEDFUNDS, CPIAUCSL, USREC, DEXUSEU, and DEXJPUS.
- [x] Main market universe now contains EFA, EWJ, EWU, EEM, VGK, FEZ, DXJ, IEF, TLT, LQD, HYG, FXE, and FXY.
- [ ] Dedicated researcher-provided instruments/events/rank files are not inherently present in repo data, but path-based ingestion is implemented.

## Data Fetch Completed In This Pass

- [x] Appended FRED `DGS3MO` into `factors/data/processed/category7_macro_regime.parquet`.
- [x] Appended FRED `USREC` into `factors/data/processed/category7_macro_regime.parquet`.
- [x] Appended FRED `DEXUSEU` into `factors/data/processed/category7_macro_regime.parquet`.
- [x] Appended FRED `DEXJPUS` into `factors/data/processed/category7_macro_regime.parquet`.
- [x] Appended Yahoo Finance `EWU` into `backend/data/market_universe.parquet`.
- [x] Appended Yahoo Finance `FEZ` into `backend/data/market_universe.parquet`.
- [x] Appended Yahoo Finance `DXJ` into `backend/data/market_universe.parquet`.
- [x] Re-ran inventory: all public macro and market proxy requirements currently show present.

## Verification

- [x] `python3 -m compileall -q backend/app/services/research_v2` passed.
- [x] Registry smoke passed for all 10 defined features: 01, 02, 03, 04, 05, 06, 07, 08, 09, and 11.
- [x] Review-driven smoke passed with controls and rank weighting enabled: all 10 defined features returned `ok`.
- [x] Final remaining-gap smoke passed after adding panel robust SE, DiD extra tables, IV LIML/AR/Sargan fields, and SCM variants: all 10 defined features returned `ok`.
- [x] Latest smoke passed after adding Feature 01 calendar-time portfolio and Feature 06 publication table builder: all 10 defined features returned `ok`.
- [x] Latest expanded smoke passed after fixing SCM refits, double-sort lookahead, F11 IR, F01 controls/FE/rebalancing/benchmark hooks, F02 spec-curve expansion, F03 protected OOS R2, F07 RDD diagnostics, and F09 staggered-adoption SCM: all 10 defined features returned `ok`.
- [x] `python3 backend/app/services/research_v2/smoke_test.py` passed.
- [x] Manifest/runtime key audit passed for every defined feature with zero missing declared outputs.
- [x] Feature 06 PDF smoke passed: `pdf_export_status=rendered`, a non-empty base64 payload, and the `pdf_report` descriptor are returned.

## Research V2 Frontend Contract

- [x] Added a dedicated `/labs/research-v2` home route, fixed navigation dock, and ten feature routes: 01-09 and 11.
- [x] Added `frontend/src/components/research-v2/registry.js` as the frontend contract mirror for all backend feature inputs and declared output keys.
- [x] All 78 backend input keys are represented in the Research V2 configuration UI with matching types for ticker lists, tickers, selects, dates, numbers, JSON, and server-side file paths.
- [x] All 124 declared Research V2 output keys, including Feature 06 `pdf_report`, have a corresponding frontend output section and a chart/table/metric renderer selection.
- [x] Added Research-specific primitives: a ticker-token selector, grouped research configuration curtain, contract-aware output rail, table renderer, matrix heatmap, metric deck, and generic line/area/waterfall renderers.
- [x] Expanded Research V2 with dedicated quantitative renderers for regression output, coefficient forests, specification curves, decision ledgers, null distributions, Q-Q diagnostics, regime probability ribbons, event-study paths, synthetic-control paths, factor vitality gauges, and Feature 06 PDF download state.
- [x] Added content-visibility and bounded table/rail surfaces so long research output books preserve scroll and rendering performance.
- [x] UI uses the actual backend response shape, `summary_cards`, `charts`, `tables`, and `meta`, without renaming output keys.
- [x] `npm run build` passed after adding all Research V2 routes and components.
- [ ] Browser/API execution is intentionally not wired in this frontend pass. The workbench accepts a future `response` prop and stages a normalized payload through `onRun`, but route-level fetch calls are deliberately absent.
