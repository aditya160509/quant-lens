# ML UI issues

Logged 2026-11-08 from the owner's review of `/ml/alpha`. Log only; nothing here is fixed yet. Applies to the design pass and the shared kit.

Keep: chart and output quality. The owner rates it above almost every competitor. Issues below are the shell, layout and controls around it.

## Finish target

| Reference | Take from it |
|---|---|
| [Fintrack dashboard](refs/ref-fintrack-dashboard.webp) | Calm cards, compact header actions, tight grid, soft status pills, dense but quiet tiles |
| [Dashboard examples](refs/ref-x-dashboards.webp) | Filter chips, tidy tables, small inline sparks, restraint |
| [TradingView search](refs/ref-tradingview-search.webp) | Large overlay, tabs, type chips, logo rows, hover actions |

These set the level of finish. Learn from them; do not copy their look.

## AI-looking details

| # | Issue | Where |
|---|---|---|
| 1 | Coloured left bar on the verdict callout | [Alpha top](refs/ml-alpha-top.webp) |
| 2 | Left bar on the selected table row, same device | [Alpha top](refs/ml-alpha-top.webp), [controls](refs/ml-controls.webp) |
| 3 | Mono `EXHIBIT N` eyebrow above every title | All exhibits |
| 4 | Helper text in empty panels and captions ("Point at a specification...", "Hover any chart...", "click a name", "click any name in the ranking") | Inspect panel, ranking |

## Space

| # | Issue | Where |
|---|---|---|
| 5 | Rail, module sidebar and Inspect panel are all open, so the content gets about 60% of the width | Every page |
| 6 | Inspect shows placeholder text when nothing is selected, and Outputs is a long list of checkboxes | Right panel |
| 7 | Title, controls, verdict, KPIs and tabs take the first half of the screen before any exhibit | [Alpha top](refs/ml-alpha-top.webp) |
| 8 | "Why this name ranks here" ends early and leaves an empty column beside the long ranking | [Ranking](refs/ml-ranking-scrolled.webp) |
| 9 | Heatmap is cut off at the right edge ("Book to m"), with most features out of view | [Heatmap](refs/ml-explain-heatmap.webp) |
| 10 | Tall heatmap cells with three decimals limit how many rows and features fit | [Heatmap](refs/ml-explain-heatmap.webp) |
| 11 | Long gaps inside exhibits, such as the radar's half-empty column | [Controls](refs/ml-controls.webp) |

## Controls and navigation

| # | Issue | Where |
|---|---|---|
| 12 | No button or auto-close for panels; opening content does not make room for it | Sidebar, Inspect |
| 13 | Sticky bar lets page content show through behind it | [Ranking](refs/ml-ranking-scrolled.webp), [controls](refs/ml-controls.webp) |
| 14 | Sticky tabs overflow: "Next" shrinks to "N" and "Data" disappears | Same |
| 15 | Universe selector is a plain dropdown; it should be a proper picker | [Alpha top](refs/ml-alpha-top.webp) |
| 16 | Search is a small box, well below the TradingView reference | Top bar |
| 17 | "Period 21 · 3y · 5" cannot be read without knowing the model | [Alpha top](refs/ml-alpha-top.webp) |
| 18 | Each exhibit shows its own row of small actions (View, table, SVG, PNG, CSV, more, expand) | All exhibits |

## Text and data display

| # | Issue | Where |
|---|---|---|
| 19 | Tickers are title-cased in the heatmap: Ge, Googl, Jpm, t | [Heatmap](refs/ml-explain-heatmap.webp) |
| 20 | Raw feature names shown: Hl amihud 21, Mom 12 1, Dollar vol Mom | Ranking, Explain |
| 21 | Sector names truncate while the table has room elsewhere: "Communicatio..." | Ranking |
| 22 | Output label cut off: "The model against simple alternatives," | Outputs list |
| 23 | Heatmap has repeated labels ("Feature → Feature value", "Feature →") | [Heatmap](refs/ml-explain-heatmap.webp) |

## Status (2026-11-08, Screener design pass)

Fixed in the shared shell and kit: 1, 2, 3, 4, 6, 13, 14, 17, 18, 19, 20 (partly), 22. Not applicable on the Screener, not re-checked on ML: 8, 9, 10, 11, 21, 23. Open: 5 and 12 (absent on the Screener, where panels start closed), 7 (header and KPI block still about 40% of the first screen), 15 (universe is still a chip with a text field; the picker belongs to Batch 2 custom universes), 16 (search enlarged; type tabs and chips wait for Batch 3).
