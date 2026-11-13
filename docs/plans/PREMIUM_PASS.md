# Premium pass: everything asked

Source: the owner's messages of 2026-11-13 (text, voice notes and screenshots). References: the fintrack dark dashboard (Yasir Noori), the CloseCRM-style light analytics board, the Northwind folder library (realistic folder icons), the Axion "Regressions" flow, Efferd CRM, and the libraries libraries.dev, pro.beui.dev, uiarc.dev, bencho.dev, boardui.com, affectui.com, kobra.systems, ui.watermelon.sh, vercel-labs/ui. Skill: design-taste-frontend (`references/app-screens.md`).

Goal: premium, finished, "liquid smooth". Every screen, output, default and alternative at its best. Fast.

## Done

- [x] First KPI value ("500") sat flush against the card edge (`e7c14d1`)
- [x] KPIs as one panel split by thin lines, larger numbers (`e7c14d1`)
- [x] Numbers out of monospace: text face with tabular digits everywhere; code stays mono (`e7c14d1`)
- [x] Sidebar icons: plain grey outline icons, no coloured squares, no blue left bar (`e7c14d1`)
- [x] Search field "AI blue" focus box replaced by a soft border (`e7c14d1`)
- [x] Date selector: calendar popover with quick picks instead of the native `dd/mm/yyyy` box (`e7c14d1`)
- [x] Filter chip (Beta etc.) closes on a second click (`e7c14d1`)
- [x] Buttons: top highlight, smoother hover, press scale; active chips neutral, not blue (`43a8e2e`)
- [x] Universe picker: presets no longer cut off; CSV upload is a button (`43a8e2e`)
- [x] Results panel collapsed to zero width on narrow windows (`527eb19`)
- [x] Table: find column, group by any column (numbers in quintiles); filter picker hides empty metrics (`527eb19`)
- [x] Backend hard items: saved-screen counts and changes, as-of, field vs field and vs sector median, held for N days, plain-English filters, run stages, P/E history, RRG (Haiku agent, `25f1679` to `5b87a39`)

- [x] Drawdown fills the full width, with grid, dates and hover readout (`6eb22cb`)
- [x] Daily returns histogram: one hue, red for the worst tail, neutral band (`6eb22cb`)
- [x] Rebalancing: offset, holding period and weekday variants as bars (best marked); turnover as bars over time (`6eb22cb`)
- [x] Holdings: P&L contributions as percent (`6eb22cb`)
- [x] Liquid glass (`@glass-sdk/liquid-glass`) on the results scroll, soft blurred top edge under the sticky bar (`6eb22cb`)
- [x] Nav icons as glossy colour tiles with white glyphs (`39dd894`)
- [x] Backend: repeated price reads cached; warm Screen 0.68 s to 0.27 s, backtest warm 8 s to 1.2 s, cold 21-58 s to 16 s (`eac80ed`)

## In progress

- [x] Alerts fail at the default 500 names; cap raised to 1,000 (`ec8b5fd`)
- [x] Speed: warm Screen run 1.44 s to 0.68 s by caching Piotroski rows (`be87568`). Cold still about 2.5 s; left: 54 separate Polars reads of prices (about 0.55 s), the close matrix (0.45 s), quick look (0.27 s), all needing the precompute
- [x] Trust "Near misses": no backend bug; the page now says no name misses by one filter (`7e20427`)

## Speed and performance

- [ ] Outputs appear fast: target a warm screen under 1 s and a cold one under 3 s (now about 0.8 s warm, 11 s cold)
- [ ] Charts and bars load instantly: skeletons sized like the result, no blank flashes
- [ ] Precompute daily indicators to Parquet (plan in `OPEN_ISSUES.md`), then Rust (PyO3) only for what profiling still shows
- [ ] Table stays smooth at 1,000 rows: scroll, hover, drag and column resize at 60 fps
- [ ] Interactions answer within 100 ms: chips, tabs, menus, the palette

## Look and feel (from the photos)

- [ ] Fintrack-level finish: calm dark surfaces, one tone step between layers, tight type, pills with a pale tint
- [ ] Realistic objects where they help, like the Northwind folder cards: saved screens and watchlists as rich cards with a mini result
- [ ] Section cards with a header row (icon, title, count, menu), as in the fintrack board columns
- [ ] Status pills in the trade's words (Passed, Near miss, New, Dropped) as pale tints
- [ ] Output that looks "magnificent, not dull": stronger hierarchy, colour on data only, one lead figure per card
- [x] Table output: cleaner headers, quieter coverage bars, sector pills calmer, ticker tiles refined, row hover and selection polished (`a70ced3`)
- [x] Remove the leftover blue accents on chrome (tabs, toggles) where they are not data (`a70ced3`)
- [ ] Two search bars (global and table): decide one pattern; the owner's call
- [ ] Light theme gets the same pass

## Motion ("liquid smooth")

- [x] Sidebar open, close and resize animate smoothly; no jank while dragging (toggles glide, drags stay 1:1)
- [x] Popovers, menus and the date picker open with a short scale and fade (`a70ced3`)
- [x] Tabs slide their active pill; page changes cross-fade (`a70ced3`; pages fade in)
- [x] Results enter staggered (heading, then figures, then table) once per run
- [x] Numbers count up on change; table rows flash on change (exists, tune) (`a70ced3`)
- [x] Every move has a reduced-motion fallback: the in-app Reduce motion switch. The OS setting no longer silences the app (it had switched off all workspace motion on this Mac)

## Icons

- [x] ~~One grey outline icon set~~ superseded: owner asked for colour; nav icons are glossy colour tiles (`39dd894`)
- [x] Product mark in the shell drawn for ATLAS, not a generic glyph (`985844e`)
- [x] Folder and file style icons for Saved, like the Northwind reference (`985844e`)

## Hard items still to build (frontend)

- [ ] Pinned board of outputs, in cards (drag to reorder; consider vercel-labs/ui or dnd-kit)
- [ ] Chart settings on every card: scale, range, colours, labels, benchmark, annotations (reuse existing settings)
- [ ] Card actions: maximise, pin, width, reorder, hide, duplicate
- [ ] Crosshair on hover, click to drill into rows, brush to filter
- [x] Price chart: P/E mode (`/pe-history`), entry and exit marks from backtests (`7684e34`)
- [x] Compare up to 8 names: overlaid chart, side-by-side table, differences highlighted (`15748af`)
- [x] Full stock page with its own URL; PDF (`5d53ffb`: `?stock=XOM&view=full`)
- [x] Saved: cards with mini result, last run, change (`/screens/counts`, `/screens/changes`), schedule pill; rename, duplicate, tag, folder, search, sort, archive
- [ ] More page: Markets tabs, hourly, plain English, share links, API keys
- [ ] Share page and embed in the same design
- [x] Plain-English filter box (`/nl-filter`) producing editable filters
- [x] Compare-to-field and sector-median filters in the editor; "held for N days"
- [x] Run progress by stage with cancel and a stale marker (stages `5d9bfaf`; cancel and stale marker already in FeatureView)
- [x] Relative Rotation Graph view (`/rrg`)
- [ ] Phone layout: bottom nav, filter sheet, card rows
- [ ] Perspective pivot view for power users
- [ ] Table benchmark at 1,000 rows
- [x] "Customised" marker listing what differs from default (`63af607`)

## Next
- [x] Liquid glass on popovers, menus, palette and runs pill (`a70ced3`)
- [ ] Backtest cold run: 13.5 s to 8.1 s (`285aa3e`); left: ~1,215 per-date snapshot reads (1.8 s) and one wide panel per date (~15 ms x 405). One snapshot file per run is a storage-format change: owner's call
- [x] Screen cold run 1.76 s to 0.96 s, warm 0.11 s: Piotroski rows persisted per fundamentals version (`427c5f5`, `e31c425`)
- [x] Saved tags and folders; run cancel and stale marker (`985844e`)

## Research still to do

- [ ] TinyFish pass over the listed UI libraries; adopt patterns, not dependencies, unless one clearly wins
- [ ] Decide on vercel-labs/ui (beta) for drag and drop only; Radix stays for menus and dialogs

## Beyond what was asked (suggested)

- [ ] Keyboard path for every action, shown in the palette
- [x] Empty, loading and error states designed per card (no "None." lines) (empty states `63af607`)
- [ ] Visual baselines (screenshots) per page so polish does not regress
- [ ] Accessibility pass: contrast 4.5:1, focus order, labels on icon buttons
- [ ] Same pass on Rank, Test, Monitor, Saved and More, then the other labs
