# ML product review: validation-first, redone against the feature rule

Redone 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b. It replaces the 2026-10-05 version. Backend claims come from function bodies read on 2026-11-09 under `backend/app/services/ml_v2/` and `backend/app/services/shared/stats.py`. Competitor prices and features come from pages fetched on the same date, listed in section 11. Items marked **unverified** were not read in code or not fetched.

## Contents
1. Verdict
2. Real versus hollow, from code read
3. Paid-feature parity table
4. Keep, build, later or cut, feature by feature
5. Our own ideas for freedom and customisation
6. Open-source picks and licences
7. Data limits
8. Screen and information
9. Build checklist
10. Tiers
11. Sources

---

## 1. Verdict

ML is the most complete validation stack in the platform. Its problem is not the maths. It is that the pieces do not yet hand off reliably, and the one feature that sells (Validate) is weaker than its verdict suggests.

- **Real.** Validate runs 14 sections on an uploaded strategy: CPCV, PBO, deflated Sharpe, minimum backtest length, a best-of-controls edge, multi-seed stability, plateau, leakage, transfer, bootstrap Monte Carlo, autopsy, improve, data quality and a reproducibility receipt. PBO and DSR call the single shared implementation in `services/shared/stats.py`, which is the decision in merge map section 8 item 1.
- **Hollow or weak, verified in code:**
  1. **Hand-offs are not durable.** `put_artifact` stores every Alpha, Allocation, Regime and Volatility result in an in-memory `OrderedDict` capped at `ARTIFACT_CAP = 32` (`ml_v2/core/common.py`). A restart empties it. Eviction after 32 runs also returns `None`. Every "pass the id to the next module" in the pipeline breaks silently when that happens.
  2. **The trial count is not counted.** `_trial_count` takes the larger of a user-typed `trial_count` and the column count of an uploaded trial matrix. It never reads the Research trial ledger, which holds Research and Screener trials. The deflated Sharpe therefore deflates by what the user typed. Research's own ledger `RESEARCH_ONLY` note in Validate names this gap.
  3. **The leakage badge is a pass for returns-only uploads.** In `block_leakage`, the returns mode runs one check: it perturbs the series after a cut and confirms Validate's own Sharpe is unchanged. Its own note says "Returns-only uploads cannot expose model leakage". The badge still feeds the verdict, where a pass reads as clean.
  4. **Some verdict rules are hard-coded.** `_verdict` treats DSR 0.95 as pass and PBO 0.3 as pass, and the rule text is returned to the user. Those cut-offs are not exposed as inputs.
  5. **Regime-switch vol uses a fixed 0.5 cut-off** on the stress probability (`volatility.py`, `_forecast_asset`). It is documented in `meta.regime_switch`, but not a user setting.
- **Competitor change since October.** Portfolio123's AI Factor, fetched 2026-11-09, now advertises blocked K-fold cross-validation with a one-year gap, lift charts and statistics, grid-search tuning and XGBoost and neural-network models. The October claim that nobody offers ML validation under $100 a month is no longer safe. Our edge is narrower and more honest: controls beaten, PBO and DSR at the true trial count, a verdict that names failures, a receipt that reruns exactly, and a stated refusal to validate what the data cannot show.

**Pitch, unchanged in spirit:** "Machine learning that shows its work. Every split purged, every result checked against a control, every claim reproducible. We tell you when your model is a bug."

**What blocks paying customers today, in order:**
1. Artifacts die on restart and after 32 runs, so a pipeline cannot be trusted across sessions.
2. Validate's trial count is typed by the user, not counted from the ledger that already exists in Research.
3. The leakage badge looks like a pass for uploads it cannot test.
4. No live refresh or alerts (later, section 4).

---

## 2. Real versus hollow, from code read

Status: **real** (function body read, behaviour matches the claim), **partial** (body read, a stated limit is material), **unverified** (not read in code this pass).

| Feature | Code read | Status | Evidence in code |
|---|---|---|---|
| Validate verdict and sections | `run_validate`, `_verdict`, `_receipt`, `_trial_count`, `prepare`, `frame_from_artifact` (`validate_engine.py`) | partial | Real sections and labels. Trial count typed by the user (item 2 above). Returns-only leakage is not a test (item 3). |
| PBO | `block_pbo` calls `shared.stats.cscv_pbo` | real | Logit of rank over N+1, the decided convention (merge map 8.1). Unavailable without a trial matrix with at least two columns. |
| Deflated Sharpe | `block_dsr` calls `shared.stats.deflated_sharpe_probability` | real | Variance across trials from the trial matrix, else 1/(T-1). Decision 6 satisfied. Trial count is the user's, not the ledger's. |
| Controls | `block_controls` | real | Best of cash, buy-and-hold, equal-weight, constant exposure, shuffled signal (95th percentile of permutations), lagged outcome and a 3-feature OLS model. Returns-only uploads get only cash and an optional benchmark. The rest is listed as unavailable. |
| Leakage | `block_leakage` | partial | Fixed-signal and model modes perturb data after a cut and check unchanged output. Returns mode is a weak self-check (item 3). |
| CPCV in Validate | `block_cpcv` | real for model mode; fixed-signal mode lists splits of one series | Says so in its own note. Engine body in `cpcv.py` (`run_cpcv_engine`) **unverified**. |
| Alpha (monthly GBT) | `run_gbt_alpha` lines 381 to 470 of 580 | real | Ensemble weights chosen on a validation window before the holdout is read. Ridge-to-tree scale locked there. OLS-3 and IC-composite controls. Time-decay sample weights. Optuna only in `optuna_research`. SHAP body and decile code **unverified** beyond the feature contract's notes. |
| Multi-horizon vol | `run_vol_forecasting`, `_forecast_asset`, `diebold_mariano` (`volatility.py`) | partial | HAR family, GJR-GARCH, regime-switch with DM test on QLIKE, FHS VaR and ES. Regime cut-off fixed at 0.5 (item 5). `arch_family` gives one-step forecasts only; macro is excluded without vintages (declared in notes). |
| Regimes | `forward_filter`, `run_regime_engine` (`regimes.py`) | partial | Forward filtering is real (`forward_filter` docstring; `probability_protocol` in meta). HMM is diagonal-covariance, three states, fit on the first 60 percent. Full body **unverified**. |
| Triple barrier and meta-labelling | `feature_04` contract; `run_triple_barrier` in `barriers.py` | unverified body | Contract notes say labels use real high and low paths and CQR is disclosed when unavailable. Body **unverified**. |
| Allocation | `run_hrp_optimizer` header, grep of `covariance_matrix`, `minimum_variance` (`allocation.py`) | partial | Default `min_variance` with Ledoit-Wolf, controls HRP, inverse-variance and 1/N, net of costs. `PPO`, `HERC` and tail-dependence are declared not implemented, with no proxy. Full body **unverified**. |
| Artifacts | `put_artifact`, `get_artifact` (`common.py`) | real, and a defect | In memory, capped at 32, evicted silently (item 1). |
| Shared stats | `services/shared/stats.py` | real | CSCV and DSR implemented once; `ml_v2/core/stats.py` re-exports them. |
| Studio pipeline | `StudioPage.tsx` (grep) | partial | Passes the Allocation artifact id to Validate, which accepts it. Passes the Alpha id to Meta-label. Depends on item 1. |
| Feature drift in Alpha | `_feature_drift`, `_what_changed` (`alpha.py`) | unverified body | Named in the old review as done. Body **unverified** in this pass. |

Frontend, read by grep only: `views.tsx` (SHAP feature detail inspector and scatter selections exist), `validateViews.tsx` (407 lines), `VerifiedPage.tsx` (66 lines), `TodayBoard.tsx`. Their behaviour is **unverified**.

---

## 3. Paid-feature parity table

Status values: **have** (code read, works as claimed), **partial** (code exists, a stated limit), **build** (data in hand, code or UI new), **later** (needs data or a live layer we do not have), **cut** (not ours to offer). Competitor sources are section 11.

| # | Feature | Who offers it | Our status | Note |
|---|---|---|---|---|
| 1 | Purged and embargoed cross-validation | P123 AI Factor (blocked K-fold, 1-year gap, fetched) | have | CPCV contract and `purged_complement`, `chronological_purged_split`. Embargo is a setting. |
| 2 | Lift chart and decile statistics | P123 (fetched) | have | `decile_spreads` contract, equal and value weight. |
| 3 | Model choice (linear, tree, boosted, neural) | P123 (XGBoost, neural nets, fetched) | partial | CPCV and Validate take ridge through CatBoost; Alpha offers ensemble, LightGBM, ridge, XGBoost, CatBoost. Neural nets only as `mlp` in CPCV. |
| 4 | Hyperparameter search | P123 (grid search, fetched) | have | `optuna_research` mode in Alpha, manual in Alpha, with trial rows audited. |
| 5 | Feature engineering from formulas | P123 (fetched) | have | Alpha accepts formulas through the Research formula language. |
| 6 | Feature attribution (SHAP) | P123 not stated | have (unverified body) | Exact TreeSHAP per notes; beeswarm and waterfall contracts. |
| 7 | Volatility forecast tournament | none | have | HAR family, GJR-GARCH, DM test. |
| 8 | VaR and expected shortfall | none | have | Filtered historical simulation at 95 and 99 percent. |
| 9 | Triple-barrier labels and meta-labelling | none | have (unverified body) | `feature_04`. |
| 10 | Allocation with controls | P123 portfolio optimisation (not fetched) | have | Shrinkage minimum variance by default, controls beside it. |
| 11 | Forward-filtered regimes | none | partial | Regime cut-offs fixed (item 5). |
| 12 | Validate with controls, PBO, DSR, leakage, transfer, bootstrap | none in P123 fetched pages | have, partial | Items 1 to 5 in section 1. This is our category. |
| 13 | Trial count from a shared ledger | none | build | Ledger exists in Research (`store/ledger.py`, Screener writes to it through `ledger_bridge.py`). Validate does not read it. |
| 14 | Durable results and hand-offs | P123 saves models | build | Artifacts are not durable (section 1, item 1). |
| 15 | Multi-seed stability | none | have | `block_stability`. |
| 16 | Transfer test (other assets or periods) | none | have | `block_transfer`. Body unverified. |
| 17 | Monte Carlo of the return path | none | have | `block_monte_carlo`. Body unverified. |
| 18 | Reproducibility receipt and rerun | none | have | `_receipt`: data, settings, seed and code hashes. Rerun needs the same upload. |
| 19 | Live refresh and alerts | P123 and others offer screen alerts | later | Needs a scheduler and alert delivery shared with Screener (Apprise plan, Screener review rows 73 to 75). |
| 20 | Python SDK and API | QuantConnect, Qlib (code) | later | Internal routes exist. Keys, limits and docs are new. |
| 21 | Tournament with live rounds (Numerai style) | Numerai (fetched staking docs) | cut | Needs a community, a token and live rounds. Out of scope for a validation tool. |
| 22 | Deep sequence models | not offered by P123 | cut | Removed from the registry. Evidence in section 5 of the old review (daily data, weak). |
| 23 | Idea to formula with an LLM | P123 and QuantConnect assistants (not verified) | later | Only if it writes an editable formula. Not a black box. |

**Counts.** 23 rows: have 12, partial 3, build 3, later 3, cut 2. Items 6, 9 and 16 to 17 are "have" on the contract and the notes; their bodies are the next verification target.

---

## 4. Keep, build, later or cut, feature by feature

| Item | Call | Reason |
|---|---|---|
| Validate (14 sections, verdict, receipt) | **Keep, fix first** | Our category. Fix trial count, returns-only leakage and artifact durability before selling it. |
| CPCV (feature 01) | **Keep** | Real purging and embargo. Demote its default path count to a note, since fixed-signal mode is trivial. |
| Alpha (feature 02) | **Keep** | Controls, locked ensemble and exact attribution are the strongest engineering in ML. Keep ridge and LightGBM as default. Drop CatBoost and XGBoost from the default ensemble unless they earn it in a CPCV run. |
| Volatility (feature 03) | **Keep** | Forecast tournament with DM test is the best-evidenced piece. Make the regime cut-off an input. |
| Meta-labelling (feature 04) | **Keep, reframe** | As a filter on an existing strategy, with the primary strategy beside it. Unverified body. |
| Allocation (feature 05) | **Keep** | Minimum variance default with controls is defensible. Remove the unimplemented PPO, HERC and tail-dependence declarations from the user-facing list. |
| Regimes (feature 06) | **Keep, as a risk input** | Only as an input to volatility and risk. Every regime filter beside a constant-exposure control (already the design). |
| Pairs | **Cut from ML** | Not in the registry any more. If it returns, it belongs in Studio. |
| Microstructure anomalies as standalone alphas | **Cut** | Weak in the replication literature. They are candidate features inside Alpha, not a page. |
| Sequence models | **Cut** | Removed. |
| Live refresh, alerts, monitoring | **Later** | Needs the shared scheduler and delivery layer. Build once with Screener, not twice. |
| Trial ledger in Validate | **Build now** | Read the existing Research ledger, and report the count used on the verdict. |
| Durable artifacts | **Build now** | Persist to the same SQLite store Research uses (`research_v2/store/db.py` pattern) with a TTL, instead of a 32-entry dictionary. |

---

## 5. Our own ideas for freedom and customisation

1. **Bring your own model.** Upload a predictions file with dates, tickers and outcomes (already) or a scikit-learn model with a sandboxed, time-limited, no-network run (RESEARCH_ONLY today). Keep the first; defer the second.
2. **Set the bar.** Let users choose the verdict thresholds (DSR, PBO, plateau width, bootstrap percentile), save the set with the run, and show the default beside it. Today they are hard-coded in `_verdict`.
3. **Pick the controls.** Tick which controls must be beaten (default: all computed). The verdict then names the one that won.
4. **Declare the search.** A "search log" where the user states what they varied (horizon, features, costs). Each declared dimension becomes a trial family, and the count is the product, not a typed number.
5. **Rerun exactly.** A receipt link that reproduces the run from its hashes, including the upload, settings and seed, with a diff if anything changed.
6. **Compare, not just rank.** Two strategies side by side on identical controls and the same trial count, so "A beats B" is tested, not eyeballed.

---

## 6. Open-source picks and licences

Checked 2026-11-09 by fetching or searching the project page. Only verified licences are stated as such.

| Need | Pick | Licence | Status |
|---|---|---|---|
| Learned allocation and covariance | skfolio | BSD-3-Clause | Verified (skfolio.org, GitHub LICENSE). Could replace hand-written Ledoit-Wolf and HRP. Spike before adopting. |
| Hidden Markov models | hmmlearn | BSD | Verified (hmmlearn.com). Already used. |
| Research platform reference | Qlib (Microsoft) | MIT | Verified (GitHub). Reference for pipelines; code-only, so not a UI replacement. |
| Factor analysis reference | alphalens-reloaded | Apache-2.0 | Verified (GitHub). Useful for tear-sheet design. |
| Hyperparameter search | Optuna | not fetched | Unverified in this pass. Already in use. Check LICENSE before any new use. |
| GARCH and bootstrap | arch | not fetched | Unverified in this pass. Already in use. |
| Gradient boosting, SHAP | LightGBM, XGBoost, CatBoost, SHAP | not fetched | Unverified in this pass. All in use. |

Do not copy code from any source without its notice kept in `THIRD_PARTY.md`.

---

## 7. Data limits

These come from the Screener review, which checked the parquet files on 2026-11-08. They were not re-checked for ML on 2026-11-09.

- Daily prices: 4,158 tickers from 1996, mostly US. No delisted names, so survivorship bias is present. ML results carry that limit and must say so.
- Statement fundamentals: 2021 to 2025 only, with a 90-day availability lag. Fundamental-driven Alpha features are short-history.
- ML models trained on this history are at risk of overfitting by construction. Validate's controls and the trial count are the protection, which is why items 1 and 2 in section 1 matter.
- Monthly Research formulas and daily ML features differ in horizon. Do not compare their scores directly.

---

## 8. Screen and information

From `docs/reviews/design/ML_UI_ISSUES.md`, status not re-checked in this pass:

- Open: layout and space (items 5 and 7: rail and Inspect panel share width with content; header and KPIs take about 40 percent of the first screen); sticky tabs and bar (13 and 14); universe picker (15); search size (16).
- Fixed in the shared shell, per the issues file: verdict bar, selected-row bar, EXHIBIT eyebrow, helper text in empty panels, ticker casing, raw feature labels, output label truncation.

Information every verdict must show, per the Screener's "trust" rule: data basis and lag, unknown inputs, survivorship status, trial count used (item 2), leakage status and what it actually tested (item 3), and the controls beaten.

---

## 9. Build checklist

Tags: **E** easy (under a day), **M** medium (a few days), **H** hard (a week or more). Items are in build order. Each is verified by a test or a live run before it is ticked.

- [ ] **E** Leakage badge: returns-only uploads show "not tested" and do not count as pass in `_verdict`. Test: a returns upload gives `not tested`, not `pass`.
- [ ] **E** Expose verdict thresholds (DSR, PBO, plateau, bootstrap percentile) as inputs with today's values as defaults; echo them in `verdict.rule`.
- [ ] **E** Make the regime-switch cut-off (0.5) an input in `feature_03`, default unchanged.
- [ ] **E** Remove unimplemented PPO, HERC and tail-dependence from the user-facing allocation list (keep the RESEARCH_ONLY note).
- [ ] **M** Durable artifacts: store Alpha, Allocation, Regime and Volatility results in the SQLite store with a TTL; `get_artifact` falls back to the store. Test: restart the process and read an id back.
- [ ] **M** Validate trial count from the Research ledger when the user names a project; show the count and its source on the verdict. Test: two runs in one project raise the count by two.
- [ ] **M** Search log input: declared dimensions multiply into the trial count. Test: three horizons times two features gives six.
- [ ] **M** Verify and document unverified bodies: `run_cpcv_engine`, `run_triple_barrier`, `run_hrp_optimizer` body, `_feature_drift`, SHAP. Each gets a sentence in section 2 with its evidence.
- [ ] **M** Validate frontend: returns-only label on the leakage badge and a visible "not tested" state (`validateViews.tsx`).
- [ ] **M** Compare two strategies on identical controls and trial count.
- [ ] **H** skfolio spike for covariance and HRP; keep ours if it does not match on the test fixtures.
- [ ] **H** Sandboxed scikit-learn model upload with a time limit and no network.
- [ ] **later** Live refresh and alerts, built once with the Screener delivery layer.
- [ ] **later** SDK and API keys.

Open UI items from section 8 stay in `ML_UI_ISSUES.md`; this list does not repeat them.

---

## 10. Tiers

Proposed, not decided. Payments are PLAN stage 9.4.

| Tier | Includes |
|---|---|
| Free | Validate on a returns upload with the default controls and the verdict. Five runs a day. Watermarked receipt. |
| Pro | All features, durable artifacts, the Research trial ledger, Validate threshold settings, two-strategy compare. |
| Quant | Model upload, live refresh and alerts when built, API. |
| Team | Seats, shared projects, audit trail. |

Pricing is a business decision; no competitor figure here is a recommendation.

---

## 11. Sources

**Fetched 2026-11-09**
- Portfolio123 AI Factor: https://www.portfolio123.com/ai-factor (blocked K-fold, lift charts, XGBoost and neural nets, grid search)
- Portfolio123 community, AI Factor versus ranking systems: https://community.portfolio123.com/t/ranking-vs-machine-learning-algorithms/74376
- QuantConnect pricing: https://www.quantconnect.com/pricing/ (fetched; only the plan names and "Everything in Team +" confirmed in the text)
- Numerai staking docs: https://docs.numer.ai/numerai-tournament/staking (atomic staking v3, staked per round, staker and model)
- Qlib, MIT licence: https://github.com/microsoft/qlib
- alphalens-reloaded, Apache-2.0: https://github.com/stefan-jansen/alphalens-reloaded
- Open Source Asset Pricing, data page: https://www.openassetpricing.com/ (page content was thin; no licence text read)

**Search snippets only (prices not confirmed on the page)**
- QuantConnect Researcher seat about $20 per month and research nodes billed separately: QuantConnect organisation resources and pricing search results, 2026.
- skfolio BSD-3-Clause: https://skfolio.org/ and https://github.com/skfolio/skfolio/blob/main/LICENSE
- hmmlearn BSD: https://hmmlearn.com/

**Internal**
- `docs/reviews/design/ML_UI_ISSUES.md`
- `docs/architecture/CROSS_MODULE_MERGE_MAP.md` section 8
- `docs/reviews/product/SCREENER_V2_PRODUCT_REVIEW.md` (data limits, delivery layer)
- Code read: `backend/app/services/ml_v2/features/feature_01.py` to `feature_06.py`, `validate.py`, `core/validate_engine.py`, `core/alpha.py` (lines 381 to 470), `core/common.py`, `core/volatility.py` (greps and `_forecast_asset`), `core/regimes.py` (greps), `core/allocation.py` (greps and `run_hrp_optimizer` header), `backend/app/services/shared/stats.py`, `ml_v2/core/stats.py`
