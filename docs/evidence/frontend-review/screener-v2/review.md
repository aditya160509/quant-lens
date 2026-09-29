# Screener-V2 Frontend Review (brutal, read-only)

**Scope:** `frontend/src/components/screener-v2/customPagePrimitives.jsx` (583 lines) + `frontend/src/components/screener-v2/registry.js` (204 lines) + `frontend/src/app/labs/screener-v2/` (8 feature pages + home + layout)
**Standard:** Bloomberg SRCH / TradingView screener / finviz Elite
**Verdict:** competent dark-shell demo with a real API call path, but not yet a screener. No virtualization, no saved views, no column management, weak filter UX, keyboard/a11y gaps throughout.

## Score: 5.0 / 10

| Axis | Score | One-line reason |
|---|---|---|
| Table for large universes | 2/10 | `slice(0,160)`, no virtualization, silent column truncation |
| Filter UX | 4/10 | stacked text/number inputs, no operators, no filter chips, no count preview |
| Saved views / columns | 1/10 | `saved_screens` returns `[]`, nothing persisted, no URL state |
| Visual craft (vs TV/finviz) | 6/10 | coherent amber-on-black system, but boxy card grid + crosshair grid slop |
| a11y / keyboard | 3/10 | clickable `th` with no keyboard path, hover-only nav highlight, modal with no trap/Escape |
| Primitive vs registry sync | 6/10 | `pick()` + `fallbackKeys` works; one dead output (`saved_screens`); chartTypes mostly honored |
| Run/data wiring | 7/10 | `runScreenerV2Feature` with demo fallback is the best part of the file |

## Top 10 improvements (ranked)

1. **Virtualize the results table (TanStack Virtual + Table).** 4,000-row universes cannot render as raw `<tr>` with a 160-row guillotine. Server-side pagination + sorting, sticky header + sticky ticker column, overscan ~15, dynamic row heights. Concrete steal: TanStack Table virtualization guide (`useVirtualizer` against table rows, keep virtualizers near leaf components, never re-render full body on scroll).
2. **Real saved views: filters + columns + sort in URL + localStorage.** TradingView's Screens menu is the spec: Save / Make a copy / Rename / Export CSV / Recently used (5) / Open preset. Persist `{filters, columns, sort, top_n}` under a named key, mirror to search params for shareability. Delete the dead `saved_screens: []` output until it is real.
3. **Column management like TradingView.** Column-set presets (Performance / Risk / Valuation), `+` add-column picker, right-click move left-right / sort / remove / customize, show-hide toggles, CSV export of the *visible* column set. Today columns are `Object.keys(row).slice(0, 12|8)` (L372), silently dropping data with no control.
4. **Filter UX rebuild: operator-aware chips + count preview.** Replace the stacked label/input grid with a TradingView-style top filter panel: Add filter (grouped: security info / market data / technicals), per-filter operator (`>`, `<`, between, in sector), removable chips, live match-count estimate, Reset. Registry `sector` is freeform `text` (registry.js L13); make it multi-select with sector list. Numeric fields need min/max/step/unit labels (bps, %, $M).
5. **Kill the 160-row silent cap; add pagination + density + row affordances.** `filtered.slice(0, 160)` (L389) with only a `{n} rows` label is data loss disguised as a feature. Add paginated footer (25/50/100), compact/comfortable density toggle, zebra/hover that does not rely on color alone, pinned rank/ticker, row click-through to Quick-Look, `aria-sort` on headers.
6. **Keyboard + a11y pass (non-negotiable for Bloomberg parity).** `th onClick` needs `tabIndex`, `Enter/Space` handlers, `aria-sort`; nav rail needs `aria-current` instead of `onMouseEnter` activation; modal needs `role=dialog`, focus trap, `Escape`, return-focus; toasts for clipboard copy (currently silent `navigator.clipboard` writes, L329/L473); visible focus rings; 200% zoom + reduced-motion (`framer-motion` stagger/translate currently ignores `prefers-reduced-motion`).
7. **Fix the ⌘K dead affordance.** Both layouts render a `⌘K` kbd badge with zero handler. Steal cmdk: global `⌘K/Ctrl-K` palette with grouped results (features, saved screens, tickers, actions), fuzzy search, arrow-key nav + Enter, recent-first, empty state, footer hints. This single addition would do more for power-user speed than any visual polish.
8. **Heatmap + chart correctness.** Heatmap forces `min-width:700px` h-scroll (L576), alpha math `Math.abs(v)/100 || Math.abs(v)` (L435) conflates correlations (-1..1) with percentiles (0..100), no keyboard/text alternative. Add diverging scale with legend + domain switch, cell focus + tooltip parity, CSV fallback. Charts: fixed 340-360px heights with no empty state when `yKeys` is empty; add `ReferenceLine` for event anchors where relevant, tick formatters (%, $), and a real waterfall (cumulative) instead of a vertical bar chart wearing a waterfall label.
9. **Remove demo-data hazards before they leak.** `Math.random()` inside demo builder (L176 sharpe) re-randomizes per fallback render; `D1..D96` fake dates (L116), `${ticker} Corporation` (L99), sin-wave equity curves. Gate all demo paths behind an explicit `?demo` or `NODE_ENV=development` flag, label every demo surface "SAMPLE DATA" in UI, and freeze the seeded generator so screenshots are reproducible.
10. **De-silo the styles + share primitives with research-v2.** ~30 lines of global `styled-jsx` per file, hardcoded `Inter`/`JetBrains Mono` (no `next/font`), `cursor:crosshair` on every output (L572) which fights text selection, card hover `translateY(-1px)` layout jitter. Extract `DataTable / Heatmap / Tip / MetricDeck / SectionCard / Token system` to `components/data/` and theme both labs from one token file (see Sync plan).

## AI slop file:line

| Location | Slop |
|---|---|
| `customPagePrimitives.jsx:49` | `DEMO_TICKERS` 14 hardcodes + L99 `${ticker} Corporation`. Fake company names in a financial tool. |
| `customPagePrimitives.jsx:112-118` | `demoSeries` sin-wave equity curves with `D1..Dn` dates. Looks alive, means nothing. |
| `customPagePrimitives.jsx:176` | `Math.random()` inside a render-fallback path. Non-reproducible "sharpe". |
| `customPagePrimitives.jsx:297` | `onMouseEnter={() => setActive(section.id)}` on nav links. Hover-jacks the active section; keyboard users never trigger it. |
| `customPagePrimitives.jsx:324` | `transition={{ delay: index * 0.045 }}` stagger. Motion for motion's sake; replays on every mount, ignores reduced motion. |
| `customPagePrimitives.jsx:329,473` | Clipboard writes with zero feedback. No toast, no fallback for insecure contexts. |
| `customPagePrimitives.jsx:342` | Modal `inset:20px` div with no `role`, no trap, no `Escape`. |
| `customPagePrimitives.jsx:372,389` | `Object.keys(rows[0]).slice(0, dense?12:8)` + `.slice(0,160)`. Silent data amputation, twice in one component. |
| `customPagePrimitives.jsx:387` | Sort arrows as literal `"↓"/"↑"` text with no `aria-sort`. |
| `customPagePrimitives.jsx:435` | Heatmap alpha `Math.abs(v)/100 \|\| Math.abs(v)`. Two domains, one formula, both wrong somewhere. |
| `customPagePrimitives.jsx:519` | `{feature.shortTitle.toUpperCase()} <GO>` Bloomberg cosplay in the hero terminal. Decorative, non-functional. |
| `customPagePrimitives.jsx:541` | Home links `SCREENER_V2_FEATURES.slice(0,4)` then full grid below. Duplicated nav with no search. |
| `customPagePrimitives.jsx:572-573` | `.sv2-screen{cursor:crosshair}` + card hover lift. Hostile to selecting/copying values, the primary screener job. |
| `customPagePrimitives.jsx:576` | `.sv2-heat{min-width:700px}` forced horizontal scroll on laptop viewports. |
| `customPagePrimitives.jsx:141` | `saved_screens: []` demo + registry output `saved` wired to an always-empty table. A whole output card promising a missing feature. |
| `registry.js:13` | `sector` as freeform `text`. Should be multi-select from a controlled list. |
| `registry.js:47-49` | Booleans (`winsorize`, `sector_neutral`, `beta_neutral`) as `select [true,false]`. Should be checkboxes/switches. |
| `registry.js:65,82,96` | `strategy_perf_limit` / `pbo_trials` / `transaction_cost_bps` inconsistent naming + missing units in labels. |
| `app/labs/screener-v2/feature-*/page.js` | Eight 16-line wrappers duplicating `PAGE_SPEC` prose already in registry descriptions. No `metadata`, no `loading.js`/`error.js`. |
| `app/labs/screener-v2/layout.js:37-40` | Nav pills `font-size:0` hiding labels until hover-expand. Sighted keyboard users get `S01..S08` codes only. `⌘K` badge is dead. |

## Missing vs best (TradingView / finviz / Bloomberg SRCH)

| Best-in-class behavior | Screener-v2 status |
|---|---|
| TradingView Screens menu: save/copy/rename/export/recent/open presets | Missing. Only stub `saved_screens` table, always empty |
| TradingView filter panel: add filter, manual thresholds, reset, collapsible | Partial. Static grouped inputs, no operators/chips/count |
| TradingView table: column sets, + add, right-click move/sort/remove, chart-grid toggle | Missing. Auto-derived columns, no visibility/order control |
| TradingView auto-refresh (10s/1m/never) + watchlist handoff + alerts | Missing. Alerts feature exists but no refresh cadence or watchlist export |
| finviz one-click filter pills + template menu + heatmap treemap | Missing. Presets row exists (`sv2-presets`) but only per-number-field shortcuts |
| Bloomberg SRCH: keyboard-first, exportable, auditable criteria | Missing. No keyboard path, export is copy-JSON only on one card (F08 excepted) |
| TanStack-scale tables: virtualization, server pagination/sort, pinning | Missing. Client slice at 160 rows |
| cmdk palette (`⌘K`, fuzzy, recent-first, grouped actions) | Missing. Badge without handler in layout |

## Concrete steals (named, implementable)

1. **TradingView screener walkthrough** (`tradingview.com/support/solutions/43000718885`): five-component anatomy (switch menu, Screens menu, top filter panel, table, settings). Steal the Screens menu item list verbatim and the filter-panel add/edit/reset pattern.
2. **TradingView "Save your Columns & Filters"** (`tradingview.com/chart/BTCUSD/ivEla24B-...`): separate persistence of column layout vs filter set. Steal the split: views store `{columns}`, screens store `{filters}`, templates bind both.
3. **finviz screener charts/templates** (`finviz.com/blog/see-your-screener-results-w-fully-customizable-charts/`): template menu driving chart look/layout. Steal for the Quick-Look + bucket-distribution cards: one template switch, not per-card controls.
4. **TanStack Table virtualization guide** (`tanstack.com/table/v8/docs/guide/virtualization` + LogRocket TanStack Virtual walkthrough): `useVirtualizer` over table rows, overscan, sticky header, server-side sort/paginate for 100k-1M rows. Steal the "virtual indexes against the same data array" rule and infinite-scroll variant for universes too large to load.
5. **cmdk + uxtpatterns command palette** (`uxpatterns.dev/patterns/advanced/command-palette`, `cmdk` package): trigger/input/grouped results/item/empty-state anatomy, keyboard-only completion, focus order, `aria-activedescendant`. Steal recent-first ordering and the empty/loading/error triad for the palette.
6. **Koyfin/Gainify 2026 screener roundups** (`koyfin.com/blog/best-stock-screeners/`): "combine filters, customize results, save screens, reuse results in research workflows" as acceptance criteria. Steal as the definition of done for F01/F08: a screen must round-trip into research-v2 and export.

## Sync plan (screener-v2 ↔ research-v2)

Divergence is the headline: screener uses `#F5A400`/`Inter`, research uses `#e6ad36`/`DM Sans`+`IBM Plex Mono`; screener tables sort+search, research tables do neither; screener tracks active section via `IntersectionObserver`, research does not; screener `pick()` honors `fallbackKeys`, research `lookup()` drops them. Fix in this order:

1. **One token file** (`frontend/src/components/data/tokens.js`): accent, panel, border, text, mono/sans stacks via `next/font`. Both labs consume it; delete per-file `TOKENS`/`T` literals.
2. **One `DataTable`** (sort + search + pagination + virtualization + `aria-sort` + export CSV + column visibility). Screener adopts it first (has the richer call sites), research replaces `CompactTable` with it. Shared `fmt`/`numberLike`/`titleize` helpers move alongside.
3. **One `SectionCard` + `OutputNav`** (anchor ids, `aria-current`, IntersectionObserver active tracking, collapse/expand, dialog-based expand with trap + Escape, copy-with-toast). Port research `OutputCard`/`OutputRail` onto it; keep research's filterable rail as a prop (`filterable`).
4. **One `Field` kit** (text/number/select/chips/ticker-list/formula/json/date/file-path) with labels, units, validation, keyboard-correct listboxes. Eliminates registry mismatch class (booleans-as-select, freeform sector, number-without-bounds) in both registries.
5. **One run contract**: URL-synced form state, named saved views, `aria-live` status (`LIVE`/`PREVIEW`/`ERROR`), reproducible seeded demo behind `?demo`. Screener's `runScreenerV2Feature` try/fallback becomes the shared pattern; research's no-op `onRun` pages get real wiring or an explicit "not wired" state instead of a dead button.
6. **One ⌘K palette** across `/labs/*` (features, saved views, tickers, run/export actions). Removes both dead `⌘K` badges with a single implementation.
