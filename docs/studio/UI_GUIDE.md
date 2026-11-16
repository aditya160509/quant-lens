# Studio UI guide

How every Studio screen is laid out, spaced, typed and charted. Studio is an operator tool (closer to Linear, Bloomberg and TradingView than to a landing page): dense, calm, data first. Check every screen against this file, alongside `CODE_STANDARDS.md` §8.

Sources: Tufte (data-ink, sparklines, small multiples), Cleveland (banking to 45°), Refactoring UI (Wathan, Schoger), Linear's 2024 and 2026 redesign notes, Matt Ström-Awn and Planetary on data tables, setproduct's chart guide, Stripe Apps chart layout, Elastic panel sizing, the ui-craft dense-dashboard rules, QuantConnect and TradingView editor layouts.

## 1. Principles

1. **Show data first.** Every pixel is data or helps read data. Erase what doesn't (Tufte: maximise data-ink, erase non-data and redundant ink).
2. **One question per block.** Each card answers one question; its title is the question's answer or its subject, not a slogan.
3. **Content beats chrome.** The sidebar and headers are a few notches dimmer than the work area (Linear 2026). Chrome never uses the accent colour except for the active item.
4. **Fewer borders.** Separate with space first, a background step second, a 1px border last. Borders quietly multiply; audit them (Linear, Refactoring UI).
5. **Hierarchy by weight and colour, not size alone.** Primary text, secondary grey, tertiary lighter grey. Two weights only: 400–500 and 600.
6. **Nothing repeated.** One headline per screen. If the hero says it, the card below doesn't.
7. **Colour means something.** `--up`, `--down`, `--warn`, `--accent` encode data or state. No decorative fills, gradients, glows, coloured edges, or icons in tinted squares.

## 2. Spacing

- **Scale:** 4 / 8 / 12 / 16 / 24 / 32 / 48. Never 5, 7, 9, 10, 14, 18 (ui-craft dense rules, 8pt grid).
- **Inside a card:** 16px padding (dense), 24px only for the hero.
- **Between cards:** 16px gap in a grid; 24px between sections; 32–48px only between page-level regions.
- **Inside a toolbar or row of controls:** 8px gap; controls 32–36px tall.
- **Table cells:** 12px horizontal, 8px vertical (row height 32px; 28px dense; 40px comfortable).
- **Label to value:** 4px. Title to body: 8–12px.
- **Related things sit closer than unrelated things** (proximity carries grouping, so you need fewer borders).
- **Page gutter:** 24px desktop, 16px phone. One pair of equal outer margins at every width.

## 3. Type

- **Family:** one sans for UI (Inter or the app's own), one mono for code and identifiers (JetBrains Mono).
- **Sizes:** page title 18–20px / 600; section title 14–15px / 500–600; body 13–14px; dense table 12–13px; caption 11–12px. Hero figure 40–56px / 600 with tabular figures and slight negative tracking.
- **Line height:** 1.4–1.5 for body, 1.2 for titles and figures.
- **Numbers:** `font-variant-numeric: tabular-nums` on every number (tables, cards, axes, tooltips, timestamps). `slashed-zero` on IDs and hashes.
- **Same decimals per column.** Units once (in the header or the first row), not on every cell.
- **Never** grey text on a coloured background; never weights under 400 for small text (use a lighter colour instead).

## 4. Layout

- **Shell:** an inverted L of chrome (sidebar 200–240px, dim; top bar ~44px) holding the work area. Sidebar never full-dark against a light body.
- **Grid:** 12 columns, 16px gutters. Common spans: 12 (time series, wide heatmaps, tables), 7/5 (main chart + its numbers), 6/6 (two comparable views), 4/4/4 (KPIs or small multiples).
- **Reading order:** F-pattern. Most important at top-left: hero figure → headline numbers → primary chart → detail tabs.
- **Hero:** one big figure (the answer), one line under it, the primary chart beside or below. No second line repeating the headline.
- **KPI strip:** 4–5 numbers max, each with label above (12px grey) and value below (20–24px, tabular). Change since last run in small text under it, coloured only by direction.
- **Tabs:** for sections of a long result. The tab bar sticks under the header on scroll.
- **Inspector / form:** a right or left column 280–340px; closed by default when the run strip already shows the key inputs.
- **Empty, loading, error, skipped:** every card has all four. Skipped says why in one plain line ("needs at least eight settings"). Loading keeps the card's final height (skeleton), so nothing jumps.
- **Phone (390px):** one column, cards full width, tables become label-value rows, charts keep at least 200px height, controls 44px tall.

## 5. Charts

### Choosing the form (by the question)

| Question | Form |
|---|---|
| How did it move over time? | Line (area only for one series from zero) |
| How are values spread? | Histogram (bin width stated), strip/beeswarm for under ~200 points |
| Do two measures move together? | Scatter, 1:1 aspect, both axes labelled with units. Never dual-axis lines |
| Which is bigger? | Horizontal bars sorted by value, zero baseline, value at bar end |
| Where does a value sit in a grid of two parameters? | Heatmap, single-hue sequential (diverging only around a real zero), values printed when cells are few |
| Part of a whole over time? | Stacked area, 4 layers max, labels inside layers |
| Clusters or hierarchy? | Dendrogram or treemap with labels only on tiles big enough |
| A score against a bar? | Gauge or bullet bar with the threshold drawn |
| Prices | Candles only when bodies stay ≥ 6px wide; otherwise a close line |

### Size

- **Aspect:** bank to 45° (Cleveland). The typical slope should sit near 45°: wide and short for long time series, square for scatter.
- **Heights:** primary time series 260–320px (hero chart up to ~360px); secondary charts 200–240px; inline sparkline 24–40px tall, 80–120px wide; heatmaps sized by rows (28–32px per row).
- **Widths:** time series and heatmaps span 12 or 7 columns; distributions and scatters 5–6 columns; never a chart under ~320px wide on desktop.
- **Minimum:** if a chart can't get 200px height and 320px width, show a table or a sparkline instead.

### Ink

- **Direct labels at line ends** instead of a legend when there are four series or fewer. More than four: colour 1–3 that matter, the rest grey (`--text-4`).
- **Gridlines:** horizontal only, faint (`--line-2`), or none when labels sit on the data.
- **Axes:** 4–6 ticks, formatted with units (`%`, `$`, `x`). Bars start at zero; lines may not.
- **Reference lines:** dashed, one label, for the thing being compared (benchmark, 0, threshold, "yours").
- **Highlight one thing.** The strategy in accent, everything else muted; the best of many bold, the rest thin.
- **No 3D** except an opt-in surface view; no gradients under noisy lines; no drop shadows on plots.
- **Tooltips:** crosshair with every series' value at that date, tabular numbers, the date as the title.
- **Small multiples** over one crowded chart when comparing many series (one shared scale, same size, same order).
- **Caption:** one line under the chart for what a number means (median, central 90%, share above 0). No caption that repeats the title.

## 6. Tables

- **Align:** numbers right, text left, headers follow their column, nothing centred.
- **Figures:** tabular, same decimals within a column, units in the header.
- **Rules:** horizontal hairlines or zebra, not both; no vertical rules when columns are aligned.
- **Headers:** short; sortable; sticky on scroll.
- **Rows:** 32px default; hover tint; selected row = ~6% accent tint plus a 2px accent left edge.
- **Inline sparklines** for a row's history; status as a short word with a coloured dot, not a coloured cell.
- **Median / total row** at the bottom when it helps, visually separated.
- **Long tables:** search, column toggle, and virtual scroll past ~200 rows.

## 7. Code editor (Build › Python and Formula)

Modelled on VS Code, QuantConnect's IDE and TradingView's Pine editor.

- **Layout:** editor in the main column at least 60% of the width (or full width with results below). Results/problems panel docked bottom, resizable, 30–40% height, tabs: Problems · Output · Results. Outline and templates on a side rail, collapsible.
- **Editor box:** min 420px tall, grows with the window; no outer padding fighting Monaco's own; 1px border, 8px radius.
- **Font:** JetBrains Mono (fallback `ui-monospace`), 13px, line height 1.5 (~20px). Line numbers dim. Ligatures off by default.
- **Monaco options:** minimap off, `scrollBeyondLastLine` off, `renderLineHighlight: "line"`, `automaticLayout` on, tab size 4 for Python, bracket-pair colours on, folding on, sticky scroll on for long files.
- **Theme:** follows the app theme (`vs-dark` / `light`), with the app's background so the editor sits in the page, not on top of it.
- **Feedback in place:** errors and warnings as squiggles with hover text; gutter markers; a status line (line:col, errors, warnings, saved/unsaved). Runtime errors jump to the line.
- **Completion:** `ctx.` members with type and one-line docs; formula catalogue inside `ctx.value("`; snippets for the common shapes.
- **Keys:** ⌘S save (formats), ⌘↵ run, ⌘⇧P command palette, ⌘/ comment, ⌥↑↓ move line. Show shortcuts in the palette, not as helper text.
- **Formula mode:** one line per rule, monospace, syntax colour for functions, numbers and fields; inline result chip (true share, last value) beside each line.
- **Split view:** code left, live preview (chart or trade list) right when the window is wider than ~1280px; stacked below that.
- **Diff:** side-by-side for version compare, with each version's run result above it.
- **Never** a code editor inside a small card, a fixed tiny height, or a toolbar of icon buttons with no labels.

## 8. Colour and theme

- Tokens only (`--bg`, `--panel`, `--line-2`, `--text`, `--text-2..4`, `--accent`, `--up`, `--down`, `--warn`). Light and dark both defined.
- Surfaces step by elevation (background → panel → popover) through small lightness changes, not shadows. Shadows only on floating layers (menus, dialogs).
- One accent. Up/down colours are colour-blind safe and always paired with a sign or word.
- Contrast: body text ≥ 4.5:1; large figures and chart strokes ≥ 3:1.

## 9. Motion

- 120–200ms ease-out for hover, open and tab change; no motion on data that is being read.
- Progress shows real stages ("walk-forward 40%"); partial results render as they arrive (the sweep map fills in).
- Respect `prefers-reduced-motion`.

## 10. Copy

- Titles are nouns or answers ("Walk-forward matrix", "Shocks"), not taglines.
- Numbers carry the message; words explain only what a number can't ("left of 0 = overfit").
- Buttons start with a verb ("Run validation"). Skipped and error states say what to do.
- No marketing words, no exclamation marks, no "insights", "powerful", "seamless".

## 11. Review checklist for a screen

- [ ] Spacing only from the scale; consistent card padding and gaps.
- [ ] One hero figure, one headline, nothing repeated.
- [ ] Every number tabular, right-aligned in tables, with units once.
- [ ] Each chart is the right form, at least 200×320px, banked near 45°, direct labels or a short legend, one highlighted series.
- [ ] No decorative colour, gradient, glow, tinted icon square or coloured edge.
- [ ] Borders audited; chrome dimmer than content.
- [ ] Empty, loading, error and skipped states present and sized.
- [ ] Editor screens meet §7.
- [ ] Checked at 1440 and 390px, light and dark, with real data, console clean.
