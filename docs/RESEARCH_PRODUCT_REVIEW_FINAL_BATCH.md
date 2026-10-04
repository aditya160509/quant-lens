# Research product review: final batch (2026-10-03)

This is a hard review of the Research module and the workspace around it, and the plan for the last build batch. It has four parts: the verdict, what to add (backend and external first, then frontend), what to remove, and UI work.

Inputs for the review:
- every screen built in this session, and the feature registry (10 features, around 220 outputs)
- the screenshots from TradingView, Koyfin, Portfolio Visualizer, TradeStation and QuantConnect
- FRONTEND.md section 10
- what researchers say they need, from r/quant and r/algotrading threads (alpha research at big firms, factor model testing, building a research app, overfitting and walk-forward) and from the Chen–Zimmermann Open Source Asset Pricing project

Each item is tagged **[B]** for backend or external (hand these to the backend agent), **[F]** for frontend, or **[B+F]** for both.

---

## 0. Verdict: is the module worth it?

**Yes, but only as a validation lab for signals, not as another backtester.** The market already has plenty of backtesters: TradingView, QuantConnect, Composer, Portfolio123, vectorbt. What nobody sells is the step researchers say decides the outcome:

> A senior QR on r/quant: alpha discovery "is NOT done via backtesting… [it] comes from model building… validated statistically and systematically."
> On fundamentals: "the data handling decides the result more than the formula does" (point-in-time, survivorship).
> On r/algotrading the recurring pain is overfitting: "deflated Sharpe", "walk forward", backtests that "flat-line or invert forward".

Our 10 features already cover what a referee would ask for: Fama-MacBeth with Newey-West, GRS, spanning, the specification curve, placebos, regimes, diagnostics, causal designs, decay, synthetic control and the Harvey–Liu–Zhu hurdle. **No retail or prosumer product does this.** Portfolio123 and QuantConnect test *strategies*; we test *whether the signal is real*. That is the pitch:

**"Bring your signal or formula. Get the referee report before the referee does."**

What stops it being worth paying for today:
1. **You cannot type your own signal as a formula.** Users pick from a few built-in signals or upload a CSV. This is the biggest gap; see A1.
2. **No point-in-time or survivorship guarantees are shown to the user.** Researchers distrust any result that doesn't show them.
3. **No single verdict across all 10 tests.** Each feature reports separately, and the user has to stitch them together.
4. **Results disappear when the server restarts,** because jobs live in memory. Nobody pays for work that vanishes.
5. **The research module uses only a slice of the data.** The parquet already holds 4,300+ tickers across many universes (US, international, indices, ETFs), but Research V2 defaults to 400 US names over about 10 years. Production data will be much larger. Build for that now (see A2.10 and section E).

Fix those five and this is a product.

---

## A. Features to add (biggest list, ranked by demand × how different it makes us)

### A1. Your own signal, your way (the core)
1. **[B+F] Formula language for signals:**
   - Build from expressions such as `rank(-ts_return(close, 252, skip=21)) * (mcap > q20(mcap))`, with an operator library: `ts_mean`, `ts_std`, `ts_rank`, `delay`, `delta`, `rank`, `zscore`, `winsorize`, `neutralize(x, sector)`, `group_rank`, `if_else`, and fundamentals fields.
   - WorldQuant BRAIN's "Fast Expression" proves this works: people compete on it for free.
   - The backend compiles each expression into polars, safely: a whitelisted parser, no `eval`.
   - **The highest-demand feature on this list.**
2. **[F] Formula editor:**
   - syntax highlighting, autocomplete for fields and operators, inline docs, and errors underlined as you type
   - a live preview of the signal's histogram and coverage per month before you run anything
3. **[B] Python signal upload:** a sandboxed `def signal(panel) -> Series`, run in the worker subprocess with a time limit, a memory limit and no network.
4. **[B] Signal library:** one click loads any of the roughly 200 Chen–Zimmermann replicated anomalies (OpenAssetPricing data and code are open). Users test against the published literature instantly, and that becomes the benchmark set for "is my signal new?"
5. **[B+F] Signal combiner:**
   - Combine signals by equal weight, IC weight, inverse-variance or rank-average.
   - Orthogonalise a new signal against known ones and test only the residual. This is the "is it new" test.
6. **[B+F] Saved signals with versions:** every signal edit is a version, each run links to its version, and old versions can be diffed. This is the research equivalent of git.

### A2. Trust: data integrity researchers demand
7. **[B] Point-in-time fundamentals:**
   - Lag every fundamental to its filing acceptance date, not the period end.
   - Keep restatements as separate versions.
   - Show the lag rule on every result. Reddit names this as the thing that decides results.
8. **[B] Survivorship-free universes:** include delisted names, apply delisting returns (Shumway-style adjustment), and use historical index membership. Show a badge on every run: "Survivorship: handled / not handled".
9. **[B+F] Data audit panel per run:**
   - coverage per month, missing share and stale prices
   - outlier counts and corporate-action adjustments
   - the exact universe size each month
   - one click downloads the panel used
10. **[B] Use every universe already in the parquet:**
    - All 4,300+ tickers and every market and asset class in the file, with a universe picker by region, exchange and asset type.
    - Country-neutral and region-level tests, so the same signal is tested in the US, Europe and Asia at once. Out-of-market replication is the strongest evidence a referee accepts.
    - Design every query to scale to the much larger production data: lazy scans, partitioning by market and year, and cached per-universe panels (WORK_LEFT memory section).
11. **[B] Look-ahead guard:** automatically detect signals that correlate with future returns impossibly well, or that use same-day closes, and flag them before showing results.

### A3. Overfitting control (r/algotrading's top pain)
12. **[B+F] Multiple-testing ledger:**
    - count every signal and specification a user has tried, per project
    - apply the deflated Sharpe ratio, haircut Sharpe (Harvey–Liu) and the probability of backtest overfitting (CSCV/PBO)
    - **The "trial counter" is unique and very sticky.**
13. **[B+F] Locked holdout vault:** the API already has holdouts and locks. Expose them as a ceremony: data after date X stays sealed until you "unseal once". This is a real differentiator, and the backend half exists.
14. **[B] Walk-forward and combinatorial purged CV** (López de Prado) for any signal or model, with embargo settings.
15. **[B+F] Pre-registration:**
    - Before running, write the hypothesis, the expected sign and the main test.
    - The report shows "pre-registered vs exploratory" for every result.
    - Academics will love it, and it suits journal submissions.

### A4. One verdict instead of ten pages
16. **[B+F] "Signal report card", one run across all modules:**
    - one button runs Canonical, Robustness, Placebo, Regimes, Diagnostics, Decay and Factor zoo on the same signal and settings
    - the result is a scored scorecard with an A–F grade per dimension and one overall verdict
    - **This is what people will share and pay for.**
17. **[B+F] Referee-style PDF/LaTeX report:**
    - an abstract-style summary, the tables (journal formatted) and the figures
    - a robustness appendix and an auto-written methods section
    - Export to Overleaf.
18. **[B] Automatic "what would a referee ask"** checks: microcaps, NYSE breakpoints, value vs equal weight, January effect, transaction costs, and post-publication decay. Each gets a pass/fail.

### A5. Costs, capacity and implementability
19. **[B+F] Transaction-cost model:** spread, commission and market impact (square-root law), with turnover-aware net returns and a break-even cost chart: "this survives up to 23 bps".
20. **[B] Capacity estimate:** AUM at which the signal's alpha is eaten by impact.
21. **[B] Short-sale constraints:** borrow availability and cost proxies, plus long-only versions of every result.

### A6. Collaboration and persistence (needed for revenue)
22. **[B] Persistent projects:**
    - runs, signals and notes stored in Postgres or SQLite with object storage
    - results survive restarts
    - shareable read-only links
23. **[B+F] Projects and notebooks:** a project holds signals, runs, notes, the board and pre-registrations, with a timeline of everything tried. This gives the multiple-testing ledger a natural home.
24. **[B+F] Share and embed:** a public link to a report card or a single chart. This doubles as viral distribution.
25. **[B] Python SDK and REST API:** `atlas.run("robustness", signal="...")` from a notebook. Quants live in Jupyter; meet them there.
26. **[B] Scheduled re-runs and alerts:** rerun monthly with fresh data and alert when a signal's decay crosses a threshold or its t-stat drops below 2.

### A7. AI that actually helps (careful, not slop)
27. **[B+F] Idea → formula:** describe a signal in English and get the formula with an explanation, which the user edits. Alpha-GPT (arXiv 2308.00016) shows the pattern.
28. **[B+F] Plain-language explainer on every result:** "Your t of 1.14 is below the factor-zoo hurdle of 3.39 because…", grounded only in the run's numbers.
29. **[B] Literature lookup:** "Has this been published?" matches the formula against the Chen–Zimmermann catalog and SSRN titles.

### A7b. Found in the extra research pass
30. **[B+F] "Assaying Anomalies"-standard template report.**
    - Novy-Marx and Velikov (2023) define the academic protocol for testing a new cross-sectional predictor. Their open MATLAB toolkit produces standardized "template reports" and has been used to screen more than 30,000 signals.
    - Matching that protocol, with a "Protocol: Novy-Marx & Velikov" badge on the report card, gives instant academic credibility.
    - It also positions us as the no-code, web version of the tool academics already trust.
31. **[B] Batch screening:** run the report card over hundreds of formula variants at once, as the AI-Powered Scholarship paper did. Rank them, apply the multiple-testing correction automatically, and keep the survivors. Power users will pay for this.
32. **[B+F] Research agent (later):** QRAFTI (arXiv 2604.18500) shows agentic empirical-finance research built on this protocol. Ours: "test these 5 ideas overnight and give me the report cards", with every step logged in the ledger.

### A8. Money features: how it gets paid for
- **Free:** 3 runs a day, US large caps, built-in signals, watermarked exports.
- **Pro (~$29–49/mo):** formula language, all features, full universe, report card, PDF/LaTeX, saved projects, 20 years of data.
- **Research (~$99/mo, academic discount):**
  - point-in-time and survivorship-free data, international markets
  - Python SDK, the multiple-testing ledger, the holdout vault, pre-registration, sharing
- **Team or institution:** seats, shared projects, SSO, an audit trail, and priority compute.

For context, Koyfin charges $39–79 for mostly data viewing. We sell validation, which is a higher-value job.

---

## B. Remove, merge or demote (bloat)

Rule: if a researcher wouldn't miss it, or it duplicates something, it goes.

1. **Merge Diagnostics into Canonical tests** as a "Model checks" section. Nobody runs regression diagnostics on their own. The report card then shows them automatically.
2. **Merge Publication table into Export,** as an export on every feature plus the report card (A17). It isn't a research question.
3. **Fold Synthetic control into Causal designs** as a fifth design (the backend already shares the treatment inputs). That gives one causal page instead of two.
4. **Demote Regimes to a section of Robustness,** "By regime". Regime splits are another robustness dimension.
5. **Overview "Tested on this device" stats:** these become meaningless once projects exist; replace them with project-level stats.
6. **Remove the old /labs/research pages** (beta, correlation, momentum, narrative, spider and others in the build list) if they aren't linked from anywhere current. They look like the earlier generation and dilute the product. *Verify first.*
7. **Cut the long tail of rarely-used options:** Causal designs has about 35 inputs, and bootstrap counts, kernels and contamination days belong under an "Advanced" fold. Keep defaults that a referee would accept.
8. **Hide or drop outputs that repeat a number shown elsewhere:** several features show the same t-stat in the KPI strip, a table and a card. Keep one.
9. **Demote the Gauge/"vitality" style widgets** unless they encode a real statistic. Dial gauges read as consumer fluff to this audience.
10. **Merge Studio and Research projects later.** Two separate saved-workspace concepts confuse people; keep one Projects system.

Result: **6 core pages** instead of 10:
1. Signal (formula and library)
2. Report card
3. Pricing tests (Canonical with Model checks)
4. Robustness (with regimes and placebos)
5. Causal (with synthetic control)
6. Decay and Novelty (Decay with Factor zoo)

---

## C. UI and frontend (from the screenshots and the session)

### C1. "View as" improvements (you said it isn't perfect yet)
1. **[F] Smarter defaults:** pick columns by role (estimate, CI, t, p, date, group) instead of the first numeric columns. Never offer a heatmap of a pure time series.
2. **[F] Small multiples / facet by group:** one mini-chart per sector, regime or portfolio. This is the Koyfin "Lots of charts" pattern.
3. **[F] Dual axis and log scale toggles,** and a per-series chart type (bars plus a line).
4. **[F] Aggregate:** group by a column, then mean, median, sum or count, before charting.
5. **[F] Chart and table split view,** side by side inside one card. This is the TradingView tester pattern.
6. **[F] Keep the designed view's annotations** (CI bands, reference lines, significance) when switching to a line or bar chart.
7. **[F] Collapse the pickers into one compact toolbar row** with popovers. They take too much height now.
8. **[F] "Save as my default for this output type"** across features.

### C2. Signal editor and report card screens (new)
9. **[F] Signal page:** a formula editor on the left; a live histogram, coverage and correlation with known factors on the right; one big "Run report card" button.
10. **[F] Report card:**
    - a grade strip at the top (Pricing, Robustness, Placebo, Regimes, Causal, Decay, Novelty, Costs)
    - each grade expands into its key chart
    - a pass/fail checklist of referee questions
    - one-page PDF export
11. **[F] Multiple-testing ledger widget,** always visible in the top bar: "Trials in this project: 37 · deflated SR hurdle 0.81".

### C3. Premium polish still missing (from the screenshots)
12. **[F] TradingView-style object tree and data window** in the right panel: values for every series at the crosshair, across all charts on the page.
13. **[F] Floating section navigation** in the Portfolio Visualizer style, for long reports and printing.
14. **[F] Trend-line and rectangle drawing tools** (only the level line and date notes exist now) and a snapshot-to-clipboard button on every chart.
15. **[F] Grouped two-level headers on every multi-model table,** like the Portfolio Visualizer loss-probability table.
16. **[F] Command palette actions,** for example "run robustness with lookback 5y" or "compare last two runs".
17. **[F] Onboarding:** a guided 60-second run on a famous anomaly (momentum) so the first session ends with a real report card.
18. **[F] Mobile read-only mode** for reports and the board. Researchers check results on phones.
19. **[F] Visual regression tests** (Playwright screenshots of each feature in dark and light) so the premium look doesn't rot.

### C4. Known issues to fix
20. **[F] Explore remembers choices per feature,** but the overlay picker lists runs that the server no longer has. Hide those once persistence (A22) lands.
21. **[F] "Settings changed, results are stale" shows too often** because restored form defaults differ in type ("12" vs 12). Normalise before comparing.
22. **[B] A Markov-switching fit in Regimes is randomised and occasionally fails** with a LinAlgError. It needs a seed and a fallback.
23. **[B] Signal decay (25 s) and Synthetic control (13 s) are slow:** cache the panel per job and parallelise the bootstrap.
24. **[B] Lazy-load sklearn and statsmodels in the other routers** so the app idles near 150 MB instead of 485 MB.

---

## E. Inputs: make them the best part of the product
The inputs decide what users can test, so this is where we give maximum freedom without clutter.

1. **[F] Three levels on every feature:**
   - *Quick*: 3–5 inputs with referee-safe defaults.
   - *Standard*: the current groups.
   - *Expert*: everything, including raw JSON.
   - One toggle in the Study panel switches level, and the setting is remembered.
2. **[B+F] Universe builder at full scale:**
   - pick region, country, exchange, asset type, sector, size band, liquidity floor, price floor and listing-age
   - "exclude financials or utilities", custom lists and uploaded lists
   - historical index membership once available
   - a live count of names per month while editing
   - save as a named universe, reusable across features
3. **[F] Sample window:**
   - a timeline brush over the data's actual coverage, with recession and crisis shading
   - presets (pre and post publication, ex-2008, ex-COVID, last 5 or 10 years)
   - the out-of-sample split drawn on the same timeline
4. **[B+F] Signal input = formula editor (A1),** with field autocomplete grouped by data source and a coverage hint on each field.
5. **[F] Every numeric input** gets a slider and a box, a unit (days, months, bps, %), a valid range from the API, a "why this default" tooltip with a citation, and a sweep toggle (already built).
6. **[F] Linked inputs:** choosing a design or method hides irrelevant inputs (built for Causal designs; extend to all features). Inputs that conflict show an inline warning, never a backend error.
7. **[F] Presets from the literature,** as one-click settings: "Fama-French 1993 setup", "Novy-Marx & Velikov protocol", "Jegadeesh-Titman momentum", "Hou-Xue-Zhang q-factor screens".
8. **[F] Shareable settings:** each run's inputs encoded in the URL, and a "copy as Python SDK call" button.
9. **[B] Validation from the API:** each input carries `required`, `min`/`max`, `depends_on` and `conflicts_with` in the feature spec, so the frontend stops hard-coding rules (StudyForm's REQUIRED and CONDITIONAL maps today).
10. **[F] Diff before run:** "You changed 3 settings vs the last run", with the list, so every comparison is deliberate.

## D. Order to build

1. **[B]** Persistence (A22), then the formula language (A1.1) and signal library (A1.4). The product isn't sellable without these three.
2. **[B+F]** Report card (A16) with the merged 6-page structure (section B).
3. **[B]** Point-in-time, survivorship and audit (A2.7–9), then longer history (A2.10).
4. **[B+F]** Multiple-testing ledger, holdout vault and pre-registration (A3).
5. **[F]** Signal editor UI, the View-as upgrades and the report card UI (C1–C2).
6. **[B+F]** Costs and capacity (A5), the SDK (A25), sharing (A24), then AI helpers (A7).

---

## F. Build checklist (status as of 2026-10-04)

`[x]` done and verified · `[~]` done with a data limit · `[ ]` not in this batch (by decision)

### B. Remove / merge
- [x] B1 Diagnostics merged into Pricing tests as "Model checks"
- [x] B2 Publication table moved under Export (no longer a nav page)
- [x] B3 Synthetic control merged into Causal designs (design "synthetic")
- [x] B4 Regimes merged into Robustness as "By regime"
- [x] B5 Device-only overview stats replaced by stats strip, stages, project ledger
- [x] B6 Old `/labs/research/*` pages deleted (15), redirected to `/research`
- [x] B7 Rare options folded behind Quick / Standard / Expert levels
- [x] B8 Outputs that only repeat the key stats are hidden
- [x] B9 Vitality dial replaced by a zone ruler
- [ ] B10 Merge Studio and Research projects (later)
- [x] Result: 6 pages: Signal, Report card, Pricing tests, Robustness, Causal, Decay & novelty; old URLs still work

### A1. Your own signal
- [x] Formula language (safe parser, ~25 operators, ~60 fields, PIT fundamentals)
- [x] Formula editor (autocomplete, error underline, live histogram/coverage/known-factor correlation)
- [ ] Python signal upload (not needed this batch)
- [x] Signal library: 55 published anomalies with citations, one-click load
- [x] Signal combiner (equal, IC, inverse variance, rank average) + orthogonalize against known signals
- [x] Saved signals with versions

### A2. Trust / data
- [~] Point-in-time fundamentals with filing lag, lag shown in every run's data audit
- [~] Survivorship: reported on every run, "not handled" (file has no delisted names)
- [x] Data audit per run (universe size and coverage by month, missing share, adjustments)
- [x] All universes in the parquet: 40 country × asset-type groups, ~4,157 tickers, region / asset-type / price / liquidity / listing-age filters, lazy scans for larger data
- [x] Look-ahead guard on every signal run

### A3. Overfitting control
- [x] Multiple-testing ledger per project (trials, deflated Sharpe hurdle, Harvey–Liu haircut, PBO)
- [x] Holdout vault (seal a date; jobs cut data after it; unseal once)
- [x] Walk-forward and purged CV with embargo, PBO
- [x] Pre-registration (hypothesis, sign, primary test); results marked pre-registered

### A4. One verdict
- [x] Report card: A–F per dimension, overall grade, one run across 7 tests
- [x] Referee-style report export: LaTeX, PDF, Markdown
- [~] Referee checklist (microcaps, NYSE breakpoints, VW vs EW, January, costs, decay); NYSE breakpoints blank (no exchange field), decay needs a discovery date

### A5. Costs and implementability
- [x] Cost model (spread, commission, sqrt impact), net Sharpe, break-even bps
- [x] Capacity estimate
- [x] Long-only variant

### A6. Collaboration and persistence
- [x] Persistent runs and results (SQLite), survive restarts
- [x] Projects (switcher, ledger, holdout, preregistration)
- [x] Share links, read-only view (feature runs and report cards)
- [ ] Python SDK and REST API (excluded)
- [ ] Scheduled re-runs and alerts (excluded)
- [ ] Embed (not needed this batch)

### A7. Explanations without AI
- [x] Plain-language explanation on the report card, built from templates
- [x] Literature lookup: nearest published anomalies by correlation
- [ ] Idea → formula with an LLM (excluded: no AI this batch)

### A7b. Protocol and screening
- [x] Novy-Marx & Velikov (2023) "Assaying Anomalies" protocol steps on the report card
- [x] Batch screening with BHY-corrected p-values
- [ ] Research agent (excluded)

### A8. Pricing tiers
- [ ] Not this batch (by decision)

### C1. View as
- [x] Role-aware default columns; CI band, zero line and significance kept
- [x] Small multiples, group-and-reduce, log transform, chart + table split
- [x] Compact toolbar; default view per output type
- [x] Overlay another run (B dashed)

### C2. New screens
- [x] Signal page
- [x] Report card page (with batch screen and walk-forward)
- [x] Multiple-testing ledger chip on every feature page

### C3. Premium polish
- [x] Data window (values of every chart at the crosshair)
- [x] Floating/section navigation (page pills, section tabs, `[` `]` keys)
- [x] Trend line, rectangle, level and note drawing tools; copy chart to clipboard
- [x] Grouped two-level table headers
- [x] Command palette actions (pages, report card, compare, every anomaly)
- [x] Onboarding (3-step first run)
- [x] Phone layout (one column, page picker)
- [x] Visual regression tests (4 pages × dark/light, baselines on installed Chrome)

### C4. Known issues
- [x] Overlay picker works across restarts (runs persist)
- [x] "Settings changed" no longer fires on "12" vs 12 or on the active formula/project
- [x] Regimes randomness / slow features addressed in the speed pass (Diagnostics 68s → 1–3s, Robustness 29s → ~17s)
- [~] Idle backend memory ~485 MB (other modules import sklearn/statsmodels eagerly)

### E. Inputs
- [x] Quick / Standard / Expert levels
- [x] Universe builder at full scale with live instrument count
- [x] Sample-window timeline brush with crisis shading and presets
- [x] Formula input on the Signal page with field autocomplete and coverage
- [x] Units, valid ranges, "why this default" tooltips with citations; sweep toggle
- [x] Linked inputs from the API (depends_on, conflicts warning, required)
- [x] Literature presets (Fama-French, Novy-Marx & Velikov, Jegadeesh-Titman, HXZ, HLZ)
- [x] Shareable settings link (Python SDK call excluded)
- [x] Input rules served by the API
- [x] "N settings changed since the run on screen" before running
