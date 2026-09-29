# Research V2 Review: Spec vs Implementation vs Frontend

Date: 2026-09-29
Scope: `backend/app/services/research_v2/` (spec: `docs/research features.md`, code: `core/analytics.py` 2,272 lines, `core/data_loader.py`, `core/performance.py`, 10 feature files), `frontend/src/app/labs/research-v2/`, `frontend/src/components/research-v2/`.

Smoke check: `python3.11 backend/app/services/research_v2/smoke_test.py` runs all 10 features to `status: ok` in 14 s (40 symbols, tiny replications). Every declared output key comes back, so it *looks* complete. The review below is about whether the numbers are right and whether a user can reach them.

---

## Status (2026-09-29): items 1-8 done in commit fd8bb373

Every blocker and feature finding below was fixed; see `backend/app/services/research_v2/DONE.md` for what exists now and its known limitations. Item 9 (shared loaders and workbench across V2 modules) is deliberately not started.

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **Broken** | No API route exists and the pages never call one. The module cannot be used from the app. |
| Data integrity | **Broken** | Value, size, quality, profitability, leverage, and value-weighting use *today's* fundamentals for every past month: look-ahead bias. |
| Features 1, 5, 8 (core stats) | Partly correct | Real OLS/FM/diagnostics, but several tests are mislabeled or mis-specified. |
| Features 2, 3, 4 | Partly correct | Real re-runs, but key statistics (Chow, interaction, power, attribution) are not what the spec says. |
| Feature 6 | Mostly fine | Table builder works; depends on Feature 1 correctness. |
| Feature 7 (causal) | **Not implemented** | DiD, RD, IV, Bacon, Callaway-Sant'Anna, Sun-Abraham are "proxy" stand-ins with names of real estimators. |
| Feature 9 (synthetic control) | Classic SCM real; variants are proxies | Augmented/Generalized/Robust/conformal are shortcuts. |
| Feature 11 | Thin | Harvey-Liu-Zhu is a user-typed threshold, no adjustment computed. |
| Tests | **None** | `research_v2/tests/` is empty. Only the smoke runner. |
| Frontend | Shell only | Nice layout, generic renderer, duplicated input contract, no data flow. |

Bottom line: the module *returns shapes* for every output in the spec, but a researcher would get look-ahead-biased signals, several mislabeled statistics, and fake causal estimators, and cannot run it from the UI anyway. Fix order: wire it, kill look-ahead, replace hand-rolled econometrics with `linearmodels`/`statsmodels`/`arch` (already installed), then add tests.

---

## 2. Blockers (fix first)

### B1. Research V2 is unreachable
- No router: `rg research_v2 backend/app/api backend/main.py` finds nothing. Factors/Screener/PCA/Portfolio/Volatility V2 all have `app/api/<module>_v2.py`; Research does not.
- Frontend: `app/labs/research-v2/feature-XX/page.js` renders `<ResearchV2Workbench featureId="01" />` with no `onRun` or `response`. `run()` calls `onRun?.(payload)`, which is undefined, so **Run does nothing**. The header still says "CONTRACT READY".
- Fix: add `backend/app/api/research_v2.py` copying the `factors_v2.py` pattern (`GET /labs/research/v2/features` from `registry.feature_manifest()`, `POST /labs/research/v2/feature/{id}/run`), mount in `main.py`, add a React Query hook, pass `response`/`onRun` from pages. Run heavy features (2, 3, 7, 8, 9) through the existing Studio job transport so the request doesn't block.

### B2. Look-ahead bias in fundamentals
- `signal_matrix` (`analytics.py:204-222`): `value`, `size`, `quality` use `latest_fundamentals()` then `broadcast_static` across every historical month.
- `_static_fundamental_controls` (`:284`): `asset_growth`, `profitability`, `leverage` same. `asset_growth` is actually `log(total_assets)`, not growth.
- `portfolio_weight_frame` (`:311`): value weights use today's market cap for all dates.
- Effect: any result using these signals/controls/weights is invalid. Momentum/reversal/low-vol (price-based) are fine.
- Fix: point-in-time fundamentals with a reporting lag (e.g., available 90 days after period end), or market cap from `price x shares` per month. If no history exists, **disable** these options and say so in the UI instead of silently broadcasting.

### B3. Silent universe fallback
- `parse_symbols` (`data_loader.py:~108`): if none of the requested tickers exist, it silently uses the default universe. A user asking for "XYZ, ABC" gets results on 400 other stocks. Fix: return a 422 with the missing tickers.

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = explicit stand-in; MISSING = not present.

### Feature 1: Canonical Test Engine
| Spec item | State | Detail |
|---|---|---|
| Fama-MacBeth, NW SE | OK | `fama_macbeth_table` + numba kernel. |
| Shanken correction | WRONG | `_gmm_shanken` multiplies NW SE by `sqrt(1 + mu' Sigma^-1 mu)` over *benchmark* factors, not the priced characteristics' lambdas. In a characteristic FM (no estimated betas) Shanken does not apply at all. |
| One-step GMM | WRONG | "GMM" is just mean and NW SE of the same lambda series, so it always equals FM. The "material disagreement" flag can never fire meaningfully. |
| FM validity (N/T regime) | MISSING | No N/T check or auto-switch. |
| Weak identification | WRONG | Condition number of the signal covariance across *assets*; skipped at >= 500 assets. Not a first-stage beta check. |
| Panel OLS + FE | OK / WRONG | Within transform correct. `hausman_p_value` uses `var_FE + var_pooled` (should be the difference) and is a FE-vs-pooled test, not the FE-vs-RE Hausman. |
| SE menu (clustered, DK, double) | Partial | `linearmodels.PanelOLS` DK/cluster used when available; OLS table SE is plain homoskedastic. |
| Single sort | OK | NW t-stats. No FF5 alpha per portfolio in sort table (it is in the GRS table). |
| Double sort | Partial | Independent only; sequential sort missing. |
| GRS | Partial | Formula shape right; uses `np.cov` (T-1) rather than MLE, and no dof adjustment for K. Small bias. |
| Patton-Timmermann MR | WRONG | iid (not block) bootstrap, not recentered under the null, p-value computed as `1 - P(boot >= obs)`. Result is not a valid monotonicity test. |
| Rolling regression | WRONG label | Rolling mean of monthly FM lambdas, not a rolling OLS. Acceptable if relabeled. |
| Calendar-time portfolio | WRONG | Uses the long-short sort, not "assets that triggered an event in the prior N months". |
| Factor spanning | OK | Regress L/S on FF5+MOM. NW lag 4 not applied (plain OLS SE). |
| Bootstrap vs t-test disagreement | FAKE | `bootstrap_significant = |t| > 2.1`. No bootstrap is run. |
| Signal menu | Partial | No Yang-Zhang/GK/VRP/regime signals from the Volatility module. |
| Dependent-variable menu | Partial | Forward returns only; no FF alpha, realized vol, spread, volume targets. |
| Universe filters (large cap, ex-fin, ex-util, ex-micro) | MISSING | Only ticker list or "master". |
| LaTeX/CSV | OK | |

### Feature 2: Robustness Engine
- Real re-runs on a config grid (OK), but the grid does not match the spec: no crisis exclusions (GFC, COVID, 2022, Apr-May 2025), no pre/post-2008/2020/2022 splits, no universe variations, no signal transforms (winsorize, rank, z, decile), no SE variations beyond NW lag. `se_lags` changes only the NW lag.
- **Mixes signals into the robustness grid**: `signal_momentum/value/...` rows are different hypotheses, not robustness of the base one.
- Full specification-curve mode (combinations) MISSING; only one-at-a-time.
- Joint p-value: sign-flip over the *coefficients of the curve*, not a permutation of the signal. Not the spec's test.
- Decision attribution: returns one row of total variance, labeled "signal/universe/se". Not attribution. Fix: regress coefficient on dimension dummies, report partial R-squared per dimension.
- AIC/BIC/sample-size weighting MISSING. Manual external base-result input MISSING.

### Feature 3: Placebo Suite
- Permutation: OK in spirit, but the null t-stat is a raw signal*return product mean, not the FM t-stat it's compared with. Apples vs oranges. Fix: permute and rerun the same FM kernel (numba makes this cheap).
- Time displacement: OK.
- Wrong-direction: OK.
- McLean-Pontiff OOS: `in_sample_t` is the full-sample t (includes OOS). `oos_degradation` divides t-stats, not coefficients. OOS R-squared (pooled) OK.
- Adjacent asset class: tries IEF/TLT/LQD/HYG/FXE/FXY inside the equity panel; usually unavailable. Fix: dedicated fetch or mark unavailable.
- Combined Fisher/Stouffer: OK, but only combines 2 p-values and the wrong-direction p-value *should* be significant, so combining it as "evidence of spuriousness" is backwards.
- Power analysis: `abs(t) > 1.96`. Not a power calculation. Fix: simulate power from the permutation null and observed effect.
- Protected OOS lock across platform: MISSING.
- Verdict card: 2 conditions, not the spec's 4-placebo green/amber/red.

### Feature 4: Regime Conditional
- "Chow test" is `scipy.stats.f_oneway` on long-short returns by regime. That is a one-way ANOVA on means, not a Chow test of regression coefficients.
- "Interaction regression" regresses returns on regime dummies only. No `signal x regime` term, so delta in the spec is never estimated.
- Threshold search: splits on the *signal's cross-sectional mean*, not the conditioning variable, and uses t not the Chow F.
- Conditioning menu: only VIX, recession, credit, realized-vol. Missing yield-curve slope, trailing 6/12m market return, intersections of two conditions, min-observations guard.
- Markov switching: real (`statsmodels.MarkovRegression`) but on returns only, not jointly with regime-specific coefficients.
- Quantile regression: real, but across the return distribution, not across the conditioning variable as the spec asks.

### Feature 5: Diagnostic Center
- VIF, Durbin-Watson, Ljung-Box, White, Breusch-Pagan, RESET, Cook's, DFBETA/DFFITS: real `statsmodels`. Good.
- But they run on a **randomly sampled, stacked (date, asset) panel** (`_stacked_panel_design`, 25k row sample). DW and Ljung-Box on that ordering are meaningless; serial correlation should be tested on the FM lambda series or per-asset residuals.
- Andrews sup-F: F path computed, **no Andrews critical values** and no p-value; break CI missing. Fix: `statsmodels` has no Andrews, but critical values are a small table (Andrews 1993 / Hansen 1997 p-values); or use `ruptures`.
- Influential observations: row index only, no date/asset label, no "coefficient change if removed" %.
- Partial residual plots: MISSING.

### Feature 6: Specification Builder
- Multi-column table, stars, LaTeX booktabs, PDF (reportlab), forest plot, confirmatory tags: present. Quality depends on Feature 1 SEs (see above). Per-column FE/time-period config should be verified once wired.

### Feature 7: Causal Identification (largest gap)
Everything is single-series and uses time as the running variable. Names are real estimators; implementations are not.
| Spec | What the code does |
|---|---|
| DiD (TWFE) | `post.mean() - pre.mean()` for one ticker. No control group. That is a before/after, not DiD. |
| Goodman-Bacon | Two hard-coded comparisons with weight 0.5 each. |
| Callaway-Sant'Anna / Sun-Abraham | Positional event rows; Sun-Abraham "SE" = mean rolling std. |
| Parallel trends F-test | Pre-period on the same series; no treated vs control. |
| Propensity matching / balance | Nearest by *signal value* on last date; no SMD. |
| Event study CAR | Single-asset path; Patell/BMP/KP need many events. Verify `_event_study_tests`; with one event these tests are undefined. |
| RD | Running variable = months to date (regression discontinuity in time). Spec RD is cross-sectional (market cap, rank, rating). McCrary on a time index is always flat by construction. IK bandwidth is a rule-of-thumb formula. |
| IV | Outcome = equal-weight market return, endogenous = mean signal, instrument = lagged market return. Wu-Hausman is `abs(b_iv - b_ols)`. LIML is a k-class "proxy". |
| `identification_design` input | Ignored; every design runs every time. |

Recommendation: rebuild on proper libraries (section 4) with a real panel of treated/control units from an uploaded events CSV. Until then, hide Feature 7 or label it "prototype, not for inference".

### Feature 8: Signal Decay
- IC, rolling IC, McLean-Pontiff split, exponential/linear/hyperbolic fits with AIC/BIC, vitality: OK.
- Exponential fit time axis starts at the first rolling point, not at `t_discovery` as the spec defines.
- Half-life bootstrap: iid resampling of (t, y) pairs, capped at 99 reps. Spec: block bootstrap, 1,000 reps. Use `arch.bootstrap.MovingBlockBootstrap`.
- Andrews break: F path only, no critical value, no CI, and scans the whole sample, not the post-discovery period.
- Arbitrage vs data-mining: `1 - survival` and `|t|/10`. Arbitrary formulas. Spec needs cross-sectional decay by liquidity/ivol/cost. Mark as heuristic or implement properly.
- International replication: depends on suffix tickers existing in the parquet; mostly empty. Split at 50% of each market's own history, not the discovery date.
- Default discovery date = 45% of sample when not provided. Should be required.

### Feature 9: Synthetic Control
- Classic SCM (SLSQP, convex weights on pre-period returns): real. Note: fits on returns, and SCM normally matches levels/cumulative outcomes plus predictors.
- Placebo-in-space, leave-one-out, in-time placebo: present.
- Augmented SC: adds mean pre-period residual (not ridge augmentation). Generalized SC: SVD factors on donors with OLS (reasonable sketch). Robust SC: winsorize + reuse weights, labeled "matrix_completion_proxy". Conformal band: 90th percentile of |gap|, not conformal inference.
- Predictor variables and donor-pool filters (same sector, same size decile): MISSING.

### Feature 11: Factor Zoo
- Correlation to FF factors, near-duplicate flag: OK.
- "IC-IR" in zoo chart is rolling correlation of the candidate to each factor, not IC.
- Harvey-Liu-Zhu: `required_t` is just the user's threshold (default 3.0). No computation of the literature-adjusted bar (HLZ Bonferroni/Holm/BHY given ~400+ factors).
- `observed_t` is the t-stat of the *intercept*... correct for spanning alpha but should be labeled alpha t.
- Extended library (quality, low-vol, BAB, STR): MISSING; only FF5+MOM.

---

## 4. Use open source that is already installed

Already importable in `python3.11` (and in `requirements.txt` except where noted):

| Hand-rolled today | Replace with | Why |
|---|---|---|
| FM + Shanken + GMM (`_gmm_shanken`, FM table) | `linearmodels.asset_pricing.LinearFactorModel` (two-pass with Shanken), `LinearFactorModelGMM`, `linearmodels.panel.FamaMacBeth` (NW/kernel cov) | Correct Shanken and real GMM, with J-test. |
| GRS | `LinearFactorModel(...).fit()` J-stat, or keep formula with MLE covariances | Standard, tested. |
| Panel OLS / FE / clustered / DK SE / Hausman | `linearmodels.panel.PanelOLS`, `RandomEffects`, `compare` | Proper clustered/DK/two-way; Hausman FE vs RE from the fits. |
| IV / LIML / weak-IV / Sargan / Wu-Hausman | `linearmodels.iv.IV2SLS`, `IVLIML`, `IVGMM`; `.first_stage`, `.sargan`, `.wu_hausman()`, `.wooldridge_regression` | Removes every `_proxy` in the IV path. |
| Bootstraps (MR test, half-life CI, sort inference) | `arch.bootstrap.StationaryBootstrap`, `MovingBlockBootstrap`; `arch.bootstrap.MCS`/`SPA`/`StepM` for multiple testing | Block bootstraps as the spec requires. |
| Diagnostics | keep `statsmodels` (already used) | Just fix the input series. |
| Markov / quantile | keep `statsmodels` | Already used. |
| Decay curve fits | keep `scipy.optimize.curve_fit` | Fine. |
| Structural break p-values | `statsmodels.stats.diagnostic.breaks_cusumolsresid` (CUSUM) plus an Andrews critical-value table; or `ruptures` (new dep) | Gives the missing p-value/CI. |

Worth adding (new dependencies, need approval):

| Library | For | Notes |
|---|---|---|
| `pyfixest` | Feature 7 DiD: TWFE, `did2s`, Sun-Abraham `i()` event study, Callaway-Sant'Anna-style via `did` module, fast multi-way FE | Pure Python, fast, fixest port. Strongest single upgrade. |
| `differences` | Callaway-Sant'Anna ATT(g,t) | Direct CS implementation. |
| `rdrobust` + `rddensity` | Feature 7 RD: CCT optimal bandwidth, robust bias-corrected CIs, Cattaneo-Jansson-Ma density test (modern McCrary) | Official Python ports. |
| `pysyncon` | Feature 9: classic, augmented (ridge) SCM, placebo tests | Replaces the augmented/robust proxies. |
| `ruptures` | Andrews-style break detection | Optional. |

Frontend: `@tanstack/react-query` is installed; use it for the run hook. For charts pick **one** of `recharts` / `echarts` / `plotly` / `d3` (all four are installed; the plan's P16 "no duplicate chart paths" rule applies).

---

## 5. Frontend review

- **No data flow** (B1). Pages render without `response`/`onRun`.
- **Duplicated contract**: `components/research-v2/registry.js` re-declares every feature's inputs/defaults/outputs by hand. Backend already has `registry.feature_manifest()`. Drift already exists (e.g. frontend Feature 1 inputs vs backend `INPUTS`). Fix: fetch `/features` and render from it; keep only presentation hints (chart type, rank) in the frontend.
- **Misleading options**: Feature 7 `identification_design` (ignored by backend), Feature 9 `augmented_proxy`, Feature 11 `extended_proxy` expose proxies as choices.
- `customPagePrimitives.jsx`: 51 KB with three lines over 1,000 chars (one ~20 KB CSS string in `<style jsx global>`). Move CSS to a module/Tailwind, split into Workbench, ConfigCurtain, OutputCard, renderers.
- `file_path` inputs ask for a *server path* (`signal_csv_path`). Browser users cannot supply that. Needs an upload endpoint (the Studio data-studio upload already exists: reuse it and pass the upload id).
- No loading, error, empty, or cancel states for long jobs (because nothing runs yet).

---

## 6. Codebase-wide pattern (same issues across the V2 modules)

Seen while reviewing; each deserves the same pass.
- **Seven copies of `core/data_loader.py`** (factors, ml, pca, portfolio, research, screener, volatility; 93-426 lines each) and seven `core/analytics.py` (16,212 lines total). Same parquet readers, symbol parsing, Ken French parsing. Fix: one shared `app/services/shared/market_data.py`; modules keep only their analytics.
- **Seven `components/*-v2/customPagePrimitives.jsx`** (10,754 lines total), each with its own design tokens and generic renderer. Fix: one shared Lab workbench + renderer registry; per-module files only declare sections.
- `linearmodels` is used but not listed in `backend/requirements.txt`.
- Backend deps are ranges, no lock (P17 gap).
- `.gitignore` excluded all `*.md`, so module docs (`DONE.md`, `review.md`, feature specs) were not versioned. Fixed in this pass.
- `DONE.md` marks every feature complete. Given the findings above, it overstates status. Update it after fixes.

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Wiring | `api/research_v2.py` router + mount; React Query hook; pages pass `response`/`onRun`; heavy features via job transport | S |
| 2 | Data integrity | Point-in-time fundamentals or disable fundamental signals/controls/value-weights; fail on unknown tickers | M |
| 3 | Correctness (F1) | FM/Shanken/GMM/GRS via `linearmodels`; real block-bootstrap MR test; delete fake bootstrap disagreement; FM N/T validity flag; sequential double sort | M |
| 4 | Correctness (F2-F5) | Spec-matching robustness grid (crisis, splits, transforms, universes), attribution via dummies; permutation on same FM kernel; real Chow + signal x regime interaction; diagnostics on the right series; Andrews p-values | M |
| 5 | Feature 7 rebuild | Panel DiD (pyfixest/differences), cross-sectional RD (rdrobust/rddensity), IV (linearmodels), multi-event study; honor `identification_design`. Hide until done | L |
| 6 | Feature 8/9/11 | Block-bootstrap half-life, post-discovery Andrews, required discovery date; pysyncon augmented SCM; real HLZ threshold; extended factor library | M |
| 7 | Tests | Golden-number tests per estimator against known datasets (e.g. `linearmodels` examples, Ken French portfolios, simulated DGP with known lambda); a look-ahead guard test | M |
| 8 | Frontend | Manifest-driven inputs; uploads instead of server paths; loading/error/cancel; split primitives; one chart lib | M |
| 9 | Cleanup | Shared data loader and shared Lab workbench across V2 modules; add `linearmodels` to requirements; update `DONE.md` | L |

Recommended next step: items 1 and 2 together (small, and they make the module both usable and honest), then 3 with tests from 7 alongside.
