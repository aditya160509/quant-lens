# Portfolio V2 — Brutal World-Class Frontend Review

**Scope (read-only):** `frontend/src/components/portfolio-v2/customPagePrimitives.jsx` (2336 lines),
`frontend/src/components/portfolio-v2/registry.js` (167 lines),
`frontend/src/app/labs/portfolio-v2/page.js` + `feature-01..13/page.js` (13 thin wrappers).
**Standard:** Bloomberg PORT / TradingView / QuantConnect + institutional risk systems (VaR, frontier geometry, concentration).
**Verdict: 5.0 / 10.** Real engine breadth (13 output books, working run/compare/export shell) dragged down by
weak signature charts (frontier, waterfall, stress fan, network), fake decorative sparklines, arbitrary bar-width math,
and a registry/input mismatch that ships silently-dead presets and textarea-for-everything inputs.

---

## 1. Score justification

| Axis | Score | Note |
|---|---|---|
| Chart truthfulness (frontier, risk, concentration) | 3/10 | Frontier has no optimum markers; MetricTape/HeaderPulse sparklines are sine-wave fiction; bar widths use made-up scales |
| Layout / density vs PORT / TradingView | 5/10 | Competent 3-column terminal, but card-soup grids (`minmax(210px,1fr)` x6) instead of dense tables + sparklines |
| Scenario / compare flows | 4/10 | Split lane exists but shows duplicated content, no delta/diff view, hover-sync deliberately disabled |
| States (loading / empty / error / stale) | 5/10 | One global error banner, thin run-rail, generic empties, no skeletons, no stale-data badge after form edits |
| a11y / keyboard | 3/10 | Mouse-enter-only activation, icon buttons without labels, `th onClick` with no keyboard role, no live region |
| Primitive vs registry sync | 5/10 | Output books are thorough; input contract ignores registry types; presets patch nonexistent keys |
| **Overall** | **5.0/10** | |

---

## 2. Top 10 improvements (ranked by user-visible payoff)

1. **Rebuild `Frontier` as a real efficient-frontier chart.** Mark max-Sharpe, min-variance, and current portfolio;
   draw the capital-market line; distinguish efficient vs dominated points; hover a portfolio to read risk/return/Sharpe/weights.
   Steal: Riskfolio-Lib `plot_frontier` + Sharpe-optimal markers; PortfolioVisualizer frontier + tangent portfolio readout.
2. **Delete every fake sparkline or feed it real data.** `MetricTape` and `HeaderPulse` draw `sin()` polylines seeded by
   a scalar. Either pass trailing series through `summary_cards` or drop the SVG. A risk terminal that fabricates
   sparklines forfeits trust.
3. **Fix bar-width math in `AllocationStack`, `RiskContribution`, `ContributionWaterfall`, `FireSaleCascade`.**
   Widths like `abs(value)*100` break for shorts, leverage, and bps units; waterfall `marginLeft: abs(start)*10%` is not
   cumulative-proportional. Normalize against per-table max (vol-v2 `VolTable` already does `stats[col].max`) and add
   connectors + subtotal logic for a true waterfall.
4. **Give `StressFan` an actual fan.** It currently renders a histogram for `monte_carlo` output. Steal quantstats
   `plots.montecarlo`: percentile fan (5/25/50/75/95) + bust-probability + goal-probability header. Histogram becomes the
   secondary tab, not the whole story.
5. **Replace the circular `PortfolioNetwork` with a force layout + centrality sizing.** Node radius is `(i%4)*2`
   decoration; edge fallback `|| 0.2` invents edges. Vol-v2 already has a draggable SVG network; go further with d3-force
   (the vol landing page already imports it) and size nodes by DebtRank/centrality, width by weight, color by community.
6. **Make compare a real delta view.** Today the comparison lane renders the same cards with `activeId={null}` and a
   no-op setter, falling back to `compareData || data` (identical content pre-run). Add weight-delta bars,
   Sharpe/return/VaR delta header, and synchronized hover. quantstats `compare()` and PortfolioVisualizer side-by-side
   backtests are the bar.
7. **Fix the input contract.** `InputCurtain` renders every non-number field as a bare textarea, ignoring registry
   `tickers` type; there are no selects, no validation, no weights-parse preview. Port vol-v2's `TerminalAssetInput`
   token box + chip/select/token field renderers, and validate tickers/weights client-side before dispatch.
8. **Repair or remove the dead presets.** `PresetBar` patches keys (`objective`, `scenario`, `target_vol`, `regimes`,
   `simulations`) that do not exist on most engines' defaults, so clicks silently no-op. Make presets per-engine
   (declare them in `registry.js`) or delete the bar.
9. **Do the a11y pass.** Icon-only buttons need `aria-label`; rail/table headers need keyboard operability
   (`<button>` or `tabIndex`+Enter); replace `onMouseEnter`-only card activation with focus/hover parity;
   add `aria-live="polite"` to toast + run status; honor `prefers-reduced-motion` for the staggered card entrances.
10. **De-box the grids.** Six grids share one `repeat(auto-fit,minmax(210px,1fr))` card pattern (constraints, audits,
    scenarios, regimes, strategies, kill-switches). PORT shows these as dense sortable tables with status pills and
    inline bars. Collapse at least ConstraintBoard / AuditLedger / ScenarioDeck into vol-v2-style `VolTable` density.

---

## 3. AI-slop list (`file:line`)

`P` = `frontend/src/components/portfolio-v2/customPagePrimitives.jsx`, `R` = `registry.js`, `LP` = labs pages.

- `P:587` — `sparkPoints(Number(card.value) || index + 1)`: sine-wave sparkline fabricated from a scalar in `MetricTape`.
- `P:2107-2117` — `HeaderPulse`: same fabrication, seeded by row count.
- `P:2220-2225` — `sparkPoints()` itself: `sin(i*0.9+seed)` decoration presented as telemetry.
- `P:1251-1258` — `Frontier`: per-point rainbow `COLORS[i % 8]` + opacity ramp `0.35+(0.65*i)/n`; color encodes nothing.
- `P:1741-1744` — `Distribution`: rainbow cell per bar; `marker={0.5}` (`P:1092`, `BacktestPrimitive`) drops a
  `ReferenceLine x={0.5}` onto a categorical axis, meaningless.
- `P:1291` — `AllocationStack` width `abs(v)*100%`: breaks for |w|>1, shorts, bps; silent `slice(0,30)`.
- `P:1319` — donut center shows allocation *count*, not concentration (HHI/effective-N).
- `P:1332` — `RiskContribution` calls `data.sort()` in render, mutating props; `OVER BUDGET` threshold is naive `1/n`.
- `P:1407-1408` — waterfall geometry `marginLeft: min(70,abs(start)*10)%`, `width: abs(value)*10%`: arbitrary factors.
- `P:1480` / `P:1483` — network edge opacity/width fall back to invented `0.2`/`0` weights.
- `P:1493` — node radius `20 + (i%4)*2`: index decoration, not centrality.
- `P:1749-1760` — `StressFan` renders a histogram and three static zone labels; no bands, no VaR/CVaR markers.
- `P:595-614` — `PresetBar` hardcodes cross-engine patches for keys most engines lack (silent no-ops).
- `P:551-557` — `Hero` orbit decoration + 390px hero pushes the workbench below the fold; zero run state.
- `P:1357-1364` — `EquityAudit` audit-strip: three static labels with arrows, no gross-vs-net numbers.
- `P:868` — card activation on `onMouseEnter` only; `P:881-917` icon buttons have `title` but no `aria-label`;
  `P:2068-2079` sortable `th` is mouse-only.
- `R:134-153` — `f()` infers only `number/text/tickers`; no select/options/presets/groups, so the contract UI
  (`P:1023-1050`) can only render textarea/number and ignores its own `tickers` type.
- `LP:feature-*/page.js` — all 13 pages are identical 13-line wrappers; per-engine context (presets, help, defaults
  summary) lives nowhere.

---

## 4. Missing vs best-in-class

| Capability | Best-in-class reference | Portfolio-v2 status |
|---|---|---|
| Efficient frontier + max-Sharpe / min-var / CML | Riskfolio-Lib `plot_frontier`; PortfolioVisualizer optimizer | Missing: unlabeled scatter, no optimums, no CML |
| Tear-sheet narrative (returns, rolling Sharpe, worst drawdowns, monthly heatmap) | quantstats `reports.html` / `plots.snapshot`; pyfolio tear sheet | Partial: pieces exist (`EquityAudit`, `CalendarMatrix`, `FoldTournament`) but no unified tear-sheet order or rolling-Sharpe/vol panels |
| Risk contribution with constraints | Riskfolio-Lib risk-budget + RC constraint reports | Weak: naive 1/n flag, no constraint linkage to `constraint_report` |
| Stress fan + bust probability | quantstats `stats.montecarlo` + `plots.montecarlo` | Missing: histogram mislabeled as fan |
| Candlestick/OHLC + volume execution view | TradingView lightweight-charts | Missing: execution is line + bar-tape only |
| HRP/HERC dendrogram ordering on correlation matrices | Riskfolio-Lib clustering; `matrixShape` has no ordering | Missing: raw grid, static scale legend |
| Strategy comparison with deltas | quantstats `compare()`; PV side-by-side | Missing: duplicated lane, no deltas |
| Density control | vol-v2 `DensityToggle` + CSS vars | Missing: single `compact` flag only |

---

## 5. Concrete steals (adopt, don't admire)

1. **Riskfolio-Lib frontier plot** (`riskfolio-lib.readthedocs.io`): frontier curve + per-portfolio risk/return markers,
   Sharpe-optimal highlight. Rebuild `Frontier` (`P:1229`) around it; keep the `Interpretation` footer pattern.
2. **quantstats tear-sheet order** (`github.com/ranaroussi/quantstats`: `plots.snapshot`, rolling Sharpe/volatility,
   drawdown periods, monthly heatmap, `stats.montecarlo` with bust/goal probability): impose this section order on
   feature 02's book and copy the fan + bust header into `StressFan`.
3. **quantstats `compare()`**: one overlay + delta table for strategy A vs B. Template for the comparison-lane delta header.
4. **TradingView lightweight-charts** (`github.com/tradingview/lightweight-charts`): crosshair + magnet + Brush-style
   navigator for `TimeSeries`/`EquityAudit`; vol-v2 already uses `Brush` past 252 rows, portfolio has none.
5. **Vol-v2's own `VolTable`** (sort, microbars, `stats[col].max` normalization, cell search hits, density vars):
   replace `EvidenceTable` wholesale; it already solves the bar-width and density problems.
6. **Vol-v2's `TerminalAssetInput`** (BBG-style token strip): drop into `InputCurtain` for every `assets` field.
7. **Riskfolio-Lib HRP/HERC leaf ordering**: sort `Matrix` rows/cols by cluster order before render.
8. **Bloomberg PORT telemetry discipline**: every dial backed by a number + timestamp; delete or rewire the two fake
   sparkline call sites rather than shipping decoration as data.

---

## 6. Primitive-vs-registry sync plan (minimal, ordered)

1. Extend `registry.js f()` with vol-v2-style field descriptors: `{ key, label, type: number|text|tickers|select|tokens, options?, presets?, group?, helper? }`, plus per-engine `presets[]`. Single source of truth for inputs.
2. Rewrite `InputCurtain` to switch on descriptor type (port vol-v2 `VolField` + `TerminalAssetInput`); add weights-JSON
   parse preview and ticker validation; strip the cross-engine `PresetBar` in favor of per-engine presets.
3. Add a backend contract check: `PORTFOLIO_OUTPUT_BOOKS` keys asserted against a per-engine manifest
   (expected `charts.*`/`tables.*` keys); render `VolEmpty`-style "key not returned + available keys" instead of generic standby.
4. Unify tables: delete `EvidenceTable`, import the vol-v2 table pattern (sort + normalized microbars + density).
5. Unify networks: one draggable force-layout component shared by `PortfolioNetwork` and vol-v2 `NetworkGraph`.
6. Fix compare contract: comparison lane gets `{ baseline, candidate, deltas }` props and a delta header; remove the
   `compareData || data` silent-duplicate fallback (show an explicit "no comparison captured" empty).
7. Audit pass on shared helpers: `infer()`/`findKey()` key-guessing should warn (inspector lineage already shows
   `source.dataKey`) when heuristics pick surprising axes; never `sort()` props in render.

---

*Review method: static read of all files above, no edits made. Line numbers refer to the repo state at review time.
External benchmarks verified via web search/fetch on 2026-09-29 (quantstats GitHub, Riskfolio-Lib docs, TradingView
lightweight-charts repo).*
