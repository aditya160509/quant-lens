# Outputs v2: fewer, bigger, cinematic

Date: 2026-11-13. Status marks: [ ] open, [x] done. Owner wants outputs that feel premium and worth paying for, not 40 equal cards.

## 1. What people pay for and ask for (research, 2026-11-13)

Sources: r/ValueInvesting threads "what tools do you wish existed" (2025-06) and "your perfect stock screener" (2026-09), "is there a reason to pay for a screener" (2025-04), r/fintech "screener where the best companies rise to the top" (2025-08), Stock Rover compare pages (2026-08), Koyfin and Investopedia 2026 roundups.

| Signal | What they said | What it means for us |
|---|---|---|
| Analysis paralysis | "50 sliders and zero direction... ingredients with no recipe" (top comment) | Lead with investor lenses, not sliders |
| Lenses and overlap | Screen "through Buffett's eyes, Graham's eyes, dividend safety"; "the overlap where a name passes two or three philosophies" | New output: Lens overlap |
| Valuation vs price | "Compare price with an automatic valuation across the whole set, then dig only into the interesting ones" | New output: Price vs fair value strip |
| Long history | ROIC 5y and 10y averages, CAPE per stock, 20 to 30 year history (Stock Rover, GuruFocus sell this) | Show history depth in the drawer; say plainly where ours stops (2021) |
| Red flags | "Insights on extreme points: debt jumps, net income drop in one quarter, short float" | New output: Red flag feed |
| Alive, not static | "Screeners haven't changed in decades: set filters, stare at a list"; bubbles that sink and rise got the most interest | Funnel story and live sorting |
| Visual summary | Simply Wall St's snowflake is "the friendliest on-ramp" | One shape per stock (our radar), used everywhere |
| Paid tiers sell | Real-time, backtesting (Finviz Elite $299/yr), equation screens, portfolio reports (Stock Rover $348 to $948/yr), AI screener (TradingView paid) | We already have formula screens, backtests and plain English; make them look like the paid tier |
| Alerts to action | "Alert me when price drops below my intrinsic value" | Fair-value alerts in Monitor |

## 2. Remove or merge (cut hard: fewer, stronger)

Rule: a card stays only if it has a lead figure or a one-line finding and nobody else on the page says the same thing. Everything cut stays reachable as a card's Table view or in the export, never deleted from the data.

Screen
- [x] Funnel tab: "Market Cap Bucket Distribution" and "Heatmap View" merge into one Sector and size map
- [x] Coverage tab removed: one coverage bar in the run header; full table in Export
- [x] "Run" card removed: run id and Copy settings move into the run header menu
- [x] "Where each name sits in its sector" 500-row table removed: shown per name in the stock drawer
- [x] "Saved Screens" and "Run Changes" outputs removed from results: Saved page and Compare runs already show them
- [x] Scatter and RRG: one card with a toggle, not two
Rank and Composite
- [x] "Table" tab removed: the ranked table is the Ranking tab
- [x] "Rules and ML" and "Backtest" tabs merge into one Evidence tab
Test
- [x] Losing streaks and Drawdown episodes merge into one Drawdown story (episodes marked on the underwater chart)
- [x] Weekly heatmap hidden by default (monthly says it better); kept as an alternate view
- [x] Horizon table and Yearly vs benchmark merge into one "By period" card
- [x] Turnover moves under Holdings; Rebalancing keeps only the variant bars
Everywhere
- [x] No generic key-value cards; no card titled by its data key ("Quick Look Card", "Heatmap View")
- [x] Caveats collapse into one line under the hero with a "4 limits" pill that opens them
- [x] The "Report" and "Export" buttons become one Export menu

## 3. Add: the cinematic set (the "wow" on first open)

Each one is real data, has a still fallback and respects the Reduce motion switch.

- [ ] C1 Hero result: one huge lead figure per run ("+71% vs SPY +38%", "12 of 500 pass") over a full-width chart, then the evidence below. Screen, Rank and Test
- [ ] C2 Funnel story: 500 dots collapse filter by filter to the passing names, count ticking down, each step labelled with the filter that removed most
- [ ] C3 Backtest replay: press play, months advance, names fly in and out of the portfolio, equity line draws live against SPY, drawdowns shade as they happen; scrub bar
- [ ] C4 Rotation trails: sectors move through the RRG quadrants week by week with fading tails; play and scrub
- [ ] C5 Live sorting field: every name a bubble sized by market cap; tighten a filter and failing names sink and fade while the strongest rise (the most-liked idea in the research)
- [ ] C6 Stock story: full stock page scrolls as chapters (price, valuation vs history, quality, peers, risks), each chapter's chart animating in

## 4. Add: the paid-tier set (what people say they would pay for)

- [ ] P1 Lens overlap: Buffett (ROE, cash flow, low debt), Graham (deep value, margin of safety), Dividend safety, Momentum; a matrix of names passing 2+ lenses, the overlap highlighted as the headline
- [ ] P2 Price vs fair value strip: every passing name on one axis, price against our valuation range, sorted by discount; click opens the drawer at Valuation
- [ ] P3 Red flag feed: debt jump, one-quarter income drop, margin collapse, dilution, Altman distress, with the quarter it happened
- [ ] P4 Fair-value alert: "tell me when JNJ trades below its fair value" from the strip or drawer, into Monitor
- [ ] P5 Score snowflake everywhere: the drawer radar as a small mark in table rows and compare, so every name has a shape
- [ ] P6 History depth badges: each metric shows how many years we hold (fundamentals from 2021), so nobody mistakes 4 years for 20
- [ ] P7 One-page stock and backtest reports (PDF) styled like the app, for sharing

## 5. Compare anything (the research's most-bought feature)

Finviz made Compare an Elite-only feature in April 2026 (charts with zoom, monthly return heatmap, relative performance, fundamentals as bars, a ranking across the set). Koyfin sells Compare Matrix and five-name PDF comparison reports. Portfolio123 built side-by-side scoring. Ours goes further: compare anything, from anywhere, in two clicks.

- [ ] X1 Tick any two to eight rows in any table (screen, rank, holdings, near misses, alerts, peers), press C or the Compare button: the compare view opens with exactly those names
- [ ] X2 Compare view tabs: Price (rebased overlay, zoom and pan), Returns (monthly heatmap with hover, relative performance by month and year), Fundamentals (any metric as bars, yearly or quarterly, grouped or stacked), Scores (radar shapes overlaid), Ranking (who leads each metric, totals)
- [ ] X3 Winner per row: best and worst highlighted (built for the drawer, `15748af`); a one-line verdict on top ("MSFT leads on 7 of 12 metrics")
- [ ] X4 Compare two runs of anything: two screens, two backtests, two weightings; shows names in and out, metrics side by side, equity curves overlaid
- [ ] X5 Compare a stock with its sector median and with SPY as permanent rows
- [ ] X6 Compare to the past: the same name today against one year ago (valuation, quality, rank)
- [ ] X7 Compare report: export the view as one styled PDF (Koyfin sells this)
- [ ] X8 Shareable compare link: names and tab in the URL

## 6. Competitors, studied (2026-11-13)

| Product | What they charge for | The idea we take | Where we beat it |
|---|---|---|---|
| Finviz Elite ($299.50 a year) | Real-time, backtests, Compare (2026), advanced charts | Compare's monthly heatmap, relative performance and ranking tabs; the heat map as the home page | Point-in-time backtests with overfitting checks; why a name passed |
| Koyfin ($39 to $209 a month) | Global data, historical graphs of any metric, Compare Matrix, comparison PDFs, percentile rank vs own history | Percentile vs own history on every metric; colour-synced multi-name charts | Screens that explain themselves; backtest any screen |
| Stock Rover ($348 to $948 a year) | 800+ metrics, 20-year history, equation screens, portfolio reports | Equation screens (we have formula); history depth as a selling point | Modern UI, speed, plain-English filters, near misses |
| TIKR ($25 to $120 a month) | 20-year standardised financials, auto peer groups, Bull/Base/Bear valuation | Auto peer group on every stock; three-case valuation | Screening and backtests they do not have |
| Simply Wall St ($131 to $258 a year) | The snowflake, visual reports | One shape per company everywhere | Depth and honesty about data limits |
| GuruFocus ($499 to $1,348 a year) | 30-year value data, guru portfolios | Investor lenses (Buffett, Graham) as screens | Price, speed, design |
| TradingView (from $12.95 a month) | Best charts, AI screener on paid plans | Overlay compare with same % scale; plain-language screening | Fundamentals, research honesty |
| Portfolio123 | Ranking systems, screens as backtestable strategies | Screen to strategy in one click (we have it; make it louder) | Usability; they are built for quants only |

What nobody has, and we lead with: every result says why (passed, near miss, what removed the rest), every backtest says if it is likely overfit, every number has its as-of date and coverage.

## 7. Order

1. Section 2 cuts (fast, makes room)
2. C1 Hero result (every run benefits)
3. X1 to X3 Compare from any table
4. C2 Funnel story, C3 Backtest replay
5. P1 Lens overlap, P2 Price vs fair value
6. X4 to X8, C4, C5, C6, then P3 to P7

## 8. Not doing

- Real-time quotes and intraday (data we do not hold)
- Conference calls and transcripts (no source)
- European screening (universe is US today)
