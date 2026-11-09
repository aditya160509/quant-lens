# Research product review: signal validation, redone against the feature rule

Redone 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b. It replaces the 2026-10-03 "final batch" review. Backend claims come from function bodies read on 2026-11-09 under `backend/app/services/research_v2/` and `backend/app/services/shared/stats.py`. Competitor and open-source facts come from pages fetched or search results on the same date, listed in section 11. Items marked **unverified** were not read in code or not fetched.

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

Research is a signal-validation lab with real referee-grade tests, and it is the strongest thing in the module set for the claim "tells you whether to trust the answer". The October review's main defects have partly been fixed, and the rest are now specific.

- **Real.** Ten features cover the referee questions: Canonical (Fama-MacBeth, panel OLS, sorts, GRS, factor spanning), Robustness, Placebo, Regime, Diagnostics, Specification, Causal, Decay, Synthetic control and Factor Zoo. The Factor Zoo applies the Harvey-Liu-Zhu bar with the observed t taken from the spanning alpha (`core/zoo.py`). The formula language is a real AST whitelist with no `eval`, and it refuses negative lags as look-ahead (`signal_lang.py`).
- **Fixed since October, verified.** Jobs, projects, pre-registrations and share links are in SQLite (`store/db.py`), so results survive a restart. The October claim "results disappear on restart" no longer holds for jobs. Screener backtests write into the same ledger (`screener_v2/core/ledger_bridge.py`), so trials are counted across modules.
- **Hollow or weak, verified in code:**
  1. **The formula language is monthly, not daily.** Every operator works on a month by ticker frame. `delay`, `delta` and `ts_return` take a month count. The October example `ts_return(close, 252, skip=21)` does not parse: there is no `skip` argument, and 252 is a month count of 252 months. The language has 25 operators (`OPERATORS` in `signal_lang.py`), not the "operator library" the October review listed.
  2. **The signal library has 54 formulas, not about 200.** Counted from `core/signal_library.py`. Each carries an expected sign and a citation. The "roughly 200 Chen-Zimmermann anomalies" claim was a plan, not a fact in code.
  3. **The trial ledger counts every completed job, not just signal trials.** `ledger_stats` filters only on `status == completed`, so a Canonical or Robustness run counts as a trial in the same way as a new signal. The Sharpe for the hurdle is read by matching a label string ("sharpe", "t-stat") in `summary_cards` (`_card`), which breaks silently if a label changes. PBO is computed only when all return series have equal length and at least eight strategies. The "haircut" is a Bonferroni haircut on the t-stat, not the Harvey-Liu method its label names.
  4. **Screener backtests inflate the Research trial count.** `ledger_bridge.record_trial` writes every distinct Screener backtest configuration into the Research project called `screener`. That is the design the Screener review asked for, but it means a Research project's hurdle depends on Screener use. Nothing separates the two in the displayed count.
  5. **Factor Zoo drops factors with short history silently from the spanning sample** (`factors.drop(columns=short)`). They are reported in `excluded_short_history_factors`, so the drop is visible, but the verdict uses the shorter sample.
- **Competitor change.** Portfolio Visualizer is still the closest factor-regression tool and is cheap, but it does not test a user's own signal, does not apply a multiple-testing bar and does not show a trial count. WorldQuant BRAIN offers free formula alphas in its Fast Expression language and a large user base, so "formula alpha" is no longer unclaimed. Our difference is the referee layer on top: placebo, pre-registration, the trial ledger and the Harvey-Liu-Zhu bar.

**Pitch, unchanged:** "Bring your signal or formula. Get the referee report before the referee does."

**What blocks paying customers today, in order:**
1. The formula language cannot express daily signals, and the examples in the October review would fail to parse. Users who expect the WorldQuant or daily-quant idiom will hit errors.
2. The trial count mixes non-signal runs and Screener backtests, so the hurdle a user sees is not the hurdle for their signal.
3. The signal library is 54 formulas, far from the claimed catalogue. Benchmarking "is my signal new" needs the published anomaly set (section 6).
4. Holdout, pre-registration and sharing exist on the backend; their frontend behaviour is **unverified** in this pass.

---

## 2. Real versus hollow, from code read

Status: **real** (function body read, behaviour matches), **partial** (body read, a stated limit is material), **unverified** (not read in code this pass).

| Feature or piece | Code read | Status | Evidence in code |
|---|---|---|---|
| Registry and runners | `registry.py`, every `features/feature_0N.py` `run` | real | Ten features: 01 to 09 and 11. There is no 10. Runners are thin wrappers that call the core engines. |
| Formula language | `signal_lang.py`: `OPERATORS`, `references_forward`, `_Eval` (grep and table read) | real, monthly | AST whitelist, length limit 2,000 and node limit 250 (constants at the top), window limit 120. Negative lags are rejected. Operators work on month by ticker frames. |
| Signal library | `core/signal_library.py` | partial | 54 formulas with expected sign, citation and year. Built from the same formula language. |
| Factor Zoo | `run_zoo` and `_zoo_point` (`zoo.py`) | real | Spanning alpha t is the observed statistic when available, else the raw long-short t. Default rule `hlz_bhy`. Literature count default 450. Near-duplicate above |correlation| 0.7, blend above R-squared 0.5. Short-history factors dropped (item 5). |
| Canonical (feature 01) | `run_canonical` and `canonical_from_panel` (`canonical.py`) | partial | Entry points read. Fama-MacBeth, Newey-West and sorts are named in the feature description. Full body **unverified**. |
| Robustness, Placebo, Regime, Diagnostics, Specification, Causal, Decay, Synthetic | `run_*` entry points, placebo bodies of `_fm_signal`, `_permutation_null`, `_mclean_pontiff` (placebo.py) | partial | Placebo entry points and helpers read by name and in part. Others read only as runner wrappers. Full bodies **unverified**. |
| Holdout vault | `holdout.py`: `reserve_window`, `record_evaluation`, `release_window`, `lock_specification` | real backend | JSON file backed (`_read` and `_write`). Whether the frontend enforces the seal is **unverified**. |
| Projects, jobs, pre-registration, shares | `store/db.py` schema and `store/ledger.py` | real | Five tables in SQLite. `is_preregistered` matches payloads against stored pre-registrations. |
| Trial ledger | `ledger_stats`, `store/ledger.py`, `core/ledger_math.py` | partial | Counts every completed job (item 3). Hurdle from the variance of Sharpes across jobs of any feature. Bonferroni haircut. PBO only on equal-length series. |
| Ledger math | `deflated_sharpe_hurdle`, `haircut_t`, `pbo_cscv` (`ledger_math.py`) | real | Hurdle uses the Euler-gamma expected maximum, matching `shared/stats.py`. PBO calls the shared CSCV. |
| Shared stats | `services/shared/stats.py` | real | CSCV and DSR, used by ML and Research (merge map 8.2). |
| Screener to ledger | `screener_v2/core/ledger_bridge.py` | real | Writes one job per distinct configuration into project `screener`. Replaces reruns of the same configuration. |
| Report card | `reports.py` (539 lines), `ReportCard.tsx` (220 lines) | unverified body | Frontend exists. Composition logic **unverified**. |
| Projects view | `Projects.tsx` (lines 50 to 65 read) | real | Shows trials, deflated Sharpe hurdle, PBO and a plain sentence on the trial count. |
| Settings diff | `Inspector.tsx` (line 56 read) | real | Lists changed settings against the run on screen. |
| Signal page | `SignalPage.tsx` (292 lines; coverage strip read) | partial | Coverage strip and one formula editor. Live histogram and correlation with known factors **unverified**. |
| Shared view and embed | `SharedView.tsx`, `ResearchApp.tsx` embed branch | real | Read-only view and an embed mode without chrome. Settings in `?s=` are applied once. |
| Universe builder, onboarding, data window | file exists | unverified | Not read. |

---

## 3. Paid-feature parity table

Status values: **have** (code read, works as claimed), **partial** (code exists, a stated limit), **build** (data in hand, code or UI new), **later** (needs data or a live layer we do not have), **cut** (not ours to offer). Competitor sources are section 11. Prices shown are the figures on the cited page or search result, dated 2026-11-09; anything not confirmed on a page is marked.

| # | Feature | Who offers it | Our status | Note |
|---|---|---|---|---|
| 1 | Factor regression on Fama-French and Carhart | Portfolio Visualizer ($30 per month Basic, $55 Pro, billed annually, from pricing page and search results) | have | Canonical and Zoo with FF5 plus momentum. Carhart is FF3 plus momentum: confirm the library list. |
| 2 | Test a user's own signal | none of the fetched tools | have | Formula language (monthly) and CSV upload. |
| 3 | Daily or high-frequency formula language | WorldQuant BRAIN Fast Expression (free, 550,000+ users, search snippet) | partial | Monthly only. A daily mode is a build with a data-size question (section 7). |
| 4 | Library of published anomalies | Open Source Asset Pricing (315 characteristics and 945 portfolios, 98 percent replicate, search snippet) | partial | 54 hand-written formulas. The published set is "later, free data" (section 6). |
| 5 | Multiple-testing hurdle from a trial count | none of the fetched tools | have, partial | Items 3 and 4 in section 1. Our category, to be made honest. |
| 6 | Harvey-Liu-Zhu bar | none | have | Factor Zoo with the three HLZ benchmarks and the current Bonferroni. |
| 7 | Placebo and falsification | none | have (partial body read) | Permutation, time displacement, wrong direction, McLean-Pontiff, adjacent classes, protected holdout. |
| 8 | Pre-registration | none | have backend | `preregistrations` table and `is_preregistered`. Frontend **unverified**. |
| 9 | Holdout vault | none | have backend | `holdout.py`. Frontend **unverified**. |
| 10 | Point-in-time fundamentals | Portfolio123 point-in-time data (not re-fetched) | partial | Filing-lag rule exists in `point_in_time_fundamental` (referenced by `signal_lang.py`). Body **unverified**. Survivorship is not handled (section 7). |
| 11 | Survivorship-free universes | GuruFocus Pro delisted stocks (Screener review, not re-fetched) | later, paid data | Needs a vendor (section 7). |
| 12 | Factor backtest and portfolio sorts | QuantConnect (code-first, research nodes billed separately, search snippets) | have | Canonical sorts. QuantConnect is the code-first alternative, not a no-code tool. |
| 13 | Spanning and near-duplicate test | Alphalens (Apache-2.0) analyses predictive factors, not spanning | have | Zoo spanning and correlation classes. |
| 14 | Tear sheet report | Alphalens tear sheets (Apache-2.0) | partial | Report card and PDF or LaTeX export (`reports.py`). Body **unverified**. |
| 15 | Transaction costs and capacity | none of the fetched tools | build | Not in the feature list. Cost model is a Research A5 item in the October review, not built. |
| 16 | Live refresh, alerts and decay monitoring | Screener and Studio share the delivery plan | later | Needs the scheduler and delivery layer (Screener review rows 72 to 76). |
| 17 | API and Python SDK | QuantConnect, Qlib (code), Portfolio Visualizer (no) | later | Internal routes exist. Keys and docs are new. |
| 18 | Formula idea from English | WorldQuant BRAIN assistants (not verified) | later | Only as an editable formula. |
| 19 | Share and embed a result | none of the fetched tools for research | have | `SharedView` and embed mode. |
| 20 | Reproduce a run from its settings | none | have | `?s=` settings link; settings diff in the Inspector. |

**Counts.** 20 rows: have 11, partial 4, build 1, later 3, cut 0 (cuts are in section 4). Rows 3, 4, 10 and 14 depend on items not yet checked in code.

---

## 4. Keep, build, later or cut, feature by feature

| Item | Call | Reason |
|---|---|---|
| Canonical (feature 01) | **Keep** | Core referee test. Verify the Newey-West lag and the sort code before the next release (unverified body). |
| Robustness (feature 02) | **Keep** | Re-runs across windows and universes. The regime slice is shared with feature 04. |
| Placebo (feature 03) | **Keep** | The most distinctive test. The McLean-Pontiff and holdout placebos are the ones users will ask about. |
| Regime (feature 04) | **Keep, merge the Markov-switching into the regime slice** | The October review noted randomised failures (`LinAlgError`). Seed and fallback still unverified. |
| Diagnostics (feature 05) | **Keep, fold into Canonical** | The October review proposed this merge; it is not done in the registry, which still lists feature 05 separately. Merge is a UI change, not a backend one. |
| Specification (feature 06) | **Keep** | Journal table and LaTeX export is a real output. |
| Causal (feature 07) | **Keep** | Difference-in-differences, event study, RD and IV with diagnostics. Keep the synthetic control in it as the October review proposed, or in feature 09 with a shared input. |
| Decay (feature 08) | **Keep** | The arbitrage-clock logic is distinctive. Its speed (25 seconds, October) is unverified now. |
| Synthetic control (feature 09) | **Keep, merge into Causal** | October review item B3. Two entries for one design confuse users. |
| Factor Zoo (feature 11) | **Keep** | The HLZ bar is the strongest single signal of a referee-grade product. |
| Signal library | **Keep, grow with the published set** | 54 formulas now. The published set (section 6) is the upgrade, not more hand-written formulas. |
| Trial ledger | **Keep, fix the counting** | Count signal trials only, separate Screener trials in the display, read the Sharpe from the result, not a label. |
| Daily formula mode | **Later** | Needs a daily panel and a size plan. Do not promise it until the data is measured. |
| Transaction costs and capacity | **Build** | Core to the implementability claim. It is the one October item that matters most after the ledger fix. |
| Live alerts and decay monitoring | **Later** | Build once with the shared delivery layer. |
| Survivorship-free data | **Later, paid** | Business decision (section 7). Do not fake it. |
| "Old /labs/research pages" cleanup | **Unverified** | October item B6. Not checked this pass. |

---

## 5. Our own ideas for freedom and customisation

1. **Three levels of inputs, as the October review proposed.** Quick, standard and expert. The schema already carries `required`, `min`, `max`, `depends_on` and `conflicts_with` (the input annotation in `features/inputs.py`), so the frontend can read it.
2. **Name the trial.** Let the user tag each run as "signal", "control" or "exploration". Only signal runs enter the hurdle by default. The tag is shown and can be changed, and changing it is logged.
3. **Your own benchmark set.** Upload a list of signals with expected signs (CSV) and run Factor Zoo and the novelty test against it, not only the 54 built-in formulas. This is the freedom to define "new" for the user's own field.
4. **Two sample windows, one verdict.** Run the same signal on two universes or periods (for example US and Europe) and show whether the verdict agrees. Out-of-market replication is the strongest evidence a referee accepts.
5. **Set the bar.** Choose the hurdle rule (already in the Zoo: t 2 or 3, HLZ Bonferroni, Holm or BHY, or custom) and save it per project.

---

## 6. Open-source picks and licences

Checked 2026-11-09. Only verified licences are stated as such.

| Need | Pick | Licence | Status |
|---|---|---|---|
| Factor-analysis tear sheets | alphalens-reloaded | Apache-2.0 | Verified (GitHub). Predictive factor analysis; the pattern for tear sheets, not for spanning. |
| Published anomaly data and code | Open Source Asset Pricing (Chen and Zimmermann) | not verified | Site says the data and code reproduce "nearly all" predictors; 315 characteristics, 945 portfolios, 98 percent replicate (site and paper snippets). **Licence text not read.** Check before any redistribution; the platform can fetch it for the user, not bundle it, until the licence is read. |
| Portfolio optimisation (for allocation controls) | skfolio | BSD-3-Clause | Verified (skfolio.org and GitHub). Not Research's concern directly; listed for the Zoo's factor construction. |
| Hidden Markov models | hmmlearn | BSD | Verified (hmmlearn.com). Used by the regime feature. |
| Code-first reference | QuantConnect LEAN | not fetched | Unverified in this pass. Reference only. |

Do not copy code from any source without its notice kept in `THIRD_PARTY.md`.

---

## 7. Data limits

From the Screener review, which checked the parquet files on 2026-11-08. Not re-checked for Research on 2026-11-09.

- Daily prices: about 4,158 tickers, mostly US, from 1996. No delisted names. **Survivorship bias is present in every Research result.** The badge the October review asked for ("Survivorship: handled / not handled") must read "not handled" until a vendor is bought.
- Statement fundamentals: 2021 to 2025, with the 90-day availability lag. Fundamental signals are short-history; ten-year Zoo tests are not possible on fundamentals.
- The formula language and most features work on monthly panels. Daily work needs a daily panel and a memory plan. Not measured here.
- The old review's claim that Research "uses only a slice of the data" is not re-checked; universe handling (`universes.py`) is **unverified**.

---

## 8. Screen and information

From the October review's UI sections and the code read in section 2. Frontend behaviour not re-checked for each item.

- Shown: trial count, deflated Sharpe hurdle and PBO in the project line (`Projects.tsx`); settings changed since the run (`Inspector.tsx`); coverage strip on the signal page; read-only shared view.
- Required on every result, per the Screener trust rule: survivorship status, data lag, trial count used and whether it includes Screener trials, and the hurdle rule applied.
- Open from October and not verified: the referee checklist as a pass or fail list, the report card grades per dimension, the look-ahead flag on signal runs (`attach_lookahead` in `core/signal_service.py`, read by name; `registry.py` calls it for every run).

---

## 9. Build checklist

Tags: **E** easy (under a day), **M** medium (a few days), **H** hard (a week or more). Items are in build order. Each is verified by a test or a live run before it is ticked.

- [ ] **E** Trial ledger reads the Sharpe and t-stat from the result, not by label match. Test: rename a card label in a fixture and the hurdle still computes.
- [ ] **E** Trial ledger counts only signal-bearing runs by default; a `trial_kind` tag (signal, control, exploration) is stored on each job. Test: a Canonical run with no signal does not raise the count.
- [ ] **E** Show Screener trials as a separate line in the project summary, not in the same count. Test: one Screener backtest and one signal run show "1 signal, 1 Screener".
- [ ] **E** Haircut label: rename "Harvey-Liu" to "Bonferroni haircut" unless the Harvey-Liu-Zhu method is implemented. Test: label matches the formula.
- [ ] **E** Factor Zoo: report the sample length of the spanning test next to the verdict whenever factors were dropped. Test: a fixture with a short factor shows its drop count.
- [ ] **M** Merge Diagnostics into Canonical and Synthetic into Causal, as the October review proposed; keep both backend engines. Test: each old feature id still resolves.
- [ ] **M** Transaction cost model with break-even cost and turnover-aware net returns. Test: a fixture with known turnover gives the expected net return.
- [ ] **M** Verify and document the unverified bodies: Canonical, Robustness, Regime Markov-switching fallback, `point_in_time_fundamental`, `universes.py`, `reports.py` composition. Each gets a sentence in section 2.
- [ ] **M** Frontend check of the holdout seal and the pre-registration flow against the backend routes. Test: a sealed window cannot be evaluated from the UI.
- [ ] **M** Replace the 54-formula library's expected signs with a citation-checked review. Test: each sign has a source line.
- [ ] **H** Daily formula mode on a daily panel, with a memory and time budget measured before any promise.
- [ ] **H** Import the published anomaly set once its licence is read; keep it as a separate benchmark list, not bundled into the library.
- [ ] **later** Survivorship-free universes once a vendor is chosen (business decision).
- [ ] **later** Live decay monitoring and alerts with the shared delivery layer.

---

## 10. Tiers

Proposed, not decided. Payments are PLAN stage 9.4.

| Tier | Includes |
|---|---|
| Free | Built-in signals, three runs a day, watermarked exports, US large caps. |
| Pro | Formula language, all features, the trial ledger with the tag, report card export, saved projects. |
| Research | Own benchmark sets, out-of-market replication, holdout vault, pre-registration, sharing, the SDK when built. |
| Team | Seats, shared projects, audit trail. |

No price here is a recommendation. Portfolio Visualizer's $30 and $55 tiers are a reference point, not a target.

---

## 11. Sources

**Fetched or read on 2026-11-09**
- Portfolio Visualizer pricing and factor regression: https://www.portfoliovisualizer.com/pricing (search snippet: Basic $30 per month, Pro $55 per month, billed annually; factor regression tool). Pricing page text confirmed by search snippet only.
- WorldQuant BRAIN: https://worldquant.com/brain/ and https://worldquantbrain.com/consultant (search snippets: free platform, Fast Expression language, 550,000+ users). Not fetched in full.
- Open Source Asset Pricing: https://www.openassetpricing.com/ (fetched; the page text is short and shows the citation, not the licence). Replication figures from search snippets of https://www.tomzimmermann.net/research/ and https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3604626.
- alphalens-reloaded: https://github.com/stefan-jansen/alphalens-reloaded (fetched; Apache-2.0 licence line confirmed).
- QuantConnect: https://www.quantconnect.com/pricing/ (search snippets: Researcher seat about $20 per month; research nodes billed separately). Not fully fetched.
- hmmlearn: https://hmmlearn.com/ (search snippet: BSD licence).
- skfolio: https://skfolio.org/ and https://github.com/skfolio/skfolio/blob/main/LICENSE (search snippets: BSD-3-Clause).

**Internal**
- `docs/reviews/product/SCREENER_V2_PRODUCT_REVIEW.md` (data limits, delivery layer, trust rule)
- `docs/reviews/product/ML_V2_PRODUCT_REVIEW.md` (shared stats, trial ledger ownership)
- `docs/architecture/CROSS_MODULE_MERGE_MAP.md` section 8 (decisions 1, 2, 4, 6)
- Code read: `backend/app/services/research_v2/registry.py`, `features/feature_01.py` to `feature_09.py` and `feature_11.py` (run bodies), `features/inputs.py` (annotate, by name), `core/zoo.py` (full), `core/signal_lang.py` (OPERATORS, `references_forward`, `_Eval` names), `core/signal_library.py` (count and structure), `core/holdout.py` (function list), `core/placebo.py` (function list and `_fm_signal`, `_permutation_null` by name), `core/canonical.py` (entry points), `store/db.py` (schema), `store/ledger.py`, `core/ledger_math.py`, `backend/app/services/shared/stats.py`, `screener_v2/core/ledger_bridge.py`, `backend/app/api/research_v2_projects.py` (ledger route)
- Frontend read: `frontend/src/modules/research/Projects.tsx` (lines 50 to 65), `Inspector.tsx` (line 56), `SharedView.tsx` (lines 13 to 50), `ResearchApp.tsx` (lines 41 to 90 and 150 to 170), `SignalPage.tsx` (grep only), `ReportCard.tsx` (not read)
