# Portfolio V2 Review: Spec vs Implementation vs Frontend

## Backend rebuild status, 2026-10-08

Portfolio V2 backend review work is completed and verified in this checkout. B1–B4 and A1–A9 backend failures are corrected: strict symbols, honest optimizer/frontier failures, signed exposure/NAV and manifest contracts, executed-turnover costs, true walk-forward estimation, preserved missing observations, compound monthly returns, actual trial multiplicity, historical sector restrictions, versioned caches, and background jobs. Per-feature proxies are replaced by measured/library-backed calculations or removed with explicit missing-data disclosures. The monolithic analytics implementation is removed; backend tests occupy the four framework files. A10 documentation is reconciled in [Portfolio V2 DONE.md](../../backend/app/services/portfolio_v2/DONE.md). That document records architecture, old-file fate, every feature's estimators, limitations and exact verification commands.

Verification: 84 targeted backend tests pass with local real-data integration enabled, including all 13 feature runners; backend Ruff and mounted import/route checks pass. Historical membership/delisting coverage, calibration-only datasets, actual external peer/strategy inputs, and other data-dependent claims remain explicit limitations, not proxies. Frontend work, browser/Jest/build checks, other V2 consolidation, and V1 deletion are excluded by the user's current scope. The original review below is preserved as audit history, not the current completion checklist.

Additional findings fixed: covariance eigenvalues were accidentally squared in PSD reconstruction; nonlinear tangency optimization could report a suboptimal solution with redundant gross/net constraints; the archived macro slope had no matching daily observations; and correlation-excluded fixed-zero strategies destabilized the allocation solve. Independent golden numbers and live-data checks cover the replacements.

Date: 2026-09-29
Scope: `backend/app/services/portfolio_v2/` (spec: `docs/portfolio features.md`, code: `core/analytics.py` 1,786 lines, `core/data_loader.py` 375 lines, `core/performance.py` 470 lines, 13 feature files), `backend/app/api/portfolio_v2.py`, `backend/app/services/portfolio.py` + `portfolio_var.py` (legacy, for duplication check), `frontend/src/app/labs/portfolio-v2/`, `frontend/src/components/portfolio-v2/`.

Smoke check: not run as a suite (there is none). Every feature exposes `run(payload)` returning the `response()` envelope (`feature_id`, `status: ok`, `summary_cards`, `charts`, `tables`, `meta`), so it *looks* complete. Unlike Research V2, Portfolio V2 **is wired**: `backend/main.py:182-183` mounts `portfolio_v2.router` at `/api/labs/portfolio/v2`, the Next.js rewrite (`frontend/next.config.mjs:71-78`) proxies `/api/:path*` to FastAPI, and `PortfolioV2Workbench` POSTs `{payload}` to `/api/labs/portfolio/v2/feature/{id}/run` (`customPagePrimitives.jsx:288-295`). The review below is about whether the numbers are right, whether the UI shows what the backend computed, and which inputs silently do nothing.

Spec numbering note: the spec doc numbers its features 1-10, 12, 13, 15 (13 features; 11 and 14 do not exist). Implementation `feature_01..feature_13` map to spec 1-10, 12, 13, 15 in order. "F11/F12/F13" below mean implementation numbers (= spec 12/13/15).

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **OK** | Router mounted, proxy configured, workbench fetches and renders. The one V2 module that runs end to end. |
| Optimizer correctness | **Partly correct** | Real SLSQP/GMV/Sharpe/RP/max-div/HRP/CVaR-LP/Kelly/BL, PSD-guarded covariances, but silent 1/N fallbacks and infeasible frontier targets. |
| Cost / turnover math | **Broken** | F02 daily drag uses a weight-sum proxy; F11 hardcodes the IS split and always reports delay cost 0. |
| Weight reconciliation | **Broken** | `parse_weights` abs-normalizes (kills 130/30 and market-neutral); `aum` vs `portfolio_nav` drift means F07/F11 silently price a $1M book; frontend mixes all 9 objectives into one allocation chart. |
| Frontier | Partly correct | 100-point frontier exists, but targets below GMV return are infeasible and fall back to 1/N without a flag. |
| Features 2, 3, 5, 6, 8, 9, 10, 13 | Partly correct | Real engines with honest `access_issues` in places, but several statistics are mislabeled or heuristic (DSR trials, HLZ threshold, MinTRL units, Chow-F, crowding percentile). |
| Features 7, 11, 12 | Mostly fine / honest | Real Amihud/DTL/AC-trajectory/overlap math; F12 explicitly refuses synthetic peers; weak spots are documented below. |
| Tests | **None** | No `portfolio_v2` test file; `backend/tests/` (31 files) has zero references to `portfolio_v2`. Only the module's own `review.md` checklist. |
| Frontend | Wired but misleading | Real data flow, but fake sparklines, a static risk dial, an always-zero warning strip, and unreachable inputs. |

Bottom line: the module *runs* and most engines compute something real, but a PM would get silently substituted universes, silently defaulted NAVs, cost numbers from a hardcoded split, and frontier points that are 1/N in disguise. Fix order: kill the silent fallbacks, fix the contract drift (`aum`, `objective`, `access_issues`), repair cost math, then add golden-number tests.

---

## 2. Blockers (fix first)

### B1. Silent universe substitution, twice stacked
- `parse_symbols` (`core/data_loader.py:202-206`): if none of the requested tickers exist, it silently returns `universe[:default_limit]`. A user asking for "XYZ, ABC" gets results on someone else's 80 stocks.
- `load_context` (`core/analytics.py:194-196`): if the return matrix still has fewer than `min_symbols` columns, it **again** silently replaces the universe with defaults. Two stacked fallbacks, neither surfaced (this one does not even add an `access_issue`).
- Fix: return/raise a 422 naming the missing tickers (the router already maps `ValueError` to 422, `api/portfolio_v2.py:24-25`). Same fix Research V2 B3 needs; share it.

### B2. Optimizer silently returns 1/N on failure, frontier includes infeasible targets
- `_solve_constrained` (`core/analytics.py:498-499`), `_min_var_target` (`:505-506`), `_risk_parity` (`:523`), `_max_diversification` (`:534`): every SLSQP failure returns equal weights with no flag. `optimize_portfolios` (`:434-443`) then publishes them as "global_min_variance" etc.
- Frontier (`:429-433`): 100 targets linearly spaced from `mu.min()` to `mu.max()`. Any target below the GMV return is infeasible under the same constraints, so `_min_var_target` fails and that frontier point is 1/N wearing a `target_return` label. No feasibility check, no per-point success flag.
- `cvar_minimize` (`:901-903`): LP failure also falls back to 1/N (at least the LP path is a real Rockafellar-Uryasev formulation, `:885-900`).
- Fix: add `success` per weight vector and per frontier point; drop or mark infeasible targets (start the grid at the GMV return); surface `result.message` in `meta`.

### B3. Frontend/backend contract drift: NAV, objective, and honesty fields
- `aum` vs `portfolio_nav`: `registry.js:63-67` (F07) and `:103-108` (F11) send `aum`, but `feature_07.py:18` and `feature_11.py:26` read `payload.get("portfolio_nav")`. Every F07/F11 run from the UI silently prices a **$1M** book instead of the $100M the user typed. `file:line` pairs: `registry.js:64` vs `feature_07.py:18`; `registry.js:104` vs `feature_11.py:26`.
- `objective: "min_variance"` (preset `customPagePrimitives.jsx:601-607`, "Defensive") matches no key in `weight_map` (`analytics.py:434-443`: keys are `global_min_variance`, `max_sharpe`, `inverse_vol`, `risk_parity`, `max_diversification`, `hrp`, `growth_optimal`, `black_litterman`, `cvar_min`). `feature_01.py:35-38` silently serves `max_sharpe`. The "Defensive" button runs the aggressive portfolio.
- `DataQualityStrip` (`customPagePrimitives.jsx:639-651`) reads `meta.notes/warnings/data_policy/engine`; backend `feature_meta` (`analytics.py:1777-1786`) writes `access_issues/performance/data_inventory`. Result: the strip always shows "LOCAL PARQUET / PORTFOLIO_V2" and **WARNINGS 0**, even when the backend reports `access_issues` (F02 point-in-time constituents, F09 ETF-AUM crowding, F12 peer-data refusal, F13 strategy proxies).
- `RiskTelemetry` (`:938-988`): `alerts` is always `[]` (no feature ever passes `alerts` to `response()`), so the dial needle (fixed SVG coords `:961-966`) and "CLEAR" status (`:970`) are decorative. Either emit real alerts (optimizer fallback, infeasible frontier, crisis DTL) or remove the dial.
- Fix: rename to one NAV key, validate `objective` against `weight_map` (422 on unknown), map `access_issues` to the strip, emit alerts on fallback paths.

### B4. Cost math is wrong, not just approximate
- F02 (`feature_02.py:49-50`): `turnover_proxy = |w|.sum() / rebalance_days`, subtracted **every day** (`net = gross - cost * proxy`). Cost should come from actual rebalance trades; this charges a full rebalancing fraction daily and scales with gross exposure rather than turnover. A low-turnover buy-and-hold book pays the same drag as a daily churner.
- F11 `is_decomposition` (`analytics.py:1587-1589`): permanent = 35% and temporary = 65% of impact, `delay_cost_bps` always 0.0, opportunity cost 0 by default. The pre-trade cost table is a fixed split, not a calibration.
- `execution_costs` sigma (`analytics.py:795`): derives "sigma" by clipping `liquidity_var_bps / 10000` to [0.005, 0.10], where `liquidity_var_bps = 10000 * sqrt(amihud * position)` (`:666`) has units of `sqrt(return * dollars)`, not return. Dimensionally incoherent; the resulting `market_impact_bps` inherits it.
- Fix: compute turnover from weight deltas at rebalance dates (F02 already builds walk-forward folds; reuse them); calibrate permanent/temporary split from data or label the 35/65 as an assumption; derive impact sigma from return volatility, not from liquidity VaR.

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = explicit stand-in; MISSING = not present.

### Feature 1: Portfolio Construction Engine
| Spec item | State | Detail |
|---|---|---|
| 9 objectives side by side | Partial | GMV, max-Sharpe, risk parity, max-div, HRP, BL, CVaR-min, growth-optimal/Kelly (`analytics.py:434-443`) all real. Markowitz trace ("100 lambda values") MISSING as an objective; the 100-point grid is min-var-at-target-return (`:429-433`), subject to B2. `inverse_vol` is extra, harmless. |
| 7 covariance estimators | OK / WRONG | Sample, Ledoit-Wolf, OAS, EWMA, constant-correlation, DCC-style, factor-structured, Gerber all run (`:254-309`) with `nearest_psd` (`:306`). WRONG label: "nonlinear_shrinkage" (`:274-285`) is a hand-rolled eigenvalue-to-median shrinkage, not Ledoit-Wolf nonlinear (Stein loss); acceptable if relabeled "eigenvalue shrinkage". DCC is EWMA-vol + DCC recursion on standardized residuals, a reasonable sketch, not full GARCH. |
| HRP | OK | Real Lopez de Prado recursion: single-linkage ordering, quasi-diagonal bisection with inverse-variance cluster weights (`:537-570`). (The old `review.md` audit calling it a proxy predates this implementation.) |
| CVaR minimization | OK | Real Rockafellar-Uryasev LP via HiGHS (`:877-905`). Long-only bounds hardcoded (`:900`); spec's 130/30 unreachable (see position-structure row). |
| Black-Litterman | Partial | Posterior formula correct (`:847-874`); but `views` is never collected: `optimize_portfolios` calls `black_litterman_weights(returns, gmv)` with `views=None` (`:445`), and no feature passes P/Q/Omega. Every BL run is just reverse-optimized GMV. |
| Position structure (long-only, 130/30, market-neutral) | MISSING | `_portfolio_constraints` (`:465-486`) always adds sum-to-1; `parse_weights` (`:250-251`) abs-normalizes, destroying leverage/short info. Market-neutral and 130/30 are unrepresentable. |
| Weight bounds, sector caps, turnover | Partial | Parsed (`:467-486`), including a correct /2 one-way turnover term. But `load_context` never injects `sector_map` into the payload `optimize_portfolios` receives, so sector caps from the UI can never bind; frontend exposes none of `min/max_weights`, `sector_max_weights`, `max_turnover` as fields. Unreachable. |
| Constraint binding report | WRONG | `feature_01.py:90-94`: statuses hardcoded `"satisfied"`/`"applied"`, values are `selected.sum()`/`selected.max()`. Never checks KKT/binding. |
| Risk contribution | OK | `rc = w * (Sigma w) / sigma` (`feature_01.py:44-49`), correct marginal-component form. |
| Covariance diagnostics | Partial | Condition numbers per estimator (`feature_01.py:57-70`) OK; Frobenius distance from sample, effective bets, OOS realized variance MISSING. |
| Weight stability index | PROXY | Cross-objective dispersion (`feature_01.py:79,95`), not the spec's rolling-12-rebalance heatmap. Labeled as dispersion, fine. |
| Turnover/cost summary, LaTeX/CSV | MISSING | JSON only; CSV export exists in the frontend (generic table dump), no LaTeX. |
| Kelly in F01 | OK | `growth_optimal` from `kelly_sizing` (`:442-443`). |

### Feature 2: Honest Backtesting Engine
- PSR formula inline (`feature_02.py:61-66`) correct in shape; DSR delegates to `deflated_sharpe_ratio` (`analytics.py:1068-1075`), shape-plausible. But `trials` is `rets.shape[1]` (asset count) because `variants_count` is referenced before definition (`feature_02.py:67` vs `:101`): the `in locals()` guard always falls through. Trials should be the number of strategy variants tried, not N assets. WRONG input, approximately right function.
- `harvey_liu_correction` (`:1085-1088`): Sidak-adjusted z-threshold compared directly against the Sharpe ratio, missing the `sqrt(1/T)` scale and SR variance. A Sharpe of 2.5 vs a z-bar of ~2.9 "fails" on wrong units. WRONG.
- `min_track_record_length` (`:1078-1082`) returns Bailey-Lopez MinTRL in the Sharpe's (annual) time units, but F02 labels it `min_track_record_length_days` (`feature_02.py:118`). Off by ~252x. WRONG label/units.
- PBO (`:1017-1046`): real CSCV over combinatorial half-splits with bounded enumeration, `pbo = mean(logit < 0)`. Reasonable engineering tradeoff vs all C(T,T/2); the bound should be reported (it is: `combination_count`). Partial/OK with disclosure.
- Walk-forward (`feature_02.py:76-87`): real IS/OOS folds with configurable window; IS/OOS ratio not computed (spec's >0.7/<0.3 rule MISSING).
- VaR trio OK (`value_at_risk_methods`, `:1049-1065`): historical, parametric normal, MC normal side by side. Cornish-Fisher lives only in legacy `portfolio_var.py`, not wired here.
- Survivorship: single `data_limited` row (`feature_02.py:121`); no before/after bps gap. MISSING (data genuinely absent; the disclosure is honest).
- Information ratio MISSING (never computed). Regime overlay on equity curve MISSING. Omega/Ulcer/Calmar/up-down/Politis-Romano block length all real.

### Feature 3: Performance Attribution
- Brinson (`:573-598`) + Brinson-Fachler (`:1146-1159`) real; benchmark is equal-weight universe in both (`feature_03.py:36,46`), consistent but the `benchmark` input (default `"SPY"` in registry) is ignored beyond parsing. A user-supplied benchmark never reaches the math. WRONG-ish: input accepted, unused.
- Factor attribution: the "waterfall" (`feature_03.py:50-53`) is `mean(return) * w`, a holdings-weighted mean decomposition, not a FF3/FF5/MOM loading x factor-return decomposition. Spec's factor model (FF3/FF5/FF5+MOM, `factor_taxonomy` input) MISSING; residual alpha MISSING.
- Linking (Carino/Menchero/GRAP, `:1127-1144`) real formulas, applied to active-vs-portfolio monthly effects. Arithmetic-naive comparison column MISSING (minor).
- Drawdown attribution real (`:1185-1195`, peak-to-trough window, per-asset contribution). Risk attribution real X-Sigma-Rho-style MCTE (`:1162-1167`).
- Skill-vs-luck (`:1170-1182`): iid bootstrap of the active-return t, 2,000 draws, not the spec's 10,000-draw within-sector random-selection null. PROXY, disclosed only by code, not by label.

### Feature 4: Stress Testing
- Historical replay (`:1198-1206`): replays the *portfolio's own* return history inside crisis windows (GFC/COVID/2022/SVB present), not the spec's factor-exposure x crisis-factor-sequence mapping. PROXY, reasonable given free data.
- Crisis menu covers GFC, COVID, 2022 rates, SVB 2023, plus quantile-labeled scenarios (`:727-751`); dot-com, European debt, 2018-Q4, Apr-2025 tariff shock MISSING as dated replays (names like `taper_tantrum_15pct` are quantile buckets, not the events).
- Reverse stress: `minimum_mahalanobis_reverse_stress` (`:771-784`) is the genuine constrained Mahalanobis projection with plausibility percentile via chi2 (`reverse_stress_test`, `:1209-1215`). Among the strongest implementations in the module. OK.
- Monte Carlo via stationary block bootstrap (`:754-768`) with Politis-Romano length (`:1119-1124`). OK; block-length override unlabeled in UI.
- Correlation breakdown (`:1218-1224`) re-prices under flat crisis rho. OK sketch. Stress verdict thresholds (`feature_04.py:63`) arbitrary but explicit.

### Feature 5: Macro Factor Model
- Portfolio + per-asset regressions real; Newey-West hand-rolled (`:1227-1247`) instead of `statsmodels` sandwich (works; replace per section 4). Per-asset batch uses Ridge lambda=1.0 hardcoded (`feature_05.py:57`); rolling uses plain solve with Ridge fallback (`:71-75`). Inconsistent regularization, undocumented.
- Factor set is price-derived only (VIX, curve slope, OAS, USD); GDP/CPI/PMI correctly removed per the spec's own "Inputs Removed". Target exposures, tolerance bands, risk-budget limits, fair-value panel MISSING (inputs accepted nowhere).
- MCTE / implied-alpha / crowding-rank / risk-budget tables real arithmetic on the estimated loadings. OK as constructed-exposure analytics.

### Feature 6: Regime Engine
- Detection: Gaussian HMM when installed and history suffices, else GMM, else vol-quantile (`:601-626`, `:1271-1283`). Real, with explicit fallback chain. Hamilton switching and VIX-classifier labels MISSING (spec lists them as options; HMM-only is defensible).
- `regime_conditional_weights` (`feature_06.py:42`): `1 + sharpe/4` clipped to [0.25, 1.5]. Heuristic, NOT the spec's `w* = sum_k P(k) w*(Sigma_k, mu_k)`. PROXY. Per-regime covariance is computed (`regime_conditional_cov`, `:1323-1328`) but never optimized against.
- Transition matrix, expected duration via KM survival (`:1302-1320`), nonhomogeneous transitions (`:1286-1299`), regime-conditional factor performance (`:1331-1338`) all real. Alert thresholds (`:46`) arbitrary but visible.

### Feature 7: Liquidity
- Amihud (dollar-volume version, `:629-668`) + recency-weighted variant (`:1341-1353`) + open-to-close option. Real. 15% and 20% ADV DTL both computed. OK.
- `liquidity_var_bps` (`:666`): `10000*sqrt(amihud*position)` is a dimensionally odd risk proxy; crisis cost = 5x and crisis DTL = /0.30 (`:1360-1361`) are hardcoded stress multiples. PROXY, labeled "crisis".
- Half-life (`:1374-1380`): `ln(0.5)/slope` of log-ILLIQ trend; negative-lambda guard returns None. Fine. Regulatory buckets (`:1383-1390`) real mapping; full SEC 22e-4/UCITS report MISSING (correctly: needs security master).
- Liquidation schedule (`feature_07.py:22-27`): equal daily slices, capped at 20 days. Orderly-playbook only; distressed/crisis urgency shapes MISSING.

### Feature 8: Correlation / Diversification / Contagion
- Pairwise corr, crisis-delta (`feature_08.py:46-65`), ENB/leading-eigenvalue, Marchenko-Pastur bound (`:1446-1448`), Mantegna MST (`:812-835`), agglomerative hierarchy (`:838-844`), precision-matrix network (`:1393-1403`), sector blocks (`:1433-1443`) all real. Strongest feature in the module.
- ENB uses the eigenvalue form `(sum l)^2/sum l^2`, not the spec's risk-contribution entropy `exp(-sum RC log RC)`. WRONG formula under the spec's name; both are legitimate concentration measures, relabel.
- `chow_test_breakpoints` (`:1416-1430`): trend-break F on a rolling-correlation series, no regressors, no p-value. Labeled "chow_f" but is not a Chow test. PROXY.
- Equity-bond tracker, DCC-per-pair dynamics MISSING (noted as extensions in `review.md`).

### Feature 9: Alpha Decay
- IC curve, hyperbolic/exponential/stretched selection by AIC (`:1455-1487`), half-life, optimal-rebalance (`:1490-1498`) real. Linear model candidate MISSING from selection (spec lists linear; only exp/hyp/stretched fitted).
- Crowding (`feature_09.py:49-54`): dispersion ratio mapped to percentile via `50 + 20*(d-1)` (`:52`). Arbitrary affine map. PROXY; spec's ETF-AUM proxy correctly disclosed unavailable (`:76`, table `publication_decay`).
- `alpha_capacity` (`:1501-1502`) with hardcoded Kyle lambda 0.10. PROXY.
- Judgment-taxonomy path (empirical IC only, no forced fit) MISSING: the parametric fit runs regardless of `factor_taxonomy`.

### Feature 10: Growth-Optimal Sizing
- Kelly core (`:695-724`): `solve(Sigma, mu)`, then `raw *= min(cap,|raw|)/|raw|`, then `clip(raw*fraction)`, then rescale. Capping *before* applying the fraction understates fractional Kelly whenever the full-Kelly vector exceeds the cap (the fraction should apply first, cap second). WRONG order; fix to `w = f*raw; cap; rescale`.
- `port_mu = mean(mu_arr)` (`feature_10.py:63`): cross-sectional mean of expected returns used as *the* portfolio drift for ruin/drawdown math, ignoring actual weights. Should be `w'mu`. WRONG.
- Drawdown-constrained leverage (`:1526-1529`), ruin surface (`:1539-1546`), turnover-optimal f* (`:1557-1560`) real approximations. Kelly-vs-Markowitz table real. Signal-decay handoff (`decay_adjusted_weights`) wired into charts. OK.

### Feature 11: Execution
- Almgren-Chriss trajectory (`:1563-1575`) real closed form; impact calibration `gamma = sigma/sqrt(ADV)`, `eta = sigma/ADV` (`:1606-1610`) is a dimensional sketch (sigma here is return-vol, ADV dollars). PROXY.
- `is_efficient_frontier` (`:1578-1584`): `impact = eta*trade^2`, `risk = sigma|trade|sqrt(lam)` traced over lam in [0,1]. Not the AC E-vs-SD frontier (variance should fall, not rise, with risk aversion). WRONG shape.
- `volume_profile_trajectory` (`:1596-1603`): synthetic U-shape `0.7+1.2*((i/T)-0.5)^2`. Fabricated intraday profile; spec admits daily-data approximation, but the UI presents it as a trajectory. PROXY, needs label.
- `correlated_multiasset_is` (`:1612-1615`): `gamma * t'Ct` with default gamma 0.1, no Riccati coupling. PROXY (spec's coupled extension correctly flagged unimplemented in `review.md`).
- `target_weights` parsed (`feature_11.py:21-25`) but the UI offers no target-weight input (registry F11 has no such field), so every UI run liquidates into itself: `current == target`, all trades zero. Unreachable input; see B3 pattern.

### Feature 12: Systemic Risk
- Honest refusal when `peer_portfolios` absent (`feature_12.py:28-35`) with `access_issue`. Best disclosure practice in the module. OK.
- Overlap index, fire-sale loss, DebtRank propagation (`:1632-1644`), SRC, liquidation-spiral (`:1673-1674`), cascade Monte Carlo (`:1652-1656`), overlap-reducing trims (`:1677-1682`) real arithmetic; DebtRank exposure = normalized overlap explicitly flagged as proxy (`feature_12.py:58`). Betweenness centrality MISSING (degree + eigenvector only, `:1663-1670`). Rolling DebtRank, path-level cascade MISSING (need peer history; correctly not faked).

### Feature 13: Multi-Strategy
- Accepts uploaded `strategy_returns` (`feature_13.py:20-30`); otherwise deterministic momentum/reversal/inv-vol/equal-weight proxies (`:1760-1774`) with an explicit note (`:74`). Honest PROXY pattern. OK.
- Kelly across strategies, Sharpe-momentum tilt, vol scaling, regime-conditional weights, kill-switch calibration, capacity realloc, netting savings (`:1743-1749`, weight-delta based) all real given the strategy panel.
- Correlation-constraint enforcement MISSING (input accepted, never enforced). Forward kill-switch simulation MISSING (historical calibration only). Risk budget is descriptive (`:59`), not a binding constraint.

---

## 4. Use open source that is already installed

Already importable (`backend/requirements.txt` confirms `cvxpy`, `arch`, `statsmodels`, `scikit-learn`, `hmmlearn`):

| Hand-rolled today | Replace with | Why |
|---|---|---|
| SLSQP GMV/max-Sharpe/RP/max-div + silent 1/N (`analytics.py:489-534`) | `cvxpy` (installed, **unused** by portfolio_v2) with DPP parameterization | Convex objectives get certificates of infeasibility instead of disguised 1/N; sector/turnover/leverage caps become one disciplined problem; B2 disappears. |
| Hand Newey-West (`:1227-1247`) | `statsmodels.stats.sandwich_covariance.cov_hac` / `linearmodels` (F02 already depends on the pattern) | Tested Bartlett kernel; removes the bespoke lag loop in F05. |
| iid skill bootstrap (`:1170-1182`), CSCV enumeration cap (`:1017-1046`) | `arch.bootstrap.StationaryBootstrap`, `MovingBlockBootstrap`, `arch.bootstrap.SPA` | Block resampling as the hon-backtest spec already demands; SPA/StepM for the trial-multiplicity story. |
| Trend-break "Chow-F" (`:1416-1430`) | `statsmodels.stats.diagnostic.breaks_cusumolsresid` + an Andrews critical-value table, or `ruptures` (new dep) | Gives the missing p-value/CI for pair-break and regime-break claims. |
| HRP stays | keep (`:537-570`, verified real) | Optionally cross-check against `riskfolio-lib` (new dep) golden vectors. |
| CVaR LP stays | keep HiGHS (`:877-905`) | Optionally move to the same `cvxpy` problem for unified constraints. |
| HMM/GMM stays | keep `hmmlearn`/`sklearn` | Already the right libraries. |
| IS frontier, volume profile, 35/65 split | `cvxportfolio` (new dep) for turnover-aware execution, or label as assumption | Removes the B4 fixed-split cost table. |

Frontend: only `recharts` is used here (good: no four-library duplication *inside* this module). Keep it that way; do not add echarts/plotly/d3 per-module.

---

## 5. Frontend review

- **Wired (unlike Research V2).** Pages pass `featureId` + output book; the workbench owns `fetch`/`response`/`onRun` (`customPagePrimitives.jsx:253-313`). Mount, proxy, and route all agree: `/api/labs/portfolio/v2/feature/{id}/run`.
- **Duplicated contract**: `registry.js` hand-declares titles/defaults/fields per feature while the backend exposes only `{id, module}` at `GET /features` (`api/portfolio_v2.py:11-13`) and per-file `INPUTS`/`OUTPUTS` that no endpoint serves. Drift already exists: `assets` vs `tickers` (works by accident: `parse_symbols` reads both), `aum` vs `portfolio_nav` (B3, silently wrong), `objective` values the backend does not know (B3), `expected_return_estimator`/`sector caps`/`target_weights`/`peer_portfolios`/`strategy_returns` never offered though the backend reads them.
- **Fake sparklines**: `sparkPoints(seed)` (`:2220-2224`) is `sin(i*0.9+seed)` polylines seeded by the card *value* (`MetricTape`, `:587`) and by row *count* (`HeaderPulse`, `:2112`). Every metric tape and card header draws data-shaped decoration from no data. Either plot the real series (equity/IC/exposure already in the response) or delete.
- **Static risk dial**: fixed needle/arc (`:948-969`), status derived from `alerts.length` (`:970`) where alerts are always empty. Always "CLEAR", including on optimizer fallback and crisis DTL. See B3.
- **Weight reconciliation failures**: (a) F01 `charts.weights` is the *all-objectives* `weight_table` (`feature_01.py:100`); `AllocationStack` (`:1276-1300`) renders the first 30 rows mixing GMV/max-Sharpe/RP weights per ticker with no portfolio grouping, and bar width `|w|*100%` (`:1291`) with `donutSegments` on `|value|` (`:2226-2235`) renders shorts as long allocations. (b) `Frontier` (`:1229-1265`) cannot show infeasible 1/N points differently because the backend does not flag them (B2). (c) `normalizePayload` (`:2207-2218`) maps only `assets`; `target_weights`, if a user hand-injects it, passes through unparsed while backend `parse_weights` expects its own shapes.
- **Unreachable UI**: F12 peer upload, F13 strategy-returns upload, F11 target weights, F01 sector/turnover/bound inputs, F05 targets/bands, F13 correlation constraint. F12 therefore always renders its refusal stub from the UI; F13 always renders proxies.
- **Dead keys, harmless**: `PORTFOLIO_OUTPUT_BOOKS` numeric keys `10/11/12/13` (`:134-148`) coerce to strings and resolve; F12 book lists `peer_data_requirement` under charts while the backend puts it in tables, found only via the `pick()` charts-then-tables fallback (`:2136-2142`). Works by accident; align the book sources.
- `customPagePrimitives.jsx`: 2,336 lines with the styles template truncated at 2,000 chars on read (one CSS-in-JS blob, `:2299-2336`). Same split prescription as Research V2: Workbench, ConfigCurtain, OutputCard, renderers, plus CSS to a module.
- No loading-beyond-rail, error (present, `:376-382`), empty (present), or cancel states for 5,000-path MC / full-universe runs; no job transport (acceptable at current sizes, revisit if F02/F04 grow).

---

## 6. Codebase-wide pattern (same issues across the V2 modules)

- **Seven copies of `core/data_loader.py` and seven `core/analytics.py`** (portfolio_v2 analytics alone 1,786 lines). Same parquet readers, symbol parsing, fallback logic. Fix: one shared `app/services/shared/market_data.py`; modules keep only their analytics. (Research V2 section 6 item, unchanged.)
- **Seven `components/*-v2/customPagePrimitives.jsx`** (portfolio's is 2,336 lines), each with its own tokens and generic renderer. Fix: one shared Lab workbench + renderer registry; per-module files declare sections only.
- **Legacy duplication**: `app/services/portfolio.py` (541 lines, disk-state holdings) and `app/services/portfolio_var.py` (1,579 lines: parametric/Cornish-Fisher VaR, component/incremental/stressed VaR, correlation stress, backtests, Kupiec) overlap F01/F02/F04/F08 conceptually but share no code with portfolio_v2 and are not called by it. Decide: port the Cornish-Fisher/component-VaR pieces into V2 (they would fill real F02 gaps) or delete the legacy path.
- **`cvxpy` installed but unused by portfolio_v2**; `linearmodels` used elsewhere but not in requirements (Research V2 section 6). Backend deps are ranges, no lock.
- `parse_weights` abs-normalization (`analytics.py:250-251`) makes short/leverage structures unrepresentable everywhere. Fix once in shared code: normalize gross exposure separately from net, or carry a `normalize_mode`.
- `review.md`/`NOT_DONE.md` checklists mark most features `[x]` complete. Given B1-B4 and the WRONG rows above, they overstate status. Update after fixes; keep the audit section as history.
- Spec-to-code numbering: implementation F11/F12/F13 = spec 12/13/15. Any shared manifest should carry both numbers to stop the next reviewer misfiling gaps under "F11".

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Honesty | Silent fallbacks to 422/flags: unknown tickers (`data_loader.py:202-206`), sub-`min_symbols` substitution (`analytics.py:194-196`), SLSQP/LP 1/N fallbacks + infeasible frontier points (`analytics.py:429-433,498-506,523,534,901-903`) | S |
| 2 | Contract | One NAV key (`aum` vs `portfolio_nav`, `registry.js:64,104` vs `feature_07.py:18`, `feature_11.py:26`); validate `objective` against `weight_map`; serve backend `INPUTS`/`OUTPUTS` from `GET /features`; map `access_issues` to the quality strip; emit real `alerts` or remove the dial | S |
| 3 | Correctness (costs) | Turnover from rebalance deltas (F02); calibrated or labeled IS split + nonzero delay (F11); volatility-based impact sigma (`analytics.py:795,666,1587-1589`) | M |
| 4 | Correctness (optimizer) | `cvxpy` GMV/Sharpe/RP/max-div with infeasibility certificates; Kelly fraction-before-cap (`analytics.py:703-708`); weight-aware `port_mu` (`feature_10.py:63`); BL views plumbing or removal; real binding report (`feature_01.py:90-94`); short/leverage representation | M |
| 5 | Correctness (stats) | DSR trials = variant count (`feature_02.py:67`); HLZ Sharpe-scale threshold (`analytics.py:1085-1088`); MinTRL units (`feature_02.py:118`); ENB formula label (`feature_08.py:43`); real Chow or relabel (`analytics.py:1416-1430`); regime-conditional optimization (`feature_06.py:42`); benchmark input honored (F03); linear decay candidate + taxonomy path (F09) | M |
| 6 | Tests | Golden-number tests per engine (GMV/Sharpe/RP/HRP/CVaR vs `riskfolio-lib` or closed forms; BL posterior; Brinson identity `alloc+sel+inter == active`; Mahalanobis projection; Amihud/DTL on fixtures); a silent-fallback guard test (unknown tickers 422, optimizer failure flagged, infeasible frontier marked) | M |
| 7 | Frontend | Real sparklines or none; live risk dial or none; per-portfolio weight views with sign-aware bars/donut; infeasible-point styling; uploads for `peer_portfolios`/`strategy_returns`/`target_weights`; sector/turnover/bound fields; split primitives + CSS module | M |
| 8 | Cleanup | Shared market-data loader and shared Lab workbench across V2 modules; port or drop legacy `portfolio.py`/`portfolio_var.py` overlap (Cornish-Fisher, component VaR worth porting); update `review.md`/`NOT_DONE.md`; dual spec/impl feature numbering in manifest | L |

Recommended next step: items 1 and 2 together (small, and they make every number the UI shows mean what it says), then 3 with tests from 6 alongside.

---

## 8. Addendum (verified 2026-10-05)

These came from a second read of the code and were not in the first pass. Read [V2_REBUILD_PLAYBOOK.md](V2_REBUILD_PLAYBOOK.md) before fixing; frontend work (section 5) is reserved for Claude. Blockers B1-B4 in section 2 were re-checked and are still open (no commits to this module since the review).

| # | Area | Finding | Where |
|---|---|---|---|
| A1 | "Honest" backtest is not a backtest (F02) | One fixed weight vector is applied to the whole history with an implicit daily rebalance; weights are never re-estimated. If the weights come from an optimizer run on the full window, the whole equity curve is in-sample. The "walk-forward" table just slices this single return series into train/test Sharpe pairs; nothing is refitted on the train slice. Rebuild as a real walk-forward: estimate weights on data up to t, hold to the next rebalance with drifting weights, charge costs on traded turnover. This also fixes B4's F02 cost drag. | `feature_02.py:34-90` |
| A2 | Fake zero returns | Prices are forward-filled and missing returns become `0.0` (`np.nan_to_num` in F02, `fillna(0.0)` in the loader). Halted or delisted names look riskless, which biases covariance, optimizer weights and Sharpe. Keep NaN and handle explicitly. | `data_loader.py:226,228,246,253`; `feature_02.py:45` |
| A3 | Monthly returns summed | Monthly heatmap and attribution effects use `resample("ME").sum()` on daily returns instead of compounding. Large months are misstated, and Brinson effects will not reconcile to the portfolio return. | `feature_02.py:70`, `feature_03.py:67-68` |
| A4 | DSR trial count | `deflated_sharpe_ratio` gets its trial count from `"variants_count" in locals()`, which is never defined at that point, so it silently falls back to the number of assets. Trials should be the number of strategy variants actually tried. | `feature_02.py:66` |
| A5 | Look-ahead in caps and sectors | `market_caps` and sectors come from today's fundamentals snapshot (BL equilibrium weights, sector caps); missing caps default to `1.0`. Fine for a current-day portfolio, look-ahead inside any backtest. Disclose, or use point-in-time caps (price x point-in-time shares) in historical paths. | `data_loader.py:267-289`, `analytics.py:215` |
| A6 | Universe | `"default"` resolves to the 80 tickers with the most price history (survivorship-biased), plus cross-asset ETFs by default. Label it as such. | `data_loader.py:168-206` |
| A7 | Caches | `_MERGED_OHLCV_CACHE` is a global loaded once and never invalidated, so data refreshes are invisible until restart. Key on parquet `mtime`. | `data_loader.py:118-139` |
| A8 | API | Synchronous runs with a raw `Dict` body; heavy features (F02 variants, F04 stress, F12 systemic) need background jobs (Studio `JobStore` pattern). | `api/portfolio_v2.py:16-25` |
| A9 | Errors and tests | 11 `except Exception` blocks; zero tests (confirmed: `test_studio_portfolio.py` is the Studio module, not this one). Add golden optimizer tests (GMV vs closed form, risk-parity equal contributions, HRP vs `riskfolio`/`PyPortfolioOpt` spot check), the frontier-feasibility check from B2, and a walk-forward look-ahead guard. | `core/*.py`, `backend/tests/` |
| A10 | Docs | `NOT_DONE.md`, `missing.md`, `review.md`, `docs_review.md`, `speed upgrades.md` overlap and partly contradict this review. Reconcile into one `DONE.md`. | `portfolio_v2/` |
