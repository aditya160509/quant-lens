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

- [x] Outputs appear fast: Screen 1.26 s cold, 0.2 s warm through the job API (targets 3 s and 1 s)
- [x] Charts and bars load instantly: skeletons sized like the result, no blank flashes (cards hold their size while running; the pulse eases instead of blinking)
- [x] Precompute: snapshot packs and persisted Piotroski rows meet the targets; profiling shows no hot loop worth Rust
- [x] Table stays smooth at 1,000 rows: scroll 50 ms → 16.7 ms a frame (median, dev build). Causes: a keyed table with nothing stored got a new view object each render, which defeated every memo; the median footer re-sorted 1,000 values per column each frame. Rows now render once and are reused while scrolling
- [x] Interactions answer within 100 ms (click to painted frame, dev build): tabs 6–30 ms, card menu 64 ms, palette 63 ms

## Look and feel (from the photos)

- [ ] Fintrack-level finish: calm dark surfaces, one tone step between layers, tight type, pills with a pale tint
- [x] Realistic objects where they help: saved screens as rich cards with a mini result; filters read in plain words (Market cap ≥ 10B, ROIC ≥ 15.0%); cards no longer float mid-page
- [x] Section cards with a header row: title, tools and card menu; tables carry their count in the table bar (a second count in the header would repeat it)
- [x] Status pills in the trade's words (New, Dropped, Passed, Near miss, Moved, Held, Closed, Delisted) as pale tints in any status column
- [ ] Output that looks "magnificent, not dull": stronger hierarchy, colour on data only, one lead figure per card (Top name card `11d7bdd` replaces the raw quick-look dump)
- [x] Table output: cleaner headers, quieter coverage bars, sector pills calmer, ticker tiles refined, row hover and selection polished (`a70ced3`)
- [x] Remove the leftover blue accents on chrome (tabs, toggles) where they are not data (`a70ced3`)
- [x] Two search bars: kept both, they do different jobs. The top bar (⌘K) goes anywhere and runs any action; the table bar finds rows in that table
- [x] Light theme gets the same pass: white selected pills on grey tracks, glass follows the theme (`2ff7e33`)

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

- [x] Pinned board of outputs, in cards, drag to reorder (Overview; native drag, no library)
- [x] Chart settings on every card: "Chart settings" in the card menu opens columns, transform (log scale, rebase), range (1M to 5Y), a marked level with a note, one-colour series; time charts also draw trend lines, boxes and notes
- [x] Card actions: maximise, pin, width, reorder, hide, duplicate (a copy keeps its own view; Remove copy)
- [x] Crosshair on hover (linked across charts), click to drill (treemap to sector, ticker to quick look), brush to filter (drag-zoom on time charts; lasso on the scatter, then Filter to N selected)
- [x] Price chart: P/E mode (`/pe-history`), entry and exit marks from backtests (`7684e34`)
- [x] Compare up to 8 names: overlaid chart, side-by-side table, differences highlighted (`15748af`)
- [x] Full stock page with its own URL; PDF (`5d53ffb`: `?stock=XOM&view=full`)
- [x] Saved: cards with mini result, last run, change (`/screens/counts`, `/screens/changes`), schedule pill; rename, duplicate, tag, folder, search, sort, archive
- [x] More page: cards with header rows; markets as a segmented switch (crypto, forex, futures, hourly); plain English to formula; share links with Copy link and Embed; API keys with copy-once
- [x] Share page and embed in the same design: `/share/<token>` with the headline figures and the results table; `?embed=1` drops the header for an iframe
- [x] Plain-English filter box (`/nl-filter`) producing editable filters
- [x] Compare-to-field and sector-median filters in the editor; "held for N days"
- [x] Run progress by stage with cancel and a stale marker (stages `5d9bfaf`; cancel and stale marker already in FeatureView)
- [x] Relative Rotation Graph view (`/rrg`)
- [ ] Phone layout: bottom nav, filter sheet, card rows. Deferred; started and listed in `SCREENER_NEEDS_CHECK.md` (phone-1)
- [x] Pivot view for power users: in-house (Show as → Pivot: rows × columns, mean, median, sum or count, with totals). Perspective's WASM bundle is not worth it for this
- [x] Table benchmark at 1,000 rows: Screen run 3.1 s cold end to end; scroll 16.7 ms median a frame, 32 rows in the DOM
- [x] "Customised" marker listing what differs from default (`63af607`)

## Next
- [x] Liquid glass on popovers, menus, palette and runs pill (`a70ced3`)
- [x] Backtest: cold 10.4 s → 8.1 s, warm 14.2 s → 1.5 s. A plain score keeps one number per name per date across runs (~12 kB a date) instead of the ~0.8 MB panel, which overflowed the 256 MB cache and evicted itself. Also fixed: any backtest that ever held a name later acquired (K, Dec 2025) failed; a delisted holding now settles at its last close into cash, and one delisted before it can be bought is skipped
- [x] Screen cold run 1.76 s to 0.96 s, warm 0.11 s: Piotroski rows persisted per fundamentals version (`427c5f5`, `e31c425`)
- [x] Saved tags and folders; run cancel and stale marker (`985844e`)

## Research still to do

- [x] Pass over the listed UI libraries: all are paid Tailwind/shadcn block kits or motion toys; patterns already here (count-up headline, stat tiles under charts, period switchers, status pills). Nothing adopted as a dependency
- [x] vercel-labs/ui (now UI SDK, beta behaviour library): not adopted; native drag already covers the board. Radix stays

## Beyond what was asked (suggested)

- [x] Keyboard path for every action, in the palette: run, report, one-page PDF, compare with the previous run, copy run id, copy link, every section and exhibit, add filter, saved screens, templates, stocks
- [x] Empty, loading and error states designed per card (no "None." lines) (empty states `63af607`)
- [x] Visual baselines (screenshots) per page in dark and light: `npm run test:e2e:labs`, Saved and More added
- [x] Accessibility pass: every text token ≥ 4.5:1 on every surface in both themes (dim hint text ≥ 3:1); every control on the screener pages has a label; focus rings on all controls
- [ ] Same pass on Rank, Test, Monitor, Saved and More (done: Rank hero plots the raw blend, section bar no longer covers the title after a run, Monitor's fair-value watch no longer loops), then the other labs
