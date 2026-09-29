# Research-V2 Frontend Review (brutal, read-only)

**Scope:** `frontend/src/components/research-v2/customPagePrimitives.jsx` (319 lines) + `frontend/src/components/research-v2/registry.js` (160 lines) + `frontend/src/app/labs/research-v2/` (10 feature pages + home + layout; note: F10 absent)
**Standard:** QuantConnect research / Jupyter-like blocks / publication-grade tables
**Verdict:** the more ambitious of the two labs (regression, forest, spec-curve, QQ, regime, event-study, vitality, PDF), but ambition outruns honesty: fabricated standard errors, a dead Run button on every page, 11 registry chartTypes with no dedicated renderer, and tables that cannot even sort.

## Score: 4.0 / 10

| Axis | Score | One-line reason |
|---|---|---|
| Research-block UX (vs notebooks) | 3/10 | linear card stack, no cells, no run-all, no kernel/run status, no markdown notes |
| Statistical honesty | 2/10 | invented SE fallback (`0.22*|est|`), hardcoded p<.05 dichotomy, clamped QQ, mis-scaled gauge |
| Table / evidence inspection | 3/10 | 50-row cap, 8-col cap, no sort/filter/pagination, objects stringified inline |
| Visual craft | 6/10 | coherent descoped-origins aesthetic; forest/QQ/regime/event renderers show real range |
| a11y / keyboard | 3/10 | chip-row fake listboxes, mousedown-dismiss modal, zero-size nav labels, dead ⌘K |
| Primitive vs registry sync | 3/10 | 11 promised chartTypes collapse to generic line; `lookup` drops `fallbackKeys`; numeric-coercion bugs |
| Run/data wiring | 2/10 | pages pass no `response`/`onRun`; Run Study is a no-op; `CONTRACT READY` always green |

## Top 10 improvements (ranked)

1. **Make Run actually run (or say it cannot).** Every feature page renders `<ResearchV2Workbench featureId="NN" />` with no `response` and no `onRun` (feature-01, feature-06 pages). `run()` calls `onRun?.(payload)` which is `undefined`, so the button closes the curtain and does nothing. Wire the API call + loading/error/empty states with `aria-live`, or replace the button with an explicit "backend not wired" state. A dead primary button is the worst defect in either lab.
2. **Delete fabricated statistics.** `stderr ?? Math.abs(estimate) * 0.22` (L205) invents precision; `p < .05 ? "statistically reliable" : "review uncertainty"` (L207) hardcodes dichotomous thinking; QQ clamps to [-3,3] silently (L226); gauge maps any value<=1 to ×100 so a t-stat of 2.5 reads "WEAK" (L242). Show CI + stars + exact p, mark missing SE as "not reported", fix gauge domain per metric, and never synthesize uncertainty.
3. **Give every registry chartType a real renderer.** `ResearchVisual` L260 collapses `portfolioLadder, placeboRanking, regimeBars, rddPlot, scatterDiagnostic, breakScan, correlogram, treatmentTimeline, zooMap` (+ `decayCurve`/`coefficientCompare` via GenericChart) into generic line. An RDD without a cutoff line, a correlogram as a line chart, and a decay curve without log-x are wrong, not simplified. Either implement (RDD scatter + bandwidth + McCrary panel; stem correlogram; log-x decay with half-life marker; placebo rank plot; timeline with treatment shading) or remove the type from the registry until it exists.
4. **Notebook-ify the workspace: cells, not cards.** QuantConnect/Jupyter parity means interleaved markdown + code/param + output cells, per-cell run, run-all, execution order numbers, kernel-style status (idle/running/failed with elapsed time), collapsible cell inputs, and a decision ledger that reads like a lab notebook. Today F01 renders 16 outputs wall-to-wall with no narrative spine and no way to re-run one block. Steal Jupyter cell anatomy + QuantConnect's parameter/result separation.
5. **Replace `CompactTable` with the shared virtualized `DataTable`.** 50-row cap (L185), 8-column cap (L183), zero sort/filter, `JSON.stringify` for nested cells, `String(val ?? "-")` with no numeric formatting. For F01's 12-table book this is the evidence surface and it cannot sort. Adopt the same virtualized table as screener-v2 (TanStack Table + Virtual, server pagination, sticky header, CSV export, `aria-sort`), add regression-aware formatting (4-dec est, 2-dec t, 3-dec p, stars).
6. **Fix `chartData` numeric coercion: empty string becomes 0.** `number("")` is `Number("") === 0`, finite, so L81 coerces every `""` cell to `0` and corrupts charts (L75-86). Skip `null/undefined/""`, never coerce date-like strings, and keep `__x` out of `numericKeys`. The `buildPayload` numeric allowlist regex (L99) is the same bug class: new numeric registry fields silently stay strings until someone edits the regex. Derive coercion from `field.type` instead.
7. **Restore `fallbackKeys` + per-feature fallback parity with screener.** Screener `pick()` honors `section.fallbackKeys`; research `lookup()` (L70-73) ignores them, so backend key renames break research first. Unify on one `resolve(response, section)` helper. While there: `rowsFrom` (L58-68) returns `[]` for non-scalar objects without `rows`/`data` where screener falls back to `Object.entries` mapping; unify so section coverage does not silently vanish.
8. **Keyboard + a11y overhaul.** Select fields render as chip-row `<button>` groups (L140) with no listbox semantics or arrow-key nav; `ConfigCurtain` dismisses on `onMouseDown` (L149-150, hostile to screen readers and drag-selects) with no focus trap or Escape; layout strip labels are `font-size:0` until hover (layout.js L21); `⌘K` kbd is dead (layout.js L18); heatmap/regime/EventStudy expose `title` tooltips only. Concrete bar: real `<select>` or ARIA listbox, dialog-pattern curtain, `aria-current` rail, visible focus, `aria-live` run status, keyboard-reachable heatmap with data-table alternative.
9. **Performance: stop mounting 10-22 Recharts instances at once.** F01 declares 16 sections, all `ResponsiveContainer`-mounted on load; `content-visibility:auto` + guessed `contain-intrinsic-size:420px` only masks layout shift. Lazy-mount offscreen charts via IntersectionObserver, memoize `chartData`/`numericKeys`, paginate `DecisionLedger` (18-cap) and regression (20-cap) instead of silent slicing, move the per-card nested `<style jsx>` (PdfReport L276) to global, and `atob`-decode PDFs in a worker or on click only.
10. **Registry hygiene: fill F10 gap, fix auto-titles, document chartType contract.** Features jump 09 to 11 with no note; `section()` auto-titles from ids producing "GrS Test"-class capitalization; `inferChartType` regex order silently decides viz (`andrews_break_chart` → line, not break-scan; `decay_curve` → line, not decay). Add a `CHART_TYPES` manifest (renderer, required keys, empty state), exhaustively switch on it so unmapped types fail loudly at build time, and either ship F10 or rename 11→10 with a redirect note.

## AI slop file:line

| Location | Slop |
|---|---|
| `customPagePrimitives.jsx:46` | `RESEARCH_TICKERS` 16 hardcodes; `matches` uses substring `includes()` (L114) so query "A" matches half the list, sliced to 7 with no "+N more". |
| `customPagePrimitives.jsx:51-54` | `number()` treats `""` as `0`. Single most corrosive helper in the file. |
| `customPagePrimitives.jsx:79` | `__x` synthesized from 7 fallbacks (`date ?? month ?? period ... ?? #index`). Charts silently re-index when backend renames a key. |
| `customPagePrimitives.jsx:99-104` | `buildPayload` numeric allowlist regex. Registry-driven form, hand-maintained coercion list. |
| `customPagePrimitives.jsx:131` | Symbol menu subtitle `{ticker.includes("_") ? "digital asset" : "listed security"}`. BTC_USD is a "digital asset", SPY is a "listed security": taxonomy cosplay. |
| `customPagePrimitives.jsx:132` | `master`/`ff5_mom` sentinel note only when selection empty. Confusing exactly when user needs it least. |
| `customPagePrimitives.jsx:140` | Chip-row fake select: buttons with `.active` class, no `role=listbox`, no arrow keys. |
| `customPagePrimitives.jsx:143` | `file_path` is a text input with a folder icon. A fake file picker. |
| `customPagePrimitives.jsx:149-150` | Curtain closes on `onMouseDown` anywhere outside. Drag-select text, lose the form. Plus spring `stiffness:280 damping:28` bounce on a config panel. |
| `customPagePrimitives.jsx:185` | `rows.slice(0, 50)`, columns `.slice(0, 8)` (L183). Silent truncation with no "showing N of M". |
| `customPagePrimitives.jsx:189` | Every metric card stamped `Research output` + forced `.toFixed(3)` (counts, percentages, all). |
| `customPagePrimitives.jsx:205` | `stderr ?? Math.abs(estimate) * 0.22`. Fabricated uncertainty. |
| `customPagePrimitives.jsx:207` | `p < .05` ? "statistically reliable" : "review uncertainty". p-value theater. |
| `customPagePrimitives.jsx:221` | `<XAxis hide />` on spec curve. Distribution of estimates with no x labels. |
| `customPagePrimitives.jsx:226` | QQ hardcoded `min=-3 max=3` clamp. Out-of-range points pile on the frame edge. |
| `customPagePrimitives.jsx:233` | Regime ribbon `min 2%` segment width distorts small probabilities; keys filtered by `/index\|state\|date\|time/` can drop legit series. |
| `customPagePrimitives.jsx:238` | "t = 0" as a text badge; the chart itself has no `ReferenceLine`. The anchor is described, not drawn. |
| `customPagePrimitives.jsx:243` | Dead `r/circumference/offset` vars; gauge branch `score>66 SURVIVING / >35 DECAYING / else WEAK` with mis-scaled inputs. |
| `customPagePrimitives.jsx:271` | `anchor.click()` without DOM attach + sync `atob` on full PDF. Firefox-incompatible, main-thread-blocking. |
| `customPagePrimitives.jsx:276-278` | Nested `<style jsx>` inside `PdfReport`. Re-injected per render. |
| `customPagePrimitives.jsx:284` | `motion.article` re-animates (`y:16`) on every mount/filter change; no reduced-motion guard. |
| `customPagePrimitives.jsx:286` | `id={section.id}` anchors with no `scroll-margin-top`; sticky 52px topbar covers scrolled headings. |
| `customPagePrimitives.jsx:293` | Rail renumbers `01..NN` from the *filtered* list (numbers jump on typing); type icon from `source` only, so `regressionTable` shows a table icon and `publicationTable` likewise. Foot copy "Research-grade design" vs "Output contract mapped" is decorative. |
| `customPagePrimitives.jsx:300-303` | `CONTRACT READY` always green; study strip always shows `universe/signal/window` fallbacks ("research", "contract-bound"). Status that cannot be red. |
| `registry.js:1-8` | `section()` auto-titles from snake_case. Produces "Rdd Bandwidth Sensitivity", "Grs Test" class titles. |
| `registry.js:68-74` | Regex fallback order decides viz for unlisted keys; `waterfall` maps to a renderer research does not implement. |
| `registry.js:93-148` | F01 (16 outputs) through F09 promiscuously mix real and aspirational chartTypes with no renderer coverage matrix. |
| `registry.js:138-148` | Feature ids jump `09 → 11`. Missing F10 unexplained. |
| `app/labs/research-v2/feature-*/page.js` | Ten 3-line wrappers passing neither `response` nor `onRun`. The workbench is a display shell with a dead primary action. |
| `app/labs/research-v2/layout.js:18-21` | Dead `⌘K` kbd; strip pills `font-size:0` + hover-expand `translateY(-7px) scale(1.07)` jank. |

## Missing vs best (QuantConnect / Jupyter / publication)

| Best-in-class behavior | Research-v2 status |
|---|---|
| QuantConnect research: parameter cells → run → versioned outputs, data-loader defaults | Partial. `ConfigCurtain` mirrors backend contract; but run is no-op and `file_path` is a raw text box |
| Jupyter: interleaved markdown/code/output cells, execution counts, run-all, kernel status | Missing. Linear output stack, all-mounted, no per-cell run or order |
| Jupyter: rich display (LaTeX tables, inline plots with zoom/pan, dataframes with sort) | Partial. Recharts line/area/bar + custom QQ/forest/spec-curve; tables cannot sort; LaTeX is a string dump |
| Publication flow: spec grid → forest → journal table → PDF bundle with manifest | Partial. F06 has the parts (`specification_grid`, `publication_table`, `journal_table_bundle`, `pdf_report`) but `publicationTable` renders as `CompactTable` and PDF decode is fragile |
| Multiple-testing discipline (Harvey-Liu-Zhu t>3, spanning, zoo positioning) | Declared (F11) but `zooMap`/`regimeBars`/`placeboRanking` render as generic line |
| Falsification suite with power + verdict calibration | Declared (F03) with `falsification_verdict` → `MetricDeck`; no calibration display |
| Diagnostic center with residual/QQ/correlogram/heterosked/breaks | Best section (F05 renderers exist) but correlogram/scatter/break-scan collapse to line |
| Provenance: seed, data vintage, run hash, code version per result | Missing. No run metadata surface at all |

## Concrete steals (named, implementable)

1. **QuantConnect research notebooks** (`quantconnect.com/docs/v2/lean-cli/research`, `github.com/QuantConnect/Research`): parameter-first cells, data-loader defaults, run-and-keep-outputs. Steal the cell contract: `{markdown | params | output}` with per-cell status and elapsed time; keep `signal_csv_path`/`event_csv_path` loader-default semantics but show resolved dataset + vintage.
2. **Jupyter cell anatomy** (execution count, run-all/restart, `%%` magics, rich MIME output): steal per-block Run, Run-all-above/below, collapse input, and "N of M cells computed" progress. This replaces the current all-or-nothing dead Run.
3. **TanStack Table + Virtual** (`tanstack.com/table/v8/docs/guide/virtualization`, LogRocket walkthrough): steal virtualized rows, column visibility/ordering/pinning, server-side sort/pagination for `CompactTable` replacement; keep regressionB formatting (est 4-dec, t 2-dec, p 3-dec + stars) as column defs, not inline ternaries.
4. **cmdk palette** (`uxpatterns.dev/patterns/advanced/command-palette`, `cmdk`): steal the one-command surface both labs lack: `⌘K` → features, output sections (deep-link scroll), recent studies, Run/Export actions, ticker jump. Fixes both dead `⌘K` badges at once.
5. **TradingView table idioms** (column sets, `+` add-column, right-click move/sort/remove, CSV export): steal for F06 publication tables: visible-column = exported-column, journal style (`finance/aer/jfe/rfs`) as a column-set preset, not a select that changes nothing visible.
6. **Publication-table tooling** (stargazer/`modelsummary` print conventions): steal coefficient rows `{term, est (se), t/z, p, stars}`, model-summary footer (N, R2/adj-R2, SE type + lag, FE), and appendix grid. Current `RegressionTable` header (TERM/ESTIMATE/T-Z/P-VALUE/INTERPRETATION) is close; add SE column, stars, CI-on-hover, and exact-p display instead of the verdict slogan.

## Sync plan (research-v2 ↔ screener-v2)

Same six steps as the screener-v2 review, research-flavored (single source of truth, implement once):

1. **One token file** — delete `T` literal; consume shared `tokens.js` (accent, panel, border, mono/sans via `next/font`). Research keeps its olive-amber identity as a theme variant, not a fork.
2. **One `DataTable`** — replace `CompactTable` everywhere; screener's sort/search/pagination/virtualization/CSV/`aria-sort` come free. Regression/publication views become column-def presets on top, not separate components.
3. **One `SectionCard` + `OutputNav`** — adopt screener's IntersectionObserver active-tracking + dialog expand (trap + Escape + return-focus) + copy-with-toast; keep research's filterable rail as `filterable` prop with stable (unfiltered) numbering.
4. **One `Field` kit** — real selects/listboxes, bounded numbers with units, ticker-list with validation + "+N more", honest file-path field (server file browser or validated path with existence check). `buildPayload` coercion derives from `field.type`, killing the regex allowlist.
5. **One run contract** — URL-synced params, named studies, `aria-live` status with real error/empty states, seeded reproducible demo behind `?demo`. Research pages get actual `onRun` wiring; `CONTRACT READY` becomes a live indicator or is removed.
6. **One ⌘K palette** across `/labs/*` — features, sections, saved views/studies, tickers, run/export. Single implementation deletes both dead badges.
7. **Renderer coverage gate** — `CHART_TYPES` manifest + exhaustive switch; CI fails on unmapped registry chartTypes so the next aspirational type cannot silently render as line. Backfill in order: `rddPlot` → `correlogram` → `decayCurve` → `placeboRanking` → `regimeBars` → `zooMap`/`treatmentTimeline`.
