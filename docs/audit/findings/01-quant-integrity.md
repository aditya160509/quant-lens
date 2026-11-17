# 01 — Quant Integrity Audit: Research V2 Backend

**Scope:** `backend/app/services/research_v2/` — all of `core/`, `features/`, `universes.py`, `registry.py`, `reports.py` (signal and return construction), `audit.py`, and the data-semantics paths of `app/api/research_v2*.py`.
**Standard:** `docs/studio/standards/CODE_STANDARDS.md` §2.1, §2.2, §2.3, §2.4, §5.2, §5.4, §4.1, §4.2, §4.3, §20, applied by analogy to a research (not execution) module.
**Method:** read-only source review plus read-only probes of the shipped datasets through `backend/.venv/bin/python`. No source file was modified. Runtime behaviour that depends on job state was not exercised.
**Severity rule used:** P0 = the defect changes a reported return, premium, or eligible universe in the direction of hindsight or fabrication; P1 = wrong methodology or inference; P2 = maintainability, provenance, or bounded mis-description. Effort S/M/L.
**Verdict:** 37 issues — 7 P0, 24 P1, 6 P2. The panel is not point-in-time, the price file is survivor-only, and macro/regime conditioning uses end-of-sample macro vintages.

| Severity | Count | Meaning here |
|---|---|---|
| P0 | 7 | Look-ahead, false chronology, survivor-only data, or fabricated paths inside a reported result |
| P1 | 24 | Wrong methodology, wrong inference, or misleading provenance that changes interpretation |
| P2 | 6 | Documentation, dead paths, bounded mis-description |

---

## Q-01 Execute at the next eligible open instead of at the close that defines the signal

**Severity:** P0 · **Effort:** M · **Confidence:** CONFIRMED

> §2.2: "Signals and fills have separate timestamps." / "Default close-of-bar signals execute no earlier than the next eligible open." / "Completed closing prices are not assumed known before the close."

**Evidence:**
- `backend/app/services/research_v2/core/panel.py:129` — `close_m = close_d.resample("ME").last()`
- `backend/app/services/research_v2/core/panel.py:133` — `returns = returns.where(returns.abs() < 3)`
- `backend/app/services/research_v2/core/panel.py:372-375` — `growth = (1 + returns).rolling(horizon).apply(np.prod, raw=True) - 1` … `forward = growth.shift(-horizon)`

**Impact:** One monthly series carries both roles. `returns[t]` is the return from the close of month `t-1` to the close of month `t`; the signal is built from `close_m` up to and including month `t`; the dependent variable for a row dated `t` is the return from the close of `t` to the close of `t+h`. So the trade is filled at the same completed close that the signal reads. Every result inherits the close-to-close drift of the day the signal is observed, which is not tradeable. The bias is largest exactly where the library is most concentrated: `str_1m` (`signal_library.py:17`, formula `returns`, expected sign −1) and `str_2m` both load on the most recent close-to-close move, so bid-ask bounce and the observation-day gap are attributed to the strategy. A 1-month reversal premium estimated this way is not comparable to the published premium it is benchmarked against, and the audit surface reports the number as if execution were feasible.

**Fix:** Separate decision from fill. Keep the signal at row `t`, but build the dependent return from the first executable price strictly after `t` — `open[t+1]` to `open[t+1+h]` (or `close[t+1]` onward), via a helper that returns both the entry date and the exit date per row. Add an `execution_price` config (`next_open`, `next_close`) that is hashed into the specification, record it in `panel.config` and in `meta.data_audit`, and add the adversarial test the standard already demands: truncating all data after `t` must leave the row-`t` signal bit-identical, and shifting execution one bar later must reduce short-horizon reversal premia.

---

## Q-02 Lag fundamentals by an actual filing date instead of a fixed 90 days from report date

**Severity:** P0 · **Effort:** M · **Confidence:** CONFIRMED

> §2.1: "Corporate announcements and financial statements respect publication dates." / "Fundamentals respect realistic filing and ingestion delays." / "Data availability is distinguished from data observation."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:408` — `def point_in_time_fundamental(field: str, dates: pd.DatetimeIndex, symbols: Iterable[str], lag_days: int = 90, max_age_days: int = 550) -> pd.DataFrame:`
- `backend/app/services/research_v2/core/data_loader.py:425` — `sub = sub.assign(available=sub["reportDate"] + pd.Timedelta(days=int(lag_days)), value=pd.to_numeric(sub[field], errors="coerce"))`
- `backend/app/services/research_v2/core/data_loader.py:452` — (same construction inside `annual_growth`)
- Probe: `backend/data/fundamentals/master_fundamentals.parquet` has 364 columns and **no `filingDate` column**; only `reportDate` (min 2021-01-31) and `periodType`.

**Impact:** 90 days is a flat assumption about a quantity with a legal distribution: 10-K is due 60–90 days after fiscal year end depending on filer class, but a Form 12b-25 (NT 10-K) extends it to 105–120 days, and amendments arrive later still. Every late filer's statements therefore become "knowable" before they were filed. Combined with Q-18's annual-only flow fields, the overlap is systematic rather than idiosyncratic: the firms that file late are disproportionately distressed, and late filing correlates with the negative earnings surprises that value and profitability signals trade on. Survivorship/backfill is also possible if the vendor rewrote history after restatement.

**Fix:** Carry a filing timestamp through the pipeline. If the vendor cannot supply `filingDate`, then (a) store the last-known report per `(ticker, available)` with the *maximum* observed lag rather than a constant, (b) add a per-filer-class lag table (60/75/90 days plus a 15-day buffer for 12b-25) keyed off market cap, and (c) disclose in `data_audit` that availability is modelled, not observed. If neither is possible, refuse fundamental signals before 2021-05 and mark `confidence: modelled-availability` on every fundamental result.

---

## Q-03 Evaluate universe membership at each formation date, not from full-sample price and liquidity statistics

**Severity:** P0 · **Effort:** M · **Confidence:** CONFIRMED

> §2.1: "Universe membership is evaluated point-in-time wherever historical membership data exists." / "Cross-sectional normalization uses only the eligible universe at that timestamp."

**Evidence:**
- `backend/app/services/research_v2/universes.py:61-65` — `pl.col("Close").last().alias("last_close")`, `(pl.col("Close") * pl.col("Volume").fill_null(0)).tail(recent_days).mean().alias("adv")`, `pl.col("Date").first().alias("first_date")`, `pl.col("Date").last().alias("last_date")`
- `backend/app/services/research_v2/universes.py:149` — `mask &= table["last_close"] >= float(payload["min_price"])`
- `backend/app/services/research_v2/universes.py:151` — `mask &= table["adv"] >= float(payload["min_dollar_volume"])`
- `backend/app/services/research_v2/universes.py:153` — `age = (table["last_date"].max() - table["first_date"]).dt.days / 30.4`

**Impact:** All three screens are computed once, as of the last row of the file, and then applied to every historical formation date. A stock that trades at $0.80 today is excluded from 2010 even though it was a $40 stock then, and a stock that is liquid today is included in 2005 even though it was untradeable then. `min_listing_months` is measured against `table["last_date"].max()` — today's snapshot — so a 2010 backtest uses 2010 listings that survived to 2026. This is hindsight in universe construction, and it is the mechanism by which "small-cap" and "illiquid" subsamples quietly become the set of small caps that later grew up.

**Fix:** Compute the screens on the panel's own `(date, ticker)` grid inside `build_panel`, from trailing windows: rolling 63-day median dollar volume ending at the formation date, the close at the formation date, and months since the first observation *up to that date*. `universes.select_symbols` should stay a coarse candidate screen for the API; the authoritative filter must be the time-varying mask in `_universe_mask`, which already has the right shape.

---

## Q-04 Build a delisting-aware panel; the price file contains essentially no dead securities

**Severity:** P0 · **Effort:** L · **Confidence:** CONFIRMED

> §2.1: "Missing historical availability metadata produces a limitation or refusal." / §4.2: "Survivorship limitations are recorded." / "Missing delisted securities are disclosed."

**Evidence:**
- `backend/app/services/research_v2/core/panel.py:129` — `close_m = close_d.resample("ME").last()` (the last observed price inside a month becomes that month's close, whether or not the security still trades)
- `backend/app/services/research_v2/audit.py:68` — `adjustments.append("Delisted names are not in the file and no delisting returns are applied, so results carry survivorship bias.")`
- Probe of `backend/data/market_universe.parquet`: 4,158 tickers, 1996-03-18 → 2026-07-06. Last-observation date distribution: 3,413 tickers end in 2026-01, 692 in 2026-02, 15 tickers in total end before 2025-01.

**Impact:** 4,158 names over 30 years with 15 apparent deaths is not a market universe; it is the set of securities that still existed at snapshot time. Acknowledging this in `data_audit` does not neutralise it, because the docstring on `us_equity_symbols` presents the result as "US common equities" and no result carries a survivorship-adjusted counterpart. Two distinct distortions follow: (i) momentum, value and size premia are overstated because the sample excludes the firms that went to zero, which is the whole point of the anomaly literature; (ii) `resample("ME").last()` silently re-dates the final trade of a dying firm to a month-end, so a stock that last printed on the 4th contributes a 26-day partial return as if it were a full month, without the −30% to −100% delisting return that accompanied it. `compute_dependent` then compounds that truncated path forward with `shift(-horizon)`.

**Fix:** Source delisted names with their final trade date, delisting code and delisting return (CRSP `dlret`, or the vendor equivalent) and append the delisting return to the last observed month. Where delisting returns are unavailable, mark the final month of any security whose last observation precedes the panel end as missing rather than observed, so the dependent variable is NaN instead of a truncated partial-month return. Add a coverage assertion: `share of tickers with a delisting flag` and `share of delisted tickers with a delisting return` must be reported in `data_audit`, and refuse to label a result "survivorship-adjusted" until they are populated.

---

## Q-05 Stop applying one static sector label to the entire history in masks and neutralization

**Severity:** P0 · **Effort:** M · **Confidence:** CONFIRMED

> §2.1: "Every signal uses only information available at its decision timestamp." / "Every feature has an explicit observation timestamp."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:392-399` — `"""Sector per ticker. Sector membership is treated as time-invariant."""` … `out = df.dropna(subset=["sector"]).sort_values("reportDate").groupby("ticker")["sector"].last()`
- `backend/app/services/research_v2/core/panel.py:427` — `sectors = static_sectors().reindex(symbols)` (then used by `ex_financials` / `ex_utilities` at lines 428-431)
- `backend/app/services/research_v2/core/signal_lang.py:143` — `lab = dl.static_sectors()` (backing the `sector` group key used by `neutralize(...)` and `group_rank`)

**Impact:** The most recent sector in the file is projected back to 1996. Two mechanisms leak hindsight. First, reclassification: GICS changed in 2016, 2018 and 2023, so a name that was "Financial Services" in 1996 and "Information Technology" in 2024 is treated as technology for its whole history, and `ex_financials` then includes it during the period when it was a bank. Second, genuine business change: a firm that became a REIT or a utility later is excluded retroactively from the pre-change sample. The same label feeds `neutralize(momentum, sector)` and `mom_sector_adj`, so the de-meaning benchmark of a 2005 cross-section is built from 2026 taxonomy. The data file does carry `reportDate` per sector row — the information needed for a point-in-time label is already present and thrown away.

**Fix:** Replace `static_sectors()` with `sector_at(dates, symbols)`: pivot the `(reportDate, ticker, sector)` rows into a date × ticker frame, apply the same availability lag as Q-02, and forward-fill within the max-age window. Wire it into `_universe_mask` and into `load_field("sector"/"industry")`. If a firm has no sector observation before a date, that date must be ineligible for `ex_financials` rather than assumed to be the eventual label.

---

## Q-06 Replace final-vintage macro with release-dated vintages, and stop treating NBER dating as contemporaneously known

**Severity:** P0 · **Effort:** M · **Confidence:** CONFIRMED

> §2.1: "Revised macroeconomic data is not treated as originally published data." / "Data availability is distinguished from data observation." / §2.3: "Regime definitions do not depend on future observations."

**Evidence:**
- `backend/app/services/research_v2/core/panel.py:485` — `return m.set_index("Date").sort_index().resample("ME").last().reindex(dates)`
- `backend/app/services/research_v2/core/regime.py:53-54` — `if "usrec" in m.columns:` / `out["recession"] = m["usrec"].reindex(idx)`
- `backend/app/services/research_v2/core/regime.py:62-64` — `nber_recession` returns `s["recession"].map({1.0: "recession", 0.0: "expansion"})`
- Probe: `load_macro()` returns a daily 12,368 × 22 frame built from `data/factors/processed/category7_macro_regime.parquet`; columns include `cpi`, `usrec`, `baa10y`, `dgs10`, `vixcls`. There is no vintage/`realtime_start` column anywhere, and the `parquet_cache/macro_*.parquet` files hold only `(index, VALUE)` pairs.

**Impact:** Three separate leaks. (1) A reference-dated series (CPI, industrial production) is stamped at the *reference* month end, but the value is published mid-*following*-month, so `_monthly_macro` grants roughly two weeks of look-ahead on every release. (2) These are final FRED vintages: CPI, GDP and credit spreads are revised, so a 2010 backtest uses numbers nobody had in 2010. (3) `usrec` is NBER's completed chronology — the December-2007 peak was announced in December 2008 and the June-2009 trough in September 2010 — so `nber_recession` labels months as "recession" eleven months before that was knowable, and the regime-conditional premia in F04 inherit that. Because regimes are the conditioning variable for a headline output, this is look-ahead inside a reported result, not a footnote.

**Fix:** Store ALFRED real-time vintages keyed by `(series, realtime_start)` and select, at each formation date, the observation with the largest `realtime_start <= t`. For release-lagged series, stamp the value at its publication date rather than its reference date. For `usrec`, use the announcement date of the peak/trough call (or a vintage dated at least 12 months after period end) and add an explicit `regime_knowledge_lag` config that is hashed and disclosed. If vintages cannot be sourced, the regime features must carry a visible "final-vintage macro" limitation and must not be presented as tradeable conditioning.

---

## Q-07 Do not fill missing monthly returns with zero in the synthetic control

**Severity:** P0 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Missing observations are distinguished from genuine zero values." / §20.8: "Uncertainty must remain visible. Insufficient evidence produces a limitation, not a fabricated conclusion."

**Evidence:**
- `backend/app/services/research_v2/core/synthetic.py:86` — `rets = rets.loc[:, rets.loc[pre_mask].notna().mean() > 0.95].iloc[1:].fillna(0.0)`
- `backend/app/services/research_v2/core/synthetic.py:90` — `y = rets.cumsum()  # log cumulative return path`
- `backend/app/services/research_v2/core/synthetic.py:321` — (the staggered driver applies the same `fillna(0.0)` path)

**Impact:** `rets` are monthly log returns. After `cumsum`, a missing month becomes a perfectly flat segment in the treated unit's and every donor's cumulative path. Two consequences: the pre-treatment fit is distorted by artificial zero-variance stretches (RMS pre-period error shrinks, which mechanically *inflates* the post/pre RMSPE ratio that the whole inference rests on), and a post-treatment gap can be manufactured or erased by a data hole. Donors are screened at 95% pre-period coverage, so the holes land in the post period — exactly where the effect is measured. A treated firm that stops trading after the event gets a flat counterfactual comparison and an apparently ordinary gap.

**Fix:** Do not fill. Restrict the fit to donor columns with complete pre- and post-period coverage, run the fit on the intersection of available months, and carry the missing months as NaN so the gap and the placebo distribution are computed on the same complete support. If interpolation is genuinely needed for a sparsely traded donor, use a documented causal (backward-only) interpolation and record it in `details`.

---

## Q-08 Mask the universe before orthogonalizing the signal

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.1: "Cross-sectional normalization uses only the eligible universe at that timestamp."

**Evidence:**
- `backend/app/services/research_v2/core/panel.py:147` — `signal = finalize_signal(compute_signal(cfg["signal"], ctx, payload), ctx, payload)  # orthogonalize_against + look-ahead guard`
- `backend/app/services/research_v2/core/signal_service.py:58` — `signal = sl.orthogonalize(signal, [_resolve_other(o, ctx) for o in others])`
- `backend/app/services/research_v2/core/panel.py:153-154` — `universe_mask = _universe_mask(...)` then `signal = signal.where(universe_mask)`

**Impact:** `orthogonalize_against` fits a cross-sectional regression per date over every column in the panel, including financials that `ex_financials` will remove and microcaps that `ex_microcaps` will remove. The residual loaded onto the surviving names is therefore computed against a benchmark set that the study has already declared ineligible. In a sector- or size-tilted application this shifts the orthogonalized signal materially, and the same ordering makes the reported `mean_assets` inconsistent with the set used to construct the signal. The `signal_transform` path (`panel.py:188`) correctly runs after masking; orthogonalization is the one that does not.

**Fix:** Move the mask ahead of `finalize_signal`: compute `universe_mask` first, apply `signal = signal.where(universe_mask)`, then orthogonalize and run the look-ahead guard on the masked frame. Keep the mask in the context so `_apply_transform` and `sort_portfolios` see the same eligible set.

---

## Q-09 Remove the full-sample coverage filter from panel construction

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.1: "Universe membership is evaluated point-in-time wherever historical membership data exists."

**Evidence:**
- `backend/app/services/research_v2/core/panel.py:130` — `close_m = close_m.loc[:, close_m.notna().sum() >= 24]`

**Impact:** A ticker is retained only if it has at least 24 monthly observations *anywhere in the sample*, counted over the whole history before any date selection. This drops short-lived listings (IPOs in the last two years, firms that delisted early) entirely, which is survivorship once more, and it does so invisibly: `symbols` is silently reassigned and no caveat records the drop. The universe the user asked for and the universe that was estimated differ.

**Fix:** Drop this filter. Coverage belongs in the time-varying eligibility mask (a name is eligible on a date when it has a signal and a dependent value on that date), and `min_assets` already refuses a date with too few names. If a minimum-history requirement is wanted for a specific signal, implement it as a trailing `count` condition inside the mask so it varies by date.

---

## Q-10 Apply one documented bad-print screen to every return consumer

**Severity:** P1 · **Effort:** M · **Confidence:** CONFIRMED

> §4.1: "OHLC consistency is checked." / "Missing observations are distinguished from genuine zero values." / §20.1: "Correctness before optimization."

**Evidence:**
- `backend/app/services/research_v2/core/panel.py:133` — `returns = returns.where(returns.abs() < 3)  # drop split/bad-print artefacts (>300% in a month)`
- `backend/app/services/research_v2/core/signal_lang.py:130` — `dr = dr.where(dr.abs() < 1)` (daily screen, 100%, used for `rvol`, `maxret`; not used for `amihud_d`, whose `dr` is built at line 134 without a screen)
- `backend/app/services/research_v2/core/causal.py:460` — `rets = daily["Close"].pct_change(fill_method=None)` (no screen at all)
- `backend/app/services/research_v2/core/panel.py:389-390` — `if name == "realized_vol":` / `vol = daily["Close"].pct_change(fill_method=None).resample("ME").std() * math.sqrt(21)` (no screen at all)
- Probe of `market_universe.parquet`: 412 daily observations with `|r| > 100%`, 278 above 300%, 240 above 1,000%. Examples: `AZUL4_SA` 2025-12-23 `r = 4196.5`, `ATO_PA` 2024-11-11 `r = 85.3`, `CHRD` 2020-11-20 `r = 257.3`.

**Impact:** Four different out-of-range conventions coexist in one module: monthly 300% in the panel, daily 100% in two signals, none in `amihud_d`, none in event studies or in the `realized_vol` dependent variable. A single unadjusted capital event (reverse split, unit change, currency redenomination, bankruptcy emergence) therefore enters `realized_vol` as a huge standard deviation, enters an event-study AR as a four-digit percentage that dominates the cross-sectional average CAR, and enters `amihud` as a liquidity spike. The 240 daily observations above 1,000% are, on inspection, unadjusted corporate actions in the file rather than genuine moves.

**Fix:** Centralise return construction in one function that (a) applies a single symmetric screen with a documented threshold, (b) records the count and share of screened observations per ticker and month, and (c) is used by `panel.build_panel`, `signal_lang.load_field`, `causal._monthly_outcome`, `_characteristics` and the event study. Surfacing the screen count in `data_audit` is what makes the 240 observations auditable instead of invisible.

---

## Q-11 Preserve missing volume as missing, not zero

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Missing observations are distinguished from genuine zero values."

**Evidence:**
- `backend/app/services/research_v2/core/signal_lang.py:123-124` — `elif name == "volume":` / `v = _frame(ctx, "Volume", "sum")`
- `backend/app/services/research_v2/core/signal_lang.py:102-103` — `r = d.resample("ME")` / `out = getattr(r, how)()`
- `backend/app/services/research_v2/core/signal_lang.py:126` — `d = (ctx["daily"]["Close"] * ctx["daily"]["Volume"]).resample("ME").sum(min_count=1)` (the *dollar* volume path does pass `min_count=1`)

**Impact:** `resample().sum()` defaults to `min_count=0`, so a month with no volume rows produces `0.0` rather than NaN. `turnover` (`volume / shares`) and `volume_trend` (`ts_mean(volume,3)/ts_mean(volume,12)`) then treat a data hole as zero trading. The file has 342,951 zero-volume days and 1,304 null volumes, so holes are routine, and a zero in the denominator or numerator of a liquidity ratio is not a small error — it is a fabricated observation of "no trading". `dollar_volume`, built two lines below with `min_count=1`, does the right thing, which proves the intent.

**Fix:** Pass `min_count=1` on the volume resample (or use `.agg(lambda s: s.sum(min_count=1))`), and add a unit test asserting that a month with no volume rows yields NaN for `volume`, `turnover`, `volume_trend` and `dollar_volume` alike.

---

## Q-12 Drop or redefine the `open` field, which is the month's first open rather than the open at the formation date

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.2: "Signals and fills have separate timestamps." / "Higher-timeframe indicators use the last completed higher-timeframe bar."

**Evidence:**
- `backend/app/services/research_v2/core/signal_lang.py:76` — `"open": "First open of the month",`
- `backend/app/services/research_v2/core/signal_lang.py:117-118` — `elif name == "open":` / `v = _frame(ctx, "Open", "first")`

**Impact:** A panel row is dated at month end, and every other price field on that row is a month-end quantity (`close` is the last close, `high`/`low`/`volume`/`dollar_volume` are within-month aggregates). `open` alone is the *first* trading day's open — up to a month in the past relative to the row timestamp. A user writing `close / open - 1` gets a within-month return, A user writing `open` as "the price I would trade at" gets a price from before the information in the same row was available. The help text is honest, but the field sits in the same namespace as `close` with the same row semantics, and the expression language exposes it to users without any guard.

**Fix:** Either remove `open` from the formula namespace, or rename it to `open_month_start` so the aggregation is explicit, and add `next_open` (the first open strictly after the formation date) as the only field intended for execution modelling once Q-01 lands.

---

## Q-13 Fix asset classification: US stocks without sector rows are labelled ETFs

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Symbols use stable identifiers where available." / §20.2: "Evidence before claims."

**Evidence:**
- `backend/app/services/research_v2/universes.py:33-34` — `def classify(ticker: str, has_sector: bool) -> tuple[str, str, str]:` / `"""(country, region, asset_type) from the ticker string and sector coverage."""`
- `backend/app/services/research_v2/universes.py:49` — `return "US", "North America", "equity" if has_sector else "etf"`

**Impact:** `has_sector` comes from `static_sectors()` (`universes.py:78-79`), which is built from `master_fundamentals.parquet` — 3,833 tickers against 4,158 in the price file. Any US common stock absent from the fundamentals file is classified as an ETF. `asset_type=equity` filters then silently drop real equities, and `asset_type=etf` contaminates ETF samples with stocks. ETFs that happen to have a sector row are mislabelled the other way. Because this is ticker-string inference, the error is invisible in the output — there is no `classification_source` field.

**Fix:** Determine `asset_type` from an explicit instrument master (the same source that knows whether a symbol is a fund), not from the presence of a sector row. Where the master is unavailable, mark `asset_type` as `unknown` and exclude it from both equity and ETF universes rather than guessing; report the unknown share in the universe response.

---

## Q-14 Stop excluding every underscore ticker from the US universe

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Symbols use stable identifiers where available." / §4.2: "Universe construction methodology is recorded."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:175` — `return tuple(s for s in available_symbols() if "_" not in s and not s.startswith("^") and s in sectors.index)`
- Probe: `BRK_B` and `BF_B` are present in `market_universe.parquet`; 2,552 tickers contain `_`, of which 334 are `_NS`, 200 `_KS`, 171 `_AX`, … and at least two are US share classes.

**Impact:** The underscore is used as a proxy for "non-US listing", but it is also the share-class separator after `normalize_symbol` maps `.` to `_`. The default US universe therefore excludes Berkshire Hathaway class B — the seventh-largest US company by market cap — plus every other dual-class US listing. Size-sorted portfolios, the `large_cap` filter and any equal-weighted cross-section are systematically wrong at the top of the cap distribution, and the omitted names are exactly the ones a size or value study cares about.

**Fix:** Exclude non-US listings by consulting the suffix table (`SUFFIX_MARKETS`) rather than by the presence of `_`, so a suffix that is not a known exchange (e.g. `_B`) is treated as a US share class. Add an assertion in the universe tests that `BRK_B` is present in `us_equity_symbols()`.

---

## Q-15 Validate OHLC before it reaches any calculation

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Required columns and data types are validated." / "Duplicate keys are detected." / "OHLC consistency is checked." / "Negative prices and volumes are rejected unless the instrument permits them."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:77` — `clean = out.dropna(subset=["Ticker", "Date", "Close"])[["Ticker", "Date", "Open", "High", "Low", "Close", "Volume"]].sort_values(["Ticker", "Date"])`
- `backend/app/services/research_v2/core/data_loader.py:473` — `return {col: df.pivot_table(index="Date", columns="Ticker", values=col, aggfunc="last", observed=True).sort_index() for col in [...]}`
- Probe of `market_universe.parquet`: 225 rows with `Close <= 0`; 6 rows with `High < Low`; 1,304 null `Volume`; 342,951 zero `Volume`; 0 duplicate `(Ticker, Date)` keys.

**Impact:** The loader drops null closes and nothing else. Negative or zero closes survive into `pct_change` (producing returns far outside any screen, or `inf` that is replaced later at the panel level but not at the daily level), into `np.log(close)` for `price_level` and `dollar_volume` (NaN that silently removes the asset), and into `shares * close` for market cap. `High < Low` breaks the Corwin-Schultz estimator (`panel.py:401-406`) with a negative variance argument inside a square root. `pivot_table(aggfunc="last")` would hide duplicate keys rather than fail; the file is currently clean, but nothing enforces that, so a future refresh can silently keep an arbitrary row.

**Fix:** Add an explicit validation stage in `_standardize_ohlcv` that fails (or quarantines with a counter) on non-positive prices, `High < Low`, `High`/`Low` outside `[Low, High]` relative to `Open`/`Close`, and duplicate `(Ticker, Date)`; write the counts to `data_audit`. Replace `pivot_table` with a `unstack` that raises on duplicates, or `drop_duplicates` with an explicit, logged policy.

---

## Q-16 Record the real adjustment convention; prices are split-adjusted but not dividend-adjusted, and the audit says otherwise

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Adjustment conventions are consistent within each return calculation." / "Mixed adjusted/raw data cannot silently enter a total-return calculation." / §4.2: "Adjustment methodology is recorded."

**Evidence:**
- `backend/app/services/research_v2/audit.py:58` — `adjustments = ["Monthly returns above 300% in absolute value are treated as bad prints and dropped.", "Prices are the adjusted closes in the local market file; no intraday data is used."]`
- `backend/app/services/research_v2/core/data_loader.py:67-68` — `if "Close" not in out.columns and "Adj Close" in out.columns:` / `out["Close"] = out["Adj Close"]`
- Probe: `market_universe.parquet` has columns `Ticker, Date, Open, High, Low, Close, Volume` — **no `Adj Close` column**, so the fallback at line 67 is unreachable for this dataset. `TSLA` 2022-08-24 = 297.10 against a raw close of 891.29 (3:1 split applied); `NVDA` 2024-06-07 = 120.83 (10:1 split applied). `NLY` on 2024-03-26/27 prints 19.73 → 19.44 across a ~3.3% ex-dividend date, i.e. the dividend drop is *not* removed.

**Impact:** Returns are price returns with corporate-action adjustment for splits and spin-offs but no dividend reinvestment. For a high-yield name the annual understatement is 3–8%; across a cross-section, value and dividend-yield strategies lose their entire cash-flow component, and any comparison to a published total-return premium (Ken French factors are total-return, and they are used as the benchmark in `sort_table`) is biased by the dividend spread between the legs. The audit text tells the user the opposite, and `div_yield` (`signal_library.py:45`) computes a yield that the return series never pays out.

**Fix:** Record the convention explicitly — `{"price_field": "Close", "split_adjusted": true, "dividend_adjusted": false, "source": "..."}` — and correct the `data_audit` sentence. Then either (a) add dividends as a separate monthly total and sum them into returns, or (b) subtract the dividend yield of each leg in the long-short spread. Add a test that a known ex-dividend date produces a return equal to the price return minus the dividend yield when adjustment is applied.

---

## Q-17 Do not drop loss-making firms from growth measures

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.1: "Every feature has an explicit observation timestamp." / §20.2: "Evidence before claims."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:438` — `def annual_growth(field: str, dates: pd.DatetimeIndex, symbols: Iterable[str], lag_days: int = 90) -> pd.DataFrame:`
- `backend/app/services/research_v2/core/data_loader.py:451-452` — `sub["growth"] = sub["value"] / prev.where(prev > 0) - 1` … `sub["available"] = sub["reportDate"] + pd.Timedelta(days=int(lag_days))`

**Impact:** `prev.where(prev > 0)` turns any non-positive base into NaN, so `asset_growth` and every other growth control is undefined exactly for firms recovering from losses — the highest-expected-growth firms in the sample. The surviving growth observations are conditioned on a positive prior, which biases the cross-sectional distribution and its mean downward. The same function also computes the growth between consecutive available annual reports without checking that they are one year apart, so a firm with a missing fiscal year receives a two-year growth rate labelled as twelve months.

**Fix:** Use a difference instead of a ratio where the base can be non-positive (`(value - prev) / assets`, the standard Cooper-Gulen-Schill asset-growth definition already uses assets as the scaler), or keep the ratio but require `prev > 0` *and* record the excluded share per date so the selection is visible. Verify the spacing (`(reportDate - prev_reportDate).days` within 300–430 days) and set the growth to NaN when it fails, with the reason counted.

---

## Q-18 Make fundamentals coverage explicit and stop mixing annual flows with quarterly stocks in one ratio

**Severity:** P1 · **Effort:** M · **Confidence:** CONFIRMED

> §2.1: "Data availability is distinguished from data observation." / "Missing historical availability metadata produces a limitation or refusal." / §4.2: "Coverage dates are recorded."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:408-435` (`point_in_time_fundamental`: annual-only for `FLOW_FIELDS`, any period type for stock fields, `max_age_days=550`)
- `backend/app/services/research_v2/core/data_loader.py:460-464` — `def fundamentals_coverage_start() -> pd.Timestamp | None:` … `return pd.Timestamp(df["reportDate"].min()) + pd.Timedelta(days=90)`
- `backend/app/services/research_v2/core/signal_library.py:48` — `("gp_a", "Gross profitability", "profitability", "gross_profit / assets", "Novy-Marx (2013)", 2013, 1)`
- Probe of `master_fundamentals.parquet`: `reportDate` min 2021-01-31 for `annual` and 2024-04-30 for `quarterly`; 20,599 quarterly rows, 16,524 annual rows, 3,833 tickers.

**Impact:** Three separate problems in one place. (1) Coverage: the fundamental panel starts 2021-05 (annual) and the *quarterly* balance-sheet data only exists from 2024-07, so a 1996–2026 study is six years shorter than it appears and market cap jumps discontinuously when quarterly share counts begin in 2024. (2) Period mixing: `gross_profit` is an annual flow (12 months to an old `reportDate`) divided by `assets`, a stock taken from the latest report of any type — so the numerator and denominator refer to different economic dates, and the mismatch changes at the 2024 boundary. (3) `drop_duplicates(["ticker", "available"], keep="last")` after sorting only by `reportDate` leaves ties (annual and quarterly rows often share a `reportDate`, hence the same `available`) resolved by incidental input order.

**Fix:** Separate the two concepts: a `FundamentalSeries` that returns `(value, period_end, available)` per `(ticker, date)`, so ratios can require matching period ends (or the nearest prior stock observation, with the mismatch recorded). Use quarterly flows where available and annual otherwise, with an explicit `flow_window_months` field. Break `available` ties deterministically by preferring the shorter reporting period, then by ingestion order. Report `fundamentals_coverage_start()` per field, not globally, and expose the coverage start in every fundamental result.

---

## Q-19 Select walk-forward parameters inside each fold and report a stitched out-of-sample path

**Severity:** P1 · **Effort:** L · **Confidence:** CONFIRMED

> §5.2: "Each evaluation window uses the parameters selected before that window." / "Stitched out-of-sample returns preserve chronological order." / "Performance is calculated from the actual stitched equity path." / "Window boundaries do not duplicate observations."

**Evidence:**
- `backend/app/services/research_v2/reports.py:367` — `chunks = np.array_split(np.arange(len(ls)), folds + 1 if method == "walk_forward" else folds)`
- `backend/app/services/research_v2/reports.py:379-382` — `for i in range(1, len(chunks)):` … `out_folds.append({"fold": i, "train": _span(train), "test": _span(test), "is_sharpe": _sharpe(train, per_year), "oos_sharpe": _sharpe(test, per_year)})`
- `backend/app/services/research_v2/reports.py:396-398` — `is_v = [...]`, `oos_v = [...]`, `degradation: (1 - mean(oos)/mean(is))`

**Impact:** There is no parameter search anywhere in the function: `is_sharpe` is the Sharpe of the same fixed specification on the training chunk and `oos_sharpe` the same specification on the test chunk. That is a stability diagnostic, not walk-forward, and `degradation` is presented as walk-forward efficiency. Three failures follow: no stitched out-of-sample series exists, so `mean_oos_sharpe` is an average of per-fold Sharpes rather than the Sharpe of the actual OOS path (a good fold can offset a bad one); the folds are contiguous chunks of formation dates with no purge *within* the test block, so consecutive test folds share overlapping `h`-month holding windows (`purge` only removes training rows); and `ls` is the long-short series of `h`-month forward returns indexed monthly, so with `holding_months > rebalancing step` the test blocks overlap each other regardless of purging.

**Fix:** Either implement real walk-forward — an explicit parameter grid, selection on each training window, evaluation on the following window, and a concatenated OOS return series whose Sharpe is computed once from the stitched path — or rename the output to "stability split" and remove the walk-forward label and the `degradation` metric. In both cases, purge training *and* embargo by `h + embargo` on both sides of each test block, and assert that the union of test indices has no duplicates.

---

## Q-20 Compute PBO on distinct candidates, not mirror-image quintile spreads

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.4: "PBO is computed only when its sampling and candidate requirements are satisfied." / "CSCV partitions preserve the documented methodology."

**Evidence:**
- `backend/app/services/research_v2/reports.py:392-394` — `for a, b in itertools.permutations(q, 2):` / `strategies[f"{a}-{b}"] = port[a] - port[b]` / `pbo = pbo_cscv(pd.DataFrame(strategies))`

**Impact:** `permutations` over five quintiles produces twenty series in ten exactly-antipodal pairs: `Q1-Q2` is the exact negative of `Q2-Q1`. In CSCV, a strategy that ranks best in-sample on a split has its mirror ranking worst on that same split and best on the complement, so the rank distribution of the in-sample winner is symmetric by construction and the PBO converges toward 0.5 for any data. The number is reported as "CSCV over all ordered quintile spreads" (`reports.py:398`), which reads as a validation of the signal but is an artefact of the candidate set.

**Fix:** Build the candidate set from genuinely distinct specifications — the Feature 2 specification curve, a parameter grid, or the set of signals being compared — and pass exactly those return series to `shared_cscv_pbo`. At minimum, restrict to `itertools.combinations` so no candidate is another's negative, and add an assertion that no two candidate return series are proportional with a negative scalar.

---

## Q-21 Include failed and excluded trials in the multiple-testing correction

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.4: "Parameter sweeps record attempted, completed, failed and excluded candidates." / "Statistical corrections are not presented as guarantees of future profitability." / §5.5: "Missing tests cannot silently count as passes."

**Evidence:**
- `backend/app/services/research_v2/reports.py:315-316` — `except Exception as exc:  # noqa: BLE001` / `rows.append({"signal": s, "error": str(exc)})`
- `backend/app/services/research_v2/reports.py:317-321` — `ok = [r for r in rows if "error" not in r]` / `for r, a in zip(ok, bhy_adjust([r["p"] for r in ok])):` … `r["survives"] = bool(a < 0.05)`

**Impact:** Benjamini-Hochberg-Yekutieli is applied to `ok` only. A signal that fails to build is dropped from the family, which shrinks the effective trial count and loosens the correction for the survivors. Since failures are often systematic — a signal needs fundamentals, or has too few assets in a narrow universe — the dropped trials are not missing at random. `trials: len(signals)` is reported alongside the smaller corrected family, so the response states one number and uses another.

**Fix:** Charge the full requested family size to the correction: apply `bhy_adjust` to `len(signals)` with `p = 1.0` for every failed or excluded candidate, and report `trials_requested`, `trials_evaluated`, `trials_failed` separately. Keep the error rows in the output with `survives: false` rather than omitting them from the family.

---

## Q-22 Report filtered probabilities (or label the smoothed ones as retrospective)

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.1: "Rolling indicators do not use future observations." / §2.3: "Regime definitions do not depend on future observations." / §9.4: "Incorrect or misleading visualizations."

**Evidence:**
- `backend/app/services/research_v2/core/regime.py:262` — `probs = pd.DataFrame({"date": y.index, "state_high_premium_probability": fit.smoothed_marginal_probabilities[high].to_numpy()})`

**Impact:** `smoothed_marginal_probabilities` conditions on the entire sample, so the probability shown for January 2008 incorporates everything known up to the end of the sample. In a time-series chart of "regime probability" this looks like a regime detector and reads as though the state were identifiable in real time; it is not. Any user who reads the chart as a conditioning variable for a tradeable rule is reading a quantity that could not have been computed at that date. The label does not disclose the conditioning set.

**Fix:** Plot `fit.filtered_marginal_probabilities` for the point-in-time series (optionally with the smoothed series as a dashed overlay) and rename the column to `filtered_state_high_probability`. Add `"conditioning": "filtered"` to the summary payload and a note that smoothed probabilities are retrospective.

---

## Q-23 Select regime thresholds out of sample and correct the conditional premium tests

**Severity:** P1 · **Effort:** M · **Confidence:** CONFIRMED

> §2.3: "Model selection and final evaluation are separated." / "Every reported out-of-sample result is genuinely out-of-sample relative to selection." / §2.4: "Multiple comparisons are accounted for where applicable."

**Evidence:**
- `backend/app/services/research_v2/core/regime.py:200-207` — `for q in np.linspace(0.15, 0.85, 15):` … `rows.append({"quantile": q, "threshold": thr, "f_stat": res["f_stat"], "p_value_pointwise": res["p_value"], "months_on": int(on.sum())})`
- `backend/app/services/research_v2/core/regime.py:211-216` — `best = table.loc[table["f_stat"].idxmax()]` … `table["sup_f_p_value"] = float(np.mean(null >= best["f_stat"]))` … `return table, float(best["threshold"])`

**Impact:** The `sup_f_p_value` correctly accounts for the grid search over the split point, which is the right correction and is worth keeping. But the chosen threshold is then used to compute the "regime-conditional premia" and the "premium difference" on the *same* sample (`premium_difference`, line 181-189). Those reported premia are selected-in-sample: the split was chosen precisely because it maximised the difference, so the t-stat on `regime_on` is not a test of a pre-specified regime. The table itself labels only the *split* p-value as corrected, not the downstream premium.

**Fix:** Split the sample: choose the threshold on the first 70% (or expanding windows) and compute the conditional premia only on the held-out remainder, or report the sup-F adjusted p-value as the *only* inference attached to a data-driven split and mark the conditional premia as descriptive. Add `"threshold_selection": "in-sample"` to the output when `threshold_mode == "data_driven"` so the label travels with the number.

---

## Q-24 Align DiD treatment to the event date, not to the calendar month containing it

**Severity:** P1 · **Effort:** M · **Confidence:** CONFIRMED

> §2.2: "Signals and fills have separate timestamps." / "Same-close execution is permitted only when the information and order-submission chronology support it."

**Evidence:**
- `backend/app/services/research_v2/core/causal.py:158` — `pos = months.searchsorted(pd.Timestamp(d) + pd.offsets.MonthEnd(0))`
- `backend/app/services/research_v2/core/causal.py:160` — `cohort[tk] = pos + 1 - anticipation`
- `backend/app/services/research_v2/core/causal.py:180` — `long["treat"] = ((long["g"] > 0) & (long["time"] >= long["g"])).astype(int)`

**Impact:** The treatment indicator turns on at the *start* of the month containing the event, because `searchsorted` snaps the event date forward to that month's end and the cohort is then expressed as a month position. An event on the 28th of a month marks the whole month — including 27 pre-event days — as treated. The outcome for that month (`_monthly_outcome`: month-end close over prior month-end close) therefore mixes pre- and post-event returns into the first treated period, which attenuates or reverses the estimated effect depending on when in the month the event fell, and contaminates the event-study lead that is used to test parallel trends.

**Fix:** Model treatment at the day level where the data allow, or snap the event to the first month boundary strictly after the event date (`pd.Timestamp(d).to_period("M") + 1`) so that the first treated month contains no pre-event days, and add an `event_timing_within_month` field to the output. Where partial-month exposure cannot be avoided, weight the first treated observation by the post-event share of the month.

---

## Q-25 Keep events that lack a complete post-event window, or disclose the resulting survivorship

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.1: "Missing historical availability metadata produces a limitation or refusal." / §4.2: "Missing delisted securities are disclosed."

**Evidence:**
- `backend/app/services/research_v2/core/causal.py:479` — `if est_start < 0 or day0 + hi >= len(r):`
- `backend/app/services/research_v2/core/causal.py:480` — `continue`
- `backend/app/services/research_v2/core/causal.py:473` — `r = rets[ev["ticker"]].dropna()`

**Impact:** An event is silently dropped when the security has fewer than `hi` trading days *after* the event. In an event study of bankruptcies, mergers, regulatory actions or de-listings — the natural subjects — the firms that stop trading shortly after the event are exactly the ones excluded, leaving the events with the mildest outcomes. Combined with Q-04 (the price file has almost no dead tickers), the surviving event set is biased toward firms that kept trading for at least `hi` days. The output reports `n_events` without `n_events_dropped_for_short_window`, so the user cannot see it.

**Fix:** Report excluded events with the reason and the count per reason. For events whose security stops trading, use the delisting return and treat the remaining window as NaN (and exclude from CAR aggregation with an explicit weight), rather than dropping the event. Alternatively, keep the event with a truncated window and mark `window_complete: false`.

---

## Q-26 Estimate RD on a proper cross-section with time-clustered inference

**Severity:** P1 · **Effort:** M · **Confidence:** CONFIRMED

> §2.5: "Confidence intervals use a method appropriate to the dependence structure." / §2.1: "Cross-sectional normalization uses only the eligible universe at that timestamp."

**Evidence:**
- `backend/app/services/research_v2/core/causal.py:613-614` — `panel = build_panel({**payload, "signal": "momentum", "controls": covariates, "min_assets": 20})` / `stacked = panel.stacked(covariates)`
- `backend/app/services/research_v2/core/causal.py:622` — `df = stacked.join(x, how="inner").dropna(subset=["x", "y"])`
- `backend/app/services/research_v2/core/causal.py:624` — `df["cluster"] = pd.factorize(df["ticker"])[0]`

**Impact:** The design is cross-sectional RD on a market-cap cutoff, but the data are a pooled panel of `(date, ticker)` observations with the *same firm appearing on both sides of the cutoff across time*. `rdrobust` is then run on that pool with clustering by ticker only. Because the dependent variable is an `h`-month forward return sampled monthly, observations overlap by `(h-1)` months within a firm and are also cross-sectionally correlated within each month; ticker clustering handles the first but not the second, so the reported robust standard errors are too small. The running variable (`market_cap`) is also mechanically related to the dependent variable through the return itself when `y` is measured from `t` (`mcap` at `t` already embeds past returns), and the pooled estimand is not the cross-sectional cutoff effect the design claims.

**Fix:** Use a single cross-section (the formation date at which the treatment rule applies) so the RD is estimated once, or use a panel RD estimator that includes date fixed effects and two-way (ticker × date) clustering with a bandwidth that respects the panel structure. Add a joint density test on the single cross-section, and state in the output which cross-section(s) were pooled.

---

## Q-27 Replace the default lagged-signal instrument with one that satisfies exclusion

**Severity:** P1 · **Effort:** M · **Confidence:** SUSPECTED

> §2.5: "P-values and confidence intervals are not interpreted as probabilities that a strategy is profitable." / §20.2: "Evidence before claims."

**Evidence:**
- `backend/app/services/research_v2/core/causal.py:748` — `instrument_kind = str(payload.get("instrument") or "lag_3").lower()`
- `backend/app/services/research_v2/core/causal.py:763-767` — `for name in endog_names:` … `if instrument_kind.startswith("lag_"):` … `instruments[f"z_{name}_lag{lag}"] = full.shift(lag).reindex(panel.dates)`
- `backend/app/services/research_v2/core/causal.py:768-777` — the `industry_mean` branch builds a leave-one-out industry mean of the same signal.

**Impact:** The endogenous regressor is a constructed characteristic (e.g. momentum) and the default instrument is that same characteristic three months earlier. Persistence makes the instrument relevant, but the exclusion restriction requires past momentum to affect future returns *only* through current momentum — which is false by construction, since momentum is the anomaly: past returns predict returns directly. The `industry_mean` instrument has the same problem through industry momentum. The output is presented as an IV estimate of a causal effect, so the untested exclusion restriction is the load-bearing assumption of a headline number. Marked SUSPECTED only because whether the output is *labelled* causal was not verified end to end in the UI.

**Fix:** Default to `uploaded` and refuse `lag_*` / `industry_mean` unless the user supplies an explicit exclusion rationale; when a lagged instrument is used, report the first-stage F, the over-identification test where available, and a plain label that the estimate is "instrumented by a lagged copy of the signal" rather than a causal effect.

---

## Q-28 Hash every input that changes the specification

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §5.4: "Hold-out membership is established before tuning." / §2.3: "Post-hoc changes to strategy logic invalidate earlier independent validation claims." / §5.5: "A certificate hash changes when materially relevant inputs change."

**Evidence:**
- `backend/app/services/research_v2/core/holdout.py:97` — `keys = ["dependent_variable", "signal", "controls", "estimator", "se", "fixed_effects", "weighting", "start", "end", "holding_months", "universe"]`
- `backend/app/services/research_v2/core/holdout.py:24-26` — `def study_key(config, universe): ... return f"{config['signal']}|{label.lower()}|{config['dependent_variable']}|h{config['holding_months']}"`

**Impact:** `spec_hash` omits `universe_filters`, `signal_transform`, `lookback_days`, `rebalancing_frequency`, `min_assets` and `orthogonalize_against`, yet all of them change the tested hypothesis. Two studies that differ only by excluding financials, or by running the signal through a decile transform, hash identically and both receive the "confirmatory" tag even if only one was locked before estimation — which is the exact failure §5.4 exists to prevent. Separately, `study_key` omits `weighting`, `controls` and `universe_filters`, so a protected window reserved for a value-weighted, controlled study also excludes data for an equal-weighted, uncontrolled study, and vice versa; the reservation is applied to a different hypothesis than the one registered.

**Fix:** Build both keys from the full normalised config dict (`normalize_config` output) with `sort_keys=True`, excluding only fields that cannot affect results (labels, display options). Version the scheme (`spec_hash_v2`) so previously locked hashes are not silently reinterpreted, and include `universe_filters`, `signal_transform`, `lookback_days`, `rebalancing_frequency` and `execution_price` (from Q-01).

---

## Q-29 Compound only non-overlapping returns in the cumulative equity chart

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §2.5: "Annualization reflects the sampling frequency and return convention." / §20.2: "Evidence before claims."

**Evidence:**
- `backend/app/services/research_v2/core/canonical.py:111` — `"cumulative_long_short": (1 + ls.fillna(0)).cumprod().rename("growth_of_1").reset_index() if len(ls) else []`
- `backend/app/services/research_v2/core/estimators.py:113` — `pr = vectorized_portfolio_returns(panel.signal if signal is None else signal, panel.dependent, panel.weights, int(buckets))` (the dependent is `h`-month forward return)
- `backend/app/services/research_v2/core/estimators.py:138` — `"sharpe_annual": float(excess.mean() / vol * np.sqrt(12 / h)) if vol else np.nan,`

**Impact:** `ls` is a series of `h`-month cumulative returns, one per formation date. When `holding_months > rebalancing step` (both are independently configurable — `panel.py:142-143`), consecutive rows overlap by `(h-1)` months, and `cumprod` compounds them as if each were a one-month return. The displayed growth of \$1 is then inflated roughly `h`-fold in the mean and its drawdowns are understated, which is exactly the chart a user reads first. Separately, `mean_return` and `std` are `h`-month quantities with no period label, and `rf.reindex(...).fillna(0)` in the same function treats a missing risk-free rate as zero, overstating excess returns.

**Fix:** Either construct a non-overlapping monthly return series (allocate `1/h` of the portfolio to each of the `h` overlapping cohorts and sum) for the cumulative chart, or refuse to draw a cumulative chart when `holding_months > step`. Label the table columns with their period (`mean_return_12m`), and do not silently zero-fill `rf` — require it or report excess returns as unavailable.

---

## Q-30 Use the same estimator for the main fit and its placebos

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §5.3: "Every test evaluates the actual user strategy." / "Every skipped test reports its reason."

**Evidence:**
- `backend/app/services/research_v2/core/synthetic.py:94` — `fit = _fit_variant(variant, y, treated, donors, pre_mask, payload)`
- `backend/app/services/research_v2/core/synthetic.py:244` — `gap = y[d] - _fast_fit(y, d, others, pre_mask)`
- `backend/app/services/research_v2/core/synthetic.py:202` — `cf = pd.Series(np.asarray(model._synthetic(z0)).ravel(), index=y.index) if hasattr(model, "_synthetic") else synth`

**Impact:** The reported effect uses the user's chosen variant (classic, augmented, robust, generalized), while every in-space placebo uses `_fast_fit`, i.e. classic simplex SCM. The p-value is therefore the rank of the chosen estimator's effect against a null distribution from a *different* estimator, which is invalid when the variants disagree — and the augmented/robust variants are precisely the ones chosen when classic SCM fits poorly. Line 202 compounds this: if the fitted model does not expose `_synthetic`, the variant silently falls back to the classic `synth` path while `details["method"]` still names the augmented or robust estimator.

**Fix:** Fit the same variant in the placebo loop (pass `variant` through to `_fit_variant`) so both distributions come from one estimator, and raise rather than fall back when `_synthetic` is missing. Record the variant actually used in the output next to the p-value.

---

## Q-31 Select replication markets deterministically by liquidity or size, not by suffix sort order

**Severity:** P1 · **Effort:** S · **Confidence:** CONFIRMED

> §4.2: "Universe construction methodology is recorded." / §5.3: "Every test evaluates the actual user strategy."

**Evidence:**
- `backend/app/services/research_v2/core/decay.py:267` — `tickers = [s for s in universe if "_" in s and s.rsplit("_", 1)[1] in suffixes][:300]`
- `backend/app/services/research_v2/core/decay.py:272` — `p = build_panel({**payload, "universe": tickers, "max_symbols": 300, "controls": "none", "weighting": "equal", "universe_filters": [], "min_assets": 20})`

**Impact:** `available_symbols()` order is the order the tickers appear in the source file, so `[:300]` is an arbitrary, file-order-dependent cut — not a sample, not a liquidity screen, and not reproducible if the file is regenerated with different row order. It also drops `universe_filters` entirely (`[]`), so the international replication does not test the user's specification (a minus-financials value test becomes an all-names test abroad), while the domestic US run does. The resulting "x of y markets still significant" headline mixes two different strategies.

**Fix:** Select the replication sample by an explicit rule (largest 300 by trailing dollar volume, or a seeded random sample with the seed recorded) and keep the user's `universe_filters`, `weighting` and `controls` unless the output states that the international test deliberately relaxes them. Record the selection rule and the resulting ticker count in the row.

---

## Q-32 Remove the import-time mutation of the fundamental field registry

**Severity:** P2 · **Effort:** S · **Confidence:** CONFIRMED

> §20.6: "One canonical implementation per financial concept." / §8.1: "Architecture."

**Evidence:**
- `backend/app/services/research_v2/core/signal_lang.py:31-32` — `# Flow items below mix quarterly and annual rows; keep annual only (shared helper reads this set).` / `dl.FLOW_FIELDS.update({"Operating Cash Flow", "Free Cash Flow", ...})`

**Impact:** Importing `signal_lang` permanently widens `data_loader.FLOW_FIELDS` for the whole process. Any caller that imports `data_loader` without `signal_lang` — including `causal._characteristics`, `synthetic._same_size_decile` and the screener — gets the un-widened set, so the *same* field name means "annual only" or "any period" depending on import order. That silently changes which accounting period backs `cash_profit`, `accruals` and `cfp` in different code paths.

**Fix:** Declare the complete `FLOW_FIELDS` set once in `data_loader` (the owner of the concept) and delete the mutation. If `signal_lang` needs a stricter subset, define a separate named constant locally.

---

## Q-33 Do not downcast prices to float32 in the shared loader

**Severity:** P2 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Required columns and data types are validated." / §12: "Reproducibility and deterministic computation."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:49` — `lf = lf.with_columns(pl.col(pl.Utf8).cast(pl.Categorical), pl.col(pl.Float64).cast(pl.Float32))`
- `backend/app/services/research_v2/core/data_loader.py:73` — `out[col] = pd.to_numeric(out[col], errors="coerce", downcast="float").astype("float32")`

**Impact:** Float32 carries ~7 significant decimal digits, which is adequate for a single price but not for cumulative products and ratio-of-sums constructions. `dollar_volume` sums `close * volume` over a month (products up to `1e10`), `amihud_d` divides tiny returns by large dollar volumes, and market cap multiplies a float32 price by a float64 share count — each step inherits the input quantisation, and the result is not bit-reproducible against a float64 recomputation. The stated justification (memory) is real, but it is applied at the shared boundary where every downstream consumer pays for it.

**Fix:** Keep float32 only in the cached, column-pruned scan used for the interactive previews; load float64 for any panel, factor or return construction. If the memory peak in `load_market_ohlcv` is the actual constraint, reduce it with `columns=` and chunking instead of precision.

---

## Q-34 Restore the unreachable missing-ticker check in `run_did`

**Severity:** P2 · **Effort:** S · **Confidence:** CONFIRMED

> §20.8: "Insufficient evidence produces a limitation, not a fabricated conclusion." / §8.2: "Python quality."

**Evidence:**
- `backend/app/services/research_v2/core/causal.py:143` — `missing = [t for t in treated if t not in set(parse_symbols({"universe": ",".join(treated)}))]`
- `backend/app/services/research_v2/core/data_loader.py:202-203` — `if missing:` / `raise UnknownSymbolsError(missing)`

**Impact:** `parse_symbols` raises `UnknownSymbolsError` on any unknown ticker, so the comprehension at line 143 can only execute when every treated ticker already exists — `missing` is always empty and the branch at 144-145 is dead. The consequence is not a wrong number but a misleading error path: a user who mistypes one treated ticker receives the generic "unknown symbols" message referencing the joined universe rather than the `treated` list, and the dedicated check never runs. (The same pattern appears at `causal.py:456` in `run_event_study`.)

**Fix:** Validate the treated list directly against `available_symbols()` (or catch `UnknownSymbolsError` and re-raise with the treated-ticker context), and delete the redundant call.

---

## Q-35 Parameterize the donor-matching lookback and screen donors before the size match

**Severity:** P2 · **Effort:** S · **Confidence:** CONFIRMED

> §20.9: "Every feature must justify its complexity." / §4.2: "Universe construction methodology is recorded."

**Evidence:**
- `backend/app/services/research_v2/core/synthetic.py:347-349` — `shares = point_in_time_fundamental("Ordinary Shares Number", at, [treated, *donors])` / `close = ohlcv_matrices([treated, *donors], 800)["Close"].resample("ME").last().reindex(at)` / `mcap = (shares * close).iloc[0].dropna()`

**Impact:** The 800-day window is hard-coded and unrelated to `payload["lookback_days"]` (default 3650), so the same-size donor pool is silently built from a different sample than the one the SCM is fitted on; a donor with no price in the last 800 days is dropped from `mcap` and therefore from the decile, without a record. `_donor_pool` has already applied its own coverage screen, so the two filters interact invisibly.

**Fix:** Derive the window from `payload["lookback_days"]` (or an explicit `donor_lookback_days`), and report how many donors were dropped at each stage (`_donor_pool`, size-decile join, final `donor_limit`).

---

## Q-36 Replace the IC-ratio "survival fraction" with a bounded, signed metric

**Severity:** P2 · **Effort:** S · **Confidence:** CONFIRMED

> §2.5: "No metric is reported with precision unsupported by its data." / "Nonstationarity and regime instability are disclosed."

**Evidence:**
- `backend/app/services/research_v2/core/decay.py:282` — `"survival_fraction": float(post.mean() / pre.mean()) if pre.mean() else np.nan, "vitality_score": float(ic.iloc[-12:].mean() / pre.mean() * 100) if pre.mean() else np.nan`
- `backend/app/services/research_v2/core/decay.py:286` — `f"{int(ok['still_significant'].sum())} of {len(ok)} markets still significant post-discovery"`

**Impact:** Both metrics divide by the sample pre-discovery mean IC, which for a weak anomaly is close to zero and can be negative. The ratio is then unbounded and sign-unstable: a pre-mean of 0.004 and a post-mean of −0.002 yields "survival −50%", and a pre-mean of 0.0005 with the same post-mean yields −400%. The `still_significant` flag uses a one-sided `t > 2` test while the domestic path uses two-sided tests, so the cross-market consistency count is not comparable to the rest of the report.

**Fix:** Report `pre_ic`, `post_ic` and their difference with a standard error, plus a bounded normalised measure such as `(post - pre) / |pre|` clipped and labelled as unstable below a stated minimum `|pre|`. Use the same two-sided test as the domestic path.

---

## Q-37 Replace the forward-filled price matrix with an explicit as-of join

**Severity:** P2 · **Effort:** S · **Confidence:** CONFIRMED

> §4.1: "Missing observations are distinguished from genuine zero values." / §4.3: "Non-trading days are handled correctly."

**Evidence:**
- `backend/app/services/research_v2/core/data_loader.py:243-244` — `mat = df.groupby(["Date", "Ticker"], observed=True)["Close"].last().unstack().sort_index().ffill()` / `return mat.dropna(axis=1, thresh=max(20, int(len(mat) * 0.45))).tail(max(30, int(lookback_days)))`
- `backend/app/services/research_v2/core/data_loader.py:260` — `prices = close_matrix(symbols, lookback_days=lookback_days, frequency=frequency)` (feeding `returns_matrix`)
- `backend/app/services/research_v2/core/data_loader.py:259` — `return np.log(prices).diff()...`

**Impact:** `ffill()` propagates the last trade across suspensions, holidays and delistings, so a halted stock contributes a run of zero returns in `returns_matrix` and a stale price in the screener. The column filter `thresh=45% of the whole matrix` is again a full-sample coverage decision. This path is used by `screener_v2` and previews rather than by the research panel, which is why it is graded P2, but it is the same defect class as Q-09/Q-07 and it will produce "flat" signals for illiquid names.

**Fix:** Drop the `ffill` for price series used to compute returns and let missing days stay missing (`returns_matrix` already replaces `inf`); if a last-known price is genuinely required for marking, use an explicit `as_of` join with a documented staleness cap and carry a `stale_days` column.

---

## N/A clauses

| Clause | Reason |
|---|---|
| §2.2 "Market holidays and missing sessions do not create fictional execution opportunities" | Partly N/A: there is no execution engine in this module; the related failure (same-close fill) is Q-01, and the missing-session failure surfaces as the month-end `.last()` re-dating in Q-04/Q-15. |
| §3.1–§3.4 (execution contract, fills, accounting invariants, engine parity) | N/A: the research module produces bucket and spread returns from a forward-return matrix; it holds no positions, cash or ledger. |
| §2.4 "Purging and embargo account for overlapping information intervals" | Partly N/A: the panel's dependent is a forward return by construction, so there is no train/test label leak within a single cross-section; the overlapping-horizon failure is Q-19. |
| §5.4 "Access controls… authenticated… atomic budgets" | N/A to the research computation paths audited here; `holdout.py` stores protected windows but enforcement is a separate store/API audit. |
| §4.3 "Paper-trading timestamps", "Alerts do not silently fire from stale observations" | N/A: no paper-trading or alerting path inside `research_v2`. |
| §6.1–§6.3 (strategy compilation) | N/A: the formula language is audited under its own scope (`shared/formula`); this audit covers only how its outputs are wired into the panel. |
