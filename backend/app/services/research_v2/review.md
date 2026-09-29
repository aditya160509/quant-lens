# Research V2 — Implementation Review

## Sources Reviewed

| Source | Lines | Description |
|--------|-------|-------------|
| `research features.md` | 773 | Full spec for Research Features 01-09, 11 |

| `backend/app/services/research_v2/DONE.md` | 97 | Self-reported completion checklist |
| `backend/app/services/research_v2/registry.py` | 62 | Feature registry + dispatch |
| `backend/app/services/research_v2/__init__.py` | 5 | Package exports |
| `backend/app/services/research_v2/core/analytics.py` | 824 | All feature logic (single file) |
| `backend/app/services/research_v2/core/data_loader.py` | 360 | Parquet/CSV data access layer |
| `backend/app/services/research_v2/fetchers/fetch_missing_data.py` | 179 | FRED + yfinance fetch helpers |
| `backend/app/services/research_v2/features/feature_01.py` | 44 | Thin shell delegating to analytics |
| `backend/app/services/research_v2/features/feature_02.py` | 39 | Thin shell |
| `backend/app/services/research_v2/features/feature_03.py` | 36 | Thin shell |
| `backend/app/services/research_v2/features/feature_04.py` | 26 | Thin shell |
| `backend/app/services/research_v2/features/feature_05.py` | 25 | Thin shell |
| `backend/app/services/research_v2/features/feature_06.py` | 25 | Thin shell |
| `backend/app/services/research_v2/features/feature_07.py` | 27 | Thin shell |
| `backend/app/services/research_v2/features/feature_08.py` | 27 | Thin shell |
| `backend/app/services/research_v2/features/feature_09.py` | 26 | Thin shell |
| `backend/app/services/research_v2/features/feature_11.py` | 26 | Thin shell |

---

## 1. Architecture Assessment

### What Exists

A working shell architecture: 10 feature modules, a registry, a shared analytics core, a data loader, and fetch helpers. The `compileall` check passes, the registry dispatches all 10 features without errors, and the analytics module produces deterministic data-backed output for every feature endpoint.

### What's Missing


- **No tests** beyond `compileall` — no pytest, no integration tests, no endpoint tests.
- **No caching layer** for expensive computations (e.g., CPCV, DML, Markov-switching).
- **No async execution** — all features run synchronously; long-running features will timeout.
- **Single-file bottleneck**: all 824 lines of logic in `analytics.py` — no modularization across features.

---

## 2. Feature-by-Feature Gap Analysis

### Feature 01 — Canonical Test Engine

| Spec Requires | Implemented | Status |
|---|---|---|
| Fama-MacBeth with Shanken SE | Basic FM with NW SE (Shanken = NW × 1.05 hardcoded) | Proxy |
| Panel OLS with fixed effects | OLS only, no FE, no Hausman test | Proxy |
| Single portfolio sort | Q-bucketed EW sort | Done |
| Double sort (independent + sequential) | Double sort with hardcoded second signal (vol) | Proxy |
| GRS test (proper F-distribution) | `nanmean(nan_square(alphas)) / nanvar(alphas)` — not real GRS | Proxy |
| Patton-Timmermann monotonicity | Simplified bootstrap proportion check | Proxy |
| Rolling regression | Rolling FM lambda with 95% bands | Done |
| Calendar-time portfolio | **Not implemented** | Missing |
| Factor spanning test | OLS of LS returns on FF5+MOM | Done |
| FM validity flag | N/T ratio check with regime labels | Done |
| Weak identification card | Condition number (only up to 500 symbols) | Proxy |
| EIV correction (Shanken + GMM) | Hardcoded multipliers (×1.05, ×0.98, ×1.12) | Proxy |
| Bootstrap sort inference | Hardcoded t-threshold difference | Proxy |
| Weighting schemes (equal/value/rank) | Equal-weight only | Missing |
| Rebalancing frequency options | Monthly only | Missing |
| Control variables | **Not implemented** — no controls in regression | Missing |
| Driscoll-Kraay SE | **Not implemented** | Missing |
| Double-clustered SE | **Not implemented** | Missing |
| User-defined factor benchmark | Internal FF5+MOM only; no manual benchmark | Missing |

### Feature 02 — Robustness Engine

| Spec Requires | Implemented | Status |
|---|---|---|
| Full spec curve (all dimension combos) | 9 hard-coded configs (base, large_cap, top_1000, NW12, quintiles, deciles, 3 signal variants) | Proxy |
| Time window variations | **Not implemented** | Missing |
| Subsample splits | **Not implemented** | Missing |
| Crisis exclusion toggles | **Not implemented** | Missing |
| Signal transformations (winsorize, rank, z-score) | **Not implemented** | Missing |
| Control variable variations | **Not implemented** | Missing |
| SE variations (OLS → NW3/6/12 → clustered) | Only NW lag; no OLS, no clustered | Missing |
| Weighting variations | **Not implemented** | Missing |
| Joint permutation test (spec curve p-value) | 1 - proportion_significant | Proxy |
| Researcher degrees of freedom counter | Hardcoded to len(configs) | Proxy |
| Decision-attribution panel | Variance of coefficients | Proxy |
| Coefficient stability chart (box plot) | Scatter of spec vs coefficient | Proxy |
| Economic magnitude range | Min/max coefficient | Done |
| Weakest/strongest spec flag | By t-stat sorting | Done |
| Robustness summary line | Simple sentence | Done |

### Feature 03 — Placebo Suite

| Spec Requires | Implemented | Status |
|---|---|---|
| Permutation placebo | Signal shuffle, re-run FM, null distribution | Done |
| Time displacement placebo | Shift signal by -N months | Done |
| Wrong-direction placebo | Multiply signal by -1 | Done |
| McLean-Pontiff OOS test | Time-split at 50/60/70% | Done |
| Adjacent asset class placebo | **Not implemented** | Missing |
| Combined significance (Fisher/Stouffer) | Proxy: permutation p-value | Proxy |
| Power analysis | `abs(t) > 1.96` | Proxy |
| Protected OOS window | **Not implemented** | Missing |
| Falsification verdict card | **Not implemented** | Missing |

### Feature 04 — Regime Conditional Analyzer

| Spec Requires | Implemented | Status |
|---|---|---|
| Conditional regressions by regime state | Vol-tercile split | Proxy |
| Chow test for structural difference | **Not implemented** | Missing |
| Threshold search (Andrews-style grid) | **Not implemented** | Missing |
| Quantile regression | **Not implemented** | Missing |
| Markov-switching model | **Not implemented** | Missing |
| Interaction term test (`signal × regime`) | Dummy-variable OLS | Proxy |
| Regime-conditional Sharpe ratio | mean/std × sqrt(12) per regime | Done |
| Economic magnitude by regime (amplification factor) | **Not implemented** | Missing |
| VIX / recession / credit spread conditioning | **Not implemented** | Missing |

### Feature 05 — Diagnostic Center

| Spec Requires | Implemented | Status |
|---|---|---|
| VIF table | **Not implemented** | Missing |
| Durbin-Watson test | **Not implemented** | Missing |
| Ljung-Box test (lags 1, 5, 12, 21) | AC(1) only | Missing |
| White test | **Not implemented** | Missing |
| Breusch-Pagan test | **Not implemented** | Missing |
| Chow test (user-specified date) | **Not implemented** | Missing |
| Andrews supremum structural break | **Not implemented** | Missing |
| Jarque-Bera normality test | Done (via scipy) | Done |
| RESET test | **Not implemented** | Missing |
| Partial residual plots | **Not implemented** | Missing |
| DFBETA / DFFITS | **Not implemented** | Missing |
| Cook's distance | **Not implemented** | Missing |
| Residual autocorrelation correlogram | **Not implemented** | Missing |
| Heteroskedasticity plot | **Not implemented** | Missing |

### Feature 06 — Specification Builder

| Spec Requires | Implemented | Status |
|---|---|---|
| Multi-column table builder (2-8 cols) | **Not implemented** (collects Feature 1 tables only) | Missing |
| Per-column configuration (DV, signal, controls, SE, FE, weighting) | **Not implemented** | Missing |
| LaTeX export (booktabs) | Concatenates existing LaTeX exports | Proxy |
| PDF export | **Not implemented** | Missing |
| Coefficient plot (forest plot) | **Not implemented** | Missing |
| Confirmatory/exploratory tagging | **Not implemented** | Missing |
| Auto-built table from spec curve | **Not implemented** | Missing |

### Feature 07 — Causal Identification Engine

| Spec Requires | Implemented | Status |
|---|---|---|
| DiD: Two-way fixed effects | Single treated unit pre/post mean diff | Proxy |
| DiD: Callaway-Sant'Anna | **Not implemented** | Missing |
| DiD: Sun-Abraham | **Not implemented** | Missing |
| DiD: Parallel trends pre-test | **Not implemented** | Missing |
| DiD: Goodman-Bacon decomposition | **Not implemented** | Missing |
| DiD: Placebo treatment | **Not implemented** | Missing |
| DiD: Covariate balance table | Matching balance on signal only | Proxy |
| Event Study: CAR/BHAR | Simple rolling sum | Proxy |
| Event Study: Patell test | **Not implemented** | Missing |
| Event Study: BMP test | **Not implemented** | Missing |
| Event Study: KP-adjusted test | **Not implemented** | Missing |
| Event Study: Calendar-time portfolio | **Not implemented** | Missing |
| Event Study: Pre-event drift | **Not implemented** | Missing |
| Event Study: Post-event reversal | **Not implemented** | Missing |
| RDD: Local linear regression | Simple 12-month bandwidth OLS | Proxy |
| RDD: IK optimal bandwidth | **Not implemented** | Missing |
| RDD: McCrary density test | **Not implemented** | Missing |
| RDD: Placebo cutoff tests | **Not implemented** | Missing |
| RDD: Bandwidth sensitivity | **Not implemented** | Missing |
| RDD: Donut hole test | **Not implemented** | Missing |
| IV: 2SLS/LIML | OLS with lagged return as instrument | Proxy |
| IV: Staiger-Stock F-test | **Not implemented** | Missing |
| IV: AR confidence set | **Not implemented** | Missing |
| IV: Sargan-Hansen test | **Not implemented** | Missing |
| IV: Hausman endogeneity test | **Not implemented** | Missing |

### Feature 08 — Signal Decay and Arbitrage Clock

| Spec Requires | Implemented | Status |
|---|---|---|
| McLean-Pontiff pre/post comparison | Split at discovery date | Done |
| Exponential decay curve fitting | NLS curve_fit with bounds | Done |
| Half-life with bootstrap CI | Point estimate + hardcoded ×0.75/×1.25 | Proxy |
| Linear / hyperbolic model comparison | Columns exist, all NaN | Missing |
| Andrews structural break (arbitrage arrival) | F-stat grid over central 70% | Done |
| Signal vitality gauge | Pre-period IC ratio × 100 | Done |
| Arbitrage vs data-mining decomposition | Hardcoded fraction from survival/t | Proxy |
| International replication | ETF proxies (EFA, EWJ, EWU, EEM) | Proxy |
| Long-short Sharpe decay chart | Rolling 12m Sharpe | Done |
| Anomaly lifecycle summary | Simple sentence | Done |

### Feature 09 — Synthetic Control Engine

| Spec Requires | Implemented | Status |
|---|---|---|
| Classic SCM (convex weights) | SLSQP optimization | Done |
| Augmented SC | **Not implemented** | Missing |
| Generalized SC (interactive FE) | **Not implemented** | Missing |
| Robust SC (matrix completion) | **Not implemented** | Missing |
| Pre-treatment fit diagnostic | Pre-RMSPE | Done |
| Post/pre RMSPE ratio | Done | Done |
| Placebo distribution (in-space) | Single proxy placebo | Proxy |
| In-time placebo test | **Not implemented** | Missing |
| Leave-one-out donor sensitivity | Proxy (weight × gap std) | Proxy |
| Conformal inference intervals | Gap ± 90th percentile quantile | Proxy |
| Staggered adoption event-study | **Not implemented** | Missing |

### Feature 11 — Factor Zoo Positioning

| Spec Requires | Implemented | Status |
|---|---|---|
| Extended spanning test | OLS of candidate on FF5+MOM | Done |
| Harvey-Liu-Zhu adjusted significance | `observed_t >= threshold` comparison | Proxy |
| Factor correlation map | Pairwise with `rho > 0.7` flagged | Done |
| IC-IR positioning scatter | `ic / ir` chart | Done |

---

## 3. Infrastructure Gaps

| Area | Status |
|---|---|
| Frontend UI components | Not created |
| Unit / integration tests | Only `compileall` — no pytest, no mock tests, no endpoint tests |
| `schemas/` directory | Empty |
| `utils/` directory | Empty |
| Caching for expensive computations | Not implemented |
| Async execution (long-running features) | Not implemented |
| Error handling / retry logic | Minimal (bare excepts in many places) |
| Authentication / authorization | Not implemented |
| Request validation (Pydantic schemas) | Not implemented |
| Webhook / callback for async completion | Not implemented |
| Rate limiting | Not implemented |
| Logging / audit trail | Not implemented |

---

## 4. DONE.md Honest Assessment

The `DONE.md` claims all 10 features are implemented with output coverage. This is accurate at the **shell/stub level** — each feature module exists, registers, and returns a deterministic response. However, the claim is misleading because:

- Every feature delegates to shared functions in `analytics.py` that implement simplified proxies, not the full statistical machinery specified in `research features.md`.
- Many outputs are hardcoded approximations (e.g., Shanken SE = NW × 1.05, GMM lambda = FM × 0.98).
- Critical tests are entirely missing (no VIF, no Chow, no quantile regression, no proper GRS, no proper DiD, no proper RDD, no proper IV).
---



## 5. Recommended Priority Roadmap

### Phase 1 — Production Hardening

1. **Input validation** — Fill `schemas/` with Pydantic models
2. **Async execution** — Use background tasks for long-running features
3. **Tests** — pytest for `analytics.py` functions (mock the data loader)
4. **Error handling** — Replace bare excepts with structured error responses

### Phase 2 — Feature Completeness

1. **Feature 01:** Controls, weighting schemes, proper GRS, proper Shanken/GMM, proper double sort
2. **Feature 04:** Chow test, quantile regression, markov-switching model
3. **Feature 05:** VIF, Ljung-Box, White/Breusch-Pagan, Andrews structural break
4. **Feature 07:** Proper DiD (TWFE), proper Event Study (Patell, BMP, calendar-time), proper RDD (IK bandwidth)
5. **Feature 08:** Bootstrap half-life CI, arbitrage vs data-mining decomposition
6. **Feature 09:** Proper placebo distribution, leave-one-out, conformal inference

### Phase 3 — Polish

1. LaTeX/PDF export quality
2. Coefficient plots and forest plots
3. International replication with real data
4. Frontend visualization components
