# Research V2: Work Left (frontend and UX)

Status 2026-09-29: backend is complete (see `DONE.md`). The frontend works end to end but is a first pass. One generic workbench renders 46 chart and table types from the manifest, and every output is a card in a long scroll. The goal of this document is the best research UI we can build: each feature gets a purpose-built result view, publication-grade charts, and an interaction model a researcher would pay for.

## 0. Principles

1. **Answer first.** Every feature opens with a verdict header in one sentence with the headline number, the test behind it, and what it means (e.g. "Momentum does not survive: FM t = -0.04, placebo p = 0.86, 3 of 5 placebos fail"). The evidence goes below it.
2. **One layout per feature, not one card per key.** Group outputs into tabs or sections that follow the spec's reasoning order. The manifest stays the contract; a per-feature *layout* file only arranges outputs.
3. **Publication-grade visuals.** Confidence bands everywhere, zero lines, significance encoded in colour and shape, and tabular numerals. Axes get units and sources, and any chart can be exported as SVG or PNG.
4. **Everything exportable.** LaTeX, CSV, PNG/SVG per chart, a full PDF report, and a shareable run link.
5. **Fast and honest states.** Skeletons that match the final layout, live job progress with the step name, errors that say how to fix the input, and caveats pinned to the outputs they affect.

## 1. Stack decision (pick once, use everywhere)

| Need | Choice | Why | Already installed? |
|---|---|---|---|
| UI primitives | **shadcn/ui** (Radix + Tailwind 4 + cva) | Accessible, themeable, owned code; matches `class-variance-authority`, `tailwind-merge`, Radix already present | Radix parts, cva, clsx yes; add shadcn components via CLI |
| Charts (default) | **visx** for bespoke statistical charts (spec curve, forest, event study, RD, gauges) | Low-level D3 primitives in React, full control of bands and annotations | yes (`@visx/*`) |
| Charts (fast/simple) | **recharts** for plain line and bar charts only | Already used in 54 files | yes |
| Big tables | **TanStack Table** + `@tanstack/react-virtual` | Sort, filter, column pinning, virtual rows for 5k-spec curves | virtual yes; add `@tanstack/react-table` |
| Command palette | **cmdk** | Jump to feature, output, or preset (⌘K) | yes |
| Layout | **react-resizable-panels** | Form, results and inspector as resizable panes | add |
| Math | **KaTeX** (`react-katex` or `katex`) | Render each estimator's formula in "Method" drawers | add |
| Motion | **framer-motion** (already) | Result reveal, number count-up, tab transitions | yes |
| Toasts | **sonner** | Job finished or failed notifications | add (or keep react-hot-toast) |
| Chart export | `html-to-image` or a visx SVG serializer | PNG/SVG download per chart | html2canvas yes; prefer SVG export |
| Code blocks | **shiki** | Syntax-highlighted LaTeX and CSV previews | add |
| State | **zustand** (already) | Saved studies, compare runs, UI prefs | yes |

Do **not** add ECharts or Plotly to Research V2. One family (visx + recharts) keeps the bundle and the look consistent.

## 2. Screenshot checklist (research 2026-09-29)

Open each link, screenshot the part named in the "Capture" column, and share it. Each row names the feature it informs. Links were found by web search on 2026-09-29.

### Statistical output (the canonical look researchers trust)

| Feature | Source | URL | Capture |
|---|---|---|---|
| F02 | specr: custom plots vignette | https://masurp.github.io/specr/articles/custom-plot.html | Curve + choice panel + sample-size strip stacked; boxplot-by-choice; variance decomposition bar |
| F02 | specr intro | https://masurp.github.io/specr/articles/specr.html | Default `plot(results)`; circular "garden of forking paths" setup plot |
| F02 | specr repo | https://github.com/masurp/specr | README figure |
| F02 | Hall et al. 2022, survey of multiverse visualisations | https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.14443 | Figure grid of multiverse vis types |
| F01, F06 | modelsummary | https://modelsummary.com/ | Side-by-side regression table; `modelplot` dot-whisker |
| F06 | modelsummary: themes and styles | https://modelsummary.com/vignettes/appearance.html | gt-styled table with spanners, footnotes and highlighted rows; density sparklines inside a table |
| F06 | modelsummary: model summaries | https://modelsummary.com/vignettes/modelsummary.html | Stars, SE in parentheses, GOF block, stacked panels (`shape="rbind"`) |
| F06 | modelplot | https://modelsummary.com/man/modelplot.html | Multi-model coefficient plot with shaded background band |
| F07 DiD | DiD / event-study workshop (hesscl) | https://hesscl.com/data-viz-workshop/case-b-event-study.html | Treated vs control trends; `ggdid` group-time and dynamic plots |
| F07 DiD | `fixes` R package README | https://cran.r-project.org/web/packages/fixes/readme/README.html | Event study with simultaneous vs pointwise bands; ATT(g,t) heatmap; honest-DiD sensitivity plot |
| F07 RD | rdrobust `rdplot` docs | https://search.r-project.org/CRAN/refmans/rdrobust/html/rdplot.html | Binned-means RD plot with fits each side |
| F07 RD | rdpackages repo | https://github.com/rdpackages/rdrobust | rdplot illustration (senate data) |
| F09 | synthdid plot reference | https://synth-inference.github.io/synthdid/reference/synthdid_plot.html | Treated vs synthetic with the 2×2 "parallelogram" diagram and the effect arrow; lambda weights strip below |
| F09 | synthdid vignette | https://github.com/synth-inference/synthdid/blob/master/vignettes/synthdid.Rmd | Unit-contribution dot plot (dot size = weight); DiD vs SC vs SDID side by side |
| F09 | synthdid "more plotting" | https://rdrr.io/github/synth-inference/synthdid/f/vignettes/more-plotting.Rmd | Spaghetti of top-weight donors; zoomed inset around treatment onset |

### Explaining inference visually (null distributions, CIs, power)

| Feature | Source | URL | Capture |
|---|---|---|---|
| F03, F02 | R Psychologist: p-values | https://rpsychologist.com/pvalue/ | Simulated null with observed marker and shaded tail |
| F03 | R Psychologist: power and significance | https://rpsychologist.com/d3/nhst/ | Two overlapping distributions with α/β regions (for the power card) |
| F01, F04 | R Psychologist: confidence intervals | https://rpsychologist.com/d3/ci/ | "Dance of CIs" stack |
| F01 | Observable: interactive t-test | https://observablehq.com/@bluprince13/an-interactive-explanation-of-the-t-test-to-compare-means | Layout of explanation text next to the live chart |

### Product feel and dashboards

| Area | Source | URL | Capture |
|---|---|---|---|
| App shell | Koyfin | https://www.koyfin.com/ | Dashboard density, sidebar drag-out, theme switcher |
| Tokens | Bloomberg design tokens (shadcn.io) | https://www.shadcn.io/design/bloomberg | Colour tokens and the market up/down semantics |
| Tokens | Perpetua style guide ("Bloomberg meets Linear") | https://github.com/tomiiide/perpetua/blob/main/design/STYLE_GUIDE.md | Surface steps, hairlines, serif display with mono data, density tokens |
| Tokens | Trading terminal design system | https://vontigo.ai/docs/systems/trading-terminal | Panel rules, no-shadow elevation |
| Shell | Fortress dashboard (shadcn + Tailwind 4) | https://fortress-shadcn.dashboardpack.com/ | Dense institutional layout on our exact stack |
| Shell | v0 Bloomberg-like terminal | https://v0.app/templates/bloomberg-like-terminal-Ywgao7dGBbN | Terminal panes |
| Principles | "Designing data-dense dashboards" | https://pixel-show.com/blog/designing-data-dense-dashboards | Dark surface ladder, sparkline vs full chart |
| Styles | financial-ui-suite (14 finance aesthetics) | https://github.com/rgourley/financial-ui-suite | `research-terminal` (AlphaSense/FactSet) and `editorial-financial` (FT) examples |
| Reports | Observable Framework showcase dashboards | https://old.observablehq.com/blog/takeaways-from-building-showcase-dashboards | Big-number boxes with tick charts; custom legends; brush-zoom |
| Reports | Evidence example apps | http://evidence.dev/examples | Component gallery; tables with sparklines |
| Reports | Quarto dashboards gallery | https://quarto.org/docs/dashboards/ | Value boxes + sidebar + tabset layout |
| Reports | Hex data stories | https://hex.tech/templates/exploratory-analysis/interactive-data-stories/ | Long-form narrative report with inline charts |

### Components and libraries to evaluate

| Need | Source | URL | Note |
|---|---|---|---|
| Charts on our stack | shadcn/ui Chart (Recharts v3) | https://ui.shadcn.com/docs/components/radix/chart | Tooltip, legend and theming pattern to adopt for simple charts |
| Chart gallery | shadcn.io charts (53) | https://www.shadcn.io/charts | Interactive area/bar with range brush |
| Linked chart + table | linked-chart | https://awesome-shadcn-ui.com/linked-chart | Click the chart, filter the table: use for the F02 matrix |
| Dashboard kit | Tremor | https://github.com/tremorlabs/tremor-npm | KPI card + chart patterns |
| Chart grammar | TanStack Charts | https://github.com/TanStack/charts | Library comparison table (bundle size, SVG/Canvas); candidate if visx gets heavy |
| Comparison | TanStack Charts vs others | https://github.com/TanStack/charts/blob/main/docs/comparison.md | Size and feature matrix used for the stack decision |

Already decided from this research: keep recharts through **shadcn Chart** for simple charts (the same library, better tooltips and theming) and **visx** for the statistical hero plots. Adopt the specr, rdplot and synthdid visual grammars exactly, because readers already know how to read them.

## 3. App-level work

- [ ] **Three-pane workbench** (react-resizable-panels): left study form (collapsible), centre results, right inspector for the selected output (method, formula, raw data, export).
- [ ] **Verdict header** per feature, driven by a new backend `headline` + `verdict` (green/amber/red) in `meta`.
- [ ] **Per-feature layout files** (`layouts/f01.js` ...) that assign manifest outputs to tabs and sections; the generic fallback stays for new outputs.
- [ ] **Live job progress:** backend emits step names ("Fama-MacBeth", "bootstrap 400/1000"), shown as a stepper; replace polling with the existing Studio SSE pattern.
- [ ] **Presets:** one-click studies (e.g. "Momentum crash test", "Value post-2021", "Index-inclusion event study").
- [ ] **Saved runs and compare:** keep run history (zustand + backend job ids), and diff two runs side by side (e.g. a coefficient with vs without controls).
- [ ] **Shareable links:** payload encoded in the URL; opening the link re-runs or loads the cached job.
- [ ] **⌘K palette** (cmdk): features, outputs, presets, recent runs.
- [ ] **Method drawer per output:** KaTeX formula, plain-language explanation, citation, assumptions, what to do if it fails.
- [ ] **Chart toolkit:** hover crosshair with exact values, brush-to-zoom on time series, PNG/SVG/CSV export on every chart, and a colour-blind-safe palette with light/dark themes.
- [ ] **Full PDF / HTML report** of a run, combining all outputs with captions; the backend already renders tables with reportlab.
- [ ] **Form UX:** field-level validation from the manifest `min`/`max`, dependent fields (hide DiD inputs when the design is RD), and a sticky "what will run" summary.
- [ ] **Accessibility:** keyboard navigation across tabs and cards, aria labels on charts with a data-table fallback, reduced-motion support.
- [ ] **Performance:** lazy-load heavy renderers per tab, virtualise big tables, memoise chart data.
- [ ] **Mobile:** single column, tabs become a segmented control, charts scroll horizontally with readable ticks.

## 4. Best outputs per feature

### F01 Canonical Test Engine
- **Verdict header:** FM λ, t, regime (valid/conservative/invalid), spanning α t.
- **Tabs:** Regressions | Sorts | Asset pricing | Panel | Exports.
- **Regressions:** journal-style FM table with stars and SE in parentheses; rolling slope chart with a significant-period shaded band (green/red).
- **Sorts:** portfolio ladder (bar per quintile with CI whiskers, long-short highlighted); a 5×5 double-sort heatmap with row and column spreads in the margins; cumulative long-short growth with drawdown shading; MR test shown as a monotonic "staircase" check.
- **Asset pricing:** GRS card; Shanken vs GMM side-by-side dumbbell chart per factor with disagreement flags; weak-identification gauge (condition number, beta dispersion).
- **Panel:** coefficient table with FE indicators; Hausman verdict chip.

### F02 Robustness Engine
- **The hero is a `specr`-style specification curve:** sorted coefficients with CIs (visx), linked to a decision dashboard below (one row per dimension, dots showing which choice each spec used). Hovering a spec highlights its column.
- A null band from the permutation test overlaid on the curve.
- Decision-attribution bar chart; weakest and strongest spec callouts with their explanation.
- Robustness matrix as a TanStack table, filterable by dimension, colour-scaled by t.

### F03 Placebo Suite
- **Scorecard:** 5 placebo tiles (pass/fail, statistic, criterion), an overall verdict ring, and a combined Fisher/Stouffer p.
- Permutation histogram with the real t marker and shaded tail area = p-value.
- Time-displacement and wrong-direction mirror chart (original vs flipped long-short).
- OOS panel: IS vs OOS coefficient bars with the ratio gauge (green >0.7, amber 0.3–0.7, red <0.3).
- **Holdout manager UI:** reserve, see status and evaluation count, evaluate with a confirm dialog ("this uses up the holdout").

### F04 Regime Conditional
- Regime timeline ribbon aligned above a cumulative long-short line (see when it works).
- Coefficient comparison forest (per regime, CIs) plus the interaction-term card.
- Threshold search curve with the chosen threshold and the sup-F p-value.
- Markov state probability area chart; quantile-regression slope fan.

### F05 Diagnostic Center
- **Report card as the hero:** one row per test with a traffic light, plain-language line and the fix (expandable).
- Small multiples: correlogram with bands, squared-residual scatter, Q-Q plot, Andrews scan with the critical line and the break-date CI shaded.
- Partial-residual small multiples with a LOESS overlay.
- Influence table linking to the date or ticker.

### F06 Specification Builder
- **Visual column builder:** drag-to-reorder columns (dnd-kit, installed); each column is a chip with estimator, controls, FE, SE and period.
- Live journal preview in a paper style (serif, booktabs rules), toggling AER/JFE/RFS styles.
- Forest plot of the signal coefficient across columns.
- One-click copy of LaTeX (shiki highlighted), CSV and PDF download.
- **Lock spec button:** pre-register a column; a confirmatory badge appears.

### F07 Causal Identification
- **Design picker as big cards** (DiD / Event study / RD / IV) with a one-line "when to use"; the form adapts to the design.
- **DiD:** event-study plot comparing TWFE, Callaway-Sant'Anna and Sun-Abraham in one chart (toggle); Goodman-Bacon scatter (weight vs estimate, coloured by comparison type) with the TWFE line; balance love-plot (SMD before and after matching); placebo distribution.
- **Event study:** CAR path -20..+20 with a CI band; CAR histogram; a test-agreement matrix (t, Patell, BMP, KP) with a verdict.
- **RD:** `rdplot`-style binned scatter with fits either side of the cutoff; density plot with the manipulation p; placebo-cutoff and bandwidth-sensitivity forests; donut table.
- **IV:** first-stage strength gauge (F vs 10 and 104.7 lines); 2SLS vs OLS dumbbell; AR confidence-set p-value curve with the accepted region shaded; test chips.

### F08 Signal Decay
- **Hero vitality gauge** (animated dial, zones) plus the life-cycle sentence.
- Decay curve with rolling IC, all three fits, discovery / publication / arbitrage-arrival vertical markers, the floor line and a half-life annotation.
- Life-cycle segmented Sharpe bars (pre-discovery → post-arbitrage).
- Arbitrage vs data-mining split bar; international replication small-multiple table with a consistency score.

### F09 Synthetic Control
- Treated vs synthetic with the post period shaded and the effect annotated.
- Placebo spaghetti (grey) with the treated gap in bold; RMSPE-ratio ranking with the p-value.
- Donor weights as a treemap or bars with sector colours; leave-one-out band; conformal band chart.
- Variant switcher (classic / augmented / generalized / robust) overlaying their counterfactuals.

### F11 Factor Zoo
- **Zoo map:** scatter of IC-IR vs Sharpe for every factor, the candidate highlighted, and quadrant labels.
- HLZ bar: observed t against the 2.0 / 3.0 / BHY / Holm / Bonferroni thresholds as a ruler.
- Correlation heatmap clustered (hierarchical ordering) with near-duplicate outlines; spanning loadings bar chart.

## 5. Backend additions the frontend needs

- [ ] `meta.verdict` (green/amber/red) and a one-line `meta.headline` for every feature (F01 already has a headline).
- [ ] Job progress messages (`JobStore.update(progress=...)`) from long loops (permutations, bootstraps, placebos).
- [ ] `GET /presets` with curated payloads.
- [ ] A per-output `method` block in the manifest (formula in LaTeX, citation, interpretation), rendered by the method drawer.
- [ ] A run-report endpoint (full PDF/HTML of all outputs).
- [ ] Payload hashing for shareable links (the job store already hashes inputs, so reuse it).

## 6. Order of work

1. App shell: three panes, verdict header, per-feature layout files, chart toolkit (export, crosshair).
2. The four hero views: F02 specification curve, F07 DiD/RD/event plots, F03 scorecard, F06 table builder.
3. Remaining features F01, F04, F05, F08, F09, F11.
4. Presets, saved runs and compare, share links, ⌘K.
5. Method drawers and the full report.
6. Accessibility, mobile, performance, and Playwright visual tests for every feature.

## 7. Definition of done

- Each feature has a verdict header and a purpose-built layout; no output falls back to a raw table unless it *is* a table.
- Every chart has CIs where they exist, a zero or reference line, a hover readout and PNG/SVG export.
- Lighthouse accessibility ≥ 95; the page is usable at 375 px wide.
- A Playwright run executes every feature with a preset and captures a screenshot; visual diffs reviewed.
- Bundle: Research V2 routes load only the renderers for the visible tab.
