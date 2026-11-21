# Studio shell polish (2026-11-21)

Next batch for the Build workspace. Sources: owner screenshots of `/studio/build`, reference dashboards (Tessera, Plunio, Acme CRM), the TradingView Products menu, and r/TradingView threads on the 2025 Strategy Tester redesign.

## Problems seen on `/studio/build`

1. **Three icon rails side by side.** App nav (Home, Labs…), the coloured lab rail (Screener, Factors, Volatility, PCA, Portfolio, Studio), and the Dev activity bar `nav.dv-icons`. About 20 icons before any content. The reference dashboards use one rail.
2. **The coloured lab rail adds nothing.** It's a module switcher that is always open, and you seldom need it while coding.
3. **Resize gutters are drawn as bars** (`.dv-gutter`, e.g. `#_r_37_`). In `studio.css:522` each one is a 1px `--workspace-edge` stripe with padding. The reference designs use no visible divider. The edge only appears on hover or while dragging.
4. **Full tester is crowded.** The editor, chart toolbar, chart, trades strip, replay bar and bottom panel all compete. The panels also have unequal padding and the chart toolbar column is doubled.

## Decisions

### D0. Top nav menus (app-wide)
- Each item in the top nav (Trade, Screener, Studio, ML, Research) opens a menu on hover or click instead of jumping straight to the page. TradingView's Products menu is the model.
- Each menu lists the item's sub-pages as icon + name rows, e.g. Studio: Home, Build, Backtest, Optimise, Validate, Live, Library. Clicking a row takes you to that page; clicking the item's own name still goes to its default page.
- The current page stays highlighted, so you always know where you are.
- The same top bar and menus appear on every page, including inside Studio, so the layout no longer changes completely when you switch module.
- Keyboard: arrow keys move through the menu, Esc closes it, Enter opens the row.

### D1. "Labs" menu replaces the coloured rail
- Remove the coloured lab rail.
- Add a **Labs ▾** button in the top bar, right after `ATLAS / Studio / Build`, modelled on the TradingView Products menu.
- The menu shows one row per lab: icon, name and keyboard number (⌘1–⌘6), grouped into Research (Screener, Factors, Volatility, PCA) and Build (Portfolio, Studio).
- ⌘K keeps working as the fast path. The menu exists for discovery.
- The name stays "Labs" (it already appears in the app nav). Alternatives considered: "Products" (sounds like a store), "Tools" (too vague).

### D2. One rail inside Build
- The app nav rail stays (Home, Labs, Settings).
- The Dev activity bar (`dv-icons`) is reduced to four items: Files, Search, Debug, Library. Inputs moves into Files as a section (it already shows there), and the Close (×) icon goes.
- The chart toolbar keeps its drawing tools, but in one column and collapsed to five groups (cursor, lines, shapes, text, measure). Each group opens a flyout, like TradingView.

### D3. Invisible gutters
- `.dv-gutter` becomes fully transparent at rest. It keeps a 6px hit area, the `col-resize` cursor and `:focus-visible` (accessibility).
- On hover or drag it shows a 2px accent line, centred.
- Panels separate by background (`--island` against `--bg`) and an 8px gap, the way the Tessera and Plunio cards do.

### D4. Full tester layout (W-8)
- Default layout: editor on the left, chart on the right, and below them the **Strategy Tester drawer**.
- The drawer opens on a **single summary view**: net P&L, max DD, win %, profit factor, trades and Sharpe, colour-coded, with an equity and drawdown strip. TradingView's 2025 move of these numbers into separate tabs was widely disliked, so they stay on one screen. Trades, Orders and Properties are secondary tabs.
- The replay bar moves into the chart footer. The trades strip under the chart goes, because the drawer covers it.
- Problems, Output and Console share one bottom tab group with the drawer, not a second panel.

### D5. Spacing and type (taken from the reference dashboards)
- Panel padding 16px, gap 8px, radius 12px. Section headers 13px/600 in sentence case, with no uppercase mono labels (`.dv-rail h4`).
- One accent colour. Status colour is used only for P&L and errors.

## Checklist
- [x] D0 Top nav menus on every page, same bar everywhere
- [x] D1 Labs menu in the top bar; coloured rail removed; ⌘1–⌘6
- [x] D2 Activity bar cut to four; chart toolbar grouped into flyouts
- [x] D3 Gutters invisible at rest, 2px accent on hover or drag
- [x] D4 Strategy Tester drawer with a single summary view (closes W-8)
- [x] D5 Spacing and header pass across the Dev workspace
- [ ] Screenshots at 1440 and 1024, dark and light (closes B-10)
