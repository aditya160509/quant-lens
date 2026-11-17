# Named Issue Register — Research Module Backend

Audit date: 2026-11-17
Standard: [`docs/studio/standards/CODE_STANDARDS.md`](../studio/standards/CODE_STANDARDS.md) (999 lines, applied by analogy)
Scope: `backend/app/services/research_v2/**`, `backend/app/api/research_v2*.py`, `backend/tests/test_research_v2_*.py`, `backend/app/services/research_cache.py`

Every issue below cites `path:line` relative to the repository root. Quoted code is copied verbatim from the file at audit time, except where a line is truncated with `…`. Severity follows the standard's own classes (P0 release blocker, P1 material defect, P2 quality/documentation) and the standard's definition of P0 for look-ahead, incorrect financial results, unauthorized access, and hold-out leakage.

`CONFIRMED` means the code path was read directly and the behaviour follows from it. `SUSPECTED` means the behaviour is reasoned from code structure but was not executed. Nothing is reported as CONFIRMED on the strength of a subagent claim alone.

---

## 1. Point-in-time correctness (§2.1)

### Q-01 Universe membership is drawn from one current snapshot, so delisted names are absent
- **Severity:** P1
- **Standard:** §2.1 — "Universe membership is evaluated point-in-time wherever historical membership data exists."
- **Evidence:** `backend/app/services/research_v2/core/data_loader.py:138-139` — `def available_symbols() -> tuple[str, ...]: return _market_summary()[0]`, where `_market_summary` reads the single `market_universe.parquet` currently on disk. `backend/app/services/research_v2/audit.py:48` emits `"survivorship": "not handled"` into every `meta.data_audit`.
- **Impact:** Any equity that stopped trading before the parquet was built cannot enter the cross-section. Momentum, reversal and volatility sorts are systematically biased upward because the worst outcomes are missing, and the bias is largest exactly in the long-horizon features (01–05). The module discloses the limitation but does not correct it, and the grade does not penalise it.
- **Fix:** Build the historical universe from the parquet's own date range (`Ticker` × `Date` presence) rather than the unique ticker list, and treat "listed but later absent" as a terminal return rather than a dropout. Until that exists, make the disclosure a graded dimension so a survivorship-affected study cannot score A.
- **Confidence:** CONFIRMED

### Q-02 Sector membership is applied to the whole history as if constant
- **Severity:** P2
- **Standard:** §2.1 — "Universe membership is evaluated point-in-time wherever historical membership data exists."
- **Evidence:** `backend/app/services/research_v2/core/data_loader.py:392-399` — `"""Sector per ticker. Sector membership is treated as time-invariant."""` then `.groupby("ticker")["sector"].last()`, i.e. the *latest* sector label is projected backwards. Used by `_universe_mask` at `core/panel.py:427` and by `/symbols` and `/universe`.
- **Impact:** `ex_financials`, `ex_utilities` and any sector neutralisation use today's GICS label applied to 2005. Companies that reclassified (payment processors, REITs, spin-offs) are filtered on the wrong side, and the cross-section is contaminated for the whole sample rather than a few months.
- **Fix:** Store `(ticker, reportDate, sector)` and join each formation date to the most recent sector known then, with the same filing lag as other fundamentals.
- **Confidence:** CONFIRMED

### Q-03 Fundamentals are lagged from `reportDate`, not from the filing timestamp
- **Severity:** P1
- **Standard:** §2.1 — "Fundamentals respect realistic filing and ingestion delays." / "Data availability is distinguished from data observation."
- **Evidence:** `backend/app/services/research_v2/core/data_loader.py:425` — `sub = sub.assign(available=sub["reportDate"] + pd.Timedelta(days=int(lag_days)), value=pd.to_numeric(sub[field], errors="coerce"))`, with `lag_days: int = 90` default at line 408.
- **Impact:** If the upstream provider's `reportDate` is the fiscal period end (true for several fundamentals feeds) rather than the announcement date, a 90-day lag makes a Q4 report usable in early April when many issuers file in February, or — worse for 10-K filers — makes it usable before the actual filing. Either direction is a look-ahead or an information loss, and the direction varies by ticker and period without any per-row evidence.
- **Fix:** Prefer an explicit `filingDate` column; if it is absent, raise the lag to 120 days and record the assumption in `meta.data_audit` per study. Do not silently assume 90.
- **Confidence:** SUSPECTED

### Q-04 A 550-day carry-forward lets 18-month-old fundamentals masquerade as current
- **Severity:** P2
- **Standard:** §2.1 — "Missing historical availability metadata produces a limitation or refusal."
- **Evidence:** `backend/app/services/research_v2/core/data_loader.py:408` — `max_age_days: int = 550`; line 434 — `values = values.where(age <= max_age_days)`.
- **Impact:** For an annual-only flow field (`periodType == "annual"`, line 422) a value can be up to 550 days stale before it is dropped, so `value`, `quality` and `investment` signals mix a fresh price with a book value from the prior fiscal year and call the result point-in-time. This is defensible for annual flows but is not disclosed anywhere the user sees it.
- **Fix:** Use 400 days for annual flows (one reporting cycle plus grace) or carry the true `age_days` into the panel so downstream features can report staleness rather than silently accept it.
- **Confidence:** CONFIRMED

### Q-05 Restatements are collapsed by timestamp with no provenance
- **Severity:** P2
- **Standard:** §2.1 — "Data availability is distinguished from data observation."
- **Evidence:** `backend/app/services/research_v2/core/data_loader.py:426` — `sub.sort_values(["ticker", "reportDate"]).drop_duplicates(["ticker", "available"], keep="last")`.
- **Impact:** Two rows with the same `reportDate` (original plus restatement) are ordered only by `reportDate`, a tie, so which value survives depends on the provider's row order. The study cannot reproduce the same panel from a re-ingested file, and no restatement flag reaches the result.
- **Fix:** Sort by `(ticker, reportDate, ingestion_ts)` and keep an explicit `is_restatement` column; expose the count of restated observations in `meta.data_audit`.
- **Confidence:** CONFIRMED

### Q-06 Macro conditioning series carry no publication lag
- **Severity:** P1
- **Standard:** §2.1 — "Revised macroeconomic data is not treated as originally published data." / "Rolling indicators do not use future observations."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:485` — `return m.set_index("Date").sort_index().resample("ME").last().reindex(dates)`. The `regime` feature then reads these values at formation dates (`core/regime.py`, `CONDITIONS` at lines 19–29, including `credit_spread_wide`, `yield_curve_inverted`, `nber_recession`).
- **Impact:** VIX, Treasury slope, credit spreads and the NBER recession indicator are all revised. The NBER announcement date lags the business-cycle peak by 6–18 months; using the revised label at the peak date is direct look-ahead in the regime split, which then feeds the "regimes" grade dimension.
- **Fix:** Attach a vintage/announcement date per macro series (FRED `ALFRED` supports this) and lag each to its first release. Mark NBER recession with its announcement date, not the peak month.
- **Confidence:** SUSPECTED

### Q-07 `.reindex(dates)` on macro drops values instead of forward-filling
- **Severity:** P2
- **Standard:** §2.1 — "Data availability is distinguished from data observation."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:485` — `.resample("ME").last().reindex(dates)` (reindex, not `ffill`/`merge_asof`).
- **Impact:** A macro series whose month-end label is a trading day (VIX, spreads) will not align exactly to the calendar month-end produced by `resample("ME")`, so whole series silently become NaN and the associated regime conditions become untestable without any error.
- **Fix:** Use `reindex(dates, method="ffill")`, assert a non-null coverage floor per macro column, and surface the coverage in `meta.data_audit`.
- **Confidence:** CONFIRMED

### Q-08 Feature outputs carry no per-feature observation timestamp
- **Severity:** P2
- **Standard:** §2.1 — "Every feature has an explicit observation timestamp."
- **Evidence:** `backend/app/services/research_v2/reports.py:81-82` — `_dim` returns only `dimension`, `grade`, `score`, `summary`, `metric`. `run_feature` results add `meta` (audit, costs, lookahead, preregistered) but no `as_of` or `data_through` field per feature.
- **Impact:** A saved result cannot be dated. When the parquet is refreshed, an old report card is indistinguishable from a current one, and the user cannot tell whether a result predates a data correction.
- **Fix:** Add `meta.data_through` (max price date), `meta.source_version` (parquet mtime + row count hash) and `meta.computed_at` to every feature result.
- **Confidence:** CONFIRMED

---

## 2. Execution chronology and return alignment (§2.2)

### Q-09 A partial current month is treated as a completed monthly bar
- **Severity:** P0
- **Standard:** §2.2 — "Completed closing prices are not assumed known before the close." / "Higher-timeframe indicators use the last completed higher-timeframe bar."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:129` — `close_m = close_d.resample("ME").last()`. `resample("ME")` stamps the last observed daily close, whatever the date, onto the calendar month end.
- **Impact:** Mid-month, the current month's `last()` is a partial-month close labelled as month end. That value enters the monthly return (`panel.py:132`), every trailing signal (`ts_mean`, 12-1 momentum, volatility), and the cross-section for the newest formation date. A 12-1 momentum signal run on the 10th of the month is computed on a 10-day stub month and presented as a month-end observation. This is the exact failure the clause names.
- **Fix:** Drop the final period unless its last observation is the actual last trading day of that month: `close_m = close_m[close_m.index <= close_d.index.max()]` plus a completeness mask from `close_d.groupby(período).max()`; or resample with `label`/`closed="left"` and explicitly exclude the incomplete trailing bar.
- **Confidence:** CONFIRMED

### Q-10 Formation dates depend on where the sample ends, so truncating future data changes earlier results
- **Severity:** P0
- **Standard:** §2.2 — "Truncating future data does not change earlier signals." / §5.2 — "Window boundaries do not duplicate observations."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:144` — `formation = all_dates[::-1][horizon::step][::-1] if len(all_dates) > horizon else all_dates[:0]`. The origin of the stride is the *last* date in the sample.
- **Impact:** Add one month of data and every formation date shifts by one month when `step > 1` (quarterly/annual rebalancing). The same study re-run next month is a different study, with a different set of cross-sections, a different FM t-stat and possibly a different grade. It also means the panel cannot be used for honest walk-forward evaluation, because the evaluation dates are a function of the evaluation end.
- **Fix:** Anchor the stride to a fixed calendar origin (e.g. the first date, or January) so `formation = all_dates[(all_dates >= start) & (position_from_origin % step == 0)]`. Add a metamorphic test: truncate the last 12 months and assert the earlier formation set is unchanged.
- **Confidence:** CONFIRMED

### Q-11 Signals and dependent returns share a timestamp, implying same-close execution
- **Severity:** P1
- **Standard:** §2.2 — "Signals and fills have separate timestamps." / "Default close-of-bar signals execute no earlier than the next eligible open."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:147-148` — `signal = finalize_signal(compute_signal(...))` then `dependent = compute_dependent(...)`; `compute_dependent` at line 372-373 computes `growth = (1 + returns).rolling(horizon)…` and `forward = growth.shift(-horizon)`, so the dependent window starts at `t+1` while the signal is measured at close `t`.
- **Impact:** The arithmetic is internally consistent, but it silently assumes the portfolio can be formed at the close that produced the signal, with zero delay. For a signal built from the same close (reversal, volume, illiquidity) that is not executable in practice, and the reported premium is an upper bound presented as an estimate.
- **Fix:** Model an explicit one-bar implementation lag (`signal.shift(1)` before weighting) and report the cost of that lag; or state plainly in `meta` that the study assumes same-close execution.
- **Confidence:** CONFIRMED

### Q-12 The 300% filter silently deletes genuine extreme months
- **Severity:** P1
- **Standard:** §2.1 — "Missing historical availability metadata produces a limitation or refusal." / §8.2 — "No silent fallback changes financial meaning."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:133` — `returns = returns.where(returns.abs() < 3)  # drop split/bad-print artefacts (>300% in a month)`.
- **Impact:** `where` converts the observation to NaN, which drops the asset from that month's cross-section entirely. Genuine >300% monthly moves exist (micro-cap biotech, post-bankruptcy equity, short squeezes) and are exactly the observations that drive equal-weighted small-cap premia. The filter also does not achieve its stated purpose: a 2:1 split shows up as −50%, not >300%, so unadjusted splits survive while real outliers are removed.
- **Fix:** Apply split/dividend adjustment at load time (the source is described as adjusted close in `audit.py:47`, so verify it), then use a symmetric MAD-based screen that flags rather than deletes, and report counts in `meta.data_audit`.
- **Confidence:** CONFIRMED

### Q-13 Delisted and suspended securities simply disappear from the return matrix
- **Severity:** P1
- **Standard:** §2.2 — "Orders are not executed on suspended or unavailable securities." / §4.2 — "Missing delisted securities are disclosed."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:129-130` — `close_d.resample("ME").last()` then `close_m = close_m.loc[:, close_m.notna().sum() >= 24]`; `returns` is `pct_change` with `fill_method=None`, and there is no delisting-return injection anywhere in the module.
- **Impact:** When a name stops trading, its last month is a NaN return, so a portfolio holding it neither loses the delisting return nor the terminal value; the position is silently dropped from the denominator. Combined with Q-01 this makes the long leg look better than it was.
- **Fix:** Carry a terminal return per delisted ticker (last traded price to zero or to the acquisition consideration) and mark it in the panel; otherwise exclude the asset from *all* months rather than just the missing ones.
- **Confidence:** CONFIRMED

### Q-14 Overlapping h-month returns are annualised as if independent
- **Severity:** P0
- **Standard:** §2.5 — "Annualization reflects the sampling frequency and return convention." / "Serial correlation is considered when estimating uncertainty."
- **Evidence:** `backend/app/services/research_v2/audit.py:130` — `ann = np.sqrt(12 / h)` and `sharpe = lambda s: float(s.mean() / s.std() * ann)`; the series it annualises is `port["long_short"]` (`audit.py:101`), which is built from the h-month forward dependent variable at every monthly formation date when `forward_months > 1`.
- **Impact:** With monthly rebalancing and `forward_months = 12`, consecutive observations share 11 of 12 months. `mean/std` on an overlapping series has a variance deflated by roughly a factor of `h`, so the Sharpe is inflated by about `sqrt(h)` — roughly 3.5× for a 12-month holding period. `cost_analysis` also charges one full turnover per formation date while the position is actually held 12 months (`audit.py:103`), which overstates cost in the opposite direction and makes the net/gross grade incoherent.
- **Fix:** Either compute non-overlapping h-month returns (form every h months) before the Sharpe, or keep the monthly series and annualise with the Newey-West/Hansen-Hodrick correction on the mean and variance. Compute turnover from the actual holding-period schedule, not from `w.diff()` at every date.
- **Confidence:** CONFIRMED

### Q-15 The cumulative long-short chart compounds overlapping returns and fills gaps with zero
- **Severity:** P0
- **Standard:** §2.2 — "Performance is calculated from the actual stitched equity path." (via §5.2) / §9.2 — "Reported changes and cumulative series correspond to the stated horizon."
- **Evidence:** `backend/app/services/research_v2/core/canonical.py:111` — `"cumulative_long_short": (1 + ls.fillna(0)).cumprod().rename("growth_of_1").reset_index() if len(ls) else []`.
- **Impact:** Two defects in one line. (a) When `holding_months > 1`, `ls` is an overlapping h-month return series, and chaining `(1+r)` across overlapping windows produces a growth path that does not correspond to any implementable portfolio — it is mathematically meaningless and typically shows implausibly smooth exponential growth. (b) `fillna(0)` turns a missing month into a zero return, hiding data gaps and delistings from the equity curve. Users see this chart as "the strategy made X%".
- **Fix:** Compound non-overlapping returns only (`ls.iloc[::h]`), or build the curve from monthly mark-to-market weights. Never `fillna(0)`; leave the gap and break the line.
- **Confidence:** CONFIRMED

### Q-16 No test asserts that a future-peeking strategy fails
- **Severity:** P0
- **Standard:** §2.2 — "A future-peeking strategy fails an explicit adversarial test."
- **Evidence:** No test in `backend/tests/test_research_v2_*.py` constructs a formula or signal that reads forward data and asserts a rejection. The guard that exists (`core/signal_lang.py:426-438`, `lookahead_check`) returns a dict and is only attached to `meta` (`core/signal_service.py:62,70`); nothing raises.
- **Impact:** The standard requires an adversarial test that proves the platform refuses a leaking strategy. The platform does not refuse one (see L-01), so the test cannot exist. Any regression in the guard is invisible.
- **Fix:** After implementing L-01, add `test_lookahead_rejects_negative_lag`, `test_lookahead_rejects_future_feature`, and a truncation-invariance test for `build_panel`.
- **Confidence:** CONFIRMED

---

## 3. Parameter selection (§2.3)

### S-01 There is no training/evaluation separation; every feature fits and reports on the same sample
- **Severity:** P1
- **Standard:** §2.3 — "Model selection and final evaluation are separated." / "Every reported out-of-sample result is genuinely out-of-sample relative to selection."
- **Evidence:** `backend/app/services/research_v2/core/canonical.py:40` — `fm, slopes = fama_macbeth(panel, controls, nw_lag)`; the panel spans the user's whole requested window. There is no fold, no burn-in split, and the grade comes from the same observations.
- **Impact:** The label "out-of-sample" appears in the holdout feature only. Every other grade is in-sample, and a user who tries 20 signals and keeps the best has 20 correlated draws from the same data with no correction (see S-05).
- **Fix:** Add an explicit `train_end` to the payload, run the headline estimate on data after `train_end`, and relabel the current mode as in-sample.
- **Confidence:** CONFIRMED

### S-02 The protected window can be evaluated on any run, not gated by a locked specification
- **Severity:** P0
- **Standard:** §2.3 — "Hyperparameter tuning does not use the final hold-out." / §5.4 — "Hold-out membership is established before tuning."
- **Evidence:** `backend/app/services/research_v2/core/panel.py:164` — `if protected and not payload.get("_evaluate_protected")`; `core/placebo.py:212` — `full = build_panel({**payload, "_evaluate_protected": True})` whenever `payload.get("evaluate_protected")` is truthy.
- **Impact:** The only thing standing between the researcher and the protected window is a boolean in the request body. There is no requirement that a specification be locked first, no check of `locked_specs.json`, and no limit on how many times it can be evaluated. A user can evaluate, adjust, evaluate again, and the reported "protected out-of-sample" number is a best-of-N in-sample number.
- **Fix:** Require an existing `locked` spec whose `spec_hash` matches the current payload before `evaluate_protected` is honoured; allow one evaluation per lock; permanently mark the window as consumed afterwards.
- **Confidence:** CONFIRMED

### S-03 Walk-forward validation exists but is not wired into selection
- **Severity:** P2
- **Standard:** §2.3 — "Walk-forward parameters are selected using only preceding training data."
- **Evidence:** `backend/app/services/research_v2/worker.py:25` dispatches `reports.run_validation(payload, method, folds, embargo_days)`; `backend/app/api/research_v2_reports.py` exposes it as a separate job kind.
- **Impact:** The folds run, but the parameter that is validated is whatever the caller already chose on the full sample. The output is a validation artefact, not a selection procedure.
- **Fix:** Have the validation job accept a grid, select inside each training fold, and report the stitched out-of-sample path.
- **Confidence:** CONFIRMED

### S-04 Grade thresholds are unversioned constants inside a module
- **Severity:** P1
- **Standard:** §5.5 — "Verdict weights and thresholds are versioned." / §12 — "Relevant software and algorithm versions are included."
- **Evidence:** `backend/app/services/research_v2/reports.py:20-21` — `BANDS = [("A", 85), ("B", 70), ("C", 55), ("D", 40)]` and `T_THRESHOLDS = (3.0, 2.5, 2.0, 1.5)  # A, B, C, D: Harvey-Liu-Zhu t = 3.0 bar down to 1.5`.
- **Impact:** A stored result cannot say which grading rules produced it. Change a threshold and every historical report card becomes silently incomparable to a new one. The comment cites Harvey-Liu-Zhu for the t grid but not for the 85/70/55/40 score bands, which are arbitrary and undocumented.
- **Fix:** Move both to a versioned `grading/v1.json`, stamp `meta.grading_version` into every result, and record the rationale for the score bands in a decision record.
- **Confidence:** CONFIRMED

---

## 4. Multiple testing and selection bias (§2.4)

### S-05 The trial ledger only sees jobs saved under one project
- **Severity:** P1
- **Standard:** §2.4 — "Every evaluated strategy candidate has a persistent trial identifier." / "Parameter sweeps record attempted, completed, failed and excluded candidates."
- **Evidence:** `backend/app/services/research_v2/store/db.py:151` — `def ledger(self, pid: str) -> dict: return ledger_stats(self.project_jobs(pid))`; `store/ledger.py` counts only rows with `status == "completed"` and a result.
- **Impact:** A user who runs 50 signals without a project, or across several projects, gets a ledger that sees none of them. Deflated Sharpe and the haircut are then computed on an understated trial count, which is precisely the bias the correction exists to remove.
- **Fix:** Key the ledger on `(signal, dependent_variable, universe, holding_months)` globally, not per project, and include failed/cancelled runs as trials.
- **Confidence:** CONFIRMED

### S-06 No trial lineage, selection criterion or exclusion record
- **Severity:** P2
- **Standard:** §2.4 — "Trial lineage connects variants to their parent strategy." / "The ledger records selection criteria and optimization objectives."
- **Evidence:** `store/db.py:19` job schema — `jobs(id, feature_id, payload, status, progress, result, error, project_id, created_at, finished_at)`; no parent id, objective or selection note.
- **Impact:** The ledger can count trials but cannot describe the search. A reviewer cannot reconstruct whether the reported trial count is honest.
- **Fix:** Add `parent_job_id`, `objective`, `selection_note` columns, and have batch screening write one parent row.
- **Confidence:** CONFIRMED

### S-07 PBO/CSCV is computed without checking its applicability
- **Severity:** P1
- **Standard:** §2.4 — "PBO is computed only when its sampling and candidate requirements are satisfied."
- **Evidence:** `backend/app/services/research_v2/core/ledger_math.py` implements `pbo_cscv`; `store/ledger.py` calls it with whatever candidate set the project's completed jobs contain.
- **Impact:** PBO requires a matrix of candidate return series over a common index with enough observations per CSCV partition. With a handful of heterogeneous jobs over different samples, the combinatorial splits are ill-defined and the number is not the statistic its name claims.
- **Fix:** Require ≥ 10 candidates on an identical date index and ≥ 8 CSCV blocks; otherwise return `available: False` with the reason (the standard also requires `§5.3 — Every skipped test reports its reason`).
- **Confidence:** SUSPECTED

### S-08 Batch screening offers 500 signals with no family-level correction
- **Severity:** P1
- **Standard:** §2.4 — "Effective trial-count methodology is documented." / §2.5 — "Multiple comparisons are accounted for where applicable."
- **Evidence:** `backend/app/api/research_v2_reports.py:29` — `signals: List[str] = Field(min_length=1, max_length=500)`; `reports.run_batch` returns per-signal results.
- **Impact:** Screening 500 signals and reading the top t-stat is the canonical multiple-testing trap, and the endpoint is designed around exactly that workflow. `zoo.py` applies Bonferroni/HLZ for its own library, but the batch screen does not correct or even annotate the family size.
- **Fix:** Add a `family_size` to the batch result and apply BHY (or report Bonferroni-adjusted p) across the 500 signals; refuse to rank without it.
- **Confidence:** SUSPECTED

---

## 5. Statistical inference (§2.5)

### S-09 The two-pass estimator uses raw asset returns against excess-return factors
- **Severity:** P1
- **Standard:** §2.5 — "Annualization reflects the sampling frequency and return convention." / §4.1 — "Adjustment conventions are consistent within each return calculation."
- **Evidence:** `backend/app/services/research_v2/core/estimators.py:270-272` — `"""… Both use excess returns and no free intercept (traded-factor pricing)."""`; the caller at `core/canonical.py:64` passes `assets` (portfolio returns from `sort_portfolios`) and `pd.concat([factors, ls.rename("signal_ls")])` where `factors` are FF excess returns, without subtracting `rf` from the assets.
- **Impact:** Risk premia `λ` absorb the average risk-free rate, since `E[r_i] = rf·1 + B λ` but the estimator solves `r̄ = B λ`. Every estimated premium is biased by roughly `rf` (≈ 0.2–0.4%/month over the sample), which is small relative to a factor premium but decisive for the "signal_ls" premium that gets a t-stat and a grade.
- **Fix:** Subtract `rf` from `assets` before `two_pass`, or pass `rf` in and let the estimator demean. Add a unit test with a synthetic zero-beta asset: the estimated λ must be zero.
- **Confidence:** CONFIRMED

### S-10 Grade bands do not adapt to sample size
- **Severity:** P1
- **Standard:** §2.5 — "Small-sample inference is refused or qualified." / "No metric is reported with precision unsupported by its data."
- **Evidence:** `reports.py:97` — `g = grade_from_thresholds(None if t is None else abs(t), T_THRESHOLDS)`; `T_THRESHOLDS` is fixed regardless of `validity["months"]`.
- **Impact:** A 36-month sample and a 600-month sample are graded identically on |t|. At 36 monthly observations with 5 controls the FM t is extremely noisy, and a t of 3.0 there is not the same evidence as a t of 3.0 over 50 years. The card shows "A" in both cases.
- **Fix:** Require a minimum month count per grade and add a small-sample qualifier to the significance summary, or use a size-aware Bayesian shrinkage on the t.
- **Confidence:** CONFIRMED

### S-11 The FM validity regime is reported but never blocks a grade
- **Severity:** P2
- **Standard:** §2.5 — "Small-sample inference is refused or qualified." / "Nonstationarity and regime instability are disclosed."
- **Evidence:** `core/estimators.py:74` — `def fm_validity(slopes, n_assets, reps=1000, lag=4)` returns a `regime`; `core/canonical.py:41` stores it; no branch in `reports.grade_dimensions` reads it.
- **Impact:** A study flagged as an unreliable FM regime still receives a significance grade from that same FM estimate.
- **Fix:** Downgrade significance when `regime` is not the healthy branch, and put the reason in `overall()`'s "strongest limiting reason" (see S-16).
- **Confidence:** CONFIRMED

### S-12 Key metrics are rounded to two decimals regardless of precision
- **Severity:** P2
- **Standard:** §2.5 — "No metric is reported with precision unsupported by its data."
- **Evidence:** `reports.py:82` — `"score": None if score is None else round(float(score), 1)`; `reports.py:100` — `f"Fama-MacBeth t = {t:.2f}."`; `canonical.py:113-117` summary values are raw floats.
- **Impact:** A t-stat from 30 observations printed as `3.04` implies a precision the estimate does not have, and the two-decimal format invites comparison across studies with very different N.
- **Fix:** Format with `g` and a significant-figure rule tied to `months`, and show N alongside every t.
- **Confidence:** CONFIRMED

### S-13 No statement of the null hypothesis for the permutation tests
- **Severity:** P2
- **Standard:** §5.3 — "Permutation tests state their null hypothesis."
- **Evidence:** `core/placebo.py:117` — `def _permutation_null(panel, controls, reps, lag, seed=3)`; the returned table carries a `permutation_p_value` with no `null_hypothesis` field, and `reports.py:112` reports it as "Permutation p".
- **Impact:** Shuffling the signal across assets tests "the signal is unrelated to returns cross-sectionally", which is not the same null as "the signal has no premium". The user reads a p-value without knowing which.
- **Fix:** Emit `null_hypothesis: "cross-sectional permutation of the signal within each month"` alongside the p-value and use it verbatim in the report card.
- **Confidence:** CONFIRMED

### S-14 Overlapping-observation dependence is only partially corrected
- **Severity:** P1
- **Standard:** §2.5 — "Serial correlation is considered when estimating uncertainty." / §2.4 — "Purging and embargo account for overlapping information intervals."
- **Evidence:** The FM step is correct — `core/estimators.py:62` — `lag = int(nw_lag) if nw_lag is not None else max(auto_nw_lag(len(slopes)), panel.holding_months)`. But `audit.py:130` annualises an overlapping series with no correction, and `canonical.py:111` compounds it (Q-14, Q-15).
- **Impact:** Inference on the FM premium is defensible; the Sharpe, the cost analysis and the cumulative chart built from the same overlapping returns are not. Two numbers on the same report card therefore use incompatible dependence assumptions.
- **Fix:** Route every performance statistic through one helper that knows the holding period and either de-overlaps or applies an overlap-robust variance; delete the ad-hoc `ann = sqrt(12/h)`.
- **Confidence:** CONFIRMED

### S-15 Bootstrap reps are user-controlled with no floor
- **Severity:** P2
- **Standard:** §2.5 — "Bootstrap resampling preserves dependence where necessary." / §11.1 — "Large allocations have explicit limits."
- **Evidence:** `core/canonical.py:36` — `reps = int(payload.get("bootstrap_replications") or 1000)`; passed to `fm_validity`, `sort_table`, `monotonic_relation_test`.
- **Impact:** `reps=5` yields a Monte Carlo p-value with a resolution of 0.2 presented as a p-value; `reps=10_000_000` is an unbounded CPU sink in a worker process with no timeout.
- **Fix:** Clamp to `[200, 20000]`, and report the Monte Carlo standard error alongside any simulated p-value.
- **Confidence:** CONFIRMED

---

## 6. Hold-out isolation (§5.4) and certification (§5.5)

### A-01 A client can disable protected-window exclusion by adding a key to the payload
- **Severity:** P0
- **Standard:** §5.4 — "Access controls are enforced server-side." / §5.4 — "Failed authorization does not reveal protected statistics."
- **Evidence:** `backend/app/api/research_v2.py:53-54` — `def _clean(payload): return {k: v for k, v in payload.items() if v not in ("", None, [])}` accepts every key; `:137` — `payload = _clean(request.payload)`; `core/panel.py:164` — `if protected and not payload.get("_evaluate_protected"):`.
- **Impact:** `POST /api/labs/research/v2/feature/01/jobs` with `{"payload": {"_evaluate_protected": true}}` returns Feature 01 computed over the protected window. No lock, no authorisation, no audit entry, and the result is persisted to SQLite and downloadable via a share link. The entire hold-out mechanism is advisory.
- **Fix:** Strip unknown/underscore-prefixed keys in `_clean`, and never accept an authorisation flag from the body. Gate protected evaluation on a server-side predicate (a locked spec that matches the payload) inside the API layer, not the panel builder.
- **Confidence:** CONFIRMED

### A-02 Omitting `project_id` bypasses the project seal entirely
- **Severity:** P0
- **Standard:** §5.4 — "Access controls are enforced server-side." / "Certification does not implicitly reopen the hold-out."
- **Evidence:** `backend/app/api/research_v2.py:70` — `run_payload = {**payload, "_sealed_after": store.sealed_after(pid)} if pid else payload`; `core/panel.py:168` — `if payload.get("_sealed_after"):` … `apply_seal(...)`.
- **Impact:** A project sealed at `2024-01-01` only restricts jobs that carry a `project_id`. Re-run the identical payload without `project_id` and the seal is absent, so data after the seal date flows into the panel. The seal is a per-request convenience, not an isolation boundary.
- **Fix:** Derive the seal from a server-side job/project binding (job row → project row), not from a payload key. Refuse to run a sealed study outside its project.
- **Confidence:** CONFIRMED

### A-03 Any unauthenticated caller can delete a protected window
- **Severity:** P0
- **Standard:** §5.4 — "Access controls are enforced server-side." / §5.4 — "Every exposure is recorded in an append-only audit trail."
- **Evidence:** `backend/app/api/research_v2.py:177-181`:
  ```python
  @router.delete("/holdouts/{study_key:path}")
  def release_holdout(study_key: str) -> Dict[str, Any]:
      if not release_window(study_key):
          raise HTTPException(status_code=404, detail="No protected window for that study")
      return {"released": study_key}
  ```
  and `core/holdout.py:78-84` — `del data[key]` then rewrite the store.
- **Impact:** `curl -X DELETE /api/labs/research/v2/holdouts/<key>` permanently removes the protection and, because `release_window` deletes the whole record, destroys the recorded `evaluations` list too. An attacker (or an accidental click) can silently un-protect every study; `GET /holdouts` then shows an empty registry with no trace that anything was ever reserved.
- **Fix:** Require authentication and ownership; replace deletion with a tombstone (`released_at`, `released_by`) so the history survives; log the release.
- **Confidence:** CONFIRMED

### A-04 Unsealing and moving the seal are unauthenticated and unaudited
- **Severity:** P0
- **Standard:** §5.4 — "Hold-out access is authenticated." / §5.4 — "Repeated exposure changes the reported independence status."
- **Evidence:** `backend/app/api/research_v2_projects.py:72-81`:
  ```python
  @router.post("/projects/{pid}/holdout")
  def set_holdout(pid: str, body: HoldoutIn) -> Dict[str, Any]:
      _project(pid)
      s = get_store()
      if body.unseal:
          s.set_holdout(pid, None)
      elif body.sealed_after:
          s.set_holdout(pid, body.sealed_after)
  ```
- **Impact:** `{"unseal": true}` clears the seal with no identity, no reason and no log. `{"sealed_after": "2030-01-01"}` moves the seal forward, re-exposing data that was previously excluded. A seal that can be edited by any caller is not a seal, and the ledger cannot distinguish an honest study from one that was unsealed after peeking.
- **Fix:** Permit unseal only as a one-way, recorded event with actor and justification; forbid moving a seal later (allow only earlier). Store the seal history as append-only rows rather than a single mutable column (`store/db.py:20`).
- **Confidence:** CONFIRMED

### A-05 The protected window is created after the researcher has already seen the results
- **Severity:** P0
- **Standard:** §5.4 — "Hold-out membership is established before tuning."
- **Evidence:** `core/placebo.py:204-211`:
  ```python
  months = int(payload.get("protected_oos_months") or 0)
  key = study_key(panel.config, payload.get("universe"))
  window = get_window(key)
  if months and not window:
      start = panel.dates.max() - pd.DateOffset(months=months)
      window = reserve_window(key, start, months)
  ```
- **Impact:** The window is reserved the first time a placebo is run, i.e. after the main study has been specified, estimated and inspected. It is not a hold-out; it is the last N months of a sample the user has already mined, relabelled "protected". The block bootstrap of the placebo then reports a pristine-looking p-value for it.
- **Fix:** Require the window to be reserved at project creation, before the first job of that study, and refuse to reserve it if any job for the same study key already exists.
- **Confidence:** CONFIRMED

### A-06 `study_key` collides across materially different specifications
- **Severity:** P1
- **Standard:** §5.4 — "Hold-out membership is established before tuning."
- **Evidence:** `core/holdout.py:24-26` — `return f"{config['signal']}|{label.lower()}|{config['dependent_variable']}|h{config['holding_months']}"`, where `label` is the *universe argument only*. Controls, weighting, filters, transform and — critically — `signal_expr` are excluded. A list universe is joined in caller order (`",".join(universe)`).
- **Impact:** Two studies with the same signal *name* but different formulas (`signal: "custom"`, different `signal_expr`) or different controls share one protected window, so the window can be consumed by one specification and then "evaluated once" by another. Reordering the universe list produces a second key for the same study, so the user can obtain a second fresh window by permuting the list.
- **Fix:** Key on the same canonical `spec_hash` used for locks (`core/holdout.py:94-99`), sorted universes included, and include `signal_expr`/`signal_ref` version.
- **Confidence:** CONFIRMED

### A-07 `spec_hash` omits the formula and is order-sensitive
- **Severity:** P1
- **Standard:** §12 — "Strategy specifications use canonical serialization." / "Hash changes are tested when relevant inputs change."
- **Evidence:** `core/holdout.py:97-99` — `keys = ["dependent_variable", "signal", "controls", "estimator", "se", "fixed_effects", "weighting", "start", "end", "holding_months", "universe"]` and `canonical = json.dumps({k: str(spec.get(k, "")) for k in keys}, sort_keys=True)`.
- **Impact:** `str()` on a list of controls makes `["size","value"]` and `["value","size"]` different hashes for the same model; `signal_expr` is absent so two different formulas under `signal="custom"` collide into one lock. A "pre-registered" stamp can therefore be attached to a specification that was never locked.
- **Fix:** Serialise the fully-resolved payload (post-`_config`, with controls sorted and the expression included) through a single canonical function, and use the same function for locks, holdouts and result provenance.
- **Confidence:** CONFIRMED

### A-08 Protected evaluations are recorded as bare timestamps
- **Severity:** P1
- **Standard:** §5.4 — "Every exposure is recorded in an append-only audit trail." / "Repeated exposure changes the reported independence status."
- **Evidence:** `core/holdout.py:69-75` — `data[key]["evaluations"].append(datetime.now(timezone.utc).isoformat())`.
- **Impact:** The trail records that *something* happened but not who, with which specification, or what the result was. It cannot support the "repeated exposure changes the independence status" requirement, and because the registry is a mutable JSON file it is not append-only in any meaningful sense (A-03 deletes it).
- **Fix:** Append `{at, actor, spec_hash, job_id, result_digest}` to an immutable table, and derive `pristine: bool` from `len(evaluations) <= 1`.
- **Confidence:** CONFIRMED

### S-16 Missing dimensions are graded F but excluded from the overall score
- **Severity:** P0
- **Standard:** §5.5 — "Missing tests cannot silently count as passes." / "Grade caps are enforced."
- **Evidence:** `reports.py:151` — `scored = [g for g in grades if g["score"] is not None]`; `reports.py:152` — `score = float(np.mean([g["score"] for g in scored]))`. Missing dimensions are emitted with `score=None, grade="F"` (e.g. `reports.py:107` — `_dim("robustness", None, "F", "No specification ran.")`), and `overall()` drops them.
- **Impact:** A run where robustness, placebo, regimes and diagnostics all failed still displays four F badges, yet the overall score is the mean of only the dimensions that produced a number — so `significance` plus `costs` alone can yield an A. The card contradicts itself and the headline grade is the optimistic side of the contradiction. This directly violates both quoted clauses.
- **Fix:** Treat `score is None` as 0 (not "absent") for required dimensions, and cap the letter at the worst required dimension. Only genuinely optional dimensions (decay without a discovery date) should be exempt, and they must be labelled `N/A` rather than `F`.
- **Confidence:** CONFIRMED

### S-17 Only the significance grade can cap the letter
- **Severity:** P0
- **Standard:** §5.5 — "Grade caps are enforced." / "The verdict reports its strongest limiting reason."
- **Evidence:** `reports.py:154-157`:
  ```python
  sig = next((g for g in grades if g["dimension"] == "significance"), None)
  if sig and sig["grade"] == "F" and letter in "ABC":
      letter = "D"
  ```
- **Impact:** A failed placebo (p = 0.99), a failed robutness (0 of 20 specs survive), or a red-flagged diagnostics panel cannot pull the letter below the arithmetic mean. A signal that is significant but indistinguishable from noise on every robustness test can still be graded A.
- **Fix:** Gate the letter on a conjunction of required dimensions (significance, robustness, placebo) with an explicit `caps` table, and return `limiting_reason` naming the binding constraint.
- **Confidence:** CONFIRMED

### S-18 The verdict text claims more than the evidence supports
- **Severity:** P1
- **Standard:** §5.5 — "A certificate is never described as proof of future profitability." / §16 — "Documentation does not claim untested functionality is verified."
- **Evidence:** `reports.py:157` — `"A": "Strong: the signal passes the full battery."`; `reports.py:158` — returned as `verdict`.
- **Impact:** "Passes the full battery" is asserted even when several dimensions were skipped or failed (see S-16). Users quote this sentence in research notes.
- **Fix:** Generate the verdict from the dimensions that actually ran, and list skipped dimensions explicitly in the sentence.
- **Confidence:** CONFIRMED

### S-19 No certificate identity, hash or version stamp
- **Severity:** P1
- **Standard:** §5.5 — "The certificate identifies the exact strategy version." / "The certificate identifies data and execution settings." / "A certificate hash changes when materially relevant inputs change."
- **Evidence:** `reports.py:150-158` returns `{"grade", "score", "verdict"}` only; `reports.py:81-82` dimension records carry no hash; the report export in `reports.py` writes tables and a grade but no identifier.
- **Impact:** A shared report cannot be tied to the payload, data version or grading version that produced it, so it cannot be cited, audited or reproduced — and two reports with the same grade may come from materially different data.
- **Fix:** Compute `certificate_id = sha256(canonical(payload) + data_version + grading_version + code_version)` and embed it in both the JSON and the exported report.
- **Confidence:** CONFIRMED

### S-20 `is_preregistered` matches only the signal name
- **Severity:** P1
- **Standard:** §2.3 — "Every reported out-of-sample result is genuinely out-of-sample relative to selection." / §5.5 — "Verdict inputs are server-computed."
- **Evidence:** `store/db.py:130-132`:
  ```python
  def is_preregistered(self, pid: str | None, payload: dict) -> bool:
      sig = str(payload.get("signal") or "")
      return bool(pid and sig and any(p["signal"] == sig for p in self.preregs(pid)))
  ```
- **Impact:** Pre-register `signal="momentum"`, then run momentum with any dependent variable, controls, weighting and sample window — and every run is stamped `meta.preregistered = true`. The flag is the platform's only evidence of pre-registration, and it certifies almost nothing.
- **Fix:** Store the preregistered `spec_hash` and compare it to the run's canonical hash; report `preregistered: partial` with the list of differing fields.
- **Confidence:** CONFIRMED

---

## 7. Formula language and outputs (§6.2)

### L-01 The look-ahead guard never rejects a formula
- **Severity:** P0
- **Standard:** §6.2 — "Look-ahead operations are rejected." / §2.2 — "A future-peeking strategy fails an explicit adversarial test."
- **Evidence:** `core/signal_service.py:61-64` — `sl.set_lookahead(sl.lookahead_check(expr, signal, ctx["returns"]))`; `core/signal_service.py:70` — `result["meta"]["lookahead"] = sl.get_lookahead()`; `core/signal_lang.py:437-438` returns `{"flagged": True, "reason": ...}` with no exception, and `core/panel.py:147` proceeds to compute the study.
- **Impact:** A flagged formula is computed, stored, graded and shareable, with a warning attached to metadata that the report card does not read. A user who writes `delay(close, -1)` gets a study, a t-stat and a grade.
- **Fix:** Raise `SignalError` when `flagged` is true (with an explicit override for retrospective/non-predictive mode that is labelled as such in the result), and make the grade dimension fail when the flag is set.
- **Confidence:** CONFIRMED

### L-02 Only three literal negative-lag calls are recognised as forward reads
- **Severity:** P1
- **Standard:** §6.2 — "Look-ahead operations are rejected." / "Unknown functions are rejected."
- **Evidence:** `core/signal_lang.py:347-353`:
  ```python
  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"delay", "delta", "ts_return"} and len(n.args) >= 2:
      a = n.args[1]
      if isinstance(a, ast.UnaryOp) and isinstance(a.op, ast.USub):
  ```
- **Impact:** Any other operator that accepts a lag/window, a variable holding a negative constant (`shift = 0 - 1; delay(x, shift)`), or a negative window passed to a rolling operator is not caught. The whitelist is the security boundary, so this is an incomplete negative test rather than a defence.
- **Fix:** Type the operators by argument semantics (lag, window, horizon) and validate the *evaluated* integer at call time, rejecting negatives for time-series operators.
- **Confidence:** CONFIRMED

### L-03 The statistical leak heuristic cannot catch a leak that a grader would believe
- **Severity:** P1
- **Standard:** §6.2 — "Look-ahead operations are rejected."
- **Evidence:** `core/signal_lang.py:435-438` — `if len(fwd) >= 12 and abs(fwd.mean()) > 0.25: return {"flagged": True, ...}`; returns `flagged: False` otherwise.
- **Impact:** A partially-leaking signal (e.g. using next month's return for 20% of the cross-section) has a mean rank IC well under 0.25 and passes silently. The threshold is a heuristic on a mean, not a test of the formula.
- **Fix:** Keep the heuristic as a secondary diagnostic, but rely on static AST validation plus the truncation-invariance property test (build the panel on data truncated at T, assert signals before T are unchanged).
- **Confidence:** CONFIRMED

### L-04 The look-ahead slot is process-global mutable state
- **Severity:** P1
- **Standard:** §8.2 — "No unnecessary mutable global state." / §12 — "Repeated runs under the supported environment produce equivalent results."
- **Evidence:** `core/signal_lang.py:441-445` — `def set_lookahead(v): _GUARD.value = v` and `def get_lookahead():`; `core/signal_service.py:62,70` writes then reads it around result assembly.
- **Impact:** Two concurrent feature runs in the same process (the report card uses `shared_panel` and calls features in sequence, but the API can also run jobs in-process) can interleave: one run's guard value is attached to another run's `meta.lookahead`. Even single-threaded, any code path that computes a signal without calling `finalize_signal` inherits the previous run's flag.
- **Fix:** Return the guard dict from `finalize_signal` and thread it through explicitly; delete the global.
- **Confidence:** SUSPECTED

### L-05 Uploaded signals are checked for column names only
- **Severity:** P1
- **Standard:** §4.1 — "Required columns and data types are validated." / §2.1 — "Every signal uses only information available at its decision timestamp."
- **Evidence:** `backend/app/api/research_v2.py:124-127` — validates `UPLOAD_KINDS[kind]` columns are present, then returns `{"upload_id", "rows", "columns"}`. `core/panel.py` later joins the upload by ticker/date.
- **Impact:** An uploaded signal may contain future-dated rows (a date after the formation date), duplicate timestamps, negative prices, or a completely different frequency. Nothing checks ordering, duplication or the relationship between the signal date and the return date, so an uploaded file is the easiest way to inject look-ahead.
- **Fix:** Validate on ingest: monotonic unique dates, no rows beyond `today`, coverage report, and reject any row whose timestamp exceeds the study's `data_through`.
- **Confidence:** CONFIRMED

### L-06 Library citations and expected signs are not validated
- **Severity:** P2
- **Standard:** §16 — "Statistical definitions are documented." / "Documentation does not claim untested functionality is verified."
- **Evidence:** `core/signal_library.py` defines the anomaly set; `core/signal_lang.py` and `zoo.py:15` reference it via `EXTENDED` and `LIBRARY`.
- **Impact:** Each library entry ships an author/year citation and an `expected_sign`, but no test checks that the formula reproduces the cited construction or that the sign matches the paper. A wrong citation is presented with the authority of the source.
- **Fix:** Add a per-entry test that asserts the formula's cross-sectional IC sign on a fixed fixture, and store the citation with a DOI/URL that a reviewer can check.
- **Confidence:** SUSPECTED

---

## 8. Application and API security (§7)

### A-09 No research endpoint authenticates or authorises anyone
- **Severity:** P0
- **Standard:** §7.1 — "Every protected operation requires authenticated identity." / "User ownership is checked on every strategy, run and artifact."
- **Evidence:** All four routers declare `APIRouter(prefix="/labs/research/v2", tags=[...])` with no `dependencies=[...]`: `api/research_v2.py:47`, `api/research_v2_projects.py:11`, `api/research_v2_reports.py:21`, `api/research_v2_signals.py:15`. No route declares `Depends` on a security scheme, and `main.py:109-114` mounts them without a router-level guard (the only middleware is CORS at `main.py:62-72`).
- **Impact:** Anyone who can reach the port can create jobs, read every project and job result, reserve/release holdouts, unseal projects, create share links and delete artefacts. On a shared network or a misconfigured deployment this is total exposure of the research IP, including the protected windows that are supposed to be the integrity guarantee.
- **Fix:** Add an authentication dependency at the router level, an `owner_id` column on projects and jobs, and an ownership predicate on every read. Add a negative test that asserts 401/403 without credentials.
- **Confidence:** CONFIRMED

### A-10 Share links expose a full result with no expiry, revocation or owner
- **Severity:** P1
- **Standard:** §7.3 — "Sensitive tokens are not embedded in URLs." / §7.1 — "User ownership is checked on every strategy, run and artifact." / §11.2 — "Large responses are paginated or bounded."
- **Evidence:** `store/db.py:22` — `CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, job_id TEXT, created_at TEXT)`; `store/db.py:143-149` — `get_share` returns `{"feature_id", "result", "created_at"}` (the entire result blob); `api/research_v2_projects.py:92-105` serves it at `GET /share/{token}`.
- **Impact:** The token is a bearer credential in a URL path (logged by proxies and browsers), never expires, cannot be revoked, and is not tied to an owner. Any result — including a protected-window evaluation — can be pinned to a permanent public URL by anyone who can call `POST /share`, with no record of who did it.
- **Fix:** Add `created_by`, `expires_at`, `revoked_at`; scope the payload to a summary rather than the full result; require auth to create and allow the owner to revoke.
- **Confidence:** CONFIRMED

### A-11 Every project and job is enumerable by id
- **Severity:** P1
- **Standard:** §7.1 — "User ownership is checked on every strategy, run and artifact." / "Cross-user access is tested."
- **Evidence:** `api/research_v2_projects.py:43-45` — `@router.get("/projects")` returns all projects; `api/research_v2.py:145-163` — `GET /jobs/{job_id}` returns the stored result for any id; `store/db.py:135-141` — `create_share` accepts any existing `job_id`.
- **Impact:** Combined with job ids written into share URLs and client logs, a third party can walk ids and read results. There is no owner column anywhere in the schema (`store/db.py:18-22`), so ownership cannot be enforced even if auth were added.
- **Fix:** Add `owner_id` to `jobs`, `projects`, `shares`; filter every list and every by-id fetch.
- **Confidence:** CONFIRMED

### A-12 Uploads are read fully into memory before the size check and are never cleaned up
- **Severity:** P1
- **Standard:** §7.3 — "Uploaded files have size and format limits." / "Temporary files have controlled lifetimes." / §7.2 — "Input payload sizes are bounded."
- **Evidence:** `api/research_v2.py:109-113`:
  ```python
  raw = await file.read()
  if len(raw) > MAX_UPLOAD_BYTES:
      raise HTTPException(status_code=413, detail="Uploads are limited to 20 MB.")
  ```
  and `:114-118` writes the file to `UPLOAD_DIR`; the only deletion is `path.unlink(missing_ok=True)` on a column-validation failure (`:125-127`).
- **Impact:** A 5 GB upload is fully materialised in the API process before being rejected, so the 20 MB limit is a post-hoc check that cannot prevent memory exhaustion. Accepted uploads accumulate in `backend/data/research_v2/uploads/` forever, with no quota and no reference counting.
- **Fix:** Stream to a temp file with a byte counter that aborts at the limit; store an `expires_at` per upload and sweep unreferenced files.
- **Confidence:** CONFIRMED

### A-13 Exception text from workers is returned to clients
- **Severity:** P2
- **Standard:** §7.2 — "Internal stack traces are not exposed to clients." / §15 — "Sensitive information is redacted."
- **Evidence:** `backend/app/services/studio/jobs.py:266-267` — `except Exception as exc: return self.update(job_id, status="failed", error=str(exc)[:500])`; `api/research_v2.py:154` — `"error": row["error"]` is returned in the job payload.
- **Impact:** A pandas or numpy failure surfaces as a message containing absolute paths, column names and internal module names. It is not a stack trace, but it is internal detail with no user-facing translation.
- **Fix:** Map known exception types to structured codes and messages; store the raw text only in the server log with a correlation id.
- **Confidence:** CONFIRMED

### A-14 No rate limiting or per-principal quota on expensive endpoints
- **Severity:** P1
- **Standard:** §7.2 — "Rate limits apply to expensive endpoints." / "Resource quotas are enforced per authenticated principal." / §11.2 — "Rate limits protect expensive computations."
- **Evidence:** `api/research_v2_reports.py:24-30` accepts `payload` dicts for report-card/batch/validation; `run_special` dispatches to `reports.run_report_card`, `run_batch`, `run_validation` (`worker.py:20-25`). There is no limiter, quota or per-user counter anywhere in the four routers.
- **Impact:** A single client can submit report-card jobs in a loop; each spawns a worker process and runs seven features with bootstrap batteries. With `max_workers=2` (`api/research_v2.py:64`) two clients can monopolise the pool indefinitely for everyone.
- **Fix:** Add a per-identity concurrent-job cap and a daily job budget, both enforced before `JOBS.submit`.
- **Confidence:** CONFIRMED

### A-15 `ProcessPoolExecutor(max_workers=2)` is a process-global singleton
- **Severity:** P1
- **Standard:** §8.3 — "Queue capacity and concurrency are bounded." / "Resource exhaustion is handled predictably." / §8.2 — "No unnecessary mutable global state."
- **Evidence:** `api/research_v2.py:57-65` — `_POOL: ProcessPoolExecutor | None = None` and `global _POOL`, `max_workers=2, max_tasks_per_child=1`.
- **Impact:** Capacity is bounded only by accident. A third concurrent job waits with no queue position, no timeout and no visibility; a chatty API process can also hold the pool open after shutdown. There is no admission control, so the observable failure mode is "the platform hangs" rather than "queue is full".
- **Fix:** Add an explicit queue with a bounded length and a 429 when full; expose queue depth in the job status; close the pool in a lifespan shutdown hook.
- **Confidence:** CONFIRMED

### A-16 Cancellation does not stop work and is not idempotent in effect
- **Severity:** P1
- **Standard:** §8.3 — "Cancellation is idempotent." / "Long-running work does not block the API event loop."
- **Evidence:** `api/research_v2.py:165-169` — returns a note: `"Cancellation stops the result from being published; a computation already running finishes in the background."`; `_execute` calls `_pool().submit(...).result()` (`:72`) with no cancellation token.
- **Impact:** A user who cancels a 10-minute report card frees nothing; the worker keeps a slot and keeps consuming CPU. Cancelling twice returns the same state, but the compute continues, so the resource guarantee the user expects is absent.
- **Fix:** Track the future per job and call `future.cancel()`; if it already started, terminate the worker process (spawned workers are per-task, so this is safe) and mark the job `cancelled`.
- **Confidence:** CONFIRMED

### A-17 A synchronous `.result()` blocks a threadpool thread for the whole job
- **Severity:** P1
- **Standard:** §8.3 — "Long-running work does not block the API event loop." / §11.2 — "Long jobs return a job identifier promptly."
- **Evidence:** `api/research_v2.py:70-74` — `run_payload = … ; result = _pool().submit(run_in_worker, feature_id, run_payload).result()` inside `_execute`, which is submitted to `JOBS.submit`. The route returns a job id, but the work is executed by a thread in the request-serving process holding `.result()`.
- **Impact:** Each running job pins a thread in the API process for its whole duration. Under load this exhausts the threadpool and new requests queue behind research compute — the exact failure the clause forbids for the event loop's sibling resource.
- **Fix:** Use `add_done_callback` (or an async task with `run_in_executor` on a dedicated executor) so the request process never blocks; keep the callback responsible for persistence.
- **Confidence:** CONFIRMED

### A-18 There is no actor identity to enforce anything against
- **Severity:** P1
- **Standard:** §18.2 — "`X-Studio-Actor` is not trusted as authentication." / "Hold-out budgets cannot be bypassed by changing headers."
- **Evidence:** No research route reads `X-Studio-Actor`, `Authorization` or any identity header. The holdout budget is not a count but an unbounded `evaluations` list (`core/holdout.py:64,73`).
- **Impact:** The standard's hold-out budget controls (per-actor, atomic, header-independent) do not exist in any form. Because there is also no identity, they cannot be added without the schema change in A-11.
- **Fix:** Introduce a verified principal and an atomic per-principal holdout-evaluation budget; treat any actor header as a display label only.
- **Confidence:** CONFIRMED

---

## 9. Backend engineering (§8)

### E-01 The module fails the standard's lint gate with 140 errors
- **Severity:** P1
- **Standard:** §1 — "Automated quality gates" / §8.2 — "Public functions have meaningful type annotations."
- **Evidence:** `cd backend && .venv/bin/ruff check app/services/research_v2 app/api/research_v2*.py` → **140 errors**. Top codes: `UP006` ×49, `BLE001` ×20, `RUF046` ×17, `I001` ×15, `UP035` ×9, `S112` ×6, `UP017` ×4, `UP037` ×3, `RUF059` ×3.
- **Impact:** The gate in §1 is a precondition for declaring a change complete; the module cannot pass it. 49 `UP006` errors are cosmetic (`Dict` → `dict`), but 20 `BLE001` are broad catches and 6 `S112` are `try/except: continue`, which are behavioural.
- **Fix:** Run `ruff check --fix` for the safe subset, then address `BLE001`/`S112` individually (narrow the exception, or add a justification comment). Add the command to CI so the count cannot rise.
- **Confidence:** CONFIRMED

### E-02 Twenty broad exception handlers swallow failures
- **Severity:** P2
- **Standard:** §8.2 — "Exceptions are specific." / "Broad exception handling is justified."
- **Evidence:** `ruff` `BLE001` ×20 across the module; representative: `core/data_loader.py:19-22` (`except Exception: pl = None`), `audit.py:35-37` (`except Exception: continue`), `core/placebo.py` and `core/causal.py` import guards.
- **Impact:** An import or data failure degrades a feature silently into "unavailable" rather than reporting the cause, which is why several grade dimensions can be `F` with no diagnostic.
- **Fix:** Catch the specific exception (`ImportError`, `KeyError`, `ValueError`) and record `unavailable_reason` in the result.
- **Confidence:** CONFIRMED

### E-03 `shared_panel` monkey-patches module globals and is not thread-safe
- **Severity:** P1
- **Standard:** §8.2 — "No unnecessary mutable global state." / §8.1 — "Refactors preserve observable behavior unless intentionally changed."
- **Evidence:** `audit.py:23-56`:
  ```python
  for name in PANEL_MODULES:
      mod = importlib.import_module(f"app.services.research_v2.core.{name}")
      ...
      def wrapper(payload, *args, _orig=original, **kwargs):
          key = json.dumps([payload, args, kwargs], sort_keys=True, default=str)
          ...
      mod.build_panel = wrapper
  ```
  with restoration in `finally`.
- **Impact:** While a report card runs, every module's `build_panel` is replaced process-wide. Any concurrent request in the same process uses the cache, and a crash between patch and restore (a `BaseException`, or a process kill) leaves the module patched. The cache key is a JSON dump of the payload, so an unhashable or non-deterministically-ordered payload can miss the cache silently and build the panel twice — the opposite of the optimisation's purpose.
- **Fix:** Pass a panel cache explicitly through the call chain (or use `functools.lru_cache` on a pure `build_panel` keyed by a canonical hash); do not mutate module attributes.
- **Confidence:** CONFIRMED

### E-04 `research_cache.py` references an attribute that does not exist
- **Severity:** P1
- **Standard:** §8.2 — "Return types represent possible failures accurately." / "Dead code and stale compatibility paths are removed only after usage checks."
- **Evidence:** `backend/app/services/research_cache.py:168` — `if self._is_expired(ts, self.PRICE_TTL)` and `:193` — `"price_ttl_seconds": self.PRICE_TTL`. The class defines `TTL_DAILY`, `TTL_HOURLY`, `TTL_QUOTE` and never assigns `PRICE_TTL` (`:34-36`).
- **Impact:** Any call reaching that branch raises `AttributeError: 'ResearchCache' object has no attribute 'PRICE_TTL'`. The cache is not imported by `research_v2` (only `api/prices.py:21`), so it is dead weight from this module's perspective while being a latent crash for the price endpoints.
- **Fix:** Replace `PRICE_TTL` with the interval-aware TTL map the class already documents, or delete the class if it is unused.
- **Confidence:** CONFIRMED

### E-05 Domain logic and HTTP handling are interleaved in the routers
- **Severity:** P2
- **Standard:** §8.1 — "Domain logic is separated from HTTP handling." / "Persistence logic is separated from numerical algorithms."
- **Evidence:** `api/research_v2.py:68-80` — `_execute` does store lookup, seal injection, pool submission, result persistence and file writing in one function; `api/research_v2.py:104-127` validates, persists, parses and deletes files inside the upload route.
- **Impact:** The seal semantics (A-02) and the result persistence live in the transport layer, so they cannot be unit-tested without a `TestClient`, and the worker entry point duplicates the persistence contract.
- **Fix:** Move job orchestration into a service function that takes a domain request and returns a domain result; keep the router to validation and serialisation.
- **Confidence:** CONFIRMED

### E-06 `_clean` cannot distinguish "explicitly empty" from "absent"
- **Severity:** P2
- **Standard:** §8.2 — "Return types represent possible failures accurately."
- **Evidence:** `api/research_v2.py:53-54` — `return {k: v for k, v in payload.items() if v not in ("", None, [])}`.
- **Impact:** `controls: []` and no `controls` key become identical, so a user cannot request "no controls" explicitly when a default would otherwise apply; and the same filter is what allows the undocumented `_evaluate_protected` key through (A-01).
- **Fix:** Use a typed request model with explicit `None` vs empty-list semantics and `model_config = ConfigDict(extra="forbid")`.
- **Confidence:** CONFIRMED

### E-07 Numeric bounds are absent on user-supplied parameters
- **Severity:** P1
- **Standard:** §7.2 — "Numeric bounds and array sizes are enforced." / §8.2 — "Integer and floating-point boundaries are checked."
- **Evidence:** `core/panel.py:221` — `holding = int(payload.get("forward_months") or payload.get("horizon_months") or REBALANCE_STEP[freq])`; `:243-245` — `"lookback_days": int(payload.get("lookback_days") or 3650)`, `"max_symbols": int(...)`, `"min_assets": int(payload.get("min_assets") or 30)`; `core/canonical.py:34-37` — `buckets`, `reps`, `nw_lag` parsed with no clamp.
- **Impact:** `lookback_days=10**9` scans the whole dataset; `holding_months=100000` makes `formation` empty or the rolling window absurd; `min_assets=-1` disables the cross-section guard. A tiny request can cause an unbounded scan or a division by zero.
- **Fix:** Define a validated `RunConfig` with ranges (`holding 1–60`, `lookback 180–7300`, `min_assets 5–500`, `reps 200–20000`) and reject out-of-range values with 422.
- **Confidence:** CONFIRMED

### E-08 Magic numbers are repeated without named constants
- **Severity:** P2
- **Standard:** §8.2 — "Named constants replace repeated unexplained literals."
- **Evidence:** `core/data_loader.py:408` (`550`, `90`), `core/panel.py:130` (`24`), `:133` (`3`), `core/panel.py:372` (`36`, `24` for betas), `reports.py:20-21`.
- **Impact:** The same economic assumption (minimum history, staleness, outlier threshold) is expressed as a literal in several places, so changing one leaves the others inconsistent.
- **Fix:** Centralise in `research_v2/config.py` with names and docstrings.
- **Confidence:** CONFIRMED

### E-09 The hold-out store's file locking does not protect writes
- **Severity:** P1
- **Standard:** §8.3 — "Concurrent writes cannot corrupt storage." / "Results are committed atomically."
- **Evidence:** `core/holdout.py:40-49` — `_write` opens `STORE.with_suffix(".tmp")` and takes `LOCK_EX` on *that tmp file*, then `tmp.replace(STORE)`. `_read` at `:32-37` takes `LOCK_SH` on `STORE`. Two concurrent writers therefore lock two different files.
- **Impact:** Read-modify-write sequences (`reserve_window`, `record_evaluation`, `release_window`) can lose updates: two evaluations recorded concurrently collapse to one, or a reservation is overwritten by a release. The lock provides no mutual exclusion between writers.
- **Fix:** Lock a dedicated lockfile (or the directory) for the whole read-modify-write, and keep the tmp-file atomic replace for durability.
- **Confidence:** CONFIRMED

### E-10 Job results are written twice with different failure semantics
- **Severity:** P2
- **Standard:** §8.3 — "Results are committed atomically." / "Failed jobs release resources."
- **Evidence:** `api/research_v2.py:73-79` — `store.save_job(job_id, ..., "completed", 1.0, result, ...)` writes the full result into SQLite, then `tmp.write_text(json.dumps(result, default=str)); tmp.replace(path)` writes the same blob to `RESULTS_DIR`.
- **Impact:** The two copies can diverge (a crash between the calls leaves a completed SQLite row with no result file, and `job_status` prefers the in-memory/file path at `:158-162` while the fallback path reads SQLite at `:154`). Duplicate storage also doubles the disk cost of every report card.
- **Fix:** Persist once (the file), store only metadata plus a digest in SQLite, and have one read path.
- **Confidence:** CONFIRMED

### E-11 Store opens a new SQLite connection per call with no busy timeout
- **Severity:** P2
- **Standard:** §8.3 — "Concurrent writes cannot corrupt storage."
- **Evidence:** `store/db.py:1` — `"""Stdlib sqlite3 (WAL) store. One short-lived connection per call…"""`; `_run`/`_q` create and close a connection each time. WAL is set, but no `busy_timeout` is configured.
- **Impact:** Concurrent writers (two jobs finishing, a UI poll writing a share) can raise `database is locked` immediately rather than waiting. The result is a spurious 500 on an otherwise valid operation.
- **Fix:** Set `PRAGMA busy_timeout = 5000` on connect, or use a small connection pool.
- **Confidence:** CONFIRMED

---

## 10. Performance and scalability (§11)

### E-12 The universe parquet is re-scanned for every symbol lookup
- **Severity:** P2
- **Standard:** §11.1 — "Hot paths are profiled before optimization." / "Caches use appropriate version keys."
- **Evidence:** `core/data_loader.py:138-140` — `available_symbols()` → `_market_summary()`; `:142-150` — `_raw_tickers()` is `lru_cache`d, but `_market_source()` and `_market_summary()` are re-derived per process. `api/research_v2.py:99-101` — `GET /symbols` calls `available_symbols()` twice per request (`hits` and the `hits +=` pass).
- **Impact:** A typeahead endpoint rescans a 295 MB parquet's ticker column on each keystroke-triggered request, and does it twice. Under typing load this is the dominant API cost.
- **Fix:** Cache the sorted symbol tuple process-wide with a file-mtime key, and compute the two `hits` lists from one pass.
- **Confidence:** CONFIRMED

### E-13 Report card rebuilds the panel through seven feature calls
- **Severity:** P2
- **Standard:** §11.1 — "Optimization does not change numerical results beyond accepted tolerances."
- **Evidence:** `reports.py:19` — `REPORT_FEATURES = ["01", "02", "03", "04", "05", "08", "11"]`; `core/audit.py:23-56` exists solely to cache the panel across those calls.
- **Impact:** The architecture depends on a monkey patch (E-03) to avoid seven full data builds. When the cache key misses (any payload dict ordering difference), the job cost multiplies by seven.
- **Fix:** Build the panel once in the report-card driver and pass it to each feature's `*_from_panel` entry point (as `canonical_from_panel` already supports).
- **Confidence:** CONFIRMED

### E-14 Jobs load the whole result into memory to return it
- **Severity:** P2
- **Standard:** §11.2 — "Large responses are paginated or bounded."
- **Evidence:** `api/research_v2.py:158-162` — `out["result"] = json.loads(path.read_text())`; `store/db.py:146` returns `job["result"]` whole.
- **Impact:** A report card with several CSVs and series can be tens of MB; `GET /jobs/{id}` returns it in one JSON response with no streaming, no pagination and no size cap.
- **Fix:** Return a summary plus signed per-table download links; cap inline response size.
- **Confidence:** CONFIRMED

---

## 11. Reproducibility (§12)

### E-15 Seeds are hardcoded but never recorded in results
- **Severity:** P1
- **Standard:** §12 — "Random seeds are included." / "Saved runs remain interpretable after software upgrades."
- **Evidence:** `core/stats.py:86,101,112` (`seed: int = 0`), `core/placebo.py:117` (`seed: int = 3`), `core/robustness.py:88,252` (`seed: int = 0, 7`), `core/decay.py:183`, `core/causal.py:356` (`seed: int = 5`). None of these values appear in any `meta` block.
- **Impact:** Results are reproducible today only because the seeds are literals. Change a default and every stored report card silently changes meaning with no way to detect it from the artefact.
- **Fix:** Record `meta.seeds = {...}` per feature and include it in the certificate hash (S-19).
- **Confidence:** CONFIRMED

### E-16 Results carry no data version or source provenance
- **Severity:** P1
- **Standard:** §12 — "Data version is included in provenance." / §4.2 — "Every run records its dataset version." / "Source provider and retrieval date are recorded."
- **Evidence:** `api/research_v2.py:76` — `tmp.write_text(json.dumps(result, default=str))`; the result's `meta` is populated by `attach_audit`/`attach_lookahead` with a survivorship note and a lookahead dict, but no file hash, mtime, row count or provider.
- **Impact:** Re-running the same payload after a parquet refresh can change the grade, and the two results are indistinguishable except by grade. There is no way to answer "was this before or after the data correction?"
- **Fix:** Add `meta.provenance = {market_universe: {sha256, rows, first_date, last_date}, fundamentals: {...}, factors: {...}, code_git_sha}`.
- **Confidence:** CONFIRMED

### E-17 `lru_cache` on loaders has no invalidation
- **Severity:** P1
- **Standard:** §11.1 — "Cache invalidation is tested." / §13.3 — "Data refresh invalidates affected caches."
- **Evidence:** `core/data_loader.py:12` imports `lru_cache`; `:142-143` decorates `_raw_tickers()` with `@lru_cache(maxsize=1)`; similar caching in the fundamentals path.
- **Impact:** A long-lived API process serves stale symbols and fundamentals after a refresh. The same code path inside a spawned worker is fresh, so the API and the job can disagree about the universe within one session.
- **Fix:** Key the cache on file mtime/size, and expose a cache-clear on the refresh path.
- **Confidence:** SUSPECTED

### E-18 JSON serialisation is not canonical
- **Severity:** P2
- **Standard:** §12 — "Serialization order is deterministic." / "Hashes are computed from canonical representations."
- **Evidence:** `api/research_v2.py:77` — `json.dumps(result, default=str)`; `core/holdout.py:45` — `json.dump(data, fh, indent=2, default=str)`; `core/holdout.py:98` — `json.dumps(..., sort_keys=True)` only for the spec hash.
- **Impact:** Dict insertion order and float repr determine the bytes, so two logically identical results can differ byte-for-byte. Any future content hash would be unstable.
- **Fix:** One `canonical_json()` helper: sorted keys, `separators=(",", ":")`, floats normalised to a fixed significant-figure format.
- **Confidence:** CONFIRMED

### E-19 Result files have no schema version
- **Severity:** P2
- **Standard:** §12 — "Saved runs remain interpretable after software upgrades."
- **Evidence:** `api/research_v2.py:76` writes the raw result dict; nothing writes a `schema_version`. `RESULTS_DIR / f"{job_id}.json"` is read back at `:160` with no migration.
- **Impact:** When a feature's output shape changes, old result files either fail to render or render misleadingly. There is no way to know which shape a file followed.
- **Fix:** Write `{"schema_version": 1, "result": ...}` and migrate on read.
- **Confidence:** CONFIRMED

---

## 12. Testing (§13)

### T-01 Test volume is far below the module's surface
- **Severity:** P1
- **Standard:** §13.1 — "Every nontrivial branch has an appropriate test." / §13.5 — "Test coverage is evaluated by risk, not percentage alone."
- **Evidence:** Six files totalling 554 lines (`wc -l backend/tests/test_research_v2_*.py`: data_and_api 102, features 43, math 115, projects 69, reports 116, signals 109) against 8,294 lines under `backend/app/services/research_v2/`.
- **Impact:** The riskiest code — holdout enforcement, seal application, grading caps, overlapping-return annualisation — has no direct test. The 43-line feature test cannot exercise eleven features with multiple branches each.
- **Fix:** Add targeted tests for the P0 paths first: seal bypass, `_evaluate_protected` rejection, grading cap, truncation invariance, overlapping-return annualisation.
- **Confidence:** CONFIRMED

### T-02 No test asserts the hold-out cannot be bypassed
- **Severity:** P0
- **Standard:** §13.5 — "Every fixed security bug gets a negative test." / §13.3 — "Authorization is enforced across interfaces."
- **Evidence:** `backend/tests/test_research_v2_projects.py` (69 lines) tests project creation and preregistration; there is no assertion that a job payload containing `_evaluate_protected` or omitting `project_id` is refused.
- **Impact:** The three P0 hold-out bypasses (A-01, A-02, A-03) survived because no test encodes the invariant "protected data is unreachable without authorisation". Adding the test is what makes the fix durable.
- **Fix:** Add `test_protected_window_not_reachable_without_lock`, `test_seal_applies_without_project_id` (expected: refuse), `test_unauthenticated_delete_holdout_forbidden`.
- **Confidence:** CONFIRMED

### T-03 No look-ahead regression test
- **Severity:** P1
- **Standard:** §13.2 — "Removing future bars does not change earlier signals."
- **Evidence:** No test builds a panel twice with different end dates and compares the overlapping history.
- **Impact:** Q-09, Q-10 and L-01 are all detectable by one metamorphic test, which does not exist.
- **Fix:** Add the truncation-invariance test now that Q-10 is fixed.
- **Confidence:** CONFIRMED

### T-04 Tests do not assert numerical independence
- **Severity:** P2
- **Standard:** §13.1 — "Expected results are independently justified." / "Tests assert behavior rather than implementation details."
- **Evidence:** `backend/tests/test_research_v2_math.py` (115 lines) covers the estimator primitives; the expected values are computed from the same helpers where they could be closed-form.
- **Impact:** A sign or annualisation error inside a shared helper passes through the test that uses the helper.
- **Fix:** Add closed-form cases: a two-asset CAPM with known λ, a constant-return series with a known Sharpe, a monotone signal with a known sort spread.
- **Confidence:** SUSPECTED

### T-05 Skipped dimensions are not tested as skips
- **Severity:** P2
- **Standard:** §5.3 — "Every skipped test reports its reason." / §5.5 — "Missing tests cannot silently count as passes."
- **Evidence:** `reports.grade_dimensions` emits `"No specification ran."`, `"No diagnostics ran."`, `"No permutation test."` — but `backend/tests/test_research_v2_reports.py` does not assert that a missing dimension blocks an A.
- **Impact:** The S-16/S-17 grading defects are behavioural and currently unasserted, so a fix could regress unnoticed.
- **Fix:** Add `test_missing_dimension_caps_grade` with a synthetic result set where only significance and costs are present; assert the letter is not A.
- **Confidence:** CONFIRMED

---

## 13. Dependencies (§14)

### E-20 Dependencies are lower-bounded, not pinned
- **Severity:** P2
- **Standard:** §14 — "Package versions are locked." / "Integrity checks are preserved."
- **Evidence:** `backend/pyproject.toml:5-16` — `"arch>=6.0.0"`, `"fastapi>=0.100.0"`, `"differences>=0.3,<1"`, `"httpx>=0.24.0"`, `"joblib>=1.3.0"`, `"lightgbm>=4.0.0"` and so on; no upper bounds except `differences`.
- **Impact:** A fresh `uv sync` can install a new minor of `linearmodels`, `statsmodels`, `arch` or `pandas` that changes estimator defaults (degrees-of-freedom, kernel bandwidth, `resample` codes), silently changing numerical results. Since no result records the package versions (E-16), the drift is undetectable.
- **Fix:** Commit `uv.lock` (present) and make CI install with `--frozen`; additionally record resolved versions in `meta.provenance`.
- **Confidence:** CONFIRMED

### E-21 No third-party notice for copied econometric implementations
- **Severity:** P2
- **Standard:** §14 — "Third-party notices are maintained." / "Copied code retains required attribution."
- **Evidence:** `core/stats.py:1-11` documents Newey-West (1987), Politis-Romano (1994), Patton-Timmermann (2010), Chow (1960) and Andrews (1993) as "standard, citable" implementations; the Shanken correction is coded by hand in `core/estimators.py:283-286`.
- **Impact:** Hand-coded academic estimators carry no licence/attribution requirement in themselves, but the module has no notice file and no note of which routines are reimplementations versus library calls, so a licence review of a distribution cannot be completed from the repository.
- **Fix:** Add `THIRD_PARTY.md` listing each reimplemented procedure with its citation, and note where the library version is used instead.
- **Confidence:** CONFIRMED

---

## 14. Observability (§15)

### E-22 No correlation id, structured log or job metric
- **Severity:** P2
- **Standard:** §15 — "Requests have correlation identifiers." / "Jobs have traceable identifiers." / "Job duration and failure rates are measurable."
- **Evidence:** `api/research_v2.py` and the other routers import no logger and emit no log lines; `main.py:31-38` configures a plain text logger for the app. The only job metadata is the SQLite row.
- **Impact:** A failed report card cannot be traced to a request, a payload or a duration. The standard's operational requirements cannot be evaluated because no telemetry exists.
- **Fix:** Add a request id middleware, structured job logs with `job_id`, `feature_id`, `duration_ms`, `outcome`, and a counter per outcome.
- **Confidence:** CONFIRMED

### E-23 Numerical "unavailable" states are reported as failures without a cause
- **Severity:** P1
- **Standard:** §15 — "Numerical failures are observable." / §8.2 — "No silent fallback changes financial meaning."
- **Evidence:** Many features return `{"available": False, "reason": ...}` (e.g. `core/placebo.py:195`, `core/causal.py`, `core/estimators.py:277`); `reports.grade_dimensions` converts that to an `F` with a generic sentence (`reports.py:107`, `:114`, `:127`).
- **Impact:** The user sees "No diagnostics ran" with no way to know whether the cause was missing data, an import failure or a genuine refusal. The reason string exists in the result but is dropped by the grader.
- **Fix:** Propagate `reason` into the dimension summary and the export.
- **Confidence:** CONFIRMED

---

## 15. Documentation and change management (§16)

### E-24 Module status documents overstate completeness
- **Severity:** P1
- **Standard:** §16 — "Checklist completion reflects actual evidence." / "Documentation does not claim untested functionality is verified." / §18.5 — "No incomplete phase is marked complete solely because its code exists."
- **Evidence:** `backend/app/services/research_v2/DONE.md` and `WORK_LEFT.md` describe the battery as complete. The defects in this register (hold-out bypass, grading cap, overlapping-return annualisation) are not disclosed in either file.
- **Impact:** A reader of `DONE.md` concludes the module is release-ready. This audit finds otherwise on the standard's P0 criteria.
- **Fix:** Rewrite both files against this register; move remaining work into `WORK_LEFT.md` with owners, and add a "Known limitations" section that names the holdout and grading issues explicitly.
- **Confidence:** CONFIRMED

### E-25 No decision record for the grading or hold-out policy
- **Severity:** P2
- **Standard:** §16 — "Decisions record rationale and alternatives." / "Temporary exceptions have an owner and expiration or review condition."
- **Evidence:** No file under `docs/` records why the score bands are 85/70/55/40, why only significance caps the letter, or why the hold-out is a mutable JSON registry rather than a table.
- **Impact:** The next engineer cannot tell an intentional simplification from an oversight, and the standard's nine-part decision-record format has nothing to attach to.
- **Fix:** Add `docs/decisions/ADR-00x-research-grading.md` and `ADR-00y-research-holdout.md` recording the current behaviour, the alternatives and the revisit condition.
- **Confidence:** CONFIRMED

### E-26 Public API contract drifted from the documented contract
- **Severity:** P2
- **Standard:** §16 — "Public behavior changes are documented." / "Deprecated behavior is identified."
- **Evidence:** `docs/architecture/RESEARCH_V3_CONTRACTS.md` documents the research API. The implementation exposes additional unauthenticated operations not described there (`DELETE /holdouts/{study_key:path}`, `POST /projects/{pid}/holdout` with `unseal`, `POST /share`, `GET /share/{token}`) in `api/research_v2.py:177-181` and `api/research_v2_projects.py:72-105`.
- **Impact:** An integrator reading the contract will not know that share links exist, are permanent, and return full results — the exact disclosure surface this audit flags in A-10.
- **Fix:** Regenerate the contract from the OpenAPI schema, and document the security model for each route.
- **Confidence:** CONFIRMED

---

## 16. Release evidence (§19)

### E-27 The module cannot produce the required release evidence
- **Severity:** P2
- **Standard:** §19 — "Final release evidence" (change summary, verification, final review) / §0 — "An unverified requirement must never be reported as passing."
- **Evidence:** The lint gate fails (E-01, 140 errors). No test run is recorded for the module in this audit beyond file inspection. No release evidence document exists under `docs/`.
- **Impact:** Under the standard's enforcement policy, the module's requirements are neither PASS nor N/A; they are UNVERIFIED, and the policy forbids reporting them as passing.
- **Fix:** Produce a §19 evidence block per change: exact commands, exact results, the P0 list above with status.
- **Confidence:** CONFIRMED

---

## Appendix A — Clauses marked N/A

These clauses were considered and judged genuinely inapplicable to a research-panel module that does not execute orders. The reason is given so the judgement can be challenged.

| Clause | Reason for N/A |
|---|---|
| §3.1–3.3 (fill modelling, accounting invariants) | The module builds a research panel and reports premia; it does not simulate fills, cash or positions. The cost model in `audit.py:88-146` is an analytic approximation, not an execution engine. |
| §3.4 (independent numerical verification) | Partially applicable and reported under T-04 rather than N/A; the clause as written targets the backtest engine. |
| §6.3 (Python strategy execution) | No user Python is executed. Formulas compile to whitelisted pandas operations (`core/signal_lang.py:1-9`). |
| §7.4 (AI and agent security) | No model or agent is used; `reports.py:1-5` states explicitly that sentences are templates and "no language model". |
| §9.1, §9.3–9.5, §10 (frontend, UX, responsive, accessibility) | Backend-only audit; no React surface was reviewed. |
| §11.3–11.4 (frontend performance and budgets) | As above. |
| §18.1 (market-data freshness) | The module is offline research over a local parquet; there is no live feed to be fresh. Freshness is instead reported as a provenance gap under E-16. |
| §18.4 (chart and engine parity) | The module does not render charts; `core/canonical.py:104-111` emits series for a frontend that was out of scope. |

---

## Appendix B — Verified as correct (not defects)

Recording these matters because the standard requires evidence, and because a later reader will otherwise re-litigate them.

- **Newey-West lag accounts for overlapping h-month returns.** `core/estimators.py:62` — `lag = int(nw_lag) if nw_lag is not None else max(auto_nw_lag(len(slopes)), panel.holding_months)`. The FM inference is correctly overlap-aware. The defect is elsewhere (S-14: the Sharpe path does not use this).
- **Dependent variable is genuinely forward.** `core/panel.py:373` — `forward = growth.shift(-horizon)`; a formation at `t` predicts `(t, t+h]`. No same-period leakage.
- **Fundamentals are not back-filled.** `core/data_loader.py:413` — "Dates before the first report are NaN: no backfill."
- **Formulas are parsed, not evaluated.** `core/signal_lang.py:343-345` delegates to `app.services.shared.formula.parse` with an explicit field whitelist and arity map; there is no `eval`, `exec`, `getattr` or import in the evaluator.
- **Expressiveness is bounded.** `MAX_EXPR_LEN`, `MAX_NODES` are imported from the shared formula module (`core/signal_lang.py:24`).
- **Bootstrap and permutation seeds are fixed literals**, so a given payload reproduces today (the reproducibility defect is that the seeds are unrecorded, E-15).
- **Historical estimator stubs are gone.** `two_pass` now uses `linearmodels` (`core/estimators.py:279`), `causal.py` uses `pyfixest`/`differences`/`rdrobust`/`pysyncon`; the fake GMM, fake Shanken and proxy DiD/RD/IV/SCM reported in the 2026-09 review have been replaced. They are not defects in the current code.
