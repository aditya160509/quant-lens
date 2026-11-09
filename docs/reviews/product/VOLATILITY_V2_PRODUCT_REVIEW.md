# Volatility product review: volatility lab, redone against the feature rule

Redone 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b. It replaces the 2026-11-06 version. Code claims were read in `backend/app/services/volatility_v2/` on this date: registry, `core/vrp.py`, `core/budget_forecasts.py`, `core/performance.py`, `core/connectedness.py`, `core/dcc.py`, `core/stress.py`, `features/feature_05.py`, `feature_06.py`, `feature_09.py`, and grep checks across all of it. Competitor prices were fetched on this date where marked. Nothing was run: no tests, no servers, no manifest call. The frontend was not read in this pass.

## Contents
1. Verdict
2. What is real and what is hollow
3. Parity with paid and free tools
4. Feature table: keep, build, later, cut
5. Our own ideas: freedom and customisation
6. Open-source picks and licences
7. Data limits
8. Build checklist (E easy, M medium, H hard)
9. Sources and unverified

---

## 1. Verdict

Volatility is the widest backend in the platform and the most honest about its inputs. Nine features cover estimators, GARCH, HAR, regimes, the variance risk premium, connectedness, DCC, stress and budgets. The 2026-11-06 review's hero literals and stale output keys are gone from the code. What is left is a product problem, not a maths problem: nine pages with no single workflow, a first screen of about 30 inputs, and three outputs that still over-claim.

- **Keep** all nine features as pages. Merge the duplicate outputs listed in the checklist (step 3 and review section 6.1 items).
- **Build** the workspace: one `/volatility` on `LabConfig`, forms from `GET /features`, and the five lead pages (Estimators, Forecast, Regime, Cross-asset, Budget).
- **Gate** the risk-premium page on matched implied vol. Without an observed surface it says "physical only" and disables VRP.
- **Cut** the claim of a trading signal. Volatility prints forecasts and limits; it does not promise returns.
- **Later**: observed options surfaces for non-US and single-stock names, point-in-time data, refreshed ETF and FX history.

---

## 2. What is real and what is hollow

Read in code on 2026-11-09. "Real" means the function body computes what its name says from the inputs. "Hollow" means a label, a literal or a fallback that the output does not earn.

| Area | Real (read in code) | Hollow, over-named or unverified |
|---|---|---|
| Hero literals (V01 18.4%, V04, V06 72) | Grep finds no hit in `backend/app`. Only in `docs/volitality ui upgrades.md` | Closed. Remove the doc line only if the docs are cleaned |
| Stale output keys (`vol_calendar`, `vol_ridge`, `volatility_cone`, `vol_signature`) | Not in code. Only in the docs file above | Closed in code |
| `SurfaceGrid` | No hit | Closed |
| Duplicate output `connectedness_at_risk` (feature 06) | Appears at `feature_06.py:144` and `:156`, and as a manifest key at `:235` and `:307` | **Still open.** Merge step 3 applies |
| `regime_probability_input` (feature 09) | Present in `feature_09.py` | **Still open.** Confirm and cut per checklist |
| `data_gaps` and `estimation_failures` | `data_gaps` in features 05 and 06; `estimation_failures` in feature 06 | Real hooks. Step 9 extends them to every page |
| VRP and implied vol (feature 05, `core/vrp.py`) | Implied-vol policy string in `feature_05.py:321`: exact observed dates, matching benchmark, no stale fill, no interpolation, no non-US VIX substitution. Lagged sums keep missing dates (`vrp.py:131`) | Real. The policy is the honest version of what the old review asked for |
| Kelly and BTZ (feature 09, `core/budget_forecasts.py`) | `kelly_target` computes constrained leverage and an optimal vol target from matured BTZ returns (`budget_forecasts.py:250-275`). Kelly is emitted as `status: unavailable` with a reason when inputs are missing (`feature_09.py:111`) | Real, and it fails visibly. Output needs matched IV and matured labels; the help text says so |
| Connectedness (feature 06, `core/connectedness.py`) | Synthetic array at lines 384-394 is a VAR simulation from fitted coefficients, not invented data | Real. Label the IRF as model-implied, not observed |
| DCC (`core/dcc.py`) | Two-stage, past-only, "without optimizer fallbacks" (module docstring) | Real. Canonical DCC per merge-map decision 14. Factors F08 runs a different EWMA DCC and must say so |
| Stress (`core/stress.py`) | Seeded `default_rng` at line 155; shocks drawn from matched history | Real. Confirm the reverse-stress copula option before counting it done |
| Bootstrap (`core/performance.py:230-246`) | `stationary_bootstrap_jit` calls `np.random.seed(seed)` and then draws inside a `prange` loop | **Not reproducible across thread counts.** Under Numba parallel, each thread has its own RNG state. Fix with per-replicate seeds before any golden test relies on it |
| Global RNG side effect | The `np.random.seed` call changes process-wide state for every caller | Hollow determinism claim. Same fix |
| Frontend controls (`compute_mode`, `active_estimators`, `cross_asset_panel`, `network_layout`, `cross_asset_mode`) | `compute_mode` appears only in `DONE.md`. The other four have no hit in `backend/app` | Frontend not read. Verify in `frontend/src/components/volatility-v2/` before deleting, per the AGENTS deletion rule |
| Tests (88 passing) | Not run in this pass | Unverified. Step 1 of the checklist |

---

## 3. Parity with paid and free tools

Checked 2026-11-09 by fetch unless marked. Prices move; re-check before any pricing decision.

| Tool | What it does for volatility | Price (verified or not) | Where we stand |
|---|---|---|---|
| NYU V-Lab (Engle) | Real-time volatility, correlation and risk measurement; GARCH, DCC, DCC-style correlation, global gauges | Free. Page fetched 2026-11-09; no pricing shown | Our feature 02 to 07 cover the same models. We lack its live refresh and its global index coverage |
| Koyfin | Screens and charts with some vol metrics; no vol model suite | $0, $39, $79 per month (Plus, Premium), fetched 2026-11-09 | We beat it on models and limits; it beats us on data breadth and charting |
| Bloomberg VOL, OVDV, IVOL | Implied vol surfaces, term structure, vol-of-vol | Not priced. Not fetched (blocked on 2026-11-09) | Observed surfaces are the gap. Feature 02 IV surface page is "no observed options surface" |
| Portfolio123 (Ultimate, Portfolio tier) | Risk and ranking tools, not a vol lab | Screener $84, Backtest $167, Portfolio $250, Ultimate $500 per month, billed monthly, fetched 2026-11-09 | Not a direct competitor. Its position-sizing and rebalance tools overlap feature 09 |
| arch (Python) | GARCH, EGARCH, HAR, bootstrap and forecast evaluation | Free, BSD-style licence, see section 6 | We use it. Our layer adds limits and honest labels |
| hmmlearn, scikit-learn | Regime models | Free | Used in Factors F04; Volatility regimes use their own kernel |

**Where we are honest and they are not.** None of the above prints a data limit, a failed estimator or a missing implied-vol surface next to the answer. Our feature 05 policy string is the model.

---

## 4. Feature table: keep, build, later, cut

| # | Feature (registry title) | Decision | Page | Reason |
|---|---|---|---|---|
| V01 | Multi-estimator daily volatility engine | Keep; page Estimators | Estimators | Five estimators with an efficiency table; print the best one for the name and window with the reason |
| V02 | GARCH family suite | Keep; tab of Forecast | Forecast | Default four models; never a single "best" model |
| V03 | HAR forecasting suite | Keep; tab of Forecast | Forecast | Eight variants; scoreboard in the same view |
| V04 | Regime detection engine | Keep; page Regime | Regime | Shares its kernel with Factors F04 (decision 7; diagonal covariance by default) |
| V05 | Variance risk premium monitor | Keep, gated | Risk premium | Needs matched observed implied vol. Otherwise "physical only" and VRP disabled |
| V06 | Cross-asset connectedness | Keep; page Cross-asset | Cross-asset | IRF labelled model-implied. Fix duplicate `connectedness_at_risk` |
| V07 | Multivariate volatility and DCC | Keep; lens on Cross-asset | Cross-asset | Canonical DCC (`core/dcc.py`). Share the covariance engine with Portfolio (decision 3) |
| V08 | Volatility stress testing | Keep; lens on Cross-asset, one reverse-stress exhibit | Cross-asset | Reverse stress with copula option is the hard item; mark it H |
| V09 | Volatility budget monitor | Keep; page Budget | Budget | Kelly and BTZ as shared engine with Portfolio F10. Validate hand-off with trial count |
| Output | `regime_probability_input` (feature 09) | Cut unless a caller exists | none | Confirm no caller, then remove |
| Output | `connectedness_at_risk` duplicate | Merge to one | Cross-asset | Duplicate in manifest and tables |
| Input | `asset` alias | Hide from the UI; keep the backend alias | none | Two names for one input confuses the form |
| Control | `compute_mode`, `active_estimators`, `cross_asset_panel`, `network_layout`, `cross_asset_mode` | Remove or wire; verify in frontend first | none | Display-only if they have no backend effect |
| Later | Observed options surface, non-US and single-stock IV | Later, paid data | none | Needs a vendor; today only via `iv_upload_id` |
| Later | Refresh of ETF history (ends January 2026) and FX (ends February 2026) | Later, free data | none | Refresh source and licence first |
| Later | Point-in-time data add-on | Later, paid data | none | Desk tier |
| Cut | "Trading signal" wording on any page | Cut | all | Volatility forecasts risk; it does not promise returns |

---

## 5. Our own ideas: freedom and customisation

1. **Pick the estimator, keep the others visible.** One input picks the estimator used downstream; the table of all five stays on the page.
2. **Pre-registered vol target.** Save the target, gross cap and forecast source before a run; score the realised outcome against a breach log (checklist, step 9).
3. **Bring your own implied vol.** Upload a dated IV series (already `iv_upload_id`); it joins the same matched-date rules, no fill.
4. **Model-set choice.** Pick any subset of the GARCH and HAR variants and see the confidence set, not one winner.
5. **Limits banner as an object.** The same limits text appears on every result and in every export.
6. **Compare two runs.** Same as Factors idea 7: the same payload with one input changed, differences highlighted.

---

## 6. Open-source picks and licences

| Library | Use | Licence | Status |
|---|---|---|---|
| arch (bashtage/arch) | GARCH family, HAR, stationary bootstrap, forecast evaluation | Repository fetched 2026-11-09 (1.6k stars). Licence file not fetched; treat as BSD-3-Clause, **unverified** | Already used. Keep |
| hmmlearn | Gaussian HMM for regimes | BSD-3-Clause, **unverified** this pass (repo fetch returned 404) | Already used in Factors F04 |
| scikit-learn, statsmodels, scipy | Shared numeric and regression | BSD-3-Clause, standard, **unverified** this pass | Already used |
| Numba | `prange` bootstrap | BSD-2-Clause, **unverified** this pass | Already used. Fix the RNG (section 2) |
| linearmodels (bashtage) | Panel and IV regressions if needed for the matched-IV work | Not fetched (unreachable 2026-11-09) | Candidate only |

Pick: keep the current stack. Do not add a dependency for the workspace or the trust work.

---

## 7. Data limits

These print on every result (checklist, Batch 10 and Trust batch):

- ETF price history 2015 to January 2026; FX to February 2026.
- Hourly prices 2023 onward for 272 tickers.
- VIX term legs from 2016.
- Source of the price files is not recorded. Record it before any charging.
- No observed options surface for most names. The IV surface page says "no observed options surface"; it never fills.
- Model-implied connectedness and IRFs are not observed.

---

## 8. Build checklist (E easy, M medium, H hard)

The list lives in `docs/plans/VOLATILITY_CHECKLIST.md`. Summary of the changes this review makes to it:

- Step 1 (clean) is partly done in code. Hero literals and stale keys are gone. The test run is still open.
- Step 2 (remove literals) is done in code except the `asset` alias and display-only controls, which need a frontend read.
- Step 3 (duplicate keys) is open: `connectedness_at_risk` in feature 06.
- New item: fix the bootstrap RNG so draws do not depend on thread count (E).
- New item: label IRF and connectedness outputs as model-implied (E).

Size: E 6, M 6, H 3 across the batches, including the later items.

---

## 9. Sources and unverified

Fetched 2026-11-09:
- V-Lab: https://vlab.stern.nyu.edu/
- Koyfin pricing: https://www.koyfin.com/pricing/
- Portfolio123 plans: https://www.portfolio123.com/sv/register/pro
- arch repository: https://github.com/bashtage/arch

Unverified in this pass:
- Bloomberg volatility products (blocked), and any price for them.
- Licence texts for arch, hmmlearn, scikit-learn, statsmodels, Numba and linearmodels. The arch licence file and the linearmodels repo were not reachable.
- 88 passing tests (not run).
- Frontend controls and the frontend review (not read).
- Whether `regime_probability_input` has any caller outside feature 09.
- Numerical correctness of every estimator and forecast (read, not run).
