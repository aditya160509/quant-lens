# ML cinema plan: the whole Machine learning lab at institutional, best-in-class quality

Date: 2026-10-06. Status marks: [ ] open, [~] in progress, [x] done. Each phase ends at a commit; the plan ends at the tag `ml-design-v1`.

## Status, 2026-11-07

17 items done, 3 partly done, 16 open. Two open items are platform work. The owner is running this plan.

Commands now, from `frontend`: `pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm build`, `pnpm test:e2e:labs`. The older `npm` and `jest` commands below are history.

### T3 Code inspection

Commit `257e4073`, MIT licence. Findings from `apps/web`:

- **No charts.** No chart library or chart components are in its web source, so the "in-thread visualisations" named under References are not available to port. Our chart kit stays ours.
- **Size:** about 1,245 files in `components`, 2,575 lines of CSS and 274 custom properties.
- **Stack:** Base UI, shadcn `base-mira` style, Tailwind 4, cva, lucide, zustand. We are not on Base UI yet.

| Take | From T3 Code | Use in ML |
|---|---|---|
| Dense type | `--text-2xs` 11px, `--text-3xs` 10px | Chart ticks, badges, table meta; replace one-off sizes |
| Semantic geometry | `--control-radius`, `--floating-content-inset`, `--command-shell-inset` | Controls, popovers and palette stop drifting apart |
| Radius scale | Base `0.5rem`; sm, md, lg, xl derived | Replaces per-component radii |
| Status set | `success`, `warning`, `error`, `info`, each with foreground and 8% `surface` via `color-mix` | Verdicts and banners; keep our `--up`, `--down`, regime tokens |
| Contrast setting | `--appearance-contrast-*` | User contrast control; helps AA |
| Font settings | Separate interface and code size settings | User font size in the customise panel |
| Motion | `--ease-drawer` `cubic-bezier(0.32, 0.72, 0, 1)` | Panels and popovers |
| Skeleton | One stepped opacity pulse, in block, card and pill shapes | Cheap skeletons shaped like exhibits |
| Button sizes | `micro`, `xs`, `sm`, `compact`, icon sizes, taller on touch | One control set for exhibit tools |
| Control depth | `inset-shadow-control-highlight` and `pressed` | Primary buttons |
| Layer order | `--z-sheet` and documented layers | Stops overlay clashes |
| Scrollbar | `--app-scrollbar-*`, 6px | Tables and rails |
| Layout | `--workspace-gutter`, safe-area insets, 52px top bar | Shell and phone |

Components worth porting: `ui/` set (`button`, `menu`, `combobox`, `autocomplete`, `number-field`, `toggle-group`, `sheet`, `sidebar`, `empty`, `skeleton`, `toast`, `kbd`, `scroll-area`, `table`, `middle-truncate`), `CommandPalette*`, `RightPanelSheet`, `RightPanelTabs`, `WorkspacePageHeader`, `WorkspaceBreadcrumb`, `AnimatedHeight`, `RelativeTime`, `RenderErrorBoundary`, `AppearanceSettingsPanel`.

Skip: composer, git, terminal, provider, auth and desktop code. Keep our blue-led palette and Geist unless the font test says otherwise. Copied code keeps its notice in `THIRD_PARTY.md`.

Add to the open work: move shared controls to the ported Base UI set, and adopt the tokens above in `workspace.css`.

---

**Scope:** every page, output, table, control and state in the Machine learning lab (`/ml`). Research gets the same system afterwards (Phase 9).

**References**
- Feel: the T3 Code in-thread visualisations (supplied screenshots). They show:
  - takeaway headlines
  - KPI strips
  - direct labels and event annotations
  - crosshair tooltips
  - calendar heatmaps
  - a zoomable treemap
  - ranked file lists
- Rigour: MSCI/Barra factor reports, AQR papers and Bloomberg PORT.
- Chart choice: the FT Visual Vocabulary.
- Density: Koyfin and TradingView.

---

## 1. North star

An ML page should read like a short analysis written by a senior quant, rendered live:
- a one-line answer
- the 3–5 exhibits that prove it
- the caveats
- the data

Every chart:
- states its finding in its title
- labels its own lines
- marks the events that matter
- holds up under hover

What's on screen is the content, not boxes around it.

### What the references do that we don't yet

| Reference move | Where we are | Target |
|---|---|---|
| **Takeaway as the title** ("Opus 5.5 went from 0 to half of all turns in 3 days") | Titles describe the chart ("Long-short after costs") | Every exhibit title is a finding generated from the data; the descriptive name moves to the subtitle |
| **Subtitle with scope** ("Share of sent turns per day, by model family. Jul 6 to Oct 2.") | Units and windows scattered | Fixed subtitle grammar: *measure, unit, universe, window* |
| **KPI strip**: big mono numbers, caption below, hairline dividers | KPI strip with label above, uneven | Caption-below strip, 4–6 numbers, equal columns, an expand icon for the "all metrics" drawer |
| **Direct labels** at line ends with values ("GPT-6.x 28%") | Legends above charts | End labels with collision avoidance; legend only when more than 6 series |
| **Event annotation** ("Opus 5.5 ships, Sep 22") with a vertical rule | None | Annotation layer: regime changes, refits, crashes, train/test boundary, "today" |
| **Crosshair tooltip**: date and total, every series sorted, swatches, right-aligned values | Basic readout | One `Readout` spec used by every chart, synced across a page |
| **Calendar or weekday×hour heatmap** with a "fewer ▢▢▢ more" ramp | Value heatmaps only | Sequential ramp legend; calendar heatmaps for IC by month, returns, breaches |
| **Zoomable treemap** with breadcrumb and mode toggles (Color: Churn · Area · Tests) | None | Treemap for universe weights, risk, SHAP families, with mode toggles |
| **Ranked list** with mono paths, bold leaf, thin bar and right count | Mixed tables | `RankList` primitive for top-N anything |
| **Document flow**: no card borders, generous rhythm, prose bullets with bold lead-ins | Bordered cards in a grid | Borderless exhibits on a canvas; cards only for interactive panels |
| **Text-tab toggles** (underlined) for chart modes | Pill segmented controls everywhere | Underlined text tabs inside exhibits; pills only for page sections |

---

## 2. Visual language (tokens)

All tokens live in one file, `src/workspace/tokens.css`, defined for dark and light. Nothing hard-codes a colour.

**Canvas**
- dark `#0B0C0E`
- panel `#111215`
- raised `#16171B`
- hairline `rgba(255,255,255,.06)`
- light theme: `#FBFBFA` and `#FFFFFF`, with hairline `rgba(0,0,0,.07)`

**Text:** 4 steps (100 / 72 / 52 / 36 % of white). Data numbers always use tabular figures.

**Type**
- UI and prose: Geist Sans. Numbers, paths and tickers: Geist Mono.
- Scale: 11 / 12 / 13 / 15 / 18 / 24 / 32 px.
  - KPI numbers: 24 px mono, medium weight.
  - Exhibit title: 15 px, semibold.
  - Subtitle: 12.5 px at 52%.
  - Axis: 11 px mono at 52%.

**Spacing:** 4 px base and an 8 px grid. Exhibit padding 0, because exhibits sit on the canvas. Section gap 40 px; exhibit gap 32 px.

**Colour roles**
- **Accent:** one blue `#4C8DFF`, used for the thing under test (our model, our strategy, the selected item).
- **Signed:** up `#3FB68B` and down `#E5484D`. Used only for signed values (returns, P&L, deltas), never as series colours.
- **Categorical (8, tuned for dark, colour-blind-checked):** blue `#4C8DFF`, orange `#F08A3C`, teal `#2DB7A3`, amber `#E2B23C`, pink `#E5689B`, violet `#9B7CF0`, slate `#8A94A6`, lime `#9BC94A`. Order is fixed so a model keeps its colour on every page.
- **Sequential:** a single blue ramp of 9 steps (`#0E2A52` to `#CFE2FF`) for heatmaps and calendars.
- **Diverging:** down to neutral to up, for correlations and signed heat.
- **Controls and baselines:** slate and dashed. **Regimes:** Calm teal, Normal slate, Stress red-orange.

**Elevation:** none for exhibits; one soft shadow for popovers and tooltips.

**Motion**
- 160 ms ease-out for hover and toggles; 280 ms for chart transitions (d3 tweened paths).
- `prefers-reduced-motion` turns transitions off.
- No bounce, no skeleton shimmer longer than 1.2 s.

**Icons:** lucide at 1.6 stroke, 14/16 px only.

---

## 3. Page architecture (every ML page)

```
┌ Breadcrumb · page switcher · run status · Share · Report ───────────────────┐
│ Title + question                                         [Run ▸]  [⋯]       │
│ Context chips: Universe · Window · Horizon · Costs · Data as-of              │
│ VERDICT  one sentence, coloured by outcome, bold lead clause                 │
│ KPI STRIP  4–6 numbers, caption below, hairline dividers, ⤢ all metrics      │
│ Section pills (sticky): Answer · Evidence · Robustness · Explain · Data      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Exhibit 1  Takeaway title                                                     │
│            measure · unit · universe · window          [mode tabs] [⋯]        │
│            CHART (direct labels, annotations, crosshair)                      │
│            Footnote: method · sample · source                                 │
│ Exhibit 2 …                                                                   │
│ • Read: bold lead-in. Plain sentence. (2–4 bullets, generated)                │
├──────────────────────────────────────────────────────────────────────────────┤
│ Methodology (collapsible) · Data (tables, CSV) · Receipt                      │
└──────────────────────────────────────────────────────────────────────────────┘
Right rail: Study (inputs) · Inspect (selection, data window) · Runs · Compare
```

- **Fixed section order on every page:**
  - **Answer:** the 1–2 exhibits that decide.
  - **Evidence:** why we believe it.
  - **Robustness:** what could break it.
  - **Explain:** drivers.
  - **Act:** hand-offs, trades, sizes.
  - **Data**
- **Exhibits are numbered** per page (Exhibit 3 can be linked: `#ex-3`) and are borderless. A card frame appears only on hover for the tool row (expand, view as, export, pin).
- **Width:**
  - Exhibits are 12 columns at most, with the reading line capped at 1,100 px.
  - Two-up only when both exhibits are small multiples of the same question.
  - Layout uses container queries, not viewport queries.
- **Verdict colour:** green held up, amber mixed, red failed, blue informational.

---

## 4. Chart kit v2 (`src/charts/v2/`)

Built once and used everywhere. Every primitive takes the same `Frame` props (title, subtitle, footnote, annotations, height, empty and loading states) and exports SVG, PNG and CSV.

- [x] **Exhibit frame:** number, takeaway title, subtitle grammar, mode tabs slot, tool row on hover, footnote, skeleton shaped like the chart, error and empty states that say why and what to do. *(number, finding title, measure as subtitle, hover frame with floating tools, plain footnotes)*
- [x] **TimeSeries v2** *(direct end labels, quiet comparator hues, accent for the series under test)*
  - direct end labels with collision avoidance
  - event annotations (vertical rule and label)
  - shaded spans (train/test, regimes)
  - a band for uncertainty
  - log scale option
  - brush to zoom with a reset chip
  - crosshair synced across the page
  - canvas rendering above 5k points
  - percent/level/indexed toggles
- [x] **StackedArea v2:** share or absolute, direct labels at the right edge with the current share, annotation layer, rich tooltip (total plus every series sorted).
- [x] **Bars v2 (vertical and horizontal):** *(axis spine and outward ticks, square edged bars, 95% CI whiskers, comparator tints; horizontal ranking uses Diverging)*
  - value labels inside or outside automatically
  - reference lines with halo labels
  - grouped and stacked variants
  - highlight the item under test
  - sorted by default
- [~] **RankList:** mono label with bold leaf, thin bar, right-aligned value, optional sparkline and delta, top-N plus "show all".
- [x] **Dumbbell and Slope:** model vs control, before vs after, in-sample vs out-of-sample. *(Dumbbell with per-row or shared scale: sizing, regime filter, holding risk)*
- [ ] **Distribution:** strip, box, ridge and histogram with a marker for "you are here" and percentile bands (Sharpe paths, bootstrap, shuffled, Monte Carlo).
- [ ] **Heat table:** matrix with sequential or diverging ramp, row and column sort, totals row, "fewer ▢▢▢ more" legend, numbers shown only when they fit.
- [~] **Calendar heatmap:** month × year (IC by month, returns, VaR breaches) and weekday × time.
- [~] **Treemap:** zoom with breadcrumb and right-click or Esc to zoom out, mode toggles (size by weight or risk, colour by return, IC or drift), labels when they fit.
- [ ] **Scatter v2:** binned calibration line, diagonal, density hexbin above 2k points, lasso to a selection.
- [ ] **Waterfall v2:** base, contributions, prediction, grouped "n other features", click a bar to see that feature's distribution.
- [ ] **Dendrogram and correlation map:** linked hover (a leaf highlights its row and column), cut-height slider that colours clusters.
- [x] **Sparkline and KPI tile:** big number, caption, delta vs previous run, tiny trend. *(KPI strip with change since the previous run; sparklines on the Today board)*
- [ ] **Readout (tooltip):** one spec everywhere (title line; rows sorted by value; swatch, name, right-aligned value; optional total), positioned to avoid the cursor, keyboard accessible.
- [ ] **Legend:** only when there are more than 6 series. Clicking isolates a series; shift-click adds it.

**Annotations data contract:** a page-level `events` list (`{date, label, kind}`) is merged from the backend (`meta.events`: refits, regime switches, train/test cut, data gaps) and drawn by every time chart on the page.

---

## 5. Interaction model

- **Crosshair sync:** hovering any dated chart moves a shared cursor on every dated chart on the page; the right rail's "Data window" lists all series at that date.
- **Selection is global:** clicking a ticker, model, state or date selects it across the page. Every chart highlights it, the waterfall explains it, the Inspect panel shows its details. Esc clears it.
- **Brush to zoom** on any time chart applies to all dated charts (a "linked zoom" toggle); a reset chip appears.
- **Mode tabs** (underlined text) switch the lens inside an exhibit, for example:
  - Color: return · IC · drift
  - Size: weight · risk
  - Scale: level · % · log
- **View as:** designed lenses first, then generic chart kinds (this exists already and gets extended).
- **Keyboard:**
  - `[` and `]` change section; `j` and `k` move between exhibits; `e` expands an exhibit
  - `.` opens the exhibit menu; `/` focuses search; `r` runs; `c` compares
- **Compare runs:** pick two runs and every exhibit overlays them (A solid, B dashed), with KPI deltas.
- **Share and report:** copy a link to an exhibit (`#ex-3`), publish a verified page, print to PDF (tear-sheet stylesheet).

---

## 6. Tables system

- Built on TanStack Table (headless) with our styling, available as `DataTable v2`.
  - sticky header and first column
  - column sort
  - density toggle
  - number formats by column role
  - conditional formatting: inline bars, signed colour, heat tint
  - inline sparklines and deltas
  - row hover syncs with charts
  - virtualised above 200 rows
  - CSV export, plus copy as markdown
- **Column roles** are inferred from names (return, rate, weight, p-value, t-stat, count, date, ticker) and can be overridden by the layout.
- Every Data-section table gets a one-line description and its row count. Huge tables (held-out predictions) are paged and downloadable, never dumped.

---

## 7. Every output: what it becomes

The takeaway template is generated from the data. "Lens" means a designed alternative in View as.

### Overview (`/ml`)
- [ ] **Hero:** three start tiles exist already. Upgrade them to show live mini-exhibits once runs exist:
  - a sparkline of the ranking's IC
  - today's regime pill
  - the last verdict stamp
- [x] **"Today" board:** current regime, 1-month vol for the watched names, top 5 ranking names with drivers, the last Validate verdict, allocation drift. Each tile links to its exhibit. *(regime, risk, top 5, last verdict, allocation weights)*
- [x] **Activity:** recent runs as a timeline with verdict colours; a calendar heatmap of runs.

### Validate my strategy
| Output | Exhibit | Takeaway template |
|---|---|---|
| verdict | Verdict hero: stamp, the autopsy sentence, the checks as a 2-column checklist with severity | "{label}: {autopsy sentence}" |
| autopsy | RankList of causes with severity bars and evidence; click a cause to jump to its exhibit | "{top cause} explains most of the result" |
| cost curve | TimeSeries-style line of Sharpe against cost bps, with breakeven and current-cost annotations | "Breakeven at {x} bps; you pay {y}" |
| controls | Dumbbell: strategy vs each control, sorted, best control marked | "Beats the best control ({name}) by {Δ}" or "Loses to {name}" |
| shuffled | Distribution (histogram of permutation Sharpes) with a "you are here" marker and p | "Better than {pct}% of shuffled signals" |
| CPCV | Distribution strip of split Sharpes plus box; lens: path fan | "{share}% of purged splits are positive" |
| Monte Carlo | Ridge of the Sharpe and drawdown distributions with actual-value markers | "1-in-20 bad case: Sharpe {x}, drawdown {y}" |
| transfer | Slope chart from in-sample to each transfer test | "Holds {pct}% of its Sharpe out of sample" |
| plateau | Heat table with the baseline outlined and plateau/cliff contours | "Neighbouring settings keep {pct}% of the Sharpe" |
| DSR, PBO, MinBTL | Three gauge tiles with thresholds | "Deflated Sharpe {x} at {n} trials" |
| leakage | Checklist with badge | "No look-ahead found" |
| improve | Slope chart: unfiltered vs filtered vs sized, plus a variant table | "Filtering {helps/doesn't}: {Δ} Sharpe" |
| receipt | Mono receipt block with copy buttons, publish and load-settings actions | none |

### Purged CV for a model
- Sharpe spread: distribution with a median annotation. Takeaway: "Median path Sharpe {x}; worst {y}".
- Leakage gap: dumbbell from naive to purged (exists; restyle).
- Paths: TimeSeries fan with a train/test shaded span and end labels for best, median and worst.
- Fold matrix: heat table (train / purge / test) with hover syncing to the path chart.

### Improve my strategy
- Label scatter: hit-time strip by barrier, with annotations for profit-taking and stop-loss levels.
- Label mix: 100% bar with direct labels.
- Timeline: StackedArea of shares with direct labels and regime annotations.
- Sensitivity: heat table of the label mix across PT/SL, where clicking a cell reruns.
- Fixed vs scaled: dumbbell per label.
- Meta probability: histogram with the 50% line and a "confident calls" annotation.
- Coverage: line against target with a band for ±3% and a status chip.

### Alpha
| Output | Exhibit | Notes |
|---|---|---|
| ranking | RankList: rank, ticker (bold), sector chip, conviction bar, top 3 driver chips, Δrank sparkline; lens: by sector, treemap | Clicking selects the name page-wide |
| why this name | Waterfall v2, linked to the selection | grouped "n other features" |
| what changed | Slope chart from previous rank to current rank for movers; entered/exited chips | "3 names entered the top 10" |
| controls | Dumbbell or bar of IC and net Sharpe, model accented, controls slate; table below | "Model {beats/loses to} {best control}" |
| buckets | Bars of excess return with a monotonicity annotation; EW/VW tabs | "Top bucket earns {x} more than bottom" |
| net curve | TimeSeries with end labels (model accent, composite dashed), cost annotation | "{model} {beats/trails} the composite after costs" |
| SHAP beeswarm | Beeswarm top 12 with value colour ramp legend; lenses: importance RankList, families treemap | none |
| IC by month | Calendar heatmap (month × year) plus the mean; lens: bars | "IC positive in {k} of {n} months" |
| blend | Line of validation IC against LightGBM share, chosen point annotated | none |
| drift | RankList of drift with threshold tick and importance rank; retrain banner | "Retrain {recommended/not needed}" |

### Volatility & risk today
- **Risk today hero:** asset, regime pill, 3 horizon tiles with gauges, VaR/ES strip, size dial. Watchlist mode: a RankList of names by 1-month vol, with a regime pill and size per name.
- **Forecast panel:** TimeSeries with a forecast band, realised as faint dots, regime spans shaded, end labels.
- **Term structure:** slope chart across horizons, with the best model accented and others slate.
- **Tournament:** ranked heat table (exists); add a "wins" column bar and DM significance dots.
- **Calibration:** scatter v2 with the binned line and diagonal.
- **VaR/ES:** matrix (exists), plus a calendar heatmap of VaR breaches.
- **Sizing:** TimeSeries of growth for unmanaged, vol-targeted and half-Kelly with end labels.

### Market state
- **Probabilities:** StackedArea v2 in regime colours with direct labels ("Calm 62%") and event annotations at regime switches.
- **Transitions:** chord-style transition diagram or the heat table (exists) with a "typical stay" bar column.
- **Returns by state:** heat table (exists) plus a RankList lens of "most hurt by stress".
- **Does it help?:** TimeSeries growth for filtered, constant and unmanaged with end labels.
- **Spells:** a timeline ribbon of coloured spans (lens exists as a table and becomes a ribbon).

### Allocation
- **Weights:**
  - treemap by sector, then name (size weight, colour risk-minus-weight)
  - lens: RankList with whiskers (exists)
- **Trades:**
  - trade ticket table: side chip, now → target slope, value, shares, cost
  - "Copy as order list" action
- **Controls:**
  - growth TimeSeries with end labels and drawdown below (exists, restyle)
  - dumbbell of Sharpe
- **Rebalance log:** calendar strip, filled when it traded, plus gain-vs-cost bars on hover.
- **Clusters:** dendrogram linked to the correlation map with a cut slider (colours clusters).
- **Alpha views:** slope chart from prior to posterior per name, shown only when views exist.

### Strategy studio
- [ ] A pipeline diagram drawn as a live flow (nodes with status, edges carrying artifact ids). Clicking a node opens its page; each node shows its verdict stamp. *(partial: left-to-right flow at ≥1000 px with status per node; edges do not yet carry artifact ids)*
- [x] "Run the whole pipeline" button that chains the supported hand-offs, with current-stage progress and run status on the nodes. Alpha feeds Filter and Allocation; Allocation feeds Validate. Size runs independently. Stops on failure, absent artifacts, navigation, or an explicit stop; an already submitted run continues in Runs.

### Verified page
- [x] A public tear-sheet design: big stamp, hash ribbon, exhibits in print layout, and an "as of" watermark. *(stamp, hash ribbon, numbered findings, print layout)*

---

## 8. UX and features

- [x] **Run flow:** the progress bar becomes a stage timeline (Loading data → Features → Training → Validation → Explaining), streamed from the API stages. Skeletons are shaped like the coming exhibits. *(finished stages listed with their durations above the live progress bar)*
- [x] **Command palette (⌘K) actions:** run page, compare last two, jump to exhibit, open hand-off, publish, export PDF, switch universe preset. *(run page, printable report, jump to any exhibit; compare last two runs already present)*
- [ ] **Study panel:**
  - inputs grouped as Data · Model · Costs · Advanced, with live validation
  - preset universes as chips with counts
  - an "Explain this setting" popover for each input
- [ ] **Inspect panel:** shows the current selection (ticker, model, date, state) with every number about it from all exhibits.
- [ ] **Compare mode:** two runs side by side and overlaid; a KPI delta strip.
- [ ] **Empty, error and stale states:** each says why and what to do, with one primary action.
- [x] **Onboarding:** a 3-step coach on first visit (validate → rank → size), dismissible and remembered.
- [ ] **Accessibility:**
  - every chart gets `role=img` with a generated summary sentence (the takeaway)
  - tables are real tables
  - focus rings visible; colour never the only cue (patterns or labels too)
  - contrast at AA
- [x] **Responsive:** 360, 768, 1280 and 1600+ breakpoints via container queries. On phones, exhibits stack and the KPI strip becomes 2 columns. *(container queries; 2-column KPI strip on phones; checked at 375 and 1600)*
- [x] **Print and PDF tear sheet:** A4 and Letter, exhibit numbering, header and footer with run hash and date. *(Verified page print layout; per-page report via ⌘K or Report)*

---

## 9. Platform consistency (after ML)

- [ ] Port the tokens and chart kit v2 to Research (same workspace engine), then Portfolio, Studio and Screener.
- [ ] One shared `Exhibit`, `KpiStrip`, `RankList` and `DataTable v2` across all modules.

---

## 10. Engineering

**Structure**
- `src/workspace/tokens.css`
- `src/charts/v2/*` (one file per primitive plus `frame.tsx`, `readout.tsx`, `labels.ts` for collision-free direct labels, `annotations.ts`, `scales.ts`)
- `src/modules/ml/exhibits/*`: one file per page, each export one exhibit, all built from v2 primitives.

**Takeaway generators:** `src/modules/ml/takeaways.ts` holds pure functions from a result to a sentence, unit-tested with Jest on fixtures from real runs.

**Backend support (small):**
- `meta.events` (refits, regime switches, train/test cut)
- `meta.state_labels` (done)
- per-run stage names for the progress timeline
- per-name 63-day sparkline data for the ranking

**Performance budget**
- first exhibit painted in under 600 ms after the result arrives
- the whole page interactive in under 1 s
- hover at 60 fps (canvas above 5k points; memoised scales)
- payload under 300 KB gzipped per page; held-out tables lazy-loaded

**Quality gates (every page, before it ships)**
1. The rubric (§11) averages 4.5 or better, and no criterion is below 4.
2. Screenshot pass in dark and light at 1440 and 375.
3. Playwright visual baselines for the empty page and a result fixture (results replayed from saved JSON, so tests are deterministic).
4. Jest tests for the takeaway generators.
5. Typecheck (strict), lint at 0 errors, build, plus a Lighthouse accessibility score of 95 or higher.

---

## 11. Exhibit rubric (score 1–5)

1. **Answer first:** the title states the finding; you could stop reading there.
2. **Honest:** uncertainty is shown; controls and baselines are visible; nothing is cherry-picked.
3. **Legible:** direct labels, units, at most 6 emphasised series, no clipped text, numbers formatted by role.
4. **Context:** annotations for the events that explain the shape; scope in the subtitle; footnote with method.
5. **Interactive:** synced crosshair, selection and drill-down where they help, and nowhere they don't.
6. **Consistent:** tokens only; the same model has the same colour everywhere; same spacing and type.
7. **Robust:** empty, error, loading, 1 point and 10k points all look intentional.
8. **Accessible and responsive:** keyboard, screen-reader summary, AA contrast, phone width.

---

## 11b. Radar (added from the figures4papers reference)

- [x] **Radar:** every model on every metric, outward is better, model under test filled, raw values on hover (Alpha controls, Allocation controls).
- [x] **Semantic comparator tints:** pink for alternatives, green for related variants, grey for baselines; edged bars as in a printed figure.

**Still open:** hexbin and lasso on scatter, dendrogram linked hover, and a dedicated Slope primitive. Calendar and treemap now have real ML callers; their remaining variants are tracked above.


## Continuation checkpoint, 2026-10-13

The existing `ml-design-v1` tag predates this audit. It is preserved, not recreated or moved. The complete definition of done below has **not** yet been demonstrated.

Implemented in this continuation:
- Stacked areas: share/absolute lenses; normalized values consistently in labels, tooltips and Inspect; direct labels with collision spacing; sorted complete readouts with absolute totals; shared crosshair; keyboard dates; regime-switch annotations; finite epoch dates; one-observation rendering; memoized geometry.
- Calendar: month/year aggregation, explicit missing months, sequential counts and signed IC, accessible data table, SVG/PNG through the existing exhibit export. Used for monthly IC and saved-run activity. Weekday/time remains open.
- RankList: sorted magnitude, bold leaf labels, exact values, notes, optional deltas, top-N/show-all. Reused by feature families and SHAP importance. Sparkline support remains open.
- Treemap: allocation sector/name and feature-family lenses, breadcrumb, keyboard/click drill-down, Escape/right-click return, weight/risk area switch, signed risk-minus-weight colour, SVG/PNG through the exhibit. Additional colour-mode toggles remain open.
- Studio: sequential runner using existing APIs and each page's saved settings. Displays actual artifact IDs. No unsupported Filter → Size or Size → Allocation link is implied; those API contracts do not exist. Missing artifacts and failed jobs stop subsequent work. The pipeline is scoped to the open Studio page; navigating away stops future submissions.
- ML onboarding: validate → rank → size, dismissible and persisted separately from Research. Only completed studies count, not link clicks.
- Overview: recovery text replaces endless skeletons for expired results; saved-history activity includes a monthly count and linked recent runs.
- Ranking selection populates Inspect; Escape clears Inspect. This is not yet the complete page-wide selection contract.
- Fixed two pre-existing TypeScript test-mock references so strict typecheck can run without changing production behavior.

Validation commands are run from `frontend`:
```sh
npm test -- --runInBand src/modules/ml/__tests__/takeaways.test.ts src/modules/research/__tests__/research.test.tsx src/components/volatility-v2/__tests__/api.test.ts
npx tsc --noEmit
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 npx playwright test --config=e2e/playwright.research.config.ts --grep cinema --workers=1 --output=/tmp/ml-cinema-final
npm run build
```

The browser fixtures are explicitly synthetic contract fixtures, not saved investment results. They cover normalized keyboard readouts and screenshots in both themes at 375/1440, onboarding persistence, successful artifact chaining, missing-artifact stopping, treemap drill-down/size switching, calendar SVG export and expired-result recovery. They do not replace the requested real-run replay coverage on every page.

Remaining release gates and functionality include the full distribution family, weekday/time calendars, scatter binning/lasso, waterfall distribution drill-down, linked dendrogram cut controls, complete shared zoom/selection/compare behavior, table virtualization/TanStack requirements, backend event/63-day sparkline contracts, and the every-page real-fixture, accessibility, rubric and performance audit. Phase 12 remains a separate platform-port plan.

## 12. Execution order and checkpoints

| Phase | Work | Commit and checkpoint |
|---|---|---|
| 1 | Tokens, palette, type scale, canvas; borderless page shell; KPI strip v2; verdict v2 | `ml-design: tokens and shell` |
| 2 | Chart kit v2 core: Exhibit frame, Readout, TimeSeries v2 (direct labels, annotations, sync, brush), Bars v2, RankList, Dumbbell/Slope, Distribution | `ml-design: chart kit core` |
| 3 | Chart kit v2 rest: Heat table, Calendar, Treemap, Scatter v2, Waterfall v2, linked dendrogram, DataTable v2 (TanStack) | `ml-design: chart kit complete` |
| 4 | Takeaway generators and tests; `meta.events` backend; fixtures replayed from saved runs | `ml-design: takeaways and fixtures` |
| 5 | Validate and Purged CV pages, all exhibits per §7 | page checkpoint |
| 6 | Alpha page | page checkpoint |
| 7 | Volatility & risk and Market state pages | page checkpoint |
| 8 | Allocation and Improve pages | page checkpoint |
| 9 | Overview "Today" board, Strategy studio flow, Verified tear sheet, PDF print | page checkpoint |
| 10 | UX: run stage timeline, command palette actions, Inspect selection, Compare mode, onboarding | `ml-design: experience` |
| 11 | Quality sweep: rubric on every exhibit, light and dark, 375 and 1440, accessibility, performance budget, visual baselines | **tag `ml-design-v1`** |
| 12 | Port to Research (then other modules) | separate plan |

**Size:** roughly 8–10 focused sessions to reach `ml-design-v1`. Phases 1–4 are the force multiplier: once the kit exists, each page is mostly composition.

**Definition of done for `ml-design-v1`**
- every ML exhibit scores 4.5 or higher on the rubric
- no generic fallback views remain on any ML page
- all quality gates are green
- this document is fully ticked except Phase 12
