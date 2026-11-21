# Studio look plan (2026-11-21)

Goal: make Studio the best-looking page in ATLAS. It should be as calm as the Tessera dashboard and the JetBrains New UI, and more useful than either for writing and testing strategies. This plan replaces the visual parts of SHELL_POLISH.md.

## Sources read

- JetBrains New UI: the window header widgets, the tool window stripes, compact mode, editor tabs and gutter (jetbrains.com/help/idea/new-ui.html). Tool window icons are 20×20, or 16×16 in compact mode.
- Linear redesign part II: the "inverted L" of global chrome, sidebar alignment, LCH themes built from base, accent and contrast, and Inter Display for headings.
- VS Code UX guidelines: Activity Bar, Primary and Secondary Sidebar, Panel, and a Status Bar split into workspace items (left) and file items (right).
- Setproduct "Sidebar navigation, 16 patterns": the numbers in the table below.
- Vercel Web Interface Guidelines: hit targets of 24px or more, hover/active/focus with more contrast than rest, labels on icon buttons.
- Stripe navigation notes: dropdowns fade in over about 100ms and close immediately on leave.
- Dark elevation guides (UI/UX Atlas, Pegasus): in dark mode a raised surface is lighter than the one under it, with a 1px hairline where a shadow would disappear.
- Zed UI checklist and vision: if anything on screen is not code, it needs a reason.
- QuantConnect IDE: the backtest result is a destination of its own, not a cramped strip.
- Owner references: Tessera dashboard, a VS Code screenshot, and the TradingView Products menu.

## Reference teardown (looked at in the browser, 2026-11-21)

| App | What makes it look good | What we take | What we avoid |
|---|---|---|---|
| **PyCharm (New UI)** | Header is all widgets: project ▾, branch ▾, then run config ▾ ▶ 🐞 ⋮ on the right. Left stripe has a top group and a bottom group of 20px icons. Two tool windows stack in one column (Project above Agent Sessions). The status bar is a breadcrumb. | Header widgets; stripe groups; side windows that stack; breadcrumb status bar | The dense default tool-window chrome (title bars with five icons each) |
| **Cursor** | Warm near-black base with each panel one step lighter and a 1px hairline at about 6% white. 13px text with muted labels. A single warm accent on the one primary button. Numbered choices. | One accent only on the primary action; hairline panels; muted secondary text | Marketing gradients behind the app |
| **Linear** | The sidebar sits directly on the page background with no panel. Content is one raised panel with a large radius. Coloured glyphs appear only for projects and status. The header lives inside the panel (40px). | Sidebar on `--bg`, content raised; colour only as data; panel-owned header | Hiding everything behind hover |
| **TradingView Supercharts** | 38px single-row top toolbar. 44px drawing stripe grouped by thin separators. A right stripe of widgets opens the right panel. 30px range bar under the chart. Panels are separated by dark gaps instead of borders. | Gap-separated panels; right widget stripe; range bar as the chart footer; grouped drawing stripe | Icon-only everything (the right stripe has no labels anywhere) |
| **Tessera (owner pick)** | A light canvas with white cards. An 8px icon rail plus a labelled section sidebar (Home, Drafts, Your work with counts). Card headers 13px/600 with a small control on the right. Generous 16–20px padding. | Labelled sidebar with counts; card header pattern; padding | A third column of profile content |

The pattern all five share is that **only one thing is loud on a screen**. That is the content (code, chart, numbers). Chrome is quiet, a single shade, and grouped.

## What is wrong now (audit of `/studio/build`, `workspace.css`, `studio.css`)

1. **Two headers stacked.** `ws-top` (module menus, search, layout toggles, settings, theme) sits above `dv-bar` (Full tester, View, Simple/Dev, ⌘, ⋯, Save, Run). That is about 80px of chrome and two rows of controls with no clear owner.
2. **Four module menus side by side.** "Screener ▾ Studio ▾ ML ▾ Research ▾" reads like a website navbar. It competes with the breadcrumb and fills the header with places you are not working in. The owner's idea is better: one switcher for the module you are in, with every module's pages on hover. JetBrains (project widget), Vercel (team/project switcher) and Linear (workspace switcher) all do this.
3. **Cramped activity bar.** It is 30px wide, buttons are 28×30 with 1px between them, and icons are 15–17px. JetBrains uses a 40px stripe with 20px icons. Setproduct gives 56px for a labelled rail and at least 32px per target. Ours is below both.
4. **Mono everywhere.** Editor tabs, panel labels, the status bar and side bar headings are all set in mono at 11–12px. Mono belongs in code and numbers. UI text in mono looks like a terminal dump.
5. **Two style passes in one file.** `studio.css` styles `.dv-*` around lines 186–300 and then re-styles the same selectors from line 470 onward ("islands", radius, borders reset to 0). Every change has to be made twice, and the cascade decides who wins.
6. **No elevation system in the Dev view.** `--island`, `--panel` and `--line` are mixed with ad-hoc `color-mix(... 5%/6%/9%/15%)` values. Panels separate by luck, not by step.
7. **Chart side is crowded.** It stacks the drawing column, legend, trade badges, "Trades 7 All ‹ ›" strip and replay slider with 1x/2x/5x. That is three rows of controls under one chart.
8. **Status bar** is 24px, mono, and full of facts with no grouping: file, Ln/Col, errors, save state, warm-up, data range, engine, preview time and runs.

## Decisions

### 1. One header, inverted L (Linear, JetBrains)

The two headers merge into one 48px header. The left stripe and the header form the global chrome; everything else is content.

| Left | Centre | Right |
|---|---|---|
| ATLAS mark · **module switcher** "Studio ▾" · page tabs | Strategy widget: name, version, saved state ▾ | Search ⌘K · **Run widget** · layout · settings |

- **Module switcher:** one button showing the current module. It opens a 280px menu with the four modules, each with icon, name and a one-line purpose. Hovering a module opens a side flyout with its pages, so any page in any module is one hover and a click away. Timing: open after 150ms, keep open for a 300ms grace period, and use a safe triangle so a diagonal mouse move does not close it. Arrow keys work, as does Esc. The landing page uses the same switcher, so the header looks identical everywhere.
- **Page tabs:** the current module's pages sit in the header as text tabs (Build, Backtest, Optimise, Validate, Portfolio, Live, Chart). The active tab gets a 2px accent underline. Pages are switched more often than modules, so they get the cheap control.
- **Strategy widget** (like JetBrains' project widget): the strategy name plus a version chip. Its menu holds recent strategies, New, Duplicate, Versions and Save. The Save button goes.
- **Run widget** (like JetBrains' run widget): a primary "Run ▾" whose menu holds Run on SPY, Run on universe, Debug and Full test. While a run is going it becomes a progress ring with Stop. This replaces Run, "Full tester ▾" and the code-lens row's separate entry points.
- **The ⋯ menu** keeps View, Simple/Dev, layout presets and theme. The three layout-toggle icons stay as one segmented control.

### 2. Tool window stripes (JetBrains)

- Left stripe: 40px wide, 32×32 buttons, 20px icons with 1.5 stroke, 6px apart.
  - Top group opens side windows: Files, Search, Versions, Docs.
  - Bottom group, below a separator, opens the bottom panel: Tester, Problems, Console.
- The active button gets a filled 32px rounded square plus the accent icon colour. Hover shifts the surface by 4–6%.
- "Show names" option (right-click the stripe): 64px stripe with an 11px label under each icon. Off by default.
- The right stripe mirrors this for the chart side: Chart, Inspector, Trades. The chart's drawing tools stay inside the chart.

### 3. Surfaces and tokens (one system)

- Three dark steps, built from one base hue (Linear's method):
  - `--bg`: oklch 0.13 (page and gutters)
  - `--surface`: oklch 0.165 (panels)
  - `--raised`: oklch 0.20 (menus, popovers, tiles)
- Light theme mirrors them: 0.965, 1.0, 1.0 + shadow. It also gets a "light with light header" variant.
- Panels are inset islands: 8px gap on `--bg`, 10px radius, no borders inside. The only hairline is 1px `--line` under the header.
- Text: `--text` 0.95, `--text-2` 0.75, `--text-3` 0.58, `--text-4` 0.42. Hover, active and focus always raise contrast.
- Colour (owner, 2026-11-21: "no blue"): chrome is fully neutral, as in T3 Code and Cursor. Greys have zero chroma; selection is a white/black overlay; the primary button is the page inverted (white in dark, black in light). Colour is only data: P&L, chart series, errors. The editor uses JetBrains' Dark and IntelliJ Light syntax palettes.
- `studio.css`: the second pass (line ~470 onward) is folded into the first, so each `.dv-*` selector is defined once and reads tokens only. Target: under 450 lines from 558.

### 4. Type

- UI font is Geist Sans (already loaded): 13px/20px body, 12px secondary, 600 for headings. Mono (Geist Mono) is only for code, numbers, tickers and timestamps.
- Editor tabs: 36px high, 13px sans, file icon, close button shown on hover, a dot for unsaved changes.
- Panel tabs: 32px high, 13px sans.
- Side bar section headers: 12px sans, `--text-3`, sentence case (done in D5; carried here).

### 5. Editor (JetBrains gutter rules)

- Breakpoints sit over the line numbers. Fold arrows appear only on hover.
- The "Run on SPY | Run on universe | Debug" lens becomes 11px `--text-4`, with the run icon on hover only.
- The current line gets a 3% surface tint with no border.

### 6. Chart column

- A single 36px chart header: symbol ▾, timeframe, indicators, then layout and full-screen on the right.
- The drawing tools keep their 5 groups as a floating 36px vertical pill inside the chart (TradingView), not a column that takes width.
- A single 36px chart footer: replay controls on the left (‹ ▶ › · speed) and trade navigator on the right (Trades 7 ▾ ‹ ›). Today these are two rows.
- The legend stays top-left, with `--raised` at 80% behind it so it reads over candles.

### 7. Bottom panel: the Tester

- Tabs: Tester · Trades · Orders · Problems · Output · Console · Debug. Plots moves under Tester as a section.
- Tester = a 6-tile KPI row (Net P&L, Max DD, Win rate, Profit factor, Sharpe, Trades), each tile `--raised`, 12px label and 20px tabular figure. Under the row, the equity and drawdown curves in one 160px chart sharing an x-axis.
- If the panel is shorter than 220px, the tiles become one line of inline figures.

### 8. Status bar (VS Code split)

- 26px high, 12px sans, mono for the numbers only.
- Left (workspace): version and save state, then problems (errors and warnings), then the last run time and its result.
- Right (file): Ln/Col, data range, engine, then the runs badge.

### 8b. Two shells, one system

- **Build (IDE)** follows the PyCharm and TradingView model: panels as islands on `--bg`, separated by 6px gaps (no borders), a stripe on each side, and widgets in the header.
- **Lab pages** (Backtest, Optimise, Validate, Portfolio, Live, Home) follow the Linear and Tessera model. A labelled sidebar sits directly on `--bg`, with counts and run dots. Content is one raised panel with a 12px radius and its own 40px header (title, then filters and actions on the right). Cards inside use the Tessera header: 13px/600 title, `--text-3` subline, one control on the right.
- Both use the same header, tokens, type and menus, so moving between them feels like one product.

### 9. Beyond the references

- **Focus mode** (Zed's zen mode): ⌘⇧F hides both stripes and the bottom panel, leaving editor and chart. The header remains.
- **Run feedback in place:** after a run, changed KPI tiles show a fading ±delta for 3s (we already compute `delta`).
- **Layout presets** as thumbnails in the ⋯ menu: Code, Split, Chart, Test.
- **Motion:** 150ms ease-out for panels and menus, no motion when Reduce motion is on (the pref exists).
- **Compact mode** (JetBrains): the existing Density pref drops the header to 40px, the stripe to 32px and tabs to 28px.

## Responsive

| Width | Layout |
|---|---|
| ≥ 1280 | Everything above |
| 1024–1279 | Right stripe folds into the header; chart and editor split 50/50; inspector becomes an overlay |
| 768–1023 | Editor *or* chart (tab switch in the header); stripes stay |
| < 768 | Current mobile layout: bottom nav and sheets |

## Checklist (in order; screenshot after each)

- [x] L1 (neutral greys, inverse primary; full three-step rename open) Tokens: three surfaces, text steps and the accent, in `workspace.css`; Dev selectors read only tokens
- [ ] L2 Fold the second `.dv-*` pass in `studio.css` into one; same pixels, fewer lines
- [x] L3 One header: module switcher with hover flyouts, page tabs, strategy widget, run widget; `dv-bar` removed
- [ ] L4 Landing-page nav uses the same switcher (replaces the hover lists added in D0)
- [x] L5 Tool window stripe: 40px, 20px icons, top and bottom groups, Show names
- [x] L6 Type pass: sans for UI, mono for code and numbers; tab and status heights
- [x] L7 Chart column: one header, floating drawing pill, one footer (drawing pill stays as Vela's own column)
- [x] L8 (Sharpe tile open: needs daily returns, not trades) Tester tiles and equity-drawdown chart; Plots under Tester
- [x] L9 Status bar grouping
- [ ] L9b Lab pages: labelled sidebar on --bg with counts, raised content panel with its own header, Tessera card headers
- [ ] L10 Focus mode, layout preset thumbnails, run deltas, compact mode
- [ ] L11 Screenshots at 1440, 1280, 1024 and 390, dark and light (closes B-10)

Each step is done when it is verified in the browser with a screenshot, `tsc` is clean, the Studio tests pass, and the work is committed.
