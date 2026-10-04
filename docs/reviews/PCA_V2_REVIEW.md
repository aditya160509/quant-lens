# PCA V2 Review: Spec vs Implementation vs Frontend

Date: 2026-09-29
Scope: `backend/app/services/pca_v2/` (spec: `docs/pca features.md` 919 lines, code: `core/analytics.py` 2,342 lines, `core/cross_asset.py` 490 lines, `core/data_loader.py` 342 lines, `core/data_pooling.py`, `core/performance.py`, 11 feature files, `registry.py`), `backend/app/api/pca_v2.py`, `frontend/src/app/labs/pca-v2/`, `frontend/src/components/pca-v2/`.

Smoke check: `PYTHONPATH=backend python3 -c "from app.services.pca_v2.registry import run_feature"` runs all 11 features to `status: ok` on local parquet (per `README.md:152-172` and `audit.md:49`). Every declared output key comes back, so it *looks* complete. The review below is about whether the numbers are right and whether a user can reach them. Prior art: `review.md` (2026-07-13, 600+ lines, now stale on wiring/frontier/F03-bug claims) and `audit.md` / `audit code.md` (pre-remediation finding sets, largely closed). This review re-verifies each line of current code against the spec and the UI.

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **Broken** | Router file exists but is never mounted and the pages never call it. The module cannot be used from the app. |
| Data integrity | **Broken** | Unknown tickers silently fall back to the default universe; small universes are silently swapped. A user asking for "XYZ" gets results on other stocks. |
| PCA math core (F1/F2 eigendecomposition, MP, RMT cleaning) | Mostly correct | Real `eigh`, iterative `fit_mp_sigma2`, 5 estimators, hard-clip reconstruction, Varimax/Promax, HPCA, Hoyer, asset R2. But no corr-matrix path, so Kaiser and standardization claims are wrong. |
| Features 3, 4, 5, 7, 8, 9, 11 | Mostly fine | Prior `review.md` gaps (F03 wrong table, F05 multi-eigenvalue/crisis/summary, F07 residual bootstrap, F08 rolling lambda1, F09 true Mahalanobis, F11 unwind) are now fixed in code. Remaining gaps are secondary options. |
| Feature 6 (optimization) | Mostly fine | Prior pseudo-frontier finding is fixed: real lambda-sweep QP frontier at 100 points plus turnover and RMT-vs-sample panels. Sector/factor/cardinality constraints still missing. |
| Feature 10 (cross-asset) | Partly correct | Real block estimators (EWMA/OAS/Student-t EM), DCC, CASCI, CF-adjusted MP, hedge ratios. But no unified RMT cleaning and no block MP-bound overlay. |
| Tests | **Thin** | 3 unit tests (blend, preprocess modes, Student-t symmetry). No golden-number, API, or frontend tests. |
| Frontend | Shell only with fake numbers | Nice layout, but every chart/table renders `Math.sin` filler. Run button says "API pending" and does nothing. No biplot, no MP overlay. |

Bottom line: the backend is a real, substantially correct PCA/RMT engine (the old audit gaps are ~90% closed), but a user gets `Math.sin` filler in the UI, cannot trigger a run from any page, and would get silently substituted universes and covariance-only PCA even when the spec promises correlation-matrix PCA. Fix order: mount the router and bind the workbench to it, kill the silent universe fallback, add the corr/standardization toggle (or relabel Kaiser), then fill the frontend renderers and add math regression tests.

---

## 2. Blockers (fix first)

### B1. PCA V2 is unreachable and the UI shows fake numbers
- Router exists but is unmounted: `backend/app/api/pca_v2.py:13` defines `APIRouter(prefix="/labs/pca/v2")` with `GET /features` (`:16-24`) and `POST /feature/{feature_id}/run` (`:27-35`), but `rg pca_v2 backend/app/main.py backend/app/api/__init__.py` finds no import or `include_router`. `review.md:416` ("No V2 API exists") is half-stale: the file now exists, the mount still does not.
- Frontend: every `frontend/src/app/labs/pca-v2/feature-*/page.js` (e.g. `feature-01/page.js:5`) renders `<PcaV2Workbench featureId="01" sections={...} />` with no `onRun` or `response`. `PcaV2Workbench` (`customPagePrimitives.jsx:521-524`) accepts only `{featureId, sections}`, holds only `form` state, and its hero button is hardcoded `API pending` (`:536`). **Run does nothing.** Each card footer still says "Ready for API key" (`:566`).
- Worse than Research V2: `previewRows` (`customPagePrimitives.jsx:210-244`) fabricates every visual: heatmap `Math.sin((i+1)*(j+2)+seed)*0.72` (`:215`), tables `Math.sin(seed+i)*0.42` (`:222`), metric deck `Math.abs(Math.sin(seed+i)*100)` (`:227`), waterfall `Math.sin(seed/10+i)*0.08` (`:230`), frontier `risk: 6+i*0.45, return: 4+sqrt(i+1)*1.45` (`:236`), scree `eigenvalue: 2.7/(i+1)+Math.sin(i)*0.05, mp: 0.42` (`:290`). `StandardChart`, `Heatmap`, `DataTable`, `MetricDeck`, `Waterfall` all call `previewRows` (`:272,:339,:365,:382,:394,:413`) and never read a `response`.
- Fix: mount the router in `main.py` (copy the `factors_v2.py` pattern), add a React Query hook against `/labs/pca/v2/feature/{id}/run`, pass `response`/`onRun` from pages into `PcaV2Workbench`, replace every `previewRows` call with real `response.charts/tables` rendering, and gate the filler behind an empty state. Run heavy features (05 rolling/tensor, 07 bootstrap, 10 cross-asset) through the existing Studio job transport so the request does not block.

### B2. Silent universe fallback
- `parse_symbols` (`core/data_loader.py:278-279`): if none of the requested tickers exist in the parquet, it silently returns `source_symbols(default_limit)`. A user asking for "XYZ, ABC" gets results on ~80-160 other stocks.
- `load_context` (`core/analytics.py:156-158`): if the returns matrix has fewer than `min_symbols` columns, it silently re-parses with `{}` defaults and refits. Same effect one layer up.
- Fix: return a 422 with the missing tickers (and, for the `load_context` guard, surface `requested vs resolved` counts in `meta`). If a fallback is ever wanted, make it opt-in (`allow_universe_fallback=true`) and label it in the UI.

### B3. Covariance-only PCA sold as covariance-or-correlation PCA, plus silent estimator fallbacks
- Spec promises a Matrix-type toggle (F1 input) and a Standardization toggle (F2 input: "Demean only / demean + standardize to unit variance (correlation matrix PCA)", spec lines 13, 48). `rmt_model` (`core/analytics.py:245-289`) has no `matrix_type`/`standardize` branch: it always runs `covariance_estimator` on raw log returns and `eig_sorted` on that covariance. There is no correlation-matrix path anywhere in `analytics.py`.
- Consequence 1: `choose_k` (`:230-242`) computes `k_kaiser = sum(vals > 1.0)` (`:237`) on covariance eigenvalues. Kaiser `lambda > 1` is only meaningful for correlation-matrix PCA where `sum(lambda) = N` (spec line 304 says exactly this). On covariance PCA the threshold is arbitrary. Currently WRONG label.
- Consequence 2: large-variance assets dominate early factors with no user recourse. Either add the toggle (standardize before `covariance_estimator`, run Kaiser only on that path) or remove both toggles from the spec/UI and relabel Kaiser as "covariance heuristic, not Kaiser".
- Silent fallbacks in the same area: `covariance_estimator` MCD guard (`:186`, `len(x) > x.shape[1] + 5`) is too weak (needs roughly T > 2N) and falls through to `np.cov` sample with no warning; `ou_signal_table` volume-time (`:1167-1172`) swallows all exceptions with `pass`; `bootstrap_validation` silently caps replications (`:1393-1394`, B=30/80 capped at 60/250 vs spec 200/500/1000). Fix: proper MCD size check with a `meta` warning, surface `volume_time_fallback` in `meta`, and surface `bootstrap_runs_requested vs executed` in `meta`.

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = explicit stand-in; MISSING = not present.

### Feature 1: RMT Noise-Filtered Covariance Engine
| Spec item | State | Detail |
|---|---|---|
| 5 estimators (Sample/LW/OAS/EWMA/MCD) | OK / WRONG guard | All five coded (`analytics.py:174-199`). MCD size guard too weak, silent fallthrough to sample (B3). |
| MP threshold with iterative sigma2 fitting | OK | `fit_mp_sigma2` (`:360-383`) is proper bulk-mean iteration; wired in `rmt_model` (`:260-266`). Bare `mp_threshold` (`:208-219`) still defaults to `nanmedian` when called without sigma2; only safe via `rmt_model`. |
| 5 K criteria | OK / WRONG | RMT/variance/elbow/manual OK (`:230-242`). Kaiser WRONG on covariance (B3). |
| RMT reconstruction (signal + diagonal idio) | OK | `signal + diag(idio)` (`:269-271`). |
| Shrinkage blend slider | OK | `blend_covariance` (`:1663-1681`) is true `(1-g)*cleaned + g*raw_sample` using stored `raw_cov`; wired in `feature_01.py:44-45`. Old review.md blend bug is fixed. Tested (`test_pca_v2_remediation.py:12-17`). |
| Outlier pre-processing (none/winsor 1/99 + 2.5/97.5/trim/Huber) | OK | All five modes in `preprocess_returns` (`:386-422`). Tested for shape/finiteness (`test_*:20-25`). Default-on `outlier_filter=true` (frontend `registry.js:10`, `rmt_model:250`) silently clips `|z|>4`; should be opt-in or disclosed. |
| Matrix type (cov vs corr) | MISSING | No corr path (B3). |
| Condition numbers | OK | Raw vs cleaned in `feature_01.py:25-27,39-42`. |
| MP density overlay curve | MISSING | Backend returns only `mp_lambda_max` scalar + spectrum table; no fitted MP density series. Frontend draws fake `mp: 0.42` line (`customPagePrimitives.jsx:290`). |
| Full audit trail JSON | Partial | `metadata` (`:1639-1656`) returns symbols/dates/K/mp/cov; retained eigenvectors added in `feature_01.py:83`. No window-type/anchor-date (spec window types rolling/expanding/anchored are all MISSING; only fixed lookback). |

### Feature 2: PCA Factor Extraction and Loading Matrix
| Spec item | State | Detail |
|---|---|---|
| Loading heatmap, explained variance, top-N table | OK | `loading_records`, `explained_variance_records`, top-10 per side (`feature_02.py:48,72-78`). |
| Factor returns + Sharpe/vol/maxDD/skew/kurt/AR(1) + t-stat | OK | `_stats` (`feature_02.py:26-39`) now includes `ar1_t_stat`. Old review.md gap fixed. |
| Varimax / Promax | OK / PROXY | Both wired (`:54-70`). Promax corr is `corr(rotated_scores)` (`:64`), a reasonable empirical Phi, not the textbook `Phi=(A^T A)^-1`. Acceptable if labeled. |
| Hoyer sparsity | OK | `hoyer_sparsity` + chart/table (`:92,:114,:124`). |
| Per-asset R2 | OK | `asset_r2` (`analytics.py:439-454`) + `asset_r2_table`. |
| Hierarchical PCA | OK / WRONG label | Real two-level `hierarchical_pca` (`:457-508`) + `hpca_cross_factor_returns`. But `hierarchical_pca_cluster_map` chart emits raw `cluster_loadings` dict (`feature_02.py:112`), not a heatmap/tree the `clusterMap` renderer understands (renderer falls back to generic table, `:440`). Dead `_cluster_map` helper (`:131-135`) still in file. Relabel or restructure. |
| Standardization toggle | MISSING | See B3. |
| Biplot (scores + loadings joint plot) | MISSING | No biplot key in backend or `PCA_OUTPUT_BOOKS`. Spec implies joint interpretation; never built. |
| Sign convention | Partial | Loadings have arbitrary sign (`eig_sorted` has no sign alignment). Rolling cosine uses `abs` (correct), but `rolling_loading_evolution` (`:2266-2303`) stores raw signed loadings with no alignment, so the F05 heatmap flickers sign across dates. Add sign-flip alignment to previous window. |

### Feature 3: Risk Decomposition and Attribution
| Spec item | State | Detail |
|---|---|---|
| PC variance stack + idiosyncratic, MRC table | OK | `risk_decomposition` (`:1103-1148`) + `feature_03.py:56,65`. |
| VaR/CVaR + waterfall | OK | Gaussian + CF + historical (`:1131-1145`); waterfall now uses true historical tail decomposition (`feature_03.py:79-99`), not the old proportional approximation. Old bug fixed. |
| Rolling per-PC decomposition | OK | `rolling_risk_decomposition` (`:566-589`) refits per window; fallback to rolling vol only on exception (`feature_03.py:36-41`, correctly marked fallback). |
| Active risk attribution | OK | Was the critical `risk["factor_rows"]`-instead-of-`active` bug in old `review.md`; now correctly uses `active["attribution_rows"]` (`feature_03.py:62,66,68`). Benchmark-PC correlation now uses true return correlation (`:102-108`), not variance-share proxy. |
| Covariance source toggle (RMT / full / raw) | Partial | Always `cleaned_cov` except F06 comparison. No user toggle. Acceptable if documented. |
| Currency hedging toggle | MISSING | No FX-hedged covariance block. |

### Feature 4: Residual OU Stat-Arb Engine
| Spec item | State | Detail |
|---|---|---|
| OU OLS + MLE, half-life/kappa/mu/sigma_eq, Z, direction | OK | `ou_signal_table` (`:1162-1214`) with delta-method `se_b/se_kappa`, `breakeven_z`, `days_since_signal_trigger`, `estimated_days_to_half_reversion`. MLE `ou_mle` (`:2202-2259`) on top-20. |
| Volume-time adjustment + calendar-vs-volume comparison | OK | `volume_time_residuals` + `_volume_time_comparison` (`feature_04.py:61-62,104-109`). Silent `except: pass` on missing dollar-volume remains (B3). |
| Signal decay (T+1..T+63) | OK | `signal_decay_analysis` (`:1758-1812`). |
| Backtest engine (gross/net, costs, DD, hit rate, holding period, turnover) | OK | `residual_ou_backtest` (`:1815-1879`) incl. `average_holding_period_days`. |
| Residual correlation heatmap in F04 | OK | Now present (`feature_04.py:80`, 60x60 cap). Duplicates F08 by design; fine. |
| OU distribution histograms | OK | Half-life/kappa/sigma_eq charts (`:81-83`). |
| Cost model beyond flat bps | Partial | `cost_bps` + square-root impact only in F11 liquidation, not in F04 backtest. Spec spread-proportional option MISSING. |

### Feature 5: Rolling Stability and Regime Monitor
| Spec item | State | Detail |
|---|---|---|
| Rolling PC1 share, eigen ratio, CUSUM + Bai-Perron | OK | `rolling_pca_metrics` (`:1217-1262`), `cusum_table`, `bai_perron_breakpoints`, wired in `feature_05.py:39-45`. |
| Multi-eigenvalue time series (top-K lines) | OK | `eigenvalue_pc1..5` columns (`:1246-1247`) + `multi_eigenvalue_time_series` chart (`feature_05.py:105`). Old gap fixed. |
| Multi-PC cosine drift (PC1-5) | OK | `cosine_pc1..5` columns (`:1248-1251`) + `multi_pc_cosine_drift` (`:106`). Old gap fixed. |
| PC1 percentile rank + loading evolution + principal angles | OK | `pc1_percentile_rank` (`:2310-2342`), `rolling_loading_evolution` (`:2266-2303`), `max_principal_angle_deg` via `subspace_principal_angles`. |
| Crisis bands (10) + regime summary | OK | 10 bands (`feature_05.py:131-143`), `_regime_summary` (`:146-158`). Old "only in F08" gap fixed. |
| Alert thresholds user-set | Partial | Cosine `< 0.85` (`:65`) and angle `> 15deg` (`:84`) hardcoded, not from payload. Wire `payload.cosine_threshold / angle_threshold`. |

### Feature 6: Constrained Optimization
| Spec item | State | Detail |
|---|---|---|
| Mean-variance / ERC (Spinu) / Max-Sharpe (Tobin) / PC risk parity | OK | Dispatched in `optimize_portfolio` (`:1291-1306`); `erc_portfolio`, `max_sharpe_portfolio`, `pc_factor_risk_parity_portfolio` all real. |
| Efficient frontier (100 Pareto-optimal, lambda sweep) | OK | `_efficient_frontier_qp` (`:1351-1387`) is a true `logspace(-3,4)` lambda sweep at 100 points with constrained QP. Old "35-point linear blend" finding is fixed and stale. |
| Shadow prices | OK | `optimize_portfolio_with_duals` (`:1688-1751`) reads `con.dual_value`. |
| Turnover constraint + cost comparison panel | OK | Wired (`:1324-1330`) + `transaction_cost_impact_panel` (`feature_06.py:47`). Only applies when `to_max < 1.0`; default 1.0 means unconstrained unless user sets it. Fine if labeled. |
| RMT-vs-sample comparison | OK | `sample_opt` on `raw_cov` + `rmt_vs_sample_allocation` (`feature_06.py:45-48`). Old gap fixed. |
| K-sensitivity OOS Sharpe vs K | OK | `k_sensitivity_sweep` (`:701-744`). Single IS/OOS split per spec; rolling rebalance variant MISSING (acceptable, spec asks single split). |
| Black-Litterman | Partial | Asset views real (`:747-791`). Spec PC-factor views MISSING (views on PCs, not assets). |
| Sector / factor exposure / tracking-error / cardinality constraints | MISSING | Only sum-to-one, long-only/max-weight, gross-limit, turnover (`:1319-1334`). No sector, PC-exposure, TE, or integer cardinality caps. |
| Rolling backtest of optimal portfolio | MISSING | No cumulative/rolling-Sharpe/DD/turnover chart for the optimized weights (only K-sweep OOS point estimates). |

### Feature 7: Bootstrap Validation and Genuineness Scorecard
| Spec item | State | Detail |
|---|---|---|
| Case / block / residual bootstrap | OK | All three in `bootstrap_validation` (`:1411-1421`); `block_bootstrap_sample` circular blocks. |
| Eigenvalue bands at selectable confidence | OK | `confidence_level` payload-driven (`:1396-1399`), full-spectrum bands (`:1432-1436`, old 25-cap removed), MP verdict per PC. |
| Cosine scorecard + subsampling KxK heatmap + principal angles | OK | `genuineness_scorecard`, `subsampling_stability` with full cross-matrix (`:849-889`), SVD `subspace_principal_angles` (`:892-900`), wired in `feature_07.py`. Off-diagonal swap detection now present. |
| Replication count | PROXY | Defaults B=30/80, hard caps 60/250 (`:1393-1394`) vs spec 200/500/1000. Bands at B=30 are unreliable for 5th/95th percentiles. Either raise research default or label "preview bands, raise bootstrap_runs for publication". Silent cap must be surfaced (B3). |
| Bai-Ng IC1/IC2/IC3 | OK | Proper SSR-based (`:794-829`). |

### Feature 8: Residual Contagion Monitor
| Spec item | State | Detail |
|---|---|---|
| Rolling group residual corr (primary) | OK | `rolling_group_residual_corr` (`:903-932`) + primary chart (`feature_08.py:65`). |
| Residual matrix heatmap, pairs, under-spec vs K | OK | `residual_contagion` (`:1458-1486`). |
| Rolling lambda1 + historical percentile alert | OK | `_rolling_residual_lambda1` (`feature_08.py:87-97`) + `lambda1_historical_percentile` (`:51,79`). Old "current-only" gap fixed. |
| Crisis overlay (10) | OK | 10 dates (`feature_08.py:23-34`). |
| Grouping options (sector/industry/region/size/custom CSV) | Partial | Sector-only via `sector_map`. Custom group upload MISSING. |
| Residuals use fixed-lookback PCA | Partial | `residual_matrix` uses the single `rmt_model` fit, not rolling refits. Rolling corr is rolling windows over fixed-model residuals, not rolling-model residuals. Label it or add `rolling_refit=true` option. |

### Feature 9: Stress Scenarios and PC-Shock P&L
| Spec item | State | Detail |
|---|---|---|
| 2K parametric shocks + heatmap + waterfall + worst-scenario | OK | `stress_scenarios` (`:1489-1508`). |
| Historical worst-day replay | OK | `historical_worst_day_scenarios` (`:935-959`) + chart/table. |
| Joint multi-PC shock | OK | `joint_scenario_pnl` (`:962-994`) via `joint_shocks` dict. |
| Stress VaR/CVaR (10K MC + 2K param) | OK | 10K Gaussian-factor MC + empirical 95th (`:1531-1540`). Covariance of MC draws is diagonal (`diag(stds^2)`), so cross-PC correlation is ignored. Label as independence approximation or sample from full factor covariance. |
| True Mahalanobis analogs + 60-day window + PC Z-scores/percentiles | OK | Inverse factor-corr Mahalanobis (`:1516-1519`), `window_60d_cumulative_return` (`:1523`), `current_factor_zscore` + `shock_historical_percentile` (`:1524-1530`). Old Euclidean finding is fixed and stale. |
| Multi-portfolio comparison (up to 4) | MISSING | Single `portfolio_weights` only. Spec heatmap across 4 portfolios absent. |
| PDF export | OK / PROXY | `stress_pdf_report_base64` real via reportlab; `None` with `reportlab_unavailable` flag when missing. Fine. |

### Feature 10: Cross-Asset RMT with Hedged Blocks
| Spec item | State | Detail |
|---|---|---|
| Block estimators (FX EWMA l=0.94, commodities/rates OAS, crypto Student-t EM, equity OAS-as-LW) | OK | `block_covariance` (`cross_asset.py:114-125`), `_student_t_em` (`:89-111`, tested). Equity uses OAS labeled `ledoit_wolf_equivalent_oas`; acceptable but relabel or use real LedoitWolf. |
| DCC conditional correlation + CASCI + rolling block monitor + stress overlays | OK | `dcc_correlation`, CASCI, rolling monitor, overlays in `cross_asset.py:195-334`. |
| Calendar alignment audit + hourly inventory + FX hedge ratios + crypto volume filter + CF-adjusted MP | OK | All emitted per `feature_10.py:42-55`. |
| Unified RMT cleaning of the N_total x N_total matrix | MISSING | PCA runs on aligned sample cov (`cross_asset.py:330`-area); block estimators feed block charts but not the unified matrix used for eigenvalues. No unified `lambda_max` filtering. |
| Block-conditional MP bounds overlay (unified + 4 block q ratios) | MISSING | Only unified-level eigenvalues returned; the spec primary chart (unified bound plus four block bounds, "cross-asset only" labeling) is absent. |
| Cross-block shrinkage slider (gamma_cross default 0.40) | MISSING | No `gamma_cross` blending of DCC cross-block vs unconditional. DCC feeds charts, not covariance assembly. |
| Cross-asset loading heatmap (N_total x K) + factor return series | Partial | `asset_class_pc_loading_share` only; full asset-level heatmap and cross-asset factor time series not returned. |
| Futures roll (Panama / ratio-adjusted with schedules) | PROXY | Yahoo-style continuous proxies; `futures_roll_audit.parquet` honestly marks them unverified (`audit.md:56`). Do not claim roll-adjusted. |
| MP overlay on unified spectrum | MISSING | Same root cause as F01 density gap, compounded by no unified cleaning. |

### Feature 11: Liquidity Factor and LaVaR
| Spec item | State | Detail |
|---|---|---|
| Amihud / Pastor-Stambaugh / Kyle branching + normalization options | OK | Branched in `liquidity_outputs` (`:1553-1584`): Amihud default, PS gamma (`:997-1028`), Kyle daily proxy (`:1031-1050`), rank/log/standardize normalization (`:1578-1584`). Old "always Amihud" gap fixed. |
| Latent factor via PCA + liquidity betas with NW SE + t-stats | OK | `vecs[:,0]` factor, `newey_west_se` (Bartlett, 3 lags, `:1053-1074`), per-asset percentile. |
| Augmented risk decomposition (PCs + Liquidity + idio) | OK | `augmented_risk_decomposition` (`:1627-1629`) + table. |
| Illiquidity-driven correlation heatmap | OK | `liquidity_driven_corr` (`:1623-1626`) + heatmap. Old gap fixed. |
| 3-signal unwind monitor | OK | p90 factor + top-20 corr 0.30 + beta threshold with count/flag (`:1630-1635`, `feature_11.py:50`). |
| Liquidation cost map (configurable participation) | OK | `adv_participation_rate` payload-driven (`:1616`). |
| MP-based K on illiquidity panel / IML alternative | MISSING | Always PC1 (`:1587`); no MP selection on illiquidity spectrum, no equal-weight IML factor (spec lines 817-820). |
| Turnover ratio illiquidity measure (needs shares-outstanding history) | MISSING | Only 3 of 4 spec measures; turnover ratio absent (shares history not in repo, honestly documented in `README.md:31`). |

---

## 4. Use open source that is already installed

Already importable (per `README.md:14` and runtime imports):

| Hand-rolled today | Replace / verify with | Why |
|---|---|---|
| `eig_sorted` + `mp_threshold` + `fit_mp_sigma2` (`analytics.py:202-219,360-383`) | Keep, add `sklearn.decomposition.PCA` as a golden-number cross-check in tests | Core math is correct; a 5-line PCA-vs-eigh equivalence test kills sign/scale regressions. |
| `covariance_estimator` LW/OAS/MCD (`:174-199`) | Keep `sklearn.covariance` (already used); route equity block in `cross_asset.py:124-125` through real `LedoitWolf` instead of OAS-aliased-as-LW | Removes a mislabeled estimator. |
| Circular `block_bootstrap_sample` (`:832-846`) | Keep, add `arch.bootstrap.MovingBlockBootstrap` as a test oracle (arch is the Research-review recommendation; verify import before adopting) | Proves the hand-rolled circular bootstrap matches a reference. |
| `newey_west_se` Bartlett HAC (`:1053-1074`) | Keep, verify once against `statsmodels.stats.sandwich.cov_hac` | One-line check that SEs are not off by a degrees-of-freedom factor. |
| `cusum_table` + Bai-Perron DP (`:1265-1272,1898-1960`) | Keep, verify break dates against `statsmodels.stats.diagnostic.breaks_cusumolsresid` on the PC1-share series | Gives the missing break p-value without a new dependency. |
| OU OLS/MLE (`:1162-1214,2202-2259`) | Keep `scipy.optimize` (already used) | Fine. |
| Frontier QP (`:1351-1387`) | Keep `cvxpy` (already used) | Fine. |

Worth adding (new dependencies, need approval):

| Library | For | Notes |
|---|---|---|
| `ruptures` | CUSUM/Bai-Perron p-values and confidence intervals (F05/F08) | Small, pure Python/C. Replaces hardcoded critical values with real CIs. |
| None for PCA core | Do not add `linearmodels` here | Unlike Research V2, PCA V2 does not need panel econometrics. Keep the stack as is. |

Frontend: `@tanstack/react-query` is installed (per Research review); use it for the run hook. For charts pick **one** of `recharts` / `echarts` / `plotly` / `d3` (all four are installed; the plan's P16 "no duplicate chart paths" rule applies). Current code uses `recharts` only; keep it and delete any parallel chart path.

---

## 5. Frontend review

- **No data flow (B1).** Pages render without `response`/`onRun`. `PcaV2Workbench` has no fetch, no loading, no error, no empty, no cancel states. The Run affordance is a dead `API pending` button.
- **Fake numbers everywhere (B1).** Every section renders `previewRows` `Math.sin` filler. A reviewer screenshot-matching backend values would fail on all 11 features. The scree `mp: 0.42` line and `2.7/(i+1)` eigenvalues are the most misleading because they mimic the two numbers (eigenvalue, MP bound) the spec cares about most.
- **Duplicated contract**: `components/pca-v2/registry.js` re-declares every feature's inputs/defaults/fields by hand (190 lines). Backend already exposes titles via `GET /labs/pca/v2/features`, and payload keys live in `analytics.py`/`load_context`. Drift already exists (e.g. frontend F01 `k_method: rmt` vs backend `component_count/k/variance_threshold`; frontend `outlier_filter: true/false + outlier_z_threshold` vs backend `outlier_method` string with 5+ modes; frontend F05 `rolling_windows` free text vs backend fixed `(21,63,126,252)` tuple). Fix: fetch the manifest and render from it; keep only presentation hints (chart type, rank) in the frontend.
- **Missing renderers for the two most important PCA visuals**: no biplot component and no MP-density-overlay component exist in `PCA_OUTPUT_BOOKS` or `RenderOutput` (`:438-446`: heatmap/table/metricDeck/waterfall/pie/tensor/line-bar-scatter only). Even after wiring, F01/F02 cannot satisfy the spec without new chart types.
- **Misleading options**: F01 exposes `blend_gamma` correctly but hides the 5 outlier modes behind a boolean; F05 `loading_evolution_pc` is 0-indexed in backend but presented without an index note; F10 `blocks` token filter has no backend key match (`symbols_from_payload` reads `equity_symbols/fx_symbols/...`, not `blocks`), so the token selection is silently ignored.
- **`file_path`-style inputs avoided, but equivalents remain**: no server-path inputs (good, unlike Research), but `weights`/`bl_views`/`joint_shocks` free-text JSON textareas have no parse validation or upload path. A malformed JSON paste fails opaquely. Reuse the Studio data-studio upload and pass structured holdings.
- **`customPagePrimitives.jsx`: 931 lines** with the full design system inline (`<style jsx global>` from `:572`). Same disease as Research (51 KB, CSS-in-JS blob). Move CSS to a module/Tailwind, split into Workbench, InputDeck, OutputCard, renderers.
- **Unreachable in effect, if not in routing**: home page links to all 11 slugs work, but no page can produce a backend-backed visual. Every section is unreachable UI for real data.

---

## 6. Codebase-wide pattern (same issues across the V2 modules)

Seen while reviewing; each deserves the same pass.
- **Seven copies of `core/data_loader.py`** (factors, ml, pca, portfolio, research, screener, volatility) and seven `core/analytics.py` files. Same parquet readers, symbol parsing, silent universe fallback. Fix: one shared `app/services/shared/market_data.py`; modules keep only their analytics. PCA's `parse_symbols` fallback is the instance to fix first.
- **Seven `components/*-v2/customPagePrimitives.jsx`** files with per-module tokens and generic renderers, each with its own `previewRows`-style filler risk. Fix: one shared Lab workbench + renderer registry; per-module files only declare sections. PCA is the proof that filler must be banned by a lint rule (`Math.sin` in a components directory should fail CI).
- **`review.md` overstates wiring**: checklist line 16 claims "API routes are wired under `/api/labs/pca/v2`". The file exists; the mount does not. `DONE`-style checklists mark execution-path success as user-facing completion. Update the checklist to distinguish "runs in Python" from "reachable from UI with real numbers".
- Backend deps are ranges, no lock (P17 gap, same as Research review).
- `backend/tests/test_pca_v2_remediation.py` is 34 lines / 3 tests. Every V2 module has the same thin-test pattern. Golden-number tests against known spectra must become the norm.
- `analytics.py` is 2,342 lines with a `model: dict` passed everywhere, `number_like` swallowing conversion errors (`:75-80`), and duplicated `model_annualization` calls (`:1280-1281`). Split into `pca_math.py`, `optimization.py`, `bootstrap.py`, `ou.py`, `scenarios.py`, `liquidity.py` when next touched.

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Wiring | Mount `api/pca_v2.py` in `main.py`; React Query hook; pages pass `response`/`onRun`; delete `previewRows` filler; heavy features via job transport | S |
| 2 | Data integrity | 422 on unknown tickers; surface requested-vs-resolved + `volume_time_fallback` + `bootstrap_runs_requested-vs-executed` + MCD fallback in `meta`; make outlier-filter default explicit | S |
| 3 | Correctness (PCA core) | Corr-matrix/standardization toggle; gate Kaiser to corr path or relabel; sign-align `rolling_loading_evolution`; MP density series for F01 overlay | M |
| 4 | Frontend renderers | Real biplot + MP-overlay chart types; manifest-driven inputs; JSON validation/uploads for weights/views/shocks; loading/error/empty/cancel; split primitives; fix F10 `blocks` key mismatch | M |
| 5 | Feature 10 hardening | Unified RMT cleaning; block-conditional MP bounds overlay; `gamma_cross` shrinkage assembly; full N_total x K loading heatmap + factor return series; relabel equity OAS vs LW; keep futures-roll proxy label | M |
| 6 | Feature 6/8/9/11 polish | Sector/factor/TE/cardinality constraints + PC-factor BL views + rolling backtest (F06); custom group upload + rolling-refit option (F08); 4-portfolio compare + full-cov MC (F09); MP-selected K + IML alternative on illiquidity panel (F11); user-set alert thresholds (F05) | M |
| 7 | Tests | Golden spectra (known covariance with planted spikes: K recovery, MP bound, RMT condition improvement); corr-vs-cov Kaiser test; sign-stability test; universe-fallback 422 test; API mount smoke test; frontend renderer snapshot against a canned response | M |
| 8 | Cleanup | Shared `market_data.py` + shared Lab workbench across V2 modules; `Math.sin`-in-components lint ban; split `analytics.py`; update `review.md` wiring claim; lock deps | L |

Recommended next step: items 1 and 2 together (small, and they make the module both usable and honest), then 3 with tests from 7 alongside.

---

## 8. Addendum (verified 2026-10-03)

These came from a second read of the code and were not in the first pass. Read [V2_REBUILD_PLAYBOOK.md](V2_REBUILD_PLAYBOOK.md) before fixing; frontend work (section 5) is reserved for Claude.

**Correction to B1:** the router **is now mounted** (`backend/main.py:164-165`, `/api/labs/pca/v2`). The rest of B1 still holds: `lib/api.js` has no PCA V2 run helper, and `customPagePrimitives.jsx` still has 10 `Math.sin`/"API pending" fabrications.

| # | Area | Finding | Where |
|---|---|---|---|
| A1 | Look-ahead (F04) | The OU stat-arb backtest uses eigenvectors and residual betas fitted on the **full sample** (`residual_matrix` regresses all dates on full-sample factor returns), then trades signals on those same dates. It is in-sample by construction. Refit PCA and betas on a rolling window ending at t, and trade t+1. | `analytics.py:1151-1159`, `feature_04.py:60` |
| A2 | Fake zero returns | Missing returns are filled with `0.0` after forward-filling prices. Zeros pull variances down and correlations toward zero, which directly distorts the eigenvalue spectrum, the MP fit and K selection, the core of this module. Use pairwise-complete covariance or drop or impute explicitly, and report coverage in `meta`. | `data_loader.py:208,211,310,317`; `analytics.py:159,175` |
| A3 | Universe | Default universe and the silent fallback (B2) resolve to tickers with the most history (survivorship-biased), and the default label does not say so. | `data_loader.py` `source_symbols` |
| A4 | OOS split | `oos_fraction` splits once at 70/30 with no embargo; residual and factor scoring on the OOS part reuses symbols chosen on full-sample coverage. Disclose or purge. | `analytics.py:704-738` |
| A5 | Errors | 28 `except Exception` blocks in `core/`; several (volume-time, bootstrap caps) turn failures into silent fallbacks with `status: ok`. | `core/*.py` |
| A6 | API | Runs are synchronous; F05 rolling and tensor, F07 bootstrap and F10 cross-asset need background jobs (Studio `JobStore` pattern). | `api/pca_v2.py:27-35` |
| A7 | Tests | Only `test_pca_v2_remediation.py` (3 tests). Add golden numbers (MP edge vs closed form on simulated white noise; RMT cleaning recovers a planted spiked covariance), a look-ahead guard for F04, and a no-zero-fill test. | `backend/tests/` |

## 9. Backend rebuild status, 2026-10-04

The PCA backend was rebuilt against this review and `V2_REBUILD_PLAYBOOK.md`. See `backend/app/services/pca_v2/DONE.md` for architecture, old-file fate, estimator choices, exact checks and limitations. The existing API mount was retained; shared application files and the frontend were not edited.

Closed backend defects include strict unknown/partial ticker errors, undersized-universe replacement, price forward-fill and zero-return fabrication, historical date filtering, covariance/correlation semantics and Kaiser gating, sign alignment, real MP-density/biplot data, full-sample F04 backtest fitting, non-working signal exits, silent bootstrap caps, MCD fallback, volume-time fallback, mislabeled equity OAS, full-covariance stress Monte Carlo, and missing manifest/jobs/uploads. F06 now has common sector/factor/turnover/tracking-error constraints, actual posterior returns and a historical rolling backtest. F08 supports custom/uploaded groups and causal residual refits. F11 has an IML option, MP-retained component series and corrected HAC inference.

A further numerical defect was found: the original Newey-West covariance formula divided by sample size twice despite using an unnormalized inverse cross-product matrix. The statsmodels reference implementation now supplies HAC standard errors, protected by a golden-number check.

Unavailable items are explicitly rejected or recorded as limitations: cardinality without a mixed-integer quadratic solver, true Kyle without signed intraday flow, turnover illiquidity without historical shares, historical index membership, currency-hedged portfolio attribution and independently verified futures rolls. The frontend still needs Claude's separate rebuild and verification; backend fixture/HTTP success is not a claim of frontend completion.
