# QUANT360 — SCREENER MODULE

## Complete Mathematical and Computational Specification

---

## FEATURE S1 — CORE MULTI-FACTOR SCREENER ENGINE

### What you are building mathematically

A cross-sectional data pipeline that ingests daily adjusted OHLCV and quarterly fundamental data for a universe of up to 5,000 tickers, computes the complete set of descriptive, technical, and fundamental metrics for every ticker on every trading day, normalizes each metric into three simultaneous percentile ranks (full universe, GICS sector, GICS industry group), applies a user-defined conjunction of filter conditions, and returns a ranked, scored output table. The filter evaluation is a conjunction (logical AND) over all active conditions; the ranking is by any user-selected column.

---

### Step 1 — Universe construction and ticker manifest

Define the full universe U as the set of all tickers for which yfinance returns valid adjusted OHLCV data with at least 252 trading days of history. For sub-universe selection:

S&P 500 proxy: the 503 constituents as defined by the SPDR SPY ETF holdings (retrieved from yfinance `SPY` holdings endpoint or a static JSON updated monthly).

S&P 400 Midcap proxy: the 401 constituents from MDY holdings.

S&P 600 Smallcap proxy: the 601 constituents from SLY holdings.

Russell 1000 proxy: the top 1,000 tickers in U sorted by market cap descending at the most recent quarter-end.

For a custom user-uploaded CSV: parse ticker column, intersect with U, reject any ticker not in U (flag to the user).

At initialization, load the GICS classification for every ticker in U:

sector_i ∈ {Energy, Materials, Industrials, Consumer Discretionary, Consumer Staples, Health Care, Financials, Information Technology, Communication Services, Utilities, Real Estate}

industry_group_i, industry_i, sub_industry_i (all from yfinance `Ticker.info["sector"]`, `["industryGroup"]`, `["industry"]`, `["subIndustry"]`).

Store the manifest as a dictionary: M[ticker] = {sector, industry_group, industry, exchange, market_cap_latest, shares_outstanding, float_shares}.

---

### Step 2 — Price and return series construction

For each ticker i ∈ U, retrieve the full adjusted close series from yfinance:

P*i = {P*{i,t} : t = 1, ..., T}

where P\_{i,t} is the adjusted closing price on date t (adjusted for splits and dividends). All return computations use adjusted prices exclusively.

Daily log-return:

r*{i,t} = ln(P*{i,t} / P\_{i,t-1})

Simple return (used for momentum and percentile-rank comparisons where sign matters but compounding is short):

R*{i,t} = (P*{i,t} / P\_{i,t-1}) - 1

For momentum horizons H ∈ {1, 5, 21, 63, 126, 252} trading days:

MOM*{i,H,t} = P*{i,t} / P\_{i,t-H} - 1

Jegadeesh-Titman momentum (skips the most recent 21 days to avoid reversal contamination):

MOM*{i,JT,t} = P*{i,t-21} / P\_{i,t-252} - 1

This is the 12-month return lagged one month. The lag is mandatory: the short-term reversal in the most recent month reduces the signal-to-noise ratio of raw 12-month momentum by approximately 20% in US equity data (Jegadeesh and Titman, 1993, Journal of Finance).

Relative performance vs. benchmark B (SPY by default):

ALPHA*{i,H,t} = MOM*{i,H,t} - MOM\_{B,H,t}

where MOM\_{B,H,t} is the benchmark's H-day return computed identically.

---

### Step 3 — Descriptive metric computation

For each ticker i at date t:

**Market capitalization:**

MCAP*{i,t} = P*{i,t} × shares_outstanding_i

where shares_outstanding_i is from the most recent quarterly filing available in yfinance `Ticker.info["sharesOutstanding"]`. Use filing date, not period end date, for point-in-time compliance.

**Dollar volume (20-day average):**

DVOL*{i,t} = (1/20) × Σ*{s=t-19}^{t} P*{i,s} × V*{i,s}

where V\_{i,s} is the raw (unadjusted) daily share volume. Dollar volume is the primary liquidity filter; all volume filters operate on DVOL.

**Float percentage:**

FLOAT_PCT_i = float_shares_i / shares_outstanding_i ∈ (0, 1)

Tickers with FLOAT_PCT_i < 0.05 are flagged as "restricted float" regardless of other filter conditions.

**52-week high and low:**

H52*{i,t} = max{P*{i,s} : s ∈ [t-251, t]}

L52*{i,t} = min{P*{i,s} : s ∈ [t-251, t]}

**52-week proximity score (George-Hwang, 2004):**

PROX52*{i,t} = P*{i,t} / H52\_{i,t} ∈ (0, 1]

This is the George-Hwang (2004, Journal of Finance) 52-week high momentum predictor. High PROX52 (price near 52-week high) predicts positive forward returns in short-to-medium horizons.

---

### Step 4 — Technical indicator computation

All technical indicators below are computed for every ticker i at every date t using only the trailing window of data ending at t (no look-ahead).

**Simple Moving Average (SMA) at window W:**

SMA*{i,W,t} = (1/W) × Σ*{s=t-W+1}^{t} P\_{i,s}

Windows computed: W ∈ {20, 50, 100, 200}.

**Exponential Moving Average (EMA) at window W:**

EMA*{i,W,t} = α × P*{i,t} + (1-α) × EMA\_{i,W,t-1}

where α = 2 / (W+1). Initialize EMA*{i,W,W} = SMA*{i,W,W} (start from the first available W-period SMA).

Windows computed: W ∈ {20, 50, 200}.

**Relative position vs. MA:**

POS*SMA*{i,W,t} = (P*{i,t} - SMA*{i,W,t}) / SMA\_{i,W,t} × 100 (percent distance from SMA)

**SMA crossover event detection:**

CROSS*{i,X,Y,t} = I{SMA*{i,X,t} > SMA*{i,Y,t}} - I{SMA*{i,X,t-1} > SMA\_{i,Y,t-1}}

CROSS = +1: SMA_X crossed above SMA_Y on date t (bullish crossover).
CROSS = -1: SMA_X crossed below SMA_Y on date t (bearish crossover).
CROSS = 0: no crossover.

For the user filter "golden cross within last N days": the filter passes if Σ*{s=t-N+1}^{t} I{CROSS*{i,50,200,s} = +1} ≥ 1.

**Relative Strength Index (RSI) at period P (default 14):**

Define up-moves and down-moves:

U*{i,t} = max(R*{i,t}, 0), D*{i,t} = max(-R*{i,t}, 0)

Initial average gain and loss (first RSI computed at t = P):

AG*{i,P} = (1/P) × Σ*{s=1}^{P} U\_{i,s}

AL*{i,P} = (1/P) × Σ*{s=1}^{P} D\_{i,s}

Smoothed (Wilder's) averages for t > P:

AG*{i,t} = ((P-1) × AG*{i,t-1} + U\_{i,t}) / P

AL*{i,t} = ((P-1) × AL*{i,t-1} + D\_{i,t}) / P

RSI*{i,t} = 100 - 100 / (1 + AG*{i,t} / AL\_{i,t})

When AL*{i,t} = 0: RSI = 100 by convention. When AG*{i,t} = 0: RSI = 0.

**MACD:**

MACD*line*{i,t} = EMA*{i,12,t} - EMA*{i,26,t}

Signal*line*{i,t} = EMA of MACD_line over 9 periods (computed recursively with α = 2/10)

MACD*hist*{i,t} = MACD*line*{i,t} - Signal*line*{i,t}

Bullish crossover event: I{MACD*line*{i,t} > Signal*line*{i,t}} - I{MACD*line*{i,t-1} > Signal*line*{i,t-1}} = +1

**Bollinger Bands at (period P, multiplier K) — default (20, 2):**

BB*mid*{i,t} = SMA\_{i,20,t}

BB*std*{i,t} = √[(1/20) × Σ_{s=t-19}^{t} (P_{i,s} - BB_mid_{i,t})²]

BB*upper*{i,t} = BB*mid*{i,t} + K × BB*std*{i,t}

BB*lower*{i,t} = BB*mid*{i,t} - K × BB*std*{i,t}

Bandwidth: BW*{i,t} = (BB_upper*{i,t} - BB*lower*{i,t}) / BB*mid*{i,t}

**Average True Range (ATR) at period P (default 14):**

True Range: TR*{i,t} = max(H*{i,t} - L*{i,t}, |H*{i,t} - C*{i,t-1}|, |L*{i,t} - C\_{i,t-1}|)

where H*{i,t}, L*{i,t} are the daily high and low (raw, not adjusted), and C\_{i,t-1} is the prior adjusted close.

ATR*{i,t} = ((P-1) × ATR*{i,t-1} + TR\_{i,t}) / P (Wilder smoothing, same structure as RSI)

Initialize: ATR*{i,P} = (1/P) × Σ*{s=1}^{P} TR\_{i,s}

ATR as percent of price: ATR*PCT*{i,t} = ATR*{i,t} / P*{i,t} × 100

**Average Directional Index (ADX) at period P (default 14):**

Directional movements:

DM+_{i,t} = max(H_{i,t} - H*{i,t-1}, 0) if H*{i,t} - H*{i,t-1} > L*{i,t-1} - L\_{i,t}, else 0

DM-_{i,t} = max(L_{i,t-1} - L*{i,t}, 0) if L*{i,t-1} - L*{i,t} > H*{i,t} - H\_{i,t-1}, else 0

Smoothed over P periods (Wilder):

SDM+_{i,t} = ((P-1) × SDM+_{i,t-1} + DM+\_{i,t}) / P

SDM-_{i,t} = ((P-1) × SDM-_{i,t-1} + DM-\_{i,t}) / P

Directional indicators:

DMI+_{i,t} = SDM+_{i,t} / ATR\_{i,t} × 100

DMI-_{i,t} = SDM-_{i,t} / ATR\_{i,t} × 100

DX*{i,t} = |DMI+*{i,t} - DMI-_{i,t}| / (DMI+_{i,t} + DMI-\_{i,t}) × 100

ADX*{i,t} = ((P-1) × ADX*{i,t-1} + DX\_{i,t}) / P (initialized at first P-period average of DX)

**Rolling beta (252-day vs. benchmark B):**

BETA*{i,t} = Cov(r_i, r_B)*{t-251:t} / Var(r*B)*{t-251:t}

= [Σ_{s=t-251}^{t} (r_{i,s} - r̄_i)(r_{B,s} - r̄_B)] / [Σ_{s=t-251}^{t} (r_{B,s} - r̄_B)²]

where r̄_i and r̄_B are the trailing 252-day sample means of each return series.

**Stochastic oscillator at (K_period, D_period) — default (14, 3):**

%K*{i,t} = (C*{i,t} - L*{i,t,K}) / (H*{i,t,K} - L\_{i,t,K}) × 100

where H*{i,t,K} = max{H*{i,s} : s ∈ [t-K_period+1, t]} and L*{i,t,K} = min{L*{i,s} : s ∈ [t-K_period+1, t]}.

%D*{i,t} = (1/D_period) × Σ*{s=t-D*period+1}^{t} %K*{i,s}

**Williams %R at period P (default 14):**

WR*{i,t} = (H*{i,t,P} - C*{i,t}) / (H*{i,t,P} - L\_{i,t,P}) × (-100)

where H*{i,t,P} and L*{i,t,P} are P-period rolling max and min of daily high and low respectively.

Range: [-100, 0]. Overbought: WR > -20. Oversold: WR < -80.

**On-Balance Volume (OBV):**

OBV*{i,t} = OBV*{i,t-1} + V*{i,t} × sign(C*{i,t} - C\_{i,t-1})

where sign() = +1 if close is up, -1 if close is down, 0 if unchanged.

OBV trend over N days: OBV*SLOPE*{i,N,t} = OLS slope of OBV\_{i,s} on s for s ∈ [t-N+1, t].

**Volume ratio:**

VRATIO*{i,t} = V*{i,t} / [(1/20) × Σ_{s=t-19}^{t} V_{i,s}]

Elevated volume: VRATIO > 1.5, 2.0, or 3.0 (user-set threshold).

**Gap:**

GAP*{i,t} = (O*{i,t} - C*{i,t-1}) / C*{i,t-1} × 100

where O\_{i,t} is the raw (unadjusted) open price on date t. Gap-up: GAP > 0. Gap-down: GAP < 0. Filter on |GAP| > user threshold.

**Consecutive directional days:**

CONSEC\_{i,t} = signed count of consecutive days with the same return sign ending at t.

CONSEC*{i,t} > 0: stock has closed higher for CONSEC*{i,t} consecutive days.
CONSEC*{i,t} < 0: stock has closed lower for |CONSEC*{i,t}| consecutive days.

Computed as: CONSEC*{i,t} = CONSEC*{i,t-1} + 1 if sign(R*{i,t}) = sign(R*{i,t-1}) and R\_{i,t} > 0, else reset to 1 (or -1 for down). Reset to 0 on sign change.

---

### Step 5 — Fundamental metric computation

All fundamental metrics are retrieved from yfinance with strict point-in-time enforcement: the filing date of each quarterly or annual report is used as the date on which the data becomes available, never the period end date.

For any metric requiring income statement or balance sheet data, the most recent available filing as of date t is:

Q\_{i,t} = the quarterly or annual filing with filing_date ≤ t and the most recent such date.

**Valuation metrics:**

P/E ratio (TTM): PE*{i,t} = P*{i,t} / EPS*TTM*{i,t}

where EPS*TTM*{i,t} = sum of the four most recently available quarterly EPS figures as of t.

P/B ratio: PB*{i,t} = P*{i,t} / BVPS\_{i,t}

where BVPS\_{i,t} = (Total Equity / Shares Outstanding) from the most recent balance sheet as of t.

P/S ratio (TTM): PS*{i,t} = MCAP*{i,t} / Revenue*TTM*{i,t}

EV computation:

EV*{i,t} = MCAP*{i,t} + Total*Debt*{i,t} + Minority*Interest*{i,t} - Cash\_{i,t}

where all balance sheet items are from the most recent filing as of t.

EV/EBITDA: EVEBITDA*{i,t} = EV*{i,t} / EBITDA*TTM*{i,t}

EV/Sales: EVSALES*{i,t} = EV*{i,t} / Revenue*TTM*{i,t}

EV/EBIT: EVEBIT*{i,t} = EV*{i,t} / EBIT*TTM*{i,t}

P/CF (operating): PCF*{i,t} = MCAP*{i,t} / OCF*TTM*{i,t}

Earnings Yield (Greenblatt Magic Formula component 1):

EYIELD*{i,t} = EBIT_TTM*{i,t} / EV\_{i,t}

This is EV-based earnings yield. High values = cheap. Used as the valuation component in the Greenblatt Magic Formula (Feature S4).

**Profitability metrics:**

Gross margin: GPM\_{i,t} = (Revenue_TTM - COGS_TTM) / Revenue_TTM

Operating margin: OPM\_{i,t} = EBIT_TTM / Revenue_TTM

Net margin: NPM\_{i,t} = NetIncome_TTM / Revenue_TTM

EBITDA margin: EBITDAM\_{i,t} = EBITDA_TTM / Revenue_TTM

Return on Equity: ROE*{i,t} = NetIncome_TTM*{i,t} / AvgEquity\_{i,t}

where AvgEquity = average of last two available quarterly total equity readings.

Return on Assets: ROA*{i,t} = NetIncome_TTM*{i,t} / AvgAssets\_{i,t}

Return on Invested Capital:

ROIC*{i,t} = EBIT_TTM*{i,t} × (1 - TaxRate*{i,t}) / (AvgEquity*{i,t} + AvgDebt*{i,t} - AvgCash*{i,t})

where TaxRate\_{i,t} = IncomeTaxExpense_TTM / PreTaxIncome_TTM, bounded to [0, 0.50].

This approximates after-tax operating return on the capital base employed. It is the Return on Capital component in the Greenblatt Magic Formula.

Gross Profit / Assets (Novy-Marx, 2013):

GPA*{i,t} = (Revenue_TTM*{i,t} - COGS*TTM*{i,t}) / TotalAssets\_{i,t}

This single metric is the empirically most robust quality predictor in the US cross-section per Novy-Marx (2013, Journal of Financial Economics). Compute it alongside all other profitability metrics.

**Growth metrics:**

Revenue growth YoY:

REVG*{i,t} = Revenue_TTM*{i,t} / Revenue*TTM*{i,t-252} - 1

where Revenue*TTM*{i,t-252} is the TTM revenue as of approximately one year ago (252 trading days prior).

EPS growth YoY: EPSG*{i,t} = EPS_TTM*{i,t} / EPS*TTM*{i,t-252} - 1

Revenue CAGR (3-year): REVG3*{i,t} = (Revenue_TTM*{i,t} / Revenue*TTM*{i,t-756})^{1/3} - 1

where 756 ≈ 3 × 252 trading days.

**Financial health metrics:**

Debt/Equity: DE*{i,t} = TotalDebt*{i,t} / TotalEquity\_{i,t}

Debt/EBITDA: DEBT*EBITDA*{i,t} = TotalDebt*{i,t} / EBITDA_TTM*{i,t}

Current ratio: CR*{i,t} = CurrentAssets*{i,t} / CurrentLiabilities\_{i,t}

Quick ratio: QR*{i,t} = (CurrentAssets*{i,t} - Inventory*{i,t}) / CurrentLiabilities*{i,t}

Interest coverage: IC*{i,t} = EBIT_TTM*{i,t} / InterestExpense*TTM*{i,t}

Accruals / Earnings quality (O'Shaughnessy quality factor):

EARN*QUAL*{i,t} = OCF*TTM*{i,t} / NetIncome*TTM*{i,t}

Values > 1 indicate cash-backed earnings (earnings quality is high). Values < 0 indicate negative operating cash flow despite positive reported earnings — a strong red flag. Values 0-1 indicate partial cash backing.

**Dividend metrics:**

Dividend yield: DIVYLD*{i,t} = DPS_TTM*{i,t} / P\_{i,t}

where DPS_TTM is the trailing twelve months of cash dividends per share from yfinance `Ticker.dividends`.

Payout ratio: PAYOUT*{i,t} = DPS_TTM*{i,t} / EPS*TTM*{i,t}

Dividend-paying filter: I{DPS*TTM*{i,t} > 0} — binary flag for any dividend payment in the trailing year.

---

### Step 6 — Platform-computed signal metrics

The following signals are computed by other modules of the platform and ingested as screener dimensions:

**Volatility forecast (21-day horizon):**

VOL*FORECAST*{i,t} = the annualized 21-day-ahead Yang-Zhang vol forecast from the HAR model (Volatility Intelligence Module Feature 3).

Low-vol universe filter: I{VOL*FORECAST*{i,t} < VOL_THRESHOLD} where VOL_THRESHOLD is user-set.

**Amihud illiquidity ratio (rolling 21-day):**

AMIHUD*{i,t} = (1/21) × Σ*{s=t-20}^{t} |R*{i,s}| / DVOL*{i,s}

This is the Amihud (2002, Journal of Financial Markets) illiquidity measure. Higher values = less liquid (larger price impact per dollar traded). Percentile rank of AMIHUD within the full universe at each date is the screener dimension.

**MAX factor (Bali, Cakici, Whitelaw, 2011):**

MAX*{i,t} = max{R*{i,s} : s ∈ [t-20, t]}

The maximum single-day return over the past 21 days. High MAX predicts negative future returns in the cross-section (investors overpay for lottery-like payoff stocks). The screener filter "exclude high-lottery stocks" sets MAX\_{i,t} < MAX_THRESHOLD.

**Idiosyncratic volatility (IVOL):**

Estimated from the Fama-French three-factor model residuals. Daily FF3 factors downloaded from the Ken French Data Library.

Regress the trailing 63-day return series of stock i on the three factors:

r*{i,s} - rf_s = α_i + β*{MKT,i} × (r*{m,s} - rf_s) + β*{SMB,i} × SMB*s + β*{HML,i} × HML*s + ε*{i,s}

for s ∈ [t-62, t]. OLS estimation.

IVOL*{i,t} = √(252 × (1/63) × Σ*{s=t-62}^{t} ε̂²\_{i,s})

where ε̂\_{i,s} are the OLS residuals. IVOL is annualized.

The Ang, Hodrick, Xing, Zhang (2006, Journal of Finance) finding: high IVOL predicts negative future returns — the idiosyncratic volatility puzzle. The screener uses IVOL as a risk quality filter and a reversal signal.

---

### Step 7 — Cross-sectional percentile normalization

For each metric M and each date t, compute three simultaneous percentile ranks:

**Universe percentile:**

UPCT*{M,i,t} = #{j ∈ U : M*{j,t} < M\_{i,t}} / (|U| - 1) × 100

**Sector percentile:**

SPCT*{M,i,t} = #{j ∈ sector(i) : M*{j,t} < M\_{i,t}} / (|sector(i)| - 1) × 100

**Industry group percentile:**

IGPCT*{M,i,t} = #{j ∈ industry_group(i) : M*{j,t} < M\_{i,t}} / (|industry_group(i)| - 1) × 100

All percentile ranks use the standard rank-based formula with ties resolved by average rank. The output for every metric M at every ticker i is a triplet: (M*{i,t}, UPCT*{M,i,t}, SPCT*{M,i,t}, IGPCT*{M,i,t}).

For valuation metrics (P/E, P/B, EV/EBITDA), the percentile rank is inverted before display in screener tables so that high percentile always means "favorable": cheaper valuation = higher display percentile. The raw value is always available on hover.

---

### Step 8 — Filter evaluation engine

A screen S is defined as a conjunction of K conditions: S = C_1 ∧ C_2 ∧ ... ∧ C_K.

Each condition C*k is of the form: metric M_k ∈ [lb_k, ub_k] or UPCT*{M*k,i,t} ∈ [lb_k, ub_k] or SPCT*{M*k,i,t} ∈ [lb_k, ub_k] or IGPCT*{M_k,i,t} ∈ [lb_k, ub_k].

The filter output set:

F(S, t) = {i ∈ U_sub : C_k(i,t) = True for all k = 1,...,K}

where U_sub is the user-selected universe (full / sector / market cap / custom list).

**Filter funnel waterfall:** After evaluating each condition C_k independently and in sequence:

Funnel_count_k = #{i ∈ U_sub : C_1(i,t) ∧ ... ∧ C_k(i,t) = True}

The funnel displays Funnel*count_0 = |U_sub| → Funnel_count_1 → ... → Funnel_count_K = |F(S,t)|. The step with the largest drop |Funnel_count*{k-1} - Funnel_count_k| is the binding constraint — highlighted in the filter funnel output.

**Sort ranking:** The output set F(S,t) is ranked by a user-selected column M_sort in ascending or descending order. The primary ranking metric has no computational constraint — any of the full metric set may serve as the sort key.

---

### Step 9 — Historical screen evaluation (point-in-time)

For a saved screen S and any historical date τ:

1. Reconstruct all metrics for all tickers using only data available on or before τ: for price metrics, use the price series ending at τ. For fundamental metrics, use only filings with filing_date ≤ τ (strict point-in-time).

2. Evaluate F(S, τ) using the historical data.

3. Return the historical screen result with all metric values as of τ.

This is the same engine used by the Screener Backtester (Feature S5). The point-in-time enforcement is unconditional — no override option. Financial data uses the reporting date, never the fiscal period end date.

---

### Data Map

| Series                                              | Source                  | Identifier                                               | Frequency         |
| --------------------------------------------------- | ----------------------- | -------------------------------------------------------- | ----------------- |
| Adjusted OHLCV                                      | yfinance                | Per ticker                                               | Daily             |
| Raw volume and open price                           | yfinance                | Per ticker                                               | Daily             |
| Income statement (quarterly and annual)             | yfinance                | `Ticker.financials`, `Ticker.quarterly_financials`       | Quarterly         |
| Balance sheet (quarterly and annual)                | yfinance                | `Ticker.balance_sheet`, `Ticker.quarterly_balance_sheet` | Quarterly         |
| Cash flow statement                                 | yfinance                | `Ticker.cashflow`, `Ticker.quarterly_cashflow`           | Quarterly         |
| Dividends                                           | yfinance                | `Ticker.dividends`                                       | Event-based       |
| Ticker metadata (sector, float, shares outstanding) | yfinance                | `Ticker.info`                                            | Quarterly refresh |
| FF3 daily factors (MKT-RF, SMB, HML, RF)            | Ken French Data Library | F-F 3 Factors Daily                                      | Daily             |
| Constituent lists (SPY, MDY, SLY)                   | yfinance ETF holdings   | Static monthly update                                    | Monthly           |

---

## FEATURE S2 — FORMULA BUILDER AND CUSTOM EXPRESSION SCREENER

### What you are building mathematically

A domain-specific expression language parser and evaluator that operates on the full data field set of the platform. The parser accepts a free-text algebraic expression, validates it syntactically and semantically, and evaluates it for every ticker in the universe on every trading day in history. The output of the expression becomes a new derived metric subject to the same cross-sectional percentile normalization as any native metric, enabling filtering and ranking by any combination of raw or cross-sectionally transformed values.

---

### Step 1 — Expression grammar specification

The formula language grammar (defined in Extended Backus-Naur Form):

expr ::= term (('+' | '-') term)_
term ::= factor (('_' | '/') factor)_
factor ::= base ('^' factor)?
base ::= NUMBER | FIELD_NAME | FUNCTION '(' args ')' | '(' expr ')'
args ::= expr (',' expr)_

FUNCTION ::= 'sqrt' | 'abs' | 'log' | 'min' | 'max' | 'if'
| 'lag' | 'rolling_mean' | 'rolling_std' | 'rolling_max' | 'rolling_min'
| 'rank' | 'sector_rank' | 'zscore' | 'sector_zscore'

FIELD_NAME ::= any string in the platform field registry (see Step 2)

NUMBER ::= any floating-point literal

Special functions:
lag(field, N): returns field value N trading days in the past. Equivalent to retrieving field*{i,t-N}.
rolling_mean(field, N): (1/N) × Σ*{s=t-N+1}^{t} field*{i,s}
rolling_std(field, N): √[(1/N) × Σ*{s=t-N+1}^{t} (field*{i,s} - rolling_mean(field,N))²]
rolling_max(field, N): max{field*{i,s} : s ∈ [t-N+1, t]}
rolling*min(field, N): min{field*{i,s} : s ∈ [t-N+1, t]}
rank(field): UPCT*{field,i,t} / 100 ∈ [0,1] — universe percentile rank, normalized to [0,1]
sector_rank(field): SPCT*{field,i,t} / 100 ∈ [0,1] — sector percentile rank
zscore(field): (field*{i,t} - μ_field_t) / σ_field_t where μ and σ are the cross-sectional mean and standard deviation at date t
sector_zscore(field): (field*{i,t} - μ_sector_t) / σ_sector_t where μ and σ are the sector-level cross-sectional mean and standard deviation
if(condition, val_true, val_false): evaluates condition as a boolean (nonzero = true), returns val_true or val_false accordingly

---

### Step 2 — Field registry

The complete set of FIELD_NAME identifiers available in the formula builder:

**Price fields:**
open, high, low, close, adj_close, volume (raw volume)

**Return fields:**
r_1d (daily simple return), r_5d, r_21d, r_63d, r_126d, r_252d (H-day simple return), r_jt (Jegadeesh-Titman 12M-1M momentum)

**Technical fields:**
sma_20, sma_50, sma_100, sma_200 (SMAs)
ema_20, ema_50, ema_200 (EMAs)
rsi_14 (14-period RSI, also rsi_N for any N user-specified in the formula)
macd_line, macd_signal, macd_hist
bb_upper, bb_lower, bb_mid, bb_width
atr_14, atr_pct (ATR as percent of price)
adx_14, dmi_plus, dmi_minus
beta_252 (252-day rolling beta vs. SPY)
stoch_k, stoch_d (stochastic K and D)
williams_r
obv (on-balance volume level)
vratio (20-day volume ratio)
gap (opening gap percent)
h52 (52-week high), l52 (52-week low)
prox52 (George-Hwang 52-week proximity)
dvol_20 (20-day average dollar volume)
mcap (market capitalization)

**Fundamental fields:**
pe_ratio, pb_ratio, ps_ratio, pcf_ratio
ev_ebitda, ev_sales, ev_ebit
eyield (EV-based earnings yield = EBIT/EV)
gross_margin, operating_margin, net_margin, ebitda_margin
roe, roa, roic
gpa (Novy-Marx gross profit / assets)
revenue_growth, eps_growth, revenue_cagr_3y
debt_equity, debt_ebitda, current_ratio, quick_ratio
interest_coverage, earn_qual (OCF/NI earnings quality)
dividend_yield, payout_ratio

**Platform signal fields:**
composite_score (from Feature S3)
vol_forecast_21d (HAR vol forecast from Vol Module)
amihud (21-day Amihud illiquidity ratio)
max_factor (maximum daily return over past 21 days)
ivol (idiosyncratic volatility from FF3 residuals)

**Fama-French daily factors (cross-asset, same value for all tickers on a given date):**
mkt_rf, smb, hml, rmw, cma, mom, rf

---

### Step 3 — Parse, validate, and compile

The expression evaluation pipeline operates in three stages:

**Stage 1 — Lexing and parsing:**
Tokenize the input string into the grammar terminals (NUMBER, FIELD_NAME, FUNCTION, operators, parentheses). Parse using a recursive descent parser over the grammar in Step 1. Output: an abstract syntax tree (AST).

**Stage 2 — Semantic validation:**
Walk the AST. For each FIELD_NAME node: verify the name exists in the field registry (Step 2). For each FUNCTION node: verify argument count matches the function signature (e.g., lag takes exactly 2 arguments; rolling_mean takes exactly 2; if takes exactly 3). Flag all errors with position (character offset in the input string) and a plain-language correction suggestion.

Division by zero protection: at every division node, inject an implicit guard: if denominator = 0, return NaN. NaN propagates through all downstream arithmetic.

**Stage 3 — Compilation to a vectorized evaluation function:**
Convert the validated AST to a Python callable f(data_panel) where data_panel is a pandas DataFrame with shape (N_tickers × T_dates). The callable evaluates the expression across the full panel simultaneously using NumPy / pandas vectorized operations. No Python-level loops over tickers or dates at evaluation time.

For time-series functions (lag, rolling_mean, rolling_std, rolling_max, rolling_min): use pandas rolling window operations with min_periods = N to avoid NaN propagation at the start of the series.

For cross-sectional functions (rank, sector_rank, zscore, sector_zscore): apply groupby over the date axis of the panel, ranking or standardizing within each date's cross-section.

---

### Step 4 — Formula evaluation across universe and history

At the most recent date T:

1. Retrieve the data panel for all tickers in U_sub for the trailing max(all_rolling_windows_in_formula) + lag_max + 252 days (sufficient history to compute all required intermediate series).

2. Call the compiled callable f on the data panel.

3. The output is a vector of length |U*sub|: formula_val*{i,T} for each ticker i.

4. Apply cross-sectional normalization: UPCT*{formula,i,T} and SPCT*{formula,i,T} as in Feature S1 Step 7.

5. Apply the filter condition: retain tickers where formula*val*{i,T} ∈ [lb, ub] (or rank in top N%, or value above/below threshold — user-set).

6. Rank by formula_val descending (or ascending) and return the top K results.

For historical evaluation at date τ: substitute τ for T. All data used is restricted to the window ending at τ — the same point-in-time discipline as Feature S1 Step 9.

---

### Step 5 — Walk-forward formula backtest

For any validated formula expression and its associated filter condition, the backtest evaluates the formula monthly (or at user-set frequency) over the full 10-year history and tracks the performance of the resulting long and short portfolios.

At each rebalancing date τ_k (k = 1, ..., K_rebal):

1. Evaluate f(data_panel ending at τ_k) using only data available on τ_k.

2. Assign tickers to deciles by formula value. Long portfolio L_k = top decile by formula value (or top N as specified). Short portfolio S_k = bottom decile.

3. Track the equal-weight portfolio return from τ*k to τ*{k+1}:

   R*{L,k} = (1/|L_k|) × Σ*{i ∈ L*k} MOM*{i,h,τ_k}

   where h = τ*{k+1} - τ_k (the holding period in trading days) and MOM*{i,h,τ_k} is the forward simple return of ticker i over the holding period.

4. Long-short return: R*{LS,k} = R*{L,k} - R\_{S,k}.

Transaction cost: deduct C × TO_k from each leg's gross return, where C is the per-leg cost in bps (user-set) and TO_k is one-way portfolio turnover:

TO*k = (1/2) × Σ_i |w*{i,k} - w\_{i,k-1}|

where w\_{i,k} = 1/|L_k| if i ∈ L_k and 0 otherwise (and similarly for the short leg).

Performance statistics over the full backtest window [τ_1, τ_K]:

Annualized return: μ*{LS} = 252/h × (1/K) × Σ_k R*{LS,k}

Annualized vol: σ*{LS} = √(252/h) × std(R*{LS,k})

Sharpe: SR*{LS} = (μ*{LS} - rf) / σ\_{LS}

where rf is the annualized Ken French risk-free rate averaged over the backtest period.

---

### Step 6 — Information Coefficient computation for formula ranking

For each rebalancing date τ_k, compute the cross-sectional Spearman rank correlation between the formula output and the subsequent H-day return:

IC*k = SpearmanCorr({rank(formula_val*{i,τ*k}) : i ∈ U_sub}, {rank(R*{i,H,τ_k}) : i ∈ U_sub})

where rank() is the cross-sectional rank operator applied to each vector independently.

The IC represents the formula's cross-sectional predictive content at rebalancing k. IC > 0 means higher-ranked stocks (by formula) tend to subsequently outperform lower-ranked stocks.

Aggregate IC statistics:

Mean IC: IC̄ = (1/K) × Σ_k IC_k

IC standard deviation: σ\_{IC} = std(IC_k)

IC Information Ratio: ICIR = IC̄ / σ\_{IC}

Fraction of periods with positive IC: HIT = #{k : IC_k > 0} / K

The ICIR is the theoretically correct metric for ranking signals (Grinold and Kahn, Active Portfolio Management): it measures the signal's consistency, not just its average strength. A signal with IC̄ = 0.04 and σ*{IC} = 0.02 (ICIR = 2.0) is more reliable than one with IC̄ = 0.06 and σ*{IC} = 0.12 (ICIR = 0.5).

Purged IC (removes look-ahead from overlapping return periods when H > rebalancing frequency): drop IC values computed over return periods that overlap with any future rebalancing date's estimation window. This is the Combinatorial Purged Cross-Validation (CPCV) discipline from Lopez de Prado (2018).

---

### Step 7 — Pre-built template library formulas

Each template is stored as a validated formula string in the registry. Loading a template populates the formula builder with the full expression.

**Piotroski F-Score (Piotroski, 2000):**

F_SCORE = if(roa > 0, 1, 0) + if(earn_qual > 0, 1, 0) + if(roa - lag(roa, 252) > 0, 1, 0) + if(current_ratio - lag(current_ratio, 252) > 0, 1, 0) + if(debt_equity - lag(debt_equity, 252) < 0, 1, 0) + if(lag(mcap, 252) / mcap > 1, 1, 0) + if(gross_margin - lag(gross_margin, 252) > 0, 1, 0) + if(revenue_growth > 0, 1, 0) + if(operating_margin - lag(operating_margin, 252) > 0, 1, 0)

F-Score range: integer in [0, 9]. F ≥ 7 is the Piotroski strong-buy signal. F ≤ 2 is the Piotroski strong-sell / short signal. Note: each term in the sum evaluates to 0 or 1 (the if function handles the binary scoring).

**Altman Z-Score (Altman, 1968, non-manufacturer version):**

ALTMAN_Z = 6.56 × (current_ratio - 1) × current_ratio / (current_ratio + 1)

This is a simplified approximation using available yfinance data. Full specification:

X1 = (CurrentAssets - CurrentLiabilities) / TotalAssets
X2 = RetainedEarnings / TotalAssets
X3 = EBIT / TotalAssets
X4 = TotalEquity / TotalLiabilities
X5 = Revenue / TotalAssets

ALTMAN_Z = 6.56 × X1 + 3.26 × X2 + 6.72 × X3 + 1.05 × X4

(Altman Z''-Score for non-manufacturers excludes X5.) These are computed from direct balance sheet and income statement fields, not via the formula builder (which lacks direct asset-level decomposition); instead, they are pre-computed native metrics in the platform and exposed as `altman_z` in the field registry.

**Greenblatt Magic Formula:**

MAGIC = rank(eyield) + rank(roic)

where rank() gives universe percentile in [0,1]. Higher rank = better. The Magic Formula ranks all stocks by earnings yield (cheap valuation) and by ROIC (capital efficiency), then sums the ranks. The combined rank selects cheap stocks that are also efficiently run businesses.

**Novy-Marx Gross Profitability:**

GROSS_PROFIT = gpa

(Directly available as a native field; the formula builder accesses it as `gpa`.)

**O'Shaughnessy Trending Value:**

TRENDING_VALUE = rank(ev_ebitda) + rank(pe_ratio) + rank(ps_ratio) + rank(pcf_ratio) + rank(ev_sales) + rank(r_126d)

The first five terms form the Value Composite Two (five valuation metrics combined; each rank() inverts so cheap = high rank, handled by the sign convention in the rank normalization). The sixth term adds 6-month price momentum. All six terms carry equal weight. Stocks are ranked by the sum; the top decile is the Trending Value universe.

---

### Data Map

| Series                                                 | Source                           | Identifier                             | Frequency |
| ------------------------------------------------------ | -------------------------------- | -------------------------------------- | --------- |
| All data fields listed in Step 2                       | yfinance / Ken French / Internal | Per field                              | Daily     |
| FF daily factors (MKT-RF, SMB, HML, RMW, CMA, MOM, RF) | Ken French Data Library          | Fama/French 5 Factors + Momentum Daily | Daily     |
| Internal platform signal fields                        | Platform computation pipeline    | —                                      | Daily     |

## FEATURE S3 — COMPOSITE QUANT SCORE ENGINE

### What you are building mathematically

A weighted linear combination of cross-sectionally normalized factor signals into a single composite score, with IC-IR-based optimal weighting, walk-forward validation, sector and beta neutralization, and a full decomposition of each stock's composite score into its factor contributions.

---

### Step 1 — Factor signal normalization pipeline

For each factor F_j (j = 1, ..., J) in the user-selected component set, and for each ticker i at date t:

**Step 1a — Raw factor value:** Retrieve the native metric value from the data layer: f\_{j,i,t}.

**Step 1b — Sign standardization:** Apply sign convention correction so that a higher score always means "more favorable":

For valuation factors (PE, PB, PS, EV/EBITDA, EV/Sales, EV/EBIT, PCF): multiply by -1 before normalization (cheap = low raw value = should map to high score).

For volatility factors (VOL_FORECAST, IVOL, BETA, ATR, AMIHUD): multiply by -1 (low vol = favorable).

For accruals / distress factors (ALTMAN_Z — direct: high = safe = favorable; MAX_FACTOR — inverse: high = unfavorable, multiply by -1): apply the correction per factor.

All other factors (momentum, profitability, growth, quality): no sign change (higher raw value = better).

Let g*{j,i,t} = sign_j × f*{j,i,t} where sign_j ∈ {+1, -1} encodes the sign correction.

**Step 1b — Winsorization:**

Winsorize at the 1st and 99th cross-sectional percentiles to remove outlier contamination:

g*{j,i,t}^{w} = max(P1*{j,t}, min(P99*{j,t}, g*{j,i,t}))

where P1*{j,t} = 1st percentile of {g*{j,i,t} : i ∈ U*sub} and P99*{j,t} = 99th percentile.

**Step 1c — Cross-sectional z-score normalization:**

z*{j,i,t} = (g*{j,i,t}^{w} - μ*{j,t}) / σ*{j,t}

where μ*{j,t} = (1/|U_sub|) × Σ_i g*{j,i,t}^{w} and σ*{j,t} = std({g*{j,i,t}^{w} : i ∈ U_sub}) are the cross-sectional mean and standard deviation after winsorization.

The z-score is approximately N(0,1) cross-sectionally by construction. Range approximately [-3, +3] after winsorization.

**Optional — Sector neutralization:**

Subtract the sector-level cross-sectional mean before normalization:

z*{j,i,t}^{sn} = (g*{j,i,t}^{w} - μ*{j,sector(i),t}) / σ*{j,sector(i),t}

where the mean and standard deviation are computed within ticker i's GICS sector. When sector neutralization is active, the composite score measures within-sector relative rank, not cross-sector exposure. This eliminates sector bets from the composite.

**Optional — Beta neutralization:**

After computing the composite score (Step 2), regress it on the cross-sectional vector of BETA\_{i,t}:

SCORE*{i,t}^{bn} = SCORE*{i,t} - β̂*{BETA} × BETA*{i,t}

where β̂*{BETA} = OLS slope from regressing SCORE*{i,t} on BETA\_{i,t} cross-sectionally. This removes the component of the composite score linearly explained by market beta, ensuring the score represents stock selection alpha independent of market exposure.

---

### Step 2 — Component weighting

The composite score at date t for ticker i under J factors with weight vector w = (w_1, ..., w_J)' (w_j ≥ 0, Σ_j w_j = 1):

SCORE*{i,t} = Σ*{j=1}^{J} w*j × z*{j,i,t}

**Weighting Mode 1 — Equal weight:**

w_j = 1/J for all j. The baseline. Robust to estimation error in the weights (no in-sample fitting).

**Weighting Mode 2 — IC-IR weighting (theoretically optimal per Grinold-Kahn):**

Compute the rolling IC for each factor j at each rebalancing date τ_k:

IC*{j,k} = SpearmanCorr({z*{j,i,τ*k} : i ∈ U_sub}, {rank(R*{i,H,τ_k}) : i ∈ U_sub})

where H is the composite's target horizon and R\_{i,H,τ_k} is the forward H-day simple return.

Rolling IC statistics over the trailing W_IC rebalancing dates (W_IC ∈ {4, 8, 16} quarters, user-set):

IC̄*j = (1/W_IC) × Σ*{k'=k-W*IC+1}^{k} IC*{j,k'}

σ*{IC,j} = std({IC*{j,k'} : k' ∈ [k-W_IC+1, k]})

ICIR*j = IC̄_j / σ*{IC,j}

IC-IR weights: w*j = max(ICIR_j, 0) / Σ*{j'} max(ICIR\_{j'}, 0)

Factors with non-positive ICIR receive zero weight (they are currently destroying information relative to the naive equal-weight composite). The max(., 0) constraint prevents negative weights.

These weights are recomputed at each rebalancing date using only data from prior periods. No look-ahead: the weight at τ*k uses IC estimates computed through τ*{k-1} only.

**Weighting Mode 3 — User-defined manual weights:**

w*j = user-input percentage for each factor j, normalized: w_j^{norm} = w_j / Σ*{j'} w\_{j'}.

**Weighting Mode 4 — Ridge-regularized OLS:**

Regress forward H-day returns on the J factor z-scores using ridge regression:

minimize over β: Σ*i (R*{i,H,τ*k} - β_0 - Σ_j β_j z*{j,i,τ_k})² + λ × Σ_j β_j²

where λ is the ridge penalty (estimated by leave-one-out cross-validation on the trailing 8 quarters).

The ridge solution:

β̂\_{ridge} = (Z'Z + λI_J)^{-1} Z'y

where Z is the T_train × J matrix of factor z-scores and y is the T_train × 1 vector of forward returns.

Weights: w*j = max(β̂*{ridge,j}, 0) / Σ*{j'} max(β̂*{ridge,j'}, 0) (positive weights only, same truncation as IC-IR mode).

---

### Step 3 — Score normalization and output scaling

After computing SCORE*{i,t} = Σ_j w_j z*{j,i,t}:

The composite score is already approximately standard-normal cross-sectionally (since each z\_{j,i,t} is normalized and the weights sum to 1). Its cross-sectional mean is approximately 0 and its standard deviation is approximately √(Σ_j w_j²) < 1 due to imperfect factor correlation.

**Output scale options:**

0–100 percentile output: SCORE*PCT*{i,t} = UPCT\_{SCORE,i,t} (universe percentile of the composite score).

Z-score output: SCORE\_{i,t} directly (approximately in [-3, +3]).

Normalized to [-1, +1]: SCORE*NORM*{i,t} = 2 × UPCT\_{SCORE,i,t}/100 - 1.

---

### Step 4 — Score decomposition (waterfall attribution)

For ticker i at date t, the contribution of factor j to the composite score:

CONTRIB*{j,i,t} = w_j × z*{j,i,t}

These contributions sum to the total composite: Σ*j CONTRIB*{j,i,t} = SCORE\_{i,t}.

The waterfall chart displays CONTRIB\_{j,i,t} as a signed bar for each j, ordered from largest positive contribution to largest negative. The sum equals the composite score displayed as the final bar.

This decomposition answers: "Why does stock X have a composite score of 72? Because momentum contributed +0.6, gross profitability contributed +0.4, low vol contributed +0.3, but its valuation subtracted -0.5 due to elevated P/E."

---

### Step 5 — Component IC-IR leaderboard

At each date t (or rebalancing date τ_k), compute the rolling ICIR for every factor j in the full platform signal library (not just those selected for the composite):

This produces a leaderboard of all available signals ranked by their current ICIR. The leaderboard answers: "Which signals are working best right now in this universe?" A regime change from low to high vol will typically elevate the low-vol factor's ICIR and depress the growth factor's ICIR — the leaderboard shows this shift in real time, guiding composite weight updates before the weights formally rebalance.

---

### Step 6 — Factor correlation heatmap

At each date t, compute the J × J pairwise Pearson correlation matrix of the factor z-scores cross-sectionally:

ρ*{jj',t} = Corr({z*{j,i,t} : i ∈ U*sub}, {z*{j',i,t} : i ∈ U_sub})

= Σ*i (z*{j,i,t} - z̄*j)(z*{j',i,t} - z̄*{j'}) / √[Σ_i (z*{j,i,t} - z̄*j)² × Σ_i (z*{j',i,t} - z̄\_{j'})²]

For factor pairs with |ρ\_{jj',t}| > 0.6: flag as "redundant pair." When two redundant factors are combined at equal weight, the effective weight on their shared information is 2 × individual weight, double-counting the same cross-sectional variation rather than diversifying across independent sources of alpha.

Effective number of independent factors:

N*{eff,t} = (Σ_j w_j)² / Σ_j w_j² × (1 / (1 + avg*ρ_t))

where avg*ρ_t = average pairwise correlation among all J factors (a scalar). N*{eff,t} ∈ [1, J]: closer to J means factors are independent (high diversification); closer to 1 means factors are all measuring the same thing.

---

### Step 7 — Regime-conditional composite performance

The composite's IC is decomposed by identified market regime. The regime state at each date is provided by the Volatility Module's regime detection output (Feature 4 of the Volatility Intelligence Module): p_composite(t) ∈ ΔK.

For each regime k:

IC̄*{j,k} = Σ_t p_composite(t)[k] × IC*{j,k(t)} / Σ_t p_composite(t)[k]

where IC\_{j,k(t)} is the factor j's IC at the rebalancing date nearest to t.

This probability-weighted mean IC by regime answers: "In high-vol regimes, what is the momentum factor's IC?" If IC̄*{momentum,high-vol} ≈ 0 but IC̄*{momentum,low-vol} = 0.05, then the composite should down-weight momentum in the current high-vol regime and up-weight quality or low-vol factors.

---

### Step 8 — Composite vs. individual factor backtest

For each individual factor j in the composite and for the full composite, compute the identical backtest procedure as Feature S2 Step 5 (same universe, same holding period, same transaction cost model). The comparison outputs:

Rolling 12-month Sharpe for the composite and for each constituent factor, plotted simultaneously. The composite Sharpe should lie above or near the best individual factor Sharpe in most periods (the benefit of combining signals). Periods where the composite underperforms its best constituent are periods of high factor correlation (N\_{eff} is low) — the heatmap from Step 6 will confirm this.

---

### Data Map

| Series                             | Source                               | Identifier | Frequency |
| ---------------------------------- | ------------------------------------ | ---------- | --------- |
| All factor z-scores                | Internal computation from Feature S1 | —          | Daily     |
| Forward returns for IC computation | yfinance adjusted close              | Per ticker | Daily     |
| Regime probability vector          | Volatility Module Feature 4 output   | —          | Daily     |
| Ken French risk-free rate          | Ken French Data Library              | RF column  | Daily     |

---

## FEATURE S4 — ACADEMIC STRATEGY SCREENER LIBRARY

### What you are building mathematically

Pre-computation of every major academic and practitioner quantitative stock selection formula for all tickers daily, implemented as native metrics in the data layer using the field registry from Feature S2. Each strategy produces a ranked score for every ticker and a backtested performance record. The library is a real-time signal dashboard, not a static reference collection.

---

### Step 1 — Piotroski F-Score (Piotroski, 2000)

Nine binary signals in three categories. All nine binary tests use the most recent quarterly filing data available in point-in-time discipline.

**Profitability signals (4):**

F1 = I{ROA\_{i,t} > 0} — positive return on assets in the most recent period.

F2 = I{OCF*TTM*{i,t} > 0} — positive operating cash flow.

F3 = I{ROA*{i,t} > ROA*{i,t-252}} — ROA improving year-over-year.

F4 = I{OCF*TTM*{i,t} / TotalAssets*{i,t} > ROA*{i,t}} — cash flow exceeds accrual earnings (earnings quality signal; Sloan accruals logic).

**Leverage and liquidity signals (3):**

F5 = I{LongTermDebt*{i,t}/TotalAssets*{i,t} < LongTermDebt*{i,t-252}/TotalAssets*{i,t-252}} — leverage declining.

F6 = I{CurrentRatio*{i,t} > CurrentRatio*{i,t-252}} — liquidity improving.

F7 = I{SharesOutstanding*{i,t} ≤ SharesOutstanding*{i,t-252}} — no dilutive share issuance (the Piotroski "accretion" signal).

**Operating efficiency signals (2):**

F8 = I{GrossMargin*{i,t} > GrossMargin*{i,t-252}} — gross margin improving.

F9 = I{Revenue*TTM*{i,t}/TotalAssets*{i,t} > Revenue_TTM*{i,t-252}/TotalAssets\_{i,t-252}} — asset turnover improving (asset efficiency increasing).

Composite: FSCORE*{i,t} = Σ*{k=1}^{9} Fk ∈ {0, 1, ..., 9}

Score interpretation: F ≥ 7 is the Piotroski strong-buy signal (historically significant positive forward returns). F ≤ 2 is the short signal. F ∈ {3,...,6} is neutral territory.

---

### Step 2 — Altman Z-Score (Altman, 1968 and Z''-Score revision)

**For manufacturing companies:**

X1*{i,t} = (CurrentAssets*{i,t} - CurrentLiabilities*{i,t}) / TotalAssets*{i,t}

X2*{i,t} = RetainedEarnings*{i,t} / TotalAssets\_{i,t}

X3*{i,t} = EBIT_TTM*{i,t} / TotalAssets\_{i,t}

X4*{i,t} = MCAP*{i,t} / TotalLiabilities\_{i,t}

X5*{i,t} = Revenue_TTM*{i,t} / TotalAssets\_{i,t}

Z*MFG*{i,t} = 1.2 × X1 + 1.4 × X2 + 3.3 × X3 + 0.6 × X4 + 1.0 × X5

Zone classification: Z > 2.99 (safe zone), 1.81 ≤ Z ≤ 2.99 (grey zone), Z < 1.81 (distress zone).

**For non-manufacturers (Z''-Score):** Excludes X5 (asset turnover) since it is not a reliable profitability signal for service and financial companies.

Z*NMF*{i,t} = 6.56 × X1 + 3.26 × X2 + 6.72 × X3 + 1.05 × X4

Zone classification: Z'' > 2.60 (safe), 1.10 ≤ Z'' ≤ 2.60 (grey), Z'' < 1.10 (distress).

The classification is applied automatically based on GICS sector: Industrials and Materials use Z_MFG; all other sectors use Z_NMF.

---

### Step 3 — Greenblatt Magic Formula (Greenblatt, The Little Book That Beats the Market)

**Earnings Yield rank:**

EY*RANK*{i,t} = UPCT\_{EYIELD,i,t} / 100 ∈ [0,1]

**Return on Capital rank:**

ROC*{i,t} = EBIT_TTM*{i,t} / (NetWorkingCapital*{i,t} + NetFixedAssets*{i,t})

where NetWorkingCapital*{i,t} = (CurrentAssets*{i,t} - ExcessCash*{i,t}) - CurrentLiabilities*{i,t}

ExcessCash is approximated as max(Cash*{i,t} - max(0, CurrentLiabilities*{i,t} - (CurrentAssets*{i,t} - Cash*{i,t})), 0)

NetFixedAssets*{i,t} = TotalAssets*{i,t} - CurrentAssets*{i,t} - Goodwill*{i,t} - IntangibleAssets\_{i,t}

ROC*RANK*{i,t} = UPCT\_{ROC,i,t} / 100 ∈ [0,1]

**Magic Formula score:**

MAGIC*{i,t} = EY_RANK*{i,t} + ROC*RANK*{i,t} ∈ [0, 2]

Rank stocks by MAGIC descending. The top decile by MAGIC is the Magic Formula buy universe.

---

### Step 4 — Acquirer's Multiple (Carlisle)

AM*{i,t} = EV*{i,t} / EBIT*TTM*{i,t}

Lower AM = cheaper acquisition target (the company's operating earnings are large relative to total enterprise value). This is the single most predictive univariate valuation metric in the empirical literature on long-horizon value returns (Carlisle, The Acquirer's Multiple).

Rank stocks by AM ascending (lowest AM = highest rank).

---

### Step 5 — Novy-Marx Gross Profitability (Novy-Marx, 2013)

GP*{i,t} = (Revenue_TTM*{i,t} - COGS*TTM*{i,t}) / TotalAssets\_{i,t}

This is field `gpa` in the registry. The Novy-Marx (2013, Journal of Financial Economics) result: GP/Assets is the single most statistically significant quality predictor in the US cross-section over 1963-2010, with a t-statistic exceeding most momentum, value, and investment-policy signals.

The economic interpretation: gross profit measures the value added by the firm's core business activities before SGA and R&D (which are more discretionary and subject to accounting manipulation). Scaling by total assets controls for asset intensity.

Rank stocks by GP descending.

---

### Step 6 — Sloan Accruals (Sloan, 1996)

ACCRUAL*{i,t} = (NetIncome_TTM*{i,t} - OCF*TTM*{i,t}) / TotalAssets\_{i,t}

The Sloan (1996, The Accounting Review) finding: high accruals predict negative future returns. The interpretation: when earnings significantly exceed cash flow (high accruals), the earnings component not backed by cash tends to reverse — the reversal is driven by investors initially failing to price the lower persistence of accrual-based earnings components relative to cash flow components.

As a screener dimension: ACCRUAL predicts returns negatively (low accruals = favorable). Sign correction applied in Feature S3 Step 1 (multiply by -1 before normalization).

---

### Step 7 — Jegadeesh-Titman Momentum (Jegadeesh and Titman, 1993)

JT*{i,t} = MOM*{i,JT,t} = P*{i,t-21} / P*{i,t-252} - 1

as computed in Feature S1 Step 2. The one-month skip is mandatory per the original specification. Rank stocks by JT descending.

**Dual Momentum (Antonacci):**

Absolute momentum filter: I{MOM*{i,252,t} > rf*{trailing_252}} — only include stocks that have outperformed the risk-free rate over the past 252 days (positive absolute momentum).

Relative momentum score (within the filtered set): JT\_{i,t}.

Dual Momentum buy universe: the intersection of {i : absolute momentum filter passes} ∩ {top decile by JT}.

**Quantitative Momentum (Gray and Vogel):**

The additional condition beyond JT: momentum smoothness filter. A stock that gained +40% over 12 months via a single spike and then corrected -30% is less predictive than a stock that gained +40% gradually.

Momentum smoothness (MOM_SMOOTH):

MOM*SMOOTH*{i,t} = 1 / σ*{MOM*{i,s} : s ∈ [t-252, t-21], monthly intervals}

where the standard deviation is computed over the monthly return series within the 12-month window. Higher MOM_SMOOTH = more consistent momentum = stronger QM signal.

QM score: QM*{i,t} = rank(JT*{i,t}) + rank(MOM*SMOOTH*{i,t})

---

### Step 8 — O'Shaughnessy Value Composite Two (O'Shaughnessy)

Five valuation metrics, each individually cross-sectionally ranked, then summed. Sign correction: each is inverted so that cheap (low raw value) = high rank.

VC2*{i,t} = rank(-EV/EBITDA*{i,t}) + rank(-PE*{i,t}) + rank(-PS*{i,t}) + rank(-PCF*{i,t}) + rank(-EV/Sales*{i,t})

where rank() returns the universe percentile in [0,1].

Note: excludes P/B ratio (per the 2024 O'Shaughnessy SSRN update finding that P/B has become unreliable as a value signal in the modern economy due to the growing importance of intangible assets).

Tickers with negative values for any constituent metric are excluded from that metric's rank (assigned rank = 0 for that component).

**Trending Value:** VC2 combined with 6-month price momentum:

TV*{i,t} = rank(VC2*{i,t}) + rank(MOM\_{i,126,t})

Rank by TV descending. The top decile is the Trending Value universe.

---

### Step 9 — Conservative Formula (Pim van Vliet, 2016)

Three components, each individually ranked:

**Low volatility:**

LOW*VOL*{i,t} = rank(-VOL*FORECAST*{i,t}) or rank(-β252\_{i,t}) (user toggle)

**Net payout yield:**

NET*PAYOUT*{i,t} = (Dividends*TTM*{i,t} + Buybacks*TTM*{i,t} - NetIssuance*TTM*{i,t}) / MCAP\_{i,t}

where Buybacks = reduction in shares outstanding × average price (approximated from share count changes in yfinance), and NetIssuance = new share issuances. Payout yield is approximated from available yfinance data as:

NET*PAYOUT*{i,t} ≈ DIVYLD*{i,t} + max(SharesOutstanding*{i,t-252} - SharesOutstanding*{i,t}, 0) × P*{i,t} / MCAP\_{i,t}

**Momentum:**

MOM12*6*{i,t} = MOM\_{i,126,t} (6-month return momentum, skips most recent month is optional in van Vliet's original specification)

**Conservative Formula composite:**

CF*{i,t} = rank(LOW_VOL*{i,t}) + rank(NET*PAYOUT*{i,t}) + rank(MOM12*6*{i,t})

Rank by CF descending.

---

### Step 10 — Quality Minus Junk approximation (Asness, Frazzini, Pedersen, 2019)

The QMJ score combines four quality dimensions, each itself a composite of multiple sub-signals.

**Profitability:**

PROF*{i,t} = zscore(gpa*{i,t}) + zscore(roe*{i,t}) + zscore(roa*{i,t}) + zscore(operating*margin*{i,t}) + zscore(earn*qual*{i,t})

**Growth:**

GROW*{i,t} = zscore(revenue_growth*{i,t}) + zscore(eps*growth*{i,t}) + zscore(roa*{i,t} - lag(roa*{i,t}, 252))

**Safety:**

SAFE*{i,t} = zscore(-beta_252*{i,t}) + zscore(-ivol*{i,t}) + zscore(-amihud*{i,t}) + zscore(-debt*ebitda*{i,t}) + zscore(interest*coverage*{i,t})

**Payout:**

PAYOUT*{i,t} = zscore(earn_qual*{i,t}) + zscore(-payout*ratio*{i,t})

Note: lower payout ratio = higher retained earnings for reinvestment = favorable in the AQR specification (inverted).

**QMJ composite:**

QMJ*{i,t} = zscore(PROF*{i,t}) + zscore(GROW*{i,t}) + zscore(SAFE*{i,t}) + zscore(PAYOUT\_{i,t})

All zscore() functions are cross-sectional z-scores at each date t. Rank by QMJ descending.

---

### Step 11 — Meb Faber Shareholder Yield (Faber, 2013)

SY*{i,t} = DIVYLD*{i,t} + BUYBACK*YIELD*{i,t} + DEBT*PAYDOWN_YIELD*{i,t}

BUYBACK*YIELD*{i,t} = max(SharesOutstanding*{i,t-252} - SharesOutstanding*{i,t}, 0) × P*{i,t} / MCAP*{i,t}

DEBT*PAYDOWN_YIELD*{i,t} = max(TotalDebt*{i,t-252} - TotalDebt*{i,t}, 0) / MCAP\_{i,t}

(Only positive debt paydown counts; debt increases penalize the shareholder yield but not below zero on this component.)

Rank by SY descending.

---

### Step 12 — ERP5 (Ensemble of Earnings-Related Price multiples)

ERP5*{i,t} = rank(EYIELD*{i,t}) + rank(ROIC*{i,t}) + rank(EYIELD_5Y_AVG*{i,t}) + rank(ROIC*5Y_AVG*{i,t}) + rank(MOM\_{i,252,t})

where EYIELD_5Y_AVG and ROIC_5Y_AVG are 5-year trailing averages of the respective metrics (using all available quarterly filings over the prior 5 years).

This extends the Greenblatt Magic Formula by incorporating historical average earnings quality and valuation, reducing sensitivity to single-period anomalies.

---

### Step 13 — Strategy IC leaderboard and cross-strategy correlation

For each strategy S_m (m = 1, ..., M strategies in the library) and each rebalancing date τ_k:

IC*{m,k} = SpearmanCorr({SCORE*{m,i,τ*k} : i ∈ U_sub}, {rank(R*{i,H,τ_k}) : i ∈ U_sub})

Rolling ICIR*{m} = IC̄_m / σ*{IC,m} over the trailing 8 quarters.

Pairwise strategy score correlation: ρ*{mm'} = Corr({SCORE*{m,i,t}}, {SCORE\_{m',i,t}}) cross-sectionally at date t.

The M × M correlation matrix identifies which strategies are genuinely distinct (low ρ) and which are effectively the same signal with different labels (high ρ). For two strategies with ρ > 0.80: flag them as "functionally redundant" and recommend running only the one with the higher ICIR.

---

### Data Map

| Series                  | Source                                    | Identifier          | Frequency        |
| ----------------------- | ----------------------------------------- | ------------------- | ---------------- |
| All fundamental metrics | yfinance financials (point-in-time)       | Per ticker          | Quarterly update |
| Price and return series | yfinance adjusted close                   | Per ticker          | Daily            |
| IVOL                    | Ken French FF3 factors + yfinance returns | Computed internally | Daily            |
| Beta                    | yfinance returns vs. SPY                  | Computed internally | Daily            |

---

## FEATURE S5 — SCREENER BACKTESTER WITH POINT-IN-TIME VALIDATION

### What you are building mathematically

A walk-forward portfolio simulation engine that replays any saved screen at a user-defined rebalancing frequency over any historical window, using strictly point-in-time data, correct survivorship bias treatment, explicit transaction cost modeling, and statistically valid performance attribution including Probability of Backtest Overfitting via Monte Carlo simulation.

---

### Step 1 — Data universe reconstruction at historical date τ

At each historical rebalancing date τ:

**Step 1a — Ticker eligibility:** A ticker i is eligible for inclusion in the historical universe at date τ if:

(a) i was listed (first trading date ≤ τ), and
(b) i was not delisted or bankrupt before date τ (last trading date > τ), and
(c) at least 252 trading days of price history exist for i ending at τ.

**Survivorship bias correction:** Include all tickers that were eligible at τ, including those that subsequently delisted, merged, or went bankrupt after τ. The yfinance delisted ticker database provides the final return series for each delisted stock: the last available return (typically -100% for bankruptcy, or the acquisition premium for mergers) is included in the portfolio return for any position that was held when the delisting event occurred.

**Step 1b — Metric reconstruction:** Compute all metrics for all eligible tickers using data ending exactly at τ:

For price metrics: use the price series ending at τ.

For technical indicators: use only the OHLCV series available at τ.

For fundamental metrics: use only quarterly filings with filing_date ≤ τ. The relevant prior-quarter filing is the most recent report filed on or before τ.

This is the strictest point-in-time discipline: the fundamental data available at τ is exactly what an investor would have had access to on date τ.

---

### Step 2 — Screen evaluation at historical date τ

Apply the saved screen S to the reconstructed universe at τ:

F(S, τ) = {i ∈ U(τ) : all K filter conditions C_k(i,τ) are satisfied}

where U(τ) is the eligible ticker universe at τ and C_k(i,τ) is condition k evaluated with τ-dated data.

Rank F(S, τ) by the user-specified sort metric to produce the portfolio.

---

### Step 3 — Portfolio construction at historical date τ

**Long-only equal-weight top N:**

w\_{i,τ}^{L} = 1/N if i is in the top N stocks of F(S,τ) ranked by sort metric, else 0.

**Long-short (top decile long, bottom decile short):**

|F(S,τ)| = total passing stocks. N_D = floor(|F(S,τ)| / 10) = decile size.

Long leg: w\_{i,τ}^{L} = 1/N_D for i in the top N_D by sort metric.

Short leg: w\_{i,τ}^{S} = -1/N_D for i in the bottom N_D by sort metric.

**Score-weighted:**

w*{i,τ}^{L} = SCORE*{i,τ} / Σ*{j ∈ F(S,τ)} SCORE*{j,τ} for long positions (assuming SCORE > 0 for all passing tickers by the filter condition).

---

### Step 4 — Forward return computation

For each position i held from τ to τ + h (the holding period):

R*{i,h,τ} = P*{i,τ+h}^{adj} / P\_{i,τ}^{adj} - 1 (simple H-day return)

For delisted tickers: use the final available return through the delisting date, then 0 for any remaining days in the holding period if the stock becomes unavailable (bankruptcy assignment: assign -100% on the delisting day).

Portfolio H-day gross return:

R*{p,h,τ}^{L} = Σ_i w*{i,τ}^{L} × R\_{i,h,τ}

Long-short return: R*{p,h,τ}^{LS} = R*{p,h,τ}^{L} - R\_{p,h,τ}^{S}

---

### Step 5 — Transaction cost adjustment

One-way turnover at each rebalancing date τ:

TO*τ = (1/2) × Σ_i |w*{i,τ}^{new} - w\_{i,τ}^{old}|

where w*{i,τ}^{old} is the drifted weight from the prior rebalancing (holding period return has altered weights) and w*{i,τ}^{new} is the rebalanced target weight.

Net portfolio return:

R*{p,h,τ}^{net} = R*{p,h,τ}^{gross} - 2 × C × TO_τ

where C is the per-leg transaction cost in decimal (5 bps = 0.0005). The factor 2 applies because TO_τ is one-way; round-trip costs affect the full traded quantity.

---

### Step 6 — Full performance statistics

Over the OOS evaluation window [τ_1, ..., τ_K] with K rebalancing dates and holding period h:

**Annualized gross return:**

μ*gross = (Π*{k=1}^{K} (1 + R\_{p,h,τ_k}^{L}))^{252/(K×h)} - 1

**Annualized net return:**

μ*net = (Π*{k=1}^{K} (1 + R\_{p,h,τ_k}^{net}))^{252/(K×h)} - 1

**Annualized volatility:**

σ*p = std(R*{p,h,τ_k}^{net}) × √(252/h)

**Sharpe ratio (using Ken French risk-free rate rf):**

SR = (μ_net - rf) / σ_p

where rf is the annualized average of the Ken French daily RF column over the backtest period.

**Sortino ratio:**

Downside deviation: σ*D = √[(252/h) × (1/K) × Σ_k min(R*{p,h,τ_k}^{net} - rf/252, 0)²]

SORTINO = (μ_net - rf) / σ_D

**Maximum drawdown:**

Cumulative return series: V*k = Π*{j=1}^{k} (1 + R\_{p,h,τ_j}^{net})

Running maximum: M*k = max*{j ≤ k} V_j

Drawdown at k: DD_k = (V_k - M_k) / M_k

MDD = min_k DD_k

**Recovery time:** Number of rebalancing periods from the MDD date to the next date where V*k ≥ M*{MDD} (the drawdown trough).

**Calmar ratio:** μ_net / |MDD|

**Hit rate:** HIT = #{k : R\_{p,h,τ_k}^{net} > 0} / K

**Average gain / average loss:** E[R|R>0] / |E[R|R<0]|

**Information ratio vs. benchmark:**

Track benchmark B return at each τ: R*{B,h,τ_k} = P*{B,τ*k+h}/P*{B,τ_k} - 1

Active return: AR*k = R*{p,h,τ*k}^{net} - R*{B,h,τ_k}

IR = (252/h × (1/K) × Σ_k AR_k) / (std(AR_k) × √(252/h))

---

### Step 7 — Rolling performance

Rolling 12-month Sharpe (each point uses trailing 12 months of rebalancing periods):

SR*{roll,k} = (252/h × mean(R^{net}*{p,h,τ*{k-J+1:k}})) / (std(R^{net}*{p,h,τ\_{k-J+1:k}}) × √(252/h))

where J = 12 months / h (number of rebalancing periods in a 12-month window).

Similarly compute rolling 36-month Sharpe.

---

### Step 8 — Holding period sensitivity analysis

For H ∈ {1, 5, 21, 63, 126, 252} trading days: run the full backtest procedure (Steps 1–6) independently at each holding period. Report SR_H for each.

The resulting curve SR_H vs. H is the holding period sensitivity curve. Its shape classifies the strategy:

Sharp peak at H = 5 or 21: the strategy has a specific optimal holding horizon; performance degrades sharply outside it. Fragile — operationally sensitive.

Flat plateau from H = 21 to H = 126: the strategy is robust to holding period choice. Robust — operationally forgiving.

Monotonically decreasing from H = 1: signal decays rapidly; likely driven by microstructure or short-term reversal. Usually not robust at institutional scale due to transaction costs.

---

### Step 9 — Rebalancing date sensitivity

For a fixed holding period H (user-set, default H = 21):

Define D = day-of-week offsets ∈ {0 (Monday), 1, 2, 3, 4 (Friday)}.

For each offset d: rebalance on all dates τ with day_of_week(τ) = d. Run the full backtest.

Report SR_d for each d ∈ {0,1,2,3,4}. The range max(SR_d) - min(SR_d) measures rebalancing sensitivity. If this range exceeds 0.5, the strategy's performance is substantially an artifact of entry timing, not signal content.

---

### Step 10 — Monte Carlo backtest overfitting test

S = number of simulation trials (user-set, default 1,000).

For each trial s = 1,...,S:

1. Randomly permute the rebalancing dates: draw K dates uniformly at random from the full calendar (or bootstrap with replacement from the actual rebalancing dates).

2. Evaluate the screen at each permuted date using point-in-time data.

3. Compute the Sharpe ratio SR_s.

The S Sharpe ratios {SR_s} form the empirical null distribution: the distribution of Sharpe ratios achievable by this screen under random timing.

**Probability of Backtest Overfitting (PBO):**

PBO = #{s : SR_s > SR_benchmark} / S

where SR_benchmark is the Sharpe of the buy-and-hold benchmark over the same window.

PBO interpretation: if PBO > 0.50, the strategy has less than 50% probability of out-of-sample success — statistically, it is as likely to underperform as outperform the benchmark under random conditions.

A strategy reporting SR = 1.2 with PBO = 0.72 is a strategy whose Sharpe was very likely inflated by specific timing artifacts. A strategy with SR = 0.7 and PBO = 0.18 has genuine signal content.

**5th and 95th percentile Sharpe from Monte Carlo:** The confidence interval on the reported Sharpe. If the 5th percentile SR is 0.2 and the 95th is 1.8, the confidence interval is wide — the Sharpe is highly sensitive to specific path realizations.

---

### Step 11 — Sector attribution

For each GICS sector c and each rebalancing date τ_k:

Sector weight in portfolio: w*{c,τ_k} = Σ*{i : sector(i)=c} w\_{i,τ_k}^{L}

Sector contribution to period return:

CONTRIB*{c,τ_k} = Σ*{i : sector(i)=c} w*{i,τ_k}^{L} × R*{i,h,τ_k}

Total portfolio return decomposition: R*{p,h,τ_k}^{L} = Σ_c CONTRIB*{c,τ_k}

Cumulative sector contribution over all K rebalancing dates:

TOTAL*CONTRIB_c = Σ*{k=1}^{K} CONTRIB\_{c,τ_k}

The fraction of total portfolio return attributable to sector c: TOTAL*CONTRIB_c / Σ*{c'} |TOTAL*CONTRIB*{c'}|.

A screen claiming stock-selection alpha but with 80%+ of return from a single sector is a disguised sector bet.

---

### Data Map

| Series                         | Source                                                     | Identifier                           | Frequency |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------ | --------- |
| Full adjusted OHLCV history    | yfinance                                                   | Per ticker                           | Daily     |
| Delisted ticker price series   | yfinance (delisted tickers accessible via historical data) | Per ticker                           | Daily     |
| Fundamental filings with dates | yfinance                                                   | `Ticker.financials` with index dates | Quarterly |
| Ken French risk-free rate      | Ken French Data Library                                    | RF column                            | Daily     |
| Benchmark (SPY)                | yfinance                                                   | SPY                                  | Daily     |

---

## FEATURE S6 — ALERT ENGINE AND WATCHLIST MONITOR

### What you are building mathematically

A stateful monitoring system that records the state of each saved screen and watchlist metric at the close of each trading day, detects state changes satisfying user-defined trigger conditions, logs all triggered alerts, and tracks the forward performance of all alert events — converting the alert system into a validated, self-improving signal detection layer.

---

### Step 1 — State snapshot storage

At the end of each trading day t, compute and store the state vector for each ticker i in every active watchlist W:

STATE*{i,t} = (P*{i,t}, SCORE*{i,t}, all_active_metrics*{i,t}, screen*membership*{S,i,t} for all active screens S)

where screen*membership*{S,i,t} = I{i ∈ F(S,t)}: binary membership of ticker i in screen S at date t.

The state is stored as a time-indexed record. The change detection step compares STATE*{i,t} against STATE*{i,t-1} to identify alert conditions.

---

### Step 2 — Alert condition evaluation

For each alert rule R_k (k = 1, ..., K_alert) defined by the user, and for each ticker i in scope:

**Screen membership change:** ENTRY*{S,i,t} = I{i ∈ F(S,t)} - I{i ∈ F(S,t-1)} = +1 (new entry). EXIT*{S,i,t} = -1 (exit). Fire alert when ENTRY or EXIT equals ±1.

**Metric threshold crossing (from below):**

CROSS*UP*{M,i,t,θ} = I{M*{i,t} ≥ θ} × I{M*{i,t-1} < θ} = 1 (crossed above threshold θ today).

**Metric threshold crossing (from above):**

CROSS*DOWN*{M,i,t,θ} = I{M*{i,t} ≤ θ} × I{M*{i,t-1} > θ} = 1 (crossed below threshold θ today).

**Composite score threshold:**

SCORE*ALERT*{i,t} = I{SCORE*{i,t} ≥ θ_up} (crossed above) or I{SCORE*{i,t} ≤ θ_down} (crossed below).

**Percentile rank shift:**

SHIFT*{M,i,t,N} = |UPCT*{M,i,t} - UPCT\_{M,i,t-N}| > Δ_threshold

where Δ_threshold is the user-set sensitivity (default: 20 percentile points over 5 days).

**Volume spike:**

VOL*SPIKE*{i,t,X} = I{VRATIO\_{i,t} > X} — volume exceeds X × 20-day average.

**Consecutive directional days:**

CONSEC*ALERT*{i,t,N} = I{|CONSEC\_{i,t}| ≥ N} — stock has moved in the same direction for N consecutive days.

**Fundamental change:**

FUND*CHANGE*{M,i,t,X} = I{|M*{i,t} / M*{i,t-252} - 1| > X} — any quarterly fundamental metric changed by more than X% year-over-year (detected when a new filing arrives with filing_date = t).

---

### Step 3 — Alert log

For each alert fired at date t for ticker i under rule R_k:

LOG*{i,t,k} = {ticker: i, date: t, rule: R_k, trigger_value: M*{i,t} or SCORE*{i,t}, prior_value: M*{i,t-1}, alert_type: type_label}

Store all log entries in a chronological database. No deletion — historical alert records are permanent.

---

### Step 4 — Alert performance tracking

For each alert event LOG\_{i,t,k}:

Forward return over H ∈ {1, 5, 21} trading days following the alert:

R*{i,H|alert} = P*{i,t+H}^{adj} / P\_{i,t}^{adj} - 1

Over all historical alerts of type R_k:

Hit rate: HIT*{R_k,H} = #{alerts : R*{i,H|alert} > 0} / #{total alerts of type k}

Average forward return: μ*{R_k,H} = (1/N_alerts) × Σ R*{i,H|alert}

Benchmark-adjusted hit rate: HIT*{R_k,H}^{adj} = #{alerts : R*{i,H|alert} > R\_{B,H,t}} / #{total alerts of type k}

where R\_{B,H,t} is the benchmark return over the same H-day window starting at t.

These statistics constitute the alert's empirical predictive track record. A price-crosses-SMA-200 alert with HIT = 0.61 at H = 21 across 200 historical firings has a statistically meaningful track record. An alert with HIT = 0.49 is noise — the alert system makes this distinction explicit and ongoing.

---

### Step 5 — Watchlist monitor dashboard

For each ticker i in a watchlist, the monitoring dashboard displays at each date t:

Column = metric M, Row = ticker i, Cell = (M*{i,t}, UPCT*{M,i,t}, Δ = M*{i,t} - M*{i,t-1}).

Color coding per cell:

- Green: M\_{i,t} within user-set target range and improved from prior day.
- Red: M\_{i,t} outside user-set target range.
- Amber: M\_{i,t} within range but deteriorating vs. prior day.

Alert indicator: cell flashes when a threshold alert fired on date t for that metric-ticker pair.

---

### Data Map

| Series                             | Source                   | Identifier | Frequency |
| ---------------------------------- | ------------------------ | ---------- | --------- |
| Daily close prices and all metrics | Internal data layer      | Per ticker | Daily     |
| Screen membership evaluations      | Feature S1 filter engine | —          | Daily     |
| Alert log                          | Internal state storage   | —          | Daily     |
| Benchmark returns (SPY)            | yfinance                 | SPY        | Daily     |

---

## FEATURE S7 — COMPARATIVE RELATIVE VALUATION SCREENER

### What you are building mathematically

Four simultaneous valuation context dimensions for every metric and every ticker: absolute current value, cross-sectional universe percentile today, cross-sectional sector percentile today, and percentile within the ticker's own historical distribution over a user-selected lookback window. These four dimensions are computed and stored for every metric in the data layer, enabling filtering and ranking by any combination of absolute and relative value simultaneously.

---

### Step 1 — Own-history percentile construction

For each metric M, ticker i, and date t, with a lookback window of W trading days:

Define the own-history distribution as the set of all values the metric has taken for this specific ticker over the prior W days:

H*{M,i,t,W} = {M*{i,s} : s ∈ [t-W+1, t-1]} (excludes the current date t from the comparison set)

Own-history percentile:

OHPCT*{M,i,t,W} = #{s ∈ [t-W+1, t-1] : M*{i,s} < M\_{i,t}} / (W-1) × 100

Lookback windows: W ∈ {252, 756, 2520} days (1, 3, and 10 years of trading days).

For fundamental metrics, which update only quarterly: the "own history" is computed over all available quarterly filing dates within the window, not daily. The number of data points is typically 4–8 per year, so at least 4–8 quarters are required for a reliable own-history percentile.

For a stock that has traded for fewer than W days: use all available history and flag the percentile as "short history" (fewer than W observations).

---

### Step 2 — Four-dimension valuation display construction

For each metric M and ticker i at date t:

DIM1*{M,i,t} = M*{i,t} (absolute current value — the raw number)

DIM2*{M,i,t} = UPCT*{M,i,t} (universe percentile, 0–100, from Feature S1 Step 7)

DIM3*{M,i,t} = SPCT*{M,i,t} (sector percentile, 0–100)

DIM4*{M,i,t,W} = OHPCT*{M,i,t,W} (own-history percentile over window W, 0–100)

For valuation metrics (PE, PB, EV/EBITDA, etc.): invert all four dimensions before display so that higher display value = cheaper. DIM2_inverted = 100 - DIM2, etc. The raw value is shown on hover.

For profitability, growth, and momentum metrics: no inversion (higher = better already).

---

### Step 3 — Sector valuation landscape heatmap

At date t, construct an 11 × J matrix where rows = GICS sectors, columns = selected metrics:

SECTOR*LANDSCAPE[sector_c, M_j, t] = median_i∈sector_c (OHPCT*{M_j,i,t,W})

This gives the median own-history percentile for each metric-sector combination. The cell value answers: "Where does the typical stock in this sector trade relative to its own history on metric M?"

An entire sector at own-history valuation percentile 20 on EV/EBITDA is cheap relative to its own 10-year history — a sector-level valuation signal that is masked entirely by cross-sectional ranking (which would show the sector at 50th percentile relative to the current universe if the whole market has also cheapened).

---

### Step 4 — Own-history percentile time series (re-rating indicator)

For any ticker i and metric M over the past 252 trading days:

RE*RATING*{M,i,t} = {OHPCT\_{M,i,s,W} : s ∈ [t-251, t]}

A rising time series of OHPCT means the stock's metric (e.g., EV/EBITDA) is increasing relative to its own historical range — the stock is re-rating (expanding multiple). A falling series means de-rating (contracting multiple).

The slope of the own-history percentile series over the trailing 21 trading days:

RE*RATE_SLOPE*{M,i,t} = OLS slope of {OHPCT\_{M,i,s,W} : s ∈ [t-20, t]} on {s ∈ [t-20, t]}

Positive slope = re-rating (multiple expansion). Negative slope = de-rating. The slope expressed in percentile points per month (multiply daily slope by 21).

---

### Step 5 — Peer comparison table

For a user-selected ticker i_ref and a peer set P (user-defined list or all tickers in the same GICS industry group):

At date t, for each metric M:

PEER*BETTER*{M,i,t} = I{M*{i,t} > M*{i*ref,t}} for quality metrics, else I{M*{i,t} < M\_{i_ref,t}} for valuation metrics (sign convention: 1 = the peer is in a more favorable position than the reference ticker on metric M).

Color coding: green = peer is better than reference on this metric, red = reference is better.

The peer table gives the cross-sectional context for a single ticker across all metrics simultaneously — the standard fundamental peer comparison in investment banking equity research, reproduced here from public data sources.

---

### Data Map

| Series                                         | Source                                            | Identifier             | Frequency         |
| ---------------------------------------------- | ------------------------------------------------- | ---------------------- | ----------------- |
| All metric values with full history            | Internal data layer                               | Per metric, per ticker | Daily             |
| GICS sector and industry group classifications | yfinance                                          | `Ticker.info`          | Quarterly refresh |
| Own-history distributions                      | Computed internally from historical metric series | —                      | Daily rolling     |

---

## FEATURE S8 — SCREENER RESULT EXPORT AND INTEGRATION LAYER

### What you are building mathematically

A structured data export system that serializes any screen result set from Features S1–S7 into multiple downstream-compatible formats, with a daily differential change report, a scheduled re-run engine, and a static API endpoint per saved screen.

---

### Step 1 — Result serialization

For any screen result set F(S, t) at date t, the serialized record for each ticker i ∈ F(S, t) is:

RECORD*i = {
ticker: i,
date: t,
screen_name: S.name,
rank: rank of i in F(S,t) by sort metric,
sort_metric_value: SORT_METRIC*{i,t},
all*active_filter_metric_values: {M_k: M*{k,i,t} for k = 1,...,K},
universe*percentiles: {M_k: UPCT*{M*k,i,t} for k = 1,...,K},
sector_percentiles: {M_k: SPCT*{M*k,i,t} for k = 1,...,K},
sector: sector_i,
industry_group: industry_group_i,
market_cap: MCAP*{i,t},
composite*score: SCORE*{i,t} (if Feature S3 is active)
}

**CSV format:** One row per ticker. Column headers: all RECORD_i fields as tab-separated headers. Standard MIME type: text/csv.

**JSON format:** Array of RECORD_i objects. Standard MIME type: application/json.

**Plain ticker list:** One ticker symbol per line. Used for copy-paste into any external platform. Standard MIME type: text/plain.

---

### Step 2 — Change report (daily differential)

For a saved screen S, at date t compare F(S,t) against F(S,t-1):

ENTERED_t = {i : i ∈ F(S,t) and i ∉ F(S,t-1)}

EXITED_t = {i : i ∉ F(S,t) and i ∈ F(S,t-1)}

RANK*CHANGE_t = {i ∈ F(S,t) ∩ F(S,t-1) : |rank*{i,t} - rank\_{i,t-1}| > N_threshold}

where N_threshold is the user-set rank change sensitivity (default: 10 ranks).

The change report contains:

1. Header: screen name, date, total count (|F(S,t)|), entries (|ENTERED_t|), exits (|EXITED_t|).
2. ENTERED section: for each i ∈ ENTERED_t: ticker, all metric values, current rank.
3. EXITED section: for each i ∈ EXITED_t: ticker, all metric values as of t-1, which filter condition they now fail.
4. RANK_CHANGE section: for each i ∈ RANK_CHANGE_t: ticker, prior rank, current rank, signed change, change in sort metric value.

The change report is a compact summary — not the full screen result — designed for daily monitoring without re-reading the full table.

---

### Step 3 — Scheduled re-run engine

Each saved screen has a schedule configuration:

SCHEDULE_S = {
frequency: daily | weekly_day,
time: after_close (default 18:00 local time),
notify: email_list,
deliver: change_report_only | full_result | both
}

At each scheduled evaluation:

1. Execute Feature S1 Step 8 (filter evaluation engine) with current date T.
2. Serialize result using Step 1 above.
3. Compute change report vs. prior run using Step 2.
4. Deliver via the specified channel.

---

### Step 4 — Static screen API endpoint

Each saved named screen S generates a deterministic URL endpoint:

/api/screens/{screen_id}/result

The endpoint returns the most recently computed screen result as a JSON array of RECORD_i objects (from Step 1). The result is cached from the most recent after-close computation (updated once per trading day). The response includes a `computed_at` timestamp.

The endpoint requires no authentication within the platform but is rate-limited to 100 requests per hour per user session to prevent abuse.

The `screen_id` is a UUID generated at screen creation time and is stable across renames.

---

### Step 5 — Portfolio optimizer feed

When the user activates the portfolio optimizer integration:

1. F(S,t) is passed as the candidate universe U_candidate to the portfolio optimizer.
2. All metric values M\_{k,i,t} for i ∈ F(S,t) are passed as the covariate matrix for the optimizer's expected return model.
3. The composite score SCORE\_{i,t} (if Feature S3 is active) is passed as the alpha signal for the optimizer's expected return vector.

This integration feeds the screener output directly into a mean-variance or risk-parity portfolio construction step, making the screener a genuine front-end to a full portfolio management workflow.

---

### Data Map

| Series                            | Source                            | Identifier    | Frequency                |
| --------------------------------- | --------------------------------- | ------------- | ------------------------ |
| Screen result sets                | Feature S1–S7 computation engines | —             | Daily after market close |
| Change log (prior screen results) | Internal state storage            | Per screen ID | Daily                    |
| API endpoint cache                | Internal cache layer              | Per screen ID | Daily refresh            |

---

## MODULE INTEGRATION MAP

| Feature                         | Primary Input                                        | Primary Dependency                                     | Key Mathematical Objects                                                                                     |
| ------------------------------- | ---------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| S1. Core Multi-Factor Engine    | yfinance OHLCV + fundamentals                        | None — foundational                                    | SMA/EMA/RSI/MACD/ATR/ADX/BB; PE/PB/EV/EBITDA/ROE/ROA/GPA; UPCT/SPCT/IGPCT; F(S,t)                            |
| S2. Formula Builder             | Feature S1 field registry + Ken French factors       | Feature S1 required                                    | Expression grammar; compiled vectorized callable f; IC_k; ICIR; walk-forward backtest                        |
| S3. Composite Score Engine      | Feature S1 z-scores; Feature S2 IC history           | Feature S1 required; Vol Module regime signal optional | w*j IC-IR weights; SCORE*{i,t} = Σ w*j z_j; CONTRIB decomposition; N*{eff}                                   |
| S4. Academic Strategy Library   | Feature S1 fundamentals + returns                    | Feature S1 required                                    | F-Score binary signals; Z-Score linear model; MAGIC = EY*rank + ROC_rank; QMJ multi-composite; IC_m; ρ*{mm'} |
| S5. Screener Backtester         | Features S1–S4 screen results; yfinance full history | Features S1/S2/S3/S4 as screen source                  | Point-in-time F(S,τ); TO*τ; R*{p,h,τ}^{net}; MDD; PBO via Monte Carlo; IC_k walk-forward                     |
| S6. Alert Engine                | Feature S1 daily state snapshots                     | Feature S1 required                                    | ENTRY/EXIT events; CROSS_UP/DOWN; SHIFT; alert forward return HIT rate                                       |
| S7. Relative Valuation Screener | Feature S1 metric history                            | Feature S1 required                                    | OHPCT\_{M,i,t,W}; DIM1–DIM4 quad-display; SECTOR_LANDSCAPE; RE_RATE_SLOPE                                    |
| S8. Export and Integration      | Features S1–S7 result sets                           | All upstream features                                  | RECORD_i serialization; ENTERED/EXITED change diff; API endpoint; optimizer feed                             |

---

## MASTER DATA MANIFEST

| Data Series                                                                   | Source                        | Identifier / Code                | Used In                                 |
| ----------------------------------------------------------------------------- | ----------------------------- | -------------------------------- | --------------------------------------- |
| Daily adjusted OHLCV (all tickers)                                            | yfinance                      | Per ticker                       | S1, S2, S3, S4, S5, S6, S7, S8          |
| Raw (unadjusted) open, high, low, volume                                      | yfinance                      | Per ticker                       | S1 (gap, ATR, stochastic)               |
| Dividends per share (event series)                                            | yfinance                      | `Ticker.dividends`               | S1, S4                                  |
| Income statement — quarterly and annual                                       | yfinance                      | `Ticker.quarterly_financials`    | S1, S2, S4, S5                          |
| Balance sheet — quarterly and annual                                          | yfinance                      | `Ticker.quarterly_balance_sheet` | S1, S2, S4, S5                          |
| Cash flow statement — quarterly and annual                                    | yfinance                      | `Ticker.quarterly_cashflow`      | S1, S2, S4                              |
| Ticker metadata (sector, industry group, float, shares outstanding, exchange) | yfinance                      | `Ticker.info`                    | S1, S2, S3, S4, S7                      |
| ETF constituent lists (SPY, MDY, SLY)                                         | yfinance ETF holdings         | Static monthly update            | S1 universe construction                |
| Fama-French 5 Factors + Momentum (daily)                                      | Ken French Data Library       | F-F 5 Factors + Mom daily CSV    | S1 (IVOL), S2 (formula field), S3       |
| Risk-free rate (daily)                                                        | Ken French Data Library       | RF column in FF factors file     | S5 (Sharpe/Sortino), S3                 |
| SPY daily OHLCV (benchmark)                                                   | yfinance                      | SPY                              | S1 (beta, relative performance), S5     |
| VIX daily level                                                               | FRED                          | VIXCLS                           | S5 (regime-conditional performance), S6 |
| 2-year and 10-year US Treasury yields                                         | FRED                          | DGS2, DGS10                      | S5 (regime context)                     |
| Volatility Module output signals                                              | Platform internal pipeline    | —                                | S1 (vol_forecast_21d), S3 (regime)      |
| All computed technical and fundamental metrics                                | Platform internal computation | —                                | S2, S3, S6, S7, S8                      |
| **Total external data cost**                                                  |                               |                                  | **$0 / month**                          |
