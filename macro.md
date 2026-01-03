🌍 WORLD-CLASS MACRO CONTROL SYSTEM — COMPLETE SPECIFICATION
For Claude Opus 4.5 Implementation

🎯 SYSTEM ARCHITECTURE OVERVIEW
Purpose
Transform raw macro market data into actionable trading constraints through 7 interconnected regime detection systems. Each feature outputs specific risk posture adjustments that cascade into portfolio-level decision rules.
Design Philosophy

- No decorative metrics — every output must change a decision
- State-driven UI — visual hierarchy based on urgency
- Institutional-grade logic — battle-tested statistical methods
- Dual-market coverage — US (SPX/VIX) + India (NIFTY/INDIAVIX)

📊 MACRO DASHBOARD — PRIMARY VIEW
Layout Structure
┌─────────────────────────────────────────────────────────────┐
│ MACRO RISK POSTURE [Last Updated: Live] │
├─────────────────────────────────────────────────────────────┤
│ │
│ ⚠️ CURRENT REGIME: BULL HIGH VOL │
│ 📊 TRADING CLEARANCE: REDUCED EXPOSURE │
│ 🚨 ACTIVE WARNINGS: 2 │
│ │
├─────────────────────────────────────────────────────────────┤
│ REGIME ENGINE │ STRESS │ VOL REGIME │ TREND │
│ BREADTH │ REVERSION │ RATES │
└─────────────────────────────────────────────────────────────┘
Master Status Card (Top Hero Section)
Visual Design

- Large card, 100% width
- Dynamic background color based on overall risk posture
  _ Green gradient: Risk-On (safe to operate)
  _ Yellow gradient: Caution (reduced operations) \* Red gradient: Risk-Off (defensive only)
  Data Displayed

1. Current Regime State
   - Primary label: Bull/Bear + Vol state
   - Confidence score (0-100%)
   - Time in current regime
2. Trading Clearance Level
   - Max Exposure Allowed: 100% / 75% / 50% / 25% / 0%
   - Leverage Allowed: YES / NO
   - New Positions: ALLOWED / RESTRICTED / FROZEN
3. Active Warnings Count
   - Clickable to expand detail panel
   - Icon indicators for warning type

1️⃣ MARKET REGIME ENGINE
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ 🔄 MARKET REGIME ENGINE │
├────────────────────────────────────────────────────┤
│ │
│ Current State: BULL HIGH VOL [Confidence: 87%]│
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ Regime Probabilities: │
│ Bull Low Vol ████░░░░░░ 32% │
│ Bull High Vol ████████░░ 87% ← Current │
│ Bear Low Vol █░░░░░░░░░ 8% │
│ Bear High Vol ██░░░░░░░░ 15% │
│ │
│ Transition Risk: MEDIUM [Stability: 71%] │
│ Time in Regime: 12 trading days │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
SPX Daily Returns Market data Daily 252 days
NIFTY Daily Returns Market data Daily 252 days
SPX Rolling Volatility (20d) Calculated Daily 60 days
NIFTY Rolling Volatility (20d) Calculated Daily 60 days
Drawdown Series Calculated Daily 252 days
Logic Flow
Step 1: State Definition
4 Hidden States:

- Bull Low Vol: μ > 0, σ < median(σ)
- Bull High Vol: μ > 0, σ > median(σ)
- Bear Low Vol: μ < 0, σ < median(σ)
- Bear High Vol: μ < 0, σ > median(σ)
  Step 2: HMM Parameter Estimation

* Use Baum-Welch algorithm for MLE
* Transition matrix: 4×4 probabilities
* Emission probabilities from Gaussian distributions
* Re-estimate parameters every 20 trading days
  Step 3: Regime Inference
* Forward-backward algorithm for posterior probabilities
* Viterbi path for most-likely state sequence
* Confidence = max(posterior probabilities)
  Step 4: Stability Scoring
  Stability = 1 - max(transition_probs_from_current_state)
  Transition_Risk = LOW if stability > 0.8
  MEDIUM if 0.6 < stability < 0.8
  HIGH if stability < 0.6
  Outputs
  Primary Outputs
* Regime Label: Bull Low Vol / Bull High Vol / Bear Low Vol / Bear High Vol
* Confidence Score: 0-100%
* Stability Score: 0-100%
* Transition Risk: LOW / MEDIUM / HIGH
* Days in Regime: Integer count
  Derived Trading Constraints
  Regime Max Exposure Allowed Strategies Stop Multiplier
  Bull Low Vol 100% All 1.0×
  Bull High Vol 75% Trend, reduce size 1.5×
  Bear Low Vol 50% Mean reversion only 1.3×
  Bear High Vol 25% Defensive only 2.0×
  Charts
  Chart 1: Regime Probability Timeline
* Type: Stacked area chart
* X-axis: Last 60 trading days
* Y-axis: Probability (0-100%)
* 4 colored bands for each regime
* Current regime highlighted
  Chart 2: Regime State Path
* Type: Step chart
* X-axis: Last 120 trading days
* Y-axis: Regime state (categorical)
* Color-coded states
* Annotations for regime changes

2️⃣ STRESS DETECTOR (TURBULENCE INDEX)
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ ⚡ STRESS DETECTOR │
├────────────────────────────────────────────────────┤
│ │
│ Status: ELEVATED [Percentile: 78th] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ Turbulence Index: 2.34 │
│ Normal Range: 0.00 - 1.50 │
│ Warning Threshold: 2.00 │
│ │
│ Time Above Threshold: 3 days │
│ Market State: ABNORMAL BEHAVIOR │
│ │
│ 🚫 TRADING CONSTRAINTS ACTIVE: │
│ • New positions restricted │
│ • Leverage disabled │
│ • Risk reduction recommended │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
Index Returns (SPX, NIFTY) Market data Daily 252 days
Return Covariance Matrix Calculated Daily 60-day window
Logic Flow
Step 1: Mean Return Vector
μ = E[r_t] over lookback window
where r_t = [r_SPX, r_NIFTY]
Step 2: Covariance Matrix
Σ = Cov(r_t, r_t-1, ..., r_t-n)
Use exponential weighting: λ = 0.94 (RiskMetrics standard)
Step 3: Mahalanobis Distance
Turbulence_t = (r_t - μ)^T × Σ^-1 × (r_t - μ)
Step 4: Percentile Ranking
Stress_Percentile = percentile_rank(Turbulence_t, historical_turbulence)
over 252-day history
Step 5: State Classification
NORMAL: Percentile < 70
ELEVATED: 70 ≤ Percentile < 90
EXTREME: Percentile ≥ 90
Outputs
Primary Outputs

- Turbulence Index: Floating point value
- Stress Percentile: 0-100th percentile
- Market State: NORMAL / ELEVATED / EXTREME
- Consecutive Days Above Threshold: Integer count
  Derived Trading Constraints
  Stress Level New Positions Leverage Risk Action
  NORMAL Allowed Allowed Normal operations
  ELEVATED Restricted Disabled Monitor closely
  EXTREME Frozen Disabled Force de-risk
  Charts
  Chart 1: Turbulence Timeline
- Type: Line chart with threshold bands
- X-axis: Last 90 trading days
- Y-axis: Turbulence Index
- Horizontal bands: Normal (green), Warning (yellow), Extreme (red)
- Current value marked
  Chart 2: Stress Percentile Distribution
- Type: Histogram
- X-axis: Turbulence Index bins
- Y-axis: Frequency
- Current value marked with vertical line
- Percentile shaded

3️⃣ VOLATILITY REGIME
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ 📈 VOLATILITY REGIME │
├────────────────────────────────────────────────────┤
│ │
│ Current Regime: HIGH VOL [Trend: RISING] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ VIX Level: 28.4 [Percentile: 82nd] │
│ INDIAVIX: 16.7 [Percentile: 71st] │
│ │
│ Vol Expansion Probability: 68% │
│ Mean Reversion Timeline: 3-5 days │
│ │
│ 📊 POSITION SIZING ADJUSTMENT: │
│ Base Size Multiplier: 0.5× │
│ Stop Width Multiplier: 1.8× │
│ Strategy Bias: Avoid trend-following │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
VIX Close Market data Daily 252 days
INDIAVIX Close Market data Daily 252 days
VIX Historical Percentiles Calculated Daily 252 days
Logic Flow
Step 1: Percentile Ranking
VIX_Percentile = percentile_rank(VIX_current, VIX_252d)
INDIAVIX_Percentile = percentile_rank(INDIAVIX_current, INDIAVIX_252d)
Step 2: Regime Classification
LOW VOL: Percentile < 40
MEDIUM VOL: 40 ≤ Percentile < 70
HIGH VOL: Percentile ≥ 70
Step 3: Trend Detection
Vol_Trend = sign(VIX_MA5 - VIX_MA20)
RISING if > 0
FALLING if < 0
Step 4: Expansion Probability
Using historical vol clustering:
P(expansion) = frequency of vol > current_vol within next 5 days
Based on 252-day history, conditional on current regime
Outputs
Primary Outputs

- Vol Regime: LOW / MEDIUM / HIGH
- VIX Level & Percentile
- INDIAVIX Level & Percentile
- Vol Trend: RISING / FALLING
- Expansion Probability: 0-100%
- Mean Reversion Timeline: Days estimate
  Derived Trading Constraints
  Vol Regime Position Size Multiplier Stop Width Strategy Bias
  LOW VOL 1.2× 1.0× All strategies
  MEDIUM VOL 1.0× 1.3× Balanced
  HIGH VOL 0.5× 1.8× Range-bound only
  Charts
  Chart 1: VIX Term Structure
- Type: Dual-axis line chart
- X-axis: Last 120 trading days
- Y-axis Left: VIX level
- Y-axis Right: Percentile rank
- Both VIX and INDIAVIX plotted
- Regime bands shaded
  Chart 2: Vol Regime History
- Type: Color-coded bar chart
- X-axis: Last 60 trading days
- Y-axis: Vol regime (categorical)
- Green = Low, Yellow = Medium, Red = High

4️⃣ CTA TREND SIGNAL
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ 🎯 CTA TREND SIGNAL │
├────────────────────────────────────────────────────┤
│ │
│ Trend Direction: LONG [Agreement: 85%] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ Timeframe Alignment: │
│ Short (20d): LONG ✓ │
│ Medium (50d): LONG ✓ │
│ Long (200d): LONG ✓ │
│ │
│ Trend Maturity: 47 days [Stage: MID] │
│ Exhaustion Risk: LOW │
│ │
│ 💡 TRADING GUIDANCE: │
│ • Trend continuation allowed │
│ • Institutional alignment confirmed │
│ • Add on pullbacks, not breakouts │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
SPX Daily Close Market data Daily 252 days
NIFTY Daily Close Market data Daily 252 days
Logic Flow
Step 1: Multi-Timeframe Breakout Detection
For each timeframe (20d, 50d, 200d):
LONG if Price > MA(period) AND Price > HH(period)
SHORT if Price < MA(period) AND Price < LL(period)
NEUTRAL otherwise

where HH = highest high, LL = lowest low
Step 2: Trend Agreement Score
Agreement = (# of aligned signals) / (# of timeframes)
Perfect alignment = 100%
Step 3: Trend Maturity Calculation
Maturity = days since trend direction change
Classification:
EARLY: < 20 days
MID: 20-60 days
LATE: > 60 days
Step 4: Exhaustion Risk
Exhaustion_Risk = LOW if maturity < 60 days AND vol not expanding
MEDIUM if maturity 60-90 days OR vol expanding
HIGH if maturity > 90 days AND price > 2σ from MA
Outputs
Primary Outputs

- Trend Direction: LONG / NEUTRAL / SHORT
- Agreement Score: 0-100%
- Timeframe Signals: Individual signal for 20d, 50d, 200d
- Trend Maturity: Days count + Stage (EARLY/MID/LATE)
- Exhaustion Risk: LOW / MEDIUM / HIGH
  Derived Trading Constraints
  Trend State Continuation Allowed Scale-in Strategy Warning
  Strong (>80% agreement) YES Buy pullbacks None
  Moderate (50-80%) SELECTIVE Small size Watch for flip
  Weak (<50%) NO Avoid directional High chop risk
  Charts
  Chart 1: Trend Alignment Heatmap
- Type: Matrix/Grid
- Rows: 3 timeframes (20d, 50d, 200d)
- Columns: Last 60 trading days
- Colors: Green (LONG), Gray (NEUTRAL), Red (SHORT)
- Current signals highlighted
  Chart 2: Trend Strength Timeline
- Type: Line chart
- X-axis: Last 120 trading days
- Y-axis: Agreement score (0-100%)
- Horizontal line at 80% (strong threshold)
- Annotations for trend changes

5️⃣ MEAN REVERSION TIMER
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ ⏱️ MEAN REVERSION TIMER │
├────────────────────────────────────────────────────┤
│ │
│ Status: OVERBOUGHT [Intensity: EXTREME] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ Return Z-Score: +2.8σ │
│ Distance from MA(50): +4.2% │
│ │
│ Snapback Probability: 73% (within 5 days) │
│ Historical Mean Reversion Time: 3-7 days │
│ │
│ 🚨 ENTRY RESTRICTIONS: │
│ • Fresh long entries BLOCKED │
│ • Profit-taking recommended │
│ • Fade setups on watchlist │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
Index Daily Returns Market data Daily 252 days
Index Close Price Market data Daily 252 days
MA(20), MA(50), MA(200) Calculated Daily N/A
Logic Flow
Step 1: Z-Score Calculation
Z = (Return_current - μ_returns) / σ_returns
where μ and σ calculated over 252-day window
Step 2: Distance from Moving Averages
Dist_MA(n) = (Price_current - MA(n)) / MA(n) × 100%
Calculate for MA(20), MA(50), MA(200)
Use most extreme value
Step 3: Overextension Classification
EXTREME OVERBOUGHT: Z > +2.5 OR Dist > +5%
OVERBOUGHT: Z > +2.0 OR Dist > +3%
NEUTRAL: -2.0 < Z < +2.0 AND -3% < Dist < +3%
OVERSOLD: Z < -2.0 OR Dist < -3%
EXTREME OVERSOLD: Z < -2.5 OR Dist < -5%
Step 4: Snapback Probability
Using historical data:
P(reversion) = frequency of price moving toward mean
within next 5 days
conditional on current extension level
Outputs
Primary Outputs

- Extension Status: EXTREME OVERBOUGHT / OVERBOUGHT / NEUTRAL / OVERSOLD / EXTREME OVERSOLD
- Return Z-Score: Sigma units
- Distance from Key MA: Percentage
- Snapback Probability: 0-100%
- Historical Reversion Time: Day range
  Derived Trading Constraints
  Extension Level Long Entries Short Entries Profit-Taking
  EXTREME OVERBOUGHT BLOCKED Allowed (fade) URGENT
  OVERBOUGHT Cooldown 2-3 days Considered Recommended
  NEUTRAL Allowed Allowed Normal
  OVERSOLD Considered Cooldown 2-3 days Hold
  EXTREME OVERSOLD Allowed (scale) BLOCKED Not yet
  Charts
  Chart 1: Z-Score Timeline
- Type: Line chart with threshold bands
- X-axis: Last 90 trading days
- Y-axis: Z-score (-3σ to +3σ)
- Bands: Overbought (+2σ), Neutral, Oversold (-2σ)
- Current value marked
  Chart 2: Price vs Moving Averages
- Type: Multi-line chart
- X-axis: Last 60 trading days
- Y-axis: Price + MA(20), MA(50), MA(200)
- Distance shaded between price and MAs
- Current distance labeled

6️⃣ MARKET BREADTH
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ 📊 MARKET BREADTH │
├────────────────────────────────────────────────────┤
│ │
│ McClellan Oscillator: +142 [Momentum: STRONG] │
│ McClellan Summation: +1,247 [Trend: BULLISH] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ Breadth Health: HEALTHY │
│ Price-Breadth Alignment: CONFIRMED │
│ │
│ ⚠️ DIVERGENCE CHECK: │
│ Price making new highs: YES │
│ Breadth confirming: YES ✓ │
│ Rally Quality: BROAD-BASED │
│ │
│ 💡 BREAKOUT TRUST: HIGH │
│ Market moves are institutionally supported │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
NYSE Advance-Decline Data Market data Daily 252 days
NSE Advance-Decline Data Market data Daily 252 days
Index Price (SPX/NIFTY) Market data Daily 90 days
Logic Flow
Step 1: McClellan Oscillator
Net_Advances = (Advances - Declines)
EMA_19 = EMA(Net_Advances, 19)
EMA_39 = EMA(Net_Advances, 39)
McClellan_Oscillator = EMA_19 - EMA_39
Step 2: McClellan Summation
Summation_t = Summation_t-1 + McClellan_Oscillator_t
(Cumulative sum of oscillator values)
Step 3: Breadth Health Classification
Oscillator Ranges:
STRONG BULLISH: > +150
BULLISH: +50 to +150
NEUTRAL: -50 to +50
BEARISH: -150 to -50
STRONG BEARISH: < -150

Summation Ranges:
BULLISH TREND: > +1000
NEUTRAL: -1000 to +1000
BEARISH TREND: < -1000
Step 4: Divergence Detection
Price_Direction = sign(Price_current - Price_20d_ago)
Breadth_Direction = sign(Summation_current - Summation_20d_ago)

DIVERGENCE if Price_Direction ≠ Breadth_Direction
CONFIRMED if Price_Direction = Breadth_Direction
Outputs
Primary Outputs

- McClellan Oscillator: Value + Momentum label
- McClellan Summation: Value + Trend label
- Breadth Health: HEALTHY / NEUTRAL / DETERIORATING
- Price-Breadth Alignment: CONFIRMED / DIVERGENCE
- Rally Quality: BROAD-BASED / NARROW / FAILING
  Derived Trading Constraints
  Breadth State Breakout Trust Chasing Allowed Warning
  Healthy + Confirmed HIGH YES None
  Neutral or Mixed MEDIUM SELECTIVE Watch closely
  Divergence LOW NO Trap risk high
  Charts
  Chart 1: McClellan Oscillator
- Type: Bar chart with centerline
- X-axis: Last 90 trading days
- Y-axis: Oscillator value (-300 to +300)
- Bars: Green (positive), Red (negative)
- Threshold lines at ±150
  Chart 2: Price vs Summation
- Type: Dual-axis chart
- X-axis: Last 120 trading days
- Y-axis Left: Index price
- Y-axis Right: McClellan Summation
- Both normalized to starting point
- Divergence zones highlighted
  Chart 3: Advance-Decline Ratio
- Type: Area chart
- X-axis: Last 60 trading days
- Y-axis: Advances / (Advances + Declines) × 100%
- 50% centerline
- Current reading labeled

7️⃣ RATE CYCLE POSITION
Feature Card Layout
┌────────────────────────────────────────────────────┐
│ 💰 RATE CYCLE POSITION │
├────────────────────────────────────────────────────┤
│ │
│ Fed Funds Rate: 4.75% [Cycle: EASING] │
│ RBI Repo Rate: 6.50% [Cycle: PAUSE] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ │
│ Policy Stance: MIXED GLOBAL RATES │
│ Trend Velocity: │
│ US: -25 bps (last cut) │
│ India: 0 bps (last meeting) │
│ │
│ Next Meeting: Fed (Jan 28), RBI (Feb 7) │
│ │
│ 📈 RISK ASSET IMPLICATIONS: │
│ • US easing = tailwind for equities │
│ • India pause = neutral-to-positive │
│ • Leverage sensitivity: MODERATE │
│ │
└────────────────────────────────────────────────────┘
Data Inputs
Input Source Frequency Lookback
Fed Funds Rate FRED / Central Bank Meeting dates 2 years
RBI Repo Rate RBI / Central Bank Meeting dates 2 years
Rate Change History Calculated N/A 2 years
Logic Flow
Step 1: Rate Level Trend
For each rate:
Trend = sign(Rate_current - Rate_6months_ago)
Step 2: Cycle Classification
TIGHTENING: Multiple consecutive rate hikes
EASING: Multiple consecutive rate cuts
PAUSE: No change in last 2 meetings
PIVOT: Direction change in last 3 meetings
Step 3: Velocity Calculation
Velocity = sum of rate changes in last 3 meetings
Measured in basis points (bps)
Step 4: Risk Asset Regime
TAILWIND: Both US and India easing
NEUTRAL: Mixed or pausing
HEADWIND: Both tightening
Outputs
Primary Outputs

- Fed Funds Rate: Level + Cycle stage
- RBI Repo Rate: Level + Cycle stage
- Policy Stance: TAILWIND / NEUTRAL / HEADWIND
- Trend Velocity: Basis points change
- Next Meeting Dates: Calendar dates
  Derived Trading Constraints
  Rate Regime Growth vs Defensive Leverage Sensitivity Duration Bias
  EASING (both) Growth stocks LOW (leverage cheap) Long duration
  MIXED Balanced MODERATE Neutral
  TIGHTENING (both) Defensive HIGH (leverage expensive) Short duration
  Charts
  Chart 1: Rate Path History
- Type: Step chart
- X-axis: Last 2 years (quarterly)
- Y-axis: Interest rate %
- Two lines: Fed Funds (blue), RBI Repo (orange)
- Meeting dates marked
  Chart 2: Rate Change Distribution
- Type: Bar chart
- X-axis: Meeting dates (last 10 meetings)
- Y-axis: Rate change in bps
- Separate series for US and India
- Current stance labeled

🎛️ MASTER CONTROL PANEL
Aggregate Risk Posture Calculator
Logic for Overall Posture
Scoring System (0-100 scale):

Regime Engine:
Bull Low Vol = 100
Bull High Vol = 70
Bear Low Vol = 40
Bear High Vol = 0

Stress Detector:
Normal = 100
Elevated = 50
Extreme = 0

Volatility:
Low = 100
Medium = 60
High = 30

Trend:
Strong Agreement = 100
Moderate = 60
Weak = 30

Reversion:
Neutral = 100
Overbought = 70
Extreme Overbought = 40
(mirrored for oversold)

Breadth:
Confirmed = 100
Neutral = 60
Divergence = 20

Rates:
Tailwind = 100
Neutral = 60
Headwind = 40

---

Overall_Score = weighted_average(all_scores)
Weights:
Regime: 25%
Stress: 20%
Vol: 15%
Trend: 15%
Reversion: 10%
Breadth: 10%
Rates: 5%

---

Final Posture:
RISK-ON: Score > 75
CAUTION: Score 50-75
RISK-OFF: Score < 50
Master Output Display
┌─────────────────────────────────────────────────────────┐
│
🎯 MASTER TRADING POSTURE │ ├─────────────────────────────────────────────────────────┤ │ │ │ Overall Risk Score: 68/100 [CAUTION] │ │ ████████████████████░░░░░░░░░░░ │ │ │ │ 🔓 TRADING CLEARANCES: │ │ Max Exposure: 75% │ │ Leverage: RESTRICTED │ │ New Positions: ALLOWED │ │ Preferred Strategies: Trend (reduced size) │ │ │ │ ⚠️ ACTIVE CONSTRAINTS: │ │ • High volatility - reduce position sizes │ │ • Watch for stress spikes │ │ │ │ 📋 FEATURE BREAKDOWN: │ │ Regime: 70/100 (Bull High Vol) │ │ Stress: 50/100 (Elevated) │ │ Vol: 30/100 (High) │ │ Trend: 100/100 (Strong) │ │ Reversion: 100/100 (Neutral) │ │ Breadth: 100/100 (Confirmed) │ │ Rates: 60/100 (Neutral) │ │ │ └─────────────────────────────────────────────────────────┘

---

## 📱 UI COMPONENTS SPECIFICATION

### Color Palette

**Risk Posture Colors**

- Risk-On: `#10B981` (green-500)
- Caution: `#F59E0B` (amber-500)
- Risk-Off: `#EF4444` (red-500)

**State Colors**

- Normal: `#10B981`
- Warning: `#F59E0B`
- Critical: `#EF4444`
- Neutral: `#6B7280` (gray-500)

**Chart Colors**

- Primary Line: `#3B82F6` (blue-500)
- Secondary Line: `#F97316` (orange-500)
- Positive: `#10B981`
- Negative: `#EF4444`
- Background: `#1F2937` (gray-800)

### Typography

**Headers**

- Page Title: 32px, Bold
- Feature Card Title: 20px, Semibold
- Section Header: 16px, Medium
- Body Text: 14px, Regular
- Caption: 12px, Regular

### Card Dimensions

- Feature Card: 600px width × Auto height
- Minimum card height: 300px
- Card padding: 24px
- Card gap: 16px between elements
- Corner radius: 12px

### Chart Specifications

**All Charts**

- Height: 250px (standard), 400px (detailed)
- Width: 100% of container
- Margin: 16px top/bottom
- Grid lines: Subtle gray (#374151)
- Axis labels: 12px
- Tooltips: On hover, white background, shadow

### Interactive Elements

**Buttons**

- Primary: Blue (#3B82F6), 40px height
- Secondary: Gray (#6B7280), 40px height
- Hover: 10% darker
- Active: 15% darker
- Border radius: 8px

**Dropdowns**

- Height: 40px
- Border: 1px solid #374151
- Hover: Border #3B82F6

### Responsive Breakpoints

- Desktop: > 1024px (3-column grid)
- Tablet: 768px - 1024px (2-column grid)
- Mobile: < 768px (1-column stack)

---

## 📊 DATA REFRESH SPECIFICATIONS

### Update Frequencies

| Data Type           | Refresh Rate | Update Time (EST) |
| ------------------- | ------------ | ----------------- |
| Index Prices        | Real-time    | Market hours      |
| VIX/INDIAVIX        | Real-time    | Market hours      |
| Advance-Decline     | End-of-day   | 4:30 PM           |
| Interest Rates      | Event-driven | Meeting dates     |
| Regime Calculations | End-of-day   | 5:00 PM           |
| Stress Calculations | End-of-day   | 5:00 PM           |

### Calculation Priority

1. **Real-time** (live updates during market hours)

   - Price-based signals (Trend, Reversion)
   - Volatility metrics

2. **End-of-day** (calculated after market close)

   - Regime probabilities
   - Stress index
   - Breadth indicators

3. **Event-driven** (on data release)
   - Interest rate changes

---

## 🚨 ALERT SYSTEM

### Alert Hierarchy

**Level 1: Information**

- Regime change
- Vol regime shift
- Trend alignment change

**Level 2: Warning**

- Stress elevated
- Overextension reached
- Breadth divergence

**Level 3: Critical**

- Stress extreme
- Multiple red flags
- Forced de-risk signal

### Alert Display

## ┌────────────────────────────────────────────┐ │ 🔔 ACTIVE ALERTS (2) │ ├────────────────────────────────────────────┤ │ │ │ ⚠️ WARNING │ │ Stress Detector: Elevated │ │ Triggered 3 days ago │ │ → Restrict new positions │ │ │ │ 🔴 CRITICAL │ │ Volatility Regime: High Vol │ │ Triggered today │ │ → Reduce position sizes to 0.5× │ │ │ └────────────────────────────────────────────┘

## 🎨 DASHBOARD LAYOUT (FULL PAGE)

┌──────────────────────────────────────────────────────────┐ │ MACRO CONTROL SYSTEM [Last Update: 4:35 PM] │ ├──────────────────────────────────────────────────────────┤ │ │ │ ┌────────────────────────────────────────────────────┐ │ │ │ 🎯 MASTER TRADING POSTURE │ │ │ │ Overall Score: 68/100 [CAUTION] │ │ │ │ Allowed: 75% exposure, No leverage, Trend (small) │ │ │ └────────────────────────────────────────────────────┘ │ │ │ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │ │ │ 🔄 REGIME │ │ ⚡ STRESS │ │ 📈 VOL │ │ │ │ Bull High Vol│ │ Elevated │ │ High │ │ │ │ 87% Conf │ │ 78th %tile │ │ Rising │ │ │ └──────────────┘ └──────────────┘ └──────────────┘ │ │ │ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │ │ │ 🎯 TREND │ │ ⏱️ REVERSION │ │ 📊 BREADTH │ │ │ │ Long │ │ Neutral │ │ Confirmed │ │ │ │ 85% Agree │ │ Z: +0.3σ │ │ Osc: +142 │ │ │ └──────────────┘ └──────────────┘ └──────────────┘ │ │ │ │ ┌──────────────────────────────────────────────────┐ │ │ │ 💰 RATE CYCLE │ │ │ │ US: Easing | India: Pause | Stance: Neutral │ │ │ └──────────────────────────────────────────────────┘ │ │ │ │ [View Detailed Charts] [Export Report] [Settings] │ │ │ └──────────────────────────────────────────────────────────┘

### Detailed View (Expandable)

When user clicks on any feature card, expand to full detailed view with:

- All calculations shown
- All charts rendered
- Historical context
- Specific trading constraints

---

## 📝 SUMMARY OUTPUT TABLE

**Master Decision Matrix**

| Factor     | Current State | Score   | Impact            | Action Required      |
| ---------- | ------------- | ------- | ----------------- | -------------------- |
| Regime     | Bull High Vol | 70/100  | Moderate exposure | Reduce size          |
| Stress     | Elevated      | 50/100  | High risk         | Monitor closely      |
| Volatility | High          | 30/100  | Severe impact     | 0.5× position size   |
| Trend      | Strong Long   | 100/100 | Favorable         | Follow, smaller size |
| Reversion  | Neutral       | 100/100 | None              | Normal operations    |
| Breadth    | Confirmed     | 100/100 | Positive          | Trust breakouts      |
| Rates      | Neutral       | 60/100  | Slight tailwind   | Balanced allocation  |

**Overall Posture: CAUTION (68/100)**

---

## 🔧 FINAL TECHNICAL NOTES

### Dependencies

- **Statistical Libraries**: NumPy, Pandas, Scikit-learn (for HMM)
- **Charting**: Recharts, Plotly, or D3.js
- **UI Framework**: React with Tailwind CSS

### Performance Requirements

- Dashboard load time: < 2 seconds
- Chart render time: < 500ms
- Real-time updates: < 100ms latency
- End-of-day calculations: < 5 seconds total

### Data Quality Checks

- Missing data: Forward-fill up to 3 days, then alert
- Outlier detection: Winsorize at 99th percentile
- Calculation errors: Fallback to last valid value, log error

---

## ✅ IMPLEMENTATION CHECKLIST

**Phase 1: Core Calculations**

- [ ] Markov HMM regime engine
- [ ] Turbulence index calculator
- [ ] Vol percentile tracker
- [ ] CTA trend signals
- [ ] Z-score calculator
- [ ] McClellan indicators
- [ ] Rate cycle tracker

**Phase 2: UI Components**

- [ ] Master control panel
- [ ] 7 feature cards
- [ ] All charts (14 total)
- [ ] Alert system
- [ ] Export functionality

**Phase 3: Integration**

- [ ] Real-time data feeds
- [ ] End-of-day batch processing
- [ ] Score aggregation
- [ ] Constraint enforcement

---

This is the complete, production-ready specification for a world-class macro control system. Every feature has clear inputs, explicit calculations, defined outputs, and actionable trading constraints.
