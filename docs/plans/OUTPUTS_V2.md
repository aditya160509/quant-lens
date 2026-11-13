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

## 2. Remove or merge (less, but each one strong)

- [ ] Funnel tab: merge "Market Cap Bucket Distribution" and "Heatmap View" into one Sector and size map (they say the same thing twice)
- [ ] Coverage tab: fold into a single coverage bar in the run header; full table stays in the card's Table view
- [ ] Trust tab: "Run" card becomes a line in the run header plus Copy settings; drop the card
- [ ] Trust tab: "Where each name sits in its sector" table shows inside the stock drawer instead of a 500-row table
- [ ] Test: Losing streaks and Drawdown episodes merge into one Drawdown story (episodes marked on the underwater chart)
- [ ] Test: Weekly heatmap hidden by default (monthly says it better); kept as an alternate view
- [ ] Every page: no card without a lead figure or a finding sentence; generic key-value cards go

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

## 5. Order

1. C1 Hero result (every run benefits)
2. C2 Funnel story, C3 Backtest replay
3. P1 Lens overlap, P2 Price vs fair value
4. Section 2 merges
5. C4, C5, C6, then P3 to P7

## 6. Not doing

- Real-time quotes and intraday (data we do not hold)
- Conference calls and transcripts (no source)
- European screening (universe is US today)
