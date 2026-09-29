That Portfolio Visualizer UI is a solid reference point. Clean left nav, white card surfaces, blue accent for charts, data-dense tables without feeling cluttered. Totally achievable and appropriate for Quant360. The "Holdings Based Style Analysis" table layout in image 2 is exactly the kind of output density you want for Feature 2 and Feature 3. Yes, build toward that aesthetic.

---


---

## REVISED DATA CATEGORIES — FINAL CLEAN LIST

---

Category 1: Daily OHLCV Price and Returns Data

What: daily open, high, low, adjusted close, volume for the full global multi-country universe. Adjusted close accounts for splits and dividends.

Source: yfinance bulk download via `yf.download()`. Free.

Used in: Features 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14.

Notes: global universe means you pull tickers from multiple exchanges. yfinance supports international tickers with the exchange suffix (e.g., RELIANCE.NS for NSE India, 7203.T for Toyota on Tokyo Stock Exchange). Returns must be computed in local currency and separately in USD using FX rates if you want a USD-normalized universe.

---

Category 2: Benchmark Index Returns

What: daily total return series for global benchmark indices used as comparison points in attribution and backtesting.

Source: yfinance. SPY for S&P 500, URTH for MSCI World, EEM for MSCI Emerging Markets, VEA for MSCI Developed ex-US. All free via yfinance.

Used in: Features 2, 3, 7, 10, 14.

---

Category 3: Non-Point-in-Time Fundamental Data

What: P/B ratio, EV/EBITDA, trailing P/E, ROE, ROA, gross margins, operating margins, revenue growth, earnings growth, total assets, total debt, book value per share, shares outstanding, market cap. All current snapshots applied historically — not point-in-time.

Source: yfinance `Ticker.info`, `Ticker.financials`, `Ticker.balance_sheet`, `Ticker.quarterly_financials`. Free. Coverage is good for large and mid cap globally, thinner for small cap internationally.

Used in: Features 1 (valuation spread gauges), 2 (characteristic-based exposure z-scores for Value, Quality, Profitability, Investment), 5 (factor characteristic ranks for IC decay), 7 (factor score construction for universe sort), 12 (factor DNA sector and return anatomy), 13 (return-characteristic divergence monitor).

Caveat applied to all outputs using this data: "Fundamental characteristics are sourced as current snapshots. Historical backtests using these characteristics contain lookahead bias and may overstate factor premiums."

---

Category 4: Pre-Built Factor Return Series (Ken French)

What and exact files:

`F-F_Research_Data_Factors_daily.CSV` — MKT-RF, SMB, HML, RF daily. Core FF3 plus T-bill.

`F-F_Research_Data_5_Factors_2x3_daily.CSV` — MKT-RF, SMB, HML, RMW, CMA, RF daily. FF5.

`F-F_Momentum_Factor_daily.CSV` — MOM factor daily.

`F-F_ST_Reversal_Factor_daily.CSV` — short-term reversal daily.

`F-F_LT_Reversal_Factor_daily.CSV` — long-term reversal daily.

`48_Industry_Portfolios_daily.CSV` — 48 industry portfolio returns daily. Used for sector-conditional IC decay.

`F-F_Research_Data_Factors.CSV` — monthly FF3. For monthly-frequency attribution.

`F-F_Research_Data_5_Factors_2x3.CSV` — monthly FF5.

Source: Kenneth French Data Library. Completely free.

Used in: Features 2, 3, 4, 5, 7, 8, 10, 14.

---

Category 5: Pre-Built Factor Return Series (AQR)

What and exact files:

`Betting Against Beta — Equity Factors` — BAB daily returns for US and international markets.

`The Devil in HML's Details — Factors Daily` — HML Devil daily. Better value factor than standard French HML because it uses current price not fiscal year-end price.

`Quality Minus Junk — Factors Monthly` — QMJ monthly only. No daily version published. Either use at monthly frequency or compute your own daily proxy from the fundamental data.

Source: AQR Data Library. Completely free.

Used in: Features 2 (extended factor model), 5 (BAB and QMJ decay), 8 (extended covariance matrix), 12 (factor DNA for QMJ classification).

---

Category 6: Risk-Free Rate

What: daily US 3-month T-bill rate.

Source: already included as the RF column in every Ken French daily factor file. No additional download needed.

Used in: Features 1, 5, 7, 8, 10.

---

Category 7: Macroeconomic and Regime Data

What: VIX daily close, US 2-year Treasury yield daily, US 10-year Treasury yield daily, Federal Funds Rate daily, CPI monthly.

Source: FRED API. All free. Series codes: VIXCLS, DGS2, DGS10, FEDFUNDS, CPIAUCSL. Python library `fredapi` makes this a single line per series.

Used in: Feature 4 (VIX threshold regime, yield curve slope regime, rate level classification for regime DNA), Feature 11 (macro variable inputs for macro-linked stress scenario mapping), Feature 12 (regime DNA bar showing factor returns across rate environments).

Note: these are US macro series. Since your universe is global, these serve as global risk proxies rather than local regime indicators. VIX is a reasonable global fear proxy. For a fully global regime model, the HMM and GMM methods in Feature 4 are the primary engines since they run directly on factor returns without needing country-specific macro data.

---

Category 8: Sector and Industry Classification

What: sector and industry classification for all tickers in the universe.

Source: yfinance `Ticker.info` fields `sector` and `industry`. Free. Current snapshot only, not historical. For international tickers, coverage is patchy — yfinance pulls from Yahoo Finance which has inconsistent sector tagging outside the US. Financial Modeling Prep free tier (`financialmodelingprep.com/api/v3/profile/{ticker}`) provides sector and country for global tickers with better international coverage at no cost.

Used in: Features 2 (sector-neutral exposure), 3 (Brinson-Fachler sector attribution), 5 (sector-conditional IC decay), 6 (crowding by sector breakdown), 7 (sector-neutral backtest, sector breakdown of long/short books), 12 (sector DNA chart), 14 (sector exposure in LP report).

---



Category 10: FX Rates (required for global universe, not in original spec)

What: daily USD exchange rates for every currency in your global universe. Required to convert local returns to a common currency for cross-country factor construction and portfolio analytics.

Source: yfinance FX tickers. Format is `EURUSD=X`, `GBPUSD=X`, `JPYUSD=X` etc. Free. Covers all major and most minor currency pairs going back 10 years.

Used in: Features 2 (country factor construction — you need to separate currency effects from style factor effects), 3 (USD-denominated P&L attribution), 7 (local return vs. USD return decomposition in backtest), 14 (currency exposure disclosure in LP report).

This category is new and critical. Without it your global universe factor ranks will be contaminated by currency momentum effects that have nothing to do with style factors.

---

Category 11: Approximate Bid-Ask Spread (Roll Estimator)

What: estimated daily bid-ask spread in bps per stock, computed from price data using the Roll (1984) formula: estimated spread equals 2 times the square root of the absolute value of the negative first-order autocovariance of daily close-to-close returns. Computed on a rolling 21-day window.

Source: derived entirely from the OHLCV data in Category 1. No additional data source needed. Pure computation.

Used in: Feature 6 (crowding metric — bid-ask spread trend of long book vs. short book), Feature 7 (timing cost component of implementation shortfall), Feature 9 (round-trip cost in capacity curve). All outputs using this label as "estimated via Roll approximation."

---

## TOTAL COST OF REVISED DATA STACK

yfinance: free. Ken French Data Library: free. AQR Data Library: free. FRED API: free. Financial Modeling Prep free tier (sector classification supplement): free.

Total: zero dollars per month.